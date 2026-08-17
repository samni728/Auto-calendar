#!/usr/bin/env bash

set -uo pipefail

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SERVER_DIR="$PROJECT_DIR/server"
WEB_DIR="$PROJECT_DIR/web"
ENV_FILE="$PROJECT_DIR/.env"
RUNTIME_DIR="$PROJECT_DIR/.runtime/source"
VENV_DIR="$PROJECT_DIR/.venv"
PID_DIR="$RUNTIME_DIR/pids"
LOG_DIR="$RUNTIME_DIR/logs"
API_PID_FILE="$PID_DIR/api.pid"
WEB_PID_FILE="$PID_DIR/web.pid"
API_LOG="$LOG_DIR/api.log"
WEB_LOG="$LOG_DIR/web.log"
DEPENDENCIES_MARKER="$RUNTIME_DIR/.dependencies-ready"

if [[ -t 1 ]]; then
  BLUE='\033[0;34m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'
  RED='\033[0;31m'; BOLD='\033[1m'; RESET='\033[0m'
else
  BLUE=''; GREEN=''; YELLOW=''; RED=''; BOLD=''; RESET=''
fi

info() { printf "%b\n" "${BLUE}ℹ ${RESET}$*"; }
success() { printf "%b\n" "${GREEN}✓ ${RESET}$*"; }
warn() { printf "%b\n" "${YELLOW}⚠ ${RESET}$*"; }
error() { printf "%b\n" "${RED}✗ ${RESET}$*" >&2; }

print_header() {
  printf "\n%b\n" "${BOLD}Auto Calendar · 源码运行管理菜单${RESET}"
  printf "%s\n" "项目目录：$PROJECT_DIR"
  printf "%s\n\n" "运行方式：FastAPI + Next.js（不使用 Docker）"
}

pause_menu() {
  if [[ -t 0 ]]; then
    printf "\n"
    read -r -p "按 Enter 返回菜单…" _
  fi
}

find_python() {
  local candidate version major minor
  for candidate in python3.12 python3.13 python3.14 python3; do
    command -v "$candidate" >/dev/null 2>&1 || continue
    version="$($candidate -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    major="${version%%.*}"; minor="${version##*.}"
    if (( major > 3 || (major == 3 && minor >= 12) )); then
      printf "%s" "$candidate"
      return 0
    fi
  done
  return 1
}

check_base_dependencies() {
  if ! SOURCE_PYTHON="$(find_python)"; then
    error "需要 Python 3.12 或更高版本。"
    return 1
  fi
  if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    error "需要 Node.js 22 或更高版本以及 npm。"
    return 1
  fi
  local node_major
  node_major="$(node -p 'process.versions.node.split(".")[0]')"
  if (( node_major < 22 )); then
    error "当前 Node.js 版本过低，需要 22 或更高版本。"
    return 1
  fi
  export SOURCE_PYTHON
}

ensure_environment() {
  if [[ -f "$ENV_FILE" ]]; then
    return 0
  fi
  check_base_dependencies || return 1
  warn "尚未发现 .env，正在生成本地开发配置。"
  local encryption_key admin_password db_password
  encryption_key="$($SOURCE_PYTHON -c 'import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"
  admin_password="$($SOURCE_PYTHON -c 'import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(24)).decode())')"
  db_password="$($SOURCE_PYTHON -c 'import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(24)).decode())')"
  sed \
    -e "s|replace-with-a-long-random-password|$admin_password|" \
    -e "s|replace-with-a-fernet-key|$encryption_key|" \
    -e "s|replace-with-a-random-password|$db_password|" \
    "$PROJECT_DIR/.env.example" > "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  success "已生成 .env；初始管理员密码保存在该文件中。"
}

load_environment() {
  ensure_environment || return 1
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  SOURCE_API_PORT="${SOURCE_API_PORT:-8000}"
  SOURCE_WEB_PORT="${SOURCE_WEB_PORT:-${APP_PORT:-8080}}"
  if [[ -n "${SOURCE_DATABASE_URL:-}" ]]; then
    DATABASE_URL="$SOURCE_DATABASE_URL"
    SOURCE_DATABASE_LABEL="自定义数据库（连接信息已隐藏）"
  elif [[ -z "${DATABASE_URL:-}" || "$DATABASE_URL" == *"@postgres:"* ]]; then
    DATABASE_URL="sqlite+pysqlite:///$RUNTIME_DIR/autocalendar.db"
    SOURCE_DATABASE_LABEL="SQLite · $RUNTIME_DIR/autocalendar.db"
  elif [[ "$DATABASE_URL" == "sqlite+pysqlite:///$RUNTIME_DIR/autocalendar.db" ]]; then
    SOURCE_DATABASE_LABEL="SQLite · $RUNTIME_DIR/autocalendar.db"
  else
    SOURCE_DATABASE_LABEL="自定义数据库（连接信息已隐藏）"
  fi
  PUBLIC_BASE_URL="${SOURCE_PUBLIC_BASE_URL:-http://localhost:$SOURCE_WEB_PORT}"
  CORS_ORIGINS="${SOURCE_CORS_ORIGINS:-$PUBLIC_BASE_URL}"
  if [[ "$PUBLIC_BASE_URL" == http://localhost:* || "$PUBLIC_BASE_URL" == http://127.0.0.1:* ]]; then
    SESSION_COOKIE_SECURE=false
  fi
  export DATABASE_URL PUBLIC_BASE_URL CORS_ORIGINS SESSION_COOKIE_SECURE
  export SOURCE_API_PORT SOURCE_WEB_PORT SOURCE_DATABASE_LABEL
}

install_dependencies() {
  check_base_dependencies || return 1
  ensure_environment || return 1
  mkdir -p "$PID_DIR" "$LOG_DIR"
  info "正在准备 Python 虚拟环境…"
  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    if command -v uv >/dev/null 2>&1; then
      uv venv --python "$SOURCE_PYTHON" "$VENV_DIR" || return 1
    else
      "$SOURCE_PYTHON" -m venv "$VENV_DIR" || return 1
    fi
  fi
  if command -v uv >/dev/null 2>&1; then
    uv pip install --python "$VENV_DIR/bin/python" -e "$SERVER_DIR" || return 1
  else
    "$VENV_DIR/bin/python" -m pip install -e "$SERVER_DIR" || return 1
  fi
  info "正在安装 WebUI 依赖…"
  (cd "$WEB_DIR" && npm ci) || return 1
  touch "$DEPENDENCIES_MARKER"
  success "源码运行依赖已安装。"
}

ensure_dependencies() {
  if [[ -f "$DEPENDENCIES_MARKER" && -x "$VENV_DIR/bin/python" && -x "$WEB_DIR/node_modules/.bin/next" ]]; then
    return 0
  fi
  warn "首次源码运行需要安装依赖。"
  install_dependencies
}

pid_from_file() {
  local pid_file="$1" pid=""
  [[ -f "$pid_file" ]] && read -r pid < "$pid_file"
  [[ "$pid" =~ ^[0-9]+$ ]] && printf "%s" "$pid"
}

is_running() {
  local pid command_line
  pid="$(pid_from_file "$1")"
  [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1 || return 1
  command_line="$(ps -ww -p "$pid" -o command= 2>/dev/null)"
  case "$1" in
    "$API_PID_FILE") [[ "$command_line" == *"-m uvicorn app.main:app"* ]] ;;
    "$WEB_PID_FILE") [[ "$command_line" == *"$WEB_DIR/node_modules/.bin/next"* && "$command_line" == *"next dev"* ]] ;;
    *) return 1 ;;
  esac
}

port_owner() {
  command -v lsof >/dev/null 2>&1 || return 0
  lsof -nP -tiTCP:"$1" -sTCP:LISTEN 2>/dev/null | head -n 1
}

check_port_available() {
  local port="$1" service="$2" owner
  owner="$(port_owner "$port")"
  if [[ -n "$owner" ]]; then
    error "$service 端口 $port 已被进程 $owner 占用。"
    if [[ "$port" == "${APP_PORT:-8080}" ]]; then
      warn "如果 Docker 版本仍在运行，请先执行：./scripts/manage.sh stop"
    fi
    return 1
  fi
}

run_migrations() {
  load_environment || return 1
  ensure_dependencies || return 1
  mkdir -p "$LOG_DIR"
  info "正在执行数据库迁移（${SOURCE_DATABASE_LABEL}）…"
  if (cd "$SERVER_DIR" && "$VENV_DIR/bin/python" -m alembic upgrade head) >> "$API_LOG" 2>&1; then
    success "数据库迁移完成。"
  else
    error "数据库迁移失败，请查看 API 日志。"
    tail -n 30 "$API_LOG" 2>/dev/null || true
    return 1
  fi
}

wait_for_url() {
  local url="$1"
  for _ in {1..30}; do
    curl -fsS "$url" >/dev/null 2>&1 && return 0
    sleep 1
  done
  return 1
}

start_services() {
  load_environment || return 1
  ensure_dependencies || return 1
  mkdir -p "$PID_DIR" "$LOG_DIR"
  if is_running "$API_PID_FILE" || is_running "$WEB_PID_FILE"; then
    warn "源码服务已经部分或全部运行，请先查看状态或执行重启。"
    show_status
    return 0
  fi
  check_port_available "$SOURCE_API_PORT" "FastAPI" || return 1
  check_port_available "$SOURCE_WEB_PORT" "WebUI" || return 1
  run_migrations || return 1
  info "正在启动 FastAPI…"
  (
    cd "$SERVER_DIR"
    nohup "$VENV_DIR/bin/python" -m uvicorn app.main:app --host 127.0.0.1 --port "$SOURCE_API_PORT" >> "$API_LOG" 2>&1 < /dev/null &
    printf "%s\n" "$!" > "$API_PID_FILE"
  )
  if ! wait_for_url "http://127.0.0.1:$SOURCE_API_PORT/healthz"; then
    error "FastAPI 启动失败。"
    tail -n 30 "$API_LOG" 2>/dev/null || true
    stop_services >/dev/null 2>&1 || true
    return 1
  fi
  info "正在启动 Next.js WebUI…"
  (
    cd "$WEB_DIR"
    export API_PROXY_TARGET="http://127.0.0.1:$SOURCE_API_PORT"
    nohup "$WEB_DIR/node_modules/.bin/next" dev --webpack --hostname 127.0.0.1 --port "$SOURCE_WEB_PORT" >> "$WEB_LOG" 2>&1 < /dev/null &
    printf "%s\n" "$!" > "$WEB_PID_FILE"
  )
  if ! wait_for_url "http://127.0.0.1:$SOURCE_WEB_PORT"; then
    error "WebUI 启动失败。"
    tail -n 30 "$WEB_LOG" 2>/dev/null || true
    stop_services >/dev/null 2>&1 || true
    return 1
  fi
  success "源码服务已启动：http://localhost:$SOURCE_WEB_PORT"
  show_status
}

stop_one() {
  local name="$1" pid_file="$2" pid
  pid="$(pid_from_file "$pid_file")"
  if [[ -z "$pid" || ! -e "$pid_file" ]]; then
    return 0
  fi
  if is_running "$pid_file"; then
    info "正在停止 ${name}（PID ${pid}）…"
    kill "$pid" >/dev/null 2>&1 || true
    for _ in {1..20}; do
      kill -0 "$pid" >/dev/null 2>&1 || break
      sleep 0.25
    done
    if kill -0 "$pid" >/dev/null 2>&1; then
      warn "$name 未正常退出，正在强制停止。"
      kill -KILL "$pid" >/dev/null 2>&1 || true
    fi
  fi
  rm -f "$pid_file"
}

stop_services() {
  stop_one "WebUI" "$WEB_PID_FILE"
  stop_one "FastAPI" "$API_PID_FILE"
  success "源码服务已停止；SQLite 数据和日志均已保留。"
}

restart_services() {
  stop_services
  start_services
}

status_line() {
  local name="$1" pid_file="$2" pid
  pid="$(pid_from_file "$pid_file")"
  if [[ -n "$pid" ]] && is_running "$pid_file"; then
    printf "  %-10s %b（PID %s）\n" "$name" "${GREEN}运行中${RESET}" "$pid"
  else
    printf "  %-10s %b\n" "$name" "${YELLOW}未运行${RESET}"
  fi
}

show_status() {
  load_environment || return 1
  printf "\n"
  status_line "FastAPI" "$API_PID_FILE"
  status_line "WebUI" "$WEB_PID_FILE"
  printf "\n  访问地址   http://localhost:%s\n" "$SOURCE_WEB_PORT"
  printf "  API 地址   http://127.0.0.1:%s\n" "$SOURCE_API_PORT"
  printf "  数据库     %s\n" "$SOURCE_DATABASE_LABEL"
  printf "  日志目录   %s\n" "$LOG_DIR"
}

follow_logs() {
  local service="${1:-all}"
  mkdir -p "$LOG_DIR"
  touch "$API_LOG" "$WEB_LOG"
  trap 'true' INT
  case "$service" in
    api) info "正在查看 API 实时日志；按 Ctrl+C 返回。"; tail -n 200 -f "$API_LOG" || true ;;
    web) info "正在查看 WebUI 实时日志；按 Ctrl+C 返回。"; tail -n 200 -f "$WEB_LOG" || true ;;
    all|"") info "正在查看全部实时日志；按 Ctrl+C 返回。"; tail -n 200 -f "$API_LOG" "$WEB_LOG" || true ;;
    *) error "未知日志类型：${service}（可选：all、api、web）"; trap - INT; return 2 ;;
  esac
  trap - INT
}

logs_menu() {
  printf "\n选择日志范围：\n  1) 全部服务\n  2) API 后端\n  3) Web UI\n  0) 返回\n\n"
  local choice
  read -r -p "请输入编号：" choice
  case "$choice" in
    1) follow_logs all ;; 2) follow_logs api ;; 3) follow_logs web ;; 0) return 0 ;; *) warn "无效编号。" ;;
  esac
}

print_help() {
  cat <<'EOF'
用法：
  ./scripts/manage-source.sh                 打开交互菜单
  ./scripts/manage-source.sh install         安装/更新 Python 与 Node 依赖
  ./scripts/manage-source.sh start           启动源码服务
  ./scripts/manage-source.sh stop            停止源码服务
  ./scripts/manage-source.sh restart         重启源码服务
  ./scripts/manage-source.sh status          查看运行状态
  ./scripts/manage-source.sh logs [api|web]  查看实时日志
  ./scripts/manage-source.sh migrate         执行数据库迁移

源码模式默认使用 .runtime/source/autocalendar.db（SQLite）。
如需本地 PostgreSQL，请在 .env 设置 SOURCE_DATABASE_URL。
EOF
}

run_command() {
  case "${1:-}" in
    install|setup) install_dependencies ;; start) start_services ;; stop) stop_services ;;
    restart) restart_services ;; status|ps) show_status ;; logs) follow_logs "${2:-all}" ;;
    migrate) run_migrations ;; help|-h|--help) print_help ;;
    *) error "未知命令：${1:-}"; print_help; return 2 ;;
  esac
}

interactive_menu() {
  while true; do
    print_header
    printf "  1) 启动源码服务\n  2) 安装 / 更新依赖\n  3) 停止源码服务\n"
    printf "  4) 重启源码服务\n  5) 查看运行状态\n  6) 查看实时日志\n"
    printf "  7) 执行数据库迁移\n  0) 退出\n\n"
    local choice
    read -r -p "请输入编号：" choice || { printf "\n"; return 0; }
    printf "\n"
    case "$choice" in
      1) start_services; pause_menu ;; 2) install_dependencies; pause_menu ;;
      3) stop_services; pause_menu ;; 4) restart_services; pause_menu ;;
      5) show_status; pause_menu ;; 6) logs_menu ;; 7) run_migrations; pause_menu ;;
      0) success "已退出源码管理菜单。"; return 0 ;;
      *) warn "请输入 0–7 之间的编号。"; pause_menu ;;
    esac
  done
}

if [[ $# -gt 0 ]]; then
  run_command "$@"
else
  interactive_menu
fi

#!/usr/bin/env bash

set -uo pipefail

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE=(docker compose --project-directory "$PROJECT_DIR" -f "$PROJECT_DIR/docker-compose.yml")

if [[ -t 1 ]]; then
  BLUE='\033[0;34m'
  GREEN='\033[0;32m'
  YELLOW='\033[0;33m'
  RED='\033[0;31m'
  BOLD='\033[1m'
  RESET='\033[0m'
else
  BLUE=''
  GREEN=''
  YELLOW=''
  RED=''
  BOLD=''
  RESET=''
fi

info() { printf "%b\n" "${BLUE}ℹ ${RESET}$*"; }
success() { printf "%b\n" "${GREEN}✓ ${RESET}$*"; }
warn() { printf "%b\n" "${YELLOW}⚠ ${RESET}$*"; }
error() { printf "%b\n" "${RED}✗ ${RESET}$*" >&2; }

print_header() {
  printf "\n%b\n" "${BOLD}Auto Calendar · Docker 管理菜单${RESET}"
  printf "%s\n\n" "项目目录：$PROJECT_DIR"
}

pause_menu() {
  if [[ -t 0 ]]; then
    printf "\n"
    read -r -p "按 Enter 返回菜单…" _
  fi
}

check_dependencies() {
  if ! command -v docker >/dev/null 2>&1; then
    error "没有找到 Docker。请先安装 Docker Desktop 或 Docker Engine。"
    return 1
  fi
  if ! docker compose version >/dev/null 2>&1; then
    error "没有找到 Docker Compose v2。"
    return 1
  fi
}

ensure_docker_running() {
  check_dependencies || return 1
  if docker info >/dev/null 2>&1; then
    return 0
  fi

  if [[ "$(uname -s)" == "Darwin" ]] && command -v open >/dev/null 2>&1; then
    warn "Docker Desktop 尚未运行，正在尝试启动…"
    open -a Docker >/dev/null 2>&1 || true
    for _ in {1..20}; do
      if docker info >/dev/null 2>&1; then
        success "Docker 已就绪。"
        return 0
      fi
      sleep 2
    done
  fi

  error "Docker daemon 未运行。请启动 Docker Desktop 后重试。"
  return 1
}

ensure_environment() {
  if [[ -f "$PROJECT_DIR/.env" ]]; then
    return 0
  fi

  warn "尚未发现 .env，需要先生成本地密钥和初始管理员密码。"
  if [[ ! -t 0 ]]; then
    error "请先运行：./scripts/bootstrap.sh"
    return 1
  fi

  local answer
  read -r -p "现在运行初始化脚本？[Y/n] " answer
  if [[ -z "$answer" || "$answer" =~ ^[Yy]$ ]]; then
    "$PROJECT_DIR/scripts/bootstrap.sh"
    return $?
  fi
  return 1
}

app_port() {
  local configured=""
  if [[ -f "$PROJECT_DIR/.env" ]]; then
    configured="$(sed -n 's/^APP_PORT=//p' "$PROJECT_DIR/.env" | tail -n 1)"
  fi
  printf "%s" "${configured:-8080}"
}

start_stack() {
  ensure_docker_running || return 1
  ensure_environment || return 1
  info "正在启动 Auto Calendar…"
  if "${COMPOSE[@]}" up -d; then
    success "启动完成：http://localhost:$(app_port)"
    "${COMPOSE[@]}" ps
  else
    error "启动失败，请通过日志菜单查看原因。"
    return 1
  fi
}

build_and_start() {
  ensure_docker_running || return 1
  ensure_environment || return 1
  info "正在重新构建并启动，首次构建可能需要几分钟…"
  if "${COMPOSE[@]}" up -d --build; then
    success "构建并启动完成：http://localhost:$(app_port)"
    "${COMPOSE[@]}" ps
  else
    error "构建或启动失败。"
    return 1
  fi
}

stop_stack() {
  ensure_docker_running || return 1
  info "正在停止容器（数据和容器都会保留）…"
  if "${COMPOSE[@]}" stop; then
    success "Auto Calendar 已停止。"
  else
    error "停止失败。"
    return 1
  fi
}

restart_stack() {
  ensure_docker_running || return 1
  ensure_environment || return 1
  info "正在重启 Auto Calendar…"
  if "${COMPOSE[@]}" restart; then
    success "重启完成。"
    "${COMPOSE[@]}" ps
  else
    error "重启失败；如果容器尚未创建，请先选择启动。"
    return 1
  fi
}

down_stack() {
  ensure_docker_running || return 1
  warn "这会停止并移除应用容器和网络，但保留 PostgreSQL 数据卷。"
  if [[ -t 0 ]]; then
    local answer
    read -r -p "确认继续？[y/N] " answer
    [[ "$answer" =~ ^[Yy]$ ]] || { info "已取消。"; return 0; }
  fi
  if "${COMPOSE[@]}" down; then
    success "容器和网络已移除，数据库卷仍然保留。"
  else
    error "关闭失败。"
    return 1
  fi
}

show_status() {
  ensure_docker_running || return 1
  "${COMPOSE[@]}" ps -a
}

follow_logs() {
  local service="${1:-}"
  ensure_docker_running || return 1
  trap 'true' INT
  if [[ -n "$service" ]]; then
    info "正在查看 $service 实时日志；按 Ctrl+C 停止查看。"
    "${COMPOSE[@]}" logs --tail=200 --follow "$service" || true
  else
    info "正在查看全部实时日志；按 Ctrl+C 停止查看。"
    "${COMPOSE[@]}" logs --tail=200 --follow || true
  fi
  trap - INT
}

logs_menu() {
  printf "\n选择日志范围：\n"
  printf "  1) 全部服务\n"
  printf "  2) API 后端\n"
  printf "  3) Web UI\n"
  printf "  4) Nginx 网关\n"
  printf "  5) PostgreSQL\n"
  printf "  6) Cloudflare Tunnel\n"
  printf "  0) 返回\n\n"
  local choice
  read -r -p "请输入编号：" choice
  case "$choice" in
    1) follow_logs ;;
    2) follow_logs api ;;
    3) follow_logs web ;;
    4) follow_logs gateway ;;
    5) follow_logs postgres ;;
    6) follow_logs cloudflared ;;
    0) return 0 ;;
    *) warn "无效编号。" ;;
  esac
}

start_cloudflare() {
  ensure_docker_running || return 1
  ensure_environment || return 1
  local token
  token="$(sed -n 's/^CLOUDFLARE_TUNNEL_TOKEN=//p' "$PROJECT_DIR/.env" | tail -n 1)"
  if [[ -z "$token" ]]; then
    error "CLOUDFLARE_TUNNEL_TOKEN 尚未配置，请先编辑 .env。"
    return 1
  fi
  if "${COMPOSE[@]}" --profile cloudflare up -d cloudflared; then
    success "Cloudflare Tunnel 已启动。"
  else
    error "Cloudflare Tunnel 启动失败。"
    return 1
  fi
}

print_help() {
  cat <<'EOF'
用法：
  ./scripts/manage.sh                 打开交互菜单
  ./scripts/manage.sh start           启动服务
  ./scripts/manage.sh build           重新构建并启动
  ./scripts/manage.sh stop            停止服务并保留容器
  ./scripts/manage.sh restart         重启服务
  ./scripts/manage.sh down            移除容器和网络，保留数据库卷
  ./scripts/manage.sh status          查看容器状态
  ./scripts/manage.sh logs [service]  查看实时日志
  ./scripts/manage.sh cloudflare      启动 Cloudflare Tunnel profile
EOF
}

run_command() {
  case "${1:-}" in
    start) start_stack ;;
    build|rebuild) build_and_start ;;
    stop) stop_stack ;;
    restart) restart_stack ;;
    down) down_stack ;;
    status|ps) show_status ;;
    logs) follow_logs "${2:-}" ;;
    cloudflare) start_cloudflare ;;
    help|-h|--help) print_help ;;
    *) error "未知命令：${1:-}"; print_help; return 2 ;;
  esac
}

interactive_menu() {
  while true; do
    print_header
    printf "  1) 启动服务\n"
    printf "  2) 重新构建并启动\n"
    printf "  3) 停止服务\n"
    printf "  4) 重启服务\n"
    printf "  5) 查看运行状态\n"
    printf "  6) 查看实时日志\n"
    printf "  7) 启动 Cloudflare Tunnel\n"
    printf "  8) 关闭并移除容器（保留数据）\n"
    printf "  0) 退出\n\n"

    local choice
    read -r -p "请输入编号：" choice || { printf "\n"; return 0; }
    printf "\n"
    case "$choice" in
      1) start_stack; pause_menu ;;
      2) build_and_start; pause_menu ;;
      3) stop_stack; pause_menu ;;
      4) restart_stack; pause_menu ;;
      5) show_status; pause_menu ;;
      6) logs_menu ;;
      7) start_cloudflare; pause_menu ;;
      8) down_stack; pause_menu ;;
      0) success "已退出管理菜单。"; return 0 ;;
      *) warn "请输入 0–8 之间的编号。"; pause_menu ;;
    esac
  done
}

if [[ $# -gt 0 ]]; then
  run_command "$@"
else
  interactive_menu
fi

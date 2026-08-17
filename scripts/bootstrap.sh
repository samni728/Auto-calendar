#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ENV_FILE="$PROJECT_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
  ENCRYPTION_KEY=$(python3 -c 'import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')
  ADMIN_PASSWORD=$(openssl rand -base64 24 | tr -d '\n')
  DB_PASSWORD=$(openssl rand -base64 24 | tr -d '\n')
  sed \
    -e "s|replace-with-a-long-random-password|$ADMIN_PASSWORD|" \
    -e "s|replace-with-a-fernet-key|$ENCRYPTION_KEY|" \
    -e "s|replace-with-a-random-password|$DB_PASSWORD|" \
    "$PROJECT_DIR/.env.example" > "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "已生成 .env 与随机初始密码。"
else
  echo ".env 已存在，保留现有配置。"
fi

docker compose --project-directory "$PROJECT_DIR" up -d --build
echo "Auto Calendar 正在启动：http://localhost:8080"
echo "管理员邮箱：$(sed -n 's/^INITIAL_ADMIN_EMAIL=//p' "$ENV_FILE")"
echo "初始密码请查看：$ENV_FILE"

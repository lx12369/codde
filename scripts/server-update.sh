#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/www/wwwroot/codde}"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIST_DIR="$PROJECT_ROOT/frontend/dist"
VENV_PYTHON="$BACKEND_DIR/.venv/bin/python"
GUNICORN_BIN="$BACKEND_DIR/.venv/bin/gunicorn"
GUNICORN_LOG="${GUNICORN_LOG:-/tmp/codde-backend.log}"
GUNICORN_BIND="${GUNICORN_BIND:-127.0.0.1:5000}"

echo "[1/5] Checking runtime files"
test -d "$PROJECT_ROOT"
test -d "$FRONTEND_DIST_DIR"
test -f "$BACKEND_DIR/.env"
test -x "$VENV_PYTHON"
test -x "$GUNICORN_BIN"

echo "[2/5] Fixing ownership"
sudo chown -R admin:admin "$PROJECT_ROOT"
mkdir -p "$BACKEND_DIR/instance"

echo "[3/5] Stopping existing gunicorn"
pkill -f gunicorn || true
sleep 2

echo "[4/5] Starting backend"
cd "$BACKEND_DIR"
nohup "$GUNICORN_BIN" -w 2 -b "$GUNICORN_BIND" "app:create_app('production')" >"$GUNICORN_LOG" 2>&1 &
sleep 5

echo "[5/5] Verifying backend"
pgrep -af gunicorn
tail -n 30 "$GUNICORN_LOG" || true
curl -s \
  -o /tmp/codde-login-check.json \
  -w "login_api_status=%{http_code}\n" \
  -H "Content-Type: application/json" \
  -d '{}' \
  "http://$GUNICORN_BIND/api/auth/login"
cat /tmp/codde-login-check.json || true
echo
"$VENV_PYTHON" -c "from app import create_app; app = create_app('production'); print(app.config['SQLALCHEMY_DATABASE_URI'])"

echo "Server restart complete."

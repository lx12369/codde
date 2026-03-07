#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/www/wwwroot/codde}"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIST_DIR="$PROJECT_ROOT/frontend/dist"
VENV_PYTHON="$BACKEND_DIR/.venv/bin/python"
GUNICORN_BIN="$BACKEND_DIR/.venv/bin/gunicorn"
GUNICORN_LOG="${GUNICORN_LOG:-/tmp/codde-backend.log}"
GUNICORN_BIND="${GUNICORN_BIND:-127.0.0.1:5000}"
LOCK_DIR="${LOCK_DIR:-/tmp/codde-server-update.lock}"
START_TIMEOUT_SECONDS="${START_TIMEOUT_SECONDS:-30}"
STOP_TIMEOUT_SECONDS="${STOP_TIMEOUT_SECONDS:-20}"
LOGIN_CHECK_URL="${LOGIN_CHECK_URL:-http://$GUNICORN_BIND/api/auth/login}"
LOGIN_CHECK_BODY_FILE="${LOGIN_CHECK_BODY_FILE:-/tmp/codde-login-check.json}"
APP_MODULE="${APP_MODULE:-app:create_app('production')}"
GUNICORN_MATCH="${GUNICORN_MATCH:-$BACKEND_DIR/.venv/bin/gunicorn}"

wait_for_port_state() {
  local target_state="$1"
  local timeout_seconds="$2"
  local elapsed=0
  local port="${GUNICORN_BIND##*:}"

  while (( elapsed < timeout_seconds )); do
    local listening=0

    if ss -ltn "( sport = :$port )" 2>/dev/null | grep -q LISTEN; then
      listening=1
    fi

    if [[ "$target_state" == "free" && "$listening" -eq 0 ]]; then
      return 0
    fi

    if [[ "$target_state" == "listening" && "$listening" -eq 1 ]]; then
      return 0
    fi

    sleep 1
    elapsed=$((elapsed + 1))
  done

  return 1
}

cleanup_lock() {
  rm -rf "$LOCK_DIR"
}

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "Another update is already running: $LOCK_DIR" >&2
  exit 1
fi

trap cleanup_lock EXIT

echo "[1/5] Checking runtime files"
test -d "$PROJECT_ROOT"
test -d "$FRONTEND_DIST_DIR"
test -f "$BACKEND_DIR/.env"
test -x "$VENV_PYTHON"
test -x "$GUNICORN_BIN"

echo "[2/5] Fixing ownership"
sudo chown -R admin:admin "$PROJECT_ROOT"
mkdir -p "$BACKEND_DIR/instance"
touch "$GUNICORN_LOG"
sudo chown admin:admin "$GUNICORN_LOG"

echo "[3/5] Stopping existing gunicorn"
pkill -f "$GUNICORN_MATCH" || true

if ! wait_for_port_state free "$STOP_TIMEOUT_SECONDS"; then
  echo "Graceful stop timed out, forcing gunicorn shutdown" >&2
  pkill -9 -f "$GUNICORN_MATCH" || true
  wait_for_port_state free 5 || {
    echo "Port $GUNICORN_BIND is still in use after forced stop" >&2
    ss -ltnp | grep "${GUNICORN_BIND##*:}" || true
    exit 1
  }
fi

echo "[4/5] Starting backend"
cd "$BACKEND_DIR"
nohup "$GUNICORN_BIN" -w 2 -b "$GUNICORN_BIND" "$APP_MODULE" >"$GUNICORN_LOG" 2>&1 &

if ! wait_for_port_state listening "$START_TIMEOUT_SECONDS"; then
  echo "Backend did not bind to $GUNICORN_BIND in time" >&2
  tail -n 50 "$GUNICORN_LOG" || true
  exit 1
fi

echo "[5/5] Verifying backend"
backend_ready=0
rm -f "$LOGIN_CHECK_BODY_FILE"

for _ in $(seq 1 "$START_TIMEOUT_SECONDS"); do
  status_code="$(
    curl -s \
      -o "$LOGIN_CHECK_BODY_FILE" \
      -w "%{http_code}" \
      -H "Content-Type: application/json" \
      -d '{}' \
      "$LOGIN_CHECK_URL" || true
  )"

  if [[ "$status_code" == "400" ]]; then
    backend_ready=1
    break
  fi

  sleep 1
done

pgrep -af gunicorn || true
tail -n 30 "$GUNICORN_LOG" || true
echo "login_api_status=${status_code:-000}"
if [[ -f "$LOGIN_CHECK_BODY_FILE" ]]; then
  cat "$LOGIN_CHECK_BODY_FILE"
fi
echo

if [[ "$backend_ready" -ne 1 ]]; then
  echo "Backend verification failed" >&2
  exit 1
fi

"$VENV_PYTHON" -c "from app import create_app; app = create_app('production'); print(app.config['SQLALCHEMY_DATABASE_URI'])"

echo "Server restart complete."

#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/www/wwwroot/codde"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
BACKEND_DIR="$PROJECT_ROOT/backend"
VENV_DIR="$BACKEND_DIR/.venv"
INSTANCE_DIR="$BACKEND_DIR/instance"
GUNICORN_LOG="/tmp/codde-backend.log"
GUNICORN_PATTERN="gunicorn -w 2 -b 127.0.0.1:5000"
GUNICORN_CMD="$VENV_DIR/bin/gunicorn -w 2 -b 127.0.0.1:5000 \"app:create_app('production')\""

echo "[1/5] Fixing ownership"
sudo chown -R admin:admin "$PROJECT_ROOT"
mkdir -p "$INSTANCE_DIR"

echo "[2/5] Rebuilding frontend"
cd "$FRONTEND_DIR"
rm -rf node_modules
npm install
chmod +x "$FRONTEND_DIR/node_modules/.bin/vite"
npm run build

echo "[3/5] Rebuilding backend virtualenv"
cd "$BACKEND_DIR"
rm -rf "$VENV_DIR"
python3.11 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
pip install -r requirements.txt

echo "[4/5] Restarting backend"
pkill -9 -f gunicorn || true
sleep 2
nohup bash -lc "$GUNICORN_CMD" >"$GUNICORN_LOG" 2>&1 &
sleep 3

echo "[5/5] Verifying services"
curl -I http://127.0.0.1/
curl -I http://127.0.0.1:5000/
tail -n 30 "$GUNICORN_LOG" || true

echo "Update complete."

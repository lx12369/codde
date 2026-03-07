#!/usr/bin/env bash
set -euo pipefail

ZIP_PATH="${1:-/tmp/codde.zip}"
PROJECT_PARENT="/www/wwwroot"
PROJECT_NAME="codde"
PROJECT_ROOT="$PROJECT_PARENT/$PROJECT_NAME"
STAGE_ROOT="$PROJECT_PARENT/${PROJECT_NAME}_zip_update_stage"
BACKUP_ROOT="/www/backup/codde"
TIMESTAMP="$(date +%F-%H%M%S)"
PROJECT_BACKUP="$BACKUP_ROOT/project_$TIMESTAMP.tar.gz"

echo "[1/6] Checking package"
if [[ ! -f "$ZIP_PATH" ]]; then
  echo "Package not found: $ZIP_PATH" >&2
  exit 1
fi

echo "[2/6] Backing up current project"
sudo mkdir -p "$BACKUP_ROOT"
sudo tar -czf "$PROJECT_BACKUP" -C "$PROJECT_PARENT" "$PROJECT_NAME"

echo "[3/6] Extracting package"
sudo rm -rf "$STAGE_ROOT"
sudo mkdir -p "$STAGE_ROOT"
sudo unzip -q "$ZIP_PATH" -d "$STAGE_ROOT"

if [[ ! -d "$STAGE_ROOT/backend" || ! -d "$STAGE_ROOT/frontend" ]]; then
  echo "Extracted package does not look like the project root." >&2
  exit 1
fi

echo "[4/6] Replacing code while preserving runtime data"
cd "$PROJECT_ROOT"
sudo find . -mindepth 1 -maxdepth 1 ! -name ".git" ! -name "backend" -exec rm -rf {} +
sudo find backend -mindepth 1 -maxdepth 1 ! -name "instance" ! -name ".env" ! -name ".venv" -exec rm -rf {} +
sudo cp -a "$STAGE_ROOT"/. "$PROJECT_ROOT"/
sudo chown -R admin:admin "$PROJECT_ROOT"

echo "[5/6] Restarting application"
sudo chmod +x "$PROJECT_ROOT/scripts/server-update.sh"
cd "$PROJECT_ROOT"
./scripts/server-update.sh

echo "[6/6] Cleaning temporary files"
sudo rm -rf "$STAGE_ROOT"

echo "Deploy complete."
echo "Project backup: $PROJECT_BACKUP"

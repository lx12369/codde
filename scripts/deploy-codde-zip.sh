#!/usr/bin/env bash
set -euo pipefail

ZIP_PATH="/www/wwwroot/codde.zip"
PROJECT_PARENT="/www/wwwroot"
PROJECT_NAME="codde"
PROJECT_ROOT="$PROJECT_PARENT/$PROJECT_NAME"
STAGING_ROOT="$PROJECT_PARENT/${PROJECT_NAME}_new"
BACKUP_ROOT="/www/backup/codde"
TIMESTAMP="$(date +%F-%H%M%S)"
PROJECT_BACKUP="$BACKUP_ROOT/project_$TIMESTAMP"
INSTANCE_BACKUP="$BACKUP_ROOT/instance_$TIMESTAMP"
APP_DB_BACKUP="$BACKUP_ROOT/app_db_$TIMESTAMP"
ENV_BACKUP="$BACKUP_ROOT/env_$TIMESTAMP"
TMP_INSTANCE="/tmp/${PROJECT_NAME}-instance-keep"
TMP_APP_DB="/tmp/${PROJECT_NAME}-app.db-keep"
TMP_ENV="/tmp/${PROJECT_NAME}-env-keep"

echo "[1/7] Checking package"
if [[ ! -f "$ZIP_PATH" ]]; then
  echo "Package not found: $ZIP_PATH" >&2
  exit 1
fi

echo "[2/7] Backing up current server data"
sudo mkdir -p "$BACKUP_ROOT"
if [[ -d "$PROJECT_ROOT" ]]; then
  sudo cp -a "$PROJECT_ROOT" "$PROJECT_BACKUP"
fi
if [[ -d "$PROJECT_ROOT/backend/instance" ]]; then
  sudo cp -a "$PROJECT_ROOT/backend/instance" "$INSTANCE_BACKUP"
  sudo rm -rf "$TMP_INSTANCE"
  sudo cp -a "$PROJECT_ROOT/backend/instance" "$TMP_INSTANCE"
fi
if [[ -f "$PROJECT_ROOT/backend/app.db" ]]; then
  sudo cp -a "$PROJECT_ROOT/backend/app.db" "$APP_DB_BACKUP"
  sudo rm -f "$TMP_APP_DB"
  sudo cp -a "$PROJECT_ROOT/backend/app.db" "$TMP_APP_DB"
fi
if [[ -f "$PROJECT_ROOT/backend/.env" ]]; then
  sudo cp -a "$PROJECT_ROOT/backend/.env" "$ENV_BACKUP"
  sudo cp -a "$PROJECT_ROOT/backend/.env" "$TMP_ENV"
fi

echo "[3/7] Extracting new package"
sudo rm -rf "$STAGING_ROOT"
sudo mkdir -p "$STAGING_ROOT"
sudo unzip -q "$ZIP_PATH" -d "$STAGING_ROOT"

NEW_ROOT="$STAGING_ROOT/$PROJECT_NAME"
if [[ ! -d "$NEW_ROOT" ]]; then
  NEW_ROOT="$STAGING_ROOT"
fi

if [[ ! -d "$NEW_ROOT/frontend" || ! -d "$NEW_ROOT/backend" ]]; then
  echo "Extracted package does not look like the project root." >&2
  exit 1
fi

echo "[4/7] Replacing project files"
sudo rm -rf "$PROJECT_ROOT"
sudo mv "$NEW_ROOT" "$PROJECT_ROOT"
sudo chown -R admin:admin "$PROJECT_ROOT"

echo "[5/7] Restoring preserved server data"
if [[ -d "$TMP_INSTANCE" ]]; then
  sudo rm -rf "$PROJECT_ROOT/backend/instance"
  sudo mv "$TMP_INSTANCE" "$PROJECT_ROOT/backend/instance"
fi
if [[ -f "$TMP_APP_DB" ]]; then
  sudo rm -f "$PROJECT_ROOT/backend/app.db"
  sudo mv "$TMP_APP_DB" "$PROJECT_ROOT/backend/app.db"
fi
if [[ -f "$TMP_ENV" ]]; then
  sudo cp -a "$TMP_ENV" "$PROJECT_ROOT/backend/.env"
  sudo rm -f "$TMP_ENV"
fi
sudo chown -R admin:admin "$PROJECT_ROOT/backend"

echo "[6/7] Running application update"
sudo chmod +x "$PROJECT_ROOT/scripts/server-update.sh"
cd "$PROJECT_ROOT"
./scripts/server-update.sh

echo "[7/7] Cleaning up package files"
sudo rm -rf "$STAGING_ROOT"
sudo rm -f "$ZIP_PATH"

echo "Deploy complete."
echo "Project backup: $PROJECT_BACKUP"
if [[ -d "$INSTANCE_BACKUP" ]]; then
  echo "Database backup: $INSTANCE_BACKUP"
fi
if [[ -f "$APP_DB_BACKUP" ]]; then
  echo "Database backup: $APP_DB_BACKUP"
fi
if [[ -f "$ENV_BACKUP" ]]; then
  echo "Env backup: $ENV_BACKUP"
fi

#!/usr/bin/env bash
set -Eeuo pipefail

BASE_PATH="/opt/apps"
GIT_HUB_URL="${GIT_HUB_URL:-https://github.com/inno-bit-lab/WhistleblowingEasy.git}"

APP_PATH="${APP_PATH:-$BASE_PATH/wbe}"
REPOS_PATH="${REPOS_PATH:-$APP_PATH/repos}"

echo "APP PATH:  $APP_PATH"
echo "REPOS PATH: $REPOS_PATH"

sudo mkdir -p "$REPOS_PATH"
sudo chown -R "$USER":"$USER" "$BASE_PATH"

cd "$REPOS_PATH"
git clone --depth=1 "$GIT_HUB_URL" || { echo "Clone fallito"; exit 1; }
echo "Clonazione completata."

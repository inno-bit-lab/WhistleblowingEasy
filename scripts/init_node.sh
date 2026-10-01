#!/usr/bin/env bash
set -Eeuo pipefail
APP_PATH=/opt/apps/wbe
REPO_PATH="${WBE_REPO_PATH:-$APP_PATH/repos/WhistleblowingEasy}"
NODE_NAME=""
while (($#)); do
  case "$1" in
    --node-name) NODE_NAME="$2"; shift 2 ;;
    --repo-path) REPO_PATH="$2"; shift 2 ;;
    *) echo "Opzione sconosciuta: $1" >&2; exit 1 ;;
  esac
done
[[ "$NODE_NAME" =~ ^[a-zA-Z0-9_-]+$ ]] || { echo 'Nome nodo non valido.' >&2; exit 1; }
NODE_PATH="$APP_PATH/$NODE_NAME"
[[ ! -e "$NODE_PATH" ]] || { echo "Il nodo $NODE_PATH esiste già; non verrà sovrascritto." >&2; exit 1; }
. /etc/os-release
REQ="$REPO_PATH/backend/requirements/requirements.txt.${VERSION_CODENAME}"
[[ -f "$REQ" ]] || { echo "Distribuzione non supportata: $VERSION_CODENAME" >&2; exit 1; }
command -v python3 >/dev/null
command -v npm >/dev/null
mkdir -p "$NODE_PATH/appdata/log"
git -C "$REPO_PATH" archive HEAD backend client LICENSE | tar -x -C "$NODE_PATH"
python3 -m venv "$NODE_PATH/backend/env"
"$NODE_PATH/backend/env/bin/python" -m pip install --require-hashes -r "$REQ"
(cd "$NODE_PATH/client" && npm ci --no-audit --no-fund && ./node_modules/.bin/grunt clean shell:build package)
cat > "$NODE_PATH/node.conf" <<CONF
NODE_NAME=$NODE_NAME
NODE_PATH=$NODE_PATH
WORKING_PATH=$NODE_PATH/appdata
HTTP_PORT=8082
HTTPS_PORT=8443
MAINTENANCE_MODE=Y
CONF
echo "Nodo preparato in manutenzione: $NODE_PATH"
echo 'Prima di avviare: ripristinare i dati se necessario, assegnare il nodo a iblapps e installare la nuova unità systemd con RuntimeDirectory.'

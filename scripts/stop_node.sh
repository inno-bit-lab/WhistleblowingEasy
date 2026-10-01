#!/usr/bin/env bash
set -Eeuo pipefail
export LC_ALL=C.UTF-8 LANG=C.UTF-8

usage(){ echo "Usage: $0 --node-name NAME"; exit 1; }
[[ $# -eq 2 && "$1" == "--node-name" && -n "$2" ]] || usage
NODE_NAME="$2"

APP_ROOT="/opt/apps/wbe"
SCRIPTS_PATH="$APP_ROOT/scripts"
. "$SCRIPTS_PATH/.common_node_wbe" --node-name "$NODE_NAME"
. "$SCRIPTS_PATH/common_functions.sh"

PID="$(get_pid || true)"
if [[ -n "${PID:-}" ]]; then
  echo "Trovato PID $PID. Invio SIGTERM..."
  kill -15 "$PID" || true
  sleep 10
  PID="$(get_pid || true)"
  if [[ -n "${PID:-}" ]]; then
    echo "Ancora vivo. Invio SIGKILL..."
    kill -9 "$PID" || true
  else
    echo "Terminato correttamente."
  fi
else
  echo "Nessun processo trovato per $NODE_NAME."
fi

#!/usr/bin/env bash
set -Eeuo pipefail
export LC_ALL=C.UTF-8 LANG=C.UTF-8

APP_ROOT="/opt/apps/wbe"
CONF_FILE="$APP_ROOT/conf/.common_wbe"
SCRIPTS_PATH="$APP_ROOT/scripts"

usage(){ echo "Usage: $0 --node-name NAME"; exit 1; }
[[ $# -eq 2 && "$1" == "--node-name" && -n "$2" ]] || usage
NODE_NAME="$2"

[[ -f "$CONF_FILE" ]] && . "$CONF_FILE"
. "$SCRIPTS_PATH/.common_node_wbe" --node-name "$NODE_NAME"
[[ -f "$CONFIG_FILE" ]] || { echo "Config $CONFIG_FILE mancante" >&2; exit 1; }
. "$CONFIG_FILE"

# Preserve maintenance mode when systemd starts the application dependency.
if [[ "${MAINTENANCE_MODE:-N}" == "Y" ]]; then
  echo "Maintenance mode enabled for $NODE_NAME; application start skipped."
  exit 0
fi

cd "$NODE_PATH/backend"
[[ -x env/bin/python && -f env/bin/activate && -f bin/globaleaks ]] || {
  echo "Backend environment missing for $NODE_NAME; run provisioning first." >&2
  exit 1
}

# Foreground belongs to wbe-app@.service. Dependencies are provisioned separately.
export WBE_HTTP_PORT="${HTTP_PORT:-8080}"
exec env/bin/python bin/globaleaks -n --working-path="$WORKING_PATH"

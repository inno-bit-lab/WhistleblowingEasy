#!/usr/bin/env bash
set -Eeuo pipefail

# Base app
APP_ROOT="/opt/apps/wbe"
CONF_FILE="$APP_ROOT/conf/.common_wbe"
[[ -f "$CONF_FILE" ]] && . "$CONF_FILE"

# Nodo: NODE_PATH e CONFIG_FILE dovrebbero arrivare da .common_node_wbe
: "${NODE_PATH:?NODE_PATH non definito (sorgi .common_node_wbe)}"
CONFIG_FILE="${CONFIG_FILE:-$NODE_PATH/node.conf}"

log() { printf '[%s] %s\n' "$(date +'%F %T')" "$*" ; }

get_property() {
  local k="$1"
  [[ -f "$CONFIG_FILE" ]] || return 1
  awk -F= -v key="$k" '$1==key{print substr($0,index($0,"=")+1)}' "$CONFIG_FILE"
}

set_property() {
  local k="$1" v="$2"
  touch "$CONFIG_FILE"
  if grep -q "^${k}=" "$CONFIG_FILE"; then
    sed -i "s|^${k}=.*|${k}=${v}|" "$CONFIG_FILE"
  else
    printf '%s=%s\n' "$k" "$v" >> "$CONFIG_FILE"
  fi
}

remove_property() {
  local k="$1"
  [[ -f "$CONFIG_FILE" ]] || return 0
  sed -i "/^${k}=.*/d" "$CONFIG_FILE"
}

# PID detection affidabile sul working path
get_pid() {
  local wp http_port https_port
  wp="$(get_property WORKING_PATH || true)"
  # se c’è porta http/https puoi raffinare il match
  pgrep -f "bin/globaleaks -n --working-path=${wp}" || true
}

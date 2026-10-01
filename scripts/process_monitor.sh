#!/usr/bin/env bash
set -Eeuo pipefail
export LC_ALL=C.UTF-8 LANG=C.UTF-8

APP_ROOT="/opt/apps/wbe"
CONF_FILE="$APP_ROOT/conf/.common_wbe"
SCRIPTS_PATH="$APP_ROOT/scripts"

[[ -f /home/iblapps/.profile ]] && . /home/iblapps/.profile || true
[[ -f /home/iblapps/.bashrc  ]] && . /home/iblapps/.bashrc  || true
[[ -f "$CONF_FILE" ]] && . "$CONF_FILE"


usage(){ echo "Usage: $0 --node-name NAME"; exit 1; }
[[ $# -eq 2 && "$1" == "--node-name" && -n "$2" ]] || usage
NODE_NAME="$2"

# Config nodo
. "$SCRIPTS_PATH/.common_node_wbe" --node-name "$NODE_NAME"

. "$SCRIPTS_PATH/common_functions.sh"


MAINTENANCE_MODE="$(get_property MAINTENANCE_MODE || echo N)"
NODE_STATUS="$(get_property NODE_STATUS || echo)"

if [[ "$MAINTENANCE_MODE" == "Y" ]]; then
  echo "Modalit� manutenzione attiva. Esco."
  exit 0
else
  set_property MAINTENANCE_MODE N
fi

# Check recovery before throttling failure notifications.
PID="$(get_pid || true)"
if [[ -n "${PID:-}" ]]; then
  echo "Processo gia in esecuzione (pid $PID)."
  if [[ "$NODE_STATUS" == "WARN" ]]; then
    remove_property NODE_STATUS
  fi
  exit 0
fi

if [[ "$NODE_STATUS" == "WARN" ]]; then
  WARN_LAST_UPDATE="$(get_property WARN_LAST_UPDATE || true)"
  if [[ -n "${WARN_LAST_UPDATE:-}" ]]; then
    last=$(date -d "$WARN_LAST_UPDATE" +%s)
    now=$(date +%s)
    (( now - last > 3600 )) && set_property WARN_LAST_UPDATE "$(date +%F'T'%T)" || exit 0
  fi
fi

PID="$(get_pid || true)"
if [[ -z "${PID:-}" ]]; then
  "$SCRIPTS_PATH/send_mail.sh" \
    --subject "[$NODE_NAME] Processo non in esecuzione" \
    --body "Il processo per $NODE_NAME non � in esecuzione. Avvio in corso."

  set_property NODE_STATUS WARN
  set_property WARN_LAST_UPDATE "$(date +%F'T'%T)"

  # wbe-app@.service is started by the monitor unit dependency, outside this cgroup.
  sleep 60

  PID="$(get_pid || true)"
  if [[ -z "${PID:-}" ]]; then
    "$SCRIPTS_PATH/send_mail.sh" \
      --subject "[$NODE_NAME] Avvio fallito" \
      --body "Impossibile avviare il processo per $NODE_NAME dopo il tentativo."
    exit 1
  else
    echo "Processo avviato (pid $PID). Pulisco WARNING."
    remove_property NODE_STATUS
  fi
else
  echo "Processo gi� in esecuzione (pid $PID)."
fi

#!/usr/bin/env bash
set -Eeuo pipefail
export LC_ALL=C.UTF-8 LANG=C.UTF-8
APP_ROOT="/opt/apps/wbe"
MSMTP_CONFIG="$APP_ROOT/conf/msmtp/config"
CONF_FILE="$APP_ROOT/conf/.common_wbe"
[[ -f "$CONF_FILE" ]] && . "$CONF_FILE"

TO=""
SUBJECT="No subject"
BODY=""

while (( "$#" )); do
  case "$1" in
    --to) TO="$2"; shift 2 ;;
    --subject) SUBJECT="$2"; shift 2 ;;
    --body) BODY="$2"; shift 2 ;;
    *) echo "Parametro non riconosciuto: $1" >&2; exit 2 ;;
  esac
done

# default destinatario da proprietà, se non passato
if [[ -z "$TO" ]]; then
  TO="$(get_property ALERT_EMAIL 2>/dev/null || true)"
  [[ -n "$TO" ]] || TO="wbe.support@innobitlab.it"
fi

printf "Subject: [WBE-MONITOR] %s\nTo: %s\n\n%s\n" "$SUBJECT" "$TO" "$BODY" | msmtp -C $MSMTP_CONFIG -a default "$TO"

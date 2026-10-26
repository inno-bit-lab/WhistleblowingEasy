#!/usr/bin/env bash
# Operator-only final freeze. Leaves legacy stopped; never starts the new stack.
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || { echo 'Eseguire con sudo.' >&2; exit 1; }
root=/opt/apps/wbe-refact
source=/opt/apps/wbe/node1/appdata
[[ -d "$root/.local/imports" && ! -L "$root/.local/imports" ]] || exit 1
trap 'echo "Operazione interrotta: non presumere che il servizio sia ripartito. Conservare output e contattare il coordinatore per rollback." >&2' ERR
printf 'Inizio fermo UTC: '; date -u +%FT%TZ
/opt/apps/wbe/install/scripts/stop-and-backup-node1.sh
umask 077
stage=$(mktemp -d "$root/.local/imports/final-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXXXX")
install -d -m 0700 "$stage/appdata"
for suffix in -wal -shm -journal; do
  [[ ! -e "$source/globaleaks.db$suffix" ]] || { echo 'SQLite sidecar presente: non migrare.' >&2; exit 1; }
done
cp -a -- "$source/globaleaks.db" "$source/files" "$source/attachments" "$stage/appdata/"
# Reject links/special files before ownership changes. Never follow links.
if find "$stage" ! -type f ! -type d -print -quit | grep -q .; then
  echo 'Snapshot contiene file speciali: non migrare.' >&2; exit 1
fi
cmp -- "$source/globaleaks.db" "$stage/appdata/globaleaks.db"
chown -R --no-dereference ibladmin:iblapps "$stage"
find "$stage" -type d -exec chmod 0700 {} +
find "$stage" -type f -exec chmod 0600 {} +
printf 'Copia finale pronta: %s/appdata\nLegacy e monitor lasciati fermi. Non riavviarli durante la migrazione.\n' "$stage"

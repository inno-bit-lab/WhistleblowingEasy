#!/usr/bin/env bash
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || { echo 'Eseguire con sudo.' >&2; exit 1; }
root=/opt/apps/wbe
stamp=$(date +%Y%m%d-%H%M%S)
backup_dir="$root/backups/node1-$stamp"
umask 077
mkdir -p "$backup_dir"
cp -p "$root/node1/node.conf" "$backup_dir/node.conf.before-stop"
systemctl stop wbe-monitor@node1.timer wbe-monitor@node1.service
if grep -q '^MAINTENANCE_MODE=' "$root/node1/node.conf"; then
  sed -i 's/^MAINTENANCE_MODE=.*/MAINTENANCE_MODE=Y/' "$root/node1/node.conf"
else
  printf '\nMAINTENANCE_MODE=Y\n' >> "$root/node1/node.conf"
fi
systemctl stop wbe-app@node1.service
for unit in wbe-app@node1.service wbe-monitor@node1.timer wbe-monitor@node1.service; do
  if systemctl is-active --quiet "$unit"; then
    echo "Ancora attivo: $unit; backup interrotto." >&2
    exit 1
  fi
done
if pgrep -f 'bin/globaleaks -n --working-path=/opt/apps/wbe/node1/appdata' >/dev/null; then
  echo 'Processo WBE ancora presente; backup interrotto.' >&2
  exit 1
fi
tar --acls --xattrs --numeric-owner -czpf "$backup_dir/node1.tar.gz" -C "$root" node1
gzip -t "$backup_dir/node1.tar.gz"
(cd "$backup_dir" && sha256sum node1.tar.gz > SHA256SUMS)
printf 'Backup completato: %s\nNode1 fermo, timer fermo, MAINTENANCE_MODE=Y.\n' "$backup_dir"

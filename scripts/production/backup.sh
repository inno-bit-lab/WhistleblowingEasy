#!/bin/sh
# Quiesce backend/frontend explicitly before this command; no live backup claim.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$ROOT"
if ./scripts/production/compose.sh ps --status running --services | grep -Eq '^(backend|frontend|migrate)$'; then
  echo 'Stop backend/frontend and complete migration jobs before backup.' >&2; exit 2
fi
umask 077
DEST="$ROOT/.local/production/backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$ROOT/.local/production/backups"
mkdir "$DEST"
./scripts/production/compose.sh exec -T postgres pg_dump -U postgres -d wbe -Fc > "$DEST/database.dump"
tar --exclude=./tmp -C .local/production/appdata -czf "$DEST/appdata.tar.gz" .
tar -C .local/production -czf "$DEST/secrets.tar.gz" secrets compose.env
(cd "$DEST" && sha256sum database.dump appdata.tar.gz secrets.tar.gz > SHA256SUMS)
printf '%s\n' "$DEST"

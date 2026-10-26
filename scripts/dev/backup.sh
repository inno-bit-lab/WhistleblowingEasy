#!/bin/sh
# Quiesce backend/frontend explicitly before this command; no live backup claim.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$ROOT"
if ./scripts/dev/compose.sh ps --status running --services | grep -Eq '^(backend|frontend|migrate)$'; then
  echo 'Stop backend/frontend and complete migration jobs before backup.' >&2; exit 2
fi
umask 077
DEST="$ROOT/.local/backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir "$DEST"
./scripts/dev/compose.sh exec -T postgres pg_dump -U postgres -d wbe -Fc > "$DEST/database.dump"
tar --exclude=./tmp -C .local/appdata -czf "$DEST/appdata.tar.gz" .
tar -C .local -czf "$DEST/secrets.tar.gz" secrets dev.env
(cd "$DEST" && sha256sum database.dump appdata.tar.gz secrets.tar.gz > SHA256SUMS)
printf '%s\n' "$DEST"

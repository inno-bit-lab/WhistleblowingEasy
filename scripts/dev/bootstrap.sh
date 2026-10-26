#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$ROOT"
[ "$(id -u)" -ne 0 ] || { echo "Run bootstrap as the development checkout owner, not root." >&2; exit 2; }
umask 077
mkdir -p .local/secrets .local/appdata .local/resources .local/imports .local/backups
chmod 700 .local/secrets .local/appdata .local/imports .local/backups
if [ ! -f .local/dev.env ]; then
  printf 'WBE_UID=%s\nWBE_GID=%s\nWBE_FRONTEND_HOST_PORT=18090\n' "$(id -u)" "$(id -g)" > .local/dev.env
fi
python3 - <<'PY'
from pathlib import Path
import secrets
root = Path('.local/secrets')
for name in ('postgres', 'owner', 'runtime'):
    path = root / (name + '-password')
    if not path.exists():
        path.write_text(secrets.token_hex(32) + '\n')
    # PostgreSQL runs as its own UID; parent directory remains mode 0700.
    path.chmod(0o644)
for role in ('owner', 'runtime'):
    path = root / (role + '-url')
    if not path.exists():
        password = (root / (role + '-password')).read_text().strip()
        path.write_text(f'postgresql+psycopg2://wbe_{role}:{password}@postgres:5432/wbe\n')
    path.chmod(0o600)
PY
./scripts/dev/compose.sh config --quiet
printf '%s\n' 'Bootstrap complete. Build runtimes, build client, start postgres, run migrate init, then start backend/frontend. See runbook.'

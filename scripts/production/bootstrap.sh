#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$ROOT"
[ "$(id -u)" -ne 0 ] || { echo 'Run bootstrap as the checkout owner, not root.' >&2; exit 2; }
umask 077
python3 - <<'PY'
from pathlib import Path
import os
import secrets
root = Path('.local/production')
for path in (root, root/'secrets', root/'appdata'):
    if path.is_symlink():
        raise SystemExit('Refusing symlink in production directories')
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)
config = root/'compose.env'
if config.is_symlink():
    raise SystemExit('Refusing symlink for production config')
if not config.exists():
    with config.open('x') as target:
        target.write(f'WBE_UID={os.getuid()}\nWBE_GID={os.getgid()}\nWBE_ONION_PUBLISH=0\nWBE_DISABLE_NOTIFICATIONS=0\n')
config.chmod(0o600)
for role in ('postgres', 'owner', 'runtime'):
    path = root/'secrets'/(role+'-password')
    if path.is_symlink():
        raise SystemExit('Refusing symlink for production secret')
    if not path.exists():
        with path.open('x') as target:
            target.write(secrets.token_hex(32)+'\n')
    # PostgreSQL entrypoint changes UID; containing host directories stay 0700.
    path.chmod(0o644)
for role in ('owner', 'runtime'):
    path = root/'secrets'/(role+'-url')
    if path.is_symlink():
        raise SystemExit('Refusing symlink for production database URL')
    if not path.exists():
        password = (root/'secrets'/(role+'-password')).read_text().strip()
        with path.open('x') as target:
            target.write(f'postgresql+psycopg2://wbe_{role}:{password}@postgres:5432/wbe\n')
    path.chmod(0o600)
PY
./scripts/production/compose.sh config --quiet
printf '%s\n' 'Production configuration prepared; no services started and no data imported.'

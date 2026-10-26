#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
PORT=$(sed -n 's/^WBE_FRONTEND_HOST_PORT=//p' "$ROOT/.local/dev.env")
BASE="http://127.0.0.1:${PORT:-18090}"
curl --fail --silent --show-error "$BASE/healthz"
curl --fail --silent --show-error "$BASE/api/health"
"$ROOT/scripts/dev/migrate.sh" check --working-path /var/globaleaks
printf '\nLayer readiness checks passed; this does not replace functional report/upload tests.\n'

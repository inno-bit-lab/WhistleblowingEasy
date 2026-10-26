#!/bin/sh
# Serializes the destructive dedicated test DB. Never runs against database wbe.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$ROOT"
MODE=${1:-postgresql}
if [ "$#" -gt 0 ]; then shift; fi
case "$MODE" in postgresql|sqlite|integration) ;; *) echo 'Usage: test-backend.sh [postgresql|sqlite|integration] [trial modules...]' >&2; exit 2;; esac
mkdir -p .local/test-results
if [ "$#" -eq 0 ]; then set -- globaleaks.tests; fi
if [ "$MODE" = sqlite ]; then
  exec ./scripts/dev/compose.sh --profile tooling run --rm --no-deps \
    -w /tmp -e WBE_DATABASE_URL_FILE= -e WBE_DATABASE_URL= \
    -e WBE_SEPARATE_FRONTEND=0 -e WBE_DEV_HTTP=0 -e WBE_RESOURCES_PATH=/test-client \
    -v "$ROOT/client/build:/test-client:ro" \
    --entrypoint python migrate -m twisted.trial "$@"
fi
python3 - <<'PY'
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
source = urlsplit(Path('.local/secrets/owner-url').read_text().strip())
p = Path('.local/secrets/test-url')
p.write_text(urlunsplit(source._replace(path='/wbe_phase1_test'))+'\n')
p.chmod(0o600)
PY
if [ "$MODE" = integration ]; then
  set -- -m unittest discover -s /tests/phase1 -p test_postgresql.py -v
else
  set -- -m twisted.trial "$@"
fi
exec flock .local/pg-tests.lock ./scripts/dev/compose.sh --profile tooling run --rm --no-deps \
  -w /tmp -e WBE_DATABASE_URL_FILE=/run/secrets/test-url \
  -e WBE_TEST_DATABASE_URL_FILE=/run/secrets/test-url \
  -e WBE_SEPARATE_FRONTEND=0 -e WBE_DEV_HTTP=0 -e WBE_RESOURCES_PATH=/test-client \
  -v "$ROOT/client/build:/test-client:ro" -v "$ROOT/tests:/tests:ro" \
  -v "$ROOT/.local/secrets/test-url:/run/secrets/test-url:ro" \
  --entrypoint python migrate "$@"

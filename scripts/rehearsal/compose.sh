#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$ROOT"
if [ -x "$ROOT/.local/bin/docker-compose" ]; then
  set -- "$ROOT/.local/bin/docker-compose" --project-name wbe-rehearsal --project-directory "$ROOT" --env-file "$ROOT/.local/rehearsal/compose.env" -f "$ROOT/deploy/rehearsal/compose.yml" "$@"
elif docker compose version >/dev/null 2>&1; then
  set -- docker compose --project-name wbe-rehearsal --project-directory "$ROOT" --env-file "$ROOT/.local/rehearsal/compose.env" -f "$ROOT/deploy/rehearsal/compose.yml" "$@"
else
  echo 'Install Docker Compose v2+ or place the verified binary at .local/bin/docker-compose' >&2
  exit 1
fi
exec "$@"

#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
if [ "$#" -lt 1 ]; then echo 'Usage: import-sqlite.sh SNAPSHOT_PATH [--dry-run]' >&2; exit 2; fi
SOURCE=$(realpath "$1")
shift
case "$SOURCE" in "$ROOT/.local/production/imports/"*) ;; *) echo 'Place an authorized frozen snapshot under .local/production/imports first.' >&2; exit 2;; esac
[ -f "$SOURCE" ] || exit 2
exec "$ROOT/scripts/production/compose.sh" --profile tooling run --rm -v "$SOURCE:/imports/source.db:ro" migrate import-sqlite --working-path /var/globaleaks --source /imports/source.db --runtime-role wbe_runtime "$@"

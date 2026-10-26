#!/bin/sh
set -eu
case "${1:-}" in
  init|import-sqlite) set -- "$@" --runtime-role wbe_runtime ;;
esac
exec "$(dirname "$0")/compose.sh" --profile tooling run --rm migrate "$@"

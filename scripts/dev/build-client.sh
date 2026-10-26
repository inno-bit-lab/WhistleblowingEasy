#!/bin/sh
set -eu
exec "$(dirname "$0")/compose.sh" --profile tooling run --rm --no-deps client-build

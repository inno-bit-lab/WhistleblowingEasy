#!/bin/sh
set -eu
exec python /app/backend/bin/globaleaks -n -i 0.0.0.0 -w /var/globaleaks "$@"

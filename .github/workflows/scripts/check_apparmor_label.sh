#!/bin/sh
# Ubuntu kernels can stack the initial unconfined label with the enforced
# application profile. Neither plain unconfined nor complain mode is acceptable.
set -eu
case "${1-}" in
  'usr.bin.globaleaks (enforce)'|'unconfined//&usr.bin.globaleaks (enforce)') exit 0 ;;
  *) printf 'Unexpected AppArmor confinement: %s\n' "${1-}" >&2; exit 1 ;;
esac

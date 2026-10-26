#!/bin/sh
# Restore a backup into a NEW development DB and NEW file directory. Never replace wbe.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
[ "$#" -eq 1 ] || { echo 'Usage: restore.sh .local/backups/TIMESTAMP' >&2; exit 2; }
BACKUP=$(realpath "$1")
case "$BACKUP" in "$ROOT/.local/backups/"*) ;; *) echo 'Backup must be under .local/backups' >&2; exit 2;; esac
# Validate filenames and archive entries before touching PostgreSQL or extracting files.
python3 - "$BACKUP" <<'PYVALIDATE'
import hashlib, pathlib, sys, tarfile
root = pathlib.Path(sys.argv[1])
expected = {'database.dump', 'appdata.tar.gz', 'secrets.tar.gz'}
lines = (root / 'SHA256SUMS').read_text().splitlines()
seen = set()
for line in lines:
    digest, name = line.split('  ', 1)
    if name not in expected or name in seen:
        raise SystemExit('Invalid backup manifest')
    seen.add(name)
    with (root / name).open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != digest:
        raise SystemExit('Backup checksum mismatch')
if seen != expected:
    raise SystemExit('Incomplete backup manifest')
for archive in ('appdata.tar.gz', 'secrets.tar.gz'):
    with tarfile.open(root / archive) as stream:
        for member in stream.getmembers():
            path = pathlib.PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or not (member.isfile() or member.isdir()):
                raise SystemExit('Unsafe backup archive entry')
print('Backup manifest and archive paths verified')
PYVALIDATE
STAMP=$(date -u +%Y%m%d%H%M%S)
DATABASE="wbe_restore_$STAMP"
DEST="$ROOT/.local/restore-$STAMP"
umask 077
mkdir "$DEST"
"$ROOT/scripts/dev/compose.sh" exec -T postgres createdb -U postgres -O wbe_owner "$DATABASE"
"$ROOT/scripts/dev/compose.sh" exec -T postgres pg_restore -U postgres --exit-on-error --single-transaction -d "$DATABASE" < "$BACKUP/database.dump"
tar --no-same-owner -C "$DEST" -xzf "$BACKUP/appdata.tar.gz"
printf 'Restored database %s and files %s. Verify with owner DSN pointing to this database; original wbe unchanged.\n' "$DATABASE" "$DEST"

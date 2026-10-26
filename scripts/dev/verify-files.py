#!/usr/bin/env python3
"""Validate/copy a frozen SQLite snapshot's permanent files, never live appdata."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile


def inventory(root):
    result = {}
    for directory in ('files', 'attachments'):
        base = root / directory
        if not base.is_dir() or base.is_symlink():
            raise ValueError('Missing or unsafe permanent file directory')
        for item in sorted(base.iterdir()):
            if item.is_symlink() or not item.is_file():
                raise ValueError('Permanent directories must contain regular files only')
            with item.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            result[f'{directory}/{item.name}'] = {'bytes': item.stat().st_size, 'sha256': digest}
    return result


def verify(snapshot, source, destination=None):
    before = inventory(source)
    with sqlite3.connect(snapshot.resolve(strict=True).as_uri() + '?mode=ro', uri=True) as db:
        version = db.execute("SELECT value FROM config WHERE tid=1 AND var_name='version_db'").fetchone()
        if version is None or json.loads(version[0]) != 69:
            raise ValueError('Frozen schema 69 required')
        if db.execute('SELECT 1 FROM internalfile WHERE new=1 LIMIT 1').fetchone():
            raise ValueError('Pending file delivery: drain uploads before taking the snapshot')
        def present(folder, identity):
            if not isinstance(identity, str) or '/' in identity or '\\' in identity or identity in ('.', '..'):
                raise ValueError('Invalid file identifier')
            return f'{folder}/{identity}' in before
        for (identity,) in db.execute('SELECT id FROM file'):
            if not present('files', identity):
                raise ValueError('Missing customization file')
        legacy = {}
        for identity, internal in db.execute('SELECT id, internalfile_id FROM whistleblowerfile'):
            legacy.setdefault(internal, []).append(identity)
            if not (present('attachments', identity) or present('attachments', internal)):
                raise ValueError('Missing whistleblower attachment')
        for (identity,) in db.execute('SELECT id FROM internalfile'):
            if not present('attachments', identity) and not any(present('attachments', x) for x in legacy.get(identity, [])):
                raise ValueError('Missing internal attachment')
        for (identity,) in db.execute('SELECT id FROM receiverfile'):
            if not present('attachments', identity):
                raise ValueError('Missing recipient attachment')
    if destination is not None:
        if destination.exists():
            raise ValueError('Destination must not exist; never merge into running appdata')
        destination.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix='.wbe-file-stage-', dir=destination.parent))
        try:
            for directory in ('files', 'attachments'):
                shutil.copytree(source / directory, stage / directory)
            if inventory(stage) != before or inventory(source) != before:
                raise ValueError('File contents changed during copy')
            stage.rename(destination)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    return {'schema': 69, 'files': before, 'count': len(before)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True, type=Path)
    parser.add_argument('--source-appdata', required=True, type=Path)
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--manifest', required=True, type=Path)
    args = parser.parse_args()
    import os
    os.umask(0o077)
    try:
        result = verify(args.snapshot, args.source_appdata, args.destination)
        with args.manifest.open('x') as output:
            json.dump(result, output, indent=2)
        print(f'Validated {result["count"]} permanent files; private manifest written')
    except (ValueError, OSError, sqlite3.Error):
        parser.exit(1, 'File verification failed; check frozen snapshot, pending uploads and file integrity.\n')


if __name__ == '__main__':
    main()

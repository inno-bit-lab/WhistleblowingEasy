#!/usr/bin/env python3
"""Frozen node1 appdata copy for rehearsal. Requires sudo; never changes live data."""
import argparse
import datetime
import json
import os
from pathlib import Path
import pwd
import shutil
import sqlite3
import subprocess
import sys
import time

SOURCE = Path('/opt/apps/wbe/node1/appdata')
IMPORTS = Path('/opt/apps/wbe-refact/.local/imports')
APP = 'wbe-app@node1.service'
TIMER = 'wbe-monitor@node1.timer'
MONITOR = 'wbe-monitor@node1.service'


def active(unit):
    return subprocess.run(['systemctl', 'is-active', '--quiet', unit]).returncode == 0


def control(action, *units):
    subprocess.run(['systemctl', action, *units], check=True, timeout=90)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check prerequisites without stopping services or copying data')
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('Run with sudo: live database is private to the service account')
    os.umask(0o077)
    if SOURCE.resolve() != SOURCE or IMPORTS.resolve() != IMPORTS:
        raise RuntimeError('Refusing symlinked source or destination roots')
    db = SOURCE / 'globaleaks.db'
    if not db.is_file() or db.is_symlink():
        raise RuntimeError('Expected regular node1 database file')
    if not active(APP) or not active(TIMER):
        raise RuntimeError('Expected running app and monitor timer; inspect maintenance state first')
    IMPORTS.mkdir(mode=0o700, parents=True, exist_ok=True)
    size = sum(p.stat().st_size for p in SOURCE.rglob('*') if p.is_file() and not p.is_symlink())
    if shutil.disk_usage(IMPORTS).free < max(size * 2, 1024**3):
        raise RuntimeError('Insufficient free space for private snapshot')
    operator = pwd.getpwnam('ibladmin')
    print('Preflight OK: source present, app/timer running, free space sufficient', flush=True)
    if args.check:
        return
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    destination = IMPORTS / ('real-' + stamp)
    destination.mkdir(mode=0o700)
    appdata = destination / 'appdata'
    appdata.mkdir(mode=0o700)
    started = time.monotonic()
    stopped_at = None
    resumed_at = None
    try:
        control('stop', TIMER, MONITOR)
        stopped_at = time.monotonic()
        control('stop', APP)
        if any(active(unit) for unit in (APP, TIMER, MONITOR)):
            raise RuntimeError('Service still active; refusing inconsistent copy')
        # Preserve permanent files and keys, including Tor material in the
        # private snapshot. The rehearsal must NOT reuse the Tor directory.
        entries = [str(p) for p in SOURCE.iterdir() if p.name not in {'tmp', 'shm', 'log'}]
        subprocess.run(['cp', '-a', '--', *entries, str(appdata) + '/'], check=True, timeout=120)
        shutil.copy2('/opt/apps/wbe/node1/node.conf', destination / 'node.conf.reference-only')
    finally:
        # Always attempt both recoveries, including copy timeout/validation error.
        try:
            control('start', APP)
        finally:
            control('start', TIMER)
        resumed_at = time.monotonic()
    if not active(APP) or not active(TIMER):
        raise RuntimeError('Production recovery requires operator attention')
    print('Production app and monitor timer restarted; validating offline snapshot', flush=True)
    with sqlite3.connect((appdata / 'globaleaks.db').as_uri() + '?mode=ro', uri=True) as conn:
        if conn.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise RuntimeError('Snapshot integrity check failed')
        if conn.execute('PRAGMA foreign_key_check').fetchone() is not None:
            raise RuntimeError('Snapshot foreign key check failed')
        row = conn.execute("SELECT value FROM config WHERE tid=1 AND var_name='version_db'").fetchone()
        schema_version = json.loads(row[0]) if row else None
        if schema_version not in (68, 69):
            raise RuntimeError('Unsupported snapshot schema; do not import')
        pending = conn.execute('SELECT count(*) FROM internalfile WHERE new=1').fetchone()[0]
        if pending:
            raise RuntimeError('Snapshot contains pending attachment delivery; do not import')
    metadata = {'status': 'snapshot-ready' if schema_version == 69 else 'requires-offline-schema-review', 'schema': schema_version, 'created_utc': stamp,
                'service_stop_start_seconds': round(resumed_at - stopped_at, 3),
                'total_seconds': round(time.monotonic() - started, 3),
                'excluded_volatile_directories': ['tmp', 'shm', 'log'],
                'production_app_active': active(APP), 'production_timer_active': active(TIMER)}
    (destination / 'snapshot.json').write_text(json.dumps(metadata, indent=2) + '\n')
    # Change ownership ONLY of the new private copy; never follow copied links.
    for directory, dirs, files in os.walk(destination, followlinks=False):
        for item in [Path(directory), *(Path(directory) / n for n in dirs + files)]:
            os.chown(item, operator.pw_uid, operator.pw_gid, follow_symlinks=False)
    destination.chmod(0o700)
    print('Snapshot copied: ' + str(destination))
    if schema_version == 68:
        print('Schema marker 68: offline structure verification/upgrade required before PostgreSQL import.')
    print('Production service stop/start seconds: ' + str(metadata['service_stop_start_seconds']))
    print('No data imported or frontend switched yet.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Avoid printing SQL rows, credentials or source configuration values.
        print('Snapshot failed: ' + str(error), file=sys.stderr)
        sys.exit(1)

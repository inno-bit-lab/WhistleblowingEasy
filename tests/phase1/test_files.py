import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('files', Path(__file__).parents[2] / 'scripts/dev/verify-files.py')
files = importlib.util.module_from_spec(spec)
spec.loader.exec_module(files)

class FileMigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source'
        for folder in ('files', 'attachments'):
            (self.source / folder).mkdir(parents=True)
        self.db = self.root / 'source.db'
        with sqlite3.connect(self.db) as db:
            db.executescript('''CREATE TABLE config(tid INTEGER, var_name TEXT, value TEXT);
                INSERT INTO config VALUES(1,'version_db','69');
                CREATE TABLE file(id TEXT); CREATE TABLE internalfile(id TEXT,new INTEGER);
                CREATE TABLE whistleblowerfile(id TEXT, internalfile_id TEXT);
                CREATE TABLE receiverfile(id TEXT);
                INSERT INTO internalfile VALUES('original',0);
                INSERT INTO whistleblowerfile VALUES('recipient-copy','original');''')
        (self.source / 'attachments/original').write_bytes(b'synthetic encrypted bytes\x00\xff')

    def test_copy_preserves_bytes_and_fallback_reference(self):
        dest = self.root / 'copy'
        result = files.verify(self.db, self.source, dest)
        self.assertEqual(result['count'], 1)
        self.assertEqual(files.inventory(dest), files.inventory(self.source))
        with self.assertRaises(ValueError):
            files.verify(self.db, self.source, dest)

    def test_missing_and_pending_files_refused(self):
        (self.source / 'attachments/original').unlink()
        with self.assertRaises(ValueError): files.verify(self.db, self.source)
        with sqlite3.connect(self.db) as db:
            db.execute('UPDATE internalfile SET new=1')
        with self.assertRaises(ValueError): files.verify(self.db, self.source)

    def test_symlink_refused(self):
        (self.source / 'files/link').symlink_to(self.db)
        with self.assertRaises(ValueError): files.verify(self.db, self.source)

if __name__ == '__main__': unittest.main()

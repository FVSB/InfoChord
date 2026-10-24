import hashlib
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class StorageTests(unittest.TestCase):
    def run_code(self, path, code):
        env = os.environ.copy()
        env["DB_PATH"] = "sqlite:///" + path.as_posix()
        env["LOG_DIR"] = str(path.parent / "logs")
        env["PYTHONPATH"] = os.pathsep.join([str(ROOT), str(ROOT / "distributed"), env.get("PYTHONPATH", "")])
        return subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=45)

    def test_legacy_database_is_rejected_without_modification(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "legacy.db"
            with closing(sqlite3.connect(path)) as connection:
                connection.execute("CREATE TABLE docs (id INTEGER PRIMARY KEY, document BLOB)")
                connection.execute("INSERT INTO docs VALUES (1, ?)", (b"old object blob",))
                connection.commit()
            before = hashlib.sha256(path.read_bytes()).digest()
            result = self.run_code(path, "import helper.db")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Legacy/incompatible database", result.stderr)
            self.assertEqual(hashlib.sha256(path.read_bytes()).digest(), before)

    def test_json_document_survives_new_process(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "new.db"
            insert = self.run_code(path, "from helper.docs import Document; from helper.db import insert_document; assert insert_document(Document('sample.txt','persistent text'), 1, True)")
            self.assertEqual(insert.returncode, 0, insert.stderr)
            read = self.run_code(path, "from helper.db import get_document_by_id; from helper.utils import getShaRepr; assert get_document_by_id(getShaRepr('sample.txt')).text == 'persistent text'")
            self.assertEqual(read.returncode, 0, read.stderr)
            with closing(sqlite3.connect(path)) as connection:
                self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 1)
                payload = connection.execute("SELECT document FROM docs").fetchone()[0]
                self.assertTrue(payload.startswith(b'{"version":1,'))

"""GET /api/doc/<id>: a document in the TextFold format, as fold.document builds it, on a server of its own (its own HOME
and data folder, no model). A document not folded yet comes with its local levels: asking for it generates nothing.

Run from the repo root:
    python3 -m unittest discover tests
"""
import json
import os
import site
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

from textfold import fold, store

ROOT = Path(__file__).resolve().parent.parent


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class DocRoute(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        home, cls.data = Path(cls.tmp.name) / "home", Path(cls.tmp.name) / "data"
        home.mkdir()
        cls.port = free_port()
        env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home), "LOCALAPPDATA": str(home / "AppData" / "Local"),
               "TEXTFOLD_DATA": str(cls.data), "TEXTFOLD_NO_MODELS": "1", "PYTHONUSERBASE": site.getuserbase()}
        cls.proc = subprocess.Popen([sys.executable, "-m", "textfold", "serve", "--port", str(cls.port)], cwd=ROOT, env=env,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{cls.port}/api/papers", timeout=1)
                break
            except OSError:
                time.sleep(0.1)
        text = "# Graphs\n\nA graph has nodes. Its edges join them.\n\n# Paths\n\nA path is a walk with no repeated node.\n"
        code, r = cls.call("/api/import", {"name": "graphs.md", "text": text})   # stored, not generated
        assert code == 200, r
        cls.pid = r["paper"]

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=10)
        cls.tmp.cleanup()

    @classmethod
    def call(cls, path, body=None):
        req = urllib.request.Request(f"http://127.0.0.1:{cls.port}{path}", data=None if body is None else json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_the_document_as_fold_builds_it(self):
        code, d = self.call(f"/api/doc/{self.pid}")
        self.assertEqual(code, 200, d)
        with mock.patch.object(store, "DATA", self.data):
            want = fold.document(self.pid, "en")
        for x in (d, want):
            x["provenance"].pop("exported")
        self.assertEqual(d, want)
        self.assertEqual((d["format"], d["id"], d["lang"]), ("textfold/doc", self.pid, "en"))
        self.assertEqual([u["full"] for s in d["sections"] for u in s["units"]],
                         ["A graph has nodes. Its edges join them.", "A path is a walk with no repeated node."])

    def test_not_folded_yet_it_is_not_folded_by_asking(self):
        code, d = self.call(f"/api/doc/{self.pid}?lang=de")   # (a language it has not: its own, as document() gives it)
        self.assertEqual((code, d["lang"]), (200, "en"))
        self.assertEqual((d["provenance"]["local"], d["provenance"]["ai_generated"], d["provenance"]["model"]), (True, False, ""))
        self.assertEqual(self.call("/api/jobs"), (200, []))
        self.assertFalse((self.data / "papers" / self.pid / "layers" / "en.json").exists())

    def test_an_unknown_document_or_language(self):
        for path in ("/api/doc/md-none-0000", "/api/doc/2512.23916", "/api/doc/..", "/api/doc/WEIRD"):
            with self.subTest(path=path):
                self.assertEqual(self.call(path)[0], 404)
        self.assertEqual(self.call(f"/api/doc/{self.pid}?lang=xx"), (400, {"error": "unknown language xx"}))


if __name__ == "__main__":
    unittest.main()

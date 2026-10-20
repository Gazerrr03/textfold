"""The library's routes on a server of its own (its own HOME and data folder, no model): a document named in the
library is listed and shown under that name (its page's title and head), and a folder goes inside another.

Run from the repo root:
    python3 -m unittest discover tests
"""
import json
import os
import re
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

ROOT = Path(__file__).resolve().parent.parent


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class LibraryRoutes(unittest.TestCase):
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

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=10)
        cls.tmp.cleanup()

    def call(self, path, body=None):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=None if body is None else json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
                return r.status, json.loads(data) if r.headers.get_content_type() == "application/json" else data.decode()
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_a_document_named_in_the_library(self):
        code, r = self.call("/api/import", {"name": "scan-0042.md", "text": "# scan 0042\n\nA paragraph of the scan.\n"})
        self.assertEqual(code, 200)
        pid = r["paper"]
        code, listed = self.call("/api/papers/name", {"paper": pid, "name": "Smith 2024 review"})
        row = next(p for p in listed if p["id"] == pid)
        self.assertEqual((code, row["name"], row["title"]), (200, "Smith 2024 review", "scan 0042"))
        code, page = self.call(f"/p/{pid}")
        self.assertEqual(re.search(r"<title>(.*?)</title>", page).group(1), "Smith 2024 review")
        data = json.loads(re.search(r'<script type="application/json" id="paper-data">(.*?)</script>', page, re.S).group(1))
        self.assertEqual((data["meta"]["name"], data["meta"]["title"]), ("Smith 2024 review", "scan 0042"))
        self.call("/api/papers/name", {"paper": pid, "name": ""})
        code, page = self.call(f"/p/{pid}")   # (its own title again: the page is drawn anew)
        self.assertEqual(re.search(r"<title>(.*?)</title>", page).group(1), "scan 0042")
        self.assertEqual(self.call("/api/papers/name", {"paper": "md-none-0000", "name": "x"})[0], 404)

    def test_a_folder_inside_another(self):
        code, f = self.call("/api/folders", {"op": "new", "name": "Thesis"})
        top = f["folders"][-1]["id"]
        code, f = self.call("/api/folders", {"op": "new", "name": "Chapter 2", "parent": top})
        self.assertEqual((code, f["folders"][-1]["parent"]), (200, top))
        self.assertEqual(self.call("/api/folders", {"op": "nest", "id": top, "parent": f["folders"][-1]["id"]})[0], 400)


if __name__ == "__main__":
    unittest.main()

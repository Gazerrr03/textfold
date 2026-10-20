"""The reader's language, told to the server for other programs (the settings' "lang", in GET /api/models), and the
languages a text can be read in (GET /api/langs), on a server of its own (its own HOME, where the settings are, and
data folder; no model).

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

from textfold import langs

ROOT = Path(__file__).resolve().parent.parent


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ReaderLang(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.home, data = Path(cls.tmp.name) / "home", Path(cls.tmp.name) / "data"
        cls.home.mkdir()
        cls.settings = cls.home / ".textfold" / "settings.json"
        cls.port = free_port()
        env = {**os.environ, "HOME": str(cls.home), "USERPROFILE": str(cls.home), "LOCALAPPDATA": str(cls.home / "AppData" / "Local"),
               "TEXTFOLD_DATA": str(data), "TEXTFOLD_NO_MODELS": "1", "PYTHONUSERBASE": site.getuserbase()}
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
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def saved(self):
        return json.loads(self.settings.read_text(encoding="utf-8")) if self.settings.exists() else {}

    def test_the_languages_by_their_own_names(self):
        code, got = self.call("/api/langs")
        self.assertEqual(code, 200)
        self.assertEqual(got, [{"code": c, "name": n} for c, n in langs.natives().items()])
        self.assertEqual(got[:2], [{"code": "en", "name": "English"}, {"code": "zh", "name": "简体中文"}])

    def test_told_kept_and_reported(self):
        # (one test, in order: the server's copy starts empty, as a settings file from before it has none)
        code, d = self.call("/api/models")
        self.assertEqual((code, d["lang"]), (200, None))
        self.assertIsNone(self.saved().get("lang"))
        code, d = self.call("/api/settings", {"lang": "zh-Hant"})
        self.assertEqual((code, d["lang"]), (200, "zh-Hant"))
        self.assertEqual(self.saved()["lang"], "zh-Hant")
        self.assertEqual(self.call("/api/models")[1]["lang"], "zh-Hant")
        self.assertEqual(self.call("/api/settings")[1]["lang"], "zh-Hant")   # (GET /api/settings: the same payload)
        self.assertEqual(self.call("/api/settings", {"lang": "xx"}), (400, {"error": "unknown language xx"}))
        self.assertEqual(self.call("/api/settings", {"lang": None})[0], 400)
        self.assertEqual(self.saved()["lang"], "zh-Hant")   # a language refused changes nothing
        code, d = self.call("/api/settings", {"pdf_tier": "fast"})   # another setting leaves it
        self.assertEqual((code, d["lang"], self.saved()["lang"]), (200, "zh-Hant", "zh-Hant"))


if __name__ == "__main__":
    unittest.main()

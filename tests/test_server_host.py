"""DNS rebinding: a web page that points its own domain at 127.0.0.1 is, to the browser, the same origin as its requests
to TextFold's server, and could read the library (its documents, their PDFs, the notes). Only the name the requests
are addressed to tells them apart, so the server answers a request addressed to this computer alone (localhost,
127.0.0.1, [::1]) and every other one with 421. On a server of its own (its own HOME and data folder, no model).

Run from the repo root:
    python3 -m unittest discover tests
"""
import http.client
import json
import os
import site
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

from textfold import server

ROOT = Path(__file__).resolve().parent.parent


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Names(unittest.TestCase):
    def test_this_computer_under_any_port(self):
        for host in ("localhost:31917", "127.0.0.1:3017", "[::1]:3017", "LOCALHOST:31917", "localhost", "127.0.0.1"):
            self.assertTrue(server.addressed_here(host), host)

    def test_any_other_name(self):
        for host in ("attacker.example:31917", "attacker.example", "127.0.0.1.attacker.example:3017", "localhost.attacker.example",
                     "localhost:31917@attacker.example", "[::1].attacker.example", "127.0.0.2:3017", "0.0.0.0:3017",
                     "localhost:abc", "", None):
            self.assertFalse(server.addressed_here(host), host)


class Rebinding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        home = Path(cls.tmp.name) / "home"
        home.mkdir()
        cls.port = free_port()
        env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home), "LOCALAPPDATA": str(home / "AppData" / "Local"),
               "TEXTFOLD_DATA": str(Path(cls.tmp.name) / "data"), "TEXTFOLD_NO_MODELS": "1", "PYTHONUSERBASE": site.getuserbase()}
        cls.proc = subprocess.Popen([sys.executable, "-m", "textfold", "serve", "--port", str(cls.port)], cwd=ROOT, env=env,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{cls.port}/api/papers", timeout=1)
                break
            except OSError:
                time.sleep(0.1)
        req = urllib.request.Request(f"http://127.0.0.1:{cls.port}/api/import", headers={"Content-Type": "application/json"},
                                     data=json.dumps({"name": "notes.md", "text": "# A private draft\n\nWhat only I should read.\n"}).encode())
        cls.pid = json.loads(urllib.request.urlopen(req, timeout=30).read())["paper"]

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=10)
        cls.tmp.cleanup()

    def ask(self, method, path, host, body=None, origin=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        c.putrequest(method, path, skip_host=True)
        if host is not None:
            c.putheader("Host", host)
        if origin:
            c.putheader("Origin", origin)
        data = json.dumps(body).encode() if body is not None else None
        if data is not None:
            c.putheader("Content-Type", "application/json")
            c.putheader("Content-Length", str(len(data)))
        c.endheaders(data)
        r = c.getresponse()
        out = (r.status, r.read())
        c.close()
        return out

    def test_a_page_under_another_name_reads_nothing(self):
        bad = f"attacker.example:{self.port}"
        for path in ("/", "/api/papers", f"/p/{self.pid}", f"/api/notes/{self.pid}", f"/api/pdf/{self.pid}", "/api/folders",
                     "/api/models", "/api/jobs", "/api/zotero", "/static/app.js", "/oauth/openrouter?code=x"):
            status, data = self.ask("GET", path, bad)
            self.assertEqual(status, 421, path)
            self.assertNotIn(b"private draft", data, path)

    def test_nor_writes(self):
        status, _ = self.ask("POST", "/api/folders", f"attacker.example:{self.port}", {"op": "new", "name": "x"},
                             origin=f"http://attacker.example:{self.port}")
        self.assertEqual(status, 421)
        status, _ = self.ask("POST", "/api/openrouter/start", f"attacker.example:{self.port}", {"back": "/"})
        self.assertEqual(status, 421)   # (its callback would carry the other name)
        self.assertEqual(self.ask("GET", "/api/folders", f"127.0.0.1:{self.port}")[1], b'{"folders": [], "of": {}}')

    def test_this_computer_reads_as_before(self):
        for host in (f"127.0.0.1:{self.port}", f"localhost:{self.port}", f"[::1]:{self.port}"):
            status, data = self.ask("GET", f"/p/{self.pid}", host)
            self.assertEqual(status, 200, host)
            self.assertIn("private draft".encode(), data)
        self.assertEqual(self.ask("GET", "/api/papers", None)[0], 421)   # (no name at all: not a browser's)


if __name__ == "__main__":
    unittest.main()

"""server.json: a running server says where it is in its data folder, and takes it back when it stops, unless a
server started since on the same folder has written its own.

Nothing here touches the reader's own library or settings: the data folder and the home are temporary, and the servers
run here listen on free ports of this computer and look for no model (TEXTFOLD_NO_MODELS).

Run from the repo root:
    python3 -m unittest discover tests
"""
import json
import os
import shutil
import signal
import site
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from datetime import datetime
from pathlib import Path
from unittest import mock

from textfold import __version__, server, store

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Written(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        patch = mock.patch.object(store, "DATA", Path(self.tmp.name))
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_where_the_server_is(self):
        f = server.announce(31917)
        self.assertEqual(f, store.DATA / "server.json")
        got = json.loads(f.read_text(encoding="utf-8"))
        started = got.pop("started")
        self.assertEqual(got, {"format": "textfold/server", "version": 1, "url": "http://127.0.0.1:31917", "port": 31917,
                               "pid": os.getpid(), "textfold": __version__})
        datetime.strptime(started, "%Y-%m-%dT%H:%M:%SZ")   # (ISO, in UTC)
        self.assertEqual([p.name for p in store.DATA.iterdir()], ["server.json"])   # the temporary file became it

    def test_taken_back_only_while_it_is_this_servers(self):
        f = server.announce(31917)
        server.withdraw(f)
        self.assertFalse(f.exists())
        server.withdraw(f)   # (gone already)
        other = {"format": "textfold/server", "version": 1, "url": "http://127.0.0.1:3017", "port": 3017, "pid": os.getpid() + 1}
        f.write_text(json.dumps(other), encoding="utf-8")
        server.withdraw(f)
        self.assertEqual(json.loads(f.read_text(encoding="utf-8")), other)
        f.write_text("{half", encoding="utf-8")
        server.withdraw(f)
        self.assertTrue(f.exists())


@unittest.skipIf(os.name == "nt", "on Windows a server is ended without a signal, and leaves server.json behind")
class Running(unittest.TestCase):
    """Real servers, each a process of its own on a free port, on one temporary data folder."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="tf-server-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.data = self.tmp / "data"
        self.file = self.data / "server.json"
        # (the packages a user installed stay found: where they are is HOME's, unless PYTHONUSERBASE says)
        self.env = {**os.environ, "HOME": str(self.tmp), "TEXTFOLD_DATA": str(self.data), "TEXTFOLD_NO_MODELS": "1",
                    "PYTHONUSERBASE": site.getuserbase()}

    def start(self):
        """A server, once its server.json is written and the address in it answers."""
        port = free_port()
        proc = subprocess.Popen([sys.executable, "-m", "textfold", "serve", "--port", str(port)], cwd=ROOT, env=self.env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(lambda: proc.poll() is None and (proc.kill(), proc.wait()))
        for _ in range(150):
            try:
                info = json.loads(self.file.read_text(encoding="utf-8"))
                if info["pid"] == proc.pid:
                    with urllib.request.urlopen(info["url"] + "/api/papers", timeout=5) as r:
                        if r.status == 200:
                            return proc, info
            except (OSError, ValueError):
                pass
            time.sleep(0.1)
        self.fail("the server wrote no server.json, or its address did not answer")

    def test_said_while_it_runs_and_taken_back_at_ctrl_c(self):
        proc, info = self.start()
        port = info["port"]
        self.assertEqual((info["url"], info["textfold"]), (f"http://127.0.0.1:{port}", __version__))
        proc.send_signal(signal.SIGINT)
        proc.wait(timeout=10)
        self.assertFalse(self.file.exists())

    def test_a_server_started_since_keeps_its_own(self):
        first, _ = self.start()
        second, _ = self.start()
        first.send_signal(signal.SIGTERM)   # (how the desktop app ends its server)
        first.wait(timeout=10)
        self.assertEqual(json.loads(self.file.read_text(encoding="utf-8"))["pid"], second.pid)
        second.send_signal(signal.SIGTERM)
        self.assertEqual(second.wait(timeout=10), -signal.SIGTERM)   # ended by the signal, at once, as before
        self.assertFalse(self.file.exists())


if __name__ == "__main__":
    unittest.main()

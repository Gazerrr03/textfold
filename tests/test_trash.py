"""A deleted paper stays in papers/.trash for 30 days; then the server erases it as it starts (store.empty_trash), by
the time in its folder's name. Nothing else there is touched: a folder of another name, a file, a link to a folder
elsewhere. A server erases the old ones when it starts and keeps the rest.

Run from the repo root:
    python3 -m unittest discover tests
"""
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
from unittest import mock

from textfold import store

ROOT = Path(__file__).resolve().parent.parent


def stamp(days_ago, now):
    return time.strftime("%Y%m%d-%H%M%S", time.localtime(now - days_ago * 86400))


def deleted(trash, pid, when):
    d = trash / f"{pid}-{when}"
    (d / "layers").mkdir(parents=True)
    (d / "meta.json").write_text("{}", encoding="utf-8")
    (d / "notes.json").write_text('{"notes": []}', encoding="utf-8")
    return d


class EmptyTrash(unittest.TestCase):
    def test_older_than_30_days_erased(self):
        now = time.time()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(store, "DATA", Path(tmp) / "data"):
            trash = store.DATA / "papers" / ".trash"
            old = [deleted(trash, "2512.23916", stamp(31, now)), deleted(trash, "md-notes-1a2b", stamp(400, now)),
                   deleted(trash, "web-example-org-0123456789ab", stamp(30.01, now))]
            kept = [deleted(trash, "2512.23916", stamp(29, now)), deleted(trash, "pdf-0123456789abcdef", stamp(0, now))]
            other = trash / "mine-20200101-000000"   # not a paper's id
            other.mkdir()
            plain = trash / "kept by hand"
            plain.mkdir()
            loose = trash / "md-loose-1-20200101-000000"   # a file, not a folder
            loose.write_text("x", encoding="utf-8")
            outside = Path(tmp) / "elsewhere"
            (outside / "inside").mkdir(parents=True)
            link = trash / "md-link-1-20200101-000000"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except OSError:   # (Windows without the right to make one)
                link = None
            living = store.DATA / "papers" / "2512.23916"
            living.mkdir(parents=True)

            gone = store.empty_trash(now=now)
            self.assertEqual(sorted(gone), sorted(d.name for d in old))
            self.assertFalse(any(d.exists() for d in old))
            self.assertTrue(all((d / "notes.json").exists() for d in kept))
            self.assertTrue(other.is_dir() and plain.is_dir() and loose.is_file() and living.is_dir())
            self.assertTrue((outside / "inside").is_dir())
            if link:
                self.assertTrue(link.is_symlink())
            self.assertEqual(store.empty_trash(now=now), [])   # (nothing more to erase)
            # a paper deleted 29 days ago goes two days later
            self.assertEqual(store.empty_trash(now=now + 2 * 86400), [kept[0].name])

    def test_no_trash(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(store, "DATA", Path(tmp)):
            self.assertEqual(store.empty_trash(), [])


class AtStart(unittest.TestCase):
    def test_server_erases_old_ones(self):
        now = time.time()
        with tempfile.TemporaryDirectory() as tmp:
            home, data = Path(tmp) / "home", Path(tmp) / "data"
            home.mkdir()
            trash = data / "papers" / ".trash"
            old, new = deleted(trash, "md-old-1", stamp(45, now)), deleted(trash, "md-new-1", stamp(3, now))
            with socket.socket() as s:
                s.bind(("127.0.0.1", 0))
                port = s.getsockname()[1]
            env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home), "LOCALAPPDATA": str(home / "AppData" / "Local"),
                   "TEXTFOLD_DATA": str(data), "TEXTFOLD_NO_MODELS": "1", "PYTHONUSERBASE": site.getuserbase()}
            proc = subprocess.Popen([sys.executable, "-m", "textfold", "serve", "--port", str(port)], cwd=ROOT, env=env,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                for _ in range(100):
                    try:
                        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/papers", timeout=1):
                            break
                    except OSError:
                        time.sleep(0.1)
                for _ in range(50):
                    if not old.exists():
                        break
                    time.sleep(0.1)
                self.assertFalse(old.exists())
                self.assertTrue((new / "notes.json").exists())
            finally:
                proc.terminate()
                proc.wait(timeout=10)


if __name__ == "__main__":
    unittest.main()

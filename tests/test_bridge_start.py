"""The ChatGPT bridge's start (#12): without a Codex login its sign-in runs first and its link reaches the status; what
stops a start reaches the status as an error, in openai-oauth's words, at once rather than after five minutes. A fake
npx stands in for openai-oauth; nothing is written outside a temporary folder and no browser opens.

Run from the repo root:
    python3 -m unittest discover tests
"""
import os
import tempfile
import textwrap
import time
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from textfold import bridges

FAKE = {
    "login fails": """
        case "$*" in *login*) echo "Starting login"; echo "Error: the sign-in was refused"; exit 1;; esac
        exit 0""",
    "bridge fails": """
        case "$*" in *--detach*) echo "No auth file was found."; echo "Run npx openai-oauth login and try again."; exit 1;; esac
        exit 0""",
    "sign-in waits": """
        case "$*" in *login*) echo "OpenAI OAuth login URL: https://auth.example.com/authorize?a=1&b=2"; sleep 30;; esac
        exit 0""",
}


@unittest.skipIf(os.name == "nt", "the fake npx is a shell script")
class BridgeStart(unittest.TestCase):
    def start(self, kind, login):
        tmp = Path(tempfile.mkdtemp())
        npx = tmp / "bin" / "npx"
        npx.parent.mkdir()
        npx.write_text("#!/bin/sh\n" + textwrap.dedent(FAKE[kind]))
        npx.chmod(0o755)
        refused = mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused"))
        for p in (refused, mock.patch.object(bridges, "HOME", tmp / "home"), mock.patch.object(bridges, "codex_login", return_value=login),
                  mock.patch.dict(os.environ, {"PATH": f"{npx.parent}{os.pathsep}{os.environ['PATH']}"}),
                  mock.patch("webbrowser.open"), mock.patch.dict(bridges._START, {"thread": None, "login": None, "error": None})):
            p.start()
            self.addCleanup(p.stop)
        bridges._SEEN.update(at=0.0, status=None)
        bridges.bridge_start()
        for _ in range(100):
            st = bridges.bridge_status(fresh=True)
            if st.get("error") or st.get("login"):
                return st
            time.sleep(0.1)
        return st

    def test_a_refused_sign_in_says_so(self):
        st = self.start("login fails", login=False)
        self.assertIn("the sign-in was refused", st["error"])

    def test_a_bridge_that_stops_says_why(self):
        st = self.start("bridge fails", login=True)
        self.assertIn("No auth file was found", st["error"])

    def test_the_sign_in_link_reaches_the_status_and_the_browser(self):
        st = self.start("sign-in waits", login=False)
        self.assertEqual(st["login"], "https://auth.example.com/authorize?a=1&b=2")
        import webbrowser
        webbrowser.open.assert_called_once_with("https://auth.example.com/authorize?a=1&b=2")


class Said(unittest.TestCase):
    def test_only_this_starts_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "bridge.log"
            log.write_text("an earlier start's reason\n")
            since = log.stat().st_size
            with open(log, "a") as f:
                f.write("\nthis start's reason\n")
            self.assertEqual(bridges._said(log, since), "this start's reason")


class CodexLogin(unittest.TestCase):
    def test_codex_home_is_looked_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "auth.json").write_text("{}")
            with mock.patch.dict(os.environ, {"CODEX_HOME": tmp}):
                self.assertTrue(bridges.codex_login())


if __name__ == "__main__":
    unittest.main()

"""A page sent from the reader's own browser (extension/, capture.py): native messaging's frames, a snapshot checked and
kept as a web page of the library (its HTML beside it, never over a page already there), the host's loop, and its
manifest, which lets only the extensions named reach it.

Run from the repo root:
    python3 -m unittest discover tests
"""
import io
import json
import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from textfold import capture, store, webpage

WORDS = ("The river office kept the gauges for a century, and its records show how the spring floods rose and fell "
         "with the snow on the hills, year after year, in the same slow rhythm the town still lives by. ")
PAGE = ("<!doctype html><html><head><title>Rivers</title></head><body><article><h1>Rivers</h1>"
        + "".join(f"<p>Paragraph {k}. {WORDS}</p>" for k in range(1, 5))
        + '<p>Read hourly<span class="mark">*</span><span data-tf-css-hidden="1" style="display:none">Since 2019.</span>.</p>'
        + "</article></body></html>")
SNAP = {"format": "textfold/snapshot", "version": 1, "url": "https://news.example.org/rivers#top", "title": "Rivers | Example",
        "html": PAGE, "taken": "2026-10-26T20:00:00Z", "how": "extension"}


def framed(obj):
    body = json.dumps(obj).encode()
    return struct.pack("=I", len(body)) + body


class Frames(unittest.TestCase):
    def test_a_message_there_and_back(self):
        out = io.BytesIO()
        capture.write_message(out, {"ok": True, "said": "日本語"})
        self.assertEqual(capture.read_message(io.BytesIO(out.getvalue())), {"ok": True, "said": "日本語"})
        self.assertIsNone(capture.read_message(io.BytesIO(b"")))   # (the browser closed the stream)

    def test_too_large_or_cut_off(self):
        with self.assertRaisesRegex(ValueError, "too-large"):
            capture.read_message(io.BytesIO(struct.pack("=I", capture.MAX + 1)))
        with self.assertRaisesRegex(ValueError, "cut-off"):
            capture.read_message(io.BytesIO(framed({"a": 1})[:-2]))


class Receive(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data = Path(tmp.name)
        for p in (mock.patch.object(store, "DATA", self.data), mock.patch("textfold.local.prefetch", lambda srcs: {})):
            p.start()
            self.addCleanup(p.stop)

    def test_what_is_not_a_snapshot_of_a_web_page(self):
        for bad, said in (({"format": "other"}, "not-a-snapshot"), (dict(SNAP, url="file:///Users/x/a.html"), "not-a-web-page"),
                          (dict(SNAP, url="chrome://settings"), "not-a-web-page"), (dict(SNAP, html="  "), "no-page")):
            with self.assertRaisesRegex(ValueError, said):
                capture.receive(bad)

    def test_kept_as_a_web_page_with_its_snapshot(self):
        r = capture.receive(SNAP)
        pid = webpage.pid_of("https://news.example.org/rivers")   # (its fragment aside)
        self.assertEqual((r["ok"], r["paper"], r["new"], r["open"]), (True, pid, True, None))
        d = store.pdir(pid)
        self.assertEqual((d / "snapshot.html").read_text(encoding="utf-8"), PAGE)
        self.assertTrue((d / "source.md").exists())
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual((meta["source"]["via"], meta["snapshot_kind"], meta["snapshot_taken"]), ("browser", "browser", SNAP["taken"]))
        html = (d / "source.html").read_text(encoding="utf-8")
        self.assertIn("Paragraph 4.", html)
        self.assertIn('<sup class="ltx_note_mark">*</sup>', html)   # (hidden on its mark: a note)

    def test_a_page_already_there_is_not_written_over(self):
        pid = capture.receive(SNAP)["paper"]
        before = (store.pdir(pid) / "source.html").read_text(encoding="utf-8")
        r = capture.receive(dict(SNAP, html=PAGE.replace("Paragraph 1.", "Changed.")))
        self.assertEqual((r["paper"], r["new"]), (pid, False))
        self.assertEqual((store.pdir(pid) / "source.html").read_text(encoding="utf-8"), before)

    def test_a_page_that_names_itself_nowhere_takes_the_tab_s_title(self):
        page = PAGE.replace("<title>Rivers</title>", "").replace("<h1>Rivers</h1>", "")
        pid = capture.receive(dict(SNAP, url="https://bare.example.org/x", html=page, title="What the tab said"))["paper"]
        self.assertEqual(json.loads((store.pdir(pid) / "meta.json").read_text(encoding="utf-8"))["title"], "What the tab said")

    def test_the_reader_opens_where_textfold_runs(self):
        (self.data / "server.json").write_text(json.dumps({"format": "textfold/server", "url": "http://127.0.0.1:4100", "pid": os.getpid()}))
        r = capture.receive(SNAP)
        self.assertEqual(r["open"], f"http://127.0.0.1:4100/p/{r['paper']}")
        (self.data / "server.json").write_text(json.dumps({"url": "http://127.0.0.1:4100", "pid": 2 ** 22 + 12345}))   # (gone)
        self.assertIsNone(capture.receive(SNAP)["open"])

    def test_the_host_answers_each_message_until_the_stream_ends(self):
        out = io.BytesIO()
        code = capture.host(io.BytesIO(framed(SNAP) + framed({"format": "other"})), out)
        stream = io.BytesIO(out.getvalue())
        first, second = capture.read_message(stream), capture.read_message(stream)
        self.assertEqual((code, first["ok"], second), (0, True, {"ok": False, "error": "not-a-snapshot"}))


class Install(unittest.TestCase):
    def test_only_the_extensions_named(self):
        ext = "hgmpkjklkepgaeppbpaphfjpkicgicbb"
        with tempfile.TemporaryDirectory() as tmp:
            out = capture.install([ext], dirs={"chrome": Path(tmp) / "c", "edge": Path(tmp) / "e"}, home=Path(tmp) / "home")
            self.assertEqual(len(out), 2)
            m = json.loads(out[0].read_text())
            self.assertEqual((m["name"], m["type"], m["allowed_origins"]), (capture.HOST, "stdio", [f"chrome-extension://{ext}/"]))
            launcher = Path(m["path"]).read_text()
            self.assertIn("-m textfold capture-host", launcher)
            self.assertTrue(os.access(m["path"], os.X_OK))
            self.assertEqual(len(capture.install([ext], ["edge"], dirs={"chrome": Path(tmp) / "c", "edge": Path(tmp) / "e"}, home=Path(tmp) / "home")), 1)
        for bad in ([], ["not-an-id"], ["HGMPKJKLKEPGAEPPBPAPHFJPKICGICBB"]):
            with self.assertRaisesRegex(ValueError, "32 letters"):
                capture.install(bad, dirs={"chrome": "/nowhere"})


if __name__ == "__main__":
    unittest.main()

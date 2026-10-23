"""A paragraph's and a section's id for the life of a document (ids.py): written into source.html when the text is
stored, read from there by a later TextFold, kept by the paragraphs and sections still there when the text is replaced
or converted again, never given to another, and, for those that are gone, where they went (ids.json, GET /api/ids,
the reader's page). In a data folder of its own; no model is called, the engine is not run, and nothing is fetched.

Run from the repo root:
    python3 -m unittest discover tests
"""
import json
import re
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_replace import TEXT, Base, FakeJobs   # noqa: E402

from textfold import ids, local, markdown, pdfdoc, semantic, server, store   # noqa: E402
from textfold.notes import _spans   # noqa: E402
from textfold.parse import parse   # noqa: E402

PID = "pdf-0123456789abcdef"
HEAT = "Heat pumps move heat from a cold place to a warm one, and the compressor does the work."
TANK = "The buffer tank stores heat for the night, so that the pump can rest while the price is high."
HOUSE = "A paragraph the accurate conversion found before the others, about the house and its walls."
ROOF = "The roof was insulated last, after the windows, which let the least heat out of all."


def bare(page):
    """A page as a TextFold before this stored it: no ids written in."""
    return re.sub(r' data-[us]="[^"]*"', "", page)


class Pdf(Base):
    """A PDF stored and converted again (pdfdoc.store_pdf, with the engine's reading given: one section's paragraphs)."""

    def convert(self, paragraphs, replace=True):
        text = "## 1 Heating\n\n" + "\n\n".join(paragraphs) + "\n"
        with (mock.patch.object(pdfdoc, "cut_figures", return_value=None),
              mock.patch.object(pdfdoc, "to_markdown", return_value=("Heat at Home", [], text)),
              mock.patch.object(pdfdoc, "layout_of", return_value=[])):
            pdfdoc.store_pdf(PID, self.tmp.name, {}, "a.pdf", "fast", replace=replace)
        doc = store.parsed(PID)
        return {_spans(u["toks"], doc["atoms"])[0]: uid for uid, u in doc["units"].items()}


class Frozen(Base):
    def test_a_stored_page_carries_its_ids_and_reads_the_same(self):
        pid = local.import_text(TEXT, "diary.md")
        page = store.read_text(store.pdir(pid) / "source.html")
        meta = json.loads(store.read_text(store.pdir(pid) / "meta.json"))
        doc = parse(page, meta)
        self.assertEqual(page.count("data-u="), len(doc["units"]))
        self.assertEqual(page.count("data-s="), len(doc["chunks"]))
        before = parse(bare(page), meta)   # read as before: the same ids, words and sections
        self.assertEqual((doc["units"], doc["chunks"], doc["blocks"]), (before["units"], before["chunks"], before["blocks"]))

    def test_a_later_reading_keeps_the_ids_written(self):
        html = semantic.normalize(markdown.to_html("## One\n\nFirst words.\n\nSecond words.\n")[0])
        meta = {"id": PID, "title": "A PDF", "source": {"kind": "pdf"}}
        page, doc = ids.freeze(html, meta)
        self.assertEqual(list(doc["units"]), ["u0", "u1"])
        # a later TextFold reads one more paragraph first: without the ids written in, u0 and u1 would name others
        later = page.replace('<p class="ltx_p" data-u="u0">', '<p class="ltx_p">A paragraph read now.</p><p class="ltx_p" data-u="u0">')
        doc = parse(later, meta)
        words = {_spans(u["toks"], doc["atoms"])[0]: uid for uid, u in doc["units"].items()}
        self.assertEqual((words["First words."], words["Second words."]), ("u0", "u1"))
        self.assertNotIn(words["A paragraph read now."], ("u0", "u1"))


class Carried(Pdf):
    def test_a_pdf_converted_again_keeps_its_paragraphs_ids(self):
        was = self.convert([HEAT, TANK], replace=False)
        now = self.convert([HOUSE, HEAT, TANK])   # one more paragraph found first: its place was HEAT's
        self.assertEqual((now[HEAT], now[TANK]), (was[HEAT], was[TANK]))
        self.assertNotIn(now[HOUSE], was.values())
        self.assertFalse((store.pdir(PID) / ids.FILE).exists())   # nothing gone

    def test_a_gone_id_is_not_given_to_another_and_its_section_is_kept(self):
        was = self.convert([HEAT, TANK, HOUSE], replace=False)
        self.convert([HEAT, HOUSE])
        gone = ids.load(PID)
        self.assertEqual(set(gone["units"]), {was[TANK]})
        sid = store.parsed(PID)["chunks"][0]["id"]
        self.assertEqual(gone["units"][was[TANK]]["section"], sid)
        now = self.convert([HEAT, ROOF, HOUSE])   # a new paragraph where the tank's was: an id of its own
        self.assertNotIn(now[ROOF], was.values())
        self.assertEqual(set(ids.load(PID)["units"]), {was[TANK]})   # (kept through another conversion)

    def test_a_markdown_text_edited_keeps_its_ids(self):
        pid = local.import_text(TEXT, "diary.md")
        _, u = self.units(pid)
        local.replace_text(pid, TEXT.replace("Nobody felt the change.", "No one felt the change.")
                           .replace("\nThe neighbours asked how loud it was.\n", "\n"))
        _, v = self.units(pid)
        self.assertEqual(v["sec-monday"], u["sec-monday"])   # the edited paragraph too
        self.assertEqual(v["sec-tuesday"], u["sec-tuesday"][:1])
        loud = u["sec-tuesday"][1]
        self.assertEqual(ids.load(pid)["units"][loud]["section"], "sec-tuesday")
        # the section gone as well, its last paragraph moved up under Monday: the gone paragraph follows it there
        local.replace_text(pid, TEXT.replace("## Tuesday\n", "").replace("\nThe neighbours asked how loud it was.\n", "\n"))
        gone = ids.load(pid)
        self.assertEqual(gone["sections"]["sec-tuesday"]["now"], "sec-monday")
        self.assertEqual(gone["units"][loud]["section"], "sec-monday")
        _, w = self.units(pid)
        self.assertIn(u["sec-tuesday"][0], w["sec-monday"])   # (it kept its id under its new heading)

    def test_words_put_back_take_their_id_back(self):
        pid = local.import_text(TEXT, "diary.md")
        _, u = self.units(pid)
        loud = u["sec-tuesday"][1]
        local.replace_text(pid, TEXT.replace("\nThe neighbours asked how loud it was.\n", "\n"))
        self.assertIn(loud, ids.load(pid)["units"])
        local.replace_text(pid, TEXT)
        _, v = self.units(pid)
        self.assertEqual(v["sec-tuesday"][1], loud)
        self.assertNotIn(loud, ids.load(pid)["units"])


class Lookup(Pdf):
    def setUp(self):
        super().setUp()
        settings = mock.patch.object(server.models, "load_settings", return_value={})   # (not the reader's own)
        settings.start()
        self.addCleanup(settings.stop)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(FakeJobs()))
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def get(self, path):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.httpd.server_port}{path}", timeout=30) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_api_ids_says_what_each_id_names_now(self):
        pid = local.import_text(TEXT, "diary.md")
        _, u = self.units(pid)
        loud, heat = u["sec-tuesday"][1], u["sec-monday"][0]
        local.replace_text(pid, TEXT.replace("## Tuesday\n", "").replace("\nThe neighbours asked how loud it was.\n", "\n"))
        code, got = self.get(f"/api/ids/{pid}?u={heat},{loud},p-00000000&s=sec-monday,sec-tuesday,sec-nowhere")
        self.assertEqual(code, 200)
        self.assertEqual(got["units"], {heat: {"here": True}, loud: {"gone": True, "section": "sec-monday"}, "p-00000000": {"unknown": True}})
        self.assertEqual(got["sections"], {"sec-monday": {"here": True}, "sec-tuesday": {"now": "sec-monday"}, "sec-nowhere": {"unknown": True}})
        self.assertEqual(self.get("/api/ids/md-gone-12345678?u=u1")[0], 404)

    def test_the_reader_page_knows_the_gone_ids(self):
        was = self.convert([HEAT, TANK], replace=False)
        self.assertNotIn('"gone":', server.reader_page(PID))
        self.convert([HEAT])
        page = server.reader_page(PID)
        data = json.loads(re.search(r'<script[^>]*id="paper-data"[^>]*>(.*?)</script>', page, re.S).group(1).replace("<\\/", "</"))
        self.assertEqual(list(data["gone"]["units"]), [was[TANK]])


if __name__ == "__main__":
    unittest.main()

"""A PDF converted again (accurately, POST /api/convert): the generations of its old text stop, and write nothing (a
translation of the old paragraphs, laid on the new ones by their places, showed each at another paragraph, outdated);
after the conversion the document is generated again in every language it had or was being generated in, not only
the one the page showed when the button was pressed. In a data folder of its own; no model is called, the engine is
not run, and nothing is fetched.

Run from the repo root:
    python3 -m unittest discover tests
"""
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_replace import TEXT, fake_model   # noqa: E402

from textfold import llm, local, pipeline, server, store   # noqa: E402

SPEC = {"id": "fake/model", "kind": "api", "protocol": "openai", "base": "http://127.0.0.1:9", "api_key": "", "model": "fake"}
PID = "pdf-0123456789abcdef"
PAGE = '<article class="ltx_document"><section class="ltx_section" id="s1"><p class="ltx_p">{}</p></section></article>'


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        for p in (mock.patch.object(store, "DATA", Path(self.tmp.name)),
                  mock.patch.object(server.models, "load_settings", return_value={})):   # (not the reader's own)
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)

    def stored(self, langs=("zh",)):
        """A converted PDF with its English and translations, as a fast conversion left it."""
        d = store.pdir(PID)
        d.mkdir(parents=True)
        (d / "meta.json").write_text('{"id": "%s", "title": "A paper", "source": {"kind": "pdf", "name": "a.pdf", "tier": "fast"}}' % PID)
        (d / "source.html").write_text(PAGE.format("The fast conversion's text."), encoding="utf-8")
        (d / "source.pdf").write_bytes(b"%PDF-1.4")
        store.write(PID, "en", {"version": "v1", "units": {}, "chunks": {}, "edges": []})
        for lang in langs:
            store.write(PID, f"tr-{lang}", {"version": "v2", "base": "v1", "units": {}, "chunks": {}})
        return d


class Pipeline(Base):
    def test_a_translation_stopped_before_it_is_written_is_not(self):
        pid = local.import_text(TEXT, "diary.md")
        stop = threading.Event()

        def build(*a, **kw):   # its last answer came as the document was converted again
            stop.set()
        with mock.patch.object(llm, "_once", fake_model([])), mock.patch.dict(os.environ):
            os.environ.pop("TEXTFOLD_NO_MODELS", None)   # (the build runs the tests with it: the model here is a stand-in)
            pipeline.generate(pid, "en", SPEC)
            with mock.patch.object(pipeline.translate, "build", build), self.assertRaises(llm.Stopped):
                pipeline.generate(pid, "zh", SPEC, stop=stop)
        self.assertIsNone(store.read(pid, "tr-zh"))
        self.assertIsNotNone(store.read(pid, "en"))


class Superseded(Base):
    def setUp(self):
        super().setUp()
        p = mock.patch.object(server.threading, "Thread")   # (no workers: the jobs stay as they are put)
        p.start()
        self.addCleanup(p.stop)
        self.jobs = server.Jobs()

    def test_its_generations_stop_and_its_languages_are_given(self):
        self.stored(langs=("de",))
        running = self.jobs.submit(PID, "zh", False)
        running["status"] = "running"
        queued = self.jobs.submit(PID, "ja", False)
        other = self.jobs.submit("2401.00001", "zh", False)
        self.assertEqual(self.jobs.superseded(PID), ["en", "de", "zh", "ja"])
        self.assertTrue(running["stopping"] and self.jobs.stops[running["id"]].is_set())
        self.assertEqual(queued["status"], "stopped")
        self.assertEqual(other["status"], "queued")   # another paper's goes on
        again = self.jobs.submit(PID, "zh", False)
        self.assertNotEqual(again["id"], running["id"])   # a new one, of the new text: not the one being stopped


class Convert(Base):
    def test_its_old_translation_stops_and_every_language_is_made_again(self):
        d = self.stored()
        calls, started = [], threading.Event()

        def generate(pid, lang, spec, force=False, progress=None, log=None, stop=None):
            calls.append((lang, (d / "source.html").read_text(encoding="utf-8")))
            if len(calls) == 1:   # the old text's translation, long under way when the conversion ends
                started.set()
                if not stop.wait(10):
                    raise AssertionError("the old text's generation went on")
                raise llm.Stopped()

        def store_pdf(pid, folder, sc, name, tier, replace=False):   # the accurate text, in place of the fast one
            self.assertTrue(replace)
            shutil.rmtree(d / "layers")
            (d / "source.html").write_text(PAGE.format("The accurate conversion's text."), encoding="utf-8")
        for p in (mock.patch.object(server.pipeline, "generate", generate), mock.patch.object(server.models, "resolve", return_value=SPEC),
                  mock.patch.object(server.engine, "convert"), mock.patch.object(server.pdfdoc, "read_output", return_value={}),
                  mock.patch.object(server.pdfdoc, "store_pdf", store_pdf)):
            p.start()
            self.addCleanup(p.stop)
        jobs = server.Jobs()
        old = jobs.submit(PID, "zh", False)
        self.assertTrue(started.wait(10))
        conv = jobs.convert(PID, d / "source.pdf", "a.pdf", "en", "accurate", replace=True)   # pressed while it showed English
        end = time.time() + 20
        while any(j["status"] in ("queued", "running") for j in jobs.items.values()) and time.time() < end:
            time.sleep(0.05)
        self.assertEqual((old["status"], conv["status"]), ("stopped", "done"))
        self.assertEqual([lang for lang, _ in calls], ["zh", "en", "zh"])
        self.assertTrue(all("accurate" in text for _, text in calls[1:]))
        self.assertEqual(jobs.items[conv["next"]]["lang"], "en")


if __name__ == "__main__":
    unittest.main()

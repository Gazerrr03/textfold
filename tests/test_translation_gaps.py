"""A translation that came back with paragraphs missing (reported: some paragraphs of a paper stayed in English). One
call that failed (a timeout, a rate limit, a reply that was not JSON) or a paragraph the model left out was stored as
it was, and since the translation existed, opening it never asked again. Now what comes back without a translation is
asked for once more at once, the paragraphs alone; a translation stored with gaps still (made before, or failed twice)
has them asked for the next time its language is generated, the rest kept. A model that stands in for one, a data
folder of its own; no network.

Run from the repo root:
    python3 -m unittest discover tests
"""
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from textfold import llm, local, pipeline, store, translate

TEXT = """# Notes on folding

## Introduction

Readers skim long papers. They miss the argument.

A ladder of levels helps them. Each level keeps the one below it.

## Method

We fold each paragraph into a takeaway. The takeaway is one line.

We check the folds by hand.
"""
CFG = {"kind": "api", "id": "fake/translator", "effort": "none"}


class Model:
    """Answers the translation prompts as a model would, in Chinese: every unit, its sentences one to one. fail: the
    sections whose calls fail (once, or always); leave: the English words of a paragraph it leaves out of its reply
    (once, or always). cache: where its replies are kept, as llm.call keeps them."""
    def __init__(self, fail=(), always=False, leave=None, cache=None):
        self.fail, self.always, self.leave, self.cache = set(fail), always, leave, cache
        self.asked = []

    def __call__(self, prompt, schema, model, cache_dir, force=False, timeout=900, system=None):
        if "titles" in schema["properties"]:
            names = prompt.split("\n\n")[-1].split("\n")
            return {"out": {"titles": [f"题：{t}" for t in names]}, "cost": 0}, False
        sec = re.sub(r"^[\d.]+\s+", "", re.search(r"^This section: (.*)$", prompt, re.M).group(1))
        units = re.findall(r"^\[U(\d+)\][^\n]*\n((?:  \d+: [^\n]*\n)+)", prompt, re.M)
        self.asked.append((sec, [re.findall(r"  \d+: ([^\n]*)", body)[0] for _, body in units]))
        for name in self.fail:
            if name in sec:
                if not self.always:
                    self.fail.discard(name)
                raise RuntimeError("timed out")
        out = {"section": {"title": f"节：{sec}", "takeaway": "这一节的要点", "topic": "要点"}, "units": [],
               "paper_title": "关于折叠的笔记"}
        for n, body in units:
            sents = re.findall(r"  \d+: ([^\n]*)", body)
            if self.leave and self.leave in body:
                if not self.always:
                    self.leave = None
                continue
            out["units"].append({"id": f"U{n}", "sentences": [f"译文{k}：{s[:12]}。" for k, s in enumerate(sents)],
                                 "takeaway": "这一段的要点", "reason": "", "topic": "要点"})
        rec = {"out": out, "cost": 0}
        if self.cache:
            f = Path(self.cache) / f"{len(self.asked)}.json"
            f.write_text(json.dumps(rec), encoding="utf-8")
            rec["file"] = str(f)
        return rec, False


class Gaps(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        p = mock.patch.object(store, "DATA", self.tmp / "data")
        p.start()
        self.addCleanup(p.stop)
        self.pid = local.import_text(TEXT)

    def doc(self):
        return store.assemble(self.pid)   # (no English layer yet: each unit's own local levels)

    def build(self, model, doc=None):
        doc = doc or self.doc()
        with mock.patch.object(llm, "call", model):
            translate.build(doc, "zh", CFG, self.tmp / "cache", jobs=1, log=lambda *a: None)
        return doc

    def method_units(self, doc):
        return next(c for c in doc["chunks"] if c["title"] == "Method")["units"]

    def test_a_part_that_failed_is_asked_for_again_at_once(self):
        model = Model(fail=["Method"])
        doc = self.build(model)
        self.assertEqual(translate.gaps(doc, "zh"), [])
        self.assertEqual([s for s, _ in model.asked].count("Method"), 2)
        c = next(c for c in doc["chunks"] if c["title"] == "Method")
        self.assertEqual(c["tr"]["zh"]["title"], "节：Method")   # (the section's own lines, from the call asked again)
        self.assertIsNotNone(c["tr"]["zh"]["lad"])

    def test_a_paragraph_left_out_is_asked_for_alone(self):
        model = Model(leave="We check the folds")
        doc = self.build(model)
        self.assertEqual(translate.gaps(doc, "zh"), [])
        self.assertEqual(model.asked[-1], ("Method", ["We check the folds by hand."]))   # that paragraph, nothing else

    def test_one_left_out_again_stays_a_gap_and_that_reply_is_not_kept(self):
        (self.tmp / "replies").mkdir()
        model = Model(leave="We check the folds", always=True, cache=self.tmp / "replies")
        doc = self.build(model)
        uid = self.method_units(doc)[1]
        self.assertEqual(translate.gaps(doc, "zh"), [uid])
        kept = sorted(f.name for f in (self.tmp / "replies").iterdir())
        self.assertNotIn(f"{len(model.asked)}.json", kept)   # (asked again next time, not read back)
        self.assertIn("1.json", kept)   # (the first replies stay: the rest of their sections is in them)

    def test_a_stored_translation_with_gaps_fills_them_and_keeps_the_rest(self):
        doc = self.build(Model(fail=["Method"], always=True))
        store.save_en(doc, "fake/levels")
        store.save_tr(doc, "zh", store.read(self.pid, "en")["version"], "fake/translator")
        intro = {uid: doc["units"][uid]["tr"]["zh"] for c in doc["chunks"] if c["title"] == "Introduction" for uid in c["units"]}
        again = self.doc()
        self.assertEqual(again["meta"]["gaps"], {"zh": 2})   # (what the reader is told, and the app asks for)
        model = Model()
        with mock.patch.object(llm, "call", model):
            translate.fill(again, "zh", CFG, self.tmp / "cache", jobs=1, log=lambda *a: None)
        self.assertEqual([s for s, _ in model.asked], ["Method"])
        self.assertEqual(translate.gaps(again, "zh"), [])
        self.assertEqual({uid: again["units"][uid]["tr"]["zh"] for uid in intro}, intro)

    def test_the_generation_of_a_language_with_gaps_fills_them(self):
        doc = self.build(Model(fail=["Method"], always=True))
        store.save_en(doc, "fake/levels")
        version = store.read(self.pid, "en")["version"]
        store.save_tr(doc, "zh", version, "fake/translator")
        with mock.patch.object(llm, "call", Model()):
            pipeline.generate(self.pid, "zh", CFG)
        tr = store.read(self.pid, "tr-zh")
        self.assertEqual(tr["base"], version)
        self.assertEqual(len(tr["units"]), len(self.doc()["units"]))
        self.assertNotIn("gaps", self.doc()["meta"])
        with mock.patch.object(translate, "fill") as fill:   # nothing missing: nothing asked
            pipeline.generate(self.pid, "zh", CFG)
        fill.assert_not_called()

    def test_without_a_model_a_translation_with_gaps_still_opens(self):
        doc = self.build(Model(fail=["Method"], always=True))
        store.save_en(doc, "fake/levels")
        store.save_tr(doc, "zh", store.read(self.pid, "en")["version"], "fake/translator")
        with mock.patch.object(translate, "fill") as fill:
            self.assertEqual(pipeline.generate(self.pid, "zh", None), self.pid)
        fill.assert_not_called()

    def test_a_formula_alone_is_no_gap(self):
        self.assertFalse(translate.worded({"toks": [{"a": "a1"}, {"t": "."}]}))
        self.assertFalse(translate.worded({"toks": [{"t": "D"}]}))   # (a letter a figure left behind)
        self.assertTrue(translate.worded({"toks": [{"t": "Folding"}, {"a": "a1"}]}))
        self.assertTrue(translate.worded({"toks": [{"t": "折叠"}]}))

    def test_a_line_translated_without_a_takeaway_is_kept(self):   # (keywords: seen with a real model)
        doc = self.doc()
        uid = self.method_units(doc)[1]
        u = doc["units"][uid]
        z = translate.assemble(u, {"sentences": ["我们手工检查折叠。"], "takeaway": "", "reason": "", "topic": ""},
                               doc["atoms"], "zh", lambda w: None)
        self.assertIsNotNone(z)
        self.assertIn("手工", "".join(tk.get("t", "") for tk in z["lad"]["brief"]))


if __name__ == "__main__":
    unittest.main()

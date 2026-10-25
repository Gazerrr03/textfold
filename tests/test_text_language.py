"""A text's levels are written in its own language, and that language is never translated (#65). Before, the levels'
base was always called English: a Chinese document's own levels (written in Chinese) were listed as English, reading
it in Chinese asked the model to translate the whole of it into Chinese again, and it could not be read in English. A
German one's lines were asked for in English. Now the language is read from the text (langs.detect) and kept with its
ladder (en.json "lang"); reading the text in it is the ladder, English is a translation like any other, and a note made
on the text's own words before (said "en") stays on them. A translation into the text's own language made before is
read while its ladder stands, so nothing read before goes. A model that stands in for one, a data folder of its own; no
network.

Run from the repo root:
    python3 -m unittest discover tests
"""
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from textfold import fold, langs, ladder, llm, local, notes, pipeline, store, translate

ZH = """# 折叠阅读的笔记

## 引言

读者常常略读长篇论文，因而错过了论证的主线。一层层的摘要可以帮助他们看清全文。

每一层都保留下面一层的要点，读者可以随时放大回原文。

## 方法

我们把每一段折叠成一个要点，这个要点只有一行。我们再逐段检查这些折叠是否准确。
"""
EN = """# Notes on folding

## Introduction

Readers skim long papers, and they miss the argument. A ladder of levels helps them see the whole of it.

Each level keeps the one below it, and the reader can zoom back in at any time.

## Method

We fold each paragraph into a takeaway that is one line. Then we check the folds by hand, one by one.
"""
DE = """# Notizen zum Falten

## Einleitung

Die Leser überfliegen lange Arbeiten und verpassen das Argument, das nicht leicht zu sehen ist. Eine Leiter von Ebenen hilft ihnen.

Jede Ebene behält die darunter, und der Leser kann jederzeit wieder in den Text hineinzoomen.

## Methode

Wir falten jeden Absatz in eine Zeile. Dann prüfen wir die Falten von Hand, eine nach der anderen, und das ist auch gut so.
"""
CFG = {"kind": "api", "id": "fake/model", "effort": "none"}


class Model:
    """Answers the ladder's and the translation's prompts as a model would, and keeps what it was asked."""
    def __init__(self):
        self.ladders, self.translations = [], []

    def __call__(self, prompt, schema, model, cache_dir, force=False, timeout=900, system=None):
        if "titles" in schema["properties"]:
            return {"out": {"titles": [f"T: {t}" for t in prompt.split("\n\n")[-1].split("\n")]}, "cost": 0}, False
        units = re.findall(r"^\[U(\d+)\][^\n]*\n((?:  \d+: [^\n]*\n?)+)", prompt, re.M)
        if prompt.startswith("Translate one section"):
            self.translations.append(prompt)
            out = {"section": {"title": "Section", "takeaway": "The point of the section", "topic": "point"}, "units": [],
                   "paper_title": "Notes on folding"}
            for n, body in units:
                sents = re.findall(r"  \d+: ([^\n]*)", body)
                out["units"].append({"id": f"U{n}", "sentences": [f"Sentence {k}." for k in range(len(sents))],
                                     "takeaway": "The point of the paragraph", "reason": "", "topic": "point"})
            return {"out": out, "cost": 0}, False
        self.ladders.append(prompt)
        line = "这一段的要点" if "这" in prompt or "的" in prompt else "The point of the paragraph"
        out = {"section": {"takeaway": line, "topic": line[:2]},
               "units": [{"id": f"U{n}", "role": "claim", "takeaway": line, "topic": line[:2], "reason": "", "evidence": [0]}
                         for n, _ in units]}
        return {"out": out, "cost": 0}, False


class TextLanguage(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        for obj, key, value in ((store, "DATA", self.tmp / "data"),):
            p = mock.patch.object(obj, key, value)
            p.start()
            self.addCleanup(p.stop)
        self.model = Model()
        for target, name, value in ((llm, "call", self.model), (pipeline, "task", lambda cfg, name: cfg),
                                    (pipeline.links, "build", lambda *a, **k: 0)):
            p = mock.patch.object(target, name, value)
            p.start()
            self.addCleanup(p.stop)

    def generate(self, pid, lang):
        return pipeline.generate(pid, lang, CFG, jobs=1)

    def test_the_language_is_read_from_the_text(self):
        for text, want in ((ZH, "zh"), (EN, "en"), (DE, "de")):
            with self.subTest(want=want):
                self.assertEqual(store.text_lang(local.import_text(text, f"{want}.md")), want)
        self.assertEqual(langs.detect("本文提出了一種新的方法，我們在多個基準上進行了實驗，結果表明這個方法是有效的。"), "zh-Hant")
        self.assertEqual(langs.detect("この論文では、新しい手法を提案する。複数のベンチマークで実験を行った。"), "ja")
        self.assertEqual(langs.detect("ผลลัพธ์แสดงว่าวิธีนี้ช่วยให้ผู้อ่านเข้าใจบทความยาวได้ดีขึ้น และใช้เวลาน้อยลง"), "th")
        self.assertEqual(langs.detect("$x$ 1 2 3"), "en")   # (too little to tell: English, as before)

    def test_a_chinese_text_read_in_chinese_is_not_translated(self):
        pid = local.import_text(ZH, "zh.md")
        self.generate(pid, "zh")
        self.assertTrue(self.model.ladders)
        self.assertEqual(self.model.translations, [])   # (before: the whole text, into Chinese again)
        self.assertEqual(store.read(pid, "en")["lang"], "zh")
        self.assertEqual(store.languages(pid), [])
        meta = store.assemble(pid)["meta"]
        self.assertEqual((meta["lang"], meta["langs"], meta["translated"]), ("zh", ["zh"], []))
        self.assertEqual(next(p for p in store.papers() if p["id"] == pid)["langs"], ["zh"])
        self.assertEqual(fold.document(pid)["lang"], "zh")

    def test_english_is_a_translation_of_it(self):
        pid = local.import_text(ZH, "zh.md")
        self.generate(pid, "zh")
        self.assertEqual(fold.document(pid, "en")["lang"], "zh")   # (not translated yet: in its own language)
        self.generate(pid, "en")
        self.assertTrue(self.model.translations)
        self.assertIn("into English", self.model.translations[0])
        self.assertIn("numbered Simplified Chinese sentences", self.model.translations[0])
        self.assertEqual(store.languages(pid), ["en"])
        meta = store.assemble(pid)["meta"]
        self.assertEqual((meta["langs"], meta["translated"], meta["stale"]), (["zh", "en"], ["en"], []))
        self.assertEqual(fold.document(pid, "en")["lang"], "en")

    def test_a_text_in_another_language_writes_its_lines_in_it(self):
        self.generate(local.import_text(DE, "de.md"), None)
        self.assertIn("ONE German sentence", self.model.ladders[0])
        self.assertNotIn("English sentence", self.model.ladders[0])

    def test_an_english_text_folds_and_translates_as_before(self):
        pid = local.import_text(EN, "en.md")
        self.generate(pid, "zh")
        self.assertIn("ONE English sentence", self.model.ladders[0])
        self.assertIn("numbered English sentences", self.model.translations[0])
        self.assertIn("English takeaway:", self.model.translations[0])
        meta = store.assemble(pid)["meta"]
        self.assertEqual((meta["lang"], meta["langs"]), ("en", ["en", "zh"]))

    def test_a_translation_into_its_own_language_from_before_is_read_while_its_ladder_stands(self):
        pid = local.import_text(ZH, "zh.md")
        doc = store.assemble(pid)
        doc["meta"]["lang"] = None   # a ladder from before 0.10.33 names no language
        store.save_en(doc, "fake/levels")
        en = store.read(pid, "en")
        en.pop("lang")
        store.write(pid, "en", en)
        with mock.patch.object(llm, "call", Model()):
            translate.build(doc, "zh", CFG, self.tmp / "cache", jobs=1, log=lambda *a: None)
        store.save_tr(doc, "zh", en["version"], "fake/translator")
        meta = store.assemble(pid)["meta"]
        self.assertEqual((meta["lang"], meta["langs"], meta["translated"], meta["stale"]), ("zh", ["zh"], ["zh"], []))
        store.write(pid, "en", {**en, "version": "2099-01-01T00:00:00"})   # its ladder written again: the old one goes
        meta = store.assemble(pid)["meta"]
        self.assertEqual((meta["langs"], meta["translated"], meta["stale"]), (["zh"], [], []))
        self.generate(pid, "zh")
        self.assertEqual(self.model.translations, [])   # (not made again either)

    def test_a_note_on_its_own_words_from_before_stays_on_them(self):
        pid = local.import_text(ZH, "zh.md")
        self.generate(pid, "zh")
        uid = next(iter(store.assemble(pid)["units"]))
        old = {"id": "n-1", "anchor": {"unit": uid, "lang": "en", "level": 4, "tokens": [0, 2]}, "text": "我的笔记",
               "kind": "ask", "thread": [{"q": "为什么？", "a": "因为。", "lang": "en"}]}
        f = store.pdir(pid) / "notes.json"
        f.write_text(json.dumps({"format": "textfold/notes", "version": 1, "notes": [old]}), encoding="utf-8")
        seen = notes.read(pid)["notes"][0]
        self.assertEqual((seen["anchor"]["lang"], seen["thread"][0]["lang"]), ("zh", "zh"))
        self.assertEqual(json.loads(f.read_text(encoding="utf-8"))["notes"][0]["anchor"]["lang"], "en")   # (only read so)
        self.generate(pid, "en")   # its English translation: the file says the text's own language first
        self.assertEqual(json.loads(f.read_text(encoding="utf-8"))["notes"][0]["anchor"]["lang"], "zh")
        notes.put(pid, {**old, "id": "n-2", "anchor": {**old["anchor"], "lang": "en"}, "thread": []})
        self.assertEqual({n["id"]: n["anchor"]["lang"] for n in notes.read(pid)["notes"]}, {"n-1": "zh", "n-2": "en"})

    def test_the_prompt_of_an_english_text_is_unchanged(self):
        doc = store.assemble(local.import_text(EN, "en.md"))
        chunk = next(c for c in doc["chunks"] if c["units"])
        with_lang = ladder.prompt_for(doc, chunk)
        doc["meta"].pop("lang")
        self.assertEqual(with_lang, ladder.prompt_for(doc, chunk))   # (named or not, English: the replies kept still fit)
        self.assertEqual(translate.prompt_for({**doc, "meta": {**doc["meta"], "lang": "en"}}, chunk, "zh"),
                         translate.prompt_for(doc, chunk, "zh"))


if __name__ == "__main__":
    unittest.main()

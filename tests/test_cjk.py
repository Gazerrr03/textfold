"""Regression test: a Chinese (CJK) document folds the way the reader can use it.

Chinese is written without spaces and ends a sentence with 。！？ rather than ". ". Three things followed from the
English-only sentence splitter, and each is held here so it cannot come back:

  1. split_sentences() took a whole Chinese paragraph as one sentence, so every level below Full was that
     paragraph again — the five levels collapsed into one.
  2. parse.add_units() cut a paragraph of more than 12 "sentences" into parts, and a part takes the next free id;
     on a Chinese paper that moved every later unit's id, so layer data keyed on ids landed on other paragraphs.
     cjk_heavy() keeps a CJK paragraph whole.
  3. A contents line, a footnote and a figure label are not units of argument: is_apparatus() says so, and such a
     unit folds to nothing instead of appearing as a stray line in the key sentences.

Run from the repo root:
    python3 -m unittest discover tests
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from textfold import ladder, local, store
from textfold.parse import cjk_heavy
from textfold.tokens import plain, split_sentences, tokenize_text

CJK_SENTENCES = "金融机构应当履行反洗钱义务。客户身份资料应当保存五年！是否合规？"
EN_SENTENCES = "The first sentence. The second one! And a third?"
TOC_LINE = "第一章 绪论 ………… 1"
FOOTNOTE = "①魏敬淼.金融法学[M].北京：中国政法大学出版社，2013：45."
ARGUMENT = "金融机构应当履行反洗钱义务，客户身份资料应当保存五年。"
ELLIPSIS_IN_PROSE = "该理论认为，市场调节并非万能……但需要法律介入。"


def spans(text):
    return [text[a:b] for a, b in split_sentences(tokenize_text(text))]


def apparatus(text):
    return ladder.is_apparatus({"toks": tokenize_text(text)}, {})


class TestSplitSentences(unittest.TestCase):
    def test_cjk_stop_ends_a_sentence(self):
        self.assertEqual(spans(CJK_SENTENCES),
                         ["金融机构应当履行反洗钱义务。", "客户身份资料应当保存五年！", "是否合规？"])

    def test_english_is_unchanged(self):
        self.assertEqual(len(spans(EN_SENTENCES)), 3)

    def test_a_number_opening_a_heading_stays_with_it(self):
        self.assertEqual(spans("1.研究背景与意义。本文讨论第三方支付。"), ["1.研究背景与意义。", "本文讨论第三方支付。"])
        toks = tokenize_text("1. Introduction. We test it.")
        self.assertEqual([plain(toks[a:b], {}) for a, b in split_sentences(toks)], ["1.", "Introduction.", "We test it."])   # (as before)


class TestParagraphsStayWhole(unittest.TestCase):
    def test_cjk_paragraph_is_not_cut(self):
        self.assertTrue(cjk_heavy(tokenize_text("中文段落永远不按句数切块。" * 20)))

    def test_english_paragraph_is_not_marked(self):
        self.assertFalse(cjk_heavy(tokenize_text("An English paragraph is cut by the sentence budget. " * 5)))


class TestApparatus(unittest.TestCase):
    def test_contents_line(self):
        self.assertTrue(apparatus(TOC_LINE))

    def test_footnote_with_citation(self):
        self.assertTrue(apparatus(FOOTNOTE))

    def test_argument_is_not_apparatus(self):
        self.assertFalse(apparatus(ARGUMENT))

    def test_ellipsis_inside_prose_is_not_a_contents_line(self):
        self.assertFalse(apparatus(ELLIPSIS_IN_PROSE))


class TestTopicSpan(unittest.TestCase):
    def test_topic_is_not_cut_mid_word(self):
        text = "第三方支付的法律监管"
        span = ladder.cjk_topic_span(text, 8)
        self.assertIsNotNone(span)
        topic = text[span[0]:span[1]]
        self.assertFalse(topic.endswith("第三"), topic)
        self.assertTrue(topic.startswith("第三方"), topic)


class TestTakeawayDensity(unittest.TestCase):
    """A section shows its points at Takeaway, not its reading list (fold_background)."""

    def doc_of(self, *units):
        doc = {"atoms": {}, "units": {}}
        for i, (role, take) in enumerate(units):
            u = {"role": role, "ev": [0], "brief": [{"t": c} for c in take], "tn": len(take), "topic": [],
                 "toks": [{"t": c} for c in take]}   # (the unit's own text: the document's script is read from it)
            u["lad"] = u
            doc["units"][f"u{i}"] = u
        return doc

    def fold(self, doc, stake=None):
        if stake:
            doc["stake"] = {"take": [{"t": c} for c in stake]}
        ladder.fold_background({"units": list(doc["units"]), "lad": doc.get("stake")}, doc)

    def kept(self, doc):
        return [bool(u["lad"]["tn"]) for u in doc["units"].values()]

    def test_a_run_of_background_keeps_two_lines(self):
        doc = self.doc_of(("context", "甲乙丙"), ("context", "丁戊"), ("context", "己庚"), ("context", "辛壬"))
        self.fold(doc)
        self.assertEqual(self.kept(doc), [True, True, True, False])

    def test_a_claim_frees_the_next_line(self):
        doc = self.doc_of(("context", "甲乙"), ("claim", "丙丁"), ("context", "戊己"),
                          ("context", "庚辛"), ("context", "壬癸"))
        self.fold(doc)
        self.assertEqual(self.kept(doc), [True, True, True, True, False])

    def test_a_line_that_opens_with_its_source_steps_down(self):
        doc = self.doc_of(("context", "甲"), ("context", "《某办法》规定乙丙丁"), ("context", "戊己"))
        self.fold(doc)
        self.assertEqual(self.kept(doc), [True, False, True])

    def test_a_line_with_a_colon_states_a_list_and_stays(self):
        doc = self.doc_of(("context", "甲"), ("context", "资本要求：乙丙丁"))
        self.fold(doc)
        self.assertEqual(self.kept(doc), [True, True])

    def test_the_opening_line_always_stands(self):
        doc = self.doc_of(("context", "《某办法》规定甲"), ("context", "乙"))
        self.fold(doc)
        self.assertEqual(self.kept(doc), [True, True])

    def test_a_line_that_repeats_the_section_line_steps_down(self):
        stake = "既有监管模式不适应第三方跨境支付发展"
        doc = self.doc_of(("claim", stake), ("claim", "另有一点与摘要无关"))
        self.fold(doc, stake)
        self.assertEqual(self.kept(doc), [False, True])

    def test_an_english_section_is_left_alone(self):
        doc = self.doc_of(("context", "One fact here."), ("context", "Another fact here."),
                          ("context", "A third one."))
        self.fold(doc)
        self.assertEqual(self.kept(doc), [True, True, True])


class TestDress(unittest.TestCase):
    """dress(): the sentence a page break cut in half."""

    def unit(self, text, role="context", tn=1):
        toks = [{"t": c} for c in text]
        sents, a = [], 0
        for i, c in enumerate(text):
            if c in "。！？":
                sents.append([a, i + 1])
                a = i + 1
        if a < len(text):
            sents.append([a, len(text)])
        lad = {"role": role, "ev": [0], "brief": [{"t": "一句话"}], "tn": tn, "topic": []}
        return {"role": role, "toks": toks, "sents": sents, "lad": lad}

    def dress(self, *units, stake="本节摘要"):
        doc = {"atoms": {}, "units": {}}
        for i, u in enumerate(units):
            u["lad"]["role"] = u["role"]
            doc["units"][f"u{i}"] = u
        chunk = {"units": list(doc["units"]), "lad": {"take": [{"t": c} for c in stake]}}
        ladder.dress(chunk, doc)
        return doc

    def test_a_paragraph_cut_across_a_page_break_carries_its_tail(self):
        doc = self.dress(self.unit("从前都是部门规章，而该条例的法律位阶为行政"),
                         self.unit("法规，加强了对第三方支付机构的监管力度。"))
        self.assertIn("而该条例的法律位阶为行政", doc["units"]["u1"]["lad"]["glue"])

    def test_a_paragraph_that_ends_whole_carries_nothing(self):
        doc = self.dress(self.unit("这一段说完了。"), self.unit("下一段另起。"))
        self.assertNotIn("glue", doc["units"]["u1"]["lad"])

    def test_a_footnote_between_the_two_halves_is_stepped_over(self):
        doc = self.dress(self.unit("至少需要五名熟悉外汇业务的工作人"),
                         self.unit("① 某某.某书[M].2017: 99"),
                         self.unit("员，并且在提交材料时需核实。"))
        self.assertIn("工作人", doc["units"]["u2"]["lad"]["glue"])

    def test_a_short_tail_carries_the_sentence_it_belongs_to(self):
        """最后一个小句太短（「…财务状况的」），只带它读者看到半句：整句带过去，而且后面那句也一起显示。"""
        doc = self.dress(self.unit("在对资本要求的动态监管方面，还有对于第三方支付机构财务状况的"),
                         self.unit("要求。第三方支付机构的亏损累计达到实缴资本的百分之五十。"))
        lad = doc["units"]["u1"]["lad"]
        self.assertTrue(lad["glue"].startswith("在对资本要求"))
        self.assertIn(1, lad["ev"])


class TestEnglishAsBefore(unittest.TestCase):
    """The CJK rules are a CJK document's only: an English paper gets the prompt it got, the same no-model levels,
    no apparatus, no glue and nothing new for the reader."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        data = mock.patch.object(store, "DATA", Path(tmp.name))
        data.start()
        self.addCleanup(data.stop)

    def doc(self, text):
        return store.assemble(local.import_text(text))

    def test_the_english_prompt(self):
        doc = self.doc("# A paper\n\nWe sum over i = 1, ..., N to get the loss. It holds.\n")
        prompt = ladder.prompt_for(doc, next(c for c in doc["chunks"] if c["units"]))
        self.assertIn("ONE English sentence of at most 14 words", prompt)
        self.assertIn("ONE sentence of at most 16 words stating what this section establishes in the text; topic, at most 3 words", prompt)   # (a text, not a paper: kinds.adapt)
        self.assertNotIn("Each line is read on its own", prompt)
        self.assertIn("no em or en dashes", prompt)
        self.assertNotIn("cjk", doc["meta"])

    def test_the_chinese_prompt(self):
        doc = self.doc("# 中文测试\n\n" + ARGUMENT + "这是第二句。\n")
        prompt = ladder.prompt_for(doc, next(c for c in doc["chunks"] if c["units"]))
        self.assertIn("Each line is read on its own", prompt)
        self.assertIn("ONE sentence of at most 40 characters", prompt)
        self.assertTrue(doc["meta"]["cjk"])

    def test_an_english_unit_with_an_ellipsis_still_folds(self):
        doc = self.doc("# A paper\n\nWe sum over i = 1, ..., N to get the loss.\n")
        u = next(iter(doc["units"].values()))
        self.assertTrue(apparatus(plain_text := "We sum over i = 1, ..., N to get the loss."), plain_text)   # (alone it reads as dot leaders)
        self.assertTrue(ladder.local(u, doc["atoms"], False)["brief"])
        o = {"takeaway": "The loss sums over all items", "topic": "loss", "reason": "", "evidence": [0]}
        self.assertTrue(ladder.assemble(u, o, doc["atoms"], "m", False)["brief"])

    def test_without_a_model_the_first_sentence(self):
        doc = self.doc("# A paper\n\nA short first one. Then: a second sentence that has a colon in it.\n")
        u = next(iter(doc["units"].values()))
        lad = ladder.local(u, doc["atoms"], False)
        s, e = u["sents"][0]
        self.assertEqual([tk.get("m") for tk in lad["brief"]], list(range(s, e)))

    def test_an_english_section_is_not_dressed(self):
        doc = self.doc("# A paper\n\nWe define the loss as\n\nthe sum of the errors, which we minimise.\n")
        for u in doc["units"].values():
            u["lad"] = ladder.local(u, doc["atoms"], False)
        chunk = next(c for c in doc["chunks"] if c["units"])
        ladder.dress(chunk, doc)
        for u in doc["units"].values():
            self.assertNotIn("glue", u["lad"])


if __name__ == "__main__":
    unittest.main()

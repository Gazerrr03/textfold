"""Thai text: no space between words, one between clauses and sentences.

Python has no Thai dictionary, so a Thai clause is cut into syllables the way a Chinese one is cut into characters;
the reader breaks its lines between words (reader.js, thaiWords).

Run from the repo root:
    python3 -m unittest discover tests
"""
import unittest

from textfold import langs, translate
from textfold.tokens import norm, plain, split_sentences, tokenize_text, words


def texts(toks):
    return [tk["t"] for tk in toks]


class ThaiTest(unittest.TestCase):
    def test_a_clause_is_cut_into_syllables_that_keep_their_vowels_and_tones(self):
        toks = tokenize_text("ผลลัพธ์แสดงว่าได้ผล")
        self.assertEqual(texts(toks), ["ผ", "ล", "ลั", "พ", "ธ์", "แส", "ด", "ง", "ว่า", "ได้", "ผ", "ล"])
        self.assertEqual(plain(toks, {}), "ผลลัพธ์แสดงว่าได้ผล")

    def test_a_space_still_ends_a_clause_and_other_scripts_stay_whole(self):
        toks = tokenize_text("ใช้ GPT-4 กับ 3.14% และ ๓.๑๔ (Smith, 2020)")
        self.assertEqual(texts(toks), ["ใช้", "GPT-4", "กั", "บ", "3.14%", "และ", "๓.๑๔", "(", "Smith", ",", "2020", ")"])
        self.assertEqual(plain(toks, {}), "ใช้ GPT-4 กับ 3.14% และ ๓.๑๔ (Smith, 2020)")
        self.assertEqual(words(toks), 9)   # (the brackets and the comma are not words)

    def test_a_tone_mark_keeps_two_syllables_apart_for_the_morph(self):
        self.assertNotEqual(norm({"t": "ที่"}, {}), norm({"t": "ที"}, {}))

    def test_other_scripts_are_unchanged(self):
        self.assertEqual(texts(tokenize_text("naïve été, 3.14% done.")), ["naïve", "été", ",", "3.14%", "done", "."])
        self.assertEqual(texts(tokenize_text("中文。")), ["中", "文", "。"])
        self.assertEqual(texts(tokenize_text("यह पहला वाक्य है।")), ["यह", "पहला", "वाक्य", "है", "।"])

    def test_a_reader_of_thai(self):
        self.assertEqual(langs.name("th"), "Thai")
        self.assertEqual(langs.natives()["th"], "ภาษาไทย")
        self.assertFalse(langs.cjk("th"))   # its sentences are joined by a space
        self.assertEqual(langs.stop("th"), ".")
        self.assertEqual(langs.budget("th")["unit"], "characters")
        self.assertIn("Thai", langs.punctuation_rule("th"))

    def test_a_translation_into_thai(self):
        toks = tokenize_text("Folding helps. It costs little.")
        sents = split_sentences(toks)
        u = {"id": "p1", "toks": toks, "sents": [list(s) for s in sents], "lad": {"ev": [0]}}
        out = {"sentences": ["การพับช่วยได้", "ใช้ต้นทุนต่ำ"], "takeaway": "การพับช่วยผู้อ่านได้มาก",
               "reason": "ต้นทุนต่ำ", "topic": "การพับ"}
        warnings = []
        z = translate.assemble(u, out, {}, "th", warnings.append)
        self.assertEqual(warnings, [])
        self.assertEqual(plain(z["toks"], {}), "การพับช่วยได้ ใช้ต้นทุนต่ำ")   # the sentences are one space apart
        self.assertEqual([plain(z["toks"][a:b], {}) for a, b in z["sents"]], ["การพับช่วยได้", "ใช้ต้นทุนต่ำ"])
        lad = z["lad"]
        self.assertEqual(plain(lad["brief"], {}), "การพับช่วยผู้อ่านได้มาก. ต้นทุนต่ำ.")
        self.assertEqual(plain(lad["topic"], {}), "การพับ")
        self.assertEqual([lad["brief"][tk["k"]]["t"] for tk in lad["topic"]], texts(lad["topic"]))   # slides from the takeaway


if __name__ == "__main__":
    unittest.main()

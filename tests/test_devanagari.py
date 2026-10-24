"""Hindi text: words keep their vowel signs, and the danda ends a sentence.

Run from the repo root:
    python3 -m unittest discover tests
"""
import unittest

from textfold import langs
from textfold.tokens import plain, split_sentences, tokenize_text, words


def texts(toks):
    return [tk["t"] for tk in toks]


class DevanagariTest(unittest.TestCase):
    def test_vowel_signs_stay_in_their_word(self):
        # re's \\w does not match combining marks: "पहला" used to come out as "पहल" + "ा"
        toks = tokenize_text("यह पहला वाक्य है।")
        self.assertEqual(texts(toks), ["यह", "पहला", "वाक्य", "है", "।"])
        self.assertEqual(words(toks), 4)
        self.assertEqual(plain(toks, {}), "यह पहला वाक्य है।")

    def test_the_danda_ends_a_sentence(self):
        toks = tokenize_text("यह पहला वाक्य है। यह दूसरा वाक्य है। तीसरा।")
        self.assertEqual([plain(toks[a:b], {}) for a, b in split_sentences(toks)],
                         ["यह पहला वाक्य है।", "यह दूसरा वाक्य है।", "तीसरा।"])

    def test_brief_joins_hindi_with_a_danda(self):
        self.assertEqual(langs.stop("hi"), "।")
        self.assertEqual(langs.stop("en"), ".")
        self.assertEqual(langs.stop("zh"), "。")

    def test_other_scripts_are_unchanged(self):
        self.assertEqual(texts(tokenize_text("naïve été, 3.14% done.")),
                         ["naïve", "été", ",", "3.14%", "done", "."])
        self.assertEqual(texts(tokenize_text("中文。")), ["中", "文", "。"])


if __name__ == "__main__":
    unittest.main()

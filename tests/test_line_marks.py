"""A mark made on a written line (Key, Takeaway) keeps the words of the line that were selected (anchor.shown), the
model's too: they are what a question about it is asked on, and what the notes keep through a save and a text
found again. In a data folder of its own; no model is called.

Run from the repo root:
    python3 -m unittest discover tests
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from textfold import local, notes, store
from textfold.tokens import plain

TEXT = "# Spacing\n\nA review pooled 317 experiments and found spaced practice ahead of massed practice. The best gap grows with how long the material has to last.\n"


class LineMarks(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        p = mock.patch.object(store, "DATA", Path(tmp.name))
        p.start()
        self.addCleanup(p.stop)
        self.pid = local.import_text(TEXT, "spacing.md")
        self.doc = store.assemble(self.pid)
        self.uid = next(iter(self.doc["units"]))
        lad = self.doc["units"][self.uid]["lad"]
        self.line = plain(lad["brief"][:lad["tn"]], self.doc["atoms"])

    def note(self, **anchor):
        return {"id": "n-line0001", "kind": "ask", "text": "", "thread": [],
                "anchor": {"unit": self.uid, "section": self.doc["units"][self.uid].get("chunk"), "lang": "en", "sents": [0],
                           "quote": {"exact": "A review pooled 317 experiments", "prefix": "", "suffix": ""}, **anchor}}

    def test_a_question_is_asked_on_the_words_of_the_line(self):
        n = self.note(level=2, tokens=[0, 4], shown={"words": [0, 3], "exact": self.line})
        text, _ = notes.prompt(self.doc, n, "Why?", "en")
        self.assertIn(f'The selected text:\n"{self.line}"', text)
        self.assertIn("The selection is the model's wording", text)

    def test_a_passage_of_the_full_text_as_before(self):
        text, _ = notes.prompt(self.doc, self.note(level=4, tokens=[0, 4]), "Why?", "en")
        self.assertIn('The selected text:\n"A review pooled 317 experiments"', text)
        self.assertNotIn("model's wording", text)

    def test_the_line_is_kept_by_a_save_and_a_text_found_again(self):
        shown = {"words": [0, 3], "exact": self.line}
        notes.put(self.pid, self.note(level=1, tokens=[0, 4], shown=shown))
        doc = store.parsed(self.pid)
        notes.reanchor(self.pid, doc, doc)   # (the same text: every paragraph still there)
        self.assertEqual(notes.read(self.pid)["notes"][0]["anchor"]["shown"], shown)


if __name__ == "__main__":
    unittest.main()

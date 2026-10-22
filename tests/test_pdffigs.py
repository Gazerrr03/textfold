"""pdffigs.py: an arXiv figure whose drawing has words in it (LaTeXML's TikZ picture, its words set by the browser)
is offered as cut from the paper's PDF, and nothing is downloaded until the reader asks (the button); then it is cut
once, where the PDF gives it under the same number and caption, and the offer goes (another button puts it back as
the HTML has it, and offered again). It stays as it was where the PDF
has no such figure, and is offered again where the PDF could not be had. A drawing without words and a paper that is
not arXiv's are left alone. The PDF is written by hand (test_pdftext's page: paragraphs, a drawing between them, its
caption); nothing is downloaded, and the library is a folder of the test's own.

Run from the repo root:
    python3 -m unittest discover tests
"""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_pdftext import PROSE, page_of   # noqa: E402

from textfold import pdffigs   # noqa: E402

CAPTION = "Figure 3: Accuracy over the epochs of training, for the three models compared."
DRAWING = '<svg class="ltx_picture" viewBox="0 0 90 40"><foreignobject width="40" height="9"><span>Step 1</span></foreignobject></svg>'


def a_pdf():
    words = [(72, 720 - 14 * n, 10, PROSE) for n in range(4)]
    words += [(90, 620, 8, "Accuracy"), (240, 490, 8, "Epochs"), (72, 455, 9, CAPTION)]
    words += [(72, 420 - 14 * n, 10, PROSE) for n in range(12)]
    return page_of(words, boxes=[(72, 480, 320, 170)])


def a_doc(pid="2401.00001", caption="Accuracy over the epochs of training, for the three models compared.", html=DRAWING):
    return {"meta": {"id": pid},
            "blocks": [{"k": "fig", "id": "S1.F3", "kind": "figure", "label": "Figure 3", "html": html, "cap": "S1.F3.cap"}],
            "units": {"S1.F3.cap": {"toks": [{"t": w} for w in caption.split()]}}}


class Figures(unittest.TestCase):
    def setUp(self):
        try:
            import pdf_inspector   # noqa: F401
            import pypdfium2   # noqa: F401
        except ImportError:
            self.skipTest("pypdfium2 or pdf-inspector is not installed")
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.pdf = root / "source.pdf"
        self.pdf.write_bytes(a_pdf())
        self.img = root / "2401.00001" / "img"
        self.asked, self.doc, self.pdf_of = [], a_doc(), lambda pid: self.pdf

        def path(pid):
            self.asked.append(pid)
            return self.pdf_of(pid)
        for p in (mock.patch.object(pdffigs.pdf, "path", path), mock.patch.object(pdffigs.store, "pdir", lambda pid: root / pid),
                  mock.patch.object(pdffigs.store, "parsed", lambda pid: copy.deepcopy(self.doc))):
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def page(self, doc=None):
        """The figure's block as a page shows it."""
        doc = copy.deepcopy(doc or self.doc)
        pdffigs.place(doc, self.img, lambda name: f"/p/x/img/{name}")
        return doc["blocks"][0]

    def test_offered_and_nothing_downloaded(self):
        b = self.page()
        self.assertEqual((b["html"], b.get("pdf")), (DRAWING, "offer"))
        self.assertEqual(self.asked, [])

    def test_cut_once_when_asked(self):
        self.assertEqual(pdffigs.from_pdf("2401.00001"), 1)
        b = self.page()
        self.assertTrue(b["html"].startswith('<img class="ltx_graphics pdf-cut" src="/p/x/img/pdf-figure-3.png'), b["html"])
        self.assertEqual(b["pdf"], "cut")   # (the button that puts it back)
        kept = json.loads((self.img / pdffigs.KEPT).read_text(encoding="utf-8"))["3"]
        self.assertTrue((self.img / kept["file"]).is_file())
        self.assertTrue(0.5 < kept["width"] <= 1, kept)
        self.assertIn(f'style="width: {round(100 * kept["width"])}%"', b["html"])
        self.assertEqual(pdffigs.from_pdf("2401.00001"), 1)   # (asked again: from what was kept)
        self.assertEqual(self.asked, ["2401.00001"])

    def test_put_back(self):
        pdffigs.from_pdf("2401.00001")
        cut = json.loads((self.img / pdffigs.KEPT).read_text(encoding="utf-8"))["3"]["file"]
        pdffigs.back("2401.00001")
        self.assertFalse((self.img / cut).exists() or (self.img / pdffigs.KEPT).exists())
        self.assertTrue(self.pdf.exists())   # (the PDF stays)
        b = self.page()
        self.assertEqual((b["html"], b.get("pdf")), (DRAWING, "offer"))

    def test_another_caption_under_that_number_is_not_taken(self):
        self.doc = a_doc(caption="Ablation of the tokenizer over seven benchmark suites and seeds.")
        self.assertEqual(pdffigs.from_pdf("2401.00001"), 0)
        b = self.page()
        self.assertEqual((b["html"], b.get("pdf")), (self.doc["blocks"][0]["html"], None))   # as it was, and no button

    def test_no_pdf_offered_again(self):
        self.pdf_of = lambda pid: None
        with self.assertRaises(LookupError):
            pdffigs.from_pdf("2401.00001")
        self.assertEqual(self.page().get("pdf"), "offer")
        self.pdf_of = lambda pid: self.pdf
        self.assertEqual(pdffigs.from_pdf("2401.00001"), 1)

    def test_left_alone(self):
        plain = '<svg class="ltx_picture" viewBox="0 0 9 9"><path d="M0 0L9 9"></path></svg>'
        self.assertNotIn("pdf", self.page(a_doc(html=plain)))   # a drawing without words
        self.assertNotIn("pdf", self.page(a_doc(pid="md-notes-1234abcd")))   # not arXiv's


if __name__ == "__main__":
    unittest.main()

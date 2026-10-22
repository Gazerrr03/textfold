"""A drawing LaTeXML gives no viewBox, only its size in px (a TikZ picture: arXiv 2610.24110's Figure 1, 2607.27402's
Figure 7), is given one of that size, so that it draws as before and the reader can scale it down to a narrower column
(at Brief, Key and Takeaway) instead of cutting it at the column's edge. A drawing with a viewBox keeps its own; one
inside another, or one sized in other units, is left alone.

Run from the repo root:
    python3 -m unittest discover tests
"""
import unittest

from bs4 import BeautifulSoup

from textfold.parse import parse

HTML = """
<html><body>
<article class="ltx_document">
<section class="ltx_section" id="S1">
<h2 class="ltx_title ltx_title_section">Introduction</h2>
<div class="ltx_para"><p class="ltx_p">A paragraph.</p></div>
<figure class="ltx_figure" id="S1.F1">
<span class="ltx_picture" style="width:345.0pt;height:172.5pt;"><svg id="bare" width="458.28" height="229.14" overflow="visible">
<g><svg id="inner" width="20" height="10"><rect width="20" height="10"/></svg></g></svg></span>
<svg id="own" class="ltx_picture" width="648.68" height="187.07" viewBox="0 0 648.68 187.07"><rect width="5" height="5"/></svg>
<svg id="points" width="12pt" height="8pt"><rect width="5" height="5"/></svg>
<figcaption class="ltx_caption"><span class="ltx_tag">Figure 1:</span> Three drawings.</figcaption>
</figure>
</section>
</article>
</body></html>
"""
META = {"id": "2401.00003", "title": "T", "authors": [], "date": "", "abs_url": "", "html_url": "", "license": ""}


class DrawingViewBox(unittest.TestCase):
    def setUp(self):
        html = next(b["html"] for b in parse(HTML, dict(META))["blocks"] if b.get("k") == "fig")
        self.fig = BeautifulSoup(html, "lxml")

    def box(self, id_):
        svg = self.fig.find("svg", id=id_)
        self.assertIsNotNone(svg, id_)
        return svg.get("viewbox")

    def test_a_drawing_with_only_its_size_has_a_viewbox_of_that_size(self):
        self.assertEqual(self.box("bare"), "0 0 458.28 229.14")
        svg = self.fig.find("svg", id="bare")
        self.assertEqual((svg["width"], svg["height"]), ("458.28", "229.14"))   # (and draws at the same size)

    def test_others_are_left_as_they_are(self):
        self.assertEqual(self.box("own"), "0 0 648.68 187.07")
        self.assertIsNone(self.box("inner"))
        self.assertIsNone(self.box("points"))


if __name__ == "__main__":
    unittest.main()

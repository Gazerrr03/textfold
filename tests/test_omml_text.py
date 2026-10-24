"""An OMML run of normal text (m:nor) becomes \\text{...}: the characters LaTeX treats as special there are escaped.

Run from the repo root:
    python3 -m unittest discover tests
"""
import unittest

from bs4 import BeautifulSoup
from lxml import etree

from textfold.markdown import to_html
from textfold.omml import latex
from textfold.semantic import normalize, tex_math

M = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def normal(text):
    xml = (f'<m:oMath xmlns:m="{M}"><m:r><m:rPr><m:nor/></m:rPr>'
           f'<m:t xml:space="preserve">{text}</m:t></m:r></m:oMath>')
    return latex(etree.fromstring(xml.encode()))


class OmmlNormalTextTest(unittest.TestCase):
    def test_specials_are_escaped(self):
        self.assertEqual(normal("50% off"), r"\text{50\% off}")
        self.assertEqual(normal("R&amp;D"), r"\text{R\&D}")
        self.assertEqual(normal("a_b"), r"\text{a\_b}")
        self.assertEqual(normal("#1"), r"\text{\#1}")
        self.assertEqual(normal("cost $5"), r"\text{cost \$5}")
        self.assertEqual(normal("x^2"), r"\text{x\textasciicircum{}2}")
        self.assertEqual(normal("a~b"), r"\text{a\textasciitilde{}b}")

    def test_backslash_keeps_its_own_braces(self):
        # the braces of \textbackslash{} used to be escaped again: "a\{}b"
        self.assertEqual(normal("a\\b"), r"\text{a\textbackslash{}b}")
        self.assertEqual(normal("{x}"), r"\text{\{x\}}")

    def test_plain_words_are_unchanged(self):
        self.assertEqual(normal("otherwise"), r"\text{otherwise}")


class TextShownTest(unittest.TestCase):
    """A \\text{...} as the reader shows it: latex2mathml ends it at its first } and keeps its escapes as written, so
    semantic.tex_math puts its words back."""

    def shown(self, latex):
        m = tex_math(latex)
        self.assertEqual(m.name, "math")
        self.assertEqual(m["alttext"], latex)   # the model still reads the LaTeX as written
        return m.get_text("").replace("\u00a0", " ")

    def test_a_word_formula_reads_as_written(self):
        # each run of normal text from a Word formula, through the Markdown it is written into
        for text, want in [("50% off", "50% off"), ("R&amp;D", "R&D"), ("a_b", "a_b"), ("#1", "#1"),
                           ("cost $5", "cost $5"), ("x^2", "x^2"), ("a~b", "a~b"), ("a\\b", "a\\b")]:
            html, _ = to_html(f"Before ${normal(text)}+y$ after.\n")
            m = BeautifulSoup(normalize(html), "lxml").find("math")
            self.assertEqual(m.get_text("").replace("\u00a0", " "), want + "+y", text)

    def test_escapes_in_a_markdown_formula(self):
        self.assertEqual(self.shown(r"\text{50\% off} + x"), "50% off+x")
        self.assertEqual(self.shown(r"\mbox{a \& b}"), "a & b")
        self.assertEqual(self.shown(r"\text{a~b}"), "a b")   # a tie: a space that does not break
        self.assertEqual(self.shown(r"\text{if } x > 0"), "if x>0")   # its spaces kept

    def test_a_text_with_math_or_commands_is_left_as_it_was(self):
        self.assertEqual(self.shown(r"\text{if $x$}"), "if $x$")
        self.assertEqual(self.shown(r"\text{bold \textbf{b}}"), "bold \\textbf{b}")


if __name__ == "__main__":
    unittest.main()

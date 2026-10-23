"""An OMML run of normal text (m:nor) becomes \\text{...}: the characters LaTeX treats as special there are escaped.

Run from the repo root:
    python3 -m unittest discover tests
"""
import unittest

from lxml import etree

from textfold.omml import latex

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


if __name__ == "__main__":
    unittest.main()

"""TextFold runs on Python 3.9 and later (requires-python in pyproject.toml), so no module may be written as only a later
Python reads it. An f-string with its own quote inside its braces (f"{x.read_text(encoding="utf-8")}") is read from
Python 3.12 on (PEP 701), and before that it is a SyntaxError: from 0.10.10 to 0.10.30 textfold/build.py had two, and
`python3 -m textfold` did not start on a Mac's own Python 3.9. The tests run on a later Python, which reads them, so
this looks for them in the tokens: inside an f-string's braces, a string in the quote that opened it, or a backslash
(also 3.12 on).

Run from the repo root:
    python3 -m unittest discover tests
"""
import io
import tokenize
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FSTRINGS = hasattr(tokenize, "FSTRING_START")   # (Python 3.12 on: an f-string comes as tokens, its braces' too)


def quote(token):
    """The quote a string token opens with: ' " ''' or \"\"\" (after its prefix, f, r, b...)."""
    body = token.lstrip("rRbBuUfF")
    return body[:3] if body[:3] in ('"""', "'''") else body[:1]


def later_only(source):
    """The lines of `source` with an f-string that only Python 3.12 and later read."""
    lines, outer = [], []   # (the quotes of the f-strings the token is in, the outermost first)
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.FSTRING_START:
            q = quote(tok.string)
            if any(len(o) == 1 and o == q[0] for o in outer):
                lines.append(tok.start[0])
            outer.append(q)
        elif tok.type == tokenize.FSTRING_END:
            outer.pop()
        elif outer and tok.type == tokenize.STRING:
            q = quote(tok.string)
            if any(len(o) == 1 and o == q[0] for o in outer) or "\\" in tok.string:
                lines.append(tok.start[0])
    return lines


@unittest.skipUnless(FSTRINGS, "this Python reads no f-string that 3.9 does not: importing TextFold is the test")
class OldPythonTest(unittest.TestCase):
    def test_the_check_finds_them(self):
        self.assertEqual(later_only('x = f"{p.read_text(encoding="utf-8")}"\n'), [1])
        self.assertEqual(later_only("x = f'{\"\\n\".join(a)}'\n"), [1])
        self.assertEqual(later_only('x = f"{f"{a}"}"\n'), [1])
        self.assertEqual(later_only("x = f\"{p.read_text(encoding='utf-8')}\"\n"), [])
        self.assertEqual(later_only('x = f"""{d["a"]}"""\n'), [])

    def test_every_module(self):
        found = [f"{f.relative_to(ROOT)}:{n}" for f in sorted((ROOT / "textfold").rglob("*.py"))
                 for n in later_only(f.read_text(encoding="utf-8"))]
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()

"""The desktop app's textfold:// links (desktop/links.js) take the documents, levels and languages the server does.

links.js checks a link's parts against its own copies of store.py's ids, fold.py's levels and langs.py's languages:
a kind of document added here and not there would be one whose links the app quietly drops. Its own tests run in
node, here too when node is on the PATH.

Run from the repo root:
    python3 -m unittest discover tests
"""
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from textfold import fold, langs, store

ROOT = Path(__file__).resolve().parent.parent
LINKS = ROOT / "desktop" / "links.js"


def raw(js, name):
    """The pattern a const of String.raw`…` pieces holds."""
    m = re.search(rf"const {name} = ((?:\s*\+?\s*String\.raw`[^`]*`)+);", js)
    return "".join(re.findall(r"String\.raw`([^`]*)`", m.group(1)))


def strings(js, name):
    """The strings of a const array."""
    return re.findall(r"'([^']*)'", re.search(rf"const {name} = \[([^\]]*)\]", js).group(1))


@unittest.skipUnless(LINKS.exists(), "no desktop/ here")
class Links(unittest.TestCase):
    def setUp(self):
        self.js = LINKS.read_text(encoding="utf-8")

    def test_the_ids_are_store_pys(self):
        self.assertEqual(raw(self.js, "ARXIV_ID"), store.ARXIV_ID.pattern)
        self.assertEqual(raw(self.js, "IMPORTED_ID"), store.IMPORTED_ID.pattern)
        self.assertIn("id.length <= 80", self.js)

    def test_the_levels_and_languages(self):
        self.assertEqual(strings(self.js, "LEVELS"), fold.LEVELS)
        self.assertEqual(strings(self.js, "LANGS"), list(langs.LANGS))

    @unittest.skipUnless(shutil.which("node"), "node is not on the PATH")
    def test_in_node(self):
        r = subprocess.run(["node", "--test", "links.test.js"], cwd=LINKS.parent, capture_output=True, text=True,
                           encoding="utf-8", timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()

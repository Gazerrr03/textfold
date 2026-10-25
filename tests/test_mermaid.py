"""A diagram written in Mermaid is drawn (#63). semantic.normalize keeps its source alone as <pre class="pf-mermaid">:
```mermaid in Markdown (and ~~~mermaid, Quarto's ```{mermaid}), a web page's <pre class="mermaid">, <pre lang="mermaid">
or <div class="mermaid">. Other code stays code, and a page's diagram already drawn (an SVG) is not taken for a source.
The page tells the reader where Mermaid is (reader.js drawDiagrams): the app's folder, or inside a single file, which
carries it only when the text has a diagram.

Run from the repo root:
    python3 -m unittest discover tests
"""
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from textfold import build, local, markdown, semantic, server, store

FLOW = "graph TD\n  A[Start] --> B{Ok?}"
DRAWN = "graph TD\n  A[Start] --&gt; B{Ok?}"   # (as it is in the page's HTML)


def sources(html):
    return re.findall(r'<pre class="pf-mermaid">(.*?)</pre>', semantic.normalize(html, sizes=True), re.S)


class Marked(unittest.TestCase):
    def test_markdown_fences(self):
        for fence, close in (("```mermaid", "```"), ("~~~mermaid", "~~~"), ("```{mermaid}", "```")):
            with self.subTest(fence=fence):
                html, _ = markdown.to_html(f"Some text.\n\n{fence}\n{FLOW}\n{close}\n\nMore text.\n")
                self.assertEqual(sources(html), [DRAWN])

    def test_web_pages(self):
        for html in (f'<p>Text.</p><pre class="mermaid">{FLOW.replace(">", "&gt;")}</pre>',
                     f'<p>Text.</p><pre lang="mermaid">{FLOW.replace(">", "&gt;")}</pre>',
                     f'<p>Text.</p><div class="mermaid">{FLOW.replace(">", "&gt;")}</div>'):
            with self.subTest(html=html[:40]):
                self.assertEqual(sources(html), [DRAWN])

    def test_other_code_stays_code(self):
        html, _ = markdown.to_html("Text.\n\n```python\nprint(1 < 2)\n```\n\n```\ngraph TD\n```\n")
        out = semantic.normalize(html, sizes=True)
        self.assertNotIn("pf-mermaid", out)
        self.assertIn("<pre><code>print(1 &lt; 2)", out)

    def test_a_diagram_already_drawn_is_no_source(self):
        self.assertEqual(sources('<p>Text.</p><div class="mermaid"><svg><g><text>A</text></g></svg></div>'), [])


class Page(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patch = mock.patch.object(store, "DATA", Path(tmp.name))
        patch.start()
        self.addCleanup(patch.stop)
        self.diagram = local.import_text(f"# With a diagram\n\nA paragraph.\n\n```mermaid\n{FLOW}\n```\n", "diagram.md")
        self.plain = local.import_text("# Without one\n\nA paragraph.\n\n```python\nprint(1)\n```\n", "plain.md")

    def test_the_app_names_its_folder(self):
        self.assertIn('"mermaid":"/static/vendor/mermaid/"', build.page(store.assemble(self.diagram), app=True))
        self.assertIsNotNone(server.vendor_file("mermaid/mermaid.min.js"))

    def test_a_single_file_carries_it_only_with_a_diagram(self):
        page = build.page(store.assemble(self.diagram))
        self.assertIn('"mermaid":"inside"', page)
        self.assertIn('globalThis["mermaid"]', page)
        self.assertNotIn("</script", page.split('globalThis["mermaid"]')[0].rsplit("<script>", 1)[1])
        page = build.page(store.assemble(self.plain))
        self.assertIn('"mermaid":null', page)
        self.assertNotIn('globalThis["mermaid"]', page)

    def test_a_gallery_keeps_it_beside_its_pages(self):
        self.assertIn('"mermaid":"assets/mermaid/"', build.page(store.assemble(self.diagram), assets="assets/"))


if __name__ == "__main__":
    unittest.main()

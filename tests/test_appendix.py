"""Regression test: a section's appendix semantics survive parsing as an inspectable chunk field.

LaTeXML marks an appendix with the ltx_appendix class, but parse.py read it only as a heading level, so nothing
downstream (the scheduler that will defer appendix work, the reader, an export) could tell a paper's body from its
appendix. The parse now keeps the flag on the chunk ("app"), and the sources that reach the parser through
semantic.normalize carry it too: JATS's <app>, and a conservative title rule for Markdown, PDF and web pages, whose
headings say "Appendix" (or 附录, Anhang, ...) in so many words. References, acknowledgments and supplementary
material are not appendices, and nothing is guessed from a bare letter.

Run from the repo root:
    python3 -m unittest discover tests
"""
import unittest

from textfold import jats, semantic
from textfold.parse import parse

META = {"id": "2401.00003", "title": "T", "authors": [], "date": "", "abs_url": "",
        "html_url": "", "license": ""}


def chunks_of(html):
    doc = parse(html, dict(META))
    return {c["id"]: c for c in doc["chunks"]}


def normalized(html):
    return semantic.normalize(html)


class LaTeXMLAppendix(unittest.TestCase):
    def test_appendix_class_marks_the_chunk(self):
        cs = chunks_of("""
        <article class="ltx_document">
        <section class="ltx_section" id="S1"><h2 class="ltx_title"><span class="ltx_tag">1</span>Intro</h2>
          <div class="ltx_para"><p class="ltx_p">Body text.</p></div></section>
        <section class="ltx_appendix" id="A1"><h2 class="ltx_title"><span class="ltx_tag">A</span>Proofs</h2>
          <div class="ltx_para"><p class="ltx_p">Proof text.</p></div></section>
        </article>""")
        self.assertFalse(cs["S1"]["app"])
        self.assertTrue(cs["A1"]["app"])

    def test_nested_sections_inherit_the_flag(self):
        cs = chunks_of("""
        <article class="ltx_document">
        <section class="ltx_appendix" id="A1"><h2 class="ltx_title"><span class="ltx_tag">A</span>Proofs</h2>
          <section class="ltx_subsection" id="A1.SS1"><h3 class="ltx_title"><span class="ltx_tag">A.1</span>Lemmas</h3>
            <div class="ltx_para"><p class="ltx_p">Lemma text.</p></div></section>
        </section>
        </article>""")
        self.assertTrue(cs["A1"]["app"])
        self.assertTrue(cs["A1.SS1"]["app"])

    def test_no_appendix_no_flag(self):
        cs = chunks_of("""
        <article class="ltx_document">
        <section class="ltx_section" id="S1"><h2 class="ltx_title">Intro</h2>
          <div class="ltx_para"><p class="ltx_p">Body text.</p></div></section>
        <section class="ltx_section" id="S2"><h2 class="ltx_title"><span class="ltx_tag">A</span>A body section that starts with a letter</h2>
          <div class="ltx_para"><p class="ltx_p">Still body.</p></div></section>
        </article>""")
        self.assertEqual({c["app"] for c in cs.values()}, {False})

    def test_bibliography_stays_no_chunk_and_no_flag(self):
        cs = chunks_of("""
        <article class="ltx_document">
        <section class="ltx_section" id="S1"><h2 class="ltx_title">Intro</h2>
          <div class="ltx_para"><p class="ltx_p">Body text.</p></div></section>
        <section class="ltx_appendix" id="A1"><h2 class="ltx_title"><span class="ltx_tag">A</span>Proofs</h2>
          <div class="ltx_para"><p class="ltx_p">Proof text.</p></div></section>
        <section class="ltx_bibliography"><h2 class="ltx_title">References</h2>
          <ul class="ltx_biblist"><li class="ltx_bibitem" id="bib.b1"><span class="ltx_bibcited">[1]</span> Someone. A paper.</li></ul>
        </section>
        </article>""")
        self.assertEqual(set(cs), {"S1", "A1"})
        self.assertTrue(cs["A1"]["app"])

    def test_trailing_loose_text_after_appendix_reads_with_it(self):
        cs = chunks_of("""
        <article class="ltx_document">
        <section class="ltx_appendix" id="A1"><h2 class="ltx_title"><span class="ltx_tag">A</span>Proofs</h2>
          <div class="ltx_para"><p class="ltx_p">Proof text.</p></div></section>
        <div class="ltx_para"><p class="ltx_p">A closing remark outside any section.</p></div>
        </article>""")
        self.assertTrue(cs["A1"]["app"])
        trailing = next(u for u in parse("""
        <article class="ltx_document">
        <section class="ltx_appendix" id="A1"><h2 class="ltx_title"><span class="ltx_tag">A</span>Proofs</h2>
          <div class="ltx_para"><p class="ltx_p">Proof text.</p></div></section>
        <div class="ltx_para"><p class="ltx_p">A closing remark outside any section.</p></div>
        </article>""", dict(META))["units"].values() if "closingremark" in "".join(tk.get("t", "") for tk in u["toks"]))
        self.assertEqual(trailing["chunk"], "A1")

    def test_abstract_is_never_appendix(self):
        cs = chunks_of("""
        <article class="ltx_document">
        <section class="ltx_abstract"><h2 class="ltx_title">Abstract</h2>
          <div class="ltx_para"><p class="ltx_p">The paper in short.</p></div></section>
        <section class="ltx_section" id="S1"><h2 class="ltx_title">Intro</h2>
          <div class="ltx_para"><p class="ltx_p">Body text.</p></div></section>
        </article>""")
        self.assertFalse(cs["abstract"]["app"])


def doc_units(cs):
    return {k: v["units"] for k, v in cs.items()}


class SemanticSources(unittest.TestCase):
    """JATS, Markdown, PDF and web pages reach parse.py through semantic.normalize: the appendix has to survive
    that road, by JATS's own <app> where the source says so, else by what the heading says."""


    def test_jats_app_marks_appendix_even_when_its_title_does_not_say_appendix(self):
        xml = """<article>
        <body><sec id="s1"><title>Results</title><p>Body text.</p></sec></body>
        <back>
          <ack><title>Acknowledgments</title><p>Thanks.</p></ack>
          <app-group><app id="app1"><label>A</label><title>Proof of Theorem 2</title><p>Proof text.</p></app></app-group>
        </back>
        </article>"""
        html, _ = jats.to_html(xml)
        cs = chunks_of(normalized(html))
        app = [c for c in cs.values() if c["app"]]
        self.assertEqual(len(app), 1, cs)
        self.assertIn("Proof of Theorem 2", app[0]["title"])
        self.assertFalse(next(c for c in cs.values() if "Results" in c["title"])["app"])

    def test_jats_title_saying_appendix_also_marks_it(self):
        xml = """<article>
        <body><sec id="s1"><title>Results</title><p>Body text.</p></sec></body>
        <back><app id="app1"><title>Appendix A: Proofs</title><p>Proof text.</p></app></back>
        </article>"""
        html, _ = jats.to_html(xml)
        cs = chunks_of(normalized(html))
        self.assertEqual([c["title"] for c in cs.values() if c["app"]], ["Appendix A: Proofs"])

    def test_heading_says_appendix(self):
        cs = chunks_of(normalized("""
        <h2>Results</h2><p>Body text.</p>
        <h2>Appendix A: Derivations</h2><p>Proof text.</p>
        """))
        body = next(c for c in cs.values() if c["title"] == "Results")
        app = next(c for c in cs.values() if "Derivations" in c["title"])
        self.assertFalse(body["app"])
        self.assertTrue(app["app"])

    def test_subsection_after_appendix_heading_inherits(self):
        cs = chunks_of(normalized("""
        <h2>Results</h2><p>Body text.</p>
        <h2>Appendix A: Derivations</h2><p>Proof text.</p>
        <h3>A.1 The bound</h3><p>Detail text.</p>
        """))
        sub = next(c for c in cs.values() if "The bound" in c["title"])
        self.assertTrue(sub["app"])

    def test_supplementary_material_is_not_called_an_appendix(self):
        cs = chunks_of(normalized("""
        <h2>Results</h2><p>Body text.</p>
        <h2>Supplementary Material</h2><p>Extra text.</p>
        """))
        sup = next(c for c in cs.values() if "Supplementary" in c["title"])
        self.assertFalse(sup["app"])

    def test_references_stay_a_bibliography(self):
        cs = chunks_of(normalized("""
        <h2>Results</h2><p>Body text.</p>
        <h2>References</h2><p>Someone. A paper.</p>
        """))
        self.assertFalse(any(c["app"] for c in cs.values()))

    def test_titles_in_other_languages(self):
        for head in ("附录A 证明", "附錄A 證明", "付録A 証明", "부록 A: 증명", "Anhang A: Beweise",
                     "Apéndice A: Demostraciones", "Приложение А. Доказательства"):
            with self.subTest(head=head):
                cs = chunks_of(normalized(f"<h2>Results</h2><p>Body text.</p>\n<h2>{head}</h2><p>Proof text.</p>"))
                app = [c for c in cs.values() if c["app"]]
                self.assertEqual(len(app), 1, cs)

    def test_a_lone_letter_names_no_appendix(self):
        cs = chunks_of(normalized("""
        <h2>Results</h2><p>Body text.</p>
        <h2>A Further notes</h2><p>More text.</p>
        """))
        self.assertFalse(any(c["app"] for c in cs.values()))


class FormatStability(unittest.TestCase):
    def test_fold_document_output_is_unchanged_by_the_flag(self):
        from textfold import fold, ladder
        html = normalized("<h2>Results</h2><p>Body text.</p>\n<h2>Appendix A: Proofs</h2><p>Proof text.</p>")
        doc = parse(html, dict(META))
        for u in doc["units"].values():   # as store.assemble does when no layer is read
            u["lad"] = ladder.local(u, doc["atoms"])
        sec_fields = {frozenset(s) for s in
                      (fold.section(doc, c) for c in doc["chunks"])}
        self.assertEqual(sec_fields, {frozenset({"id", "num", "title", "depth", "takeaway", "topic", "units"})})


class AppendixAncestry(unittest.TestCase):
    """The flag comes from the section itself or its DOM ancestors — never from the section read just before it.
    A plain section after the appendices (a NeurIPS checklist, acknowledgments) is body, and reads as body."""

    SIBLINGS = """
        <article class="ltx_document">
        <section class="ltx_section" id="S1"><h2 class="ltx_title"><span class="ltx_tag">1</span>Intro</h2>
          <div class="ltx_para"><p class="ltx_p">Body text.</p></div></section>
        <section class="ltx_appendix" id="A1"><h2 class="ltx_title"><span class="ltx_tag">A</span>Proofs</h2>
          <div class="ltx_para"><p class="ltx_p">Proof text.</p></div>
          <section class="ltx_subsection" id="A1.SS1"><h3 class="ltx_title"><span class="ltx_tag">A.1</span>Lemmas</h3>
            <div class="ltx_para"><p class="ltx_p">Lemma text.</p></div></section>
        </section>
        <section class="ltx_section" id="S2"><h2 class="ltx_title">NeurIPS Checklist</h2>
          <div class="ltx_para"><p class="ltx_p">Answered yes.</p></div></section>
        <section class="ltx_section" id="S3"><h2 class="ltx_title">Acknowledgments</h2>
          <div class="ltx_para"><p class="ltx_p">Thanks.</p></div></section>
        </article>"""

    def test_a_plain_section_after_the_appendices_is_not_an_appendix(self):
        cs = chunks_of(self.SIBLINGS)
        self.assertEqual([(cid, cs[cid]["app"]) for cid in ("S1", "A1", "A1.SS1", "S2", "S3")],
                         [("S1", False), ("A1", True), ("A1.SS1", True), ("S2", False), ("S3", False)])

    def test_a_plain_section_inside_the_appendix_is(self):
        cs = chunks_of("""
        <article class="ltx_document">
        <section class="ltx_appendix" id="A1"><h2 class="ltx_title"><span class="ltx_tag">A</span>Proofs</h2>
          <section class="ltx_section" id="A1.S0"><h3 class="ltx_title">A note on the proofs</h3>
            <div class="ltx_para"><p class="ltx_p">Note text.</p></div></section>
        </section>
        <section class="ltx_section" id="S1"><h2 class="ltx_title">Checklist</h2>
          <div class="ltx_para"><p class="ltx_p">Body text.</p></div></section>
        </article>""")
        self.assertTrue(cs["A1.S0"]["app"])   # inside the appendix's element, whatever its own class says
        self.assertFalse(cs["S1"]["app"])

    def test_two_appendices_do_not_carry_the_flag_between_them(self):
        cs = chunks_of("""
        <article class="ltx_document">
        <section class="ltx_appendix" id="A1"><h2 class="ltx_title">Proofs</h2>
          <div class="ltx_para"><p class="ltx_p">Proof text.</p></div></section>
        <section class="ltx_section" id="S1"><h2 class="ltx_title">Back Matter</h2>
          <div class="ltx_para"><p class="ltx_p">Body text.</p></div></section>
        <section class="ltx_appendix" id="A2"><h2 class="ltx_title">Extra Tables</h2>
          <div class="ltx_para"><p class="ltx_p">Table text.</p></div></section>
        </article>""")
        self.assertEqual([(cid, cs[cid]["app"]) for cid in ("A1", "S1", "A2")],
                         [("A1", True), ("S1", False), ("A2", True)])


class SemanticAncestry(unittest.TestCase):
    def test_after_an_appendix_heading_a_plain_sibling_stays_body(self):
        # the same trap through semantic.normalize: an appendix heading, then a plain one at the same depth
        cs = chunks_of(normalized("""
        <h2>Results</h2><p>Body text.</p>
        <h2>Appendix A: Proofs</h2><p>Proof text.</p>
        <h2>NeurIPS Checklist</h2><p>Answered yes.</p>
        <h3>Inside the checklist</h3><p>Still body.</p>
        """))
        app = {c["title"]: c["app"] for c in cs.values()}
        proofs = next(t for t in app if "Derivations" in t or "Proofs" in t)
        check = next(t for t in app if "Checklist" in t)
        inside = next(t for t in app if "Inside the checklist" in t)
        self.assertTrue(app[proofs])
        self.assertFalse(app[check])
        self.assertFalse(app[inside])   # and the checklist's own subsection stays body too


if __name__ == "__main__":
    unittest.main()

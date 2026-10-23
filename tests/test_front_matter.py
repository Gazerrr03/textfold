import unittest

from textfold.markdown import front_matter


class FrontMatterTest(unittest.TestCase):
    def test_quarto_author_mappings_give_the_names(self):
        fm = front_matter(
            "title: A Study\n"
            "author:\n"
            "  - name: Jane Doe\n"
            "    affiliation: MIT\n"
            "  - name: John Roe\n"
        )
        self.assertEqual(fm["authors"], ["Jane Doe", "John Roe"])
        self.assertEqual(fm["title"], "A Study")

    def test_author_mapping_whose_name_is_not_the_first_field(self):
        fm = front_matter("author:\n  - id: jd\n    name: Jane Doe\n  - name: John Roe\n")
        self.assertEqual(fm["authors"], ["Jane Doe", "John Roe"])

    def test_an_authors_affiliations_are_not_authors(self):
        # Quarto's own example of an author: the `- name:` of an affiliation is in the author's mapping
        fm = front_matter(
            "author:\n"
            "  - name: Norah Jones\n"
            "    orcid: 0000-0001-2345-6789\n"
            "    affiliations:\n"
            "      - name: Carnegie Mellon University\n"
            "        city: Pittsburgh\n"
            "  - name: John Roe\n"
        )
        self.assertEqual(fm["authors"], ["Norah Jones", "John Roe"])
        # the items at the key's own indent, their affiliations two in
        fm = front_matter("author:\n- name: Jane Doe\n  affiliations:\n  - name: MIT\n- name: John Roe\n")
        self.assertEqual(fm["authors"], ["Jane Doe", "John Roe"])

    def test_a_name_in_parts(self):
        fm = front_matter(
            "author:\n"
            "  - name:\n"
            "      given: Norah\n"
            "      family: Jones\n"
            "    affiliations:\n"
            "      - name: Carnegie Mellon University\n"
            "  - name:\n"
            "      literal: The TextFold Team\n"
        )
        self.assertEqual(fm["authors"], ["Norah Jones", "The TextFold Team"])

    def test_plain_and_inline_author_lists_are_unchanged(self):
        self.assertEqual(front_matter("authors:\n  - Jane Doe\n  - John Roe\n")["authors"],
                         ["Jane Doe", "John Roe"])
        self.assertEqual(front_matter('author: [Jane Doe, "Roe, John"]\n')["authors"],
                         ["Jane Doe", "Roe, John"])

    def test_folded_and_literal_block_titles(self):
        self.assertEqual(front_matter("title: >\n  A Long\n  Title\nauthor: Jane\n")["title"], "A Long Title")
        self.assertEqual(front_matter("author: Jane\ntitle: |-\n  Line one\n  Line two\n")["title"],
                         "Line one\nLine two")

    def test_trailing_comment_is_not_part_of_the_value(self):
        self.assertEqual(front_matter("title: Paper # draft\n")["title"], "Paper")
        # a # inside quotes, or not after a space, is text
        self.assertEqual(front_matter('title: "C# in depth"\n')["title"], "C# in depth")
        self.assertEqual(front_matter("title: C#Sharp\n")["title"], "C#Sharp")
        self.assertEqual(front_matter('title: "Paper" # draft\n')["title"], "Paper")
        self.assertEqual(front_matter("author:\n  - Jane Doe # lead\n  - name: John Roe # second\n")["authors"],
                         ["Jane Doe", "John Roe"])


if __name__ == "__main__":
    unittest.main()

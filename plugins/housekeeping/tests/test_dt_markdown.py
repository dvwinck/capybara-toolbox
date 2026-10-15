import unittest

from helpers import load_doc_truth

dt = load_doc_truth()

SAMPLE = """---
title: front matter is skipped
# not a heading
---
# Title

Some `code.py` and a [link](docs/a.md#intro) and ![img](assets/x.svg).

## Second `part`

```bash
# a comment, not a heading
python3 tools/x.py   # run it
```

<img src="assets/banner.svg" alt="b">

[ref]: other.md
"""


class DocParsingTest(unittest.TestCase):
    def setUp(self):
        self.doc = dt.Doc(SAMPLE)

    def test_headings_skip_front_matter_and_fences(self):
        self.assertEqual([(lv, tx) for lv, tx, _ in self.doc.headings], [(1, "Title"), (2, "Second `part`")])

    def test_spans_and_fenced_lines_are_kept_apart(self):
        self.assertIn("code.py", [t for _, t in self.doc.spans])
        self.assertIn("part", [t for _, t in self.doc.spans])
        self.assertEqual([t for _, t in self.doc.fenced], ["# a comment, not a heading", "python3 tools/x.py   # run it"])

    def test_links_include_markdown_images_html_and_reference_definitions(self):
        self.assertEqual({t for _, t in self.doc.links}, {"docs/a.md#intro", "assets/x.svg", "assets/banner.svg", "other.md"})

    def test_prose_excludes_front_matter_and_fences(self):
        texts = [t for _, t in self.doc.prose]
        self.assertIn("# Title", texts)
        self.assertNotIn("python3 tools/x.py   # run it", texts)
        self.assertNotIn("title: front matter is skipped", texts)

    def test_a_link_inside_an_inline_code_span_is_not_a_link(self):
        doc = dt.Doc("see `[x](nowhere.md)` here\n")
        self.assertEqual(doc.links, [])

    def test_line_numbers_are_one_based(self):
        doc = dt.Doc("a\n\n## H\n")
        self.assertEqual(doc.headings, [(2, "H", 3)])

    def test_a_longer_fence_is_closed_only_by_an_equal_or_longer_one(self):
        doc = dt.Doc("````\n```\n# inside\n```\n````\n# out\n")
        self.assertEqual([t for _, t, _ in doc.headings], ["out"])

    def test_tilde_fences_work(self):
        doc = dt.Doc("~~~\n# inside\n~~~\n# out\n")
        self.assertEqual([t for _, t, _ in doc.headings], ["out"])


class SlugTest(unittest.TestCase):
    def test_github_style_slugs(self):
        cases = {
            "Hello World": "hello-world",
            "What's inside": "whats-inside",
            "Install / Setup": "install--setup",
            "`code` and **bold**": "code-and-bold",
            "A [link](x.md) here": "a-link-here",
            "Instalação": "instalação",
            "snake_case stays": "snake_case-stays",
        }
        for heading, slug in cases.items():
            with self.subTest(heading=heading):
                self.assertEqual(dt.slugify(heading), slug)

    def test_a_repeated_heading_gets_a_numeric_suffix(self):
        doc = dt.Doc("# Same\n## Same\n### Same\n")
        self.assertEqual(dt.anchors_of(doc), {"same", "same-1", "same-2"})


class TokenTest(unittest.TestCase):
    def paths(self, text, fenced=False):
        toks = dt.tokens_of_fenced_line(text) if fenced else dt.tokens_of_span(text)
        return [t for t in toks if dt.is_path(t)]

    def test_what_counts_as_a_path(self):
        self.assertEqual(self.paths("plugins/ar-board/README.md"), ["plugins/ar-board/README.md"])
        self.assertEqual(self.paths("README.md"), ["README.md"])
        self.assertEqual(self.paths("tools/"), ["tools/"])
        self.assertEqual(self.paths(".github/workflows/ci.yml"), [".github/workflows/ci.yml"])

    def test_what_does_not(self):
        for tok in ["https://example.com/a.md", "/abs/path.md", "~/x/y.md", "$HOME/x.md", "<name>/x.md", "docs/*.md",
                    "PATH", "DIR", "--check", "x...y/z", "a|b/c.md", "foo", "3.10", "ar-board@capybara-toolbox",
                    "text/html", "application/json", "image/png", ".svg", ".json", "A/R/M", "n/N"]:
            with self.subTest(tok=tok):
                self.assertFalse(dt.is_path(dt.clean_token(tok)), tok)

    def test_near_misses_that_are_still_paths(self):
        for tok in ["x/y.md", ".doc-truth.json", "docs/pt-BR", "a/bc", "plugins/x"]:
            with self.subTest(tok=tok):
                self.assertTrue(dt.is_path(tok), tok)

    def test_a_line_suffix_and_punctuation_are_dropped(self):
        self.assertEqual(self.paths("src/x.py:42"), ["src/x.py"])
        self.assertEqual(self.paths("src/x.py:42:7"), ["src/x.py"])
        self.assertEqual(self.paths("(see docs/a.md)."), ["docs/a.md"])

    def test_a_variable_assignment_exposes_its_value(self):
        self.assertEqual(self.paths("S=plugins/x/scripts", fenced=True), ["plugins/x/scripts"])
        self.assertEqual(self.paths("python3 -I $S/tool.py scan", fenced=True), [])

    def test_fenced_comments_slash_commands_and_trees_are_skipped(self):
        self.assertEqual(self.paths("# docs/a.md is mentioned in a comment", fenced=True), [])
        self.assertEqual(self.paths("/plugin marketplace add dvwinck/capybara-toolbox", fenced=True), [])
        self.assertEqual(self.paths("├── plugins/   # the plugins", fenced=True), [])
        self.assertEqual(self.paths("./install.sh x   # install/upgrade", fenced=True), ["./install.sh"])  # the comment is cut

    def test_a_fenced_command_keeps_its_path_arguments(self):
        self.assertEqual(self.paths("python3 -m unittest discover -s plugins/x/tests", fenced=True), ["plugins/x/tests"])
        self.assertEqual(self.paths("cp a.json docs/b.json", fenced=True), ["a.json", "docs/b.json"])


if __name__ == "__main__":
    unittest.main()

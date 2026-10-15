import tempfile
import unittest
from pathlib import Path

from helpers import commit, init_repo, load_doc_truth

dt = load_doc_truth()


class CheckCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = init_repo(Path(tmp.name).resolve() / "r")

    def build(self, files, config=None):
        commit(self.repo, "docs", files)
        cfg = {"exclude": [], "ignore_paths": [], "allow": []}
        cfg.update(config or {})
        return dt.Context(self.repo, dt.tracked_files(self.repo), cfg)

    def values(self, findings):
        return sorted(f["value"] for f in findings)


class PathCheckTest(CheckCase):
    def test_a_missing_path_is_reported_with_its_line(self):
        ctx = self.build({"README.md": "intro\n\nSee `docs/missing.md` now.\n", "docs/real.md": "x\n"})
        found = dt.check_paths(ctx, "README.md")
        self.assertEqual([(f["category"], f["line"], f["value"]) for f in found], [("path", 3, "docs/missing.md")])

    def test_existing_files_and_folders_pass(self):
        ctx = self.build({"README.md": "`docs/real.md` and `docs/` and `docs`\n", "docs/real.md": "x\n"})
        self.assertEqual(dt.check_paths(ctx, "README.md"), [])

    def test_a_path_may_be_relative_to_the_document_or_to_the_root(self):
        ctx = self.build({"docs/a.md": "`b.md` and `docs/b.md` and `../README.md`\n", "docs/b.md": "x\n", "README.md": "r\n"})
        self.assertEqual(dt.check_paths(ctx, "docs/a.md"), [])

    def test_paths_that_escape_the_repository_do_not_exist(self):
        ctx = self.build({"a.md": "`../outside.md`\n"})
        self.assertEqual(self.values(dt.check_paths(ctx, "a.md")), ["../outside.md"])

    def test_existence_is_judged_against_the_git_tree_not_the_filesystem(self):
        ctx = self.build({"a.md": "`local-only.md`\n"})
        (self.repo / "local-only.md").write_text("x\n", encoding="utf-8")  # untracked: CI would not have it
        self.assertEqual(self.values(dt.check_paths(ctx, "a.md")), ["local-only.md"])

    def test_ignore_paths_silence_run_time_files(self):
        ctx = self.build({"a.md": "`.ar-board/x/batch.json` and `decisions.json` and `src/missing.py`\n"},
                         {"ignore_paths": [".ar-board/", "decisions.json"]})
        self.assertEqual(self.values(dt.check_paths(ctx, "a.md")), ["src/missing.py"])

    def test_an_anchored_entry_silences_the_bare_shorthand_but_not_a_broken_full_path(self):
        text = ("`SKILL.md` and `./SKILL.md`\n`plugins/nope/skills/x/SKILL.md` and `skills/x/SKILL.md`\n"
                "`plugins/nope/.claude-plugin/plugin.json` and `plugin.json` and `batch.json` and `x/batch.json`\n")
        files = {"README.md": text, "plugins/y/README.md": text.replace("`./SKILL.md`", "`SKILL.md`")}
        ctx = self.build(files, {"ignore_paths": ["/SKILL.md", "/plugin.json", "batch.json"]})
        expected = ["plugins/nope/.claude-plugin/plugin.json", "plugins/nope/skills/x/SKILL.md", "skills/x/SKILL.md"]
        self.assertEqual(self.values(dt.check_paths(ctx, "README.md")), expected)
        self.assertEqual(self.values(dt.check_paths(ctx, "plugins/y/README.md")), expected)

    def test_a_bare_entry_still_silences_that_name_in_any_folder(self):
        ctx = self.build({"a.md": "`SKILL.md` and `plugins/nope/skills/x/SKILL.md`\n"}, {"ignore_paths": ["SKILL.md"]})
        self.assertEqual(dt.check_paths(ctx, "a.md"), [])

    def test_placeholders_urls_and_absolute_paths_are_not_checked(self):
        ctx = self.build({"a.md": "`<name>/x.md` `PATH` `https://x.org/a.md` `/etc/hosts` `docs/*.md` `$HOME/a.md`\n"})
        self.assertEqual(dt.check_paths(ctx, "a.md"), [])

    def test_fenced_command_arguments_are_checked(self):
        text = "```bash\npython3 tools/missing.py --check\n# docs/in-a-comment.md\n```\n"
        ctx = self.build({"a.md": text})
        self.assertEqual(self.values(dt.check_paths(ctx, "a.md")), ["tools/missing.py"])

    def test_a_tree_diagram_is_a_picture_not_a_claim(self):
        text = "```text\n.\n├── plugins/ghost/\n│   └── nothing.md\n```\n"
        ctx = self.build({"a.md": text})
        self.assertEqual(dt.check_paths(ctx, "a.md"), [])

    def test_the_same_missing_path_is_reported_once_per_document(self):
        ctx = self.build({"a.md": "`x/y.md` again `x/y.md`\n"})
        self.assertEqual(len(dt.check_paths(ctx, "a.md")), 1)


class LinkCheckTest(CheckCase):
    def test_a_broken_relative_link_is_reported(self):
        ctx = self.build({"a.md": "[gone](nope.md) and [ok](b.md)\n", "b.md": "# B\n"})
        found = dt.check_links(ctx, "a.md")
        self.assertEqual([(f["category"], f["value"]) for f in found], [("link", "nope.md")])

    def test_links_resolve_next_to_the_document_and_a_leading_slash_means_the_root(self):
        ctx = self.build({"docs/a.md": "[x](b.md) [y](/README.md) [z](../README.md)\n", "docs/b.md": "x\n", "README.md": "r\n"})
        self.assertEqual(dt.check_links(ctx, "docs/a.md"), [])

    def test_external_links_are_never_followed(self):
        ctx = self.build({"a.md": "[x](https://example.org/nope) [m](mailto:a@b.c)\n"})
        self.assertEqual(dt.check_links(ctx, "a.md"), [])

    def test_a_link_to_a_folder_is_fine(self):
        ctx = self.build({"a.md": "[p](plugins/x)\n", "plugins/x/README.md": "r\n"})
        self.assertEqual(dt.check_links(ctx, "a.md"), [])

    def test_html_references_are_links_too(self):
        ctx = self.build({"a.md": '<img src="assets/missing.svg">\n'})
        self.assertEqual(self.values(dt.check_links(ctx, "a.md")), ["assets/missing.svg"])


class AnchorCheckTest(CheckCase):
    def test_an_anchor_must_match_a_heading_of_the_target(self):
        ctx = self.build({"a.md": "[ok](b.md#install) [bad](b.md#nothing)\n", "b.md": "# Intro\n## Install\n"})
        found = dt.check_links(ctx, "a.md")
        self.assertEqual([(f["category"], f["value"]) for f in found], [("anchor", "b.md#nothing")])

    def test_same_document_anchors_count(self):
        ctx = self.build({"a.md": "# Top\n[ok](#top) [bad](#bottom)\n"})
        self.assertEqual(self.values(dt.check_links(ctx, "a.md")), ["a.md#bottom"])

    def test_accents_duplicates_and_percent_encoding(self):
        ctx = self.build({"a.md": "[x](b.md#instalação) [y](b.md#instala%C3%A7%C3%A3o) [z](b.md#dup-1) [w](b.md#dup-2)\n",
                          "b.md": "# Instalação\n## Dup\n## Dup\n"})
        self.assertEqual(self.values(dt.check_links(ctx, "a.md")), ["b.md#dup-2"])

    def test_a_hash_line_inside_a_fence_is_not_a_heading(self):
        ctx = self.build({"a.md": "[x](b.md#fake)\n", "b.md": "# Real\n```\n# fake\n```\n"})
        self.assertEqual(self.values(dt.check_links(ctx, "a.md")), ["b.md#fake"])

    def test_an_anchor_on_a_file_that_is_not_markdown_is_not_checked(self):
        ctx = self.build({"a.md": "[x](code.py#L10)\n", "code.py": "x\n"})
        self.assertEqual(dt.check_links(ctx, "a.md"), [])


if __name__ == "__main__":
    unittest.main()

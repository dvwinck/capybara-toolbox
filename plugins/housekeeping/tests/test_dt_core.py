import json
import os
import tempfile
import unittest
from pathlib import Path

from helpers import commit, init_repo, load_doc_truth

dt = load_doc_truth()


class RepoCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()  # git reports real paths (/private/var on macOS)
        self.repo = init_repo(self.tmp / "r")


class TrackedFilesTest(RepoCase):
    def test_only_tracked_files_are_listed(self):
        commit(self.repo, "init", {"a.md": "x\n", "sub/b.md": "y\n"})
        (self.repo / "untracked.md").write_text("z\n", encoding="utf-8")
        self.assertEqual(dt.tracked_files(self.repo), ["a.md", "sub/b.md"])

    def test_a_folder_that_is_not_a_repository_is_an_error(self):
        plain = self.tmp / "plain"
        plain.mkdir()
        with self.assertRaises(dt.DocTruthError):
            dt.tracked_files(plain)
        with self.assertRaises(dt.DocTruthError):
            dt.repo_root(plain)

    def test_repo_root_from_a_subfolder(self):
        commit(self.repo, "init", {"sub/b.md": "y\n"})
        self.assertEqual(dt.repo_root(self.repo / "sub"), self.repo)

    def test_tree_paths_include_every_parent_folder(self):
        tree = dt.tree_paths(["a/b/c.md", "d.md"])
        self.assertEqual(tree, {"a/b/c.md", "d.md", "a/b", "a"})


class ReadTextTest(RepoCase):
    def test_a_regular_file_is_read(self):
        commit(self.repo, "init", {"a.md": "hello\n"})
        self.assertEqual(dt.read_text(self.repo, "a.md"), "hello\n")

    def test_a_missing_file_a_folder_and_a_symlink_are_not_read(self):
        outside = self.tmp / "secret.txt"
        outside.write_text("do not read me\n", encoding="utf-8")
        commit(self.repo, "init", {"sub/b.md": "y\n"})
        os.symlink(outside, self.repo / "link.md")
        os.symlink(self.repo / "sub" / "b.md", self.repo / "inside.md")  # even a link to a tracked file is skipped
        for rel in ("missing.md", "sub", "link.md", "inside.md"):
            with self.subTest(rel=rel):
                self.assertIsNone(dt.read_text(self.repo, rel))


class ConfigTest(RepoCase):
    def write(self, data, name=".doc-truth.json"):
        (self.repo / name).write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")

    def test_no_config_means_empty_lists(self):
        self.assertEqual(dt.load_config(self.repo), {"exclude": [], "ignore_paths": [], "allow": []})

    def test_a_config_is_read(self):
        self.write({"exclude": ["docs/plans/**"], "allow": ["abc"]})
        cfg = dt.load_config(self.repo)
        self.assertEqual(cfg["exclude"], ["docs/plans/**"])
        self.assertEqual(cfg["allow"], ["abc"])
        self.assertEqual(cfg["ignore_paths"], [])

    def test_an_unknown_key_is_rejected(self):
        self.write({"excludes": []})
        with self.assertRaises(dt.DocTruthError) as ctx:
            dt.load_config(self.repo)
        self.assertIn("excludes", str(ctx.exception))

    def test_wrong_types_are_rejected(self):
        for bad in ({"exclude": "docs"}, {"allow": [1]}, [1, 2], "not json"):
            with self.subTest(bad=bad):
                self.write(bad)
                with self.assertRaises(dt.DocTruthError):
                    dt.load_config(self.repo)

    def test_an_explicit_missing_config_is_an_error(self):
        with self.assertRaises(dt.DocTruthError):
            dt.load_config(self.repo, str(self.repo / "nope.json"))

    def test_an_explicit_config_replaces_the_default_one(self):
        self.write({"exclude": ["a"]})
        self.write({"exclude": ["b"]}, name="other.json")
        self.assertEqual(dt.load_config(self.repo, str(self.repo / "other.json"))["exclude"], ["b"])


class GlobTest(unittest.TestCase):
    def match(self, pattern, rel):
        return bool(dt.glob_regex(pattern).match(rel))

    def test_star_is_a_name_part_and_never_crosses_a_slash(self):
        self.assertTrue(self.match("docs/*.md", "docs/a.md"))
        self.assertFalse(self.match("docs/*.md", "docs/sub/a.md"))

    def test_double_star_is_any_depth(self):
        self.assertTrue(self.match("docs/plans/**", "docs/plans/a.md"))
        self.assertTrue(self.match("docs/plans/**", "docs/plans/x/y/a.md"))
        self.assertTrue(self.match("**/CHANGELOG.md", "plugins/x/CHANGELOG.md"))
        self.assertTrue(self.match("**/CHANGELOG.md", "CHANGELOG.md"))
        self.assertFalse(self.match("docs/plans/**", "docs/other/a.md"))

    def test_a_trailing_slash_means_everything_under_a_folder_of_that_name(self):
        self.assertTrue(self.match(".ar-board/", ".ar-board"))  # the folder itself, as a document may cite it
        self.assertTrue(self.match(".ar-board/", ".ar-board/x/decisions.json"))
        self.assertTrue(self.match(".ar-board/", "src/.ar-board/x"))  # no other slash: the name may sit anywhere
        self.assertFalse(self.match(".ar-board/", "src/my.ar-board/x"))
        self.assertFalse(self.match("docs/plans/", "src/docs/plans/x.md"))  # a slash inside anchors it

    def test_a_pattern_without_a_slash_matches_a_name_anywhere(self):
        self.assertTrue(self.match("decisions.json", "decisions.json"))
        self.assertTrue(self.match("decisions.json", "a/b/decisions.json"))
        self.assertFalse(self.match("decisions.json", "a/b/my-decisions.json"))

    def test_a_pattern_with_a_slash_is_anchored_at_the_root(self):
        self.assertTrue(self.match("docs/a.md", "docs/a.md"))
        self.assertFalse(self.match("docs/a.md", "x/docs/a.md"))

    def test_a_leading_slash_anchors_the_pattern_at_the_root_even_without_another_slash(self):
        self.assertTrue(self.match("/SKILL.md", "SKILL.md"))
        self.assertFalse(self.match("/SKILL.md", "plugins/nope/skills/x/SKILL.md"))
        self.assertFalse(self.match("/SKILL.md", "x/SKILL.md"))
        self.assertTrue(self.match("/docs/a.md", "docs/a.md"))
        self.assertFalse(self.match("/docs/a.md", "x/docs/a.md"))
        self.assertTrue(self.match("/.ar-board/", ".ar-board/x/decisions.json"))
        self.assertFalse(self.match("/.ar-board/", "src/.ar-board/x"))
        self.assertTrue(self.match("/*.md", "README.md"))
        self.assertFalse(self.match("/*.md", "docs/README.md"))

    def test_regex_characters_are_literal(self):
        self.assertTrue(self.match("a.b+c.md", "a.b+c.md"))
        self.assertFalse(self.match("a.b+c.md", "aXb+c.md"))

    def test_matches_any(self):
        rx = dt.compile_globs(["a/**", "b.md"])
        self.assertTrue(dt.matches_any(rx, "a/x.md"))
        self.assertTrue(dt.matches_any(rx, "b.md"))
        self.assertFalse(dt.matches_any(rx, "c.md"))


if __name__ == "__main__":
    unittest.main()

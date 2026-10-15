import os
import tempfile
import unittest
from pathlib import Path

from helpers import commit, git, init_repo, load_handoff

ho = load_handoff()


class CitationCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        self.repo = init_repo(self.tmp / "r")
        self.first = commit(self.repo, "first", {"src/a.py": "one\ntwo\n", "README.md": "r\n"})

    def check(self, kind, value):
        return ho.check_citation(self.repo, kind, value)


class FindTest(unittest.TestCase):
    def test_only_typed_spans_are_citations(self):
        text = "see `commit:abc1234`, `branch:feat/x` and `file:a/b.py:42`; but `abc1234`, `feat/x` and `a/b.py` are prose"
        self.assertEqual([(k, v) for k, v, _s, _e in ho.find_citations(text)],
                         [("commit", "abc1234"), ("branch", "feat/x"), ("file", "a/b.py:42")])

    def test_untyped_and_unknown_types_are_ignored(self):
        self.assertEqual(ho.find_citations("`commit abc1234` `url:http://x` `branch:` `file: a.py`"), [])

    def test_positions_point_at_the_whole_span(self):
        text = "x `file:a.py` y"
        (_k, _v, start, end), = ho.find_citations(text)
        self.assertEqual(text[start:end], "`file:a.py`")


class CommitTest(CitationCase):
    def test_a_real_commit_in_full_or_abbreviated_form(self):
        self.assertEqual(self.check("commit", self.first), (True, self.first, ""))
        self.assertEqual(self.check("commit", self.first[:7]), (True, self.first, ""))

    def test_a_commit_that_does_not_exist(self):
        ok, sha, why = self.check("commit", "1234567")
        self.assertEqual((ok, sha), (False, None))
        self.assertIn("nao existe", why)

    def test_what_is_not_a_hex_id_is_invalid_even_if_it_names_a_branch(self):
        for bad in ("main", "added", "abc12", "HEAD", "zzzzzzz", "a" * 41):
            with self.subTest(bad=bad):
                self.assertFalse(self.check("commit", bad)[0])

    def test_a_ref_named_like_a_hex_id_never_stands_in_for_a_commit_id(self):
        git(self.repo, "branch", "deadbeef")
        git(self.repo, "tag", "abcdef1")
        for name in ("deadbeef", "abcdef1"):
            with self.subTest(name=name):
                ok, sha, _why = self.check("commit", name)
                self.assertEqual((ok, sha), (False, None))

    def test_a_branch_named_like_a_real_commit_prefix_does_not_hide_the_commit(self):
        second = commit(self.repo, "second", {"b.txt": "b\n"})
        git(self.repo, "branch", self.first[:7], second)  # a branch whose name is the first commit's abbreviation
        git(self.repo, "tag", self.first[:8], second)
        self.assertEqual(self.check("commit", self.first[:7]), (True, self.first, ""))
        self.assertEqual(self.check("commit", self.first[:8]), (True, self.first, ""))
        self.assertEqual(self.check("commit", self.first), (True, self.first, ""))

    def test_upper_case_hex_resolves_to_the_same_commit(self):
        self.assertEqual(self.check("commit", self.first[:9].upper()), (True, self.first, ""))

    def test_an_embedded_nul_is_just_an_invalid_commit(self):
        self.assertFalse(self.check("commit", self.first[:7] + "\x00" + "ab")[0])

    def test_a_tree_or_blob_id_is_not_a_commit(self):
        tree = git(self.repo, "rev-parse", "HEAD^{tree}").strip()
        self.assertFalse(self.check("commit", tree[:10])[0])


class BranchTest(CitationCase):
    def test_a_local_branch_returns_its_tip(self):
        git(self.repo, "branch", "feat/x")
        self.assertEqual(self.check("branch", "feat/x"), (True, self.first, ""))
        self.assertTrue(self.check("branch", "main")[0])

    def test_a_remote_tracking_branch_counts(self):
        origin = init_repo(self.tmp / "o.git")
        git(origin, "config", "receive.denyCurrentBranch", "ignore")
        git(self.repo, "remote", "add", "origin", str(origin))
        git(self.repo, "push", "-q", "origin", "main")
        self.assertTrue(self.check("branch", "origin/main")[0])

    def test_a_missing_branch_fails(self):
        self.assertFalse(self.check("branch", "ghost")[0])

    def test_a_tag_is_not_a_branch(self):
        git(self.repo, "tag", "v1")
        self.assertFalse(self.check("branch", "v1")[0])

    def test_a_tag_with_the_name_of_a_missing_branch_cannot_stand_in_for_it(self):
        git(self.repo, "tag", "feat")
        self.assertFalse(self.check("branch", "feat")[0])

    def test_option_looking_names_are_just_missing_branches(self):
        self.assertFalse(self.check("branch", "--all")[0])

    def test_revision_expressions_are_not_branch_names(self):
        commit(self.repo, "second", {"b.txt": "b\n"})
        for expr in ("main~1", "main^", "main@{0}", "main^{tree}", "main^{commit}", "main..main", "HEAD", "@{-1}", "main:a.txt"):
            with self.subTest(expr=expr):
                ok, sha, _why = self.check("branch", expr)
                self.assertEqual((ok, sha), (False, None))
        self.assertTrue(self.check("branch", "main")[0])

    def test_an_embedded_nul_or_control_character_is_an_unverified_branch(self):
        for value in ("a\x00b", "main\x00", "ma\x01in", "main\x7f"):
            with self.subTest(value=value):
                self.assertFalse(self.check("branch", value)[0])


class FileTest(CitationCase):
    def test_an_existing_file_with_or_without_a_line_suffix(self):
        for value in ("src/a.py", "src/a.py:2", "src/a.py:2:5", "src"):
            with self.subTest(value=value):
                self.assertTrue(self.check("file", value)[0])

    def test_a_missing_file(self):
        ok, _sha, why = self.check("file", "src/gone.py")
        self.assertFalse(ok)
        self.assertIn("nao existe", why)

    def test_a_file_the_session_deleted_is_not_verified(self):
        (self.repo / "src" / "a.py").unlink()
        self.assertFalse(self.check("file", "src/a.py")[0])

    def test_absolute_and_escaping_paths_are_refused(self):
        for value in ("/etc/hosts", "../outside.txt", "src/../../x", "a/../../x"):
            with self.subTest(value=value):
                ok, _sha, why = self.check("file", value)
                self.assertFalse(ok)
                self.assertIn("relativo", why)

    def test_a_symlink_that_leads_outside_the_repository_is_not_a_file_of_it(self):
        outside = self.tmp / "secret.txt"
        outside.write_text("x\n", encoding="utf-8")
        os.symlink(outside, self.repo / "link.txt")
        ok, _sha, why = self.check("file", "link.txt")
        self.assertFalse(ok)
        self.assertIn("sai do repositorio", why)

    def test_an_embedded_nul_or_control_character_is_an_unverified_file(self):
        for value in ("a\x00b", "src/a.py\x00", "src/a.py\x01"):
            with self.subTest(value=value):
                ok, _sha, why = self.check("file", value)
                self.assertFalse(ok)
                self.assertTrue(why)

    def test_a_symlink_inside_the_repository_is_fine(self):
        os.symlink(self.repo / "README.md", self.repo / "alias.md")
        self.assertTrue(self.check("file", "alias.md")[0])


class MarkTest(CitationCase):
    def draft(self):
        return "Fixed `commit:%s` and `file:src/gone.py` (see `branch:ghost`).\n" % self.first[:7]

    def test_a_failing_citation_is_marked_once_and_nothing_is_removed(self):
        text = self.draft()
        marked = ho.mark_unverified(text, ho.check_text(self.repo, text))
        self.assertEqual(marked, "Fixed `commit:%s` and `file:src/gone.py` [nao verificado] (see `branch:ghost` [nao verificado]).\n" % self.first[:7])
        again = ho.mark_unverified(marked, ho.check_text(self.repo, marked))
        self.assertEqual(again, marked)  # idempotent

    def test_a_draft_with_only_good_citations_is_unchanged(self):
        text = "ok `commit:%s` and `file:README.md`\n" % self.first
        self.assertEqual(ho.mark_unverified(text, ho.check_text(self.repo, text)), text)

    def test_results_carry_the_line_of_each_citation(self):
        text = "a\n`file:README.md`\n\n`file:nope.md`\n"
        self.assertEqual([(r["line"], r["verified"]) for r in ho.check_text(self.repo, text)], [(2, True), (4, False)])

    def test_a_citation_with_a_nul_is_unverified_and_marked_once_without_crashing(self):
        text = "x `file:a\x00b` y `branch:a\x00b` z `commit:abcdef1\x00` w `branch:main~1` v\n"
        results = ho.check_text(self.repo, text)
        self.assertEqual([r["verified"] for r in results], [False, False, False, False])
        marked = ho.mark_unverified(text, results)
        self.assertEqual(marked.count(ho.UNVERIFIED), 4)
        self.assertEqual(ho.mark_unverified(marked, ho.check_text(self.repo, marked)), marked)

    def test_the_git_helper_survives_a_nul_in_an_argument(self):
        rc, out = ho.git(self.repo, "show-ref", "--verify", "a\x00b")
        self.assertNotEqual(rc, 0)

    def test_text_with_no_citations_has_no_results(self):
        self.assertEqual(ho.check_text(self.repo, "just prose with `code`\n"), [])


if __name__ == "__main__":
    unittest.main()

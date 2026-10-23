import os
import tempfile
import unittest
from pathlib import Path

from helpers import commit, git, init_repo, load_handoff

ho = load_handoff()


class RepoCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()  # git reports real paths (/private/var on macOS)
        self.repo = init_repo(self.tmp / "r")
        self.first = commit(self.repo, "first", {"a.txt": "one\n"})


class CollectTest(RepoCase):
    def test_the_basic_facts_of_a_clean_repository(self):
        facts = ho.collect(self.repo)
        self.assertEqual((facts["branch"], facts["tip"], facts["upstream"], facts["base"]), ("main", self.first, None, "main"))
        self.assertEqual((facts["ahead"], facts["behind"]), (0, 0))
        self.assertEqual((facts["modified"], facts["untracked"], facts["stashes"]), ([], [], 0))
        self.assertEqual([c["subject"] for c in facts["commits"]], ["first"])
        self.assertEqual(facts["commits"][0]["sha"], self.first[:7])
        self.assertEqual(facts["schema"], 1)

    def test_ahead_and_behind_the_base(self):
        git(self.repo, "checkout", "-q", "-b", "feat")
        commit(self.repo, "f1", {"f.txt": "1\n"})
        commit(self.repo, "f2", {"f.txt": "2\n"})
        git(self.repo, "checkout", "-q", "main")
        commit(self.repo, "m1", {"m.txt": "1\n"})
        git(self.repo, "checkout", "-q", "feat")
        facts = ho.collect(self.repo)
        self.assertEqual((facts["branch"], facts["ahead"], facts["behind"]), ("feat", 2, 1))

    def test_the_base_is_detected_in_order_base_main_master(self):
        git(self.repo, "branch", "master")
        self.assertEqual(ho.detect_base(self.repo), "main")
        git(self.repo, "branch", "base")
        self.assertEqual(ho.detect_base(self.repo), "base")

    def test_the_remote_default_branch_wins_over_the_name_order(self):
        origin = init_repo(self.tmp / "origin.git")
        git(origin, "config", "receive.denyCurrentBranch", "ignore")
        git(self.repo, "remote", "add", "origin", str(origin))
        git(self.repo, "push", "-q", "origin", "main")
        git(self.repo, "remote", "set-head", "origin", "main")
        git(self.repo, "branch", "base")
        self.assertEqual(ho.detect_base(self.repo), "main")

    def test_an_explicit_base_is_used_or_rejected(self):
        git(self.repo, "branch", "other")
        self.assertEqual(ho.detect_base(self.repo, "other"), "other")
        with self.assertRaises(ho.HandoffError):
            ho.detect_base(self.repo, "nope")

    def test_no_base_at_all_is_reported_as_none_not_an_error(self):
        git(self.repo, "branch", "-m", "main", "work")
        facts = ho.collect(self.repo)
        self.assertEqual((facts["base"], facts["ahead"], facts["behind"]), (None, None, None))

    def test_modified_and_untracked_files_are_listed_and_a_rename_counts_once(self):
        (self.repo / "a.txt").write_text("changed\n", encoding="utf-8")
        (self.repo / "new.txt").write_text("x\n", encoding="utf-8")
        commit(self.repo, "second", {"b.txt": "b\n"})
        git(self.repo, "mv", "b.txt", "c.txt")
        facts = ho.collect(self.repo)
        self.assertEqual(facts["modified"], ["a.txt", "c.txt"])
        self.assertEqual(facts["untracked"], ["new.txt"])

    def test_untracked_files_inside_new_folders_are_listed_one_by_one(self):
        (self.repo / "d").mkdir()
        (self.repo / "d" / "x.txt").write_text("x\n", encoding="utf-8")
        self.assertEqual(ho.collect(self.repo)["untracked"], ["d/x.txt"])

    def test_the_notes_folder_is_not_work_in_progress(self):
        (self.repo / ".handoff").mkdir()
        (self.repo / ".handoff" / "2026-10-14-090507.md").write_text("a note\n", encoding="utf-8")
        (self.repo / "real.txt").write_text("x\n", encoding="utf-8")
        facts = ho.collect(self.repo)
        self.assertEqual(facts["untracked"], ["real.txt"])

    def test_stashes_and_linked_worktrees(self):
        (self.repo / "a.txt").write_text("stash me\n", encoding="utf-8")
        git(self.repo, "stash", "-q")
        wt = self.tmp / "wt"
        git(self.repo, "worktree", "add", "-q", "-b", "side", str(wt))
        facts = ho.collect(self.repo)
        self.assertEqual(facts["stashes"], 1)
        self.assertEqual([(w["path"], w["branch"]) for w in facts["worktrees"]], [(str(self.repo), "main"), (str(wt), "side")])

    def test_a_detached_head_has_no_branch(self):
        git(self.repo, "checkout", "-q", "--detach")
        facts = ho.collect(self.repo)
        self.assertIsNone(facts["branch"])
        self.assertEqual(facts["tip"], self.first)

    def test_a_repository_without_commits_still_collects(self):
        empty = init_repo(self.tmp / "empty")
        facts = ho.collect(empty)
        self.assertEqual((facts["branch"], facts["tip"], facts["commits"], facts["ahead"]), ("main", None, [], None))

    def test_only_the_last_five_commits_are_listed_newest_first(self):
        for i in range(7):
            commit(self.repo, f"c{i}", {"a.txt": f"{i}\n"})
        self.assertEqual([c["subject"] for c in ho.collect(self.repo)["commits"]], ["c6", "c5", "c4", "c3", "c2"])

    def test_the_upstream_is_reported(self):
        origin = init_repo(self.tmp / "o.git")
        git(origin, "config", "receive.denyCurrentBranch", "ignore")
        git(self.repo, "remote", "add", "origin", str(origin))
        git(self.repo, "push", "-q", "-u", "origin", "main")
        self.assertEqual(ho.collect(self.repo)["upstream"], "origin/main")

    def test_collecting_never_writes_to_the_repository(self):
        (self.repo / "new.txt").write_text("x\n", encoding="utf-8")
        before = git(self.repo, "status", "--porcelain=v1", "--ignored")
        ho.collect(self.repo)
        self.assertEqual(git(self.repo, "status", "--porcelain=v1", "--ignored"), before)

    def test_not_a_repository_is_an_error(self):
        plain = self.tmp / "plain"
        plain.mkdir()
        with self.assertRaises(ho.HandoffError):
            ho.repo_root(plain)


class GitEnvironmentTest(RepoCase):
    """The git helper must not depend on the caller's environment (ledgered deviation from the brief)."""

    def test_a_missing_git_binary_raises_the_tools_own_error(self):
        empty = self.tmp / "no-git-here"
        empty.mkdir()
        old = os.environ["PATH"]
        os.environ["PATH"] = str(empty)
        try:
            with self.assertRaises(ho.HandoffError) as ctx:
                ho.collect(self.repo)
        finally:
            os.environ["PATH"] = old
        self.assertIn("git not found", str(ctx.exception))

    def test_inherited_repository_location_variables_do_not_change_the_repository_judged(self):
        other = init_repo(self.tmp / "other")
        commit(other, "elsewhere", {"z.txt": "z\n"})
        want = ho.collect(self.repo)
        old = {k: os.environ.get(k) for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")}
        os.environ["GIT_DIR"] = str(other / ".git")
        os.environ["GIT_WORK_TREE"] = str(other)
        os.environ["GIT_INDEX_FILE"] = str(other / ".git" / "index")
        try:
            got = ho.collect(self.repo)
            root = ho.repo_root(self.repo)
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        self.assertEqual(got, want)
        self.assertEqual(root, self.repo)


if __name__ == "__main__":
    unittest.main()

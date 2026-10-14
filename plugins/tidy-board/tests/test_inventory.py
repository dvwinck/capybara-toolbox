import unittest

from helpers import commit, git, init_repo, tb
from repo_case import RepoCase


class ProofLevelTest(RepoCase):
    def test_p1_a_branch_merged_with_a_merge_commit(self):
        self.work("feat/a", {"a.txt": "one\ntwo\n"})
        git(self.repo, "merge", "-q", "--no-ff", "-m", "merge feat/a", "feat/a")
        self.assertEqual(self.by_name()["feat/a"]["proof"], "P1")

    def test_p1_a_branch_at_the_same_commit_as_the_base(self):
        git(self.repo, "branch", "same")
        self.assertEqual(self.by_name()["same"]["proof"], "P1")

    def test_p4_a_branch_with_unique_work(self):
        self.work("spike/x", {"x.txt": "x\n"}, message="wip: x")
        item = self.by_name()["spike/x"]
        self.assertEqual(item["proof"], "P4")
        self.assertTrue(item["backup"])
        self.assertEqual(item["unique_count"], 1)
        self.assertIn("wip: x", item["unique"][0])

    def test_p3_the_same_patch_was_cherry_picked_into_the_base(self):
        sha = self.work("feat/c", {"c.txt": "c\n"})
        commit(self.repo, "unrelated", {"u.txt": "u\n"})  # a different parent: the pick is a new commit
        git(self.repo, "cherry-pick", sha)
        self.assertEqual(self.by_name()["feat/c"]["proof"], "P3")

    def test_p3_a_squash_merge_with_other_work_landing_in_between(self):
        self.work("feat/s", {"s.txt": "s1\n"}, message="s1")
        git(self.repo, "checkout", "-q", "feat/s")
        commit(self.repo, "s2", {"s.txt": "s1\ns2\n"})
        git(self.repo, "checkout", "-q", "main")
        commit(self.repo, "unrelated", {"other.txt": "o\n"})
        git(self.repo, "merge", "-q", "--squash", "feat/s")
        git(self.repo, "commit", "-q", "-m", "squash feat/s")
        item = self.by_name()["feat/s"]
        self.assertEqual(item["proof"], "P3")
        self.assertTrue(item["backup"])

    def test_a_squash_that_also_changed_the_branch_diff_is_not_mistaken_for_merged(self):
        self.work("feat/t", {"t.txt": "t1\n"})
        git(self.repo, "checkout", "-q", "feat/t")
        commit(self.repo, "more", {"t.txt": "t1\nmore\n"})
        git(self.repo, "checkout", "-q", "main")
        git(self.repo, "merge", "-q", "--squash", "feat/t")
        commit(self.repo, "squash minus one line", {"t.txt": "t1\n"})  # not the same diff as the branch
        self.assertEqual(self.by_name()["feat/t"]["proof"], "P4")

    def test_p2_a_merged_pr_whose_head_is_the_branch_tip(self):
        sha = self.work("feat/p", {"p.txt": "p\n"})
        self.fake_gh([{"number": 7, "headRefName": "feat/p", "headRefOid": sha, "url": "https://example.com/pr/7"}])
        inv = self.inv(gh="auto")
        self.assertTrue(inv["gh"])
        item = self.by_name(inv)["feat/p"]
        self.assertEqual(item["proof"], "P2")
        self.assertIn("#7 mergeado (a ponta confere)", item["pr"])

    def test_a_pr_whose_head_is_not_the_tip_does_not_prove_anything(self):
        self.work("feat/q", {"q.txt": "q\n"})
        self.fake_gh([{"number": 8, "headRefName": "feat/q", "headRefOid": "0" * 40, "url": ""}])
        item = self.by_name(self.inv(gh="auto"))["feat/q"]
        self.assertEqual(item["proof"], "P4")
        self.assertIn("DIFERENTE", item["pr"])

    def test_gh_off_or_failing_leaves_the_proof_to_git_alone(self):
        sha = self.work("feat/r", {"r.txt": "r\n"})
        self.fake_gh([{"number": 9, "headRefName": "feat/r", "headRefOid": sha, "url": ""}], exit_code=1)
        inv = self.inv(gh="auto")
        self.assertFalse(inv["gh"])
        self.assertEqual(self.by_name(inv)["feat/r"]["proof"], "P4")
        self.assertEqual(self.by_name(inv)["feat/r"]["pr"], "")
        self.assertFalse(self.inv(gh="off")["gh"])

    def test_upstream_gone_alone_never_raises_the_level(self):
        # a remote branch can be deleted without being merged: only the history may prove it
        origin = self.repo
        clone = self.tmp / "clone"
        git(self.tmp, "clone", "-q", str(origin), str(clone))
        git(clone, "checkout", "-q", "-b", "feat/g")
        commit(clone, "g", {"g.txt": "g\n"})
        git(clone, "push", "-q", "-u", "origin", "feat/g")
        git(origin, "branch", "-D", "feat/g")
        git(clone, "fetch", "-q", "--prune")
        git(clone, "checkout", "-q", "main")
        inv = tb.inventory(clone, tb.detect_base(clone), "off")
        item = {i["name"]: i for i in inv["items"]}["feat/g"]
        self.assertEqual(item["proof"], "P4")
        self.assertIn("ja foi removida", item["remote"])

    def test_a_remote_counterpart_is_reported_and_left_alone(self):
        clone = self.tmp / "clone"
        git(self.tmp, "clone", "-q", str(self.repo), str(clone))
        git(clone, "checkout", "-q", "-b", "feat/h")
        commit(clone, "h", {"h.txt": "h\n"})
        git(clone, "push", "-q", "-u", "origin", "feat/h")
        git(clone, "checkout", "-q", "main")
        inv = tb.inventory(clone, tb.detect_base(clone), "off")
        self.assertIn("ainda existe (nao sera tocada)", {i["name"]: i for i in inv["items"]}["feat/h"]["remote"])


class NeverOfferedTest(RepoCase):
    def test_the_base_and_the_current_branch_are_never_cards(self):
        self.work("feat/cur", {"c.txt": "c\n"})
        git(self.repo, "checkout", "-q", "feat/cur")
        inv = self.inv()
        self.assertNotIn("main", self.by_name(inv))
        self.assertNotIn("feat/cur", self.by_name(inv))
        why = {u["name"]: u["why"] for u in inv["untouched"]}
        self.assertEqual(why["main"], "branch base do repositorio")
        self.assertIn("branch atual", why["feat/cur"])

    def test_a_branch_checked_out_in_a_linked_worktree_is_carried_by_the_worktree_card(self):
        git(self.repo, "branch", "feat/w")
        wt = self.tmp / "wt"
        git(self.repo, "worktree", "add", "-q", str(wt), "feat/w")
        inv = self.inv()
        kinds = {(i["kind"], i["name"]) for i in inv["items"]}
        self.assertIn(("worktree", str(wt)), kinds)
        self.assertNotIn(("branch", "feat/w"), kinds)

    def test_a_worktree_with_tracked_changes_or_untracked_files_is_untouched(self):
        for name, mutate in (("d1", lambda p: (p / "a.txt").write_text("changed\n")), ("d2", lambda p: (p / "new.txt").write_text("n\n"))):
            git(self.repo, "branch", name)
            wt = self.tmp / name
            git(self.repo, "worktree", "add", "-q", str(wt), name)
            mutate(wt)
        inv = self.inv()
        self.assertEqual([i for i in inv["items"] if i["kind"] == "worktree"], [])
        reasons = [u["why"] for u in inv["untouched"] if u["name"].endswith(("d1", "d2"))]
        self.assertEqual(len(reasons), 2)
        self.assertTrue(all("alterado(s) ou nao rastreado(s)" in r for r in reasons))

    def test_a_locked_worktree_is_untouched(self):
        git(self.repo, "branch", "lk")
        wt = self.tmp / "lk"
        git(self.repo, "worktree", "add", "-q", str(wt), "lk")
        git(self.repo, "worktree", "lock", str(wt))
        inv = self.inv()
        self.assertEqual([i for i in inv["items"] if i["kind"] == "worktree"], [])
        self.assertTrue(any("bloqueado" in u["why"] for u in inv["untouched"]))


class WorktreeAndStashTest(RepoCase):
    def test_a_clean_worktree_on_a_merged_branch_drops_its_branch_too(self):
        git(self.repo, "branch", "feat/done")
        wt = self.tmp / "done"
        git(self.repo, "worktree", "add", "-q", str(wt), "feat/done")
        item = [i for i in self.inv()["items"] if i["kind"] == "worktree"][0]
        self.assertEqual((item["proof"], item["branch"], item["drop_branch"], item["backup"]), ("P1", "feat/done", True, False))
        self.assertGreater(item["size"], 0)

    def test_a_clean_worktree_on_unique_work_keeps_its_branch_and_needs_no_backup(self):
        git(self.repo, "checkout", "-q", "-b", "spike/wt")
        commit(self.repo, "wip", {"w.txt": "w\n"})
        git(self.repo, "checkout", "-q", "main")
        wt = self.tmp / "spike"
        git(self.repo, "worktree", "add", "-q", str(wt), "spike/wt")
        item = [i for i in self.inv()["items"] if i["kind"] == "worktree"][0]
        self.assertEqual((item["proof"], item["drop_branch"], item["backup"]), ("P4", False, False))

    def test_a_detached_worktree_with_unique_commits_needs_a_backup(self):
        git(self.repo, "checkout", "-q", "-b", "tmp")
        sha = commit(self.repo, "wip", {"w.txt": "w\n"})
        git(self.repo, "checkout", "-q", "main")
        git(self.repo, "branch", "-D", "tmp")
        wt = self.tmp / "det"
        git(self.repo, "worktree", "add", "-q", "--detach", str(wt), sha)
        item = [i for i in self.inv()["items"] if i["kind"] == "worktree"][0]
        self.assertEqual((item["proof"], item["branch"], item["backup"]), ("P4", None, True))

    def test_a_worktree_on_the_base_branch_never_offers_the_base_for_deletion(self):
        git(self.repo, "checkout", "-q", "-b", "dev")
        wt = self.tmp / "on-main"
        git(self.repo, "worktree", "add", "-q", str(wt), "main")
        item = [i for i in self.inv()["items"] if i["kind"] == "worktree"][0]
        self.assertEqual((item["branch"], item["proof"], item["drop_branch"]), ("main", "P1", False))

    def test_ignored_files_in_a_clean_worktree_are_listed_because_removing_it_deletes_them(self):
        commit(self.repo, "ignore", {".gitignore": "*.env\n"})
        git(self.repo, "branch", "feat/ig")
        wt = self.tmp / "ig"
        git(self.repo, "worktree", "add", "-q", str(wt), "feat/ig")
        (wt / "secret.env").write_text("TOKEN=1\n")
        item = [i for i in self.inv()["items"] if i["kind"] == "worktree"][0]
        self.assertEqual(item["ignored"], ["secret.env"])  # git status says clean; the file is in no commit

    def test_a_stash_is_always_p4_and_is_identified_by_its_commit(self):
        (self.repo / "a.txt").write_text("dirty\n")
        git(self.repo, "stash", "push", "-q", "-m", "wip handoff draft")
        sha = git(self.repo, "rev-parse", "stash@{0}").strip()
        item = [i for i in self.inv()["items"] if i["kind"] == "stash"][0]
        self.assertEqual((item["proof"], item["sha"], item["backup"]), ("P4", sha, True))
        self.assertIn("wip handoff draft", item["name"])
        self.assertEqual(item["files"], ["a.txt"])


class RefNameTest(RepoCase):
    """Ref names are resolved in full, so a tag cannot stand in for a branch."""

    def test_a_tag_named_like_the_base_cannot_make_unique_work_look_merged(self):
        sha = self.work("feat/x", {"x.txt": "x\n"})
        git(self.repo, "tag", "main", sha)  # `main` is now ambiguous: a tag at the unique commit, and the branch
        self.assertEqual(self.by_name()["feat/x"]["proof"], "P4")

    def test_the_base_branch_is_never_a_card_even_when_a_tag_shares_its_name(self):
        git(self.repo, "tag", "main", "HEAD")
        inv = self.inv()
        self.assertEqual([i["name"] for i in inv["items"] if i["name"].endswith("main")], [])
        self.assertIn("main", [u["name"] for u in inv["untouched"]])

    def test_a_tag_named_like_a_branch_does_not_rename_the_branch(self):
        git(self.repo, "branch", "same")
        git(self.repo, "tag", "same", "HEAD")
        self.assertIn("same", self.by_name())
        self.assertNotIn("heads/same", self.by_name())


class OrderingTest(RepoCase):
    def test_cards_are_ordered_safest_first_and_oldest_first_inside_a_level(self):
        self.work("new-unique", {"n.txt": "n\n"}, date="2026-01-02T00:00:00")
        self.work("old-unique", {"o.txt": "o\n"}, date="2020-01-02T00:00:00")
        git(self.repo, "branch", "merged")
        names = [i["name"] for i in self.inv()["items"]]
        self.assertEqual(names, ["merged", "old-unique", "new-unique"])


class BaseDetectionTest(RepoCase):
    def test_falls_back_to_main(self):
        self.assertEqual(tb.detect_base(self.repo), "main")

    def test_uses_what_origin_head_points_to(self):
        base_repo = init_repo(self.tmp / "o", branch="base")
        commit(base_repo, "init", {"a.txt": "one\n"})
        clone = self.tmp / "c"
        git(self.tmp, "clone", "-q", str(base_repo), str(clone))
        self.assertEqual(tb.detect_base(clone), "base")

    def test_an_explicit_base_wins_and_an_unknown_one_is_an_error(self):
        git(self.repo, "branch", "develop")
        self.assertEqual(tb.detect_base(self.repo, "develop"), "develop")
        with self.assertRaises(tb.TidyError):
            tb.detect_base(self.repo, "nope")

    def test_no_recognisable_base_asks_for_one(self):
        other = init_repo(self.tmp / "odd", branch="weird")
        commit(other, "init", {"a.txt": "x\n"})
        with self.assertRaises(tb.TidyError) as ctx:
            tb.detect_base(other)
        self.assertIn("--base", str(ctx.exception))

    def test_the_remote_base_also_counts_as_merged_into(self):
        bare = self.tmp / "bare.git"
        git(self.tmp, "clone", "-q", "--bare", str(self.repo), str(bare))
        clone = self.tmp / "cl"
        git(self.tmp, "clone", "-q", str(bare), str(clone))
        git(clone, "checkout", "-q", "-b", "feat/m")
        commit(clone, "m", {"m.txt": "m\n"})
        git(clone, "checkout", "-q", "main")
        git(clone, "merge", "-q", "--ff-only", "feat/m")
        git(clone, "push", "-q", "origin", "main")
        git(clone, "reset", "-q", "--hard", "HEAD~1")  # local main is behind origin/main
        self.assertEqual(tb.base_refs(clone, "main"), ["refs/heads/main", "refs/remotes/origin/main"])
        inv = tb.inventory(clone, "main", "off")
        self.assertEqual({i["name"]: i for i in inv["items"]}["feat/m"]["proof"], "P1")

    def test_a_base_spelled_as_a_full_ref_still_protects_the_base_branch(self):
        base = tb.detect_base(self.repo, "refs/heads/main")
        self.assertEqual(base, "main")
        names = [i["name"] for i in tb.inventory(self.repo, base, "off")["items"]]
        self.assertNotIn("main", names)

    def test_a_remote_base_protects_its_local_twin(self):
        clone = self.tmp / "cl"
        git(self.tmp, "clone", "-q", str(self.repo), str(clone))
        git(clone, "checkout", "-q", "-b", "dev")  # so that `main` is not protected just by being the current branch
        inv = tb.inventory(clone, tb.detect_base(clone, "origin/main"), "off")
        self.assertNotIn("main", [i["name"] for i in inv["items"]])
        self.assertIn("main", [u["name"] for u in inv["untouched"]])

    def test_not_a_repository_is_an_error(self):
        with self.assertRaises(tb.TidyError):
            tb.repo_root(self.tmp)


class RepoConfigIsNotTrustedTest(RepoCase):
    """The repository's own config can name programs for git to run: tidy-board must not run them."""

    def trap(self, name):
        """An executable that leaves a marker file when git runs it."""
        marker = self.tmp / f"{name}.ran"
        script = self.tmp / f"{name}.sh"
        script.write_text(f"#!/bin/sh\ntouch '{marker}'\nexit 0\n", encoding="utf-8")
        script.chmod(0o755)
        return script, marker

    def test_an_external_diff_program_never_runs(self):
        script, marker = self.trap("extdiff")
        self.work("feat/s", {"s.txt": "s1\n"}, message="s1")
        git(self.repo, "checkout", "-q", "feat/s")
        commit(self.repo, "s2", {"s.txt": "s1\ns2\n"})
        git(self.repo, "checkout", "-q", "main")
        commit(self.repo, "unrelated", {"u.txt": "u\n"})
        git(self.repo, "merge", "-q", "--squash", "feat/s")
        git(self.repo, "commit", "-q", "-m", "squash")
        git(self.repo, "config", "diff.external", str(script))
        # two commits squashed into one: `git cherry` cannot match, so the whole-diff path runs `git diff`
        self.assertEqual(self.by_name()["feat/s"]["proof"], "P3")
        self.assertFalse(marker.exists())

    def test_a_filesystem_monitor_program_never_runs(self):
        script, marker = self.trap("fsmonitor")
        git(self.repo, "branch", "feat/w")
        git(self.repo, "worktree", "add", "-q", str(self.tmp / "wt"), "feat/w")
        git(self.repo, "config", "core.fsmonitor", str(script))
        self.inv()  # reads the status of the worktree
        self.assertFalse(marker.exists())

import contextlib
import io
import json
import unittest
from pathlib import Path
from unittest import mock

from helpers import commit, git, tb
from repo_case import RepoCase


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = tb.main(list(argv))
    return rc, out.getvalue(), err.getvalue()


class ApplyCase(RepoCase):
    """main; merged feat/a, feat/b and a clean worktree on a merged branch (P1); a squash (P3);
    unique work (P4); a stash. Scanned into self.board, ready for decisions."""

    def setUp(self):
        super().setUp()
        for name in ("feat/a", "feat/b"):
            self.work(name, {f"{name[-1]}.txt": "x\n"})
            git(self.repo, "merge", "-q", "--no-ff", "-m", f"merge {name}", name)
        self.work("feat/s", {"s.txt": "s\n"})
        commit(self.repo, "unrelated", {"u.txt": "u\n"})
        git(self.repo, "merge", "-q", "--squash", "feat/s")
        git(self.repo, "commit", "-q", "-m", "squash feat/s")
        self.work("spike/x", {"x.txt": "x\n"}, message="wip: x")
        git(self.repo, "branch", "wtm")
        self.wt = self.tmp / "wtm"
        git(self.repo, "worktree", "add", "-q", str(self.wt), "wtm")
        (self.repo / "a.txt").write_text("dirty\n")
        git(self.repo, "stash", "push", "-q", "-m", "wip handoff")
        self.board = self.tmp / "board"
        rc, out, _ = run_cli("scan", str(self.repo), "--gh", "off", "--out", str(self.board))
        assert rc == 0, out
        self.scan = json.loads((self.board / "scan.json").read_text(encoding="utf-8"))
        self.batch = json.loads((self.board / "batch.json").read_text(encoding="utf-8"))
        self.ids = {e["name"]: e["id"] for e in self.scan["items"]}
        self.ids["G"] = "G"

    def decide(self, decisions, **state):
        items = {self.ids[name]: {"decision": d} for name, d in decisions.items()}
        body = {"batch_id": self.batch["batch_id"], "round": 1, "finished": True, "batch_note": "", "items": items}
        body.update(state)
        (self.board / "decisions.json").write_text(json.dumps(body), encoding="utf-8")

    def apply(self, *extra):
        return run_cli("apply", str(self.board), *extra)

    def branches(self):
        return set(git(self.repo, "for-each-ref", "--format=%(refname:short)", "refs/heads").split())

    def backups(self):
        return set(git(self.repo, "for-each-ref", "--format=%(refname)", "refs/tidy-board/backup").split())

    def sha(self, name):
        return git(self.repo, "rev-parse", "refs/heads/" + name).strip()

    def applied(self):
        return {e["id"]: e for e in json.loads((self.board / "applied.json").read_text(encoding="utf-8"))}

    def stashes(self):
        return git(self.repo, "stash", "list", "--format=%gs").splitlines()


class RefusalTest(ApplyCase):
    def test_no_decisions_file_means_no_apply(self):
        rc, _, err = self.apply()
        self.assertEqual(rc, 2)
        self.assertIn("decisions.json ausente", err)

    def test_an_unfinished_board_is_refused(self):
        self.decide({"feat/a": "approved"}, finished=False)
        rc, _, err = self.apply()
        self.assertEqual(rc, 2)
        self.assertIn("nao foi concluido", err)
        self.assertIn("feat/a", self.branches())

    def test_decisions_from_another_batch_or_round_are_refused(self):
        for key, value in (("batch_id", "other"), ("round", 2)):
            with self.subTest(key=key):
                self.decide({"feat/a": "approved"}, **{key: value})
                rc, _, err = self.apply()
                self.assertEqual(rc, 2)
                self.assertIn("outro lote ou rodada", err)
        self.assertIn("feat/a", self.branches())

    def test_garbage_decisions_do_not_crash_and_delete_nothing(self):
        (self.board / "decisions.json").write_text(json.dumps(
            {"batch_id": self.batch["batch_id"], "round": 1, "finished": True, "items": {self.ids["feat/a"]: "approved"}}),
            encoding="utf-8")
        rc, out, _ = self.apply()
        self.assertEqual(rc, 0)
        self.assertIn("nada aprovado", out)
        self.assertIn("feat/a", self.branches())

    def test_a_broken_scan_is_refused(self):
        self.decide({"feat/a": "approved"})
        scan = json.loads((self.board / "scan.json").read_text(encoding="utf-8"))
        scan["items"][0]["sha"] = "zzz"
        (self.board / "scan.json").write_text(json.dumps(scan), encoding="utf-8")
        rc, _, err = self.apply()
        self.assertEqual(rc, 2)
        self.assertIn("invalidos", err)


class DeletionTest(ApplyCase):
    def test_only_what_was_approved_is_deleted(self):
        self.decide({"feat/a": "approved", "feat/b": "rejected"})
        rc, out, _ = self.apply()
        self.assertEqual(rc, 0, out)
        self.assertNotIn("feat/a", self.branches())
        self.assertIn("feat/b", self.branches())
        self.assertIn("spike/x", self.branches())
        self.assertEqual(self.applied()[self.ids["feat/a"]]["action"], "deleted")
        self.assertEqual(self.backups(), set())  # a merged branch needs no backup

    def test_nothing_is_deleted_by_default(self):
        self.decide({})
        rc, out, _ = self.apply()
        self.assertEqual(rc, 0)
        self.assertEqual(self.branches(), {"main", "feat/a", "feat/b", "feat/s", "spike/x", "wtm"})

    def test_a_probable_or_unique_branch_is_backed_up_before_it_goes(self):
        sha_x, sha_s = self.sha("spike/x"), self.sha("feat/s")
        self.decide({"spike/x": "approved", "feat/s": "approved"})
        rc, out, _ = self.apply()
        self.assertEqual(rc, 0, out)
        self.assertNotIn("spike/x", self.branches())
        self.assertEqual(self.backups(), {"refs/tidy-board/backup/spike/x", "refs/tidy-board/backup/feat/s"})
        self.assertEqual(git(self.repo, "rev-parse", "refs/tidy-board/backup/spike/x").strip(), sha_x)
        self.assertEqual(git(self.repo, "rev-parse", "refs/tidy-board/backup/feat/s").strip(), sha_s)
        self.assertEqual(self.applied()[self.ids["spike/x"]]["backup"], "refs/tidy-board/backup/spike/x")

    def test_a_stash_is_dropped_by_its_commit_even_when_its_index_moved(self):
        scanned = [s for s in tb.list_stashes(self.repo)][0]["sha"]
        (self.repo / "a.txt").write_text("newer\n")
        git(self.repo, "stash", "push", "-q", "-m", "newer stash")  # the scanned one is now stash@{1}
        self.decide({self.scan_stash_name(): "approved"})
        rc, out, _ = self.apply()
        self.assertEqual(rc, 0, out)
        self.assertEqual(len(self.stashes()), 1)
        self.assertIn("newer stash", self.stashes()[0])
        self.assertEqual(git(self.repo, "rev-parse", "refs/tidy-board/backup/stash-" + scanned[:12]).strip(), scanned)

    def scan_stash_name(self):
        return [e["name"] for e in self.scan["items"] if e["kind"] == "stash"][0]

    def test_a_clean_worktree_on_a_merged_branch_goes_with_its_branch(self):
        self.decide({str(self.wt): "approved"})
        rc, out, _ = self.apply()
        self.assertEqual(rc, 0, out)
        self.assertFalse(self.wt.exists())
        self.assertNotIn("wtm", self.branches())
        self.assertIn("feat/a", self.branches())

    def test_dry_run_changes_nothing_and_writes_nothing(self):
        before = (self.branches(), self.stashes(), self.wt.exists())
        self.decide({"feat/a": "approved", "spike/x": "approved", self.scan_stash_name(): "approved", str(self.wt): "approved"})
        rc, out, _ = self.apply("--dry-run")
        self.assertEqual(rc, 0, out)
        self.assertEqual((self.branches(), self.stashes(), self.wt.exists()), before)
        self.assertEqual(self.backups(), set())
        self.assertFalse((self.board / "applied.json").exists())
        self.assertIn("would-delete", out)
        self.assertIn("simulado", out)


class GroupTest(ApplyCase):
    def test_the_group_deletes_every_p1_item_without_an_own_decision(self):
        self.decide({"G": "approved"})
        rc, out, _ = self.apply()
        self.assertEqual(rc, 0, out)
        for gone in ("feat/a", "feat/b", "wtm"):
            self.assertNotIn(gone, self.branches())
        self.assertFalse(self.wt.exists())

    def test_an_own_keep_or_later_beats_the_group(self):
        self.decide({"G": "approved", "feat/b": "rejected", "feat/a": "maybe"})
        rc, out, _ = self.apply()
        self.assertEqual(rc, 0, out)
        self.assertIn("feat/a", self.branches())
        self.assertIn("feat/b", self.branches())
        self.assertNotIn("wtm", self.branches())

    def test_the_group_never_reaches_probable_unique_or_stashes(self):
        self.decide({"G": "approved"})
        self.apply()
        self.assertIn("feat/s", self.branches())
        self.assertIn("spike/x", self.branches())
        self.assertEqual(len(self.stashes()), 1)
        self.assertEqual(self.backups(), set())

    def test_an_own_approval_still_works_when_the_group_is_kept(self):
        self.decide({"G": "rejected", "feat/a": "approved"})
        self.apply()
        self.assertNotIn("feat/a", self.branches())
        self.assertIn("feat/b", self.branches())


class RecheckTest(ApplyCase):
    def test_a_branch_that_moved_since_the_scan_is_skipped(self):
        git(self.repo, "checkout", "-q", "spike/x")
        commit(self.repo, "later", {"later.txt": "l\n"})
        git(self.repo, "checkout", "-q", "main")
        self.decide({"spike/x": "approved"})
        rc, out, _ = self.apply()
        self.assertEqual(rc, 1)
        self.assertIn("a ponta mudou desde o scan", out)
        self.assertIn("spike/x", self.branches())
        self.assertEqual(self.backups(), set())

    def test_a_branch_checked_out_since_the_scan_is_skipped(self):
        git(self.repo, "checkout", "-q", "spike/x")
        self.decide({"spike/x": "approved"})
        rc, out, _ = self.apply()
        self.assertEqual(rc, 1)
        self.assertIn("esta em uso em", out)
        self.assertIn("spike/x", self.branches())

    def test_a_branch_that_vanished_is_reported_not_crashed_on(self):
        git(self.repo, "branch", "-D", "feat/a")
        self.decide({"feat/a": "approved"})
        rc, out, _ = self.apply()
        self.assertEqual(rc, 1)
        self.assertIn("a branch nao existe mais", out)

    def test_p1_is_recomputed_so_an_edited_scan_cannot_delete_unmerged_work(self):
        scan = json.loads((self.board / "scan.json").read_text(encoding="utf-8"))
        for e in scan["items"]:
            if e["name"] == "spike/x":
                e["proof"], e["backup"] = "P1", False
        (self.board / "scan.json").write_text(json.dumps(scan), encoding="utf-8")
        self.decide({"spike/x": "approved"})
        rc, out, _ = self.apply()
        self.assertEqual(rc, 1)
        self.assertIn("deixou de estar mesclada na base", out)
        self.assertIn("spike/x", self.branches())

    def test_a_worktree_that_became_dirty_is_kept_with_its_branch(self):
        (self.wt / "scratch.txt").write_text("precious\n")
        self.decide({str(self.wt): "approved"})
        rc, out, _ = self.apply()
        self.assertEqual(rc, 1)
        self.assertIn("alterado(s) ou nao rastreado(s)", out)
        self.assertTrue((self.wt / "scratch.txt").exists())
        self.assertIn("wtm", self.branches())

    def test_a_worktree_is_removed_without_force_so_a_late_change_still_stops_git(self):
        calls = []
        real = tb.git

        def spy(root, *args, **kw):
            calls.append(args)
            return real(root, *args, **kw)

        self.decide({str(self.wt): "approved"})
        with mock.patch.object(tb, "git", spy):
            rc, out, _ = self.apply()
        self.assertEqual(rc, 0, out)
        removals = [c for c in calls if c[:2] == ("worktree", "remove")]
        self.assertEqual(len(removals), 1)
        self.assertFalse(any("--force" in c or "-f" in c for c in removals), removals)

    def test_a_worktree_whose_head_moved_is_kept(self):
        commit(self.wt, "moved", {"m.txt": "m\n"})
        self.decide({str(self.wt): "approved"})
        rc, out, _ = self.apply()
        self.assertEqual(rc, 1)
        self.assertTrue(self.wt.exists())

    def test_a_backup_name_that_collides_with_an_older_backup_skips_the_item(self):
        self.decide({"spike/x": "approved"})
        self.apply()  # leaves refs/tidy-board/backup/spike/x
        git(self.repo, "checkout", "-q", "-b", "spike")
        commit(self.repo, "wip", {"s2.txt": "s\n"})
        git(self.repo, "checkout", "-q", "main")
        board = self.tmp / "board2"
        self.assertEqual(run_cli("scan", str(self.repo), "--gh", "off", "--out", str(board))[0], 0)
        scan = json.loads((board / "scan.json").read_text(encoding="utf-8"))
        batch = json.loads((board / "batch.json").read_text(encoding="utf-8"))
        iid = [e["id"] for e in scan["items"] if e["name"] == "spike"][0]
        (board / "decisions.json").write_text(json.dumps({"batch_id": batch["batch_id"], "round": 1, "finished": True,
                                                          "items": {iid: {"decision": "approved"}}}), encoding="utf-8")
        rc, out, _ = run_cli("apply", str(board))
        self.assertEqual(rc, 1)
        self.assertIn("nao consegui criar o backup", out)
        self.assertIn("spike", self.branches())

    def test_a_stash_that_vanished_is_reported(self):
        git(self.repo, "stash", "drop", "-q")
        self.decide({self.scan_stash_name(): "approved"})
        rc, out, _ = self.apply()
        self.assertEqual(rc, 1)
        self.assertIn("o stash nao existe mais", out)

    def scan_stash_name(self):
        return [e["name"] for e in self.scan["items"] if e["kind"] == "stash"][0]

    def test_a_second_run_reports_the_gone_items_but_keeps_the_first_runs_record(self):
        self.decide({"spike/x": "approved"})
        self.apply()
        rc, out, _ = self.apply()
        self.assertEqual(rc, 1)
        self.assertIn("a branch nao existe mais", out)
        entry = self.applied()[self.ids["spike/x"]]
        self.assertEqual(entry["action"], "deleted")
        self.assertEqual(entry["backup"], "refs/tidy-board/backup/spike/x")


class RestoreTest(ApplyCase):
    def test_a_unique_branch_comes_back_and_its_backup_is_released(self):
        sha = self.sha("spike/x")
        self.decide({"spike/x": "approved"})
        self.apply()
        rc, out, _ = run_cli("restore", str(self.board), self.ids["spike/x"])
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.sha("spike/x"), sha)
        self.assertEqual(self.backups(), set())
        self.assertEqual(self.applied()[self.ids["spike/x"]]["action"], "restored")

    def test_a_merged_branch_has_no_backup_so_restore_says_how_to_recreate_it(self):
        sha = self.sha("feat/a")
        self.decide({"feat/a": "approved"})
        self.apply()
        rc, _, err = run_cli("restore", str(self.board), self.ids["feat/a"])
        self.assertEqual(rc, 2)
        self.assertIn("nao tem backup", err)
        self.assertIn(f"git branch feat/a {sha}", err)
        self.assertNotIn("feat/a", self.branches())
        self.assertEqual(self.applied()[self.ids["feat/a"]]["action"], "deleted")

    def test_a_merged_worktree_has_no_backup_either(self):
        self.decide({str(self.wt): "approved"})
        self.apply()
        rc, _, err = run_cli("restore", str(self.board), self.ids[str(self.wt)])
        self.assertEqual(rc, 2)
        self.assertIn("git branch wtm", err)

    def test_a_stash_is_stored_again(self):
        name = [e["name"] for e in self.scan["items"] if e["kind"] == "stash"][0]
        self.decide({name: "approved"})
        self.apply()
        self.assertEqual(self.stashes(), [])
        rc, out, _ = run_cli("restore", str(self.board), self.ids[name])
        self.assertEqual(rc, 0, out)
        self.assertEqual(len(self.stashes()), 1)
        self.assertEqual(self.backups(), set())

    def test_restoring_over_an_existing_branch_is_an_error_and_loses_nothing(self):
        self.decide({"spike/x": "approved"})
        self.apply()
        git(self.repo, "branch", "spike/x", "main")
        rc, _, err = run_cli("restore", str(self.board), self.ids["spike/x"])
        self.assertEqual(rc, 2)
        self.assertIn("refs/tidy-board/backup/spike/x", self.backups())

    def test_only_deleted_items_can_be_restored(self):
        self.decide({"spike/x": "approved"})
        self.apply()
        for item in (self.ids["feat/b"], "T99"):
            rc, _, err = run_cli("restore", str(self.board), item)
            self.assertEqual(rc, 2)
            self.assertIn("nao foi apagado por este lote", err)
        run_cli("restore", str(self.board), self.ids["spike/x"])
        rc, _, err = run_cli("restore", str(self.board), self.ids["spike/x"])
        self.assertEqual(rc, 2)


class DetachedWorktreeTest(RepoCase):
    def test_a_detached_worktree_with_unique_commits_is_backed_up_and_restorable(self):
        git(self.repo, "checkout", "-q", "-b", "tmp")
        sha = commit(self.repo, "wip", {"w.txt": "w\n"})
        git(self.repo, "checkout", "-q", "main")
        git(self.repo, "branch", "-D", "tmp")
        wt = self.tmp / "det"
        git(self.repo, "worktree", "add", "-q", "--detach", str(wt), sha)
        board = self.tmp / "board"
        run_cli("scan", str(self.repo), "--gh", "off", "--out", str(board))
        scan = json.loads((board / "scan.json").read_text(encoding="utf-8"))
        batch = json.loads((board / "batch.json").read_text(encoding="utf-8"))
        iid = scan["items"][0]["id"]
        (board / "decisions.json").write_text(json.dumps({"batch_id": batch["batch_id"], "round": 1, "finished": True,
                                                          "items": {iid: {"decision": "approved"}}}), encoding="utf-8")
        rc, out, _ = run_cli("apply", str(board))
        self.assertEqual(rc, 0, out)
        self.assertFalse(wt.exists())
        backup = "refs/tidy-board/backup/wt-" + sha[:12]
        self.assertEqual(git(self.repo, "rev-parse", backup).strip(), sha)
        rc, out, _ = run_cli("restore", str(board), iid)
        self.assertEqual(rc, 0, out)
        self.assertEqual(git(self.repo, "rev-parse", "tidy-board/restored-" + sha[:12]).strip(), sha)
        self.assertIn("git worktree add", out)


class P2RecheckTest(RepoCase):
    """P2 rested on gh at scan time: apply asks gh again, once per run, unless the history already proves it."""

    def setUp(self):
        super().setUp()
        self.sha = {n: self.work(f"feat/{n}", {f"{n}.txt": "x\n"}) for n in ("p", "q")}
        self.prs = [{"number": i, "headRefName": f"feat/{n}", "headRefOid": self.sha[n], "url": ""}
                    for i, n in enumerate(("p", "q"), 7)]
        self.fake_gh(self.prs)
        self.board = self.tmp / "board"
        rc, out, _ = run_cli("scan", str(self.repo), "--gh", "auto", "--out", str(self.board))
        assert rc == 0, out
        scan = json.loads((self.board / "scan.json").read_text(encoding="utf-8"))
        batch = json.loads((self.board / "batch.json").read_text(encoding="utf-8"))
        assert [e["proof"] for e in scan["items"]] == ["P2", "P2"], scan["items"]
        items = {e["id"]: {"decision": "approved"} for e in scan["items"]}
        (self.board / "decisions.json").write_text(json.dumps(
            {"batch_id": batch["batch_id"], "round": 1, "finished": True, "items": items}), encoding="utf-8")

    def branches(self):
        return set(git(self.repo, "for-each-ref", "--format=%(refname:short)", "refs/heads").split())

    def test_deleted_when_gh_still_confirms_and_asked_only_once(self):
        before = self.gh_calls()
        rc, out, _ = run_cli("apply", str(self.board))
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.gh_calls() - before, 1)
        self.assertEqual(self.branches(), {"main"})

    def test_skipped_when_gh_is_unavailable(self):
        self.fake_gh(self.prs, exit_code=1)
        rc, out, _ = run_cli("apply", str(self.board))
        self.assertEqual(rc, 1)
        self.assertIn("gh indisponivel", out)
        self.assertEqual(self.branches(), {"main", "feat/p", "feat/q"})

    def test_skipped_when_the_pr_no_longer_matches_the_tip(self):
        self.fake_gh([{**self.prs[0], "headRefOid": "0" * 40}, self.prs[1]])
        rc, out, _ = run_cli("apply", str(self.board))
        self.assertEqual(rc, 1)
        self.assertIn("nao confere mais", out)
        self.assertEqual(self.branches(), {"main", "feat/p"})  # only the one gh still confirms went

    def test_no_gh_call_when_the_history_already_proves_it(self):
        for n in ("p", "q"):
            git(self.repo, "merge", "-q", "--no-ff", "-m", f"merge {n}", f"feat/{n}")
        self.fake_gh(self.prs, exit_code=1)  # would fail the items if it were consulted
        before = self.gh_calls()
        rc, out, _ = run_cli("apply", str(self.board))
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.gh_calls(), before)
        self.assertEqual(self.branches(), {"main"})


class RepoHooksTest(ApplyCase):
    def test_no_hook_of_the_repository_runs_while_apply_deletes(self):
        marker = self.tmp / "hook.ran"
        hook = self.repo / ".git" / "hooks" / "reference-transaction"
        hook.write_text(f"#!/bin/sh\ntouch '{marker}'\nexit 0\n", encoding="utf-8")
        hook.chmod(0o755)
        self.decide({"feat/a": "approved", "spike/x": "approved"})
        rc, out, _ = self.apply()
        self.assertEqual(rc, 0, out)
        self.assertNotIn("feat/a", self.branches())
        self.assertNotIn("spike/x", self.branches())
        self.assertFalse(marker.exists(), "git ran a hook of the repository")


class LyingSidecarTest(ApplyCase):
    """apply derives backups and branch drops from what it re-verifies, never from flags in scan.json."""

    def rescan(self, name="board2"):
        board = self.tmp / name
        rc, out, _ = run_cli("scan", str(self.repo), "--gh", "off", "--out", str(board))
        assert rc == 0, out
        scan = json.loads((board / "scan.json").read_text(encoding="utf-8"))
        batch = json.loads((board / "batch.json").read_text(encoding="utf-8"))
        return board, scan, batch

    def approve_only(self, board, batch, iid):
        (board / "decisions.json").write_text(json.dumps({"batch_id": batch["batch_id"], "round": 1, "finished": True,
                                                          "items": {iid: {"decision": "approved"}}}), encoding="utf-8")

    def lie(self, board, scan, iid, **fields):
        for e in scan["items"]:
            if e["id"] == iid:
                e.update(fields)
        (board / "scan.json").write_text(json.dumps(scan), encoding="utf-8")

    def test_a_cleared_backup_flag_still_gets_a_backup(self):
        self.lie(self.board, self.scan, self.ids["spike/x"], backup=False)
        self.decide({"spike/x": "approved"})
        rc, out, _ = self.apply()
        self.assertEqual(rc, 0, out)
        self.assertNotIn("spike/x", self.branches())
        self.assertEqual(self.backups(), {"refs/tidy-board/backup/spike/x"})

    def test_a_drop_branch_flag_cannot_delete_the_unique_work_of_a_worktree(self):
        git(self.repo, "checkout", "-q", "-b", "wtu")
        commit(self.repo, "unique", {"wtu.txt": "u\n"})
        git(self.repo, "checkout", "-q", "main")
        wt = self.tmp / "wtu"
        git(self.repo, "worktree", "add", "-q", str(wt), "wtu")
        board, scan, batch = self.rescan()
        iid = [e["id"] for e in scan["items"] if e["kind"] == "worktree" and e["name"] == str(wt)][0]
        self.lie(board, scan, iid, drop_branch=True, backup=False)
        self.approve_only(board, batch, iid)
        rc, out, _ = run_cli("apply", str(board))
        self.assertEqual(rc, 0, out)
        self.assertFalse(wt.exists())
        self.assertIn("wtu", self.branches())  # the branch has unique work: only the folder went

    def test_a_detached_worktree_is_backed_up_even_when_the_sidecar_claims_it_is_merged(self):
        git(self.repo, "checkout", "-q", "-b", "tmp")
        sha = commit(self.repo, "wip", {"w.txt": "w\n"})
        git(self.repo, "checkout", "-q", "main")
        git(self.repo, "branch", "-D", "tmp")
        wt = self.tmp / "det"
        git(self.repo, "worktree", "add", "-q", "--detach", str(wt), sha)
        board, scan, batch = self.rescan()
        iid = [e["id"] for e in scan["items"] if e["name"] == str(wt)][0]
        self.lie(board, scan, iid, proof="P1", backup=False)
        self.approve_only(board, batch, iid)
        rc, out, _ = run_cli("apply", str(board))
        self.assertEqual(rc, 0, out)
        self.assertEqual(git(self.repo, "rev-parse", "refs/tidy-board/backup/wt-" + sha[:12]).strip(), sha)

    def test_a_worktree_that_switched_branch_since_the_scan_is_kept(self):
        git(self.wt, "checkout", "-q", "-b", "other")  # same commit, another branch
        self.decide({str(self.wt): "approved"})
        rc, out, _ = self.apply()
        self.assertEqual(rc, 1)
        self.assertIn("mudou de branch", out)
        self.assertTrue(self.wt.exists())
        self.assertIn("wtm", self.branches())


class DeletionMechanicsTest(ApplyCase):
    def test_a_branch_is_deleted_only_if_it_still_points_where_it_was_checked(self):
        sha = self.sha("feat/a")
        calls = []
        real = tb.git

        def spy(root, *args, **kw):
            calls.append(args)
            return real(root, *args, **kw)

        self.decide({"feat/a": "approved"})
        with mock.patch.object(tb, "git", spy):
            rc, out, _ = self.apply()
        self.assertEqual(rc, 0, out)
        deletions = [c for c in calls if c[:2] == ("update-ref", "-d")]
        self.assertTrue(any(c[2] == "refs/heads/feat/a" and c[3] == sha for c in deletions), deletions)
        self.assertFalse(any(c[:2] == ("branch", "-D") for c in calls))

    def test_the_branch_config_section_goes_with_the_branch(self):
        git(self.repo, "config", "branch.feat/a.remote", "origin")
        git(self.repo, "config", "branch.feat/a.merge", "refs/heads/feat/a")
        self.decide({"feat/a": "approved"})
        self.assertEqual(self.apply()[0], 0)
        left = git(self.repo, "config", "--get-regexp", r"^branch\.feat/a\.", check=False)
        self.assertEqual(left.strip(), "")

    def test_an_interrupted_run_still_records_what_it_already_deleted(self):
        real = tb.apply_item
        seen = []

        def interrupt_on_second(*args, **kw):
            if seen:
                raise KeyboardInterrupt
            seen.append(1)
            return real(*args, **kw)

        self.decide({"feat/a": "approved", "feat/b": "approved"})
        with mock.patch.object(tb, "apply_item", interrupt_on_second):
            with self.assertRaises(KeyboardInterrupt):
                self.apply()
        done = [e for e in self.applied().values() if e["action"] == "deleted"]
        self.assertEqual([e["name"] for e in done], ["feat/a"])

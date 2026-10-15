import argparse
import contextlib
import io
import json
import os
import stat
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from helpers import commit, git, init_repo, load_engine, load_todo_sweep

ts = load_todo_sweep()
engine = load_engine()
NOW = 1_800_000_000  # a fixed "today"
DAY = 86400


def when(days_ago):
    return f"{NOW - days_ago * DAY} +0000"


class SweepCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        self.repo = init_repo(self.tmp / "r")
        quiet = contextlib.redirect_stdout(io.StringIO())  # cmd_scan reports on stdout; the tests do not need it
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)
        clock = mock.patch.object(ts, "NOW", lambda: NOW)
        clock.start()
        self.addCleanup(clock.stop)

    def commit(self, files, days_ago=0):
        return commit(self.repo, "c", files, date=when(days_ago))

    def args(self, **kw):
        base = dict(repo=str(self.repo), limit=20, max_blame=300, out=None)
        base.update(kw)
        return argparse.Namespace(**base)

    def scan(self, **kw):
        rc = ts.cmd_scan(self.args(**kw))
        folders = sorted((self.repo / ".todo-sweep").glob("todo-sweep-*"))
        return rc, folders[-1] if folders else None


class ScanFilesTest(SweepCase):
    def test_hits_come_in_path_order_with_ids_and_context(self):
        self.commit({"b.py": "# TODO: second file\n", "a.py": "x = 1\n# FIXME: first file\n"})
        hits = ts.scan_files(self.repo)
        self.assertEqual([(h["file"], h["line"], h["marker"], h["text"]) for h in hits],
                         [("a.py", 2, "FIXME", "first file"), ("b.py", 1, "TODO", "second file")])
        self.assertEqual(len({h["todo_id"] for h in hits}), 2)
        self.assertEqual(hits[0]["context"][0], (1, "x = 1"))

    def test_identical_todos_in_one_file_get_distinct_ids(self):
        self.commit({"a.py": "# TODO\n# TODO\n"})
        ids = [h["todo_id"] for h in ts.scan_files(self.repo)]
        self.assertEqual(len(set(ids)), 2)

    def test_markdown_binary_large_untracked_and_symlinked_files_are_skipped(self):
        self.commit({"notes.md": "# TODO: prose\n", "NOTES.MARKDOWN": "# TODO: prose\n", "ok.py": "# TODO: real\n"})
        (self.repo / "bin.dat").write_bytes(b"\0\0# TODO: binary\n")
        (self.repo / "big.txt").write_text("# TODO: big\n" + "x" * (ts.MAX_FILE + 10), encoding="utf-8")
        (self.repo / "untracked.py").write_text("# TODO: untracked\n", encoding="utf-8")
        outside = self.tmp / "outside.py"
        outside.write_text("# TODO: outside\n", encoding="utf-8")
        os.symlink(outside, self.repo / "link.py")
        git(self.repo, "add", "bin.dat", "big.txt", "link.py")
        git(self.repo, "commit", "-q", "-m", "more")
        self.assertEqual([h["text"] for h in ts.scan_files(self.repo)], ["real"])

    def test_a_folder_that_is_not_a_repository_is_an_error(self):
        plain = self.tmp / "plain"
        plain.mkdir()
        with self.assertRaises(ts.SweepError):
            ts.repo_root(plain)


class AgeTest(SweepCase):
    def ages(self, **kw):
        hits = ts.scan_files(self.repo)
        ts.blame_ages(self.repo, hits, kw.get("cap", 300))
        return hits

    def test_the_age_is_the_days_since_the_lines_last_change(self):
        self.commit({"a.py": "# TODO: old\nx = 1\n"}, days_ago=400)
        self.commit({"a.py": "# TODO: old\nx = 1\n# TODO: newer\n"}, days_ago=10)
        old, newer = self.ages()
        self.assertEqual((old["age"]["days"], old["age"]["commit"]), (400, git(self.repo, "log", "--format=%h", "--reverse").split()[0]))
        self.assertEqual(newer["age"]["days"], 10)
        self.assertEqual(old["age_reason"], "")

    def test_an_uncommitted_line_has_no_age(self):
        self.commit({"a.py": "x = 1\n"}, days_ago=5)
        (self.repo / "a.py").write_text("x = 1\n# TODO: fresh\n", encoding="utf-8")
        hit, = self.ages()
        self.assertIsNone(hit["age"])
        self.assertEqual(hit["age_reason"], "linha nao commitada")

    def test_a_staged_but_uncommitted_new_file_has_no_age(self):
        self.commit({"keep.py": "x\n"}, days_ago=5)
        (self.repo / "new.py").write_text("# TODO: new\n", encoding="utf-8")
        git(self.repo, "add", "new.py")
        hit, = self.ages()
        self.assertIsNone(hit["age"])
        self.assertEqual(hit["age_reason"], "linha nao commitada")

    def test_when_blame_itself_fails_the_hit_says_so(self):
        self.commit({"a.py": "# TODO: x\n"}, days_ago=5)
        real = ts.git
        with mock.patch.object(ts, "git", lambda root, *args: (128, "") if args[0] == "blame" else real(root, *args)):
            hit, = self.ages()
        self.assertIsNone(hit["age"])
        self.assertIn("sem historico", hit["age_reason"])

    def test_the_cap_limits_how_many_are_measured_in_listing_order(self):
        self.commit({"a.py": "# TODO: a\n", "b.py": "# TODO: b\n", "c.py": "# TODO: c\n"}, days_ago=30)
        hits = self.ages(cap=2)
        self.assertEqual([bool(h["age"]) for h in hits], [True, True, False])
        self.assertEqual(hits[2]["age_reason"], "alem do limite de --max-blame")

    def test_a_shallow_clone_boundary_has_no_age(self):
        self.commit({"a.py": "# TODO: ancient\n"}, days_ago=900)
        self.commit({"b.py": "# TODO: recent\n"}, days_ago=3)
        clone = self.tmp / "clone"
        git(self.tmp, "clone", "-q", "--depth", "1", f"file://{self.repo}", str(clone))
        hits = ts.scan_files(clone)
        ts.blame_ages(clone, hits, 300)
        self.assertTrue(ts.is_shallow(clone))
        self.assertFalse(ts.is_shallow(self.repo))
        self.assertTrue(all(h["age"] is None and "clone raso" in h["age_reason"] for h in hits), hits)

    def test_the_first_commit_of_a_full_repository_still_has_an_age(self):
        self.commit({"a.py": "# TODO: from the very first commit\n"}, days_ago=77)
        hit, = self.ages()
        self.assertEqual(hit["age"]["days"], 77)

    def test_blame_output_where_a_commit_repeats_is_parsed(self):
        self.commit({"a.py": "# TODO: one\n# TODO: two\n# TODO: three\n"}, days_ago=20)
        self.assertEqual([h["age"]["days"] for h in self.ages()], [20, 20, 20])

    def test_ordering_is_oldest_first_then_what_has_no_age(self):
        self.commit({"a.py": "# TODO: mid\n", "z.py": "# TODO: oldest\n"}, days_ago=50)
        self.commit({"a.py": "# TODO: mid\n", "z.py": "# TODO: oldest\n", "m.py": "# TODO: new\n"}, days_ago=2)
        hits = self.ages(cap=2)  # a.py and m.py are measured; z.py is not
        ordered = ts.order_hits(hits)
        self.assertEqual([h["text"] for h in ordered], ["mid", "new", "oldest"])


class LedgerTest(SweepCase):
    def test_no_ledger_means_nothing_decided(self):
        self.assertEqual(ts.load_ledger(self.repo), {})

    def test_a_ledger_round_trips_privately(self):
        ts.save_ledger(self.repo, {"abc": {"decision": "keep"}})
        self.assertEqual(ts.load_ledger(self.repo), {"abc": {"decision": "keep"}})
        self.assertEqual(stat.S_IMODE(os.stat(ts.ledger_path(self.repo)).st_mode), 0o600)

    def test_a_corrupt_ledger_is_an_error_not_an_empty_one(self):
        (self.repo / ".todo-sweep").mkdir()
        for bad in ("not json", "[]", '{"decided": 3}'):
            ts.ledger_path(self.repo).write_text(bad, encoding="utf-8")
            with self.subTest(bad=bad), self.assertRaises(ts.SweepError):
                ts.load_ledger(self.repo)


class SymlinkedWorkFolderTest(SweepCase):
    def test_a_work_folder_that_is_a_symlink_is_never_written_or_read_through(self):
        self.commit({"a.py": "# TODO: x\n"}, days_ago=3)
        outside = self.tmp / "elsewhere"
        outside.mkdir()
        os.symlink(outside, self.repo / ".todo-sweep")
        with self.assertRaises(ts.SweepError) as ctx:
            ts.cmd_scan(self.args())
        self.assertIn("link simbolico", str(ctx.exception))
        with self.assertRaises(ts.SweepError):
            ts.save_ledger(self.repo, {"a": {}})
        with self.assertRaises(ts.SweepError):
            ts.load_ledger(self.repo)
        self.assertEqual(list(outside.iterdir()), [])


class ScanCommandTest(SweepCase):
    def seed(self):
        self.commit({"src/a.py": "# TODO: oldest\n", "src/b.py": "x = 1\n"}, days_ago=300)
        self.commit({"src/b.py": "x = 1\n# FIXME: middle\n"}, days_ago=100)
        self.commit({"src/c.py": "# TODO: youngest\n"}, days_ago=5)

    def test_the_batch_is_valid_for_the_real_engine_and_oldest_first(self):
        self.seed()
        rc, out = self.scan()
        batch = json.loads((out / "batch.json").read_text(encoding="utf-8"))
        self.assertEqual((rc, engine.validate(batch)), (0, []))
        self.assertEqual([i["id"] for i in batch["items"]], ["T01", "T02", "T03"])
        self.assertEqual([i["title"] for i in batch["items"]],
                         ["TODO em src/a.py:1: oldest", "FIXME em src/b.py:2: middle", "TODO em src/c.py:1: youngest"])
        self.assertEqual(batch["labels"]["approve"], {"text": "Resolver", "tone": "safe"})
        self.assertEqual(batch["labels"]["reject"], {"text": "Descartar", "tone": "danger"})
        self.assertEqual(batch["labels"]["maybe"], {"text": "Manter", "tone": "caution"})
        self.assertEqual(batch["batch_id"], out.name)
        card = {f["label"]: f["text"] for f in batch["items"][0]["fields"]}
        self.assertEqual(card["Onde"], "`src/a.py:1`")
        self.assertTrue(card["Idade"].startswith("300 dias"), card["Idade"])
        self.assertIn("   1  # TODO: oldest", card["Trecho"])

    def test_the_sidecar_records_what_the_report_needs(self):
        self.seed()
        _rc, out = self.scan()
        scan = json.loads((out / "scan.json").read_text(encoding="utf-8"))
        self.assertEqual((scan["schema"], scan["tool"], scan["round"], scan["repo"]), (1, "todo-sweep", 1, str(self.repo)))
        first = scan["items"][0]
        self.assertEqual((first["id"], first["file"], first["line"], first["marker"], first["text"], first["age_days"]),
                         ("T01", "src/a.py", 1, "TODO", "oldest", 300))
        self.assertEqual(len(first["todo_id"]), 16)
        self.assertEqual({k: scan["totals"][k] for k in ("found", "new", "unaged", "shown")}, {"found": 3, "new": 3, "unaged": 0, "shown": 3})

    def test_the_limit_and_the_ledger_give_the_next_batch_the_next_todos(self):
        self.seed()
        _rc, first = self.scan(limit=2)
        scan = json.loads((first / "scan.json").read_text(encoding="utf-8"))
        self.assertEqual([i["text"] for i in scan["items"]], ["oldest", "middle"])
        ts.save_ledger(self.repo, {i["todo_id"]: {"decision": "keep"} for i in scan["items"]})
        _rc, second = self.scan(limit=2)
        self.assertNotEqual(second, first)
        again = json.loads((second / "scan.json").read_text(encoding="utf-8"))
        self.assertEqual([i["text"] for i in again["items"]], ["youngest"])
        self.assertEqual(again["totals"]["decided_before"], 2)

    def test_when_everything_is_decided_nothing_is_written(self):
        self.commit({"a.py": "# TODO: only\n"}, days_ago=9)
        ts.save_ledger(self.repo, {h["todo_id"]: {"decision": "discard"} for h in ts.scan_files(self.repo)})
        rc, out = self.scan()
        self.assertEqual((rc, out), (0, None))

    def test_the_batch_folder_and_files_are_private_and_the_repository_is_untouched(self):
        self.seed()
        _rc, out = self.scan()
        for name in ("batch.json", "scan.json"):
            self.assertEqual(stat.S_IMODE(os.stat(out / name).st_mode), 0o600)
        self.assertEqual(git(self.repo, "status", "--porcelain").strip(), "?? .todo-sweep/")

    def test_a_custom_output_folder_names_the_batch(self):
        self.seed()
        target = self.tmp / "board"
        ts.cmd_scan(self.args(out=str(target)))
        self.assertEqual(json.loads((target / "batch.json").read_text(encoding="utf-8"))["batch_id"], "board")

    def test_backticks_in_names_cannot_open_a_code_span_on_the_card(self):
        self.commit({"we`ird.py": "# TODO: use `x` here\n"}, days_ago=1)
        _rc, out = self.scan()
        batch = json.loads((out / "batch.json").read_text(encoding="utf-8"))
        self.assertEqual(engine.validate(batch), [])
        self.assertNotIn("we`ird", json.dumps(batch))

    def test_a_long_text_is_cut_in_the_title_and_whole_in_the_card(self):
        self.commit({"a.py": "# TODO: " + "word " * 40 + "\n"}, days_ago=1)
        _rc, out = self.scan()
        item = json.loads((out / "batch.json").read_text(encoding="utf-8"))["items"][0]
        self.assertTrue(item["title"].endswith("..."))
        self.assertLess(len(item["title"]), 120)
        self.assertGreater(len(dict((f["label"], f["text"]) for f in item["fields"])["Texto"]), 150)

    def test_many_cards_get_wider_ids(self):
        self.commit({"a.py": "".join(f"# TODO: n{i}\n" for i in range(120))}, days_ago=3)
        _rc, out = self.scan(limit=120)
        ids = [i["id"] for i in json.loads((out / "batch.json").read_text(encoding="utf-8"))["items"]]
        self.assertEqual((ids[0], ids[-1]), ("T001", "T120"))


class CheckTest(SweepCase):
    def test_a_fresh_scan_passes_and_tampering_is_reported(self):
        self.commit({"a.py": "# TODO: one\n# TODO: two\n"}, days_ago=4)
        _rc, out = self.scan()
        self.assertEqual(ts.cmd_check(argparse.Namespace(dir=str(out))), 0)
        scan = json.loads((out / "scan.json").read_text(encoding="utf-8"))
        scan["items"].pop()
        (out / "scan.json").write_text(json.dumps(scan), encoding="utf-8")
        self.assertEqual(ts.cmd_check(argparse.Namespace(dir=str(out))), 1)

    def test_missing_files_are_an_error(self):
        with self.assertRaises(ts.SweepError):
            ts.cmd_check(argparse.Namespace(dir=str(self.tmp / "none")))

    def test_a_scan_of_another_tool_or_shape_is_rejected(self):
        batch = {"batch_id": "x", "items": []}
        for scan in ({"tool": "tidy-board", "schema": 1}, [], {"tool": "todo-sweep", "schema": 1, "items": {}, "repo": "r"}):
            with self.subTest(scan=scan):
                self.assertTrue(ts.scan_problems(batch, scan))


class GitHelperTest(SweepCase):
    def test_a_missing_git_binary_is_the_tools_own_error(self):
        with mock.patch.object(ts.subprocess, "run", side_effect=FileNotFoundError(2, "No such file or directory")):
            with self.assertRaises(ts.SweepError) as ctx:
                ts.git(self.repo, "status")
        self.assertIn("git nao encontrado", str(ctx.exception))

    def test_an_embedded_nul_in_an_argument_is_a_failed_result(self):
        self.assertEqual(ts.git(self.repo, "rev-parse", "a\0b")[0], 1)

    def test_a_git_dir_of_another_repository_does_not_change_what_the_scan_reports(self):
        self.commit({"a.py": "# TODO: mine\n"}, days_ago=3)
        other = init_repo(self.tmp / "other")
        commit(other, "c", {"z.py": "# TODO: theirs\n"}, date=when(1))
        keep = {k: os.environ.get(k) for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")}
        os.environ.update(GIT_DIR=str(other / ".git"), GIT_WORK_TREE=str(other), GIT_INDEX_FILE=str(other / ".git" / "index"))
        try:
            root = ts.repo_root(self.repo)
            texts = [h["text"] for h in ts.scan_files(root)]
        finally:
            for k, v in keep.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        self.assertEqual((root, texts), (self.repo, ["mine"]))


class HostileInputTest(SweepCase):
    def ledger(self, text):
        (self.repo / ".todo-sweep").mkdir(exist_ok=True)
        ts.ledger_path(self.repo).write_text(text, encoding="utf-8")

    def test_a_deeply_nested_ledger_is_an_error_not_a_traceback(self):
        self.ledger("[" * 100000)
        with self.assertRaises(ts.SweepError):
            ts.load_ledger(self.repo)
        self.ledger('{"decided": ' + "[" * 100000)
        with self.assertRaises(ts.SweepError):
            ts.load_ledger(self.repo)

    def test_a_ledger_that_is_not_utf8_is_an_error(self):
        (self.repo / ".todo-sweep").mkdir()
        ts.ledger_path(self.repo).write_bytes(b'{"decided": {"\xff\xfe": 1}}')
        with self.assertRaises(ts.SweepError):
            ts.load_ledger(self.repo)

    def test_an_unreadable_ledger_is_an_error(self):
        self.ledger('{"decided": {}}')
        path = ts.ledger_path(self.repo)
        os.chmod(path, 0)
        self.addCleanup(os.chmod, path, 0o600)
        if os.access(path, os.R_OK):
            self.skipTest("this user can read a file with no permissions")
        with self.assertRaises(ts.SweepError):
            ts.load_ledger(self.repo)

    def test_a_ledger_that_is_a_folder_is_an_error(self):
        (self.repo / ".todo-sweep" / "ledger.json").mkdir(parents=True)
        with self.assertRaises(ts.SweepError):
            ts.load_ledger(self.repo)

    def test_a_deeply_nested_or_unreadable_batch_folder_is_an_error(self):
        out = self.tmp / "b"
        out.mkdir()
        (out / "batch.json").write_text("[" * 100000, encoding="utf-8")
        (out / "scan.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(ts.SweepError):
            ts.cmd_check(argparse.Namespace(dir=str(out)))
        (out / "batch.json").write_bytes(b"\xff\xfe")
        with self.assertRaises(ts.SweepError):
            ts.cmd_check(argparse.Namespace(dir=str(out)))
        (out / "batch.json").unlink()
        (out / "batch.json").mkdir()
        with self.assertRaises(ts.SweepError):
            ts.cmd_check(argparse.Namespace(dir=str(out)))

    def test_an_unreadable_source_file_is_skipped_not_fatal(self):
        self.commit({"a.py": "# TODO: a\n", "b.py": "# TODO: b\n"}, days_ago=1)
        os.chmod(self.repo / "a.py", 0)
        self.addCleanup(os.chmod, self.repo / "a.py", 0o600)
        self.assertEqual(sorted(h["text"] for h in ts.scan_files(self.repo)),
                         ["b"] if not os.access(self.repo / "a.py", os.R_OK) else ["a", "b"])


class FailedWriteTest(SweepCase):
    def test_a_failed_write_raises_the_tools_error_and_leaves_no_file_behind(self):
        target = self.tmp / "x.json"
        with mock.patch.object(ts.os, "replace", side_effect=OSError(28, "No space left on device")):
            with self.assertRaises(ts.SweepError) as ctx:
                ts.write_private(target, "{}")
        self.assertIn("nao consegui gravar", str(ctx.exception))
        self.assertEqual(list(self.tmp.glob("x.json*")), [])

    def test_text_that_cannot_be_encoded_is_an_error_and_creates_nothing(self):
        target = self.tmp / "x.json"
        with self.assertRaises(ts.SweepError):
            ts.write_private(target, "lone surrogate \ud800")
        self.assertEqual(list(self.tmp.glob("x.json*")), [])

    def test_the_ledger_is_not_half_written(self):
        ts.save_ledger(self.repo, {"a": {"decision": "keep"}})
        with mock.patch.object(ts.os, "replace", side_effect=OSError(5, "I/O error")):
            with self.assertRaises(ts.SweepError):
                ts.save_ledger(self.repo, {"b": {"decision": "keep"}})
        self.assertEqual(ts.load_ledger(self.repo), {"a": {"decision": "keep"}})
        self.assertEqual(sorted(p.name for p in (self.repo / ".todo-sweep").iterdir()), ["ledger.json"])

    def test_a_scan_whose_second_file_fails_leaves_no_batch_behind(self):
        self.commit({"a.py": "# TODO: x\n"}, days_ago=3)
        real, calls = os.replace, []

        def flaky(src, dst):
            calls.append(dst)
            if len(calls) == 2:
                raise OSError(28, "No space left on device")
            return real(src, dst)

        with mock.patch.object(ts.os, "replace", flaky):
            with self.assertRaises(ts.SweepError):
                ts.cmd_scan(self.args())
        self.assertEqual(len(calls), 2)
        self.assertEqual(list((self.repo / ".todo-sweep").glob("*")), [])

    def test_an_output_folder_that_cannot_be_created_is_an_error(self):
        self.commit({"a.py": "# TODO: x\n"}, days_ago=3)
        blocker = self.tmp / "blocker"
        blocker.write_text("a file", encoding="utf-8")
        with self.assertRaises(ts.SweepError):
            ts.cmd_scan(self.args(out=str(blocker / "board")))

    def test_an_existing_output_folder_keeps_what_it_had_when_the_write_fails(self):
        self.commit({"a.py": "# TODO: x\n"}, days_ago=3)
        out = self.tmp / "board"
        out.mkdir()
        (out / "batch.json").write_text("old", encoding="utf-8")
        with mock.patch.object(ts.os, "replace", side_effect=OSError(28, "No space left on device")):
            with self.assertRaises(ts.SweepError):
                ts.cmd_scan(self.args(out=str(out)))
        self.assertEqual((out / "batch.json").read_text(encoding="utf-8"), "old")
        self.assertEqual(sorted(p.name for p in out.iterdir()), ["batch.json"])


if __name__ == "__main__":
    unittest.main()

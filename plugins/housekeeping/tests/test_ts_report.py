import argparse
import contextlib
import io
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import commit, git, init_repo, load_engine, load_todo_sweep

ts = load_todo_sweep()
engine = load_engine()
NOW = 1_800_000_000
DAY = 86400


class ReportCase(unittest.TestCase):
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
        commit(self.repo, "c1", {"a.py": "# TODO: one\n# TODO: two\n"}, date=f"{NOW - 90 * DAY} +0000")
        commit(self.repo, "c2", {"b.py": "# FIXME: three\n# TODO: four\n"}, date=f"{NOW - 5 * DAY} +0000")
        ts.cmd_scan(self.args())
        self.out = sorted((self.repo / ".todo-sweep").glob("todo-sweep-*"))[-1]
        self.scan = json.loads((self.out / "scan.json").read_text(encoding="utf-8"))

    def args(self, **kw):
        base = dict(repo=str(self.repo), limit=20, max_blame=300, out=None, lang="en")
        base.update(kw)
        return argparse.Namespace(**base)

    def decide(self, decisions, finish=True):
        """The way the real panel does it: the engine's own Store writes decisions.json."""
        store = engine.Store(self.out)
        for item_id, (decision, comment) in decisions.items():
            body = {"decision": decision}
            if comment:
                body["comment"] = comment
            store.set_item(item_id, body)
        if finish:
            store.set_finished(True)

    def report(self):
        return ts.cmd_report(argparse.Namespace(dir=str(self.out)))

    def result(self):
        return json.loads((self.out / "report.json").read_text(encoding="utf-8"))


class ReportTest(ReportCase):
    def test_decisions_become_a_report_in_three_words_plus_undecided(self):
        ids = [i["id"] for i in self.scan["items"]]
        self.decide({ids[0]: ("approved", "do it soon"), ids[1]: ("rejected", ""), ids[2]: ("maybe", "")})
        self.assertEqual(self.report(), 0)
        data = self.result()
        self.assertEqual((data["schema"], data["tool"], data["batch_id"], data["round"]), (1, "todo-sweep", self.out.name, 1))
        self.assertEqual(data["counts"], {"resolver": 1, "descartar": 1, "manter": 1, "sem_decisao": 1})
        self.assertEqual(data["resolver"][0]["comment"], "do it soon")
        self.assertEqual([h["text"] for h in data["sem_decisao"]], [self.scan["items"][3]["text"]])
        md = (self.out / "report.md").read_text(encoding="utf-8")
        for heading in ("## Resolve (1)", "## Discard (1)", "## Keep (1)", "## No decision (1)"):
            self.assertIn(heading, md)
        self.assertIn("do it soon", md)
        self.assertIn("No file was edited", md)
        self.assertEqual(data["lang"], "en")

    def test_only_descartar_and_manter_are_remembered_and_the_next_scan_skips_them(self):
        ids = [i["id"] for i in self.scan["items"]]
        self.decide({ids[0]: ("approved", ""), ids[1]: ("rejected", ""), ids[2]: ("maybe", "")})
        self.report()
        ledger = ts.load_ledger(self.repo)
        self.assertEqual(sorted(e["decision"] for e in ledger.values()), ["discard", "keep"])
        self.assertNotIn(self.scan["items"][0]["todo_id"], ledger)  # Resolver stays until the TODO disappears
        self.assertNotIn(self.scan["items"][3]["todo_id"], ledger)  # undecided stays too
        ts.cmd_scan(self.args())
        newest = sorted((self.repo / ".todo-sweep").glob("todo-sweep-*"))[-1]
        texts = [i["text"] for i in json.loads((newest / "scan.json").read_text(encoding="utf-8"))["items"]]
        self.assertEqual(sorted(texts), sorted([self.scan["items"][0]["text"], self.scan["items"][3]["text"]]))

    def test_running_the_report_twice_gives_the_same_result(self):
        ids = [i["id"] for i in self.scan["items"]]
        self.decide({ids[0]: ("approved", "soon"), ids[1]: ("rejected", "old"), ids[2]: ("maybe", "")})

        def snapshot():
            data = json.loads((self.out / "report.json").read_text(encoding="utf-8"))
            data.pop("created")
            ledger = {k: {f: v for f, v in e.items() if f not in ("at", "created")} for k, e in ts.load_ledger(self.repo).items()}
            return data, (self.out / "report.md").read_bytes(), ledger

        self.report()
        first = snapshot()
        self.report()
        second = snapshot()
        self.assertEqual(first, second)
        self.assertEqual(len(first[2]), 2)
        self.assertEqual(len(second[2]), 2)
        self.assertEqual(sum(len(second[0][k]) for k in ("resolver", "descartar", "manter", "sem_decisao")), 4)

    def test_the_report_files_and_ledger_are_private_and_no_source_file_is_touched(self):
        self.decide({self.scan["items"][0]["id"]: ("rejected", "")})
        before = {p: p.read_bytes() for p in self.repo.glob("*.py")}
        self.report()
        for path in (self.out / "report.md", self.out / "report.json", ts.ledger_path(self.repo)):
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600, path)
        self.assertEqual({p: p.read_bytes() for p in self.repo.glob("*.py")}, before)
        self.assertEqual(git(self.repo, "status", "--porcelain").strip(), "?? .todo-sweep/")

    def test_a_comment_with_backticks_cannot_break_the_markdown_code_spans(self):
        self.decide({self.scan["items"][0]["id"]: ("approved", "use `rm -rf`")})
        self.report()
        self.assertNotIn("`rm -rf`", (self.out / "report.md").read_text(encoding="utf-8"))


class RefusalTest(ReportCase):
    def test_an_unfinished_board_writes_nothing(self):
        self.decide({self.scan["items"][0]["id"]: ("rejected", "")}, finish=False)
        with self.assertRaises(ts.SweepError) as ctx:
            self.report()
        self.assertIn("the panel was not finished", str(ctx.exception))
        self.assertFalse((self.out / "report.json").exists())
        self.assertEqual(ts.load_ledger(self.repo), {})

    def test_decisions_of_another_round_or_batch_are_never_used(self):
        self.decide({self.scan["items"][0]["id"]: ("rejected", "")})
        for key, value in (("round", 2), ("batch_id", "someone-else")):
            state = json.loads((self.out / "decisions.json").read_text(encoding="utf-8"))
            state[key] = value
            (self.out / "decisions.json").write_text(json.dumps(state), encoding="utf-8")
            with self.subTest(key=key), self.assertRaises(ts.SweepError) as ctx:
                self.report()
            self.assertIn("another batch or round", str(ctx.exception))
        self.assertEqual(ts.load_ledger(self.repo), {})

    def test_missing_and_garbage_decisions_are_refused(self):
        with self.assertRaises(ts.SweepError):
            self.report()
        for bad in ("not json", "[]", '{"items": 3}'):
            (self.out / "decisions.json").write_text(bad, encoding="utf-8")
            with self.subTest(bad=bad), self.assertRaises(ts.SweepError):
                self.report()

    def test_a_hand_edited_scan_that_does_not_match_the_batch_is_refused(self):
        self.decide({self.scan["items"][0]["id"]: ("rejected", "")})
        scan = dict(self.scan, items=self.scan["items"][:-1])
        (self.out / "scan.json").write_text(json.dumps(scan), encoding="utf-8")
        with self.assertRaises(ts.SweepError):
            self.report()

    def test_a_repository_that_is_gone_is_an_error_before_anything_is_written(self):
        self.decide({self.scan["items"][0]["id"]: ("rejected", "")})
        scan = dict(self.scan, repo=str(self.tmp / "gone"))
        (self.out / "scan.json").write_text(json.dumps(scan), encoding="utf-8")
        with self.assertRaises(ts.SweepError):
            self.report()
        self.assertFalse((self.out / "report.json").exists())

    def test_a_corrupt_ledger_stops_the_report_before_it_writes(self):
        self.decide({self.scan["items"][0]["id"]: ("rejected", "")})
        ts.ledger_path(self.repo).write_text("not json", encoding="utf-8")
        with self.assertRaises(ts.SweepError):
            self.report()
        self.assertFalse((self.out / "report.json").exists())

class TrustedRepoTest(ReportCase):
    """scan.json's `repo` says where the ledger is written, so a hand-edited sidecar may not redirect it: it must be
    an absolute path equal to the toplevel of a repository. Refused before anything is written, anywhere."""

    def tree(self, *roots):
        snap = {}
        for root in roots:
            for path in sorted(Path(root).rglob("*")):
                if ".git" in path.relative_to(root).parts:
                    continue
                snap[str(path)] = path.read_bytes() if path.is_file() else None
        return snap

    def refused_repo(self, value, *extra_roots):
        self.decide({self.scan["items"][0]["id"]: ("rejected", "")})
        (self.out / "scan.json").write_text(json.dumps(dict(self.scan, repo=value)), encoding="utf-8")
        before = self.tree(self.repo, *extra_roots)
        with self.assertRaises(ts.SweepError) as ctx:
            self.report()
        self.assertIn("repo", str(ctx.exception))
        self.assertEqual(self.tree(self.repo, *extra_roots), before)

    def test_another_repository_is_refused_and_neither_is_written(self):
        other = init_repo(self.tmp / "other")
        commit(other, "o", {"o.py": "# TODO: elsewhere\n"})
        self.refused_repo(str(other), other)
        self.assertFalse((other / ".todo-sweep").exists())

    def test_a_subdirectory_of_the_same_repository_is_refused(self):
        (self.repo / "sub").mkdir()
        self.refused_repo(str(self.repo / "sub"))
        self.assertFalse((self.repo / "sub" / ".todo-sweep").exists())

    def test_a_relative_path_is_refused_whatever_the_working_directory(self):
        for value in (".", "r", "../r"):
            old = os.getcwd()
            os.chdir(self.repo)
            try:
                with self.subTest(value=value):
                    self.refused_repo(value)
            finally:
                os.chdir(old)

    def test_a_repo_that_is_not_text_is_refused(self):
        for value in (None, 3, ["x"], {"a": 1}, True):
            with self.subTest(value=value):
                self.refused_repo(value)

    def test_a_path_with_a_nul_is_refused(self):
        self.refused_repo(str(self.repo) + "\0x")

    def test_the_normal_flow_and_a_symlinked_spelling_of_the_toplevel_still_work(self):
        self.decide({self.scan["items"][0]["id"]: ("rejected", "")})
        self.assertEqual(self.report(), 0)
        link = self.tmp / "link"
        link.symlink_to(self.repo)
        (self.out / "scan.json").write_text(json.dumps(dict(self.scan, repo=str(link))), encoding="utf-8")
        self.assertEqual(self.report(), 0)  # the same toplevel by its real path

    def test_a_custom_out_folder_outside_the_work_area_still_reports(self):
        out = self.tmp / "custom"
        ts.cmd_scan(self.args(out=str(out)))
        store = engine.Store(out)
        store.set_item("T01", {"decision": "rejected"})
        store.set_finished(True)
        self.assertEqual(ts.cmd_report(argparse.Namespace(dir=str(out))), 0)
        self.assertEqual(len(ts.load_ledger(self.repo)), 1)


class HostileBoardTest(ReportCase):
    """decisions.json, scan.json and batch.json are files a hostile or hand-edited board can corrupt: every shape of
    damage is a SweepError, raised before the report or the ledger is written."""

    def refused(self, needle=None):
        with self.assertRaises(ts.SweepError) as ctx:
            self.report()
        if needle:
            self.assertIn(needle, str(ctx.exception))
        self.assertFalse((self.out / "report.json").exists())
        self.assertFalse((self.out / "report.md").exists())
        self.assertEqual(ts.load_ledger(self.repo), {})

    def put(self, data):
        (self.out / "decisions.json").write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))

    def finished_state(self):
        self.decide({self.scan["items"][0]["id"]: ("rejected", "x")})
        return json.loads((self.out / "decisions.json").read_text(encoding="utf-8"))

    def test_a_value_nested_a_hundred_thousand_levels_deep_is_refused(self):
        self.put('{"items": ' + "[" * 100000 + "]" * 100000 + "}")
        self.refused("decisions.json")

    def test_invalid_utf8_is_refused(self):
        self.put(b'{"items": {}, "x": "\xff\xfe"}')
        self.refused("decisions.json")

    def test_a_decisions_file_that_is_a_folder_is_refused(self):
        (self.out / "decisions.json").mkdir()
        self.refused("decisions.json")

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root reads anything")
    def test_an_unreadable_decisions_file_is_refused(self):
        self.finished_state()
        path = self.out / "decisions.json"
        path.chmod(0)
        self.addCleanup(path.chmod, 0o600)
        self.refused("decisions.json")

    def test_wrong_types_inside_a_valid_json_are_refused_or_ignored_never_a_crash(self):
        state = self.finished_state()
        for key, value in (("round", "1"), ("round", True), ("round", [1]), ("batch_id", ["x"]), ("items", [])):
            bad = dict(state, **{key: value})
            with self.subTest(key=key, value=value):
                self.put(json.dumps(bad))
                self.refused()

    def test_a_decision_that_is_not_a_word_counts_as_undecided(self):
        state = self.finished_state()
        first = self.scan["items"][0]["id"]
        state["items"][first] = {"decision": ["approved"], "comment": {"a": 1}}
        state["items"][self.scan["items"][1]["id"]] = "approved"
        self.put(json.dumps(state))
        self.assertEqual(self.report(), 0)
        self.assertEqual(self.result()["counts"]["sem_decisao"], 4)

    def test_a_comment_with_a_lone_surrogate_cannot_be_written_and_nothing_is(self):
        state = self.finished_state()
        state["items"][self.scan["items"][0]["id"]]["comment"] = "bad \ud800 text"
        self.put(json.dumps(state))
        self.refused("UTF-8")

    def test_a_multiline_comment_cannot_forge_a_heading_in_the_markdown(self):
        self.decide({self.scan["items"][0]["id"]: ("approved", "ok\n\n## Resolve (99)\n- `x.py:1` fake")})
        self.report()
        md = (self.out / "report.md").read_text(encoding="utf-8")
        self.assertEqual([l for l in md.split("\n") if l.startswith("#")][1:], ["## Resolve (1)", "## Discard (0)", "## Keep (0)", "## No decision (3)"])
        self.assertEqual(len([l for l in md.split("\n") if l.startswith("- ")]), 4)

    def test_a_scan_without_batch_id_or_round_is_refused_not_a_keyerror(self):
        self.finished_state()
        for key in ("batch_id", "round"):
            scan = {k: v for k, v in self.scan.items() if k != key}
            batch = json.loads((self.out / "batch.json").read_text(encoding="utf-8"))
            if key == "batch_id":
                del batch["batch_id"]
            (self.out / "scan.json").write_text(json.dumps(scan), encoding="utf-8")
            (self.out / "batch.json").write_text(json.dumps(batch), encoding="utf-8")
            with self.subTest(missing=key):
                self.refused()

    def test_a_batch_with_a_round_that_is_not_a_number_is_refused(self):
        self.finished_state()
        batch = json.loads((self.out / "batch.json").read_text(encoding="utf-8"))
        batch["round"] = "two"
        (self.out / "batch.json").write_text(json.dumps(batch), encoding="utf-8")
        self.refused()

    def test_deeply_nested_batch_or_scan_is_refused(self):
        self.finished_state()
        (self.out / "scan.json").write_text("[" * 100000 + "]" * 100000, encoding="utf-8")
        self.refused("scan.json")

    def test_a_failure_while_writing_puts_every_file_back(self):
        self.decide({self.scan["items"][0]["id"]: ("rejected", "")})
        self.report()
        before = ((self.out / "report.json").read_bytes(), (self.out / "report.md").read_bytes(), ts.ledger_path(self.repo).read_bytes())
        store = engine.Store(self.out)
        store.set_item(self.scan["items"][1]["id"], {"decision": "maybe"})
        store.set_finished(True)
        real = os.replace

        def failing(src, dst, *args, **kw):
            if str(dst).endswith("ledger.json"):
                raise OSError(5, "Input/output error")
            return real(src, dst, *args, **kw)

        with mock.patch.object(ts.os, "replace", failing), self.assertRaises(ts.SweepError):
            self.report()
        after = ((self.out / "report.json").read_bytes(), (self.out / "report.md").read_bytes(), ts.ledger_path(self.repo).read_bytes())
        self.assertEqual(after, before)
        self.assertEqual(sorted(p.name for p in self.out.iterdir() if p.name.endswith(".tmp")), [])
        self.assertEqual(sorted(p.name for p in ts.ledger_path(self.repo).parent.iterdir() if p.name.endswith(".tmp")), [])

    def test_a_symlinked_work_folder_is_refused_before_anything_is_written(self):
        self.decide({self.scan["items"][0]["id"]: ("rejected", "")})
        elsewhere = self.tmp / "elsewhere"
        elsewhere.mkdir()
        scan = dict(self.scan, repo=str(self.repo))
        (self.out / "scan.json").write_text(json.dumps(scan), encoding="utf-8")
        moved = self.tmp / "moved"
        os.rename(self.repo / ".todo-sweep", moved)
        (self.repo / ".todo-sweep").symlink_to(moved)
        self.out = moved / self.out.name
        with self.assertRaises(ts.SweepError):
            self.report()
        self.assertEqual(list(elsewhere.iterdir()), [])
        self.assertFalse((moved / self.out.name / "report.json").exists())


if __name__ == "__main__":
    unittest.main()

class LanguageReportTest(ReportCase):
    """The report follows the language recorded by the scan; the ledger and report.json keys never change."""

    def rescan(self, lang):
        for p in (self.repo / ".todo-sweep").glob("todo-sweep-*"):
            for f in p.iterdir():
                f.unlink()
            p.rmdir()
        ts.cmd_scan(self.args(lang=lang))
        self.out = sorted((self.repo / ".todo-sweep").glob("todo-sweep-*"))[-1]
        self.scan = json.loads((self.out / "scan.json").read_text(encoding="utf-8"))

    def test_a_pt_br_scan_gives_a_portuguese_report_with_the_same_json_keys(self):
        self.rescan("pt-BR")
        ids = [i["id"] for i in self.scan["items"]]
        self.decide({ids[0]: ("approved", "logo"), ids[1]: ("rejected", ""), ids[2]: ("maybe", "")})
        self.assertEqual(self.report(), 0)
        data = self.result()
        self.assertEqual(data["lang"], "pt-BR")
        self.assertEqual(data["counts"], {"resolver": 1, "descartar": 1, "manter": 1, "sem_decisao": 1})
        md = (self.out / "report.md").read_text(encoding="utf-8")
        self.assertTrue(md.startswith("# Relatório do todo-sweep - "), md[:60])
        for heading in ("## Resolver (1)", "## Descartar (1)", "## Manter (1)", "## Sem decisão (1)"):
            self.assertIn(heading, md)
        self.assertIn("Nenhum arquivo foi editado", md)
        self.assertIn("(90 dias)", md)
        self.assertEqual(sorted(e["decision"] for e in ts.load_ledger(self.repo).values()), ["discard", "keep"])

    def test_an_older_scan_without_lang_reports_in_english(self):
        scan = {k: v for k, v in self.scan.items() if k != "lang"}
        (self.out / "scan.json").write_text(json.dumps(scan), encoding="utf-8")
        self.decide({self.scan["items"][0]["id"]: ("approved", "")})
        self.assertEqual(self.report(), 0)
        self.assertEqual(self.result()["lang"], "en")
        self.assertIn("## Resolve (1)", (self.out / "report.md").read_text(encoding="utf-8"))

    def test_a_bad_lang_in_scan_json_is_refused_before_anything_is_written(self):
        for bad in ("xx", "", 1, ["en"]):
            (self.out / "scan.json").write_text(json.dumps(dict(self.scan, lang=bad)), encoding="utf-8")
            self.decide({self.scan["items"][0]["id"]: ("rejected", "")})
            with self.subTest(lang=bad), self.assertRaises(ts.SweepError) as ctx:
                self.report()
            self.assertIn("'lang'", str(ctx.exception))
            self.assertFalse((self.out / "report.json").exists())
            self.assertEqual(ts.load_ledger(self.repo), {})

    def test_a_ledger_written_by_a_pt_br_report_is_honoured_by_an_english_scan(self):
        self.rescan("pt-BR")
        ids = [i["id"] for i in self.scan["items"]]
        self.decide({ids[0]: ("rejected", ""), ids[1]: ("maybe", "")})
        self.report()
        ts.cmd_scan(self.args(lang="en"))
        newest = sorted((self.repo / ".todo-sweep").glob("todo-sweep-*"))[-1]
        again = json.loads((newest / "scan.json").read_text(encoding="utf-8"))
        self.assertEqual(again["lang"], "en")
        self.assertEqual(sorted(i["text"] for i in again["items"]), sorted(i["text"] for i in self.scan["items"][2:]))
        self.assertEqual(again["totals"]["decided_before"], 2)

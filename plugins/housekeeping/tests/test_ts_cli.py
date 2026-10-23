import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import TODO_SWEEP, commit, init_repo, load_engine, load_todo_sweep

ts = load_todo_sweep()
engine = load_engine()


def run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = ts.main(argv)
    return rc, out.getvalue(), err.getvalue()


class CliCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        self.repo = init_repo(self.tmp / "r")
        commit(self.repo, "c", {"a.py": "# TODO: first\n# FIXME: second\n", "b.py": "x = 1  # TODO: third\n"})


class FlowTest(CliCase):
    def test_scan_check_decide_report_end_to_end_with_the_real_engine(self):
        rc, out, _ = run_main(["scan", str(self.repo), "--limit", "2"])
        self.assertEqual(rc, 0, out)
        self.assertIn("3 TODO/FIXME achados", out)
        self.assertIn("mostrando 2", out)
        folder = Path(out.split("lote: ")[1].strip())
        self.assertEqual(engine.validate(json.loads((folder / "batch.json").read_text(encoding="utf-8"))), [])
        self.assertEqual(run_main(["check", str(folder)])[0], 0)
        store = engine.Store(folder)
        store.set_item("T01", {"decision": "rejected"})
        store.set_item("T02", {"decision": "approved", "comment": "next sprint"})
        store.set_finished(True)
        rc, out, _ = run_main(["report", str(folder)])
        self.assertEqual(rc, 0, out)
        self.assertIn("REPORT: 1 resolver, 1 descartar, 0 manter, 0 sem decisao", out)
        rc, out, _ = run_main(["scan", str(self.repo)])
        self.assertIn("2 novos", out.replace("1 ja decididos, ", ""))  # one was remembered, two are still open

    def test_scan_when_nothing_is_left_exits_zero_and_says_so(self):
        run_main(["scan", str(self.repo)])
        store = engine.Store(sorted((self.repo / ".todo-sweep").glob("todo-sweep-*"))[-1])
        for item_id in ("T01", "T02", "T03"):
            store.set_item(item_id, {"decision": "maybe"})
        store.set_finished(True)
        run_main(["report", str(sorted((self.repo / ".todo-sweep").glob("todo-sweep-*"))[-1])])
        rc, out, _ = run_main(["scan", str(self.repo)])
        self.assertEqual(rc, 0)
        self.assertIn("nada novo para mostrar", out)


class ErrorTest(CliCase):
    def test_bad_numbers_exit_two(self):
        self.assertEqual(run_main(["scan", str(self.repo), "--limit", "0"])[0], 2)
        self.assertEqual(run_main(["scan", str(self.repo), "--max-blame", "-1"])[0], 2)

    def test_bad_counts_are_refused_in_portuguese_with_exit_two_and_nothing_written(self):
        for flag, value in (("--limit", "0"), ("--limit", "-5"), ("--limit", "abc"), ("--limit", "2.5"),
                            ("--max-blame", "0"), ("--max-blame", "-1"), ("--max-blame", "x")):
            with self.subTest(flag=flag, value=value):
                rc, out, err = run_main(["scan", str(self.repo), flag, value])
                self.assertEqual((rc, out), (2, ""))
                self.assertIn("erro:", err)
                self.assertIn(flag, err)
                self.assertNotIn("Traceback", err)
        self.assertFalse((self.repo / ".todo-sweep").exists())

    def test_cmd_scan_itself_refuses_a_negative_cap_instead_of_slicing_wrongly(self):
        import argparse
        for kw in ({"limit": -1}, {"max_blame": -1}, {"limit": 0}):
            args = argparse.Namespace(**{**dict(repo=str(self.repo), limit=20, max_blame=300, out=None, lang="en"), **kw})
            with self.subTest(kw=kw), self.assertRaises(ts.SweepError):
                ts.cmd_scan(args)
        self.assertFalse((self.repo / ".todo-sweep").exists())

    def test_usage_errors_exit_two_with_an_erro_line(self):
        for argv in (["bogus"], ["scan", "--nope"], ["report"], ["check", "a", "b"]):
            with self.subTest(argv=argv):
                err = io.StringIO()
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as ctx:
                    ts.main(argv)
                self.assertEqual(ctx.exception.code, 2)
                self.assertIn("erro:", err.getvalue())

    def test_a_corrupt_board_through_main_is_an_erro_line_and_exit_two_never_a_traceback(self):
        run_main(["scan", str(self.repo)])
        folder = sorted((self.repo / ".todo-sweep").glob("todo-sweep-*"))[-1]
        for payload in (b'{"items": ' + b"[" * 100000 + b"]" * 100000 + b"}", b"\xff\xfe", b"[]", b""):
            (folder / "decisions.json").write_bytes(payload)
            with self.subTest(payload=payload[:12]):
                rc, out, err = run_main(["report", str(folder)])
                self.assertEqual((rc, out), (2, ""))
                self.assertTrue(err.startswith("erro:"), err)
                self.assertNotIn("Traceback", err)
        self.assertFalse((folder / "report.json").exists())

    def test_an_unexpected_io_failure_is_still_an_erro_line_and_exit_two(self):
        for failure in (OSError(5, "Input/output error"), UnicodeEncodeError("utf-8", "x", 0, 1, "bad"), RecursionError("deep")):
            with self.subTest(failure=type(failure).__name__), mock.patch.object(ts, "cmd_scan", side_effect=failure):
                rc, out, err = run_main(["scan", str(self.repo)])
                self.assertEqual((rc, out), (2, ""))
                self.assertTrue(err.startswith("erro:"), err)

    def test_not_a_repository_and_a_missing_folder_exit_two(self):
        plain = self.tmp / "plain"
        plain.mkdir()
        rc, out, err = run_main(["scan", str(plain)])
        self.assertEqual((rc, out), (2, ""))
        self.assertIn("nao e um repositorio git", err)
        self.assertEqual(run_main(["report", str(self.tmp / "none")])[0], 2)
        self.assertEqual(run_main(["check", str(self.tmp / "none")])[0], 2)

    def test_report_before_the_panel_is_concluded_exits_two(self):
        run_main(["scan", str(self.repo)])
        folder = sorted((self.repo / ".todo-sweep").glob("todo-sweep-*"))[-1]
        rc, _, err = run_main(["report", str(folder)])
        self.assertEqual(rc, 2)
        self.assertIn("decisions.json ausente", err)

    def test_a_command_is_required(self):
        with self.assertRaises(SystemExit) as ctx:
            run_main([])
        self.assertEqual(ctx.exception.code, 2)


class ScriptTest(CliCase):
    def test_the_script_runs_in_isolated_mode_from_any_folder(self):
        r = subprocess.run([sys.executable, "-I", str(TODO_SWEEP), "scan", str(self.repo)], capture_output=True, text=True, cwd=str(self.tmp))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("3 TODO/FIXME achados", r.stdout)

    def test_version_flag(self):
        r = subprocess.run([sys.executable, "-I", str(TODO_SWEEP), "--version"], capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "todo-sweep " + ts.VERSION)


if __name__ == "__main__":
    unittest.main()

class LanguageCliTest(CliCase):
    def test_lang_pt_br_flows_end_to_end_and_the_command_line_stays_portuguese(self):
        rc, out, _ = run_main(["scan", str(self.repo), "--lang", "pt-BR"])
        self.assertEqual(rc, 0, out)
        self.assertIn("3 TODO/FIXME achados", out)
        folder = Path(out.split("lote: ")[1].strip())
        batch = json.loads((folder / "batch.json").read_text(encoding="utf-8"))
        self.assertEqual((batch["lang"], batch["labels"]["approve"]["text"]), ("pt-BR", "Resolver"))
        self.assertEqual(engine.validate(batch), [])
        store = engine.Store(folder)
        store.set_item("T01", {"decision": "approved"})
        store.set_finished(True)
        rc, out, _ = run_main(["report", str(folder)])
        self.assertEqual(rc, 0, out)
        self.assertIn("REPORT: 1 resolver, 0 descartar, 0 manter, 2 sem decisao", out)
        self.assertIn("## Resolver (1)", (folder / "report.md").read_text(encoding="utf-8"))

    def test_an_unknown_lang_is_an_erro_line_with_exit_two_and_nothing_written(self):
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as ctx:
            ts.main(["scan", str(self.repo), "--lang", "xx"])
        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("erro: argumento --lang: comando invalido: 'xx'", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())
        self.assertFalse((self.repo / ".todo-sweep").exists())

    def test_help_documents_the_flag(self):
        r = subprocess.run([sys.executable, "-I", str(TODO_SWEEP), "scan", "--help"], capture_output=True, text=True)
        self.assertIn("--lang {en,pt-BR}", r.stdout)

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
        self.assertIn("SCAN: 3 TODO/FIXME found, 0 already decided, 3 new, 0 without an age", out)
        self.assertIn("showing 2, oldest first", out)
        folder = Path(out.split("batch: ")[1].strip())
        self.assertEqual(engine.validate(json.loads((folder / "batch.json").read_text(encoding="utf-8"))), [])
        self.assertEqual(run_main(["check", str(folder)])[0], 0)
        store = engine.Store(folder)
        store.set_item("T01", {"decision": "rejected"})
        store.set_item("T02", {"decision": "approved", "comment": "next sprint"})
        store.set_finished(True)
        rc, out, _ = run_main(["report", str(folder)])
        self.assertEqual(rc, 0, out)
        self.assertIn("REPORT: 1 resolve, 1 discard, 0 keep, 0 no decision", out)
        self.assertIn("1 decision remembered in ", out)
        rc, out, _ = run_main(["scan", str(self.repo)])
        self.assertIn("1 already decided, 2 new", out)  # one was remembered, two are still open

    def test_scan_when_nothing_is_left_exits_zero_and_says_so(self):
        run_main(["scan", str(self.repo)])
        store = engine.Store(sorted((self.repo / ".todo-sweep").glob("todo-sweep-*"))[-1])
        for item_id in ("T01", "T02", "T03"):
            store.set_item(item_id, {"decision": "maybe"})
        store.set_finished(True)
        run_main(["report", str(sorted((self.repo / ".todo-sweep").glob("todo-sweep-*"))[-1])])
        rc, out, _ = run_main(["scan", str(self.repo)])
        self.assertEqual(rc, 0)
        self.assertIn("nothing new to show", out)


class ErrorTest(CliCase):
    def test_bad_numbers_exit_two(self):
        self.assertEqual(run_main(["scan", str(self.repo), "--limit", "0"])[0], 2)
        self.assertEqual(run_main(["scan", str(self.repo), "--max-blame", "-1"])[0], 2)

    def test_bad_counts_are_refused_with_exit_two_and_nothing_written(self):
        for flag, value in (("--limit", "0"), ("--limit", "-5"), ("--limit", "abc"), ("--limit", "2.5"),
                            ("--max-blame", "0"), ("--max-blame", "-1"), ("--max-blame", "x")):
            with self.subTest(flag=flag, value=value):
                rc, out, err = run_main(["scan", str(self.repo), flag, value])
                self.assertEqual((rc, out), (2, ""))
                self.assertIn("error:", err)
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

    def test_usage_errors_exit_two_with_an_error_line_in_either_language(self):
        for argv in (["bogus"], ["scan", "--nope"], ["report"], ["check", "a", "b"]):
            with self.subTest(argv=argv):
                err = io.StringIO()
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as ctx:
                    ts.main(argv)
                self.assertEqual(ctx.exception.code, 2)
                self.assertIn("error:", err.getvalue())
                err = io.StringIO()
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
                    ts.main(argv + ["--lang", "pt-BR"])
                self.assertIn("erro: ", err.getvalue())  # argparse's words translated, as in 0.3.1

    def test_a_corrupt_board_through_main_is_an_error_line_and_exit_two_never_a_traceback(self):
        run_main(["scan", str(self.repo)])
        folder = sorted((self.repo / ".todo-sweep").glob("todo-sweep-*"))[-1]
        for payload in (b'{"items": ' + b"[" * 100000 + b"]" * 100000 + b"}", b"\xff\xfe", b"[]", b""):
            (folder / "decisions.json").write_bytes(payload)
            with self.subTest(payload=payload[:12]):
                rc, out, err = run_main(["report", str(folder)])
                self.assertEqual((rc, out), (2, ""))
                self.assertTrue(err.startswith("error:"), err)
                self.assertNotIn("Traceback", err)
        self.assertFalse((folder / "report.json").exists())

    def test_an_unexpected_io_failure_is_still_an_error_line_and_exit_two(self):
        for failure in (OSError(5, "Input/output error"), UnicodeEncodeError("utf-8", "x", 0, 1, "bad"), RecursionError("deep")):
            with self.subTest(failure=type(failure).__name__), mock.patch.object(ts, "cmd_scan", side_effect=failure):
                rc, out, err = run_main(["scan", str(self.repo)])
                self.assertEqual((rc, out), (2, ""))
                self.assertTrue(err.startswith("error: unexpected failure ("), err)

    def test_not_a_repository_and_a_missing_folder_exit_two(self):
        plain = self.tmp / "plain"
        plain.mkdir()
        rc, out, err = run_main(["scan", str(plain)])
        self.assertEqual((rc, out), (2, ""))
        self.assertIn("is not a git repository", err)
        self.assertEqual(run_main(["report", str(self.tmp / "none")])[0], 2)
        self.assertEqual(run_main(["check", str(self.tmp / "none")])[0], 2)

    def test_report_before_the_panel_is_concluded_exits_two(self):
        run_main(["scan", str(self.repo)])
        folder = sorted((self.repo / ".todo-sweep").glob("todo-sweep-*"))[-1]
        rc, _, err = run_main(["report", str(folder)])
        self.assertEqual(rc, 2)
        self.assertIn("decisions.json missing or unreadable", err)

    def test_a_command_is_required(self):
        with self.assertRaises(SystemExit) as ctx:
            run_main([])
        self.assertEqual(ctx.exception.code, 2)


class ScriptTest(CliCase):
    def test_the_script_runs_in_isolated_mode_from_any_folder(self):
        r = subprocess.run([sys.executable, "-I", str(TODO_SWEEP), "scan", str(self.repo)], capture_output=True, text=True, cwd=str(self.tmp))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("3 TODO/FIXME found", r.stdout)

    def test_version_flag(self):
        r = subprocess.run([sys.executable, "-I", str(TODO_SWEEP), "--version"], capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "todo-sweep " + ts.VERSION)


if __name__ == "__main__":
    unittest.main()

class LanguageCliTest(CliCase):
    def test_lang_pt_br_flows_end_to_end_and_the_command_line_follows_it(self):
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
        self.assertIn("REPORT: 1 resolver, 0 descartar, 0 manter, 2 sem decisao", out)  # report reads the scan's language
        self.assertIn("0 decisoes lembradas em ", out)
        self.assertIn("## Resolver (1)", (folder / "report.md").read_text(encoding="utf-8"))

    def test_an_unknown_lang_is_an_error_line_with_exit_two_and_nothing_written(self):
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as ctx:
            ts.main(["scan", str(self.repo), "--lang", "xx"])
        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("error: argument --lang: invalid choice: 'xx'", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())
        self.assertFalse((self.repo / ".todo-sweep").exists())

    def test_help_documents_the_flag(self):
        r = subprocess.run([sys.executable, "-I", str(TODO_SWEEP), "scan", "--help"], capture_output=True, text=True)
        self.assertIn("--lang {en,pt-BR}", r.stdout)


# ---------------------------------------------------------------- the command line's language (housekeeping 0.4.0)

import ast as _ast
import os as _os
import re as _re

_PLACEHOLDER = _re.compile(r"\{(\w+)\}")
TS_PRINTING = ("git", "repo_root", "stage_private", "write_all", "scan_files", "work_dir", "load_ledger", "save_ledger",
               "check_lang", "make_folder", "refuse_old_decisions", "check_counts", "cmd_scan", "load_dir", "scan_problems",
               "cmd_check", "read_decisions", "trusted_repo", "cmd_report", "parser", "main")
TS_PT_WORDS = {"nao", "encontrado", "repositorio", "conteudo", "cabem", "nada", "gravado", "consegui", "gravar", "link",
               "simbolico", "recuso", "ilegivel", "corrija", "apague", "arquivo", "formato", "invalido", "criar", "pasta",
               "idioma", "ler", "ja", "tem", "lote", "anterior", "escolha", "outra", "decisoes", "deve", "numero", "inteiro",
               "recebi", "achados", "decididos", "novo", "novos", "mostrar", "sem", "idade", "aviso", "raso", "limite",
               "historico", "resolve", "primeiros", "medidos", "suba", "medir", "mostrando", "antigo", "ausente", "rode",
               "itens", "coincidem", "lotes", "diferentes", "problema", "suba", "painel", "conclua", "outro", "rodada",
               "concluido", "clique", "caminho", "absoluto", "existe", "raiz", "guardado", "invalidos", "resolver",
               "descartar", "manter", "decisao", "relatorio", "lembradas", "proximo", "oferece", "proximos", "erro",
               "falha", "inesperada", "acha", "escreve", "padrao", "quantos", "valida", "grava", "partir"}


class CommandLineTableTest(unittest.TestCase):
    def test_both_tables_have_the_same_keys_and_placeholders_and_are_plain_ascii(self):
        en, pt = ts.MSG["en"], ts.MSG["pt-BR"]
        self.assertEqual(set(en), set(pt))
        for key in en:
            with self.subTest(key=key):
                self.assertEqual(set(_PLACEHOLDER.findall(en[key])), set(_PLACEHOLDER.findall(pt[key])))
                self.assertTrue(en[key].isascii() and pt[key].isascii(), key)
        self.assertEqual(ts.MSG["pt-BR"]["report"], "REPORT: {resolve} resolver, {discard} descartar, {keep} manter, {none} sem decisao")

    def test_no_portuguese_literal_is_left_in_the_functions_that_print(self):
        tree = _ast.parse(TODO_SWEEP.read_text(encoding="utf-8"))
        found = []
        for fn in (n for n in _ast.walk(tree) if isinstance(n, _ast.FunctionDef) and n.name in TS_PRINTING):
            body = fn.body[1:] if isinstance(fn.body[0], _ast.Expr) and isinstance(fn.body[0].value, _ast.Constant) else fn.body
            for node in (n for stmt in body for n in _ast.walk(stmt)):
                if isinstance(node, _ast.Constant) and isinstance(node.value, str) and node.value not in {key for key, _text in ts.SECTIONS}:  # JSON keys are data
                    if set(_re.split(r"[^a-z]+", node.value.lower())) & TS_PT_WORDS:
                        found.append(f"{fn.name}: {node.value!r}")
        self.assertEqual(found, [], "Portuguese left outside MSG:\n" + "\n".join(found))


class CommandLineLanguageTest(CliCase):
    def scan(self, *extra, env=None):
        with mock.patch.dict(_os.environ, env or {}):
            rc, out, err = run_main(["scan", str(self.repo), *extra])
        self.assertEqual(rc, 0, err)
        return Path(out.split("batch: " if "batch: " in out else "lote: ")[1].strip()), out

    def test_capybara_lang_is_the_default_for_scan_and_the_flag_wins(self):
        folder, out = self.scan(env={"CAPYBARA_LANG": "pt-BR"})
        self.assertIn("SCAN: 3 TODO/FIXME achados, 0 ja decididos, 3 novos, 0 sem idade", out)
        self.assertEqual(json.loads((folder / "batch.json").read_text(encoding="utf-8"))["lang"], "pt-BR")
        _folder, out = self.scan("--out", str(self.tmp / "b2"), "--lang", "en", env={"CAPYBARA_LANG": "pt-BR"})
        self.assertIn("SCAN: 3 TODO/FIXME found", out)
        _folder, out = self.scan("--out", str(self.tmp / "b3"), env={"CAPYBARA_LANG": "portuguese"})
        self.assertIn("SCAN: 3 TODO/FIXME found", out)  # a bad value is ignored
        self.assertEqual(ts.CLI_LANG, "en")  # main() put the default back

    def test_check_and_report_speak_the_scans_language_even_in_their_errors(self):
        folder, _ = self.scan("--lang", "pt-BR")
        rc, out, _ = run_main(["check", str(folder)])
        self.assertEqual((rc, out), (0, "ok: 3 itens, lote %s\n" % folder.name))
        rc, _, err = run_main(["report", str(folder)])
        self.assertEqual(rc, 2)
        self.assertTrue(err.startswith("erro: decisions.json ausente ou ilegivel"), err)
        self.assertEqual(run_main(["check", str(folder), "--lang", "en"])[1], "ok: 3 items, batch %s\n" % folder.name)

    def test_report_lang_chooses_the_report_and_records_it(self):
        folder, _ = self.scan("--lang", "pt-BR")
        store = engine.Store(folder)
        store.set_item("T01", {"decision": "maybe"})
        store.set_finished(True)
        rc, out, _ = run_main(["report", str(folder), "--lang", "en"])
        self.assertEqual(rc, 0, out)
        self.assertIn("REPORT: 0 resolve, 0 discard, 1 keep, 2 no decision", out)
        self.assertIn("1 decision remembered in ", out)
        self.assertIn("## Keep (1)", (folder / "report.md").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((folder / "report.json").read_text(encoding="utf-8"))["lang"], "en")

    def test_one_takes_the_singular_form_in_pt_br(self):
        commit(self.repo, "only one", {"a.py": "x = 1\n", "b.py": "# TODO: only\n"})
        _folder, out = self.scan("--lang", "pt-BR")
        self.assertIn("SCAN: 1 TODO/FIXME achado, 0 ja decididos, 1 novo, 0 sem idade", out)

    def test_every_command_takes_lang(self):
        for argv in (["scan"], ["check", "d"], ["report", "d"]):
            with self.subTest(cmd=argv[0]):
                self.assertEqual(ts.parser().parse_args(argv + ["--lang", "pt-BR"]).lang, "pt-BR")
                self.assertIsNone(ts.parser().parse_args(argv).lang)

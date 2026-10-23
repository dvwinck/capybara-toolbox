import ast
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from unittest import mock

from helpers import SCRIPT, ab, make_batch

PLACEHOLDER = re.compile(r"\{(\w+)\}")
CLI_FUNCTIONS = ("validate_question", "validate_labels", "validate", "load_batch", "answer_text", "render_summary",
                 "cmd_serve", "cmd_wait", "cmd_summary", "cmd_build", "cmd_check", "main")
PT_WORDS = {  # words of the old command-line output: any of them in a literal of those functions is a leftover
    "nao", "deve", "obrigatorio", "itens", "lote", "rodada", "perguntas", "aviso", "erro", "encontrei", "consegui",
    "invalido", "valido", "porta", "usuario", "concluiu", "resposta", "comentario", "outra", "concluido", "aprovados",
    "rejeitados", "talvez", "respondidas", "precisam", "decisao", "nota", "geral", "sim", "parcial", "recomendada",
    "painel", "aprovar", "rejeitar", "somente", "chave", "desconhecida", "objeto", "booleano", "inteiro", "opcoes",
    "combina", "casar", "duplicado", "cita", "repetido", "limite", "pergunta", "contexto", "texto", "vazio", "raiz",
}


def board(**extra):
    b = {"batch_id": "t", "title": "T", "items": [{"id": "A01", "title": "x"}]}
    b.update(extra)
    return b


def run(*args, env=None):
    return subprocess.run([sys.executable, "-I", str(SCRIPT), *args], capture_output=True, text=True,
                          env={**os.environ, **(env or {})})


def literals(fn):
    """Every string literal inside a function, docstring left out."""
    body = fn.body[1:] if fn.body and isinstance(fn.body[0], ast.Expr) and isinstance(fn.body[0].value, ast.Constant) else fn.body
    return [n.value for stmt in body for n in ast.walk(stmt) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


class MessageTableTest(unittest.TestCase):
    def test_both_languages_have_the_same_keys_and_placeholders(self):
        self.assertEqual(set(ab.MSG), set(ab.LANGS))
        en, pt = ab.MSG["en"], ab.MSG["pt-BR"]
        self.assertEqual(set(en), set(pt))
        for key in en:
            with self.subTest(key=key):
                self.assertEqual(set(PLACEHOLDER.findall(en[key])), set(PLACEHOLDER.findall(pt[key])))
                if key.endswith("_1"):
                    self.assertIn(key[:-2], en)  # a singular form always has its plural

    def test_the_command_line_text_is_plain_ascii_in_both_languages(self):
        for lang, table in ab.MSG.items():  # pt-BR stays accent-free, as the command line always was
            for key, value in table.items():
                with self.subTest(lang=lang, key=key):
                    self.assertTrue(value.isascii(), value)

    def test_the_pt_br_side_is_the_old_output(self):
        pt = ab.MSG["pt-BR"]
        self.assertEqual(pt["invalid"], "batch.json invalido:")
        self.assertEqual(pt["ok"], "ok: {n} itens, lote {id}, rodada {round}")
        self.assertEqual(pt["timeout"], "TIMEOUT: o usuario ainda nao concluiu o lote.")
        self.assertEqual(pt["item_title"], "item {i}: 'title' obrigatorio")

    def test_no_portuguese_literal_is_left_in_the_functions_that_print(self):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        found = []
        for fn in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in CLI_FUNCTIONS):
            for text in literals(fn):
                words = set(re.split(r"[^a-z]+", text.lower()))
                if words & PT_WORDS:
                    found.append(f"{fn.name}: {text!r}")
        self.assertEqual(found, [], "Portuguese left outside MSG:\n" + "\n".join(found))

    def test_one_takes_the_singular_form(self):
        self.assertEqual(ab.say("en", "ok", n=1, id="t", round=1), "ok: 1 item, batch t, round 1")
        self.assertEqual(ab.say("en", "ok", n=2, id="t", round=1), "ok: 2 items, batch t, round 1")
        self.assertEqual(ab.say("pt-BR", "ok", n=1, id="t", round=1), "ok: 1 item, lote t, rodada 1")
        self.assertEqual(ab.say("pt-BR", "ok", n=0, id="t", round=1), "ok: 0 itens, lote t, rodada 1")


class ResolveWithTheEnvironmentTest(unittest.TestCase):
    def test_capybara_lang_comes_after_the_flag_and_the_batch(self):
        with mock.patch.dict(os.environ, {"CAPYBARA_LANG": "pt-BR"}):
            self.assertEqual(ab.resolve_lang(board()), "pt-BR")
            self.assertEqual(ab.resolve_lang(board(lang="en")), "en")
            self.assertEqual(ab.resolve_lang(board(), "en"), "en")
            self.assertEqual(ab.resolve_lang(None), "pt-BR")  # no batch read yet (a missing or broken batch.json)

    def test_a_bad_capybara_lang_is_ignored_and_never_an_error(self):
        for bad in ("pt", "PT-BR", "pt_BR", "", "xx"):
            with self.subTest(env=bad), mock.patch.dict(os.environ, {"CAPYBARA_LANG": bad}):
                self.assertEqual(ab.resolve_lang(board()), "en")
                self.assertIsNone(ab.env_lang())


class ValidateAndSummaryLanguageTest(unittest.TestCase):
    STATE = {"round": 1, "finished": True, "batch_note": "n", "items": {"A01": {"decision": "approved", "comment": "ok"}}}

    def test_validate_speaks_english_by_default_and_pt_br_on_request(self):
        self.assertEqual(ab.validate(board(items=[{"id": "A01"}])), ["item 0: 'title' is required"])
        self.assertEqual(ab.validate(board(items=[{"id": "A01"}]), "pt-BR"), ["item 0: 'title' obrigatorio"])

    def test_the_text_summary_in_both_languages(self):
        out = ab.render_summary(board(), self.STATE)
        for line in ("# AR board - T (batch t, round 1)", "Finished by the user: yes", "## Approved (1)",
                     "    user comment: 'ok'", "## No decision (0)", "## General note on the batch\nn"):
            self.assertIn(line, out)
        out = ab.render_summary(board(), self.STATE, lang="pt-BR")
        for line in ("# AR board - T (lote t, rodada 1)", "Concluido pelo usuario: sim", "## Aprovados (1)",
                     "    comentario do usuario: 'ok'", "## Sem decisao (0)", "## Nota geral do lote\nn"):
            self.assertIn(line, out)

    def test_the_json_summary_carries_no_language(self):
        a = json.loads(ab.render_summary(board(), self.STATE, as_json=True))
        b = json.loads(ab.render_summary(board(), self.STATE, as_json=True, lang="pt-BR"))
        self.assertEqual(a, b)
        self.assertNotIn("lang", a)


class CommandLineLanguageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_check_follows_flag_then_batch_then_environment_then_english(self):
        d = make_batch(self.tmp.name)
        self.assertEqual(run("check", str(d)).stdout, "ok: 2 items, batch t, round 1\n")
        self.assertEqual(run("check", str(d), "--lang", "pt-BR").stdout, "ok: 2 itens, lote t, rodada 1\n")
        self.assertEqual(run("check", str(d), env={"CAPYBARA_LANG": "pt-BR"}).stdout, "ok: 2 itens, lote t, rodada 1\n")
        d = make_batch(self.tmp.name, lang="pt-BR")
        self.assertEqual(run("check", str(d)).stdout, "ok: 2 itens, lote t, rodada 1\n")
        self.assertEqual(run("check", str(d), "--lang", "en").stdout, "ok: 2 items, batch t, round 1\n")

    def test_a_bad_capybara_lang_falls_back_to_english_without_a_warning(self):
        d = make_batch(self.tmp.name)
        r = run("check", str(d), env={"CAPYBARA_LANG": "pt"})
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "ok: 2 items, batch t, round 1\n", ""))

    def test_a_broken_batch_is_reported_in_the_language_of_the_run(self):
        d = make_batch(self.tmp.name, lang="xx", items=[{"id": "A01"}])
        r = run("check", str(d))
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stderr, "invalid batch.json:\n- field 'lang' must be en or pt-BR\n- item 0: 'title' is required\n")
        r = run("check", str(d), "--lang", "pt-BR")
        self.assertEqual(r.stderr, "batch.json invalido:\n- campo 'lang' deve ser en ou pt-BR\n- item 0: 'title' obrigatorio\n")
        self.assertIn("could not find", run("check", os.path.join(self.tmp.name, "nope")).stderr)
        self.assertIn("nao encontrei", run("check", os.path.join(self.tmp.name, "nope"), "--lang", "pt-BR").stderr)

    def test_summary_and_wait_in_both_languages(self):
        d = make_batch(self.tmp.name)
        self.assertIn("## No decision (2)", run("summary", str(d)).stdout)
        self.assertIn("## Sem decisao (2)", run("summary", str(d), "--lang", "pt-BR").stdout)
        r = run("wait", str(d), "--timeout", "1", "--lang", "pt-BR")
        self.assertEqual((r.returncode, r.stdout), (2, "TIMEOUT: o usuario ainda nao concluiu o lote.\n"))
        r = run("wait", str(d), "--timeout", "1")
        self.assertEqual((r.returncode, r.stdout), (2, "TIMEOUT: the user has not finished the batch yet.\n"))

    def test_the_line_tags_are_the_same_in_both_languages(self):
        d = make_batch(self.tmp.name)
        for lang in ("en", "pt-BR"):
            with self.subTest(lang=lang):
                self.assertTrue(run("build", str(d), "--lang", lang).stdout.startswith("AR-BOARD ARQUIVO: "))

    def test_every_command_takes_lang_and_refuses_a_bad_one(self):
        d = make_batch(self.tmp.name)
        for cmd in ("serve", "wait", "summary", "build", "check"):
            with self.subTest(cmd=cmd):
                self.assertIn("--lang {en,pt-BR}", run(cmd, "--help").stdout)
                r = run(cmd, str(d), "--lang", "xx")
                self.assertEqual(r.returncode, 2)
                self.assertIn("invalid choice: 'xx'", r.stderr)

    def test_a_namespace_without_lang_still_works(self):
        d = make_batch(self.tmp.name)  # callers that build the namespace by hand (the older tests) give no lang
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(ab.cmd_check(Namespace(dir=str(d))), 0)
        self.assertEqual(out.getvalue(), "ok: 2 items, batch t, round 1\n")


if __name__ == "__main__":
    unittest.main()

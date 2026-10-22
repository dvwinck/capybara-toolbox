import contextlib
import io
import json
import re
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from argparse import Namespace
from http.server import ThreadingHTTPServer
from pathlib import Path

from helpers import REPO, SCRIPT, ab, make_batch

PLACEHOLDER = re.compile(r"\{(\w+)\}")


def board(**extra):
    b = {"batch_id": "t", "title": "T", "items": [{"id": "A01", "title": "x"}]}
    b.update(extra)
    return b


def boot_of(page):
    """The BOOT object the page starts from (the JSON the server injects)."""
    return json.loads(re.search(r"const BOOT = (\{.*?\});\n", page).group(1))


class TableTest(unittest.TestCase):
    def test_both_languages_are_shipped_and_english_is_the_default(self):
        self.assertEqual(ab.LANGS, ("en", "pt-BR"))
        self.assertEqual(ab.DEFAULT_LANG, "en")
        self.assertEqual(set(ab.I18N), set(ab.LANGS))

    def test_the_two_tables_have_the_same_keys_and_the_same_placeholders(self):
        en, pt = ab.I18N["en"], ab.I18N["pt-BR"]
        self.assertEqual(set(en), set(pt))
        for key in en:
            with self.subTest(key=key):
                self.assertEqual(set(PLACEHOLDER.findall(en[key])), set(PLACEHOLDER.findall(pt[key])))

    def test_every_value_is_plain_non_empty_text(self):
        for lang, table in ab.I18N.items():
            for key, value in table.items():
                with self.subTest(lang=lang, key=key):
                    self.assertIsInstance(value, str)
                    self.assertTrue(value.strip())
                    for ch in "<>&":
                        self.assertNotIn(ch, value)  # values reach innerHTML unescaped

    def test_the_portuguese_table_is_written_with_accents(self):
        text = " ".join(ab.I18N["pt-BR"].values())
        for word in ("decisão", "Comentário", "opção", "Concluído"):
            self.assertIn(word, text)
        self.assertNotIn("decisao", text)


class ValidateLangTest(unittest.TestCase):
    def test_the_two_languages_and_null_are_accepted(self):
        for value in ("en", "pt-BR", None):
            with self.subTest(lang=value):
                self.assertEqual(ab.validate(board(lang=value)), [])
        self.assertEqual(ab.validate(board()), [])

    def test_any_other_value_or_a_non_string_is_rejected(self):
        for bad in ("pt", "EN", "en-US", "", " en", 1, True, ["en"], {"en": 1}):
            with self.subTest(lang=bad):
                errs = ab.validate(board(lang=bad))
                self.assertEqual(errs, ["campo 'lang' deve ser en ou pt-BR"])

    def test_a_lang_error_does_not_hide_item_errors(self):
        errs = ab.validate(board(lang="xx", items=[{"id": "A01"}]))
        self.assertTrue(any("'lang'" in e for e in errs), errs)
        self.assertTrue(any("'title' obrigatorio" in e for e in errs), errs)

    def test_every_shipped_example_batch_still_validates(self):
        examples = sorted((REPO / "plugins").glob("*/skills/*/examples/batch.example.json"))
        self.assertGreaterEqual(len(examples), 4)
        for path in examples:
            with self.subTest(example=str(path.relative_to(REPO))):
                self.assertEqual(ab.validate(json.loads(path.read_text(encoding="utf-8"))), [])


class ResolveLangTest(unittest.TestCase):
    def test_a_batch_without_lang_opens_in_english(self):
        self.assertEqual(ab.resolve_lang(board()), "en")
        self.assertEqual(ab.resolve_lang(board(lang=None)), "en")

    def test_the_batch_lang_is_used(self):
        self.assertEqual(ab.resolve_lang(board(lang="pt-BR")), "pt-BR")

    def test_the_flag_wins_over_the_batch(self):
        self.assertEqual(ab.resolve_lang(board(lang="pt-BR"), "en"), "en")
        self.assertEqual(ab.resolve_lang(board(), "pt-BR"), "pt-BR")

    def test_an_unknown_value_falls_back_to_english_instead_of_breaking_the_page(self):
        self.assertEqual(ab.resolve_lang(board(lang="xx")), "en")
        self.assertEqual(ab.resolve_lang(board(lang=["pt-BR"]), None), "en")
        self.assertEqual(ab.resolve_lang(board(lang="pt-BR"), "xx"), "pt-BR")


class BootDataTest(unittest.TestCase):
    def test_the_page_receives_both_tables_and_the_resolved_language(self):
        boot = boot_of(ab.render_page(board(), {"items": {}}, "tok", True).decode("utf-8"))
        self.assertEqual(boot["lang"], "en")
        self.assertEqual(boot["i18n"], ab.I18N)

    def test_the_batch_lang_and_the_flag_reach_the_page(self):
        page = ab.render_page(board(lang="pt-BR"), {"items": {}}, "tok", True).decode("utf-8")
        self.assertEqual(boot_of(page)["lang"], "pt-BR")
        page = ab.render_page(board(lang="pt-BR"), {"items": {}}, "tok", True, "en").decode("utf-8")
        self.assertEqual(boot_of(page)["lang"], "en")

    def test_the_offline_page_carries_the_tables_too(self):
        page = ab.render_page(board(lang="pt-BR"), {"items": {}}, "", False).decode("utf-8")
        boot = boot_of(page)
        self.assertEqual((boot["live"], boot["lang"]), (False, "pt-BR"))
        self.assertIn("Concluído", page)
        self.assertIn("Finished.", page)


class CommandLineTest(unittest.TestCase):
    def test_build_takes_lang_and_the_batch_lang_is_the_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = make_batch(tmp, lang="pt-BR")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ab.cmd_build(Namespace(dir=str(d), lang=None)), 0)
            self.assertEqual(boot_of((d / "board.html").read_text(encoding="utf-8"))["lang"], "pt-BR")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ab.cmd_build(Namespace(dir=str(d), lang="en")), 0)
            self.assertEqual(boot_of((d / "board.html").read_text(encoding="utf-8"))["lang"], "en")

    def test_serve_passes_its_lang_to_the_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = make_batch(tmp)
            srv = ThreadingHTTPServer(("127.0.0.1", 0), ab.make_handler(ab.Store(d), "tok", "pt-BR"))
            thread = threading.Thread(target=srv.serve_forever, daemon=True)
            thread.start()
            try:
                with urllib.request.urlopen("http://127.0.0.1:%d/?t=tok" % srv.server_address[1], timeout=5) as r:
                    page = r.read().decode("utf-8")
            finally:
                srv.shutdown()
                srv.server_close()
            self.assertEqual(boot_of(page)["lang"], "pt-BR")

    def test_check_rejects_a_bad_lang_with_exit_code_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = make_batch(tmp, lang="xx")
            r = subprocess.run([sys.executable, "-I", str(SCRIPT), "check", str(d)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("campo 'lang' deve ser en ou pt-BR", r.stderr)
            self.assertNotIn("Traceback", r.stderr)

    def test_an_unknown_lang_flag_is_refused_before_anything_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = make_batch(tmp)
            for cmd in ("build", "serve"):
                with self.subTest(cmd=cmd):
                    r = subprocess.run([sys.executable, "-I", str(SCRIPT), cmd, str(d), "--lang", "xx"], capture_output=True, text=True)
                    self.assertEqual(r.returncode, 2)
                    self.assertIn("invalid choice: 'xx'", r.stderr)
            self.assertEqual(sorted(p.name for p in Path(d).iterdir()), ["batch.json"])

    def test_help_documents_the_flag(self):
        for cmd in ("serve", "build"):
            r = subprocess.run([sys.executable, "-I", str(SCRIPT), cmd, "--help"], capture_output=True, text=True)
            self.assertIn("--lang {en,pt-BR}", r.stdout)


if __name__ == "__main__":
    unittest.main()

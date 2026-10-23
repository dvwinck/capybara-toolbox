import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from helpers import HANDOFF, commit, git, init_repo, load_handoff

ho = load_handoff()


def run_main(argv, stdin=None):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        if stdin is not None:
            with mock.patch.object(sys, "stdin", io.StringIO(stdin)):
                rc = ho.main(argv)
        else:
            rc = ho.main(argv)
    return rc, out.getvalue(), err.getvalue()


class CliCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        self.repo = init_repo(self.tmp / "r")
        self.first = commit(self.repo, "first", {"src/a.py": "one\n"})
        clock = mock.patch.object(ho, "NOW", lambda: time.struct_time((2026, 10, 14, 9, 5, 7, 2, 287, -1)))
        clock.start()
        self.addCleanup(clock.stop)

    def draft_file(self, text):
        path = self.tmp / "draft.md"
        path.write_text(text, encoding="utf-8")
        return str(path)


class CollectCliTest(CliCase):
    def test_collect_prints_the_git_section_or_json(self):
        rc, out, _ = run_main(["collect", str(self.repo)])
        self.assertEqual(rc, 0)
        self.assertIn("## Git state", out)
        self.assertIn("## Estado do git", run_main(["collect", str(self.repo), "--lang", "pt-BR"])[1])
        rc, out, _ = run_main(["collect", str(self.repo), "--json"])
        self.assertEqual((rc, json.loads(out)["tip"]), (0, self.first))


class WriteCliTest(CliCase):
    def test_the_metainfo_block_becomes_the_header_and_a_missing_row_is_a_warning(self):
        draft = "---\nModelo: Claude Sonnet 5.5\nStatus: Proposta\n---\n## O que foi feito\n`file:src/a.py`\n"
        rc, out, _ = run_main(["write", str(self.repo), "--draft", self.draft_file(draft)])
        self.assertEqual(rc, 0)
        self.assertIn("warning: metainfo 'Original request' is missing", out)  # a pt-BR key counts in an English note
        self.assertNotIn("warning: metainfo 'Model' is missing", out)
        note = Path(out.split("note saved to ")[1].splitlines()[0]).read_text(encoding="utf-8")
        self.assertIn("| Modelo | Claude Sonnet 5.5 |", note)  # the agent's key is kept as written
        rc, out, _ = run_main(["write", str(self.repo), "--draft", self.draft_file(draft), "--json"])
        self.assertEqual(json.loads(out)["missing_meta"], ["Original request"])
        rc, out, _ = run_main(["write", str(self.repo), "--draft", self.draft_file(draft), "--json", "--lang", "pt-BR"])
        self.assertEqual(json.loads(out)["missing_meta"], ["Pedido original"])

    def test_a_bad_metainfo_block_is_exit_two_without_a_note(self):
        rc, _, err = run_main(["write", str(self.repo), "--draft", self.draft_file("---\nModelo\n---\n## O que foi feito\nx\n")])
        self.assertEqual(rc, 2)
        self.assertIn("error: invalid metainfo on line 2", err)
        self.assertFalse((self.repo / ".handoff").exists())

    def test_all_citations_verified_exits_zero(self):
        rc, out, _ = run_main(["write", str(self.repo), "--draft", self.draft_file("## O que foi feito\n`file:src/a.py`\n")])
        self.assertEqual(rc, 0)
        self.assertIn("note saved to", out)
        self.assertIn("1 citation, 0 not verified", out)
        self.assertIn("warning: section 'Next steps' is missing", out)

    def test_an_unverified_citation_exits_one_but_the_note_is_saved(self):
        rc, out, _ = run_main(["write", str(self.repo), "--draft", self.draft_file("## O que foi feito\n`branch:ghost`\n")])
        self.assertEqual(rc, 1)
        self.assertIn("line 2: branch:ghost  NOT VERIFIED", out)
        self.assertTrue(list((self.repo / ".handoff").glob("*.md")))

    def test_the_draft_can_come_from_standard_input(self):
        rc, out, _ = run_main(["write", str(self.repo), "--draft", "-", "--json"], stdin="## O que foi feito\n`file:src/a.py`\n")
        data = json.loads(out)
        self.assertEqual((rc, data["schema"], len(data["citations"])), (0, 1, 1))
        self.assertNotIn("start", data["citations"][0])

    def test_a_missing_draft_is_an_error(self):
        rc, out, err = run_main(["write", str(self.repo), "--draft", str(self.tmp / "none.md")])
        self.assertEqual((rc, out), (2, ""))
        self.assertIn("could not read the draft", err)


class VerifyCliTest(CliCase):
    def test_verify_reports_each_citation_and_never_edits_the_file(self):
        path = self.draft_file("`file:src/a.py` `file:nope.py`\n")
        rc, out, _ = run_main(["verify", path, str(self.repo)])
        self.assertEqual(rc, 1)
        self.assertIn("2 citations, 1 not verified", out)
        self.assertIn("nope.py  NOT VERIFIED", out)
        self.assertEqual(Path(path).read_text(encoding="utf-8"), "`file:src/a.py` `file:nope.py`\n")

    def test_verify_of_a_clean_note_exits_zero(self):
        self.assertEqual(run_main(["verify", self.draft_file("`file:src/a.py`\n"), str(self.repo)])[0], 0)

    def test_verify_of_something_that_is_not_a_file_is_an_error(self):
        self.assertEqual(run_main(["verify", str(self.tmp), str(self.repo)])[0], 2)


class ResumeCliTest(CliCase):
    def test_resume_shows_the_note_and_what_changed(self):
        run_main(["write", str(self.repo), "--draft", self.draft_file("## O que foi feito\n`branch:main`\n")])
        rc, out, _ = run_main(["resume", str(self.repo)])
        self.assertEqual(rc, 0)
        self.assertIn("# Handoff - 2026-10-14 09:05 - main", out)
        self.assertIn("nothing changed in git since the note", out)
        commit(self.repo, "later", {"b.txt": "b\n"})
        rc, out, _ = run_main(["resume", str(self.repo)])
        self.assertEqual(rc, 1)
        self.assertIn("changed since the note:", out)
        self.assertIn("MOVED (the tip is another)", out)

    def test_resume_json(self):
        run_main(["write", str(self.repo), "--draft", self.draft_file("## O que foi feito\nx\n")])
        rc, out, _ = run_main(["resume", str(self.repo), "--json"])
        data = json.loads(out)
        self.assertEqual((rc, data["schema"], data["drift"]), (0, 1, []))

    def test_resume_without_a_note_exits_two(self):
        rc, _, err = run_main(["resume", str(self.repo)])
        self.assertEqual(rc, 2)
        self.assertIn("there is no note", err)


class ScriptTest(CliCase):
    def test_the_script_runs_in_isolated_mode_from_any_folder(self):
        r = subprocess.run([sys.executable, "-I", str(HANDOFF), "collect", str(self.repo), "--json"], capture_output=True, text=True, cwd=str(self.tmp))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["branch"], "main")

    def test_not_a_repository_and_a_missing_command_are_errors(self):
        plain = self.tmp / "plain"
        plain.mkdir()
        self.assertEqual(run_main(["collect", str(plain)])[0], 2)
        with self.assertRaises(SystemExit) as ctx:
            run_main([])
        self.assertEqual(ctx.exception.code, 2)

    def test_version_flag(self):
        r = subprocess.run([sys.executable, "-I", str(HANDOFF), "--version"], capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "handoff " + ho.VERSION)


class FailureExitCodesTest(CliCase):
    def assert_clean_error(self, argv, stdin=None, needle="error:"):
        rc, out, err = run_main(argv, stdin=stdin)
        self.assertEqual((rc, out), (2, ""), err)
        self.assertIn(needle, err)
        self.assertNotIn("Traceback", err)

    def test_a_notes_folder_that_is_a_file(self):
        (self.repo / ".handoff").write_text("x\n", encoding="utf-8")
        self.assert_clean_error(["write", str(self.repo), "--draft", self.draft_file("## O que foi feito\nx\n")])

    def test_an_out_that_is_a_file(self):
        self.assert_clean_error(["write", str(self.repo), "--draft", self.draft_file("x\n"), "--out", self.draft_file("y\n")])

    def test_a_draft_that_is_a_folder(self):
        self.assert_clean_error(["write", str(self.repo), "--draft", str(self.tmp)])

    def test_an_unreadable_note_for_verify_and_resume(self):
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("running as root")
        run_main(["write", str(self.repo), "--draft", self.draft_file("## O que foi feito\n`file:src/a.py`\n")])
        note = next((self.repo / ".handoff").glob("*.md"))
        os.chmod(note, 0)
        self.addCleanup(os.chmod, note, 0o600)
        self.assert_clean_error(["verify", str(note), str(self.repo)], needle="could not read the note")
        self.assert_clean_error(["resume", str(self.repo), "--lang", "pt-BR"], needle="erro: nao consegui ler a nota")

    def test_invalid_utf8_on_standard_input(self):
        r = subprocess.run([sys.executable, "-I", str(HANDOFF), "write", str(self.repo), "--draft", "-"], input=b"## O que foi feito\n\xff\xfe\n",
                           capture_output=True, env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1"))
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn(b"error:", r.stderr)
        self.assertNotIn(b"Traceback", r.stderr)
        self.assertFalse((self.repo / ".handoff").exists() and list((self.repo / ".handoff").iterdir()))

    def test_the_safety_net_turns_stray_os_unicode_and_recursion_errors_into_exit_two(self):
        for exc in (OSError(13, "Permission denied"), UnicodeEncodeError("utf-8", "x", 0, 1, "bad"), RecursionError("deep")):
            with self.subTest(exc=type(exc).__name__):
                with mock.patch.object(ho, "collect", side_effect=exc):
                    self.assert_clean_error(["collect", str(self.repo)])


class AgreementTest(CliCase):
    def test_write_then_resume_and_verify_agree_on_a_note_whose_git_section_quotes_citations(self):
        commit(self.repo, "rename `file:old.py` to a.py and `branch:nope`", {"b.txt": "b\n"})
        rc, out, _ = run_main(["write", str(self.repo), "--draft", self.draft_file("## O que foi feito\n`file:src/a.py`\n")])
        self.assertEqual(rc, 0)
        self.assertIn("1 citation, 0 not verified", out)
        rc, out, _ = run_main(["resume", str(self.repo)])
        self.assertEqual(rc, 0, out)
        self.assertIn("nothing changed in git since the note", out)
        self.assertIn("1 citation, 0 with problems", out)
        note = next((self.repo / ".handoff").glob("*.md"))
        rc, out, _ = run_main(["verify", str(note), str(self.repo)])
        self.assertEqual(rc, 0, out)
        self.assertIn("1 citation, 0 not verified", out)


if __name__ == "__main__":
    unittest.main()


class LanguageCliTest(CliCase):
    def test_write_in_pt_br_prints_the_old_lines_and_writes_a_pt_br_note(self):
        rc, out, _ = run_main(["write", str(self.repo), "--draft", self.draft_file("## O que foi feito\n`branch:ghost`\n"), "--lang", "pt-BR"])
        self.assertEqual(rc, 1)
        self.assertIn("1 citacao, 1 nao verificada", out)
        self.assertIn("linha 2: branch:ghost  NAO VERIFICADO (a branch nao existe (local ou remota))", out)
        self.assertIn("aviso: falta a secao 'Proximos passos'", out)
        note = Path(out.split("nota gravada em ")[1].splitlines()[0]).read_text(encoding="utf-8")
        self.assertIn("`branch:ghost` [nao verificado]", note)
        self.assertIn("| Metainfo da sessao | |", note)

    def test_capybara_lang_is_the_default_and_the_flag_wins(self):
        with mock.patch.dict(os.environ, {"CAPYBARA_LANG": "pt-BR"}):
            self.assertIn("## Estado do git", run_main(["collect", str(self.repo)])[1])
            self.assertIn("## Git state", run_main(["collect", str(self.repo), "--lang", "en"])[1])
        with mock.patch.dict(os.environ, {"CAPYBARA_LANG": "ptbr"}):
            rc, out, err = run_main(["collect", str(self.repo)])
        self.assertEqual((rc, err), (0, ""))
        self.assertIn("## Git state", out)
        self.assertEqual(ho.CLI_LANG, "en")  # main() put the default back

    def test_a_note_does_not_set_the_language_of_resume(self):
        run_main(["write", str(self.repo), "--draft", self.draft_file("## O que foi feito\n`file:src/a.py`\n"), "--lang", "pt-BR"])
        rc, out, _ = run_main(["resume", str(self.repo)])
        self.assertEqual(rc, 0, out)
        self.assertIn("| Metainfo da sessao | |", out)  # the note, as it was written
        self.assertIn("--- checked now ---", out)  # the run's own lines, in the run's language
        self.assertIn("nothing changed in git since the note", out)

    def test_every_command_takes_lang_and_refuses_a_bad_one(self):
        for argv in (["collect"], ["write", "--draft", "x"], ["verify", "f"], ["resume"]):
            with self.subTest(cmd=argv[0]):
                self.assertEqual(ho.parser().parse_args(argv + ["--lang", "pt-BR"]).lang, "pt-BR")
        r = subprocess.run([sys.executable, "-I", str(HANDOFF), "collect", str(self.repo), "--lang", "xx"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn("invalid choice: 'xx'", r.stderr)

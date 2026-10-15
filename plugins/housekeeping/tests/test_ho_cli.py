import contextlib
import io
import json
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
        self.assertIn("## Estado do git", out)
        rc, out, _ = run_main(["collect", str(self.repo), "--json"])
        self.assertEqual((rc, json.loads(out)["tip"]), (0, self.first))


class WriteCliTest(CliCase):
    def test_all_citations_verified_exits_zero(self):
        rc, out, _ = run_main(["write", str(self.repo), "--draft", self.draft_file("## O que foi feito\n`file:src/a.py`\n")])
        self.assertEqual(rc, 0)
        self.assertIn("nota gravada em", out)
        self.assertIn("1 citacoes, 0 nao verificadas", out)
        self.assertIn("aviso: falta a secao 'Proximos passos'", out)

    def test_an_unverified_citation_exits_one_but_the_note_is_saved(self):
        rc, out, _ = run_main(["write", str(self.repo), "--draft", self.draft_file("## O que foi feito\n`branch:ghost`\n")])
        self.assertEqual(rc, 1)
        self.assertIn("linha 2: branch:ghost  NAO VERIFICADO", out)
        self.assertTrue(list((self.repo / ".handoff").glob("*.md")))

    def test_the_draft_can_come_from_standard_input(self):
        rc, out, _ = run_main(["write", str(self.repo), "--draft", "-", "--json"], stdin="## O que foi feito\n`file:src/a.py`\n")
        data = json.loads(out)
        self.assertEqual((rc, data["schema"], len(data["citations"])), (0, 1, 1))
        self.assertNotIn("start", data["citations"][0])

    def test_a_missing_draft_is_an_error(self):
        rc, out, err = run_main(["write", str(self.repo), "--draft", str(self.tmp / "none.md")])
        self.assertEqual((rc, out), (2, ""))
        self.assertIn("nao consegui ler o rascunho", err)


class VerifyCliTest(CliCase):
    def test_verify_reports_each_citation_and_never_edits_the_file(self):
        path = self.draft_file("`file:src/a.py` `file:nope.py`\n")
        rc, out, _ = run_main(["verify", path, str(self.repo)])
        self.assertEqual(rc, 1)
        self.assertIn("2 citacoes, 1 nao verificadas", out)
        self.assertIn("nope.py  NAO VERIFICADO", out)
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
        self.assertIn("nada mudou no git desde a nota", out)
        commit(self.repo, "later", {"b.txt": "b\n"})
        rc, out, _ = run_main(["resume", str(self.repo)])
        self.assertEqual(rc, 1)
        self.assertIn("mudou desde a nota:", out)
        self.assertIn("MUDOU (a ponta e outra)", out)

    def test_resume_json(self):
        run_main(["write", str(self.repo), "--draft", self.draft_file("## O que foi feito\nx\n")])
        rc, out, _ = run_main(["resume", str(self.repo), "--json"])
        data = json.loads(out)
        self.assertEqual((rc, data["schema"], data["drift"]), (0, 1, []))

    def test_resume_without_a_note_exits_two(self):
        rc, _, err = run_main(["resume", str(self.repo)])
        self.assertEqual(rc, 2)
        self.assertIn("nao ha nota", err)


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


if __name__ == "__main__":
    unittest.main()

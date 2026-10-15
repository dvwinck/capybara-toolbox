import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import DOC_TRUTH, commit, git, init_repo, load_doc_truth

dt = load_doc_truth()


def run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = dt.main(argv)
    return rc, out.getvalue(), err.getvalue()


class CliCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        self.repo = init_repo(self.tmp / "r")

    def docs(self, files):
        commit(self.repo, "docs", files)

    def config(self, data):
        (self.repo / ".doc-truth.json").write_text(json.dumps(data), encoding="utf-8")


class RunTest(CliCase):
    def test_a_clean_repository_exits_zero(self):
        self.docs({"README.md": "# T\n`a.md`\n", "README.pt-BR.md": "# T\n", "a.md": "x\n"})
        rc, out, _ = run_main([str(self.repo)])
        self.assertEqual(rc, 0, out)
        self.assertIn("limpo: nenhum achado", out)

    def test_findings_exit_one_and_are_grouped_by_category(self):
        self.docs({"README.md": "# T\n`gone.md` [x](nope.md)\n", "README.pt-BR.md": "# T\n"})
        rc, out, _ = run_main([str(self.repo)])
        self.assertEqual(rc, 1)
        self.assertIn("[path] 1", out)
        self.assertIn("[link] 1", out)
        self.assertIn("README.md:2  gone.md", out)
        self.assertIn("fingerprint:", out)

    def test_json_output_has_a_schema_and_the_findings(self):
        self.docs({"README.md": "# T\n`gone.md`\n", "README.pt-BR.md": "# T\n"})
        rc, out, _ = run_main([str(self.repo), "--json"])
        data = json.loads(out)
        self.assertEqual(rc, 1)
        self.assertEqual((data["schema"], data["tool"], data["documents"], data["accepted"]), (1, "doc-truth", 2, 0))
        f = data["findings"][0]
        self.assertEqual((f["category"], f["document"], f["line"], f["value"]), ("path", "README.md", 2, "gone.md"))
        self.assertEqual(len(f["fingerprint"]), 16)

    def test_the_fingerprint_ignores_the_line_so_an_edit_above_keeps_an_accepted_finding_accepted(self):
        self.docs({"README.md": "# T\n`gone.md`\n", "README.pt-BR.md": "# T\n"})
        fp = json.loads(run_main([str(self.repo), "--json"])[1])["findings"][0]["fingerprint"]
        self.config({"allow": [fp]})
        self.docs({"README.md": "# T\n\nintro line added\n\n`gone.md`\n"})
        rc, out, _ = run_main([str(self.repo), "--json"])
        data = json.loads(out)
        self.assertEqual((rc, data["findings"], data["accepted"]), (0, [], 1))

    def test_a_new_value_in_an_accepted_place_is_a_new_finding(self):
        self.docs({"README.md": "# T\n`gone.md`\n", "README.pt-BR.md": "# T\n"})
        fp = json.loads(run_main([str(self.repo), "--json"])[1])["findings"][0]["fingerprint"]
        self.config({"allow": [fp]})
        self.docs({"README.md": "# T\n`gone.md` `other-gone.md`\n"})
        data = json.loads(run_main([str(self.repo), "--json"])[1])
        self.assertEqual([f["value"] for f in data["findings"]], ["other-gone.md"])

    def test_exclude_removes_a_document_from_the_check(self):
        self.docs({"README.md": "# T\n", "README.pt-BR.md": "# T\n", "docs/plans/p.md": "`gone.md`\n"})
        self.assertEqual(run_main([str(self.repo)])[0], 1)
        self.config({"exclude": ["docs/plans/**"]})
        rc, out, _ = run_main([str(self.repo)])
        self.assertEqual(rc, 0, out)

    def test_an_excluded_document_is_still_a_valid_link_target(self):
        self.docs({"README.md": "# T\n[p](docs/plans/p.md#top)\n", "README.pt-BR.md": "# T\n", "docs/plans/p.md": "# Top\n"})
        self.config({"exclude": ["docs/plans/**"]})
        self.assertEqual(run_main([str(self.repo)])[0], 0)

    def test_the_run_never_writes_to_the_repository(self):
        self.docs({"README.md": "# T\n`gone.md`\n", "README.pt-BR.md": "# T\n"})
        before = git(self.repo, "status", "--porcelain=v1", "--ignored")
        run_main([str(self.repo)])
        run_main([str(self.repo), "--json"])
        self.assertEqual(git(self.repo, "status", "--porcelain=v1", "--ignored"), before)
        self.assertEqual(before, "")

    def test_a_document_listed_by_git_but_missing_from_the_disk_is_skipped(self):
        self.docs({"README.md": "# T\n", "README.pt-BR.md": "# T\n", "gone.md": "x\n"})
        (self.repo / "gone.md").unlink()
        self.assertEqual(run_main([str(self.repo)])[0], 0)


class SymlinkTest(CliCase):
    def test_a_tracked_symlink_to_a_file_outside_the_repository_is_never_read(self):
        outside = self.tmp / "outside.md"
        outside.write_text("# Secret\n`leaked-path.md` [x](nowhere.md)\n", encoding="utf-8")
        self.docs({"README.md": "# T\n", "README.pt-BR.md": "# T\n"})
        os.symlink(outside, self.repo / "notes.md")
        git(self.repo, "add", "notes.md")
        git(self.repo, "commit", "-q", "-m", "link")
        rc, out, _ = run_main([str(self.repo), "--json"])
        data = json.loads(out)
        self.assertEqual((rc, data["findings"], data["documents"]), (0, [], 2))
        self.assertNotIn("leaked-path", out)

    def test_a_symlinked_manifest_is_not_trusted(self):
        outside = self.tmp / "plugin.json"
        outside.write_text(json.dumps({"name": "evil", "version": "9.9.9"}), encoding="utf-8")
        self.docs({"README.md": "# T\nevil 1.0.0\n", "README.pt-BR.md": "# T\n"})
        (self.repo / "plugins" / "evil" / ".claude-plugin").mkdir(parents=True)
        os.symlink(outside, self.repo / "plugins" / "evil" / ".claude-plugin" / "plugin.json")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "manifest link")
        self.assertEqual(run_main([str(self.repo)])[0], 0)


class ErrorTest(CliCase):
    def test_not_a_repository_exits_two(self):
        plain = self.tmp / "plain"
        plain.mkdir()
        rc, out, err = run_main([str(plain)])
        self.assertEqual((rc, out), (2, ""))
        self.assertIn("nao e um repositorio git", err)

    def test_a_bad_config_exits_two_and_names_the_problem(self):
        self.docs({"README.md": "# T\n", "README.pt-BR.md": "# T\n"})
        self.config({"exclud": []})
        rc, _, err = run_main([str(self.repo)])
        self.assertEqual(rc, 2)
        self.assertIn("exclud", err)

    def test_an_explicit_config_that_does_not_exist_exits_two(self):
        self.docs({"README.md": "# T\n", "README.pt-BR.md": "# T\n"})
        self.assertEqual(run_main([str(self.repo), "--config", str(self.tmp / "none.json")])[0], 2)


class ScriptTest(CliCase):
    def test_the_script_runs_in_isolated_mode_from_any_folder(self):
        self.docs({"README.md": "# T\n`gone.md`\n", "README.pt-BR.md": "# T\n"})
        r = subprocess.run([sys.executable, "-I", str(DOC_TRUTH), str(self.repo)], capture_output=True, text=True, cwd=str(self.tmp))
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("gone.md", r.stdout)

    def test_version_flag(self):
        r = subprocess.run([sys.executable, "-I", str(DOC_TRUTH), "--version"], capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "doc-truth " + dt.VERSION)


if __name__ == "__main__":
    unittest.main()

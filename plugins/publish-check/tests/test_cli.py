import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import LEAK_EMAIL, LEAK_LINK, SCRIPT, commit, init_repo


def run(*argv, cwd=None):
    return subprocess.run([sys.executable, "-I", str(SCRIPT), *argv], capture_output=True, text=True, cwd=cwd)


class CliTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.repo = init_repo(self.tmp / "repo")

    def test_clean_repository_exits_0(self):
        commit(self.repo, "fine", {"a.txt": "hello\n"})
        r = run(str(self.repo))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("clean: no findings", r.stdout)

    def test_findings_exit_1_and_the_report_never_shows_the_raw_value(self):
        commit(self.repo, f"leaky\n\nsee {LEAK_LINK}", {"a.txt": f"mail {LEAK_EMAIL}\n"})
        r = run(str(self.repo))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("[email]", r.stdout)
        self.assertIn("[session-link]", r.stdout)
        self.assertIn("fingerprint:", r.stdout)
        self.assertIn("never rewrites history", r.stdout)
        for raw in ("FIXTURE123", "fixture.person"):
            self.assertNotIn(raw, r.stdout)

    def test_default_path_is_the_current_directory(self):
        commit(self.repo, "fine", {"a.txt": "hello\n"})
        r = run(cwd=self.repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_json_report_has_a_stable_shape(self):
        commit(self.repo, "leaky", {"a.txt": f"mail {LEAK_EMAIL}\n"})
        r = run(str(self.repo), "--json")
        self.assertEqual(r.returncode, 1)
        report = json.loads(r.stdout)
        self.assertEqual(report["schema"], 1)
        self.assertEqual(report["tool"], "publish-check")
        self.assertFalse(report["clean"])
        self.assertEqual(set(report["counts"]), {"session-link", "home-path", "email", "denylist"})
        self.assertEqual(set(report["scanned"]), {"files", "commits", "skipped"})
        self.assertIn("allowed", report)
        self.assertIn("shallow", report)
        for f in report["findings"]:
            self.assertEqual(set(f), {"category", "where", "location", "snippet", "fingerprint"})
            self.assertNotIn("fixture.person", json.dumps(f))

    def test_skipped_files_are_visible_in_both_reports(self):
        commit(self.repo, "fine", {"a.txt": "hello\n"})
        (self.repo / "blob.bin").write_bytes(b"\0\1\2")
        text = run(str(self.repo))
        self.assertEqual(text.returncode, 0, text.stdout + text.stderr)
        self.assertIn("1 file skipped", text.stdout)
        self.assertEqual(json.loads(run(str(self.repo), "--json").stdout)["scanned"]["skipped"], 1)

    def test_json_report_of_a_clean_repository(self):
        commit(self.repo, "fine", {"a.txt": "hello\n"})
        r = run(str(self.repo), "--json")
        self.assertEqual(r.returncode, 0)
        report = json.loads(r.stdout)
        self.assertTrue(report["clean"])
        self.assertEqual(report["findings"], [])

    def test_a_shallow_clone_is_reported_as_incomplete(self):
        commit(self.repo, "one", {"a.txt": "1\n"})
        commit(self.repo, "two", {"a.txt": "2\n"})
        clone = self.tmp / "clone"
        subprocess.run(["git", "clone", "-q", "--depth", "1", "file://" + str(self.repo), str(clone)], check=True,
                       capture_output=True)
        text = run(str(clone))
        self.assertEqual(text.returncode, 0, text.stdout + text.stderr)
        self.assertIn("shallow", text.stdout)
        self.assertTrue(json.loads(run(str(clone), "--json").stdout)["shallow"])
        self.assertFalse(json.loads(run(str(self.repo), "--json").stdout)["shallow"])

    def test_not_a_git_repository_exits_2(self):
        r = run(str(self.tmp))
        self.assertEqual(r.returncode, 2)
        self.assertIn("not inside a git repository", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_bad_config_exits_2(self):
        commit(self.repo, "fine", {"a.txt": "hello\n"})
        (self.repo / ".publish-check.json").write_text("{nope", encoding="utf-8")
        r = run(str(self.repo))
        self.assertEqual(r.returncode, 2)
        self.assertIn("not valid JSON", r.stderr)

    def test_invalid_options_exit_2(self):
        r = run(str(self.repo), "--max-commits", "0")
        self.assertEqual(r.returncode, 2)

    def test_version_flag(self):
        r = run("--version")
        self.assertEqual(r.returncode, 0)
        self.assertRegex(r.stdout, r"^publish-check \d+\.\d+\.\d+")

    def test_report_does_not_modify_the_repository(self):
        commit(self.repo, "leaky", {"a.txt": f"mail {LEAK_EMAIL}\n"})
        before = subprocess.run(["git", "-C", str(self.repo), "status", "--porcelain"], capture_output=True, text=True).stdout
        run(str(self.repo))
        after = subprocess.run(["git", "-C", str(self.repo), "status", "--porcelain"], capture_output=True, text=True).stdout
        self.assertEqual(before, after)
        self.assertEqual(sorted(p.name for p in self.repo.iterdir()), [".git", "a.txt"])


if __name__ == "__main__":
    unittest.main()

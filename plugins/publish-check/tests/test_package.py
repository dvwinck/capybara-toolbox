import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import LEAK_EMAIL, REPO, ROOT, SCRIPT, commit, init_repo, load_sync

sync = load_sync()


def run_sync(argv, root):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = sync.main(argv, root=Path(root))
    return rc, out.getvalue()


def copy_plugin(dest):
    for rel in sync.INPUTS:
        (Path(dest) / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, Path(dest) / rel)


class RepositoryStateTest(unittest.TestCase):
    def test_plugin_is_in_sync(self):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "sync.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_manifest_version_matches_script(self):
        script = (ROOT / sync.SCRIPT).read_text(encoding="utf-8")
        manifest = json.loads((ROOT / sync.PLUGIN).read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], sync.script_version(script))

    def test_script_carries_its_license(self):
        head = SCRIPT.read_text(encoding="utf-8").splitlines()[:6]
        self.assertTrue(head[1].startswith("# publish-check "), head[1])
        self.assertIn("# SPDX-License-Identifier: MIT", head)
        self.assertIn("# Copyright (c) 2026 Diogo Winck", head)

    def test_manifest_points_to_the_repository(self):
        manifest = json.loads((ROOT / sync.PLUGIN).read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "publish-check")
        self.assertEqual(manifest["homepage"], "https://github.com/dvwinck/capybara-toolbox")
        self.assertEqual(manifest["repository"], "https://github.com/dvwinck/capybara-toolbox")


class SyncToolTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        copy_plugin(self.tmp)

    def test_manifest_drift_is_detected_and_fixed(self):
        manifest = self.tmp / sync.PLUGIN
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["version"] = "9.9.9"
        manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        self.assertEqual(run_sync(["--check"], self.tmp)[0], 1)
        self.assertEqual(run_sync([], self.tmp)[0], 0)
        self.assertEqual(run_sync(["--check"], self.tmp)[0], 0)
        self.assertNotEqual(json.loads(manifest.read_text(encoding="utf-8"))["version"], "9.9.9")

    def test_version_bump_propagates_and_requires_a_changelog_entry(self):
        script = self.tmp / sync.SCRIPT
        text = script.read_text(encoding="utf-8")
        text = re.sub(r"^# publish-check \d+\.\d+\.\d+ - ", "# publish-check 9.9.9 - ", text, flags=re.M)
        text = re.sub(r'^VERSION = "\d+\.\d+\.\d+"', 'VERSION = "9.9.9"', text, flags=re.M)
        script.write_text(text, encoding="utf-8")
        rc, out = run_sync([], self.tmp)
        self.assertEqual(rc, 1)  # CHANGELOG has no 9.9.9 entry
        self.assertIn("CHANGELOG.md", out)
        self.assertEqual(json.loads((self.tmp / sync.PLUGIN).read_text(encoding="utf-8"))["version"], "9.9.9")
        changelog = self.tmp / sync.CHANGELOG
        changelog.write_text("## [9.9.9] - 2099-01-01\n" + changelog.read_text(encoding="utf-8"), encoding="utf-8")
        self.assertEqual(run_sync(["--check"], self.tmp)[0], 0)

    def test_stale_header_comment_is_reported(self):
        script = self.tmp / sync.SCRIPT
        text = script.read_text(encoding="utf-8")
        script.write_text(re.sub(r"^# publish-check \d+\.\d+\.\d+ - ", "# publish-check 0.0.1 - ", text, flags=re.M),
                          encoding="utf-8")
        rc, out = run_sync(["--check"], self.tmp)
        self.assertEqual(rc, 1)
        self.assertIn("header comment", out)



class DocsTest(unittest.TestCase):
    def test_files_named_in_the_readmes_exist(self):
        for readme in ("README.md", "README.pt-BR.md"):
            text = (ROOT / readme).read_text(encoding="utf-8")
            for rel in ("docs/remediation.md", "examples/pre-push.sh", "examples/ci-step.yml", "CHANGELOG.md"):
                with self.subTest(readme=readme, rel=rel):
                    self.assertIn(rel, text)
                    self.assertTrue((ROOT / rel).is_file(), rel)


class SkillTest(unittest.TestCase):
    SKILL = (ROOT / "skills" / "publish-check" / "SKILL.md")

    def test_frontmatter_names_the_skill_and_has_triggers(self):
        text = self.SKILL.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nname: publish-check\ndescription: "))
        head = text.split("\n---\n", 1)[0]
        for trigger in ("/publish-check", "publish-check", "antes de publicar", "before I publish"):
            self.assertIn(trigger, head)

    def test_skill_runs_the_bundled_script_in_isolated_mode(self):
        text = self.SKILL.read_text(encoding="utf-8")
        self.assertIn('python3 -I "${CLAUDE_SKILL_DIR}/scripts/publish_check.py"', text)
        self.assertIn("Base directory for this skill", text)  # fallback when the variable is not expanded

    def test_skill_is_read_only_and_never_blocks(self):
        text = self.SKILL.read_text(encoding="utf-8")
        self.assertIn("somente leitura", text.lower())
        self.assertIn("Nunca reescreva histórico", text)
        self.assertIn("nunca bloqueie", text.lower())


class ExamplesTest(unittest.TestCase):
    def run_hook(self, repo):
        env = {**os.environ, "PUBLISH_CHECK": str(SCRIPT)}
        return subprocess.run(["bash", str(ROOT / "examples" / "pre-push.sh")], cwd=repo, env=env,
                              capture_output=True, text=True)

    def test_pre_push_hook_blocks_a_leak_and_lets_a_clean_repository_through(self):
        with tempfile.TemporaryDirectory() as tmp:
            clean = init_repo(Path(tmp) / "clean")
            commit(clean, "fine", {"a.txt": "hello\n"})
            r = self.run_hook(clean)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            leaky = init_repo(Path(tmp) / "leaky")
            commit(leaky, "oops", {"a.txt": f"mail {LEAK_EMAIL}\n"})
            r = self.run_hook(leaky)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("push blocked", r.stderr)

    def test_ci_example_fetches_the_whole_history(self):
        text = (ROOT / "examples" / "ci-step.yml").read_text(encoding="utf-8")
        self.assertIn("fetch-depth: 0", text)


class ManualInstallTest(unittest.TestCase):
    def run_install(self, home, *args):
        return subprocess.run(["bash", str(REPO / "install.sh"), *args], env={**os.environ, "HOME": home},
                              capture_output=True, text=True)

    def test_install_copies_the_skill_and_uninstall_removes_it(self):
        with tempfile.TemporaryDirectory() as home:
            r = self.run_install(home, "publish-check")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            dest = Path(home, ".claude", "skills", "publish-check")
            self.assertEqual((dest / "scripts" / "publish_check.py").read_bytes(), SCRIPT.read_bytes())
            self.assertTrue((dest / "SKILL.md").exists())
            r = self.run_install(home, "publish-check", "--uninstall")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertFalse(dest.exists())

    def test_list_shows_the_plugin(self):
        with tempfile.TemporaryDirectory() as home:
            r = self.run_install(home, "--list")
            self.assertEqual(r.returncode, 0)
            self.assertIn("publish-check", r.stdout.split())


if __name__ == "__main__":
    unittest.main()

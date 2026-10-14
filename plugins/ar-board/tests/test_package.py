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

from helpers import REPO, ROOT, load_sync

sync = load_sync()
TRACKED = sync.INPUTS + [sync.SINGLE, sync.QB_SINGLE, sync.QB_SCRIPT]


def run_sync(argv, root):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = sync.main(argv, root=Path(root))
    return rc, out.getvalue()


def copy_plugin(dest):
    for rel in TRACKED:
        src = ROOT / rel
        if src.exists():
            (Path(dest) / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, Path(dest) / rel)


class RepositoryStateTest(unittest.TestCase):
    def test_plugin_is_in_sync(self):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "sync.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_manifest_version_matches_script(self):
        script = (ROOT / sync.SCRIPT).read_text(encoding="utf-8")
        manifest = json.loads((ROOT / sync.PLUGIN).read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], sync.script_version(script))

    def test_script_carries_its_license(self):
        head = (ROOT / sync.SCRIPT).read_text(encoding="utf-8").splitlines()[:6]
        self.assertTrue(head[1].startswith("# ar-board "), head[1])
        self.assertIn("# SPDX-License-Identifier: MIT", head)
        self.assertIn("# Copyright (c) 2026 Diogo Winck", head)

    def test_manifest_points_to_the_repository(self):
        manifest = json.loads((ROOT / sync.PLUGIN).read_text(encoding="utf-8"))
        self.assertEqual(manifest["homepage"], "https://github.com/dvwinck/capybara-toolbox")
        self.assertEqual(manifest["repository"], "https://github.com/dvwinck/capybara-toolbox")


class SkillCommandsTest(unittest.TestCase):
    BUNDLED = '"${CLAUDE_SKILL_DIR}/scripts/ar_board.py"'
    INSTALLED = '"$HOME/.claude/ar-board/ar_board.py"'

    def test_lean_skill_runs_the_bundled_script(self):
        skill = (ROOT / sync.SKILL).read_text(encoding="utf-8")
        for cmd in ("check", "serve", "wait", "summary"):
            with self.subTest(cmd=cmd):
                self.assertIn("python3 -I %s %s " % (self.BUNDLED, cmd), skill)
        self.assertNotIn('"$S"', skill)
        self.assertIn("Base directory for this skill", skill)  # fallback when the variable is not expanded

    def test_single_file_variant_uses_the_installed_path_everywhere(self):
        skill = (ROOT / sync.SKILL).read_text(encoding="utf-8")
        single = sync.build(ROOT)[sync.SINGLE]
        body = single.split("\n## Script\n", 1)[0]
        self.assertNotIn("CLAUDE_SKILL_DIR", body)
        self.assertNotIn('"$S"', body)
        self.assertEqual(body.count("python3 -I " + self.INSTALLED), skill.count("python3 -I " + self.BUNDLED))
        self.assertIn('test -f %s' % self.INSTALLED, body)


class QuestionBoardPackageTest(unittest.TestCase):
    def test_the_script_copy_is_byte_identical(self):
        self.assertEqual((ROOT / sync.QB_SCRIPT).read_bytes(), (ROOT / sync.SCRIPT).read_bytes())

    def test_lean_skill_runs_the_bundled_script(self):
        skill = (ROOT / sync.QB_SKILL).read_text(encoding="utf-8")
        for cmd in ("check", "serve", "wait", "summary"):
            with self.subTest(cmd=cmd):
                self.assertIn('python3 -I "${CLAUDE_SKILL_DIR}/scripts/ar_board.py" %s ' % cmd, skill)
        self.assertIn("Base directory for this skill", skill)

    def test_skill_declares_its_name_and_both_triggers(self):
        head = (ROOT / sync.QB_SKILL).read_text(encoding="utf-8").split("---", 2)[1]
        self.assertIn("name: question-board", head)
        self.assertIn("/ar-board:question-board", head)

    def test_single_file_variant_uses_the_installed_path_everywhere(self):
        skill = (ROOT / sync.QB_SKILL).read_text(encoding="utf-8")
        single = sync.build(ROOT)[sync.QB_SINGLE]
        body = single.split("\n## Script\n", 1)[0]
        self.assertNotIn("CLAUDE_SKILL_DIR", body)
        self.assertEqual(body.count('python3 -I "$HOME/.claude/ar-board/ar_board.py"'),
                         skill.count('python3 -I "${CLAUDE_SKILL_DIR}/scripts/ar_board.py"'))
        self.assertIn("`" * 3 + "python", single)  # the embedded script block

    def test_example_batch_is_valid(self):
        import json
        from helpers import ab

        data = json.loads((ROOT / "skills" / "question-board" / "examples" / "batch.example.json").read_text(encoding="utf-8"))
        self.assertEqual(ab.validate(data), [])
        self.assertTrue(all(ab.is_question(it) for it in data["items"]))


class SyncToolTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        copy_plugin(self.tmp)

    def test_detects_drift_and_fixes_it(self):
        self.assertEqual(run_sync(["--check"], self.tmp)[0], 0)
        with open(self.tmp / sync.SCRIPT, "a", encoding="utf-8") as f:
            f.write("# marker-for-test\n")
        self.assertEqual(run_sync(["--check"], self.tmp)[0], 1)
        self.assertEqual(run_sync([], self.tmp)[0], 0)
        self.assertEqual(run_sync(["--check"], self.tmp)[0], 0)
        self.assertIn("# marker-for-test", (self.tmp / sync.SINGLE).read_text(encoding="utf-8"))

    def test_version_bump_propagates_to_manifest_and_requires_changelog(self):
        script = self.tmp / sync.SCRIPT
        text = script.read_text(encoding="utf-8")
        text = re.sub(r"^# ar-board \d+\.\d+\.\d+ - ", "# ar-board 9.9.9 - ", text, flags=re.M)
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
        script.write_text(re.sub(r"^# ar-board \d+\.\d+\.\d+ - ", "# ar-board 0.0.1 - ", text, flags=re.M), encoding="utf-8")
        rc, out = run_sync(["--check"], self.tmp)
        self.assertEqual(rc, 1)
        self.assertIn("header comment", out)

    def test_drift_in_the_script_copy_is_detected_and_repaired(self):
        self.assertEqual(run_sync(["--check"], self.tmp)[0], 0)
        copy = self.tmp / sync.QB_SCRIPT
        copy.write_text(copy.read_text(encoding="utf-8") + "# edited by hand\n", encoding="utf-8")
        rc, out = run_sync(["--check"], self.tmp)
        self.assertEqual(rc, 1)
        self.assertIn(sync.QB_SCRIPT, out)
        self.assertEqual(run_sync([], self.tmp)[0], 0)
        self.assertEqual(copy.read_bytes(), (self.tmp / sync.SCRIPT).read_bytes())

    def test_a_missing_script_copy_is_created(self):
        (self.tmp / sync.QB_SCRIPT).unlink()
        self.assertEqual(run_sync(["--check"], self.tmp)[0], 1)
        self.assertEqual(run_sync([], self.tmp)[0], 0)
        self.assertTrue((self.tmp / sync.QB_SCRIPT).is_file())

    def test_sync_fails_loudly_when_the_question_board_marker_stops_matching(self):
        skill = self.tmp / sync.QB_SKILL
        text = skill.read_text(encoding="utf-8")
        self.assertIn("<!-- question-board:locate-script -->", text)
        skill.write_text(text.replace("<!-- question-board:locate-script -->", "", 1), encoding="utf-8")
        with self.assertRaises(SystemExit):
            run_sync(["--check"], self.tmp)

    def test_sync_fails_loudly_when_the_question_board_skill_stops_naming_the_bundled_script(self):
        skill = self.tmp / sync.QB_SKILL
        skill.write_text(skill.read_text(encoding="utf-8").replace(sync.BUNDLED, "<script>"), encoding="utf-8")
        with self.assertRaises(SystemExit):
            run_sync(["--check"], self.tmp)

    def test_sync_fails_loudly_when_the_marker_stops_matching(self):
        skill = self.tmp / sync.SKILL
        text = skill.read_text(encoding="utf-8")
        self.assertIn("<!-- ar-board:locate-script -->", text)
        skill.write_text(text.replace("<!-- ar-board:locate-script -->", "", 1), encoding="utf-8")
        with self.assertRaises(SystemExit):
            run_sync(["--check"], self.tmp)

    def test_sync_fails_loudly_when_the_skill_stops_naming_the_bundled_script(self):
        skill = self.tmp / sync.SKILL
        skill.write_text(skill.read_text(encoding="utf-8").replace(sync.BUNDLED, "<script>"), encoding="utf-8")
        with self.assertRaises(SystemExit):
            run_sync(["--check"], self.tmp)


class ManualInstallTest(unittest.TestCase):
    def run_install(self, home, *args):
        return subprocess.run(["bash", str(REPO / "install.sh"), *args], env={**os.environ, "HOME": home}, capture_output=True, text=True)

    def test_install_copies_the_skill_and_uninstall_removes_it(self):
        with tempfile.TemporaryDirectory() as home:
            r = self.run_install(home, "ar-board")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            dest = Path(home, ".claude", "skills", "ar-board")
            self.assertEqual((dest / "scripts" / "ar_board.py").read_bytes(), (ROOT / sync.SCRIPT).read_bytes())
            self.assertTrue((dest / "SKILL.md").exists())
            r = self.run_install(home, "ar-board", "--uninstall")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertFalse(dest.exists())

    def test_install_does_not_copy_bytecode_caches(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp, "repo")
            shutil.copytree(ROOT / "skills", repo / "plugins" / "ar-board" / "skills",
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            shutil.copy2(REPO / "install.sh", repo / "install.sh")
            cache = repo / "plugins" / "ar-board" / "skills" / "ar-board" / "scripts" / "__pycache__"
            cache.mkdir()
            (cache / "ar_board.cpython-39.pyc").write_bytes(b"stale")
            (repo / "plugins" / "ar-board" / "skills" / "ar-board" / "stray.pyc").write_bytes(b"stale")
            home = Path(tmp, "home")
            home.mkdir()
            r = subprocess.run(["bash", str(repo / "install.sh"), "ar-board"], env={**os.environ, "HOME": str(home)},
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            dest = home / ".claude" / "skills" / "ar-board"
            self.assertTrue((dest / "scripts" / "ar_board.py").is_file())
            leftovers = [p.name for p in dest.rglob("*") if p.name == "__pycache__" or p.suffix == ".pyc"]
            self.assertEqual(leftovers, [])

    def test_unknown_plugin_is_rejected_and_installs_nothing(self):
        with tempfile.TemporaryDirectory() as home:
            r = self.run_install(home, "does-not-exist")
            self.assertNotEqual(r.returncode, 0)
            self.assertFalse(Path(home, ".claude").exists())

    def test_list_shows_available_plugins(self):
        with tempfile.TemporaryDirectory() as home:
            r = self.run_install(home, "--list")
            self.assertEqual(r.returncode, 0)
            self.assertIn("ar-board", r.stdout.split())

    def test_install_copies_both_skills_and_uninstall_removes_both(self):
        with tempfile.TemporaryDirectory() as home:
            r = self.run_install(home, "ar-board")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            for name in ("ar-board", "question-board"):
                dest = Path(home, ".claude", "skills", name)
                with self.subTest(skill=name):
                    self.assertEqual((dest / "scripts" / "ar_board.py").read_bytes(), (ROOT / sync.SCRIPT).read_bytes())
                    self.assertTrue((dest / "SKILL.md").exists())
            r = self.run_install(home, "ar-board", "--uninstall")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            for name in ("ar-board", "question-board"):
                self.assertFalse(Path(home, ".claude", "skills", name).exists())

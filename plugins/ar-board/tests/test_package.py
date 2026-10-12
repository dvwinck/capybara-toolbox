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
TRACKED = sync.INPUTS + [sync.SINGLE]


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

    def test_sync_fails_loudly_when_the_marker_stops_matching(self):
        skill = self.tmp / sync.SKILL
        text = skill.read_text(encoding="utf-8")
        self.assertIn("<!-- ar-board:locate-script -->", text)
        skill.write_text(text.replace("<!-- ar-board:locate-script -->", "", 1), encoding="utf-8")
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

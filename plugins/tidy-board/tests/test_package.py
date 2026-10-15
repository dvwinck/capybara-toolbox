import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import CAPY, ENGINE, REPO, ROOT, SCRIPT, load_sync

sync = load_sync()


def run_sync(argv, root):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = sync.main(argv, root=Path(root))
    return rc, out.getvalue()


def copy_plugin(tmp):
    """A throwaway marketplace: this plugin plus the engine it vendors, laid out as in the repository."""
    root = Path(tmp) / "plugins" / "tidy-board"
    for rel in sync.INPUTS + [sync.CAPY]:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, root / rel)
    engine = (root / sync.ENGINE).resolve()
    engine.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ENGINE, engine)
    return root


class RepositoryStateTest(unittest.TestCase):
    def test_plugin_is_in_sync(self):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "sync.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_vendored_engine_is_a_byte_copy_of_the_ar_board_engine(self):
        self.assertEqual(CAPY.read_bytes(), ENGINE.read_bytes())

    def test_manifest_version_matches_script(self):
        manifest = json.loads((ROOT / sync.PLUGIN).read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], sync.script_version(SCRIPT.read_text(encoding="utf-8")))

    def test_script_carries_its_license(self):
        head = SCRIPT.read_text(encoding="utf-8").splitlines()[:6]
        self.assertTrue(head[1].startswith("# tidy-board "), head[1])
        self.assertIn("# SPDX-License-Identifier: MIT", head)
        self.assertIn("# Copyright (c) 2026 Diogo Winck", head)

    def test_manifest_points_to_the_repository(self):
        manifest = json.loads((ROOT / sync.PLUGIN).read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "tidy-board")
        self.assertEqual(manifest["homepage"], "https://github.com/dvwinck/capybara-toolbox")
        self.assertEqual(manifest["repository"], "https://github.com/dvwinck/capybara-toolbox")


class SyncToolTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = copy_plugin(tmp.name)

    def test_a_clean_copy_passes_the_check(self):
        rc, out = run_sync(["--check"], self.root)
        self.assertEqual((rc, out), (0, ""))

    def test_drift_in_the_vendored_engine_is_detected_and_repaired(self):
        (self.root / sync.CAPY).write_text("# tampered\n", encoding="utf-8")
        rc, out = run_sync(["--check"], self.root)
        self.assertEqual(rc, 1)
        self.assertIn(f"out of sync: {sync.CAPY}", out)
        run_sync([], self.root)
        self.assertEqual((self.root / sync.CAPY).read_bytes(), ENGINE.read_bytes())

    def test_a_missing_vendored_engine_is_created(self):
        (self.root / sync.CAPY).unlink()
        run_sync([], self.root)
        self.assertEqual((self.root / sync.CAPY).read_bytes(), ENGINE.read_bytes())

    def test_a_new_engine_version_reaches_the_copy(self):
        engine = (self.root / sync.ENGINE).resolve()
        engine.write_text(engine.read_text(encoding="utf-8") + "# a newer engine\n", encoding="utf-8")
        rc, out = run_sync(["--check"], self.root)
        self.assertEqual(rc, 1)
        run_sync([], self.root)
        self.assertTrue((self.root / sync.CAPY).read_text(encoding="utf-8").endswith("# a newer engine\n"))

    def test_version_bump_propagates_to_the_manifest_and_requires_changelog(self):
        script = self.root / sync.SCRIPT
        script.write_text(script.read_text(encoding="utf-8").replace('VERSION = "0.1.1"', 'VERSION = "9.9.9"'), encoding="utf-8")
        rc, out = run_sync([], self.root)
        self.assertEqual(rc, 1)
        self.assertIn("problem:", out)
        self.assertEqual(json.loads((self.root / sync.PLUGIN).read_text(encoding="utf-8"))["version"], "9.9.9")
        self.assertIn("no '## [9.9.9]' entry", out)

    def test_stale_header_comment_is_reported(self):
        script = self.root / sync.SCRIPT
        script.write_text(script.read_text(encoding="utf-8").replace("# tidy-board 0.1.1 - ", "# tidy-board 0.0.1 - "), encoding="utf-8")
        rc, out = run_sync(["--check"], self.root)
        self.assertEqual(rc, 1)
        self.assertIn("header comment must say 'tidy-board 0.1.1'", out)


class ManualInstallTest(unittest.TestCase):
    def test_install_ships_both_scripts_and_uninstall_removes_them(self):
        import os
        with tempfile.TemporaryDirectory() as home:
            env = {**os.environ, "HOME": home}
            r = subprocess.run(["bash", str(REPO / "install.sh"), "tidy-board"], env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            dest = Path(home, ".claude", "skills", "tidy-board")
            self.assertEqual((dest / "scripts" / "tidy_board.py").read_bytes(), SCRIPT.read_bytes())
            self.assertEqual((dest / "scripts" / "capy_board.py").read_bytes(), ENGINE.read_bytes())
            r = subprocess.run(["bash", str(REPO / "install.sh"), "tidy-board", "--uninstall"], env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertFalse(dest.exists())

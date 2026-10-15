import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import DOC_TRUTH, HANDOFF, ROOT, TODO_SWEEP, load_sync

sync = load_sync()
SCRIPT_FILES = [p for p in (DOC_TRUTH, HANDOFF, TODO_SWEEP) if p.exists()]


def run_sync(argv, root):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = sync.main(argv, root=Path(root))
    return rc, out.getvalue()


def fake_plugin(tmp):
    """A minimal plugin laid out like this one, with only the doc-truth script, so the sync tests do not depend on
    which skills the real plugin has yet."""
    root = Path(tmp) / "plugins" / "housekeeping"
    script = root / sync.SCRIPTS["doc-truth"]
    script.parent.mkdir(parents=True)
    script.write_text('#!/usr/bin/env python3\n# doc-truth 0.1.0 - x\nVERSION = "0.1.0"\n', encoding="utf-8")
    (root / ".claude-plugin").mkdir()
    (root / sync.PLUGIN).write_text(json.dumps({"name": "housekeeping", "version": "0.1.0"}, indent=2) + "\n", encoding="utf-8")
    (root / sync.CHANGELOG).write_text("# Changelog\n\n## [0.1.0] - 2026-01-01\n", encoding="utf-8")
    return root


class RepositoryStateTest(unittest.TestCase):
    def test_plugin_is_in_sync(self):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "sync.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_manifest_version_matches_the_scripts(self):
        manifest = json.loads((ROOT / sync.PLUGIN).read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], sync.plugin_version(ROOT))

    def test_every_script_carries_its_license_and_the_plugin_version(self):
        for script in SCRIPT_FILES:
            with self.subTest(script=script.name):
                head = script.read_text(encoding="utf-8").splitlines()[:6]
                self.assertTrue(head[1].startswith("# "), head[1])
                self.assertIn("# SPDX-License-Identifier: MIT", head)
                self.assertIn("# Copyright (c) 2026 Diogo Winck", head)

    def test_manifest_points_to_the_repository(self):
        manifest = json.loads((ROOT / sync.PLUGIN).read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "housekeeping")
        self.assertEqual(manifest["homepage"], "https://github.com/dvwinck/capybara-toolbox")
        self.assertEqual(manifest["repository"], "https://github.com/dvwinck/capybara-toolbox")


class SyncToolTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = fake_plugin(tmp.name)
        self.script = self.root / sync.SCRIPTS["doc-truth"]

    def bump(self, text):
        self.script.write_text(self.script.read_text(encoding="utf-8").replace('VERSION = "0.1.0"', f'VERSION = "{text}"'), encoding="utf-8")

    def test_a_clean_copy_passes_the_check(self):
        rc, out = run_sync(["--check"], self.root)
        self.assertEqual((rc, out), (0, ""))

    def test_version_bump_propagates_to_the_manifest_and_requires_the_changelog(self):
        self.bump("9.9.9")
        rc, out = run_sync([], self.root)
        self.assertEqual(rc, 1)
        self.assertEqual(json.loads((self.root / sync.PLUGIN).read_text(encoding="utf-8"))["version"], "9.9.9")
        self.assertIn("no '## [9.9.9]' entry", out)

    def test_a_stale_manifest_is_detected_and_repaired(self):
        manifest = self.root / sync.PLUGIN
        manifest.write_text(manifest.read_text(encoding="utf-8").replace('"0.1.0"', '"0.0.1"'), encoding="utf-8")
        rc, out = run_sync(["--check"], self.root)
        self.assertEqual(rc, 1)
        self.assertIn(f"out of sync: {sync.PLUGIN}", out)
        run_sync([], self.root)
        self.assertEqual(run_sync(["--check"], self.root), (0, ""))

    def test_stale_header_comment_is_reported(self):
        self.script.write_text(self.script.read_text(encoding="utf-8").replace("# doc-truth 0.1.0 - ", "# doc-truth 0.0.1 - "), encoding="utf-8")
        rc, out = run_sync(["--check"], self.root)
        self.assertEqual(rc, 1)
        self.assertIn("header comment must say 'doc-truth 0.1.0'", out)

    def test_scripts_that_disagree_are_reported_and_the_highest_version_wins(self):
        other = self.root / sync.SCRIPTS["handoff"]
        other.parent.mkdir(parents=True, exist_ok=True)
        other.write_text('# handoff 0.2.0 - x\nVERSION = "0.2.0"\n', encoding="utf-8")
        rc, out = run_sync(["--check"], self.root)
        self.assertEqual(rc, 1)
        self.assertIn("the scripts disagree on VERSION: doc-truth 0.1.0, handoff 0.2.0", out)
        self.assertEqual(sync.plugin_version(self.root), "0.2.0")

    def test_a_skill_that_is_not_there_yet_is_simply_absent(self):
        self.assertEqual(sorted(sync.present(self.root)), ["doc-truth"])
        self.assertEqual(sync.inputs(self.root), [sync.SCRIPTS["doc-truth"], sync.PLUGIN, sync.CHANGELOG])


if __name__ == "__main__":
    unittest.main()

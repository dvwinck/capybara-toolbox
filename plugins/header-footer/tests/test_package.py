import contextlib
import io
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT, SCRIPT, SKILL, load_sync

sync = load_sync()


def run_sync(argv, root):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = sync.main(argv, root=Path(root))
    return rc, out.getvalue()


class RepositoryStateTest(unittest.TestCase):
    def test_plugin_is_in_sync(self):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "sync.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_script_carries_its_license_and_version(self):
        head = SCRIPT.read_text(encoding="utf-8").splitlines()[:6]
        self.assertTrue(head[1].startswith("# header-footer "), head[1])
        self.assertIn("# SPDX-License-Identifier: MIT", head)
        self.assertIn("# Copyright (c) 2026 Diogo Winck", head)

    def test_manifest_points_to_the_repository(self):
        manifest = json.loads((ROOT / sync.PLUGIN).read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "header-footer")
        self.assertEqual(manifest["homepage"], "https://github.com/dvwinck/capybara-toolbox")

    def test_the_plugin_hook_runs_the_shipped_script_in_isolated_mode(self):
        hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
        command = hooks["UserPromptSubmit"][0]["hooks"][0]["command"]
        self.assertEqual(command, 'python3 -I "${CLAUDE_PLUGIN_ROOT}/' + SCRIPT.relative_to(ROOT).as_posix() + '" header-hook')

    def test_the_skill_names_itself_and_runs_its_script(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        fm = re.match(r"---\nname: (.*)\ndescription: (.*)\n---\n", text)
        self.assertEqual(fm.group(1), "header-footer")
        self.assertIn("/header-footer:header-footer", fm.group(2))
        self.assertIn('python3 -I "${CLAUDE_SKILL_DIR}/scripts/header_footer.py"', text)
        self.assertIn("Base directory for this skill", text)

    def test_the_example_config_uses_only_known_fields(self):
        sys.dont_write_bytecode = True
        from helpers import load_hf
        hf = load_hf()
        example = json.loads((SKILL / "examples" / "header-footer.example.json").read_text(encoding="utf-8"))
        self.assertEqual(set(example), set(hf.DEFAULTS))
        self.assertTrue(set(example["header"]["fields"]) <= set(hf.HEADER_FIELDS))
        self.assertTrue(set(example["footer"]["fields"]) <= set(hf.FOOTER_FIELDS))
        self.assertEqual(set(example["header"]), set(hf.DEFAULTS["header"]))
        self.assertEqual(set(example["footer"]), set(hf.DEFAULTS["footer"]))

    def test_the_script_has_no_machine_specific_path(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertNotRegex(text, r"/Users/[a-z]|/home/[a-z]|/opt/homebrew")


class SyncToolTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        script = self.root / sync.SCRIPT
        script.parent.mkdir(parents=True)
        script.write_text('#!/usr/bin/env python3\n# header-footer 0.1.0 - x\nVERSION = "0.1.0"\n', encoding="utf-8")
        (self.root / ".claude-plugin").mkdir()
        (self.root / sync.PLUGIN).write_text(json.dumps({"name": "header-footer", "version": "0.1.0"}, indent=2) + "\n", encoding="utf-8")
        (self.root / sync.CHANGELOG).write_text("# Changelog\n\n## [0.1.0] - 2026-01-01\n", encoding="utf-8")
        self.script = script

    def test_a_clean_copy_passes_the_check(self):
        self.assertEqual(run_sync(["--check"], self.root), (0, ""))

    def test_version_bump_propagates_and_requires_the_changelog(self):
        self.script.write_text(self.script.read_text(encoding="utf-8").replace('"0.1.0"', '"0.2.0"').replace(" 0.1.0 ", " 0.2.0 "), encoding="utf-8")
        rc, out = run_sync([], self.root)
        self.assertEqual(rc, 1)
        self.assertEqual(json.loads((self.root / sync.PLUGIN).read_text(encoding="utf-8"))["version"], "0.2.0")
        self.assertIn("no '## [0.2.0]' entry", out)

    def test_stale_header_comment_is_reported(self):
        self.script.write_text(self.script.read_text(encoding="utf-8").replace("# header-footer 0.1.0", "# header-footer 0.0.9"), encoding="utf-8")
        rc, out = run_sync(["--check"], self.root)
        self.assertEqual(rc, 1)
        self.assertIn("header comment must say 'header-footer 0.1.0'", out)


if __name__ == "__main__":
    unittest.main()

import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import REPO, ROOT, SKILLS, load_doc_truth, load_engine, load_todo_sweep

dt = load_doc_truth()
ts = load_todo_sweep()
engine = load_engine()


def frontmatter(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    return dict(line.split(": ", 1) for line in m.group(1).splitlines()) if m else {}


class SkillFilesTest(unittest.TestCase):
    def test_every_skill_folder_has_a_skill_file_with_the_matching_name_and_a_description(self):
        for folder in sorted(SKILLS.iterdir()):
            with self.subTest(skill=folder.name):
                fm = frontmatter((folder / "SKILL.md").read_text(encoding="utf-8"))
                self.assertEqual(fm.get("name"), folder.name)
                self.assertIn(f"/housekeeping:{folder.name}", fm.get("description", ""))
                self.assertGreater(len(fm["description"]), 80)

    def test_every_skill_runs_its_script_from_the_skill_folder_in_isolated_mode(self):
        for folder in sorted(SKILLS.iterdir()):
            with self.subTest(skill=folder.name):
                text = (folder / "SKILL.md").read_text(encoding="utf-8")
                scripts = sorted(p.name for p in (folder / "scripts").glob("*.py") if p.name != "capy_board.py")
                self.assertEqual(len(scripts), 1, scripts)
                self.assertIn('python3 -I "${CLAUDE_SKILL_DIR}/scripts/' + scripts[0], text)
                self.assertIn("Base directory for this skill", text)

    def test_the_examples_are_valid(self):
        cfg = SKILLS / "doc-truth" / "examples" / "doc-truth.example.json"
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(set(json.loads(cfg.read_text(encoding="utf-8"))), set(dt.CONFIG_KEYS))
            loaded = dt.load_config(tmp, str(cfg))
            self.assertIn("docs/plans/**", loaded["exclude"])


    def test_the_todo_sweep_examples_agree_with_each_other_and_the_real_engine(self):
        examples = SKILLS / "todo-sweep" / "examples"
        batch = json.loads((examples / "batch.example.json").read_text(encoding="utf-8"))
        scan = json.loads((examples / "scan.example.json").read_text(encoding="utf-8"))
        self.assertEqual(engine.validate(batch), [])
        self.assertEqual(ts.scan_problems(batch, scan), [])
        self.assertEqual(batch["labels"], ts.LABELS)

    def test_the_handoff_example_note_has_a_valid_data_block_and_its_own_citations(self):
        from helpers import load_handoff
        ho = load_handoff()
        text = (SKILLS / "handoff" / "examples" / "note.example.md").read_text(encoding="utf-8")
        self.assertIsNotNone(ho.parse_data(text))
        self.assertEqual([c[0] for c in ho.find_citations(text)], ["file", "commit", "branch", "file", "branch", "file"])
        for section in ho.SECTIONS:
            self.assertIn(f"## {section}", text)


class ManualInstallTest(unittest.TestCase):
    def test_install_ships_every_skill_and_uninstall_removes_them(self):
        import os
        names = sorted(p.name for p in SKILLS.iterdir())
        with tempfile.TemporaryDirectory() as home:
            env = {**os.environ, "HOME": home}
            r = subprocess.run(["bash", str(REPO / "install.sh"), "housekeeping"], env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            installed = Path(home, ".claude", "skills")
            self.assertEqual(sorted(p.name for p in installed.iterdir()), names)
            for folder in SKILLS.iterdir():
                for script in (folder / "scripts").glob("*.py"):
                    self.assertEqual((installed / folder.name / "scripts" / script.name).read_bytes(), script.read_bytes())
            r = subprocess.run(["bash", str(REPO / "install.sh"), "housekeeping", "--uninstall"], env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(list(installed.iterdir()), [])


class RepositoryDocsTest(unittest.TestCase):
    def test_the_repository_documents_tell_the_truth(self):
        """doc-truth on its own home: `git add` new documents first, the check judges the git tree."""
        result = dt.run(REPO, dt.load_config(REPO))
        report = dt.report(result)
        self.assertEqual(result["findings"], [], report)
        self.assertGreater(result["documents"], 10)

    def test_the_repository_config_is_valid_and_keeps_history_out(self):
        cfg = dt.load_config(REPO)
        self.assertIn("docs/plans/**", cfg["exclude"])
        self.assertIn("docs/refinements/**", cfg["exclude"])
        self.assertTrue((REPO / dt.CONFIG_NAME).exists())


if __name__ == "__main__":
    unittest.main()

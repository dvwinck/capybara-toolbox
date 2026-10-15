import json
import re
import unittest

from helpers import SKILL_DIR, load_capy, tb

capy = load_capy()
SKILL = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
EXAMPLES = SKILL_DIR / "examples"


class SkillTest(unittest.TestCase):
    def test_the_skill_declares_its_name_and_both_triggers(self):
        front = SKILL.split("---")[1]
        self.assertRegex(front, r"(?m)^name: tidy-board$")
        self.assertIn("/tidy-board", front)
        self.assertIn("tidy my branches", front)

    def test_every_command_runs_a_bundled_script_in_isolated_mode(self):
        commands = re.findall(r"(?m)^python3 (.*)$", SKILL)
        self.assertGreaterEqual(len(commands), 7)
        for c in commands:
            self.assertTrue(c.startswith('-I "${CLAUDE_SKILL_DIR}/scripts/'), c)
        self.assertIn("capy_board.py", SKILL)
        self.assertIn("tidy_board.py", SKILL)

    def test_the_skill_documents_every_subcommand_and_never_tells_the_agent_to_delete_by_hand(self):
        for sub in ("scan", "check", "apply", "restore", "--dry-run"):
            self.assertIn(sub, SKILL)
        self.assertIn("Never** run `git branch -D`", SKILL)

    def test_the_skill_always_simulates_before_applying(self):
        # the panel's counters cannot show what the group card covers: only the dry run can
        self.assertIn("**always** simulate first", SKILL)
        self.assertLess(SKILL.index("--dry-run"), SKILL.rindex("tidy_board.py\" apply <pasta>"))

    def test_the_skill_says_restore_needs_a_backup_and_apply_asks_gh_again_for_p2(self):
        self.assertIn("**only for items with a backup**", SKILL)
        self.assertIn("P2 is checked again with `gh`", SKILL)

    def test_the_skill_prepares_the_user_for_the_conclude_dialog(self):
        self.assertIn("Concluir mesmo assim?", SKILL)

    def test_the_skill_names_the_proof_levels_and_what_is_never_offered(self):
        for level in ("P1", "P2", "P3", "P4"):
            self.assertIn(f"**{level}**", SKILL)
        self.assertIn("Never offered", SKILL)

    def test_every_script_option_the_skill_mentions_exists(self):
        parser_help = tb.parser().format_help()
        for flag in ("scan", "check", "apply", "restore"):
            self.assertIn(flag, parser_help)


class DocumentedExampleTest(unittest.TestCase):
    batch = json.loads((EXAMPLES / "batch.example.json").read_text(encoding="utf-8"))
    scan = json.loads((EXAMPLES / "scan.example.json").read_text(encoding="utf-8"))

    def test_the_example_batch_is_accepted_by_the_engine_check(self):
        self.assertEqual(capy.validate(self.batch), [])

    def test_the_example_pair_passes_the_tool_check(self):
        self.assertEqual(tb.scan_problems(self.batch, self.scan), [])

    def test_the_example_matches_what_scan_writes(self):
        self.assertEqual(self.batch["labels"], tb.LABELS)
        risky = {c["id"] for c in self.batch["items"] if "confirm" in c}
        self.assertEqual(risky, {e["id"] for e in self.scan["items"] if e["proof"] in tb.RISKY_PROOFS})

    def test_the_example_leaks_no_home_path(self):
        text = (EXAMPLES / "scan.example.json").read_text(encoding="utf-8")
        self.assertNotIn("/Users/", text)
        self.assertNotIn("/home/", text)

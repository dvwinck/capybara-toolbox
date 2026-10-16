import json
import tempfile
import unittest
from datetime import datetime

from helpers import ConfigDirCase, git_repo

NOW = datetime(2026, 10, 16, 9, 5, 7)  # a Friday


class RenderHeaderTest(ConfigDirCase):
    def header(self, **over):
        h = dict(self.hf.DEFAULTS["header"])
        h.update(over)
        return h

    def test_default_is_the_icon_and_the_time(self):
        self.assertEqual(self.hf.render_header(self.header(), "/tmp", NOW), "🕐 09:05")

    def test_fields_keep_their_order_and_skip_the_empty_ones(self):
        h = self.header(fields=["weekday", "branch", "date", "time"], date_format="%d/%m")
        # /nonexistent is no git repository, so branch is empty and leaves no double separator
        self.assertEqual(self.hf.render_header(h, "/nonexistent", NOW), "🕐 sex · 16/10 · 09:05")

    def test_branch_and_repo_come_from_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = git_repo(tmp, branch="feat/x")
            h = self.header(fields=["repo", "branch"], icon="")
            self.assertEqual(self.hf.render_header(h, str(repo), NOW), f"{repo.resolve().name} · feat/x")

    def test_time_format_and_separator_are_configurable(self):
        h = self.header(fields=["time", "dir"], time_format="%H:%M:%S", separator=" | ", icon="⏱")
        self.assertEqual(self.hf.render_header(h, "/a/b/project/", NOW), "⏱ 09:05:07 | project")

    def test_nothing_to_show_gives_an_empty_line(self):
        self.assertEqual(self.hf.render_header(self.header(fields=["branch"]), "/nonexistent", NOW), "")


class HeaderHookTest(ConfigDirCase):
    def payload(self, prompt="hi"):
        return json.dumps({"session_id": "s1", "prompt": prompt, "cwd": "/nonexistent"})

    def test_injects_the_tag_and_the_instruction(self):
        out = self.hf.header_hook(self.payload(), now=NOW)
        self.assertTrue(out.startswith("<reply-header>🕐 09:05</reply-header>\n"))
        self.assertIn(self.hf.INSTRUCTION, out)

    def test_the_same_prompt_prints_only_once(self):
        # plugin hook + an old settings.json hook both run for one prompt; only one header may appear
        self.assertNotEqual(self.hf.header_hook(self.payload(), now=NOW), "")
        self.assertEqual(self.hf.header_hook(self.payload(), now=NOW), "")
        self.assertNotEqual(self.hf.header_hook(self.payload("next prompt"), now=NOW), "")

    def test_disabled_header_prints_nothing(self):
        self.write_config({"header": {"enabled": False}})
        self.assertEqual(self.hf.header_hook(self.payload(), now=NOW), "")

    def test_a_broken_config_or_payload_still_gives_the_default_header(self):
        (self.home / "header-footer.json").write_text("{not json", encoding="utf-8")
        out = self.hf.header_hook("not json either", now=NOW)
        self.assertIn("<reply-header>🕐 09:05</reply-header>", out)

    def test_cli_entry_point(self):
        rc, out, _ = self.run_cli("header-hook", stdin=self.payload())
        self.assertEqual(rc, 0)
        self.assertIn("<reply-header>", out)


if __name__ == "__main__":
    unittest.main()

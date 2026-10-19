import json
import tempfile
import unittest
from datetime import datetime
from unittest import mock

from helpers import ConfigDirCase, WindowsDatetime, git_repo, run_like_a_windows_pipe

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

    def test_a_format_the_platform_rejects_falls_back_to_the_default(self):
        now = WindowsDatetime(2026, 10, 16, 9, 5, 7)
        self.assertEqual(self.hf.render_header(self.header(time_format="%-H:%M"), "/x", now), "🕐 09:05")

    def test_nothing_to_show_gives_an_empty_line(self):
        self.assertEqual(self.hf.render_header(self.header(fields=["branch"]), "/nonexistent", NOW), "")


class HeaderHookTest(ConfigDirCase):
    def payload(self, prompt="hi", **extra):
        return json.dumps({"session_id": "s1", "prompt": prompt, "cwd": "/nonexistent", **extra})

    def test_injects_the_tag_and_the_instruction(self):
        out = self.hf.header_hook(self.payload(), now=NOW)
        self.assertTrue(out.startswith("<reply-header>🕐 09:05</reply-header>\n"))
        self.assertIn(self.hf.INSTRUCTION, out)

    def test_the_same_prompt_prints_only_once(self):
        # plugin hook + an old settings.json hook both run for one prompt; only one header may appear
        self.assertNotEqual(self.hf.header_hook(self.payload(), now=NOW), "")
        self.assertEqual(self.hf.header_hook(self.payload(), now=NOW), "")
        self.assertNotEqual(self.hf.header_hook(self.payload("next prompt"), now=NOW), "")

    def test_a_repeated_prompt_with_a_new_prompt_id_prints_again(self):
        # "sim" sent twice is two submissions; prompt_id tells them apart
        self.assertNotEqual(self.hf.header_hook(self.payload("sim", prompt_id="p1"), now=NOW), "")
        self.assertNotEqual(self.hf.header_hook(self.payload("sim", prompt_id="p2"), now=NOW), "")
        self.assertEqual(self.hf.header_hook(self.payload("sim", prompt_id="p2"), now=NOW), "")

    def test_without_prompt_id_a_grown_transcript_marks_a_new_submission(self):
        transcript = self.home / "t.jsonl"
        transcript.write_text("{}\n", encoding="utf-8")
        payload = lambda: self.payload("sim", transcript_path=str(transcript))
        self.assertNotEqual(self.hf.header_hook(payload(), now=NOW), "")
        self.assertEqual(self.hf.header_hook(payload(), now=NOW), "")  # the parallel copy of the same submission
        with transcript.open("a", encoding="utf-8") as fh:
            fh.write('{"type": "assistant"}\n')
        self.assertNotEqual(self.hf.header_hook(payload(), now=NOW), "")

    def test_disabled_header_prints_nothing(self):
        self.write_config({"header": {"enabled": False}})
        self.assertEqual(self.hf.header_hook(self.payload(), now=NOW), "")

    def test_a_broken_config_or_payload_still_gives_the_default_header(self):
        (self.home / "header-footer.json").write_text("{not json", encoding="utf-8")
        out = self.hf.header_hook("not json either", now=NOW)
        self.assertIn("<reply-header>🕐 09:05</reply-header>", out)

    def test_a_wrongly_typed_config_value_falls_back_to_its_default(self):
        bad = [{"fields": None}, {"fields": "time"}, {"fields": [1]}, {"separator": 3}, {"icon": None}, {"enabled": "no"}]
        for i, header in enumerate(bad):
            with self.subTest(header=header):
                self.write_config({"header": header})
                out = self.hf.header_hook(self.payload(f"p{i}"), now=NOW)
                self.assertIn("<reply-header>🕐 09:05</reply-header>", out)

    def test_a_windows_code_page_pipe_still_gets_utf8(self):
        done = run_like_a_windows_pipe(self.home, "header-hook", stdin=self.payload("olá, ação 🙂"))
        self.assertEqual(done.returncode, 0, done.stderr.decode("utf-8", "replace"))
        self.assertIn("<reply-header>🕐 ", done.stdout.decode("utf-8"))

    def test_cli_entry_point(self):
        rc, out, _ = self.run_cli("header-hook", stdin=self.payload())
        self.assertEqual(rc, 0)
        self.assertIn("<reply-header>", out)


if __name__ == "__main__":
    unittest.main()

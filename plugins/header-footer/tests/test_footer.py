import json
import os
import unittest
from datetime import datetime
from pathlib import Path

from helpers import ConfigDirCase, strip_ansi

NOW = datetime(2026, 10, 16, 14, 7)


def assistant(mid, inp, out, cache_read=0):
    return json.dumps({"type": "assistant", "message": {"id": mid, "usage": {
        "input_tokens": inp, "output_tokens": out, "cache_read_input_tokens": cache_read}}}) + "\n"


class FooterTest(ConfigDirCase):
    def render(self, data, fields=None, separator=" │ "):
        footer = {"enabled": True, "fields": fields or ["tokens", "limits", "clock"], "separator": separator}
        return strip_ansi(self.hf.render_footer(json.dumps(data), now=NOW, footer=footer))

    def test_fields_render_in_the_configured_order(self):
        data = {"model": {"display_name": "Opus"}, "workspace": {"current_dir": "/x/proj"},
                "context_window": {"remaining_percentage": 62.5}, "cost": {"total_cost_usd": 1.845}}
        self.assertEqual(self.render(data, ["clock", "model", "dir", "context", "cost"]),
                         "14:07 │ Opus │ proj │ ctx 38% │ $1.84")

    def test_missing_data_and_unknown_fields_are_skipped(self):
        self.assertEqual(self.render({}, ["tokens", "limits", "nope", "model", "clock"]), "14:07")

    def test_limits_show_both_windows_and_the_reset(self):
        resets = NOW.timestamp() + 2 * 3600 + 13 * 60
        data = {"rate_limits": {"five_hour": {"used_percentage": 37.5, "resets_at": resets},
                                "seven_day": {"used_percentage": 12}}}
        self.assertEqual(self.render(data, ["limits"]), "5h 38%/2h13 7d 12%")

    def test_rounding_matches_the_javascript_footer_it_replaces(self):
        self.assertEqual(self.hf.half_up(2.5), 3)
        self.assertEqual(self.hf.fmt_tokens(2500), "3k")
        self.assertEqual(self.hf.fmt_tokens(1_250_000), "1.2M")

    def test_a_reset_far_away_or_in_the_past_is_not_shown(self):
        self.assertEqual(self.hf.fmt_resets_in(NOW.timestamp() - 5, NOW.timestamp()), "")
        self.assertEqual(self.hf.fmt_resets_in(NOW.timestamp() + 9 * 86400, NOW.timestamp()), "")
        self.assertEqual(self.hf.fmt_resets_in(NOW.timestamp() + 47 * 60, NOW.timestamp()), "47m")

    def test_separator_is_configurable(self):
        data = {"model": {"display_name": "Opus"}}
        self.assertEqual(self.render(data, ["model", "clock"], separator=" · "), "Opus · 14:07")

    def test_gsd_field_is_empty_without_gsd(self):
        self.assertEqual(self.render({}, ["gsd"]), "")

    def test_cli_entry_point_uses_the_config(self):
        self.write_config({"footer": {"fields": ["model"]}})
        rc, out, _ = self.run_cli("footer", stdin=json.dumps({"model": {"display_name": "Opus"}}))
        self.assertEqual((rc, strip_ansi(out)), (0, "Opus"))


class SessionTokensTest(ConfigDirCase):
    def setUp(self):
        super().setUp()
        self.transcript = self.home / "t.jsonl"

    def tokens(self, sid="s1"):
        return self.hf.session_tokens(str(self.transcript), sid)

    def test_sums_the_whole_transcript_and_dedupes_repeated_messages(self):
        self.transcript.write_text(assistant("a", 100, 10, cache_read=900) + assistant("a", 100, 10)
                                   + json.dumps({"type": "user"}) + "\n" + assistant("b", 5, 1), encoding="utf-8")
        self.assertEqual(self.tokens(), (1005, 11))

    def test_reads_only_what_was_appended_and_skips_a_partial_line(self):
        self.transcript.write_text(assistant("a", 100, 10), encoding="utf-8")
        self.assertEqual(self.tokens(), (100, 10))
        with open(self.transcript, "a", encoding="utf-8") as fh:
            fh.write(assistant("b", 1, 1) + '{"type": "assist')
        self.assertEqual(self.tokens(), (101, 11))
        with open(self.transcript, "a", encoding="utf-8") as fh:
            fh.write('ant", "message": {"id": "c", "usage": {"input_tokens": 2, "output_tokens": 2}}}\n')
        self.assertEqual(self.tokens(), (103, 13))

    def test_a_shrunk_transcript_is_read_again_from_the_start(self):
        self.transcript.write_text(assistant("a", 100, 10) + assistant("b", 100, 10), encoding="utf-8")
        self.assertEqual(self.tokens(), (200, 20))
        self.transcript.write_text(assistant("c", 7, 7), encoding="utf-8")
        self.assertEqual(self.tokens(), (7, 7))

    def test_a_hostile_session_id_gets_no_cache_file(self):
        self.transcript.write_text(assistant("a", 1, 1), encoding="utf-8")
        self.assertEqual(self.tokens("../../escape"), (1, 1))
        self.assertFalse((self.home / "escape.json").exists())
        self.assertIsNone(self.hf.token_state_path("a/b"))

    def test_missing_transcript_gives_nothing(self):
        self.assertIsNone(self.hf.session_tokens(str(self.home / "absent.jsonl"), "s1"))


if __name__ == "__main__":
    unittest.main()

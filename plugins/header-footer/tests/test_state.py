import json
import unittest
from datetime import datetime

from helpers import ConfigDirCase, strip_ansi

T0 = 1_800_000_000.0


class StateHookTest(ConfigDirCase):
    def hook(self, event, at, sid="s1"):
        self.hf.state_hook(event, json.dumps({"session_id": sid}), now_ts=at)
        return self.hf.read_state(sid)

    def footer(self, at, sid="s1"):
        footer = {"enabled": True, "fields": ["state"], "separator": " │ "}
        return strip_ansi(self.hf.render_footer(json.dumps({"session_id": sid}), now=datetime.fromtimestamp(at), footer=footer))

    def test_a_turn_runs_until_stop(self):
        self.hook("turn", T0)
        self.assertEqual(self.footer(T0 + 185), "● running 3m")
        self.hook("idle", T0 + 200)
        self.assertEqual(self.footer(T0 + 300), "○ idle")

    def test_a_permission_prompt_waits_and_keeps_the_turn_clock(self):
        self.hook("turn", T0)
        self.assertEqual(self.hook("waiting", T0 + 30), {"state": "waiting", "since": T0})
        self.assertEqual(self.footer(T0 + 40), "◐ waiting")
        self.hook("running", T0 + 90)
        self.assertEqual(self.footer(T0 + 4380), "● running 1h13")

    def test_a_new_turn_restarts_the_clock(self):
        self.hook("turn", T0)
        self.hook("idle", T0 + 10)
        self.hook("turn", T0 + 500)
        self.assertEqual(self.footer(T0 + 545), "● running 45s")

    def test_running_without_a_previous_turn_starts_its_own_clock(self):
        self.assertEqual(self.hook("running", T0), {"state": "running", "since": T0})

    def test_sessions_are_independent_and_unknown_ones_show_nothing(self):
        self.hook("turn", T0, sid="a")
        self.assertEqual(self.footer(T0, sid="b"), "")
        self.assertEqual(self.footer(T0, sid="a"), "● running 0s")

    def test_a_hostile_session_id_writes_nothing(self):
        self.hook("turn", T0, sid="../../escape")
        self.assertFalse(any(self.home.rglob("*escape*")))
        self.assertIsNone(self.hf.state_path("a/b"))
        self.assertIsNone(self.hf.state_path(None))

    def test_bad_input_is_ignored_and_a_bad_event_is_a_usage_error(self):
        self.assertEqual(self.run_cli("state-hook", "turn", stdin="not json")[0], 0)
        rc, _, err = self.run_cli("state-hook", "sleeping", stdin='{"session_id": "s1"}')
        self.assertEqual(rc, 2)
        self.assertIn("sleeping", err)

    def test_cli_entry_point(self):
        self.assertEqual(self.run_cli("state-hook", "turn", stdin='{"session_id": "s1"}')[0], 0)
        self.assertEqual(self.hf.read_state("s1")["state"], "running")


if __name__ == "__main__":
    unittest.main()

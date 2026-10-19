import json
import unittest
from datetime import datetime, timezone

from helpers import ConfigDirCase, strip_ansi

T0 = 1_800_000_000.0


class StateHookTest(ConfigDirCase):
    def hook(self, event, at, sid="s1"):
        self.hf.state_hook(event, json.dumps({"session_id": sid}), now_ts=at)
        return self.hf.read_state(sid)

    def footer(self, at, sid="s1", transcript=None):
        footer = {"enabled": True, "fields": ["state"], "separator": " │ "}
        payload = {"session_id": sid}
        if transcript is not None:
            payload["transcript_path"] = str(transcript)
        return strip_ansi(self.hf.render_footer(json.dumps(payload), now=datetime.fromtimestamp(at), footer=footer))

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

    def test_a_new_turn_prunes_cache_files_older_than_a_week(self):
        import os
        cache = self.hf.cache_dir()
        cache.mkdir(parents=True)
        week = 7 * 86400
        files = {name: cache / name for name in ("state-old.json", "tokens-old.json", "state-new.json", "tokens-new.json", "other-old.json")}
        for name, path in files.items():
            path.write_text("{}", encoding="utf-8")
            age = week + 60 if "old" in name else week - 60
            os.utime(path, (T0 - age, T0 - age))
        self.hook("running", T0)
        self.assertTrue(files["state-old.json"].exists())  # only a new turn prunes
        self.hook("turn", T0)
        self.assertEqual(sorted(p.name for p in cache.iterdir()),
                         ["other-old.json", "state-new.json", "state-s1.json", "tokens-new.json"])

    def test_cli_entry_point(self):
        self.assertEqual(self.run_cli("state-hook", "turn", stdin='{"session_id": "s1"}')[0], 0)
        self.assertEqual(self.hf.read_state("s1")["state"], "running")



def stamp(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class InterruptTest(ConfigDirCase):
    """Stop does not run on Esc and no hook runs on a denied permission; the transcript tells."""

    footer = StateHookTest.footer
    hook = StateHookTest.hook

    def transcript(self, *entries):
        path = self.home / "t.jsonl"
        path.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
        return path

    def user(self, text, at, **extra):
        return {"type": "user", "timestamp": stamp(at), "message": {"role": "user", "content": [{"type": "text", "text": text}]}, **extra}

    def assistant(self, at, **extra):
        return {"type": "assistant", "timestamp": stamp(at), "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}, **extra}

    def test_an_interrupt_after_the_turn_started_shows_idle(self):
        self.hook("turn", T0)
        t = self.transcript(self.assistant(T0 + 5), self.user("[Request interrupted by user]", T0 + 9),
                            {"type": "system", "timestamp": stamp(T0 + 9)})
        self.assertEqual(self.footer(T0 + 60, transcript=t), "○ idle")

    def test_a_denied_permission_shows_idle(self):
        self.hook("turn", T0)
        self.hook("waiting", T0 + 5)
        t = self.transcript(self.user("[Request interrupted by user for tool use]", T0 + 8))
        self.assertEqual(self.footer(T0 + 60, transcript=t), "○ idle")

    def test_an_interrupt_from_an_earlier_turn_is_ignored(self):
        self.hook("turn", T0 + 100)
        t = self.transcript(self.user("[Request interrupted by user]", T0))
        self.assertEqual(self.footer(T0 + 160, transcript=t), "● running 1m")

    def test_work_after_the_interrupt_keeps_running(self):
        self.hook("turn", T0)
        t = self.transcript(self.user("[Request interrupted by user]", T0 + 5), self.assistant(T0 + 9))
        self.assertEqual(self.footer(T0 + 60, transcript=t), "● running 1m")

    def test_a_sidechain_entry_does_not_hide_the_interrupt(self):
        self.hook("turn", T0)
        t = self.transcript(self.user("[Request interrupted by user]", T0 + 5), self.assistant(T0 + 9, isSidechain=True))
        self.assertEqual(self.footer(T0 + 60, transcript=t), "○ idle")

    def test_local_commands_after_the_interrupt_keep_it_idle(self):
        # /context and !git status write user entries but run no UserPromptSubmit hook
        self.hook("turn", T0)
        t = self.transcript(self.user("[Request interrupted by user]", T0 + 5),
                            self.user("<command-name>/context</command-name>", T0 + 20),
                            self.user("<local-command-stdout>ctx</local-command-stdout>", T0 + 20),
                            self.user("<bash-input>git status</bash-input>", T0 + 30),
                            self.user("<bash-stdout>clean</bash-stdout>", T0 + 30))
        self.assertEqual(self.footer(T0 + 60, transcript=t), "○ idle")

    def test_an_interrupt_behind_a_long_non_conversation_tail_is_found(self):
        self.hook("turn", T0)
        filler = [{"type": "attachment", "timestamp": stamp(T0 + 6), "blob": "x" * 7000} for _ in range(10)]
        t = self.transcript(self.user("[Request interrupted by user]", T0 + 5), *filler)
        self.assertEqual(self.footer(T0 + 60, transcript=t), "○ idle")

    def test_a_missing_or_corrupt_transcript_keeps_running(self):
        self.hook("turn", T0)
        self.assertEqual(self.footer(T0 + 60, transcript=self.home / "missing.jsonl"), "● running 1m")
        bad = self.home / "bad.jsonl"
        bad.write_bytes(b"\xff\xfe not json\n{\"type\": \"user\", \"timestamp\": 3}\n")
        self.assertEqual(self.footer(T0 + 60, transcript=bad), "● running 1m")


if __name__ == "__main__":
    unittest.main()

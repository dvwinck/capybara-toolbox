import json
import os
import stat
import unittest

from helpers import ConfigDirCase, strip_ansi


class FieldCommandsTest(ConfigDirCase):
    def test_header_fields_are_validated_and_saved(self):
        rc, out, _ = self.run_cli("header-fields", "date,time")
        self.assertEqual(rc, 0)
        self.assertEqual(self.read_json("header-footer.json")["header"]["fields"], ["date", "time"])
        self.assertTrue(out.startswith("header: "))

    def test_an_unknown_field_is_a_usage_error_and_changes_nothing(self):
        rc, _, err = self.run_cli("header-fields", "time,foo")
        self.assertEqual(rc, 2)
        self.assertIn("foo", err)
        self.assertFalse((self.home / "header-footer.json").exists())

    def test_footer_fields_format_icon_and_separator(self):
        self.assertEqual(self.run_cli("footer-fields", "model,clock")[0], 0)
        self.assertEqual(self.run_cli("header-format", "%d/%m/%Y", "--date")[0], 0)
        self.assertEqual(self.run_cli("header-icon", "")[0], 0)
        self.assertEqual(self.run_cli("separator", "footer", " · ")[0], 0)
        cfg = self.read_json("header-footer.json")
        self.assertEqual(cfg["footer"]["fields"], ["model", "clock"])
        self.assertEqual(cfg["header"]["date_format"], "%d/%m/%Y")
        self.assertEqual(cfg["header"]["icon"], "")
        self.assertEqual(cfg["footer"]["separator"], " · ")

    def test_a_format_without_a_directive_is_refused(self):
        self.assertEqual(self.run_cli("header-format", "HH:MM")[0], 2)

    def test_header_on_off_is_only_the_config_flag(self):
        self.assertEqual(self.run_cli("off", "header")[0], 0)
        self.assertFalse(self.read_json("header-footer.json")["header"]["enabled"])
        self.assertFalse((self.home / "settings.json").exists())

    def test_a_broken_config_is_reported_not_overwritten(self):
        (self.home / "header-footer.json").write_text("{oops", encoding="utf-8")
        rc, _, err = self.run_cli("header-fields", "time")
        self.assertEqual(rc, 2)
        self.assertIn("nao e JSON valido", err)
        self.assertEqual((self.home / "header-footer.json").read_text(encoding="utf-8"), "{oops")

    def test_a_wrongly_typed_config_value_is_a_usage_error_naming_the_key(self):
        self.write_config({"header": {"separator": 3}})
        for cmd in ("status", "preview"):
            with self.subTest(cmd=cmd):
                rc, _, err = self.run_cli(cmd)
                self.assertEqual(rc, 2)
                self.assertIn("header.separator", err)

    def test_bad_commands_are_usage_errors(self):
        for argv in (["nope"], ["on", "middle"], ["on", "footer", "--force"], ["separator", "x", "y"]):
            with self.subTest(argv=argv):
                self.assertEqual(self.run_cli(*argv)[0], 2)


class SettingsWiringTest(ConfigDirCase):
    def write_settings(self, data):
        path = self.home / "settings.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        os.chmod(path, 0o600)
        return path

    def backups(self):
        return sorted(self.home.glob("settings.json.bak-header-footer-*"))

    def test_footer_on_points_to_a_stable_copy_and_keeps_everything_else(self):
        path = self.write_settings({"model": "opus", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "x"}]}]}})
        rc, _, _ = self.run_cli("on", "footer")
        self.assertEqual(rc, 0)
        data = self.read_json("settings.json")
        self.assertEqual(data["model"], "opus")
        self.assertIn("Stop", data["hooks"])
        self.assertIn(str(self.hf.stable_script()), data["statusLine"]["command"])
        self.assertTrue(data["statusLine"]["command"].endswith(" footer"))
        self.assertEqual(self.hf.script_version(self.hf.stable_script()), self.hf.VERSION)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(len(self.backups()), 1)

    def test_a_symlinked_settings_file_stays_a_symlink(self):
        # dotfiles setups link ~/.claude/settings.json to a file kept elsewhere
        target = self.home / "dotfiles" / "settings.json"
        target.parent.mkdir()
        target.write_text(json.dumps({"model": "opus"}), encoding="utf-8")
        os.chmod(target, 0o600)
        (self.home / "settings.json").symlink_to(target)
        self.assertEqual(self.run_cli("on", "footer")[0], 0)
        self.assertTrue((self.home / "settings.json").is_symlink())
        data = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(data["model"], "opus")
        self.assertTrue(self.hf.footer_wired(data))
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)

    def test_footer_on_refuses_to_replace_another_status_line_without_replace(self):
        self.write_settings({"statusLine": {"type": "command", "command": "my-own-line"}})
        rc, _, err = self.run_cli("on", "footer")
        self.assertEqual(rc, 2)
        self.assertIn("my-own-line", err)
        self.assertEqual(self.read_json("settings.json")["statusLine"]["command"], "my-own-line")
        self.assertEqual(self.backups(), [])
        self.assertEqual(self.run_cli("on", "footer", "--replace")[0], 0)
        self.assertTrue(self.hf.footer_wired(self.read_json("settings.json")))

    def test_footer_off_removes_only_its_own_status_line(self):
        self.write_settings({"statusLine": {"type": "command", "command": "my-own-line"}})
        self.assertEqual(self.run_cli("off", "footer")[0], 2)
        self.run_cli("on", "footer", "--replace")
        self.assertEqual(self.run_cli("off", "footer")[0], 0)
        self.assertNotIn("statusLine", self.read_json("settings.json"))

    def test_wire_and_unwire_hooks_touch_only_their_own_entries(self):
        other = {"hooks": [{"type": "command", "command": "keep-me"}]}
        self.write_settings({"hooks": {"UserPromptSubmit": [other], "Stop": [other]}})
        self.assertEqual(self.run_cli("wire-hooks")[0], 0)
        self.assertEqual(self.run_cli("wire-hooks")[0], 0)  # idempotent
        hooks = self.read_json("settings.json")["hooks"]
        for event, modes in self.hf.PLUGIN_HOOKS.items():
            commands = [h["command"] for g in hooks[event] for h in g["hooks"]]
            ours = [c.split('" ', 2)[-1] for c in commands if "header_footer.py" in c]
            self.assertEqual(ours, modes, event)
            matchers = [g.get("matcher") for g in hooks[event] if any("header_footer.py" in h["command"] for h in g["hooks"])]
            self.assertEqual(set(matchers), {self.hf.PLUGIN_HOOK_MATCHERS.get(event)}, event)
        self.assertEqual(hooks["UserPromptSubmit"][0], other)
        self.assertEqual(self.run_cli("unwire-hooks")[0], 0)
        self.assertEqual(self.read_json("settings.json")["hooks"], {"UserPromptSubmit": [other], "Stop": [other]})

    def test_unwire_hooks_drops_empty_hook_sections(self):
        self.write_settings({})
        self.run_cli("wire-hooks")
        self.run_cli("unwire-hooks")
        self.assertEqual(self.read_json("settings.json"), {})


class StatusTest(ConfigDirCase):
    def status(self):
        rc, out, _ = self.run_cli("status", "--json")
        return rc, json.loads(out)

    def test_an_older_header_hook_is_reported_as_a_duplicate(self):
        (self.home / "settings.json").write_text(json.dumps({"hooks": {"UserPromptSubmit": [
            {"hooks": [{"type": "command", "command": "/x/hooks/reply-header.py"}]}]}}), encoding="utf-8")
        self.write_config({"footer": {"enabled": False}})
        rc, st = self.status()
        self.assertEqual(rc, 1)
        self.assertTrue(any("duplicado" in p for p in st["problems"]))

    def test_footer_enabled_but_not_wired_is_reported(self):
        rc, st = self.status()
        self.assertEqual(rc, 1)
        self.assertTrue(any("on footer" in p for p in st["problems"]))

    def test_a_stale_stable_copy_is_reported(self):
        self.run_cli("on", "footer")
        copy = self.hf.stable_script()
        copy.write_text(copy.read_text(encoding="utf-8").replace(f'VERSION = "{self.hf.VERSION}"', 'VERSION = "0.0.1"'), encoding="utf-8")
        rc, st = self.status()
        self.assertEqual(rc, 1)
        self.assertTrue(any("0.0.1" in p for p in st["problems"]))

    def test_a_clean_setup_has_no_problems(self):
        self.write_config({"footer": {"fields": ["clock"]}})
        self.run_cli("on", "footer")
        rc, st = self.status()
        self.assertEqual((rc, st["problems"]), (0, []))
        rc, out, _ = self.run_cli("status")
        self.assertIn("tudo certo", strip_ansi(out))

    def test_preview_and_fields_list(self):
        rc, out, _ = self.run_cli("preview")
        self.assertEqual(rc, 0)
        self.assertIn("header: 🕐 ", out)
        rc, out, _ = self.run_cli("fields")
        for name in list(self.hf.HEADER_FIELDS) + list(self.hf.FOOTER_FIELDS):
            self.assertIn(name, out)


if __name__ == "__main__":
    unittest.main()

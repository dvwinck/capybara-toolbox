import json
import os
import stat
import sys
import unittest
from unittest import mock

from helpers import ConfigDirCase, WindowsDatetime, strip_ansi


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

    def test_a_format_the_platform_rejects_is_refused(self):
        with mock.patch.object(self.hf, "datetime", WindowsDatetime):
            rc, _, err = self.run_cli("header-format", "%-H:%M")
        self.assertEqual(rc, 2)
        self.assertIn("%-H:%M", err)
        self.assertFalse((self.home / "header-footer.json").exists())

    def test_header_on_off_is_only_the_config_flag(self):
        self.assertEqual(self.run_cli("off", "header")[0], 0)
        self.assertFalse(self.read_json("header-footer.json")["header"]["enabled"])
        self.assertFalse((self.home / "settings.json").exists())

    def test_a_broken_config_is_reported_not_overwritten(self):
        (self.home / "header-footer.json").write_text("{oops", encoding="utf-8")
        rc, _, err = self.run_cli("header-fields", "time")
        self.assertEqual(rc, 2)
        self.assertIn("is not valid JSON", err)
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
        self.assertEqual(data["statusLine"]["refreshInterval"], 10)  # state timer, interrupts and clock move without an event
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

    def test_saves_within_one_second_keep_distinct_backups_and_only_the_last_five(self):
        self.write_settings({"model": "opus"})
        self.run_cli("on", "footer")
        self.run_cli("off", "footer")
        self.assertEqual(len(self.backups()), 2)
        for _ in range(5):
            self.run_cli("on", "footer")
        newest = self.backups()[-1].read_text(encoding="utf-8")
        self.assertEqual(len(self.backups()), 5)
        self.assertIn("statusLine", newest)  # the newest backup holds the state before the last save

    def test_a_refused_replace_is_retried(self):
        # Windows refuses to replace a file another process holds open (the footer reading its state)
        real_replace = os.replace
        calls = []

        def flaky(src, dst):
            calls.append(dst)
            if len(calls) < 3:
                raise PermissionError("in use")
            real_replace(src, dst)

        target = self.home / "state.json"
        with mock.patch.object(self.hf.os, "replace", flaky), mock.patch.object(self.hf.time, "sleep"):
            self.hf.atomic_write(target, "{}")
        self.assertEqual(target.read_text(encoding="utf-8"), "{}")
        self.assertEqual(len(calls), 3)

    def test_a_replace_refused_three_times_raises_and_leaves_no_temp_file(self):
        with mock.patch.object(self.hf.os, "replace", side_effect=PermissionError("in use")), \
                mock.patch.object(self.hf.time, "sleep"):
            with self.assertRaises(PermissionError):
                self.hf.atomic_write(self.home / "state.json", "{}")
        self.assertEqual(list(self.home.iterdir()), [])

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


class InterpreterTest(ConfigDirCase):
    """The wired commands must survive an upgrade of the interpreter (Homebrew removes python@3.N)."""

    def test_python3_on_the_path_is_used_when_it_is_this_interpreter(self):
        link = self.home / "bin" / "python3"
        link.parent.mkdir()
        link.symlink_to(os.path.realpath(sys.executable))
        with mock.patch.object(self.hf.shutil, "which", return_value=str(link)):
            self.assertTrue(self.hf.command_for("footer").startswith(f'"{link}" -I "'))

    def test_another_python3_on_the_path_is_not_used(self):
        other = self.home / "python3"
        other.write_text("", encoding="utf-8")
        with mock.patch.object(self.hf.shutil, "which", return_value=str(other)):
            self.assertTrue(self.hf.command_for("footer").startswith(f'"{sys.executable}" -I "'))

    def test_windows_never_looks_up_python3_and_writes_forward_slashes(self):
        # on Windows python3 may be the Store stub, and Git Bash eats backslashes
        which = mock.Mock(return_value="C:\\stub\\python3.exe")
        with mock.patch.object(self.hf.os, "name", "nt"), mock.patch.object(self.hf.sys, "executable", "C:\\Py\\python.exe"), \
                mock.patch.object(self.hf, "stable_script", return_value="D:\\cfg\\header-footer\\header_footer.py"), \
                mock.patch.object(self.hf.shutil, "which", which):
            command = self.hf.command_for("footer")
        which.assert_not_called()
        self.assertEqual(command, '"C:/Py/python.exe" -I "D:/cfg/header-footer/header_footer.py" footer')

    def test_status_reports_a_wired_interpreter_that_no_longer_exists(self):
        gone = "/nonexistent/python@3.14/bin/python3.14"
        script = self.hf.stable_script()
        (self.home / "settings.json").write_text(json.dumps({
            "statusLine": {"type": "command", "command": f'"{gone}" -I "{script}" footer'},
            "hooks": {"Stop": [{"hooks": [{"type": "command", "command": f'"{gone}" -I "{script}" state-hook idle'}]}]},
        }), encoding="utf-8")
        _, out, _ = self.run_cli("status", "--json")
        problems = [p for p in json.loads(out)["problems"] if gone in p]
        self.assertEqual(len(problems), 1, problems)


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
        self.assertTrue(any("comes out twice" in p for p in st["problems"]))

    def header_problems(self, settings, header_on=True):
        (self.home / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
        self.write_config({"header": {"enabled": header_on}})
        return [p for p in self.status()[1]["problems"] if "no hook runs it" in p]

    def test_a_header_with_no_hook_to_drive_it_is_reported(self):
        self.assertEqual(len(self.header_problems({})), 1)
        self.assertEqual(len(self.header_problems({"enabledPlugins": {"header-footer@capybara-toolbox": False}})), 1)

    def test_the_plugin_or_a_wired_hook_drives_the_header(self):
        self.assertEqual(self.header_problems({"enabledPlugins": {"header-footer@capybara-toolbox": True}}), [])
        hook = {"type": "command", "command": self.hf.command_for("header-hook")}
        self.assertEqual(self.header_problems({"hooks": {"UserPromptSubmit": [{"hooks": [hook]}]}}), [])

    def test_a_header_turned_off_needs_no_hook(self):
        self.assertEqual(self.header_problems({}, header_on=False), [])

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
        settings = self.read_json("settings.json")
        settings["enabledPlugins"] = {"header-footer@capybara-toolbox": True}  # what drives the header
        (self.home / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
        rc, st = self.status()
        self.assertEqual((rc, st["problems"]), (0, []))
        rc, out, _ = self.run_cli("status")
        self.assertIn("all good", strip_ansi(out))
        rc, out, _ = self.run_cli("status", "--lang", "pt-BR")
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


# ---------------------------------------------------------------- the language (header-footer 0.4.0)

import ast
import re
from datetime import datetime

from helpers import SCRIPT

FRIDAY = datetime(2026, 10, 16, 9, 5, 7)
HF_PRINTING = ("load_config", "type_name", "state_hook", "load_settings", "collect_status", "preview_header",
               "preview_footer", "print_status", "parse_fields", "toggle", "main", "run_command", "split_lang")
HF_PT_WORDS = {"nao", "valido", "precisa", "objeto", "texto", "lista", "textos", "evento", "estado", "invalido", "antigo",
               "duplicado", "remova", "entrada", "campo", "desconhecido", "ligado", "desligado", "nenhum", "executa",
               "habilitado", "usuario", "projeto", "aponta", "rode", "copia", "versao", "novo", "gravado", "existe",
               "instalado", "sai", "vazio", "linha", "topo", "resposta", "quando", "diagnostico", "tudo", "certo",
               "informe", "menos", "disponiveis", "vale", "proximo", "outra", "troca", "ganha", "deste", "vou", "mao",
               "reinicie", "mudar", "registrados", "removidos", "uso", "formato", "funciona", "plataforma", "comando",
               "erro", "idioma", "padrao", "depois"}


class LanguageTablesTest(ConfigDirCase):
    def test_the_tables_agree_in_both_languages_and_the_messages_are_plain_ascii(self):
        en, pt = self.hf.MSG["en"], self.hf.MSG["pt-BR"]
        self.assertEqual(set(en), set(pt))
        for key in en:
            with self.subTest(key=key):
                self.assertEqual(set(re.findall(r"\{(\w+)\}", en[key])), set(re.findall(r"\{(\w+)\}", pt[key])))
                self.assertTrue(en[key].isascii() and pt[key].isascii(), key)
        for section in ("header", "footer"):
            self.assertEqual(list(self.hf.FIELD_HELP["en"][section]), list(self.hf.FIELD_HELP["pt-BR"][section]))
        self.assertEqual([len(days) for days in self.hf.WEEKDAYS.values()], [7, 7])
        self.assertEqual((pt["s_all_good"], pt["s_diagnosis"]), ("tudo certo", "DIAGNOSTICO"))  # the 0.3.0 output

    def test_no_portuguese_literal_is_left_in_the_functions_that_print(self):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        found = []
        for fn in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in HF_PRINTING):
            body = fn.body[1:] if isinstance(fn.body[0], ast.Expr) and isinstance(fn.body[0].value, ast.Constant) else fn.body
            for node in (n for stmt in body for n in ast.walk(stmt)):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if set(re.split(r"[^a-z]+", node.value.lower())) & HF_PT_WORDS:
                        found.append(f"{fn.name}: {node.value!r}")
        self.assertEqual(found, [], "Portuguese left outside MSG:\n" + "\n".join(found))


class LanguageTest(ConfigDirCase):
    def hook(self, prompt_id):
        payload = json.dumps({"session_id": "s1", "prompt": "hi", "prompt_id": prompt_id, "cwd": "/nonexistent"})
        return self.hf.header_hook(payload, now=FRIDAY)

    def test_the_weekday_follows_the_config_then_capybara_lang_and_the_instruction_stays_english(self):
        self.write_config({"header": {"fields": ["weekday"]}})
        self.assertTrue(self.hook("p1").startswith("<reply-header>🕐 Fri</reply-header>\n"))
        with mock.patch.dict(os.environ, {"CAPYBARA_LANG": "pt-BR"}):
            out = self.hook("p2")
        self.assertTrue(out.startswith("<reply-header>🕐 sex</reply-header>\n"))
        self.assertIn(self.hf.INSTRUCTION, out)  # addressed to the model: English in both languages
        self.write_config({"lang": "en", "header": {"fields": ["weekday"]}})
        with mock.patch.dict(os.environ, {"CAPYBARA_LANG": "pt-BR"}):
            self.assertTrue(self.hook("p3").startswith("<reply-header>🕐 Fri</reply-header>\n"))

    def test_the_footer_is_the_same_in_both_languages(self):
        payload = json.dumps({"model": {"display_name": "Opus"}, "context_window": {"remaining_percentage": 62},
                              "cost": {"total_cost_usd": 1.84}})
        outputs = []
        for lang in ("en", "pt-BR"):
            self.write_config({"lang": lang, "footer": {"fields": ["model", "context", "cost"]}})
            outputs.append(self.run_cli("footer", stdin=payload)[1])
        self.assertEqual(outputs[0], outputs[1])
        self.assertIn("Opus", outputs[0])

    def test_the_lang_command_saves_and_clears_the_config(self):
        rc, out, _ = self.run_cli("lang", "pt-BR")
        self.assertEqual((rc, out), (0, "lang: pt-BR\n"))
        self.assertEqual(self.read_json("header-footer.json")["lang"], "pt-BR")
        self.assertIn("IDIOMA: pt-BR (header-footer.json)", strip_ansi(self.run_cli("status")[1]))
        self.assertIn("  time     hora (header-format)", self.run_cli("fields")[1])
        self.assertIn("  time     time (header-format)", self.run_cli("fields", "--lang", "en")[1])
        rc, out, _ = self.run_cli("lang", "auto")
        self.assertEqual((rc, out), (0, "lang: auto (CAPYBARA_LANG, then en)\n"))
        self.assertNotIn("lang", self.read_json("header-footer.json"))
        rc, _, err = self.run_cli("lang", "pt")
        self.assertEqual((rc, err), (2, "error: usage: lang en|pt-BR|auto\n"))

    def test_a_bad_flag_or_a_bad_config_lang_is_a_usage_error_but_the_hooks_keep_working(self):
        rc, _, err = self.run_cli("status", "--lang", "xx")
        self.assertEqual((rc, err), (2, "error: --lang must be en or pt-BR\n"))
        self.write_config({"lang": "pt", "header": {"fields": ["weekday"]}})
        rc, _, err = self.run_cli("status")
        self.assertEqual(rc, 2)
        self.assertIn("lang must be en or pt-BR", err)
        self.assertTrue(self.hook("p1").startswith("<reply-header>🕐 Fri</reply-header>\n"))

    def test_the_lang_command_can_repair_a_bad_config_lang_and_nothing_else_is_relaxed(self):
        for arg, stored in (("en", "en"), ("auto", None)):
            self.write_config({"lang": "pt_BR"})
            rc, _, err = self.run_cli("lang", arg)
            self.assertEqual((rc, err), (0, ""))
            self.assertEqual(self.read_json("header-footer.json").get("lang"), stored)
        self.write_config({"lang": "pt_BR"})
        self.assertEqual(self.run_cli("status")[0], 2)  # every other command still refuses it
        self.write_config({"lang": "pt_BR", "header": {"fields": None}})
        rc, _, err = self.run_cli("lang", "en")  # a bad field is still refused, and nothing is saved
        self.assertEqual(rc, 2)
        self.assertIn("header.fields", err)
        self.assertEqual(self.read_json("header-footer.json")["lang"], "pt_BR")

    def test_a_bad_capybara_lang_is_a_status_problem_and_nothing_else(self):
        with mock.patch.dict(os.environ, {"CAPYBARA_LANG": "pt_BR"}):
            rc, out, err = self.run_cli("status", "--json")
            self.assertEqual(err, "")
            self.assertTrue(any("CAPYBARA_LANG=pt_BR is not en or pt-BR" in p for p in json.loads(out)["problems"]))
            self.assertEqual(json.loads(out)["lang"], "en")
        self.assertEqual(self.hf.CLI_LANG, "en")  # main() put the default back

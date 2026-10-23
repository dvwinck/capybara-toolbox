#!/usr/bin/env python3
# header-footer 0.4.0 - a header line at the top of every Claude reply and a configurable status-line footer
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Diogo Winck
"""header-footer: the reply header (a line such as "🕐 14:57 · main" at the top of Claude's first
reply of each turn) and the footer (Claude Code's status line), both driven by one config file.

The header is a UserPromptSubmit hook: it renders the line and injects it, together with the
instruction to copy it, as turn context. Claude has no clock and no git of its own, so every value
comes from here; a guessed timestamp is worse than none.

The footer is a status-line command: it renders the configured fields in the configured order.
Its `state` field (running / waiting / idle) is fed by `state-hook`, registered on UserPromptSubmit,
PostToolUse, Notification, PermissionRequest and Stop.
A plugin cannot set `statusLine`, so `on footer` copies this script to a stable place under the
Claude config directory and points `statusLine` there (the plugin cache path changes on every update).

Python 3.9+ standard library only; `git` is optional (branch/repo fields), `node` only for the `gsd` field.

Usage:
  python3 -I header_footer.py header-hook            # UserPromptSubmit hook (stdin: hook payload)
  python3 -I header_footer.py footer                 # status line command (stdin: status-line payload)
  python3 -I header_footer.py state-hook turn|running|waiting|idle   # hooks that feed the `state` field
  python3 -I header_footer.py status [--json]        # what is on, what is wired, what is wrong
  python3 -I header_footer.py on|off header|footer [--replace]
  python3 -I header_footer.py wire-hooks|unwire-hooks     # hooks in settings.json, for installs without the plugin
  python3 -I header_footer.py header-fields time,branch
  python3 -I header_footer.py header-format "%H:%M" [--date]
  python3 -I header_footer.py header-icon "⏱"
  python3 -I header_footer.py footer-fields gsd,tokens,limits,clock
  python3 -I header_footer.py separator header|footer " · "
  python3 -I header_footer.py lang en|pt-BR|auto     # the language of the messages and of the weekday (auto: CAPYBARA_LANG, then en)
  python3 -I header_footer.py preview | fields

Every command except the hooks takes --lang en|pt-BR (default: the config's lang, then CAPYBARA_LANG, then en).
The footer and the instruction to Claude are the same in both languages.

Exit codes: 0 ok, 1 `status` found problems, 2 usage or config error.
"""
import copy
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

VERSION = "0.4.0"

LANGS = ("en", "pt-BR")  # languages of the messages and of the header's weekday; the first is the default
DEFAULT_LANG = "en"
ENV_LANG = "CAPYBARA_LANG"  # one shell-wide default for every Capybara Toolbox script
CLI_LANG = DEFAULT_LANG  # the language of this run's messages, set by main() only

# The help of each field (printed by `fields`), per language. The names are the config's: the same in both.
FIELD_HELP = {
    "en": {
        "header": {
            "time": "time (header-format)",
            "date": "date (header-format --date)",
            "weekday": "weekday: Mon..Sun",
            "dir": "current folder",
            "repo": "name of the git repository",
            "branch": "current git branch",
        },
        "footer": {
            "state": "running Nm while Claude works, waiting while it waits for you, idle when it stops",
            "gsd": "the GSD block (model | task | folder | context), when GSD is installed",
            "model": "model",
            "dir": "current folder",
            "branch": "current git branch",
            "context": "ctx N% used",
            "tokens": "session tokens so far (input and output)",
            "limits": "the plan's 5h/7d windows and the time until they reset",
            "cost": "estimated session cost in US$",
            "clock": "clock HH:MM",
        },
    },
    "pt-BR": {
        "header": {
            "time": "hora (header-format)",
            "date": "data (header-format --date)",
            "weekday": "dia da semana: seg..dom",
            "dir": "pasta atual",
            "repo": "nome do repositorio git",
            "branch": "branch git atual",
        },
        "footer": {
            "state": "running Nm enquanto o Claude trabalha, waiting quando espera voce, idle quando termina",
            "gsd": "bloco do GSD (modelo | tarefa | pasta | contexto), se o GSD estiver instalado",
            "model": "modelo",
            "dir": "pasta atual",
            "branch": "branch git atual",
            "context": "ctx N% usado",
            "tokens": "tokens acumulados da sessao (entrada e saida)",
            "limits": "janelas 5h/7d do plano e o tempo ate zerar",
            "cost": "custo estimado da sessao em US$",
            "clock": "relogio HH:MM",
        },
    },
}
HEADER_FIELDS = FIELD_HELP["en"]["header"]  # the names a header may show
FOOTER_FIELDS = FIELD_HELP["en"]["footer"]  # the names a footer may show

# Every message of the command line (and every `status` problem), in both languages. Same keys and {placeholders}
# in both (a test enforces it); both plain ASCII, so the pt-BR side is the accent-free Portuguese of 0.3.0. The
# footer is not here: it must stay byte-identical to the Node status line it ports, in either language.
MSG = {
    "en": {
        "cfg_json": "{path} is not valid JSON: {exc}", "cfg_obj": "{path} must be a JSON object",
        "cfg_type": "{path}: {key} must be {kind}", "t_bool": "true/false", "t_str": "text", "t_list": "a list of strings",
        "cfg_lang": "{path}: lang must be en or pt-BR",
        "bad_event": "invalid state event: {event} (use {events})",
        "p_legacy": "an older header hook in settings.json ({names}): with the plugin installed the header comes out twice; remove that entry from settings.json",
        "p_field": "unknown {section} field: {field}",
        "p_no_hook": "header on, but no hook runs it: the plugin is not enabled in the user's settings.json and there is no `wire-hooks` (a project settings.json, which status does not read, may still enable the plugin)",
        "p_footer": "footer on in the config, but statusLine does not point to this script: run `on footer`",
        "p_stale": "the copy in {path} is at version {copy}, the plugin at {version}: run `on footer` (or `wire-hooks`) again",
        "absent": "missing",
        "p_python": "the python written into settings.json no longer exists ({interp}): run `on footer` (or `wire-hooks`) again",
        "p_gsd": "the gsd field is configured, but GSD (or node) is not installed: the field comes out empty",
        "p_env": "CAPYBARA_LANG={value} is not en or pt-BR: it is ignored",
        "empty": "(empty)", "on": "on", "off": "off",
        "s_header": "HEADER (the line at the top of the reply)", "s_config": "  config:   {state}  fields={fields}",
        "s_hook": "  hook:     {hook}", "s_plugin_hook": "the plugin's hooks.json (when installed from the marketplace)",
        "s_footer": "FOOTER (status line)", "s_wiring": "  wiring:   {wiring}", "s_wired": "statusLine points to this script",
        "s_diagnosis": "DIAGNOSIS", "s_all_good": "all good", "s_lang": "LANGUAGE: {lang} ({source})",
        "src_flag": "--lang", "src_config": "header-footer.json", "src_env": "CAPYBARA_LANG", "src_default": "default",
        "no_field": "give at least one {section} field",
        "bad_fields": "unknown {section} field(s): {bad}. Available: {known}",
        "header_toggled": "header: {state} (takes effect on the next prompt)",
        "foreign_line": "another statusLine already exists ({command}); use `on footer --replace` to replace it (settings.json gets a backup)",
        "not_ours": "the current statusLine is not this script's; I will not remove it (edit settings.json by hand)",
        "footer_toggled": "footer: {state} (settings.json backed up; restart Claude Code if it does not change)",
        "hooks_wired": "hooks registered in settings.json (backed up): {events}",
        "hooks_unwired": "hooks removed from settings.json (backed up): {events}",
        "format_usage": 'usage: header-format "%H:%M" [--date]',
        "format_bad": "the format {fmt} does not work on this platform (on Windows, %-H does not exist)",
        "lang_usage": "usage: lang en|pt-BR|auto", "lang_set": "lang: {lang}", "lang_auto": "lang: auto (CAPYBARA_LANG, then en)",
        "bad_flag": "--lang must be en or pt-BR", "bad_command": "invalid command: {command} (use --help)", "error": "error: {e}",
    },
    "pt-BR": {
        "cfg_json": "{path} nao e JSON valido: {exc}", "cfg_obj": "{path} precisa ser um objeto JSON",
        "cfg_type": "{path}: {key} precisa ser {kind}", "t_bool": "true/false", "t_str": "texto", "t_list": "lista de textos",
        "cfg_lang": "{path}: lang precisa ser en ou pt-BR",
        "bad_event": "evento de estado invalido: {event} (use {events})",
        "p_legacy": "hook de header antigo no settings.json ({names}): com o plugin instalado o header sai duplicado; remova essa entrada do settings.json",
        "p_field": "campo de {section} desconhecido: {field}",
        "p_no_hook": "header ligado, mas nenhum hook o executa: o plugin nao esta habilitado no settings.json do usuario e nao ha `wire-hooks` (um settings.json de projeto, que o status nao le, ainda pode habilitar o plugin)",
        "p_footer": "footer ligado na config, mas a statusLine nao aponta para este script: rode `on footer`",
        "p_stale": "a copia em {path} esta na versao {copy}, o plugin na {version}: rode `on footer` (ou `wire-hooks`) de novo",
        "absent": "ausente",
        "p_python": "o python gravado no settings.json nao existe mais ({interp}): rode `on footer` (ou `wire-hooks`) de novo",
        "p_gsd": "campo gsd configurado, mas o GSD (ou o node) nao esta instalado: o campo sai vazio",
        "p_env": "CAPYBARA_LANG={value} nao e en nem pt-BR: fica ignorado",
        "empty": "(vazio)", "on": "ligado", "off": "desligado",
        "s_header": "HEADER (linha no topo da resposta)", "s_config": "  config:   {state}  campos={fields}",
        "s_hook": "  hook:     {hook}", "s_plugin_hook": "hooks.json do plugin (quando instalado pelo marketplace)",
        "s_footer": "FOOTER (status line)", "s_wiring": "  wiring:   {wiring}", "s_wired": "statusLine aponta para este script",
        "s_diagnosis": "DIAGNOSTICO", "s_all_good": "tudo certo", "s_lang": "IDIOMA: {lang} ({source})",
        "src_flag": "--lang", "src_config": "header-footer.json", "src_env": "CAPYBARA_LANG", "src_default": "padrao",
        "no_field": "informe ao menos um campo de {section}",
        "bad_fields": "campo(s) de {section} desconhecido(s): {bad}. Disponiveis: {known}",
        "header_toggled": "header: {state} (vale no proximo prompt)",
        "foreign_line": "ja existe outra statusLine ({command}); use `on footer --replace` para troca-la (o settings.json ganha backup)",
        "not_ours": "a statusLine atual nao e deste script; nao vou remove-la (edite o settings.json a mao)",
        "footer_toggled": "footer: {state} (settings.json com backup; reinicie o Claude Code se nao mudar)",
        "hooks_wired": "hooks registrados no settings.json (com backup): {events}",
        "hooks_unwired": "hooks removidos no settings.json (com backup): {events}",
        "format_usage": 'uso: header-format "%H:%M" [--date]',
        "format_bad": "formato {fmt} nao funciona nesta plataforma (no Windows, %-H nao existe)",
        "lang_usage": "uso: lang en|pt-BR|auto", "lang_set": "lang: {lang}", "lang_auto": "lang: auto (CAPYBARA_LANG, depois en)",
        "bad_flag": "--lang precisa ser en ou pt-BR", "bad_command": "comando invalido: {command} (use --help)", "error": "erro: {e}",
    },
}


def env_lang():
    """CAPYBARA_LANG when it is exactly one of LANGS, else None. A bad value never breaks a hook or a command;
    `status` lists it as a problem."""
    value = os.environ.get(ENV_LANG)
    return value if value in LANGS else None


def pick_lang(*candidates):
    """The first candidate that is one of LANGS (--lang, then the config's lang), then CAPYBARA_LANG, then en."""
    for cand in candidates:
        if isinstance(cand, str) and cand in LANGS:
            return cand
    return env_lang() or DEFAULT_LANG


def say(msg_id, /, **values):
    """One message in the language of this run. The template is ours, the values are data."""
    return MSG[CLI_LANG][msg_id].format(**values)
DEFAULTS = {
    "header": {
        "enabled": True,
        "icon": "🕐",
        "fields": ["time"],
        "separator": " · ",
        "time_format": "%H:%M",
        "date_format": "%d/%m",
    },
    "footer": {
        "enabled": True,
        "fields": ["state", "tokens", "limits", "clock"],
        "separator": " │ ",
    },
}
WEEKDAYS = {"en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], "pt-BR": ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]}
# The instruction is addressed to the model, not to the user: it is English whatever the language.
INSTRUCTION = (
    "Start your first reply of this turn with the text inside <reply-header>, verbatim, on a line "
    "of its own. Do not estimate, complete or reformat it."
)
# Markers live this long; the header hook only needs them to recognise the parallel copy of one
# submission, which runs within the 5 s hook timeout.
MARKER_TTL = 60
SEEN_IDS_KEPT = 200
# Per-session state and token files older than this are pruned when a turn starts.
CACHE_TTL = 7 * 86400
STATE_EVENTS = ("turn", "running", "waiting", "idle")
# The hooks the plugin registers (hooks/hooks.json) and that `wire-hooks` writes into settings.json
# for installs without the plugin system: event -> subcommands. PostToolUse brings "waiting" back to
# "running" after a permission prompt.
PLUGIN_HOOKS = {
    "UserPromptSubmit": ["header-hook", "state-hook turn"],
    "PostToolUse": ["state-hook running"],
    "Notification": ["state-hook waiting"],
    "PermissionRequest": ["state-hook waiting"],
    "Stop": ["state-hook idle"],
}  # duplicate transcript entries sit adjacent, so a short ring of ids dedupes them
# Only these notifications mean Claude waits for you; idle_prompt (about 60 s after a turn ends) and
# auth_success must not turn "idle" into "waiting".
PLUGIN_HOOK_MATCHERS = {"Notification": "permission_prompt|elicitation_dialog|elicitation_url_dialog"}

# Seconds between status line runs without an event, so the running timer, an interrupt and the clock move.
FOOTER_REFRESH = 10

DIM = "\x1b[2m"
RESET = "\x1b[0m"


class UsageError(Exception):
    pass


# --- paths and config -----------------------------------------------------------

def claude_dir():
    """Claude Code's config directory: CLAUDE_CONFIG_DIR when set, as Claude Code itself does."""
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def config_path():
    return claude_dir() / "header-footer.json"


def settings_path():
    return claude_dir() / "settings.json"


def stable_script():
    return claude_dir() / "header-footer" / "header_footer.py"


def cache_dir():
    return claude_dir() / "cache" / "header-footer"


def gsd_script():
    return claude_dir() / "hooks" / "gsd-statusline.js"


def load_config(path=None, strict=False):
    """The config merged over DEFAULTS. A broken file is an error only when `strict` (the CLI); the
    hooks fall back to the defaults so a typo never blanks the header or the footer."""
    path = Path(path or config_path())
    cfg = copy.deepcopy(DEFAULTS)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return cfg
    except (OSError, ValueError) as exc:
        if strict:
            raise UsageError(say("cfg_json", path=path, exc=exc))
        return cfg
    if not isinstance(raw, dict):
        if strict:
            raise UsageError(say("cfg_obj", path=path))
        return cfg
    for section in DEFAULTS:
        if not isinstance(raw.get(section), dict):
            continue
        for key, value in raw[section].items():
            if key in DEFAULTS[section] and not same_type(value, DEFAULTS[section][key]):
                if strict:
                    raise UsageError(say("cfg_type", path=path, key=f"{section}.{key}", kind=type_name(DEFAULTS[section][key])))
                continue
            cfg[section][key] = value
    lang = raw.get("lang")  # top level, optional: the language of the header's weekday and of the messages
    if lang in LANGS:
        cfg["lang"] = lang
    elif lang is not None and strict:
        raise UsageError(say("cfg_lang", path=path))
    return cfg


def same_type(value, default):
    """The config keeps the shape of DEFAULTS: bool, str or a list of str."""
    if isinstance(default, list):
        return isinstance(value, list) and all(isinstance(v, str) for v in value)
    return type(value) is type(default)


def type_name(default):
    return say({bool: "t_bool", str: "t_str", list: "t_list"}[type(default)])


REPLACE_ATTEMPTS = 3
SETTINGS_BACKUPS_KEPT = 5


def atomic_write(path, text, mode=None):
    """Write through a private temp file and os.replace, keeping the old file's mode (settings.json is 600).
    A symlink is followed, so a settings.json linked from a dotfiles repository stays a link."""
    path = Path(os.path.realpath(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode is None:
        mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(tmp, mode)
        for attempt in range(REPLACE_ATTEMPTS):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:  # Windows: another process holds the file open
                if attempt == REPLACE_ATTEMPTS - 1:
                    raise
                time.sleep(0.05)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def dump_json(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def save_config(cfg):
    atomic_write(config_path(), dump_json(cfg))


# --- git ------------------------------------------------------------------------

def git(cwd, *args):
    if not cwd:
        return ""
    try:
        out = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=1)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


# --- header ---------------------------------------------------------------------

def format_time(now, header, key):
    """strftime with the configured format, or the default one when this platform rejects it
    (Windows refuses %-H, which macOS and Linux accept)."""
    try:
        return now.strftime(header[key])
    except ValueError:
        return now.strftime(DEFAULTS["header"][key])


def render_header(header, cwd, now, lang=DEFAULT_LANG):
    """The header line, or "" when every field came out empty. Only the weekday depends on `lang`."""
    values = {
        "time": lambda: format_time(now, header, "time_format"),
        "date": lambda: format_time(now, header, "date_format"),
        "weekday": lambda: WEEKDAYS[lang if lang in LANGS else DEFAULT_LANG][now.weekday()],
        "dir": lambda: os.path.basename(str(cwd).rstrip("/")) if cwd else "",
        "repo": lambda: os.path.basename(git(cwd, "rev-parse", "--show-toplevel")),
        "branch": lambda: git(cwd, "branch", "--show-current"),
    }
    parts = [values[f]() for f in header["fields"] if f in values]
    body = header["separator"].join(p for p in parts if p)
    if not body:
        return ""
    return f"{header['icon']} {body}".strip()


def submission_key(payload):
    """What identifies one prompt submission: its prompt_id when Claude Code sends one, else the prompt
    text plus the transcript size (the hook runs before the prompt is written, so both copies of one
    submission see the same size, and any later submission sees a longer transcript)."""
    prompt_id = payload.get("prompt_id")
    if isinstance(prompt_id, str) and prompt_id:
        return [payload.get("session_id"), prompt_id]
    size = None
    transcript = payload.get("transcript_path")
    if isinstance(transcript, str) and transcript:
        try:
            size = os.path.getsize(transcript)
        except OSError:
            pass
    return [payload.get("session_id"), payload.get("prompt"), size]


def first_run(payload, now_ts):
    """True for the first header hook run of this prompt submission. With the plugin hook and a
    settings.json hook both registered, one submission reaches two copies of this script; only one may print."""
    key = json.dumps(submission_key(payload), ensure_ascii=False)
    marker = cache_dir() / ("hdr-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24])
    try:
        cache_dir().mkdir(parents=True, exist_ok=True)
        for old in cache_dir().glob("hdr-*"):
            try:
                if now_ts - old.stat().st_mtime > MARKER_TTL:
                    old.unlink()
            except OSError:
                pass
        if marker.exists() and now_ts - marker.stat().st_mtime <= MARKER_TTL:
            return False
        fd = os.open(str(marker), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        return True
    except FileExistsError:
        return False
    except OSError:
        return True  # no cache directory: a duplicate header beats a missing one


def header_hook(stdin_text, now=None):
    cfg = load_config()
    header = cfg["header"]
    if not header.get("enabled", True):
        return ""
    try:
        payload = json.loads(stdin_text or "{}")
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    now = now or datetime.now()
    line = render_header(header, payload.get("cwd") or os.getcwd(), now, pick_lang(cfg.get("lang")))
    if not line or not first_run(payload, time.time()):
        return ""
    return f"<reply-header>{line}</reply-header>\n{INSTRUCTION}\n"


# --- state (running / waiting / idle) -----------------------------------------------

def session_file(prefix, session_id):
    """A per-session file in the cache directory, or None for a session_id that could escape it."""
    if not isinstance(session_id, str) or not session_id or "/" in session_id or "\\" in session_id or ".." in session_id:
        return None
    return cache_dir() / f"{prefix}-{session_id}.json"


def state_path(session_id):
    return session_file("state", session_id)


def read_state(session_id):
    sp = state_path(session_id)
    if not sp:
        return {}
    try:
        st = json.loads(sp.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return st if isinstance(st, dict) else {}


def prune_cache(now_ts):
    """Drop the state and token files of sessions untouched for CACHE_TTL. A session resumed later
    recounts its tokens from the start of its transcript, which gives the same total."""
    for pattern in ("state-*.json", "tokens-*.json"):
        for old in cache_dir().glob(pattern):
            try:
                if now_ts - old.stat().st_mtime > CACHE_TTL:
                    old.unlink()
            except OSError:
                pass


def state_hook(event, stdin_text, now_ts=None):
    """Record the session's state. `turn` starts the turn's clock; a permission prompt (`waiting`) and
    the tool call after it (`running`) keep it; `idle` restarts it as "idle since"."""
    if event not in STATE_EVENTS:
        raise UsageError(say("bad_event", event=event, events=", ".join(STATE_EVENTS)))
    try:
        payload = json.loads(stdin_text or "{}")
    except ValueError:
        return
    sp = state_path(payload.get("session_id") if isinstance(payload, dict) else None)
    if not sp:
        return
    now_ts = time.time() if now_ts is None else now_ts
    if event == "turn":
        prune_cache(now_ts)
    prev = read_state(payload["session_id"])
    since = prev.get("since")
    if event in ("turn", "idle") or not isinstance(since, (int, float)):
        since = now_ts
    state = {"state": "running" if event in ("turn", "running") else event, "since": since}
    if state == {k: prev.get(k) for k in state}:
        return  # PostToolUse fires on every tool call; skip the write when nothing changed
    try:
        atomic_write(sp, json.dumps(state), mode=0o600)
    except OSError:
        pass


def fmt_elapsed(secs):
    """45s, 3m, 1h12."""
    if secs < 60:
        return f"{max(0, int(secs))}s"
    mins = int(secs // 60)
    if mins < 60:
        return f"{mins}m"
    return f"{mins // 60}h{mins % 60:02d}"


INTERRUPT_MARKER = "[Request interrupted by user"
# The tail read first, and the wider one tried when trailing bookkeeping entries (attachments, file
# snapshots) hide every conversation entry from the first.
TRANSCRIPT_TAILS = (64 * 1024, 1024 * 1024)


def entry_epoch(entry):
    try:
        return datetime.strptime(entry["timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc).timestamp()
    except (KeyError, TypeError, ValueError):
        return None


def interrupt_verdict(tail, since):
    """Walk the tail backwards: True at an interrupt written at or after `since`, False at an older one or
    at Claude's own work (an assistant entry), None when the tail holds neither. Other user entries are
    skipped: local commands (/context, !git status) write them without starting a turn."""
    for raw in reversed(tail.split(b"\n")):
        try:
            entry = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(entry, dict) or entry.get("type") not in ("user", "assistant") or entry.get("isSidechain"):
            continue
        if entry["type"] == "assistant":
            return False
        content = (entry.get("message") or {}).get("content") if isinstance(entry.get("message"), dict) else None
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content
        texts = [b.get("text") for b in blocks or [] if isinstance(b, dict) and isinstance(b.get("text"), str)]
        if any(t.startswith(INTERRUPT_MARKER) for t in texts):
            at = entry_epoch(entry)
            return at is not None and at >= since
    return None


def interrupted_since(transcript_path, since):
    """True when the transcript shows a user interrupt (Esc, or a denied permission) at or after `since`
    with no assistant entry after it. Stop does not run on an interrupt and no hook runs on a manual
    denial, so the transcript is the only witness. Reads only the tail of the file."""
    if not isinstance(transcript_path, str) or not transcript_path or not isinstance(since, (int, float)):
        return False
    for size in TRANSCRIPT_TAILS:
        try:
            with open(transcript_path, "rb") as fh:
                fh.seek(0, os.SEEK_END)
                start = max(0, fh.tell() - size)
                fh.seek(start)
                verdict = interrupt_verdict(fh.read(), since)
        except OSError:
            return False
        if verdict is not None:
            return verdict
        if start == 0:
            break
    return False


def render_state(session_id, now_ts, transcript_path=None):
    st = read_state(session_id)
    since = st.get("since")
    if st.get("state") in ("running", "waiting") and interrupted_since(transcript_path, since):
        return f"{DIM}○ idle{RESET}"
    if st.get("state") == "running":
        elapsed = f" {fmt_elapsed(now_ts - since)}" if isinstance(since, (int, float)) else ""
        return f"\x1b[33m● running{elapsed}{RESET}"
    if st.get("state") == "waiting":
        return f"\x1b[38;5;208m◐ waiting{RESET}"
    if st.get("state") == "idle":
        return f"{DIM}○ idle{RESET}"
    return ""


# --- footer ---------------------------------------------------------------------

def half_up(x):
    """Round half up, like JavaScript's Math.round (Python's round() goes to the even neighbour)."""
    return int(math.floor(x + 0.5))


def fmt_tokens(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{half_up(n / 1000)}k"
    return str(n)


def pct_color(pct):
    if pct < 50:
        return "\x1b[32m"
    if pct < 75:
        return "\x1b[33m"
    if pct < 90:
        return "\x1b[38;5;208m"
    return "\x1b[31m"


def fmt_resets_in(epoch_seconds, now_ts):
    """Minutes-granularity "resets in" label, e.g. 2h13 or 47m."""
    try:
        secs = float(epoch_seconds) - now_ts
    except (TypeError, ValueError):
        return ""
    # The widest real window is 7 days, so anything beyond 8 is bad data.
    if secs <= 0 or secs > 8 * 86400:
        return ""
    mins = half_up(secs / 60)
    if mins < 60:
        return f"{mins}m"
    return f"{mins // 60}h{mins % 60:02d}"


def token_state_path(session_id):
    return session_file("tokens", session_id)


def session_tokens(transcript_path, session_id):
    """Sum input and output tokens over the whole transcript, reading only the bytes appended since the
    last render (the status-line payload carries the current window, not the session total).
    Returns (in, out) or None."""
    if not transcript_path:
        return None
    try:
        size = os.path.getsize(transcript_path)
    except OSError:
        return None
    sp = token_state_path(session_id)
    state = {"offset": 0, "in": 0, "out": 0, "seen": []}
    if sp:
        try:
            prev = json.loads(sp.read_text(encoding="utf-8"))
            if isinstance(prev, dict) and isinstance(prev.get("offset"), int):
                state = prev
        except (OSError, ValueError):
            pass
    if size < state["offset"]:  # compaction or rotation shrank the file
        state = {"offset": 0, "in": 0, "out": 0, "seen": []}
    if size == state["offset"]:
        return state["in"], state["out"]
    try:
        with open(transcript_path, "rb") as fh:
            fh.seek(state["offset"])
            chunk = fh.read(size - state["offset"])
    except OSError:
        return state["in"], state["out"]
    last_nl = chunk.rfind(b"\n")
    if last_nl == -1:  # a partial line is read again next time
        return state["in"], state["out"]
    consumed = chunk[: last_nl + 1]
    seen = list(state.get("seen") or [])
    seen_set = set(seen)
    for raw in consumed.split(b"\n"):
        if not raw:
            continue
        try:
            entry = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(entry, dict) or entry.get("type") != "assistant":
            continue
        msg = entry.get("message")
        if not isinstance(msg, dict) or not isinstance(msg.get("usage"), dict):
            continue
        mid = msg.get("id")
        if mid:  # each assistant message is written to the transcript more than once
            if mid in seen_set:
                continue
            seen_set.add(mid)
            seen.append(mid)
        u = msg["usage"]
        state["in"] += (u.get("input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0)
        state["out"] += u.get("output_tokens") or 0
    state["offset"] += len(consumed)
    state["seen"] = seen[-SEEN_IDS_KEPT:]
    if sp:
        try:
            atomic_write(sp, json.dumps(state), mode=0o600)
        except OSError:
            pass  # best effort: a failed write only means a full re-read next render
    return state["in"], state["out"]


def gsd_block(stdin_text):
    node = shutil.which("node")
    if not node or not gsd_script().exists():
        return ""
    try:
        out = subprocess.run([node, str(gsd_script())], input=stdin_text, capture_output=True, text=True, timeout=2.5)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.rstrip("\n")


def footer_field(name, data, stdin_text, now):
    workspace = data.get("workspace") if isinstance(data.get("workspace"), dict) else {}
    cwd = workspace.get("current_dir") or data.get("cwd") or ""
    if name == "state":
        return render_state(data.get("session_id"), now.timestamp(), data.get("transcript_path"))
    if name == "gsd":
        return gsd_block(stdin_text)
    if name == "model":
        model = data.get("model") if isinstance(data.get("model"), dict) else {}
        return model.get("display_name") or ""
    if name == "dir":
        return os.path.basename(cwd.rstrip("/")) if cwd else ""
    if name == "branch":
        branch = git(cwd, "branch", "--show-current")
        return f"{DIM}⎇ {branch}{RESET}" if branch else ""
    if name == "context":
        window = data.get("context_window") if isinstance(data.get("context_window"), dict) else {}
        remaining = window.get("remaining_percentage")
        if not isinstance(remaining, (int, float)):
            return ""
        used = half_up(100 - remaining)
        return f"{pct_color(used)}ctx {used}%{RESET}"
    if name == "tokens":
        tok = session_tokens(data.get("transcript_path"), data.get("session_id"))
        if not tok or not any(tok):
            return ""
        return f"{DIM}{fmt_tokens(tok[0])}↑ {fmt_tokens(tok[1])}↓{RESET}"
    if name == "limits":
        rl = data.get("rate_limits") if isinstance(data.get("rate_limits"), dict) else {}
        windows = []
        for label, key in (("5h", "five_hour"), ("7d", "seven_day")):
            w = rl.get(key)
            if not isinstance(w, dict) or not isinstance(w.get("used_percentage"), (int, float)):
                continue
            pct = half_up(w["used_percentage"])
            resets = fmt_resets_in(w.get("resets_at"), now.timestamp()) if w.get("resets_at") else ""
            windows.append(f"{pct_color(pct)}{label} {pct}%{RESET}" + (f"{DIM}/{resets}{RESET}" if resets else ""))
        return " ".join(windows)
    if name == "cost":
        cost = data.get("cost") if isinstance(data.get("cost"), dict) else {}
        usd = cost.get("total_cost_usd")
        return f"{DIM}${usd:.2f}{RESET}" if isinstance(usd, (int, float)) else ""
    if name == "clock":
        return f"{DIM}{now.strftime('%H:%M')}{RESET}"
    return ""


def render_footer(stdin_text, now=None, footer=None):
    footer = footer or load_config()["footer"]
    try:
        data = json.loads(stdin_text or "{}")
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    now = now or datetime.now()
    parts = []
    for name in footer["fields"]:
        try:
            out = footer_field(name, data, stdin_text, now)
        except Exception:  # one broken field must not blank the whole footer
            out = ""
        if out:
            parts.append(out)
    return f"{DIM}{footer['separator']}{RESET}".join(parts)


# --- settings.json wiring -------------------------------------------------------

LEGACY_HEADER_HOOKS = ("reply-header.py", "inject-timestamp.sh")


def load_settings():
    path = settings_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except ValueError as exc:
        raise UsageError(say("cfg_json", path=path, exc=exc))
    if not isinstance(data, dict):
        raise UsageError(say("cfg_obj", path=path))
    return data


def save_settings(data):
    path = settings_path()
    if path.exists():
        backup = path.with_name(f"{path.name}.bak-header-footer-{datetime.now().strftime('%Y%m%d%H%M%S%f')}")
        shutil.copy2(str(path), str(backup))
        # names sort by time (copy2 keeps the source's mtime, so mtime cannot order them)
        for old in sorted(path.parent.glob(f"{path.name}.bak-header-footer-*"))[:-SETTINGS_BACKUPS_KEPT]:
            try:
                old.unlink()
            except OSError:
                pass
    atomic_write(path, dump_json(data))


def prompt_hook_commands(settings):
    """Every UserPromptSubmit command, as (group index, hook index, command)."""
    found = []
    groups = (settings.get("hooks") or {}).get("UserPromptSubmit") or []
    for gi, group in enumerate(groups):
        for hi, hook in enumerate(group.get("hooks") or []):
            found.append((gi, hi, hook.get("command", "")))
    return found


def is_ours(command):
    return "header_footer.py" in command


def install_stable_copy():
    """Copy this script to a path that survives plugin updates; settings.json points there."""
    target = stable_script()
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(Path(__file__).resolve()), str(target))
    return target


def interpreter():
    """The python to write into settings.json. sys.executable can be a versioned path that an upgrade
    removes (Homebrew's python@3.N), so prefer python3 on the PATH when it is this same interpreter.
    Not on Windows, where python3 may be the Microsoft Store stub."""
    if os.name != "nt":
        found = shutil.which("python3")
        if found and os.path.realpath(found) == os.path.realpath(sys.executable):
            return found
    return sys.executable


def shell_path(path):
    """Forward slashes on Windows: Git Bash, which runs hook and status line commands there, eats backslashes."""
    return str(path).replace("\\", "/") if os.name == "nt" else str(path)


def command_for(mode):
    return f'"{shell_path(interpreter())}" -I "{shell_path(stable_script())}" {mode}'


def command_interpreter(command):
    """The quoted interpreter path that command_for writes, or None for any other command shape."""
    if command.startswith('"') and '"' in command[1:]:
        return command[1:].split('"', 1)[0]
    return None


def our_commands(settings):
    """Every command of this script in settings.json: the status line and the hooks of every event."""
    commands = [(settings.get("statusLine") or {}).get("command", "")]
    for groups in (settings.get("hooks") or {}).values():
        for group in groups or []:
            commands += [h.get("command", "") for h in group.get("hooks") or []]
    return [c for c in commands if is_ours(c)]


def wire_hooks(settings, on):
    """Remove every hook of this script from settings.json and, when `on`, add the PLUGIN_HOOKS set."""
    hooks = settings.setdefault("hooks", {})
    for event, modes in PLUGIN_HOOKS.items():
        groups = hooks.setdefault(event, [])
        for group in groups:
            group["hooks"] = [h for h in group.get("hooks") or [] if not is_ours(h.get("command", ""))]
        groups[:] = [g for g in groups if g["hooks"]]
        if on:
            for mode in modes:
                group = {"hooks": [{"type": "command", "command": command_for(mode), "timeout": 5}]}
                if event in PLUGIN_HOOK_MATCHERS:
                    group = {"matcher": PLUGIN_HOOK_MATCHERS[event], **group}
                groups.append(group)
        if not groups:
            del hooks[event]
    if not hooks:
        del settings["hooks"]


def footer_wired(settings):
    return is_ours((settings.get("statusLine") or {}).get("command", ""))


def script_version(path):
    try:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if line.startswith('VERSION = "'):
                return line.split('"')[1]
    except OSError:
        pass
    return None


# --- status ---------------------------------------------------------------------

def collect_status(cfg, settings):
    commands = [cmd for _, _, cmd in prompt_hook_commands(settings)]
    legacy = [cmd for cmd in commands if any(name in cmd for name in LEGACY_HEADER_HOOKS)]
    status_line = settings.get("statusLine") or {}
    copy_version = script_version(stable_script())
    problems = []
    if legacy:
        problems.append(say("p_legacy", names=", ".join(sorted({n for n in LEGACY_HEADER_HOOKS if any(n in c for c in legacy)}))))
    for section, known in (("header", HEADER_FIELDS), ("footer", FOOTER_FIELDS)):
        for f in cfg[section]["fields"]:
            if f not in known:
                problems.append(say("p_field", section=section, field=f))
    plugin_on = any(v is True and k.startswith("header-footer@") for k, v in (settings.get("enabledPlugins") or {}).items())
    header_wired = any(is_ours(c) and c.endswith(" header-hook") for c in commands)
    if cfg["header"]["enabled"] and not (plugin_on or header_wired):
        problems.append(say("p_no_hook"))
    if cfg["footer"]["enabled"] and not footer_wired(settings):
        problems.append(say("p_footer"))
    uses_copy = footer_wired(settings) or any(is_ours(c) for c in commands)
    if uses_copy and copy_version != VERSION:
        problems.append(say("p_stale", path=stable_script(), copy=copy_version or say("absent"), version=VERSION))
    gone = sorted({i for i in map(command_interpreter, our_commands(settings)) if i and not os.path.exists(i)})
    for interp in gone:
        problems.append(say("p_python", interp=interp))
    if "gsd" in cfg["footer"]["fields"] and not (gsd_script().exists() and shutil.which("node")):
        problems.append(say("p_gsd"))
    raw_env = os.environ.get(ENV_LANG)
    if raw_env is not None and raw_env not in LANGS:  # ignored everywhere; this is where the person learns why
        problems.append(say("p_env", value=raw_env))
    return {
        "version": VERSION,
        "config": str(config_path()),
        "lang": CLI_LANG,
        "header": {
            "enabled": cfg["header"]["enabled"],
            "fields": cfg["header"]["fields"],
            "settings_hook": any(is_ours(c) for c in commands),
            "legacy_hooks": legacy,
        },
        "footer": {
            "enabled": cfg["footer"]["enabled"],
            "fields": cfg["footer"]["fields"],
            "wired": footer_wired(settings),
            "status_line": status_line.get("command"),
        },
        "stable_copy": {"path": str(stable_script()), "version": copy_version},
        "problems": problems,
    }


def sample_footer_payload():
    return json.dumps({
        "session_id": "header-footer-preview",
        "model": {"display_name": "Opus"},
        "workspace": {"current_dir": os.getcwd()},
        "context_window": {"remaining_percentage": 62},
        "cost": {"total_cost_usd": 1.84},
        "rate_limits": {"five_hour": {"used_percentage": 37}, "seven_day": {"used_percentage": 12}},
    })


def preview_header(cfg):
    """The header as the hook renders it now: its weekday follows the config's lang, then CAPYBARA_LANG."""
    return render_header(cfg["header"], os.getcwd(), datetime.now(), pick_lang(cfg.get("lang"))) or say("empty")


def preview_footer(cfg):
    return render_footer(sample_footer_payload(), footer=cfg["footer"]) or say("empty")


def print_status(st, cfg, source="src_default"):
    h, f = st["header"], st["footer"]
    print(say("s_header"))
    print(say("s_config", state=say("on" if h["enabled"] else "off"), fields=",".join(h["fields"])))
    print(say("s_hook", hook="settings.json" if h["settings_hook"] else say("s_plugin_hook")))
    print(f"  preview:  {preview_header(cfg)}")
    print(say("s_footer"))
    print(say("s_config", state=say("on" if f["enabled"] else "off"), fields=",".join(f["fields"])))
    print(say("s_wiring", wiring=say("s_wired") if f["wired"] else "statusLine = " + json.dumps(f["status_line"])))
    print(f"  preview:  {preview_footer(cfg)}")
    print(say("s_lang", lang=st["lang"], source=say(source)))
    print(say("s_diagnosis"))
    for p in st["problems"] or [say("s_all_good")]:
        print(f"  {'! ' if st['problems'] else 'ok '}{p}")


# --- CLI ------------------------------------------------------------------------

def parse_fields(raw, known, section):
    fields = [f.strip() for f in raw.split(",") if f.strip()]
    if not fields:
        raise UsageError(say("no_field", section=section))
    bad = [f for f in fields if f not in known]
    if bad:
        raise UsageError(say("bad_fields", section=section, bad=", ".join(bad), known=", ".join(known)))
    return fields


def set_and_show(cfg, section, key, value):
    cfg[section][key] = value
    save_config(cfg)
    print(f"{section}: {preview_header(cfg) if section == 'header' else preview_footer(cfg)}")


def toggle(cfg, piece, on, replace=False):
    if piece == "header":
        cfg["header"]["enabled"] = on
        save_config(cfg)
        print(say("header_toggled", state=say("on" if on else "off")))
        return
    settings = load_settings()
    foreign = bool(settings.get("statusLine")) and not footer_wired(settings)
    if on and foreign and not replace:
        raise UsageError(say("foreign_line", command=json.dumps(settings["statusLine"].get("command"))))
    if on:
        install_stable_copy()
        settings["statusLine"] = {"type": "command", "command": command_for("footer"), "refreshInterval": FOOTER_REFRESH}
    elif footer_wired(settings):
        del settings["statusLine"]
    elif foreign:
        raise UsageError(say("not_ours"))
    save_settings(settings)
    cfg["footer"]["enabled"] = on
    save_config(cfg)
    print(say("footer_toggled", state=say("on" if on else "off")))


def split_lang(args):
    """(the value of --lang or None, the other arguments). `--lang X` and `--lang=X` may stand anywhere."""
    flag, rest, i = None, [], 0
    while i < len(args):
        if args[i] == "--lang":
            flag = args[i + 1] if i + 1 < len(args) else ""
            i += 2
            continue
        if args[i].startswith("--lang="):
            flag = args[i][len("--lang="):]
        else:
            rest.append(args[i])
        i += 1
    return flag, rest


def main(argv, stdin=None):
    """Run one command. The language of its messages is set here: --lang, then the config's lang, then
    CAPYBARA_LANG, then en (the hooks take no flags: the config, then CAPYBARA_LANG). It is put back afterwards,
    so an in-process caller (the tests) never inherits another run's language."""
    global CLI_LANG
    stdin = stdin if stdin is not None else sys.stdin
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    before = CLI_LANG
    try:
        return run_command(argv, stdin)
    finally:
        CLI_LANG = before


def run_command(argv, stdin):
    global CLI_LANG
    cmd, (flag, args) = argv[0], split_lang(argv[1:])
    CLI_LANG = pick_lang(load_config().get("lang"))  # what a broken config or a bad flag is reported in
    try:
        if cmd == "header-hook":
            sys.stdout.write(header_hook(stdin.read()))
            return 0
        if cmd == "footer":
            sys.stdout.write(render_footer(stdin.read()))
            return 0
        if cmd == "state-hook" and len(args) == 1:
            state_hook(args[0], stdin.read())
            return 0
        if flag is not None and flag not in LANGS:
            raise UsageError(say("bad_flag"))
        CLI_LANG = pick_lang(flag)  # a broken config is reported in --lang, else CAPYBARA_LANG, else en
        cfg = load_config(strict=True)
        CLI_LANG = pick_lang(flag, cfg.get("lang"))
        source = "src_flag" if flag else "src_config" if cfg.get("lang") else "src_env" if env_lang() else "src_default"
        if cmd == "status":
            st = collect_status(cfg, load_settings())
            if "--json" in args:
                print(dump_json(st), end="")
            else:
                print_status(st, cfg, source)
            return 1 if st["problems"] else 0
        if cmd in ("on", "off") and args[:1] in (["header"], ["footer"]) and set(args[1:]) <= {"--replace"}:
            toggle(cfg, args[0], cmd == "on", replace="--replace" in args)
        elif cmd in ("wire-hooks", "unwire-hooks") and not args:
            settings = load_settings()
            if cmd == "wire-hooks":
                install_stable_copy()
            wire_hooks(settings, cmd == "wire-hooks")
            save_settings(settings)
            print(say("hooks_wired" if cmd == "wire-hooks" else "hooks_unwired", events=", ".join(PLUGIN_HOOKS)))
        elif cmd == "header-fields" and len(args) == 1:
            set_and_show(cfg, "header", "fields", parse_fields(args[0], HEADER_FIELDS, "header"))
        elif cmd == "footer-fields" and len(args) == 1:
            set_and_show(cfg, "footer", "fields", parse_fields(args[0], FOOTER_FIELDS, "footer"))
        elif cmd == "header-format" and args:
            key = "date_format" if "--date" in args else "time_format"
            fmt = [a for a in args if a != "--date"]
            if len(fmt) != 1 or "%" not in fmt[0]:
                raise UsageError(say("format_usage"))
            try:
                datetime.now().strftime(fmt[0])
            except ValueError:
                raise UsageError(say("format_bad", fmt=fmt[0]))
            set_and_show(cfg, "header", key, fmt[0])
        elif cmd == "header-icon" and len(args) == 1:
            set_and_show(cfg, "header", "icon", args[0])
        elif cmd == "separator" and len(args) == 2 and args[0] in ("header", "footer"):
            set_and_show(cfg, args[0], "separator", args[1])
        elif cmd == "lang" and len(args) == 1 and args[0] in LANGS + ("auto",):
            if args[0] == "auto":
                cfg.pop("lang", None)
            else:
                cfg["lang"] = args[0]
            save_config(cfg)
            CLI_LANG = pick_lang(flag, cfg.get("lang"))
            print(say("lang_auto") if args[0] == "auto" else say("lang_set", lang=args[0]))
        elif cmd == "lang":
            raise UsageError(say("lang_usage"))
        elif cmd == "preview" and not args:
            print(f"header: {preview_header(cfg)}")
            print(f"footer: {preview_footer(cfg)}")
        elif cmd == "fields" and not args:
            for section in ("header", "footer"):
                print(section.upper())
                for k, v in FIELD_HELP[CLI_LANG][section].items():
                    print(f"  {k:8} {v}")
        else:
            raise UsageError(say("bad_command", command=" ".join(argv)))
    except UsageError as exc:
        print(say("error", e=exc), file=sys.stderr)
        return 2
    return 0


def utf8_stdio():
    """Claude Code speaks UTF-8, but a Windows pipe defaults to the ANSI code page (cp1252), where the
    icon and the separator cannot be written, and -I ignores PYTHONUTF8."""
    for stream, errors in ((sys.stdin, "replace"), (sys.stdout, "strict"), (sys.stderr, "backslashreplace")):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors=errors)


if __name__ == "__main__":
    utf8_stdio()
    sys.exit(main(sys.argv[1:]))

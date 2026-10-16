#!/usr/bin/env python3
# header-footer 0.1.0 - a header line at the top of every Claude reply and a configurable status-line footer
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Diogo Winck
"""header-footer: the reply header (a line such as "🕐 14:57 · main" at the top of Claude's first
reply of each turn) and the footer (Claude Code's status line), both driven by one config file.

The header is a UserPromptSubmit hook: it renders the line and injects it, together with the
instruction to copy it, as turn context. Claude has no clock and no git of its own, so every value
comes from here; a guessed timestamp is worse than none.

The footer is a status-line command: it renders the configured fields in the configured order.
A plugin cannot set `statusLine`, so `on footer` copies this script to a stable place under the
Claude config directory and points `statusLine` there (the plugin cache path changes on every update).

Python 3.9+ standard library only; `git` is optional (branch/repo fields), `node` only for the `gsd` field.

Usage:
  python3 -I header_footer.py header-hook            # UserPromptSubmit hook (stdin: hook payload)
  python3 -I header_footer.py footer                 # status line command (stdin: status-line payload)
  python3 -I header_footer.py status [--json]        # what is on, what is wired, what is wrong
  python3 -I header_footer.py on|off header|footer [--replace]
  python3 -I header_footer.py wire-header|unwire-header   # hook in settings.json, for installs without the plugin
  python3 -I header_footer.py header-fields time,branch
  python3 -I header_footer.py header-format "%H:%M" [--date]
  python3 -I header_footer.py header-icon "⏱"
  python3 -I header_footer.py footer-fields gsd,tokens,limits,clock
  python3 -I header_footer.py separator header|footer " · "
  python3 -I header_footer.py preview | fields

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
from datetime import datetime
from pathlib import Path

VERSION = "0.1.0"

HEADER_FIELDS = {
    "time": "hora (header-format)",
    "date": "data (header-format --date)",
    "weekday": "dia da semana: seg..dom",
    "dir": "pasta atual",
    "repo": "nome do repositorio git",
    "branch": "branch git atual",
}
FOOTER_FIELDS = {
    "gsd": "bloco do GSD (modelo | tarefa | pasta | contexto), se o GSD estiver instalado",
    "model": "modelo",
    "dir": "pasta atual",
    "branch": "branch git atual",
    "context": "ctx N% usado",
    "tokens": "tokens acumulados da sessao (entrada e saida)",
    "limits": "janelas 5h/7d do plano e o tempo ate zerar",
    "cost": "custo estimado da sessao em US$",
    "clock": "relogio HH:MM",
}
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
        "fields": ["tokens", "limits", "clock"],
        "separator": " │ ",
    },
}
WEEKDAYS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
INSTRUCTION = (
    "Start your first reply of this turn with the text inside <reply-header>, verbatim, on a line "
    "of its own. Do not estimate, complete or reformat it."
)
# Markers live this long; the header hook only needs them to recognise a second run of the same prompt.
MARKER_TTL = 600
SEEN_IDS_KEPT = 200  # duplicate transcript entries sit adjacent, so a short ring of ids dedupes them

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
            raise UsageError(f"{path} nao e JSON valido: {exc}")
        return cfg
    if not isinstance(raw, dict):
        if strict:
            raise UsageError(f"{path} precisa ser um objeto JSON")
        return cfg
    for section in DEFAULTS:
        if isinstance(raw.get(section), dict):
            cfg[section].update(raw[section])
    return cfg


def atomic_write(path, text, mode=None):
    """Write through a private temp file and os.replace, keeping the old file's mode (settings.json is 600)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode is None:
        mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
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

def render_header(header, cwd, now):
    """The header line, or "" when every field came out empty."""
    values = {
        "time": lambda: now.strftime(header["time_format"]),
        "date": lambda: now.strftime(header["date_format"]),
        "weekday": lambda: WEEKDAYS[now.weekday()],
        "dir": lambda: os.path.basename(str(cwd).rstrip("/")) if cwd else "",
        "repo": lambda: os.path.basename(git(cwd, "rev-parse", "--show-toplevel")),
        "branch": lambda: git(cwd, "branch", "--show-current"),
    }
    parts = [values[f]() for f in header["fields"] if f in values]
    body = header["separator"].join(p for p in parts if p)
    if not body:
        return ""
    return f"{header['icon']} {body}".strip()


def first_run(payload, now_ts):
    """True for the first header hook run of this prompt. With the plugin hook and a settings.json hook
    both registered, the same prompt reaches two copies of this script; only one may print."""
    key = json.dumps([payload.get("session_id"), payload.get("prompt")], ensure_ascii=False)
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
    header = load_config()["header"]
    if not header.get("enabled", True):
        return ""
    try:
        payload = json.loads(stdin_text or "{}")
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    now = now or datetime.now()
    line = render_header(header, payload.get("cwd") or os.getcwd(), now)
    if not line or not first_run(payload, time.time()):
        return ""
    return f"<reply-header>{line}</reply-header>\n{INSTRUCTION}\n"


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
    # Reject separators and traversal so a hostile session_id cannot escape the cache directory.
    if not session_id or "/" in session_id or "\\" in session_id or ".." in session_id:
        return None
    return cache_dir() / f"tokens-{session_id}.json"


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
        raise UsageError(f"{path} nao e JSON valido: {exc}")
    if not isinstance(data, dict):
        raise UsageError(f"{path} precisa ser um objeto JSON")
    return data


def save_settings(data):
    path = settings_path()
    if path.exists():
        backup = path.with_name(f"{path.name}.bak-header-footer-{datetime.now().strftime('%Y%m%d%H%M%S')}")
        shutil.copy2(str(path), str(backup))
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


def command_for(mode):
    return f'"{sys.executable}" -I "{stable_script()}" {mode}'


def wire_header(settings, on):
    hooks = settings.setdefault("hooks", {})
    groups = hooks.setdefault("UserPromptSubmit", [])
    for gi, hi, cmd in sorted(prompt_hook_commands(settings), reverse=True):
        if is_ours(cmd):
            del groups[gi]["hooks"][hi]
            if not groups[gi]["hooks"]:
                del groups[gi]
    if on:
        groups.append({"hooks": [{"type": "command", "command": command_for("header-hook"), "timeout": 5}]})
    if not groups:
        del hooks["UserPromptSubmit"]
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
        problems.append("hook de header antigo no settings.json (" + ", ".join(sorted({n for n in LEGACY_HEADER_HOOKS if any(n in c for c in legacy)}))
                        + "): com o plugin instalado o header sai duplicado; remova essa entrada do settings.json")
    for section, known in (("header", HEADER_FIELDS), ("footer", FOOTER_FIELDS)):
        for f in cfg[section]["fields"]:
            if f not in known:
                problems.append(f"campo de {section} desconhecido: {f}")
    if cfg["footer"]["enabled"] and not footer_wired(settings):
        problems.append("footer ligado na config, mas a statusLine nao aponta para este script: rode `on footer`")
    uses_copy = footer_wired(settings) or any(is_ours(c) for c in commands)
    if uses_copy and copy_version != VERSION:
        problems.append(f"a copia em {stable_script()} esta na versao {copy_version or 'ausente'}, o plugin na {VERSION}: rode `on footer` (ou `wire-header`) de novo")
    if "gsd" in cfg["footer"]["fields"] and not (gsd_script().exists() and shutil.which("node")):
        problems.append("campo gsd configurado, mas o GSD (ou o node) nao esta instalado: o campo sai vazio")
    return {
        "version": VERSION,
        "config": str(config_path()),
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
    return render_header(cfg["header"], os.getcwd(), datetime.now()) or "(vazio)"


def preview_footer(cfg):
    return render_footer(sample_footer_payload(), footer=cfg["footer"]) or "(vazio)"


def print_status(st, cfg):
    h, f = st["header"], st["footer"]
    print("HEADER (linha no topo da resposta)")
    print(f"  config:   {'ligado' if h['enabled'] else 'desligado'}  campos={','.join(h['fields'])}")
    print(f"  hook:     {'settings.json' if h['settings_hook'] else 'hooks.json do plugin (quando instalado pelo marketplace)'}")
    print(f"  preview:  {preview_header(cfg)}")
    print("FOOTER (status line)")
    print(f"  config:   {'ligado' if f['enabled'] else 'desligado'}  campos={','.join(f['fields'])}")
    print(f"  wiring:   {'statusLine aponta para este script' if f['wired'] else 'statusLine = ' + json.dumps(f['status_line'])}")
    print(f"  preview:  {preview_footer(cfg)}")
    print("DIAGNOSTICO")
    for p in st["problems"] or ["tudo certo"]:
        print(f"  {'! ' if st['problems'] else 'ok '}{p}")


# --- CLI ------------------------------------------------------------------------

def parse_fields(raw, known, section):
    fields = [f.strip() for f in raw.split(",") if f.strip()]
    if not fields:
        raise UsageError(f"informe ao menos um campo de {section}")
    bad = [f for f in fields if f not in known]
    if bad:
        raise UsageError(f"campo(s) de {section} desconhecido(s): {', '.join(bad)}. Disponiveis: {', '.join(known)}")
    return fields


def set_and_show(cfg, section, key, value):
    cfg[section][key] = value
    save_config(cfg)
    print(f"{section}: {preview_header(cfg) if section == 'header' else preview_footer(cfg)}")


def toggle(cfg, piece, on, replace=False):
    if piece == "header":
        cfg["header"]["enabled"] = on
        save_config(cfg)
        print(f"header: {'ligado' if on else 'desligado'} (vale no proximo prompt)")
        return
    settings = load_settings()
    foreign = bool(settings.get("statusLine")) and not footer_wired(settings)
    if on and foreign and not replace:
        raise UsageError("ja existe outra statusLine (" + json.dumps(settings["statusLine"].get("command"))
                         + "); use `on footer --replace` para troca-la (o settings.json ganha backup)")
    if on:
        install_stable_copy()
        settings["statusLine"] = {"type": "command", "command": command_for("footer")}
    elif footer_wired(settings):
        del settings["statusLine"]
    elif foreign:
        raise UsageError("a statusLine atual nao e deste script; nao vou remove-la (edite o settings.json a mao)")
    save_settings(settings)
    cfg["footer"]["enabled"] = on
    save_config(cfg)
    print(f"footer: {'ligado' if on else 'desligado'} (settings.json com backup; reinicie o Claude Code se nao mudar)")


def main(argv, stdin=None):
    stdin = stdin if stdin is not None else sys.stdin
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd, args = argv[0], argv[1:]
    try:
        if cmd == "header-hook":
            sys.stdout.write(header_hook(stdin.read()))
            return 0
        if cmd == "footer":
            sys.stdout.write(render_footer(stdin.read()))
            return 0
        cfg = load_config(strict=True)
        if cmd == "status":
            st = collect_status(cfg, load_settings())
            if "--json" in args:
                print(dump_json(st), end="")
            else:
                print_status(st, cfg)
            return 1 if st["problems"] else 0
        if cmd in ("on", "off") and args[:1] in (["header"], ["footer"]) and set(args[1:]) <= {"--replace"}:
            toggle(cfg, args[0], cmd == "on", replace="--replace" in args)
        elif cmd in ("wire-header", "unwire-header") and not args:
            settings = load_settings()
            if cmd == "wire-header":
                install_stable_copy()
            wire_header(settings, cmd == "wire-header")
            save_settings(settings)
            print(f"hook do header {'registrado' if cmd == 'wire-header' else 'removido'} no settings.json (com backup)")
        elif cmd == "header-fields" and len(args) == 1:
            set_and_show(cfg, "header", "fields", parse_fields(args[0], HEADER_FIELDS, "header"))
        elif cmd == "footer-fields" and len(args) == 1:
            set_and_show(cfg, "footer", "fields", parse_fields(args[0], FOOTER_FIELDS, "footer"))
        elif cmd == "header-format" and args:
            key = "date_format" if "--date" in args else "time_format"
            fmt = [a for a in args if a != "--date"]
            if len(fmt) != 1 or "%" not in fmt[0]:
                raise UsageError('uso: header-format "%H:%M" [--date]')
            set_and_show(cfg, "header", key, fmt[0])
        elif cmd == "header-icon" and len(args) == 1:
            set_and_show(cfg, "header", "icon", args[0])
        elif cmd == "separator" and len(args) == 2 and args[0] in ("header", "footer"):
            set_and_show(cfg, args[0], "separator", args[1])
        elif cmd == "preview" and not args:
            print(f"header: {preview_header(cfg)}")
            print(f"footer: {preview_footer(cfg)}")
        elif cmd == "fields" and not args:
            for section, known in (("HEADER", HEADER_FIELDS), ("FOOTER", FOOTER_FIELDS)):
                print(section)
                for k, v in known.items():
                    print(f"  {k:8} {v}")
        else:
            raise UsageError(f"comando invalido: {' '.join(argv)} (use --help)")
    except UsageError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

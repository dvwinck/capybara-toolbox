#!/usr/bin/env python3
# todo-sweep 0.4.0 - TODO e FIXME como cards num painel local, do mais antigo ao mais novo; o resultado e um relatorio somente leitura (somente stdlib e git)
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Diogo Winck
#
# Uso:
#   todo_sweep.py scan   [REPO] [--limit N] [--max-blame N] [--out DIR] [--lang en|pt-BR]   # acha os TODO/FIXME, mede a idade, escreve batch.json + scan.json
#   todo_sweep.py check  DIR                                              # valida batch.json + scan.json
#   todo_sweep.py report DIR                                              # grava report.md e report.json a partir das decisoes
# Todo comando aceita --lang en|pt-BR (padrao: o lang do scan.json, depois CAPYBARA_LANG, depois en).
# O painel e o capy_board.py desta skill (`serve DIR`). Nenhum arquivo-fonte e editado.
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

VERSION = "0.4.0"
SCHEMA = 1
WORK_DIR = ".todo-sweep"
LEDGER = "ledger.json"
MAX_FILE = 1024 * 1024  # bytes; larger files are skipped
TEXT_MAX = 200
CONTEXT = 2  # lines shown before and after a TODO
LEAD = re.compile(r"^\s*(?:#+|//+|--|/\*+|\*+|;+)\s*(TODO|FIXME)\b(.*)$")  # a comment line that starts with the marker
TRAIL = re.compile(r"^\s*\S.*?\s(?:#+|//+)\s*(TODO|FIXME)\b(.*)$")  # a trailing comment after code
SKIP_SUFFIXES = (".md", ".markdown")  # prose mentions TODO; it is not a code comment
ZERO_SHA = "0" * 40
NOW = time.time  # a function: the tests replace it
LANGS = ("en", "pt-BR")  # languages of the cards and the report (`scan --lang`); the first is the default
DEFAULT_LANG = "en"
AGE_REASONS = ("max_blame", "no_history", "uncommitted", "shallow")  # codes kept in the hits and in scan.json

# Every card and report text, in both languages. Hits and scan.json hold codes (`age_reason`), never text;
# `t()` renders them. The two tables have the same keys and placeholders (a test enforces it).
TEXT = {
    "en": {
        "f_where": "Where", "f_text": "Text", "f_age": "Age", "f_excerpt": "Excerpt", "m_area": "Area", "m_age": "Age",
        "title": "{marker} in {place}", "no_text": "(no text)", "root": "(root)",
        "age": "{days} days (the line last changed on {day}, commit {commit})", "age_days": "{days} days",
        "no_age": "no age", "no_age_reason": "no age: {reason}",
        "reason_max_blame": "beyond the --max-blame limit", "reason_no_history": "no history (new file or the blame failed)",
        "reason_uncommitted": "uncommitted line", "reason_shallow": "limit of a shallow clone (the earlier history is not here)",
        "batch_title": "TODO and FIXME: {n} of {total}",
        "subtitle": "oldest first; Resolve, Discard or Keep, and the result is only a report",
        "report_title": "todo-sweep report - {batch}",
        "report_intro": "The lines are those of the moment of the scan. No file was edited by this tool.",
        "s_resolver": "Resolve", "s_descartar": "Discard", "s_manter": "Keep", "s_sem_decisao": "No decision",
    },
    "pt-BR": {
        "f_where": "Onde", "f_text": "Texto", "f_age": "Idade", "f_excerpt": "Trecho", "m_area": "Área", "m_age": "Idade",
        "title": "{marker} em {place}", "no_text": "(sem texto)", "root": "(raiz)",
        "age": "{days} dias (a linha mudou pela última vez em {day}, commit {commit})", "age_days": "{days} dias",
        "no_age": "sem idade", "no_age_reason": "sem idade: {reason}",
        "reason_max_blame": "além do limite de --max-blame", "reason_no_history": "sem histórico (arquivo novo ou o blame falhou)",
        "reason_uncommitted": "linha não commitada", "reason_shallow": "limite de um clone raso (o histórico anterior não está aqui)",
        "batch_title": "TODO e FIXME: {n} de {total}",
        "subtitle": "do mais antigo ao mais novo; Resolver, Descartar ou Manter, e o resultado é só um relatório",
        "report_title": "Relatório do todo-sweep - {batch}",
        "report_intro": "As linhas são as do momento do scan. Nenhum arquivo foi editado por esta ferramenta.",
        "s_resolver": "Resolver", "s_descartar": "Descartar", "s_manter": "Manter", "s_sem_decisao": "Sem decisão",
    },
}
ENV_LANG = "CAPYBARA_LANG"  # one shell-wide default for every Capybara Toolbox script
CLI_LANG = DEFAULT_LANG  # the language of this run's messages, set by main() only

# Every message the command line prints, in both languages (the cards and the report are TEXT, above). Same keys
# and {placeholders} in both (a test enforces it); both plain ASCII, so the pt-BR side is the accent-free
# Portuguese of 0.3.1, and a key ending in `_1` is the form used when n == 1.
MSG = {
    "en": {
        "git_missing": "git not found ({e})", "not_repo": "{path} is not a git repository",
        "not_utf8": "the content of {name} has characters that do not fit in UTF-8: nothing was written",
        "write_failed": "could not write {path}: {e}",
        "symlink": "{folder} is a symbolic link: I refuse to write or read through it",
        "ledger_unreadable": "{path} is unreadable: fix or delete the file",
        "ledger_shape": "{path} has an invalid shape: fix or delete the file",
        "mkdir_failed": "could not create the folder {path}: {e}", "bad_lang": "invalid language: {lang} (use en or pt-BR)",
        "listdir_failed": "could not read the folder {path}: {e}",
        "old_decisions_here": "{path} already has a decisions.json from an earlier batch: choose another folder with --out or delete the decisions",
        "bad_count": "{flag} must be a whole number >= 1 (got {value})",
        "found": "{n} TODO/FIXME found", "found_1": "{n} TODO/FIXME found",
        "decided": "{n} already decided", "decided_1": "{n} already decided", "new": "{n} new", "new_1": "{n} new",
        "unaged": "{n} without an age", "unaged_1": "{n} without an age",
        "scan_nothing": "SCAN: {found}, {decided}; nothing new to show", "scan": "SCAN: {found}, {decided}, {new}, {unaged}",
        "shallow": "warning: shallow clone: the lines at the edge of the history have no age (git fetch --unshallow fixes it)",
        "max_blame": "warning: only the first {n} were measured; raise --max-blame to measure more",
        "showing": "showing {n}, oldest first", "batch": "batch: {path}",
        "missing_file": "{path} missing or unreadable: run scan",
        "p_not_scan": "scan.json is not a todo-sweep scan (schema 1)", "p_no_items": "scan.json without 'items' or 'repo'",
        "p_batch_items": "batch.json without 'items'",
        "p_ids": "scan.json without 'batch_id' (text) or 'round' (integer), or batch.json with an invalid 'round'",
        "p_other_batch": "batch.json and scan.json are from different batches", "p_lang": "scan.json: 'lang' must be en or pt-BR",
        "p_items_differ": "the items of batch.json and scan.json do not match", "p_bad_item": "invalid item in scan.json: {item}",
        "problem": "problem: {e}", "ok": "ok: {n} items, batch {id}", "ok_1": "ok: {n} item, batch {id}",
        "no_decisions": "decisions.json missing or unreadable: open the panel and finish it before report",
        "bad_decisions": "decisions.json has an invalid shape",
        "old_decisions": "decisions.json belongs to another batch or round: I will not use old decisions",
        "not_finished": "the panel was not finished (click Finish before report)",
        "repo_absolute": "the repo of scan.json must be an absolute path: {value}",
        "repo_gone": "the repository of the scan no longer exists: {root}",
        "repo_not_root": "the repo of scan.json is not the root of a git repository: {root}",
        "repo_elsewhere": "the repo of scan.json ({root}) is not the repository this batch is kept in ({anchor})",
        "invalid": "invalid scan.json/batch.json: {errs}",
        "report": "REPORT: {resolve} resolve, {discard} discard, {keep} keep, {none} no decision",
        "report_file": "report: {path}",
        "remembered": "{n} decisions remembered in {ledger}; the next scan offers the next ones",
        "remembered_1": "{n} decision remembered in {ledger}; the next scan offers the next ones",
        "error": "error: {e}", "unexpected": "unexpected failure ({name}: {e})",
    },
    "pt-BR": {
        "git_missing": "git nao encontrado ({e})", "not_repo": "{path} nao e um repositorio git",
        "not_utf8": "o conteudo de {name} tem caracteres que nao cabem em UTF-8: nada foi gravado",
        "write_failed": "nao consegui gravar {path}: {e}",
        "symlink": "{folder} e um link simbolico: recuso escrever ou ler por ele",
        "ledger_unreadable": "{path} esta ilegivel: corrija ou apague o arquivo",
        "ledger_shape": "{path} tem formato invalido: corrija ou apague o arquivo",
        "mkdir_failed": "nao consegui criar a pasta {path}: {e}", "bad_lang": "idioma invalido: {lang} (use en ou pt-BR)",
        "listdir_failed": "nao consegui ler a pasta {path}: {e}",
        "old_decisions_here": "{path} ja tem decisions.json de um lote anterior: escolha outra pasta com --out ou apague as decisoes",
        "bad_count": "{flag} deve ser um numero inteiro >= 1 (recebi {value})",
        "found": "{n} TODO/FIXME achados", "found_1": "{n} TODO/FIXME achado",
        "decided": "{n} ja decididos", "decided_1": "{n} ja decidido", "new": "{n} novos", "new_1": "{n} novo",
        "unaged": "{n} sem idade", "unaged_1": "{n} sem idade",
        "scan_nothing": "SCAN: {found}, {decided}; nada novo para mostrar", "scan": "SCAN: {found}, {decided}, {new}, {unaged}",
        "shallow": "aviso: clone raso: as linhas no limite do historico ficam sem idade (git fetch --unshallow resolve)",
        "max_blame": "aviso: so os primeiros {n} foram medidos; suba --max-blame para medir mais",
        "showing": "mostrando {n}, do mais antigo ao mais novo", "batch": "lote: {path}",
        "missing_file": "{path} ausente ou ilegivel: rode o scan",
        "p_not_scan": "scan.json nao e um scan do todo-sweep (schema 1)", "p_no_items": "scan.json sem 'items' ou 'repo'",
        "p_batch_items": "batch.json sem 'items'",
        "p_ids": "scan.json sem 'batch_id' (texto) ou 'round' (inteiro), ou batch.json com 'round' invalido",
        "p_other_batch": "batch.json e scan.json sao de lotes diferentes", "p_lang": "scan.json: 'lang' deve ser en ou pt-BR",
        "p_items_differ": "os itens do batch.json e do scan.json nao coincidem", "p_bad_item": "item invalido no scan.json: {item}",
        "problem": "problema: {e}", "ok": "ok: {n} itens, lote {id}", "ok_1": "ok: {n} item, lote {id}",
        "no_decisions": "decisions.json ausente ou ilegivel: suba o painel e conclua antes do report",
        "bad_decisions": "decisions.json com formato invalido",
        "old_decisions": "decisions.json e de outro lote ou rodada: nao vou usar decisoes antigas",
        "not_finished": "o painel nao foi concluido (clique em Concluir antes do report)",
        "repo_absolute": "o repo do scan.json deve ser um caminho absoluto: {value}",
        "repo_gone": "o repositorio do scan nao existe mais: {root}",
        "repo_not_root": "o repo do scan.json nao e a raiz de um repositorio git: {root}",
        "repo_elsewhere": "o repo do scan.json ({root}) nao e o repositorio onde este lote esta guardado ({anchor})",
        "invalid": "scan.json/batch.json invalidos: {errs}",
        "report": "REPORT: {resolve} resolver, {discard} descartar, {keep} manter, {none} sem decisao",
        "report_file": "relatorio: {path}",
        "remembered": "{n} decisoes lembradas em {ledger}; o proximo scan oferece os proximos",
        "remembered_1": "{n} decisao lembrada em {ledger}; o proximo scan oferece os proximos",
        "error": "erro: {e}", "unexpected": "falha inesperada ({name}: {e})",
    },
}


def env_lang():
    """CAPYBARA_LANG when it is exactly one of LANGS. Any other value is ignored, silently: a shell setting must
    never break a command, and a warning on every run would be noise in the agent's context."""
    value = os.environ.get(ENV_LANG)
    return value if value in LANGS else None


def pick_lang(*candidates):
    """The first candidate that is one of LANGS (--lang, then the language a scan recorded), then CAPYBARA_LANG,
    then English. A recorded value is data: anything else is ignored here and refused by `check` and `report`."""
    for cand in candidates:
        if isinstance(cand, str) and cand in LANGS:
            return cand
    return env_lang() or DEFAULT_LANG


def use_lang(*candidates):
    """Set the language of this run's messages (see pick_lang) and return it. Only main() calls it."""
    global CLI_LANG
    CLI_LANG = pick_lang(*candidates)
    return CLI_LANG


def recorded_lang(folder):
    """The `lang` the scan in `folder` recorded, or None (no folder, no scan.json, not JSON). main() reads it before
    the command runs, so the command's lines and its errors speak the language of the board it works on."""
    if not folder:
        return None
    try:
        data = json.loads((Path(folder) / "scan.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, RecursionError):
        return None
    return data.get("lang") if isinstance(data, dict) else None


def lang_in_argv(argv):
    """The value of --lang as typed, read before argparse runs: its usage errors are printed while it parses."""
    for i, arg in enumerate(argv):
        if arg == "--lang" and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith("--lang="):
            return arg[len("--lang="):]
    return None


def say(msg_id, /, **values):
    """One command-line message in the language of this run; with n == 1 the `_1` form wins when there is one.
    The template is ours, the values are data (substituted, never parsed)."""
    table = MSG[CLI_LANG]
    if values.get("n") == 1 and msg_id + "_1" in table:
        msg_id += "_1"
    return table[msg_id].format(**values)


LABELS = {  # the panel's own wording per language: A resolves, R discards, M keeps
    "en": {"approve": {"text": "Resolve", "tone": "safe"}, "reject": {"text": "Discard", "tone": "danger"},
           "maybe": {"text": "Keep", "tone": "caution"}},
    "pt-BR": {"approve": {"text": "Resolver", "tone": "safe"}, "reject": {"text": "Descartar", "tone": "danger"},
              "maybe": {"text": "Manter", "tone": "caution"}},
}

# git never prompts, never runs the repository's hooks or a filesystem monitor, and never uses the network
GIT_FLAGS = ["-c", "core.quotepath=off", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=" + os.devnull,
             "-c", "protocol.allow=never", "-c", "log.showSignature=false"]


class SweepError(Exception):
    """Something the person must fix before the tool can run (exit code 2)."""


# where git looks for the repository: inherited from a hook or a wrapper, these would make `-C path` judge another tree
GIT_LOCATION_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY",
                     "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE", "GIT_PREFIX", "GIT_IMPLICIT_WORK_TREE")


def git(root, *args):
    env = {k: v for k, v in os.environ.items() if k not in GIT_LOCATION_VARS}
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        r = subprocess.run(["git", *GIT_FLAGS, "-C", str(root), *args], capture_output=True, env=env)
    except OSError as e:
        raise SweepError(say("git_missing", e=e.strerror or e))
    except ValueError:  # an embedded NUL in an argument: git is never run, the answer is "no"
        return 1, ""
    return r.returncode, r.stdout.decode("utf-8", "replace")


def repo_root(path):
    rc, out = git(path, "rev-parse", "--show-toplevel")
    if rc != 0:
        raise SweepError(say("not_repo", path=path))
    return Path(out.strip())


def stage_private(path, text):
    """Write `text` to a private (mode 0600) temporary file next to `path` and return its name. The text is encoded
    before any file exists, and a failure leaves no temporary file behind."""
    path = Path(path)
    try:
        payload = text.encode("utf-8")
    except UnicodeError:
        raise SweepError(say("not_utf8", name=path.name))
    tmp = path.with_name(path.name + ".tmp")
    try:
        try:
            os.unlink(str(tmp))  # a stale temporary file (or a link planted in its place) is never reused
        except FileNotFoundError:
            pass
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError as e:
        raise SweepError(say("write_failed", path=path, e=e.strerror or e))
    try:
        try:
            view = memoryview(payload)
            while view:
                view = view[os.write(fd, view):]
        finally:
            os.close(fd)
    except OSError as e:
        discard(tmp)
        raise SweepError(say("write_failed", path=path, e=e.strerror or e))
    return tmp


def discard(path):
    try:
        os.unlink(str(path))
    except OSError:
        pass


def write_private(path, text):
    """Atomic and private (mode 0600): the cards quote code, and a ledger must never be half written."""
    write_all({path: text})


def write_all(files):
    """Write several files ({path: text}) as one step: every one is staged first, and if a later step fails the
    files already replaced go back to what they were (or disappear if they were new)."""
    staged = {}
    try:
        for path, text in files.items():
            staged[path] = stage_private(path, text)
    except SweepError:
        for tmp in staged.values():
            discard(tmp)
        raise
    undo = []
    try:
        for path, tmp in staged.items():
            try:
                before = Path(path).read_bytes()
            except OSError:
                before = None
            os.replace(tmp, path)
            undo.append((path, before))
    except OSError as e:
        for tmp in staged.values():
            discard(tmp)
        for path, before in undo:
            try:
                if before is None:
                    os.unlink(str(path))
                else:
                    Path(path).write_bytes(before)
            except OSError:
                pass
        raise SweepError(say("write_failed", path=", ".join(str(p) for p in files), e=e.strerror or e))


def dump_json(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------- finding the markers

def find_todos(text):
    """Every TODO or FIXME inside a comment: (line number, marker, text, context). Upper case, whole word; the
    comment must start the line or trail some code. It is a heuristic (a `# TODO` inside a string after a space
    matches) and the README says so."""
    lines = text.split("\n")  # the way git counts lines: str.splitlines also splits on form feeds, U+2028 and a lone CR
    if lines and lines[-1] == "":
        lines.pop()  # the newline that ends the last line does not start another
    lines = [line[:-1] if line.endswith("\r") else line for line in lines]
    out = []
    for i, line in enumerate(lines):
        m = LEAD.match(line) or TRAIL.match(line)
        if not m:
            continue
        out.append((i + 1, m.group(1), clean_text(m.group(2)), context_of(lines, i)))
    return out


def clean_text(rest):
    """What follows the marker, without its colon and a closing `*/`, capped. Only linear work is done on it (a
    tracked file can hold one huge line): the leading run is skipped by position and the tail is cut before it is
    stripped."""
    start = re.match(r"[:\s]*", rest).end()
    body = rest[start:start + TEXT_MAX + 64].rstrip()
    if body.endswith("*/"):
        body = body[:-2]
    return body.strip()[:TEXT_MAX]


def context_of(lines, i):
    lo, hi = max(0, i - CONTEXT), min(len(lines), i + CONTEXT + 1)
    return [(n + 1, lines[n][:160]) for n in range(lo, hi)]


def read_source(root, rel):
    """A tracked text file's content, or None: symlinks, folders, binary files and files over 1 MB are skipped."""
    path = Path(root) / rel
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FILE:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:8192]:
        return None
    return data.decode("utf-8", errors="replace")


def todo_id(file, text, n):
    """Who a TODO is, never by its line: its file, its text and which of identical ones it is."""
    return hashlib.sha256(f"{file}|{text}|{n}".encode("utf-8")).hexdigest()[:16]


def scan_files(root):
    """Every hit in the tracked files, in the order the files are listed, with no age yet."""
    rc, out = git(root, "ls-files", "-z")
    if rc != 0:
        raise SweepError(say("not_repo", path=root))
    hits = []
    for rel in sorted(p for p in out.split("\0") if p):
        if rel.lower().endswith(SKIP_SUFFIXES):
            continue
        text = read_source(root, rel)
        if text is None:
            continue
        seen = {}
        for line, marker, body, context in find_todos(text):
            n = seen.get(body, 0)
            seen[body] = n + 1
            hits.append({"file": rel, "line": line, "marker": marker, "text": body, "context": context,
                         "todo_id": todo_id(rel, body, n), "age": None, "age_reason": "max_blame"})
    return hits


# ---------------------------------------------------------------- age

HEADER = re.compile(r"^([0-9a-f]{40}) \d+ (\d+)(?: \d+)?$")


def parse_blame(out):
    """`git blame --porcelain` output as {final line: {sha, time, boundary}}. A commit's headers are printed only
    the first time it appears, so they are remembered by sha."""
    info, entries, cur = {}, {}, None
    for line in out.splitlines():
        m = HEADER.match(line)
        if m and (cur is None or cur.get("done")):
            cur = {"sha": m.group(1), "final": int(m.group(2)), "done": False}
            info.setdefault(cur["sha"], {})
        elif cur is not None and not cur["done"]:
            if line.startswith("\t"):
                data = info[cur["sha"]]
                entries[cur["final"]] = {"sha": cur["sha"], "time": data.get("author-time"), "boundary": "boundary" in data}
                cur["done"] = True
            else:
                key, _, value = line.partition(" ")
                info[cur["sha"]][key] = value
    return entries


def is_shallow(root):
    rc, out = git(root, "rev-parse", "--is-shallow-repository")
    return rc == 0 and out.strip() == "true"


def blame_ages(root, hits, cap):
    """Give an age to the first `cap` hits, in the order given: the days since the line's last change (author
    time). Uncommitted lines and a shallow clone's boundary commits have no age, and say why."""
    by_file = {}
    for h in hits[:cap]:
        by_file.setdefault(h["file"], []).append(h)
    now = NOW()
    shallow = is_shallow(root)  # blame calls the repository's root commit a boundary too, and its age is real
    for rel, group in by_file.items():
        args = ["blame", "--porcelain"]
        for h in group:
            args += ["-L", f"{h['line']},{h['line']}"]
        rc, out = git(root, *args, "--", rel)
        entries = parse_blame(out) if rc == 0 else {}
        for h in group:
            e = entries.get(h["line"])
            if e is None:
                h["age_reason"] = "no_history"
            elif e["sha"] == ZERO_SHA or e["time"] is None:
                h["age_reason"] = "uncommitted"
            elif e["boundary"] and shallow:
                h["age_reason"] = "shallow"
            else:
                t = int(e["time"])
                h["age"] = {"days": max(0, int((now - t) // 86400)), "time": t, "commit": e["sha"][:7]}
                h["age_reason"] = ""
    return hits


# ---------------------------------------------------------------- what was already decided

def work_dir(root):
    """The folder the batches and the ledger live in. A symlink there (a hostile repository can track one) would
    send what the tool writes, or what it trusts, somewhere else, so it is refused."""
    folder = Path(root) / WORK_DIR
    if folder.is_symlink():
        raise SweepError(say("symlink", folder=folder))
    return folder


def ledger_path(root):
    return work_dir(root) / LEDGER


def load_ledger(root):
    path = ledger_path(root)
    try:
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, RecursionError):  # unreadable, not UTF-8, not JSON, or nested too deep
        raise SweepError(say("ledger_unreadable", path=path))
    if not isinstance(data, dict) or not isinstance(data.get("decided"), dict):
        raise SweepError(say("ledger_shape", path=path))
    return data["decided"]


def save_ledger(root, decided):
    path = ledger_path(root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise SweepError(say("mkdir_failed", path=path.parent, e=e.strerror or e))
    write_private(path, dump_json({"schema": SCHEMA, "decided": decided}))


# ---------------------------------------------------------------- cards and scan

def check_lang(lang):
    """A language is one of LANGS; anything else (a typo, a value edited into a file) is the person's error."""
    if lang not in LANGS:
        raise SweepError(say("bad_lang", lang=repr(lang)))
    return lang


def t(lang, key, **values):
    """One card or report text in `lang`. The template is ours; the values are data, substituted and never parsed."""
    return TEXT[lang][key].format(**values)


def shown(name):
    """A name as the card shows it: a backtick would be read as the start of a code span."""
    return name.replace("`", "'")


def area(file):
    """The top folder of a file, or '' at the root (the card names the root in its own language)."""
    return file.split("/", 1)[0] if "/" in file else ""


def order_hits(hits):
    """Oldest first; what has no age comes after, in the order the files are listed."""
    aged = sorted((h for h in hits if h["age"]), key=lambda h: (-h["age"]["days"], h["file"], h["line"]))
    return aged + [h for h in hits if not h["age"]]


def age_text(h, lang):
    if h["age"]:
        day = time.strftime("%Y-%m-%d", time.gmtime(h["age"]["time"]))
        return t(lang, "age", days=h["age"]["days"], day=day, commit=h["age"]["commit"])
    reason = t(lang, "reason_" + h["age_reason"]) if h["age_reason"] in AGE_REASONS else h["age_reason"]
    return t(lang, "no_age_reason", reason=reason)


def card_for(item_id, h, lang):
    short = h["text"] if len(h["text"]) <= 90 else h["text"][:87] + "..."
    place = f"{shown(h['file'])}:{h['line']}"
    context = "\n".join(f"{n:>4}  {shown(text)}" for n, text in h["context"])
    where = shown(area(h["file"])) or t(lang, "root")
    return {"id": item_id, "tag": f"{h['marker']} - {where}",
            "title": t(lang, "title", marker=h["marker"], place=place) + (f": {shown(short)}" if short else ""),
            "fields": [{"label": t(lang, "f_where"), "text": f"`{place}`"},
                       {"label": t(lang, "f_text"), "text": shown(h["text"]) or t(lang, "no_text")},
                       {"label": t(lang, "f_age"), "text": age_text(h, lang)},
                       {"label": t(lang, "f_excerpt"), "text": context}],
            "meta": {t(lang, "m_area"): where, t(lang, "m_age"): t(lang, "age_days", days=h["age"]["days"]) if h["age"] else t(lang, "no_age")}}


def build_batch(batch_id, shown_hits, found, lang):
    width = max(2, len(str(len(shown_hits))))
    items = [card_for(f"T{i + 1:0{width}}", h, lang) for i, h in enumerate(shown_hits)]
    return {"batch_id": batch_id, "title": t(lang, "batch_title", n=len(shown_hits), total=found),
            "subtitle": t(lang, "subtitle"), "round": 1, "lang": lang, "labels": LABELS[lang], "items": items}


def build_scan(batch_id, root, shown_hits, totals, lang):
    items = []
    for i, h in enumerate(shown_hits):
        items.append({"id": f"T{i + 1:0{max(2, len(str(len(shown_hits))))}}", "todo_id": h["todo_id"], "file": h["file"],
                      "line": h["line"], "marker": h["marker"], "text": h["text"],
                      "age_days": h["age"]["days"] if h["age"] else None, "commit": h["age"]["commit"] if h["age"] else None,
                      "age_reason": h["age_reason"]})
    return {"schema": SCHEMA, "tool": "todo-sweep", "version": VERSION, "batch_id": batch_id, "repo": str(root),
            "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "round": 1, "lang": lang, "totals": totals, "items": items}


def unique_dir(parent, base):
    name, n = base, 2
    while (Path(parent) / name).exists():
        name, n = f"{base}-{n}", n + 1
    return name


def make_folder(out):
    """Create `out` (and its missing parents) and return the folders this call created, deepest first."""
    made, cur = [], Path(out)
    while not cur.exists() and cur != cur.parent:
        made.append(cur)
        cur = cur.parent
    try:
        Path(out).mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise SweepError(say("mkdir_failed", path=out, e=e.strerror or e))
    return made


def refuse_old_decisions(out):
    """A decisions file in an existing output folder was written for other cards that used the same ids (the board
    would resume it, and the ledger would record what nobody judged). Refused before anything is written."""
    try:
        names = os.listdir(str(out)) if out.is_dir() else []
    except OSError as e:
        raise SweepError(say("listdir_failed", path=out, e=e.strerror or e))
    if any(n == "decisions.json" or (n.startswith("decisions.r") and n.endswith(".json")) for n in names):
        raise SweepError(say("old_decisions_here", path=out))


def check_counts(a):
    """--limit and --max-blame are whole numbers of at least 1: a negative one would slice from the end of the list."""
    for name, flag in (("limit", "--limit"), ("max_blame", "--max-blame")):
        value = getattr(a, name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise SweepError(say("bad_count", flag=flag, value=repr(value)))


def cmd_scan(a):
    check_counts(a)
    lang = check_lang(getattr(a, "lang", None) or pick_lang())  # one language per run: the cards and these lines
    root = repo_root(a.repo)
    if a.out:
        refuse_old_decisions(Path(a.out))
    decided = load_ledger(root)
    hits = scan_files(root)
    fresh = [h for h in hits if h["todo_id"] not in decided]
    if not fresh:
        print(say("scan_nothing", found=say("found", n=len(hits)), decided=say("decided", n=len(hits) - len(fresh))))
        return 0
    blame_ages(root, fresh, a.max_blame)
    offered = order_hits(fresh)[:a.limit]
    unaged = [h for h in fresh if not h["age"]]
    totals = {"found": len(hits), "decided_before": len(hits) - len(fresh), "new": len(fresh), "unaged": len(unaged),
              "shown": len(offered), "shallow": is_shallow(root), "max_blame": a.max_blame}
    stamp = time.strftime("todo-sweep-%Y-%m-%d")
    if a.out:
        out = Path(a.out)
    else:
        parent = work_dir(root)
        out = parent / unique_dir(parent, stamp)
    batch_id = out.name
    made = make_folder(out)
    try:
        write_all({out / "batch.json": dump_json(build_batch(batch_id, offered, len(fresh), lang)),
                   out / "scan.json": dump_json(build_scan(batch_id, root, offered, totals, lang))})
    except SweepError:
        for folder in made:  # a folder this run created is removed again; one that was there is left as it was
            try:
                folder.rmdir()
            except OSError:
                pass
        raise
    print(say("scan", found=say("found", n=len(hits)), decided=say("decided", n=totals["decided_before"]),
              new=say("new", n=len(fresh)), unaged=say("unaged", n=len(unaged))))
    if totals["shallow"]:
        print(say("shallow"))
    if len(unaged) and a.max_blame < len(fresh):
        print(say("max_blame", n=a.max_blame))
    print(say("showing", n=len(offered)))
    print(say("batch", path=out))
    return 0


def load_dir(d):
    out = []
    for name in ("batch.json", "scan.json"):
        try:
            out.append(json.loads((Path(d) / name).read_text(encoding="utf-8")))
        except (OSError, UnicodeError, ValueError, RecursionError):
            raise SweepError(say("missing_file", path=Path(d) / name))
    return out


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def scan_problems(batch, scan):
    errs = []
    if not isinstance(scan, dict) or scan.get("tool") != "todo-sweep" or scan.get("schema") != SCHEMA:
        return [say("p_not_scan")]
    if not isinstance(scan.get("items"), list) or not isinstance(scan.get("repo"), str):
        return [say("p_no_items")]
    if not isinstance(batch, dict) or not isinstance(batch.get("items"), list):
        return [say("p_batch_items")]
    if not isinstance(scan.get("batch_id"), str) or not is_int(scan.get("round")) or not is_int(batch.get("round", 1)):
        return [say("p_ids")]
    if batch.get("batch_id") != scan.get("batch_id"):
        errs.append(say("p_other_batch"))
    if scan.get("lang") is not None and scan["lang"] not in LANGS:  # an older scan has no lang: that is English
        errs.append(say("p_lang"))
    ids = [i.get("id") for i in batch["items"] if isinstance(i, dict)]
    mine = [i.get("id") for i in scan["items"] if isinstance(i, dict)]
    if ids != mine:
        errs.append(say("p_items_differ"))
    for it in scan["items"]:
        if not (isinstance(it, dict) and all(isinstance(it.get(k), str) for k in ("id", "todo_id", "file", "marker", "text"))
                and isinstance(it.get("line"), int)):
            errs.append(say("p_bad_item", item=repr(it))[:120])
            break
    return errs


def cmd_check(a):
    batch, scan = load_dir(a.dir)
    errs = scan_problems(batch, scan)
    for e in errs:
        print(say("problem", e=e))
    if not errs:
        print(say("ok", n=len(scan["items"]), id=scan["batch_id"]))
    return 1 if errs else 0


# ---------------------------------------------------------------- the report

DECISIONS = {"approved": "resolver", "rejected": "descartar", "maybe": "manter"}  # the panel's A, R and M
SECTIONS = (("resolver", "s_resolver"), ("descartar", "s_descartar"), ("manter", "s_manter"), ("sem_decisao", "s_sem_decisao"))  # JSON key, text key


def read_decisions(d, batch):
    """The panel's decisions.json, or a SweepError. The file is whatever a board (or a hand) left there: unreadable,
    not UTF-8, not JSON, nested too deep, a folder, the wrong shape, another batch or round, or not concluded."""
    path = Path(d) / "decisions.json"
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, RecursionError):
        raise SweepError(say("no_decisions"))
    if not isinstance(state, dict) or not isinstance(state.get("items"), dict):
        raise SweepError(say("bad_decisions"))
    if state.get("batch_id") != batch.get("batch_id") or not is_int(state.get("round")) or state["round"] != batch.get("round", 1):
        raise SweepError(say("old_decisions"))
    if state.get("finished") is not True:
        raise SweepError(say("not_finished"))
    return state["items"]


def group_items(scan, decisions):
    groups = {key: [] for key, _text in SECTIONS}
    for it in scan["items"]:
        entry = decisions.get(it["id"])
        entry = entry if isinstance(entry, dict) else {}
        word = entry.get("decision")
        key = DECISIONS.get(word, "sem_decisao") if isinstance(word, str) else "sem_decisao"
        comment = entry.get("comment")
        age = it.get("age_days")
        groups[key].append({"id": it["id"], "todo_id": it["todo_id"], "file": it["file"], "line": it["line"],
                            "marker": it["marker"], "text": it["text"], "age_days": age if is_int(age) else None,
                            "comment": comment if isinstance(comment, str) else ""})
    return groups


def md_line(text):
    """Text as one line of the report: a newline (a comment, or a file name git allows to hold one) could start a
    heading or a list item of its own, and a backtick would open a code span."""
    return shown(" ".join(text.split()))


def report_markdown(scan, groups, lang):
    lines = ["# " + t(lang, "report_title", batch=md_line(scan["batch_id"])), "", t(lang, "report_intro"), ""]
    for key, text_key in SECTIONS:
        lines += [f"## {t(lang, text_key)} ({len(groups[key])})", ""]
        for h in groups[key]:
            age = t(lang, "age_days", days=h["age_days"]) if h["age_days"] is not None else t(lang, "no_age")
            lines.append(f"- `{md_line(h['file'])}:{h['line']}` {md_line(h['marker'])} {md_line(h['text']) or t(lang, 'no_text')} ({age})"
                         + (f" - {md_line(h['comment'])}" if md_line(h["comment"]) else ""))
        lines.append("")
    return "\n".join(lines)


def trusted_repo(scan, a_dir):
    """The repository the scan was made in, from scan.json. That path decides where the ledger is written, and the
    file may have been edited by hand: it must be absolute and be the toplevel of the repository (not a subfolder or
    a relative spelling that depends on the working directory), and a batch kept in a `.todo-sweep` folder must be
    reported against the repository that folder belongs to. A batch made with --out elsewhere has no such anchor,
    so only the first rule applies to it."""
    value = scan["repo"]
    if not isinstance(value, str) or not os.path.isabs(value) or "\0" in value:
        raise SweepError(say("repo_absolute", value=repr(value))[:200])
    root = Path(value)
    if not root.is_dir() or git(root, "rev-parse", "--git-dir")[0] != 0:
        raise SweepError(say("repo_gone", root=root))
    try:
        same = root.resolve() == repo_root(root).resolve()
    except (OSError, RuntimeError, ValueError):
        same = False
    if not same:
        raise SweepError(say("repo_not_root", root=root))
    anchor = next((p.parent for p in Path(a_dir).resolve().parents if p.name == WORK_DIR), None)
    if anchor is not None and anchor != root.resolve():  # a batch kept in some repository's work area belongs to that repository
        raise SweepError(say("repo_elsewhere", root=root, anchor=anchor))
    return root


def cmd_report(a):
    batch, scan = load_dir(a.dir)
    errs = scan_problems(batch, scan)
    if errs:
        raise SweepError(say("invalid", errs="; ".join(errs)))
    lang = pick_lang(getattr(a, "lang", None), scan.get("lang"))  # --lang, the scan's (an older one has none), CAPYBARA_LANG, en
    groups = group_items(scan, read_decisions(a.dir, batch))
    root = trusted_repo(scan, a.dir)
    decided = load_ledger(root)  # read first: a bad ledger (or a symlinked folder) stops the run before anything is written
    ledger = ledger_path(root)
    now_text = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    data = {"schema": SCHEMA, "tool": "todo-sweep", "batch_id": scan["batch_id"], "round": batch.get("round", 1), "lang": lang,
            "created": now_text, "counts": {key: len(groups[key]) for key, _text in SECTIONS}, **groups}
    for key, word in (("descartar", "discard"), ("manter", "keep")):
        for h in groups[key]:
            decided[h["todo_id"]] = {"decision": word, "at": now_text, "file": h["file"], "text": h["text"]}
    out = Path(a.dir)
    made = make_folder(ledger.parent)
    try:  # the two report files and the ledger go together: all of them, or (rolled back) none
        write_all({out / "report.json": dump_json(data), out / "report.md": report_markdown(scan, groups, lang),
                   ledger: dump_json({"schema": SCHEMA, "decided": decided})})
    except SweepError:
        for folder in made:
            try:
                folder.rmdir()
            except OSError:
                pass
        raise
    c = data["counts"]
    print(say("report", resolve=c["resolver"], discard=c["descartar"], keep=c["manter"], none=c["sem_decisao"]))
    print(say("report_file", path=out / "report.md"))
    print(say("remembered", n=c["descartar"] + c["manter"], ledger=ledger))
    return 0


# ---------------------------------------------------------------- the command line

USAGE_WORDS = ((r"^argument ", "argumento "), (r"the following arguments are required: ", "faltam argumentos obrigatorios: "),
               (r"unrecognized arguments: ", "argumentos desconhecidos: "), (r"expected one argument", "falta o valor"),
               (r"invalid choice: ", "comando invalido: "))


class Parser(argparse.ArgumentParser):
    """Usage mistakes end the way every other failure does: an `error:` line (pt-BR `erro:`) on stderr and exit
    code 2. argparse speaks English; in pt-BR its words are translated as before."""

    def error(self, message):
        if CLI_LANG == "pt-BR":
            for pattern, text in USAGE_WORDS:
                message = re.sub(pattern, text, message)
        self.print_usage(sys.stderr)
        self.exit(2, say("error", e=message) + "\n")


def count(text):
    """A count as typed: a whole number, or the text itself, which check_counts refuses with its own message."""
    try:
        return int(text)
    except ValueError:
        return text


def parser():
    p = Parser(prog="todo_sweep.py", description="TODO and FIXME as cards on a local panel; the result is a read-only report.")
    p.add_argument("--version", action="version", version=f"todo-sweep {VERSION}")
    sub = p.add_subparsers(dest="cmd", required=True)
    lang = Parser(add_help=False)  # every command takes --lang (the help text is English in both)
    lang.add_argument("--lang", choices=LANGS, default=None,
                      help="language of the messages, of the cards (scan) and of report.md (report); default: the scan's lang, then CAPYBARA_LANG, then en")
    s = sub.add_parser("scan", parents=[lang], help="find the TODO/FIXME and write batch.json + scan.json")
    s.add_argument("repo", nargs="?", default=".")
    s.add_argument("--limit", type=count, default=20, help="cards per batch (default 20)")
    s.add_argument("--max-blame", type=count, default=300, help="how many to measure with git blame (default 300)")
    s.add_argument("--out", help=f"batch folder (default: {WORK_DIR}/todo-sweep-YYYY-MM-DD)")
    c = sub.add_parser("check", parents=[lang], help="validate batch.json + scan.json")
    c.add_argument("dir")
    r = sub.add_parser("report", parents=[lang], help="write report.md and report.json from the decisions")
    r.add_argument("dir")
    return p


def main(argv=None):
    """Run one command. The language of its messages is set here, once: --lang, then the lang of the scan in the
    command's folder (check, report), then CAPYBARA_LANG, then en. It is put back afterwards, so an in-process
    caller (the tests) never inherits another run's language; the commands never set it."""
    global CLI_LANG
    argv = sys.argv[1:] if argv is None else list(argv)
    before = CLI_LANG
    use_lang(lang_in_argv(argv))  # a usage error is printed while argparse parses, before args exist
    try:
        args = parser().parse_args(argv)
        use_lang(args.lang, recorded_lang(getattr(args, "dir", None)))
        try:
            return {"scan": cmd_scan, "check": cmd_check, "report": cmd_report}[args.cmd](args)
        except SweepError as e:
            print(say("error", e=e), file=sys.stderr)
            return 2
        except (OSError, UnicodeError, RecursionError) as e:  # whatever a hostile folder or a full disk still throws
            print(say("error", e=say("unexpected", name=type(e).__name__, e=e)), file=sys.stderr)
            return 2
    finally:
        CLI_LANG = before


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# handoff 0.3.1 - nota de fim de sessao com fatos do git coletados e citacoes conferidas (somente stdlib e git)
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Diogo Winck
#
# Uso:
#   handoff.py collect [REPO] [--base REF] [--json]                   # fatos do git (branch, ponta, a frente/atras, sujos...)
#   handoff.py write   [REPO] --draft FILE|- [--out DIR] [--base REF] # confere as citacoes e grava .handoff/AAAA-MM-DD-hhmmss.md
#                                                                     # (um bloco --- Chave: Valor --- no inicio do rascunho vira a metainfo da nota)
#   handoff.py verify  FILE [REPO] [--json]                           # confere as citacoes de uma nota ou rascunho
#   handoff.py resume  [REPO] [--file FILE] [--json]                  # mostra a nota mais recente e o que mudou desde entao
# Saida: 0 tudo conferido, 1 citacao nao verificada ou algo mudou, 2 erro.
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

VERSION = "0.3.1"
SCHEMA = 1  # of the --json output and of the data block inside a note
NOTE_DIR = ".handoff"
RECENT = 5  # commits listed in the note
LANGS = ("en", "pt-BR")  # languages of the note and of the messages (--lang); the first is the default
DEFAULT_LANG = "en"
ENV_LANG = "CAPYBARA_LANG"  # one shell-wide default for every Capybara Toolbox script
CLI_LANG = DEFAULT_LANG  # the language of this run's messages, set by main()

# The fixed texts the tool writes into a note, per language. The pt-BR side is exactly what 0.3.1 wrote (accent-
# free), so every note written before 0.4.0 is a pt-BR note. `resume` and `verify` recognise the tool's parts in
# either language, and the agent's metainfo keys and section headings are accepted in either language too.
NOTE = {
    "en": {
        "unverified": " [not verified]", "meta_title": "Session metainfo", "written_at": "Written at", "repository": "Repository",
        "expected": ("Model", "Original request", "Status"),
        "sections": ("What was done", "Decisions and why", "Next steps", "What failed or got stuck"),
        "git_title": "## Git state", "detached": "detached HEAD", "tip": ", tip {tip}", "no_commits": ", no commits",
        "vs_base": "- Against the base {base}: {ahead} ahead, {behind} behind", "no_base": "- Base: not found",
        "modified": "- Modified files: {n}", "untracked": "- New (untracked) files: {n}", "stashes": "- Stashes: {n}",
        "worktrees": "- Other worktrees: ", "commits": "- Recent commits:", "more": " and {n} more",
    },
    "pt-BR": {
        "unverified": " [nao verificado]", "meta_title": "Metainfo da sessao", "written_at": "Gravada em", "repository": "Repositorio",
        "expected": ("Modelo", "Pedido original", "Status"),
        "sections": ("O que foi feito", "Decisoes e por que", "Proximos passos", "O que falhou ou travou"),
        "git_title": "## Estado do git", "detached": "HEAD solta", "tip": ", ponta {tip}", "no_commits": ", sem commits",
        "vs_base": "- Em relacao a base {base}: {ahead} a frente, {behind} atras", "no_base": "- Base: nao encontrada",
        "modified": "- Arquivos modificados: {n}", "untracked": "- Arquivos novos (nao rastreados): {n}", "stashes": "- Stashes: {n}",
        "worktrees": "- Outros worktrees: ", "commits": "- Commits recentes:", "more": " e mais {n}",
    },
}

# Every message the command line prints, in both languages. Same keys and {placeholders} in both (a test enforces
# it); both plain ASCII, so the pt-BR side is the accent-free Portuguese of 0.3.1, and a key ending in `_1` is the
# form used when n == 1.
MSG = {
    "en": {
        "git_missing": "git not found ({e})", "not_repo": "{path} is not a git repository",
        "no_base": "the base '{base}' does not exist", "ambiguous": "the commit id is ambiguous",
        "no_commit": "the commit does not exist", "control": "the citation has control characters",
        "bad_commit": "invalid commit id (7 to 40 hexadecimal characters)",
        "bad_branch": "invalid branch name (it cannot be a revision expression)",
        "no_branch": "the branch does not exist (local or remote)",
        "not_relative": "the path must be relative to the repository root", "outside": "the path leaves the repository",
        "no_file": "the file does not exist in the working tree",
        "symlink": "{folder} is a symbolic link: I refuse to write or read through it (use --out to choose the folder)",
        "meta_control": "the metainfo has control characters",
        "meta_line": "invalid metainfo on line {line} of the draft: use 'Key: Value', one per line, between two '---'",
        "meta_empty": "the metainfo needs a key and a value",
        "meta_long": "metainfo '{key}': a key of up to {max_key} and a value of up to {max_value} characters (shorten it)",
        "meta_reserved": "metainfo '{key}': repeated or reserved key (the tool writes 'Written at' and 'Repository' itself)",
        "meta_citation": "metainfo '{key}': a typed citation (commit:, branch:, file:) does not go in the header, put it in a section",
        "draft_utf8": "the draft has characters that do not fit in UTF-8: nothing was written",
        "mkdir_failed": "could not create the notes folder {folder}: {e}", "create_failed": "could not create the note in {folder}: {e}",
        "write_failed": "could not write the note {path}: {e}",
        "d_branch": "the branch was {old} and is now {new}", "d_detached": "(detached HEAD)",
        "d_new_commits": " ({n} new commits)", "d_new_commits_1": " ({n} new commit)", "d_old_gone": " (the old commit no longer exists)",
        "d_tip": "the tip of {branch} moved: {old} -> {new}{extra}",
        "d_counts": "ahead/behind the base changed: {a}/{b} -> {c}/{d}",
        "d_gone": "dirty files that are gone: {names}", "d_new": "new dirty files: {names}", "more": " and {n} more",
        "read_failed": "could not read the note {path}: {e}", "no_note": "there is no note in {folder}/ (run `write` first)",
        "not_note": "{path} is not a note file", "not_file": "{path} is not a file",
        "line": "  line {line}: {type}:{value}  {flag}", "f_ok": "ok", "f_unverified": "NOT VERIFIED", "f_moved": "MOVED (the tip is another)",
        "draft_not_utf8": "could not read the draft: it is not valid UTF-8", "draft_failed": "could not read the draft: {e}",
        "saved": "note saved to {path}",
        "n_citations": "{n} citations", "n_citations_1": "{n} citation",
        "n_unverified": "{n} not verified", "n_unverified_1": "{n} not verified",
        "n_problems": "{n} with problems", "n_problems_1": "{n} with a problem",
        "missing_section": "warning: section '{name}' is missing", "missing_meta": "warning: metainfo '{name}' is missing",
        "checked_now": "--- checked now ---", "note": "note: {path}",
        "no_data": "the note has no data block: only the citations were checked",
        "changed": "changed since the note:", "unchanged": "nothing changed in git since the note",
        "error": "error: {e}", "too_deep": "a structure of the note is too deep to read",
        "not_utf8": "text that does not fit in UTF-8 ({e})", "io": "read or write failure ({e})",
    },
    "pt-BR": {
        "git_missing": "git nao encontrado ({e})", "not_repo": "{path} nao e um repositorio git",
        "no_base": "a base '{base}' nao existe", "ambiguous": "o id de commit e ambiguo",
        "no_commit": "o commit nao existe", "control": "a citacao tem caracteres de controle",
        "bad_commit": "id de commit invalido (7 a 40 caracteres hexadecimais)",
        "bad_branch": "nome de branch invalido (nao pode ser uma expressao de revisao)",
        "no_branch": "a branch nao existe (local ou remota)",
        "not_relative": "o caminho deve ser relativo a raiz do repositorio", "outside": "o caminho sai do repositorio",
        "no_file": "o arquivo nao existe na arvore de trabalho",
        "symlink": "{folder} e um link simbolico: recuso escrever ou ler por ele (use --out para escolher a pasta)",
        "meta_control": "a metainfo tem caracteres de controle",
        "meta_line": "metainfo invalida na linha {line} do rascunho: use 'Chave: Valor', uma por linha, entre dois '---'",
        "meta_empty": "a metainfo precisa de chave e valor",
        "meta_long": "metainfo '{key}': chave de ate {max_key} e valor de ate {max_value} caracteres (resuma)",
        "meta_reserved": "metainfo '{key}': chave repetida ou reservada (a ferramenta ja grava 'Gravada em' e 'Repositorio')",
        "meta_citation": "metainfo '{key}': citacao tipada (commit:, branch:, file:) nao entra no cabecalho, ponha-a numa secao",
        "draft_utf8": "o rascunho tem caracteres que nao cabem em UTF-8: nada foi gravado",
        "mkdir_failed": "nao consegui criar a pasta das notas {folder}: {e}", "create_failed": "nao consegui criar a nota em {folder}: {e}",
        "write_failed": "nao consegui gravar a nota {path}: {e}",
        "d_branch": "a branch era {old} e agora e {new}", "d_detached": "(HEAD solta)",
        "d_new_commits": " ({n} commits novos)", "d_new_commits_1": " ({n} commit novo)", "d_old_gone": " (o commit antigo nao existe mais)",
        "d_tip": "a ponta de {branch} mudou: {old} -> {new}{extra}",
        "d_counts": "a frente/atras da base mudou: {a}/{b} -> {c}/{d}",
        "d_gone": "arquivos sujos que ja nao estao: {names}", "d_new": "arquivos sujos novos: {names}", "more": " e mais {n}",
        "read_failed": "nao consegui ler a nota {path}: {e}", "no_note": "nao ha nota em {folder}/ (rode `write` primeiro)",
        "not_note": "{path} nao e um arquivo de nota", "not_file": "{path} nao e um arquivo",
        "line": "  linha {line}: {type}:{value}  {flag}", "f_ok": "ok", "f_unverified": "NAO VERIFICADO", "f_moved": "MUDOU (a ponta e outra)",
        "draft_not_utf8": "nao consegui ler o rascunho: nao e UTF-8 valido", "draft_failed": "nao consegui ler o rascunho: {e}",
        "saved": "nota gravada em {path}",
        "n_citations": "{n} citacoes", "n_citations_1": "{n} citacao",
        "n_unverified": "{n} nao verificadas", "n_unverified_1": "{n} nao verificada",
        "n_problems": "{n} com problema", "n_problems_1": "{n} com problema",
        "missing_section": "aviso: falta a secao '{name}'", "missing_meta": "aviso: falta a metainfo '{name}'",
        "checked_now": "--- conferencia agora ---", "note": "nota: {path}",
        "no_data": "a nota nao tem o bloco de dados: so as citacoes foram conferidas",
        "changed": "mudou desde a nota:", "unchanged": "nada mudou no git desde a nota",
        "error": "erro: {e}", "too_deep": "uma estrutura da nota e funda demais para ser lida",
        "not_utf8": "texto que nao cabe em UTF-8 ({e})", "io": "falha de leitura ou escrita ({e})",
    },
}

# git never prompts, never runs the repository's hooks or a filesystem monitor, and never uses the network
GIT_FLAGS = ["-c", "core.quotepath=off", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=" + os.devnull,
             "-c", "protocol.allow=never", "-c", "log.showSignature=false", "-c", "i18n.logOutputEncoding=UTF-8"]


class HandoffError(Exception):
    """Something the person must fix before the tool can run (exit code 2)."""


def env_lang():
    """CAPYBARA_LANG when it is exactly one of LANGS. Any other value is ignored, silently: a shell setting must
    never break a command, and a warning on every run would be noise in the agent's context."""
    value = os.environ.get(ENV_LANG)
    return value if value in LANGS else None


def pick_lang(*candidates):
    """The first candidate that is one of LANGS (--lang), then CAPYBARA_LANG, then English. A note never sets the
    language of a run: an old note is Portuguese, and it must not turn an English session's output Portuguese."""
    for cand in candidates:
        if isinstance(cand, str) and cand in LANGS:
            return cand
    return env_lang() or DEFAULT_LANG


def use_lang(*candidates):
    """Set the language of this run's messages (see pick_lang) and return it."""
    global CLI_LANG
    CLI_LANG = pick_lang(*candidates)
    return CLI_LANG


def say(msg_id, /, **values):
    """One message in the language of this run; with n == 1 the `_1` form wins when there is one. The template is
    ours, the values are data (substituted, never parsed)."""
    table = MSG[CLI_LANG]
    if values.get("n") == 1 and msg_id + "_1" in table:
        msg_id += "_1"
    return table[msg_id].format(**values)


def note_text(lang, key, **values):
    """One fixed text of a note in `lang` (an unknown language is English)."""
    text = NOTE[lang if lang in LANGS else DEFAULT_LANG][key]
    return text.format(**values) if values else text


# where git looks for the repository: inherited from a hook or a wrapper, these would make `-C path` judge another tree
GIT_LOCATION_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY",
                     "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE", "GIT_PREFIX", "GIT_IMPLICIT_WORK_TREE")


def git(root, *args):
    env = {k: v for k, v in os.environ.items() if k not in GIT_LOCATION_VARS}
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        r = subprocess.run(["git", *GIT_FLAGS, "-C", str(root), *args], capture_output=True, env=env)
    except OSError as e:
        raise HandoffError(say("git_missing", e=e.strerror or e))
    except ValueError:  # an embedded NUL in an argument: git is never run, the answer is "no"
        return 1, ""
    return r.returncode, r.stdout.decode("utf-8", "replace")


def repo_root(path):
    rc, out = git(path, "rev-parse", "--show-toplevel")
    if rc != 0:
        raise HandoffError(say("not_repo", path=path))
    return Path(out.strip())


def resolve(root, ref):
    """The commit a ref names, or None. Full ref names are used where it matters so a tag cannot shadow a branch."""
    rc, out = git(root, "rev-parse", "--verify", "--quiet", ref + "^{commit}")
    return out.strip() if rc == 0 and out.strip() else None


def detect_base(root, override=None):
    """--base, else the branch origin/HEAD points to, else the first of base, main, master."""
    if override:
        if resolve(root, override) is None:
            raise HandoffError(say("no_base", base=override))
        return override
    rc, out = git(root, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
    if rc == 0 and "/" in out.strip():
        short = out.strip().split("/", 1)[1]
        if resolve(root, "refs/heads/" + short):
            return short
    for name in ("base", "main", "master"):
        if resolve(root, "refs/heads/" + name):
            return name
    return None


def base_ref(root, base):
    """The full ref to compare with: the local branch when there is one."""
    local = "refs/heads/" + base
    return local if resolve(root, local) else base


def worktrees(root):
    rc, out = git(root, "worktree", "list", "--porcelain")
    items, cur = [], {}
    for line in out.splitlines() + [""]:
        if not line:
            if cur.get("path"):
                items.append(cur)
            cur = {}
        elif line.startswith("worktree "):
            cur["path"] = line[len("worktree "):]
        elif line.startswith("branch "):
            cur["branch"] = line[len("branch refs/heads/"):] if line.startswith("branch refs/heads/") else line[len("branch "):]
    return items


def collect(root, base=None):
    """The git facts a handoff note is built on: all of them come from git, none from memory."""
    rc, head = git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    branch = head.strip() if rc == 0 else None
    tip = resolve(root, "HEAD")
    rc, up = git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    upstream = up.strip() if rc == 0 and up.strip() else None
    base_name = detect_base(root, base)
    ahead = behind = None
    if base_name and tip:
        rc, counts = git(root, "rev-list", "--left-right", "--count", f"{base_ref(root, base_name)}...HEAD")
        if rc == 0 and len(counts.split()) == 2:
            behind, ahead = (int(n) for n in counts.split())
    rc, status = git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    modified, untracked = [], []
    entries = status.split("\0")
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if len(entry) < 4:
            continue
        code, path = entry[:2], entry[3:]
        if code[0] in "RC":  # renames carry the old name as a second field
            i += 1
        if path.startswith(NOTE_DIR + "/"):  # the notes are not work in progress; otherwise writing one would change the git state
            continue
        (untracked if code == "??" else modified).append(path)
    rc, stashes = git(root, "stash", "list")
    rc, log = git(root, "log", f"-{RECENT}", "--format=%h%x00%s") if tip else (1, "")
    commits = [dict(zip(("sha", "subject"), line.split("\0", 1))) for line in log.splitlines() if "\0" in line]
    return {"schema": SCHEMA, "branch": branch, "tip": tip, "upstream": upstream, "base": base_name,
            "ahead": ahead, "behind": behind, "modified": sorted(modified), "untracked": sorted(untracked),
            "stashes": len([l for l in stashes.splitlines() if l]),
            "worktrees": [{"path": w["path"], "branch": w.get("branch")} for w in worktrees(root)],
            "commits": commits}


CITATION = re.compile(r"`(commit|branch|file):([^`\s]+)`")
HEX_ID = re.compile(r"[0-9a-fA-F]{7,40}")
LINE_SUFFIX = re.compile(r":\d+(?::\d+)?$")
UNVERIFIED = {lang: NOTE[lang]["unverified"] for lang in LANGS}
BAD_BRANCH_CHARS = re.compile(r"[~^:?*\[\\\s\x00-\x1f\x7f]")


def find_citations(text):
    """Every typed citation in a note: `commit:abc1234`, `branch:feat/x`, `file:path/to/f.py:42`. An untyped
    backtick span is prose and is never checked. Returns (kind, value, start, end) per citation."""
    return [(m.group(1), m.group(2), m.start(), m.end()) for m in CITATION.finditer(text)]


def commit_by_id(root, hex_id):
    """The commit whose id starts with `hex_id`, or (None, why). Only object ids are looked at (git's
    --disambiguate lists ids, never refs), so a branch or tag named like a hex id cannot stand in for one."""
    rc, out = git(root, "rev-parse", "--disambiguate=" + hex_id.lower())
    commits = []
    for oid in out.split():
        rc, kind = git(root, "cat-file", "-t", oid)
        if rc == 0 and kind.strip() == "commit" and oid.startswith(hex_id.lower()):
            commits.append(oid)
    if len(commits) == 1:
        return commits[0], ""
    return None, say("ambiguous" if commits else "no_commit")


def check_citation(root, kind, value):
    """(verified, sha, why): `sha` is what the citation pointed at (commits and branches), `why` explains a failure."""
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        return False, None, say("control")
    if kind == "commit":
        if not HEX_ID.fullmatch(value):
            return False, None, say("bad_commit")
        sha, why = commit_by_id(root, value)
        return (True, sha, "") if sha else (False, None, why)
    if kind == "branch":
        # a plain branch name only: no revision expression (main~1, main^, main@{0}, a..b, a:b) and no option
        if BAD_BRANCH_CHARS.search(value) or "@{" in value or ".." in value or value.startswith("-"):
            return False, None, say("bad_branch")
        for ref in ("refs/heads/" + value, "refs/remotes/" + value):
            rc, out = git(root, "show-ref", "--verify", "--hash", ref)  # exact ref, no revision parsing
            if rc == 0 and out.strip():
                return True, resolve(root, ref), ""
        return False, None, say("no_branch")
    path = LINE_SUFFIX.sub("", value)
    parts = path.split("/")
    if path.startswith("/") or ".." in parts or not path:
        return False, None, say("not_relative")
    target = Path(root) / path
    try:  # a symlink that leads outside the repository is not a file of the repository
        inside = target.resolve().is_relative_to(Path(root).resolve())
    except (OSError, RuntimeError, ValueError):
        inside = False
    if not inside:
        return False, None, say("outside")
    return ((True, None, "") if target.exists() else (False, None, say("no_file")))


def check_text(root, text):
    """One result per citation, in order."""
    out = []
    for kind, value, start, end in find_citations(text):
        ok, sha, why = check_citation(root, kind, value)
        line = text.count("\n", 0, start) + 1
        out.append({"type": kind, "value": value, "verified": ok, "sha": sha, "why": why, "line": line, "start": start, "end": end})
    return out


def mark_unverified(text, results, lang=DEFAULT_LANG):
    """Append ` [not verified]` (pt-BR ` [nao verificado]`) after each citation that failed, once: a citation
    already marked in either language is never marked again and no text is ever removed."""
    out, last = [], 0
    for r in results:
        out.append(text[last:r["end"]])
        last = r["end"]
        if not r["verified"] and not any(text.startswith(mark, r["end"]) for mark in UNVERIFIED.values()):
            out.append(UNVERIFIED[lang if lang in LANGS else DEFAULT_LANG])
    out.append(text[last:])
    return "".join(out)


SECTIONS = {lang: NOTE[lang]["sections"] for lang in LANGS}  # the draft's headings: either language counts
DATA_OPEN = "<!-- handoff:data "
DATA_CLOSE = "} -->"
NOTE_NAME = re.compile(r"(\d{4}-\d{2}-\d{2}-\d{6})(?:-(\d+))?\.md")
SHOWN = 8  # file names listed per group in the git section
NOW = time.localtime  # a function: the tests replace it


def data_block(data):
    """The machine-readable part of a note, as one HTML comment. `--` is escaped so no text inside it can end
    the comment early."""
    text = json.dumps(data, ensure_ascii=True, separators=(",", ":")).replace("--", "-\\u002d")
    return f"<!-- handoff:data {text} -->"


FACT_TYPES = {"branch": (str, type(None)), "tip": (str, type(None)), "upstream": (str, type(None)), "base": (str, type(None)),
              "ahead": (int, type(None)), "behind": (int, type(None)), "stashes": (int,)}


def valid_facts(facts):
    """A note is plain text anyone can edit or plant: its data block is used only if it has exactly the shape
    `collect` writes."""
    if not isinstance(facts, dict):
        return False
    for key, types in FACT_TYPES.items():
        if key not in facts or not isinstance(facts[key], types) or isinstance(facts[key], bool):
            return False
    return all(isinstance(facts.get(k), list) and all(isinstance(x, str) for x in facts[k]) for k in ("modified", "untracked"))


def last_data_block(text):
    """The last data block of a note as (start, end, json text), or None, found in linear time. A block is
    `<!-- handoff:data {` up to the first `} -->` on the same line. A regex with a lazy run is quadratic on a line
    that repeats the opener (a planted note can hold a megabyte of it), so the text is walked backwards by opener:
    an opener with no closer after it on its line is skipped together with every earlier opener of that line (their
    closer would also be after it), so each line is looked at once."""
    opener = DATA_OPEN + "{"
    limit = len(text)
    while True:
        i = text.rfind(opener, 0, limit)
        if i < 0:
            return None
        line_end = text.find("\n", i)
        if line_end < 0:
            line_end = len(text)
        j = text.find(DATA_CLOSE, i + len(opener), line_end)
        if j >= 0:
            return i, j + len(DATA_CLOSE), text[i + len(DATA_OPEN):j + 1]
        limit = text.rfind("\n", 0, i) + 1  # the start of this line: its earlier openers fail too, so go to the line before


def parse_data(text):
    found = last_data_block(text)
    if not found:
        return None
    try:
        data = json.loads(found[2])
    except (ValueError, RecursionError):  # not JSON, or nested so deep that reading it overflows: no usable block
        return None
    return data if isinstance(data, dict) and valid_facts(data.get("facts")) else None


def notes_folder(root):
    """The default notes folder. A symlink there (a hostile repository can track one) would send the notes, or
    the reading of them, somewhere else, so it is refused."""
    folder = Path(root) / NOTE_DIR
    if folder.is_symlink():
        raise HandoffError(say("symlink", folder=folder))
    return folder


def names(items, lang=None):
    """Up to SHOWN names; `lang` is a note's language, None the language of this run's messages."""
    shown = ", ".join(items[:SHOWN])
    if len(items) <= SHOWN:
        return shown
    return shown + (note_text(lang, "more", n=len(items) - SHOWN) if lang else say("more", n=len(items) - SHOWN))


META_TITLE = {lang: NOTE[lang]["meta_title"] for lang in LANGS}
META_RESERVED = tuple(NOTE[lang][k].lower() for lang in LANGS for k in ("written_at", "repository"))  # rows the tool writes itself
META_EXPECTED = {lang: NOTE[lang]["expected"] for lang in LANGS}  # what the agent always knows: a missing one is a warning
MAX_META_KEY = 40
MAX_META_VALUE = 1000
FRONT_LINE = re.compile(r"([^:]{1,%d}):[ \t]+(\S.*)" % MAX_META_KEY)
META_PART = re.compile(r"\| (?:" + "|".join(map(re.escape, META_TITLE.values())) + r") \| \|\n(?:\|[^\n]*\n)*\n")


def clean_meta_text(text):
    """One line, single spaces. Control characters are refused, never dropped."""
    text = " ".join(text.split())
    if any(ord(c) < 32 or ord(c) == 127 for c in text):
        raise HandoffError(say("meta_control"))
    return text


def split_front(draft):
    """The metainfo block at the top of a draft: `---`, one `Chave: Valor` per line, `---`. Returns
    (rows, the rest of the draft, how many lines the block took). A draft that does not start with such a block
    comes back untouched, and a block with a line of another shape is an error, so nothing is dropped quietly."""
    lines = draft.split("\n")
    first = next((i for i, l in enumerate(lines) if l.strip()), None)
    if first is None or lines[first].strip() != "---":
        return [], draft, 0
    close = next((j for j in range(first + 1, len(lines)) if lines[j].strip() == "---"), None)
    if close is None:
        return [], draft, 0
    rows = []
    for n in range(first + 1, close):
        if not lines[n].strip():
            continue
        m = FRONT_LINE.fullmatch(lines[n].strip())
        if not m:
            raise HandoffError(say("meta_line", line=n + 1))
        rows.append((m.group(1), m.group(2)))
    return rows, "\n".join(lines[close + 1:]), close + 1


def clean_meta(rows):
    """The agent's rows, validated: single line, no duplicate, none of the tool's own keys, and no typed citation
    (a citation is checked only where the tool checks them: in the sections)."""
    out, seen = [], set()
    for key, value in rows:
        key, value = clean_meta_text(key), clean_meta_text(value)
        if not key or not value:
            raise HandoffError(say("meta_empty"))
        if len(key) > MAX_META_KEY or len(value) > MAX_META_VALUE:
            raise HandoffError(say("meta_long", key=key[:20], max_key=MAX_META_KEY, max_value=MAX_META_VALUE))
        if key.lower() in META_RESERVED or key.lower() in seen:
            raise HandoffError(say("meta_reserved", key=key))
        if CITATION.search(key) or CITATION.search(value):
            raise HandoffError(say("meta_citation", key=key))
        seen.add(key.lower())
        out.append((key, value))
    return out


def meta_rows(root, agent_rows, when, lang=DEFAULT_LANG):
    """The header rows: the agent's, then what the tool knows by itself (its keys in the note's language)."""
    own = [(note_text(lang, "written_at"), when), (note_text(lang, "repository"), Path(root).name)]
    return agent_rows + [(k, clean_meta_text(v).replace("`", "'")) for k, v in own]


def meta_section(rows, lang=DEFAULT_LANG):
    esc = lambda text: text.replace("|", "\\|")
    return "\n".join([f"| {note_text(lang, 'meta_title')} | |", "|---|---|"] + [f"| {esc(k)} | {esc(v)} |" for k, v in rows])


def valid_meta(meta):
    """The rows a note recorded, or None. The data block is untrusted: whatever is not a list of string pairs is no header."""
    if isinstance(meta, list) and all(isinstance(r, list) and len(r) == 2 and all(isinstance(x, str) for x in r) for r in meta):
        return [tuple(r) for r in meta]
    return None


def missing_meta(rows, lang=DEFAULT_LANG):
    """The expected keys the agent left out, named in `lang`. A key counts in either language (`Model` or `Modelo`)."""
    have = {k.lower() for k, _ in rows}
    return [META_EXPECTED[lang][i] for i in range(len(META_EXPECTED[lang]))
            if not any(META_EXPECTED[other][i].lower() in have for other in LANGS)]


def git_section(facts, lang=DEFAULT_LANG):
    """The facts, as prose with no backtick spans (those are reserved for typed citations), in `lang`."""
    n = lambda key, **values: note_text(lang, key, **values)
    branch = facts["branch"] or f"({n('detached')})"
    tip = n("tip", tip=facts["tip"][:7]) if facts["tip"] else n("no_commits")
    lines = [n("git_title"), "", f"- Branch: {branch}{tip}"]
    if facts["upstream"]:
        lines.append(f"- Upstream: {facts['upstream']}")
    if facts["base"] and facts["ahead"] is not None:
        lines.append(n("vs_base", base=facts["base"], ahead=facts["ahead"], behind=facts["behind"]))
    else:
        lines.append(n("no_base"))
    lines.append(n("modified", n=len(facts["modified"])) + (f" ({names(facts['modified'], lang)})" if facts["modified"] else ""))
    lines.append(n("untracked", n=len(facts["untracked"])) + (f" ({names(facts['untracked'], lang)})" if facts["untracked"] else ""))
    lines.append(n("stashes", n=facts["stashes"]))
    others = [w for w in facts["worktrees"][1:]]
    if others:
        lines.append(n("worktrees") + ", ".join(f"{w['path']} ({w['branch'] or n('detached')})" for w in others))
    if facts["commits"]:
        lines += [n("commits")] + [f"  - {c['sha']} {c['subject']}" for c in facts["commits"]]
    return "\n".join(lines)


def missing_sections(draft, lang=DEFAULT_LANG):
    """The sections the draft has no heading for, named in `lang`. A heading counts in either language."""
    has = lambda name: re.search(rf"^#{{1,6}}[ \t]+{re.escape(name)}[ \t]*$", draft, re.M | re.I)
    return [SECTIONS[lang][i] for i in range(len(SECTIONS[lang])) if not any(has(SECTIONS[other][i]) for other in LANGS)]


def render_note(facts, meta, draft, results, when, lang=DEFAULT_LANG):
    """The note in `lang`; its data block records the language (a note written before 0.4.0 has none: pt-BR)."""
    cites = [{"type": r["type"], "value": r["value"], "sha": r["sha"], "verified": r["verified"]} for r in results]
    data = {"schema": SCHEMA, "lang": lang, "facts": facts, "meta": [list(r) for r in meta], "citations": cites}
    return (f"# Handoff - {when} - {facts['branch'] or note_text(lang, 'detached')}\n\n" + meta_section(meta, lang) + "\n\n"
            + git_section(facts, lang) + "\n\n" + draft.strip("\n") + "\n\n" + data_block(data) + "\n")


def write_note(root, draft, out_dir=None, base=None, lang=DEFAULT_LANG):
    """Check the draft's citations, mark the ones that fail, and save the note, in `lang`, in a new file (never over
    another)."""
    facts = collect(root, base)
    agent_rows, body, skipped = split_front(draft)
    agent_rows = clean_meta(agent_rows)
    results = check_text(root, body)
    when = time.strftime("%Y-%m-%d %H:%M", NOW())
    meta = meta_rows(root, agent_rows, when, lang)
    text = render_note(facts, meta, mark_unverified(body, results, lang), results, when, lang)
    for r in results:  # the lines the person wrote, not the lines left after the metainfo block
        r["line"] += skipped
    try:  # encoded before any file exists: a text that cannot be written must not leave an empty note behind
        payload = text.encode("utf-8")
    except UnicodeError:
        raise HandoffError(say("draft_utf8"))
    folder = Path(out_dir) if out_dir else notes_folder(root)
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise HandoffError(say("mkdir_failed", folder=folder, e=e.strerror or e))
    stamp = time.strftime("%Y-%m-%d-%H%M%S", NOW())
    name, n = stamp + ".md", 2
    while True:
        try:  # private (the note may name internal paths) and exclusive (two runs in a second never share a file)
            fd = os.open(str(folder / name), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            break
        except FileExistsError:
            name, n = f"{stamp}-{n}.md", n + 1
        except OSError as e:
            raise HandoffError(say("create_failed", folder=folder, e=e.strerror or e))
    try:
        view = memoryview(payload)
        while view:
            view = view[os.write(fd, view):]
    except OSError as e:  # never leave a partial note: it would be the newest one and shadow the last good note
        try:
            os.close(fd)
        finally:
            try:
                os.unlink(str(folder / name))
            except OSError:
                pass
        raise HandoffError(say("write_failed", path=folder / name, e=e.strerror or e))
    os.close(fd)
    return {"path": str(folder / name), "facts": facts, "meta": meta, "citations": results,
            "missing": missing_sections(body, lang), "missing_meta": missing_meta(agent_rows, lang)}


TITLE = re.compile(r"# Handoff - [^\n]*\n\n")
GIT_PART = re.compile(r"(?:" + "|".join(re.escape(NOTE[lang]["git_title"]) for lang in LANGS) + r")\n\n(?:[^\n]+\n)+")


def tool_spans(text):
    """The parts of a note the tool wrote itself: the title, the metainfo header and the git section (commit
    subjects, branch and file names, quoted verbatim) and the data block. They are not the agent's citations and
    are never checked."""
    spans = []
    title = TITLE.match(text)
    if title:
        pos = title.end()
        data = parse_data(text)
        meta = valid_meta(data.get("meta")) if data else None
        recorded = data.get("lang") if data and data.get("lang") in LANGS else "pt-BR"  # no lang: a note from before 0.4.0
        langs = [recorded] + [lang for lang in LANGS if lang != recorded]  # the recorded language first, then the other
        header = None
        if meta is not None:  # the exact rendering of the recorded rows, as for the git section below
            for lang in langs:
                exact = meta_section(meta, lang) + "\n\n"
                if text.startswith(exact, pos):
                    header = pos + len(exact)
                    break
        if header is None:
            part = META_PART.match(text, pos)
            header = part.end() if part else pos  # a note written before the header existed has none
        end = None
        if data:  # the exact rendering of the recorded facts, so even a file name with a blank line in it is covered
            for lang in langs:
                try:
                    section = git_section(data["facts"], lang) + "\n"
                    if text.startswith(section, header):
                        end = header + len(section)
                        break
                except (KeyError, TypeError, ValueError, AttributeError):
                    end = None
        if end is None:
            part = GIT_PART.match(text, header)
            end = part.end() if part else header
        spans.append((0, end))
    block = last_data_block(text)
    if block:
        spans.append((block[0], block[1]))
    return spans


def check_note(root, text):
    """The citations of a note or a draft: only the agent's own text. The tool's parts are blanked out (same length,
    newlines kept) so positions and line numbers still point into the note. `write`, `resume` and `verify` all go
    through here, so they agree on the set of citations."""
    chars = list(text)
    for start, end in tool_spans(text):
        for i in range(start, end):
            if chars[i] != "\n":
                chars[i] = " "
    return check_text(root, "".join(chars))


def note_key(name):
    m = NOTE_NAME.fullmatch(name)
    return (m.group(1), int(m.group(2) or 1)) if m else None


def newest_note(folder):
    """The newest note of a folder: by its timestamp, then by its collision number. Anything that is not a regular
    note file is ignored."""
    best = None
    for p in Path(folder).glob("*.md"):
        key = note_key(p.name)
        if key and p.is_file() and not p.is_symlink() and (best is None or key > best[0]):
            best = (key, p)
    return best[1] if best else None


def drift(root, then, now):
    """What changed between the facts a note recorded and the repository now, as a list of messages."""
    out = []
    if then["branch"] != now["branch"]:
        out.append(say("d_branch", old=then["branch"] or say("d_detached"), new=now["branch"] or say("d_detached")))
    elif then["tip"] != now["tip"]:
        extra = ""
        if then["tip"] and resolve(root, then["tip"]):
            rc, count = git(root, "rev-list", "--count", f"{then['tip']}..HEAD")
            extra = say("d_new_commits", n=int(count.strip())) if rc == 0 and count.strip().isdigit() else ""
        else:
            extra = say("d_old_gone")
        out.append(say("d_tip", branch=now["branch"] or "HEAD", old=(then["tip"] or "-")[:7], new=(now["tip"] or "-")[:7], extra=extra))
    if (then["ahead"], then["behind"]) != (now["ahead"], now["behind"]):
        out.append(say("d_counts", a=then["ahead"], b=then["behind"], c=now["ahead"], d=now["behind"]))
    before, after = set(then["modified"] + then["untracked"]), set(now["modified"] + now["untracked"])
    if before - after:
        out.append(say("d_gone", names=names(sorted(before - after))))
    if after - before:
        out.append(say("d_new", names=names(sorted(after - before))))
    if then["stashes"] != now["stashes"]:
        out.append(f"stashes: {then['stashes']} -> {now['stashes']}")
    return out


def read_note(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise HandoffError(say("read_failed", path=path, e=e.strerror or e))


def recorded_citations(data):
    """The (type, value) -> commit a note recorded. The block is untrusted: whatever is not shaped right is skipped."""
    out = {}
    cites = (data or {}).get("citations")
    for c in cites if isinstance(cites, list) else []:
        if isinstance(c, dict) and isinstance(c.get("type"), str) and isinstance(c.get("value"), str):
            out[(c["type"], c["value"])] = c.get("sha")
    return out


def resume(root, file=None):
    """The newest note, every citation checked again, and what drifted since it was written."""
    path = Path(file) if file else newest_note(notes_folder(root))
    if path is None:
        raise HandoffError(say("no_note", folder=NOTE_DIR))
    if path.is_symlink() or not path.is_file():
        raise HandoffError(say("not_note", path=path))
    text = read_note(path)
    data = parse_data(text)
    results = check_note(root, text)
    recorded = recorded_citations(data)
    for r in results:
        before = recorded.get((r["type"], r["value"]))
        r["moved"] = bool(r["verified"] and before and r["sha"] and before != r["sha"])
    changes = None
    if data:
        try:
            now = collect(root, data["facts"].get("base"))
        except HandoffError:  # the recorded base is gone (or is not a ref at all): detect it again
            now = collect(root)
        changes = drift(root, data["facts"], now)
    return {"path": str(path), "text": text, "has_data": data is not None, "citations": results, "drift": changes}


def facts_report(facts):
    return git_section(facts, CLI_LANG)


def citation_lines(results):
    out = []
    for r in results:
        flag = say("f_ok") if r["verified"] else say("f_unverified")
        if r.get("moved"):
            flag = say("f_moved")
        out.append(say("line", line=r["line"], type=r["type"], value=r["value"], flag=flag) + (f" ({r['why']})" if r["why"] else ""))
    return out


def clean_result(results):
    return [{k: v for k, v in r.items() if k not in ("start", "end")} for r in results]


def parser():
    p = argparse.ArgumentParser(prog="handoff.py", description="End-of-session note with git facts and checked citations.")
    p.add_argument("--version", action="version", version=f"handoff {VERSION}")
    sub = p.add_subparsers(dest="cmd", required=True)
    lang = argparse.ArgumentParser(add_help=False)  # every command takes --lang (the help text is English in both)
    lang.add_argument("--lang", choices=LANGS, default=None,
                      help="language of the messages, and of the note for write (default: CAPYBARA_LANG, then en)")
    c = sub.add_parser("collect", parents=[lang], help="the git facts, as JSON or text")
    c.add_argument("repo", nargs="?", default=".")
    c.add_argument("--base")
    c.add_argument("--json", action="store_true")
    w = sub.add_parser("write", parents=[lang], help="check the citations of a draft and save the note")
    w.add_argument("repo", nargs="?", default=".")
    w.add_argument("--draft", required=True, help="file with the draft, or - for standard input")
    w.add_argument("--out", help=f"notes folder (default: {NOTE_DIR}/ at the root)")
    w.add_argument("--base")
    w.add_argument("--json", action="store_true")
    v = sub.add_parser("verify", parents=[lang], help="check the citations of a note or a draft")
    v.add_argument("file")
    v.add_argument("repo", nargs="?", default=".")
    v.add_argument("--json", action="store_true")
    r = sub.add_parser("resume", parents=[lang], help="show the newest note and what changed since then")
    r.add_argument("repo", nargs="?", default=".")
    r.add_argument("--file", help="a specific note (default: the newest)")
    r.add_argument("--json", action="store_true")
    return p


def read_draft(arg):
    try:
        return sys.stdin.read() if arg == "-" else Path(arg).read_text(encoding="utf-8", errors="replace")
    except UnicodeError:
        raise HandoffError(say("draft_not_utf8"))
    except OSError as e:
        raise HandoffError(say("draft_failed", e=e))


def emit(args, payload, text):
    print(json.dumps(payload, indent=2, ensure_ascii=False) if args.json else text)


def main(argv=None):
    """Run one command. The language of its messages (and of the note `write` saves) is set here: --lang, then
    CAPYBARA_LANG, then en; it is put back afterwards, so an in-process caller (the tests) never inherits another
    run's language."""
    global CLI_LANG
    args = parser().parse_args(argv)
    before = CLI_LANG
    use_lang(args.lang)
    try:
        return run_command(args)
    finally:
        CLI_LANG = before


def run_command(args):
    try:
        root = repo_root(args.repo)
        if args.cmd == "collect":
            facts = collect(root, args.base)
            emit(args, facts, facts_report(facts))
            return 0
        if args.cmd == "write":
            res = write_note(root, read_draft(args.draft), args.out, args.base, CLI_LANG)
            bad = [c for c in res["citations"] if not c["verified"]]
            lines = [say("saved", path=res["path"]), say("n_citations", n=len(res["citations"])) + ", " + say("n_unverified", n=len(bad))]
            lines += citation_lines(bad)
            lines += [say("missing_section", name=name) for name in res["missing"]]
            lines += [say("missing_meta", name=name) for name in res["missing_meta"]]
            emit(args, {"schema": SCHEMA, "path": res["path"], "citations": clean_result(res["citations"]), "missing_sections": res["missing"],
                        "missing_meta": res["missing_meta"]}, "\n".join(lines))
            return 1 if bad else 0
        if args.cmd == "verify":
            path = Path(args.file)
            if path.is_symlink() or not path.is_file():
                raise HandoffError(say("not_file", path=path))
            results = check_note(root, read_note(path))
            bad = [c for c in results if not c["verified"]]
            emit(args, {"schema": SCHEMA, "citations": clean_result(results)},
                 "\n".join([say("n_citations", n=len(results)) + ", " + say("n_unverified", n=len(bad))] + citation_lines(results)))
            return 1 if bad else 0
        res = resume(root, args.file)
        bad = [c for c in res["citations"] if not c["verified"] or c["moved"]]
        changed = res["drift"] or []
        lines = [res["text"].rstrip("\n"), "", say("checked_now"), say("note", path=res["path"])]
        if res["drift"] is None:
            lines.append(say("no_data"))
        lines += ([say("changed")] + [f"  - {m}" for m in changed]) if changed else ([] if res["drift"] is None else [say("unchanged")])
        lines += [say("n_citations", n=len(res["citations"])) + ", " + say("n_problems", n=len(bad))] + citation_lines(bad)
        emit(args, {"schema": SCHEMA, "path": res["path"], "drift": res["drift"], "citations": clean_result(res["citations"])},
             "\n".join(lines))
        return 1 if (bad or changed) else 0
    except HandoffError as e:
        print(say("error", e=e), file=sys.stderr)
        return 2
    except RecursionError:  # the safety net: a failure of the system or of the text is exit 2, never a traceback
        print(say("error", e=say("too_deep")), file=sys.stderr)
        return 2
    except UnicodeError as e:
        print(say("error", e=say("not_utf8", e=e)), file=sys.stderr)
        return 2
    except OSError as e:
        print(say("error", e=say("io", e=e.strerror or e)), file=sys.stderr)
        return 2



if __name__ == "__main__":
    sys.exit(main())

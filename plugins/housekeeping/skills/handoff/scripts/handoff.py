#!/usr/bin/env python3
# handoff 0.2.0 - nota de fim de sessao com fatos do git coletados e citacoes conferidas (somente stdlib e git)
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Diogo Winck
#
# Uso:
#   handoff.py collect [REPO] [--base REF] [--json]                   # fatos do git (branch, ponta, a frente/atras, sujos...)
#   handoff.py write   [REPO] --draft FILE|- [--out DIR] [--base REF] # confere as citacoes e grava .handoff/AAAA-MM-DD-hhmmss.md
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

VERSION = "0.2.0"
SCHEMA = 1  # of the --json output and of the data block inside a note
NOTE_DIR = ".handoff"
RECENT = 5  # commits listed in the note

# git never prompts, never runs the repository's hooks or a filesystem monitor, and never uses the network
GIT_FLAGS = ["-c", "core.quotepath=off", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=" + os.devnull,
             "-c", "protocol.allow=never", "-c", "log.showSignature=false", "-c", "i18n.logOutputEncoding=UTF-8"]


class HandoffError(Exception):
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
        raise HandoffError(f"git nao encontrado ({e.strerror or e})")
    return r.returncode, r.stdout.decode("utf-8", "replace")


def repo_root(path):
    rc, out = git(path, "rev-parse", "--show-toplevel")
    if rc != 0:
        raise HandoffError(f"{path} nao e um repositorio git")
    return Path(out.strip())


def resolve(root, ref):
    """The commit a ref names, or None. Full ref names are used where it matters so a tag cannot shadow a branch."""
    rc, out = git(root, "rev-parse", "--verify", "--quiet", ref + "^{commit}")
    return out.strip() if rc == 0 and out.strip() else None


def detect_base(root, override=None):
    """--base, else the branch origin/HEAD points to, else the first of base, main, master."""
    if override:
        if resolve(root, override) is None:
            raise HandoffError(f"a base '{override}' nao existe")
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
UNVERIFIED = " [nao verificado]"


def find_citations(text):
    """Every typed citation in a note: `commit:abc1234`, `branch:feat/x`, `file:path/to/f.py:42`. An untyped
    backtick span is prose and is never checked. Returns (kind, value, start, end) per citation."""
    return [(m.group(1), m.group(2), m.start(), m.end()) for m in CITATION.finditer(text)]


def check_citation(root, kind, value):
    """(verified, sha, why): `sha` is what the citation pointed at (commits and branches), `why` explains a failure."""
    if kind == "commit":
        if not HEX_ID.fullmatch(value):
            return False, None, "id de commit invalido (7 a 40 caracteres hexadecimais)"
        sha = resolve(root, value)
        return (True, sha, "") if sha else (False, None, "o commit nao existe")
    if kind == "branch":
        for ref in ("refs/heads/" + value, "refs/remotes/" + value):
            sha = resolve(root, ref)
            if sha:
                return True, sha, ""
        return False, None, "a branch nao existe (local ou remota)"
    path = LINE_SUFFIX.sub("", value)
    parts = path.split("/")
    if path.startswith("/") or ".." in parts or not path:
        return False, None, "o caminho deve ser relativo a raiz do repositorio"
    target = Path(root) / path
    try:  # a symlink that leads outside the repository is not a file of the repository
        inside = target.resolve().is_relative_to(Path(root).resolve())
    except (OSError, RuntimeError):
        inside = False
    if not inside:
        return False, None, "o caminho sai do repositorio"
    return ((True, None, "") if target.exists() else (False, None, "o arquivo nao existe na arvore de trabalho"))


def check_text(root, text):
    """One result per citation, in order."""
    out = []
    for kind, value, start, end in find_citations(text):
        ok, sha, why = check_citation(root, kind, value)
        line = text.count("\n", 0, start) + 1
        out.append({"type": kind, "value": value, "verified": ok, "sha": sha, "why": why, "line": line, "start": start, "end": end})
    return out


def mark_unverified(text, results):
    """Append ` [nao verificado]` after each citation that failed, once: a note is never marked twice and no
    text is ever removed."""
    out, last = [], 0
    for r in results:
        out.append(text[last:r["end"]])
        last = r["end"]
        if not r["verified"] and not text.startswith(UNVERIFIED, r["end"]):
            out.append(UNVERIFIED)
    out.append(text[last:])
    return "".join(out)

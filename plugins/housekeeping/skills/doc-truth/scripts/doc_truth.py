#!/usr/bin/env python3
# doc-truth 0.1.0 - confere se o que os documentos dizem existe: caminhos, links, ancoras, paridade EN/PT-BR e versoes (somente stdlib e git)
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Diogo Winck
#
# Uso:
#   doc_truth.py [PATH] [--json] [--config FILE]     # somente leitura; saida 0 limpo, 1 achados, 2 erro
import argparse
import hashlib
import json
import os
import posixpath
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

VERSION = "0.1.0"
SCHEMA = 1  # of the --json output; it is a public contract
CONFIG_NAME = ".doc-truth.json"
CONFIG_KEYS = ("exclude", "ignore_paths", "allow")

# git never prompts, never runs the repository's hooks or a filesystem monitor, and never uses the network
GIT_FLAGS = ["-c", "core.quotepath=off", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=" + os.devnull,
             "-c", "protocol.allow=never"]


class DocTruthError(Exception):
    """Something the person must fix before the check can run (exit code 2)."""


def git(root, *args):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    return subprocess.run(["git", *GIT_FLAGS, "-C", str(root), *args], capture_output=True, env=env)


def repo_root(path):
    r = git(path, "rev-parse", "--show-toplevel")
    if r.returncode != 0:
        raise DocTruthError(f"{path} nao e um repositorio git")
    return Path(r.stdout.decode("utf-8", "replace").strip())


def tracked_files(root):
    """Every path git tracks, POSIX style: existence is judged against this, so a local run and CI agree."""
    r = git(root, "ls-files", "-z")
    if r.returncode != 0:
        raise DocTruthError(f"{root} nao e um repositorio git")
    return sorted(p for p in r.stdout.decode("utf-8", "replace").split("\0") if p)


def tree_paths(files):
    """The tracked files plus every folder they imply."""
    out = set(files)
    for f in files:
        d = posixpath.dirname(f)
        while d:
            out.add(d)
            d = posixpath.dirname(d)
    return out


def read_text(root, rel):
    """A tracked file's text, or None. Symlinks are never followed (a hostile repository could point one outside
    itself) and anything that is not a regular file is skipped."""
    path = Path(root) / rel
    try:
        if path.is_symlink() or not path.is_file():
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def load_config(root, explicit=None):
    path = Path(explicit) if explicit else Path(root) / CONFIG_NAME
    cfg = {k: [] for k in CONFIG_KEYS}
    if not path.exists():
        if explicit:
            raise DocTruthError(f"{path}: arquivo de configuracao nao encontrado")
        return cfg
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise DocTruthError(f"{path}: {e}")
    if not isinstance(data, dict):
        raise DocTruthError(f"{path}: deve ser um objeto JSON")
    for key, value in data.items():
        if key not in CONFIG_KEYS:
            raise DocTruthError(f"{path}: chave desconhecida '{key}' (use {', '.join(CONFIG_KEYS)})")
        if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
            raise DocTruthError(f"{path}: '{key}' deve ser uma lista de textos")
        cfg[key] = value
    return cfg


def glob_regex(pattern):
    """`*` is a name part (never crosses `/`), `**` is any depth. A pattern with no `/` except a trailing one
    matches a name anywhere (like .gitignore); a pattern with a `/` inside is anchored at the repository root;
    a trailing `/` means the folder itself and everything under it."""
    pat = pattern.strip()
    folder = pat.endswith("/")
    if folder:
        pat = pat[:-1]
    anchored = "/" in pat
    out, i = "", 0
    while i < len(pat):
        if pat.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif pat.startswith("**", i):
            out += ".*"
            i += 2
        elif pat[i] == "*":
            out += "[^/]*"
            i += 1
        elif pat[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(pat[i])
            i += 1
    if folder:
        out += "(?:/.*)?"
    if not anchored:
        out = "(?:.*/)?" + out
    return re.compile("^" + out + "$")


def compile_globs(patterns):
    return [glob_regex(p) for p in patterns]


def matches_any(regexes, rel):
    return any(rx.match(rel) for rx in regexes)

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


FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
SPAN = re.compile(r"(`+)([^`\n]+?)\1")
LINK = re.compile(r"!?\[[^\]\n]*\]\(\s*(<[^>\n]*>|[^)\s]+)(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")
REFDEF = re.compile(r"^ {0,3}\[[^\]\n]+\]:\s*(<[^>\n]*>|\S+)")
HTML_REF = re.compile(r"""\b(?:href|src)=["']([^"']+)["']""")
TREE_CHARS = "├└│─┌┐┘┬┴┼"
EXTENSIONS = (".md", ".py", ".json", ".sh", ".yml", ".yaml", ".toml", ".html", ".svg", ".txt")
SKIP_CHARS = "<>*$~|@{}"
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
MIME = re.compile(r"(?:application|text|image|audio|video|font|multipart|message)/[\w.+-]+")


class Doc:
    """What the checks need from one markdown file: headings, backtick spans, fenced lines and link targets.
    Front matter, fenced lines and tree diagrams never count as headings or prose."""

    def __init__(self, text):
        self.headings = []  # (level, text, line)
        self.spans = []  # (line, text) - inline code
        self.fenced = []  # (line, text) - lines inside a code fence
        self.links = []  # (line, target)
        self.prose = []  # (line, text) - everything outside front matter and fences
        lines = text.splitlines()
        start = 0
        if lines and lines[0].strip() == "---":
            for i in range(1, len(lines)):
                if lines[i].strip() == "---":
                    start = i + 1
                    break
        fence = None
        for n in range(start, len(lines)):
            line = lines[n]
            m = FENCE.match(line)
            if fence:
                if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and not line.strip(" `~"):
                    fence = None
                else:
                    self.fenced.append((n + 1, line))
                continue
            if m:
                fence = m.group(1)
                continue
            self.prose.append((n + 1, line))
            h = HEADING.match(line)
            if h:
                self.headings.append((len(h.group(1)), h.group(2), n + 1))
            ref = REFDEF.match(line)
            if ref:
                self.links.append((n + 1, ref.group(1).strip("<>")))
            for s in SPAN.finditer(line):
                self.spans.append((n + 1, s.group(2).strip()))
            bare = SPAN.sub(" ", line)
            for lm in LINK.finditer(bare):
                self.links.append((n + 1, lm.group(1).strip("<>")))
            for hm in HTML_REF.finditer(bare):
                self.links.append((n + 1, hm.group(1)))


def slugify(heading):
    """GitHub's anchor for a heading: lower case, punctuation dropped except - and _, spaces to -, letters kept."""
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    text = text.replace("`", "").replace("*", "").strip().lower()
    kept = "".join(c for c in text if c.isalnum() or c in " -_")
    return kept.replace(" ", "-")


def anchors_of(doc):
    """Every anchor a document offers; a repeated heading gets -1, -2 ..."""
    seen, out = {}, set()
    for _level, text, _line in doc.headings:
        slug = slugify(text)
        n = seen.get(slug, 0)
        out.add(slug if n == 0 else f"{slug}-{n}")
        seen[slug] = n + 1
    return out


def trim(tok):
    """Punctuation around a token, including a sentence's final full stop."""
    while True:
        new = tok.strip("\"'()[]{},;:!?")
        if new.endswith(".") and not new.endswith(".."):
            new = new[:-1]
        if new == tok:
            return tok
        tok = new


def clean_token(tok):
    tok = trim(tok)
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tok):  # NAME=value: the value is what may be a path
        tok = trim(tok.split("=", 1)[1])
    return re.sub(r":\d+(?::\d+)?$", "", tok)  # file.py:42


def is_path(tok):
    """Does this token claim to be a repository path? Placeholders, URLs, flags and absolute paths do not."""
    if not tok or tok.startswith("-") or tok.startswith("/") or "..." in tok:
        return False
    if SCHEME.match(tok) or "://" in tok or any(c in tok for c in SKIP_CHARS):
        return False
    if re.fullmatch(r"[A-Z][A-Z0-9_]*", tok):  # PATH, DIR
        return False
    if MIME.fullmatch(tok) or re.fullmatch(r"\.[A-Za-z0-9]+", tok):  # text/html, a bare extension like .svg
        return False
    if all(len(part) == 1 for part in tok.split("/") if part):  # A/R/M, n/N, a/b: choices, not paths
        return False
    return "/" in tok or tok.endswith(EXTENSIONS)


def tokens_of_span(text):
    return [clean_token(t) for t in text.split()]


def tokens_of_fenced_line(text):
    """Shell-ish lines: a leading # is a comment, a leading / is a Claude Code command, a tree diagram is a picture,
    and anything after ` #` is a comment."""
    stripped = text.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith("/") or any(c in text for c in TREE_CHARS):
        return []
    cut = re.split(r"\s#", text, maxsplit=1)[0]
    return [clean_token(t) for t in cut.split()]


def finding(category, document, line, value, message):
    return {"category": category, "document": document, "line": line, "value": value, "message": message}


class Context:
    """The repository as the checks see it: the git tree, the documents (parsed once) and what to ignore."""

    def __init__(self, root, files, config):
        self.root = Path(root)
        self.files = files
        self.tree = tree_paths(files)
        self.ignore = compile_globs(config["ignore_paths"])
        self._docs = {}

    def doc(self, rel):
        if rel not in self._docs:
            text = read_text(self.root, rel)
            self._docs[rel] = Doc(text) if text is not None else None
        return self._docs[rel]


def candidates(document, token):
    """Where a token may point: next to the document first, then from the repository root."""
    t = token.rstrip("/")
    out = []
    for base in (posixpath.dirname(document), ""):
        cand = posixpath.normpath(posixpath.join(base, t))
        if cand != "." and not cand.startswith(".."):
            out.append(cand)
    return out


def path_exists(ctx, document, token):
    return any(c in ctx.tree for c in candidates(document, token))


def is_ignored(ctx, document, token):
    shown = token.rstrip("/")
    forms = [shown[2:] if shown.startswith("./") else shown] + candidates(document, token)
    return any(matches_any(ctx.ignore, f) for f in forms)


def check_paths(ctx, document):
    doc = ctx.doc(document)
    out, seen = [], set()
    pairs = [(n, t) for n, text in doc.spans for t in tokens_of_span(text)]
    pairs += [(n, t) for n, text in doc.fenced for t in tokens_of_fenced_line(text)]
    for line, tok in pairs:
        if tok in seen or not is_path(tok):
            continue
        seen.add(tok)
        if is_ignored(ctx, document, tok) or path_exists(ctx, document, tok):
            continue
        out.append(finding("path", document, line, tok, f"o caminho citado nao existe: {tok}"))
    return out


def check_links(ctx, document):
    doc = ctx.doc(document)
    out, seen = [], set()
    for line, raw in doc.links:
        if raw in seen or SCHEME.match(raw):
            continue
        seen.add(raw)
        target, _, fragment = raw.partition("#")
        target = unquote(target.partition("?")[0])
        fragment = unquote(fragment)
        if target:
            if target.startswith("/"):
                cand = posixpath.normpath(target.lstrip("/"))
            else:
                cand = posixpath.normpath(posixpath.join(posixpath.dirname(document), target))
            if cand.startswith("..") or cand not in ctx.tree:
                out.append(finding("link", document, line, target, f"o link aponta para algo que nao existe: {target}"))
                continue
        else:
            cand = document
        if fragment and cand.endswith(".md") and cand in ctx.files:
            other = ctx.doc(cand)
            if other is not None and fragment.lower() not in anchors_of(other):
                value = f"{cand}#{fragment}"
                out.append(finding("anchor", document, line, value, f"nao ha titulo para a ancora: {value}"))
    return out

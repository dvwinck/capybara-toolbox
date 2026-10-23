#!/usr/bin/env python3
# doc-truth 0.3.1 - confere se o que os documentos dizem existe: caminhos, links, ancoras, paridade EN/PT-BR e versoes (somente stdlib e git)
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Diogo Winck
#
# Uso:
#   doc_truth.py [PATH] [--json] [--config FILE] [--lang en|pt-BR]   # read-only; exit 0 clean, 1 findings, 2 error
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

VERSION = "0.3.1"
SCHEMA = 1  # of the --json output; it is a public contract
CONFIG_NAME = ".doc-truth.json"
CONFIG_KEYS = ("exclude", "ignore_paths", "allow")
LANGS = ("en", "pt-BR")  # languages of the messages (--lang); the first is the default
DEFAULT_LANG = "en"
ENV_LANG = "CAPYBARA_LANG"  # one shell-wide default for every Capybara Toolbox script
CLI_LANG = DEFAULT_LANG  # the language of this run's messages, set by main()

# Every message doc-truth prints or puts in a finding, in both languages. Same keys and {placeholders} in both
# (a test enforces it); both plain ASCII, so the pt-BR side is the accent-free Portuguese of 0.3.1, and a key
# ending in `_1` is the form used when n == 1. A finding's `value` (and so its fingerprint) never depends on the
# language: an `allow` list written in one language keeps working in the other.
MSG = {
    "en": {
        "git_missing": "git not found ({e})", "not_repo": "{path} is not a git repository",
        "cfg_missing": "{path}: configuration file not found", "cfg_deep": "{path}: JSON nested too deep",
        "cfg_obj": "{path}: must be a JSON object", "cfg_key": "{path}: unknown key '{key}' (use {keys})",
        "cfg_list": "{path}: '{key}' must be a list of strings",
        "m_path": "the cited path does not exist: {tok}", "m_link": "the link points to something that does not exist: {target}",
        "m_anchor": "no heading for the anchor: {value}", "m_no_pt": "{rel} has no Portuguese version ({name})",
        "m_levels": "the heading levels of {rel} and {pt} differ ({where})", "where_heading": "heading {i} differs",
        "where_count": "{n} headings against {b}", "where_count_1": "{n} heading against {b}",
        "m_version": "version {v} does not match the manifest ({expected})",
        "m_plugins": "the catalog has the plugin {name}, but {rel} has no link to plugins/{name}",
        "checked": "doc-truth {version}: {n} documents checked in {root}",
        "checked_1": "doc-truth {version}: {n} document checked in {root}",
        "findings": "{n} findings", "findings_1": "{n} finding", "clean": "clean: no findings",
        "accepted": "({n} accepted by the allow list)", "accepted_1": "({n} accepted by the allow list)",
        "how_to_accept": 'To accept a finding, put its fingerprint in "allow" in {config}.', "error": "error: {e}",
    },
    "pt-BR": {
        "git_missing": "git nao encontrado ({e})", "not_repo": "{path} nao e um repositorio git",
        "cfg_missing": "{path}: arquivo de configuracao nao encontrado", "cfg_deep": "{path}: JSON aninhado fundo demais",
        "cfg_obj": "{path}: deve ser um objeto JSON", "cfg_key": "{path}: chave desconhecida '{key}' (use {keys})",
        "cfg_list": "{path}: '{key}' deve ser uma lista de textos",
        "m_path": "o caminho citado nao existe: {tok}", "m_link": "o link aponta para algo que nao existe: {target}",
        "m_anchor": "nao ha titulo para a ancora: {value}", "m_no_pt": "{rel} nao tem a versao em portugues ({name})",
        "m_levels": "os niveis de titulo de {rel} e {pt} diferem ({where})", "where_heading": "o titulo {i} difere",
        "where_count": "{n} titulos contra {b}", "where_count_1": "{n} titulo contra {b}",
        "m_version": "a versao {v} nao bate com o manifesto ({expected})",
        "m_plugins": "o catalogo tem o plugin {name}, mas {rel} nao tem link para plugins/{name}",
        "checked": "doc-truth {version}: {n} documentos conferidos em {root}",
        "checked_1": "doc-truth {version}: {n} documento conferido em {root}",
        "findings": "{n} achados", "findings_1": "{n} achado", "clean": "limpo: nenhum achado",
        "accepted": "({n} aceitos pela lista allow)", "accepted_1": "({n} aceito pela lista allow)",
        "how_to_accept": 'Para aceitar um achado, ponha o fingerprint em "allow" em {config}.', "error": "erro: {e}",
    },
}

# git never prompts, never runs the repository's hooks or a filesystem monitor, and never uses the network
GIT_FLAGS = ["-c", "core.quotepath=off", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=" + os.devnull,
             "-c", "protocol.allow=never"]


class DocTruthError(Exception):
    """Something the person must fix before the check can run (exit code 2)."""


def env_lang():
    """CAPYBARA_LANG when it is exactly one of LANGS. Any other value is ignored, silently: a shell setting must
    never break a command, and a warning on every run would be noise in the agent's context."""
    value = os.environ.get(ENV_LANG)
    return value if value in LANGS else None


def pick_lang(*candidates):
    """The first candidate that is one of LANGS (--lang), then CAPYBARA_LANG, then English."""
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


# where git looks for the repository: inherited from a hook or a wrapper, these would make `-C path` judge another tree
GIT_LOCATION_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY",
                     "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE", "GIT_PREFIX")


def git(root, *args):
    env = {k: v for k, v in os.environ.items() if k not in GIT_LOCATION_VARS}
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        return subprocess.run(["git", *GIT_FLAGS, "-C", str(root), *args], capture_output=True, env=env)
    except OSError as e:
        raise DocTruthError(say("git_missing", e=e.strerror or e))


def repo_root(path):
    r = git(path, "rev-parse", "--show-toplevel")
    if r.returncode != 0:
        raise DocTruthError(say("not_repo", path=path))
    return Path(r.stdout.decode("utf-8", "replace").strip())


def tracked_files(root):
    """Every path git tracks, POSIX style: existence is judged against this, so a local run and CI agree."""
    r = git(root, "ls-files", "-z")
    if r.returncode != 0:
        raise DocTruthError(say("not_repo", path=root))
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
            raise DocTruthError(say("cfg_missing", path=path))
        return cfg
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise DocTruthError(f"{path}: {e}")
    except RecursionError:  # Python 3.9 recurses while decoding; a hostile file can nest far deeper than that
        raise DocTruthError(say("cfg_deep", path=path))
    if not isinstance(data, dict):
        raise DocTruthError(say("cfg_obj", path=path))
    for key, value in data.items():
        if key not in CONFIG_KEYS:
            raise DocTruthError(say("cfg_key", path=path, key=key, keys=", ".join(CONFIG_KEYS)))
        if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
            raise DocTruthError(say("cfg_list", path=path, key=key))
        cfg[key] = value
    return cfg


def glob_regex(pattern):
    """`*` is a name part (never crosses `/`), `**` is any depth. A pattern with no `/` except a trailing one
    matches a name anywhere (like .gitignore); a pattern with a `/` inside is anchored at the repository root;
    a leading `/` also anchors it (and is not part of the path), so `/SKILL.md` is the bare name `SKILL.md` as
    written and the root file, never `plugins/x/SKILL.md`; a trailing `/` means the folder itself and everything
    under it."""
    pat = pattern.strip()
    folder = pat.endswith("/")
    if folder:
        pat = pat[:-1]
    rooted = pat.startswith("/")
    if rooted:
        pat = pat[1:]
    anchored = rooted or "/" in pat
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
HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+)$")  # the closing # run is stripped by heading_text, not by the regex
SPAN = re.compile(r"(`+)([^`\n]+?)\1")
# every run is capped so that a hostile line (a megabyte of "[a](") cannot make the scan quadratic
LINK = re.compile(r"!?\[[^\]\n]{0,500}\]\(\s*(<[^>\n]{0,1000}>|[^)\s]{1,1000})"
                  r"(?:\s+(?:\"[^\"]{0,500}\"|'[^']{0,500}'))?\s*\)")
REFDEF = re.compile(r"^ {0,3}\[[^\]\n]+\]:\s*(<[^>\n]*>|\S+)")
HTML_REF = re.compile(r"""\b(?:href|src)=["']([^"']+)["']""")
TREE_CHARS = "├└│─┌┐┘┬┴┼"
EXTENSIONS = (".md", ".py", ".json", ".sh", ".yml", ".yaml", ".toml", ".html", ".svg", ".txt")
SKIP_CHARS = "<>*$~|@{}"
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
MIME = re.compile(r"(?:application|text|image|audio|video|font|multipart|message)/[\w.+-]+")


def heading_text(rest):
    """The text of an ATX heading without its optional closing # run (only when preceded by a space or tab)."""
    text = rest.rstrip(" \t")
    stripped = text.rstrip("#")
    if stripped != text and (not stripped or stripped[-1] in " \t"):
        text = stripped.rstrip(" \t")
    return text


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
                text = heading_text(h.group(2))
                if text:
                    self.headings.append((len(h.group(1)), text, n + 1))
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
        out.append(finding("path", document, line, tok, say("m_path", tok=tok)))
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
                out.append(finding("link", document, line, target, say("m_link", target=target)))
                continue
        else:
            cand = document
        if fragment and cand.endswith(".md") and cand in ctx.files:
            other = ctx.doc(cand)
            if other is not None and fragment.lower() not in anchors_of(other):
                value = f"{cand}#{fragment}"
                out.append(finding("anchor", document, line, value, say("m_anchor", value=value)))
    return out


MANIFEST = re.compile(r"plugins/[^/]+/\.claude-plugin/plugin\.json")
CATALOG = ".claude-plugin/marketplace.json"
VERSION_IN_TEXT = re.compile(r"(?<![\d.])v?(\d+\.\d+\.\d+)(?!\.?\d)")
VERSION_DOCS = (re.compile(r"README(?:\.pt-BR)?\.md"), re.compile(r"plugins/[^/]+/README(?:\.pt-BR)?\.md"),
                re.compile(r"plugins/[^/]+/skills/[^/]+/SKILL\.md"))
ROOT_READMES = ("README.md", "README.pt-BR.md")


def read_json(ctx, rel):
    text = read_text(ctx.root, rel)
    try:
        data = json.loads(text) if text is not None else None
    except (ValueError, RecursionError):  # invalid, or nested deeper than the decoder recurses (Python 3.9): not trusted
        return None
    return data if isinstance(data, dict) else None


def plugin_versions(ctx):
    """{plugin name: version} from every tracked plugin.json."""
    out = {}
    for rel in ctx.files:
        if MANIFEST.fullmatch(rel):
            data = read_json(ctx, rel)
            if data and isinstance(data.get("name"), str) and isinstance(data.get("version"), str):
                out[data["name"]] = data["version"]
    return out


def check_parity(ctx, documents):
    """X.md and X.pt-BR.md must have the same sequence of heading levels (the text is translated, so it is not
    compared). A README.md with no README.pt-BR.md next to it is a finding; any other document without a pair is not."""
    present = set(documents)
    out = []
    for rel in sorted(present):
        if rel.endswith(".pt-BR.md"):
            continue
        pt = rel[:-3] + ".pt-BR.md"
        if pt not in ctx.files:
            if posixpath.basename(rel) == "README.md":
                out.append(finding("parity", rel, 1, "falta " + posixpath.basename(pt),  # the value is data: same in both languages
                                   say("m_no_pt", rel=rel, name=posixpath.basename(pt))))
            continue
        if pt not in present:
            continue
        en, br = ctx.doc(rel), ctx.doc(pt)
        a, b = [h[0] for h in en.headings], [h[0] for h in br.headings]
        if a == b:
            continue
        i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
        where = say("where_heading", i=i + 1) if i < min(len(a), len(b)) else say("where_count", n=len(a), b=len(b))
        out.append(finding("parity", rel, 1, ",".join(map(str, a)) + "|" + ",".join(map(str, b)),
                           say("m_levels", rel=rel, pt=pt, where=where)))
    return out


def check_versions(ctx, documents):
    """A version X.Y.Z written on the same line as a plugin's name must be that plugin's version (or the version of
    another plugin named on the line). Only the root README, plugin READMEs and SKILL.md are checked."""
    versions = plugin_versions(ctx)
    out = []
    for rel in documents:
        if not any(rx.fullmatch(rel) for rx in VERSION_DOCS):
            continue
        for line, text in ctx.doc(rel).prose:
            named = [n for n in versions if re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", text)]
            if not named:
                continue
            allowed = {versions[n] for n in named}
            for v in VERSION_IN_TEXT.findall(text):
                if v not in allowed:
                    value = "/".join(named) + " " + v
                    expected = ", ".join(f"{n} {versions[n]}" for n in named)
                    out.append(finding("version", rel, line, value, say("m_version", v=v, expected=expected)))
    return out


def check_plugin_lists(ctx, documents):
    """Every plugin of the catalog must be linked from the root README and its Portuguese counterpart."""
    catalog = read_json(ctx, CATALOG) if CATALOG in ctx.files else None
    names = [p["name"] for p in (catalog or {}).get("plugins", []) if isinstance(p, dict) and isinstance(p.get("name"), str)]
    out = []
    for rel in ROOT_READMES:
        if rel not in documents:
            continue
        targets = [posixpath.normpath(t.partition("#")[0]) for _, t in ctx.doc(rel).links if t.partition("#")[0]]
        for name in names:
            if not any(t == f"plugins/{name}" or t.startswith(f"plugins/{name}/") for t in targets):
                out.append(finding("plugins", rel, 1, name, say("m_plugins", name=name, rel=rel)))
    return out


CATEGORIES = ("path", "link", "anchor", "parity", "version", "plugins")


def fingerprint(f):
    """Category, document and value; never the line, so an edit above an accepted finding does not revive it."""
    return hashlib.sha256(f"{f['category']}|{f['document']}|{f['value']}".encode("utf-8")).hexdigest()[:16]


def run(root, config):
    files = tracked_files(root)
    ctx = Context(root, files, config)
    exclude = compile_globs(config["exclude"])
    documents = [f for f in files if f.endswith(".md") and not matches_any(exclude, f) and ctx.doc(f) is not None]
    found = []
    for doc in documents:
        found += check_paths(ctx, doc) + check_links(ctx, doc)
    found += check_parity(ctx, documents) + check_versions(ctx, documents) + check_plugin_lists(ctx, documents)
    for f in found:
        f["fingerprint"] = fingerprint(f)
    allow = set(config["allow"])
    kept = [f for f in found if f["fingerprint"] not in allow]
    kept.sort(key=lambda f: (CATEGORIES.index(f["category"]), f["document"], f["line"], f["value"]))
    return {"schema": SCHEMA, "tool": "doc-truth", "version": VERSION, "root": str(root), "documents": len(documents),
            "findings": kept, "accepted": len(found) - len(kept)}


def report(result):
    lines = [say("checked", version=result["version"], n=result["documents"], root=result["root"])]
    kept = result["findings"]
    lines.append(say("findings", n=len(kept)) if kept else say("clean"))
    for cat in CATEGORIES:
        group = [f for f in kept if f["category"] == cat]
        if not group:
            continue
        lines += ["", f"[{cat}] {len(group)}"]
        for f in group:
            lines += [f"  {f['document']}:{f['line']}  {f['value']}", f"    {f['message']}", f"    fingerprint: {f['fingerprint']}"]
    if result["accepted"]:
        lines.append(say("accepted", n=result["accepted"]))
    if kept:
        lines += ["", say("how_to_accept", config=CONFIG_NAME)]
    return "\n".join(lines)


def parser():
    p = argparse.ArgumentParser(prog="doc_truth.py", description="Checks that what a repository's documents say exists (read-only).")
    p.add_argument("path", nargs="?", default=".", help="the repository (default: the current folder)")
    p.add_argument("--json", action="store_true", help="JSON output (schema field)")
    p.add_argument("--config", help=f"configuration file (default: {CONFIG_NAME} at the repository root)")
    p.add_argument("--lang", choices=LANGS, default=None, help="language of the messages (default: CAPYBARA_LANG, then en)")
    p.add_argument("--version", action="version", version=f"doc-truth {VERSION}")
    return p


def main(argv=None):
    """Run the check. The language of the messages is set here (--lang, then CAPYBARA_LANG, then en) and put back
    afterwards, so an in-process caller (the tests) never inherits the language of another run."""
    global CLI_LANG
    args = parser().parse_args(argv)
    before = CLI_LANG
    use_lang(args.lang)
    try:
        try:
            root = repo_root(args.path)
            config = load_config(root, args.config)
            result = run(root, config)
        except DocTruthError as e:
            print(say("error", e=e), file=sys.stderr)
            return 2
        except (OSError, UnicodeError, RecursionError) as e:  # a safety net: no failure path may end in a traceback and exit 1
            print(say("error", e=f"{type(e).__name__}: {e}"), file=sys.stderr)
            return 2
        print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else report(result))
        return 1 if result["findings"] else 0
    finally:
        CLI_LANG = before


if __name__ == "__main__":
    sys.exit(main())

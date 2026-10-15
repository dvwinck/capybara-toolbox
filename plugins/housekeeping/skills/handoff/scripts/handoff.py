#!/usr/bin/env python3
# handoff 0.3.0 - nota de fim de sessao com fatos do git coletados e citacoes conferidas (somente stdlib e git)
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

VERSION = "0.3.0"
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
    except ValueError:  # an embedded NUL in an argument: git is never run, the answer is "no"
        return 1, ""
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
    return None, ("o id de commit e ambiguo" if commits else "o commit nao existe")


def check_citation(root, kind, value):
    """(verified, sha, why): `sha` is what the citation pointed at (commits and branches), `why` explains a failure."""
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        return False, None, "a citacao tem caracteres de controle"
    if kind == "commit":
        if not HEX_ID.fullmatch(value):
            return False, None, "id de commit invalido (7 a 40 caracteres hexadecimais)"
        sha, why = commit_by_id(root, value)
        return (True, sha, "") if sha else (False, None, why)
    if kind == "branch":
        # a plain branch name only: no revision expression (main~1, main^, main@{0}, a..b, a:b) and no option
        if BAD_BRANCH_CHARS.search(value) or "@{" in value or ".." in value or value.startswith("-"):
            return False, None, "nome de branch invalido (nao pode ser uma expressao de revisao)"
        for ref in ("refs/heads/" + value, "refs/remotes/" + value):
            rc, out = git(root, "show-ref", "--verify", "--hash", ref)  # exact ref, no revision parsing
            if rc == 0 and out.strip():
                return True, resolve(root, ref), ""
        return False, None, "a branch nao existe (local ou remota)"
    path = LINE_SUFFIX.sub("", value)
    parts = path.split("/")
    if path.startswith("/") or ".." in parts or not path:
        return False, None, "o caminho deve ser relativo a raiz do repositorio"
    target = Path(root) / path
    try:  # a symlink that leads outside the repository is not a file of the repository
        inside = target.resolve().is_relative_to(Path(root).resolve())
    except (OSError, RuntimeError, ValueError):
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


SECTIONS = ("O que foi feito", "Decisoes e por que", "Proximos passos", "O que falhou ou travou")
DATA_BLOCK = re.compile(r"<!-- handoff:data (\{.*?\}) -->")
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


def parse_data(text):
    found = DATA_BLOCK.findall(text)
    if not found:
        return None
    try:
        data = json.loads(found[-1])
    except (ValueError, RecursionError):  # not JSON, or nested so deep that reading it overflows: no usable block
        return None
    return data if isinstance(data, dict) and valid_facts(data.get("facts")) else None


def notes_folder(root):
    """The default notes folder. A symlink there (a hostile repository can track one) would send the notes, or
    the reading of them, somewhere else, so it is refused."""
    folder = Path(root) / NOTE_DIR
    if folder.is_symlink():
        raise HandoffError(f"{folder} e um link simbolico: recuso escrever ou ler por ele (use --out para escolher a pasta)")
    return folder


def names(items):
    shown = ", ".join(items[:SHOWN])
    return shown + (f" e mais {len(items) - SHOWN}" if len(items) > SHOWN else "")


def git_section(facts):
    """The facts, as prose with no backtick spans (those are reserved for typed citations)."""
    branch = facts["branch"] or "(HEAD solta)"
    tip = f", ponta {facts['tip'][:7]}" if facts["tip"] else ", sem commits"
    lines = ["## Estado do git", "", f"- Branch: {branch}{tip}"]
    if facts["upstream"]:
        lines.append(f"- Upstream: {facts['upstream']}")
    if facts["base"] and facts["ahead"] is not None:
        lines.append(f"- Em relacao a base {facts['base']}: {facts['ahead']} a frente, {facts['behind']} atras")
    else:
        lines.append("- Base: nao encontrada")
    lines.append(f"- Arquivos modificados: {len(facts['modified'])}" + (f" ({names(facts['modified'])})" if facts["modified"] else ""))
    lines.append(f"- Arquivos novos (nao rastreados): {len(facts['untracked'])}" + (f" ({names(facts['untracked'])})" if facts["untracked"] else ""))
    lines.append(f"- Stashes: {facts['stashes']}")
    others = [w for w in facts["worktrees"][1:]]
    if others:
        lines.append("- Outros worktrees: " + ", ".join(f"{w['path']} ({w['branch'] or 'HEAD solta'})" for w in others))
    if facts["commits"]:
        lines += ["- Commits recentes:"] + [f"  - {c['sha']} {c['subject']}" for c in facts["commits"]]
    return "\n".join(lines)


def missing_sections(draft):
    return [name for name in SECTIONS if not re.search(rf"^#{{1,6}}[ \t]+{re.escape(name)}[ \t]*$", draft, re.M | re.I)]


def render_note(facts, draft, results, when):
    cites = [{"type": r["type"], "value": r["value"], "sha": r["sha"], "verified": r["verified"]} for r in results]
    data = {"schema": SCHEMA, "facts": facts, "citations": cites}
    return (f"# Handoff - {when} - {facts['branch'] or 'HEAD solta'}\n\n" + git_section(facts) + "\n\n"
            + draft.strip("\n") + "\n\n" + data_block(data) + "\n")


def write_note(root, draft, out_dir=None, base=None):
    """Check the draft's citations, mark the ones that fail, and save the note in a new file (never over another)."""
    facts = collect(root, base)
    results = check_text(root, draft)
    text = render_note(facts, mark_unverified(draft, results), results, time.strftime("%Y-%m-%d %H:%M", NOW()))
    try:  # encoded before any file exists: a text that cannot be written must not leave an empty note behind
        payload = text.encode("utf-8")
    except UnicodeError:
        raise HandoffError("o rascunho tem caracteres que nao cabem em UTF-8: nada foi gravado")
    folder = Path(out_dir) if out_dir else notes_folder(root)
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise HandoffError(f"nao consegui criar a pasta das notas {folder}: {e.strerror or e}")
    stamp = time.strftime("%Y-%m-%d-%H%M%S", NOW())
    name, n = stamp + ".md", 2
    while True:
        try:  # private (the note may name internal paths) and exclusive (two runs in a second never share a file)
            fd = os.open(str(folder / name), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            break
        except FileExistsError:
            name, n = f"{stamp}-{n}.md", n + 1
        except OSError as e:
            raise HandoffError(f"nao consegui criar a nota em {folder}: {e.strerror or e}")
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
        raise HandoffError(f"nao consegui gravar a nota {folder / name}: {e.strerror or e}")
    os.close(fd)
    return {"path": str(folder / name), "facts": facts, "citations": results, "missing": missing_sections(draft)}


TITLE = re.compile(r"# Handoff - [^\n]*\n\n")
GIT_PART = re.compile(r"## Estado do git\n\n(?:[^\n]+\n)+")


def tool_spans(text):
    """The parts of a note the tool wrote itself: the title and the git section (commit subjects, branch and file
    names, quoted verbatim) and the data block. They are not the agent's citations and are never checked."""
    spans = []
    title = TITLE.match(text)
    if title:
        end = None
        data = parse_data(text)
        if data:  # the exact rendering of the recorded facts, so even a file name with a blank line in it is covered
            try:
                section = git_section(data["facts"]) + "\n"
                if text.startswith(section, title.end()):
                    end = title.end() + len(section)
            except (KeyError, TypeError, ValueError, AttributeError):
                end = None
        if end is None:
            part = GIT_PART.match(text, title.end())
            end = part.end() if part else title.end()
        spans.append((0, end))
    blocks = list(DATA_BLOCK.finditer(text))
    if blocks:
        spans.append((blocks[-1].start(), blocks[-1].end()))
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
        out.append(f"a branch era {then['branch'] or '(HEAD solta)'} e agora e {now['branch'] or '(HEAD solta)'}")
    elif then["tip"] != now["tip"]:
        extra = ""
        if then["tip"] and resolve(root, then["tip"]):
            rc, count = git(root, "rev-list", "--count", f"{then['tip']}..HEAD")
            extra = f" ({count.strip()} commits novos)" if rc == 0 else ""
        else:
            extra = " (o commit antigo nao existe mais)"
        out.append(f"a ponta de {now['branch'] or 'HEAD'} mudou: {(then['tip'] or '-')[:7]} -> {(now['tip'] or '-')[:7]}{extra}")
    if (then["ahead"], then["behind"]) != (now["ahead"], now["behind"]):
        out.append(f"a frente/atras da base mudou: {then['ahead']}/{then['behind']} -> {now['ahead']}/{now['behind']}")
    before, after = set(then["modified"] + then["untracked"]), set(now["modified"] + now["untracked"])
    if before - after:
        out.append("arquivos sujos que ja nao estao: " + names(sorted(before - after)))
    if after - before:
        out.append("arquivos sujos novos: " + names(sorted(after - before)))
    if then["stashes"] != now["stashes"]:
        out.append(f"stashes: {then['stashes']} -> {now['stashes']}")
    return out


def read_note(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise HandoffError(f"nao consegui ler a nota {path}: {e.strerror or e}")


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
        raise HandoffError(f"nao ha nota em {NOTE_DIR}/ (rode `write` primeiro)")
    if path.is_symlink() or not path.is_file():
        raise HandoffError(f"{path} nao e um arquivo de nota")
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
    return git_section(facts)


def citation_lines(results):
    out = []
    for r in results:
        flag = "ok" if r["verified"] else "NAO VERIFICADO"
        if r.get("moved"):
            flag = "MUDOU (a ponta e outra)"
        out.append(f"  linha {r['line']}: {r['type']}:{r['value']}  {flag}" + (f" ({r['why']})" if r["why"] else ""))
    return out


def clean_result(results):
    return [{k: v for k, v in r.items() if k not in ("start", "end")} for r in results]


def parser():
    p = argparse.ArgumentParser(prog="handoff.py", description="Nota de fim de sessao com fatos do git e citacoes conferidas.")
    p.add_argument("--version", action="version", version=f"handoff {VERSION}")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect", help="os fatos do git, como JSON ou texto")
    c.add_argument("repo", nargs="?", default=".")
    c.add_argument("--base")
    c.add_argument("--json", action="store_true")
    w = sub.add_parser("write", help="confere as citacoes de um rascunho e grava a nota")
    w.add_argument("repo", nargs="?", default=".")
    w.add_argument("--draft", required=True, help="arquivo com o rascunho, ou - para a entrada padrao")
    w.add_argument("--out", help=f"pasta das notas (padrao: {NOTE_DIR}/ na raiz)")
    w.add_argument("--base")
    w.add_argument("--json", action="store_true")
    v = sub.add_parser("verify", help="confere as citacoes de uma nota ou rascunho")
    v.add_argument("file")
    v.add_argument("repo", nargs="?", default=".")
    v.add_argument("--json", action="store_true")
    r = sub.add_parser("resume", help="mostra a nota mais recente e o que mudou desde entao")
    r.add_argument("repo", nargs="?", default=".")
    r.add_argument("--file", help="uma nota especifica (padrao: a mais recente)")
    r.add_argument("--json", action="store_true")
    return p


def read_draft(arg):
    try:
        return sys.stdin.read() if arg == "-" else Path(arg).read_text(encoding="utf-8", errors="replace")
    except UnicodeError:
        raise HandoffError("nao consegui ler o rascunho: nao e UTF-8 valido")
    except OSError as e:
        raise HandoffError(f"nao consegui ler o rascunho: {e}")


def emit(args, payload, text):
    print(json.dumps(payload, indent=2, ensure_ascii=False) if args.json else text)


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        root = repo_root(args.repo)
        if args.cmd == "collect":
            facts = collect(root, args.base)
            emit(args, facts, facts_report(facts))
            return 0
        if args.cmd == "write":
            res = write_note(root, read_draft(args.draft), args.out, args.base)
            bad = [c for c in res["citations"] if not c["verified"]]
            lines = [f"nota gravada em {res['path']}", f"{len(res['citations'])} citacoes, {len(bad)} nao verificadas"]
            lines += citation_lines(bad)
            lines += [f"aviso: falta a secao '{name}'" for name in res["missing"]]
            emit(args, {"schema": SCHEMA, "path": res["path"], "citations": clean_result(res["citations"]), "missing_sections": res["missing"]},
                 "\n".join(lines))
            return 1 if bad else 0
        if args.cmd == "verify":
            path = Path(args.file)
            if path.is_symlink() or not path.is_file():
                raise HandoffError(f"{path} nao e um arquivo")
            results = check_note(root, read_note(path))
            bad = [c for c in results if not c["verified"]]
            emit(args, {"schema": SCHEMA, "citations": clean_result(results)},
                 "\n".join([f"{len(results)} citacoes, {len(bad)} nao verificadas"] + citation_lines(results)))
            return 1 if bad else 0
        res = resume(root, args.file)
        bad = [c for c in res["citations"] if not c["verified"] or c["moved"]]
        changed = res["drift"] or []
        lines = [res["text"].rstrip("\n"), "", "--- conferencia agora ---", f"nota: {res['path']}"]
        if res["drift"] is None:
            lines.append("a nota nao tem o bloco de dados: so as citacoes foram conferidas")
        lines += (["mudou desde a nota:"] + [f"  - {m}" for m in changed]) if changed else ([] if res["drift"] is None else ["nada mudou no git desde a nota"])
        lines += [f"{len(res['citations'])} citacoes, {len(bad)} com problema"] + citation_lines(bad)
        emit(args, {"schema": SCHEMA, "path": res["path"], "drift": res["drift"], "citations": clean_result(res["citations"])},
             "\n".join(lines))
        return 1 if (bad or changed) else 0
    except HandoffError as e:
        print(f"erro: {e}", file=sys.stderr)
        return 2
    except RecursionError:  # the safety net: a failure of the system or of the text is exit 2, never a traceback
        print("erro: uma estrutura da nota e funda demais para ser lida", file=sys.stderr)
        return 2
    except UnicodeError as e:
        print(f"erro: texto que nao cabe em UTF-8 ({e})", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"erro: falha de leitura ou escrita ({e.strerror or e})", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

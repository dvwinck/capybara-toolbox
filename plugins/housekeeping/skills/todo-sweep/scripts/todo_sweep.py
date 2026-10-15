#!/usr/bin/env python3
# todo-sweep 0.3.0 - TODO e FIXME como cards num painel local, do mais antigo ao mais novo; o resultado e um relatorio somente leitura (somente stdlib e git)
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Diogo Winck
#
# Uso:
#   todo_sweep.py scan   [REPO] [--limit N] [--max-blame N] [--out DIR]   # acha os TODO/FIXME, mede a idade, escreve batch.json + scan.json
#   todo_sweep.py check  DIR                                              # valida batch.json + scan.json
#   todo_sweep.py report DIR                                              # grava report.md e report.json a partir das decisoes
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

VERSION = "0.3.0"
SCHEMA = 1
WORK_DIR = ".todo-sweep"
LEDGER = "ledger.json"
MAX_FILE = 1024 * 1024  # bytes; larger files are skipped
TEXT_MAX = 200
CONTEXT = 2  # lines shown before and after a TODO
LEAD = re.compile(r"^\s*(?:#+|//+|--|/\*+|\*+|;+)\s*(TODO|FIXME)\b(.*)$")  # a comment line that starts with the marker
TRAIL = re.compile(r"\S.*?\s(?:#+|//+)\s*(TODO|FIXME)\b(.*)$")  # a trailing comment after code
SKIP_SUFFIXES = (".md", ".markdown")  # prose mentions TODO; it is not a code comment
ZERO_SHA = "0" * 40
NOW = time.time  # a function: the tests replace it
LABELS = {"approve": {"text": "Resolver", "tone": "safe"}, "reject": {"text": "Descartar", "tone": "danger"},
          "maybe": {"text": "Manter", "tone": "caution"}}

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
        raise SweepError(f"git nao encontrado ({e.strerror or e})")
    except ValueError:  # an embedded NUL in an argument: git is never run, the answer is "no"
        return 1, ""
    return r.returncode, r.stdout.decode("utf-8", "replace")


def repo_root(path):
    rc, out = git(path, "rev-parse", "--show-toplevel")
    if rc != 0:
        raise SweepError(f"{path} nao e um repositorio git")
    return Path(out.strip())


def stage_private(path, text):
    """Write `text` to a private (mode 0600) temporary file next to `path` and return its name. The text is encoded
    before any file exists, and a failure leaves no temporary file behind."""
    path = Path(path)
    try:
        payload = text.encode("utf-8")
    except UnicodeError:
        raise SweepError(f"o conteudo de {path.name} tem caracteres que nao cabem em UTF-8: nada foi gravado")
    tmp = path.with_name(path.name + ".tmp")
    try:
        try:
            os.unlink(str(tmp))  # a stale temporary file (or a link planted in its place) is never reused
        except FileNotFoundError:
            pass
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError as e:
        raise SweepError(f"nao consegui gravar {path}: {e.strerror or e}")
    try:
        try:
            view = memoryview(payload)
            while view:
                view = view[os.write(fd, view):]
        finally:
            os.close(fd)
    except OSError as e:
        discard(tmp)
        raise SweepError(f"nao consegui gravar {path}: {e.strerror or e}")
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
        raise SweepError(f"nao consegui gravar {', '.join(str(p) for p in files)}: {e.strerror or e}")


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
        raise SweepError(f"{root} nao e um repositorio git")
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
                         "todo_id": todo_id(rel, body, n), "age": None, "age_reason": "alem do limite de --max-blame"})
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
                h["age_reason"] = "sem historico (arquivo novo ou o blame falhou)"
            elif e["sha"] == ZERO_SHA or e["time"] is None:
                h["age_reason"] = "linha nao commitada"
            elif e["boundary"] and shallow:
                h["age_reason"] = "limite de um clone raso (o historico anterior nao esta aqui)"
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
        raise SweepError(f"{folder} e um link simbolico: recuso escrever ou ler por ele")
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
        raise SweepError(f"{path} esta ilegivel: corrija ou apague o arquivo")
    if not isinstance(data, dict) or not isinstance(data.get("decided"), dict):
        raise SweepError(f"{path} tem formato invalido: corrija ou apague o arquivo")
    return data["decided"]


def save_ledger(root, decided):
    path = ledger_path(root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise SweepError(f"nao consegui criar a pasta {path.parent}: {e.strerror or e}")
    write_private(path, dump_json({"schema": SCHEMA, "decided": decided}))


# ---------------------------------------------------------------- cards and scan

def shown(name):
    """A name as the card shows it: a backtick would be read as the start of a code span."""
    return name.replace("`", "'")


def area(file):
    return file.split("/", 1)[0] if "/" in file else "(raiz)"


def order_hits(hits):
    """Oldest first; what has no age comes after, in the order the files are listed."""
    aged = sorted((h for h in hits if h["age"]), key=lambda h: (-h["age"]["days"], h["file"], h["line"]))
    return aged + [h for h in hits if not h["age"]]


def age_text(h):
    if h["age"]:
        day = time.strftime("%Y-%m-%d", time.gmtime(h["age"]["time"]))
        return f"{h['age']['days']} dias (a linha mudou pela ultima vez em {day}, commit {h['age']['commit']})"
    return "sem idade: " + h["age_reason"]


def card_for(item_id, h):
    short = h["text"] if len(h["text"]) <= 90 else h["text"][:87] + "..."
    place = f"{shown(h['file'])}:{h['line']}"
    context = "\n".join(f"{n:>4}  {shown(text)}" for n, text in h["context"])
    return {"id": item_id, "tag": f"{h['marker']} - {shown(area(h['file']))}",
            "title": f"{h['marker']} em {place}" + (f": {shown(short)}" if short else ""),
            "fields": [{"label": "Onde", "text": f"`{place}`"},
                       {"label": "Texto", "text": shown(h["text"]) or "(sem texto)"},
                       {"label": "Idade", "text": age_text(h)},
                       {"label": "Trecho", "text": context}],
            "meta": {"Area": shown(area(h["file"])), "Idade": f"{h['age']['days']} dias" if h["age"] else "sem idade"}}


def build_batch(batch_id, shown_hits, found):
    width = max(2, len(str(len(shown_hits))))
    items = [card_for(f"T{i + 1:0{width}}", h) for i, h in enumerate(shown_hits)]
    return {"batch_id": batch_id, "title": f"TODO e FIXME: {len(shown_hits)} de {found}",
            "subtitle": "do mais antigo ao mais novo; Resolver, Descartar ou Manter, e o resultado e so um relatorio",
            "round": 1, "labels": LABELS, "items": items}


def build_scan(batch_id, root, shown_hits, totals):
    items = []
    for i, h in enumerate(shown_hits):
        items.append({"id": f"T{i + 1:0{max(2, len(str(len(shown_hits))))}}", "todo_id": h["todo_id"], "file": h["file"],
                      "line": h["line"], "marker": h["marker"], "text": h["text"],
                      "age_days": h["age"]["days"] if h["age"] else None, "commit": h["age"]["commit"] if h["age"] else None,
                      "age_reason": h["age_reason"]})
    return {"schema": SCHEMA, "tool": "todo-sweep", "version": VERSION, "batch_id": batch_id, "repo": str(root),
            "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "round": 1, "totals": totals, "items": items}


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
        raise SweepError(f"nao consegui criar a pasta {out}: {e.strerror or e}")
    return made


def refuse_old_decisions(out):
    """A decisions file in an existing output folder was written for other cards that used the same ids (the board
    would resume it, and the ledger would record what nobody judged). Refused before anything is written."""
    try:
        names = os.listdir(str(out)) if out.is_dir() else []
    except OSError as e:
        raise SweepError(f"nao consegui ler a pasta {out}: {e.strerror or e}")
    if any(n == "decisions.json" or (n.startswith("decisions.r") and n.endswith(".json")) for n in names):
        raise SweepError(f"{out} ja tem decisions.json de um lote anterior: escolha outra pasta com --out ou apague as decisoes")


def check_counts(a):
    """--limit and --max-blame are whole numbers of at least 1: a negative one would slice from the end of the list."""
    for name, flag in (("limit", "--limit"), ("max_blame", "--max-blame")):
        value = getattr(a, name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise SweepError(f"{flag} deve ser um numero inteiro >= 1 (recebi {value!r})")


def cmd_scan(a):
    check_counts(a)
    root = repo_root(a.repo)
    if a.out:
        refuse_old_decisions(Path(a.out))
    decided = load_ledger(root)
    hits = scan_files(root)
    fresh = [h for h in hits if h["todo_id"] not in decided]
    if not fresh:
        print(f"SCAN: {len(hits)} TODO/FIXME achados, {len(hits) - len(fresh)} ja decididos; nada novo para mostrar")
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
        write_all({out / "batch.json": dump_json(build_batch(batch_id, offered, len(fresh))),
                   out / "scan.json": dump_json(build_scan(batch_id, root, offered, totals))})
    except SweepError:
        for folder in made:  # a folder this run created is removed again; one that was there is left as it was
            try:
                folder.rmdir()
            except OSError:
                pass
        raise
    print(f"SCAN: {len(hits)} TODO/FIXME achados, {totals['decided_before']} ja decididos, {len(fresh)} novos, {len(unaged)} sem idade")
    if totals["shallow"]:
        print("aviso: clone raso: as linhas no limite do historico ficam sem idade (git fetch --unshallow resolve)")
    if len(unaged) and a.max_blame < len(fresh):
        print(f"aviso: so os primeiros {a.max_blame} foram medidos; suba --max-blame para medir mais")
    print(f"mostrando {len(offered)}, do mais antigo ao mais novo")
    print(f"lote: {out}")
    return 0


def load_dir(d):
    out = []
    for name in ("batch.json", "scan.json"):
        try:
            out.append(json.loads((Path(d) / name).read_text(encoding="utf-8")))
        except (OSError, UnicodeError, ValueError, RecursionError):
            raise SweepError(f"{Path(d) / name} ausente ou ilegivel: rode o scan")
    return out


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def scan_problems(batch, scan):
    errs = []
    if not isinstance(scan, dict) or scan.get("tool") != "todo-sweep" or scan.get("schema") != SCHEMA:
        return ["scan.json nao e um scan do todo-sweep (schema 1)"]
    if not isinstance(scan.get("items"), list) or not isinstance(scan.get("repo"), str):
        return ["scan.json sem 'items' ou 'repo'"]
    if not isinstance(batch, dict) or not isinstance(batch.get("items"), list):
        return ["batch.json sem 'items'"]
    if not isinstance(scan.get("batch_id"), str) or not is_int(scan.get("round")) or not is_int(batch.get("round", 1)):
        return ["scan.json sem 'batch_id' (texto) ou 'round' (inteiro), ou batch.json com 'round' invalido"]
    if batch.get("batch_id") != scan.get("batch_id"):
        errs.append("batch.json e scan.json sao de lotes diferentes")
    ids = [i.get("id") for i in batch["items"] if isinstance(i, dict)]
    mine = [i.get("id") for i in scan["items"] if isinstance(i, dict)]
    if ids != mine:
        errs.append("os itens do batch.json e do scan.json nao coincidem")
    for it in scan["items"]:
        if not (isinstance(it, dict) and all(isinstance(it.get(k), str) for k in ("id", "todo_id", "file", "marker", "text"))
                and isinstance(it.get("line"), int)):
            errs.append(f"item invalido no scan.json: {it!r}"[:120])
            break
    return errs


def cmd_check(a):
    batch, scan = load_dir(a.dir)
    errs = scan_problems(batch, scan)
    for e in errs:
        print(f"problema: {e}")
    if not errs:
        print(f"ok: {len(scan['items'])} itens, lote {scan['batch_id']}")
    return 1 if errs else 0


# ---------------------------------------------------------------- the report

DECISIONS = {"approved": "resolver", "rejected": "descartar", "maybe": "manter"}  # the panel's A, R and M
SECTIONS = (("resolver", "Resolver"), ("descartar", "Descartar"), ("manter", "Manter"), ("sem_decisao", "Sem decisao"))


def read_decisions(d, batch):
    """The panel's decisions.json, or a SweepError. The file is whatever a board (or a hand) left there: unreadable,
    not UTF-8, not JSON, nested too deep, a folder, the wrong shape, another batch or round, or not concluded."""
    path = Path(d) / "decisions.json"
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, RecursionError):
        raise SweepError("decisions.json ausente ou ilegivel: suba o painel e conclua antes do report")
    if not isinstance(state, dict) or not isinstance(state.get("items"), dict):
        raise SweepError("decisions.json com formato invalido")
    if state.get("batch_id") != batch.get("batch_id") or not is_int(state.get("round")) or state["round"] != batch.get("round", 1):
        raise SweepError("decisions.json e de outro lote ou rodada: nao vou usar decisoes antigas")
    if state.get("finished") is not True:
        raise SweepError("o painel nao foi concluido (clique em Concluir antes do report)")
    return state["items"]


def group_items(scan, decisions):
    groups = {key: [] for key, _title in SECTIONS}
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


def report_markdown(scan, groups):
    lines = [f"# Relatorio do todo-sweep - {md_line(scan['batch_id'])}", "",
             "As linhas sao as do momento do scan. Nenhum arquivo foi editado por esta ferramenta.", ""]
    for key, title in SECTIONS:
        lines += [f"## {title} ({len(groups[key])})", ""]
        for h in groups[key]:
            age = f"{h['age_days']} dias" if h["age_days"] is not None else "sem idade"
            lines.append(f"- `{md_line(h['file'])}:{h['line']}` {md_line(h['marker'])} {md_line(h['text']) or '(sem texto)'} ({age})"
                         + (f" - {md_line(h['comment'])}" if md_line(h["comment"]) else ""))
        lines.append("")
    return "\n".join(lines)


def cmd_report(a):
    batch, scan = load_dir(a.dir)
    errs = scan_problems(batch, scan)
    if errs:
        raise SweepError("scan.json/batch.json invalidos: " + "; ".join(errs))
    groups = group_items(scan, read_decisions(a.dir, batch))
    root = Path(scan["repo"])
    if not root.is_dir() or git(root, "rev-parse", "--git-dir")[0] != 0:
        raise SweepError(f"o repositorio do scan nao existe mais: {root}")
    decided = load_ledger(root)  # read first: a bad ledger (or a symlinked folder) stops the run before anything is written
    ledger = ledger_path(root)
    now_text = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    data = {"schema": SCHEMA, "tool": "todo-sweep", "batch_id": scan["batch_id"], "round": batch.get("round", 1),
            "created": now_text, "counts": {key: len(groups[key]) for key, _t in SECTIONS}, **groups}
    for key, word in (("descartar", "discard"), ("manter", "keep")):
        for h in groups[key]:
            decided[h["todo_id"]] = {"decision": word, "at": now_text, "file": h["file"], "text": h["text"]}
    out = Path(a.dir)
    made = make_folder(ledger.parent)
    try:  # the two report files and the ledger go together: all of them, or (rolled back) none
        write_all({out / "report.json": dump_json(data), out / "report.md": report_markdown(scan, groups),
                   ledger: dump_json({"schema": SCHEMA, "decided": decided})})
    except SweepError:
        for folder in made:
            try:
                folder.rmdir()
            except OSError:
                pass
        raise
    c = data["counts"]
    print(f"REPORT: {c['resolver']} resolver, {c['descartar']} descartar, {c['manter']} manter, {c['sem_decisao']} sem decisao")
    print(f"relatorio: {out / 'report.md'}")
    print(f"{c['descartar'] + c['manter']} decisoes lembradas em {ledger}; o proximo scan oferece os proximos")
    return 0


# ---------------------------------------------------------------- the command line

USAGE_WORDS = ((r"^argument ", "argumento "), (r"the following arguments are required: ", "faltam argumentos obrigatorios: "),
               (r"unrecognized arguments: ", "argumentos desconhecidos: "), (r"expected one argument", "falta o valor"),
               (r"invalid choice: ", "comando invalido: "))


class Parser(argparse.ArgumentParser):
    """Usage mistakes end the way every other failure does: an `erro:` line on stderr and exit code 2."""

    def error(self, message):
        for pattern, text in USAGE_WORDS:
            message = re.sub(pattern, text, message)
        self.print_usage(sys.stderr)
        self.exit(2, f"erro: {message}\n")


def count(text):
    """A count as typed: a whole number, or the text itself, which check_counts refuses with its own message."""
    try:
        return int(text)
    except ValueError:
        return text


def parser():
    p = Parser(prog="todo_sweep.py", description="TODO e FIXME como cards num painel local; o resultado e um relatorio somente leitura.")
    p.add_argument("--version", action="version", version=f"todo-sweep {VERSION}")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="acha os TODO/FIXME e escreve batch.json + scan.json")
    s.add_argument("repo", nargs="?", default=".")
    s.add_argument("--limit", type=count, default=20, help="cards por lote (padrao 20)")
    s.add_argument("--max-blame", type=count, default=300, help="quantos medir com git blame (padrao 300)")
    s.add_argument("--out", help=f"pasta do lote (padrao: {WORK_DIR}/todo-sweep-AAAA-MM-DD)")
    c = sub.add_parser("check", help="valida batch.json + scan.json")
    c.add_argument("dir")
    r = sub.add_parser("report", help="grava report.md e report.json a partir das decisoes")
    r.add_argument("dir")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        return {"scan": cmd_scan, "check": cmd_check, "report": cmd_report}[args.cmd](args)
    except SweepError as e:
        print(f"erro: {e}", file=sys.stderr)
        return 2
    except (OSError, UnicodeError, RecursionError) as e:  # whatever a hostile folder or a full disk still throws
        print(f"erro: falha inesperada ({type(e).__name__}: {e})", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

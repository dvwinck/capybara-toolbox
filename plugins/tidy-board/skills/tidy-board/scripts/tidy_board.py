#!/usr/bin/env python3
# tidy-board 0.1.0 - cards para limpar branches, worktrees e stashes; o apply reconfere e apaga (somente stdlib e git)
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Diogo Winck
#
# Uso:
#   tidy_board.py scan    [REPO] [--base REF] [--gh auto|off] [--out DIR]   # le o git e escreve batch.json + scan.json
#   tidy_board.py check   DIR                                              # valida batch.json + scan.json
#   tidy_board.py apply   DIR [--dry-run]                                  # reconfere cada item aprovado e apaga
#   tidy_board.py restore DIR ID                                           # recria o que foi apagado (backup ou sha)
import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import namedtuple
from pathlib import Path

VERSION = "0.1.0"


BACKUP = "refs/tidy-board/backup/"  # where apply keeps what could not be recreated from another ref
SAFE_PROOFS = ("P1", "P2")  # provably merged: eligible for the group card
RISKY_PROOFS = ("P3", "P4")  # probable or unique: extra confirmation and a backup ref
PROOFS = ("P1", "P2", "P3", "P4")
SQUASH_WINDOW = 500  # base commits compared when looking for a squash
PROOF_TEXT = {
    "P1": "provado: ancestral da base",
    "P2": "provado: PR mergeado no GitHub",
    "P3": "provavel: o mesmo patch ja esta na base",
    "P4": "trabalho unico: existe so aqui",
}

# Every git call is deaf to what the repository's own config asks git to run (a filesystem monitor,
# hooks; external diff programs are switched off per command below), never prompts, never fetches
# lazily and never touches the network.
GIT_FLAGS = ["-c", "core.quotepath=off", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=" + os.devnull,
             "-c", "protocol.allow=never", "-c", "log.showSignature=false", "-c", "i18n.logOutputEncoding=UTF-8"]
GIT_ENV = {"GIT_NO_LAZY_FETCH": "1", "GIT_NO_REPLACE_OBJECTS": "1", "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"}

Result = namedtuple("Result", "rc out err")


class TidyError(Exception):
    """A problem the person must fix (not a repository, git missing, unknown base)."""


# ---------------------------------------------------------------- git

def git(root, *args, input=None):
    data = input.encode("utf-8") if isinstance(input, str) else input
    try:
        r = subprocess.run(["git", *GIT_FLAGS, "-C", str(root), *args], capture_output=True, input=data,
                           env={**os.environ, **GIT_ENV})
    except FileNotFoundError:
        raise TidyError("git nao encontrado no PATH")
    return Result(r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace"))


def git_ok(root, *args, input=None):
    r = git(root, *args, input=input)
    if r.rc != 0:
        raise TidyError(f"git {' '.join(args)} falhou: {r.err.strip()}")
    return r.out


def repo_root(path):
    r = git(path, "rev-parse", "--show-toplevel")
    if r.rc != 0:
        raise TidyError(f"nao e um repositorio git: {path}")
    return Path(r.out.strip())


def rev(root, ref):
    """The commit id a ref points to, or None."""
    r = git(root, "rev-parse", "--verify", "--quiet", ref + "^{commit}")
    return r.out.strip() if r.rc == 0 else None


def detect_base(root, override=None):
    """--base, else the branch origin/HEAD points to, else the first of main, master, base, trunk."""
    if override:
        if rev(root, override) is None:
            raise TidyError(f"a base '{override}' nao existe")
        full = git(root, "rev-parse", "--symbolic-full-name", override).out.strip()
        return full[len("refs/heads/"):] if full.startswith("refs/heads/") else override
    r = git(root, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
    if r.rc == 0 and "/" in r.out.strip():
        short = r.out.strip().split("/", 1)[1]
        if rev(root, "refs/heads/" + short):
            return short
    for name in ("main", "master", "base", "trunk"):
        if rev(root, "refs/heads/" + name):
            return name
    raise TidyError("nao consegui detectar a branch base; passe --base REF")


def base_refs(root, base):
    """The refs a branch may be merged into: the local base and, when it exists, origin/<base>. Full names, so
    a tag called like the base cannot stand in for it (`git` prefers tags to branches for a short name)."""
    local = "refs/heads/" + base
    refs = [local] if rev(root, local) else [base]
    remote = "refs/remotes/origin/" + base
    if rev(root, remote):
        refs.append(remote)
    return refs


def base_branch_names(root, base):
    """Local branch names that are never offered: the base itself and, for `--base origin/main`, its local twin."""
    names = {base}
    full = git(root, "rev-parse", "--symbolic-full-name", base).out.strip()
    if full.startswith("refs/remotes/"):
        names.add(full.split("/", 3)[3])
    return names


# ---------------------------------------------------------------- what exists

def list_branches(root):
    fmt = "%(refname)%09%(objectname)%09%(upstream:track)%09%(committerdate:unix)%09%(authorname)%09%(subject)"
    rows = []
    for line in git_ok(root, "for-each-ref", "--format=" + fmt, "refs/heads").splitlines():
        ref, sha, track, ts, author, subject = line.split("\t", 5)
        rows.append({"name": ref[len("refs/heads/"):], "sha": sha, "gone": track == "[gone]", "ts": int(ts or 0), "author": author,
                     "subject": subject})
    return rows


def list_worktrees(root):
    """Entries of `git worktree list --porcelain`; the first one is the main worktree."""
    blocks, cur = [], {}
    for line in git_ok(root, "worktree", "list", "--porcelain").splitlines() + [""]:
        if not line:
            if cur:
                blocks.append(cur)
                cur = {}
            continue
        key, _, value = line.partition(" ")
        cur[key] = value
    return blocks


def list_stashes(root):
    rows = []
    for line in git_ok(root, "stash", "list", "--format=%H%x09%ct%x09%gs").splitlines():
        sha, ts, subject = line.split("\t", 2)
        rows.append({"sha": sha, "ts": int(ts or 0), "subject": subject})
    return rows


def dirty_files(path):
    """Tracked changes and untracked files of a worktree; None when git cannot tell."""
    r = git(path, "status", "--porcelain", "--untracked-files=all")
    return [line for line in r.out.splitlines() if line.strip()] if r.rc == 0 else None


def ignored_entries(path, limit=20):
    """Top-level entries git ignores in a worktree (`.env`, `node_modules/`): they are in no commit and removing
    the worktree deletes them, although `git status` calls it clean."""
    r = git(path, "ls-files", "--others", "--ignored", "--exclude-standard", "--directory")
    return [line for line in r.out.splitlines() if line.strip()][:limit] if r.rc == 0 else []


def last_commit(root, sha):
    ts, author, subject = git_ok(root, "log", "-1", "--format=%ct%x09%an%x09%s", sha).strip().split("\t", 2)
    return int(ts), author, subject


def ahead_behind(root, base, sha):
    parts = git(root, "rev-list", "--left-right", "--count", f"{base}...{sha}").out.split()
    return (int(parts[1]), int(parts[0])) if len(parts) == 2 else (0, 0)


def unique_commits(root, sha, name=None):
    """(count, up to 5 'id subject' lines) of the commits reachable from sha and from no other branch, remote or tag."""
    scope = ["--not", *([f"--exclude={name}"] if name else []), "--branches", "--remotes", "--tags"]
    count = int(git(root, "rev-list", "--count", sha, *scope).out.strip() or 0)
    lines = git(root, "log", "-n", "5", "--format=%h %s", sha, *scope).out.splitlines()
    return count, lines


# ---------------------------------------------------------------- proof of "merged"

def is_ancestor(root, sha, ref):
    return git(root, "merge-base", "--is-ancestor", sha, ref).rc == 0


def patch_equivalent(root, sha, refs):
    """P3: every patch of the branch is already in a base ref (cherry-pick, rebase), or the branch's whole
    diff has the same patch-id as one recent base commit (a squash merge). A false negative is safe (the
    item stays P4); only a false positive would hurt, hence the extra confirmation and the backup."""
    for ref in refs:
        cherry = git(root, "cherry", ref, sha)
        marks = [line[:1] for line in cherry.out.splitlines() if line.strip()] if cherry.rc == 0 else []
        if marks and all(m == "-" for m in marks):
            return True
        mb = git(root, "merge-base", ref, sha)
        if mb.rc != 0:
            continue
        fork = mb.out.strip()
        whole = git(root, "diff", "--no-ext-diff", "--no-textconv", fork, sha)
        if whole.rc != 0 or not whole.out.strip():
            continue
        mine = git(root, "patch-id", "--stable", input=whole.out).out.split()
        if not mine:
            continue
        log = git(root, "log", "-p", "--no-ext-diff", "--no-textconv", "--no-merges", "--format=commit %H", "-n", str(SQUASH_WINDOW),
                  f"{fork}..{ref}")
        if log.rc != 0:
            continue
        seen = {line.split()[0] for line in git(root, "patch-id", "--stable", input=log.out).out.splitlines() if line.split()}
        if mine[0] in seen:
            return True
    return False


def load_merged_prs(root, mode):
    """{branch name: [{number, url, oid}]} of merged PRs from `gh`, or None when gh is off or unusable."""
    if mode == "off":
        return None
    env = {**os.environ, "GH_PROMPT_DISABLED": "1", "GH_NO_UPDATE_NOTIFIER": "1", "NO_COLOR": "1"}
    try:
        r = subprocess.run(["gh", "pr", "list", "--state", "merged", "--limit", "300", "--json",
                            "number,headRefName,headRefOid,url"], cwd=str(root), capture_output=True, text=True,
                           timeout=30, env=env)
        data = json.loads(r.stdout) if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    if not isinstance(data, list):
        return None
    out = {}
    for pr in data:
        if isinstance(pr, dict) and isinstance(pr.get("headRefName"), str):
            out.setdefault(pr["headRefName"], []).append(
                {"number": pr.get("number"), "url": pr.get("url") or "", "oid": pr.get("headRefOid") or ""})
    return out


def classify(root, sha, name, refs, prs):
    """P1 ancestor of the base, P2 merged PR with the same tip, P3 equivalent patch or squash, else P4."""
    if any(is_ancestor(root, sha, ref) for ref in refs):
        return "P1"
    if any(pr["oid"] == sha for pr in (prs or {}).get(name or "", [])):
        return "P2"
    if patch_equivalent(root, sha, refs):
        return "P3"
    return "P4"


def pr_note(prs, name, sha):
    if prs is None:
        return ""
    found = prs.get(name or "", [])
    if not found:
        return "sem PR mergeado"
    pr = found[0]
    return f"#{pr['number']} mergeado" + (" (a ponta confere)" if pr["oid"] == sha else " (a ponta e DIFERENTE da do PR)")


def remote_note(root, name, gone):
    if rev(root, "refs/remotes/origin/" + name):
        return f"origin/{name} ainda existe (nao sera tocada)"
    return f"origin/{name} ja foi removida" if gone else "sem contraparte"


# ---------------------------------------------------------------- inventory

def dir_size(path):
    total = 0
    for here, _dirs, files in os.walk(path, followlinks=False):
        for f in files:
            try:
                total += os.lstat(os.path.join(here, f)).st_size
            except OSError:
                pass
    return total


def inventory(root, base, gh_mode="auto"):
    """Everything the board can offer and everything it must never touch. Read-only: no fetch, no network."""
    root = Path(root)
    refs = base_refs(root, base)
    base_names = base_branch_names(root, base)
    prs = load_merged_prs(root, gh_mode)
    trees = list_worktrees(root)
    here = Path(os.path.realpath(root))
    main_path = Path(os.path.realpath(trees[0]["worktree"])) if trees else here
    checked_out = {wt["branch"][len("refs/heads/"):]: wt["worktree"] for wt in trees
                   if wt.get("branch", "").startswith("refs/heads/")}
    items, untouched = [], []

    for b in list_branches(root):
        name = b["name"]
        if name in base_names:
            untouched.append({"name": name, "why": "branch base do repositorio"})
            continue
        wt = checked_out.get(name)
        if wt:  # a linked worktree carries its branch in its own card
            real = Path(os.path.realpath(wt))
            if real == here:
                untouched.append({"name": name, "why": "branch atual (em uso por este worktree)"})
            elif real == main_path:
                untouched.append({"name": name, "why": f"em uso pelo worktree principal ({wt})"})
            continue
        proof = classify(root, b["sha"], name, refs, prs)
        ahead, behind = ahead_behind(root, refs[0], b["sha"])
        count, lines = unique_commits(root, b["sha"], name) if proof in RISKY_PROOFS else (0, [])
        items.append({"kind": "branch", "name": name, "sha": b["sha"], "proof": proof, "ts": b["ts"],
                      "author": b["author"], "subject": b["subject"], "ahead": ahead, "behind": behind,
                      "unique": lines, "unique_count": count, "pr": pr_note(prs, name, b["sha"]),
                      "remote": remote_note(root, name, b["gone"]), "backup": proof in RISKY_PROOFS})

    for wt in trees[1:]:
        path = wt["worktree"]
        if "bare" in wt:
            continue
        if Path(os.path.realpath(path)) == here:
            untouched.append({"name": path, "why": "worktree atual"})
            continue
        if "locked" in wt:
            untouched.append({"name": path, "why": "worktree bloqueado (locked)"})
            continue
        if "prunable" in wt or not Path(path).is_dir():
            untouched.append({"name": path, "why": "diretorio ausente (git worktree prune resolve)"})
            continue
        dirty = dirty_files(path)
        if dirty is None:
            untouched.append({"name": path, "why": "nao consegui ler o estado do worktree"})
            continue
        if dirty:
            untouched.append({"name": path, "why": f"{len(dirty)} arquivo(s) alterado(s) ou nao rastreado(s): apagar perderia trabalho sem sha para recuperar"})
            continue
        sha = wt["HEAD"]
        branch = wt["branch"][len("refs/heads/"):] if wt.get("branch", "").startswith("refs/heads/") else None
        proof = classify(root, sha, branch, refs, prs)
        ts, author, subject = last_commit(root, sha)
        ahead, behind = ahead_behind(root, refs[0], sha)
        count, lines = unique_commits(root, sha, branch) if proof in RISKY_PROOFS else (0, [])
        items.append({"kind": "worktree", "name": path, "path": path, "sha": sha, "branch": branch, "proof": proof,
                      "drop_branch": bool(branch) and proof in SAFE_PROOFS and branch not in base_names, "ts": ts, "author": author,
                      "subject": subject, "ahead": ahead, "behind": behind, "unique": lines, "unique_count": count,
                      "pr": pr_note(prs, branch, sha), "remote": remote_note(root, branch, False) if branch else "",
                      "size": dir_size(path), "ignored": ignored_entries(path), "backup": branch is None and proof in RISKY_PROOFS})

    for s in list_stashes(root):
        files = git(root, "diff", "--no-ext-diff", "--name-only", s["sha"] + "^1", s["sha"]).out.splitlines()
        stat = git(root, "diff", "--no-ext-diff", "--shortstat", s["sha"] + "^1", s["sha"]).out.strip()
        items.append({"kind": "stash", "name": s["subject"], "sha": s["sha"], "proof": "P4", "ts": s["ts"],
                      "author": "", "subject": s["subject"], "files": files[:5], "file_count": len(files),
                      "shortstat": stat, "backup": True})

    items.sort(key=lambda i: (PROOFS.index(i["proof"]), i["ts"]))
    return {"base": base, "base_sha": rev(root, base), "gh": prs is not None, "items": items, "untouched": untouched}


# ---------------------------------------------------------------- cards

WARN_CARDS = 40  # `check` warns above this many cards: a long board is a tiring one
SHA = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
KINDS = ("branch", "worktree", "stash")
LABELS = {  # the board's own wording; "approve" deletes, so it is painted as the dangerous action
    "approve": {"text": "Apagar", "tone": "danger"},
    "reject": {"text": "Manter", "tone": "safe"},
    "maybe": {"text": "Depois", "tone": "caution"},
}


def short_name(name):
    """A worktree is named by its folder on the card (the full path is in its own field)."""
    return os.path.basename(name.rstrip("/")) if os.path.isabs(name) else name


def safe_text(text):
    """Card text is shown with inline-code markup: a stray backtick would swallow the rest of the line."""
    return str(text).replace("`", "'")


def age_text(ts, now):
    days = int((now - ts) // 86400)
    return "hoje" if days <= 0 else f"ha {days} dia" + ("" if days == 1 else "s")


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def backup_name(it):
    if it["kind"] == "stash":
        return BACKUP + "stash-" + it["sha"][:12]
    if it["kind"] == "worktree":
        return BACKUP + "wt-" + it["sha"][:12]
    return BACKUP + it["name"]


def confirm_text(it):
    """The second-press warning of a card that is not provably merged (None for P1 and P2)."""
    if it["kind"] == "stash":
        return "Trabalho unico: este stash nao existe em outro lugar. Um backup sera criado antes de descartar."
    if it["kind"] == "worktree" and it.get("ignored"):
        shown = ", ".join(safe_text(e) for e in it["ignored"][:3])
        return f"Este worktree tem arquivos ignorados pelo git (ex.: {shown}) que serao apagados junto e nao tem backup."
    if it["kind"] == "worktree":
        if it["proof"] in SAFE_PROOFS:
            return None
        if it["branch"]:
            return "A branch deste worktree tem trabalho que so existe nela: ela fica. Remove so a pasta do worktree."
        return "Este worktree esta sem branch e seus commits so existem aqui. Um backup sera criado antes de remover."
    if it["proof"] == "P3":
        return "Heuristica: o mesmo patch parece estar na base, mas isso nao e prova. Um backup sera criado antes de apagar."
    if it["proof"] == "P4":
        return "Trabalho unico: estes commits nao existem em nenhuma outra branch, remoto ou tag. Um backup sera criado antes de apagar."
    return None


def card_for(it, iid, now):
    kind, name = it["kind"], it["name"]
    fields = [{"label": "Prova", "text": f"{it['proof']} - {PROOF_TEXT[it['proof']]}"}]
    if kind == "worktree":
        fields.append({"label": "Worktree", "text": f"`{safe_text(it['path'])}` ({human_size(it['size'])}, limpo)"})
        if it["branch"]:
            tail = " (sai junto)" if it["drop_branch"] else " (fica)"
            fields.append({"label": "Branch", "text": f"`{safe_text(it['branch'])}`{tail}"})
        else:
            fields.append({"label": "Branch", "text": "nenhuma (HEAD solto)"})
        if it.get("ignored"):
            body = "\n".join(f"`{safe_text(e)}`" for e in it["ignored"][:5])
            fields.append({"label": "Ignorados", "text": body + "\n(apagados junto com a pasta, sem backup)"})
    who = f", {safe_text(it['author'])}" if it["author"] else ""
    fields.append({"label": "Ultimo", "text": f"{safe_text(it['subject'])} ({age_text(it['ts'], now)}{who})"})
    if kind == "stash":
        fields.append({"label": "Conteudo", "text": safe_text(it["shortstat"] or "vazio")})
    else:
        fields.append({"label": "Vs base", "text": f"{it['ahead']} a frente, {it['behind']} atras"})
        if it["pr"]:
            fields.append({"label": "PR", "text": it["pr"]})
        if it["remote"]:
            fields.append({"label": "Remoto", "text": safe_text(it["remote"])})
    if kind == "stash" and it["files"]:
        more = it["file_count"] - len(it["files"])
        body = "\n".join(f"`{safe_text(f)}`" for f in it["files"]) + (f"\n(+{more})" if more > 0 else "")
        fields.append({"label": "Arquivos", "text": body})
    elif kind != "stash" and it["unique"]:
        more = it["unique_count"] - len(it["unique"])
        body = "\n".join(f"`{safe_text(line)}`" for line in it["unique"]) + (f"\n(+{more})" if more > 0 else "")
        fields.append({"label": "So aqui", "text": body})
    if kind == "branch":
        effect = "Apaga a branch local."
    elif kind == "worktree":
        effect = "Remove a pasta do worktree" + (" e a branch." if it["drop_branch"] else ".")
    else:
        effect = "Descarta o stash."
    if it["backup"]:
        effect += f" Antes, guarda `{safe_text(backup_name(it))}`."
    fields.append({"label": "Efeito", "text": effect})
    verb = {"branch": "Apagar a branch", "worktree": "Remover o worktree", "stash": "Descartar o stash"}[kind]
    card = {"id": iid, "tag": it["proof"], "title": f"{verb} {safe_text(short_name(name))}?", "fields": fields}
    confirm = confirm_text(it)
    if confirm:
        card["confirm"] = confirm
    return card


def build_scan(root, inv, now=None, stamp=None):
    """(batch, scan) for an inventory, or None when there is nothing to offer."""
    if not inv["items"]:
        return None
    now = now or time.time()
    stamp = stamp or time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
    repo_name = Path(root).name
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", repo_name).strip("-") or "repo"
    cards, entries, safe_ids, safe_lines = [], [], [], []
    for n, it in enumerate(inv["items"], 1):
        iid = f"T{n:02d}"
        cards.append(card_for(it, iid, now))
        entries.append({"id": iid, "kind": it["kind"], "name": it["name"], "sha": it["sha"], "proof": it["proof"],
                        "branch": it.get("branch"), "path": it.get("path"), "drop_branch": bool(it.get("drop_branch")),
                        "backup": bool(it["backup"])})
        if it["proof"] in SAFE_PROOFS and not it.get("ignored"):  # ignored files need their own confirmation
            safe_ids.append(iid)
            safe_lines.append(f"`{safe_text(short_name(it['name']))}` ({it['kind']}, {it['proof']})")
    group = None
    if len(safe_ids) >= 2:
        lines = "\n".join(safe_lines)
        cards.insert(0, {"id": "G", "tag": "grupo P1/P2",
                         "title": f"Apagar os {len(safe_ids)} itens provados como mergeados?",
                         "fields": [{"label": "Itens", "text": lines},
                                    {"label": "Regra", "text": "Vale para os itens abaixo em que voce nao marcar Manter ou Depois. Nao inclui P3, P4 nem stashes."}]})
        group = {"id": "G", "members": safe_ids}
    if inv["untouched"]:  # a field, not meta: the side panel's key column is too narrow for this label
        lines = "\n".join(f"`{safe_text(short_name(u['name']))}`: {safe_text(u['why'])}" for u in inv["untouched"])
        cards[0]["fields"].append({"label": "Nao tocar", "text": lines})
    cards[0]["meta"] = {"Base": inv["base"], "gh": "sim" if inv["gh"] else "nao (so git local)"}
    batch = {"batch_id": f"tidy-{slug}-{stamp}", "title": f"Limpeza de {repo_name}",
             "subtitle": f"base: {inv['base']} - gh: {'sim' if inv['gh'] else 'nao'} - {len(inv['items'])} itens",
             "round": 1, "labels": LABELS, "items": cards}
    scan = {"version": VERSION, "repo": str(root), "base": inv["base"], "base_sha": inv["base_sha"], "gh": inv["gh"],
            "scanned_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(now)), "group": group,
            "untouched": inv["untouched"], "items": entries}
    return batch, scan


def write_private(path, text):
    """0600 from creation, and never through a planted symlink (the files name your branches and paths)."""
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)


def dump_json(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def write_dir(out, batch, scan):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    write_private(out / "batch.json", dump_json(batch))
    write_private(out / "scan.json", dump_json(scan))


# ---------------------------------------------------------------- reading a scanned directory

def load_dir(d):
    d = Path(d)
    try:
        batch = json.loads((d / "batch.json").read_text(encoding="utf-8"))
        scan = json.loads((d / "scan.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise TidyError(f"nao consegui ler batch.json e scan.json em {d}: {e}")
    return batch, scan


def scan_problems(batch, scan):
    """What is wrong with a batch.json + scan.json pair; empty when `apply` may trust it."""
    if not isinstance(scan, dict) or not isinstance(scan.get("items"), list):
        return ["scan.json: 'items' deve ser uma lista"]
    if not isinstance(batch, dict) or not isinstance(batch.get("items"), list):
        return ["batch.json: 'items' deve ser uma lista"]
    errs = []
    for key in ("repo", "base"):
        if not isinstance(scan.get(key), str) or not scan[key]:
            errs.append(f"scan.json: '{key}' obrigatorio (texto)")
    card_ids = {c.get("id") for c in batch["items"] if isinstance(c, dict)}
    entries, seen = {}, set()
    for i, it in enumerate(scan["items"]):
        where = f"scan.json item {i}"
        if not isinstance(it, dict):
            errs.append(f"{where}: deve ser objeto")
            continue
        iid = it.get("id")
        if not isinstance(iid, str) or not iid or iid == "G":
            errs.append(f"{where}: 'id' invalido")
            continue
        if iid in seen:
            errs.append(f"{where}: id duplicado '{iid}'")
        seen.add(iid)
        entries[iid] = it
        if iid not in card_ids:
            errs.append(f"{where}: '{iid}' nao tem card no batch.json")
        if it.get("kind") not in KINDS:
            errs.append(f"{where}: 'kind' deve ser branch, worktree ou stash")
        if it.get("proof") not in PROOFS:
            errs.append(f"{where}: 'proof' deve ser P1, P2, P3 ou P4")
        if not isinstance(it.get("sha"), str) or not SHA.fullmatch(it["sha"]):
            errs.append(f"{where}: 'sha' deve ser um id de commit completo")
        if not isinstance(it.get("name"), str) or not it["name"]:
            errs.append(f"{where}: 'name' obrigatorio")
        if it.get("kind") == "worktree" and not it.get("path"):
            errs.append(f"{where}: um worktree precisa de 'path'")
    group = scan.get("group")
    if group is not None:
        if not isinstance(group, dict) or group.get("id") != "G" or not isinstance(group.get("members"), list):
            errs.append("scan.json: 'group' invalido")
        else:
            if "G" not in card_ids:
                errs.append("batch.json: falta o card G do grupo")
            for m in group["members"]:
                if m not in entries or entries[m].get("proof") not in SAFE_PROOFS:
                    errs.append(f"scan.json: o grupo so aceita itens P1 ou P2 ('{m}')")
    for cid in sorted(c for c in card_ids if isinstance(c, str) and c != "G"):
        if cid not in entries:
            errs.append(f"batch.json: o card '{cid}' nao tem entrada no scan.json")
    return errs


# ---------------------------------------------------------------- commands

def cmd_scan(a):
    root = repo_root(a.repo)
    base = detect_base(root, a.base)
    inv = inventory(root, base, a.gh)
    built = build_scan(root, inv)
    for u in inv["untouched"]:
        print(f"NAO TOCAR: {u['name']} ({u['why']})")
    if built is None:
        print("TIDY-BOARD: nada para limpar")
        return 0
    batch, scan = built
    out = Path(a.out) if a.out else root / ".tidy-board" / batch["batch_id"]
    if not a.out and out.exists():  # same batch id: the panel would resume decisions made for other cards
        raise TidyError(f"a pasta {out} ja existe (dois scans no mesmo segundo); tente de novo")
    write_dir(out, batch, scan)
    counts = ", ".join(f"{p} {n}" for p in PROOFS if (n := sum(1 for i in scan["items"] if i["proof"] == p)))
    print(f"TIDY-BOARD DIR: {out}")
    print(f"TIDY-BOARD ITENS: {len(scan['items'])} ({counts}); base {base}; gh {'sim' if scan['gh'] else 'nao'}")
    return 0


def cmd_check(a):
    batch, scan = load_dir(a.dir)
    errs = scan_problems(batch, scan)
    if errs:
        print("scan.json/batch.json invalidos:\n- " + "\n- ".join(errs), file=sys.stderr)
        return 1
    n = len(scan["items"])
    if n > WARN_CARDS:
        print(f"aviso: {n} itens; acima de {WARN_CARDS} a revisao cansa (considere limpar em duas rodadas)", file=sys.stderr)
    print(f"ok: {n} itens, lote {batch['batch_id']}")
    return 0


def parser():
    p = argparse.ArgumentParser(prog="tidy_board.py", description="Cards para limpar branches, worktrees e stashes.")
    p.add_argument("--version", action="version", version=f"tidy-board {VERSION}")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="le o git (somente leitura) e escreve batch.json + scan.json")
    s.add_argument("repo", nargs="?", default=".")
    s.add_argument("--base", help="branch base (padrao: origin/HEAD, depois main, master, base, trunk)")
    s.add_argument("--gh", choices=("auto", "off"), default="auto", help="usar o gh para provar PRs mergeados")
    s.add_argument("--out", help="pasta do lote (padrao: <repo>/.tidy-board/<batch_id>)")
    c = sub.add_parser("check", help="valida batch.json + scan.json")
    c.add_argument("dir")
    a = sub.add_parser("apply", help="reconfere cada item aprovado e apaga")
    a.add_argument("dir")
    a.add_argument("--dry-run", action="store_true", help="mostra o que faria, sem apagar nada")
    r = sub.add_parser("restore", help="recria um item apagado a partir do backup ou do sha registrado")
    r.add_argument("dir")
    r.add_argument("id")
    return p


COMMANDS = {"scan": cmd_scan, "check": cmd_check}


# ---------------------------------------------------------------- apply: re-verify, then delete

def outcome(it, action, reason=None, backup=None):
    out = {"id": it["id"], "kind": it["kind"], "name": it["name"], "sha": it["sha"], "proof": it["proof"],
           "action": action}
    if reason:
        out["reason"] = reason
    if backup:
        out["backup"] = backup
    return out


def skip(it, reason):
    return outcome(it, "skipped", reason)


def checked_out_branches(root):
    return {wt["branch"][len("refs/heads/"):]: wt["worktree"] for wt in list_worktrees(root)
            if wt.get("branch", "").startswith("refs/heads/")}


def make_backup(root, refname, sha):
    """Create the backup ref; None when it is in place, otherwise the reason it could not be made."""
    current = git(root, "rev-parse", "--verify", "--quiet", refname).out.strip()
    if current == sha:
        return None
    if current:
        return "ja existe um backup com outro sha"
    r = git(root, "update-ref", refname, sha, "")  # the empty old value means "must not exist yet"
    return None if r.rc == 0 else "nao consegui criar o backup: " + r.err.strip()


def merged_prs_once(root, scan):
    """gh is asked at most once per apply run, and only when a P2 item needs it (None: gh unusable)."""
    if "_prs" not in scan:
        scan["_prs"] = load_merged_prs(root, "auto")
    return scan["_prs"]


def pr_blocker(root, scan, name, sha):
    prs = merged_prs_once(root, scan)
    if prs is None:
        return "gh indisponivel: nao consegui reconferir o PR mergeado"
    if not any(pr["oid"] == sha for pr in prs.get(name, [])):
        return "o PR mergeado nao confere mais com a ponta da branch"
    return None


def branch_blocker(root, scan, name, sha, proof, held_by=None):
    """Why a branch must not be deleted now (None when it may): the scan is a photograph, this is the check."""
    tip = rev(root, "refs/heads/" + name)
    if tip is None:
        return "a branch nao existe mais"
    if tip != sha:
        return "a ponta mudou desde o scan"
    if name in base_branch_names(root, scan["base"]):
        return "e a branch base"
    held = checked_out_branches(root).get(name)
    if held and not (held_by and os.path.realpath(held) == os.path.realpath(held_by)):
        return f"esta em uso em {held}"
    merged = any(is_ancestor(root, sha, ref) for ref in base_refs(root, scan["base"]))
    if proof == "P1" and not merged:
        return "deixou de estar mesclada na base"
    if proof == "P2" and not merged:  # P2 rested on gh at scan time: ask again, unless the history proves it now
        return pr_blocker(root, scan, name, sha)
    return None


def delete_branch(root, name, sha):
    """Delete the ref only if it still points at sha (a commit landing since the check makes git refuse), then
    drop the branch's config section the way `git branch -D` does (best effort)."""
    r = git(root, "update-ref", "-d", "refs/heads/" + name, sha)
    if r.rc == 0:
        git(root, "config", "--remove-section", "branch." + name)
    return r


def apply_branch(root, scan, it, dry):
    why = branch_blocker(root, scan, it["name"], it["sha"], it["proof"])
    if why:
        return skip(it, why)
    backup = backup_name(it) if it["proof"] in RISKY_PROOFS else None  # from the re-verified proof, not from a flag in scan.json
    if dry:
        return outcome(it, "would-delete", backup=backup)
    if backup:
        why = make_backup(root, backup, it["sha"])
        if why:
            return skip(it, why)
    r = delete_branch(root, it["name"], it["sha"])
    if r.rc != 0:
        return skip(it, r.err.strip() or "a branch mudou durante o apply")
    return outcome(it, "deleted", backup=backup)


def apply_worktree(root, scan, it, dry):
    path = it["path"]
    trees = list_worktrees(root)
    real = os.path.realpath(path)
    entry = next((wt for wt in trees if os.path.realpath(wt["worktree"]) == real), None)
    if entry is None or not Path(path).is_dir():
        return skip(it, "o worktree nao existe mais")
    if real == os.path.realpath(trees[0]["worktree"]) or real == os.path.realpath(root):
        return skip(it, "e o worktree principal ou o atual")
    if "locked" in entry:
        return skip(it, "o worktree esta bloqueado (locked)")
    dirty = dirty_files(path)
    if dirty is None:
        return skip(it, "nao consegui ler o estado do worktree")
    if dirty:
        return skip(it, f"tem {len(dirty)} arquivo(s) alterado(s) ou nao rastreado(s)")
    head = git(path, "rev-parse", "--verify", "--quiet", "HEAD").out.strip()
    if head != it["sha"]:
        return skip(it, "o HEAD mudou desde o scan")
    live = entry["branch"][len("refs/heads/"):] if entry.get("branch", "").startswith("refs/heads/") else None
    if live != it.get("branch"):
        return skip(it, "o worktree mudou de branch desde o scan")
    # what to delete and what to back up come from the live state and the re-verified proof, never from scan.json flags
    drop = live if (live and it["proof"] in SAFE_PROOFS and live not in base_branch_names(root, scan["base"])) else None
    if drop:
        why = branch_blocker(root, scan, drop, it["sha"], it["proof"], held_by=path)
        if why:
            return skip(it, f"a branch {drop}: {why}")
    risky_head = live is None and (it["proof"] in RISKY_PROOFS or
                                   not any(is_ancestor(root, it["sha"], ref) for ref in base_refs(root, scan["base"])))
    backup = backup_name(it) if risky_head else None
    if dry:
        return outcome(it, "would-delete", backup=backup)
    if backup:
        why = make_backup(root, backup, it["sha"])
        if why:
            return skip(it, why)
    r = git(root, "worktree", "remove", path)  # never --force: a dirty tree must stop here
    if r.rc != 0:
        return skip(it, r.err.strip() or "git worktree remove falhou")
    if drop:
        r = delete_branch(root, drop, it["sha"])
        if r.rc != 0:
            return outcome(it, "deleted", reason="worktree removido; a branch ficou: " + r.err.strip(), backup=backup)
    return outcome(it, "deleted", backup=backup)


def apply_stash(root, it, dry):
    if it["sha"] not in [st["sha"] for st in list_stashes(root)]:
        return skip(it, "o stash nao existe mais")
    backup = backup_name(it)
    if dry:
        return outcome(it, "would-delete", backup=backup)
    why = make_backup(root, backup, it["sha"])
    if why:
        return skip(it, why)
    shas = [st["sha"] for st in list_stashes(root)]  # read again right before the drop: a stash pushed meanwhile moved the indexes
    if it["sha"] not in shas:
        return skip(it, "o stash mudou durante o apply")
    r = git(root, "stash", "drop", f"stash@{{{shas.index(it['sha'])}}}")
    if r.rc != 0:
        return skip(it, r.err.strip() or "git stash drop falhou")
    return outcome(it, "deleted", backup=backup)


def apply_item(root, scan, it, dry):
    if it["kind"] == "branch":
        return apply_branch(root, scan, it, dry)
    if it["kind"] == "worktree":
        return apply_worktree(root, scan, it, dry)
    return apply_stash(root, it, dry)


def decision_of(decisions, iid):
    entry = decisions.get(iid)
    return entry.get("decision") if isinstance(entry, dict) else None


def approved_items(scan, decisions):
    """What to delete: an item's own decision first, else the group card (P1 and P2 members only).
    Manter and Depois on an item always win over the group, and nothing is deleted by default."""
    group = scan.get("group")
    group_on = group is not None and decision_of(decisions, "G") == "approved"
    members = set(group["members"]) if group else set()
    out = []
    for it in scan["items"]:
        own = decision_of(decisions, it["id"])
        if own == "approved" or (own is None and group_on and it["id"] in members):
            out.append(it)
    return out


def read_decisions(d, batch):
    try:
        state = json.loads((Path(d) / "decisions.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise TidyError("decisions.json ausente ou ilegivel: suba o painel e conclua antes do apply")
    if not isinstance(state, dict) or not isinstance(state.get("items"), dict):
        raise TidyError("decisions.json com formato invalido")
    if state.get("batch_id") != batch.get("batch_id") or state.get("round") != int(batch.get("round", 1)):
        raise TidyError("decisions.json e de outro lote ou rodada: nao vou agir sobre decisoes antigas")
    if state.get("finished") is not True:
        raise TidyError("o painel nao foi concluido (clique em Concluir antes do apply)")
    return state["items"]


def read_applied(d):
    try:
        data = json.loads((Path(d) / "applied.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [e for e in data if isinstance(e, dict) and "id" in e] if isinstance(data, list) else []


def save_applied(d, results):
    """Merge into applied.json: what an earlier run deleted (and backed up) is never forgotten by a re-run."""
    merged = {e["id"]: e for e in read_applied(d)}
    for r in results:
        if merged.get(r["id"], {}).get("action") == "deleted" and r["action"] != "deleted":
            continue
        merged[r["id"]] = {**r, "at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    write_private(Path(d) / "applied.json", dump_json(list(merged.values())))


def cmd_apply(a):
    batch, scan = load_dir(a.dir)
    errs = scan_problems(batch, scan)
    if errs:
        raise TidyError("scan.json/batch.json invalidos: " + "; ".join(errs))
    decisions = read_decisions(a.dir, batch)
    root = Path(scan["repo"])
    if not root.is_dir() or git(root, "rev-parse", "--git-dir").rc != 0:
        raise TidyError(f"o repositorio do scan nao existe mais: {root}")
    todo = approved_items(scan, decisions)
    if not todo:
        print("APPLY: nada aprovado; nada foi apagado")
        return 0
    results = []
    try:
        for it in todo:
            results.append(apply_item(root, scan, it, a.dry_run))
    finally:  # an interrupt or a crash mid-run must not lose the record of what was already deleted
        if results and not a.dry_run:
            save_applied(a.dir, results)
    for r in results:
        line = f"{r['action']:<12} {r['id']} {r['kind']} {r['name']}"
        if r.get("backup"):
            line += f"  (backup {r['backup']})"
        if r.get("reason"):
            line += f"  - {r['reason']}"
        print(line)
    done = sum(1 for r in results if r["action"] in ("deleted", "would-delete"))
    skipped = len(results) - done
    print(f"APPLY{' (simulado)' if a.dry_run else ''}: {done} {'seriam apagados' if a.dry_run else 'apagados'}, {skipped} pulados")
    return 1 if skipped else 0


def cmd_restore(a):
    batch, scan = load_dir(a.dir)
    applied = read_applied(a.dir)
    entry = next((e for e in applied if e["id"] == a.id), None)
    if entry is None or entry.get("action") != "deleted":
        raise TidyError(f"'{a.id}' nao foi apagado por este lote (veja applied.json)")
    root = Path(scan["repo"])
    sha = entry["sha"]
    if git(root, "cat-file", "-e", sha + "^{commit}").rc != 0:
        raise TidyError(f"o commit {sha[:12]} nao existe mais neste repositorio")
    if not entry.get("backup"):  # P1/P2: the commits are in the base, there is nothing to bring back from a backup
        item = next((i for i in scan["items"] if i["id"] == a.id), {})
        target = entry["name"] if entry["kind"] == "branch" else (item.get("branch") or "<nome>")
        raise TidyError(f"'{a.id}' nao tem backup (estava provado como mesclado e seus commits estao na base): "
                        f"se precisar, recrie com `git branch {target} {sha}`")
    if entry["kind"] == "stash":
        r = git(root, "stash", "store", "-m", f"tidy-board restore {sha[:12]}", sha)
        what = "stash recriado"
    else:
        name = entry["name"] if entry["kind"] == "branch" else f"tidy-board/restored-{sha[:12]}"
        r = git(root, "branch", name, sha)
        what = f"branch {name} recriada em {sha[:12]}"
        if entry["kind"] == "worktree":
            what += f" (o worktree nao e recriado: git worktree add {entry['name']} {name})"
    if r.rc != 0:
        raise TidyError(r.err.strip() or "git falhou ao restaurar")
    git(root, "update-ref", "-d", entry["backup"])
    entry["action"] = "restored"
    write_private(Path(a.dir) / "applied.json", dump_json(applied))
    print(f"RESTORE: {what}")
    return 0


COMMANDS.update({"apply": cmd_apply, "restore": cmd_restore})


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        return COMMANDS[args.cmd](args)
    except TidyError as e:
        print(f"erro: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

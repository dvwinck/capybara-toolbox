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

# Every git call is deaf to what the repository's own config asks git to run, never prompts, never
# fetches lazily and never touches the network.
GIT_FLAGS = ["-c", "core.quotepath=off", "-c", "core.fsmonitor=false", "-c", "protocol.allow=never",
             "-c", "log.showSignature=false", "-c", "i18n.logOutputEncoding=UTF-8"]
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
        return override
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
    """The refs a branch may be merged into: the local base and, when it exists, origin/<base>."""
    refs = [base]
    if rev(root, "refs/remotes/origin/" + base):
        refs.append("origin/" + base)
    return refs


# ---------------------------------------------------------------- what exists

def list_branches(root):
    fmt = "%(refname:short)%09%(objectname)%09%(upstream:track)%09%(committerdate:unix)%09%(authorname)%09%(subject)"
    rows = []
    for line in git_ok(root, "for-each-ref", "--format=" + fmt, "refs/heads").splitlines():
        name, sha, track, ts, author, subject = line.split("\t", 5)
        rows.append({"name": name, "sha": sha, "gone": track == "[gone]", "ts": int(ts or 0), "author": author,
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
        whole = git(root, "diff", fork, sha)
        if whole.rc != 0 or not whole.out.strip():
            continue
        mine = git(root, "patch-id", "--stable", input=whole.out).out.split()
        if not mine:
            continue
        log = git(root, "log", "-p", "--no-merges", "--format=commit %H", "-n", str(SQUASH_WINDOW), f"{fork}..{ref}")
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
    prs = load_merged_prs(root, gh_mode)
    trees = list_worktrees(root)
    here = Path(os.path.realpath(root))
    main_path = Path(os.path.realpath(trees[0]["worktree"])) if trees else here
    checked_out = {wt["branch"][len("refs/heads/"):]: wt["worktree"] for wt in trees
                   if wt.get("branch", "").startswith("refs/heads/")}
    items, untouched = [], []

    for b in list_branches(root):
        name = b["name"]
        if name == base:
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
        ahead, behind = ahead_behind(root, base, b["sha"])
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
        ahead, behind = ahead_behind(root, base, sha)
        count, lines = unique_commits(root, sha, branch) if proof in RISKY_PROOFS else (0, [])
        items.append({"kind": "worktree", "name": path, "path": path, "sha": sha, "branch": branch, "proof": proof,
                      "drop_branch": bool(branch) and proof in SAFE_PROOFS, "ts": ts, "author": author,
                      "subject": subject, "ahead": ahead, "behind": behind, "unique": lines, "unique_count": count,
                      "pr": pr_note(prs, branch, sha), "remote": remote_note(root, branch, False) if branch else "",
                      "size": dir_size(path), "backup": branch is None and proof in RISKY_PROOFS})

    for s in list_stashes(root):
        files = git(root, "diff", "--name-only", s["sha"] + "^1", s["sha"]).out.splitlines()
        stat = git(root, "diff", "--shortstat", s["sha"] + "^1", s["sha"]).out.strip()
        items.append({"kind": "stash", "name": s["subject"], "sha": s["sha"], "proof": "P4", "ts": s["ts"],
                      "author": "", "subject": s["subject"], "files": files[:5], "file_count": len(files),
                      "shortstat": stat, "backup": True})

    items.sort(key=lambda i: (PROOFS.index(i["proof"]), i["ts"]))
    return {"base": base, "base_sha": rev(root, base), "gh": prs is not None, "items": items, "untouched": untouched}


def main(argv=None):
    print(f"tidy-board {VERSION}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

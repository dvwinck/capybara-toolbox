#!/usr/bin/env python3
# tidy-board 0.1.1 - cards para limpar branches, worktrees e stashes; o apply reconfere e apaga (somente stdlib e git)
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

VERSION = "0.1.1"


BACKUP = "refs/tidy-board/backup/"  # where apply keeps what could not be recreated from another ref
SAFE_PROOFS = ("P1", "P2")  # provably merged: eligible for the group card
RISKY_PROOFS = ("P3", "P4")  # probable or unique: extra confirmation and a backup ref
PROOFS = ("P1", "P2", "P3", "P4")
SQUASH_WINDOW = 500  # base commits compared when looking for a squash
LANGS = ("en", "pt-BR")  # languages of the cards (`scan --lang`); the first is the default
DEFAULT_LANG = "en"

# Every card text, in both languages. The inventory never holds text: it holds codes (proof levels, reason
# codes, PR and remote states) and `t()` renders them. The two tables have the same keys and placeholders.
TEXT = {
    "en": {
        "proof_P1": "proven: ancestor of the base", "proof_P2": "proven: merged PR on GitHub",
        "proof_P3": "probable: the same patch is already in the base", "proof_P4": "unique work: exists only here",
        "why_base_branch": "base branch of the repository", "why_current_branch": "current branch (in use by this worktree)",
        "why_main_worktree": "in use by the main worktree ({path})", "why_current_worktree": "current worktree",
        "why_locked": "locked worktree", "why_missing_dir": "folder missing (git worktree prune fixes it)",
        "why_unreadable": "could not read the state of the worktree",
        "why_dirty": "{n} changed or untracked file(s): deleting would lose work with no sha to recover",
        "pr_none": "no merged PR", "pr_merged": "#{n} merged (the tip matches)", "pr_differs": "#{n} merged (the tip is DIFFERENT from the PR's)",
        "remote_exists": "origin/{name} still exists (it will not be touched)", "remote_removed": "origin/{name} was already removed",
        "remote_none": "no counterpart",
        "age_today": "today", "age_day": "{n} day ago", "age_days": "{n} days ago",
        "confirm_stash": "Unique work: this stash exists nowhere else. A backup will be created before discarding.",
        "confirm_ignored": "This worktree has files ignored by git (e.g. {shown}) that will be deleted with it and have no backup.",
        "confirm_wt_branch": "The branch of this worktree has work that exists only there: it stays. Only the worktree folder is removed.",
        "confirm_wt_detached": "This worktree has no branch and its commits exist only here. A backup will be created before removing.",
        "confirm_p3": "Heuristic: the same patch seems to be in the base, but that is not proof. A backup will be created before deleting.",
        "confirm_p4": "Unique work: these commits do not exist on any other branch, remote or tag. A backup will be created before deleting.",
        "f_proof": "Proof", "f_worktree": "Worktree", "f_branch": "Branch", "f_ignored": "Ignored", "f_last": "Last",
        "f_content": "Content", "f_vs_base": "Vs base", "f_pr": "PR", "f_remote": "Remote", "f_files": "Files",
        "f_only_here": "Only here", "f_effect": "Effect", "f_items": "Items", "f_rule": "Rule", "f_untouched": "Do not touch",
        "wt_text": "`{path}` ({size}, clean)", "branch_goes": " (goes too)", "branch_stays": " (stays)",
        "no_branch": "none (detached HEAD)", "ignored_note": "(deleted with the folder, no backup)", "empty": "empty",
        "vs_base": "{ahead} ahead, {behind} behind",
        "effect_branch": "Deletes the local branch.", "effect_worktree": "Removes the worktree folder.",
        "effect_worktree_branch": "Removes the worktree folder and the branch.", "effect_stash": "Discards the stash.",
        "effect_backup": " First, it saves `{ref}`.",
        "verb_branch": "Delete the branch", "verb_worktree": "Remove the worktree", "verb_stash": "Discard the stash",
        "group_tag": "group P1/P2", "group_title": "Delete the {n} items proven as merged?",
        "group_rule": "Applies to the items below that you do not mark {keep} or {later}. It does not include P3, P4 or stashes.",
        "gh_yes": "yes", "gh_no": "no (git only)", "gh_short_yes": "yes", "gh_short_no": "no",
        "batch_title": "Cleanup of {repo}", "subtitle": "base: {base} - gh: {gh} - {n} items",
    },
    "pt-BR": {
        "proof_P1": "provado: ancestral da base", "proof_P2": "provado: PR mergeado no GitHub",
        "proof_P3": "provável: o mesmo patch já está na base", "proof_P4": "trabalho único: existe só aqui",
        "why_base_branch": "branch base do repositório", "why_current_branch": "branch atual (em uso por este worktree)",
        "why_main_worktree": "em uso pelo worktree principal ({path})", "why_current_worktree": "worktree atual",
        "why_locked": "worktree bloqueado (locked)", "why_missing_dir": "diretório ausente (git worktree prune resolve)",
        "why_unreadable": "não consegui ler o estado do worktree",
        "why_dirty": "{n} arquivo(s) alterado(s) ou não rastreado(s): apagar perderia trabalho sem sha para recuperar",
        "pr_none": "sem PR mergeado", "pr_merged": "#{n} mergeado (a ponta confere)", "pr_differs": "#{n} mergeado (a ponta é DIFERENTE da do PR)",
        "remote_exists": "origin/{name} ainda existe (não será tocada)", "remote_removed": "origin/{name} já foi removida",
        "remote_none": "sem contraparte",
        "age_today": "hoje", "age_day": "há {n} dia", "age_days": "há {n} dias",
        "confirm_stash": "Trabalho único: este stash não existe em outro lugar. Um backup será criado antes de descartar.",
        "confirm_ignored": "Este worktree tem arquivos ignorados pelo git (ex.: {shown}) que serão apagados junto e não têm backup.",
        "confirm_wt_branch": "A branch deste worktree tem trabalho que só existe nela: ela fica. Remove só a pasta do worktree.",
        "confirm_wt_detached": "Este worktree está sem branch e seus commits só existem aqui. Um backup será criado antes de remover.",
        "confirm_p3": "Heurística: o mesmo patch parece estar na base, mas isso não é prova. Um backup será criado antes de apagar.",
        "confirm_p4": "Trabalho único: estes commits não existem em nenhuma outra branch, remoto ou tag. Um backup será criado antes de apagar.",
        "f_proof": "Prova", "f_worktree": "Worktree", "f_branch": "Branch", "f_ignored": "Ignorados", "f_last": "Último",
        "f_content": "Conteúdo", "f_vs_base": "Vs base", "f_pr": "PR", "f_remote": "Remoto", "f_files": "Arquivos",
        "f_only_here": "Só aqui", "f_effect": "Efeito", "f_items": "Itens", "f_rule": "Regra", "f_untouched": "Não tocar",
        "wt_text": "`{path}` ({size}, limpo)", "branch_goes": " (sai junto)", "branch_stays": " (fica)",
        "no_branch": "nenhuma (HEAD solto)", "ignored_note": "(apagados junto com a pasta, sem backup)", "empty": "vazio",
        "vs_base": "{ahead} à frente, {behind} atrás",
        "effect_branch": "Apaga a branch local.", "effect_worktree": "Remove a pasta do worktree.",
        "effect_worktree_branch": "Remove a pasta do worktree e a branch.", "effect_stash": "Descarta o stash.",
        "effect_backup": " Antes, guarda `{ref}`.",
        "verb_branch": "Apagar a branch", "verb_worktree": "Remover o worktree", "verb_stash": "Descartar o stash",
        "group_tag": "grupo P1/P2", "group_title": "Apagar os {n} itens provados como mergeados?",
        "group_rule": "Vale para os itens abaixo em que você não marcar {keep} ou {later}. Não inclui P3, P4 nem stashes.",
        "gh_yes": "sim", "gh_no": "não (só git local)", "gh_short_yes": "sim", "gh_short_no": "não",
        "batch_title": "Limpeza de {repo}", "subtitle": "base: {base} - gh: {gh} - {n} itens",
    },
}
LABELS = {  # the board's own wording per language; "approve" deletes, so it is painted as the dangerous action
    "en": {"approve": {"text": "Delete", "tone": "danger"}, "reject": {"text": "Keep", "tone": "safe"},
           "maybe": {"text": "Later", "tone": "caution"}},
    "pt-BR": {"approve": {"text": "Apagar", "tone": "danger"}, "reject": {"text": "Manter", "tone": "safe"},
              "maybe": {"text": "Depois", "tone": "caution"}},
}


def check_lang(lang):
    """A language is one of LANGS; anything else (a typo, a value edited into a file) is the person's error."""
    if lang not in LANGS:
        raise TidyError(f"idioma invalido: {lang!r} (use en ou pt-BR)")
    return lang


def t(lang, key, **values):
    """One card text in `lang`. The template is ours; the values are data, substituted and never parsed."""
    return TEXT[lang][key].format(**values)


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


def pr_info(prs, name, sha):
    """None when gh was off or unusable; {} when gh knows no merged PR for the branch; else the first PR's number
    and whether its head is the branch tip. Text comes later, from the table (`pr_text`)."""
    if prs is None:
        return None
    found = prs.get(name or "", [])
    if not found:
        return {}
    return {"number": found[0]["number"], "tip_matches": found[0]["oid"] == sha}


def remote_state(root, name, gone):
    """'exists', 'removed' or 'none': the state of origin/<name>, rendered by `remote_text`."""
    if rev(root, "refs/remotes/origin/" + name):
        return "exists"
    return "removed" if gone else "none"


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
            untouched.append({"name": name, "why": "base_branch"})
            continue
        wt = checked_out.get(name)
        if wt:  # a linked worktree carries its branch in its own card
            real = Path(os.path.realpath(wt))
            if real == here:
                untouched.append({"name": name, "why": "current_branch"})
            elif real == main_path:
                untouched.append({"name": name, "why": "main_worktree", "path": wt})
            continue
        proof = classify(root, b["sha"], name, refs, prs)
        ahead, behind = ahead_behind(root, refs[0], b["sha"])
        count, lines = unique_commits(root, b["sha"], name) if proof in RISKY_PROOFS else (0, [])
        items.append({"kind": "branch", "name": name, "sha": b["sha"], "proof": proof, "ts": b["ts"],
                      "author": b["author"], "subject": b["subject"], "ahead": ahead, "behind": behind,
                      "unique": lines, "unique_count": count, "pr": pr_info(prs, name, b["sha"]),
                      "remote": remote_state(root, name, b["gone"]), "backup": proof in RISKY_PROOFS})

    for wt in trees[1:]:
        path = wt["worktree"]
        if "bare" in wt:
            continue
        if Path(os.path.realpath(path)) == here:
            untouched.append({"name": path, "why": "current_worktree"})
            continue
        if "locked" in wt:
            untouched.append({"name": path, "why": "locked"})
            continue
        if "prunable" in wt or not Path(path).is_dir():
            untouched.append({"name": path, "why": "missing_dir"})
            continue
        dirty = dirty_files(path)
        if dirty is None:
            untouched.append({"name": path, "why": "unreadable"})
            continue
        if dirty:
            untouched.append({"name": path, "why": "dirty", "count": len(dirty)})
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
                      "pr": pr_info(prs, branch, sha) if branch else None, "remote": remote_state(root, branch, False) if branch else None,
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
WHY_CODES = ("base_branch", "current_branch", "main_worktree", "current_worktree", "locked", "missing_dir", "unreadable", "dirty")


def short_name(name):
    """A worktree is named by its folder on the card (the full path is in its own field)."""
    return os.path.basename(name.rstrip("/")) if os.path.isabs(name) else name


def safe_text(text):
    """Card text is shown with inline-code markup: a stray backtick would swallow the rest of the line."""
    return str(text).replace("`", "'")


def age_text(ts, now, lang):
    days = int((now - ts) // 86400)
    if days <= 0:
        return t(lang, "age_today")
    return t(lang, "age_day" if days == 1 else "age_days", n=days)


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def reason_text(u, lang):
    """The reason an item is never offered, from its code (see `inventory`)."""
    return t(lang, "why_" + u["why"], path=safe_text(u.get("path", "")), n=u.get("count", 0))


def pr_text(it, lang):
    pr = it.get("pr")
    if pr is None:  # gh off or unusable, or a worktree with no branch
        return ""
    if not pr:
        return t(lang, "pr_none")
    return t(lang, "pr_merged" if pr["tip_matches"] else "pr_differs", n=pr["number"])


def remote_text(it, lang):
    state = it.get("remote")
    if not state:
        return ""
    return t(lang, "remote_" + state, name=safe_text(it.get("branch") or it["name"]))


def backup_name(it):
    if it["kind"] == "stash":
        return BACKUP + "stash-" + it["sha"][:12]
    if it["kind"] == "worktree":
        return BACKUP + "wt-" + it["sha"][:12]
    return BACKUP + it["name"]


def confirm_text(it, lang):
    """The second-press warning of a card that is not provably merged (None for P1 and P2)."""
    if it["kind"] == "stash":
        return t(lang, "confirm_stash")
    if it["kind"] == "worktree" and it.get("ignored"):
        return t(lang, "confirm_ignored", shown=", ".join(safe_text(e) for e in it["ignored"][:3]))
    if it["kind"] == "worktree":
        if it["proof"] in SAFE_PROOFS:
            return None
        return t(lang, "confirm_wt_branch" if it["branch"] else "confirm_wt_detached")
    if it["proof"] == "P3":
        return t(lang, "confirm_p3")
    if it["proof"] == "P4":
        return t(lang, "confirm_p4")
    return None


def card_for(it, iid, now, lang):
    kind, name = it["kind"], it["name"]
    fields = [{"label": t(lang, "f_proof"), "text": f"{it['proof']} - {t(lang, 'proof_' + it['proof'])}"}]
    if kind == "worktree":
        fields.append({"label": t(lang, "f_worktree"), "text": t(lang, "wt_text", path=safe_text(it["path"]), size=human_size(it["size"]))})
        if it["branch"]:
            tail = t(lang, "branch_goes" if it["drop_branch"] else "branch_stays")
            fields.append({"label": t(lang, "f_branch"), "text": f"`{safe_text(it['branch'])}`{tail}"})
        else:
            fields.append({"label": t(lang, "f_branch"), "text": t(lang, "no_branch")})
        if it.get("ignored"):
            body = "\n".join(f"`{safe_text(e)}`" for e in it["ignored"][:5])
            fields.append({"label": t(lang, "f_ignored"), "text": body + "\n" + t(lang, "ignored_note")})
    who = f", {safe_text(it['author'])}" if it["author"] else ""
    fields.append({"label": t(lang, "f_last"), "text": f"{safe_text(it['subject'])} ({age_text(it['ts'], now, lang)}{who})"})
    if kind == "stash":
        fields.append({"label": t(lang, "f_content"), "text": safe_text(it["shortstat"]) or t(lang, "empty")})
    else:
        fields.append({"label": t(lang, "f_vs_base"), "text": t(lang, "vs_base", ahead=it["ahead"], behind=it["behind"])})
        pr = pr_text(it, lang)
        if pr:
            fields.append({"label": t(lang, "f_pr"), "text": pr})
        remote = remote_text(it, lang)
        if remote:
            fields.append({"label": t(lang, "f_remote"), "text": remote})
    if kind == "stash" and it["files"]:
        more = it["file_count"] - len(it["files"])
        body = "\n".join(f"`{safe_text(f)}`" for f in it["files"]) + (f"\n(+{more})" if more > 0 else "")
        fields.append({"label": t(lang, "f_files"), "text": body})
    elif kind != "stash" and it["unique"]:
        more = it["unique_count"] - len(it["unique"])
        body = "\n".join(f"`{safe_text(line)}`" for line in it["unique"]) + (f"\n(+{more})" if more > 0 else "")
        fields.append({"label": t(lang, "f_only_here"), "text": body})
    if kind == "branch":
        effect = t(lang, "effect_branch")
    elif kind == "worktree":
        effect = t(lang, "effect_worktree_branch" if it["drop_branch"] else "effect_worktree")
    else:
        effect = t(lang, "effect_stash")
    if it["backup"]:
        effect += t(lang, "effect_backup", ref=safe_text(backup_name(it)))
    fields.append({"label": t(lang, "f_effect"), "text": effect})
    card = {"id": iid, "tag": it["proof"], "title": f"{t(lang, 'verb_' + kind)} {safe_text(short_name(name))}?", "fields": fields}
    confirm = confirm_text(it, lang)
    if confirm:
        card["confirm"] = confirm
    return card


def build_scan(root, inv, now=None, stamp=None, lang=DEFAULT_LANG):
    """(batch, scan) for an inventory in `lang`, or None when there is nothing to offer."""
    check_lang(lang)
    if not inv["items"]:
        return None
    now = now or time.time()
    stamp = stamp or time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
    repo_name = Path(root).name
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", repo_name).strip("-") or "repo"
    cards, entries, safe_ids, safe_lines = [], [], [], []
    for n, it in enumerate(inv["items"], 1):
        iid = f"T{n:02d}"
        cards.append(card_for(it, iid, now, lang))
        entries.append({"id": iid, "kind": it["kind"], "name": it["name"], "sha": it["sha"], "proof": it["proof"],
                        "branch": it.get("branch"), "path": it.get("path"), "drop_branch": bool(it.get("drop_branch")),
                        "backup": bool(it["backup"])})
        if it["proof"] in SAFE_PROOFS and not it.get("ignored"):  # ignored files need their own confirmation
            safe_ids.append(iid)
            safe_lines.append(f"`{safe_text(short_name(it['name']))}` ({it['kind']}, {it['proof']})")
    group = None
    if len(safe_ids) >= 2:
        labels = LABELS[lang]
        cards.insert(0, {"id": "G", "tag": t(lang, "group_tag"),
                         "title": t(lang, "group_title", n=len(safe_ids)),
                         "fields": [{"label": t(lang, "f_items"), "text": "\n".join(safe_lines)},
                                    {"label": t(lang, "f_rule"), "text": t(lang, "group_rule", keep=labels["reject"]["text"], later=labels["maybe"]["text"])}]})
        group = {"id": "G", "members": safe_ids}
    untouched = [{"name": u["name"], "why": reason_text(u, lang)} for u in inv["untouched"]]
    if untouched:  # a field, not meta: the side panel's key column is too narrow for this label
        lines = "\n".join(f"`{safe_text(short_name(u['name']))}`: {u['why']}" for u in untouched)
        cards[0]["fields"].append({"label": t(lang, "f_untouched"), "text": lines})
    cards[0]["meta"] = {"Base": inv["base"], "gh": t(lang, "gh_yes" if inv["gh"] else "gh_no")}
    batch = {"batch_id": f"tidy-{slug}-{stamp}", "title": t(lang, "batch_title", repo=repo_name),
             "subtitle": t(lang, "subtitle", base=inv["base"], gh=t(lang, "gh_short_yes" if inv["gh"] else "gh_short_no"), n=len(inv["items"])),
             "round": 1, "lang": lang, "labels": LABELS[lang], "items": cards}
    scan = {"version": VERSION, "repo": str(root), "base": inv["base"], "base_sha": inv["base_sha"], "gh": inv["gh"], "lang": lang,
            "scanned_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(now)), "group": group,
            "untouched": untouched, "items": entries}
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
    if scan.get("lang") is not None and scan["lang"] not in LANGS:  # an older scan has no lang: that is English
        errs.append("scan.json: 'lang' deve ser en ou pt-BR")
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
    built = build_scan(root, inv, lang=a.lang)
    for u in inv["untouched"]:  # transient: Task 4b moves every line of the command line to its own table
        print(f"NAO TOCAR: {u['name']} ({reason_text(u, 'pt-BR')})")
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
    print(f"TIDY-BOARD ITENS: {len(scan['items'])} ({counts}); base {base}; gh {'sim' if scan['gh'] else 'nao'}; idioma {a.lang}")
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
    s.add_argument("--lang", choices=LANGS, default=DEFAULT_LANG, help="idioma dos cards: en (padrao) ou pt-BR")
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

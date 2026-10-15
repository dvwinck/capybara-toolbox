#!/usr/bin/env python3
# publish-check 0.1.1 - read-only scan of a git repository for leaks before it goes public
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Diogo Winck
"""publish-check: read-only scan of a git repository, working tree and full history, for things
that should not become public.

Categories: session-link (claude.ai conversation links), home-path (/Users/<name>, /home/<name>,
C:\\Users\\<name>), email (addresses in text and in author/committer fields) and denylist (internal
names you list in .publish-check.json). Secrets are out of scope on purpose: use a secret scanner.

It never writes to the repository and never rewrites history. Python 3.9+ standard library and
the `git` command only; no network.

Usage:
  python3 -I publish_check.py [PATH] [--json] [--config FILE] [--denylist FILE]
                              [--since WHEN] [--max-commits N]

Exit codes: 0 clean, 1 findings, 2 error.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import namedtuple
from pathlib import Path

VERSION = "0.1.1"
SCHEMA = 1
CONFIG_NAME = ".publish-check.json"
MAX_FILE_BYTES = 50_000_000  # larger text files are not read; they are counted as skipped, never silently ignored
CATEGORIES = ("session-link", "home-path", "email", "denylist")

SESSION_LINK = re.compile(r"https?://claude\.ai/(?:code/session|chat|share)[^\s)>\]\"'`]*")
HOME_PATH = re.compile(r"(?:/Users/|/home/|[A-Za-z]:[\\/]+(?i:users)[\\/]+)([A-Za-z0-9._-]+)")
LOCAL_TAIL = re.compile(r"[A-Za-z0-9._%+-]+$")
DOMAIN_HEAD = re.compile(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
CONTROL = re.compile(r"[\x00-\x08\x0a-\x1f\x7f-\x9f]")

# Generic values that are never a leak: placeholders, CI users, noreply addresses.
BENIGN_HOME_NAMES = {"shared", "runner", "user", "username", "you", "name", "me", "example",
                     "yourname", "your-name", "root", "ubuntu", "vagrant", "public", "default"}
BENIGN_EMAILS = {"noreply@anthropic.com", "noreply@github.com", "support@github.com"}
BENIGN_EMAIL_DOMAINS = {"example.com", "example.org", "example.net", "example.invalid",
                        "users.noreply.github.com", "noreply.github.com"}

# Every git call: read-only, and deaf to what the scanned repository's own config asks git to run
# (core.fsmonitor makes `git ls-files --others` execute a program named in .git/config).
GIT_FLAGS = ["--no-optional-locks", "-c", "core.quotepath=off", "-c", "core.fsmonitor=false",
             "-c", "protocol.allow=never", "-c", "log.showSignature=false", "-c", "log.showRoot=true",
             "-c", "i18n.logOutputEncoding=UTF-8"]
# Also: no lazy fetch of missing objects (a partial clone would reach the network and run
# core.sshCommand), no replace refs and no grafts (they can hide history), no prompts.
GIT_ENV = {"GIT_NO_LAZY_FETCH": "1", "GIT_NO_REPLACE_OBJECTS": "1", "GIT_GRAFT_FILE": os.devnull,
           "GIT_TERMINAL_PROMPT": "0"}

Match = namedtuple("Match", "category start end value")


class ScanError(Exception):
    """A problem the user must fix (bad config, not a git repository, git missing)."""


# ---------------------------------------------------------------- detection

def email_matches(text):
    """E-mail addresses, found from each '@' outwards with bounded windows, so the cost stays linear
    even for megabyte-long minified lines (a plain regex over such a line is quadratic)."""
    out, at = [], text.find("@")
    while at != -1:
        left = LOCAL_TAIL.search(text[max(0, at - 64):at])
        right = DOMAIN_HEAD.match(text[at + 1:at + 256])
        if left and right:
            start = at - len(left.group(0))
            out.append(Match("email", start, at + 1 + right.end(), text[start:at + 1 + right.end()]))
        at = text.find("@", at + 1)
    return out


def find_matches(text, denylist=()):
    """Every leak candidate in one piece of text, sorted, without overlaps."""
    found = [Match("session-link", m.start(), m.end(), m.group(0)) for m in SESSION_LINK.finditer(text)]
    for m in HOME_PATH.finditer(text):
        if m.group(1).lower() not in BENIGN_HOME_NAMES:
            found.append(Match("home-path", m.start(), m.end(), m.group(0)))
    for m in email_matches(text):
        addr = m.value.lower()
        if addr not in BENIGN_EMAILS and addr.rsplit("@", 1)[1] not in BENIGN_EMAIL_DOMAINS:
            found.append(m)
    for term in denylist:
        for m in re.finditer(re.escape(term), text, re.I):
            found.append(Match("denylist", m.start(), m.end(), m.group(0)))
    found.sort(key=lambda x: (x.start, -(x.end - x.start)))
    kept, cursor = [], 0
    for m in found:
        if m.start >= cursor:
            kept.append(m)
            cursor = m.end
    return kept


def mask(category, value):
    """Partly hide a value so the report itself does not leak what it finds."""
    if category == "session-link":
        m = re.match(r"https?://claude\.ai/(?:code/session|chat|share)", value)
        return (m.group(0) if m else value[:12]) + "/***"
    if category == "home-path":
        return HOME_PATH.sub(lambda m: m.group(0)[:m.start(1) - m.start(0)] + "***", value)
    if category == "email":
        local, domain = value.rsplit("@", 1)
        return local[:1] + "***@" + domain
    return value[:1] + "***"


def fingerprint(category, where, origin, value):
    """Stable id of one finding: category, kind of place, file (when there is one) and the value.

    The commit id is deliberately not part of it: an address that appears in the author field of
    every commit must be acceptable once, not once per commit (and not again for each new commit)."""
    key = "|".join((category, where, origin, value.lower()))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def masked_view(line, matches):
    """The line with every match masked, and where each masked value starts in it."""
    out, offsets, cursor = [], [], 0
    pos = 0
    for m in matches:
        out.append(line[cursor:m.start])
        pos += m.start - cursor
        masked = mask(m.category, m.value)
        offsets.append((pos, len(masked)))
        out.append(masked)
        pos += len(masked)
        cursor = m.end
    out.append(line[cursor:])
    return "".join(out), offsets


def printable(text):
    """Untrusted repository text must not carry terminal escape sequences into the report."""
    return CONTROL.sub("?", text.replace("\t", " "))


def window(masked_line, start, length, width=40):
    left = max(0, start - width)
    right = min(len(masked_line), start + length + width)
    text = masked_line[left:right].strip()
    return ("..." if left > 0 else "") + text + ("..." if right < len(masked_line) else "")


def findings_in_text(text, denylist, where, origin, locate):
    """Yield one finding dict per match. `locate(line_number)` names the place for the report."""
    for number, line in enumerate(text.splitlines(), 1):
        matches = find_matches(line, denylist)
        if not matches:
            continue
        masked_line, offsets = masked_view(line, matches)
        for m, (start, length) in zip(matches, offsets):
            yield {
                "category": m.category,
                "where": where,
                "location": printable(locate(number)),
                "snippet": printable(window(masked_line, start, length)),
                "fingerprint": fingerprint(m.category, where, origin, m.value),
            }


# ---------------------------------------------------------------- git scanning

def git(root, *args):
    try:
        return subprocess.run(["git", *GIT_FLAGS, "-C", str(root), *args], capture_output=True, check=False,
                              env={**os.environ, **GIT_ENV})
    except FileNotFoundError:
        raise ScanError("git was not found on PATH")


def git_checked(root, *args):
    """git, but a failing command is an error: a scan that silently saw nothing would read as 'clean'."""
    r = git(root, *args)
    if r.returncode != 0:
        detail = r.stderr.decode("utf-8", "replace").strip().splitlines()
        raise ScanError(f"git {args[0]} failed ({detail[-1] if detail else 'exit ' + str(r.returncode)})")
    return r


def repo_root(path):
    r = git(path, "rev-parse", "--show-toplevel")
    if r.returncode != 0:
        raise ScanError(f"{path} is not inside a git repository")
    return Path(r.stdout.decode("utf-8", "replace").strip())


def is_shallow(root):
    """True for a shallow clone: its history is incomplete, so a clean scan proves little."""
    r = git(root, "rev-parse", "--is-shallow-repository")
    return r.returncode == 0 and r.stdout.decode("utf-8", "replace").strip() == "true"


def is_partial(root):
    """True for a partial (promisor) clone: blobs missing locally are never fetched by this tool."""
    r = git(root, "config", "--get-regexp", r"^(extensions\.partialclone|remote\..*\.promisor)$")
    return r.returncode == 0 and bool(r.stdout.strip())


def history_args(since, max_commits):
    """Every ref except the stash (it is not pushed); the stash is itself a merge commit."""
    args = ["--exclude=refs/stash", "--all"]
    if since:
        args.append(f"--since={since}")
    if max_commits:
        args += ["-n", str(max_commits)]
    return args


def scan_tree(root, denylist, stats):
    """Tracked and untracked-but-not-ignored text files of the working tree."""
    r = git_checked(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    for rel in r.stdout.decode("utf-8", "replace").split("\0"):
        if not rel:
            continue
        path = root / rel
        yield from findings_in_text(rel, denylist, "path", rel, lambda n, rel=rel: rel)
        if path.is_symlink() or not path.is_file():
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                stats["skipped"] += 1
                continue
            data = path.read_bytes()
        except OSError:
            stats["skipped"] += 1
            continue
        if b"\0" in data[:8192]:
            stats["skipped"] += 1  # binary
            continue
        stats["files"] += 1
        yield from findings_in_text(data.decode("utf-8", "replace"), denylist, "tree", rel,
                                    lambda n, rel=rel: f"{rel}:{n}")


def scan_commit_metadata(root, denylist, since, max_commits, stats):
    """One NUL-terminated record of six NUL-separated fields per commit; git cannot put NUL in any of them."""
    fmt = "--format=%H%x00%an%x00%ae%x00%cn%x00%ce%x00%B"
    r = git_checked(root, "log", "--no-color", "-z", fmt, *history_args(since, max_commits))
    fields = r.stdout.decode("utf-8", "replace").split("\0")
    if fields and fields[-1] == "":
        fields.pop()
    if len(fields) % 6:
        raise ScanError("unexpected git log output (commit fields were not in groups of six)")
    for k in range(0, len(fields), 6):
        sha, an, ae, cn, ce, body = (x.strip("\n") if n == 0 else x for n, x in enumerate(fields[k:k + 6]))
        stats["commits"] += 1
        short = sha[:7]
        who = [("commit-author", "author", f"{an} <{ae}>")]
        if (cn, ce) != (an, ae):
            who.append(("commit-committer", "committer", f"{cn} <{ce}>"))
        for where, label, text in who:
            yield from findings_in_text(text, denylist, where, "", lambda n, s=short, l=label: f"{s} {l}")
        yield from findings_in_text(body, denylist, "commit-message", "",
                                    lambda n, s=short: f"{s} message line {n}")


def scan_patches(root, denylist, since, max_commits):
    """Added lines of every patch on every ref (removed lines were added by an earlier commit).

    The body of each hunk is consumed by the line counts in its `@@` header, so a content line that
    merely looks like a header ("+++ ...", "@@ ...") is scanned as content, never mistaken for one."""
    # --text: files marked binary/-diff in .gitattributes are scanned too; --root: the first commit's patch;
    # --diff-merges=first-parent: what a merge commit itself changed (resolutions, files added in the merge).
    cmd = ["git", *GIT_FLAGS, "-C", str(root), "log", "-p", "-U0", "--no-color", "--text", "--root",
           "--diff-merges=first-parent", "--no-ext-diff", "--no-textconv", "--format=%x1e%H",
           *history_args(since, max_commits)]
    with tempfile.TemporaryFile() as errors:
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=errors, env={**os.environ, **GIT_ENV})
        except FileNotFoundError:
            raise ScanError("git was not found on PATH")
        sha = path = ""
        number = old_left = new_left = 0
        with proc:
            for raw in proc.stdout:
                line = raw.decode("utf-8", "replace").rstrip("\n")
                if old_left or new_left:  # inside a hunk body
                    if line.startswith("+") and new_left:
                        new_left -= 1
                        for f in findings_in_text(line[1:], denylist, "patch", path,
                                                  lambda n, s=sha[:7], p=path, at=number: f"{s} {p}:{at}"):
                            yield f
                        number += 1
                    elif line.startswith("-") and old_left:
                        old_left -= 1
                    # "\ No newline at end of file" and anything else inside a hunk is ignored
                    continue
                if line.startswith("\x1e"):
                    sha, path = line[1:].strip(), ""
                elif line.startswith("diff --git "):
                    path = line.rsplit(" b/", 1)[-1]
                    yield from findings_in_text(path, denylist, "path", path,
                                                lambda n, s=sha[:7], p=path: f"{s} {p}")
                elif line.startswith("+++ "):
                    target = line[4:].rstrip("\t")
                    if target != "/dev/null":
                        path = target[2:] if target.startswith("b/") else target
                elif line.startswith("@@"):
                    m = re.match(r"@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
                    if m:
                        old_left = int(m.group(1)) if m.group(1) is not None else 1
                        number = int(m.group(2))
                        new_left = int(m.group(3)) if m.group(3) is not None else 1
        if proc.returncode != 0:
            errors.seek(0)
            detail = errors.read().decode("utf-8", "replace").strip().splitlines()
            raise ScanError(f"git log -p failed ({detail[-1] if detail else 'exit ' + str(proc.returncode)})")


def scan_tags(root, denylist):
    fmt = "--format=%(refname:short)%1f%(objecttype)%1f%(taggername)%1f%(taggeremail)%1f%(contents)%1e"
    r = git_checked(root, "for-each-ref", fmt, "refs/tags")
    for rec in r.stdout.decode("utf-8", "replace").split("\x1e"):
        if not rec.strip():
            continue
        name, kind, tagger, email, contents = rec.strip("\n").split("\x1f", 4)
        if kind != "tag":
            continue
        text = f"{tagger} {email}\n{contents}"
        yield from findings_in_text(text, denylist, "tag", name, lambda n, name=name: f"tag {name}")


def scan_refs(root, denylist):
    """Branch and tag names can carry client names or addresses too."""
    r = git_checked(root, "for-each-ref", "--format=%(refname)")
    for name in r.stdout.decode("utf-8", "replace").splitlines():
        yield from findings_in_text(name, denylist, "ref", name, lambda n, name=name: f"ref {name}")


def scan(root, denylist, since=None, max_commits=None):
    """Return (findings, stats) for a repository root."""
    stats = {"files": 0, "commits": 0, "skipped": 0}
    findings = list(scan_tree(root, denylist, stats))
    findings += scan_commit_metadata(root, denylist, since, max_commits, stats)
    findings += scan_patches(root, denylist, since, max_commits)
    findings += scan_tags(root, denylist)
    findings += scan_refs(root, denylist)
    return findings, stats


# ---------------------------------------------------------------- configuration

def load_config(path):
    """(denylist, allow) from a .publish-check.json file."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as e:
        raise ScanError(f"cannot read config {path}: {e.strerror}")
    except ValueError as e:
        raise ScanError(f"config {path} is not valid JSON: {e}")
    if not isinstance(data, dict):
        raise ScanError(f"config {path} must be a JSON object")
    unknown = sorted(set(data) - {"denylist", "allow"})
    if unknown:
        raise ScanError(f"config {path}: unknown keys {', '.join(unknown)}")
    for key in ("denylist", "allow"):
        value = data.get(key, [])
        if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
            raise ScanError(f"config {path}: '{key}' must be a list of strings")
    return list(data.get("denylist", [])), list(data.get("allow", []))


def read_denylist_file(path):
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError as e:
        raise ScanError(f"cannot read denylist {path}: {e.strerror}")
    return [x.strip() for x in lines if x.strip() and not x.strip().startswith("#")]


# ---------------------------------------------------------------- report

def build_report(root, findings, stats, allowed, shallow=False, partial=False, limits=None):
    counts = {c: 0 for c in CATEGORIES}
    for f in findings:
        counts[f["category"]] += 1
    return {
        "schema": SCHEMA,
        "tool": "publish-check",
        "version": VERSION,
        "path": str(root),
        "scanned": {"files": stats["files"], "commits": stats["commits"], "skipped": stats["skipped"]},
        "clean": not findings,
        "counts": counts,
        "allowed": allowed,
        "shallow": shallow,
        "partial": partial,
        "limits": limits or {"since": None, "max_commits": None},
        "findings": findings,
    }


def render_text(report):
    lines = [f"publish-check {VERSION}: scanned {report['scanned']['files']} files and "
             f"{report['scanned']['commits']} commits in {report['path']}"]
    if report["clean"]:
        lines.append("clean: no findings")
    else:
        total = len(report["findings"])
        lines.append(f"{total} finding{'s' if total != 1 else ''}")
        for category in CATEGORIES:
            group = [f for f in report["findings"] if f["category"] == category]
            if not group:
                continue
            lines.append("")
            lines.append(f"[{category}] {len(group)}")
            for f in group:
                lines.append(f"  {f['where']}: {f['location']}")
                lines.append(f"    {f['snippet']}")
                lines.append(f"    fingerprint: {f['fingerprint']}")
    skipped = report["scanned"]["skipped"]
    if skipped:
        lines.append(f"{skipped} file{'s' if skipped != 1 else ''} skipped (binary, unreadable or larger than "
                     f"{MAX_FILE_BYTES // 1_000_000} MB): not scanned")
    if report["allowed"]:
        lines.append(f"({report['allowed']} accepted by the allow list)")
    limits = report["limits"]
    if limits["since"] or limits["max_commits"]:
        parts = [f"--since {limits['since']}" if limits["since"] else "",
                 f"--max-commits {limits['max_commits']}" if limits["max_commits"] else ""]
        lines.append("note: history limited (" + ", ".join(p for p in parts if p) + "): older commits were not scanned.")
        if report["scanned"]["commits"] == 0:
            lines.append("note: no commits were scanned; check the --since value.")
    if report["partial"]:
        lines.append("warning: this is a partial clone; blobs that are not stored locally are never fetched, so the "
                     "scan stops with an error if it needs one.")
    if report["shallow"]:
        lines.append("warning: this is a shallow clone, so only part of the history was scanned; "
                     "fetch the full history (git fetch --unshallow) for a complete scan.")
    lines.append("")
    lines.append("Secrets are not scanned; use a secret scanner such as gitleaks for those.")
    if not report["clean"]:
        lines.append("This tool is read-only and never rewrites history. To remove a finding from "
                     "history, see the plugin's docs/remediation.md (back up first).")
        lines.append("To accept a finding, add its fingerprint to \"allow\" in " + CONFIG_NAME + ".")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- command line

def positive_int(text):
    n = int(text)
    if n < 1:
        raise argparse.ArgumentTypeError("must be 1 or more")
    return n


def parser():
    p = argparse.ArgumentParser(prog="publish_check.py", description=__doc__.split("\n")[0])
    p.add_argument("path", nargs="?", default=".", help="repository to scan (default: current directory)")
    p.add_argument("--json", action="store_true", help="print the report as JSON")
    p.add_argument("--config", help=f"config file (default: <repository>/{CONFIG_NAME} when present)")
    p.add_argument("--denylist", action="append", default=[], metavar="FILE",
                   help="file with one internal name per line (repeatable; keep it outside the repository)")
    p.add_argument("--since", help="only scan commits newer than this (any date git accepts)")
    p.add_argument("--max-commits", type=positive_int, help="only scan the newest N commits")
    p.add_argument("--version", action="version", version=f"publish-check {VERSION}")
    return p


def run(args):
    root = repo_root(args.path)
    config_path = Path(args.config) if args.config else root / CONFIG_NAME
    denylist, allow = [], []
    if args.config or config_path.is_file():
        denylist, allow = load_config(config_path)
    for extra in args.denylist:
        denylist += read_denylist_file(extra)
    findings, stats = scan(root, denylist, args.since, args.max_commits)
    allow_set = set(allow)
    kept = [f for f in findings if f["fingerprint"] not in allow_set]
    limits = {"since": args.since, "max_commits": args.max_commits}
    return build_report(root, kept, stats, len(findings) - len(kept), is_shallow(root), is_partial(root), limits)


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        report = run(args)
    except ScanError as e:
        print(f"publish-check: error: {e}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n" if args.json else render_text(report))
    return 0 if report["clean"] else 1


if __name__ == "__main__":
    sys.exit(main())

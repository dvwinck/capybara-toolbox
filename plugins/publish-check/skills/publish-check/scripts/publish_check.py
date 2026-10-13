#!/usr/bin/env python3
# publish-check 0.1.0 - read-only scan of a git repository for leaks before it goes public
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
import re
import subprocess
import sys
import tempfile
from collections import namedtuple
from pathlib import Path

VERSION = "0.1.0"
SCHEMA = 1
CONFIG_NAME = ".publish-check.json"
MAX_FILE_BYTES = 50_000_000  # larger text files are not read; they are counted as skipped, never silently ignored
CATEGORIES = ("session-link", "home-path", "email", "denylist")

SESSION_LINK = re.compile(r"https?://claude\.ai/(?:code/session|chat|share)[^\s)>\]\"'`]*")
HOME_PATH = re.compile(r"(?:/Users/|/home/|[A-Za-z]:[\\/]Users[\\/])([A-Za-z0-9._-]+)")
LOCAL_TAIL = re.compile(r"[A-Za-z0-9._%+-]+$")
DOMAIN_HEAD = re.compile(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
CONTROL = re.compile(r"[\x00-\x08\x0a-\x1f\x7f-\x9f]")

# Generic values that are never a leak: placeholders, CI users, noreply addresses.
BENIGN_HOME_NAMES = {"shared", "runner", "user", "username", "you", "name", "me", "example",
                     "yourname", "your-name", "root", "ubuntu", "vagrant"}
BENIGN_EMAILS = {"noreply@anthropic.com", "noreply@github.com", "support@github.com"}
BENIGN_EMAIL_DOMAINS = {"example.com", "example.org", "example.net", "example.invalid",
                        "users.noreply.github.com", "noreply.github.com"}

# Every git call: read-only, and deaf to what the scanned repository's own config asks git to run
# (core.fsmonitor makes `git ls-files --others` execute a program named in .git/config).
GIT_FLAGS = ["--no-optional-locks", "-c", "core.quotepath=off", "-c", "core.fsmonitor=false"]

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

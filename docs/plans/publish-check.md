# publish-check Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `publish-check`, the second plugin of the Capybara Toolbox: a read-only scan of a git repository (working tree and full history) for Claude conversation links, home paths, e-mail addresses and an owner-supplied denylist, shipped as a CLI plus an agent-facing skill.

**Architecture:** One stdlib-only script, `plugins/publish-check/skills/publish-check/scripts/publish_check.py`, in four layers: detection of leaks in a piece of text, scanning of git data (working tree, commit metadata, patches, tags), configuration (`.publish-check.json`, denylist file, allow list by fingerprint) and a report/CLI layer. It never writes to the scanned repository. The plugin is self-contained (own tests, sync tool, changelog, READMEs) and is registered in the marketplace catalog; CI discovers every plugin's suite by glob.

**Tech Stack:** Python 3.9+ standard library, the `git` command, `unittest`, GitHub Actions.

**Spec:** [docs/refinements/publish-check.md](../refinements/publish-check.md) (scope closed on 2026-10-12). Rulings taken while planning are listed in "Rulings" below; they amend that document.

## Global Constraints

- Python **3.9+**, standard library only; the `git` command is the only external dependency; no network.
- Read-only: the scanner never writes to, fetches into or rewrites the scanned repository.
- Exit codes: `0` clean, `1` findings, `2` error. The JSON report carries `"schema": 1`.
- The version single source is `VERSION` in the script; `tools/sync.py` propagates it to `plugin.json`, and a `## [X.Y.Z]` CHANGELOG entry plus the `# publish-check X.Y.Z - ` header comment are required.
- Fixture leaks in tests are assembled at run time (string concatenation) so that scanning this repository does not flag the tests.
- Git workflow of this machine: cut `feat/publish-check` from `base`, merge back into `base` locally when done; **no push and no PR unless the owner asks**. Commit messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` and must **not** contain a `Claude-Session:` line or any claude.ai session link.
- Docs are English with a Portuguese counterpart; the skill itself is Portuguese; in-page UI conventions do not apply (no UI).

## Rulings (decisions taken while planning, with evidence)

- **Fingerprint excludes the commit id.** The refinement said "category + commit + snippet". A real scan of this toolbox gave 29 findings with 27 distinct fingerprints for one intended public e-mail, and every future commit would add another. The fingerprint is now category, kind of place, file (when there is one) and the value; the same author in a hundred commits is accepted once, a new value or a new file is a new finding.
- **Shallow clones are reported** (`"shallow": true` and a warning line). A default CI checkout has one commit, so a "clean" result would be false assurance.
- **A failing git command is exit 2**, never a silent "clean"; files that cannot be scanned (binary, unreadable, over 50 MB) are counted in the report.
- **Hardening against hostile repositories** (found by testing, see Review Focus): git runs with `core.fsmonitor` disabled and `--no-optional-locks`; e-mail matching is linear-time; patch hunks are consumed by their line counts; commit fields are NUL-delimited; control characters are neutralised in snippets and locations.
- **Masked home paths show only the prefix** (`/Users/***`), because a masked form such as a one-letter name looks like a real path and the scanner would flag its own documentation.
- Catalog and CI changes come first (Tasks 1-2) so the repository-level suite is green at every commit.

## Review Focus

Failure modes the spec implies but a straightforward implementation misses. Each one has a test in the task that owns the code.

1. **Hostile `.git/config`** (`core.fsmonitor`) makes `git ls-files --others` execute a program: Task 4, `test_a_hostile_repository_config_cannot_run_programs`.
2. **Quadratic e-mail regex** hangs on a minified line of a few hundred KB: Task 3, `EmailRobustnessTest`.
3. **Content that looks like a diff header** (`+++ ...` added as a line) used to be skipped, hiding a leak: Task 4, `test_added_lines_that_look_like_diff_headers_are_still_scanned`.
4. **git failure or shallow clone read as "clean"**: Task 4 (`test_a_git_failure_is_an_error_not_a_clean_scan`, `test_a_shallow_clone_is_detected`) and Task 6 (`test_a_shallow_clone_is_reported_as_incomplete`).
5. **Terminal escape sequences in repository text** reaching the report: Task 3, `test_control_characters_cannot_reach_the_terminal`.

## File Structure

```text
plugins/publish-check/
├── .claude-plugin/plugin.json
├── skills/publish-check/
│   ├── SKILL.md
│   └── scripts/publish_check.py        # the whole product
├── tests/                              # helpers.py, test_detect/scan/config/run/cli/package.py
├── tools/sync.py                       # version -> plugin.json; header comment and CHANGELOG checks
├── examples/                           # pre-push.sh, ci-step.yml
├── docs/remediation.md
├── README.md, README.pt-BR.md, CHANGELOG.md
```

Repository-level edits: `.claude-plugin/marketplace.json`, `.github/workflows/ci.yml`, `tests/test_marketplace.py`, `README.md`, `README.pt-BR.md`, `CONTRIBUTING.md`, `CLAUDE.md`.

Commands used throughout (from the repository root):

```bash
PLUGIN_TESTS="python3 -m unittest discover -s plugins/publish-check/tests"
ROOT_TESTS="python3 -m unittest discover -s tests"
```

---

## Task 0: Branch

- [ ] **Step 1: Cut the branch from `base`**

```bash
git checkout base && git pull --ff-only && git checkout -b feat/publish-check
```

Expected: on branch `feat/publish-check`, clean tree.

---


### Task 1: Plugin skeleton and catalog entry

**Files:**
- Create: `plugins/publish-check/skills/publish-check/scripts/publish_check.py` (header and `VERSION` only for now)
- Create: `plugins/publish-check/.claude-plugin/plugin.json`, `plugins/publish-check/CHANGELOG.md`, `plugins/publish-check/tools/sync.py`
- Create: `plugins/publish-check/tests/helpers.py`, `plugins/publish-check/tests/test_package.py` (first half)
- Modify: `.claude-plugin/marketplace.json`, `tests/test_marketplace.py`

**Interfaces:**
- Produces: `helpers.py` exports `ROOT`, `REPO`, `SKILL_DIR`, `SCRIPT`, `LEAK_LINK`, `LEAK_PATH`, `LEAK_EMAIL`, `LEAK_TERM`, `pc` (the loaded script module), `load_sync()`, `git(repo, *args, author=..., committer=..., date=None)`, `init_repo(path)` and `commit(repo, message, files=None, remove=(), author=..., committer=..., date=None)` (returns the commit sha). `sync.py` exports `INPUTS`, `SCRIPT`, `PLUGIN`, `CHANGELOG`, `build(root)`, `problems(root)`, `main(argv, root=ROOT)`, `script_version(text)`.

- [ ] **Step 1: Write the failing tests**


Create `plugins/publish-check/tests/helpers.py`:

````python
import sys

sys.dont_write_bytecode = True  # never leave __pycache__ inside the plugin (it would ship with it)

import importlib.util
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the plugin directory (plugins/publish-check)
REPO = ROOT.parent.parent  # the marketplace repository root
SKILL_DIR = ROOT / "skills" / "publish-check"
SCRIPT = SKILL_DIR / "scripts" / "publish_check.py"

# Fixture leaks are assembled at run time so that scanning this very repository does not flag the tests.
LEAK_LINK = "https://claude." + "ai/code/session_FIXTURE123"
LEAK_PATH = "/Users/" + "fixtureuser"
LEAK_EMAIL = "fixture.person@" + "acme-fixture.dev"
LEAK_TERM = "Project-" + "Zephyr"


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pc = load_module(SCRIPT, "publish_check")


def load_sync():
    return load_module(ROOT / "tools" / "sync.py", "publish_check_sync")


def _env(author=("Alice Example", "alice@example.com"), committer=None, date=None):
    committer = committer or author
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_AUTHOR_NAME=author[0],
        GIT_AUTHOR_EMAIL=author[1],
        GIT_COMMITTER_NAME=committer[0],
        GIT_COMMITTER_EMAIL=committer[1],
    )
    if date:
        env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
    return env


def git(repo, *args, author=("Alice Example", "alice@example.com"), committer=None, date=None):
    r = subprocess.run(["git", "-C", str(repo), "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", *args],
                       env=_env(author, committer, date), capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {r.stderr}")
    return r.stdout


def init_repo(path):
    Path(path).mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    return Path(path)


def commit(repo, message, files=None, remove=(), author=("Alice Example", "alice@example.com"), committer=None,
           date=None):
    for rel, text in (files or {}).items():
        target = Path(repo) / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        git(repo, "add", "--", rel)
    for rel in remove:
        git(repo, "rm", "-q", "--", rel)
    git(repo, "commit", "-q", "--allow-empty", "-m", message, author=author, committer=committer, date=date)
    return git(repo, "rev-parse", "HEAD").strip()
````



Create `plugins/publish-check/tests/test_package.py` (the remaining classes are added in Task 7):

````python
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import LEAK_EMAIL, REPO, ROOT, SCRIPT, commit, init_repo, load_sync

sync = load_sync()


def run_sync(argv, root):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = sync.main(argv, root=Path(root))
    return rc, out.getvalue()


def copy_plugin(dest):
    for rel in sync.INPUTS:
        (Path(dest) / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, Path(dest) / rel)


class RepositoryStateTest(unittest.TestCase):
    def test_plugin_is_in_sync(self):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "sync.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_manifest_version_matches_script(self):
        script = (ROOT / sync.SCRIPT).read_text(encoding="utf-8")
        manifest = json.loads((ROOT / sync.PLUGIN).read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], sync.script_version(script))

    def test_script_carries_its_license(self):
        head = SCRIPT.read_text(encoding="utf-8").splitlines()[:6]
        self.assertTrue(head[1].startswith("# publish-check "), head[1])
        self.assertIn("# SPDX-License-Identifier: MIT", head)
        self.assertIn("# Copyright (c) 2026 Diogo Winck", head)

    def test_manifest_points_to_the_repository(self):
        manifest = json.loads((ROOT / sync.PLUGIN).read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "publish-check")
        self.assertEqual(manifest["homepage"], "https://github.com/dvwinck/capybara-toolbox")
        self.assertEqual(manifest["repository"], "https://github.com/dvwinck/capybara-toolbox")


class SyncToolTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        copy_plugin(self.tmp)

    def test_manifest_drift_is_detected_and_fixed(self):
        manifest = self.tmp / sync.PLUGIN
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["version"] = "9.9.9"
        manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        self.assertEqual(run_sync(["--check"], self.tmp)[0], 1)
        self.assertEqual(run_sync([], self.tmp)[0], 0)
        self.assertEqual(run_sync(["--check"], self.tmp)[0], 0)
        self.assertNotEqual(json.loads(manifest.read_text(encoding="utf-8"))["version"], "9.9.9")

    def test_version_bump_propagates_and_requires_a_changelog_entry(self):
        script = self.tmp / sync.SCRIPT
        text = script.read_text(encoding="utf-8")
        text = re.sub(r"^# publish-check \d+\.\d+\.\d+ - ", "# publish-check 9.9.9 - ", text, flags=re.M)
        text = re.sub(r'^VERSION = "\d+\.\d+\.\d+"', 'VERSION = "9.9.9"', text, flags=re.M)
        script.write_text(text, encoding="utf-8")
        rc, out = run_sync([], self.tmp)
        self.assertEqual(rc, 1)  # CHANGELOG has no 9.9.9 entry
        self.assertIn("CHANGELOG.md", out)
        self.assertEqual(json.loads((self.tmp / sync.PLUGIN).read_text(encoding="utf-8"))["version"], "9.9.9")
        changelog = self.tmp / sync.CHANGELOG
        changelog.write_text("## [9.9.9] - 2099-01-01\n" + changelog.read_text(encoding="utf-8"), encoding="utf-8")
        self.assertEqual(run_sync(["--check"], self.tmp)[0], 0)

    def test_stale_header_comment_is_reported(self):
        script = self.tmp / sync.SCRIPT
        text = script.read_text(encoding="utf-8")
        script.write_text(re.sub(r"^# publish-check \d+\.\d+\.\d+ - ", "# publish-check 0.0.1 - ", text, flags=re.M),
                          encoding="utf-8")
        rc, out = run_sync(["--check"], self.tmp)
        self.assertEqual(rc, 1)
        self.assertIn("header comment", out)


if __name__ == "__main__":
    unittest.main()
````



In `tests/test_marketplace.py`, replace:

````
    def test_catalog_has_no_unverifiable_fields(self):
````

with:

````
    def test_catalog_lists_every_plugin(self):
        market = json.loads((REPO / tool.MARKET).read_text(encoding="utf-8"))
        names = [p["name"] for p in market["plugins"]]
        self.assertEqual(names, ["ar-board", "publish-check"])

    def test_catalog_has_no_unverifiable_fields(self):
````


- [ ] **Step 2: Run the tests to verify they fail**

```bash
$PLUGIN_TESTS
$ROOT_TESTS
```

Expected: the plugin suite fails at import with `FileNotFoundError` for `publish_check.py`; the root suite fails with `AssertionError: Lists differ: ['ar-board'] != ['ar-board', 'publish-check']` and in `test_catalog_is_in_sync` (the new plugin directory is not in the catalog yet).

- [ ] **Step 3: Create the skeleton and register the plugin**


Create `plugins/publish-check/skills/publish-check/scripts/publish_check.py` (stages A-D of the script are added in Tasks 3-6):

````python
#!/usr/bin/env python3
# publish-check 0.1.0 - read-only scan of a git repository for leaks before it goes public
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Diogo Winck

VERSION = "0.1.0"
````



Create `plugins/publish-check/.claude-plugin/plugin.json`:

````json
{
  "name": "publish-check",
  "description": "Read-only scan of a git repository (working tree and full history) for session links, home paths, e-mail addresses and internal names before it goes public. Python standard library and git only.",
  "version": "0.1.0",
  "author": {
    "name": "Diogo Winck",
    "email": "diogo.winck@gmail.com"
  },
  "homepage": "https://github.com/dvwinck/capybara-toolbox",
  "repository": "https://github.com/dvwinck/capybara-toolbox",
  "license": "MIT",
  "keywords": [
    "security",
    "privacy",
    "git",
    "pre-publish",
    "skill"
  ]
}
````



Create `plugins/publish-check/CHANGELOG.md`:

````markdown
# Changelog

All notable changes to the **publish-check** plugin are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-10-12

### Added
- `publish_check.py`: read-only scan of a git repository for session links (claude.ai), home paths, e-mail addresses and an owner-supplied denylist of internal names, across the working tree (tracked and non-ignored files), every commit message, author and committer field, every patch and annotated tag on all refs.
- Readable report and `--json` (`schema` 1); exit code 0 clean, 1 findings, 2 error. Reported values are partly masked.
- `.publish-check.json` with `denylist` and `allow` (accepted findings by fingerprint), `--denylist FILE` for a list kept outside the repository, `--since` and `--max-commits`.
- Shallow clones are detected and reported as incomplete (`"shallow": true` in the JSON report).
- Hardening: e-mail detection is linear-time on huge lines; patch hunks are consumed by their line counts so content that looks like a diff header is still scanned; commit fields are NUL-delimited; a failing git command is an error (exit 2) instead of a silent "clean"; skipped files (binary, unreadable, over 50 MB) are counted in the report; control characters in snippets and locations are neutralised so a hostile repository cannot drive the terminal.
- Safe on untrusted repositories: git runs with `--no-optional-locks` and `core.fsmonitor` disabled, so a hostile `.git/config` cannot make the scan execute a program.
- Skill that offers the scan right before something is made public, plus documented `pre-push` hook and CI examples and a remediation guide.
````



Create `plugins/publish-check/tools/sync.py`:

````python
#!/usr/bin/env python3
"""Keeps the publish-check plugin consistent from one source of truth: the script's VERSION.

It propagates the version into .claude-plugin/plugin.json and reports problems it cannot fix by
itself (stale header comment, missing CHANGELOG entry).

Usage (from the plugin directory or anywhere):
  python3 tools/sync.py           # write whatever is out of sync
  python3 tools/sync.py --check   # only verify (exit 1 if anything differs or is wrong)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = "skills/publish-check/scripts/publish_check.py"
PLUGIN = ".claude-plugin/plugin.json"
CHANGELOG = "CHANGELOG.md"

INPUTS = [SCRIPT, PLUGIN, CHANGELOG]


def read(root, rel):
    return (root / rel).read_text(encoding="utf-8")


def dump_json(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def script_version(script):
    return re.search(r'^VERSION = "(\d+\.\d+\.\d+)"', script, re.M).group(1)


def build(root):
    """Return {relative path: expected content} for every generated file."""
    plugin = json.loads(read(root, PLUGIN))
    plugin["version"] = script_version(read(root, SCRIPT))
    return {PLUGIN: dump_json(plugin)}


def problems(root):
    """Things the tool cannot fix by itself; each one is a message."""
    out = []
    script = read(root, SCRIPT)
    version = script_version(script)
    if not re.search(rf"^# publish-check {re.escape(version)} - ", script, re.M):
        out.append(f"{SCRIPT}: header comment must say 'publish-check {version}' (VERSION is {version})")
    if not re.search(rf"^## \[{re.escape(version)}\]", read(root, CHANGELOG), re.M):
        out.append(f"{CHANGELOG}: no '## [{version}]' entry")
    return out


def main(argv, root=ROOT):
    files = build(root)
    found = problems(root)
    stale = [rel for rel, text in files.items() if not (root / rel).exists() or read(root, rel) != text]
    if "--check" in argv:
        for rel in stale:
            print(f"out of sync: {rel}")
        for msg in found:
            print(f"problem: {msg}")
        return 1 if (stale or found) else 0
    for rel in stale:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(files[rel], encoding="utf-8")
        print(f"updated: {rel}")
    for msg in found:
        print(f"problem: {msg}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
````



In `tests/test_marketplace.py`, replace:

````
        shutil.copytree(REPO / "plugins" / "ar-board" / ".claude-plugin", self.root / "plugins" / "ar-board" / ".claude-plugin")
````

with:

````
        for manifest_dir in sorted((REPO / "plugins").glob("*/.claude-plugin")):
            shutil.copytree(manifest_dir, self.root / manifest_dir.relative_to(REPO))
````


(Without this change the catalog-tool tests copy only the ar-board manifest into their temporary catalog and fail on the new entry.)


In `.claude-plugin/marketplace.json`, replace:

````
    }
  ]
}
````

with:

````
    },
    {
      "name": "publish-check",
      "source": "./plugins/publish-check",
      "author": {
        "name": "Diogo Winck",
        "email": "diogo.winck@gmail.com"
      },
      "license": "MIT",
      "keywords": [
        "security",
        "privacy",
        "git",
        "pre-publish",
        "skill"
      ],
      "category": "security"
    }
  ]
}
````


Then let the tool fill the synced fields (`version`, `description`, `homepage`, `repository`):

```bash
python3 tools/marketplace.py
```

Expected: `updated: .claude-plugin/marketplace.json`.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
$PLUGIN_TESTS
$ROOT_TESTS
python3 tools/marketplace.py --check && python3 plugins/publish-check/tools/sync.py --check
```

Expected: plugin suite `Ran 7 tests ... OK`; root suite `OK`; both checks exit 0 silently.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: publish-check plugin skeleton

Register the second plugin in the catalog, add its version sync tool,
helpers and package tests, and make the catalog tool tests copy every
plugin manifest.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---


### Task 2: CI discovers every plugin by glob

**Files:**
- Modify: `tests/test_marketplace.py`, `.github/workflows/ci.yml`

- [ ] **Step 1: Write the failing test**


In `tests/test_marketplace.py`, replace:

````
    def test_catalog_has_no_unverifiable_fields(self):
````

with:

````
    def test_ci_runs_every_plugin_suite_and_sync_tool(self):
        ci = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("plugins/*/tests", ci)
        self.assertIn("plugins/*/tools/sync.py", ci)
        self.assertNotIn("plugins/ar-board/tests", ci)
        self.assertNotIn("plugins/ar-board/tools/sync.py", ci)

    def test_catalog_has_no_unverifiable_fields(self):
````


- [ ] **Step 2: Run it to verify it fails**

```bash
$ROOT_TESTS
```

Expected: `FAIL: test_ci_runs_every_plugin_suite_and_sync_tool` with `AssertionError: 'plugins/*/tests' not found in 'name: CI ...'`.

- [ ] **Step 3: Replace the per-plugin steps with loops**


In `.github/workflows/ci.yml`, replace:

````
      - name: ar-board tests
        run: python -m unittest discover -s plugins/ar-board/tests
      - name: Catalog is in sync with the plugins
        run: python tools/marketplace.py --check
      - name: ar-board is in sync (version, manifest, single-file variant)
        run: python plugins/ar-board/tools/sync.py --check
````

with:

````
      - name: Plugin tests
        run: |
          for suite in plugins/*/tests; do
            echo "== $suite"
            python -m unittest discover -s "$suite"
          done
      - name: Catalog is in sync with the plugins
        run: python tools/marketplace.py --check
      - name: Plugins are in sync (version, manifest, generated files)
        run: |
          for tool in plugins/*/tools/sync.py; do
            echo "== $tool"
            python "$tool" --check
          done
````


- [ ] **Step 4: Run the tests to verify they pass**

```bash
$ROOT_TESTS
```

Expected: `OK`. (`bash -e` is the default shell for `run:` on Linux and macOS runners, so a failing suite aborts the loop.)

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "ci: run every plugin suite and sync check by glob

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---


### Task 3: Detection (categories, masking, fingerprints, findings)

**Files:**
- Replace: `plugins/publish-check/skills/publish-check/scripts/publish_check.py` (stage A)
- Create: `plugins/publish-check/tests/test_detect.py`

**Interfaces:**
- Produces (script): `Match(category, start, end, value)`, `ScanError`, `email_matches(text)`, `find_matches(text, denylist=())`, `mask(category, value)`, `fingerprint(category, where, origin, value)`, `findings_in_text(text, denylist, where, origin, locate)` yielding finding dicts `{"category","where","location","snippet","fingerprint"}`; constants `VERSION`, `SCHEMA`, `CONFIG_NAME`, `MAX_FILE_BYTES`, `CATEGORIES`, `GIT_FLAGS`.

- [ ] **Step 1: Write the failing tests**


Create `plugins/publish-check/tests/test_detect.py`:

````python
import time
import unittest

from helpers import LEAK_EMAIL, LEAK_LINK, LEAK_PATH, LEAK_TERM, pc


def cats(text, denylist=()):
    return [(m.category, m.value) for m in pc.find_matches(text, denylist)]


class SessionLinkTest(unittest.TestCase):
    def test_code_session_link_is_found(self):
        self.assertEqual(cats(f"see {LEAK_LINK} for context"), [("session-link", LEAK_LINK)])

    def test_chat_and_share_links_are_found(self):
        for url in ("https://claude." + "ai/chat/0f1e2d3c-aaaa", "https://claude." + "ai/share/abc123"):
            with self.subTest(url=url):
                self.assertEqual(cats(f"({url})"), [("session-link", url)])

    def test_the_site_itself_is_not_a_leak(self):
        self.assertEqual(cats("docs at https://claude.com/claude-code and https://claude.ai/"), [])


class HomePathTest(unittest.TestCase):
    def test_unix_mac_and_windows_home_paths_are_found(self):
        for path in (LEAK_PATH + "/projects", "/home/" + "fixtureuser/work", "C:\\Users\\" + "fixtureuser\\Desktop"):
            with self.subTest(path=path):
                self.assertEqual([c for c, _ in cats(f"cd {path}")], ["home-path"])

    def test_placeholders_and_ci_users_are_ignored(self):
        for text in ("/Users/<name>/x", "/home/runner/work", "/Users/Shared/data", "~/x and $HOME/y", "/Users/you/x"):
            with self.subTest(text=text):
                self.assertEqual(cats(text), [])


class EmailTest(unittest.TestCase):
    def test_email_is_found(self):
        self.assertEqual(cats(f"Reach me at {LEAK_EMAIL}."), [("email", LEAK_EMAIL)])

    def test_noreply_and_example_addresses_are_ignored(self):
        for text in ("Co-Authored-By: Claude <noreply@anthropic.com>", "a@example.com", "12345+bot@users.noreply.github.com"):
            with self.subTest(text=text):
                self.assertEqual(cats(text), [])

    def test_version_pins_are_not_emails(self):
        self.assertEqual(cats("uses: actions/checkout@v7 and pkg@1.2.3"), [])


class EmailRobustnessTest(unittest.TestCase):
    def test_a_huge_line_without_an_at_sign_is_scanned_in_linear_time(self):
        started = time.monotonic()
        self.assertEqual(cats("a" * 300000), [])
        self.assertEqual(cats("a." * 150000), [])
        self.assertLess(time.monotonic() - started, 2.0)

    def test_many_at_signs_are_scanned_in_linear_time(self):
        started = time.monotonic()
        self.assertEqual(cats("a@" * 100000), [])
        self.assertLess(time.monotonic() - started, 2.0)

    def test_a_long_prefix_does_not_hide_an_address(self):
        found = cats("x" * 200 + LEAK_EMAIL)
        self.assertEqual([c for c, _ in found], ["email"])
        self.assertTrue(found[0][1].endswith(LEAK_EMAIL.split("@")[1]))

    def test_trailing_punctuation_is_not_part_of_the_address(self):
        self.assertEqual(cats(f"({LEAK_EMAIL}), or {LEAK_EMAIL}.")[0][1], LEAK_EMAIL)
        self.assertEqual(cats(f"mail {LEAK_EMAIL}.")[0][1], LEAK_EMAIL)


class DenylistTest(unittest.TestCase):
    def test_denylist_is_case_insensitive(self):
        self.assertEqual(cats(f"the {LEAK_TERM.upper()} plan", [LEAK_TERM]), [("denylist", LEAK_TERM.upper())])

    def test_overlapping_matches_keep_only_the_first(self):
        text = LEAK_LINK
        self.assertEqual(cats(text, ["session_FIXTURE"]), [("session-link", LEAK_LINK)])

    def test_matches_are_sorted_by_position(self):
        text = f"{LEAK_EMAIL} then {LEAK_PATH}/x"
        self.assertEqual([c for c, _ in cats(text)], ["email", "home-path"])


class MaskTest(unittest.TestCase):
    def test_masked_values_do_not_contain_the_original(self):
        samples = {
            "session-link": LEAK_LINK,
            "home-path": LEAK_PATH + "/projects",
            "email": LEAK_EMAIL,
            "denylist": LEAK_TERM,
        }
        for category, value in samples.items():
            with self.subTest(category=category):
                masked = pc.mask(category, value)
                self.assertNotEqual(masked, value)
                self.assertIn("***", masked)
                self.assertNotIn("FIXTURE123", masked)
                self.assertNotIn("fixtureuser", masked)
                self.assertNotIn("fixture.person", masked)

    def test_email_keeps_the_domain_for_triage(self):
        self.assertEqual(pc.mask("email", "jane@" + "acme.dev"), "j***@acme.dev")

    def test_home_path_keeps_only_the_directory_prefix(self):
        self.assertEqual(pc.mask("home-path", "/Users/" + "jane"), "/Users/***")
        self.assertEqual(pc.mask("home-path", "C:\\Users\\" + "jane"), "C:\\Users\\***")


class FingerprintTest(unittest.TestCase):
    def test_fingerprint_is_stable_and_case_insensitive_on_the_value(self):
        a = pc.fingerprint("email", "tree", "README.md", "Jane@" + "Acme.dev")
        self.assertEqual(a, pc.fingerprint("email", "tree", "README.md", "jane@" + "acme.dev"))
        self.assertEqual(len(a), 16)

    def test_fingerprint_depends_on_category_place_and_origin(self):
        base = pc.fingerprint("email", "tree", "README.md", "jane@" + "acme.dev")
        self.assertNotEqual(base, pc.fingerprint("home-path", "tree", "README.md", "jane@" + "acme.dev"))
        self.assertNotEqual(base, pc.fingerprint("email", "patch", "README.md", "jane@" + "acme.dev"))
        self.assertNotEqual(base, pc.fingerprint("email", "tree", "OTHER.md", "jane@" + "acme.dev"))


class FindingsInTextTest(unittest.TestCase):
    def test_every_leak_on_a_line_is_masked_in_every_snippet(self):
        text = f"from {LEAK_EMAIL} at {LEAK_PATH}/x"
        found = list(pc.findings_in_text(text, [], "tree", "a.txt", lambda n: f"a.txt:{n}"))
        self.assertEqual([f["category"] for f in found], ["email", "home-path"])
        for f in found:
            self.assertNotIn("fixture.person", f["snippet"])
            self.assertNotIn("fixtureuser", f["snippet"])
            self.assertEqual(f["location"], "a.txt:1")

    def test_line_numbers_follow_the_text(self):
        found = list(pc.findings_in_text(f"ok\nok\n{LEAK_EMAIL}\n", [], "tree", "a.txt", lambda n: f"a.txt:{n}"))
        self.assertEqual(found[0]["location"], "a.txt:3")

    def test_control_characters_cannot_reach_the_terminal(self):
        text = f"\x1b[2J\x1b]0;owned\x07 mail {LEAK_EMAIL}\r\x85"
        found = list(pc.findings_in_text(text, [], "tree", "a.txt", lambda n: "bad\x1b[0mname.txt:%d" % n))
        for f in found:
            for field in ("snippet", "location"):
                self.assertFalse(any(ord(ch) < 32 and ch != "\t" or 127 <= ord(ch) < 160 for ch in f[field]), f[field])

    def test_long_lines_keep_a_window_around_the_match(self):
        line = "x" * 500 + " " + LEAK_EMAIL + " " + "y" * 500
        found = list(pc.findings_in_text(line, [], "tree", "min.js", lambda n: "min.js:1"))
        self.assertLess(len(found[0]["snippet"]), 140)
        self.assertIn("***@", found[0]["snippet"])


if __name__ == "__main__":
    unittest.main()
````


- [ ] **Step 2: Run them to verify they fail**

```bash
$PLUGIN_TESTS -p test_detect.py
```

Expected: errors such as `AttributeError: module 'publish_check' has no attribute 'find_matches'`.

- [ ] **Step 3: Implement stage A**

Replace the whole script with (this adds every import the later stages use, and ends before the git-scanning section):


````python
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
````


- [ ] **Step 4: Run the tests to verify they pass**

```bash
$PLUGIN_TESTS -p test_detect.py
$PLUGIN_TESTS
```

Expected: `Ran 24 tests ... OK` for `test_detect.py`; the whole plugin suite `OK` (the sync check still passes: the header comment and `VERSION` are unchanged).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(publish-check): detect leaks in text

Session links, home paths, e-mail addresses and a denylist, with masking,
stable fingerprints, linear-time e-mail matching and control-character
neutralisation.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---


### Task 4: Scan the working tree, commit metadata, patches and tags

**Files:**
- Append to: `plugins/publish-check/skills/publish-check/scripts/publish_check.py` (stage B)
- Create: `plugins/publish-check/tests/test_scan.py`

**Interfaces:**
- Consumes: `findings_in_text`, `ScanError`, `GIT_FLAGS`, `MAX_FILE_BYTES` from Task 3.
- Produces: `git(root, *args)`, `git_checked(root, *args)`, `repo_root(path)`, `is_shallow(root)`, `history_args(since, max_commits)`, `scan_tree`, `scan_commit_metadata`, `scan_patches`, `scan_tags`, and `scan(root, denylist, since=None, max_commits=None)` returning `(findings, stats)` with `stats == {"files", "commits", "skipped"}`.

- [ ] **Step 1: Write the failing tests**


Create `plugins/publish-check/tests/test_scan.py`:

````python
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import LEAK_EMAIL, LEAK_LINK, LEAK_PATH, LEAK_TERM, commit, git, init_repo, pc


class RepoCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = init_repo(Path(tmp.name) / "repo")

    def scan(self, denylist=(), **kw):
        findings, stats = pc.scan(self.repo, list(denylist), **kw)
        return findings, stats

    def where(self, findings, where):
        return [f for f in findings if f["where"] == where]


class TreeScanTest(RepoCase):
    def test_tracked_file_leak_is_found_with_file_and_line(self):
        commit(self.repo, "add notes", {"notes.md": f"intro\ncontact {LEAK_EMAIL}\n"})
        findings, stats = self.scan()
        tree = self.where(findings, "tree")
        self.assertEqual([(f["category"], f["location"]) for f in tree], [("email", "notes.md:2")])
        self.assertEqual(stats["files"], 1)

    def test_untracked_but_not_ignored_file_is_scanned_and_ignored_file_is_not(self):
        commit(self.repo, "base", {".gitignore": "secret.txt\n", "ok.txt": "fine\n"})
        (self.repo / "new.txt").write_text(f"path {LEAK_PATH}/x\n", encoding="utf-8")
        (self.repo / "secret.txt").write_text(f"mail {LEAK_EMAIL}\n", encoding="utf-8")
        findings, _ = self.scan()
        self.assertEqual([f["location"] for f in self.where(findings, "tree")], ["new.txt:1"])

    def test_clean_repository_has_no_findings(self):
        commit(self.repo, "clean\n\nCo-Authored-By: Claude <noreply@anthropic.com>", {"a.txt": "hello\n"})
        findings, stats = self.scan()
        self.assertEqual(findings, [])
        self.assertEqual(stats, {"files": 1, "commits": 1, "skipped": 0})


class HistoryScanTest(RepoCase):
    def test_leak_only_in_an_old_commit_message_is_found(self):
        commit(self.repo, f"first\n\nsee {LEAK_LINK}", {"a.txt": "one\n"})
        commit(self.repo, "second", {"a.txt": "two\n"})
        findings, stats = self.scan()
        msgs = self.where(findings, "commit-message")
        self.assertEqual([f["category"] for f in msgs], ["session-link"])
        self.assertRegex(msgs[0]["location"], r"^[0-9a-f]{7} message line 3$")
        self.assertEqual(stats["commits"], 2)

    def test_author_and_committer_fields_are_scanned_separately(self):
        commit(self.repo, "by two people", {"a.txt": "x\n"},
               author=("Pat Author", LEAK_EMAIL), committer=("Chris Committer", "chris@" + "other-fixture.dev"))
        findings, _ = self.scan()
        self.assertEqual([f["location"].split()[1] for f in self.where(findings, "commit-author")], ["author"])
        self.assertEqual([f["location"].split()[1] for f in self.where(findings, "commit-committer")], ["committer"])

    def test_same_author_and_committer_is_reported_once(self):
        commit(self.repo, "solo", {"a.txt": "x\n"}, author=("Pat", LEAK_EMAIL))
        findings, _ = self.scan()
        self.assertEqual(len(self.where(findings, "commit-author")), 1)
        self.assertEqual(self.where(findings, "commit-committer"), [])

    def test_leak_added_then_removed_is_found_in_the_patch(self):
        commit(self.repo, "add", {"conf.txt": f"ok\nhome={LEAK_PATH}\n"})
        commit(self.repo, "remove it", {"conf.txt": "ok\n"})
        findings, _ = self.scan()
        self.assertEqual(self.where(findings, "tree"), [])
        patches = self.where(findings, "patch")
        self.assertEqual([f["category"] for f in patches], ["home-path"])
        self.assertRegex(patches[0]["location"], r"^[0-9a-f]{7} conf\.txt:2$")

    def test_other_branches_are_scanned(self):
        commit(self.repo, "main work", {"a.txt": "x\n"})
        git(self.repo, "checkout", "-q", "-b", "feature")
        commit(self.repo, f"feature {LEAK_EMAIL}", {"b.txt": "y\n"})
        git(self.repo, "checkout", "-q", "main")
        findings, _ = self.scan()
        self.assertEqual([f["category"] for f in self.where(findings, "commit-message")], ["email"])

    def test_annotated_tag_message_is_scanned_but_lightweight_tags_are_not(self):
        commit(self.repo, "release", {"a.txt": "x\n"})
        git(self.repo, "tag", "-a", "v1", "-m", f"release notes {LEAK_LINK}")
        git(self.repo, "tag", "light")
        findings, _ = self.scan()
        tags = self.where(findings, "tag")
        self.assertEqual([(f["category"], f["location"]) for f in tags], [("session-link", "tag v1")])

    def test_denylist_terms_are_found_everywhere(self):
        commit(self.repo, f"about {LEAK_TERM}", {"a.txt": f"{LEAK_TERM.lower()} notes\n"})
        findings, _ = self.scan(denylist=[LEAK_TERM])
        self.assertEqual({f["where"] for f in findings if f["category"] == "denylist"},
                         {"tree", "commit-message", "patch"})

    def test_max_commits_and_since_limit_the_history(self):
        commit(self.repo, f"old {LEAK_EMAIL}", {"a.txt": "1\n"}, date="2020-01-01T00:00:00")
        commit(self.repo, "new", {"a.txt": "2\n"}, date="2024-01-01T00:00:00")
        full, stats = self.scan()
        self.assertEqual(len(self.where(full, "commit-message")), 1)
        self.assertEqual(stats["commits"], 2)
        limited, stats = self.scan(max_commits=1)
        self.assertEqual(self.where(limited, "commit-message"), [])
        self.assertEqual(stats["commits"], 1)
        recent, stats = self.scan(since="2022-01-01")
        self.assertEqual(self.where(recent, "commit-message"), [])
        self.assertEqual(stats["commits"], 1)


class RobustnessTest(RepoCase):
    def test_a_repository_without_commits_still_scans_the_tree(self):
        (self.repo / "draft.txt").write_text(f"mail {LEAK_EMAIL}\n", encoding="utf-8")
        findings, stats = self.scan()
        self.assertEqual([f["where"] for f in findings], ["tree"])
        self.assertEqual(stats["commits"], 0)

    def test_text_that_is_not_utf8_is_scanned_not_fatal(self):
        commit(self.repo, "base", {"ok.txt": "fine\n"})
        (self.repo / "latin1.txt").write_bytes(b"caf\xe9 mail " + LEAK_EMAIL.encode() + b"\n")
        findings, _ = self.scan()
        self.assertEqual([f["location"] for f in findings if f["where"] == "tree"], ["latin1.txt:1"])

    def test_paths_with_spaces_and_accents_are_reported_correctly(self):
        commit(self.repo, "add", {"dir with space/a\u00e7\u00e3o.txt": f"mail {LEAK_EMAIL}\n"})
        findings, _ = self.scan()
        self.assertEqual([f["location"] for f in self.where(findings, "tree")], ["dir with space/a\u00e7\u00e3o.txt:1"])
        patch = self.where(findings, "patch")
        self.assertRegex(patch[0]["location"], r"^[0-9a-f]{7} dir with space/a\u00e7\u00e3o\.txt:1$")

    def test_a_shallow_clone_is_detected(self):
        commit(self.repo, "one", {"a.txt": "1\n"})
        commit(self.repo, "two", {"a.txt": "2\n"})
        self.assertFalse(pc.is_shallow(self.repo))
        with tempfile.TemporaryDirectory() as d:
            clone = Path(d) / "clone"
            git(self.repo, "clone", "-q", "--depth", "1", "file://" + str(self.repo), str(clone))
            self.assertTrue(pc.is_shallow(clone))


class AdversarialInputTest(RepoCase):
    """Content written by a malicious committer must not make the scan skip or misread anything."""

    def test_added_lines_that_look_like_diff_headers_are_still_scanned(self):
        commit(self.repo, "add", {"a.txt": f"ok\n++ b/other.txt\n++ mail {LEAK_EMAIL}\n+++ mail {LEAK_EMAIL}\n"})
        findings, _ = self.scan()
        patches = self.where(findings, "patch")
        self.assertEqual(len(patches), 2)
        self.assertTrue(all(f["location"].endswith(" a.txt:" + n) for f, n in zip(patches, ("3", "4"))),
                        [f["location"] for f in patches])

    def test_record_separator_characters_in_a_message_do_not_hide_later_text(self):
        commit(self.repo, "one\x1e two\x1f three\n\n" + f"see {LEAK_EMAIL}", {"a.txt": "x\n"})
        findings, stats = self.scan()
        self.assertEqual([f["category"] for f in self.where(findings, "commit-message")], ["email"])
        self.assertEqual(stats["commits"], 1)

    def test_a_git_failure_is_an_error_not_a_clean_scan(self):
        sha = commit(self.repo, "add", {"a.txt": "hello\n"})
        blob = git(self.repo, "rev-parse", "HEAD:a.txt").strip()
        os.remove(self.repo / ".git" / "objects" / blob[:2] / blob[2:])
        with self.assertRaises(pc.ScanError):
            self.scan()

    def test_a_hostile_repository_config_cannot_run_programs(self):
        marker = self.repo.parent / "PWNED"
        hook = self.repo.parent / "hook.sh"
        hook.write_text(f"#!/bin/sh\ntouch '{marker}'\nprintf '\\0'\n", encoding="utf-8")
        hook.chmod(0o755)
        commit(self.repo, "base", {"a.txt": "x\n"})
        git(self.repo, "config", "core.fsmonitor", str(hook))
        self.scan()
        self.assertFalse(marker.exists(), "scanning ran a program named by the repository's own config")

    def test_files_that_cannot_be_scanned_are_counted_not_ignored(self):
        commit(self.repo, "base", {"ok.txt": "fine\n"})
        (self.repo / "blob.bin").write_bytes(b"\0\1\2" + LEAK_EMAIL.encode())
        (self.repo / "big.txt").write_text(LEAK_EMAIL + "\n" + "x" * 2000, encoding="utf-8")
        with mock.patch.object(pc, "MAX_FILE_BYTES", 1000):
            findings, stats = self.scan()
        self.assertEqual(self.where(findings, "tree"), [])
        self.assertEqual(stats["skipped"], 2)
        self.assertEqual(stats["files"], 1)


class FingerprintAcrossCommitsTest(RepoCase):
    def fingerprints(self, findings, where):
        return {f["fingerprint"] for f in self.where(findings, where)}

    def test_the_same_author_in_many_commits_is_one_fingerprint(self):
        for i in range(3):
            commit(self.repo, f"change {i}", {"a.txt": f"{i}\n"}, author=("Pat", LEAK_EMAIL))
        findings, _ = self.scan()
        self.assertEqual(len(self.where(findings, "commit-author")), 3)
        self.assertEqual(len(self.fingerprints(findings, "commit-author")), 1)

    def test_the_same_value_added_to_the_same_file_twice_is_one_fingerprint(self):
        commit(self.repo, "one", {"conf.txt": f"mail {LEAK_EMAIL}\n"})
        commit(self.repo, "two", {"conf.txt": f"mail {LEAK_EMAIL}\nmore\n"})
        commit(self.repo, "three", {"conf.txt": f"more\nmail {LEAK_EMAIL}\nagain\n"})
        findings, _ = self.scan()
        self.assertGreater(len(self.where(findings, "patch")), 1)
        self.assertEqual(len(self.fingerprints(findings, "patch")), 1)

    def test_a_new_value_or_a_new_file_is_a_new_fingerprint(self):
        commit(self.repo, "one", {"a.txt": f"mail {LEAK_EMAIL}\n"})
        commit(self.repo, "two", {"b.txt": f"mail {LEAK_EMAIL}\n"})
        commit(self.repo, "three", {"c.txt": "mail other.person@" + "acme-fixture.dev\n"})
        findings, _ = self.scan()
        self.assertEqual(len(self.fingerprints(findings, "patch")), 3)

    def test_dependabot_trailers_are_not_findings(self):
        commit(self.repo, "bump\n\nSigned-off-by: dependabot[bot] <support@github.com>", {"a.txt": "x\n"})
        findings, _ = self.scan()
        self.assertEqual(findings, [])


class RepoRootTest(unittest.TestCase):
    def test_a_directory_that_is_not_a_repository_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(pc.ScanError):
                pc.repo_root(Path(d))

    def test_a_subdirectory_resolves_to_the_repository_root(self):
        with tempfile.TemporaryDirectory() as d:
            repo = init_repo(Path(d) / "r")
            (repo / "sub").mkdir()
            self.assertEqual(pc.repo_root(repo / "sub").resolve(), repo.resolve())


if __name__ == "__main__":
    unittest.main()
````


- [ ] **Step 2: Run them to verify they fail**

```bash
$PLUGIN_TESTS -p test_scan.py
```

Expected: errors such as `AttributeError: module 'publish_check' has no attribute 'scan'`.

- [ ] **Step 3: Implement stage B**

Append to the script (after `findings_in_text`):


````python
# ---------------------------------------------------------------- git scanning

def git(root, *args):
    try:
        return subprocess.run(["git", *GIT_FLAGS, "-C", str(root), *args], capture_output=True, check=False)
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


def history_args(since, max_commits):
    args = []
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
    r = git_checked(root, "log", "--all", "--no-color", "-z", fmt, *history_args(since, max_commits))
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
    cmd = ["git", *GIT_FLAGS, "-C", str(root), "log", "--all", "-p", "-U0", "--no-color",
           "--no-ext-diff", "--no-textconv", "--format=%x1e%H", *history_args(since, max_commits)]
    with tempfile.TemporaryFile() as errors:
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=errors)
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


def scan(root, denylist, since=None, max_commits=None):
    """Return (findings, stats) for a repository root."""
    stats = {"files": 0, "commits": 0, "skipped": 0}
    findings = list(scan_tree(root, denylist, stats))
    findings += scan_commit_metadata(root, denylist, since, max_commits, stats)
    findings += scan_patches(root, denylist, since, max_commits)
    findings += scan_tags(root, denylist)
    return findings, stats
````


- [ ] **Step 4: Run the tests to verify they pass**

```bash
$PLUGIN_TESTS -p test_scan.py
$PLUGIN_TESTS
```

Expected: `OK` for both. This suite builds many temporary git repositories and takes tens of seconds.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(publish-check): scan tree, history, patches and tags

Read-only git scanning that is deaf to the repository's own config, fails
closed when git fails, counts files it cannot scan and parses patches by
hunk line counts.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---


### Task 5: Configuration file, denylist file, allow list

**Files:**
- Append to: `plugins/publish-check/skills/publish-check/scripts/publish_check.py` (stage C)
- Create: `plugins/publish-check/tests/test_config.py`

**Interfaces:**
- Produces: `load_config(path) -> (denylist, allow)` and `read_denylist_file(path) -> [names]`; both raise `ScanError` on bad input.

- [ ] **Step 1: Write the failing tests**


Create `plugins/publish-check/tests/test_config.py`:

````python
import json
import tempfile
import unittest
from pathlib import Path

from helpers import pc


class LoadConfigTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def write(self, text, name=".publish-check.json"):
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_valid_config_returns_denylist_and_allow(self):
        path = self.write(json.dumps({"denylist": ["Acme"], "allow": ["0123456789abcdef"]}))
        self.assertEqual(pc.load_config(path), (["Acme"], ["0123456789abcdef"]))

    def test_missing_keys_default_to_empty(self):
        self.assertEqual(pc.load_config(self.write("{}")), ([], []))

    def test_unknown_keys_are_rejected(self):
        with self.assertRaisesRegex(pc.ScanError, "unknown keys deny"):
            pc.load_config(self.write(json.dumps({"deny": ["x"]})))

    def test_wrong_types_are_rejected(self):
        for body in ('{"denylist": "Acme"}', '{"allow": [1, 2]}', "[]"):
            with self.subTest(body=body):
                with self.assertRaises(pc.ScanError):
                    pc.load_config(self.write(body))

    def test_invalid_json_and_missing_file_are_errors(self):
        with self.assertRaisesRegex(pc.ScanError, "not valid JSON"):
            pc.load_config(self.write("{nope"))
        with self.assertRaisesRegex(pc.ScanError, "cannot read config"):
            pc.load_config(self.dir / "absent.json")

    def test_denylist_file_skips_blank_lines_and_comments(self):
        path = self.write("# internal names\nAcme\n\n  Zephyr  \n", "names.txt")
        self.assertEqual(pc.read_denylist_file(path), ["Acme", "Zephyr"])

    def test_missing_denylist_file_is_an_error(self):
        with self.assertRaisesRegex(pc.ScanError, "cannot read denylist"):
            pc.read_denylist_file(self.dir / "absent.txt")


if __name__ == "__main__":
    unittest.main()
````


- [ ] **Step 2: Run them to verify they fail**

```bash
$PLUGIN_TESTS -p test_config.py
```

Expected: `AttributeError: module 'publish_check' has no attribute 'load_config'`.

- [ ] **Step 3: Implement stage C**

Append to the script:


````python
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
````


- [ ] **Step 4: Run the tests to verify they pass**

```bash
$PLUGIN_TESTS -p test_config.py
```

Expected: `Ran 7 tests ... OK`.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(publish-check): config file, denylist file and allow list

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---


### Task 6: Report, JSON output and command line

**Files:**
- Append to: `plugins/publish-check/skills/publish-check/scripts/publish_check.py` (stage D, which completes the script)
- Create: `plugins/publish-check/tests/test_run.py`, `plugins/publish-check/tests/test_cli.py`

**Interfaces:**
- Consumes: everything from Tasks 3-5.
- Produces: `build_report(root, findings, stats, allowed, shallow=False)`, `render_text(report)`, `parser()`, `run(args) -> report`, `main(argv=None) -> exit code`. The JSON report: `{"schema", "tool", "version", "path", "scanned": {"files","commits","skipped"}, "clean", "counts", "allowed", "shallow", "findings"}`.

- [ ] **Step 1: Write the failing tests**


Create `plugins/publish-check/tests/test_run.py`:

````python
import json
import tempfile
import unittest
from pathlib import Path

from helpers import LEAK_EMAIL, LEAK_TERM, commit, init_repo, pc


class RunTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.repo = init_repo(self.tmp / "repo")
        commit(self.repo, "initial", {"a.txt": f"mail {LEAK_EMAIL}\nthe {LEAK_TERM} plan\n"})

    def run_cli(self, *argv):
        return pc.run(pc.parser().parse_args([str(self.repo), *argv]))

    def test_findings_without_any_config(self):
        report = self.run_cli()
        self.assertEqual(report["counts"]["email"], 2)  # once in the tree, once in the patch that added it
        self.assertFalse(report["clean"])

    def test_config_in_the_repository_is_discovered_and_adds_the_denylist(self):
        (self.repo / pc.CONFIG_NAME).write_text(json.dumps({"denylist": [LEAK_TERM]}), encoding="utf-8")
        report = self.run_cli()
        self.assertGreater(report["counts"]["denylist"], 0)

    def test_allow_list_removes_exactly_the_accepted_findings(self):
        before = self.run_cli()
        accepted = [f["fingerprint"] for f in before["findings"] if f["category"] == "email"]
        cfg = self.tmp / "accept.json"
        cfg.write_text(json.dumps({"allow": accepted}), encoding="utf-8")
        after = self.run_cli("--config", str(cfg))
        self.assertEqual(after["counts"]["email"], 0)
        self.assertEqual(after["allowed"], len(accepted))
        self.assertEqual(len(after["findings"]), len(before["findings"]) - len(accepted))

    def test_denylist_file_outside_the_repository(self):
        names = self.tmp / "names.txt"
        names.write_text(LEAK_TERM + "\n", encoding="utf-8")
        report = self.run_cli("--denylist", str(names))
        self.assertGreater(report["counts"]["denylist"], 0)

    def test_explicit_config_that_does_not_exist_is_an_error(self):
        with self.assertRaises(pc.ScanError):
            self.run_cli("--config", str(self.tmp / "absent.json"))


if __name__ == "__main__":
    unittest.main()
````



Create `plugins/publish-check/tests/test_cli.py`:

````python
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import LEAK_EMAIL, LEAK_LINK, SCRIPT, commit, init_repo


def run(*argv, cwd=None):
    return subprocess.run([sys.executable, "-I", str(SCRIPT), *argv], capture_output=True, text=True, cwd=cwd)


class CliTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.repo = init_repo(self.tmp / "repo")

    def test_clean_repository_exits_0(self):
        commit(self.repo, "fine", {"a.txt": "hello\n"})
        r = run(str(self.repo))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("clean: no findings", r.stdout)

    def test_findings_exit_1_and_the_report_never_shows_the_raw_value(self):
        commit(self.repo, f"leaky\n\nsee {LEAK_LINK}", {"a.txt": f"mail {LEAK_EMAIL}\n"})
        r = run(str(self.repo))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("[email]", r.stdout)
        self.assertIn("[session-link]", r.stdout)
        self.assertIn("fingerprint:", r.stdout)
        self.assertIn("never rewrites history", r.stdout)
        for raw in ("FIXTURE123", "fixture.person"):
            self.assertNotIn(raw, r.stdout)

    def test_default_path_is_the_current_directory(self):
        commit(self.repo, "fine", {"a.txt": "hello\n"})
        r = run(cwd=self.repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_json_report_has_a_stable_shape(self):
        commit(self.repo, "leaky", {"a.txt": f"mail {LEAK_EMAIL}\n"})
        r = run(str(self.repo), "--json")
        self.assertEqual(r.returncode, 1)
        report = json.loads(r.stdout)
        self.assertEqual(report["schema"], 1)
        self.assertEqual(report["tool"], "publish-check")
        self.assertFalse(report["clean"])
        self.assertEqual(set(report["counts"]), {"session-link", "home-path", "email", "denylist"})
        self.assertEqual(set(report["scanned"]), {"files", "commits", "skipped"})
        self.assertIn("allowed", report)
        self.assertIn("shallow", report)
        for f in report["findings"]:
            self.assertEqual(set(f), {"category", "where", "location", "snippet", "fingerprint"})
            self.assertNotIn("fixture.person", json.dumps(f))

    def test_skipped_files_are_visible_in_both_reports(self):
        commit(self.repo, "fine", {"a.txt": "hello\n"})
        (self.repo / "blob.bin").write_bytes(b"\0\1\2")
        text = run(str(self.repo))
        self.assertEqual(text.returncode, 0, text.stdout + text.stderr)
        self.assertIn("1 file skipped", text.stdout)
        self.assertEqual(json.loads(run(str(self.repo), "--json").stdout)["scanned"]["skipped"], 1)

    def test_json_report_of_a_clean_repository(self):
        commit(self.repo, "fine", {"a.txt": "hello\n"})
        r = run(str(self.repo), "--json")
        self.assertEqual(r.returncode, 0)
        report = json.loads(r.stdout)
        self.assertTrue(report["clean"])
        self.assertEqual(report["findings"], [])

    def test_a_shallow_clone_is_reported_as_incomplete(self):
        commit(self.repo, "one", {"a.txt": "1\n"})
        commit(self.repo, "two", {"a.txt": "2\n"})
        clone = self.tmp / "clone"
        subprocess.run(["git", "clone", "-q", "--depth", "1", "file://" + str(self.repo), str(clone)], check=True,
                       capture_output=True)
        text = run(str(clone))
        self.assertEqual(text.returncode, 0, text.stdout + text.stderr)
        self.assertIn("shallow", text.stdout)
        self.assertTrue(json.loads(run(str(clone), "--json").stdout)["shallow"])
        self.assertFalse(json.loads(run(str(self.repo), "--json").stdout)["shallow"])

    def test_not_a_git_repository_exits_2(self):
        r = run(str(self.tmp))
        self.assertEqual(r.returncode, 2)
        self.assertIn("not inside a git repository", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_bad_config_exits_2(self):
        commit(self.repo, "fine", {"a.txt": "hello\n"})
        (self.repo / ".publish-check.json").write_text("{nope", encoding="utf-8")
        r = run(str(self.repo))
        self.assertEqual(r.returncode, 2)
        self.assertIn("not valid JSON", r.stderr)

    def test_invalid_options_exit_2(self):
        r = run(str(self.repo), "--max-commits", "0")
        self.assertEqual(r.returncode, 2)

    def test_version_flag(self):
        r = run("--version")
        self.assertEqual(r.returncode, 0)
        self.assertRegex(r.stdout, r"^publish-check \d+\.\d+\.\d+")

    def test_report_does_not_modify_the_repository(self):
        commit(self.repo, "leaky", {"a.txt": f"mail {LEAK_EMAIL}\n"})
        before = subprocess.run(["git", "-C", str(self.repo), "status", "--porcelain"], capture_output=True, text=True).stdout
        run(str(self.repo))
        after = subprocess.run(["git", "-C", str(self.repo), "status", "--porcelain"], capture_output=True, text=True).stdout
        self.assertEqual(before, after)
        self.assertEqual(sorted(p.name for p in self.repo.iterdir()), [".git", "a.txt"])


if __name__ == "__main__":
    unittest.main()
````


- [ ] **Step 2: Run them to verify they fail**

```bash
$PLUGIN_TESTS -p test_run.py
$PLUGIN_TESTS -p test_cli.py
```

Expected: `AttributeError: module 'publish_check' has no attribute 'parser'` (run) and `AssertionError` on the exit codes (cli: the script has no `main` yet).

- [ ] **Step 3: Implement stage D**

Append to the script (it ends with the `if __name__ == "__main__"` block):


````python
# ---------------------------------------------------------------- report

def build_report(root, findings, stats, allowed, shallow=False):
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
    return build_report(root, kept, stats, len(findings) - len(kept), is_shallow(root))


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
````


- [ ] **Step 4: Run the tests to verify they pass**

```bash
$PLUGIN_TESTS
```

Expected: `OK` for the whole plugin suite.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(publish-check): report, JSON output and command line

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---


### Task 7: Skill, documentation, examples and repository docs

**Files:**
- Modify: `plugins/publish-check/tests/test_package.py` (add the remaining classes), `tests/test_marketplace.py`, `README.md`, `README.pt-BR.md`, `CONTRIBUTING.md`, `CLAUDE.md`
- Create: `plugins/publish-check/skills/publish-check/SKILL.md`, `plugins/publish-check/README.md`, `plugins/publish-check/README.pt-BR.md`, `plugins/publish-check/docs/remediation.md`, `plugins/publish-check/examples/pre-push.sh`, `plugins/publish-check/examples/ci-step.yml`

- [ ] **Step 1: Write the failing tests**

In `plugins/publish-check/tests/test_package.py`, insert the following classes immediately before the line `if __name__ == "__main__":`:


````python
class DocsTest(unittest.TestCase):
    def test_files_named_in_the_readmes_exist(self):
        for readme in ("README.md", "README.pt-BR.md"):
            text = (ROOT / readme).read_text(encoding="utf-8")
            for rel in ("docs/remediation.md", "examples/pre-push.sh", "examples/ci-step.yml", "CHANGELOG.md"):
                with self.subTest(readme=readme, rel=rel):
                    self.assertIn(rel, text)
                    self.assertTrue((ROOT / rel).is_file(), rel)


class SkillTest(unittest.TestCase):
    SKILL = (ROOT / "skills" / "publish-check" / "SKILL.md")

    def test_frontmatter_names_the_skill_and_has_triggers(self):
        text = self.SKILL.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nname: publish-check\ndescription: "))
        head = text.split("\n---\n", 1)[0]
        for trigger in ("/publish-check", "publish-check", "antes de publicar", "before I publish"):
            self.assertIn(trigger, head)

    def test_skill_runs_the_bundled_script_in_isolated_mode(self):
        text = self.SKILL.read_text(encoding="utf-8")
        self.assertIn('python3 -I "${CLAUDE_SKILL_DIR}/scripts/publish_check.py"', text)
        self.assertIn("Base directory for this skill", text)  # fallback when the variable is not expanded

    def test_skill_is_read_only_and_never_blocks(self):
        text = self.SKILL.read_text(encoding="utf-8")
        self.assertIn("somente leitura", text.lower())
        self.assertIn("Nunca reescreva histórico", text)
        self.assertIn("nunca bloqueie", text.lower())


class ExamplesTest(unittest.TestCase):
    def run_hook(self, repo):
        env = {**os.environ, "PUBLISH_CHECK": str(SCRIPT)}
        return subprocess.run(["bash", str(ROOT / "examples" / "pre-push.sh")], cwd=repo, env=env,
                              capture_output=True, text=True)

    def test_pre_push_hook_blocks_a_leak_and_lets_a_clean_repository_through(self):
        with tempfile.TemporaryDirectory() as tmp:
            clean = init_repo(Path(tmp) / "clean")
            commit(clean, "fine", {"a.txt": "hello\n"})
            r = self.run_hook(clean)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            leaky = init_repo(Path(tmp) / "leaky")
            commit(leaky, "oops", {"a.txt": f"mail {LEAK_EMAIL}\n"})
            r = self.run_hook(leaky)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("push blocked", r.stderr)

    def test_ci_example_fetches_the_whole_history(self):
        text = (ROOT / "examples" / "ci-step.yml").read_text(encoding="utf-8")
        self.assertIn("fetch-depth: 0", text)


class ManualInstallTest(unittest.TestCase):
    def run_install(self, home, *args):
        return subprocess.run(["bash", str(REPO / "install.sh"), *args], env={**os.environ, "HOME": home},
                              capture_output=True, text=True)

    def test_install_copies_the_skill_and_uninstall_removes_it(self):
        with tempfile.TemporaryDirectory() as home:
            r = self.run_install(home, "publish-check")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            dest = Path(home, ".claude", "skills", "publish-check")
            self.assertEqual((dest / "scripts" / "publish_check.py").read_bytes(), SCRIPT.read_bytes())
            self.assertTrue((dest / "SKILL.md").exists())
            r = self.run_install(home, "publish-check", "--uninstall")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertFalse(dest.exists())

    def test_list_shows_the_plugin(self):
        with tempfile.TemporaryDirectory() as home:
            r = self.run_install(home, "--list")
            self.assertEqual(r.returncode, 0)
            self.assertIn("publish-check", r.stdout.split())
````



In `tests/test_marketplace.py`, replace:

````
    def test_catalog_has_no_unverifiable_fields(self):
````

with:

````
    def test_every_plugin_has_a_test_suite_a_sync_tool_and_both_readmes(self):
        for d in sorted((REPO / "plugins").iterdir()):
            with self.subTest(plugin=d.name):
                self.assertTrue((d / "tests").is_dir())
                self.assertTrue((d / "tools" / "sync.py").is_file())
                self.assertTrue((d / "README.md").is_file())
                self.assertTrue((d / "README.pt-BR.md").is_file())
                self.assertTrue((d / "CHANGELOG.md").is_file())

    def test_catalog_has_no_unverifiable_fields(self):
````


- [ ] **Step 2: Run them to verify they fail**

```bash
$PLUGIN_TESTS -p test_package.py
$ROOT_TESTS
```

Expected: plugin tests fail (`SKILL.md`, READMEs, examples and the remediation guide do not exist; `bash: .../examples/pre-push.sh: No such file or directory`); the root suite fails in `test_every_plugin_has_a_test_suite_a_sync_tool_and_both_readmes`.

- [ ] **Step 3: Create the skill, docs and examples**


Create `plugins/publish-check/skills/publish-check/SKILL.md`:

````markdown
---
name: publish-check
description: Varredura somente leitura de um repositório git (árvore e histórico completo) atrás de vazamentos antes de publicar - links de conversa do Claude, caminhos da sua máquina (/Users/<nome>), e-mails e nomes internos. Use quando o usuário for tornar algo público - criar repositório público, abrir PR para repositório público ou dar push em remoto público - ou pedir para checar vazamentos antes de publicar. Also use when the user says "publish-check", "check this repo before I publish", "scan history for leaks" or "is it safe to make this repo public". Gatilhos - /publish-check ou /publish-check:publish-check.
---

# publish-check (checagem antes de publicar)

Procura, na árvore de trabalho e em **todo o histórico git**, o que não deveria ficar público: links de conversa do Claude (`claude.ai/code/session...`, `/chat/...`, `/share/...`), caminhos da máquina de alguém (`/Users/<nome>`, `/home/<nome>`, `C:\Users\<nome>`), e-mails (texto, autor e committer) e uma lista de nomes internos do dono. É **somente leitura**: nunca altera o repositório nem reescreve histórico. Requer `python3` (stdlib) e `git`.

Não procura segredos (chaves, tokens): para isso use um scanner de segredos, como o gitleaks. Diga isso ao usuário no relatório.

## Quando usar

Antes de tornar algo público: criar um repositório público, abrir PR para um repositório público ou dar push para um remoto público. **Ofereça** rodar a checagem e **nunca bloqueie**: a decisão de publicar é do usuário. Em repositórios privados que não vão ser publicados, não ofereça.

## Fluxo

### 0. Localizar o script

O script acompanha esta skill: `${CLAUDE_SKILL_DIR}/scripts/publish_check.py`. Use-o direto, sempre com `python3 -I`.

```bash
test -f "${CLAUDE_SKILL_DIR}/scripts/publish_check.py" && echo OK || echo FALTA
```

Se `${CLAUDE_SKILL_DIR}` aparecer sem ser substituído, use no lugar dele o caminho mostrado como "Base directory for this skill" quando a skill foi carregada, escrito por extenso em cada comando.

### 1. Confirmar que o repositório vai (ou já está) público

Se não estiver claro, pergunte. Se o `gh` existir, `gh repo view --json visibility -q .visibility` mostra a visibilidade de um repositório já no GitHub. Não presuma.

### 2. Rodar

```bash
python3 -I "${CLAUDE_SKILL_DIR}/scripts/publish_check.py" <repositório>
```

Opções úteis: `--json`, `--since <data>`, `--max-commits N` (repositórios grandes), `--denylist <arquivo>` (nomes internos, um por linha, **fora** do repositório) e `--config <arquivo>`. Se existir `.publish-check.json` na raiz, ele é lido sozinho: chaves `denylist` (nomes internos) e `allow` (fingerprints de achados aceitos).

Código de saída: `0` limpo, `1` com achados, `2` erro (não é repositório git, config inválida, `git` ausente).

### 3. Apresentar

Mostre os achados agrupados por categoria, como o relatório os imprime: os valores já vêm parcialmente mascarados (`j***@dominio.dev`, `/Users/***`); **não** reproduza o valor completo em outro lugar. Diga quantos arquivos e commits foram varridos. Para cada categoria explique o que fazer, sem executar nada:

- achado só na **árvore**: editar o arquivo e commitar;
- achado no **histórico** (mensagem, autor, patch, tag): só some reescrevendo o histórico. Aponte `docs/remediation.md` (dentro do plugin), lembre de fazer backup antes e de que todos os SHAs mudam. **Nunca reescreva histórico por conta própria**, nem ofereça rodar a reescrita sem pedido explícito do usuário;
- se o relatório disser **skipped** (arquivos binários, ilegíveis ou muito grandes), esses arquivos **não foram verificados**: diga isso; se mostrar "accepted by the allow list", diga quantos achados foram aceitos e por quem (o `allow` do `.publish-check.json`);
- se o relatório avisar **shallow clone**, o resultado é parcial (só parte do histórico foi varrida): diga isso e sugira `git fetch --unshallow` antes de confiar em "limpo";
- achado que é falso positivo (um e-mail público de propósito, um caminho de exemplo): o usuário pode aceitá-lo adicionando o `fingerprint` ao `allow` de `.publish-check.json`. Só edite esse arquivo com o OK do usuário.

### 4. Fechar

Resuma: limpo, ou N achados em M categorias e o que o usuário decidiu. A decisão de publicar continua dele.

## Regras

- Somente leitura. Nunca rode comandos que reescrevem histórico (`filter-branch`, `filter-repo`) nem envie com força para o remoto.
- A lista de nomes internos (`denylist`) é sensível: se o repositório for público, mantenha-a em arquivo **fora** dele (`--denylist`), ou em `.publish-check.json` ignorado pelo git (`.gitignore` ou `.git/info/exclude`). Um `.publish-check.json` com `denylist` commitado em repositório público vaza a própria lista, e a ferramenta vai acusar isso.
- O relatório tem nomes de arquivos e mensagens de commit: trate-o como interno até o usuário decidir.
- Se `git` não existir no PATH, diga isso ao usuário em vez de tentar outra forma.
````



Create `plugins/publish-check/README.md`:

````markdown
# publish-check

A read-only scan of a git repository, **working tree and full history**, for what should not become public: Claude conversation links, absolute home paths, e-mail addresses and your own list of internal names. Run it right before a repository, branch or pull request goes public.

- **Version:** see [CHANGELOG](CHANGELOG.md) · **Requires:** `python3` (standard library only) and `git`; no network.
- **Languages:** the skill is in Portuguese; the documentation is in English ([README.pt-BR.md](README.pt-BR.md) is the Portuguese counterpart).
- **Not a secret scanner.** Keys and tokens are out of scope on purpose; use a dedicated tool such as [gitleaks](https://github.com/gitleaks/gitleaks). gitleaks does not read commit messages or author fields, which is the gap this tool fills.

## Install

```text
/plugin marketplace add dvwinck/capybara-toolbox
/plugin install publish-check@capybara-toolbox
```

Or copy the skill without the plugin system: `./install.sh publish-check` from a clone.

## What it finds

| Category | Examples |
| --- | --- |
| `session-link` | `claude.ai/code/session_...`, `claude.ai/chat/...`, `claude.ai/share/...` |
| `home-path` | `/Users/<name>`, `/home/<name>`, `C:\Users\<name>` (placeholders and CI users such as `/home/runner` are ignored) |
| `email` | addresses in text, in author and in committer fields (`noreply` and `example.*` addresses are ignored) |
| `denylist` | any internal name you list, case-insensitive |

Where it looks: tracked and non-ignored files of the working tree, plus `git log --all`: every commit message, author and committer, every added line of every patch, and annotated tags. Stash and reflog are not scanned (they are not pushed).

## Use

Ask Claude *"check this repo before I publish it"*, call `/publish-check:publish-check`, or run the script directly:

```bash
python3 -I plugins/publish-check/skills/publish-check/scripts/publish_check.py [PATH]
```

| Option | Meaning |
| --- | --- |
| `--json` | machine-readable report (`schema` 1) |
| `--since WHEN`, `--max-commits N` | limit the history scanned |
| `--denylist FILE` | internal names, one per line; keep this file **outside** the repository |
| `--config FILE` | config file (default: `.publish-check.json` in the repository, when present) |

Exit code: `0` clean, `1` findings, `2` error. On a shallow clone (for example a default CI checkout) the report warns that only part of the history was scanned; use `fetch-depth: 0` or `git fetch --unshallow`. Reported values are partly masked (`j***@acme.dev`, `/Users/***`), so the report does not leak what it finds.

### Accepting false positives

`.publish-check.json`:

```json
{
  "denylist": ["Internal-Project-Name"],
  "allow": ["0123456789abcdef"]
}
```

`allow` takes the `fingerprint` printed under each finding. A fingerprint covers category, kind of place, file (when there is one) and the value, but not the commit id: an address that is the author of every commit is accepted once, while a new value or a new file is a new finding. If the repository is public, do not commit a `denylist` (it would leak the list): use `--denylist` with a file outside the repository, or git-ignore `.publish-check.json`.

### Automating

- `examples/pre-push.sh`: a git `pre-push` hook (copy it yourself; nothing installs hooks for you).
- `examples/ci-step.yml`: a GitHub Actions step (`fetch-depth: 0` so the whole history is scanned).

## Limits

- It reads text. Binary files, and text files larger than 50 MB, are **not scanned**; the report counts them ("N files skipped") so a clean result is never silently partial. Encoded or deliberately split values (base64, a name broken over two lines) are not detected.
- Patterns are heuristic: expect to accept a few false positives, and treat "clean" as "nothing found by these four checks", not as a guarantee.
- A `.publish-check.json` inside the scanned repository is trusted: a pull request can add `allow` entries that hide findings. The report always prints how many findings the allow list accepted; in CI, prefer `--config` pointing at a file you control.
- Scanning is read-only and safe on untrusted repositories: every git call runs with `--no-optional-locks` and with `core.fsmonitor` disabled (a repository's own config could otherwise make `git ls-files` run a program), and diffs are read without external diff or textconv drivers.
- If git fails on any step the scan stops with exit code 2 instead of reporting a partial "clean".

## When something is found

publish-check never rewrites history. For findings that are already in commits, follow [docs/remediation.md](docs/remediation.md): back up first, rewrite, verify, and mind that a rewrite changes every commit id after the first changed commit.

## Develop

```bash
python3 -m unittest discover -s tests      # temporary repositories with planted leaks; needs git
python3 tools/sync.py --check              # version, manifest, changelog
```

The script's `VERSION` is the single source of truth; after changing it run `python3 tools/sync.py` and `python3 ../../tools/marketplace.py`.
````



Create `plugins/publish-check/README.pt-BR.md`:

````markdown
# publish-check

Varredura **somente leitura** de um repositório git, **árvore de trabalho e histórico completo**, atrás do que não deveria ficar público: links de conversa do Claude, caminhos absolutos da sua máquina, e-mails e a sua lista de nomes internos. Rode logo antes de um repositório, branch ou PR ficar público.

- **Versão:** veja o [CHANGELOG](CHANGELOG.md) · **Requer:** `python3` (somente biblioteca padrão) e `git`; sem rede.
- **Idiomas:** a skill está em português; a documentação principal é em inglês ([README.md](README.md)).
- **Não é um scanner de segredos.** Chaves e tokens ficam de fora de propósito; use uma ferramenta própria, como o [gitleaks](https://github.com/gitleaks/gitleaks). O gitleaks não lê mensagens de commit nem os campos de autor, que é a lacuna que esta ferramenta cobre.

## Instalação

```text
/plugin marketplace add dvwinck/capybara-toolbox
/plugin install publish-check@capybara-toolbox
```

Ou copie a skill sem o sistema de plugins: `./install.sh publish-check`, a partir de um clone.

## O que encontra

| Categoria | Exemplos |
| --- | --- |
| `session-link` | `claude.ai/code/session_...`, `claude.ai/chat/...`, `claude.ai/share/...` |
| `home-path` | `/Users/<nome>`, `/home/<nome>`, `C:\Users\<nome>` (placeholders e usuários de CI como `/home/runner` são ignorados) |
| `email` | endereços no texto, no autor e no committer (endereços `noreply` e `example.*` são ignorados) |
| `denylist` | qualquer nome interno da sua lista, sem diferenciar maiúsculas |

Onde procura: arquivos rastreados e não ignorados da árvore de trabalho, mais `git log --all`: toda mensagem de commit, autor e committer, toda linha adicionada em todo patch e as tags anotadas. Stash e reflog não são varridos (não vão no push).

## Uso

Peça ao Claude *"cheque este repositório antes de eu publicar"*, chame `/publish-check:publish-check` ou rode o script direto:

```bash
python3 -I plugins/publish-check/skills/publish-check/scripts/publish_check.py [CAMINHO]
```

| Opção | Significado |
| --- | --- |
| `--json` | relatório para máquina (`schema` 1) |
| `--since QUANDO`, `--max-commits N` | limitam o histórico varrido |
| `--denylist ARQUIVO` | nomes internos, um por linha; mantenha este arquivo **fora** do repositório |
| `--config ARQUIVO` | arquivo de config (padrão: `.publish-check.json` no repositório, se existir) |

Código de saída: `0` limpo, `1` com achados, `2` erro. Em um clone raso (por exemplo o checkout padrão do CI) o relatório avisa que só parte do histórico foi varrida; use `fetch-depth: 0` ou `git fetch --unshallow`. Os valores aparecem parcialmente mascarados (`j***@acme.dev`, `/Users/***`), para o relatório não vazar o que encontra.

### Aceitar falsos positivos

`.publish-check.json`:

```json
{
  "denylist": ["Nome-Interno-do-Projeto"],
  "allow": ["0123456789abcdef"]
}
```

`allow` recebe o `fingerprint` impresso abaixo de cada achado. O fingerprint cobre categoria, tipo de local, arquivo (quando há) e o valor, mas não o id do commit: um endereço que é o autor de todos os commits é aceito uma vez, e um valor novo ou um arquivo novo é um achado novo. Se o repositório for público, não commite uma `denylist` (ela vazaria a lista): use `--denylist` com um arquivo fora do repositório, ou ignore o `.publish-check.json` no git.

### Automatizar

- `examples/pre-push.sh`: um hook `pre-push` do git (você copia; nada instala hooks por você).
- `examples/ci-step.yml`: um passo do GitHub Actions (`fetch-depth: 0` para varrer o histórico inteiro).

## Limites

- Ele lê texto. Arquivos binários e arquivos de texto maiores que 50 MB **não são varridos**; o relatório os conta ("N files skipped"), então um resultado limpo nunca fica parcial em silêncio. Valores codificados ou propositalmente quebrados (base64, um nome dividido em duas linhas) não são detectados.
- Os padrões são heurísticos: espere aceitar alguns falsos positivos e trate "limpo" como "nada encontrado por estas quatro checagens", não como garantia.
- Um `.publish-check.json` dentro do repositório varrido é confiável por definição: um pull request pode adicionar entradas em `allow` que escondem achados. O relatório sempre mostra quantos achados a lista de aceitos absorveu; no CI, prefira `--config` apontando para um arquivo que você controla.
- A varredura é somente leitura e segura em repositórios de terceiros: todo comando git roda com `--no-optional-locks` e com `core.fsmonitor` desativado (a config do próprio repositório poderia fazer o `git ls-files` executar um programa), e os diffs são lidos sem drivers de diff externo nem de textconv.
- Se o git falhar em qualquer etapa, a varredura para com código de saída 2, em vez de relatar um "limpo" parcial.

## Quando encontrar algo

O publish-check nunca reescreve histórico. Para achados que já estão em commits, siga [docs/remediation.md](docs/remediation.md) (em inglês): faça backup, reescreva, verifique, e lembre que a reescrita muda o id de todos os commits a partir do primeiro alterado.

## Desenvolvimento

```bash
python3 -m unittest discover -s tests      # repositórios temporários com vazamentos plantados; precisa de git
python3 tools/sync.py --check              # versão, manifesto, changelog
```

O `VERSION` do script é a única fonte da versão; depois de mudá-lo rode `python3 tools/sync.py` e `python3 ../../tools/marketplace.py`.
````



Create `plugins/publish-check/docs/remediation.md`:

````markdown
# Removing findings from history

publish-check is read-only: it finds leaks but never rewrites history. This page is the manual guide for the cases it reports. **A rewrite changes every commit id from the first changed commit on, and it cannot recall copies that already exist** (forks, clones, caches, pull request refs on the host). Treat anything that was ever public as compromised and, for secrets, rotate them.

## 0. Back up first

```bash
git clone --mirror /path/to/repo /path/to/repo-backup.git
```

## 1. Findings in the working tree only

Edit the file and commit. Nothing else is needed if the value never reached a commit.

## 2. Findings in commit messages, authors or patches

Preferred tool: [git filter-repo](https://github.com/newren/git-filter-repo) (a separate install; not part of git).

- Text in file contents (home paths, e-mails, internal names): put one rule per line in `replacements.txt` (`literal==>replacement`) and run
  `git filter-repo --replace-text replacements.txt`.
- Text in commit messages (session links, trailers): `git filter-repo --replace-message replacements.txt`.
- Author or committer e-mails: write a mailmap (`New Name <new@address> <old@address>`) and run `git filter-repo --mailmap mailmap.txt`.
- A whole file that should never have been committed: `git filter-repo --invert-paths --path path/to/file`.

Without filter-repo, `git filter-branch` (shipped with git, slower, discouraged by git itself) can do the same with `--msg-filter`, `--env-filter` and `--index-filter`.

## 3. Verify

Run publish-check again on the rewritten repository; it must exit 0 (or only report findings you chose to accept). Then check tags and every branch: the scan covers all refs.

## 4. Publish the rewritten history

Rewritten history needs a forced update of a remote that already had the old one, and everyone who cloned must re-clone. On a hosting service, also remove any stale pull request refs, cached views and forks you control. For a repository that was never pushed, there is nothing to force.

## 5. Keep it from coming back

Run publish-check before each publish: see `examples/pre-push.sh` (git hook) and `examples/ci-step.yml` (GitHub Actions).
````



Create `plugins/publish-check/examples/pre-push.sh` and make it executable (`chmod +x`):

````bash
#!/usr/bin/env bash
# publish-check as a git pre-push hook (example, not installed for you).
#   cp pre-push.sh /path/to/your/repo/.git/hooks/pre-push && chmod +x /path/to/your/repo/.git/hooks/pre-push
# PUBLISH_CHECK points at the script (default: where the manual install puts it).
# PUBLISH_CHECK_MAX_COMMITS limits how much history is scanned on each push (default 200).
set -euo pipefail

SCRIPT="${PUBLISH_CHECK:-$HOME/.claude/skills/publish-check/scripts/publish_check.py}"
ROOT="$(git rev-parse --show-toplevel)"

if ! python3 -I "$SCRIPT" "$ROOT" --max-commits "${PUBLISH_CHECK_MAX_COMMITS:-200}"; then
  echo "pre-push: publish-check found leaks (or could not run); push blocked. Review the report above." >&2
  exit 1
fi
````



Create `plugins/publish-check/examples/ci-step.yml`:

````yaml
# Steps for a GitHub Actions job. fetch-depth: 0 is required so the whole history is scanned.
# The script is downloaded outside the workspace so the scan does not read the tool itself.
# Replace "main" in the URL with a release tag or commit you have vetted.
- uses: actions/checkout@v7
  with:
    fetch-depth: 0
- name: publish-check
  run: |
    curl -fsSL "https://raw.githubusercontent.com/dvwinck/capybara-toolbox/main/plugins/publish-check/skills/publish-check/scripts/publish_check.py" \
      -o "$RUNNER_TEMP/publish_check.py"
    python3 -I "$RUNNER_TEMP/publish_check.py" .
````


### Repository-level documentation


In `README.md`, replace:

````
| [CHANGELOG](plugins/ar-board/CHANGELOG.md) |
````

with:

````
| [CHANGELOG](plugins/ar-board/CHANGELOG.md) |
| [**publish-check**](plugins/publish-check) | A read-only scan of a git repository, working tree and full history, for Claude conversation links, home paths, e-mail addresses and your own internal names, to run right before something goes public. Not a secret scanner. | [CHANGELOG](plugins/publish-check/CHANGELOG.md) |
````



In `README.md`, replace:

````
/plugin install ar-board@capybara-toolbox
```

Restart Claude Code, then ask for a board
````

with:

````
/plugin install ar-board@capybara-toolbox
/plugin install publish-check@capybara-toolbox
```

Install only the plugins you want. Restart Claude Code, then ask for a board
````



In `README.pt-BR.md`, replace:

````
| [CHANGELOG](plugins/ar-board/CHANGELOG.md) |
````

with:

````
| [CHANGELOG](plugins/ar-board/CHANGELOG.md) |
| [**publish-check**](plugins/publish-check/README.pt-BR.md) | Varredura somente leitura de um repositório git, árvore e histórico completo, atrás de links de conversa do Claude, caminhos da sua máquina, e-mails e nomes internos seus, para rodar logo antes de algo ficar público. Não é um scanner de segredos. | [CHANGELOG](plugins/publish-check/CHANGELOG.md) |
````



In `README.pt-BR.md`, replace:

````
/plugin install ar-board@capybara-toolbox
```

Reinicie o Claude Code e peça
````

with:

````
/plugin install ar-board@capybara-toolbox
/plugin install publish-check@capybara-toolbox
```

Instale só os plugins que quiser. Reinicie o Claude Code e peça
````



In `CONTRIBUTING.md`, replace:

````
python3 -m unittest discover -s plugins/ar-board/tests     # ar-board suite
````

with:

````
python3 -m unittest discover -s plugins/ar-board/tests     # one plugin's suite (repeat for each plugin)
````



In `CONTRIBUTING.md`, replace:

````
python3 plugins/ar-board/tools/sync.py --check             # ar-board version, manifest, single-file variant
````

with:

````
python3 plugins/ar-board/tools/sync.py --check             # one plugin's version, manifest, generated files
````



In `CONTRIBUTING.md`, replace:

````
CI runs the same commands on every push and pull request.
````

with:

````
CI runs every plugin's suite and sync check (`plugins/*/tests`, `plugins/*/tools/sync.py`) on every push and pull request, so a new plugin needs no CI edit.
````



In `CONTRIBUTING.md`, replace:

````
3. Give the plugin its own `README.md`, `CHANGELOG.md` and `tests/`, and extend `.github/workflows/ci.yml` with its test command.
````

with:

````
3. Give the plugin its own `README.md`, `README.pt-BR.md`, `CHANGELOG.md`, `tests/` and `tools/sync.py`; CI picks them up by glob and a catalog test fails if one is missing.
````



In `CONTRIBUTING.md`, replace:

````
Never edit generated files by hand (`plugins/ar-board/dist/`).
````

with:

````
Never edit generated files by hand (for example `plugins/ar-board/dist/`).
````



In `CLAUDE.md`, replace:

````
The first (and currently only) plugin is **ar-board**: a local approve/reject web panel (Python stdlib only, no build step, no package manager, no linter).
````

with:

````
The first plugin is **ar-board**: a local approve/reject web panel; the second is **publish-check**: a read-only scan of a git repository for leaks before it goes public. Both are Python stdlib only (publish-check also needs `git`), with no build step, no package manager and no linter.
````



In `CLAUDE.md`, replace:

````
python3 -m unittest discover -s plugins/ar-board/tests    # ar-board suite
````

with:

````
python3 -m unittest discover -s plugins/ar-board/tests    # ar-board suite
python3 -m unittest discover -s plugins/publish-check/tests   # publish-check suite (builds temporary git repositories)
````



In `CLAUDE.md`, replace:

````
python3 plugins/ar-board/tools/sync.py [--check]          # sync/verify ar-board version, manifest, single-file variant
````

with:

````
python3 plugins/ar-board/tools/sync.py [--check]          # sync/verify ar-board version, manifest, single-file variant
python3 plugins/publish-check/tools/sync.py [--check]    # sync/verify publish-check version and manifest
````



In `CLAUDE.md`, replace:

````
python3 -I $S check|serve|wait|summary|build DIR          # DIR must contain batch.json (copy skills/ar-board/examples/batch.example.json)
````

with:

````
python3 -I $S check|serve|wait|summary|build DIR          # DIR must contain batch.json (copy skills/ar-board/examples/batch.example.json)
python3 -I plugins/publish-check/skills/publish-check/scripts/publish_check.py [PATH] [--json]   # scan a repository (exit 0 clean, 1 findings, 2 error)
````



In `CLAUDE.md`, replace:

````
## Keeping things consistent (non-obvious)
````

with:

````
## publish-check (second plugin)

`plugins/publish-check/skills/publish-check/scripts/publish_check.py` is the whole product: detection (`find_matches`, `mask`, `fingerprint`), git scanning (`scan_tree`, `scan_commit_metadata`, `scan_patches`, `scan_tags`), config (`load_config`) and the CLI. It never writes to the scanned repository. A fingerprint deliberately excludes the commit id (an address that authors every commit is accepted once). Test fixtures assemble their leaks at run time (string concatenation) so that scanning this repository with publish-check does not flag the tests. Its version source is the script's `VERSION`, kept in sync by `plugins/publish-check/tools/sync.py`.

## Keeping things consistent (non-obvious)
````




- [ ] **Step 4: Run the tests to verify they pass**

```bash
chmod +x plugins/publish-check/examples/pre-push.sh
$PLUGIN_TESTS
$ROOT_TESTS
python3 tools/marketplace.py --check
for t in plugins/*/tools/sync.py; do python3 "$t" --check || echo "FAILED: $t"; done
```

Expected: all suites `OK`, no `FAILED` line.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "docs(publish-check): skill, READMEs, examples and repository docs

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---


### Task 8: Acceptance on the real repository

**Files:**
- Modify: `docs/refinements/publish-check.md`, `backlog.md`
- Possibly create: `.publish-check.json` (allow list only)

This task has no new code; it proves the plugin works for real and closes the documentation loop.

- [ ] **Step 1: Validate with the real CLI and install in an isolated config**

```bash
claude plugin validate .
claude plugin validate plugins/publish-check
export CLAUDE_CONFIG_DIR="$(mktemp -d)"
claude plugin marketplace add "$PWD"
claude plugin install publish-check@capybara-toolbox
claude plugin list | grep -A4 "publish-check@"
unset CLAUDE_CONFIG_DIR
```

Expected: both validations print `Validation passed`; the install reports `Successfully installed plugin: publish-check@capybara-toolbox` and `Status: enabled`, version `0.1.0`.

- [ ] **Step 2: Scan the toolbox itself**

```bash
python3 -I plugins/publish-check/skills/publish-check/scripts/publish_check.py . --json \
  | python3 -c "import json,sys; r=json.load(sys.stdin); print(r['counts'], r['scanned'], len({f['fingerprint'] for f in r['findings']}), 'fingerprints')"
```

Expected: `session-link` 0 and `home-path` 0 (the history was cleaned before publishing); the only findings are the owner's intentionally public e-mail address (in `plugin.json` files, the catalog, `SECURITY.md` and every commit's author field) and a handful of distinct fingerprints. If anything else shows up, stop and fix it before continuing.

- [ ] **Step 3: Accept the intended e-mail once**

Only the e-mail is accepted, only by fingerprint, and the file contains no denylist (so it is safe in a public repository):

```bash
python3 -I plugins/publish-check/skills/publish-check/scripts/publish_check.py . --json \
  | python3 -c "
import json, sys
r = json.load(sys.stdin)
assert {f['category'] for f in r['findings']} == {'email'}, 'unexpected categories'
json.dump({'allow': sorted({f['fingerprint'] for f in r['findings']})}, open('.publish-check.json', 'w'), indent=2)
open('.publish-check.json', 'a').write('\n')"
python3 -I plugins/publish-check/skills/publish-check/scripts/publish_check.py .
```

Expected: `clean: no findings` and `(N accepted by the allow list)`, exit code 0.

- [ ] **Step 4: Amend the refinement and update the backlog**

In `docs/refinements/publish-check.md`: change the **P05** row so the fingerprint reads "category, kind of place, file (when there is one) and the value" and add a final section:

```markdown
## Amendments made while planning

- The fingerprint does not include the commit id (a real scan of this toolbox showed one intended e-mail producing 27 fingerprints, growing with every commit).
- Shallow clones are reported as incomplete, a failing git command is exit code 2, and files that cannot be scanned are counted in the report.
- Scanning is hardened for untrusted repositories (`core.fsmonitor` disabled, linear-time matching, hunk-count patch parsing, neutralised control characters).
```

In `backlog.md`, change the publish-check row of the Refinements table to `Built (0.1.0)`.

- [ ] **Step 5: Final verification and local merge**

```bash
$PLUGIN_TESTS
$ROOT_TESTS
python3 tools/marketplace.py --check
for t in plugins/*/tools/sync.py; do python3 "$t" --check || echo "FAILED: $t"; done
git add -A && git commit -m "docs: close publish-check, accept the owner address, update backlog

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
git log --format=%B base..HEAD | grep -c "claude.ai/code/session"
```

Expected: everything `OK`, no `FAILED`, and the last command prints `0` (no session link in any commit). Then merge locally, as the owner's workflow says, and **do not push** unless asked:

```bash
git checkout base && git merge --ff-only feat/publish-check && git branch -d feat/publish-check
```

---

## Self-Review

- **Spec coverage** (P01-P10 of the refinement): own plugin (Tasks 1, 7); four categories plus denylist (3); tree, full history, tags, `--since`/`--max-commits` (4, 6); text, JSON and exit codes (6); JSON config with `denylist`/`allow` by fingerprint (5); CLI only, panel in v2 (no task, by design); read-only, remediation printed and documented (6, 7); skill, hook and CI examples without an installer (7); skill triggers when publishing, never blocks (7); definition of done including a real scan (8).
- **Placeholders:** none. Every code block is the file as verified by running the full plan from a clean copy of `base`.
- **Type consistency:** `scan` returns `(findings, stats)`; `stats` has `files`, `commits`, `skipped` everywhere; `build_report` takes `shallow` as its fifth argument; finding dicts have the same five keys in the script, the tests and the JSON schema.
- **Out of scope (unchanged):** secrets, SARIF, panel triage, stash/reflog scanning, history rewriting, a hook installer.

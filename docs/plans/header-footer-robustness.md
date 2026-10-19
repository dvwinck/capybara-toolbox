# header-footer robustness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the header-footer bugs found in the 0.2.0 review and make the plugin safe on Windows, then release 0.3.0. Every bug below was reproduced, or confirmed in the Claude Code hooks and status line documentation, before this plan was written.

**Architecture:** All changes are in the one script, `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, plus `hooks/hooks.json` (a `matcher` on `Notification`), the tests and the docs. No new file at run time; the cache directory and `settings.json` keep their shapes (the status line entry gains `refreshInterval`).

**Tech Stack:** Python 3.9+ standard library; `unittest` with a temporary `CLAUDE_CONFIG_DIR` per test (`tests/helpers.py`).

## Root causes

| # | Symptom | Root cause | Evidence |
|---|---|---|---|
| 1 | The header disappears when a prompt is repeated within 10 min | `first_run` keys the duplicate marker on session + prompt text (a content key, not a submission key) with a 600 s TTL | Reproduced. Docs: the hook input carries `prompt_id`, a UUID per submission |
| 2 | `idle` turns into `waiting` about 60 s after a turn ends | `Notification` is registered without a `matcher`, so `idle_prompt` (and `auth_success`) also set `waiting` | Reproduced; hooks reference, Notification matchers |
| 3 | `running` (or `waiting`) stays forever after Esc or a denied permission | `Stop` does not run on a user interrupt and no hook runs on a manual denial | Hooks reference, Stop; the transcript records a user message `[Request interrupted by user]` or `[Request interrupted by user for tool use]` |
| 4 | A symlinked `settings.json` (dotfiles) becomes a regular file | `atomic_write` calls `os.replace` on the link path | Reproduced |
| 5 | A wrongly typed config value crashes the hooks (`fields: null` gives `TypeError`) | `load_config` merges values without checking their type | Reproduced |
| 6 | `state-*.json` and `tokens-*.json` pile up in the cache | Only the `hdr-*` markers are pruned | 46 files in a real cache |
| W1 | Windows: `UnicodeEncodeError` on the header and on the footer | Piped stdio uses the ANSI code page (cp1252) and `-I` ignores `PYTHONUTF8`/`PYTHONIOENCODING` | Reproduced with `PYTHONIOENCODING=cp1252` |
| W2 | Windows: hooks fail where `python3` is missing | Hooks run in Git Bash or PowerShell; the python.org installer ships no `python3.exe` | Hooks reference, command hook fields (`shell`) |
| W3 | A `header-format` that this platform's `strftime` rejects crashes the hook | The CLI only checks that the format contains `%` | `%-H` is valid on macOS/glibc, invalid on Windows |
| M1 | The status line and the wired hooks break after a Homebrew Python upgrade | `command_for` writes the versioned `sys.executable` (`/opt/homebrew/opt/python@3.15/bin/python3.15`) | Observed |

## Decisions (owner, 2026-10-19)

- Windows: fix W1 and W3, keep `python3` in `hooks/hooks.json`, and document that on Windows the hooks are installed with `wire-hooks` (absolute interpreter path, forward slashes).
- `on footer` writes `"refreshInterval": 10` into `statusLine`, so an interrupt, the `running` timer and the clock refresh without an event.
- Release 0.3.0.
- Also in scope: `settings.json` backups with microseconds and only the last 5 kept; `os.replace` retried on `PermissionError`; `status` warns when the header is on and no hook drives it (checked through `enabledPlugins` in the user `settings.json`, a documented setting, not `installed_plugins.json`).
- Out of scope: the `git branch --show-current` fallback for git older than 2.22; a `hooks.json` command that works without `python3` on Windows.

## Global Constraints

- Python 3.9 compatible, standard library only. CLI and card text stay accent-free Portuguese; docs are English with `README.pt-BR.md` keeping the same heading levels.
- Test first: every task starts with a test that fails for the reason in the table above, then the smallest fix, then the whole plugin suite.
- `hooks/hooks.json` must equal `PLUGIN_HOOKS` (and now `PLUGIN_HOOK_MATCHERS`); `tests/test_package.py` enforces it.
- The footer fields that port the Node status line stay byte-identical; only `state` changes behaviour.
- Commits authored with the repo-local address (`git config --local user.email`), ending with the single trailer `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>` (no session link: publish-check flags it). Branch `fix/header-footer-robustness` from `base`, merged locally into `base`, no push, no PR.

Suite: `python3 -m unittest discover -s plugins/header-footer/tests`.

---

### Task 1: a repeated prompt keeps its header

**Files:** `header_footer.py` (`first_run`, `MARKER_TTL`), `tests/test_header.py`.

- [ ] Tests: two submissions with the same text and different `prompt_id` both print; two runs with the same `prompt_id` print once; without `prompt_id`, the same text with a transcript that grew in between prints twice, and with the same transcript size prints once; `test_the_same_prompt_prints_only_once` still passes.
- [ ] Fix: the marker key is `[session_id, prompt_id]` when `prompt_id` is a non-empty string, else `[session_id, prompt, size of transcript_path or None]` (the hook runs before the prompt is written, so both copies of one submission see the same size). `MARKER_TTL` drops to 60 s; parallel copies run within the 5 s hook timeout.
- [ ] Commit `fix(header-footer): key the duplicate-header marker on the submission, not the prompt text`.

### Task 2: only real waits set `waiting`

**Files:** `header_footer.py` (`PLUGIN_HOOK_MATCHERS`, `wire_hooks`), `hooks/hooks.json`, `tests/test_package.py`, `tests/test_cli.py`.

- [ ] Tests: the package test also compares each group's `matcher` with `PLUGIN_HOOK_MATCHERS.get(event)`; `wire-hooks` writes the `Notification` group with that matcher and `unwire-hooks` still removes it.
- [ ] Fix: `PLUGIN_HOOK_MATCHERS = {"Notification": "permission_prompt|elicitation_dialog|elicitation_url_dialog"}`; `wire_hooks` sets `matcher` on the groups it adds; `hooks/hooks.json` gains the same matcher.
- [ ] Commit `fix(header-footer): register the waiting state only for permission and elicitation notifications`.

### Task 3: an interrupt shows `idle`

**Files:** `header_footer.py` (`render_state`, new `interrupted_since`), `tests/test_state.py`.

- [ ] Tests: state `running` since T and a transcript whose last user/assistant entry is a user message `[Request interrupted by user]` (or `... for tool use]`) stamped after T renders `idle`; the same marker stamped before T, a later assistant entry, a missing transcript or a corrupt tail keep `running`; `waiting` follows the same rule.
- [ ] Fix: `render_state(session_id, now_ts, transcript_path)` reads at most the last 64 KB of the transcript, walks the lines backwards to the latest non-sidechain `user`/`assistant` entry and reports an interrupt when that entry's text starts with `[Request interrupted by user` and its ISO `timestamp` is not older than `since`. Read-only; the next `state-hook` call rewrites the state as before.
- [ ] Commit `fix(header-footer): show idle after a user interrupt or a denied permission`.

### Task 4: a symlinked `settings.json` stays a symlink

**Files:** `header_footer.py` (`atomic_write`), `tests/test_cli.py`.

- [ ] Test: with `settings.json` a symlink to a file elsewhere, `on footer` leaves the link in place and writes the target, keeping the target's mode.
- [ ] Fix: `atomic_write` resolves the path with `os.path.realpath` before computing the mode, the temp file's folder and the `os.replace` target.
- [ ] Commit `fix(header-footer): write through a symlinked settings.json instead of replacing the link`.

### Task 5: a wrongly typed config value falls back to the default

**Files:** `header_footer.py` (`load_config`, `header_hook`, `render_footer`), `tests/test_header.py`, `tests/test_footer.py`, `tests/test_cli.py`.

- [ ] Tests: `fields: null`, `fields: "time"`, `separator: 3`, `icon: null`, `enabled: "no"` give the default value in the hooks and exit code 2 with a message naming the key in the CLI (`status`, `preview`).
- [ ] Fix: each known key must have the type of its `DEFAULTS` value (`bool`, `str`, list of `str`); a wrong one is dropped (hooks) or a `UsageError` (`strict`). Unknown keys are kept as today. As a last net, `header_hook` and `render_footer` render with `DEFAULTS` if rendering still raises.
- [ ] Commit `fix(header-footer): validate config value types so a typo never blanks the header or the footer`.

### Task 6: the cache is pruned

**Files:** `header_footer.py` (`state_hook`, new `prune_cache`, `CACHE_TTL`), `tests/test_state.py`.

- [ ] Test: on `state-hook turn`, `state-*.json` and `tokens-*.json` older than 7 days are removed and recent ones (including the current session's) stay; other events prune nothing.
- [ ] Fix: `prune_cache(now_ts)` with `CACHE_TTL = 7 * 86400`, called from `state_hook` on `turn` (once per prompt). A session resumed after 7 days recounts its tokens from the start of the transcript, which gives the same total.
- [ ] Commit `fix(header-footer): prune per-session cache files older than a week`.

### Task 7: UTF-8 stdio on every platform (W1)

**Files:** `header_footer.py` (`__main__` block), `tests/test_header.py`, `tests/test_footer.py`.

- [ ] Tests: the script run as a subprocess with `PYTHONIOENCODING=cp1252` (without `-I`, so the variable applies, which is what a Windows pipe does) exits 0 for `header-hook` and `footer`, and its stdout decodes as UTF-8 with the icon and the separator intact, including a prompt with an emoji.
- [ ] Fix: before `main`, `reconfigure(encoding="utf-8")` stdout and stderr, and stdin with `errors="replace"`, when the stream supports it.
- [ ] Commit `fix(header-footer): force UTF-8 stdio so Windows pipes do not crash the hooks`.

### Task 8: a format the platform rejects never crashes (W3)

**Files:** `header_footer.py` (`render_header`, CLI `header-format`), `tests/test_header.py`, `tests/test_cli.py`.

- [ ] Tests: `header-format "%H\0"` (rejected by `strftime` on every platform) exits 2; the same format written straight into the config renders with the default format.
- [ ] Fix: the CLI tries `datetime.now().strftime(fmt)` before saving; `render_header` falls back to the `DEFAULTS` format on `ValueError`.
- [ ] Commit `fix(header-footer): reject time formats this platform cannot render`.

### Task 9: a stable interpreter path (M1, W2)

**Files:** `header_footer.py` (new `interpreter`, `command_for`, `collect_status`), `tests/test_cli.py`.

- [ ] Tests: off Windows, when `shutil.which("python3")` resolves to the running interpreter, the wired command uses the `which` path; otherwise `sys.executable`; paths are written with forward slashes; `status` reports a wired command whose quoted interpreter path no longer exists.
- [ ] Fix: `interpreter()` as above (never `which` on Windows, where `python3` may be the Store stub); `command_for` uses `Path(...).as_posix()` for both paths; `collect_status` checks the interpreter of the `statusLine` and of our hooks.
- [ ] Commit `fix(header-footer): wire a stable interpreter path and report a missing one`.

### Task 10: status line refresh

**Files:** `header_footer.py` (`toggle`, `FOOTER_REFRESH`), `tests/test_cli.py`.

- [ ] Test: `on footer` writes `statusLine.refreshInterval == 10`.
- [ ] Fix: `FOOTER_REFRESH = 10` in the `statusLine` entry.
- [ ] Commit `feat(header-footer): refresh the footer every 10 s`.

### Task 11: settings.json backups and replace retries

**Files:** `header_footer.py` (`save_settings`, `atomic_write`), `tests/test_cli.py`.

- [ ] Tests: two saves within one second leave two backups; after seven saves only the five newest backups remain; `atomic_write` succeeds when `os.replace` raises `PermissionError` twice and then works, and re-raises after the third failure without leaving a temp file.
- [ ] Fix: backup suffix `%Y%m%d%H%M%S%f`, prune to the newest 5 by mtime; `os.replace` retried 3 times, 50 ms apart, on `PermissionError` (Windows refuses to replace a file another process holds open).
- [ ] Commit `fix(header-footer): keep distinct settings backups and retry a refused replace`.

### Task 12: status warns when no hook drives the header

**Files:** `header_footer.py` (`collect_status`), `tests/test_cli.py`.

- [ ] Tests: header on, no hook of ours in `settings.json` and no true `enabledPlugins` key starting with `header-footer@` gives a problem; either one present gives none; header off gives none.
- [ ] Fix: the check above; the message says the plugin may still be enabled in a project `settings.json`, which `status` does not read.
- [ ] Commit `feat(header-footer): status reports a header with no hook to drive it`.

### Task 13: release 0.3.0

**Files:** `header_footer.py` (`VERSION`, header comment), `CHANGELOG.md`, `README.md`, `README.pt-BR.md`, `skills/header-footer/SKILL.md` if it describes changed behaviour, generated `plugin.json` and `.claude-plugin/marketplace.json`.

- [ ] Changelog `## [0.3.0]` (Fixed: tasks 1-9, 11; Added: 10, 12); READMEs: Windows section (UTF-8, `wire-hooks`, forward slashes), macOS note (Command Line Tools or Homebrew Python), `refreshInterval`.
- [ ] `python3 plugins/header-footer/tools/sync.py`, `python3 tools/marketplace.py`, `git add -A`, doc-truth, the plugin and catalog suites, `claude plugin validate .`, publish-check on the repository.
- [ ] Commit `feat(header-footer): robustness fixes and Windows-safe I/O, release 0.3.0`; merge locally into `base`.

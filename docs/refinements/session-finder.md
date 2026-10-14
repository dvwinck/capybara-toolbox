# Refinement: session-finder

- **Status:** refined (scope closed on 2026-10-14: two critic rounds, then the owner approved all eight decisions in an ar-board panel; ready for milestone M1)
- **Date:** 2026-10-14
- **Backlog entry:** #21, still unscored (the gap check below raises its utility; scoring is left to the owner). Effort: **L as a whole; M for milestone M1 alone** (the first draft said S-M; both critics called that unrealistic).
- **Goal set by the owner:** a *very useful* iTerm2 toolbelt for people who work with an LLM (Claude Code): choose which directory is watched, filter, show each session with a quick description and, when possible, its last-update date; when a session is found, open it. The owner accepts the iTerm2 frictions (a non-stdlib registration script, a separate install step, macOS and iTerm2 only).

## Gap against what Claude Code already does

`claude --resume [id|search term]` and `/resume` already open a picker, and `-n/--name`, `--fork-session`, `--from-pr` exist (claude 2.1.296). Whether the picker searches across projects or by branch is **unverified** and must be checked before scoring. The gap this tool closes:

1. **One view across all projects and worktrees**, grouped by repository, instead of one picker per directory.
2. **A persistent panel** (the toolbelt) that stays beside the terminal, instead of a prompt you open and leave.
3. **What is running now**, so you do not resume a session already open in another tab.
4. **Recognisable rows**: a decent title, the real last-activity date, branch, PR, and chains of continued sessions collapsed to their leaf.

If a later check shows the native picker already covers 1 and 4, the tool shrinks to 2 and 3 and should be re-scored.

### Gap check result (2026-10-14, from the Claude Code docs, "Manage sessions")

- **The native picker does not list sessions created with `claude -p` or the Agent SDK, nor sessions whose first prompt was `/loop`**, and `claude --continue` skips them too; they can only be resumed by passing their id. On this machine that is 129 of 287 sessions (`sdk-py`) and 86 of the 113 touched in the last 7 days. This is the strongest gap and it confirms decision Q01 (show them).
- The picker offers search, preview (`Space`), rename (`Ctrl+R`), expand/collapse of grouped sessions and a way to widen the list; the exact scope of "widen" (all projects, branch filter) was truncated in the fetched text and stays **unverified**. The picker is a prompt that opens and closes; it is not a persistent panel and does not show which sessions are running elsewhere (agent view, `claude agents`, covers background sessions).
- `claude --resume <name>` resumes by name or generated title; `claude --resume <transcript-path>` accepts the absolute path of a `.jsonl` transcript (new fact: a possible handle that avoids filename/inner-id confusion; to evaluate in M1).
- A session from another worktree resumes in place; when its own worktree no longer exists Claude Code resumes it in the current directory. This matches the dead-home handling in this scope.
- `CLAUDE_CODE_PROJECT_DIR_NAME` (with `CLAUDE_CONFIG_DIR`) lets a host choose the project folder name, so the folder name is not always derived from the working directory: the home rule must treat a non-matching folder as "unresolved", never as an error.
- Transcripts age out under a retention sweep, so the index must tolerate files disappearing between scan and open.
- Net effect on scope: nothing is cut; the gap is larger than assumed.

## Facts measured on the owner's machine (2026-10-13/14, read-only, no transcript content read)

- `~/.claude/projects/<encoded-dir>/<session-id>.jsonl`: 287 top-level sessions (286 on the first count) in 32 project directories, 506 MB (median 0.37 MB, p90 5.8 MB, max 28 MB); 114 touched in the last 7 days. A further 1,287 nested `.jsonl` files (subagents) are not sessions a person resumes. A full parse of everything takes about 2 s; head + tail only, about 0.26 s (warm page cache). **No persistent cache is needed.**
- **Last update.** File mtime is later than the last record timestamp by more than 1 h in 79 of 276 sessions (34% counting user/assistant records) and by up to about 105 days, because resume and exit append records that carry no `timestamp` (cost-state, last-prompt, ai-title, bridge-session, ledgers). Resuming a session appends to the same file, so **opening a session from this tool would bump its mtime and reorder the list**. Only 13 of 276 files end on a timestamped record; the last line is usually `cost-state`. In 9 sessions the last timestamp is not the maximum.
- **Title.** `ai-title` exists in 269 of 286 sessions (regenerated; median 3 per session, max 368; the last one wins; a 64 KB tail read missed none). `custom-title` in 3. `agent-name` records in 33 (30 of them without a custom title). 16 sessions (5.6%) have no title of any kind. The first user record is unusable as a title in about a quarter of sessions (53 `isMeta`, 66 wrapped in a `<command-...>` tag, 7 with list content, 11 without a user record, 47 with none in the first 64 KB).
- **last-prompt.** 266 non-empty (11 empty, 1 missed); at most 1,000 characters; stale (older than the last user record) in 30 sessions.
- **Directory.** The folder name is a lossy encoding of the launch path: every non-alphanumeric character becomes `-`. The first `cwd` re-encodes to the folder name in 275 of 276 sessions; no folder was found to hold more than one distinct home (a collision stays possible but was not reproduced). 103 sessions have more than one `cwd` (a `cd`, a worktree, or a resume from elsewhere), 76 of them with a different first and last `cwd`; 27 have all `cwd` values gone from disk and 9 only some; 10 have no `cwd`; 31 were launched inside a `worktrees` directory.
- **Resume.** Verified with claude 2.1.296 in `-p` mode on a synthetic session: `claude --resume <id>` finds the session from **any** directory, resumes **in place** (the same file grows, with new records carrying the new `cwd`), and an unknown id fails at once with "No conversation found". This is how the multi-`cwd` sessions arise. Interactive mode (trust or "different directory" prompts) is unverified.
- **Running now.** `~/.claude/sessions/<pid>.json` (7 files, all pids alive) holds `sessionId`, `cwd`, `pid`, `pidDomain` (`darwin`), `procStart`, `status`, `name`, `startedAt`/`updatedAt` (epoch ms), `kind`; `procStart` (for example `Fri Oct  9 00:02:01 2026`) equals `LC_ALL=C TZ=UTC ps -o lstart= -p <pid>` in 7 of 7 cases, while `ps` in the local timezone is 3 h off, and `ps comm` is `claude` for interactive entries but `bg-spare` for `kind=bg`; next to it sit `*.key` files and a `messagingSocketPath`, which must never be read or shown. Undocumented.
- **Entrypoints and stubs.** 129 of 287 sessions are `sdk-py` (116 of the 129 `sdk-*` sessions have more than 6 records, so they are real conversations, in 23 project folders of which only 4 also hold `cli` sessions); of 113 sessions with a record in the last 7 days, 88 are `sdk-*` and 24 are `cli`. **`kind` does not exist in transcripts** (0 of 287 files); it exists only in the live registry (2 of 7 entries are `bg`). The real noise is 10 stub files (at most 378 bytes, no user or assistant record, no `cwd`, no entrypoint). One project directory holds 136 of 286 sessions.
- **Continuation.** 17 `continued-in` records, all `{type, sessionId, timestamp, continuedInSessionId}`; `sessionId` is the predecessor (equal to the file stem) and `continuedInSessionId` the successor. Clean structure (one successor per predecessor, no loops, no missing files, every chain of length 2), **but 6 of the 17 successors are empty stubs, in 11 of 11 non-empty successors the first record predates the `continued-in` timestamp (by 1 minute to 26 hours), 2 of the 7 live sessions are predecessors, and one of those is interactive and would collapse under an empty `bg` stub.** Collapsing is therefore unsafe by default.
- **Last prompt is far from EOF.** The last real user message (a `user` record that is not meta or sidechain, whose text is not a `<`-wrapper and not a `tool_result`) lies inside a 64 KB tail in only 20 of 41 recent non-sdk sessions (49%); distance from EOF: median 68 KB, p75 266 KB, p90 505 KB, max 2.9 MB. Parsing a 64 KB tail of all files takes 0.11 s, a 1 MB tail 0.63 s (warm).
- **Title-only search is not enough.** Of 41 non-sdk sessions in the last 14 days, a title-only search matches at least two words of the last real prompt in 6 (15%).
- **Branch and PR.** `gitBranch` in 277 sessions (9 with more than one); `pr-link` records (`prNumber`, `prRepository`, `prUrl`) in 13 sessions (4.5%). 2 files contain a `sessionId` different from their filename (forks/copies).
- **Environment.** claude honours `CLAUDE_CONFIG_DIR`. iTerm2 3.7.4 is installed with its API server enabled, but there is no `iterm2` Python module, no runtime and no `AutoLaunch` folder; the real path is `~/Library/Application Support/iTerm2/Scripts/AutoLaunch`. A toolbelt web-view tool is a WKWebView on a URL registered with `iterm2.tool.async_register_web_view_tool(...)`; the page cannot call iTerm2 and cannot know the focused pane's directory.

## Scope (v1)

**A new plugin `session-finder`** in `plugins/session-finder/`: one stdlib script `session_finder.py` (engine, CLI, local panel server) plus a thin iTerm2 adapter. Delivered in three milestones, each shippable and tested on its own:

- **M1, engine + CLI** (`list`, `search`, `open`, all with `--json`; skill wrapper). No server, no config file, no cache.
- **M2, local panel** (`serve`: HTTP on 127.0.0.1, token, the security contract below).
- **M3, iTerm2 toolbelt adapter** (registration script, lifecycle, `install.sh` support, docs).

### Index (read-only, never writes under the claude config directory)

- Root = `CLAUDE_CONFIG_DIR` if set, else `~/.claude`. Walk `projects/*/*.jsonl` only (`scandir`/`lstat`; skip symlinks and anything that is not a regular file). Session id = **filename stem**, validated with `re.fullmatch` as a UUID; never the `sessionId` inside records. Two files that report the same inner `sessionId` are flagged as duplicates.
- Read the head and a tail window of **1 MB, widened to 4 MB, then the whole file**, only as far as needed (the title, branch, PR and last-update fields normally resolve in the first 64 KB; the last-prompt field needs the wider window). Cold-index budget on the owner's corpus: under 2 s warm. Drop an unparseable trailing line instead of failing; drop an unparseable trailing line instead of failing. Unknown record types are ignored; every derived field may be `None` and is shown as `?`, never as a wrong value. The docs pin the claude version the format was tested against (2.1.296).
- **Last update** = the maximum `timestamp` among the last user/assistant records found in the tail, else the last record with a timestamp, else mtime. mtime is only a tie-breaker. Timestamps are parsed explicitly (`...Z` is not accepted by `fromisoformat` on Python 3.9/3.10).
- **Title** = `custom-title`, else `agent-name`, else last `ai-title`, else the text of the first non-meta user message with `<tag>` wrappers stripped and content-block lists handled, limited to 60 characters and marked `(from first prompt)`, else `(untitled)` plus branch and date.
- **Last real prompt** = the last `user` record that is not meta or sidechain and whose text is not a `<`-wrapper or a `tool_result` (not the `last-prompt` record, which is stale in 10%). **Snippet** = that text truncated to 80 characters, with control and bidi characters stripped and obvious secret shapes redacted. **Excerpts are off by default** (`--snippets`, a toggle in the panel); the text is still used for search (below). Titles and snippets are untrusted text and are length-capped in the index.
- **Home directory** of a session = its first `cwd` whose re-encoding `re.sub(r'[^A-Za-z0-9]', '-', cwd)` (ASCII only, not `str.isalnum`) equals the project folder name; a session with records but no `cwd` goes to "unresolved"; one with neither is a stub (below). Matching is lexical, by path component (never a string prefix: `/a/b` must not match `/a/bc`), with the root kept as given plus its `realpath` when it resolves. A home inside `.claude/worktrees/<name>` also matches its parent repository, when that parent path can be computed (lexically, so it works after the worktree is deleted; otherwise it stays on its own). Other `cwd` values are a secondary match ("also visited"), off by default. A home that no longer exists is computed at display time, shown dimmed with the reason and never used to filter it out.
- **Running now** = a `~/.claude/sessions/*.json` entry whose `sessionId` equals the filename stem, whose pid exists, and whose `procStart` (whitespace-normalised) equals `LC_ALL=C TZ=UTC ps -o lstart= -p <pid>`; a mismatch means not running (pid reuse). If `ps` fails or `pidDomain` is not `darwin`, show "unknown", never "running". Never match on the process name. Evaluated per request. Best effort, tolerate drift; never open `*.key` files, never expose a socket path.
- **Branch** = the last `gitBranch` seen. **PR** = the last `pr-link`, shown as `repo#number`; `prUrl` is untrusted and never rendered as a link.
- **Chains.** A session with a `continued-in` record shows a `continued` badge and the title of its successor and is **never collapsed or hidden in M1**. Collapse is opt-in (`--collapse`) and applies only when the successor has at least one user or assistant record, is not hidden and the predecessor is not running. Search always indexes collapsed members. A running session is never collapsed or hidden.
- **Noise.** Hidden by default: stubs (no user or assistant record) and live-registry entries with `kind=bg`. `sdk-*` sessions are **shown**, grouped under a collapsed "SDK / automation (N)" group per project and always included in search; `--hide-sdk` hides them. A match inside a hidden group is never lost: the result line says "N hidden matches".

### Watched directory and filters

- **Watched roots**: repeatable `--root` and an environment variable in M1; a selector in the panel (M2) with the last choice remembered in the browser; default is all projects. A config file is out of v1. The toolbelt **cannot** follow the focused pane's directory; that would need an iTerm2 API script plus shell integration and is deferred.
- **Search** (case-insensitive, all words must match) covers: title, branch, directory, the last real prompt and the first real prompt (each up to 1,000 characters). Matching happens in memory; the prompt text is never returned unless excerpts are on, and a match from prompt text only says "matched in last prompt". Full transcript bodies are never searched.
- **Filters**: `--since` (for example `7d`); `--branch`; running only; show hidden or collapsed sessions. (`--has-pr` is dropped from M1: only about 5% of sessions have a PR.) Default order: last update, newest first; grouped by repository with a collapsible count.
- **Row** (two lines, because the toolbelt is narrow): title and relative last update (absolute on hover); then directory basename, branch, PR and badges (running, continued, dead directory). Size in the detail only.

### Open

- The server or CLI receives **only a session id**. It re-resolves the session from disk at click time: home from the index, `realpath` and `isdir` checked then, not at index time.
- Action: a new tab in the current iTerm2 window with `cd -- <home> && claude --resume <id>` **written into the tab's shell** (so the tab survives `claude` exiting), through `osascript`, data passed as `argv` (`on run argv`, `quoted form of`), never interpolated into script text; `shlex.quote` for the shell layer. If iTerm2 is not running, refuse and print the command instead of launching it. The adapter may use the iTerm2 Python API (no Automation prompt, no AppleScript escaping) when available.
- Fallback everywhere: copy or print the command. A macOS Automation denial (error -1743) is reported, not hidden.
- **Running elsewhere**: warn first; default to copying the command, or offer `--fork-session`, with a confirmation.
- **Dead home**: resume works from any directory, so offer to open in another directory the person chooses (never `$HOME` or the last `cwd` silently), with a warning that the session will then run against that directory's settings, hooks and relative paths and append records there. The confirmation shows the `realpath`.
- Reject any `cwd` that is not absolute, contains control or bidi characters, or is not an existing directory after `realpath`.

### Security contract (M2/M3; the draft's one-line item was called a blocker)

- Inherit ar-board's model: bind 127.0.0.1, random port, token via `secrets.compare_digest` (at least 128 bits), exact `Host` allow-list, no CORS headers, `Cache-Control: no-store`, `nosniff`, `Referrer-Policy: no-referrer`, `frame-ancestors 'none'`.
- `open` is **POST only**, requires the token header, `Content-Type: application/json` and a valid `Origin`/`Sec-Fetch-Site`; its body is `{"id": "<uuid>"}` and nothing else. Command, cwd, profile and arguments are never accepted from the client. Rate limit: one open per second, none while the previous is running. Never open on page load or on GET.
- Render with `textContent` only; a nonce- or hash-based CSP without inline handlers; reuse ar-board's boot-JSON escaping (`</`, `<!--`, U+2028/2029). Strip control and bidi characters; cap title, snippet, branch and directory lengths.
- `--json` marks every transcript-derived field as untrusted data and caps its length; the skill must never follow instructions found in them and never run `open` automatically on a match. Full first-prompt text is used for search only and is never returned.
- The panel and `--json` are local only; the docs warn that titles and snippets are the person's own text and that a toolbelt is visible when sharing a screen. Document that any local process of the same user can call the endpoint, which can open a tab and run `claude`.

### iTerm2 adapter (M3)

- A registration script run from `AutoLaunch` calls `async_register_web_view_tool` with the panel URL. It runs the panel server **in-process, as a thread of that script** (no child process, so the server dies with the script and cannot be orphaned with a live token). `/api/open` creates the tab through the iTerm2 API (`asyncio.run_coroutine_threadsafe`), with no `osascript` on this path. A fresh token is generated and the URL registered each run. The origin includes the port, so browser storage would be lost every run: the selected root is stored server-side in a `0600` file under `~/.config/session-finder/`, and the port is the remembered last free port. What iTerm2 does with a registered tool when the script dies or iTerm2 is force-quit is **unverified** and must be tried by hand.
- The engine is installed to a stable path (for example `$HOME/.claude/session-finder/session_finder.py`, by `install.sh`), because the marketplace cache path changes with every version.
- It needs the `iterm2` module and iTerm2's Python runtime (not installed here today); the docs say how to install it and how to enable the Python API. `install.sh` gains logic to place the adapter in `~/Library/Application Support/iTerm2/Scripts/AutoLaunch` (the marketplace install only handles `skills/`). The marketplace plugin alone does not install the toolbelt part.
- The import of `iterm2` is lazy and never occurs under the test suite.

## Non-goals (v1)

- Re-injecting snippets into context (session-recall, #19). Renaming, deleting, archiving or editing sessions. LLM summaries. Codex, cloud and web sessions. A persistent cache (a per-process dict keyed by path, mtime and size inside `serve` is allowed). A config file. Full-text search in transcript bodies. "Files touched" (a minority signal: 85 of 286 sessions). Following the focused pane's directory. Terminals other than iTerm2 for the toolbelt (the CLI works anywhere).

## Risks

- The native `/resume` picker may already cover part of the value (see the gap check).
- The transcript format is undocumented and can change without notice; mitigated by tolerant parsing and a pinned tested version, not eliminated.
- Titles and snippets can contain secrets or prompt injection; mitigated by opt-in snippets, redaction, length caps and the untrusted-data marking, not eliminated.
- `claude --resume` from another directory runs that directory's project settings and hooks after claude's own trust prompt; mitigated by the confirmation, not eliminated.
- Interactive-mode resume behaviour is unverified.
- The toolbelt adapter and its install path cannot be tested in CI.

## Definition of done

**M1 (engine + CLI)** is complete when:

- `list`, `search` and `open --print` work, all with `--json` (field names, the untrusted-field marker and the exit codes of `open --print` are fixed in the first commit and documented).
- The scanner and field-derivation tests pass, plus the command-builder tests with an injected runner, and a fake `ps` runner for the running check.
- **Automated acceptance:** on the fixture corpus, and once on the owner's real corpus, `search` with two words from the last prompt returns the target in the top 3 in under 1 s; and after an injected `utime` bump (what `open` does), the order is unchanged. Ordering uses record timestamps, so after `open` and one new prompt the session moves to the top, and before the prompt it does not move.
- Skill, EN and PT-BR docs, CHANGELOG, catalog entry and the sync tools run. A real `open` in iTerm2 is a manual smoke test, not CI.

**M2 (panel)** adds: the HTTP-layer tests (token, Host, Origin, Content-Type, status codes, headers, boot escaping), the security contract above, and a test proving the real runner is unreachable under `unittest`.

**M3 (toolbelt)** adds: the adapter, the lifecycle above, `install.sh` support, the docs for enabling iTerm2's Python API, and the owner's real use on the toolbelt: starting from nothing, finding a session from last week by words from its last prompt in under 10 seconds, three times.

**Test environment (all milestones):** Linux and macOS, Python 3.9-3.13, no iTerm2, no real `claude`, no real `osascript`; paths compared through `realpath` (macOS `/private`); `iterm2` imported lazily and never under the suite.

**Fixtures** (hostile strings assembled at run time, per repo convention): an ordinary session; one ending on `cost-state`; a wrapper-first or meta-first session; content as a list; `agent-name` only; no title; stale last-prompt; a last real user record 300 KB from EOF; resumed-from-elsewhere (multi-`cwd`); no `cwd`; dead home (all and partial); stub files; encoded-folder collision; home inside a worktree path; `/a/b` versus `/a/bc`; filename id differing from inner `sessionId`; a non-UUID filename; `continued-in` with a real successor, with an empty stub successor, and with a running predecessor; `sdk-py` sessions; a nested subagent file; a corrupt line; a partial last line; invalid UTF-8; `cwd` with spaces, quotes, `$(...)`, newline, backslash and a relative path; titles with `</script>`, `<!--<script>`, `<img onerror>`, bidi and control characters and 10k characters; a symlinked `.jsonl` and a FIFO; mtime later than the last timestamp (`os.utime`); a fake `sessions/` registry with a live and a dead pid and a `bg` entry.

## Round 1 findings and what was done with them

| Finding | Source | Disposition |
| --- | --- | --- |
| mtime is the wrong "last update" (34% off, and open bumps it) | technical | Adopted: record timestamps; mtime only as tie-breaker. |
| Last record is not at EOF; take the max timestamp | technical | Adopted. |
| Title chain incomplete; first prompt is garbage in about 25% | both | Adopted: custom, agent-name, last ai-title, cleaned first prompt, then `(untitled)`. |
| Resume from another directory unverified | both | Verified by the technical critic in `-p` mode (works, in place); interactive stays unverified and is listed as a risk. |
| Directory model wrong (multi-`cwd`, dead, worktrees, collision) | both | Adopted: first `cwd` that re-encodes to the folder name, lexical component match, worktree maps to the repo, secondary `cwd` opt-in. |
| "Running now" missing | both | Adopted, with the `*.key`/socket prohibition. |
| `continued-in` chains ignored | product | Adopted: collapse to the leaf. |
| Noise from sdk/bg entrypoints, no grouping | product | Adopted: hidden by default, grouped by repository. |
| Open endpoint contract and two-layer quoting (blockers) | technical | Adopted as the security contract and the Open section. |
| XSS, CSRF, DNS rebinding, prompt injection through `--json` | technical | Adopted. |
| Last-prompt snippet is sensitive | technical | Adopted: opt-in, 80 characters, redacted. The product critic would show it by default; overruled for privacy. |
| No persistent cache | both | Adopted. |
| Honour `CLAUDE_CONFIG_DIR`; pin the tested version | technical | Adopted. |
| Toolbelt cannot know the focused pane's directory | technical | Adopted: manual selector only; follow-pane deferred. |
| iTerm2 adapter and HTTP panel are excess for v1; ship CLI only | product | **Partly overruled**: the toolbelt is the owner's stated goal, so it stays in v1, but as milestones M2 and M3 after a CLI-first M1. |
| Config file excess | product | Adopted: out of v1. |
| Effort S-M unrealistic | both | Adopted: L as a whole, M for M1. |
| Gap against `/resume` not stated | product | Adopted as the first section; the picker check is still to be done. |
| "Files touched" and transcript-body search | product | Deferred. |
| 270/276 figures in the first draft | technical | Corrected to 269 titles and 266 non-empty last prompts. |

## Round 2 findings and what was done with them

| Finding | Disposition |
| --- | --- |
| Collapsing `continued-in` chains hides empty stubs and running sessions; successors are not always newer | Adopted: badge plus successor title, never collapsed in M1; opt-in `--collapse` with guards; search keeps collapsed members. |
| The hide rule hides 78% of recent sessions (`sdk-py`), and `kind` is not in transcripts | Adopted: hide only stubs and live `bg`; show `sdk-*` grouped and searchable (owner decision 1, recommended answer applied). |
| "Metadata only" search cannot meet the acceptance test (15% title-only hit rate) and contradicts itself | Adopted: search over title, branch, directory, last and first real prompt; excerpts stay off (owner decision 2, recommended answer applied). |
| A 64 KB tail finds the last prompt in only 49% of cases | Adopted: 1 MB window, widened to 4 MB, then the file. |
| `procStart` only matches under UTC rendering; process name differs for `bg` | Adopted: `LC_ALL=C TZ=UTC ps -o lstart=`, no name match, "unknown" when `ps` fails. |
| Milestone boundaries not real; no M1 acceptance | Adopted: definition of done split per milestone. |
| Adapter lifecycle: child server can be orphaned, no channel to the iTerm2 connection, browser storage lost per port | Adopted: in-process thread, iTerm2 API for the tab, server-side root file, remembered port, stable engine path. Script-death behaviour remains unverified. |
| Directory rule wording, branch and PR sources, "open does not reorder" wording | Adopted (ASCII re-encoding regex, stubs, last `gitBranch`/`pr-link`, wording of the order test). The claim of one folder-name collision was not reproduced and was corrected. |

## Decisions (owner, 2026-10-14, ar-board panel `session-finder-scope-2026-10-14`; all eight approved, no comments)

| # | Decision |
| --- | --- |
| Q01 | `sdk-*` sessions are shown, grouped and searchable; only stubs and live `bg` entries are hidden by default. |
| Q02 | Search covers title, branch, directory, and the last and first real prompt; excerpts stay off by default. |
| Q03 | `continued-in` sessions get a badge and the successor's title; never collapsed in M1 (opt-in `--collapse` later, with guards). |
| Q04 | The iTerm2 toolbelt stays in v1, delivered as milestones M1 (engine + CLI), M2 (panel), M3 (toolbelt). |
| Q05 | M3: the panel server runs as a thread of the AutoLaunch script; engine installed at a stable path; selected root stored server-side. |
| Q06 | `open` = new tab in the current iTerm2 window with the command written into the shell; print or copy it when iTerm2 is not running; confirm and offer `--fork-session` for a running session. |
| Q07 | Check the native `/resume` picker before scoring and building: done, see the gap check result above. |
| Q08 | M1 starts on `feat/session-finder`, cut from `base` after these decisions; no push, no PR, local merge to `base` only when M1 is done. |

## Still open

- Unverified and to be tried by hand during M3: what iTerm2 does with a registered toolbelt tool when the script dies or iTerm2 is force-quit; interactive-mode `claude --resume` from another directory; the picker's exact "widen the list" scope.
- Scoring (U x A) of session-finder in the backlog table.

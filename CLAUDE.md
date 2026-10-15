# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**Capybara Toolbox** is a Claude Code plugin marketplace (`.claude-plugin/marketplace.json`, name `capybara-toolbox`). Each plugin lives in `plugins/<name>/` and is self-contained. The first plugin is **ar-board**: a local approve/reject web panel; the second is **publish-check**: a read-only scan of a git repository for leaks before it goes public; the third is **tidy-board**: stale branches, worktrees and stashes as cards on the ar-board engine, deleted only on approval; the fourth is **housekeeping**: small read-only tools (doc-truth, handoff and todo-sweep) that keep a repository and a work session honest. All are Python stdlib only (publish-check, tidy-board and housekeeping also need `git`), with no build step, no package manager and no linter. Docs are English with Portuguese counterparts; the skills (`SKILL.md`) are English, while the panel UI, the card text the tools generate and their CLI messages are Portuguese. `base` is the main branch.

## Commands

```bash
python3 -m unittest discover -s tests                     # catalog tests (repo root)
python3 -m unittest discover -s plugins/ar-board/tests    # ar-board suite
python3 -m unittest discover -s plugins/publish-check/tests   # publish-check suite (builds temporary git repositories)
python3 -m unittest discover -s plugins/tidy-board/tests      # tidy-board suite (builds temporary git repositories; about a minute)
python3 -m unittest discover -s plugins/housekeeping/tests    # housekeeping suite (builds temporary git repositories; `git add` new documents first, it also runs doc-truth on this repository)
python3 -m unittest discover -s plugins/ar-board/tests -v -k stale   # one test by name fragment
python3 tools/marketplace.py [--check]                    # sync/verify the catalog from the plugins
python3 plugins/ar-board/tools/sync.py [--check]          # sync/verify ar-board version, manifest, single-file variant
python3 plugins/publish-check/tools/sync.py [--check]    # sync/verify publish-check version and manifest
python3 plugins/tidy-board/tools/sync.py [--check]       # sync/verify tidy-board version, manifest and the vendored engine copy
python3 plugins/housekeeping/tools/sync.py [--check]     # sync/verify housekeeping version and manifest (one version for all its scripts)
claude plugin validate .                                  # validate manifests with the real CLI
./install.sh ar-board [--uninstall]                       # manual (non-marketplace) install into ~/.claude/skills

S=plugins/ar-board/skills/ar-board/scripts/ar_board.py    # the product itself
python3 -I $S check|serve|wait|summary|build DIR          # DIR must contain batch.json (copy skills/ar-board/examples/batch.example.json)
python3 -I plugins/publish-check/skills/publish-check/scripts/publish_check.py [PATH] [--json]   # scan a repository (exit 0 clean, 1 findings, 2 error)
python3 -I plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py [PATH] [--json]            # do the documents tell the truth (exit 0 clean, 1 findings, 2 error)
python3 -I plugins/housekeeping/skills/handoff/scripts/handoff.py collect|write|verify|resume [REPO]   # end-of-session note (exit 0 all verified, 1 unverified or drifted, 2 error)
python3 -I plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py scan|check|report [REPO|DIR]   # TODO/FIXME triage (the panel is capy_board.py serve DIR)
```

## Architecture (ar-board)

- **`skills/ar-board/scripts/ar_board.py` is the whole product**: validation (`validate`/`load_batch`), persistence (`Store`), HTTP server (`make_handler`), CLI (`cmd_*`) and the HTML/CSS/JS front end as the `PAGE` string (themed with the capybara mascot; `render_page` substitutes `__TITLE__`/`__BOOT__`/`__MASCOT__`/`__FAVICON__` in a single pass).
- **Agent ↔ panel channel is a file**: the server atomically writes `decisions.json` (private tmp file + `os.replace`, under `Store.lock`); `wait`/`summary` read it through `read_state`, which ignores a file from another batch/round or with a wrong shape (`valid_state`) — the agent must never act on a previous round's approvals. `batch.json` is read once at startup.
- **Round/resume logic lives in `Store.__init__`**: same `batch_id` + `round` resumes (and resets `finished`); different → the old file is archived as `decisions.r<N>[.k].json`, never overwritten. `cmd_serve` binds the port first so a busy port archives nothing.
- **Live vs offline**: `serve` talks to `/api/*` (token in the URL for GET, `X-AR-Token` for POST, `Host` must be 127.0.0.1/localhost, strict CSP); `build` makes `live=false` HTML that only uses `localStorage` and exports through Copiar (`AR-BOARD-RESULT` + JSON, a different shape from `decisions.json`).
- `Store.set_item` validates everything before touching state, so a 400 leaves no trace. `finished` resets to `false` on any item edit, but not on note edits.
- `skills/ar-board/SKILL.md` is the agent-facing contract (flow, card-quality rules, `preferences.md` format). It is lean: every command is `python3 -I "${CLAUDE_SKILL_DIR}/scripts/ar_board.py" <cmd> …` (Claude Code expands the variable to the skill's folder; the skill tells the agent to fall back to the "Base directory for this skill" path if it is not expanded). `tools/sync.py` rewrites that path to `$HOME/.claude/ar-board/ar_board.py` in the single-file variant.

## publish-check (second plugin)

`plugins/publish-check/skills/publish-check/scripts/publish_check.py` is the whole product: detection (`find_matches`, `mask`, `fingerprint`), git scanning (`scan_tree`, `scan_commit_metadata`, `scan_patches`, `scan_tags`), config (`load_config`) and the CLI. It never writes to the scanned repository. A fingerprint deliberately excludes the commit id (an address that authors every commit is accepted once). Test fixtures assemble their leaks at run time (string concatenation) so that scanning this repository with publish-check does not flag the tests. Its version source is the script's `VERSION`, kept in sync by `plugins/publish-check/tools/sync.py`.

## tidy-board (third plugin)

`plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py` is the tool and `capy_board.py` next to it is the panel: a **generated byte copy of the ar-board engine** (tidy-board stays installable on its own). Subcommands: `scan` (read-only: classifies each local branch, linked worktree and stash into proof levels P1 ancestor of the base, P2 merged PR via `gh`, P3 equivalent patch or squash, P4 unique work; writes `batch.json` plus a `scan.json` sidecar), `check`, `apply` (re-verifies each approved item at deletion time, asking `gh` again for P2 items, and never forces; writes `applied.json`) and `restore` (only for items with a backup). The engine knows nothing about git: tidy-board only uses its batch format, the additive `labels`/`confirm` fields (ar-board 1.3.0) and the `decisions.json` channel. Test fixtures build temporary git repositories (see `tests/repo_case.py`); `tests/test_apply.py` is the safety net for deletion, so extend it with any change to `apply`. Its version source is the script's `VERSION`, kept in sync by `plugins/tidy-board/tools/sync.py`.

## housekeeping (fourth plugin)

One plugin, one version, several skills added one release at a time; every script of the plugin carries the plugin's `VERSION` and a release bumps them together, which `plugins/housekeeping/tools/sync.py` enforces. The scripts are standalone (`python3 -I` does not put their folder on the path), so the few helpers they share (git wrapper, fingerprint, config loader) are duplicated on purpose. **doc-truth** (`plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py`) reads every git-tracked `.md` and reports cited paths that are not in the git tree, broken links and anchors, EN/PT-BR heading-level drift, and versions or plugin lists that disagree with the manifests; it is read-only, never runs a documented command and never uses the network. The repository's own `.doc-truth.json` excludes history (`docs/plans`, `docs/refinements`, CHANGELOGs, `backlog.md`) and the generated `dist/`, and lists run-time file names in `ignore_paths`. **handoff** (`plugins/housekeeping/skills/handoff/scripts/handoff.py`) writes `.handoff/<date>-<time>.md`: the git facts come from `collect`, and every typed citation in the agent's draft (`commit:`, `branch:`, `file:`; an untyped backtick is prose) is checked, kept and marked `[nao verificado]` when it fails; the note ends with a JSON data block that `resume` compares with the repository. `.handoff/` is git-ignored, and `collect` leaves it out of the facts so that writing a note does not change the state it records. **todo-sweep** (`plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`) finds `TODO`/`FIXME` inside comments of tracked text files, ages each with `git blame` (a repository's root commit is a blame boundary but has a real age; only a shallow clone's boundary does not), writes an ar-board batch (labels Resolver, Descartar, Manter) plus a `scan.json` sidecar, and `report` (which needs a concluded board of the current round) writes a read-only report and remembers Descartar and Manter in `.todo-sweep/ledger.json` by a hash of file, text and occurrence; it never edits a source file. `capy_board.py` next to it is a **generated byte copy of the ar-board engine** (the panel); `plugins/housekeeping/tools/sync.py` regenerates it, so after editing or releasing `ar_board.py` run the ar-board sync and then this one. `.handoff/` and `.todo-sweep/` are git-ignored, and both tools refuse such a folder when it is a symlink.

## Keeping things consistent (non-obvious)

- The script's `VERSION` is the source of truth for ar-board's version. After editing the script run `python3 plugins/ar-board/tools/sync.py` (updates `plugin.json` and regenerates `dist/ar-board-single-file.SKILL.md`) and then `python3 tools/marketplace.py` (copies version/description into the catalog). Never edit generated files by hand.
- To release: bump `VERSION` and the `# ar-board X.Y.Z -` header comment, add a `## [X.Y.Z]` entry to `plugins/ar-board/CHANGELOG.md`, then run both sync tools. `--check` (run by the tests and CI) fails on drift, on a stale header comment and on a missing changelog entry.
- The `<!-- ar-board:locate-script -->` markers in `SKILL.md` are what the single-file generator swaps for the "install the script" step; don't remove them.
- After editing any README, `SKILL.md`, `CLAUDE.md` or file under `docs/` run doc-truth (`git add` new files first: it judges the git tree); a path that only exists at run time (a file the tools write) goes in `ignore_paths` of `.doc-truth.json`, and the English and Portuguese README of a plugin keep the same heading levels.
- tidy-board vendors the engine, so after editing or releasing `ar_board.py` run the ar-board sync **and then** `python3 plugins/tidy-board/tools/sync.py` (it regenerates `capy_board.py`); CI fails on drift in either.
- The JS in `PAGE` is not executed by the suite (only string guards + WCAG checks on the palette); check UI changes in a browser.
- In-page UI strings are accent-free Portuguese by project convention (the page itself is UTF-8); card content may be any Unicode.
- `tests/helpers.py` sets `sys.dont_write_bytecode` and CI sets `PYTHONDONTWRITEBYTECODE=1`, so no `__pycache__` lands inside the plugin; `install.sh` strips caches anyway.
- `MASCOT_BODY` in the script must equal the body of `assets/logo.svg` (a test enforces it); edit the logo, then paste the compact body into the script.

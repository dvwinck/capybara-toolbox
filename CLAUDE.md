# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**Capybara Toolbox** is a Claude Code plugin marketplace (`.claude-plugin/marketplace.json`, name `capybara-toolbox`). Each plugin lives in `plugins/<name>/` and is self-contained. The first (and currently only) plugin is **ar-board**: a local approve/reject web panel (Python stdlib only, no build step, no package manager, no linter). Docs are English with Portuguese counterparts; the skill and the panel UI are Portuguese. `base` is the main branch.

## Commands

```bash
python3 -m unittest discover -s tests                     # catalog tests (repo root)
python3 -m unittest discover -s plugins/ar-board/tests    # ar-board suite
python3 -m unittest discover -s plugins/ar-board/tests -v -k stale   # one test by name fragment
python3 tools/marketplace.py [--check]                    # sync/verify the catalog from the plugins
python3 plugins/ar-board/tools/sync.py [--check]          # sync/verify ar-board version, manifest, single-file variant
claude plugin validate .                                  # validate manifests with the real CLI
./install.sh ar-board [--uninstall]                       # manual (non-marketplace) install into ~/.claude/skills

S=plugins/ar-board/skills/ar-board/scripts/ar_board.py    # the product itself
python3 -I $S check|serve|wait|summary|build DIR          # DIR must contain batch.json (copy skills/ar-board/examples/batch.example.json)
```

## Architecture (ar-board)

- **`skills/ar-board/scripts/ar_board.py` is the whole product**: validation (`validate`/`load_batch`), persistence (`Store`), HTTP server (`make_handler`), CLI (`cmd_*`) and the HTML/CSS/JS front end as the `PAGE` string (themed with the capybara mascot; `render_page` substitutes `__TITLE__`/`__BOOT__`/`__MASCOT__`/`__FAVICON__` in a single pass).
- **Agent ↔ panel channel is a file**: the server atomically writes `decisions.json` (private tmp file + `os.replace`, under `Store.lock`); `wait`/`summary` read it through `read_state`, which ignores a file from another batch/round or with a wrong shape (`valid_state`) — the agent must never act on a previous round's approvals. `batch.json` is read once at startup.
- **Round/resume logic lives in `Store.__init__`**: same `batch_id` + `round` resumes (and resets `finished`); different → the old file is archived as `decisions.r<N>[.k].json`, never overwritten. `cmd_serve` binds the port first so a busy port archives nothing.
- **Live vs offline**: `serve` talks to `/api/*` (token in the URL for GET, `X-AR-Token` for POST, `Host` must be 127.0.0.1/localhost, strict CSP); `build` makes `live=false` HTML that only uses `localStorage` and exports through Copiar (`AR-BOARD-RESULT` + JSON, a different shape from `decisions.json`).
- `Store.set_item` validates everything before touching state, so a 400 leaves no trace. `finished` resets to `false` on any item edit, but not on note edits.
- `skills/ar-board/SKILL.md` is the agent-facing contract (flow, card-quality rules, `preferences.md` format). It is lean: every command is `python3 -I "${CLAUDE_SKILL_DIR}/scripts/ar_board.py" <cmd> …` (Claude Code expands the variable to the skill's folder; the skill tells the agent to fall back to the "Base directory for this skill" path if it is not expanded). `tools/sync.py` rewrites that path to `$HOME/.claude/ar-board/ar_board.py` in the single-file variant.

## Keeping things consistent (non-obvious)

- The script's `VERSION` is the source of truth for ar-board's version. After editing the script run `python3 plugins/ar-board/tools/sync.py` (updates `plugin.json` and regenerates `dist/ar-board-single-file.SKILL.md`) and then `python3 tools/marketplace.py` (copies version/description into the catalog). Never edit generated files by hand.
- To release: bump `VERSION` and the `# ar-board X.Y.Z -` header comment, add a `## [X.Y.Z]` entry to `plugins/ar-board/CHANGELOG.md`, then run both sync tools. `--check` (run by the tests and CI) fails on drift, on a stale header comment and on a missing changelog entry.
- The `<!-- ar-board:locate-script -->` markers in `SKILL.md` are what the single-file generator swaps for the "install the script" step; don't remove them.
- The JS in `PAGE` is not executed by the suite (only string guards + WCAG checks on the palette); check UI changes in a browser.
- In-page UI strings are accent-free Portuguese by project convention (the page itself is UTF-8); card content may be any Unicode.
- `tests/helpers.py` sets `sys.dont_write_bytecode` and CI sets `PYTHONDONTWRITEBYTECODE=1`, so no `__pycache__` lands inside the plugin; `install.sh` strips caches anyway.
- `MASCOT_BODY` in the script must equal the body of `assets/logo.svg` (a test enforces it); edit the logo, then paste the compact body into the script.

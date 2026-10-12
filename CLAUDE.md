# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`ar-board` is a Claude Code **skill** (v1.0.3, docs in Portuguese): the agent writes a `batch.json` of N options, a local web panel lets the user approve/reject/maybe each one with keyboard shortcuts and comments, and the agent reads the result from `decisions.json`. Python 3 stdlib only — no build step, no package manager, no linter. Tests are `unittest` under `tests/`; the package is kept consistent by `tools/sync.py`; git repo with `base` as the main branch.

## Commands

```bash
S=scripts/ar_board.py
python3 -I $S check   DIR                 # validate DIR/batch.json (examples/ holds batch.example.json, which must be copied to <tmp>/batch.json first)
python3 -I $S serve   DIR --open          # live panel on 127.0.0.1:<random port>, prints AR-BOARD URL
python3 -I $S wait    DIR --timeout 60    # block until user clicks Concluir (exit 2 on timeout)
python3 -I $S summary DIR [--json]
python3 -I $S build   DIR                 # offline board.html (no server)
./install.sh                              # copies script -> ~/.claude/ar-board/, SKILL.md -> ~/.claude/skills/ar-board/
shasum -a 256 -c CHECKSUMS.sha256         # integrity of the package
python3 -m unittest discover -s tests -v            # whole suite
python3 -m unittest discover -s tests -v -k stale   # one test by name fragment
python3 tools/sync.py [--check]                     # keep SKILL.md/README/CHECKSUMS in sync
```

To try it manually: copy `examples/batch.example.json` to `<tmp>/batch.json`, then `check`/`serve` that dir.

## Architecture

- **`scripts/ar_board.py` is the whole product**: validation (`validate`/`load_batch`), persistence (`Store`), HTTP server (`make_handler`), CLI (`cmd_*`), and the entire HTML/CSS/JS front end as the `PAGE` string. `__TITLE__` and `__BOOT__` are substituted by `render_page`, which injects batch + state as JSON (escaping `</` and U+2028/2029).
- **Agent ↔ panel channel is a file**, not a socket: the server atomically writes `decisions.json` (tmp + `os.replace`, under `Store.lock`) on every action; `wait`/`summary` just read it. `batch.json` is read once at startup.
- **Round/resume logic lives in `Store.__init__`**: same `batch_id` + `round` resumes; different → the old file is archived as `decisions.r<N>[.k].json`, never overwritten.
- **Live vs offline**: `serve` talks to `/api/*` (token in URL for GET, `X-AR-Token` header for POST, `Host` must be 127.0.0.1/localhost, strict CSP); `build` produces `live=false` HTML that only uses `localStorage` and exports through the Copiar button (`AR-BOARD-RESULT` + JSON, a different shape from `decisions.json`).
- `wait`/`summary` read state through `read_state`, which ignores a `decisions.json` from another batch/round (the agent must never act on a previous round's approvals).
- `finished` resets to `false` on any item edit (`Store.set_item`), but not on note edits.
- `SKILL.md` is the agent-facing contract (flow, card-quality rules, preferences.md format) and tells the agent to install `~/.claude/ar-board/ar_board.py` and run it with `python3 -I`.

## Keeping the package consistent

- `scripts/ar_board.py` is the source of truth. After editing it, run `python3 tools/sync.py`: it re-embeds the script in `SKILL.md`, propagates `VERSION` into README/SKILL/install.sh, rewrites the script SHA-256 in the README and regenerates `CHECKSUMS.sha256`. `python3 tools/sync.py --check` only verifies (the test suite runs it).
- Never edit the fenced python block in `SKILL.md` by hand.
- To bump the version: change the header comment and `VERSION` in the script, add a row to the README history table by hand, then run sync (history rows are not rewritten).
- `tests/` and `tools/` are repo-only; they are not in `install.sh` or `CHECKSUMS.sha256`.
- README documents behavior in detail (API, keyboard, validation messages, security model, known limits); update the relevant section when changing behavior.
- In-page UI strings are deliberately accent-free Portuguese; card content may be any Unicode.

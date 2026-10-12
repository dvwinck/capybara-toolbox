# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`ar-board` is a Claude Code **skill** (v1.0.2, docs in Portuguese): the agent writes a `batch.json` of N options, a local web panel lets the user approve/reject/maybe each one with keyboard shortcuts and comments, and the agent reads the result from `decisions.json`. Python 3 stdlib only — no build, no package manager, no test suite, no linter, no git repo.

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
```

To try it manually: copy `examples/batch.example.json` to `<tmp>/batch.json`, then `check`/`serve` that dir.

## Architecture

- **`scripts/ar_board.py` is the whole product**: validation (`validate`/`load_batch`), persistence (`Store`), HTTP server (`make_handler`), CLI (`cmd_*`), and the entire HTML/CSS/JS front end as the `PAGE` string. `__TITLE__` and `__BOOT__` are substituted by `render_page`, which injects batch + state as JSON (escaping `</` and U+2028/2029).
- **Agent ↔ panel channel is a file**, not a socket: the server atomically writes `decisions.json` (tmp + `os.replace`, under `Store.lock`) on every action; `wait`/`summary` just read it. `batch.json` is read once at startup.
- **Round/resume logic lives in `Store.__init__`**: same `batch_id` + `round` resumes; different → the old file is archived as `decisions.r<N>[.k].json`, never overwritten.
- **Live vs offline**: `serve` talks to `/api/*` (token in URL for GET, `X-AR-Token` header for POST, `Host` must be 127.0.0.1/localhost, strict CSP); `build` produces `live=false` HTML that only uses `localStorage` and exports through the Copiar button (`AR-BOARD-RESULT` + JSON, a different shape from `decisions.json`).
- `finished` resets to `false` on any item edit (`Store.set_item`), but not on note edits.
- `SKILL.md` is the agent-facing contract (flow, card-quality rules, preferences.md format) and tells the agent to install `~/.claude/ar-board/ar_board.py` and run it with `python3 -I`.

## Keep these in sync (non-obvious)

- **`SKILL.md` embeds a literal copy of `scripts/ar_board.py`** (the fenced ```python block under "## Script", currently lines 127–792). They must stay byte-identical; check with:
  `sed -n '/^```python$/,/^```$/p' SKILL.md | sed '1d;$d' | diff - scripts/ar_board.py`
- **Version `1.0.2`** appears in the script header comment and `VERSION`, `SKILL.md` (install check `grep -q 'ar-board 1.0.2'`), `install.sh` (same grep + messages), and `README.md` (header, install check, history table). The install checks grep for the literal string `ar-board 1.0.2` in the script's header comment, so bump all of them together.
- After any change to the script, `SKILL.md`, `install.sh`, `README.md` or the example, regenerate `CHECKSUMS.sha256`, and update the script's SHA-256 quoted at the top of `README.md` (line 8).
- README documents behavior in detail (API, keyboard, validation messages, security model, known limits); update the relevant section when changing behavior.
- In-page UI strings are deliberately accent-free Portuguese (encoding simplicity); the card content itself may be any Unicode.

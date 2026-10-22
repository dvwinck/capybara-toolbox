# Changelog

All notable changes to the **ar-board** plugin are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.4.0] - 2026-10-22

### Added
- The panel speaks **English by default and pt-BR on demand**. Every user-visible string of the page (key bar, buttons, hints, dialogs, review screen, counters, completion banner) comes from an `I18N` table shipped inside the page through the boot data, so the Content-Security-Policy is unchanged and the offline `build` page switches too.
- Optional top-level **`lang`** in `batch.json` (`"en"` or `"pt-BR"`); `check` rejects any other value. A batch without `lang` opens in English.
- **`--lang en|pt-BR`** on `serve` and `build`: overrides the batch's `lang` for the language the page opens in.
- An **EN/PT toggle** in the header, next to the live/offline badge. It switches the chrome at once, sets `<html lang>` and is remembered in the browser (`localStorage` key `ar-board:lang`). Precedence: the saved toggle, then `--lang`, then the batch's `lang`, then `CAPYBARA_LANG`, then English. A saved value that is not one of the two is ignored.
- Risk levels `low`, `medium` and `high` are coloured like `baixo`, `medio` and `alto` (accents and case still ignored); the CSS classes do not change.
- **`--lang en|pt-BR` on every command** (`serve`, `wait`, `summary`, `build`, `check`) for the command-line messages, and the environment variable **`CAPYBARA_LANG`** (`en` or `pt-BR`) as the default when neither the flag nor the batch decides (any other value is ignored).

### Changed
- **The command line speaks English by default**: `check`, the validation errors, `summary` (text), `wait` and the other messages follow `--lang`, then the batch's `lang`, then `CAPYBARA_LANG`. The pt-BR text is the accent-free Portuguese of 1.3.1, except that a count of one now takes the singular (`ok: 1 item, ...`). The line tags `AR-BOARD URL:`, `AR-BOARD DECISOES:`, `AR-BOARD ARQUIVO:`, `TIMEOUT:` and `ok:` are the same in both languages; the JSON `summary` and the HTTP error bodies do not change. The `--help` text is English.
- The pt-BR wording of the panel is now written with accents (the page is UTF-8).
- Batch-level `labels` and per-item `confirm` are card content: they are shown as written and do not follow the toggle. The key letters (`A`, `R`, `M`, `S`, `C`) are the same in both languages.
- `decisions.json` and the offline `AR-BOARD-RESULT` export have the same shape as before; nothing about the language is stored in them.

## [1.3.1] - 2026-10-15

### Changed
- The `ar-board` and `question-board` SKILL.md files and their `examples/batch.example.json` files are rewritten in clear English for LLM use. Every rule, command and limit is kept. The agent now replies and writes card content in the user's language, while the panel's own UI stays in Portuguese.
- The generated single-file variants in `dist/` are English end to end: the "install the script" step 0 and the "Script" intro written by `tools/sync.py` are translated.
- Behaviour and scripts are unchanged apart from the version number.

## [1.3.0] - 2026-10-14

### Added
- Optional batch-level **`labels`** (`approve`, `reject`, `maybe`, each `{text, tone}`): custom wording for the three decisions on the buttons, key bar, state chip, counters and in the text `summary`. `tone` (`safe`, `danger`, `caution`) sets the colour of that decision, so a board where approving deletes something can paint it red. `check` validates them (unknown keys, empty or over-long text and unknown tones are rejected).
- Optional per-item **`confirm`**: the first approve press only arms the card (banner and a *Confirmar* button); a second press records the decision. Esc or navigating cancels it. Not allowed on question cards.
- Decision colours in the page go through CSS variables (`--cA`, `--cR`, `--cM` and their `-b` backgrounds) that `labels` can swap.

### Notes
- Additive: batches without `labels` or `confirm` render and summarise exactly as in 1.2.0. `decisions.json` and `summary --json` are unchanged.
- The wording and tone changes exist for the tidy-board plugin, which carries a generated copy of this engine.

## [1.2.0] - 2026-10-14

### Added
- **question-board**, a second skill in the plugin (`/ar-board:question-board`): a local form for a round of up to 8 independent questions. Each card shows its context, numbered options (keys 1-9), an optional recommended option (starred, never pre-selected) with its reason, an automatic "Outra resposta..." option, and "Preciso de mais contexto" (key M). Single choice, `multiple` choice (`min`/`max`; "Outra" counts toward `max`) and `open` text questions are supported, and mixed boards with proposal cards work.
- A review screen lists every answer before the agent is told; unanswered questions are highlighted and link back to their card.
- `summary` / `summary --json` report `answered` (with the chosen option's id and label, or the "other"/open text, and `recommended_taken`) and `unsure`, only for boards that have question cards; proposal-only output is unchanged.
- `batch.json` question cards (`choices`, `multiple`, `min`, `max`, `open`, `recommended`, `why`), validated by `check`, which also warns above 8 questions per round.
- `decisions.json` entries may carry `choice`, `choices` and `other`; `valid_state` type-checks them.
- The offline `build` variant and `Copiar` export support question cards (`kind`, `choice`, `choices`, `other`).
- `tools/sync.py` keeps `skills/question-board/scripts/ar_board.py` as a generated byte copy of the engine and generates a single-file variant per skill (`dist/question-board-single-file.SKILL.md`); `--check` fails on drift.

### Changed
- `POST /api/item` accepts `choice`, `choices`, `other` and, on question cards, only `decision: "maybe"`; a request that fails validation still leaves no trace.
- Option and focus outlines in the panel use `--mut`, not `--line` (3:1 contrast for control boundaries); new tests cover it.

### Notes
- Update both skills together: an older `ar-board` 1.1.0 single-file install shows question cards without their options.

## [1.1.0] - 2026-10-12

### Added
- Distribution as a Claude Code plugin in the Capybara Toolbox marketplace; the script now ships inside the skill (`skills/ar-board/scripts/ar_board.py`) and carries an SPDX MIT license header.
- Lean `SKILL.md` that runs the bundled script as `python3 -I "${CLAUDE_SKILL_DIR}/scripts/ar_board.py"` (with a fallback to the skill's base directory); its description now also lists English trigger phrases and both `/ar-board` and `/ar-board:ar-board`.
- A generated self-contained single-file variant (`dist/ar-board-single-file.SKILL.md`) for surfaces that accept a lone `SKILL.md`; it installs the script at `~/.claude/ar-board/ar_board.py` and its commands point there. The plugin install remains the supported route.
- Capybara-themed panel: mascot in the header, favicon, warm light/dark palette (WCAG AA checked by the test suite), `color-scheme` per theme and themed form controls (`accent-color`).
- Security regression tests (token, `Host`, `/files/` traversal and symlinks, sandboxed SVG, CSP, POST token placement, unsupported methods, page escaping, `Server` header).
- `plugin.json` declares `homepage` and `repository`; `tools/marketplace.py` copies them into the catalog entry.

### Changed
- `check`: `null` counts as omitted for every optional item key (`tag`, `image`, `meta`, `risk` and `fields`).
- `decisions.json` must have the shape the server writes (object `items`, valid `decision`/`comment` per entry, string `batch_note`, integer `round`); anything else is treated as unreadable by the server, `wait` and `summary`.
- `POST /api/finish` requires a boolean.
- Restarting the server on a finished round resets `finished` (the user must conclude again); decisions are kept.
- The page CSP adds `frame-ancestors 'none'`; the `Server` header no longer reveals the Python version.
- `python3 ar_board.py --help` shows a description.
- `install.sh` no longer copies bytecode caches (`__pycache__`, `*.pyc`).

### Fixed
- A `decisions.json` whose `round` was not an integer could turn into a bogus archive path (and abort `serve`); it is now ignored as malformed.
- Held `Enter` on a focused button no longer fires it repeatedly.
- `Limpar` waits for in-flight requests before resetting, so a late autosave cannot bring an item back.
- The empty hint line in the shortcut bar no longer takes space.

### Removed
- `CHECKSUMS.sha256` and the zip package: the marketplace/git history provides integrity.

## [1.0.3] - 2026-10-12

### Added
- Automated `unittest` suite (state and rounds, HTTP endpoints, validation, permissions, page guards, packaging) and `tools/sync.py` (embeds the script in the single-file skill, propagates the version, regenerates hashes).
- Skill step that asks the user to confirm inferred preference rules before they are applied.
- `install.sh` verifies `CHECKSUMS.sha256`.

### Changed
- `wait` and `summary` ignore a `decisions.json` that belongs to another batch or round (they used to act on stale approvals).
- Any rejected request (400) leaves the state untouched.
- `check` validates `round` (integer >= 1; a string such as `"2"` is rejected), `tag`, `image`, `meta`, `risk` and `fields`.
- `decisions.json` and `server.json` are created with mode `0600` and never follow a planted symlink.
- A busy port aborts `serve` before any round is archived.

### Fixed
- Held-down `A`/`R`/`M` (auto-repeat) no longer decides several items in a row.
- `Limpar` cancels pending autosave and clears `finished_at`.
- The panel opens on the first undecided item.
- Non-string `decision` (400), non-ASCII tokens (403) and negative `Content-Length` (400) no longer drop the connection.
- Clearing an item's decision and comment no longer leaves a stray `{"at": ...}` entry behind.

## [1.0.2] - 2026-10-12

### Fixed
- Malformed `id` answers `400` (it used to drop the connection); round archiving never overwrites existing files; `finished_at` stays coherent with `finished`; the completion banner follows comment edits; `SIGTERM` cleans `server.json`.

## [1.0.1] - 2026-10-12

### Fixed
- Pending autosaves are flushed before concluding and on `pagehide`/`visibilitychange`; long text wraps on mobile; the `GET` state read is locked.

### Added
- "Advance on decide" option with a hint on how to go back and comment.

## [1.0.0] - 2026-10-12

### Added
- First release: panel, shortcuts, autosave, `serve`/`wait`/`summary`/`build`/`check`, rounds and archiving.

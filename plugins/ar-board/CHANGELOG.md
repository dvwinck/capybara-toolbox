# Changelog

All notable changes to the **ar-board** plugin are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

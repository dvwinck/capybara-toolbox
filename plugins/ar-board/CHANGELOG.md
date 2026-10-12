# Changelog

All notable changes to the **ar-board** plugin are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-10-12

### Added
- Capybara-themed panel: mascot in the header, favicon, warm light/dark palette (WCAG AA checked by the test suite).
- Distribution as a Claude Code plugin in the Capybara Toolbox marketplace; the script now ships inside the skill (`skills/ar-board/scripts/ar_board.py`).
- Lean `SKILL.md`; a generated single-file variant (`dist/ar-board-single-file.SKILL.md`) remains for pasting into claude.ai.
- Automated `unittest` suite (state and rounds, HTTP endpoints, validation, permissions, page guards, packaging) and `tools/sync.py`.
- Skill step that asks the user to confirm inferred preference rules before they are applied.

### Changed
- `wait` and `summary` ignore a `decisions.json` that belongs to another batch or round, or that is unreadable or malformed.
- Restarting the server on a finished round resets `finished` (the user must conclude again); decisions are kept.
- `POST /api/finish` requires a boolean; any rejected request (400) leaves the state untouched.
- `check` validates `round` (integer >= 1), `tag`, `image`, `meta`, `risk` and `fields`; `null` counts as omitted for optional keys.
- `decisions.json` and `server.json` are created with mode `0600` and never follow a planted symlink.
- A busy port aborts `serve` before any round is archived.

### Fixed
- Held-down `A`/`R`/`M` (auto-repeat) no longer decides several items in a row; neither does a held `Enter` on a focused button.
- `Limpar` cancels pending autosave, waits for in-flight requests and clears `finished_at`.
- The panel opens on the first undecided item.
- Non-string `decision`, non-ASCII tokens and negative `Content-Length` no longer drop the connection.
- Clearing an item's decision and comment no longer leaves a stray `{"at": ...}` entry behind.

### Removed
- `CHECKSUMS.sha256` and the zip package: the marketplace/git history provides integrity.

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

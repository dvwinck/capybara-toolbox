# Changelog

All notable changes to the **header-footer** plugin are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-10-16

### Added
- Footer field `state`: `● running 3m` from the moment a prompt is sent (with the turn's elapsed time), `◐ waiting` while Claude waits for a permission or an answer, `○ idle` when it stops. It is fed by a new `state-hook` subcommand that the plugin registers on `UserPromptSubmit`, `PostToolUse`, `Notification`, `PermissionRequest` and `Stop`; one small file per session in the cache directory. `state` is now the first default footer field.

### Changed
- `wire-header` and `unwire-header` became `wire-hooks` and `unwire-hooks`: for installs without the plugin system they register (or remove) the whole hook set of the plugin, header and state, in `settings.json`.

## [0.1.0] - 2026-10-16

### Added
- `header_footer.py`: one script for both pieces and their CLI. Python 3.9+ standard library only.
- Header: a `UserPromptSubmit` hook (registered by the plugin's `hooks/hooks.json`) renders a line from the fields `time`, `date`, `weekday`, `dir`, `repo` and `branch` and injects it as `<reply-header>` with the instruction to copy it verbatim. When two header hooks run for the same prompt (the plugin's and an older one in `settings.json`), only the first prints.
- Footer: a status-line command with the fields `gsd`, `model`, `dir`, `branch`, `context`, `tokens`, `limits`, `cost` and `clock`, in the configured order. Session tokens are summed over the transcript incrementally (byte offset and a short ring of message ids cached per session).
- One config file, `header-footer.json` in the Claude config directory (`CLAUDE_CONFIG_DIR` is honoured), and a CLI: `status [--json]`, `on|off header|footer [--replace]`, `wire-header`, `unwire-header`, `header-fields`, `header-format [--date]`, `header-icon`, `footer-fields`, `separator`, `preview`, `fields`.
- `settings.json` is changed only through the CLI: backup first, atomic write that keeps the file mode, only its own entries; an existing status line from another tool is replaced only with `--replace`.
- `status` reports an older header hook left in `settings.json`, a stable copy older than the plugin, unknown fields, and a `gsd` field without GSD.

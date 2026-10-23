# Changelog

All notable changes to the **header-footer** plugin are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-10-23

### Added
- **The language** of the messages and of the header's weekday: English by default, pt-BR on request. `header-footer.json` takes a top-level `"lang"` (`"en"` or `"pt-BR"`), the new command `lang en|pt-BR|auto` sets or clears it, every command takes `--lang`, and the environment variable `CAPYBARA_LANG` is the default when the config has none (every Capybara Toolbox tool that speaks pt-BR reads the same variable; publish-check prints English only). The hooks take no flags: they read the config, then `CAPYBARA_LANG`.
- `status` names the language in use and where it came from (`LANGUAGE: en (default)`), lists a `CAPYBARA_LANG` that is neither `en` nor `pt-BR` as a problem (every other path ignores it) and has a `lang` key in `--json`.

### Changed
- **The default is English**: the `weekday` field shows `Mon` … `Sun` (pt-BR `seg` … `dom`), and every message of the command line (`status` and its problems, `fields`, the toggles, the errors: `error:`, pt-BR `erro:`) is English unless `lang` or `CAPYBARA_LANG` says `pt-BR`. The pt-BR text is the accent-free Portuguese of 0.3.0. The `--help` text was already English.
- The footer and the instruction that goes with the `<reply-header>` line are the same in both languages: the footer stays byte-identical to the Node status line it ports, and the instruction is addressed to the model.

## [0.3.0] - 2026-10-19

### Fixed
- The header no longer disappears when the same prompt is sent again within 10 minutes: the marker that stops a second header hook from printing is keyed on the submission (`prompt_id`, or the prompt plus the transcript size) and lives 60 seconds.
- `idle` no longer turns into `waiting` a minute after a turn ends: the `Notification` hook only listens to `permission_prompt`, `elicitation_dialog` and `elicitation_url_dialog`.
- `state` shows `idle` after an Esc interrupt or a denied permission, read from the transcript, since Claude Code runs no hook for either.
- A symlinked `settings.json` stays a symlink; the write goes to its target.
- A config value of the wrong type (`"fields": null`, a numeric separator) no longer crashes the hooks: they use the default, and the CLI exits 2 naming the key.
- Per-session state and token files older than a week are pruned from the cache.
- Windows: UTF-8 stdio whatever the code page, so the icon and the separator no longer raise `UnicodeEncodeError`; a time format the platform rejects (such as `%-H`) is refused by `header-format` and falls back to the default in the header; paths in the wired commands use forward slashes.
- `on footer` and `wire-hooks` write `python3` from the `PATH` when it is the running interpreter, instead of a versioned path that a Homebrew upgrade removes.
- `settings.json` backups carry microseconds, so two saves in one second keep two backups, and only the five newest are kept; a replace refused because another process holds the file is retried.

### Added
- `on footer` sets `refreshInterval: 10`, so the `state` timer, an interrupt and the clock refresh without an event.
- `status` reports a wired interpreter that no longer exists, and a header that is on with no hook to run it.

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

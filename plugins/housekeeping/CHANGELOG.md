# Changelog

All notable changes to the **housekeeping** plugin are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-10-14

### Added
- The second skill, **handoff** (`handoff.py`): an end-of-session note whose git facts come from git and whose citations are checked before the note is saved, and again when it is resumed.
- `collect` prints the git facts as JSON: branch, tip, upstream, commits ahead of and behind the base (`--base`, else the remote default branch, else `base`, `main`, `master`), modified and untracked files, stashes, linked worktrees and the last commits.
- Citations are typed: `` `commit:abc1234` ``, `` `branch:feat/x` `` and `` `file:path/to/f.py:42` ``; only typed spans are verified and an untyped backtick is prose. `write` takes the agent's draft, keeps every word of it, appends ` [nao verificado]` (once) after a citation that fails and saves `.handoff/AAAA-MM-DD-hhmmss.md` with the git section and a machine-readable data block; `verify` checks any note or draft.
- `resume` prints the newest note and compares it with the repository now: a moved branch tip, a changed ahead/behind count, files modified then and not now (or the reverse), stashes, and every citation again. It never acts on its own.
- Exit code 0 when every citation is verified and nothing drifted, 1 otherwise, 2 on error; `--json` has a `schema` field. Never writes outside the notes folder, never uses the network.
- All three scripts now carry the plugin version (0.2.0).

## [0.1.0] - 2026-10-14

### Added
- First release: the plugin and its first skill, **doc-truth** (`doc_truth.py`): a read-only check that what a repository's markdown documents say exists.
- Four checks over every git-tracked `.md` (minus `exclude`): paths cited in backticks and code fences exist in the git tree; relative links and `#anchors` resolve (GitHub slug rules); an `<name>.md` and its `<name>.pt-BR.md` have the same sequence of heading levels, and a `README.md` has a Portuguese counterpart; a version written next to a plugin's name matches its `plugin.json`, and the root READMEs link every plugin of the catalog.
- `.doc-truth.json` with `exclude` (globs), `ignore_paths` (globs for files created at run time) and `allow` (fingerprints of accepted findings; a fingerprint is `sha256(category|document|value)[:16]`, never the line). Unknown keys are an error.
- A readable report, `--json` with a `schema` field, exit code 0 clean, 1 findings, 2 error. It never writes to the repository, never runs a documented command and never uses the network.

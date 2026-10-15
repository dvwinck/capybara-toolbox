# Changelog

All notable changes to the **publish-check** plugin are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2026-10-15

### Changed
- `SKILL.md` rewritten in English for LLM use (the skill now tells the agent to reply in the user's language). The example files were already English. Behaviour and the script are unchanged apart from the version.

## [0.1.0] - 2026-10-12

### Added
- `publish_check.py`: read-only scan of a git repository for session links (claude.ai), home paths, e-mail addresses and an owner-supplied denylist of internal names, across the working tree (tracked and non-ignored files), every commit message, author and committer field, every patch and annotated tag on all refs.
- Readable report and `--json` (`schema` 1); exit code 0 clean, 1 findings, 2 error. Reported values are partly masked.
- `.publish-check.json` with `denylist` and `allow` (accepted findings by fingerprint), `--denylist FILE` for a list kept outside the repository, `--since` and `--max-commits`.
- Shallow clones are detected and reported as incomplete (`"shallow": true` in the JSON report).
- Hardening: e-mail detection is linear-time on huge lines; patch hunks are consumed by their line counts so content that looks like a diff header is still scanned; commit fields are NUL-delimited; a failing git command is an error (exit 2) instead of a silent "clean"; skipped files (binary, unreadable, over 50 MB) are counted in the report; control characters in snippets and locations are neutralised so a hostile repository cannot drive the terminal.
- Hardened against hostile repositories (not a sandbox): git runs with `--no-optional-locks`, `core.fsmonitor`, signature verification, lazy fetch (`protocol.allow=never`, `GIT_NO_LAZY_FETCH`), replace refs and grafts disabled, so a hostile `.git/config` cannot make the scan run a program or reach the network.
- History coverage: merge commits are compared with their first parent, files marked `binary`/`-diff` in `.gitattributes` and the root commit are scanned, the stash is excluded, and file, branch and tag names are scanned (category places `path` and `ref`).
- The report states its limits: `--since`/`--max-commits` (`limits`), shallow and partial clones (`shallow`, `partial`) and "no commits were scanned".
- Windows home paths with doubled separators or any case are found.
- Skill that offers the scan right before something is made public, plus documented `pre-push` hook and CI examples and a remediation guide.

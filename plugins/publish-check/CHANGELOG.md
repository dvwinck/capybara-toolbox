# Changelog

All notable changes to the **publish-check** plugin are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-10-12

### Added
- `publish_check.py`: read-only scan of a git repository for session links (claude.ai), home paths, e-mail addresses and an owner-supplied denylist of internal names, across the working tree (tracked and non-ignored files), every commit message, author and committer field, every patch and annotated tag on all refs.
- Readable report and `--json` (`schema` 1); exit code 0 clean, 1 findings, 2 error. Reported values are partly masked.
- `.publish-check.json` with `denylist` and `allow` (accepted findings by fingerprint), `--denylist FILE` for a list kept outside the repository, `--since` and `--max-commits`.
- Shallow clones are detected and reported as incomplete (`"shallow": true` in the JSON report).
- Hardening: e-mail detection is linear-time on huge lines; patch hunks are consumed by their line counts so content that looks like a diff header is still scanned; commit fields are NUL-delimited; a failing git command is an error (exit 2) instead of a silent "clean"; skipped files (binary, unreadable, over 50 MB) are counted in the report; control characters in snippets and locations are neutralised so a hostile repository cannot drive the terminal.
- Safe on untrusted repositories: git runs with `--no-optional-locks` and `core.fsmonitor` disabled, so a hostile `.git/config` cannot make the scan execute a program.
- Skill that offers the scan right before something is made public, plus documented `pre-push` hook and CI examples and a remediation guide.

# Changelog

All notable changes to the **housekeeping** plugin are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-10-14

### Added
- First release: the plugin and its first skill, **doc-truth** (`doc_truth.py`): a read-only check that what a repository's markdown documents say exists.
- Four checks over every git-tracked `.md` (minus `exclude`): paths cited in backticks and code fences exist in the git tree; relative links and `#anchors` resolve (GitHub slug rules); an `<name>.md` and its `<name>.pt-BR.md` have the same sequence of heading levels, and a `README.md` has a Portuguese counterpart; a version written next to a plugin's name matches its `plugin.json`, and the root READMEs link every plugin of the catalog.
- `.doc-truth.json` with `exclude` (globs), `ignore_paths` (globs for files created at run time) and `allow` (fingerprints of accepted findings; a fingerprint is `sha256(category|document|value)[:16]`, never the line). Unknown keys are an error.
- A readable report, `--json` with a `schema` field, exit code 0 clean, 1 findings, 2 error. It never writes to the repository, never runs a documented command and never uses the network.

# Refinement: publish-check

- **Status:** refined (scope closed, no open points)
- **Date:** 2026-10-12
- **Backlog entry:** #2, score 45 (U 5 x A 9), effort M.
- **How it was refined:** ten scope questions, each with context, lettered options (A recommended) and a reason, judged one by one in an ar-board panel. All ten were approved, so option A was chosen every time. No comments were left.

## What it is

A read-only scanner that checks a repository, working tree and full git history, for things that should not become public: Claude session links, absolute home paths, e-mail addresses and an owner-supplied list of internal names. It ships as its own plugin with a CLI and an agent-facing skill that offers to run it right before something is made public.

It exists because these leaks are real and the common tools miss them: gitleaks scans secrets but not commit messages (gitleaks#800 is open), and the leaks that mattered when this very repository was published lived in commit trailers, author metadata, home paths and an internal plan file.

## Decisions

| # | Topic | Decision |
| --- | --- | --- |
| P01 | Structure | Its own plugin, `plugins/publish-check`, independent of the ar-board engine. It is the first separate plugin, so it also pays for the second-plugin plumbing: its own sync check, a CI loop over `plugins/*/tests`, a catalog entry and a PT-BR README. |
| P02 | Detection | Four built-in categories plus an owner-supplied denylist: (1) claude.ai session links, (2) absolute home paths (`/Users/<name>`, `/home/<name>` and Windows equivalents), (3) e-mail addresses of authors and committers and inside text, (4) the denylist of internal names. Secrets are deliberately out of scope (use gitleaks); the report says so. |
| P03 | Where it looks | The working tree (tracked and non-ignored files) plus `git log --all`: commit messages, author and committer fields, patches, and annotated tags, on all refs. Stash and reflog are not scanned, because they are not pushed. Large repositories are bounded with `--since` and `--max-commits`. |
| P04 | Output | A readable report and `--json`. Exit code 0 = clean, 1 = findings, 2 = error. Each finding carries category, location (commit, file:line or message field) and a snippet with the sensitive value partly masked, so the report does not leak what it finds. The JSON has a `schema` field because it becomes a public contract. |
| P05 | False positives | A JSON config, `.publish-check.json`, with `denylist` and `allow` (accepted findings by fingerprint: category, commit and snippet). JSON because the CI matrix includes Python 3.9 and `tomllib` exists only from 3.11. |
| P06 | Triage | Command line only in v1. Triage in the ar-board panel (each finding as a card) is a v2. |
| P07 | Remediation | Strictly read-only: it never rewrites history. It prints guidance (filter-repo, filter-branch, back up first) but runs nothing. |
| P08 | Integration | The CLI, the agent-facing skill, and documented examples of a `pre-push` hook and a CI step. No hook installer. |
| P09 | Skill trigger | The skill offers to run when the owner is about to make something public: create a public repository, open a PR to a public repository, or push to a public remote. It proposes and never blocks. |
| P10 | Definition of done | CLI tested on temporary repositories with planted leaks in each category, in the history and in the tree; the skill; EN and PT-BR docs; catalog entry and CI; a `0.1.0` CHANGELOG entry; and one real scan of this toolbox itself. |

## Design notes derived from the decisions

- **Dependencies:** Python 3.9+ standard library and the `git` command only. No network.
- **Tests:** temporary repositories built in the test run, one planted leak per category in a past commit message, an author field, a patch and a tracked file; exit codes and JSON schema are asserted. The documented `pre-push` snippet is exercised in a temporary repository.
- **Fingerprint:** category + commit id + normalised snippet, so accepting one finding does not silently accept a new, similar one.
- **Report masking:** values are shown partly masked (for example the local part of an e-mail), because the report itself may be pasted somewhere.

## Risks

- A user may expect "everything" and assume secrets are covered. Mitigation: the report states it does not scan secrets and recommends gitleaks.
- A config file inside a public repository can leak its own denylist. Mitigation: the docs warn about it and support `--denylist` pointing at a file outside the repository.
- Full-history scans are slow on very large repositories (`--since`, `--max-commits`).
- The skill cannot know for certain that a remote is public. It must ask or check (for example `gh repo view` when available) instead of assuming.
- Documentation examples age; the hook snippet is therefore part of the package tests.
- Generalising CI and the sync tooling from one plugin to several is extra work, already counted in effort M.

## Out of scope for v1

- Secret detection.
- Triage in the ar-board panel (v2).
- SARIF output.
- Scanning stash and reflog.
- Rewriting history, or generating a rewrite script.
- A hook installer.
- Running automatically before every push.

## Discarded alternatives

- A skill inside the ar-board plugin (P01 B) or only a script under `tools/` (P01 C).
- Generic secret patterns (P02 B) or only session links and paths (P02 C).
- Scanning only the tree and the last commit (P03 B), or also stash and reflog (P03 C).
- SARIF for GitHub code scanning (P04 B) in v1; plain text only (P04 C).
- A `.publish-check-ignore` line file (P05 B); no config, flags only (P05 C).
- Panel triage in v1 (P06 B), or never (P06 C).
- Generating a rewrite script (P07 B), or running the rewrite with approval (P07 C).
- A `publish-check install-hook` command (P08 B), or the CLI alone (P08 C).
- Offering only on explicit request (P09 B), or running before every push (P09 C).
- Skipping the real scan of the toolbox (P10 B), or including SARIF and the panel in the first delivery (P10 C).

# Refinement: housekeeping (doc-truth, handoff, todo-sweep)

- **Status:** refined, awaiting the owner's review of this written spec (no plan yet)
- **Date:** 2026-10-14
- **Backlog entries:** #12 doc-truth (score 24, M), #6 handoff (score 28, S), #15 todo-sweep (score 18, S, filler).
- **How it was refined:** two rounds of the question-board, 16 questions, each with context, lettered options and a recommendation, answered in a panel. Round 1 had 8 questions, round 2 had 8 that depended on it. Of the 15 questions that had a recommendation, the owner took it in 12; the three that differed are marked below (the sixteenth was the free-text one). One free-text comment was cut off in the panel (round 1, Q02) and the owner's answer to the follow-up was to ignore it, so the plugin shape below stands.
- **Research done before asking (2026-10-14, a standard web search, summaries only):** see *Evidence and its limits*.

## What it is

One new plugin, `housekeeping`, holding three independent skills that keep a repository and a work session honest:

- **doc-truth**: a read-only static check that what the documents say exists: paths, internal links and anchors, EN/PT-BR parity, versions and plugin lists against the manifests.
- **handoff**: an end-of-session note whose git facts come from git and whose citations are checked before the note is saved, and re-checked when it is resumed.
- **todo-sweep**: a triage of `TODO`/`FIXME` comments as cards in the ar-board engine, ordered by age; the decision is recorded in a read-only report, and nothing in the code is touched.

## Decisions

| # | Topic | Decision | Owner's choice |
| --- | --- | --- | --- |
| H01 | Which items | All three go ahead (the question offered doc-truth alone as the recommendation). | differs from the recommendation |
| H02 | Packaging | One new plugin with the three skills, not one plugin per skill. Name `housekeeping`; commands are `/housekeeping:doc-truth`, `/housekeeping:handoff`, `/housekeeping:todo-sweep`. | differs on packaging (recommended: one plugin per skill); name as recommended |
| H03 | Build order | doc-truth, then handoff, then todo-sweep. The first one also creates the plugin (manifest, sync tool, CHANGELOG, READMEs in EN and PT-BR, catalog entry, CI). todo-sweep is last because it is the only one that vendors the ar-board engine. | as recommended |
| H04 | doc-truth checks | Four: referenced paths exist; EN/PT-BR parity; internal links and anchors; versions and plugin lists match the manifests. | differs (recommended: only paths and parity) |
| H05 | doc-truth output | A CLI only, read-only: a readable report, `--json` with a `schema` field, exit code 0 clean, 1 findings, 2 error. No panel. | as recommended |
| H06 | doc-truth scope | Every git-tracked `.md`, with exclusions in a config file. In this repository `docs/plans` and `docs/refinements` are excluded: they are historical and cite files and commands that changed on purpose. | as recommended |
| H07 | doc-truth false positives | `.doc-truth.json` with `exclude` (globs) and `allow` (fingerprints), like `.publish-check.json`. No marker inside the markdown. | as recommended |
| H08 | handoff storage | `.handoff/YYYY-MM-DD-hhmm.md`, one note per run, in a git-ignored folder. The most recent is the one resumed. | as recommended |
| H09 | handoff truth | The tool collects the git facts and checks every citation in the agent's text. A citation that cannot be verified is kept and marked `[nao verificado]`, never silently dropped. | as recommended |
| H10 | handoff sections | Git state; what was done; decisions and why; next steps; what failed or got stuck. Not included: a "commands to resume" section. | as recommended |
| H11 | handoff resume | Only on request ("resume the handoff"). The skill reads the newest note and re-checks every citation against the repository as it is now, listing what drifted, before acting. No session-start hook, no automatic offer. | as recommended |
| H12 | todo-sweep decision | The panel only records the decision. The result is a read-only report; the agent does not edit, remove or resolve anything. | as recommended |
| H13 | todo-sweep age | `git blame` on the comment line, capped at 300 hits per scan; hits past the cap appear without an age. | as recommended |
| H14 | todo-sweep cards | One card per TODO, oldest first, at most 20 per batch; the rest waits for the next round. | as recommended |

## Design notes derived from the decisions

These follow from the decisions and are not decisions of the owner; the plan may refine them. Each is something to check when reading.

### Common to the plugin

- Python 3.9+ standard library and `git` only. No network at all in any of the three skills.
- One version for the plugin. Each script carries `VERSION` equal to the plugin's version and the sync tool fails when the three differ, because the repository's rule is that the script's `VERSION` is the source of truth and this plugin has three scripts. (To confirm in the plan.)
- Release plan: `housekeeping` 0.1.0 = doc-truth, 0.2.0 adds handoff, 0.3.0 adds todo-sweep and the vendored engine copy.
- Docs in English with Portuguese counterparts; skills and the panel UI in Portuguese; in-page strings accent-free, per the repository convention.

### doc-truth

- Input: `git ls-files '*.md'`, minus `exclude`. Output per finding: category, document, line, the value, and a fingerprint (`sha256(category|document|value)[:16]`, no line number, so an edit above does not invalidate an accepted finding).
- Path check: tokens in backticks and in code fences that look like repository paths, and relative link targets. A token resolves against the repository root and against the document's own folder. Placeholders (`<name>`, `PATH`, `DIR`, globs) are ignored. Commands are never run.
- Parity check: for each `X.md` with an `X.pt-BR.md`, the same sequence of heading levels, and the same set of relative link targets. Headings are translated, so their text is not compared. A document with no counterpart is reported only when its sibling exists.
- Anchors: GitHub's slug rules for the heading of the target document.
- Versions and lists: a version number written next to a plugin name must equal that plugin's `plugin.json`; the plugin table of the root README must name every plugin in the catalog. (The exact rule is the loosest part of the spec; the plan must write it as testable cases.)
- Tests: temporary repositories with one planted defect per category; the CLI is also run on this repository itself as the definition of done.

### handoff

- `collect` prints the git facts as JSON: branch, upstream, commits ahead of and behind the base, the last commits, modified files, stashes, linked worktrees.
- `write` takes the agent's draft (what was done, decisions, next steps, what failed) and saves the note with the git section from `collect`.
- `verify` and `resume` use the same checks: commit ids, branch names, file paths in backticks. `resume` prints the note and, next to each citation, whether it still holds.
- `.handoff/` is not added to `.gitignore` by the tool; it says so and suggests the line, as the ar-board skill does for `.ar-board/`. Notes can name internal paths or hold pasted text, so they are local, and the skill warns not to commit them.

### todo-sweep

- Scans tracked text files (skips binary and very large files) for `TODO`, `FIXME`, `HACK` and `XXX` that sit inside a comment (after a comment leader such as `#`, `//`, `--`, `/*`, `*`, `<!--` or `;`). It is a heuristic and the README says so.
- Writes `batch.json` plus a `scan.json` sidecar into `.todo-sweep/<batch>/`, as tidy-board does, and a `report` subcommand writes the read-only result from `decisions.json`.
- Panel wording through the ar-board 1.3.0 `labels`: A Resolver, R Descartar, M Manter, with tones safe, danger and caution. (Proposed, not asked.)
- Vendors the engine as a generated copy with a byte-equality check, as tidy-board does.

## Evidence and its limits

- **doc-truth:** the backlog's objection cites a `/doctor prompt-audit` (2.1.283). A web search found no source for it; blogs say `/doctor` checks launchers, configuration, permission rules, MCP and updates. **Unconfirmed either way**: the search was US-only and in standard mode. No tool was found that checks paths, anchors and EN/PT-BR parity of a repository's documents; link checkers exist and were not examined.
- **handoff:** several community skills (for example `rb17080/session-handoff`, a handoff skill by `ostikwhy-blip`) already pull git facts first and verify claims, per their summaries. The code of none of them was read. What this one adds is a tested CLI with no network and a re-check on resume.
- **todo-sweep:** Todoctor, todo-harvest, check-fixmes and todoq already list TODO/FIXME with age from `git blame`. No evidence of demand was found. The owner chose to build it anyway; it is the lowest-value of the three and the natural one to stop after doc-truth and handoff if priorities change.

## Risks

- doc-truth false positives from prose that mentions a path as an example. Mitigation: placeholders are ignored, exclusions and `allow` are versioned, and the first definition-of-done run on this repository tunes the rules before release.
- Heuristics in two places (what counts as a path in prose; what counts as a TODO inside a comment). Mitigation: both are documented as heuristics and tested on planted cases, including the near-misses.
- handoff notes may contain internal paths or pasted text. Mitigation: local-only folder, a warning, no network.
- Three scripts in one plugin strain the "script `VERSION` is the source of truth" rule (see Common). Mitigation: a sync check across the three.
- Building all three delivers the least-demanded last; the plan should let work stop after any release.

## Out of scope for v1

- Checking external links (network) and running documented commands.
- A panel for doc-truth findings (the owner chose a CLI).
- Any edit of source files by todo-sweep: removing or resolving TODOs.
- A session-start hook or an automatic offer to resume a handoff, and a `.gitignore` editor.
- Creating issues from TODOs (needs network).
- Semantic checks that a description is accurate.

## Discarded alternatives

- One plugin per skill, or the skills inside ar-board (H02).
- doc-truth alone, or doc-truth plus handoff only (H01).
- todo-sweep first, or all three in one 0.1.0 (H03).
- doc-truth checking only paths and parity (H04); a panel or a "suggest the fix" mode (H05).
- Only README, CHANGELOG, SKILL.md and `docs/` of each plugin; only paths given on the command line (H06).
- An inline `<!-- doc-truth: ignore -->` marker, or no mechanism in v1 (H07).
- `HANDOFF.md` at the root, or the note only in the chat (H08).
- Only collecting git facts, or only checking citations (H09).
- A "commands to resume" section (H10).
- An automatic offer or a session-start hook for resuming (H11).
- The agent removing or resolving approved TODOs (H12).
- No age, or the date of the file's last commit (H13).
- One card per area or per file (H14).

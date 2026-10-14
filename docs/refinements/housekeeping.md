# Refinement: housekeeping (doc-truth, handoff, todo-sweep)

- **Status:** refined, awaiting the owner's review of this written spec (no plan yet)
- **Date:** 2026-10-14
- **Backlog entries:** #12 doc-truth (score 24, M), #6 handoff (score 28, S), #15 todo-sweep (score 18, S, filler).
- **How it was refined:** two rounds of the question-board, 16 questions, each with context, numbered options and a recommendation, answered in a panel. Round 1 had 8 questions, round 2 had 8 that depended on it. Of the 15 questions that had a recommendation, the owner took it in 12; the three that differed are marked below (the other, Q09, was a free-text question with no options). One free-text comment was cut off in the panel (round 1, Q02) and the owner's answer to the follow-up was to ignore it, so the plugin shape below stands.
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
| H02 | Packaging | One new plugin with the three skills, not one plugin per skill. Name `housekeeping` (the other names offered were `capy-desk` and `chores`); commands are `/housekeeping:doc-truth`, `/housekeeping:handoff`, `/housekeeping:todo-sweep`. | differs on packaging (recommended: one plugin per skill); name as recommended |
| H03 | Build order | doc-truth, then handoff, then todo-sweep. The first one also creates the plugin (manifest, sync tool, CHANGELOG, READMEs in EN and PT-BR, catalog entry; CI already loops over `plugins/*`). todo-sweep is last because it is the only one that vendors the ar-board engine. | as recommended |
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

These follow from the decisions and are not decisions of the owner. Every rule marked **R** is a ruling made while writing this spec to close a gap an independent review found; the owner may veto any of them (see *Rulings in this spec*).

### Common to the plugin

- Python 3.9+ standard library and `git` only. No network at all in any of the three skills.
- **R1.** Each script is standalone (`python3 -I` does not put the script's folder on the path): the small helpers (git wrapper, fingerprint, config loader) are duplicated, as publish-check and tidy-board already do, not shared through a module.
- **R2.** The plugin has one version. Each of the three scripts carries `VERSION` equal to it, and the sync tool fails when they differ; a release bumps all three (one line each). Release plan: `housekeeping` 0.1.0 = doc-truth, 0.2.0 adds handoff, 0.3.0 adds todo-sweep and the vendored engine copy.
- Plumbing the plan must include, none of it CI: the plugin's own `tools/sync.py`, manifest, CHANGELOG, READMEs in EN and PT-BR, a catalog entry, new rows in both root READMEs, a `housekeeping` section and a Commands line in `CLAUDE.md` (and its "first/second/third plugin" sentence), the backlog status and refinement rows, and `.handoff/` and `.todo-sweep/` added to this repository's `.gitignore` (the tools themselves never edit a `.gitignore`). `ci.yml` and `tests/test_marketplace.py` already loop over `plugins/*`.
- **R3.** No skill offers itself on its own. Each is called by name or by the trigger phrases in its description; unlike publish-check there is no moment that clearly calls for an offer.
- Docs in English with Portuguese counterparts; skills and the panel UI in Portuguese; in-page strings accent-free.
- Each CLI follows the publish-check pattern: a readable report, `--json` with a `schema` field, exit code 0 clean, 1 findings, 2 error, and unknown config keys rejected with exit 2. (The `schema` field and the exit codes come from that pattern, not from the owner's answer.)

### doc-truth

- Input: `git ls-files '*.md'` minus `exclude`. A finding has category, document, line, value and a fingerprint `sha256(category|document|value)[:16]` (no line number, so an edit above does not invalidate an accepted finding).
- **R4. Existence is judged against the git tree** (tracked files, and the folders they imply), not the filesystem, so a local run and CI agree. Paths that are created at run time (`.ar-board/`, `.tidy-board/`, `.handoff/`, `.todo-sweep/` and the like) are declared in `ignore_paths` in `.doc-truth.json`.
- **R5. Path check.** A token is taken from a backtick span or a line of a code fence. It counts as a path when it contains `/` or ends in a known extension (`.md .py .json .sh .yml .yaml .toml .html .svg .txt`). It is skipped when it contains `<`, `>`, `*`, `$`, `~` or `...`, starts with `/` or a URL scheme, or is a bare upper-case word (`PATH`, `DIR`). `file.py:42` loses its `:42`. Inside a shell line only the tokens that satisfy the rule above are considered. It resolves against the document's folder first, then the repository root, and passes if either exists (documents use both). Commands are never run.
- **R6. Links and anchors.** Relative link targets must exist (same rules). An anchor must match a heading of the target document using GitHub's slug: lower case, punctuation removed except `-` and `_`, spaces to `-`, accented letters kept, duplicates get `-1`, `-2`, headings inside code fences are not headings, the fragment is percent-decoded. Same-document `#x` links count; targets that are not `.md` are not anchored.
- **R7. Parity.** For each `X.md` with an `X.pt-BR.md`, the sequence of heading levels must be equal (headings are translated, so text is not compared, and fenced lines are not headings). Link sets are **not** compared: the pairs link each other and their children on purpose. A document is paired only by that naming, so `plugins/ar-board/docs/pt-BR/guia-completo.md` is out of the check. A `README.md` with no `README.pt-BR.md` next to it is a finding; any other unpaired document is not.
- **R8. Versions and lists.** In the documents under the root README, each plugin's README and `SKILL.md`, a version `X.Y.Z` on the same line as a plugin's name must equal that plugin's `plugin.json`. The plugin table of the root README must name (by link) every plugin of the catalog. `CHANGELOG.md` and `backlog.md` are history and are excluded in this repository's config.
- **R9.** `exclude` globs use `*` for a name part (not crossing `/`) and `**` for any depth, matched on the POSIX path from the repository root.
- **R10. The definition-of-done run is a work item, not a formality.** The first run on this repository will report real drift (the root README and ar-board's README already differ in heading levels with their Portuguese counterparts). The plan fixes the documents it can and accepts the rest with a reason in `.doc-truth.json`, before 0.1.0 is released.
- Tests: temporary repositories with one planted defect per category and one near-miss per rule (a placeholder, a URL, an ignored path, a duplicate heading, a translated heading, an accented anchor).

### handoff

- **R11. Typed citations.** The note grammar is explicit: a citation is a backtick span with a type, `commit:abc1234`, `branch:feat/x` or `file:path/to/f.py:42`. Only typed spans are verified; an untyped backtick is prose. This replaces guessing what a backticked word is, and the skill tells the agent to write citations this way. It is the one change to how the agent writes that this spec asks for.
- **R12. Checks.** `commit:` is a hex id of 7 to 40 characters verified with `git rev-parse --verify --quiet <id>^{commit}` (existence, not reachability). `branch:` must match an existing local or remote-tracking branch. `file:` is relative to the repository root and must exist in the working tree. A citation that fails is kept in the note and followed by `[nao verificado]`; the marker is added once (a note is never rewritten twice) and nothing is removed.
- `collect` prints git facts as JSON: branch, upstream, tip, commits ahead of and behind the base, the last commits, modified files, stashes, linked worktrees. The base is detected as tidy-board does it (`--base`, then the remote default branch, then `base`, `main`, `master`).
- `write` takes the agent's draft (done, decisions, next steps, failed), runs the checks, and saves the note with the `collect` section. The note ends with a machine-readable footer (a JSON block in an HTML comment) holding that `collect` output.
- **R13. Drift on resume.** `resume` prints the newest note and compares it with the repository now: a branch whose tip moved, a changed ahead/behind count, files modified then and not now (or the reverse), and every citation re-checked. Each difference is listed; it never acts on its own.
- **R14. File name.** `.handoff/YYYY-MM-DD-hhmmss.md` in local time, with `-2`, `-3` on a collision; the newest is the greatest name.
- `.handoff/` is not added to `.gitignore` by the tool, which says so. Notes can hold internal paths or pasted text, so they are local and the skill warns not to commit them. Exit codes: 0 all citations verified, 1 some unverified, 2 error.
- Tests: temporary repositories; each citation type true, false, and renamed since; a moved branch tip on resume; two notes in the same second; the footer round trip.

### todo-sweep

- **R15. What is a TODO.** `TODO` and `FIXME`, upper case, as whole words, in a comment: a line that starts (after spaces) with a comment leader (`#`, `//`, `--`, `/*`, `*`, `;`) followed by the marker, or a trailing ` #` or ` //` comment followed by the marker. `HACK` and `XXX`, which an earlier draft of this spec listed, are out: the backlog and the owner's options said TODO and FIXME. Markdown files are not scanned (bullets and prose mention TODO). Binary files and files over 1 MB are skipped. It is a heuristic and the README says so.
- **R16. Age.** `git blame --porcelain` on the line, author time; it is the age of the line's last change, not of the TODO's first appearance (a reformat resets it). Uncommitted lines and boundary commits of a shallow clone have no age and are reported as such (the scan says when the clone is shallow). The cap is a flag, `--max-blame`, default 300; which hits are blamed is the order the files are listed; hits past the cap come after the aged ones, marked "sem idade", and the scan prints how many.
- **R17. Rounds.** A TODO is identified by `sha256(file|text)[:16]`. `report` appends each Manter and Descartar decision to `.todo-sweep/ledger.json`, and `scan` skips those ids, so round 2 offers the next 20 and not the same ones. Resolver decisions are not stored: a TODO the owner wants resolved stays until it disappears from the code. (This store is new; it is not in the owner's decisions.)
- **R18. The report.** `report` requires a concluded board for the current round (like tidy-board's `apply`) and writes `report.md` and `report.json` into the batch folder, with the file and the line as of the scan. It never edits a source file.
- **R19. Labels.** Through ar-board 1.3.0 `labels`: approve = Resolver (tone safe), reject = Descartar (danger), maybe = Manter (caution).
- Writes `batch.json` and a `scan.json` sidecar into `.todo-sweep/<batch>/`, as tidy-board does, and vendors the engine as a generated copy with a byte-equality check.
- Tests: planted TODOs and near-misses (`TODOS`, `todo`, a TODO inside a string, a markdown bullet); blame ages including an uncommitted line; the cap; the ledger skipping decided ids; `report` refusing an unfinished board.

## Definition of done, per skill

- **doc-truth:** CLI tested on temporary repositories as above; the skill; EN and PT-BR docs; the plumbing list; a real run on this repository whose findings are fixed or accepted (R10); the 0.1.0 CHANGELOG entry.
- **handoff:** `collect`, `write`, `verify`, `resume` tested as above; the skill, with the citation grammar; docs; a real note written and resumed in this repository; the 0.2.0 entry.
- **todo-sweep:** `scan`, `report`, the vendored engine and its `--check`; the panel checked in a browser; a real scan of this repository; the 0.3.0 entry.

## Evidence and its limits

- **doc-truth:** the backlog's objection cites a `/doctor prompt-audit` (2.1.283). A web search found no source for it; blogs say `/doctor` checks launchers, configuration, permission rules, MCP and updates. **Unconfirmed either way**: the search was US-only and in standard mode. No tool was found that checks paths, anchors and EN/PT-BR parity of a repository's documents; link checkers exist and were not examined.
- **handoff:** several community skills (for example `rb17080/session-handoff`, a handoff skill by `ostikwhy-blip`) already pull git facts first and verify claims, per their summaries. The code of none of them was read. What this one adds is a tested CLI with no network and a re-check on resume.
- **todo-sweep:** Todoctor, todo-harvest, check-fixmes and todoq already list TODO/FIXME with age from `git blame`. No evidence of demand was found. The owner chose to build it anyway; it is the lowest-value of the three and the natural one to stop after doc-truth and handoff if priorities change.

## Risks

- doc-truth false positives from prose that mentions a path as an example. Mitigation: placeholders are ignored, exclusions and `allow` are versioned, and the first definition-of-done run on this repository tunes the rules before release.
- Heuristics in two places (what counts as a path in prose; what counts as a TODO inside a comment). Mitigation: rules R5 and R15 are written as testable cases, both are documented as heuristics, and tests include the near-misses.
- handoff notes may contain internal paths or pasted text. Mitigation: local-only folder, a warning, no network.
- Three scripts in one plugin strain the "script `VERSION` is the source of truth" rule. Mitigation: R2, a sync check that the three are equal.
- The parity rule is only as good as the documents' structure: this repository's own pairs already differ (R10).
- Citation typing (R11) depends on the agent writing `commit:`, `branch:` and `file:` spans; a note without them verifies nothing. The skill must say so and `write` should report how many citations it found.
- Building all three delivers the least-demanded last; the plan should let work stop after any release.

## Out of scope for v1

- Checking external links (network) and running documented commands.
- A panel for doc-truth findings (the owner chose a CLI).
- Any edit of source files by todo-sweep: removing or resolving TODOs.
- A session-start hook or an automatic offer to resume a handoff, and a `.gitignore` editor.
- Creating issues from TODOs (needs network).
- Semantic checks that a description is accurate.

## Discarded alternatives

- One plugin per skill, or the skills inside ar-board (H02); the names `capy-desk` and `chores`.
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

## Rulings in this spec

The owner decided H01 to H14. Everything marked R above is a ruling by the author of this spec, made after an independent review found gaps; the cost of each being wrong is small and it can be reversed in the plan. The ones worth a look before a plan is written:

- **R7, R10:** parity compares heading levels only, and the plan fixes this repository's real drift, or accepts it with a reason, before 0.1.0.
- **R11:** handoff citations are typed (`commit:`, `branch:`, `file:`). Cost if wrong: an agent that forgets the type gets nothing verified.
- **R17:** todo-sweep keeps a `ledger.json` of Manter and Descartar decisions. Cost if wrong: a decision persisted that the owner did not ask for; removing it means round 2 re-offers decided TODOs.
- **R15:** only `TODO` and `FIXME`; no `HACK` or `XXX`.
- **R2:** three scripts with one version, bumped together.

## Open doubts

- Whether `/doctor` in Claude Code audits documents (see *Evidence and its limits*); it does not change the decisions, only how new doc-truth is.
- Whether the handoff note format should anticipate a future `/handoff` in Claude Code itself.
- `git blame` cost on large repositories; the cap is the only guard.

# Backlog

What the Capybara Toolbox may still build, and what has already been decided. Decisions below were taken on **2026-10-12** by the owner, one card at a time, in an ar-board approve/reject panel. No comments were left on the cards, so rejections carry no stated reason; the "main objection" column is the reviewers' strongest counter-argument, not the owner's.

## How the candidates were ranked

- **Score = U x A.** U (utility, 1-10) is judged against the whole market of Claude Code skills, plugins and agents (demand, frequency, saturation), not against what any one person has installed. A (alignment, 1-10) is fit with the toolbox principles: calm, human in the loop, Python stdlib only, offline, testable in CI, safe by default, installable as a plugin.
- Three market scouts (supply, demand, adjacent ecosystems) fed a draft; two critic/reviewer iterations corrected it against live issue states, the Claude Code changelog and incumbent projects. The ranking is stable; positions 15-20 are explicitly filler.
- **The score orders the work, it does not filter it:** five of the six filler items were approved anyway.

## Decisions

| Decision | Skills |
| --- | --- |
| **Approved (14)** | diff-board, publish-check, question-board, tidy-board, commit-groups, handoff, memory-board, doc-truth, safety-net, todo-sweep, calm-mode, loadout-board, session-recall, issue-triage-board |
| **Maybe (1)** | variant-board (undecided; revisit in the next round) |
| **Rejected (5)** | review-map, skill-check, settings-doctor, changelog-keeper, guard-recipes |

## Full list

Effort: S = days, M = about a week, L = several weeks. "Filler" means score 18 or below.

| # | Skill | Status | U | A | Score | Effort | What it does |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | diff-board | Approved | 6 | 8 | 48 | L | End-of-turn, cross-file review: the agent keeps or reverts only the hunks you approve, in edits already applied. |
| 2 | publish-check | Approved | 5 | 9 | 45 | M | Read-only scan of the tree and `git log --all` (messages, trailers, author emails, patches) for session links, home paths, emails and internal names. |
| 3 | question-board | Approved | 4 | 9 | 36 | S | A round of clarifying questions answered in one form: one card per question, with the recommended answer. |
| 4 | tidy-board | Approved | 4 | 9 | 36 | M | Stale branches and worktrees as cards; approving means deleting. |
| 5 | commit-groups | Approved | 4 | 8 | 32 | M | Splits a dirty tree into atomic commit groups, approved one by one. |
| 6 | handoff | Approved | 4 | 7 | 28 | S | End-of-session note whose branches, commits and paths are verified to exist before it is written. |
| 7 | review-map | Rejected | 4 | 7 | 28 | S | Risk-ordered map of an agent diff, as a read-only CLI. |
| 8 | skill-check | Rejected | 4 | 7 | 28 | M | Offline lint of SKILL.md and plugin.json, plus an advisory pre-install check. |
| 9 | settings-doctor | Rejected | 4 | 7 | 28 | M | Read-only lint of settings.json permission rules and hook/MCP config. |
| 10 | changelog-keeper | Rejected | 3 | 9 | 27 | S | Keep-a-Changelog lines from commits since the last tag, approved before writing. |
| 11 | memory-board | Approved | 3 | 8 | 24 | S | Keep / archive / edit verdicts for memory files, in one batch. |
| 12 | doc-truth | Approved | 3 | 8 | 24 | M | Static check that paths, commands and links in README/docs exist, plus EN/PT-BR section parity. |
| 13 | guard-recipes | Rejected | 3 | 7 | 21 | M | Tested PreToolUse hook recipes and `.env`/key deny rules. |
| 14 | safety-net | Approved | 4 | 5 | 20 | M | Git-ref snapshots before risky Bash, restored only on approval. |
| 15 | todo-sweep | Approved (filler) | 2 | 9 | 18 | S | TODO/FIXME triage by area and age. |
| 16 | calm-mode | Approved (filler) | 3 | 5 | 15 | S | A brief, kind "capybara voice" output style. |
| 17 | loadout-board | Approved (filler) | 3 | 5 | 15 | M | What loads at session start, with its estimated cost; approved trims are applied. |
| 18 | variant-board | Maybe (filler) | 3 | 5 | 15 | M | Pick among N UI variants rendered as image cards. |
| 19 | session-recall | Approved (filler) | 3 | 4 | 12 | M | Approve which snippets of old transcripts are re-injected into context. |
| 20 | issue-triage-board | Approved (filler) | 4 | 3 | 12 | M | Approve per issue before applying `gh` labels/close/duplicate actions. |

## Evidence and main objection, per skill

Counts are as read on 2026-10-12 and may have drifted. Versions refer to the Claude Code changelog.

- **diff-board.** Issue anthropics/claude-code#33932 (204 +1, open) asks for end-of-turn, cross-file Keep/Revert per hunk; plannotator (9.4k stars) and revdiff (927) only annotate. *Objection:* Anthropic is iterating on `/diff` and added per-change accept/reject in VS Code (2.1.275); a native post-apply hunk revert could land at any time.
- **publish-check.** gitleaks (29.9k stars) does not scan commit messages (gitleaks#800, open). *Objection:* `attribution.sessionUrl` can disable the main leak vector natively, and session links only appear in web and Remote Control sessions; demand is thin.
- **question-board.** Pocock's grill-me (1.3M installs) shows the frequency of question-heavy sessions; its rounds are independent questions, which fits ar-board's "each item is independent" rule with no engine change. *Objection:* the in-chat round is already cheap; the gain is a calmer UI.
- **tidy-board.** Issue #26725 (open). Pruners exist (git-delete-merged-branches 920 stars, git-trim 547) but none gate each deletion in a panel. *Objection:* a quiet pain; squash-merge detection without `gh` is a heuristic and a false "merged" would be costly.
- **commit-groups.** Local and reversible (soft reset). *Objection:* the official commit-commands plugin exists and Claude already splits commits when asked.
- **handoff.** Pocock's handoff has about 969k installs, so demand is proven. *Objection:* a near-1M-install free incumbent; "verified references" is a thin differentiator.
- **memory-board.** claude-mem (100k stars) shows memory demand; pruning is thinly served. *Objection:* the VS Code Memory dialog already views, edits and deletes memories (2.1.275).
- **doc-truth.** Closes the docs-quality loop for this repo (README and README.pt-BR). *Objection:* `/doctor prompt-audit` (2.1.283) already checks stale paths and commands in Claude config files.
- **safety-net.** Bash edits escape `/rewind` in auto mode, now the default (2.1.284): #87575 and #87971, both open. *Objection:* writes into the user's `.git`, misses ignored files such as `.env`, slow on large repos.
- **todo-sweep.** Fits the engine perfectly and is the cheapest item. *Objection:* no demand evidence at all.
- **calm-mode.** Tone packs are the hottest consumer trend (ponytail 161k stars, caveman 111k). *Objection:* saturated, the cited issues are model behaviour, and the effect cannot be tested.
- **loadout-board.** Issue #14920 (open). *Objection:* the docs say plugin skills are not affected by `skillOverrides`; `/skills` already toggles skills with token estimates (2.1.280).
- **session-recall.** Issue #27242 (open). *Objection:* claude-mem and episodic-memory already feed context back; transcripts contain secrets and their JSONL format is undocumented.
- **issue-triage-board.** Pocock's triage (about 930k installs) proves the activity. *Objection:* needs `gh`, auth and network, and changes shared remote state, which breaks the offline principle.
- **variant-board.** Design activity is large (Pocock prototype 925k installs, impeccable 80k stars). *Objection:* no direct ask; rendering needs a browser or screenshot tool outside stdlib, and picking one variant is a choice, not approve/reject.
- **Rejected: review-map, skill-check, settings-doctor, changelog-keeper, guard-recipes.** No reason was recorded. The reviewers' objections were: review-map overlaps diff-board's risk grouping; skill-check is saturated (snyk/agent-scan, Cisco skill-scanner, agnix) and rule-only scanning catches about 8% of threats; settings-doctor overlaps `/doctor`; changelog-keeper is served by git-cliff (12.3k stars), release-please and release-it; guard-recipes is saturated (destructive_command_guard 6.2k, cc-safety-net 1.6k, hookify).

## Refinements

Each approved skill is refined one at a time, with scope questions judged in an ar-board panel; the closed result lives in `docs/refinements/<skill>.md`.

| Skill | Status | Refinement |
| --- | --- | --- |
| question-board | Refined, 1 open point (effort S or M) | [docs/refinements/question-board.md](docs/refinements/question-board.md) |
| publish-check | Refined, scope closed (effort M); plan written | [docs/refinements/publish-check.md](docs/refinements/publish-check.md) · [docs/plans/publish-check.md](docs/plans/publish-check.md) |

## Suggested build order

1. **question-board**, as a second skill inside the ar-board plugin: effort S, current engine, no new plugin, so no engine-sharing decision is needed.
2. **publish-check**: read-only, no engine dependency; it pays the cost of the second-plugin plumbing (its own sync check, CI loop over `plugins/*/tests`, catalog entry, PT-BR README).
3. **tidy-board**: the first separate plugin that reuses the engine with no protocol change, so it forces the sharing decision (a vendored `capy_board.py` with a byte-equality `--check`).
4. **diff-board**: number one by score but the only L; it needs engine v2 (a diff block) and a hunk library. If a native per-hunk revert shows up in the Claude Code changelog first, re-score it before starting.
5. **commit-groups** and **safety-net** become incremental on the same hunk library and snapshot code.

Dependencies: commit-groups needs diff-board's hunk library; safety-net shares its snapshot code. Plugins are self-contained, so shared engine code is either extra skills inside ar-board or a copy per plugin.

## Open doubts

- Whether Anthropic ships hunk-level approve/revert natively (it would sink diff-board).
- Whether `/plugin` already toggles individual plugin skills (it would sink loadout-board further).
- Squash-merge detection reliability on rebased or conflict-resolved histories (tidy-board).
- Star and install counts may be inflated; only the relative ordering is trusted.

## Next round

Decide variant-board; rejected items stay out unless reopened.

# Refinement: question-board

- **Status:** refined (scope closed with one open point, see the end)
- **Date:** 2026-10-12
- **Backlog entry:** #3, score 36 (U 4 x A 9), effort S as ranked. The amendment below may raise it to M.
- **How it was refined:** nine scope questions, each with a recommended answer and alternatives, judged one by one in an ar-board panel. All nine were approved; one carried a comment that amends the design.

## What it is

A second skill in the ar-board plugin (`/ar-board:question-board`). When the agent has several independent questions to ask before it can proceed, it puts them in one calm form instead of a long chat round. The person answers each one and the agent reads the answers from disk.

Where ar-board asks "approve or reject this proposal?", question-board asks "which of these options do you choose?" and always shows the context needed to decide.

## Decisions

| # | Topic | Decision |
| --- | --- | --- |
| Q01 | Where it lives | Second skill inside the ar-board plugin, own description and triggers, same `ar_board.py`. Not a separate plugin, not just a section in the ar-board SKILL.md. |
| Q02 | Answer model | Approved **with an amendment** (below). Base proposal: approve = accept the recommended answer, reject = a different answer written in the comment, maybe = explain better in the next round. |
| Q03 | Multiple choice | Approved as proposed: options shown as text on the card, chosen by typing the letter in the comment. Affected by the Q02 amendment (below). |
| Q04 | Round size | Up to 8 questions per round, all independent. A question that depends on another answer goes to the next round (same `batch_id`, `round + 1`; the server archives the previous one). |
| Q05 | Output contract | No new subcommand in v1: the agent reads `summary --json` and the skill defines how to translate decisions into answers; an example batch shows the format. Affected by the Q02 amendment (below). |
| Q06 | Trigger | When the person asks ("grill me", "me interrogue", "faca as perguntas") or when the agent has 4 or more independent questions before starting. Below 4, ask in chat. The skill offers the panel; it does not start one silently. |
| Q07 | Persistence | Only return the answers to the agent. Answers that become rules go to `.ar-board/preferences.md`. No ADRs and no per-round answers file in v1. |
| Q08 | Card quality | One-sentence question, 2-4 options, one recommended with a one-line reason, and what changes if another option is chosen. Extended by the Q02 amendment: context is always present. |
| Q09 | Definition of done | Skill, an example batch accepted by `check`, package tests covering the new skill, EN and PT-BR docs, a `1.2.0` CHANGELOG entry with the sync tools run, and one real use before closing. |

## Amendment from the owner (Q02)

Original comment, in Portuguese: "creio que a diferenca entre o ar-board e o question-board deveria ser trazer outras opcoes. Entao, nao deve ser apenas A e R, mas sim outras opcoes. Importante sempre trazer contexto para facilitar a decisao."

Taken as requirements:

1. **Options are first-class.** The point of question-board is offering several options to choose from, not only accept or reject one proposal.
2. **Context is mandatory.** Every card carries the context needed to decide, not just the options.

## Interpretation to confirm

The panel today only records approved, rejected or maybe plus a comment. Taken literally, requirement 1 is not met by Q03 and Q05 as approved ("options as text, pick a letter in the comment", "no engine change"). The reading proposed here:

- The additive engine change that Q03 listed as alternative B is pulled into v1: an optional `choices` list per card, so the person picks an option directly (for example with the number keys), and `summary --json` reports the chosen option. Cards without `choices` behave exactly as today, so ar-board is unaffected.
- Q05 still holds in spirit (no new subcommand), provided `summary --json` exposes the chosen option; the translation rule in the skill becomes simpler.
- Effort moves from S to M, and the "engine as is" property that justified A 9 no longer fully holds, though the change is additive and backward compatible.
- The stopgap in Q03 (letters in the comment) stays as the fallback for terminals or batches without `choices`.

Whether this reading is right is the open point below.

## Out of scope for v1

- ADR generation from approved answers (the grill-with-docs skill already covers it).
- A per-round answers file.
- Dependent or branching questions inside one round.
- Posting questions to any remote system.

## Risks

- A recommendation can anchor the answer. Mitigation: every card shows what changes if another option is chosen (Q08).
- Two skills in one plugin can compete for the trigger. The descriptions must be sharply different ("answer questions" versus "judge proposals").
- If the translation of decisions into answers stays in prose rather than code, the agent can apply it wrongly. The `choices` reading removes most of this; the example batch and a test that the example parses cover the rest.
- The threshold of 4 questions is a guess; adjust after a few real uses.

## Discarded alternatives

- Separate `question-board` plugin with a copy of the engine (Q01 B).
- Free-text answer field in the engine (Q02 C); superseded by `choices` plus the comment.
- Unlimited questions per round or a cap of 4 (Q04 B, C).
- A dedicated `summary --answers` subcommand (Q05 B), unless the `choices` change makes it cheap.
- Always asking when there are 2 or more questions (Q06 C).
- ADR output or an `answers.md` per round (Q07 B, C).
- Neutral cards with no recommendation (Q08 B).

## Open point

**Does the Q02 amendment override Q03 and Q05, so that v1 includes the `choices` engine change (effort M)?** If yes, nothing else in this document changes. If the owner wants to keep v1 strictly on the current engine (effort S), the "options" requirement is delivered only as lettered text in the comment, and `choices` moves to a v2.

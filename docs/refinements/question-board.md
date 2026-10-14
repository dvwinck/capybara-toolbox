# Refinement: question-board

- **Status:** refined, requirements and UX analysed on 2026-10-14; the open point is closed (decision UX1); ready to build
- **Date:** 2026-10-12
- **Backlog entry:** #3, score 36 (U 4 x A 9), effort S as ranked; **now M** (the `choices` engine change, multiple choice and the review screen are in v1).
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

## Open point (closed on 2026-10-14)

*Does the Q02 amendment override Q03 and Q05, so that v1 includes the `choices` engine change (effort M)?* **Yes** (decision UX1 below). Q03 and Q05 now read as: options are first-class (`choices`), chosen with the number keys, and `summary --json` reports the chosen option; the lettered-comment stopgap is dropped.

---

# Requirements and UX analysis (2026-10-14)

Companion file: [question-board-prototype.html](question-board-prototype.html), a clickable design prototype (interface only, no server, nothing saved) built with the real ar-board theme tokens. Open it in a browser and try the keys; the behaviours described below were exercised in it.

## 1. Job to be done

A person is working with an agent that needs several independent answers before it can continue (a design choice, a name, a scope boundary). Typing six answers in chat is slow and error-prone: options get lost, the context scrolls away, and the agent cannot read the answers as data. The question-board lets the agent put the questions in one local form; the person answers with a key press per question and the agent reads structured answers from disk.

How it differs from the ar-board: the ar-board asks "do you approve this proposal?" and answers with A/R/M. The question-board asks "which of these do you choose?" and answers with an option, a free-text "other", or a request for more context.

## 2. Decisions taken in this analysis (owner, 2026-10-14, asked one by one)

| # | Decision | Answer |
| --- | --- | --- |
| UX1 | `choices` in the engine in v1 (closes the open point) | Yes: optional `choices` per card, number keys, chosen option in `summary --json`. Effort M, version 1.2.0. |
| UX2 | Flow | One card at a time, like the ar-board (options inside the card; comment and numbered chips beside it). A single scrolling form was rejected. |
| UX3 | Recommended option | Marked with a star and a one-line reason, **never pre-selected**; Enter does not accept it. |
| UX4 | Outside the options | Every card with options gets an automatic last option "Outra resposta..." whose text is the answer; a card with `"open": true` has no options, only a required text box. |
| UX5 | Multiple choice | **Accepted in v1** (`"multiple": true`), against the recommendation to start with single choice. This widens the contract (see 5.2) and the flow (see 6.4). |
| UX6 | Script sharing | The second skill carries a generated copy of `ar_board.py` and `sync.py --check` fails if the copies differ byte for byte. |
| UX7 | Review before finishing | A review screen lists "question -> your answer" (unanswered ones highlighted, each with a link back) before the agent is told. |
| UX8 | Unanswered or "more context" | They come back as pending: the agent never acts on them and never falls back to the recommended option; it asks in chat or re-explains in the next round. |

Derived from these (not asked, flagged for review): a card is a question when it has `choices` or `open` (mixed boards are allowed); "Outra" counts toward a multiple card's maximum; multiple cards never auto-advance; the last question's Enter opens the review; single-file variants are generated for both skills.

## 3. Requirements

**Functional**

- FR1. A card can carry 2-8 `choices` (`id`, `label`, optional `effect`); the person picks one with keys 1-9. With `multiple` they pick `min`..`max`.
- FR2. Every question card shows context (at least one field with text), enforced by `check`, because the owner's amendment made context mandatory.
- FR3. One option may be marked recommended with a reason; it is never pre-selected (UX3).
- FR4. "Outra resposta..." is appended automatically to every card with options; its text, entered in the comment box, is the answer and is required (UX4).
- FR5. `"open": true` cards have a required text answer and no options.
- FR6. "Preciso de mais contexto" (key M) marks a question as unsure; it clears any option picked and is undone by pressing M again.
- FR7. Skipping (S, right arrow) leaves the question unanswered; there is no implicit answer (UX8).
- FR8. A review screen shows every answer before the agent is told; unanswered ones link back to their card (UX7).
- FR9. `summary` and `summary --json` report answered (with the chosen option's id and label, or the "other"/open text, and whether the recommended option was taken), unsure and pending questions, in addition to the existing proposal groups (additive; the existing keys do not change).
- FR10. The offline `build` variant supports the same cards and exports them through Copiar (`AR-BOARD-RESULT`), including the chosen options.
- FR11. Rounds work as in the ar-board: dependent questions go to the next round (same `batch_id`, `round + 1`).
- FR12. A comment can accompany any answer; for "Outra" and open cards the comment *is* the answer.

**Non-functional**

- NFR1. Python standard library only; no new dependency; Python 3.9-3.13.
- NFR2. Existing ar-board behaviour and files are unchanged for cards without `choices`/`open` (cards, summary keys, state shape, tests).
- NFR3. Strings in the page are accent-free Portuguese (project convention); card content may be any Unicode.
- NFR4. All user text is escaped; no change to the CSP (inline script and style only, no fonts, no network).
- NFR5. WCAG AA text contrast in both themes (existing test) and 3:1 for control boundaries (new test, see 6.7).
- NFR6. A 400 from the server leaves no trace in the state (existing invariant of `set_item`).
- NFR7. Keyboard-complete: every action reachable without a mouse; visible focus; no colour-only meaning.

## 4. What the current engine gives and what it forbids (read from `ar_board.py` 1.1.0)

- `validate` accepts `tag`, `image`, `meta`, `risk`, `fields`; it ignores unknown item keys, so old versions tolerate `choices` but would show a card with no way to choose (version mismatch is a documented risk).
- `Store.set_item` knows only `decision` in {approved, rejected, maybe} and `comment`; it rebuilds the entry from existing keys, so extra keys survive but are unvalidated. `valid_state` checks only `decision` and `comment` types, so a hand-edited `choice` would pass unchecked today.
- `render_summary` groups by `decision`; there is nowhere to put a chosen option.
- The page decides with `decide(d)`, keys A/R/M/S/C and arrows, auto-advance after a decision with a user toggle, a side panel (comment, buttons, chips), a result section with counts, Concluir / Baixar / Copiar / Limpar, and a `confirm()` for unanswered items.
- The page JS is not run by the test suite; only string guards and the colour tests exist, and CI syntax-checks the extracted script (`page-js`).
- `exportObj` and the offline path produce a different shape from `decisions.json` and must be extended too.
- The skill is lean: every command is `python3 -I "${CLAUDE_SKILL_DIR}/scripts/ar_board.py" ...`, and `sync.py` is written for a single skill.

## 5. Data contract (proposed; names fixed in the first commit)

### 5.1 `batch.json` question card

```json
{
  "id": "Q01", "tag": "merge",
  "title": "Como detectar que um branch ja foi mesclado?",
  "fields": [{"label": "Contexto", "text": "Squash-merge reescreve os commits..."}],
  "choices": [
    {"id": "ancestor", "label": "Ancestral de base", "effect": "seguro, mas nao reconhece squash-merge"},
    {"id": "patch",    "label": "Comparar patch-id", "effect": "reconhece squash simples"}
  ],
  "recommended": ["patch"], "why": "cobre o caso mais comum sem rede.",
  "multiple": false, "min": 1, "max": 2, "open": false
}
```

Rules enforced by `check` (and by the same validation in `Store`):

- A card is a **question** when `choices` or `open` is present; otherwise it is a proposal exactly as today.
- `choices`: list of 2-8 objects; `id` matches `^[A-Za-z0-9_-]{1,32}$` and is unique in the card; `label` is a non-empty string; `effect` is an optional string. Keys 1-9 cover 8 options plus "Outra".
- `open: true` excludes `choices`, `multiple`, `recommended`.
- `recommended`: list of choice ids; at most 1 for single choice, at most `max` for multiple; `why` is required when `recommended` is present.
- `multiple`, `min`, `max`: booleans and integers (not bool); `1 <= min <= max <= len(choices)`; defaults `min` 1, `max` `len(choices)`; "Outra" counts toward `max`.
- A question card needs at least one `fields` entry with non-empty text (mandatory context).
- `check` prints a warning (exit 0) when a board has more than 8 questions; the skill's limit is a rule, not an engine error.

### 5.2 Saved state per item (`decisions.json`)

| Situation | Entry |
| --- | --- |
| single choice | `{"choice": "patch", "comment": "..."}` |
| multiple choice | `{"choices": ["local", "wt"], "other": false, "comment": "..."}` |
| "Outra" (single) | `{"other": true, "comment": "ordem alfabetica"}` (the comment is the answer) |
| open | `{"comment": "limpar-branches"}` |
| more context | `{"decision": "maybe"}` |
| proposal card (unchanged) | `{"decision": "approved", "comment": "..."}` |

`/api/item` accepts `choice` (string or null), `choices` (list of strings or null), `other` (bool), `decision` (only `maybe` or null for question cards; `approved`/`rejected` are a 400 there), `comment`. Validation, all before touching state: the card is a question; every id belongs to the card; no duplicates; the count, including "Outra", is within `max`. Setting an answer clears `maybe`; setting `maybe` clears `choice`, `choices` and `other`; single `choice` and `other` are mutually exclusive, multiple allows both. `valid_state` gains type checks (`choice` string, `choices` list of strings, `other` bool) and `summary` treats an id no longer in the card as pending, so editing a batch after answering cannot crash it.

One function, `answer_of(card, entry)`, decides "answered / unsure / pending" and builds the answer object; the summary uses it and the page has a hand-written twin, guarded by tests on both sides.

### 5.3 `summary --json` (additive)

```json
{
  "answered": [{"id": "Q01", "title": "...",
     "answer": {"kind": "choice", "id": "patch", "label": "Comparar patch-id"},
     "recommended_taken": true, "comment": ""}],
  "unsure":   [{"id": "Q05", "title": "...", "comment": ""}],
  "pending":  [{"id": "Q04", "title": "...", "comment": ""}]
}
```

`kind` is `choice`, `choices` (with `ids`, `labels`, and `other` text when used), `other` (with `text`), or `open` (with `text`). `recommended_taken` is `null` for open and "Outra" answers. The existing `approved`/`rejected`/`maybe` groups stay for proposal cards, so a mixed board is read with one call. The text summary gains "Respondidas (N)" and "Precisam de contexto (N)" sections before "Sem decisao", each answered line showing the chosen label, a "(recomendada)" mark when applicable, and the comment. The offline `AR-BOARD-RESULT` adds the same fields per item.

## 6. UX design

### 6.1 Principles

1. **Decide in under thirty seconds.** One question, its context and its options on one screen; no scrolling inside a card for 8 options.
2. **Help without steering.** A recommendation is shown with its reason, never pre-selected; the effect of each option is visible before choosing.
3. **Nothing happens by accident.** No answer is implied; Enter does not accept a recommendation; finishing goes through a review.
4. **Same house as the ar-board.** Same capybara palette, header, key bar, progress bar, side panel and chips, so the muscle memory carries over; the differences are exactly the ones the job needs.

### 6.2 Visual direction

The frontend-design guidance asks for a bold, unmistakable aesthetic. Here the constraint is the opposite and deliberate: this is a second skill in an existing product, so it extends the existing system and invents no new one. The decisions that give it character inside that system:

- **The question is set in the system serif** (`ui-serif`, with Iowan Old Style / Palatino / Georgia fallbacks) while everything else stays in the system sans. The page's CSP allows only inline style and script, so web fonts are impossible; the serif stack is the offline way to make the question read as a question and not as a proposal title.
- **Options are keycaps and cards**: each option is a full-width row with its number as a small keycap, so the key to press is the first thing the eye meets; the chosen option gets the accent border, an accent keycap and a check, three signals that do not rely on colour alone.
- **The star is the only ornament**: the recommended option carries a star and a small "recomendada" tag in the amber token, the reason sits under the list.
- **Calm motion**: a 120 ms border and background transition on options and the existing 200 ms progress bar; `prefers-reduced-motion` turns them off.
- **No new colour tokens.** Answered uses the accent (not green, because green means "approved" in the ar-board and an answer is not an approval); unsure reuses the amber "maybe" tokens; pending is neutral.

### 6.3 Screen anatomy (one card at a time, UX2)

- Header, key bar, progress bar: as today; the key bar shows `1-9` choose, `Enter` confirm, `M` more context, `S` skip, `C` comment, `Esc`, arrows, and the auto-advance toggle (relabelled "avancar ao escolher").
- Card (left): pill `n/N - id - tag`, a state chip (Respondida / Precisa de contexto), the question in serif, the context box (the card's `fields`), a one-line instruction ("Escolha uma opcao." / "Escolha de 1 ate 2. Enter confirma."), the options, and the recommendation reason.
- Side panel (right): the comment box, whose label changes to "Sua resposta (obrigatoria)" for "Outra" and open cards; the buttons "Preciso de mais contexto (M)", "Pular (S)", "Anterior", "Proximo"; the numbered chips (answered = accent outline, unsure = amber, pending = neutral, current = outlined).
- Result section: counts (respondidas / precisam de contexto / sem resposta) and one button, "Revisar e concluir" (the ar-board's "Concluir" becomes the last step of the review).
- Narrow screens: one column; the side panel drops under the card (existing breakpoint).

### 6.4 Interaction rules

| Input | Single choice | Multiple choice | Open card |
| --- | --- | --- | --- |
| `1`-`8` | choose that option (again to undo); advances if the toggle is on | toggle it; never advances; past `max` shows "Maximo de N opcoes" | ignored |
| `9`... last number = "Outra" | selects it, moves focus to the comment box, does not advance | toggles it (counts toward `max`), focuses the comment box | n/a |
| `Enter` | advances only if answered, else explains why | advances only if the count is within `min`..`max` | advances only if there is text |
| `M` | toggles "more context", clearing any pick | same | same |
| `S`, right arrow | next question, no answer | same | same |
| `C` | focus the comment box | same | same |
| `Esc` | leave the comment box | same | same |
| `A`/`R` | ignored on question cards | | |

On the last question, an answered Enter opens the review. In the review: "Voltar e corrigir" (Esc also) returns to the cards; each row has "alterar"/"responder"; "Confirmar e avisar o agente" sends the finish (live) or shows Copiar (offline). Unanswered questions are listed with a note that the agent will ask in chat and never assumes the recommended option (UX8). The browser `confirm()` of the ar-board is no longer needed for question boards.

### 6.5 States

| State | Card | Chip | Counts as |
| --- | --- | --- | --- |
| nothing chosen | no option checked | neutral | pending |
| option(s) chosen within limits | accent border, keycap, check; chip "Respondida" | accent | answered |
| multiple below `min` | options marked, instruction unchanged | neutral | pending |
| "Outra" without text | option checked, label "(obrigatoria)" | neutral | pending |
| open without text | text box required | neutral | pending |
| more context | amber chip; options cleared | amber | unsure |

### 6.6 Microcopy (accent-free Portuguese)

"Escolha uma opcao." · "Escolha de 1 ate 2. Enter confirma." · "Outra resposta..." with "o texto do campo ao lado vira a resposta" · "Sua resposta (obrigatoria)" · "Preciso de mais contexto" · "se escolher: <effect>" · "Por que recomendamos: <why>" · "Respondida: Q01. Use seta para a esquerda para mudar" · "Maximo de 2 opcoes. Desmarque uma antes." · "Revise suas respostas (6 de 8)" · "(sem resposta)" · "Voltar e corrigir" · "Confirmar e avisar o agente".

### 6.7 Accessibility and contrast

- Options are real buttons with `role="radio"` (single) or `role="checkbox"` (multiple) inside a `radiogroup`/`group` labelled by the question, with `aria-checked`; chips carry an `aria-label` with the question number and state; the hint line is a polite live region.
- Measured on the current palette: accent text on `panel` and `panel2` is at least 4.76:1 in both themes (AA needs 4.5); **the `line` token is only about 1.5:1 against the panel, so it cannot outline a control** (WCAG asks 3:1 for the boundary of a component). Option borders therefore use `mut` (and `acc` when chosen). New tests: `acc`/`panel`, `acc`/`panel2` at 4.5, and `mut`/`panel2`, `acc`/`panel` at 3.
- Selection never relies on colour alone (border, keycap fill and check). The star is accompanied by the word "recomendada".

### 6.8 What the prototype verified (and found)

Run in a browser through scripted key presses: auto-advance, out-of-range keys, "Outra" with focus on the comment box, multiple choice with a maximum, open cards, undo of "more context", the review table and the `summary --json` shape. It found two defects in its own first version that are now requirements: **"Outra" must count toward a multiple card's `max`** (it allowed a fourth selection), and **Enter on an unanswered card must never advance** (it advanced an empty open question). Not verified: screen readers, a real touch device, very long option labels.

## 7. The skill (`skills/question-board/SKILL.md`)

- **Description and triggers**: sharply different from the ar-board so they do not compete: the ar-board is "judge N proposals"; the question-board is "answer N questions". Portuguese and English triggers: "grill me", "me interrogue", "faca as perguntas", "preciso te perguntar varias coisas", "ask me the questions in a form".
- **When**: the person asks, or the agent has 4 or more independent questions before it can start (Q06). Fewer than 4: ask in chat. The skill offers the panel; it never starts one silently.
- **Round**: up to 8 questions, all independent; a question that depends on another answer waits for the next round (`round + 1`).
- **Card quality** (extends Q08): one-sentence question; 2-4 options (the engine allows 8); one recommended with a one-line reason; an `effect` on each option; context always present; use `open` sparingly; no leading wording; options mutually exclusive unless `multiple`.
- **Reading**: `summary --json`; act on `answered`; never act on `unsure` or `pending`: ask in chat or fold them into the next round with a better explanation (UX8).
- **Learning**: answers that turn into rules go to `.ar-board/preferences.md` as "Regra confirmada" after the person confirms them; nothing else is persisted (Q07).

## 8. Packaging and engineering plan (effort M; estimate from the code read, not measured)

| Area | Work |
| --- | --- |
| Engine (`ar_board.py` 1.2.0) | `validate` for question cards; `Store.set_item` and `valid_state` for `choice`/`choices`/`other`; `answer_of`; `render_summary` (text and JSON); `exportObj`. About 150 lines. |
| Page | Option list, keys 1-9, "Outra", multiple, open cards, `M` semantics, review screen, new tokens-free CSS, `exportObj`. About 200 lines of JS/CSS; checked in a browser, with the prototype as the reference. |
| Skill | `skills/question-board/SKILL.md`, an example batch accepted by `check`, the generated `scripts/ar_board.py` copy (UX6). |
| Packaging | `sync.py` handles two skills: copies the script into `question-board`, `--check` fails on a byte difference, generates a single-file variant per skill, updates manifest description and keywords; `install.sh` already installs every skill of a plugin. |
| Docs | Plugin README (EN, PT-BR), root README rows, `docs/reference.md` (card schema, state, summary), `guia-completo.md`, CHANGELOG `1.2.0`, backlog. |
| Tests | See 9. |

## 9. Test plan

- **validate**: valid single, multiple, open and mixed boards; fewer than 2 or more than 8 choices; duplicate or malformed ids; `recommended` not in `choices`, too many for single, missing `why`; `min`/`max` out of range or bool; `open` with `choices`; missing context; the more-than-8-questions warning.
- **Store**: choose, undo, switch single choice, toggle multiple within and beyond `max` (including "Outra"), "Outra" and open require text to count, `maybe` clears and is cleared, `approved` on a question card is a 400, an unknown id is a 400 with no trace, a stale id in the saved state is treated as pending.
- **summary**: text and JSON for each answer kind, `recommended_taken` (true/false/null), mixed boards, unchanged output for proposal-only boards (golden test).
- **HTTP**: POST `/api/item` with `choice`, `choices`, `other`; malformed bodies; existing security tests unchanged.
- **Page guards** (strings, as today): keys 1-9 handler, "Outra" counted against `max`, Enter blocked while pending, `A`/`R` ignored on question cards, `aria-checked` in the option template, serif question font; plus the new contrast tests.
- **Packaging**: the two script copies are identical; `--check` detects a drift and `sync` repairs it; both skills are lean and use the bundled script; install and uninstall handle both skills; the example batch passes `check`; version, manifest and changelog stay in sync (existing tests, generalised).
- **Manual browser checklist** (the suite does not run JS; record the result in the PR): every row of 6.4 in light and dark, a 360 px width, a keyboard-only pass, an 8-option card, a long label, offline `build` plus Copiar, a resumed round.

## 10. Risks and what is still unverified

- The page JS has no automated behavioural test; the prototype and the checklist reduce this, they do not remove it. Consider a later headless test if the page keeps growing.
- Multiple choice (UX5) widens the contract for every consumer of `summary --json` (a card yields a string id or a list); the `kind` field makes this explicit, and the skill documents it.
- An older single-file `ar-board` (1.1.0) reading a 1.2.0 batch shows question cards without options; the docs ask to update both skills together.
- Two script copies can drift; the byte check in `sync --check` (run by the tests and CI) is the guard.
- Screen-reader behaviour of buttons with radio roles, touch devices and very long labels are unverified.
- The 4-question threshold and the 8-question round limit remain guesses (Q04, Q06); adjust after a few real uses.

## 11. Definition of done (replaces Q09)

The `choices`/`open`/`multiple` engine change with tests; the page with the review screen, checked against the 6.4 checklist in a browser; `skills/question-board` with SKILL.md and an example batch accepted by `check`; the generated script copy and the generalised sync; EN and PT-BR docs; `1.2.0` CHANGELOG with both sync tools run; `claude plugin validate .` passing; and one real use by the owner before closing.

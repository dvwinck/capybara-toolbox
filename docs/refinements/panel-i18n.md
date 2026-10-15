# Refinement: a switchable panel language (English default, pt-BR)

- **Status:** refined, awaiting the owner's review of this written spec (no plan yet)
- **Date:** 2026-10-15
- **Follows:** the English skills (PR #10, step 1). This is step 2: the panel the skills open, and the cards the tools put on it.
- **How it was refined:** the owner asked for "a bilingual panel interface, English by default, switchable to pt-BR". Three questions were answered with a recommendation each (toggle scope, pt-BR style, what `scan` does about language), then the design below was shown in chat and approved ("ok"). No web research: this is an internal design.
- **Read before writing (2026-10-15):** `plugins/ar-board/skills/ar-board/scripts/ar_board.py` (`PAGE`, `render_page`, `validate`, `cmd_serve`, `cmd_build`), the card builders of `tidy_board.py` and `todo_sweep.py`, and the tests that pin Portuguese UI text.

## What it is

Today the panel is Portuguese only. After this change:

- the **panel chrome** (buttons, key bar, review screen, hints, dialogs) exists in English and pt-BR, English by default, switchable in the page without a reload;
- tidy-board and todo-sweep generate their **cards** (field labels, titles, reasons, button wording, the todo-sweep report) in a chosen language, English by default;
- the agent's skills say which language to ask for, from the language the user writes in.

## Decisions

| # | Topic | Decision | Owner's choice |
| --- | --- | --- | --- |
| P01 | Default | English. Portuguese is an option (`pt-BR`). | as stated by the owner |
| P02 | How the language is chosen | A batch field `lang` (`"en"` default, `"pt-BR"`), a `--lang` flag on `serve` and `build`, and an EN/PT toggle in the page header that is remembered in the browser. | as recommended |
| P03 | What the toggle changes | The panel chrome only. Card text stays in the language it was generated in: one batch, one content language. | as recommended |
| P04 | Portuguese style | Proper pt-BR with accents (the page is UTF-8). The old accent-free convention ends for the page. | as recommended |
| P05 | Tool cards | `scan --lang en\|pt-BR` on tidy-board and todo-sweep, default `en`; cards, labels, reasons and the todo-sweep report come out in that language and `lang` is written into `batch.json`. | as recommended |
| P06 | Delivery | Two steps: skills in English (done, PR #10), then this. | as recommended |
| P07 | Mechanism | Both dictionaries ship inside the page (a Python `I18N` table injected through the boot data), so the toggle is instant and also works in the offline `build` page. | approved with the design |

## Design notes derived from the decisions

Every rule marked **R** is a ruling made while writing this spec; the owner may veto any of them (see *Rulings in this spec*).

### The contract (ar-board 1.4.0)

- `batch.json` gets an optional top-level `lang`: `"en"` or `"pt-BR"`. `check` rejects any other value, and a non-string, with an error. A batch without `lang` is English.
- `serve` and `build` take `--lang en|pt-BR`. It overrides the batch's `lang` for what the page shows first.
- The page reads, in this order, the first that is set: the language saved by the toggle in the browser (`localStorage`, key `ar-board:lang`), then `--lang`, then the batch `lang`, then `en`. A saved value that is not one of the two is ignored. **R1**
- The toggle sits in the header next to the live/offline badge. It switches the chrome at once, sets `<html lang>`, and saves the choice. It never touches the cards or `decisions.json`.
- Nothing about the language is stored in `decisions.json`, and the offline `Copiar` export (`AR-BOARD-RESULT`) has the same shape as before.

### The engine

- Every user-visible string of the page moves out of the JavaScript and the markup into `I18N = {"en": {...}, "pt-BR": {...}}` in the script. The two tables have the same keys and the same placeholders (`{n}`, `{total}`, ...). The page gets the table through the boot data it already receives, so the Content-Security-Policy does not change.
- The dynamic messages are covered too: the hints, the "N items without a decision. Finish anyway?" dialog, the armed-confirmation text, the review-screen headings, the counts line.
- The panel's own button wording (Approve / Reject / Maybe, or the question-board equivalents) comes from the table. A batch-level `labels` and a card-level `confirm` are card content: they are shown as written and do not switch with the toggle. **R2**
- The risk words on a card are read as before (`baixo`/`médio`/`alto`, accents and case ignored) and now also `low`/`medium`/`high`. The CSS classes and colours do not change. **R3**
- `check`, `summary`, `wait`, the HTTP error bodies and every other message printed by the engine's command line stay as they are, accent-free Portuguese. They are read by the agent, not shown in the panel, and the skills quote them literally. Changing them is a separate step.
- The key letters (`A`, `R`, `M`, `S`, `C`) and the shortcuts do not change in either language. **R4**

### tidy-board 0.2.0 and housekeeping 0.4.0 (todo-sweep)

- Each tool gets a small string table per language and one function that formats from it. All the card text now built inline moves there: field labels (Proof, Where, Text, Age, Excerpt, ...), titles, effects, reasons for "do not touch", the group card, `LABELS` (Delete / Keep / Later for tidy-board, Resolve / Discard / Keep for todo-sweep), `confirm` texts, the subtitle, the age wording.
- `scan --lang en|pt-BR` (default `en`) selects the table. The language is written to `batch.json` as `lang` (so the page opens in it) and to the `scan.json` sidecar, so `report` and `apply`/`restore` use the same language later without being told. **R5**
- Everything a script parses or compares stays language-independent: ids (`T01`, `G`), proof levels, decision values (`approved`/`rejected`/`maybe`), ledger keys, JSON keys. The ledger remembers decisions by id and decision, never by label.
- The todo-sweep `report.md` and `report.json` headings follow the scan's language. The tools' other command-line output (the scan summary, `apply`'s per-item lines, errors) stays Portuguese, as for the engine. **R6**
- The old default changes: a `scan` without `--lang` now writes English cards. This is why these two plugins take a minor version.

### The skills and the docs

- The eight `SKILL.md` files stop saying the panel is Portuguese. They name each literal the panel or a script shows in English first, with the pt-BR wording next to it, and tell the agent: ask for the language the user writes in (`lang` in the batch it writes for ar-board and question-board; `--lang` on `scan` for tidy-board and todo-sweep), and write card and question content in that language.
- The finish signal the panel asks the user to say becomes "done" (English panel) or "terminei" (pt-BR panel); the skills accept either, as they already accept "done"/"finished" next to "terminei".
- The READMEs' "Languages" lines, the root and plugin docs and `CLAUDE.md` say: skills in English; the panel and the generated cards in English or pt-BR (`--lang`); the engine and tool command-line output in Portuguese. `CLAUDE.md` also drops "In-page UI strings are accent-free Portuguese" and says that the tool tables carry both languages.
- The generated single-file variants (`dist/*.SKILL.md`) follow from the sync tool.

### Versions

ar-board 1.4.0, tidy-board 0.2.0, housekeeping 0.4.0, with CHANGELOG entries. The vendored copies of the engine in tidy-board and housekeeping are regenerated by their sync tools. publish-check does not change.

## Definition of done

- A batch with no `lang` opens in English; `"lang": "pt-BR"` opens in pt-BR; `--lang` overrides the batch; the toggle switches the chrome instantly, survives a reload, and an invalid saved value is ignored.
- A test proves the two `I18N` tables have identical keys and identical placeholders, and that no Portuguese literal is left in the page's code outside the table.
- `check` rejects `lang` values other than the two; every existing example batch still validates.
- A `scan --lang pt-BR` on each tool produces the cards the tools produced before this change, up to the accents and wording of pt-BR; `scan` without the flag produces English cards; `report` and `apply`/`restore` work on a batch whatever its language, and the ledger and `decisions.json` are identical in shape.
- The suites of ar-board, tidy-board, housekeeping, publish-check and the catalog pass, on Python 3.9 as well; all sync checks, `claude plugin validate`, doc-truth and publish-check are clean.
- A manual check in a browser, in both languages, of: the header toggle, the key bar, a decision, the review screen, the finish dialog, and an offline `build` page (the JavaScript is not executed by the suite).

## Evidence and its limits

- The page is one string of about 40 KB with roughly 140 user-visible multi-word strings, plus dynamic ones built in the JavaScript; the engine's command line has about 30 more messages (kept, out of scope). tidy-board builds about 35 card strings and todo-sweep about 15 plus the report headings. These are counts from reading the code, not measured by a tool.
- Five test files pin Portuguese UI or card text: `ar-board/tests/test_question_summary.py`, `ar-board/tests/test_labels_confirm.py`, `housekeeping/tests/test_ts_scan.py`, `housekeeping/tests/test_ts_report.py`, `tidy-board/tests/test_scan.py`. They are updated to the new default and parametrised over both languages, never deleted.
- The suite does not run the page's JavaScript (see `CLAUDE.md`), so the toggle and the dialogs are only verified by the manual browser check above.

## Risks

- A stale string: a Portuguese literal left in the JavaScript would show in the English page. The test that scans the page code for literals outside the table is the guard.
- The two tables drifting apart (a key or a placeholder missing in one). Guarded by the parity test.
- The default flip: someone who relied on Portuguese cards must now pass `--lang pt-BR`. The skills tell the agent to do it; the CHANGELOGs say it.
- The engine is vendored (byte copy) into tidy-board and housekeeping. A change in `ar_board.py` must be followed by both sync tools, or CI fails on drift.
- The pt-BR wording is drafted by the agent. A native reader (the owner) should skim it once.

## Out of scope

- Translating the content of cards the agent or the user wrote.
- The command-line output and error messages of the engine and the tools (still Portuguese, accent-free); the HTTP error bodies.
- A third language. The mechanism allows it: one more table in `I18N`, one more value accepted by `check` and `--lang`.
- Switching card text with the toggle (it needs both languages in every card).
- Translating the documentation beyond the language lines.

## Discarded alternatives

- **One page per language** (`?lang=` re-rendered by the server): the toggle would reload the page and the offline `build` page could not switch.
- **The dictionary inside the JavaScript string**: the same effect, but the suite does not execute JavaScript, so a missing key could not be tested.
- **Default from the environment** (`$LANG`): the output would depend on the machine, which is harder to test and to document.
- **Both languages in every tool card**, so the toggle changes cards too: roughly doubles the card data and the builders, for little gain while agent-written cards stay in one language.
- **Keeping accent-free Portuguese** for the pt-BR option: fewer test edits, but a pt-BR option that reads like ASCII-only text.

## Rulings in this spec

- **R1** Precedence: saved toggle, then `--lang`, then batch `lang`, then `en`. The user's own click wins over the agent's choice, so a Brazilian user keeps Portuguese across batches.
- **R2** `labels` and `confirm` are card content and do not follow the toggle; the panel's own button names do.
- **R3** The engine also accepts `low`/`medium`/`high` as risk levels (additive), because English cards written by an agent would otherwise lose their colour.
- **R4** Key letters stay `A R M S C` in both languages.
- **R5** `scan` records `lang` in `scan.json`; later commands read it from there and have no `--lang` of their own.
- **R6** The tools' command-line output stays Portuguese in this step; only the cards and the todo-sweep report follow `--lang`.
- **R7** Minor version bumps (1.4.0, 0.2.0, 0.4.0): the contract gains a field and the tools' default output changes.

## Open doubts

- Whether the command-line output should follow `--lang` in a later step. The agent reads it, so English would suit the English skills better, but the skills quote the Portuguese literals today and the tests pin them.
- The pt-BR wording of the panel and of the cards: drafted by the agent, to be skimmed by the owner.

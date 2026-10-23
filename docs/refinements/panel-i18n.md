# Refinement: a switchable panel language (English default, pt-BR)

- **Status:** built (ar-board 1.4.0, tidy-board 0.2.0, housekeeping 0.4.0, header-footer 0.4.0); the plan is [docs/plans/panel-i18n.md](../plans/panel-i18n.md)
- **Date:** 2026-10-15 (amended 2026-10-22)
- **Follows:** the English skills (PR #10, step 1). This is step 2: the panel the skills open, the cards the tools put on it and, since P08, every line the scripts print.
- **How it was refined:** the owner asked for "a bilingual panel interface, English by default, switchable to pt-BR". Three questions were answered with a recommendation each (toggle scope, pt-BR style, what `scan` does about language), then the design below was shown in chat and approved ("ok"). No web research: this is an internal design. On 2026-10-22, before the plan was executed, the owner extended the scope to the command-line output of every script (P08); the rulings R8-R18 were made while amending the plan and are listed below.
- **Read before writing (2026-10-15):** `plugins/ar-board/skills/ar-board/scripts/ar_board.py` (`PAGE`, `render_page`, `validate`, `cmd_serve`, `cmd_build`), the card builders of `tidy_board.py` and `todo_sweep.py`, and the tests that pin Portuguese UI text. **Read for the amendment (2026-10-22):** the command-line code of `ar_board.py`, `tidy_board.py`, `todo_sweep.py`, `doc_truth.py`, `handoff.py` and `header_footer.py`, their tests, the seven skills and the plugin READMEs.

## What it is

Today the panel is Portuguese only. After this change:

- the **panel chrome** (buttons, key bar, review screen, hints, dialogs) exists in English and pt-BR, English by default, switchable in the page without a reload;
- tidy-board and todo-sweep generate their **cards** (field labels, titles, reasons, button wording, the todo-sweep report) in a chosen language, English by default;
- the **command-line output** of every script except publish-check (which prints English already) exists in English and pt-BR, English by default: messages, `error:`/`warning:` lines, the text `summary`, the `check`/`scan`/`apply`/`report` lines; handoff's **notes** and header-footer's **weekday** follow the same language (P08);
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
| P08 | The command line (2026-10-22) | All user-visible text defaults to English, with pt-BR selectable, and this includes the command-line output (stdout/stderr messages, `erro:`/`aviso:` lines, the text `summary`, the check/scan/apply/report lines) of `ar_board.py`, `tidy_board.py`, `todo_sweep.py`, `doc_truth.py`, `handoff.py` and `header_footer.py`. It ships in this same branch and supersedes R6. publish-check prints English already and is out of scope. | owner's decision, 2026-10-22 |

## Design notes derived from the decisions

Every rule marked **R** is a ruling made while writing this spec or amending it; the owner may veto any of them (see *Rulings in this spec*).

### The contract (ar-board 1.4.0)

- `batch.json` gets an optional top-level `lang`: `"en"` or `"pt-BR"`. `check` rejects any other value, and a non-string, with an error; `null` counts as omitted, like every optional key (R9). A batch without `lang` is English.
- `serve` and `build` take `--lang en|pt-BR`. It overrides the batch's `lang` for what the page shows first.
- The page reads, in this order, the first that is set: the language saved by the toggle in the browser (`localStorage`, key `ar-board:lang`), then `--lang`, then the batch `lang`, then the environment variable `CAPYBARA_LANG` (R8), then `en`. A saved value that is not one of the two is ignored. **R1**
- The toggle sits in the header next to the live/offline badge. It switches the chrome at once, sets `<html lang>`, and saves the choice. It never touches the cards or `decisions.json`.
- Nothing about the language is stored in `decisions.json`, and the offline `Copiar` export (`AR-BOARD-RESULT`) has the same shape as before.

### The engine

- Every user-visible string of the page moves out of the JavaScript and the markup into `I18N = {"en": {...}, "pt-BR": {...}}` in the script. The two tables have the same keys and the same placeholders (`{n}`, `{total}`, ...). The page gets the table through the boot data it already receives, so the Content-Security-Policy does not change.
- The dynamic messages are covered too: the hints, the "Undecided items: N. Finish anyway?" dialog, the armed-confirmation text, the review-screen headings, the counts line.
- The panel's own button wording (Approve / Reject / Maybe, or the question-board equivalents) comes from the table. A batch-level `labels` and a card-level `confirm` are card content: they are shown as written and do not switch with the toggle. **R2**
- The risk words on a card are read as before (`baixo`/`médio`/`alto`, accents and case ignored) and now also `low`/`medium`/`high`. The CSS classes and colours do not change. **R3**
- `check`, `summary`, `wait`, the validation errors and every other message printed by the engine's command line follow the language of the run too (P08; see *The command line*). The HTTP error bodies do not change: they are part of the API the page reads (R13).
- The key letters (`A`, `R`, `M`, `S`, `C`) and the shortcuts do not change in either language. **R4**

### tidy-board 0.2.0 and housekeeping 0.4.0 (todo-sweep)

- Each tool gets a small string table per language and one function that formats from it. All the card text now built inline moves there: field labels (Proof, Where, Text, Age, Excerpt, ...), titles, effects, reasons for "do not touch", the group card, `LABELS` (Delete / Keep / Later for tidy-board, Resolve / Discard / Keep for todo-sweep), `confirm` texts, the subtitle, the age wording.
- `scan --lang en|pt-BR` (default `en`) selects the table. The language is written to `batch.json` as `lang` (so the page opens in it) and to the `scan.json` sidecar, so `report` and `apply`/`restore` use the same language later without being told. **R5** (amended by P08: every command also takes `--lang`, which wins over the recorded language, R17).
- Everything a script parses or compares stays language-independent: ids (`T01`, `G`), proof levels, decision values (`approved`/`rejected`/`maybe`), ledger keys, JSON keys. The ledger remembers decisions by id and decision, never by label.
- The todo-sweep `report.md` and `report.json` headings follow the scan's language. ~~The tools' other command-line output (the scan summary, `apply`'s per-item lines, errors) stays Portuguese, as for the engine. **R6**~~ Superseded by P08: the tools' other command-line output follows the language too.
- The old default changes: a `scan` without `--lang` now writes English cards. This is why these two plugins take a minor version.

### The command line (P08, 2026-10-22)

- **Resolution.** The language of a run is the first that is set of: `--lang`, the `lang` of the batch or scan the command reads, the environment variable `CAPYBARA_LANG`, `en`. header-footer reads `"lang"` from its `header-footer.json` where the others read a batch; its hooks (header, footer, state) take no flags and use the config, then `CAPYBARA_LANG`, then `en`; its CLI also takes `--lang`. Values are exactly `en` and `pt-BR`: a bad `--lang` exits 2 before anything is written; a bad `CAPYBARA_LANG` is ignored, never an error, with nothing on stderr (header-footer's `status`, the diagnostic command, lists it as a problem). **R8**
- **Tables.** Each script gets a `MSG = {"en": {...}, "pt-BR": {...}}` table and a `say()` helper; the two sides have the same keys and placeholders and are plain ASCII, so the pt-BR side is the accent-free Portuguese each script printed before, except that a count of one now takes the singular (`1 item`, not `1 itens`). A parity test and an AST guard (no Portuguese literal left in a function that prints) per script. **R10**
- **Accents.** pt-BR command-line text stays accent-free, as it always was (Windows consoles, the existing convention); tidy-board's `NAO TOCAR:` reasons therefore come from its command-line table, not from the accented card table. pt-BR page, card and report text keeps its accents. **R11**
- **Line tags.** The tags agents, skills and docs look for are the same in both languages: `AR-BOARD URL:`, `AR-BOARD DECISOES:`, `AR-BOARD ARQUIVO:`, `AR-BOARD-RESULT`, `TIDY-BOARD DIR:`, `TIDY-BOARD ITENS:`, `TIDY-BOARD:`, `SCAN:`, `REPORT:`, `APPLY:`, `RESTORE:`, `TIMEOUT:`, `ok:` and tidy-board's action words (`deleted`, `skipped`, `would-delete`). What reads as prose translates: `erro:`/`error:`, `aviso:`/`warning:`, `NAO TOCAR:`/`DO NOT TOUCH:`, todo-sweep's `lote:`/`batch:`, and the rest of every line. **R12**
- **Help and API.** The `--help` text is English in both languages (argparse prints its own words in English anyway); the engine's HTTP error bodies and every JSON output keep their shape (a few gain a `lang` key: `report.json`, handoff's data block, header-footer's `status --json`). **R13**
- **handoff's note.** The note is written in the language of the `write` run. Its pt-BR texts are exactly those of 0.3.1 (`Metainfo da sessao`, `Estado do git`, `[nao verificado]`), so every note written before this change is a pt-BR note; the data block records `lang` (a block without it is pt-BR), and `resume` and `verify` recognise the tool's parts of a note in either language, with or without the data block. The agent's metainfo keys (`Model`/`Modelo`, `Original request`/`Pedido original`, `Status`) and section headings (`What was done`/`O que foi feito`, `Decisions and why`/`Decisoes e por que`, `Next steps`/`Proximos passos`, `What failed or got stuck`/`O que falhou ou travou`) count in either language, and a missing one is named in the note's language; the tool's own row keys are reserved in both languages; a citation marked in either language is never marked again. A note never sets the language of a run: an old note is Portuguese and must not turn an English session's output Portuguese. **R14**
- **header-footer.** The header's `weekday` field (`Mon` … `Sun`, pt-BR `seg` … `dom`) and every message of the CLI follow the language; a new `lang en|pt-BR|auto` command sets or clears the config's `lang`. The footer does not change in either language: it must stay byte-identical to the Node status line it ports (its texts are `running`/`waiting`/`idle`, numbers and units). The instruction that goes with the `<reply-header>` line does not change either: it is addressed to the model. **R15**
- **doc-truth.** A finding's `value` and `fingerprint` never depend on the language (the `parity` value stays `falta README.pt-BR.md`), so an `allow` list survives a language switch; only the `message` and the report lines change. **R16**
- **Every command takes `--lang`.** Without it, the commands that read a scan (`check`, `apply`, `restore`, `report`) speak the language the scan recorded; `report --lang` also chooses the language of `report.md`, and `report.json` records it. **R17**
- **Plurals.** On the command line a count of one takes the singular in both languages. The page's two count phrases are worded so no agreement is needed (`Batch: x · items: 3 · round 1`, `Undecided items: 1. Finish anyway?`). **R18**

### The skills and the docs

- Seven `SKILL.md` files change: the four panel skills (ar-board, question-board, tidy-board, todo-sweep) stop saying the panel is Portuguese, and those four plus doc-truth, handoff and header-footer stop saying the command line is. They name each literal the panel or a script shows in English first, with the pt-BR wording next to it, and tell the agent: ask for the language the user writes in (`lang` in the batch it writes for ar-board and question-board; `--lang` on `scan` for tidy-board and todo-sweep, on `write` for handoff and on any command; `lang` in the config for header-footer), and write card, question and note content in that language. publish-check's skill does not change.
- The finish signal the panel asks the user to say becomes "done" (English panel) or "terminei" (pt-BR panel); the skills accept either, as they already accept "done"/"finished" next to "terminei".
- The READMEs' "Languages" lines, the root and plugin docs and `CLAUDE.md` say: skills in English; the panel, the generated cards and reports, the notes and the command-line output in English by default and pt-BR on request (`lang`, `--lang`, `CAPYBARA_LANG`). `CLAUDE.md` also drops "In-page UI strings are accent-free Portuguese" and says that the tables carry both languages. The short mentions that name the buttons, the note headings or the weekday as the tool's wording give the English form first and the pt-BR one in parentheses; the long ar-board reference documents keep their Portuguese quotes and say they are the pre-1.4.0 pt-BR wording.
- The generated single-file variants (`dist/*.SKILL.md`) follow from the sync tool.

### Versions

ar-board 1.4.0, tidy-board 0.2.0, housekeeping 0.4.0 and header-footer 0.4.0, with CHANGELOG entries. No plugin releases twice: each release carries its plugin's command-line work (housekeeping 0.4.0 also absorbs the unreleased handoff metainfo header). The vendored copies of the engine in tidy-board and housekeeping are regenerated by their sync tools. publish-check does not change.

## Definition of done

- A batch with no `lang` opens in English; `"lang": "pt-BR"` opens in pt-BR; `--lang` overrides the batch; `CAPYBARA_LANG` is the last fallback before English; the toggle switches the chrome instantly, survives a reload, and an invalid saved value is ignored.
- A test proves the two `I18N` tables have identical keys and identical placeholders, and that no Portuguese literal is left in the page's code outside the table.
- `check` rejects `lang` values other than the two; every existing example batch still validates.
- A `scan --lang pt-BR` on each tool produces the cards the tools produced before this change, up to the accents and wording of pt-BR; `scan` without the flag produces English cards; `report` and `apply`/`restore` work on a batch whatever its language, and the ledger and `decisions.json` are identical in shape.
- Every script but publish-check prints English by default and pt-BR with `--lang pt-BR`, with the batch's or scan's `lang`, or with `CAPYBARA_LANG=pt-BR`; a test per script pins the parity of its message table, its pt-BR side against the old output, and an AST guard against a Portuguese literal left in a function that prints; a bad `--lang` exits 2 and a bad `CAPYBARA_LANG` changes nothing.
- A handoff note written before this change resumes and verifies exactly as before; a note in either language is read by `resume` and `verify`; doc-truth fingerprints are the same in both languages; header-footer's footer is byte-identical in both languages.
- The suites of ar-board, tidy-board, housekeeping, header-footer, publish-check and the catalog pass, on Python 3.9 as well; all sync checks (header-footer's included), `claude plugin validate`, doc-truth and publish-check are clean.
- A manual check in a browser, in both languages, of: the header toggle, the key bar, a decision, the review screen, the finish dialog, and an offline `build` page (the JavaScript is not executed by the suite).

## Evidence and its limits

- The page is one string of about 40 KB with roughly 140 user-visible multi-word strings, plus dynamic ones built in the JavaScript. tidy-board builds about 35 card strings and todo-sweep about 15 plus the report headings. The command line (P08) adds, by message-table size: about 70 messages in the engine (the validation errors and the text summary are most of them), 90 in tidy-board, 50 in todo-sweep, 25 in doc-truth, 80 in handoff (its note texts included) and 50 in header-footer. These are counts from reading the code and from the tables the plan writes, not measured by a tool.
- Five test files pin Portuguese UI or card text: `ar-board/tests/test_question_summary.py`, `ar-board/tests/test_labels_confirm.py`, `housekeeping/tests/test_ts_scan.py`, `housekeeping/tests/test_ts_report.py`, `tidy-board/tests/test_scan.py`. With P08, about fifteen more pin Portuguese command-line text across the four plugins (for example `test_question_validate.py`, `test_cli.py`, `test_apply.py`, `test_dt_cli.py`, `test_ho_cli.py`, `test_ho_notes.py`, `test_ts_cli.py`, header-footer's `test_cli.py` and `test_header.py`). They are updated to the new default and gain a pt-BR case, never deleted; handoff's note-format tests write pt-BR notes explicitly, since that layout is also the layout of every older note.
- The suite does not run the page's JavaScript (see `CLAUDE.md`), so the toggle and the dialogs are only verified by the manual browser check above.
- The plan was replayed mechanically in a scratch clone after the amendment (every file instruction of Tasks 1 to 6), and the suites, sync checks, doc-truth and publish-check were run there; see the plan's *Verification of this plan*.

## Risks

- A stale string: a Portuguese literal left in the JavaScript would show in the English page. The test that scans the page code for literals outside the table is the guard; the AST guard per script does the same for the command line.
- The two tables drifting apart (a key or a placeholder missing in one). Guarded by the parity tests (page, cards, and each command line).
- The default flip: someone who relied on Portuguese cards, notes or command-line lines must now pass `--lang pt-BR` or set `CAPYBARA_LANG=pt-BR`. The skills tell the agent to do it; the CHANGELOGs say it. A script or a habit that greps a Portuguese message breaks unless it asks for pt-BR; the line tags stay put to keep the usual ones working.
- `CAPYBARA_LANG` in someone's shell changes every default at once (a feature, but a surprise in a test run): every plugin's test helpers clear it, and a bad value is ignored rather than fatal.
- The owner's own header changes: the `weekday` field reads `Mon` … `Sun` until `lang pt-BR` (or `CAPYBARA_LANG=pt-BR`) is set.
- handoff notes written before 0.4.0 must keep resuming: guarded by the unchanged pt-BR note layout and the tests that read an older note.
- The engine is vendored (byte copy) into tidy-board and housekeeping. A change in `ar_board.py` must be followed by both sync tools, or CI fails on drift.
- The pt-BR wording is drafted by the agent. A native reader (the owner) should skim it once.

## Out of scope

- Translating the content of cards the agent or the user wrote.
- The HTTP error bodies of the engine (API, read by the page) and argparse's own words (`usage:`, `invalid choice`), which stay English.
- publish-check, whose output is English already.
- A third language. The mechanism allows it: one more table in `I18N` and in each `MSG`, one more value accepted by `check` and `--lang`.
- Switching card text with the toggle (it needs both languages in every card).
- Translating the documentation beyond the language lines and the short mentions of the tools' wording.

## Discarded alternatives

- **One page per language** (`?lang=` re-rendered by the server): the toggle would reload the page and the offline `build` page could not switch.
- **The dictionary inside the JavaScript string**: the same effect, but the suite does not execute JavaScript, so a missing key could not be tested.
- **Default from the environment** (`$LANG`): the output would depend on the machine, which is harder to test and to document. (P08 adds a dedicated variable, `CAPYBARA_LANG`, as the last fallback only: it is the user's explicit choice, not the locale, and the tests clear it.)
- **Both languages in every tool card**, so the toggle changes cards too: roughly doubles the card data and the builders, for little gain while agent-written cards stay in one language.
- **Keeping accent-free Portuguese** for the pt-BR option: fewer test edits, but a pt-BR option that reads like ASCII-only text. (Kept for the command line, where it was already the convention, R11.)
- **English line tags** (`AR-BOARD DECISIONS:`, `TIDY-BOARD ITEMS:`): cleaner English output, but every agent, skill and doc that looks for the current tags would break at once (R12).
- **A note's language setting the language of `resume`**: an old note is Portuguese and would turn an English session's output Portuguese (R14).

## Rulings in this spec

- **R1** Precedence: saved toggle, then `--lang`, then batch `lang`, then `CAPYBARA_LANG`, then `en`. The user's own click wins over the agent's choice, so a Brazilian user keeps Portuguese across batches.
- **R2** `labels` and `confirm` are card content and do not follow the toggle; the panel's own button names do.
- **R3** The engine also accepts `low`/`medium`/`high` as risk levels (additive), because English cards written by an agent would otherwise lose their colour.
- **R4** Key letters stay `A R M S C` in both languages.
- **R5** `scan` records `lang` in `scan.json`; later commands read it from there. Amended by P08: they also take `--lang`, which wins (R17).
- **R6** ~~The tools' command-line output stays Portuguese in this step; only the cards and the todo-sweep report follow `--lang`.~~ Superseded by P08 (2026-10-22).
- **R7** Minor version bumps (1.4.0, 0.2.0, 0.4.0, and 0.4.0 for header-footer): the contract gains a field and the tools' default output changes.
- **R8** The language of a run: `--lang`, then the batch's or scan's `lang`, then `CAPYBARA_LANG`, then `en` (header-footer: its config instead of a batch); exact values only; a bad `CAPYBARA_LANG` is ignored, and header-footer's `status` reports it.
- **R9** `lang: null` counts as omitted, like every optional key of the batch.
- **R10** One `MSG` table per script, pt-BR side equal to the old output (accent-free), singular for a count of one; parity tests and an AST guard per script.
- **R11** The pt-BR command line stays accent-free; tidy-board's `NAO TOCAR:` reasons come from the command-line table; pt-BR page, card and report text keeps its accents.
- **R12** The line tags agents look for are the same in both languages; prose words translate.
- **R13** `--help` is English in both languages; the HTTP error bodies and the JSON shapes do not change.
- **R14** handoff writes its note in the language of the run, keeps the 0.3.1 layout for pt-BR, reads notes in either language and accepts the agent's keys and headings in either language; a note never sets the language of a run.
- **R15** header-footer: the weekday and the messages follow the language (config `lang`, `lang` command, `--lang`, `CAPYBARA_LANG`); the footer and the instruction to the model do not.
- **R16** doc-truth's finding values and fingerprints never depend on the language.
- **R17** Every command of every script takes `--lang`; `report --lang` also chooses the language of `report.md`.
- **R18** The page's count phrases avoid number agreement; the command line uses singular forms for one.

## Open doubts

- ~~Whether the command-line output should follow `--lang` in a later step.~~ Decided by the owner on 2026-10-22: it does, in this step (P08).
- Whether the line tags with Portuguese words (`AR-BOARD DECISOES:`, `AR-BOARD ARQUIVO:`, `TIDY-BOARD ITENS:`) should get English names in a later, coordinated change of the skills and docs (R12 keeps them).
- The name `CAPYBARA_LANG` and whether the owner's own machine should set it to `pt-BR` (the header's weekday turns English otherwise).
- The pt-BR wording of the panel and of the cards: drafted by the agent, to be skimmed by the owner.

## Amendments made while planning and building

- **Codes, not text, below the cards.** tidy-board's inventory holds reason codes (`base_branch`, `current_branch`, `main_worktree`, `current_worktree`, `locked`, `missing_dir`, `unreadable`, `dirty`), `pr` as `None`/`{}`/`{number, tip_matches}` and `remote` as `None`/`exists`/`removed`/`none`; todo-sweep's `age_reason` is a code (`max_blame`, `no_history`, `uncommitted`, `shallow`). The text is rendered from the tables when the cards are built. `scan.json` keeps its shape (tidy-board writes the rendered reasons there, in the scan's language).
- **`report.json`** keeps its keys (`resolver`, `descartar`, `manter`, `sem_decisao`) and records `lang`; only `report.md` follows the language (`report --lang`, else the scan's).
- **The shipped examples follow the new default** (`"lang": "en"`, English labels, an English handoff note); the Portuguese reference batches inside the ar-board and question-board skills set `"lang": "pt-BR"`.
- **A bad `--lang`** exits 2 through argparse (`invalid choice`) on every command; todo-sweep's own parser prints it as an `error:` line (pt-BR `erro:`) and header-footer as a usage error. Nothing is written.
- **The panel's two count phrases** are worded without number agreement (`Batch: x · items: 3 · round 1`, `Undecided items: 1. Finish anyway?`); the command line takes the singular for a count of one.

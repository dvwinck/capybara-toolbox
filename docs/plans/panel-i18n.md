# Switchable panel language Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every user-visible text of the toolbox English by default and pt-BR on demand: the ar-board panel (a `lang` field in the batch, `--lang`, an EN/PT toggle remembered in the browser), the cards and the report tidy-board and todo-sweep write (`scan --lang`), handoff's notes, header-footer's weekday, and the command-line output of every script but publish-check (`--lang` on every command, the batch's or scan's `lang`, the `CAPYBARA_LANG` environment variable); have the skills ask for the language the user writes in; released as ar-board 1.4.0, tidy-board 0.2.0, housekeeping 0.4.0 and header-footer 0.4.0.

**Architecture:** Every user-visible string of the page moves out of the markup and the JavaScript into one Python table, `I18N = {"en": {...}, "pt-BR": {...}}`, injected through the boot data the page already receives (no CSP change; the offline `build` page switches too). The page resolves its language as saved toggle, then `--lang`, then batch `lang`, then `en`, and asks `T('key')` for every text; a parity test pins the two tables and a guard test scans `PAGE` for any literal left outside the table. tidy-board and todo-sweep get a `TEXT`/`LABELS` table per language and one `t(lang, key, **values)` function; their inventories and sidecars hold **codes** (proof levels, reason codes, `age_reason` codes, PR and remote states), never text, so `apply`, `restore`, `report` and the ledger are language independent. The engine is vendored (byte copy) into tidy-board and housekeeping, so every engine change is followed by the three sync tools. The command line of each script gets its own `MSG` table (`en` and `pt-BR`, both plain ASCII: the pt-BR side is the accent-free output the scripts printed before) and a `say()` helper; the language of a run resolves `--lang`, then the batch's or scan's `lang`, then `CAPYBARA_LANG`, then `en`, and only `main()` sets it (the engine passes it explicitly). An AST guard per script flags any Portuguese literal left in the functions that print.

**Tech Stack:** Python 3.9+ standard library (`unittest`, throwaway git repositories), plain HTML/CSS/JavaScript inside the `PAGE` string (not executed by the suite; `node --check` in CI, a manual browser check at the end).

**Spec:** [docs/refinements/panel-i18n.md](../refinements/panel-i18n.md) (decisions P01-P08, rulings R1-R18; P08 is the owner's decision of 2026-10-22 that puts the command-line output in scope and supersedes R6). Conventions this plan follows: [CLAUDE.md](../../CLAUDE.md). The spec wins where the two disagree; the rulings this plan adds are listed under *Rulings made while planning*.

## Global Constraints

- Python standard library only, Python 3.9 compatible (no `match`, no `X | Y` runtime types, no `str.removeprefix`); `git` is required by tidy-board and housekeeping. The plan was verified on the machine's default Python (3.15) and on the system Python 3.9.6.
- No network, anywhere.
- Never edit generated files by hand: `plugin.json`, `marketplace.json`, the vendored `capy_board.py` copies, `dist/*.SKILL.md`, `question-board/scripts/ar_board.py`. Run the sync tools in the order CLAUDE.md gives: `python3 plugins/ar-board/tools/sync.py`, then `python3 plugins/tidy-board/tools/sync.py` and `python3 plugins/housekeeping/tools/sync.py`, then `python3 tools/marketplace.py`; header-footer has its own `python3 plugins/header-footer/tools/sync.py` (Task 5e).
- One plugin version for all scripts of housekeeping: `doc_truth.py`, `handoff.py` and `todo_sweep.py` carry the same `VERSION` and header comment, and `plugins/housekeeping/tools/sync.py --check` fails otherwise.
- Every user-visible text is English by default and pt-BR on request (spec P08): the page, the cards, the todo-sweep report, handoff's notes, header-footer's weekday and the command-line output of every script but publish-check. pt-BR page, card and report text is written with accents (UTF-8); the pt-BR command line stays accent-free, as it always was (Windows consoles, the existing convention), and so do handoff's pt-BR note texts (a pt-BR note is byte-identical to a 0.3.1 note). tidy-board's `NAO TOCAR:` reasons therefore come from its command-line table, never from the accented card table.
- The language of a run: `--lang`, then the `lang` of the batch or scan the command reads (`check`, `summary`, `wait`, `serve`, `build`, tidy-board's `check`/`apply`/`restore`, todo-sweep's `check`/`report`), then the environment variable `CAPYBARA_LANG`, then `en`; header-footer reads `lang` from its `header-footer.json` where the others read a batch, and its hooks take no flag. Values are exactly `en` and `pt-BR`: a bad `--lang` exits 2 before anything is written, a bad `CAPYBARA_LANG` is ignored (never an error; header-footer's `status` lists it as a problem). The page applies the browser's saved toggle on top (R1). A handoff note never sets the language of a run.
- Commit hygiene: every commit is authored with the owner's personal address, which the repo-local git config already pins (print it with `git config --local user.email`; never the work address). Wherever this plan writes `OWNER_EMAIL`, that is the address. The message ends with the single line `Co-Authored-By: Claude <model> <noreply@anthropic.com>` naming the model that executes the task (the commands below write `Claude Sonnet 5.5`; put the real one) and NO claude.ai session link or any other trailer (publish-check flags the link); plain multi-line body.
- No push and no PR unless the owner asks. `git add -A` before doc-truth (it judges the git tree). `PYTHONDONTWRITEBYTECODE=1` for tests.
- Dates in changelogs are the execution day: wherever this plan writes `DAY`, write the output of `date +%Y-%m-%d`.
- Scratch files of the manual steps go in a fresh `mktemp -d` directory, never in a fixed `/tmp` path.
- Lessons from the housekeeping build: every new failure path ends in `error: ...` (pt-BR `erro: ...`; the engine's `invalid batch.json:` list, pt-BR `batch.json invalido:`) and exit 2 (engine `check`: exit 1), never a traceback; `lang` values read from files are data (validated against `LANGS`, never used as code, as a format string or in a path); nothing is parsed from label text; tests that pin text are updated, never deleted; each task ends green on its own suite (the transient reds are named where they happen).

## Review Focus

Failure modes the spec implies but a first pass would not test; each line has a test in the task that owns the code.

- **A leftover literal on the page** (a Portuguese or English string left in the markup or the JavaScript outside the table, so one language shows the other's text): `PageLanguageGuardTest.test_no_literal_of_the_page_reads_as_text_outside_the_table` scans every JS string literal and every markup text node and prints what it finds (Task 2).
- **Table key or placeholder drift** (a key missing in one language, a `{placeholder}` renamed on one side, a key the page asks for that no table has, a table key no page uses): `TableTest.test_the_two_tables_have_the_same_keys_and_the_same_placeholders` (Task 1) and `PageLanguageGuardTest.test_every_key_the_page_uses_exists_and_every_key_of_the_table_is_used` (Task 2); the same parity test exists for the two tool tables (Tasks 4 and 5).
- **The toggle with an invalid saved value** (`localStorage` holding `xx` or a stale value): the page keeps `BOOT.lang`; `test_the_precedence_is_saved_toggle_then_boot_then_english` pins the exact guard and the manual check reloads with a bad value (Tasks 2 and 7).
- **A batch with a bad `lang`** (`"pt"`, `"EN"`, `""`, a number, a list): `check` lists `field 'lang' must be en or pt-BR` (pt-BR `campo 'lang' deve ser en ou pt-BR`) and exits 1; `render_page` falls back to English instead of breaking the page (`ValidateLangTest`, `ResolveLangTest`, Task 1).
- **An older batch or scan without `lang`**: the page opens in English; tidy-board `check` and todo-sweep `check`/`report` accept a `scan.json` without `lang` and read it as English (`ResolveLangTest`, Task 1; `LanguageBoardTest`, Task 4; `LanguageReportTest.test_an_older_scan_without_lang_reports_in_english`, Task 5).
- **A `decisions.json`, ledger or `applied.json` produced in one language and read after a rerun in the other**: nothing in them carries a language (`test_the_export_and_the_decisions_carry_no_language`, Task 2); a pt-BR tidy-board batch is applied and restored exactly like an English one (`LanguageApplyTest`, Task 4); a ledger written by a pt-BR report is honoured by an English scan (`LanguageReportTest.test_a_ledger_written_by_a_pt_br_report_is_honoured_by_an_english_scan`, Task 5).
- **Label text containing markup or backticks** (a batch `labels` text such as `<img onerror=1>`, a branch name with a backtick): labels are escaped wherever they reach the DOM (the existing `LabelsPageGuardsTest`, kept, plus `test_batch_labels_and_confirm_are_card_content_shown_as_written`, Task 2); the tool tables are plain text and every value a tool substitutes passes `safe_text`/`shown` (`test_reasons_pr_remote_and_age_render_in_both_languages`, Task 4; `test_backticks_in_names_cannot_open_a_code_span_on_the_card`, kept, Task 5).
- **`scan --lang` with a bad value**: refused by argparse before anything is written, exit 2 (`LanguageCliTest`, Tasks 4 and 5; todo-sweep prints its `error:` line, pt-BR `erro:`); a bad value edited into `scan.json` is refused by `check` and by `report` before anything is written (Tasks 4 and 5).
- **`report` on a batch whose scan has no `lang`** (an older scan): English headings, `report.json` records `"lang": "en"` (Task 5).
- **A Portuguese literal left in a function that prints** (one message missed while moving the text to a table, so an English run prints Portuguese): an AST guard per script lists every string constant of those functions that contains a word of the old output (`test_no_portuguese_literal_is_left_in_the_functions_that_print`, Tasks 2b, 4b, 5b, 5c, 5d, 5e).
- **Message table drift** (a key or a placeholder missing in one language, or accents creeping into the command line): a parity and plain-ASCII test per `MSG` table, plus one that pins the pt-BR side to the old output (Tasks 2b to 5e).
- **A placeholder named like the helper's own argument** (`{key}` in a template while `say()` took `key`): `say(msg_id, /, **values)` is positional-only, and `test_a_placeholder_named_like_an_argument_is_still_substituted` (Task 4b) renders such a message.
- **The language of one run leaking into the next** (the tests call `main()` and the command functions in-process): only `main()` sets `CLI_LANG` and puts it back in a `finally`; each tool's tests assert the default after a pt-BR run (Tasks 4b, 5b, 5c, 5d, 5e).
- **`CAPYBARA_LANG` with a bad value** (`pt`, `pt_BR`, `PT-BR`, empty): ignored, never an error, nothing on stderr (Tasks 2b to 5d); header-footer's `status` lists it as a problem (Task 5e).
- **An error about a scan's folder in the wrong language** (`apply` refusing a pt-BR board in English): `main()` reads the folder's `scan.json` language before the command runs (`recorded_lang`, Tasks 4b and 5d).
- **A handoff note written before this change** (pt-BR, no `lang` in its data block): its header, git section and data block are still recognised as the tool's, so `resume` and `verify` check only the agent's citations and report no drift (`test_a_note_without_lang_in_its_data_block_is_read_as_pt_br`, the existing note-format tests, Task 5c); a citation already marked in either language is never marked twice.
- **An accepted doc-truth finding revived by a language switch**: a finding's `value` and `fingerprint` are the same in both languages (`test_a_finding_keeps_its_value_and_fingerprint_in_both_languages`, Task 5b).
- **The header-footer footer changing with the language** (it must stay byte-identical to the Node status line it ports): `test_the_footer_is_the_same_in_both_languages` (Task 5e).
- **"1 items", "1 days"**: a count of one takes the singular in both languages on the command line (`_1` keys, Tasks 2b to 5d); the page avoids the agreement altogether (`items: N`, `Undecided items: N`, Task 1); todo-sweep's card age keeps `{days} days` (Task 5) and tidy-board's has `age_day`.

## Rulings made while planning

The spec states the command-line ones as R8-R18 (amended 2026-10-22); the others are written into its amendments in Task 7. The owner may veto any of them.

- **`lang: null` counts as omitted**, like every other optional key of the batch (`tag`, `meta`, `risk`, `fields`); `check` rejects every other non-string. The spec ratifies it (R9).
- **The `NAO TOCAR:` lines of tidy-board's scan** come from its command-line table: `DO NOT TOUCH: main (base branch of the repository)` in English, `NAO TOCAR: main (branch base do repositorio)` in pt-BR, accent-free like the rest of the command line (spec R11). Task 4 prints the accented card reason for one commit; Task 4b replaces it before the release.
- **todo-sweep's `age_reason` becomes a code** (`max_blame`, `no_history`, `uncommitted`, `shallow`, or empty) in the hits and in `scan.json`, rendered on the card in the chosen language. It is read by nothing else; the tests that pinned the Portuguese text now pin the code.
- **tidy-board's inventory holds codes**: `untouched[].why` is a code (`base_branch`, `current_branch`, `main_worktree` with `path`, `current_worktree`, `locked`, `missing_dir`, `unreadable`, `dirty` with `count`), `pr` is `None` / `{}` / `{number, tip_matches}` and `remote` is `None` / `exists` / `removed` / `none`. `scan.json` keeps its shape: `untouched[].why` is written there as the rendered text in the scan's language, as before.
- **`report.json` keeps its keys** (`resolver`, `descartar`, `manter`, `sem_decisao`) and gains `lang`; only `report.md`'s headings and lines follow the language. The spec's "report.json headings" are those keys, which scripts read.
- **`test_question_summary.py` is updated** (Task 2b): the text `summary` is command-line output, English by default now; its Portuguese pins become the pt-BR case.
- **The shipped examples follow the new default**: tidy-board's and todo-sweep's examples carry `"lang": "en"` and English labels (the tests compare them with what `scan` writes); ar-board's and question-board's examples (English content) carry `"lang": "en"`, and the Portuguese reference batches inside the two SKILL.md files carry `"lang": "pt-BR"`.
- **Docs beyond the language lines**: besides the READMEs' language lines and `CLAUDE.md`, the short mentions that name the buttons, the note headings or the weekday as the tool's wording get the English form first and the pt-BR one in parentheses (`Delete (Apagar)`; the tidy-board, housekeeping and header-footer READMEs, `CLAUDE.md`), and of `docs/reference.md` and `docs/pt-BR/guia-completo.md` only the header sentence, the CLI tables (`--lang`, the English lines), the risk words and the completion banner are touched; their header says the other Portuguese quotes are the pre-1.4.0 pt-BR wording (translating those documents is out of scope).
- **A bad `--lang` exits 2 through argparse** (`usage:` plus `invalid choice`) on every command of the engine, tidy-board, doc-truth and handoff; todo-sweep's own `Parser` prints it as an `error:` line (in pt-BR the translated `erro: argumento ...` of 0.3.1); header-footer, which has no argparse, refuses it as a usage error. Nothing is written.
- **Line tags stay put**: `AR-BOARD URL:`, `AR-BOARD DECISOES:`, `AR-BOARD ARQUIVO:`, `AR-BOARD-RESULT`, `TIDY-BOARD DIR:`, `TIDY-BOARD ITENS:`, `TIDY-BOARD:`, `SCAN:`, `APPLY:`, `RESTORE:`, `REPORT:`, `TIMEOUT:`, `ok:` and tidy-board's action words (`deleted`, `skipped`, `would-delete`) are the same in both languages: agents, skills and docs look for them, like JSON keys. What reads as prose translates: `erro:`/`error:`, `aviso:`/`warning:`, `NAO TOCAR:`/`DO NOT TOUCH:`, todo-sweep's `lote:`/`batch:`, and the rest of every line.
- **The `--help` text is English in both languages**: argparse prints its own words (`usage:`, `options:`) in English anyway; header-footer's `--help` was English already.
- **The HTTP error bodies of the engine do not change**: they are part of the API the page reads, not command-line output.
- **One language per run, set in one place**: the engine passes the language explicitly (`validate(b, lang)`, `render_summary(..., lang=)`); the tools keep a module `CLI_LANG` that only `main()` sets (reading the folder's `scan.json` first for the commands that work on a board) and puts back, so no command function ever changes it. `scan` uses that one language for its cards too.
- **`report --lang`** chooses `report.md`'s language as well as the messages; without it the report follows the scan (R5 kept as the default). `report.json` records the language used.
- **handoff's note**: written in the language of the `write` run; its pt-BR texts are exactly those of 0.3.1 (so every older note is a pt-BR note, and `resume`/`verify` recognise the tool's parts in either language, with or without the data block, which now records `lang`); the agent's metainfo keys (`Model`/`Modelo`, `Original request`/`Pedido original`, `Status`) and section headings count in either language and a missing one is named in the note's language; the tool's own row keys are reserved in both languages; a citation marked in either language is never marked again. The example note is English, the new default.
- **header-footer**: the `weekday` field and every message follow the language (`lang` in the config, the new `lang en|pt-BR|auto` command, `--lang`, `CAPYBARA_LANG`); the footer (byte-identical to the Node status line: `running`/`waiting`/`idle`, numbers and units) and `INSTRUCTION` (addressed to the model) are the same in both; `status` names the language and its source and reports a bad `CAPYBARA_LANG`.
- **doc-truth**: a finding's `value` and `fingerprint` never depend on the language (the `parity` value stays `falta README.pt-BR.md`), so an `allow` list survives a language switch; only `message` and the report lines change.
- **applied.json**: unchanged in shape; the `reason` of a skipped item is text in the language of the `apply` run (nothing reads it back).
- **Plurals**: a count of one takes the singular on the command line (`_1` keys in the tables: `1 item`, `1 apagado`, `1 citacao`); the page's two count phrases are reworded so no agreement is needed (`Batch: x · items: 3 · round 1`, `Undecided items: 1. Finish anyway?`).
- **Skills**: the four panel skills plus doc-truth, handoff and header-footer change (seven, not the spec's first estimate of eight); publish-check's does not.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `plugins/ar-board/skills/ar-board/scripts/ar_board.py` | `LANGS`, `DEFAULT_LANG`, the `I18N` table, `resolve_lang`, `lang` validation, `--lang` on `serve`/`build`, the boot data, and the `PAGE` string (markup, CSS, JavaScript with `T()`, `applyLang()`, the toggle) (Tasks 1-2); `MSG`, `say()`, `env_lang()`, `--lang` on every command, `validate`/`render_summary` in a language (Task 2b). |
| `plugins/ar-board/skills/question-board/scripts/ar_board.py`, `plugins/tidy-board/skills/tidy-board/scripts/capy_board.py`, `plugins/housekeeping/skills/todo-sweep/scripts/capy_board.py`, `plugins/ar-board/dist/*.SKILL.md` | Generated byte copies of the engine and the single-file variants: regenerated by the sync tools, never edited. |
| `plugins/ar-board/tests/test_lang.py` (new), `test_page.py`, `test_labels_confirm.py`, `test_cli.py`, `test_validate.py` | Table parity, validation, resolution, boot data, CLI flags; the page guards; the pinned Portuguese literals updated. |
| `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py` | `LANGS`, `TEXT`, `LABELS`, `t()`, `check_lang`, codes in `inventory`, `reason_text`/`pr_text`/`remote_text`, cards and `build_scan` in a language, `--lang`, `lang` in `scan.json` (Task 4); `MSG`, `say()`, `CLI_LANG`, `--lang` on every command (Task 4b). |
| `plugins/tidy-board/tests/test_scan.py`, `test_inventory.py`, `test_apply.py`, `test_skill.py`, `test_package.py`, `plugins/tidy-board/skills/tidy-board/examples/*.json` | Both languages tested; the examples in the new default. |
| `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py` | `LANGS`, `TEXT`, `LABELS`, `AGE_REASONS`, `t()`, `check_lang`, cards and the report in a language, `--lang`, `lang` in `scan.json` and `report.json` (Task 5); `MSG`, `say()`, `CLI_LANG`, `--lang` on every command (Task 5d). |
| `plugins/housekeeping/tests/test_ts_scan.py`, `test_ts_report.py`, `test_ts_cli.py`, `test_skills.py`, `plugins/housekeeping/skills/todo-sweep/examples/*.json` | Both languages tested; the examples in the new default. |
| `plugins/ar-board/tests/test_cli_lang.py` (new), `helpers.py`, `test_question_validate.py`, `test_question_summary.py` | The engine's command line in both languages, `CAPYBARA_LANG`, the AST guard (Task 2b). |
| `plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py`, `plugins/housekeeping/tests/test_dt_cli.py`, `test_dt_parity_versions.py`, `helpers.py` | doc-truth's `MSG`, `--lang`, stable fingerprints (Task 5b). |
| `plugins/housekeeping/skills/handoff/scripts/handoff.py`, `plugins/housekeeping/skills/handoff/examples/note.example.md`, `plugins/housekeeping/tests/test_ho_*.py`, `test_skills.py` | handoff's `NOTE` and `MSG` tables, notes in either language, older notes still resume (Task 5c). |
| `plugins/housekeeping/tests/test_ts_cli.py` (and the pins of `test_ts_scan.py`, `test_ts_report.py`) | todo-sweep's command line in both languages (Task 5d). |
| `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, `plugins/header-footer/tests/helpers.py`, `test_cli.py`, `test_header.py` | header-footer's `MSG`, `FIELD_HELP`, `WEEKDAYS`, `lang` in the config, the `lang` command (Task 5e). |
| `plugins/*/CHANGELOG.md`, `plugins/*/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | Releases ar-board 1.4.0, tidy-board 0.2.0, housekeeping 0.4.0 and header-footer 0.4.0 (the manifests and the catalog through the sync tools). |
| The seven skills (`ar-board`, `question-board`, `tidy-board`, `todo-sweep`, `doc-truth`, `handoff`, `header-footer` `SKILL.md`), the examples, the eight plugin READMEs (EN and pt-BR), `plugins/ar-board/docs/*`, `CLAUDE.md`, `docs/refinements/panel-i18n.md` | The agent asks for the language; the docs say that everything is English by default and pt-BR on request, and how to ask for it. |

---

### Task 0: Pre-flight: the branch and the baseline

**Files:**
- No files.

**Interfaces:**
- Produces: the work branch `feat/panel-i18n`. It exists already: it was cut from `base` (the spec and the first version of this plan are on `base`), and it holds the commit that amended the spec and this plan for the command line.

- [ ] **Step 1: Switch to the branch and check who commits**

Every commit is authored with the owner's personal address (the repo-local git config, never the work address).

Run: `git switch feat/panel-i18n && git status --short && git config --local user.email`

Expected: the branch is checked out with a clean tree and the owner's personal address (OWNER_EMAIL) is printed; a livon.io address means stop and fix the config.

- [ ] **Step 2: Record the baseline**

Run: `for d in tests plugins/ar-board/tests plugins/publish-check/tests; do PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s $d 2>&1 | tail -n 3; done`

Expected: three runs ending in `OK`: catalog `Ran 11 tests`, ar-board `Ran 202 tests`, publish-check `Ran 105 tests`. The tidy-board suite (133 tests, about two minutes), the housekeeping suite (377 tests, about a minute) and the header-footer suite (87 tests) are run when their tasks start.

### Task 1: Engine, Python side: the `I18N` table, `lang`, `--lang` and the boot data

**Files:**
- Modify: `plugins/ar-board/skills/ar-board/scripts/ar_board.py` (constants after `MAX_LABEL`, `validate`, a new section before `# ---- pagina`, `render_page`, `make_handler`, `cmd_serve`, `cmd_build`, `main`)
- Modify: `plugins/ar-board/tests/test_cli.py`, `plugins/ar-board/tests/test_validate.py` (the `Namespace` objects gain `lang`)
- Create: `plugins/ar-board/tests/test_lang.py`

**Interfaces:**
- Produces: `LANGS = ("en", "pt-BR")`, `DEFAULT_LANG = "en"`, `I18N` (dict of two dicts with identical keys; values are plain text with `{name}` placeholders), `resolve_lang(batch, flag=None) -> str`, `validate` accepting an optional `lang`, `render_page(batch, state, token, live, lang=None)` whose boot JSON gains `"lang"` (the resolved language) and `"i18n"` (the whole table), `make_handler(store, token, lang=None)`, `--lang {en,pt-BR}` on `serve` and `build` (default `None`: the batch decides).
- Consumed by Task 2 (the page reads `BOOT.i18n` and `BOOT.lang`), Tasks 4 and 5 (`lang` in the batches the tools write is validated by `check`).

- [ ] **Step 1: Write the failing tests**

`test_lang.py` pins the table's shape, the validation of `lang`, the resolution order, the boot data and the command line. It also checks that every example batch shipped in the repository still validates (spec, Definition of done).

Create `plugins/ar-board/tests/test_lang.py`:

```python
import contextlib
import io
import json
import re
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from argparse import Namespace
from http.server import ThreadingHTTPServer
from pathlib import Path

from helpers import REPO, SCRIPT, ab, make_batch

PLACEHOLDER = re.compile(r"\{(\w+)\}")


def board(**extra):
    b = {"batch_id": "t", "title": "T", "items": [{"id": "A01", "title": "x"}]}
    b.update(extra)
    return b


def boot_of(page):
    """The BOOT object the page starts from (the JSON the server injects)."""
    return json.loads(re.search(r"const BOOT = (\{.*?\});\n", page).group(1))


class TableTest(unittest.TestCase):
    def test_both_languages_are_shipped_and_english_is_the_default(self):
        self.assertEqual(ab.LANGS, ("en", "pt-BR"))
        self.assertEqual(ab.DEFAULT_LANG, "en")
        self.assertEqual(set(ab.I18N), set(ab.LANGS))

    def test_the_two_tables_have_the_same_keys_and_the_same_placeholders(self):
        en, pt = ab.I18N["en"], ab.I18N["pt-BR"]
        self.assertEqual(set(en), set(pt))
        for key in en:
            with self.subTest(key=key):
                self.assertEqual(set(PLACEHOLDER.findall(en[key])), set(PLACEHOLDER.findall(pt[key])))

    def test_every_value_is_plain_non_empty_text(self):
        for lang, table in ab.I18N.items():
            for key, value in table.items():
                with self.subTest(lang=lang, key=key):
                    self.assertIsInstance(value, str)
                    self.assertTrue(value.strip())
                    for ch in "<>&":
                        self.assertNotIn(ch, value)  # values reach innerHTML unescaped

    def test_the_portuguese_table_is_written_with_accents(self):
        text = " ".join(ab.I18N["pt-BR"].values())
        for word in ("decisão", "Comentário", "opção", "Concluído"):
            self.assertIn(word, text)
        self.assertNotIn("decisao", text)


class ValidateLangTest(unittest.TestCase):
    def test_the_two_languages_and_null_are_accepted(self):
        for value in ("en", "pt-BR", None):
            with self.subTest(lang=value):
                self.assertEqual(ab.validate(board(lang=value)), [])
        self.assertEqual(ab.validate(board()), [])

    def test_any_other_value_or_a_non_string_is_rejected(self):
        for bad in ("pt", "EN", "en-US", "", " en", 1, True, ["en"], {"en": 1}):
            with self.subTest(lang=bad):
                errs = ab.validate(board(lang=bad))
                self.assertEqual(errs, ["campo 'lang' deve ser en ou pt-BR"])

    def test_a_lang_error_does_not_hide_item_errors(self):
        errs = ab.validate(board(lang="xx", items=[{"id": "A01"}]))
        self.assertTrue(any("'lang'" in e for e in errs), errs)
        self.assertTrue(any("'title' obrigatorio" in e for e in errs), errs)

    def test_every_shipped_example_batch_still_validates(self):
        examples = sorted((REPO / "plugins").glob("*/skills/*/examples/batch.example.json"))
        self.assertGreaterEqual(len(examples), 4)
        for path in examples:
            with self.subTest(example=str(path.relative_to(REPO))):
                self.assertEqual(ab.validate(json.loads(path.read_text(encoding="utf-8"))), [])


class ResolveLangTest(unittest.TestCase):
    def test_a_batch_without_lang_opens_in_english(self):
        self.assertEqual(ab.resolve_lang(board()), "en")
        self.assertEqual(ab.resolve_lang(board(lang=None)), "en")

    def test_the_batch_lang_is_used(self):
        self.assertEqual(ab.resolve_lang(board(lang="pt-BR")), "pt-BR")

    def test_the_flag_wins_over_the_batch(self):
        self.assertEqual(ab.resolve_lang(board(lang="pt-BR"), "en"), "en")
        self.assertEqual(ab.resolve_lang(board(), "pt-BR"), "pt-BR")

    def test_an_unknown_value_falls_back_to_english_instead_of_breaking_the_page(self):
        self.assertEqual(ab.resolve_lang(board(lang="xx")), "en")
        self.assertEqual(ab.resolve_lang(board(lang=["pt-BR"]), None), "en")
        self.assertEqual(ab.resolve_lang(board(lang="pt-BR"), "xx"), "pt-BR")


class BootDataTest(unittest.TestCase):
    def test_the_page_receives_both_tables_and_the_resolved_language(self):
        boot = boot_of(ab.render_page(board(), {"items": {}}, "tok", True).decode("utf-8"))
        self.assertEqual(boot["lang"], "en")
        self.assertEqual(boot["i18n"], ab.I18N)

    def test_the_batch_lang_and_the_flag_reach_the_page(self):
        page = ab.render_page(board(lang="pt-BR"), {"items": {}}, "tok", True).decode("utf-8")
        self.assertEqual(boot_of(page)["lang"], "pt-BR")
        page = ab.render_page(board(lang="pt-BR"), {"items": {}}, "tok", True, "en").decode("utf-8")
        self.assertEqual(boot_of(page)["lang"], "en")

    def test_the_offline_page_carries_the_tables_too(self):
        page = ab.render_page(board(lang="pt-BR"), {"items": {}}, "", False).decode("utf-8")
        boot = boot_of(page)
        self.assertEqual((boot["live"], boot["lang"]), (False, "pt-BR"))
        self.assertIn("Concluído", page)
        self.assertIn("Finished.", page)


class CommandLineTest(unittest.TestCase):
    def test_build_takes_lang_and_the_batch_lang_is_the_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = make_batch(tmp, lang="pt-BR")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ab.cmd_build(Namespace(dir=str(d), lang=None)), 0)
            self.assertEqual(boot_of((d / "board.html").read_text(encoding="utf-8"))["lang"], "pt-BR")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ab.cmd_build(Namespace(dir=str(d), lang="en")), 0)
            self.assertEqual(boot_of((d / "board.html").read_text(encoding="utf-8"))["lang"], "en")

    def test_serve_passes_its_lang_to_the_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = make_batch(tmp)
            srv = ThreadingHTTPServer(("127.0.0.1", 0), ab.make_handler(ab.Store(d), "tok", "pt-BR"))
            thread = threading.Thread(target=srv.serve_forever, daemon=True)
            thread.start()
            try:
                with urllib.request.urlopen("http://127.0.0.1:%d/?t=tok" % srv.server_address[1], timeout=5) as r:
                    page = r.read().decode("utf-8")
            finally:
                srv.shutdown()
                srv.server_close()
            self.assertEqual(boot_of(page)["lang"], "pt-BR")

    def test_check_rejects_a_bad_lang_with_exit_code_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = make_batch(tmp, lang="xx")
            r = subprocess.run([sys.executable, "-I", str(SCRIPT), "check", str(d)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("campo 'lang' deve ser en ou pt-BR", r.stderr)
            self.assertNotIn("Traceback", r.stderr)

    def test_an_unknown_lang_flag_is_refused_before_anything_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = make_batch(tmp)
            for cmd in ("build", "serve"):
                with self.subTest(cmd=cmd):
                    r = subprocess.run([sys.executable, "-I", str(SCRIPT), cmd, str(d), "--lang", "xx"], capture_output=True, text=True)
                    self.assertEqual(r.returncode, 2)
                    self.assertIn("invalid choice: 'xx'", r.stderr)
            self.assertEqual(sorted(p.name for p in Path(d).iterdir()), ["batch.json"])

    def test_help_documents_the_flag(self):
        for cmd in ("serve", "build"):
            r = subprocess.run([sys.executable, "-I", str(SCRIPT), cmd, "--help"], capture_output=True, text=True)
            self.assertIn("--lang {en,pt-BR}", r.stdout)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/ar-board/tests -p test_lang.py 2>&1 | tail -n 3`

Expected: `FAILED (failures=` with `errors=`: the module loads, but ab.LANGS, ab.I18N and ab.resolve_lang do not exist yet (AttributeError), validate accepts any lang and the boot data has no language.

- [ ] **Step 3: Add the constants, the validation, the table and the resolution**

The constants sit next to the other limits; `lang` is validated right after `labels`; the table and `resolve_lang` get their own section just before the page. The I18N block below is inserted as a whole (the pt-BR side is written with accents; the two sides have the same keys in the same order).

In `plugins/ar-board/skills/ar-board/scripts/ar_board.py`, replace:

```python
MAX_LABEL = 24
```

with:

```python
MAX_LABEL = 24
LANGS = ("en", "pt-BR")  # panel languages accepted by `lang`, --lang and the header toggle
DEFAULT_LANG = "en"
```

In `plugins/ar-board/skills/ar-board/scripts/ar_board.py`, replace:

```python
    validate_labels(b, errs)
    items = b.get("items")
```

with:

```python
    validate_labels(b, errs)
    lang = b.get("lang")  # null counts as omitted, like every optional key
    if lang is not None and (not isinstance(lang, str) or lang not in LANGS):
        errs.append("campo 'lang' deve ser en ou pt-BR")
    items = b.get("items")
```

In `plugins/ar-board/skills/ar-board/scripts/ar_board.py`, replace the line:

```python
# ---------------------------------------------------------------- pagina
```

with the following block (the old line stays as its last line):

```python
# ---------------------------------------------------------------- textos do painel

# Every user-visible string of the page, in both languages: the markup and the JavaScript only ever ask
# T('key'). The two tables have the same keys and the same {placeholders} (a test enforces it). Values
# are plain text (no markup: some reach innerHTML unescaped) and the pt-BR side is written with accents.
I18N = {
    "en": {
        "lang_label": "Language",
        "key_approve": "approve", "key_reject": "reject", "key_maybe": "maybe", "key_choose": "choose",
        "key_confirm": "confirm", "key_more_context": "more context", "key_skip": "skip", "key_comment": "comment",
        "key_leave_field": "leave the field", "key_navigate": "navigate", "auto_advance": "advance on decide",
        "comment_label": "Comment on this item (C focuses · saves by itself). Valid for any decision.",
        "comment_placeholder": "Why did you approve, reject or hesitate? This is what trains the agent most.",
        "comment_optional": "Comment (optional, saves by itself)", "your_answer": "Your answer", "required": "(required)",
        "approve": "Approve", "reject": "Reject", "maybe": "Maybe", "skip": "Skip", "prev": "Previous", "next": "Next",
        "confirm_label": "Confirm: {label}",
        "armed_hint": "Press A again (or click Confirm) to confirm; Esc cancels.", "confirm_cancelled": "Confirmation cancelled.",
        "state_approved": "Approved", "state_rejected": "Rejected", "state_maybe": "Maybe",
        "state_answered": "Answered", "state_unsure": "Needs context",
        "count_approved": "approved", "count_rejected": "rejected", "count_maybe": "maybe", "count_pending": "undecided",
        "count_answered": "answered", "count_unsure": "need context", "count_unanswered": "unanswered",
        "subtitle": "Batch: {id} · items: {n} · round {round}", "risk": "Risk",
        "decided_hint": "{label}: {id} — use ← to go back and comment",
        "result": "Result", "note_label": "General note on the batch (batch_note)",
        "note_placeholder": "General remark about this whole batch...",
        "finish": "Finish and notify the agent", "review_finish": "Review and finish", "download": "Download JSON",
        "copy": "Copy", "copied": "Copied!", "clear": "Clear",
        "clear_confirm": "Clear every decision and comment of this batch?",
        "finish_anyway": "Undecided items: {n}. Finish anyway?",
        "done_banner": "Finished. Go back to Claude Code and say \"done\" — the agent reads the decisions by itself.",
        "no_server": "No connection to the server. Use Copy and paste the result in the chat.",
        "live": "live", "disconnected_badge": "no connection — use Copy", "offline_badge": "local file — use Copy",
        "need_context": "I need more context", "other_prefix": "Other: ", "other_answer": "Other answer...",
        "other_effect": "the text of the field beside becomes the answer",
        "open_question_how": "Open question: write the answer in the field beside (required).",
        "choose_range": "Choose from {min} to {max}. Enter confirms.", "choose_one": "Choose one option.",
        "if_chosen": "if chosen: ", "recommended": "recommended", "why_recommended": "Why we recommend it:",
        "max_options": "At most {max} options. Unselect one first.", "write_answer": "Write your answer in the field beside.",
        "answered_hint": "Answered: {id} — use ← to go back and change",
        "marked_unsure": "Marked: needs more context. The agent explains again in the next round.",
        "need_open_answer": "Write the answer in the field beside (or use M).",
        "need_min_options": "Choose at least {min} option(s) (or use M).",
        "need_one_option": "Choose an option first (or M to ask for context).",
        "review_title": "Review your answers ({n} of {total})", "no_answer": "(no answer)",
        "answer_link": "answer", "change_link": "change",
        "review_missing": "{n} without an answer: the agent will ask in the chat and never assumes the recommended option.",
        "back_fix": "Go back and fix", "confirm_finish": "Confirm and notify the agent", "copy_result": "Copy the result",
    },
    "pt-BR": {
        "lang_label": "Idioma",
        "key_approve": "aprovar", "key_reject": "rejeitar", "key_maybe": "talvez", "key_choose": "escolher",
        "key_confirm": "confirmar", "key_more_context": "mais contexto", "key_skip": "pular", "key_comment": "comentar",
        "key_leave_field": "sair do campo", "key_navigate": "navegar", "auto_advance": "avançar ao decidir",
        "comment_label": "Comentário deste item (C foca · salva sozinho). Vale para qualquer decisão.",
        "comment_placeholder": "Por que aprovou, rejeitou ou ficou em dúvida? Isso é o que mais treina o agente.",
        "comment_optional": "Comentário (opcional, salva sozinho)", "your_answer": "Sua resposta", "required": "(obrigatória)",
        "approve": "Aprovar", "reject": "Rejeitar", "maybe": "Talvez", "skip": "Pular", "prev": "Anterior", "next": "Próximo",
        "confirm_label": "Confirmar: {label}",
        "armed_hint": "Aperte A de novo (ou clique em Confirmar) para confirmar; Esc cancela.", "confirm_cancelled": "Confirmação cancelada.",
        "state_approved": "Aprovado", "state_rejected": "Rejeitado", "state_maybe": "Talvez",
        "state_answered": "Respondida", "state_unsure": "Precisa de contexto",
        "count_approved": "aprovados", "count_rejected": "rejeitados", "count_maybe": "talvez", "count_pending": "sem decisão",
        "count_answered": "respondidas", "count_unsure": "precisam de contexto", "count_unanswered": "sem resposta",
        "subtitle": "Lote: {id} · itens: {n} · rodada {round}", "risk": "Risco",
        "decided_hint": "{label}: {id} — use ← para voltar e comentar",
        "result": "Resultado", "note_label": "Nota geral do lote (batch_note)",
        "note_placeholder": "Observação geral sobre este lote inteiro...",
        "finish": "Concluir e avisar o agente", "review_finish": "Revisar e concluir", "download": "Baixar JSON",
        "copy": "Copiar", "copied": "Copiado!", "clear": "Limpar",
        "clear_confirm": "Limpar todas as decisões e comentários deste lote?",
        "finish_anyway": "Itens sem decisão: {n}. Concluir mesmo assim?",
        "done_banner": "Concluído. Volte ao Claude Code e diga \"terminei\" — o agente lê as decisões sozinho.",
        "no_server": "Sem conexão com o servidor. Use Copiar e cole o resultado no chat.",
        "live": "ao vivo", "disconnected_badge": "sem conexão — use Copiar", "offline_badge": "arquivo local — use Copiar",
        "need_context": "Preciso de mais contexto", "other_prefix": "Outra: ", "other_answer": "Outra resposta...",
        "other_effect": "o texto do campo ao lado vira a resposta",
        "open_question_how": "Pergunta aberta: escreva a resposta ao lado (obrigatória).",
        "choose_range": "Escolha de {min} até {max}. Enter confirma.", "choose_one": "Escolha uma opção.",
        "if_chosen": "se escolher: ", "recommended": "recomendada", "why_recommended": "Por que recomendamos:",
        "max_options": "Máximo de {max} opções. Desmarque uma antes.", "write_answer": "Escreva sua resposta no campo ao lado.",
        "answered_hint": "Respondida: {id} — use ← para voltar e mudar",
        "marked_unsure": "Marcada: precisa de mais contexto. O agente volta a explicar na próxima rodada.",
        "need_open_answer": "Escreva a resposta no campo ao lado (ou use M).",
        "need_min_options": "Escolha pelo menos {min} opção(ões) (ou use M).",
        "need_one_option": "Escolha uma opção primeiro (ou M para pedir contexto).",
        "review_title": "Revise suas respostas ({n} de {total})", "no_answer": "(sem resposta)",
        "answer_link": "responder", "change_link": "alterar",
        "review_missing": "{n} sem resposta: o agente vai perguntar no chat e nunca assume a opção recomendada.",
        "back_fix": "Voltar e corrigir", "confirm_finish": "Confirmar e avisar o agente", "copy_result": "Copiar resultado",
    },
}


def resolve_lang(batch, flag=None):
    """The language the page opens in before the browser's own choice: --lang, then the batch's `lang`, then English."""
    for cand in (flag, batch.get("lang")):
        if cand in LANGS:
            return cand
    return DEFAULT_LANG


# ---------------------------------------------------------------- pagina
```

- [ ] **Step 4: Pass the language to the page and to the command line**

`render_page` puts the resolved language and the table into the boot JSON; `make_handler` carries the flag of `serve`; `build` and `serve` take `--lang`.

In `plugins/ar-board/skills/ar-board/scripts/ar_board.py`, replace:

```python
def render_page(batch, state, token, live):
    boot = json.dumps({"batch": batch, "state": state, "token": token, "live": live}, ensure_ascii=False)
```

with:

```python
def render_page(batch, state, token, live, lang=None):
    """`lang` is the --lang of serve/build (None: the batch decides); the page itself applies the saved toggle on top."""
    boot = json.dumps({"batch": batch, "state": state, "token": token, "live": live, "lang": resolve_lang(batch, lang), "i18n": I18N},
                      ensure_ascii=False)
```

In `plugins/ar-board/skills/ar-board/scripts/ar_board.py`, replace:

```python
def make_handler(store, token):
```

with:

```python
def make_handler(store, token, lang=None):
```

In `plugins/ar-board/skills/ar-board/scripts/ar_board.py`, replace:

```python
                    page = render_page(store.batch, store.state, token, True)
```

with:

```python
                    page = render_page(store.batch, store.state, token, True, lang)
```

In `plugins/ar-board/skills/ar-board/scripts/ar_board.py`, replace:

```python
    srv.RequestHandlerClass = make_handler(store, token)
```

with:

```python
    srv.RequestHandlerClass = make_handler(store, token, a.lang)
```

In `plugins/ar-board/skills/ar-board/scripts/ar_board.py`, replace:

```python
    out.write_bytes(render_page(batch, state, "", False))
```

with:

```python
    out.write_bytes(render_page(batch, state, "", False, a.lang))
```

In `plugins/ar-board/skills/ar-board/scripts/ar_board.py`, replace:

```python
    s.add_argument("--exit-on-finish", action="store_true")
```

with:

```python
    s.add_argument("--exit-on-finish", action="store_true")
    s.add_argument("--lang", choices=LANGS, default=None, help="idioma inicial do painel (padrao: o lang do batch, senao en)")
```

In `plugins/ar-board/skills/ar-board/scripts/ar_board.py`, replace:

```python
    b = sub.add_parser("build")
    b.add_argument("dir")
```

with:

```python
    b = sub.add_parser("build")
    b.add_argument("dir")
    b.add_argument("--lang", choices=LANGS, default=None, help="idioma inicial do painel (padrao: o lang do batch, senao en)")
```

The two tests that build a `Namespace` by hand for `cmd_serve` and `cmd_build` now give it a `lang`:

In `plugins/ar-board/tests/test_cli.py`, replace:

```python
ab.cmd_serve(Namespace(dir=str(d), port=port, open=False, exit_on_finish=False))
```

with:

```python
ab.cmd_serve(Namespace(dir=str(d), port=port, open=False, exit_on_finish=False, lang=None))
```

In `plugins/ar-board/tests/test_validate.py`, replace:

```python
                self.assertEqual(ab.cmd_build(Namespace(dir=str(d))), 0)
            self.assertIn("(it.fields
```

with:

```python
                self.assertEqual(ab.cmd_build(Namespace(dir=str(d), lang=None)), 0)
            self.assertIn("(it.fields
```

In `plugins/ar-board/tests/test_validate.py`, replace:

```python
                self.assertEqual(ab.cmd_build(Namespace(dir=str(d))), 0)

    def test_load_batch_rejects_bad_round
```

with:

```python
                self.assertEqual(ab.cmd_build(Namespace(dir=str(d), lang=None)), 0)

    def test_load_batch_rejects_bad_round
```

- [ ] **Step 5: Regenerate the copies and run the suite**

The ar-board suite checks that the generated copies are in sync (`test_package.py`), and the tidy-board and housekeeping suites check their vendored engine, so every engine change is followed by the three sync tools. The version is still 1.3.1: the sync tools only copy.

Run: `python3 plugins/ar-board/tools/sync.py && python3 plugins/tidy-board/tools/sync.py && python3 plugins/housekeeping/tools/sync.py && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/ar-board/tests 2>&1 | grep -v '^AR-BOARD' | tail -n 3`

Expected: the three syncs print `updated:` lines (the two `dist/` variants, `skills/question-board/scripts/ar_board.py` and the two `capy_board.py`), then `Ran 222 tests` and `OK`.

- [ ] **Step 6: Commit**

Run:

```bash
git add -A
git commit -m "feat(ar-board): the I18N table, lang in the batch, --lang on serve and build, the language in the boot data" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

Expected: one commit (git status --short is empty afterwards).

### Task 2: Engine, the page: every string from the table, the EN/PT toggle, `low`/`medium`/`high`

**Files:**
- Modify: `plugins/ar-board/skills/ar-board/scripts/ar_board.py` (the whole `PAGE` string is replaced)
- Modify: `plugins/ar-board/tests/test_page.py` (one import, a new class appended), `plugins/ar-board/tests/test_labels_confirm.py` (four pinned literals)

**Interfaces:**
- Consumes: `BOOT.i18n`, `BOOT.lang` (Task 1).
- Produces: the page's `T(key, vars)`, `applyLang()`, `setLang(l)`, `applyLabels()`; elements with `data-t="key"` (text) and `data-tp="key"` (placeholder); the header toggle `#lang` with two `button[data-lang]`; `<html lang="en">` set at run time; `localStorage` key `ar-board:lang`; the risk map `RISK` (`low`/`medium`/`high` to the classes `baixo`/`medio`/`alto`). `decisions.json`, the HTTP API and the `AR-BOARD-RESULT` export are unchanged.

- [ ] **Step 1: Write the failing guard tests**

The suite does not run JavaScript, so the page is pinned by string guards, as `test_page.py` already does: a scan of every JS string literal and markup text node for anything that reads as text (two words of four letters or more, or any word of the old Portuguese page), the set of keys the page asks for against the table, and the exact lines that implement the precedence, the toggle, the risk map and the key letters. `test_no_literal_...` prints every literal it flags, so it is the failing test of the mechanical substitution below.

In `plugins/ar-board/tests/test_page.py`, replace:

```python
import re
import unittest

from helpers import REPO, ab
```

with:

```python
import re
import unicodedata
import unittest

from helpers import REPO, ab
```

Append to `plugins/ar-board/tests/test_page.py` (after a blank line):

```python
# ---------------------------------------------------------------- the switchable language (ar-board 1.4.0)

PT_WORDS = {  # words of the old Portuguese page: any of them in a literal outside the table is a leftover
    "aprovar", "rejeitar", "talvez", "pular", "comentar", "escolher", "confirmar", "contexto", "navegar", "avancar",
    "decidir", "comentario", "resposta", "respostas", "obrigatoria", "opcional", "lote", "itens", "rodada", "decisao",
    "decisoes", "concluir", "concluido", "avisar", "agente", "baixar", "copiar", "copiado", "limpar", "resultado", "nota",
    "observacao", "aperte", "cancela", "confirmacao", "cancelada", "escreva", "campo", "maximo", "opcoes", "opcao",
    "desmarque", "marcada", "precisa", "precisam", "revise", "responder", "alterar", "voltar", "corrigir", "conexao",
    "servidor", "cole", "arquivo", "vivo", "recomendada", "recomendamos", "outra", "pergunta", "aberta", "primeiro",
    "respondida", "respondidas", "terminei", "volte", "diga", "sozinho", "todas", "deste", "mesmo", "assim", "proxima",
    "mudar", "risco", "anterior", "proximo", "salva", "foca", "vale", "qualquer", "aprovou", "rejeitou", "ficou", "duvida",
    "treina", "sim", "nao", "sem", "idioma", "sair", "escolha", "mais",
}
PROSE = re.compile(r"[A-Za-zÀ-ɏ]{4,}\s+[A-Za-zÀ-ɏ]{4,}")  # two words: text, not a token
JS_LITERAL = re.compile(r"'(?:[^'\\\n]|\\.)*'|\"(?:[^\"\\\n]|\\.)*\"")
TAG_BITS = re.compile(r"<[^>]*>|<[^>]*$|^[^<]*>")  # whole tags, an unclosed tag at the end, a tag's tail at the start
ALLOWED_TEXT = ("Capybara Toolbox",)  # the brand line in the footer


def page_body():
    """(markup of <body> before the script, the script's code)."""
    body = ab.PAGE.split("<body>", 1)[1]
    script = re.search(r"<script>(.*?)</script>", body, re.S).group(1)
    return body[:body.index("<script>")], script


def plain(text):
    return unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("ascii").lower()


def looks_like_text(fragment):
    clean = TAG_BITS.sub(" ", fragment)
    words = set(re.split(r"[^a-z]+", plain(clean)))
    return bool(PROSE.search(clean)) or bool(words & PT_WORDS)


class PageLanguageGuardTest(unittest.TestCase):
    """The page's text comes from the I18N table: no literal of the markup or the JavaScript may read as prose
    (in either language), and every key the page asks for exists, and every key of the table is asked for."""

    def test_no_literal_of_the_page_reads_as_text_outside_the_table(self):
        markup, script = page_body()
        left = [m.group(0) for m in JS_LITERAL.finditer(script) if looks_like_text(m.group(0)[1:-1])]
        for node in re.split(r"<[^>]*>", markup):
            node = node.strip()
            if node and not any(a in node for a in ALLOWED_TEXT) and looks_like_text(node):
                left.append(node)
        self.assertEqual(left, [], "text left outside the I18N table:\n" + "\n".join(left))

    def test_every_key_the_page_uses_exists_and_every_key_of_the_table_is_used(self):
        markup, script = page_body()
        used = set(re.findall(r"T\('([a-z_]+)'", script)) | set(re.findall(r'data-tp?="([a-z_]+)"', markup))
        self.assertEqual(used - set(ab.I18N["en"]), set(), "keys missing from the table")
        self.assertEqual(set(ab.I18N["en"]) - used, set(), "table keys the page never uses")
        dynamic = set(re.findall(r"(?<!function )T\((?!')[^)]*\)", script))
        self.assertEqual(dynamic, {"T(el.dataset.t)", "T(el.dataset.tp)"})  # the only non-literal lookups

    def test_the_precedence_is_saved_toggle_then_boot_then_english(self):
        self.assertIn("let lang = LANGS.includes(BOOT.lang) ? BOOT.lang : 'en';", ab.PAGE)
        self.assertIn("const saved = localStorage.getItem('ar-board:lang'); if(LANGS.includes(saved)) lang = saved;", ab.PAGE)
        self.assertIn("localStorage.setItem('ar-board:lang', l)", ab.PAGE)
        self.assertIn("function setLang(l){if(!LANGS.includes(l)) return;", ab.PAGE)

    def test_the_toggle_sits_in_the_header_and_sets_html_lang(self):
        self.assertIn('<html lang="en">', ab.PAGE)
        self.assertIn("document.documentElement.lang = lang;", ab.PAGE)
        self.assertIn('<button type="button" data-lang="en">EN</button><button type="button" data-lang="pt-BR">PT</button>', ab.PAGE)
        self.assertIn("if(b) setLang(b.dataset.lang);", ab.PAGE)
        self.assertLess(ab.PAGE.index('id="live"'), ab.PAGE.index('id="lang"'))

    def test_switching_re_renders_without_a_reload_and_keeps_the_card_labels(self):
        self.assertIn("applyLang(); render();}", ab.PAGE)
        self.assertIn("  applyLabels();\n", ab.PAGE)  # batch labels win over the table after every switch
        self.assertIn("$('#bF').textContent = hasQ ? T('review_finish') : T('finish');", ab.PAGE)
        self.assertNotIn("location.reload", ab.PAGE)

    def test_risk_levels_accept_english_words_and_keep_the_css_classes(self):
        for pair in ("['low','baixo']", "['medium','medio']", "['high','alto']", "['baixo','baixo']"):
            self.assertIn(pair, ab.PAGE)
        self.assertIn("const RISK = Object.create(null);", ab.PAGE)
        self.assertIn("const lvl = RISK[norm(it.risk.level)] || 'medio';", ab.PAGE)
        for cls in (".risk.baixo{", ".risk.medio{", ".risk.alto{"):
            self.assertIn(cls, ab.PAGE)

    def test_the_key_letters_do_not_change_with_the_language(self):
        for key in ("<kbd>A</kbd>", "<kbd>R</kbd>", "<kbd>M</kbd>", "<kbd>S</kbd>", "<kbd>C</kbd>"):
            self.assertIn(key, ab.PAGE)
        self.assertIn("if(k === 'a') decide('approved');", ab.PAGE)
        self.assertIn("else if(k === 's') go(idx+1);", ab.PAGE)
        self.assertIn("else if(k === 'c'){ev.preventDefault(); $('#cmt').focus();}", ab.PAGE)

    def test_batch_labels_and_confirm_are_card_content_shown_as_written(self):
        self.assertIn("LBL[p[1]] = l.text; CNT[p[1]] = l.text.toLowerCase();", ab.PAGE)
        self.assertIn("T('confirm_label', {label: esc((LB.approve ? LB.approve.text : T('approve')).toLowerCase())})", ab.PAGE)
        self.assertIn("rich(it.confirm) + '<b>' + T('armed_hint') + '</b></div>'", ab.PAGE)

    def test_the_export_and_the_decisions_carry_no_language(self):
        self.assertNotIn("lang:", ab.PAGE.split("function exportObj(){", 1)[1].split("}\n", 1)[0])
        self.assertNotIn("'/api/lang'", ab.PAGE)

    def test_the_rendered_page_shows_the_table_values_and_no_old_literal(self):
        batch = {"batch_id": "t", "title": "T", "items": [{"id": "A01", "title": "x"}]}
        page = ab.render_page(batch, {"items": {}}, "tok", True).decode("utf-8")
        self.assertIn('"done_banner": "Finished.', page)
        self.assertIn('"done_banner": "Concluído.', page)
        self.assertNotIn("Concluido. Volte", page)
        self.assertNotIn("avancar ao decidir", page)
```

- [ ] **Step 2: Run the guard tests to see them fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/ar-board/tests -p test_page.py -k PageLanguageGuardTest 2>&1 | tail -n 3`

Expected: `Ran 10 tests` and `FAILED (failures=8)`: the literal scan lists the Portuguese strings of the old page, no T() call exists and the page still declares pt-BR; the two guards that already hold on the old page are the key letters and the export shape.

- [ ] **Step 3: Replace the page**

Every user-visible string becomes a `T('key')` lookup (markup: elements with `data-t`/`data-tp`, filled by `applyLang()`; JavaScript: `T()` calls, with `{placeholders}` substituted from already-escaped values where the result reaches `innerHTML`). The substitution rules, each applied to every occurrence:

- A markup text (`<i id="kA">aprovar</i>`, `<h3>Resultado</h3>`, `<button id="bC">Copiar</button>`) becomes an empty element with `data-t="key"`; a `placeholder="..."` becomes `data-tp="key"`; the `<kbd>` letters and the `&larr;`/`&rarr;`/`&#10003;`/`&#10007;`/`&asymp;`/`&#9733;` symbols stay in the markup or in the code, outside the table.
- A JS literal written to `textContent`, `confirm()`, `alert()` or `showHint()` becomes `T('key')` or `T('key', {name: value})`.
- A JS literal concatenated into `innerHTML` becomes `T('key')`; a user value inside it stays wrapped in `esc()` (`T('confirm_label', {label: esc(...)})`).
- The constants `LBL`, `CNT`, `QLBL` and `CMT0` are no longer constants: `applyLang()` rebuilds `LBL`, `CNT` and `QLBL` from the table and then `applyLabels()` overrides them with the batch `labels` (R2); `CMT0` disappears (`render()` asks `T('comment_label')`).
- `setLive(ok)` remembers `liveOk` so `applyLang()` can re-render the badge; `#bF`'s text is set by `applyLang()` (`finish` or `review_finish`).
- The risk level goes through `RISK` (a null-prototype map) so `low`/`medium`/`high` select `baixo`/`medio`/`alto` (R3); the CSS classes are untouched.
- The toggle is a `.lang` group in a new `.hdr` wrapper next to the badge; `setLang(l)` validates `l`, saves it, re-applies the language and re-renders without a reload (R1); the key letters and the `keydown` handler are untouched (R4).

The result, in full (the CSS is the old one plus `.hdr`, `.lang` and `.lang button`):

In `plugins/ar-board/skills/ar-board/scripts/ar_board.py`, replace everything from the line `PAGE = r"""<!doctype html>` up to and including the next line that is exactly `"""` with:

```python
PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<link rel="icon" href="__FAVICON__">
<style>
:root{color-scheme:dark;accent-color:var(--acc);--bg:#1a1410;--panel:#241c15;--panel2:#2e241b;--line:#46382b;--fg:#f4ebdf;--mut:#b09c85;--ok:#8cc474;--ok-bg:#1d2b1a;--no:#ef8570;--no-bg:#34201a;--mb:#ecb856;--mb-bg:#342a14;--acc:#f29a45;--accfg:#2a1a0c;--cA:var(--ok);--cAb:var(--ok-bg);--cR:var(--no);--cRb:var(--no-bg);--cM:var(--mb);--cMb:var(--mb-bg)}
@media (prefers-color-scheme:light){:root{color-scheme:light;--bg:#f7f0e5;--panel:#fffaf2;--panel2:#f1e7d8;--line:#dccbb3;--fg:#2c2018;--mut:#6b5645;--ok:#2d6a1f;--ok-bg:#e3f0da;--no:#a8381f;--no-bg:#fbe4dd;--mb:#8a5a00;--mb-bg:#faecc8;--acc:#a24d0d;--accfg:#ffffff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:20px 16px 60px}
header{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap}
h1{font-size:22px;margin:0 0 4px}.sub{color:var(--mut);font-size:13px}
.hdr{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.badge{font-size:12px;padding:3px 10px;border-radius:99px;border:1px solid var(--line);white-space:nowrap}
.badge.on{color:var(--ok);border-color:var(--ok)}.badge.off{color:var(--mb);border-color:var(--mb)}
.lang{display:inline-flex;border:1px solid var(--line);border-radius:99px;overflow:hidden}
.lang button{border:0;border-radius:0;padding:3px 10px;font-size:12px;background:transparent;color:var(--mut)}
.lang button.on{background:var(--panel2);color:var(--fg);font-weight:600}
.keys{display:flex;flex-wrap:wrap;gap:6px 14px;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:14px 0 10px;font-size:13px;color:var(--mut)}
kbd{font:600 11px ui-monospace,Menlo,monospace;background:var(--panel2);border:1px solid var(--line);border-radius:5px;padding:1px 6px;color:var(--fg);margin-right:4px}
.keys .auto{margin-left:auto;cursor:pointer;color:var(--fg)}#hint{flex-basis:100%;color:var(--acc);font-weight:600}#hint:empty{display:none}
.bar{height:5px;background:var(--panel2);border-radius:9px;overflow:hidden;margin-bottom:16px}.bar>i{display:block;height:100%;width:0;background:var(--acc);transition:width .2s}
.grid{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:16px}
@media (max-width:860px){.grid{grid-template-columns:minmax(0,1fr)}}
.grid>*,.row>div,.meta b{min-width:0;overflow-wrap:anywhere}
.card,.side,.res{background:var(--panel);border:1px solid var(--line);border-radius:14px}
.card{padding:22px}.side{padding:16px;align-self:start}
.pill{display:inline-block;font-size:12px;color:var(--mut);border:1px solid var(--line);border-radius:99px;padding:2px 10px;margin-bottom:12px}
.card h2{font-size:21px;margin:0 0 16px;line-height:1.3}
.state{display:inline-block;margin-left:8px;font-size:12px;font-weight:600;padding:2px 10px;border-radius:99px}
.state.approved{color:var(--cA);background:var(--cAb)}.state.rejected{color:var(--cR);background:var(--cRb)}.state.maybe{color:var(--cM);background:var(--cMb)}
.box{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.row{display:grid;grid-template-columns:86px 1fr;gap:12px;padding:6px 0}
.row>b{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--mut);padding-top:3px}
code{font:13px ui-monospace,Menlo,monospace;background:var(--bg);border:1px solid var(--line);border-radius:5px;padding:0 5px}
.risk{display:inline-block;border-radius:99px;padding:2px 12px;font-size:13px;border:1px solid}
.risk.baixo{color:var(--ok);background:var(--ok-bg);border-color:var(--ok)}.risk.medio{color:var(--mb);background:var(--mb-bg);border-color:var(--mb)}.risk.alto{color:var(--no);background:var(--no-bg);border-color:var(--no)}
.card img{max-width:100%;border-radius:10px;border:1px solid var(--line);margin:0 0 14px;display:block}
.meta{margin:0 0 12px;font-size:13px}.meta div{display:flex;justify-content:space-between;gap:10px;padding:3px 0;border-bottom:1px dashed var(--line)}.meta span{color:var(--mut)}.meta b{text-align:right;font-weight:600}
.side label{display:block;font-size:12px;color:var(--mut);margin:6px 0}
textarea{width:100%;min-height:84px;resize:vertical;background:var(--panel2);color:var(--fg);border:1px solid var(--line);border-radius:10px;padding:10px;font:inherit;font-size:14px}
textarea:focus{outline:2px solid var(--acc);outline-offset:0}
.btns{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}
button{font:inherit;font-size:14px;cursor:pointer;color:var(--fg);background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:8px 14px}
button:hover{border-color:var(--mut)}button kbd{margin:0 0 0 6px}
button.ok{color:var(--ok);border-color:var(--ok);background:var(--ok-bg)}button.no{color:var(--no);border-color:var(--no);background:var(--no-bg)}button.mb{color:var(--mb);border-color:var(--mb);background:var(--mb-bg)}
button.on{box-shadow:0 0 0 2px currentColor inset}
.chips{display:flex;flex-wrap:wrap;gap:6px}.chips button{width:34px;height:34px;padding:0;font-size:13px}
.chips .approved{background:var(--cAb);color:var(--cA);border-color:var(--cA)}.chips .rejected{background:var(--cRb);color:var(--cR);border-color:var(--cR)}.chips .maybe{background:var(--cMb);color:var(--cM);border-color:var(--cM)}
.armed{background:var(--no-bg);color:var(--no);border:1px solid var(--no);border-radius:10px;padding:10px 14px;margin:12px 0 0}.armed b{display:block;margin-top:4px}
button.sure{background:var(--cA);border-color:var(--cA);color:var(--accfg);font-weight:700}.keys i{font-style:normal}.chips .cur{outline:2px solid var(--acc);outline-offset:1px}
.res{margin-top:16px;padding:18px}.res h3{margin:0 0 10px;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--mut)}
.counts{display:flex;gap:16px;flex-wrap:wrap;font-size:14px;margin-bottom:12px}
.done{display:none;margin-top:12px;padding:12px 14px;border-radius:10px;background:var(--ok-bg);border:1px solid var(--ok);color:var(--ok)}
button.go{background:var(--acc);border-color:var(--acc);color:var(--accfg);font-weight:600}
.brand{display:flex;align-items:center;gap:14px}.mascot{width:56px;height:56px;flex:none}
.foot{margin-top:28px;text-align:center;font-size:12px;color:var(--mut)}
[hidden]{display:none!important}
.qonly{display:none}.hasq .qonly{display:inline}.onlyq .pronly{display:none}
.state.answered{color:var(--acc);border:1px solid var(--acc)}
.chips .answered{color:var(--acc);border-color:var(--acc)}
.card.q h2{font:600 24px/1.3 ui-serif,"Iowan Old Style","Palatino Linotype",Georgia,serif}
.how{font-size:13px;color:var(--mut);margin:18px 0 8px}
.opts{display:grid;gap:8px}
.opt{display:grid;grid-template-columns:34px 1fr auto;gap:12px;align-items:start;text-align:left;width:100%;font:inherit;color:var(--fg);background:var(--panel2);border:1.5px solid var(--mut);border-radius:12px;padding:12px 14px;cursor:pointer;transition:border-color .12s,background .12s}
.opt:hover{border-color:var(--fg)}.opt:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
.opt .k{font:600 13px ui-monospace,Menlo,monospace;background:var(--bg);border:1px solid var(--mut);border-radius:7px;text-align:center;padding:3px 0}
.opt .lbl{font-weight:600}.opt .fx{display:block;font-size:13px;color:var(--mut);font-weight:400;margin-top:2px}
.opt .rec{font-size:12px;color:var(--mb);border:1px solid var(--mb);border-radius:99px;padding:1px 9px;white-space:nowrap}
.opt[aria-checked="true"]{border-color:var(--acc);background:var(--panel);box-shadow:0 0 0 2px var(--acc) inset}
.opt[aria-checked="true"] .k{background:var(--acc);color:var(--accfg);border-color:var(--acc)}
.opt[aria-checked="true"] .lbl::after{content:" \2713";color:var(--acc)}
.why{font-size:13px;color:var(--mut);margin:10px 2px 0}.why b{color:var(--mb)}
.req{color:var(--acc);font-weight:600}
.rev h2{font:600 24px/1.3 ui-serif,"Iowan Old Style","Palatino Linotype",Georgia,serif;margin:0 0 12px}
.rev table{width:100%;border-collapse:collapse;font-size:14px}.rev td{padding:9px 6px;border-bottom:1px dashed var(--line);vertical-align:top}
.rev td:first-child{color:var(--mut);width:46%}.rev .none{color:var(--mb);font-weight:600}
.rev a{color:var(--acc);cursor:pointer;margin-left:8px;text-decoration:underline}
@media (prefers-reduced-motion:reduce){.opt{transition:none}}
</style></head><body><div class="wrap">
<header><div class="brand">__MASCOT__<div><h1 id="ttl"></h1><div class="sub" id="sub"></div></div></div><div class="hdr"><span class="badge" id="live"></span><span class="lang" id="lang" role="group"><button type="button" data-lang="en">EN</button><button type="button" data-lang="pt-BR">PT</button></span></div></header>
<div class="keys"><span class="pronly"><kbd>A</kbd><i id="kA"></i></span><span class="pronly"><kbd>R</kbd><i id="kR"></i></span><span class="pronly"><kbd>M</kbd><i id="kM"></i></span><span class="qonly"><kbd>1-9</kbd><i data-t="key_choose"></i></span><span class="qonly"><kbd>Enter</kbd><i data-t="key_confirm"></i></span><span class="qonly"><kbd>M</kbd><i data-t="key_more_context"></i></span><span><kbd>S</kbd><i data-t="key_skip"></i></span><span><kbd>C</kbd><i data-t="key_comment"></i></span><span><kbd>Esc</kbd><i data-t="key_leave_field"></i></span><span><kbd>&larr;</kbd><kbd>&rarr;</kbd><i data-t="key_navigate"></i></span><label class="auto"><input type="checkbox" id="auto" checked> <i data-t="auto_advance"></i></label><span id="hint" role="status" aria-live="polite"></span></div>
<div class="bar"><i id="prog"></i></div>
<div class="grid">
  <section class="card" id="card"></section>
  <aside class="side">
    <div class="meta" id="meta"></div>
    <label for="cmt" id="cmtlbl"></label>
    <textarea id="cmt" data-tp="comment_placeholder"></textarea>
    <div class="btns">
      <button class="ok" id="bA"></button>
      <button class="no" id="bR"></button>
      <button class="mb" id="bM"></button>
      <button id="bS"><span data-t="skip"></span><kbd>S</kbd></button>
      <button id="bP">&larr; <span data-t="prev"></span></button><button id="bN"><span data-t="next"></span> &rarr;</button>
    </div>
    <div class="chips" id="chips"></div>
  </aside>
</div>
<section class="card rev" id="rev" hidden></section>
<section class="res">
  <h3 data-t="result"></h3>
  <div class="counts" id="counts"></div>
  <label for="note" class="sub" data-t="note_label"></label>
  <textarea id="note" data-tp="note_placeholder"></textarea>
  <div class="btns">
    <button class="go" id="bF"></button>
    <button id="bD" data-t="download"></button><button id="bC" data-t="copy"></button><button id="bX" data-t="clear"></button>
  </div>
  <div class="done" id="done"></div>
</section>
<div class="foot">ar-board &middot; Capybara Toolbox</div>
</div>
<script>
(function(){
const BOOT = __BOOT__;
const B = BOOT.batch, items = B.items, S = BOOT.state, I18N = BOOT.i18n;
S.items = S.items || {};
const $ = s => document.querySelector(s);
const LANGS = Object.keys(I18N);
let lang = LANGS.includes(BOOT.lang) ? BOOT.lang : 'en';
try{const saved = localStorage.getItem('ar-board:lang'); if(LANGS.includes(saved)) lang = saved;}catch(e){}
function T(key, vars){let s = I18N[lang][key]; if(s === undefined) s = I18N.en[key]; if(s === undefined) s = key; return vars ? s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m)) : s;}
let LBL = {}, CNT = {}, QLBL = {};
const LB = B.labels || {};
const TONE = {safe:['ok','--ok','--ok-bg'], danger:['no','--no','--no-bg'], caution:['mb','--mb','--mb-bg']};
let armed = null, liveOk = false;
function applyLabels(){
  [['approve','approved','A'], ['reject','rejected','R'], ['maybe','maybe','M']].forEach(p => {
    const l = LB[p[0]]; if(!l) return;
    LBL[p[1]] = l.text; CNT[p[1]] = l.text.toLowerCase();
    $('#k' + p[2]).textContent = l.text.toLowerCase();
    const t = TONE[l.tone]; if(!t) return;
    $('#b' + p[2]).className = t[0];
    document.documentElement.style.setProperty('--c' + p[2], 'var(' + t[1] + ')');
    document.documentElement.style.setProperty('--c' + p[2] + 'b', 'var(' + t[2] + ')');
  });
}
function applyLang(){
  document.documentElement.lang = lang;
  document.querySelectorAll('[data-t]').forEach(el => {el.textContent = T(el.dataset.t);});
  document.querySelectorAll('[data-tp]').forEach(el => {el.placeholder = T(el.dataset.tp);});
  document.querySelectorAll('#lang>button').forEach(b => b.classList.toggle('on', b.dataset.lang === lang));
  $('#lang').setAttribute('aria-label', T('lang_label'));
  LBL = {approved: T('state_approved'), rejected: T('state_rejected'), maybe: T('state_maybe')};
  CNT = {approved: T('count_approved'), rejected: T('count_rejected'), maybe: T('count_maybe')};
  QLBL = {answered: T('state_answered'), maybe: T('state_unsure')};
  $('#kA').textContent = T('key_approve'); $('#kR').textContent = T('key_reject'); $('#kM').textContent = T('key_maybe');
  applyLabels();
  $('#bF').textContent = hasQ ? T('review_finish') : T('finish');
  setLive(liveOk);
}
function setLang(l){if(!LANGS.includes(l)) return; lang = l; try{localStorage.setItem('ar-board:lang', l);}catch(e){} applyLang(); render();}
const LS = 'ar-board:' + B.batch_id + ':r' + (B.round || 1);
let idx = 0, timers = {};

function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function rich(s){return esc(s).replace(/`([^`]+)`/g,'<code>$1</code>').replace(/\n/g,'<br>');}
function norm(s){return String(s||'').normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase();}
const RISK = Object.create(null);
[['baixo','baixo'], ['low','baixo'], ['medio','medio'], ['medium','medio'], ['alto','alto'], ['high','alto']].forEach(p => {RISK[p[0]] = p[1];});
function ent(id){return S.items[id] || (S.items[id] = {});}
function tidy(id){const e=S.items[id]; if(e && !e.decision && !e.comment && !e.choice && !(e.choices && e.choices.length) && !e.other) delete S.items[id];}

const isQ = it => (it.choices != null || it.open === true);
const hasQ = items.some(isQ), onlyQ = hasQ && items.every(isQ);
document.body.classList.toggle('hasq', hasQ);
document.body.classList.toggle('onlyq', onlyQ);
let reviewing = false;
function cmtOf(e){return (e.comment || '').trim();}
function qlabels(it){const m = Object.create(null); (it.choices || []).forEach(c => {m[c.id] = c.label;}); return m;}
function qmax(it){return it.max || (it.choices || []).length;}
function qstatus(it){
  const e = S.items[it.id] || {};
  if(e.decision === 'maybe') return 'maybe';
  const text = cmtOf(e), lab = qlabels(it);
  if(it.open === true) return text ? 'answered' : '';
  if(it.multiple){
    if(e.other && !text) return '';
    const n = (e.choices || []).filter(i => i in lab).length + (e.other ? 1 : 0);
    return n >= (it.min || 1) ? 'answered' : '';
  }
  if(e.choice && e.choice in lab) return 'answered';
  return e.other && text ? 'answered' : '';
}
function qanswer(it){
  const e = S.items[it.id] || {}, st = qstatus(it);
  if(st === 'maybe') return T('need_context');
  if(st !== 'answered') return null;
  const lab = qlabels(it);
  if(it.open === true) return cmtOf(e);
  if(it.multiple){const p = (e.choices || []).filter(i => i in lab).map(i => lab[i]); if(e.other) p.push(T('other_prefix') + cmtOf(e)); return p.join(' + ');}
  return e.other ? T('other_prefix') + cmtOf(e) : lab[e.choice];
}
function status(it){return isQ(it) ? qstatus(it) : ((S.items[it.id] || {}).decision || '');}
function answerText(it){
  if(isQ(it)) return qanswer(it);
  const d = (S.items[it.id] || {}).decision;
  return d ? LBL[d] : null;
}
function qbody(it, e){
  const dec = e.decision === 'maybe' ? 'maybe' : null;
  if(it.open === true) return {id: it.id, decision: dec};
  return {id: it.id, decision: dec, choice: it.multiple ? null : (e.choice || null), choices: it.multiple ? (e.choices || []) : null, other: !!e.other};
}
function qsave(it){
  const body = qbody(it, S.items[it.id] || {});
  tidy(it.id); S.finished = false;
  post('/api/item', body);
}
function questionHtml(it, e){
  if(it.open === true) return '<p class="how">' + T('open_question_how') + '</p>';
  const opts = it.choices.concat([{id: null, label: T('other_answer'), effect: T('other_effect')}]);
  const rec = it.recommended || [];
  let h = '<p class="how">' + (it.multiple ? T('choose_range', {min: it.min || 1, max: qmax(it)}) : T('choose_one')) + '</p>';
  h += '<div class="opts" role="' + (it.multiple ? 'group' : 'radiogroup') + '" aria-labelledby="qtitle">';
  opts.forEach((o, i) => {
    const other = i === opts.length - 1;
    const on = other ? !!e.other : (it.multiple ? (e.choices || []).includes(o.id) : e.choice === o.id);
    h += '<button type="button" class="opt" role="' + (it.multiple ? 'checkbox' : 'radio') + '" aria-checked="' + on + '" data-n="' + (i+1) + '"><span class="k">' + (i+1) + '</span><span><span class="lbl">' + esc(o.label) + '</span>' + (o.effect ? '<span class="fx">' + (other ? '' : T('if_chosen')) + esc(o.effect) + '</span>' : '') + '</span>' + (!other && rec.includes(o.id) ? '<span class="rec">&#9733; ' + T('recommended') + '</span>' : '<span></span>') + '</button>';
  });
  h += '</div>';
  if(it.why) h += '<p class="why"><b>&#9733; ' + T('why_recommended') + '</b> ' + esc(it.why) + '</p>';
  return h;
}
function pick(n){
  const it = items[idx]; if(!isQ(it) || it.open === true) return;
  const e = ent(it.id), total = it.choices.length + 1;
  if(n < 1 || n > total) return;
  const other = n === total, max = qmax(it);
  if(it.multiple){
    const lab = qlabels(it), sel = (e.choices || []).filter(i => i in lab);
    if(other){
      if(!e.other && sel.length >= max){showHint(T('max_options', {max: max})); tidy(it.id); return;}
    } else if(!sel.includes(it.choices[n-1].id) && sel.length + (e.other ? 1 : 0) >= max){
      showHint(T('max_options', {max: max})); tidy(it.id); return;
    }
    delete e.decision;
    e.choices = sel;
    if(other){e.other = !e.other;}
    else {const id = it.choices[n-1].id, p = sel.indexOf(id); if(p >= 0) sel.splice(p, 1); else sel.push(id);}
    qsave(it); render();
    if(other && e.other){$('#cmt').focus(); showHint(T('write_answer'));}
    return;
  }
  delete e.decision;
  if(other){
    e.other = !e.other; if(e.other) delete e.choice;
    qsave(it); render();
    if(e.other){$('#cmt').focus(); showHint(T('write_answer'));}
    return;
  }
  const id = it.choices[n-1].id;
  if(e.choice === id) delete e.choice; else {e.choice = id; delete e.other;}
  qsave(it);
  if(auto && e.choice && idx < items.length - 1){idx++; showHint(T('answered_hint', {id: it.id}));}
  render();
}
function askMore(){
  const it = items[idx]; if(!isQ(it)) return;
  const e = ent(it.id);
  if(e.decision === 'maybe') delete e.decision;
  else {delete e.choice; delete e.choices; delete e.other; e.decision = 'maybe';}
  qsave(it); render();
  if(e.decision === 'maybe') showHint(T('marked_unsure'));
}
function confirmCard(){
  const it = items[idx], st = qstatus(it);
  if(!st){showHint(it.open === true ? T('need_open_answer') : it.multiple ? T('need_min_options', {min: it.min || 1}) : T('need_one_option')); return;}
  if(idx < items.length - 1) go(idx + 1); else openReview();
}
function openReview(){reviewing = true; render();}
function closeReview(){reviewing = false; render();}
function renderReview(){
  const miss = items.filter(it => answerText(it) === null).length;
  let h = '<h2>' + T('review_title', {n: items.length - miss, total: items.length}) + '</h2><table>';
  items.forEach((it, i) => {
    const a = answerText(it);
    h += '<tr><td>' + (i+1) + '. ' + esc(it.title) + '</td><td>' + (a === null ? '<span class="none">' + T('no_answer') + '</span>' : esc(a)) + '<a data-i="' + i + '" role="button" tabindex="0">' + (a === null ? T('answer_link') : T('change_link')) + '</a></td></tr>';
  });
  h += '</table>';
  if(miss) h += '<p class="sub">' + T('review_missing', {n: miss}) + '</p>';
  h += '<div class="btns"><button id="rB" type="button">' + T('back_fix') + '</button><button class="go" id="rC" type="button">' + (BOOT.live ? T('confirm_finish') : T('copy_result')) + '</button></div>';
  $('#rev').innerHTML = h;
}
function finishNow(){
  flushAll().then(() => post('/api/finish', {finished: true})).then(ok => {
    S.finished = ok; if(ok) reviewing = false; render();
    if(!ok) alert(T('no_server'));
  });
}

function persistLocal(){try{localStorage.setItem(LS, JSON.stringify(S));}catch(e){}}
function setLive(ok){
  liveOk = ok;
  const b = $('#live');
  if(!BOOT.live){b.className='badge off';b.textContent=T('offline_badge');return;}
  b.className = 'badge ' + (ok ? 'on' : 'off');
  b.textContent = ok ? '● ' + T('live') : T('disconnected_badge');
}
const inflight = new Set();
function post(path, body){
  if(!BOOT.live){persistLocal();return Promise.resolve(true);}
  const pr = fetch(path,{method:'POST',keepalive:true,headers:{'Content-Type':'application/json','X-AR-Token':BOOT.token},body:JSON.stringify(body)})
    .then(r=>{if(!r.ok)throw new Error(r.status);setLive(true);return true;})
    .catch(()=>{setLive(false);persistLocal();return false;});
  inflight.add(pr); pr.then(() => inflight.delete(pr));
  return pr;
}
let pend = {};
function queue(key, path, body){
  pend[key] = {path:path, body:body};
  clearTimeout(timers[key]);
  timers[key] = setTimeout(() => sendPend(key), 350);
}
function sendPend(key){
  const q = pend[key]; clearTimeout(timers[key]);
  if(!q) return Promise.resolve(true);
  delete pend[key];
  return post(q.path, q.body);
}
function flushAll(){return Promise.all(Object.keys(pend).map(sendPend));}
window.addEventListener('pagehide', flushAll);
document.addEventListener('visibilitychange', () => {if(document.visibilityState === 'hidden') flushAll();});
if(!BOOT.live){try{const raw=localStorage.getItem(LS); if(raw){const o=JSON.parse(raw); S.items=o.items||{}; S.batch_note=o.batch_note||'';}}catch(e){}}

function counts(){
  const c={approved:0,rejected:0,maybe:0,answered:0};
  items.forEach(it=>{const d=status(it); if(d) c[d]++;});
  c.pending = items.length - c.approved - c.rejected - c.maybe - c.answered;
  return c;
}
function exportObj(){
  return {batch_id:B.batch_id, round:B.round||1, finished:!!S.finished, batch_note:S.batch_note||'',
    items: items.map(it=>{const e=S.items[it.id]||{};
      const o={id:it.id,title:it.title,decision:e.decision||null,comment:e.comment||''};
      if(isQ(it)){o.kind = 'question'; o.choice = e.choice||null; o.choices = e.choices||[]; o.other = !!e.other;}
      return o;})};
}
function imgSrc(p){return /^data:/.test(p) ? p : '/files/' + p.split('/').map(encodeURIComponent).join('/') + '?t=' + encodeURIComponent(BOOT.token);}

function render(){
  const it = items[idx], e = S.items[it.id] || {}, q = isQ(it), st = status(it);
  $('#ttl').textContent = B.title;
  $('#sub').textContent = (B.subtitle ? B.subtitle + ' · ' : '') + T('subtitle', {id: B.batch_id, n: items.length, round: B.round || 1});
  $('.grid').hidden = reviewing; $('#rev').hidden = !reviewing; $('.res').hidden = reviewing;
  let h = '<span class="pill">' + (idx+1) + '/' + items.length + ' · ' + esc(it.id) + (it.tag ? ' · ' + esc(it.tag) : '') + '</span>';
  if(st) h += '<span class="state ' + st + '">' + (q ? QLBL[st] : esc(LBL[st])) + '</span>';
  h += '<h2 id="qtitle">' + esc(it.title) + '</h2>';
  if(it.image) h += '<img alt="" src="' + esc(imgSrc(it.image)) + '">';
  h += '<div class="box">';
  (it.fields || []).forEach(f => { h += '<div class="row"><b>' + esc(f.label) + '</b><div>' + rich(f.text) + '</div></div>'; });
  if(it.risk){
    const lvl = RISK[norm(it.risk.level)] || 'medio';
    h += '<div class="row"><b>' + T('risk') + '</b><div><span class="risk ' + lvl + '">' + esc(it.risk.level || '') + (it.risk.text ? ' — ' + esc(it.risk.text) : '') + '</span></div></div>';
  }
  h += '</div>';
  if(armed === it.id) h += '<div class="armed" role="alert">' + rich(it.confirm) + '<b>' + T('armed_hint') + '</b></div>';
  if(q) h += questionHtml(it, e);
  $('#card').className = q ? 'card q' : 'card';
  $('#card').innerHTML = h;
  $('#meta').innerHTML = Object.entries(it.meta || {}).map(([k,v]) => '<div><span>' + esc(k) + '</span><b>' + esc(v) + '</b></div>').join('');
  $('#cmtlbl').innerHTML = q ? ((it.open === true || e.other) ? T('your_answer') + ' <span class="req">' + T('required') + '</span>' : T('comment_optional')) : T('comment_label');
  const cm = $('#cmt'); if(cm.value !== (e.comment || '')) cm.value = e.comment || '';
  $('#bA').style.display = $('#bR').style.display = q ? 'none' : '';
  const sure = armed === it.id;
  $('#bM').innerHTML = q ? T('need_context') + '<kbd>M</kbd>' : (LB.maybe ? esc(LB.maybe.text) : '&asymp; ' + T('maybe')) + '<kbd>M</kbd>';
  $('#bA').innerHTML = (sure ? T('confirm_label', {label: esc((LB.approve ? LB.approve.text : T('approve')).toLowerCase())}) : (LB.approve ? esc(LB.approve.text) : '&#10003; ' + T('approve'))) + '<kbd>A</kbd>';
  $('#bA').classList.toggle('sure', sure);
  $('#bR').innerHTML = (LB.reject ? esc(LB.reject.text) : '&#10007; ' + T('reject')) + '<kbd>R</kbd>';
  ['A:approved','R:rejected','M:maybe'].forEach(p => { const [k,d] = p.split(':'); $('#b'+k).classList.toggle('on', e.decision === d); });
  $('#chips').innerHTML = items.map((x,i) => { const d = status(x); return '<button class="' + d + (i===idx?' cur':'') + '" data-i="' + i + '" title="' + esc(x.title) + '">' + (i+1) + '</button>'; }).join('');
  const c = counts();
  $('#prog').style.width = ((items.length - c.pending) / items.length * 100) + '%';
  const base = '<span style="color:var(--cA)">✓ ' + c.approved + ' ' + esc(CNT.approved) + '</span><span style="color:var(--cR)">✗ ' + c.rejected + ' ' + esc(CNT.rejected) + '</span><span style="color:var(--cM)">≈ ' + c.maybe + ' ' + esc(CNT.maybe) + '</span><span style="color:var(--mut)">' + c.pending + ' ' + T('count_pending') + '</span>';
  $('#counts').innerHTML = onlyQ
    ? '<span style="color:var(--acc)">' + c.answered + ' ' + T('count_answered') + '</span><span style="color:var(--mb)">' + c.maybe + ' ' + T('count_unsure') + '</span><span style="color:var(--mut)">' + c.pending + ' ' + T('count_unanswered') + '</span>'
    : base + (hasQ ? '<span style="color:var(--acc)">' + c.answered + ' ' + T('count_answered') + '</span>' : '');
  const n = $('#note'); if(n.value !== (S.batch_note || '')) n.value = S.batch_note || '';
  $('#bF').style.display = (BOOT.live || hasQ) ? '' : 'none';
  const dn = $('#done');
  if(S.finished){dn.style.display='block';dn.textContent=T('done_banner');} else dn.style.display='none';
  if(reviewing) renderReview();
}

function go(i){armed = null; idx = Math.max(0, Math.min(items.length-1, i)); render();}
function decide(d){
  const it = items[idx], e = ent(it.id);
  if(d === 'approved' && it.confirm && e.decision !== 'approved' && armed !== it.id){armed = it.id; render(); return;}
  armed = null;
  if(e.decision === d) delete e.decision; else e.decision = d;
  tidy(it.id); S.finished = false;
  post('/api/item', {id: it.id, decision: e.decision || null});
  const decided = S.items[it.id] && S.items[it.id].decision;
  if(auto && decided && idx < items.length-1){
    idx++;
    showHint(T('decided_hint', {label: LBL[decided], id: it.id}));
  }
  render();
}
let auto = true, hintTimer;
try{auto = localStorage.getItem('ar-board:auto') !== '0';}catch(e){}
$('#auto').checked = auto;
$('#auto').onchange = ev => {auto = ev.target.checked; try{localStorage.setItem('ar-board:auto', auto ? '1' : '0');}catch(e){}};
function showHint(t){const h = $('#hint'); h.textContent = t; clearTimeout(hintTimer); hintTimer = setTimeout(() => h.textContent = '', 4500);}

$('#cmt').addEventListener('input', ev => {
  const id = items[idx].id, v = ev.target.value;
  const e = ent(id); if(v.trim()) e.comment = v; else delete e.comment; tidy(id);
  queue('c:' + id, '/api/item', {id: id, comment: v});
  if(S.finished || isQ(items[idx])){S.finished = false; render();}
});
$('#note').addEventListener('input', ev => {
  S.batch_note = ev.target.value;
  queue('note', '/api/note', {text: S.batch_note});
});
$('#chips').addEventListener('click', ev => {const b = ev.target.closest('button'); if(b) go(+b.dataset.i);});
$('#lang').addEventListener('click', ev => {const b = ev.target.closest('button[data-lang]'); if(b) setLang(b.dataset.lang);});
$('#bA').onclick = () => decide('approved'); $('#bR').onclick = () => decide('rejected'); $('#bM').onclick = () => (isQ(items[idx]) ? askMore() : decide('maybe'));
$('#bS').onclick = () => go(idx+1); $('#bN').onclick = () => go(idx+1); $('#bP').onclick = () => go(idx-1);

document.addEventListener('keydown', ev => {
  if(ev.ctrlKey || ev.metaKey || ev.altKey) return;
  if(ev.repeat && ev.key === 'Enter' && ev.target.tagName === 'BUTTON'){ev.preventDefault(); return;}
  if(reviewing){if(ev.key === 'Escape') closeReview(); return;}
  const typing = (ev.target.tagName || '').toLowerCase() === 'textarea';
  if(ev.key === 'Escape'){ if(typing) ev.target.blur(); else if(armed){armed = null; showHint(T('confirm_cancelled')); render();} return; }
  if(typing) return;
  const k = ev.key.toLowerCase();
  if(ev.repeat && (k === 'a' || k === 'r' || k === 'm')) return;
  if(isQ(items[idx])){
    if(/^[1-9]$/.test(k)){if(!ev.repeat) pick(+k); return;}
    if(k === 'enter' && (ev.target === document.body || ev.target.classList.contains('opt'))){ev.preventDefault(); confirmCard(); return;}
    if(k === 'm'){if(!ev.repeat) askMore(); return;}
    if(k === 'a' || k === 'r') return;
  }
  if(k === 'a') decide('approved');
  else if(k === 'r') decide('rejected');
  else if(k === 'm') decide('maybe');
  else if(k === 's') go(idx+1);
  else if(k === 'c'){ev.preventDefault(); $('#cmt').focus();}
  else if(ev.key === 'ArrowRight') go(idx+1);
  else if(ev.key === 'ArrowLeft') go(idx-1);
});

function flash(btn, txt){const o = btn.textContent; btn.textContent = txt; setTimeout(() => btn.textContent = o, 1400);}
$('#bC').onclick = () => {
  const txt = 'AR-BOARD-RESULT\n' + JSON.stringify(exportObj(), null, 2);
  const fallback = () => {const t = document.createElement('textarea'); t.value = txt; document.body.appendChild(t); t.select(); try{document.execCommand('copy');}catch(e){} t.remove();};
  (navigator.clipboard ? navigator.clipboard.writeText(txt).catch(fallback) : Promise.resolve(fallback())).then(() => flash($('#bC'), T('copied')));
};
$('#bD').onclick = () => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(exportObj(), null, 2)], {type:'application/json'}));
  a.download = 'ar-board-' + B.batch_id + '-r' + (B.round || 1) + '.json'; a.click();
};
$('#bX').onclick = () => {
  if(!confirm(T('clear_confirm'))) return;
  Object.keys(timers).forEach(k => clearTimeout(timers[k])); pend = {};
  S.items = {}; S.batch_note = ''; S.finished = false; Promise.all(Array.from(inflight)).then(() => post('/api/reset', {})); persistLocal(); idx = 0; render();
};
$('#bF').onclick = () => {
  const c = counts();
  if(c.pending && !confirm(T('finish_anyway', {n: c.pending}))) return;
  flushAll().then(() => post('/api/finish', {finished: true})).then(ok => {
    S.finished = ok; render();
    if(!ok) alert(T('no_server'));
  });
};

if(hasQ){
  $('#bF').onclick = openReview;
}
$('#card').addEventListener('click', ev => {
  const b = ev.target.closest('.opt'); if(!b) return;
  const n = +b.dataset.n, kb = ev.detail === 0, before = idx;
  pick(n);
  if(kb && document.activeElement !== $('#cmt')){const t = $('#card .opt[data-n="' + (idx === before ? n : 1) + '"]'); if(t) t.focus();}
});
$('#rev').addEventListener('click', ev => {
  const a = ev.target.closest('a[data-i]');
  if(a){reviewing = false; go(+a.dataset.i); return;}
  if(ev.target.closest('#rB')) closeReview();
  else if(ev.target.closest('#rC')) (BOOT.live ? finishNow() : $('#bC').click());
});
$('#rev').addEventListener('keydown', ev => {if(ev.key === 'Enter' && ev.target.matches('a[data-i]')){ev.preventDefault(); ev.target.click();}});
setLive(BOOT.live);
applyLang();
const first = items.findIndex(it => !status(it));
idx = first < 0 ? 0 : first;
render();
})();
</script></body></html>
"""
```

- [ ] **Step 4: Update the four pinned literals of the labels test**

`test_labels_confirm.py` pinned the old default wording and the IIFE; the behaviour is the same, the strings moved into the table.

In `plugins/ar-board/tests/test_labels_confirm.py`, replace:

```python
        self.assertIn("(function applyLabels(){", ab.PAGE)
```

with:

```python
        self.assertIn("function applyLabels(){", ab.PAGE)
```

In `plugins/ar-board/tests/test_labels_confirm.py`, replace:

```python
        self.assertIn("'&#10003; Aprovar'", ab.PAGE)
        self.assertIn("'&#10007; Rejeitar'", ab.PAGE)
        self.assertIn("'&asymp; Talvez'", ab.PAGE)
        self.assertIn("maybe:'talvez'", ab.PAGE)
```

with:

```python
        self.assertIn("'&#10003; ' + T('approve')", ab.PAGE)
        self.assertIn("'&#10007; ' + T('reject')", ab.PAGE)
        self.assertIn("'&asymp; ' + T('maybe')", ab.PAGE)
        self.assertIn("maybe: T('count_maybe')", ab.PAGE)
```

In `plugins/ar-board/tests/test_labels_confirm.py`, replace:

```python
        self.assertIn("else if(armed){armed = null; showHint('Confirmacao cancelada.'); render();}", ab.PAGE)
```

with:

```python
        self.assertIn("else if(armed){armed = null; showHint(T('confirm_cancelled')); render();}", ab.PAGE)
```

- [ ] **Step 5: Regenerate the copies, run the suite and parse the script**

Run: `python3 plugins/ar-board/tools/sync.py && python3 plugins/tidy-board/tools/sync.py && python3 plugins/housekeeping/tools/sync.py && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/ar-board/tests 2>&1 | grep -v '^AR-BOARD' | tail -n 3`

Expected: `Ran 232 tests` and `OK` (the ten new guards included; the literal scan finds nothing).

CI parses the embedded script with `node --check`; do the same locally when `node` is installed:

Run:

```bash
D=$(mktemp -d)
python3 - "$D/panel.js" <<'PY'
import importlib.util, re, pathlib, sys
spec = importlib.util.spec_from_file_location("ab", "plugins/ar-board/skills/ar-board/scripts/ar_board.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
pathlib.Path(sys.argv[1]).write_text("\n".join(re.findall(r"<script>(.*?)</script>", m.PAGE, re.S)), encoding="utf-8")
PY
node --check "$D/panel.js" && echo node-ok || echo 'node is not installed: CI will parse the script'
```

Expected: `node-ok` (or the fallback message).

- [ ] **Step 6: Commit**

Run:

```bash
git add -A
git commit -m "feat(ar-board): the page reads every string from the I18N table and gets an EN/PT toggle" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

Expected: one commit (git status --short is empty afterwards).

### Task 2b: Engine, the command line: every message in English or pt-BR, `--lang` on every command, `CAPYBARA_LANG`

**Files:**
- Modify: `plugins/ar-board/skills/ar-board/scripts/ar_board.py` (the usage comment; a new section `mensagens da linha de comando` before `# ---- batch`; `validate_question`, `validate_labels`, `validate`, `load_batch`; `Store.__init__`; `answer_text`, `render_summary`; `resolve_lang`; every `cmd_*` and `main`)
- Modify: `plugins/ar-board/tests/helpers.py`, `test_lang.py`, `test_labels_confirm.py`, `test_question_validate.py`, `test_question_summary.py`, `test_cli.py` (the pinned Portuguese command-line text becomes the English default; each file keeps or gains a pt-BR case)
- Create: `plugins/ar-board/tests/test_cli_lang.py`

**Interfaces:**
- Consumes: `LANGS`, `DEFAULT_LANG`, `resolve_lang` (Task 1).
- Produces: `ENV_LANG = "CAPYBARA_LANG"`, `MSG` (two dicts with identical keys; the pt-BR side is the accent-free Portuguese the engine printed before, a key ending in `_1` is the singular form used when `n == 1`), `env_lang() -> str | None`, `say(lang, msg_id, /, **values) -> str` (positional-only, so a placeholder may be named like any argument); `resolve_lang(batch, flag=None)` now reads `flag`, then the batch's `lang`, then `CAPYBARA_LANG`, then `en` (the page applies the saved toggle on top, R1); `validate(b, lang=DEFAULT_LANG)`, `load_batch(d, flag=None)`, `Store(d, lang=None)`, `answer_text(answer, lang=DEFAULT_LANG)`, `render_summary(batch, state, as_json=False, lang=DEFAULT_LANG)`; `--lang {en,pt-BR}` on all five subcommands (default `None`); the help text in English. The JSON summary, `decisions.json`, the HTTP API and its error bodies are unchanged. The line tags `AR-BOARD URL:`, `AR-BOARD DECISOES:`, `AR-BOARD ARQUIVO:`, `TIMEOUT:` and `ok:` are the same in both languages (agents and scripts look for them); the rest of each line follows the language.
- Consumed by Task 3 (the release), Tasks 4b and 5b-5d (the same resolution order and the same `CAPYBARA_LANG`), Task 6 (the skills quote the English lines).

- [ ] **Step 1: Keep the environment out of the suite**

`CAPYBARA_LANG` set in the shell of whoever runs the tests would change every default the suite pins. The helpers module is imported by every test file, and the subprocesses the tests start inherit `os.environ`, so one line covers both:

In `plugins/ar-board/tests/helpers.py`, replace:

```python
sys.dont_write_bytecode = True  # never leave __pycache__ inside the plugin (it would ship with it)
```

with:

```python
sys.dont_write_bytecode = True  # never leave __pycache__ inside the plugin (it would ship with it)

import os

os.environ.pop("CAPYBARA_LANG", None)  # the defaults the suite pins must not depend on the shell that runs it
```

- [ ] **Step 2: Write the failing tests**

`test_cli_lang.py` pins the message table (same keys and placeholders, plain ASCII, the pt-BR side equal to the old output), an AST guard that no Portuguese literal is left in the functions that print, the singular forms, the resolution order with `CAPYBARA_LANG`, and every command in both languages.

Create `plugins/ar-board/tests/test_cli_lang.py`:

```python
import ast
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from unittest import mock

from helpers import SCRIPT, ab, make_batch

PLACEHOLDER = re.compile(r"\{(\w+)\}")
CLI_FUNCTIONS = ("validate_question", "validate_labels", "validate", "load_batch", "answer_text", "render_summary",
                 "cmd_serve", "cmd_wait", "cmd_summary", "cmd_build", "cmd_check", "main")
PT_WORDS = {  # words of the old command-line output: any of them in a literal of those functions is a leftover
    "nao", "deve", "obrigatorio", "itens", "lote", "rodada", "perguntas", "aviso", "erro", "encontrei", "consegui",
    "invalido", "valido", "porta", "usuario", "concluiu", "resposta", "comentario", "outra", "concluido", "aprovados",
    "rejeitados", "talvez", "respondidas", "precisam", "decisao", "nota", "geral", "sim", "parcial", "recomendada",
    "painel", "aprovar", "rejeitar", "somente", "chave", "desconhecida", "objeto", "booleano", "inteiro", "opcoes",
    "combina", "casar", "duplicado", "cita", "repetido", "limite", "pergunta", "contexto", "texto", "vazio", "raiz",
}


def board(**extra):
    b = {"batch_id": "t", "title": "T", "items": [{"id": "A01", "title": "x"}]}
    b.update(extra)
    return b


def run(*args, env=None):
    return subprocess.run([sys.executable, "-I", str(SCRIPT), *args], capture_output=True, text=True,
                          env={**os.environ, **(env or {})})


def literals(fn):
    """Every string literal inside a function, docstring left out."""
    body = fn.body[1:] if fn.body and isinstance(fn.body[0], ast.Expr) and isinstance(fn.body[0].value, ast.Constant) else fn.body
    return [n.value for stmt in body for n in ast.walk(stmt) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


class MessageTableTest(unittest.TestCase):
    def test_both_languages_have_the_same_keys_and_placeholders(self):
        self.assertEqual(set(ab.MSG), set(ab.LANGS))
        en, pt = ab.MSG["en"], ab.MSG["pt-BR"]
        self.assertEqual(set(en), set(pt))
        for key in en:
            with self.subTest(key=key):
                self.assertEqual(set(PLACEHOLDER.findall(en[key])), set(PLACEHOLDER.findall(pt[key])))
                if key.endswith("_1"):
                    self.assertIn(key[:-2], en)  # a singular form always has its plural

    def test_the_command_line_text_is_plain_ascii_in_both_languages(self):
        for lang, table in ab.MSG.items():  # pt-BR stays accent-free, as the command line always was
            for key, value in table.items():
                with self.subTest(lang=lang, key=key):
                    self.assertTrue(value.isascii(), value)

    def test_the_pt_br_side_is_the_old_output(self):
        pt = ab.MSG["pt-BR"]
        self.assertEqual(pt["invalid"], "batch.json invalido:")
        self.assertEqual(pt["ok"], "ok: {n} itens, lote {id}, rodada {round}")
        self.assertEqual(pt["timeout"], "TIMEOUT: o usuario ainda nao concluiu o lote.")
        self.assertEqual(pt["item_title"], "item {i}: 'title' obrigatorio")

    def test_no_portuguese_literal_is_left_in_the_functions_that_print(self):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        found = []
        for fn in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in CLI_FUNCTIONS):
            for text in literals(fn):
                words = set(re.split(r"[^a-z]+", text.lower()))
                if words & PT_WORDS:
                    found.append(f"{fn.name}: {text!r}")
        self.assertEqual(found, [], "Portuguese left outside MSG:\n" + "\n".join(found))

    def test_one_takes_the_singular_form(self):
        self.assertEqual(ab.say("en", "ok", n=1, id="t", round=1), "ok: 1 item, batch t, round 1")
        self.assertEqual(ab.say("en", "ok", n=2, id="t", round=1), "ok: 2 items, batch t, round 1")
        self.assertEqual(ab.say("pt-BR", "ok", n=1, id="t", round=1), "ok: 1 item, lote t, rodada 1")
        self.assertEqual(ab.say("pt-BR", "ok", n=0, id="t", round=1), "ok: 0 itens, lote t, rodada 1")


class ResolveWithTheEnvironmentTest(unittest.TestCase):
    def test_capybara_lang_comes_after_the_flag_and_the_batch(self):
        with mock.patch.dict(os.environ, {"CAPYBARA_LANG": "pt-BR"}):
            self.assertEqual(ab.resolve_lang(board()), "pt-BR")
            self.assertEqual(ab.resolve_lang(board(lang="en")), "en")
            self.assertEqual(ab.resolve_lang(board(), "en"), "en")
            self.assertEqual(ab.resolve_lang(None), "pt-BR")  # no batch read yet (a missing or broken batch.json)

    def test_a_bad_capybara_lang_is_ignored_and_never_an_error(self):
        for bad in ("pt", "PT-BR", "pt_BR", "", "xx"):
            with self.subTest(env=bad), mock.patch.dict(os.environ, {"CAPYBARA_LANG": bad}):
                self.assertEqual(ab.resolve_lang(board()), "en")
                self.assertIsNone(ab.env_lang())


class ValidateAndSummaryLanguageTest(unittest.TestCase):
    STATE = {"round": 1, "finished": True, "batch_note": "n", "items": {"A01": {"decision": "approved", "comment": "ok"}}}

    def test_validate_speaks_english_by_default_and_pt_br_on_request(self):
        self.assertEqual(ab.validate(board(items=[{"id": "A01"}])), ["item 0: 'title' is required"])
        self.assertEqual(ab.validate(board(items=[{"id": "A01"}]), "pt-BR"), ["item 0: 'title' obrigatorio"])

    def test_the_text_summary_in_both_languages(self):
        out = ab.render_summary(board(), self.STATE)
        for line in ("# AR board - T (batch t, round 1)", "Finished by the user: yes", "## Approved (1)",
                     "    user comment: 'ok'", "## No decision (0)", "## General note on the batch\nn"):
            self.assertIn(line, out)
        out = ab.render_summary(board(), self.STATE, lang="pt-BR")
        for line in ("# AR board - T (lote t, rodada 1)", "Concluido pelo usuario: sim", "## Aprovados (1)",
                     "    comentario do usuario: 'ok'", "## Sem decisao (0)", "## Nota geral do lote\nn"):
            self.assertIn(line, out)

    def test_the_json_summary_carries_no_language(self):
        a = json.loads(ab.render_summary(board(), self.STATE, as_json=True))
        b = json.loads(ab.render_summary(board(), self.STATE, as_json=True, lang="pt-BR"))
        self.assertEqual(a, b)
        self.assertNotIn("lang", a)


class CommandLineLanguageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_check_follows_flag_then_batch_then_environment_then_english(self):
        d = make_batch(self.tmp.name)
        self.assertEqual(run("check", str(d)).stdout, "ok: 2 items, batch t, round 1\n")
        self.assertEqual(run("check", str(d), "--lang", "pt-BR").stdout, "ok: 2 itens, lote t, rodada 1\n")
        self.assertEqual(run("check", str(d), env={"CAPYBARA_LANG": "pt-BR"}).stdout, "ok: 2 itens, lote t, rodada 1\n")
        d = make_batch(self.tmp.name, lang="pt-BR")
        self.assertEqual(run("check", str(d)).stdout, "ok: 2 itens, lote t, rodada 1\n")
        self.assertEqual(run("check", str(d), "--lang", "en").stdout, "ok: 2 items, batch t, round 1\n")

    def test_a_bad_capybara_lang_falls_back_to_english_without_a_warning(self):
        d = make_batch(self.tmp.name)
        r = run("check", str(d), env={"CAPYBARA_LANG": "pt"})
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "ok: 2 items, batch t, round 1\n", ""))

    def test_a_broken_batch_is_reported_in_the_language_of_the_run(self):
        d = make_batch(self.tmp.name, lang="xx", items=[{"id": "A01"}])
        r = run("check", str(d))
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stderr, "invalid batch.json:\n- field 'lang' must be en or pt-BR\n- item 0: 'title' is required\n")
        r = run("check", str(d), "--lang", "pt-BR")
        self.assertEqual(r.stderr, "batch.json invalido:\n- campo 'lang' deve ser en ou pt-BR\n- item 0: 'title' obrigatorio\n")
        self.assertIn("could not find", run("check", os.path.join(self.tmp.name, "nope")).stderr)
        self.assertIn("nao encontrei", run("check", os.path.join(self.tmp.name, "nope"), "--lang", "pt-BR").stderr)

    def test_summary_and_wait_in_both_languages(self):
        d = make_batch(self.tmp.name)
        self.assertIn("## No decision (2)", run("summary", str(d)).stdout)
        self.assertIn("## Sem decisao (2)", run("summary", str(d), "--lang", "pt-BR").stdout)
        r = run("wait", str(d), "--timeout", "1", "--lang", "pt-BR")
        self.assertEqual((r.returncode, r.stdout), (2, "TIMEOUT: o usuario ainda nao concluiu o lote.\n"))
        r = run("wait", str(d), "--timeout", "1")
        self.assertEqual((r.returncode, r.stdout), (2, "TIMEOUT: the user has not finished the batch yet.\n"))

    def test_the_line_tags_are_the_same_in_both_languages(self):
        d = make_batch(self.tmp.name)
        for lang in ("en", "pt-BR"):
            with self.subTest(lang=lang):
                self.assertTrue(run("build", str(d), "--lang", lang).stdout.startswith("AR-BOARD ARQUIVO: "))

    def test_every_command_takes_lang_and_refuses_a_bad_one(self):
        d = make_batch(self.tmp.name)
        for cmd in ("serve", "wait", "summary", "build", "check"):
            with self.subTest(cmd=cmd):
                self.assertIn("--lang {en,pt-BR}", run(cmd, "--help").stdout)
                r = run(cmd, str(d), "--lang", "xx")
                self.assertEqual(r.returncode, 2)
                self.assertIn("invalid choice: 'xx'", r.stderr)

    def test_a_namespace_without_lang_still_works(self):
        d = make_batch(self.tmp.name)  # callers that build the namespace by hand (the older tests) give no lang
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(ab.cmd_check(Namespace(dir=str(d))), 0)
        self.assertEqual(out.getvalue(), "ok: 2 items, batch t, round 1\n")


if __name__ == "__main__":
    unittest.main()
```

The tests of Task 1 and the older suites that pinned the Portuguese text now pin the English default; the pt-BR text they pinned is covered by `test_cli_lang.py` and by the pt-BR cases added here.

In `plugins/ar-board/tests/test_lang.py`, replace:

```python
                self.assertEqual(errs, ["campo 'lang' deve ser en ou pt-BR"])
```

with:

```python
                self.assertEqual(errs, ["field 'lang' must be en or pt-BR"])
                self.assertEqual(ab.validate(board(lang=bad), "pt-BR"), ["campo 'lang' deve ser en ou pt-BR"])
```

In `plugins/ar-board/tests/test_lang.py`, replace:

```python
        self.assertTrue(any("'title' obrigatorio" in e for e in errs), errs)
```

with:

```python
        self.assertTrue(any("'title' is required" in e for e in errs), errs)
```

In `plugins/ar-board/tests/test_lang.py`, replace:

```python
            self.assertIn("campo 'lang' deve ser en ou pt-BR", r.stderr)
```

with:

```python
            self.assertIn("field 'lang' must be en or pt-BR", r.stderr)
```

In `plugins/ar-board/tests/test_labels_confirm.py`, replace:

```python
        self.assertTrue(has(ab.validate(board(labels=["Apagar"])), "'labels' deve ser objeto"))
```

with:

```python
        self.assertTrue(has(ab.validate(board(labels=["Apagar"])), "'labels' must be an object"))
        self.assertTrue(has(ab.validate(board(labels=["Apagar"]), "pt-BR"), "'labels' deve ser objeto"))
```

In `plugins/ar-board/tests/test_labels_confirm.py`, replace:

```python
        self.assertTrue(has(errs, "chave desconhecida 'aprove'"), errs)
```

with:

```python
        self.assertTrue(has(errs, "unknown key 'aprove'"), errs)
```

In `plugins/ar-board/tests/test_labels_confirm.py`, replace:

```python
        self.assertTrue(has(ab.validate(board(labels={"approve": "Apagar"})), "labels.approve: deve ser objeto"))
```

with:

```python
        self.assertTrue(has(ab.validate(board(labels={"approve": "Apagar"})), "labels.approve: must be an object"))
```

In `plugins/ar-board/tests/test_labels_confirm.py`, replace:

```python
                self.assertTrue(has(errs, "labels.reject: 'text' obrigatorio"), errs)
```

with:

```python
                self.assertTrue(has(errs, "labels.reject: 'text' is required"), errs)
```

In `plugins/ar-board/tests/test_labels_confirm.py`, replace:

```python
        self.assertTrue(has(errs, "labels.maybe: 'tone' deve ser safe, danger ou caution"), errs)
```

with:

```python
        self.assertTrue(has(errs, "labels.maybe: 'tone' must be safe, danger or caution"), errs)
```

In `plugins/ar-board/tests/test_labels_confirm.py`, replace:

```python
        self.assertTrue(has(errs, "chave desconhecida"), errs)
        self.assertTrue(has(errs, "'title' obrigatorio"), errs)
```

with:

```python
        self.assertTrue(has(errs, "unknown key"), errs)
        self.assertTrue(has(errs, "'title' is required"), errs)
```

In `plugins/ar-board/tests/test_labels_confirm.py`, replace:

```python
                self.assertTrue(has(ab.validate(self.item(confirm=bad)), "'confirm' deve ser texto nao vazio"))
```

with:

```python
                self.assertTrue(has(ab.validate(self.item(confirm=bad)), "'confirm' must be non-empty text"))
```

In `plugins/ar-board/tests/test_labels_confirm.py`, replace:

```python
        self.assertTrue(has(errs, "'confirm' nao vale em card de pergunta"), errs)
```

with:

```python
        self.assertTrue(has(errs, "'confirm' does not apply to a question card"), errs)
```

In `plugins/ar-board/tests/test_labels_confirm.py`, replace:

```python
        out = ab.render_summary(b, self.STATE)
        self.assertIn("## Apagar (1)", out)
        self.assertIn("## Rejeitados (1)", out)
        self.assertIn("## Talvez (0)", out)
```

with:

```python
        out = ab.render_summary(b, self.STATE)
        self.assertIn("## Apagar (1)", out)
        self.assertIn("## Rejected (1)", out)
        self.assertIn("## Maybe (0)", out)
        out = ab.render_summary(b, self.STATE, lang="pt-BR")
        self.assertIn("## Apagar (1)", out)
        self.assertIn("## Rejeitados (1)", out)
        self.assertIn("## Talvez (0)", out)
```

In `plugins/ar-board/tests/test_labels_confirm.py`, replace:

```python
        out = ab.render_summary(b, self.STATE)
        self.assertIn("## Aprovados (1)", out)
        self.assertIn("## Rejeitados (1)", out)
```

with:

```python
        out = ab.render_summary(b, self.STATE)
        self.assertIn("## Approved (1)", out)
        self.assertIn("## Rejected (1)", out)
        out = ab.render_summary(b, self.STATE, lang="pt-BR")
        self.assertIn("## Aprovados (1)", out)
        self.assertIn("## Rejeitados (1)", out)
```

In `plugins/ar-board/tests/test_labels_confirm.py`, replace:

```python
        self.assertNotIn("## Aprovados", out)
```

with:

```python
        self.assertNotIn("## Approved", out)
```

In `plugins/ar-board/tests/test_question_validate.py`, replace:

```python
        self.assertTrue(has(errors(choices=[{"id": "a", "label": "A"}, {"id": "a", "label": "B"}]), "duplicado"))
```

with:

```python
        self.assertTrue(has(errors(choices=[{"id": "a", "label": "A"}, {"id": "a", "label": "B"}]), "duplicate"))
```

In `plugins/ar-board/tests/test_question_validate.py`, replace:

```python
        self.assertTrue(has(errors(choices=["a", "b"]), "deve ser objeto"))
```

with:

```python
        self.assertTrue(has(errors(choices=["a", "b"]), "must be an object"))
```

In `plugins/ar-board/tests/test_question_validate.py`, replace:

```python
        self.assertTrue(has(errors(open=True), "'open' nao combina com 'choices'"))
```

with:

```python
        self.assertTrue(has(errors(open=True), "'open' does not go with 'choices'"))
```

In `plugins/ar-board/tests/test_question_validate.py`, replace:

```python
                self.assertTrue(has(errors(choices=None, open=True, **{key: value}), "'open' nao combina com '%s'" % key))
```

with:

```python
                self.assertTrue(has(errors(choices=None, open=True, **{key: value}), "'open' does not go with '%s'" % key))
```

In `plugins/ar-board/tests/test_question_validate.py`, replace:

```python
                self.assertTrue(has(errors(**{key: 1}), "so vale com 'multiple'"))
```

with:

```python
                self.assertTrue(has(errors(**{key: 1}), "only applies with 'multiple'"))
```

In `plugins/ar-board/tests/test_question_validate.py`, replace:

```python
                self.assertTrue(has(errors(fields=bad), "contexto"))
```

with:

```python
                self.assertTrue(has(errors(fields=bad), "context"))
```

In `plugins/ar-board/tests/test_question_validate.py`, replace:

```python
        self.assertTrue(has(errors(choices=None, open=True, fields=None), "contexto"))
```

with:

```python
        self.assertTrue(has(errors(choices=None, open=True, fields=None), "context"))
```

In `plugins/ar-board/tests/test_question_validate.py`, replace:

```python
        self.assertIn("ok: 8 itens", out)
```

with:

```python
        self.assertIn("ok: 8 items", out)
```

In `plugins/ar-board/tests/test_question_validate.py`, replace:

```python
        self.assertIn("aviso", err)
        self.assertIn("9 perguntas", err)
```

with:

```python
        self.assertIn("warning: 9 questions in the round", err)
```

In `plugins/ar-board/tests/test_question_summary.py`, replace:

```python
        out = ab.render_summary(b, s)
        self.assertIn("## Respondidas (1)", out)
        self.assertIn("- Q01 - Um", out)
        self.assertIn("resposta: Opcao A (recomendada)", out)
        self.assertIn("comentario do usuario: 'gostei'", out)
        self.assertIn("## Precisam de contexto (1)", out)
        self.assertIn("- Q03 - Tres", out)
        self.assertIn("## Sem decisao (1)", out)
        self.assertLess(out.index("## Respondidas"), out.index("## Sem decisao"))
```

with:

```python
        out = ab.render_summary(b, s)
        self.assertIn("## Answered (1)", out)
        self.assertIn("- Q01 - Um", out)
        self.assertIn("answer: Opcao A (recommended)", out)
        self.assertIn("user comment: 'gostei'", out)
        self.assertIn("## Need context (1)", out)
        self.assertIn("- Q03 - Tres", out)
        self.assertIn("## No decision (1)", out)
        self.assertLess(out.index("## Answered"), out.index("## No decision"))
        out = ab.render_summary(b, s, lang="pt-BR")  # the pt-BR summary is the one the engine printed before
        self.assertIn("## Respondidas (1)", out)
        self.assertIn("resposta: Opcao A (recomendada)", out)
        self.assertIn("comentario do usuario: 'gostei'", out)
        self.assertIn("## Precisam de contexto (1)", out)
        self.assertIn("## Sem decisao (1)", out)
        self.assertLess(out.index("## Respondidas"), out.index("## Sem decisao"))
```

In `plugins/ar-board/tests/test_question_summary.py`, replace:

```python
        self.assertIn("resposta: limpar", out)
        self.assertIn("resposta: Outra: x y", out)
```

with:

```python
        self.assertIn("answer: limpar", out)
        self.assertIn("answer: Other: x y", out)
```

In `plugins/ar-board/tests/test_question_summary.py`, replace:

```python
        self.assertNotIn("Respondidas", out)
        self.assertNotIn("Precisam de contexto", out)
        self.assertIn("## Aprovados (1)", out)
```

with:

```python
        self.assertNotIn("Answered", out)
        self.assertNotIn("Need context", out)
        self.assertIn("## Approved (1)", out)
```

In `plugins/ar-board/tests/test_question_summary.py`, replace:

```python
        self.assertEqual(ab.answer_text({"kind": "choices", "ids": ["a"], "labels": ["A"], "other": "z"}), "A + Outra: z")
        self.assertEqual(ab.answer_text({"kind": "other", "text": "z"}), "Outra: z")
```

with:

```python
        self.assertEqual(ab.answer_text({"kind": "choices", "ids": ["a"], "labels": ["A"], "other": "z"}), "A + Other: z")
        self.assertEqual(ab.answer_text({"kind": "other", "text": "z"}), "Other: z")
        self.assertEqual(ab.answer_text({"kind": "other", "text": "z"}, "pt-BR"), "Outra: z")
```

In `plugins/ar-board/tests/test_cli.py`, replace:

```python
        self.assertIn("painel local de aprovar/rejeitar", r.stdout)
```

with:

```python
        self.assertIn("a local approve/reject panel", r.stdout)
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/ar-board/tests 2>&1 | grep -v '^AR-BOARD' | tail -n 3`

Expected: `FAILED (` with failures and errors: `ab.MSG`, `ab.say` and `ab.env_lang` do not exist, `validate` takes no language and the engine still prints Portuguese.

- [ ] **Step 4: The message table, the resolution and the usage comment**

The table sits before the batch section, so `validate` and every command can use it. The pt-BR side is the accent-free Portuguese the engine printed before (byte for byte, except that a count of one now takes the singular: `1 item`, not `1 itens`).

In `plugins/ar-board/skills/ar-board/scripts/ar_board.py`, replace:

```python
#   ar_board.py serve   DIR [--port N] [--open] [--exit-on-finish]
#   ar_board.py wait    DIR [--timeout SEGUNDOS]     # bloqueia ate o usuario clicar "Concluir"
#   ar_board.py summary DIR [--json]                  # resumo das decisoes (le decisions.json)
#   ar_board.py build   DIR                           # gera board.html offline (fallback sem localhost)
#   ar_board.py check   DIR                           # valida batch.json
```

with:

```python
#   ar_board.py serve   DIR [--port N] [--open] [--exit-on-finish]
#   ar_board.py wait    DIR [--timeout SEGUNDOS]     # bloqueia ate o usuario clicar "Concluir"
#   ar_board.py summary DIR [--json]                  # resumo das decisoes (le decisions.json)
#   ar_board.py build   DIR                           # gera board.html offline (fallback sem localhost)
#   ar_board.py check   DIR                           # valida batch.json
# Todo comando aceita --lang en|pt-BR (padrao: o lang do batch, depois CAPYBARA_LANG, depois en).
```

In `plugins/ar-board/skills/ar-board/scripts/ar_board.py`, replace the line:

```python
# ---------------------------------------------------------------- batch
```

with the following block (the old line stays as its last line):

```python
# ---------------------------------------------------------------- mensagens da linha de comando

ENV_LANG = "CAPYBARA_LANG"  # one shell-wide default for every Capybara Toolbox script

# Every message the command line prints, in both languages (the panel's own text is I18N, below). The two tables
# have the same keys and {placeholders} (a test enforces it); both are plain ASCII, so the pt-BR side is the
# accent-free Portuguese these commands always printed. A key ending in `_1` is the form used when n == 1.
# The HTTP error bodies are not here: they are part of the API the page reads.
MSG = {
    "en": {
        "q_open_bool": "item {i}: 'open' must be a boolean", "q_open_conflict": "item {i}: 'open' does not go with '{k}'",
        "q_choices": "item {i}: 'choices' must be a list of 2 to {max} options",
        "q_choice_obj": "item {i}: choices[{j}] must be an object",
        "q_choice_id": "item {i}: choices[{j}] 'id' must match [A-Za-z0-9_-]{{1,32}}",
        "q_choice_dup": "item {i}: choices[{j}] duplicate id '{cid}'",
        "q_choice_label": "item {i}: choices[{j}] 'label' is required",
        "q_choice_effect": "item {i}: choices[{j}] 'effect' must be a string",
        "q_multiple_bool": "item {i}: 'multiple' must be a boolean", "q_int": "item {i}: '{k}' must be an integer",
        "q_only_multiple": "item {i}: '{k}' only applies with 'multiple': true",
        "q_range": "item {i}: needs 1 <= min <= max <= {count} (the number of options)",
        "q_rec_list": "item {i}: 'recommended' must be a list of ids (text)",
        "q_rec_unknown": "item {i}: 'recommended' names an id that is not in 'choices'",
        "q_rec_repeat": "item {i}: 'recommended' repeats an id",
        "q_rec_limit": "item {i}: 'recommended' has more ids than the limit ({limit})",
        "q_why_required": "item {i}: 'why' is required when there is 'recommended'",
        "q_why_str": "item {i}: 'why' must be a string",
        "q_context": "item {i}: a question needs context (an entry in 'fields' with text)",
        "labels_obj": "field 'labels' must be an object",
        "labels_key": "labels: unknown key '{k}' (use approve, reject or maybe)",
        "labels_entry": "labels.{k}: must be an object with 'text' and, optionally, 'tone'",
        "labels_text": "labels.{k}: 'text' is required (1 to {max} characters)",
        "labels_tone": "labels.{k}: 'tone' must be safe, danger or caution",
        "root_obj": "the root of batch.json must be an object", "field_required": "field '{k}' is required (string)",
        "field_round": "field 'round' must be an integer >= 1", "field_lang": "field 'lang' must be en or pt-BR",
        "field_items": "'items' must be a non-empty list",
        "item_obj": "item {i}: must be an object", "item_id": "item {i}: 'id' is required",
        "item_dup": "item {i}: duplicate id '{iid}'", "item_title": "item {i}: 'title' is required",
        "item_str": "item {i}: '{k}' must be a string", "item_meta": "item {i}: 'meta' must be an object",
        "item_risk": "item {i}: 'risk' must be an object with 'level' and 'text' as text",
        "item_fields": "item {i}: 'fields' must be a list of {{label, text}} (text)",
        "item_confirm": "item {i}: 'confirm' must be non-empty text",
        "item_confirm_q": "item {i}: 'confirm' does not apply to a question card",
        "no_batch": "could not find {path}", "bad_json": "batch.json is not valid JSON: {e}", "invalid": "invalid batch.json:",
        "port": "could not open port {port}: {e}", "timeout": "TIMEOUT: the user has not finished the batch yet.",
        "many_questions": "warning: {n} questions in the round; the ideal is up to {max} (the dependent ones wait for the next round)",
        "ok": "ok: {n} items, batch {id}, round {round}", "ok_1": "ok: {n} item, batch {id}, round {round}",
        "s_head": "# AR board - {title} (batch {id}, round {round})", "s_finished": "Finished by the user: {value}",
        "s_yes": "yes", "s_partial": "NO (partial)", "s_comment": "user comment: {comment}",
        "s_answer": "answer: {answer}", "s_recommended": "(recommended)", "s_other": "Other: {text}",
        "s_approved": "Approved", "s_rejected": "Rejected", "s_maybe": "Maybe", "s_answered": "Answered",
        "s_unsure": "Need context", "s_pending": "No decision", "s_note": "General note on the batch",
    },
    "pt-BR": {
        "q_open_bool": "item {i}: 'open' deve ser booleano", "q_open_conflict": "item {i}: 'open' nao combina com '{k}'",
        "q_choices": "item {i}: 'choices' deve ser uma lista de 2 a {max} opcoes",
        "q_choice_obj": "item {i}: choices[{j}] deve ser objeto",
        "q_choice_id": "item {i}: choices[{j}] 'id' deve casar [A-Za-z0-9_-]{{1,32}}",
        "q_choice_dup": "item {i}: choices[{j}] id duplicado '{cid}'",
        "q_choice_label": "item {i}: choices[{j}] 'label' obrigatorio",
        "q_choice_effect": "item {i}: choices[{j}] 'effect' deve ser string",
        "q_multiple_bool": "item {i}: 'multiple' deve ser booleano", "q_int": "item {i}: '{k}' deve ser inteiro",
        "q_only_multiple": "item {i}: '{k}' so vale com 'multiple': true",
        "q_range": "item {i}: precisa 1 <= min <= max <= {count} (numero de opcoes)",
        "q_rec_list": "item {i}: 'recommended' deve ser lista de ids (texto)",
        "q_rec_unknown": "item {i}: 'recommended' cita id que nao esta em 'choices'",
        "q_rec_repeat": "item {i}: 'recommended' tem id repetido",
        "q_rec_limit": "item {i}: 'recommended' tem mais ids do que o limite ({limit})",
        "q_why_required": "item {i}: 'why' e obrigatorio quando ha 'recommended'",
        "q_why_str": "item {i}: 'why' deve ser string",
        "q_context": "item {i}: pergunta precisa de contexto (um item em 'fields' com texto)",
        "labels_obj": "campo 'labels' deve ser objeto",
        "labels_key": "labels: chave desconhecida '{k}' (use approve, reject ou maybe)",
        "labels_entry": "labels.{k}: deve ser objeto com 'text' e, opcional, 'tone'",
        "labels_text": "labels.{k}: 'text' obrigatorio (1 a {max} caracteres)",
        "labels_tone": "labels.{k}: 'tone' deve ser safe, danger ou caution",
        "root_obj": "a raiz do batch.json deve ser um objeto", "field_required": "campo '{k}' e obrigatorio (string)",
        "field_round": "campo 'round' deve ser inteiro >= 1", "field_lang": "campo 'lang' deve ser en ou pt-BR",
        "field_items": "'items' deve ser uma lista nao vazia",
        "item_obj": "item {i}: deve ser objeto", "item_id": "item {i}: 'id' obrigatorio",
        "item_dup": "item {i}: id duplicado '{iid}'", "item_title": "item {i}: 'title' obrigatorio",
        "item_str": "item {i}: '{k}' deve ser string", "item_meta": "item {i}: 'meta' deve ser objeto",
        "item_risk": "item {i}: 'risk' deve ser objeto com 'level' e 'text' em texto",
        "item_fields": "item {i}: 'fields' deve ser lista de {{label, text}} (texto)",
        "item_confirm": "item {i}: 'confirm' deve ser texto nao vazio",
        "item_confirm_q": "item {i}: 'confirm' nao vale em card de pergunta",
        "no_batch": "nao encontrei {path}", "bad_json": "batch.json nao e JSON valido: {e}", "invalid": "batch.json invalido:",
        "port": "nao consegui abrir a porta {port}: {e}", "timeout": "TIMEOUT: o usuario ainda nao concluiu o lote.",
        "many_questions": "aviso: {n} perguntas na rodada; o ideal e ate {max} (as dependentes ficam para a proxima rodada)",
        "ok": "ok: {n} itens, lote {id}, rodada {round}", "ok_1": "ok: {n} item, lote {id}, rodada {round}",
        "s_head": "# AR board - {title} (lote {id}, rodada {round})", "s_finished": "Concluido pelo usuario: {value}",
        "s_yes": "sim", "s_partial": "NAO (parcial)", "s_comment": "comentario do usuario: {comment}",
        "s_answer": "resposta: {answer}", "s_recommended": "(recomendada)", "s_other": "Outra: {text}",
        "s_approved": "Aprovados", "s_rejected": "Rejeitados", "s_maybe": "Talvez", "s_answered": "Respondidas",
        "s_unsure": "Precisam de contexto", "s_pending": "Sem decisao", "s_note": "Nota geral do lote",
    },
}


def env_lang():
    """CAPYBARA_LANG when it is exactly one of LANGS. Any other value is ignored, silently: a shell setting must
    never break a command, and a warning on every run would be noise in the agent's context."""
    value = os.environ.get(ENV_LANG)
    return value if value in LANGS else None


def say(lang, msg_id, /, **values):
    """One command-line message in `lang`; with n == 1 the `_1` form wins when the table has one. The template is
    ours, the values are data (substituted, never parsed)."""
    table = MSG[lang] if lang in LANGS else MSG[DEFAULT_LANG]
    if values.get("n") == 1 and msg_id + "_1" in table:
        msg_id += "_1"
    return table[msg_id].format(**values)


# ---------------------------------------------------------------- batch
```

The resolution of Task 1 gains the environment as its last step before English, and accepts no batch at all (an error before `batch.json` could be read):

In `plugins/ar-board/skills/ar-board/scripts/ar_board.py`, replace:

```python
def resolve_lang(batch, flag=None):
    """The language the page opens in before the browser's own choice: --lang, then the batch's `lang`, then English."""
    for cand in (flag, batch.get("lang")):
        if cand in LANGS:
            return cand
    return DEFAULT_LANG
```

with:

```python
def resolve_lang(batch, flag=None):
    """The language of a run: --lang, then the batch's `lang`, then CAPYBARA_LANG, then English. The command line
    uses it as it is; the page opens in it and then applies the browser's saved toggle on top (R1)."""
    for cand in (flag, batch.get("lang") if isinstance(batch, dict) else None, env_lang()):
        if isinstance(cand, str) and cand in LANGS:
            return cand
    return DEFAULT_LANG
```

- [ ] **Step 5: Validation, the summary and the commands in a language**

Each function that produced text now takes the language and asks `say()`; the logic is unchanged line for line.

In `plugins/ar-board/skills/ar-board/scripts/ar_board.py`, replace everything from the line `def validate_question(i, it, errs):` up to (not including) the line `def round_of(b):` with:

```python
def validate_question(i, it, errs, lang=DEFAULT_LANG):
    opened = it.get("open")
    if opened is not None and not isinstance(opened, bool):
        errs.append(say(lang, "q_open_bool", i=i))
    if not is_question(it):
        return
    if opened is True:
        for k in ("choices", "multiple", "min", "max", "recommended", "why"):
            if it.get(k) is not None:
                errs.append(say(lang, "q_open_conflict", i=i, k=k))
    else:
        choices = it.get("choices")
        listed = choices if isinstance(choices, list) else []
        if not isinstance(choices, list) or not 2 <= len(choices) <= MAX_CHOICES:
            errs.append(say(lang, "q_choices", i=i, max=MAX_CHOICES))
        ids = []
        for j, c in enumerate(listed):
            if not isinstance(c, dict):
                errs.append(say(lang, "q_choice_obj", i=i, j=j))
                continue
            cid = c.get("id")
            if not isinstance(cid, str) or not CHOICE_ID.fullmatch(cid):
                errs.append(say(lang, "q_choice_id", i=i, j=j))
            elif cid in ids:
                errs.append(say(lang, "q_choice_dup", i=i, j=j, cid=cid))
            else:
                ids.append(cid)
            if not isinstance(c.get("label"), str) or not c["label"].strip():
                errs.append(say(lang, "q_choice_label", i=i, j=j))
            if c.get("effect") is not None and not isinstance(c["effect"], str):
                errs.append(say(lang, "q_choice_effect", i=i, j=j))
        n = len(listed)
        multiple = it.get("multiple")
        if multiple is not None and not isinstance(multiple, bool):
            errs.append(say(lang, "q_multiple_bool", i=i))
        mn, mx = it.get("min"), it.get("max")
        for k, v in (("min", mn), ("max", mx)):
            if v is not None and not _int(v):
                errs.append(say(lang, "q_int", i=i, k=k))
            elif v is not None and multiple is not True:
                errs.append(say(lang, "q_only_multiple", i=i, k=k))
        if multiple is True and n and (mn is None or _int(mn)) and (mx is None or _int(mx)):
            lo, hi = (1 if mn is None else mn), (n if mx is None else mx)
            if not 1 <= lo <= hi <= n:
                errs.append(say(lang, "q_range", i=i, count=n))
        rec = it.get("recommended")
        if rec is not None:
            if not isinstance(rec, list) or any(not isinstance(x, str) for x in rec):
                errs.append(say(lang, "q_rec_list", i=i))
            else:
                if any(x not in ids for x in rec):
                    errs.append(say(lang, "q_rec_unknown", i=i))
                if len(set(rec)) != len(rec):
                    errs.append(say(lang, "q_rec_repeat", i=i))
                limit = (mx if _int(mx) else n) if multiple is True else 1
                if len(rec) > limit:
                    errs.append(say(lang, "q_rec_limit", i=i, limit=limit))
                if rec and not (isinstance(it.get("why"), str) and it["why"].strip()):
                    errs.append(say(lang, "q_why_required", i=i))
        if it.get("why") is not None and not isinstance(it["why"], str):
            errs.append(say(lang, "q_why_str", i=i))
    fields = it.get("fields")
    fields = fields if isinstance(fields, list) else []
    if not any(isinstance(f, dict) and isinstance(f.get("text"), str) and f["text"].strip() for f in fields):
        errs.append(say(lang, "q_context", i=i))


def validate_labels(b, errs, lang=DEFAULT_LANG):
    """Optional batch-level `labels`: {"approve": {"text": "Apagar", "tone": "danger"}, ...}."""
    lb = b.get("labels")
    if lb is None:
        return
    if not isinstance(lb, dict):
        errs.append(say(lang, "labels_obj"))
        return
    for k, v in lb.items():
        if k not in LABEL_KEYS:
            errs.append(say(lang, "labels_key", k=k))
            continue
        if not isinstance(v, dict):
            errs.append(say(lang, "labels_entry", k=k))
            continue
        t = v.get("text")
        if not isinstance(t, str) or not t.strip() or len(t) > MAX_LABEL:
            errs.append(say(lang, "labels_text", k=k, max=MAX_LABEL))
        if v.get("tone") is not None and v["tone"] not in TONES:
            errs.append(say(lang, "labels_tone", k=k))


def validate(b, lang=DEFAULT_LANG):
    """Every problem of a batch, as messages in `lang` (empty when the batch is valid)."""
    errs = []
    if not isinstance(b, dict):
        return [say(lang, "root_obj")]
    for k in ("batch_id", "title"):
        if not isinstance(b.get(k), str) or not b[k].strip():
            errs.append(say(lang, "field_required", k=k))
    if "round" in b and (not isinstance(b["round"], int) or isinstance(b["round"], bool) or b["round"] < 1):
        errs.append(say(lang, "field_round"))
    validate_labels(b, errs, lang)
    lang_value = b.get("lang")  # null counts as omitted, like every optional key
    if lang_value is not None and (not isinstance(lang_value, str) or lang_value not in LANGS):
        errs.append(say(lang, "field_lang"))
    items = b.get("items")
    if not isinstance(items, list) or not items:
        return errs + [say(lang, "field_items")]
    seen = set()
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            errs.append(say(lang, "item_obj", i=i))
            continue
        iid = it.get("id")
        if not isinstance(iid, str) or not iid:
            errs.append(say(lang, "item_id", i=i))
        elif iid in seen:
            errs.append(say(lang, "item_dup", i=i, iid=iid))
        else:
            seen.add(iid)
        if not isinstance(it.get("title"), str) or not it["title"].strip():
            errs.append(say(lang, "item_title", i=i))
        for k in ("tag", "image"):
            if it.get(k) is not None and not isinstance(it[k], str):
                errs.append(say(lang, "item_str", i=i, k=k))
        if it.get("meta") is not None and not isinstance(it["meta"], dict):
            errs.append(say(lang, "item_meta", i=i))
        r = it.get("risk")
        if r is not None and (not isinstance(r, dict) or any(k in r and not isinstance(r[k], str) for k in ("level", "text"))):
            errs.append(say(lang, "item_risk", i=i))
        f = it.get("fields")
        if f is None:  # null conta como omitido, como nos outros campos opcionais
            f = []
        if not isinstance(f, list) or any(
            not isinstance(x, dict) or not isinstance(x.get("label"), str) or not isinstance(x.get("text"), str)
            for x in f
        ):
            errs.append(say(lang, "item_fields", i=i))
        cf = it.get("confirm")  # null counts as omitted
        if cf is not None:
            if not isinstance(cf, str) or not cf.strip():
                errs.append(say(lang, "item_confirm", i=i))
            elif is_question(it):
                errs.append(say(lang, "item_confirm_q", i=i))
        validate_question(i, it, errs, lang)
    return errs


def load_batch(d, flag=None):
    """The valid batch.json of `d`, or SystemExit with the reasons in the language of the run (`flag` is --lang)."""
    p = Path(d) / "batch.json"
    lang = resolve_lang(None, flag)
    if not p.exists():
        raise SystemExit(say(lang, "no_batch", path=p))
    try:
        b = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(say(lang, "bad_json", e=e))
    lang = resolve_lang(b, flag)
    errs = validate(b, lang)
    if errs:
        raise SystemExit(say(lang, "invalid") + "\n- " + "\n- ".join(errs))
    return b


```

`serve` reads the batch through the `Store`, so the store passes the flag on:

In `plugins/ar-board/skills/ar-board/scripts/ar_board.py`, replace:

```python
    def __init__(self, d):
        self.dir = Path(d).resolve()
        self.lock = threading.Lock()
        self.batch = load_batch(self.dir)
```

with:

```python
    def __init__(self, d, lang=None):
        self.dir = Path(d).resolve()
        self.lock = threading.Lock()
        self.batch = load_batch(self.dir, lang)
```

In `plugins/ar-board/skills/ar-board/scripts/ar_board.py`, replace everything from the line `def answer_text(answer):` up to (not including) the line `# ---------------------------------------------------------------- textos do painel` with:

```python
def answer_text(answer, lang=DEFAULT_LANG):
    k = answer["kind"]
    if k == "choice":
        return answer["label"]
    if k == "choices":
        parts = list(answer["labels"])
        if "other" in answer:
            parts.append(say(lang, "s_other", text=answer["other"]))
        return " + ".join(parts)
    if k == "other":
        return say(lang, "s_other", text=answer["text"])
    return answer["text"]


def render_summary(batch, state, as_json=False, lang=DEFAULT_LANG):
    """The decisions as JSON (no language in it) or as text in `lang`."""
    groups = {"approved": [], "rejected": [], "maybe": [], "pending": []}
    answered, unsure = [], []
    has_questions = any(is_question(it) for it in batch["items"])
    for it in batch["items"]:
        e = state.get("items", {}).get(it["id"], {})
        row = {"id": it["id"], "title": it["title"], "comment": e.get("comment", "")}
        if is_question(it):
            a = answer_of(it, e)
            if a is None:
                groups["pending"].append(row)
            elif a["kind"] == "unsure":
                unsure.append(row)
            else:
                if a["kind"] in ("other", "open"):
                    row["comment"] = ""  # the comment is the answer itself
                answered.append({**row, "answer": a, "recommended_taken": recommended_taken(it, a)})
            continue
        groups[e.get("decision", "pending")].append(row)
    if as_json:
        extra = {"answered": answered, "unsure": unsure} if has_questions else {}
        return json.dumps(
            {
                "batch_id": batch["batch_id"],
                "round": state.get("round"),
                "finished": state.get("finished", False),
                "batch_note": state.get("batch_note", ""),
                **{k: v for k, v in groups.items() if k != "pending"},
                **extra,
                "pending": groups["pending"],
            },
            ensure_ascii=False,
            indent=2,
        )
    lab = batch.get("labels") or {}
    names = [(k, (lab.get(lk) or {}).get("text") or say(lang, dflt)) for k, lk, dflt in
             (("approved", "approve", "s_approved"), ("rejected", "reject", "s_rejected"), ("maybe", "maybe", "s_maybe"))]
    out = [say(lang, "s_head", title=batch["title"], id=batch["batch_id"], round=state.get("round"))]
    out.append(say(lang, "s_finished", value=say(lang, "s_yes" if state.get("finished") else "s_partial")))

    def section(label, rows, fmt):
        out.append(f"\n## {label} ({len(rows)})")
        for r in rows:
            line = fmt(r)
            if r["comment"]:
                line += "\n    " + say(lang, "s_comment", comment=repr(r["comment"]))
            out.append(line)

    def plain(r):
        return f"- {r['id']} - {r['title']}"

    def with_answer(r):
        mark = " " + say(lang, "s_recommended") if r["recommended_taken"] else ""
        return f"- {r['id']} - {r['title']}\n    " + say(lang, "s_answer", answer=answer_text(r["answer"], lang)) + mark

    for key, label in names:
        section(label, groups[key], plain)
    if has_questions:
        section(say(lang, "s_answered"), answered, with_answer)
        section(say(lang, "s_unsure"), unsure, plain)
    section(say(lang, "s_pending"), groups["pending"], plain)
    if state.get("batch_note"):
        out.append(f"\n## {say(lang, 's_note')}\n{state['batch_note']}")
    return "\n".join(out)


```

The commands resolve their language once (`--lang`, then the batch, then the environment) and print through `say()`; a namespace built by hand without `lang` (the older tests) means "no flag". The help text is English in both languages: argparse prints its own words (`usage:`, `options:`, `invalid choice`) in English anyway.

In `plugins/ar-board/skills/ar-board/scripts/ar_board.py`, replace everything from the line `def cmd_serve(a):` up to (not including) the line `if __name__ == "__main__":` with:

```python
def cmd_serve(a):
    flag = getattr(a, "lang", None)
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", a.port), BaseHTTPRequestHandler)
    except OSError as e:
        raise SystemExit(say(resolve_lang(None, flag), "port", port=a.port, e=e))
    try:
        store = Store(a.dir, flag)
    except BaseException:
        srv.server_close()
        raise
    token = secrets.token_urlsafe(16)
    srv.RequestHandlerClass = make_handler(store, token, flag)
    if a.exit_on_finish:
        store.exit_cb = lambda: (time.sleep(0.6), srv.shutdown())
    signal.signal(signal.SIGTERM, lambda s, f: threading.Thread(target=srv.shutdown, daemon=True).start())
    url = f"http://127.0.0.1:{srv.server_address[1]}/?t={token}"
    info = store.dir / "server.json"
    write_private(info, json.dumps({"url": url, "pid": os.getpid(), "started_at": now()}))
    print(f"AR-BOARD URL: {url}", flush=True)  # the line tags are the same in both languages: agents look for them
    print(f"AR-BOARD DECISOES: {store.path}", flush=True)
    if a.open:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            info.unlink()
        except OSError:
            pass


def cmd_wait(a):
    batch = load_batch(a.dir, getattr(a, "lang", None))
    lang = resolve_lang(batch, getattr(a, "lang", None))
    end = time.time() + a.timeout if a.timeout else None
    while True:
        s = read_state(a.dir, batch)
        if s and s.get("finished"):
            print(render_summary(batch, s, lang=lang))
            return 0
        if end and time.time() > end:
            print(say(lang, "timeout"))
            return 2
        time.sleep(1)


def cmd_summary(a):
    batch = load_batch(a.dir, getattr(a, "lang", None))
    state = read_state(a.dir, batch) or {"round": round_of(batch), "items": {}}
    print(render_summary(batch, state, as_json=a.json, lang=resolve_lang(batch, getattr(a, "lang", None))))
    return 0


def cmd_build(a):
    batch = json.loads(json.dumps(load_batch(a.dir, getattr(a, "lang", None))))
    root = Path(a.dir).resolve()
    for it in batch["items"]:
        img = it.get("image")
        if img and not img.startswith("data:"):
            p = (root / img).resolve()
            if root in p.parents and p.suffix.lower() in IMG_EXT and p.is_file() and p.stat().st_size < 2_000_000:
                ctype = mimetypes.guess_type(p.name)[0] or "image/png"
                it["image"] = f"data:{ctype};base64," + base64.b64encode(p.read_bytes()).decode()
            else:
                it.pop("image")
    state = {"batch_id": batch["batch_id"], "round": int(batch.get("round", 1)), "items": {}, "batch_note": ""}
    out = root / "board.html"
    out.write_bytes(render_page(batch, state, "", False, getattr(a, "lang", None)))
    print(f"AR-BOARD ARQUIVO: {out}")
    return 0


def cmd_check(a):
    b = load_batch(a.dir, getattr(a, "lang", None))
    lang = resolve_lang(b, getattr(a, "lang", None))
    nq = sum(1 for it in b["items"] if is_question(it))
    if nq > MAX_QUESTIONS:
        print(say(lang, "many_questions", n=nq, max=MAX_QUESTIONS), file=sys.stderr)
    print(say(lang, "ok", n=len(b["items"]), id=b["batch_id"], round=b.get("round", 1)))
    return 0


def main():
    ap = argparse.ArgumentParser(prog="ar_board.py", description="ar-board: a local approve/reject panel (standard library only).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    lang_help = "language of the panel and of the messages (default: the batch's lang, then CAPYBARA_LANG, then en)"
    s = sub.add_parser("serve")
    s.add_argument("dir")
    s.add_argument("--port", type=int, default=0)
    s.add_argument("--open", action="store_true")
    s.add_argument("--exit-on-finish", action="store_true")
    s.add_argument("--lang", choices=LANGS, default=None, help=lang_help)
    s.set_defaults(fn=cmd_serve)
    w = sub.add_parser("wait")
    w.add_argument("dir")
    w.add_argument("--timeout", type=int, default=0)
    w.add_argument("--lang", choices=LANGS, default=None, help=lang_help)
    w.set_defaults(fn=cmd_wait)
    m = sub.add_parser("summary")
    m.add_argument("dir")
    m.add_argument("--json", action="store_true")
    m.add_argument("--lang", choices=LANGS, default=None, help=lang_help)
    m.set_defaults(fn=cmd_summary)
    b = sub.add_parser("build")
    b.add_argument("dir")
    b.add_argument("--lang", choices=LANGS, default=None, help=lang_help)
    b.set_defaults(fn=cmd_build)
    c = sub.add_parser("check")
    c.add_argument("dir")
    c.add_argument("--lang", choices=LANGS, default=None, help=lang_help)
    c.set_defaults(fn=cmd_check)
    a = ap.parse_args()
    sys.exit(a.fn(a) or 0)


```

- [ ] **Step 6: Regenerate the copies and run the suite**

Run: `python3 plugins/ar-board/tools/sync.py && python3 plugins/tidy-board/tools/sync.py && python3 plugins/housekeeping/tools/sync.py && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/ar-board/tests 2>&1 | grep -v '^AR-BOARD' | tail -n 3`

Expected: `updated:` lines for the two `dist/` variants, the question-board copy and the two `capy_board.py`, then `Ran 249 tests` and `OK` (17 new tests).

- [ ] **Step 7: Commit**

Run:

```bash
git add -A
git commit -m "feat(ar-board): the command line speaks English by default and pt-BR on request, --lang on every command" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

Expected: one commit (git status --short is empty afterwards).

### Task 3: Release ar-board 1.4.0 and regenerate the vendored copies

**Files:**
- Modify: `plugins/ar-board/skills/ar-board/scripts/ar_board.py` (header comment and `VERSION`), `plugins/ar-board/CHANGELOG.md`
- Generated (by the sync tools): `plugins/ar-board/.claude-plugin/plugin.json`, `plugins/ar-board/dist/*.SKILL.md`, `plugins/ar-board/skills/question-board/scripts/ar_board.py`, `plugins/tidy-board/skills/tidy-board/scripts/capy_board.py`, `plugins/housekeeping/skills/todo-sweep/scripts/capy_board.py`, `.claude-plugin/marketplace.json`

**Interfaces:**
- Produces: ar-board 1.4.0 everywhere the version appears, carrying the page (Tasks 1 and 2) and the command line (Task 2b); the engine that Tasks 4 and 5 vendor (their `check` must accept `lang`).

- [ ] **Step 1: Bump the version and write the changelog entry**

`DAY` is the day of execution (`date +%Y-%m-%d`).

In `plugins/ar-board/skills/ar-board/scripts/ar_board.py`, replace:

```python
# ar-board 1.3.1 - painel local de aprovar/rejeitar e formulario de perguntas (somente stdlib, sem rede externa)
```

with:

```python
# ar-board 1.4.0 - painel local de aprovar/rejeitar e formulario de perguntas (somente stdlib, sem rede externa)
```

In `plugins/ar-board/skills/ar-board/scripts/ar_board.py`, replace:

```python
VERSION = "1.3.1"
```

with:

```python
VERSION = "1.4.0"
```

In `plugins/ar-board/CHANGELOG.md`, replace:

```markdown
## [Unreleased]

## [1.3.1] - 2026-10-15
```

with:

```markdown
## [Unreleased]

## [1.4.0] - DAY

### Added
- The panel speaks **English by default and pt-BR on demand**. Every user-visible string of the page (key bar, buttons, hints, dialogs, review screen, counters, completion banner) comes from an `I18N` table shipped inside the page through the boot data, so the Content-Security-Policy is unchanged and the offline `build` page switches too.
- Optional top-level **`lang`** in `batch.json` (`"en"` or `"pt-BR"`); `check` rejects any other value. A batch without `lang` opens in English.
- **`--lang en|pt-BR`** on `serve` and `build`: overrides the batch's `lang` for the language the page opens in.
- An **EN/PT toggle** in the header, next to the live/offline badge. It switches the chrome at once, sets `<html lang>` and is remembered in the browser (`localStorage` key `ar-board:lang`). Precedence: the saved toggle, then `--lang`, then the batch's `lang`, then `CAPYBARA_LANG`, then English. A saved value that is not one of the two is ignored.
- Risk levels `low`, `medium` and `high` are coloured like `baixo`, `medio` and `alto` (accents and case still ignored); the CSS classes do not change.
- **`--lang en|pt-BR` on every command** (`serve`, `wait`, `summary`, `build`, `check`) for the command-line messages, and the environment variable **`CAPYBARA_LANG`** (`en` or `pt-BR`) as the default when neither the flag nor the batch decides (any other value is ignored).

### Changed
- **The command line speaks English by default**: `check`, the validation errors, `summary` (text), `wait` and the other messages follow `--lang`, then the batch's `lang`, then `CAPYBARA_LANG`. The pt-BR text is the accent-free Portuguese of 1.3.1, except that a count of one now takes the singular (`ok: 1 item, ...`). The line tags `AR-BOARD URL:`, `AR-BOARD DECISOES:`, `AR-BOARD ARQUIVO:`, `TIMEOUT:` and `ok:` are the same in both languages; the JSON `summary` and the HTTP error bodies do not change. The `--help` text is English.
- The pt-BR wording of the panel is now written with accents (the page is UTF-8).
- Batch-level `labels` and per-item `confirm` are card content: they are shown as written and do not follow the toggle. The key letters (`A`, `R`, `M`, `S`, `C`) are the same in both languages.
- `decisions.json` and the offline `AR-BOARD-RESULT` export have the same shape as before; nothing about the language is stored in them.

## [1.3.1] - 2026-10-15
```

- [ ] **Step 2: Sync everything and check**

Run: `python3 plugins/ar-board/tools/sync.py && python3 plugins/tidy-board/tools/sync.py && python3 plugins/housekeeping/tools/sync.py && python3 tools/marketplace.py && python3 plugins/ar-board/tools/sync.py --check && python3 plugins/tidy-board/tools/sync.py --check && python3 plugins/housekeeping/tools/sync.py --check && python3 tools/marketplace.py --check && echo all-in-sync`

Expected: `updated:` lines for `.claude-plugin/plugin.json`, the two `dist/` variants, the question-board copy, the two `capy_board.py` and `.claude-plugin/marketplace.json`, then `all-in-sync`.

Run: `grep -c '"version": "1.4.0"' plugins/ar-board/.claude-plugin/plugin.json .claude-plugin/marketplace.json && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/ar-board/tests 2>&1 | grep -v '^AR-BOARD' | tail -n 3 && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests 2>&1 | tail -n 1`

Expected: `plugins/ar-board/.claude-plugin/plugin.json:1`, `.claude-plugin/marketplace.json:1`, `Ran 249 tests` and `OK` twice (ar-board and the catalog).

- [ ] **Step 3: Commit**

Run:

```bash
git add -A
git commit -m "chore(ar-board): release 1.4.0 and regenerate the vendored engine copies" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

Expected: one commit (git status --short is empty afterwards).

### Task 4: tidy-board: cards in a language, `scan --lang`

**Files:**
- Modify: `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py` (the table replaces `PROOF_TEXT`; `pr_note`/`remote_note` become `pr_info`/`remote_state`; `inventory` stores codes; the cards section is replaced; `scan_problems`, `cmd_scan`, `parser`)
- Modify: `plugins/tidy-board/tests/test_inventory.py`, `test_scan.py`, `test_apply.py`, `test_skill.py`; `plugins/tidy-board/skills/tidy-board/examples/batch.example.json`, `scan.example.json`
- The release (header, `VERSION`, `CHANGELOG.md`, `test_package.py`, the manifests) moved to the end of Task 4b, so 0.2.0 ships the cards and the command line together.

**Interfaces:**
- Consumes: the engine's `validate` with `lang` (Task 3, through `capy_board.py`).
- Produces: `LANGS`, `DEFAULT_LANG`, `TEXT` (two dicts, same keys), `LABELS[lang]`, `WHY_CODES`, `check_lang(lang)` (raises `TidyError`), `t(lang, key, **values)`, `pr_info(prs, name, sha)`, `remote_state(root, name, gone)`, `reason_text(u, lang)`, `pr_text(it, lang)`, `remote_text(it, lang)`, `age_text(ts, now, lang)`, `confirm_text(it, lang)`, `card_for(it, iid, now, lang)`, `build_scan(root, inv, now=None, stamp=None, lang=DEFAULT_LANG)` writing `lang` into `batch.json` and `scan.json`, `scan --lang {en,pt-BR}` (default `en`), `scan_problems` refusing a bad `lang` in `scan.json`. `apply` and `restore` are unchanged.

- [ ] **Step 1: Record the baseline and update the tests that pin the old text**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/tidy-board/tests 2>&1 | tail -n 3`

Expected: `Ran 133 tests` and `OK` (about two minutes).

The inventory tests now pin codes, the scan tests pin the English default, the skill test compares the example's labels with the table of its language:

In `plugins/tidy-board/tests/test_inventory.py`, replace:

```python
        self.assertIn("#7 mergeado (a ponta confere)", item["pr"])
```

with:

```python
        self.assertEqual(item["pr"], {"number": 7, "tip_matches": True})
```

In `plugins/tidy-board/tests/test_inventory.py`, replace:

```python
        self.assertIn("DIFERENTE", item["pr"])
```

with:

```python
        self.assertEqual(item["pr"], {"number": 8, "tip_matches": False})
```

In `plugins/tidy-board/tests/test_inventory.py`, replace:

```python
        self.assertEqual(self.by_name(inv)["feat/r"]["pr"], "")
```

with:

```python
        self.assertIsNone(self.by_name(inv)["feat/r"]["pr"])
```

In `plugins/tidy-board/tests/test_inventory.py`, replace:

```python
        self.assertIn("ja foi removida", item["remote"])
```

with:

```python
        self.assertEqual(item["remote"], "removed")
```

In `plugins/tidy-board/tests/test_inventory.py`, replace:

```python
        self.assertIn("ainda existe (nao sera tocada)", {i["name"]: i for i in inv["items"]}["feat/h"]["remote"])
```

with:

```python
        self.assertEqual({i["name"]: i for i in inv["items"]}["feat/h"]["remote"], "exists")
```

In `plugins/tidy-board/tests/test_inventory.py`, replace:

```python
        self.assertEqual(why["main"], "branch base do repositorio")
        self.assertIn("branch atual", why["feat/cur"])
```

with:

```python
        self.assertEqual(why["main"], "base_branch")
        self.assertEqual(why["feat/cur"], "current_branch")
```

In `plugins/tidy-board/tests/test_inventory.py`, replace:

```python
        self.assertTrue(all("alterado(s) ou nao rastreado(s)" in r for r in reasons))
```

with:

```python
        self.assertEqual(reasons, ["dirty", "dirty"])
```

In `plugins/tidy-board/tests/test_inventory.py`, replace:

```python
        self.assertTrue(any("bloqueado" in u["why"] for u in inv["untouched"]))
```

with:

```python
        self.assertTrue(any(u["why"] == "locked" for u in inv["untouched"]))
```

In `plugins/tidy-board/tests/test_skill.py`, replace:

```python
        self.assertEqual(self.batch["labels"], tb.LABELS)
```

with:

```python
        self.assertEqual(self.batch["labels"], tb.LABELS[self.batch["lang"]])
        self.assertEqual(self.scan["lang"], self.batch["lang"])
```

In `plugins/tidy-board/tests/test_scan.py`, replace:

```python
        self.assertIn("2 itens", batch["items"][0]["title"])
```

with:

```python
        self.assertIn("2 items", batch["items"][0]["title"])
```

In `plugins/tidy-board/tests/test_scan.py`, replace:

```python
        self.assertEqual(batch["labels"]["approve"], {"text": "Apagar", "tone": "danger"})
        self.assertEqual(batch["labels"]["reject"], {"text": "Manter", "tone": "safe"})
        self.assertEqual(batch["labels"]["maybe"], {"text": "Depois", "tone": "caution"})
```

with:

```python
        self.assertEqual(batch["labels"]["approve"], {"text": "Delete", "tone": "danger"})
        self.assertEqual(batch["labels"]["reject"], {"text": "Keep", "tone": "safe"})
        self.assertEqual(batch["labels"]["maybe"], {"text": "Later", "tone": "caution"})
        batch, _ = self.build(lang="pt-BR")
        self.assertEqual(batch["labels"]["approve"], {"text": "Apagar", "tone": "danger"})
        self.assertEqual(batch["labels"]["reject"], {"text": "Manter", "tone": "safe"})
        self.assertEqual(batch["labels"]["maybe"], {"text": "Depois", "tone": "caution"})
```

In `plugins/tidy-board/tests/test_scan.py`, replace:

```python
        field = [f for f in first["fields"] if f["label"] == "Nao tocar"][0]["text"]
        self.assertIn("`main`: branch base do repositorio", field)
```

with:

```python
        field = [f for f in first["fields"] if f["label"] == "Do not touch"][0]["text"]
        self.assertIn("`main`: base branch of the repository", field)
```

In `plugins/tidy-board/tests/test_scan.py`, replace:

```python
        self.assertEqual(first["meta"], {"Base": "main", "gh": "nao (so git local)"})
```

with:

```python
        self.assertEqual(first["meta"], {"Base": "main", "gh": "no (git only)"})
```

In `plugins/tidy-board/tests/test_scan.py`, replace:

```python
        card = [c for c in batch["items"] if c["title"].startswith("Remover o worktree")][0]
        self.assertEqual(card["title"], "Remover o worktree wtc?")
```

with:

```python
        card = [c for c in batch["items"] if c["title"].startswith("Remove the worktree")][0]
        self.assertEqual(card["title"], "Remove the worktree wtc?")
```

In `plugins/tidy-board/tests/test_scan.py`, replace:

```python
        self.assertIn("NAO TOCAR: main (branch base do repositorio)", stdout)
```

with:

```python
        self.assertIn("NAO TOCAR: main (branch base do repositório)", stdout)
        self.assertIn("; idioma en", stdout)
```

- [ ] **Step 2: Write the failing tests for both languages**

The new tests cover the table parity, the renderers, the English default against the old pt-BR wording with accents, the same board shape in both languages, `check` on an older scan without `lang`, the command line, and `apply`/`restore` on a pt-BR board.

Append to `plugins/tidy-board/tests/test_scan.py` (after a blank line):

```python
# ---------------------------------------------------------------- the cards' language (tidy-board 0.2.0)

import re as _re

PLACEHOLDER = _re.compile(r"\{(\w+)\}")


class LanguageTableTest(unittest.TestCase):
    def test_both_tables_have_the_same_keys_and_placeholders(self):
        self.assertEqual(tb.LANGS, ("en", "pt-BR"))
        self.assertEqual(tb.DEFAULT_LANG, "en")
        en, pt = tb.TEXT["en"], tb.TEXT["pt-BR"]
        self.assertEqual(set(en), set(pt))
        for key in en:
            with self.subTest(key=key):
                self.assertEqual(set(PLACEHOLDER.findall(en[key])), set(PLACEHOLDER.findall(pt[key])))
        self.assertEqual(set(tb.LABELS), set(tb.LANGS))
        for code in tb.WHY_CODES:
            self.assertIn("why_" + code, en)
        for proof in tb.PROOFS:
            self.assertIn("proof_" + proof, en)

    def test_the_portuguese_table_has_accents(self):
        text = " ".join(tb.TEXT["pt-BR"].values())
        for word in ("repositório", "único", "Não tocar", "à frente"):
            self.assertIn(word, text)

    def test_reasons_pr_remote_and_age_render_in_both_languages(self):
        self.assertEqual(tb.reason_text({"name": "x", "why": "base_branch"}, "en"), "base branch of the repository")
        self.assertEqual(tb.reason_text({"name": "x", "why": "dirty", "count": 3}, "pt-BR"),
                         "3 arquivo(s) alterado(s) ou não rastreado(s): apagar perderia trabalho sem sha para recuperar")
        self.assertEqual(tb.reason_text({"name": "x", "why": "main_worktree", "path": "/w`t"}, "en"), "in use by the main worktree (/w't)")
        self.assertEqual(tb.pr_text({"pr": None}, "en"), "")
        self.assertEqual(tb.pr_text({"pr": {}}, "pt-BR"), "sem PR mergeado")
        self.assertEqual(tb.pr_text({"pr": {"number": 7, "tip_matches": True}}, "en"), "#7 merged (the tip matches)")
        self.assertEqual(tb.pr_text({"pr": {"number": 7, "tip_matches": False}}, "pt-BR"), "#7 mergeado (a ponta é DIFERENTE da do PR)")
        self.assertEqual(tb.remote_text({"remote": None, "name": "x"}, "en"), "")
        self.assertEqual(tb.remote_text({"remote": "exists", "name": "feat/x"}, "en"), "origin/feat/x still exists (it will not be touched)")
        self.assertEqual(tb.remote_text({"remote": "removed", "name": "w", "branch": "feat/y"}, "pt-BR"), "origin/feat/y já foi removida")
        now = 1_800_000_000
        self.assertEqual([tb.age_text(now - d * 86400, now, "en") for d in (0, 1, 2)], ["today", "1 day ago", "2 days ago"])
        self.assertEqual([tb.age_text(now - d * 86400, now, "pt-BR") for d in (0, 1, 2)], ["hoje", "há 1 dia", "há 2 dias"])

    def test_an_unknown_language_is_refused_by_the_builder(self):
        with self.assertRaises(tb.TidyError) as ctx:
            tb.check_lang("xx")
        self.assertIn("idioma invalido", str(ctx.exception))


class LanguageBoardTest(BoardRepo):
    def test_english_is_the_default_and_pt_br_is_the_old_wording_with_accents(self):
        batch, scan = self.build()
        self.assertEqual((batch["lang"], scan["lang"]), ("en", "en"))
        titles = [c["title"] for c in batch["items"]]
        self.assertIn("Delete the branch feat/a?", titles)
        self.assertTrue(any(title.startswith("Discard the stash ") for title in titles), titles)
        self.assertEqual(batch["title"], "Cleanup of r")
        self.assertEqual(batch["subtitle"], "base: main - gh: no - 5 items")
        self.assertEqual(batch["items"][0]["tag"], "group P1/P2")
        batch, scan = self.build(lang="pt-BR")
        self.assertEqual((batch["lang"], scan["lang"]), ("pt-BR", "pt-BR"))
        titles = [c["title"] for c in batch["items"]]
        self.assertIn("Apagar a branch feat/a?", titles)
        self.assertEqual(batch["title"], "Limpeza de r")
        self.assertEqual(batch["subtitle"], "base: main - gh: não - 5 itens")
        self.assertEqual(batch["items"][0]["title"], "Apagar os 2 itens provados como mergeados?")
        field = [f for f in batch["items"][0]["fields"] if f["label"] == "Não tocar"][0]["text"]
        self.assertIn("`main`: branch base do repositório", field)
        self.assertIn("Vale para os itens abaixo em que você não marcar Manter ou Depois.", [f["text"] for f in batch["items"][0]["fields"]][1])
        self.assertEqual(batch["items"][0]["meta"], {"Base": "main", "gh": "não (só git local)"})

    def test_both_languages_build_the_same_board_shape(self):
        en, en_scan = self.build()
        pt, pt_scan = self.build(lang="pt-BR")
        self.assertEqual([c["id"] for c in en["items"]], [c["id"] for c in pt["items"]])
        for a, b in zip(en["items"], pt["items"]):
            with self.subTest(card=a["id"]):
                self.assertEqual(len(a["fields"]), len(b["fields"]))
                self.assertEqual("confirm" in a, "confirm" in b)
                self.assertEqual(a.get("meta", {}).keys(), b.get("meta", {}).keys())
        self.assertEqual({k: v for k, v in en_scan.items() if k not in ("lang", "untouched")},
                         {k: v for k, v in pt_scan.items() if k not in ("lang", "untouched")})
        self.assertEqual(capy.validate(pt), [])
        self.assertEqual(tb.scan_problems(pt, pt_scan), [])

    def test_a_scan_in_either_language_passes_check_and_the_older_shape_without_lang_still_does(self):
        batch, scan = self.build(lang="pt-BR")
        self.assertEqual(tb.scan_problems(batch, scan), [])
        del scan["lang"]
        self.assertEqual(tb.scan_problems(batch, scan), [])
        scan["lang"] = "xx"
        self.assertTrue(any("'lang' deve ser en ou pt-BR" in e for e in tb.scan_problems(batch, scan)))
        scan["lang"] = None  # null counts as omitted
        self.assertEqual(tb.scan_problems(batch, scan), [])


class LanguageCliTest(BoardRepo):
    def test_scan_lang_reaches_both_files_and_the_command_line_stays_portuguese(self):
        out = self.tmp / "board"
        rc, stdout, _ = run_cli("scan", str(self.repo), "--gh", "off", "--out", str(out), "--lang", "pt-BR")
        self.assertEqual(rc, 0, stdout)
        batch = json.loads((out / "batch.json").read_text(encoding="utf-8"))
        scan = json.loads((out / "scan.json").read_text(encoding="utf-8"))
        self.assertEqual((batch["lang"], scan["lang"]), ("pt-BR", "pt-BR"))
        self.assertEqual(batch["labels"]["approve"]["text"], "Apagar")
        self.assertEqual(capy.validate(batch), [])
        self.assertIn("NAO TOCAR: main (branch base do repositório)", stdout)
        self.assertIn("; idioma pt-BR", stdout)
        self.assertEqual(run_cli("check", str(out))[0], 0)

    def test_an_unknown_lang_is_refused_before_anything_is_written(self):
        out = self.tmp / "board"
        with self.assertRaises(SystemExit) as ctx:
            run_cli("scan", str(self.repo), "--gh", "off", "--out", str(out), "--lang", "xx")
        self.assertEqual(ctx.exception.code, 2)
        self.assertFalse(out.exists())
        self.assertFalse((self.repo / ".tidy-board").exists())

    def test_check_rejects_a_bad_lang_edited_into_scan_json(self):
        out = self.tmp / "board"
        run_cli("scan", str(self.repo), "--gh", "off", "--out", str(out))
        scan = json.loads((out / "scan.json").read_text(encoding="utf-8"))
        scan["lang"] = "xx"
        (out / "scan.json").write_text(json.dumps(scan), encoding="utf-8")
        rc, _, err = run_cli("check", str(out))
        self.assertEqual(rc, 1)
        self.assertIn("'lang' deve ser en ou pt-BR", err)
```

Append to `plugins/tidy-board/tests/test_apply.py` (after a blank line):

```python
class LanguageApplyTest(RepoCase):
    """The cards' language changes nothing below the panel: apply and restore read ids, shas and proofs."""

    def board_in(self, lang):
        self.work("feat/m", {"m.txt": "m\n"})
        git(self.repo, "merge", "-q", "--no-ff", "-m", "merge feat/m", "feat/m")
        self.work("spike/u", {"u.txt": "u\n"}, message="wip: u")
        board = self.tmp / ("board-" + lang)
        rc, out, _ = run_cli("scan", str(self.repo), "--gh", "off", "--out", str(board), "--lang", lang)
        assert rc == 0, out
        scan = json.loads((board / "scan.json").read_text(encoding="utf-8"))
        batch = json.loads((board / "batch.json").read_text(encoding="utf-8"))
        ids = {e["name"]: e["id"] for e in scan["items"]}
        items = {ids["feat/m"]: {"decision": "approved"}, ids["spike/u"]: {"decision": "approved"}}
        state = {"batch_id": batch["batch_id"], "round": 1, "finished": True, "batch_note": "", "items": items}
        (board / "decisions.json").write_text(json.dumps(state), encoding="utf-8")
        return board, ids

    def test_a_pt_br_board_is_applied_and_restored_exactly_like_an_english_one(self):
        board, ids = self.board_in("pt-BR")
        rc, out, _ = run_cli("apply", str(board))
        self.assertEqual(rc, 0, out)
        self.assertIn("APPLY: 2 apagados, 0 pulados", out)
        applied = json.loads((board / "applied.json").read_text(encoding="utf-8"))
        self.assertEqual({e["action"] for e in applied}, {"deleted"})
        self.assertEqual(set(applied[0]), {"id", "kind", "name", "sha", "proof", "action", "at"})  # no language anywhere
        self.assertNotIn("lang", json.dumps(applied))
        branches = set(git(self.repo, "for-each-ref", "--format=%(refname:short)", "refs/heads").split())
        self.assertNotIn("feat/m", branches)
        self.assertNotIn("spike/u", branches)
        rc, out, _ = run_cli("restore", str(board), ids["spike/u"])
        self.assertEqual(rc, 0, out)
        self.assertIn("RESTORE: branch spike/u recriada", out)
        rc, _, err = run_cli("restore", str(board), ids["feat/m"])
        self.assertEqual(rc, 2)
        self.assertIn("nao tem backup", err)
```

- [ ] **Step 3: Run the new tests to see them fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/tidy-board/tests -k Language 2>&1 | tail -n 3`

Expected: `FAILED (`: tb.LANGS, tb.TEXT, tb.LABELS[lang] and build_scan(..., lang=...) do not exist yet.

- [ ] **Step 4: The table, the codes and the cards**

`PROOF_TEXT` is replaced by the languages, the table, the labels, `check_lang` and `t()`:

In `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py`, replace everything from the line `PROOF_TEXT = {` up to and including the next line that is exactly `}` with:

```python
LANGS = ("en", "pt-BR")  # languages of the cards (`scan --lang`); the first is the default
DEFAULT_LANG = "en"

# Every card text, in both languages. The inventory never holds text: it holds codes (proof levels, reason
# codes, PR and remote states) and `t()` renders them. The two tables have the same keys and placeholders.
TEXT = {
    "en": {
        "proof_P1": "proven: ancestor of the base", "proof_P2": "proven: merged PR on GitHub",
        "proof_P3": "probable: the same patch is already in the base", "proof_P4": "unique work: exists only here",
        "why_base_branch": "base branch of the repository", "why_current_branch": "current branch (in use by this worktree)",
        "why_main_worktree": "in use by the main worktree ({path})", "why_current_worktree": "current worktree",
        "why_locked": "locked worktree", "why_missing_dir": "folder missing (git worktree prune fixes it)",
        "why_unreadable": "could not read the state of the worktree",
        "why_dirty": "{n} changed or untracked file(s): deleting would lose work with no sha to recover",
        "pr_none": "no merged PR", "pr_merged": "#{n} merged (the tip matches)", "pr_differs": "#{n} merged (the tip is DIFFERENT from the PR's)",
        "remote_exists": "origin/{name} still exists (it will not be touched)", "remote_removed": "origin/{name} was already removed",
        "remote_none": "no counterpart",
        "age_today": "today", "age_day": "{n} day ago", "age_days": "{n} days ago",
        "confirm_stash": "Unique work: this stash exists nowhere else. A backup will be created before discarding.",
        "confirm_ignored": "This worktree has files ignored by git (e.g. {shown}) that will be deleted with it and have no backup.",
        "confirm_wt_branch": "The branch of this worktree has work that exists only there: it stays. Only the worktree folder is removed.",
        "confirm_wt_detached": "This worktree has no branch and its commits exist only here. A backup will be created before removing.",
        "confirm_p3": "Heuristic: the same patch seems to be in the base, but that is not proof. A backup will be created before deleting.",
        "confirm_p4": "Unique work: these commits do not exist on any other branch, remote or tag. A backup will be created before deleting.",
        "f_proof": "Proof", "f_worktree": "Worktree", "f_branch": "Branch", "f_ignored": "Ignored", "f_last": "Last",
        "f_content": "Content", "f_vs_base": "Vs base", "f_pr": "PR", "f_remote": "Remote", "f_files": "Files",
        "f_only_here": "Only here", "f_effect": "Effect", "f_items": "Items", "f_rule": "Rule", "f_untouched": "Do not touch",
        "wt_text": "`{path}` ({size}, clean)", "branch_goes": " (goes too)", "branch_stays": " (stays)",
        "no_branch": "none (detached HEAD)", "ignored_note": "(deleted with the folder, no backup)", "empty": "empty",
        "vs_base": "{ahead} ahead, {behind} behind",
        "effect_branch": "Deletes the local branch.", "effect_worktree": "Removes the worktree folder.",
        "effect_worktree_branch": "Removes the worktree folder and the branch.", "effect_stash": "Discards the stash.",
        "effect_backup": " First, it saves `{ref}`.",
        "verb_branch": "Delete the branch", "verb_worktree": "Remove the worktree", "verb_stash": "Discard the stash",
        "group_tag": "group P1/P2", "group_title": "Delete the {n} items proven as merged?",
        "group_rule": "Applies to the items below that you do not mark {keep} or {later}. It does not include P3, P4 or stashes.",
        "gh_yes": "yes", "gh_no": "no (git only)", "gh_short_yes": "yes", "gh_short_no": "no",
        "batch_title": "Cleanup of {repo}", "subtitle": "base: {base} - gh: {gh} - {n} items",
    },
    "pt-BR": {
        "proof_P1": "provado: ancestral da base", "proof_P2": "provado: PR mergeado no GitHub",
        "proof_P3": "provável: o mesmo patch já está na base", "proof_P4": "trabalho único: existe só aqui",
        "why_base_branch": "branch base do repositório", "why_current_branch": "branch atual (em uso por este worktree)",
        "why_main_worktree": "em uso pelo worktree principal ({path})", "why_current_worktree": "worktree atual",
        "why_locked": "worktree bloqueado (locked)", "why_missing_dir": "diretório ausente (git worktree prune resolve)",
        "why_unreadable": "não consegui ler o estado do worktree",
        "why_dirty": "{n} arquivo(s) alterado(s) ou não rastreado(s): apagar perderia trabalho sem sha para recuperar",
        "pr_none": "sem PR mergeado", "pr_merged": "#{n} mergeado (a ponta confere)", "pr_differs": "#{n} mergeado (a ponta é DIFERENTE da do PR)",
        "remote_exists": "origin/{name} ainda existe (não será tocada)", "remote_removed": "origin/{name} já foi removida",
        "remote_none": "sem contraparte",
        "age_today": "hoje", "age_day": "há {n} dia", "age_days": "há {n} dias",
        "confirm_stash": "Trabalho único: este stash não existe em outro lugar. Um backup será criado antes de descartar.",
        "confirm_ignored": "Este worktree tem arquivos ignorados pelo git (ex.: {shown}) que serão apagados junto e não têm backup.",
        "confirm_wt_branch": "A branch deste worktree tem trabalho que só existe nela: ela fica. Remove só a pasta do worktree.",
        "confirm_wt_detached": "Este worktree está sem branch e seus commits só existem aqui. Um backup será criado antes de remover.",
        "confirm_p3": "Heurística: o mesmo patch parece estar na base, mas isso não é prova. Um backup será criado antes de apagar.",
        "confirm_p4": "Trabalho único: estes commits não existem em nenhuma outra branch, remoto ou tag. Um backup será criado antes de apagar.",
        "f_proof": "Prova", "f_worktree": "Worktree", "f_branch": "Branch", "f_ignored": "Ignorados", "f_last": "Último",
        "f_content": "Conteúdo", "f_vs_base": "Vs base", "f_pr": "PR", "f_remote": "Remoto", "f_files": "Arquivos",
        "f_only_here": "Só aqui", "f_effect": "Efeito", "f_items": "Itens", "f_rule": "Regra", "f_untouched": "Não tocar",
        "wt_text": "`{path}` ({size}, limpo)", "branch_goes": " (sai junto)", "branch_stays": " (fica)",
        "no_branch": "nenhuma (HEAD solto)", "ignored_note": "(apagados junto com a pasta, sem backup)", "empty": "vazio",
        "vs_base": "{ahead} à frente, {behind} atrás",
        "effect_branch": "Apaga a branch local.", "effect_worktree": "Remove a pasta do worktree.",
        "effect_worktree_branch": "Remove a pasta do worktree e a branch.", "effect_stash": "Descarta o stash.",
        "effect_backup": " Antes, guarda `{ref}`.",
        "verb_branch": "Apagar a branch", "verb_worktree": "Remover o worktree", "verb_stash": "Descartar o stash",
        "group_tag": "grupo P1/P2", "group_title": "Apagar os {n} itens provados como mergeados?",
        "group_rule": "Vale para os itens abaixo em que você não marcar {keep} ou {later}. Não inclui P3, P4 nem stashes.",
        "gh_yes": "sim", "gh_no": "não (só git local)", "gh_short_yes": "sim", "gh_short_no": "não",
        "batch_title": "Limpeza de {repo}", "subtitle": "base: {base} - gh: {gh} - {n} itens",
    },
}
LABELS = {  # the board's own wording per language; "approve" deletes, so it is painted as the dangerous action
    "en": {"approve": {"text": "Delete", "tone": "danger"}, "reject": {"text": "Keep", "tone": "safe"},
           "maybe": {"text": "Later", "tone": "caution"}},
    "pt-BR": {"approve": {"text": "Apagar", "tone": "danger"}, "reject": {"text": "Manter", "tone": "safe"},
              "maybe": {"text": "Depois", "tone": "caution"}},
}


def check_lang(lang):
    """A language is one of LANGS; anything else (a typo, a value edited into a file) is the person's error."""
    if lang not in LANGS:
        raise TidyError(f"idioma invalido: {lang!r} (use en ou pt-BR)")
    return lang


def t(lang, key, **values):
    """One card text in `lang`. The template is ours; the values are data, substituted and never parsed."""
    return TEXT[lang][key].format(**values)
```

`pr_note` and `remote_note` return codes now (the text is rendered when the cards are built):

In `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py`, replace everything from the line `def pr_note(prs, name, sha):` up to (not including) the line `# ---------------------------------------------------------------- inventory` with:

```python
def pr_info(prs, name, sha):
    """None when gh was off or unusable; {} when gh knows no merged PR for the branch; else the first PR's number
    and whether its head is the branch tip. Text comes later, from the table (`pr_text`)."""
    if prs is None:
        return None
    found = prs.get(name or "", [])
    if not found:
        return {}
    return {"number": found[0]["number"], "tip_matches": found[0]["oid"] == sha}


def remote_state(root, name, gone):
    """'exists', 'removed' or 'none': the state of origin/<name>, rendered by `remote_text`."""
    if rev(root, "refs/remotes/origin/" + name):
        return "exists"
    return "removed" if gone else "none"
```

`inventory` stores the reason codes and the new `pr`/`remote` values:

In `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py`, replace:

```python
            untouched.append({"name": name, "why": "branch base do repositorio"})
```

with:

```python
            untouched.append({"name": name, "why": "base_branch"})
```

In `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py`, replace:

```python
                untouched.append({"name": name, "why": "branch atual (em uso por este worktree)"})
```

with:

```python
                untouched.append({"name": name, "why": "current_branch"})
```

In `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py`, replace:

```python
                untouched.append({"name": name, "why": f"em uso pelo worktree principal ({wt})"})
```

with:

```python
                untouched.append({"name": name, "why": "main_worktree", "path": wt})
```

In `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py`, replace:

```python
                      "unique": lines, "unique_count": count, "pr": pr_note(prs, name, b["sha"]),
                      "remote": remote_note(root, name, b["gone"]), "backup": proof in RISKY_PROOFS})
```

with:

```python
                      "unique": lines, "unique_count": count, "pr": pr_info(prs, name, b["sha"]),
                      "remote": remote_state(root, name, b["gone"]), "backup": proof in RISKY_PROOFS})
```

In `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py`, replace:

```python
            untouched.append({"name": path, "why": "worktree atual"})
```

with:

```python
            untouched.append({"name": path, "why": "current_worktree"})
```

In `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py`, replace:

```python
            untouched.append({"name": path, "why": "worktree bloqueado (locked)"})
```

with:

```python
            untouched.append({"name": path, "why": "locked"})
```

In `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py`, replace:

```python
            untouched.append({"name": path, "why": "diretorio ausente (git worktree prune resolve)"})
```

with:

```python
            untouched.append({"name": path, "why": "missing_dir"})
```

In `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py`, replace:

```python
            untouched.append({"name": path, "why": "nao consegui ler o estado do worktree"})
```

with:

```python
            untouched.append({"name": path, "why": "unreadable"})
```

In `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py`, replace:

```python
            untouched.append({"name": path, "why": f"{len(dirty)} arquivo(s) alterado(s) ou nao rastreado(s): apagar perderia trabalho sem sha para recuperar"})
```

with:

```python
            untouched.append({"name": path, "why": "dirty", "count": len(dirty)})
```

In `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py`, replace:

```python
                      "pr": pr_note(prs, branch, sha), "remote": remote_note(root, branch, False) if branch else "",
```

with:

```python
                      "pr": pr_info(prs, branch, sha) if branch else None, "remote": remote_state(root, branch, False) if branch else None,
```

The whole cards section (from `WARN_CARDS` to the end of `build_scan`) is replaced; every text goes through `t()`, `build_scan` takes `lang`, validates it, and writes it into both files:

In `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py`, replace everything from the line `WARN_CARDS = 40  # `check` warns above this many cards: a long board is a tiring one` up to (not including) the line `def write_private(path, text):` with:

```python
WARN_CARDS = 40  # `check` warns above this many cards: a long board is a tiring one
SHA = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
KINDS = ("branch", "worktree", "stash")
WHY_CODES = ("base_branch", "current_branch", "main_worktree", "current_worktree", "locked", "missing_dir", "unreadable", "dirty")


def short_name(name):
    """A worktree is named by its folder on the card (the full path is in its own field)."""
    return os.path.basename(name.rstrip("/")) if os.path.isabs(name) else name


def safe_text(text):
    """Card text is shown with inline-code markup: a stray backtick would swallow the rest of the line."""
    return str(text).replace("`", "'")


def age_text(ts, now, lang):
    days = int((now - ts) // 86400)
    if days <= 0:
        return t(lang, "age_today")
    return t(lang, "age_day" if days == 1 else "age_days", n=days)


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def reason_text(u, lang):
    """The reason an item is never offered, from its code (see `inventory`)."""
    return t(lang, "why_" + u["why"], path=safe_text(u.get("path", "")), n=u.get("count", 0))


def pr_text(it, lang):
    pr = it.get("pr")
    if pr is None:  # gh off or unusable, or a worktree with no branch
        return ""
    if not pr:
        return t(lang, "pr_none")
    return t(lang, "pr_merged" if pr["tip_matches"] else "pr_differs", n=pr["number"])


def remote_text(it, lang):
    state = it.get("remote")
    if not state:
        return ""
    return t(lang, "remote_" + state, name=safe_text(it.get("branch") or it["name"]))


def backup_name(it):
    if it["kind"] == "stash":
        return BACKUP + "stash-" + it["sha"][:12]
    if it["kind"] == "worktree":
        return BACKUP + "wt-" + it["sha"][:12]
    return BACKUP + it["name"]


def confirm_text(it, lang):
    """The second-press warning of a card that is not provably merged (None for P1 and P2)."""
    if it["kind"] == "stash":
        return t(lang, "confirm_stash")
    if it["kind"] == "worktree" and it.get("ignored"):
        return t(lang, "confirm_ignored", shown=", ".join(safe_text(e) for e in it["ignored"][:3]))
    if it["kind"] == "worktree":
        if it["proof"] in SAFE_PROOFS:
            return None
        return t(lang, "confirm_wt_branch" if it["branch"] else "confirm_wt_detached")
    if it["proof"] == "P3":
        return t(lang, "confirm_p3")
    if it["proof"] == "P4":
        return t(lang, "confirm_p4")
    return None


def card_for(it, iid, now, lang):
    kind, name = it["kind"], it["name"]
    fields = [{"label": t(lang, "f_proof"), "text": f"{it['proof']} - {t(lang, 'proof_' + it['proof'])}"}]
    if kind == "worktree":
        fields.append({"label": t(lang, "f_worktree"), "text": t(lang, "wt_text", path=safe_text(it["path"]), size=human_size(it["size"]))})
        if it["branch"]:
            tail = t(lang, "branch_goes" if it["drop_branch"] else "branch_stays")
            fields.append({"label": t(lang, "f_branch"), "text": f"`{safe_text(it['branch'])}`{tail}"})
        else:
            fields.append({"label": t(lang, "f_branch"), "text": t(lang, "no_branch")})
        if it.get("ignored"):
            body = "\n".join(f"`{safe_text(e)}`" for e in it["ignored"][:5])
            fields.append({"label": t(lang, "f_ignored"), "text": body + "\n" + t(lang, "ignored_note")})
    who = f", {safe_text(it['author'])}" if it["author"] else ""
    fields.append({"label": t(lang, "f_last"), "text": f"{safe_text(it['subject'])} ({age_text(it['ts'], now, lang)}{who})"})
    if kind == "stash":
        fields.append({"label": t(lang, "f_content"), "text": safe_text(it["shortstat"]) or t(lang, "empty")})
    else:
        fields.append({"label": t(lang, "f_vs_base"), "text": t(lang, "vs_base", ahead=it["ahead"], behind=it["behind"])})
        pr = pr_text(it, lang)
        if pr:
            fields.append({"label": t(lang, "f_pr"), "text": pr})
        remote = remote_text(it, lang)
        if remote:
            fields.append({"label": t(lang, "f_remote"), "text": remote})
    if kind == "stash" and it["files"]:
        more = it["file_count"] - len(it["files"])
        body = "\n".join(f"`{safe_text(f)}`" for f in it["files"]) + (f"\n(+{more})" if more > 0 else "")
        fields.append({"label": t(lang, "f_files"), "text": body})
    elif kind != "stash" and it["unique"]:
        more = it["unique_count"] - len(it["unique"])
        body = "\n".join(f"`{safe_text(line)}`" for line in it["unique"]) + (f"\n(+{more})" if more > 0 else "")
        fields.append({"label": t(lang, "f_only_here"), "text": body})
    if kind == "branch":
        effect = t(lang, "effect_branch")
    elif kind == "worktree":
        effect = t(lang, "effect_worktree_branch" if it["drop_branch"] else "effect_worktree")
    else:
        effect = t(lang, "effect_stash")
    if it["backup"]:
        effect += t(lang, "effect_backup", ref=safe_text(backup_name(it)))
    fields.append({"label": t(lang, "f_effect"), "text": effect})
    card = {"id": iid, "tag": it["proof"], "title": f"{t(lang, 'verb_' + kind)} {safe_text(short_name(name))}?", "fields": fields}
    confirm = confirm_text(it, lang)
    if confirm:
        card["confirm"] = confirm
    return card


def build_scan(root, inv, now=None, stamp=None, lang=DEFAULT_LANG):
    """(batch, scan) for an inventory in `lang`, or None when there is nothing to offer."""
    check_lang(lang)
    if not inv["items"]:
        return None
    now = now or time.time()
    stamp = stamp or time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
    repo_name = Path(root).name
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", repo_name).strip("-") or "repo"
    cards, entries, safe_ids, safe_lines = [], [], [], []
    for n, it in enumerate(inv["items"], 1):
        iid = f"T{n:02d}"
        cards.append(card_for(it, iid, now, lang))
        entries.append({"id": iid, "kind": it["kind"], "name": it["name"], "sha": it["sha"], "proof": it["proof"],
                        "branch": it.get("branch"), "path": it.get("path"), "drop_branch": bool(it.get("drop_branch")),
                        "backup": bool(it["backup"])})
        if it["proof"] in SAFE_PROOFS and not it.get("ignored"):  # ignored files need their own confirmation
            safe_ids.append(iid)
            safe_lines.append(f"`{safe_text(short_name(it['name']))}` ({it['kind']}, {it['proof']})")
    group = None
    if len(safe_ids) >= 2:
        labels = LABELS[lang]
        cards.insert(0, {"id": "G", "tag": t(lang, "group_tag"),
                         "title": t(lang, "group_title", n=len(safe_ids)),
                         "fields": [{"label": t(lang, "f_items"), "text": "\n".join(safe_lines)},
                                    {"label": t(lang, "f_rule"), "text": t(lang, "group_rule", keep=labels["reject"]["text"], later=labels["maybe"]["text"])}]})
        group = {"id": "G", "members": safe_ids}
    untouched = [{"name": u["name"], "why": reason_text(u, lang)} for u in inv["untouched"]]
    if untouched:  # a field, not meta: the side panel's key column is too narrow for this label
        lines = "\n".join(f"`{safe_text(short_name(u['name']))}`: {u['why']}" for u in untouched)
        cards[0]["fields"].append({"label": t(lang, "f_untouched"), "text": lines})
    cards[0]["meta"] = {"Base": inv["base"], "gh": t(lang, "gh_yes" if inv["gh"] else "gh_no")}
    batch = {"batch_id": f"tidy-{slug}-{stamp}", "title": t(lang, "batch_title", repo=repo_name),
             "subtitle": t(lang, "subtitle", base=inv["base"], gh=t(lang, "gh_short_yes" if inv["gh"] else "gh_short_no"), n=len(inv["items"])),
             "round": 1, "lang": lang, "labels": LABELS[lang], "items": cards}
    scan = {"version": VERSION, "repo": str(root), "base": inv["base"], "base_sha": inv["base_sha"], "gh": inv["gh"], "lang": lang,
            "scanned_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(now)), "group": group,
            "untouched": untouched, "items": entries}
    return batch, scan
```

`check` refuses a bad `lang` in `scan.json`, `scan` takes `--lang`, prints the `NAO TOCAR:` reasons from the pt-BR card table and names the language on its summary line. These command-line lines are transient: Task 4b moves every line the tool prints to its own accent-free message table, before the release:

In `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py`, replace:

```python
    group = scan.get("group")
    if group is not None:
        if not isinstance(group, dict)
```

with:

```python
    if scan.get("lang") is not None and scan["lang"] not in LANGS:  # an older scan has no lang: that is English
        errs.append("scan.json: 'lang' deve ser en ou pt-BR")
    group = scan.get("group")
    if group is not None:
        if not isinstance(group, dict)
```

In `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py`, replace:

```python
    built = build_scan(root, inv)
    for u in inv["untouched"]:
        print(f"NAO TOCAR: {u['name']} ({u['why']})")
```

with:

```python
    built = build_scan(root, inv, lang=a.lang)
    for u in inv["untouched"]:  # transient: Task 4b moves every line of the command line to its own table
        print(f"NAO TOCAR: {u['name']} ({reason_text(u, 'pt-BR')})")
```

In `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py`, replace:

```python
    print(f"TIDY-BOARD ITENS: {len(scan['items'])} ({counts}); base {base}; gh {'sim' if scan['gh'] else 'nao'}")
```

with:

```python
    print(f"TIDY-BOARD ITENS: {len(scan['items'])} ({counts}); base {base}; gh {'sim' if scan['gh'] else 'nao'}; idioma {a.lang}")
```

In `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py`, replace:

```python
    s.add_argument("--out", help="pasta do lote (padrao: <repo>/.tidy-board/<batch_id>)")
```

with:

```python
    s.add_argument("--out", help="pasta do lote (padrao: <repo>/.tidy-board/<batch_id>)")
    s.add_argument("--lang", choices=LANGS, default=DEFAULT_LANG, help="idioma dos cards: en (padrao) ou pt-BR")
```

- [ ] **Step 5: The examples in the new default**

The shipped example already used English card text; its labels and the group rule follow, and both files record the language (the skill test compares them with the table, so this comes before the suite runs):

In `plugins/tidy-board/skills/tidy-board/examples/batch.example.json`, replace:

```json
  "round": 1,
  "labels": {
    "approve": {"text": "Apagar", "tone": "danger"},
    "reject": {"text": "Manter", "tone": "safe"},
    "maybe": {"text": "Depois", "tone": "caution"}
  },
```

with:

```json
  "round": 1,
  "lang": "en",
  "labels": {
    "approve": {"text": "Delete", "tone": "danger"},
    "reject": {"text": "Keep", "tone": "safe"},
    "maybe": {"text": "Later", "tone": "caution"}
  },
```

In `plugins/tidy-board/skills/tidy-board/examples/batch.example.json`, replace:

```json
Applies to the items below that you do not mark Manter or Depois.
```

with:

```json
Applies to the items below that you do not mark Keep or Later.
```

In `plugins/tidy-board/skills/tidy-board/examples/scan.example.json`, replace:

```json
  "version": "0.1.0",
```

with:

```json
  "version": "0.2.0",
```

In `plugins/tidy-board/skills/tidy-board/examples/scan.example.json`, replace:

```json
  "gh": true,
```

with:

```json
  "gh": true,
  "lang": "en",
```

- [ ] **Step 6: Run the suite**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/tidy-board/tests 2>&1 | tail -n 3`

Expected: `Ran 144 tests` and `OK` (about two minutes).

- [ ] **Step 7: Commit**

Run:

```bash
git add -A
git commit -m "feat(tidy-board): cards in English by default or pt-BR with scan --lang" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

Expected: one commit (git status --short is empty afterwards).

### Task 4b: tidy-board: the command line in English or pt-BR, `--lang` on every command, release 0.2.0

**Files:**
- Modify: `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py` (a message table `MSG` with `env_lang`, `pick_lang`, `use_lang` and `say` before `check_lang`; `git` to `detect_base`; `load_dir` to `parser`; `make_backup` to `apply_stash`; `read_decisions`; `cmd_apply` to `main`; then the release: header, `VERSION`, usage comment)
- Modify: `plugins/tidy-board/tests/helpers.py`, `test_scan.py`, `test_apply.py` (the pinned Portuguese command-line text becomes the English default; the pt-BR board keeps its Portuguese pins), `test_package.py` (the released version); `plugins/tidy-board/CHANGELOG.md`
- Generated: `plugins/tidy-board/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`

**Interfaces:**
- Consumes: `LANGS`, `DEFAULT_LANG`, `WHY_CODES`, `TidyError`, the reason codes of `inventory` (Task 4); the resolution order and `CAPYBARA_LANG` of the engine (Task 2b).
- Produces: `ENV_LANG`, `CLI_LANG` (the language of the current run), `MSG` (two dicts, identical keys and placeholders, plain ASCII; pt-BR is the 0.1.1 output; `_1` keys are the singular forms), `env_lang()`, `pick_lang(*candidates)`, `use_lang(*candidates)`, `recorded_lang(folder)`, `say(msg_id, /, **values)`; `--lang {en,pt-BR}` on `scan`, `check`, `apply` and `restore` (default `None`). `scan` resolves `--lang`, then `CAPYBARA_LANG`, then `en`, and that one language goes to the cards, `batch.json`, `scan.json` and its output; `check`, `apply` and `restore` resolve `--lang`, then the `lang` recorded in `scan.json`, then `CAPYBARA_LANG`, then `en` (this replaces R5's "no `--lang` of their own"). Only `main()` sets `CLI_LANG`: it reads the folder's `scan.json` language first (`recorded_lang`), so even an error about that folder speaks the board's language, and it puts the previous value back afterwards; the commands never touch it. The `NAO TOCAR:` reasons come from `MSG` (accent-free), never from the accented card table. Tags kept in both languages: `TIDY-BOARD DIR:`, `TIDY-BOARD ITENS:`, `TIDY-BOARD:`, `APPLY:`, `RESTORE:`, `ok:` and the action words `deleted`, `skipped`, `would-delete`; `NAO TOCAR:` reads `DO NOT TOUCH:` in English and `erro:` reads `error:`. `applied.json` keeps its shape; the `reason` of a skipped item is text in the language of the run (nothing reads it back).
- Consumed by Task 6 (the tidy-board skill quotes the English lines with the pt-BR ones next to them).

- [ ] **Step 1: Keep the environment out of the suite**

In `plugins/tidy-board/tests/helpers.py`, replace:

```python
import importlib.util
import os
import subprocess
```

with:

```python
import importlib.util
import os
import subprocess

os.environ.pop("CAPYBARA_LANG", None)  # the defaults the suite pins must not depend on the shell that runs it
```

- [ ] **Step 2: Update the tests that pin the old command-line text and write the new ones**

Every board these tests scan is English (no `--lang`), so their `apply`, `check` and `restore` lines are English now. `LanguageApplyTest` (Task 4) scans with `--lang pt-BR`, so its pins (`APPLY: 2 apagados, 0 pulados`, `RESTORE: branch spike/u recriada`, `nao tem backup`) stay as they are: they are the pt-BR case.


In `plugins/tidy-board/tests/test_scan.py`, replace:

```python
        for fragment in ("id duplicado", "'kind' deve ser", "'proof' deve ser", "'sha' deve ser um id de commit completo"):
```

with:

```python
        for fragment in ("duplicate id", "'kind' must be", "'proof' must be", "'sha' must be a full commit id"):
```

In `plugins/tidy-board/tests/test_scan.py`, replace:

```python
        self.assertTrue(any("so aceita itens P1 ou P2" in e for e in self.problems(mutate)))
```

with:

```python
        self.assertTrue(any("only takes P1 or P2 items" in e for e in self.problems(mutate)))
```

In `plugins/tidy-board/tests/test_scan.py`, replace:

```python
        self.assertTrue(any("nao tem entrada no scan.json" in e or "nao tem card" in e for e in errs), errs)
```

with:

```python
        self.assertTrue(any("has no entry in scan.json" in e or "has no card" in e for e in errs), errs)
```

In `plugins/tidy-board/tests/test_scan.py`, replace:

```python
        self.assertTrue(any("precisa de 'path'" in e for e in self.problems(mutate)))
```

with:

```python
        self.assertTrue(any("needs 'path'" in e for e in self.problems(mutate)))
```

In `plugins/tidy-board/tests/test_scan.py`, replace:

```python
        self.assertIn("NAO TOCAR: main (branch base do repositório)", stdout)
        self.assertIn("; idioma en", stdout)
```

with:

```python
        self.assertIn("DO NOT TOUCH: main (base branch of the repository)", stdout)
        self.assertIn("; language en", stdout)
```

In `plugins/tidy-board/tests/test_scan.py`, replace:

```python
        self.assertIn("ja existe", err)
```

with:

```python
        self.assertIn("already exists", err)
```

In `plugins/tidy-board/tests/test_scan.py`, replace:

```python
        self.assertIn("'sha' deve ser um id de commit completo", err)
```

with:

```python
        self.assertIn("'sha' must be a full commit id", err)
```

In `plugins/tidy-board/tests/test_scan.py`, replace:

```python
        self.assertIn("erro:", err)
```

with:

```python
        self.assertIn("error:", err)
```

In `plugins/tidy-board/tests/test_scan.py`, replace:

```python
        self.assertIn("nao e um repositorio git", err)
```

with:

```python
        self.assertIn("not a git repository", err)
```

In `plugins/tidy-board/tests/test_scan.py`, replace:

```python
        self.assertIn("nada para limpar", stdout)
```

with:

```python
        self.assertIn("nothing to clean up", stdout)
```

In `plugins/tidy-board/tests/test_scan.py`, replace:

```python
        self.assertIn("a base 'nope' nao existe", err)
```

with:

```python
        self.assertIn("the base 'nope' does not exist", err)
```

In `plugins/tidy-board/tests/test_scan.py`, replace:

```python
        self.assertIn("a revisao cansa", err)
```

with:

```python
        self.assertIn("the review gets tiring", err)
```

In `plugins/tidy-board/tests/test_scan.py`, replace:

```python
        self.assertIn("idioma invalido", str(ctx.exception))
```

with:

```python
        self.assertIn("invalid language", str(ctx.exception))
```

In `plugins/tidy-board/tests/test_scan.py`, replace:

```python
        self.assertTrue(any("'lang' deve ser en ou pt-BR" in e for e in tb.scan_problems(batch, scan)))
```

with:

```python
        self.assertTrue(any("'lang' must be en or pt-BR" in e for e in tb.scan_problems(batch, scan)))
```

In `plugins/tidy-board/tests/test_scan.py`, replace:

```python
    def test_scan_lang_reaches_both_files_and_the_command_line_stays_portuguese(self):
```

with:

```python
    def test_scan_lang_reaches_both_files_and_the_command_line_follows_it(self):
```

In `plugins/tidy-board/tests/test_scan.py`, replace:

```python
        self.assertIn("NAO TOCAR: main (branch base do repositório)", stdout)
        self.assertIn("; idioma pt-BR", stdout)
        self.assertEqual(run_cli("check", str(out))[0], 0)
```

with:

```python
        self.assertIn("NAO TOCAR: main (branch base do repositorio)", stdout)  # accent-free, as the command line always was
        self.assertIn("; gh nao; idioma pt-BR", stdout)
        rc, stdout, _ = run_cli("check", str(out))  # check reads the scan's language
        self.assertEqual(rc, 0)
        self.assertTrue(stdout.startswith("ok: 5 itens, lote tidy-r-"), stdout)
```

In `plugins/tidy-board/tests/test_scan.py`, replace:

```python
        self.assertEqual(rc, 1)
        self.assertIn("'lang' deve ser en ou pt-BR", err)
```

with:

```python
        self.assertEqual(rc, 1)
        self.assertIn("scan.json: 'lang' must be en or pt-BR", err)  # an invalid recorded language is ignored: English
```

In `plugins/tidy-board/tests/test_apply.py`, replace:

```python
        self.assertIn("decisions.json ausente", err)
```

with:

```python
        self.assertIn("decisions.json missing or unreadable", err)
```

In `plugins/tidy-board/tests/test_apply.py`, replace:

```python
        self.assertIn("nao foi concluido", err)
```

with:

```python
        self.assertIn("the panel was not finished", err)
```

In `plugins/tidy-board/tests/test_apply.py`, replace:

```python
                self.assertIn("outro lote ou rodada", err)
```

with:

```python
                self.assertIn("another batch or round", err)
```

In `plugins/tidy-board/tests/test_apply.py`, replace:

```python
        self.assertIn("nada aprovado", out)
```

with:

```python
        self.assertIn("nothing approved", out)
```

In `plugins/tidy-board/tests/test_apply.py`, replace:

```python
        self.assertIn("invalidos", err)
```

with:

```python
        self.assertIn("invalid scan.json/batch.json", err)
```

In `plugins/tidy-board/tests/test_apply.py`, replace:

```python
        self.assertIn("simulado", out)
```

with:

```python
        self.assertIn("APPLY (dry run): 4 would be deleted, 0 skipped", out)
```

In `plugins/tidy-board/tests/test_apply.py`, replace:

```python
        self.assertIn("a ponta mudou desde o scan", out)
```

with:

```python
        self.assertIn("the tip changed since the scan", out)
```

In `plugins/tidy-board/tests/test_apply.py`, replace:

```python
        self.assertIn("esta em uso em", out)
```

with:

```python
        self.assertIn("it is in use in", out)
```

In `plugins/tidy-board/tests/test_apply.py`, replace:

```python
        rc, out, _ = self.apply()
        self.assertEqual(rc, 1)
        self.assertIn("a branch nao existe mais", out)


```

with:

```python
        rc, out, _ = self.apply()
        self.assertEqual(rc, 1)
        self.assertIn("the branch no longer exists", out)


```

In `plugins/tidy-board/tests/test_apply.py`, replace:

```python
        self.assertIn("deixou de estar mesclada na base", out)
```

with:

```python
        self.assertIn("it is no longer merged into the base", out)
```

In `plugins/tidy-board/tests/test_apply.py`, replace:

```python
        self.assertIn("alterado(s) ou nao rastreado(s)", out)
```

with:

```python
        self.assertIn("it has 1 changed or untracked file(s)", out)
```

In `plugins/tidy-board/tests/test_apply.py`, replace:

```python
        self.assertIn("nao consegui criar o backup", out)
```

with:

```python
        self.assertIn("could not create the backup", out)
```

In `plugins/tidy-board/tests/test_apply.py`, replace:

```python
        self.assertIn("o stash nao existe mais", out)
```

with:

```python
        self.assertIn("the stash no longer exists", out)
```

In `plugins/tidy-board/tests/test_apply.py`, replace:

```python
        self.assertIn("a branch nao existe mais", out)
        entry = self.applied()[self.ids["spike/x"]]
```

with:

```python
        self.assertIn("the branch no longer exists", out)
        entry = self.applied()[self.ids["spike/x"]]
```

In `plugins/tidy-board/tests/test_apply.py`, replace:

```python
        self.assertIn("nao tem backup", err)
        self.assertIn(f"git branch feat/a {sha}", err)
```

with:

```python
        self.assertIn("has no backup", err)
        self.assertIn(f"git branch feat/a {sha}", err)
```

In `plugins/tidy-board/tests/test_apply.py`, replace:

```python
            self.assertIn("nao foi apagado por este lote", err)
```

with:

```python
            self.assertIn("was not deleted by this batch", err)
```

In `plugins/tidy-board/tests/test_apply.py`, replace:

```python
        self.assertIn("gh indisponivel", out)
```

with:

```python
        self.assertIn("gh unavailable", out)
```

In `plugins/tidy-board/tests/test_apply.py`, replace:

```python
        self.assertIn("nao confere mais", out)
```

with:

```python
        self.assertIn("no longer matches the branch tip", out)
```

In `plugins/tidy-board/tests/test_apply.py`, replace:

```python
        self.assertIn("mudou de branch", out)
```

with:

```python
        self.assertIn("switched branches since the scan", out)
```

The new tests: the table's parity, its ASCII text and its pt-BR side, an AST guard over every function that prints, the singular forms, `CAPYBARA_LANG` for `scan`, the flag over the recorded language, `--lang` on every command and a run that leaves no language behind.

Append to `plugins/tidy-board/tests/test_scan.py` (after a blank line):

```python
# ---------------------------------------------------------------- the command line's language (tidy-board 0.2.0)

import ast as _ast
import os as _os

PRINTING = ("git", "git_ok", "repo_root", "detect_base", "check_lang", "load_dir", "scan_problems", "cmd_scan", "cmd_check",
            "parser", "make_backup", "pr_blocker", "branch_blocker", "apply_branch", "apply_worktree", "apply_stash",
            "read_decisions", "cmd_apply", "cmd_restore", "main")
CLI_PT_WORDS = {  # words of the old command-line output: any of them in a literal of those functions is a leftover
    "nao", "deve", "obrigatorio", "itens", "lote", "aviso", "erro", "consegui", "existe", "falhou", "invalido",
    "invalidos", "pasta", "tente", "nada", "limpar", "sim", "idioma", "apagados", "pulados", "simulado", "seriam",
    "recriado", "recriada", "ponta", "mudou", "uso", "mesclada", "bloqueado", "alterado", "rastreado", "ja",
    "painel", "concluido", "rodada", "decisoes", "escreve", "padrao", "reconfere", "apaga",
    "mostra", "faria", "recria", "registrado", "valida", "usar", "provar", "mergeados", "depois",
}


def _literals(fn):
    body = fn.body[1:] if fn.body and isinstance(fn.body[0], _ast.Expr) and isinstance(fn.body[0].value, _ast.Constant) else fn.body
    return [n.value for stmt in body for n in _ast.walk(stmt) if isinstance(n, _ast.Constant) and isinstance(n.value, str)]


class CommandLineTableTest(unittest.TestCase):
    def test_both_tables_have_the_same_keys_and_placeholders_and_are_plain_ascii(self):
        en, pt = tb.MSG["en"], tb.MSG["pt-BR"]
        self.assertEqual(set(en), set(pt))
        for key in en:
            with self.subTest(key=key):
                self.assertEqual(set(PLACEHOLDER.findall(en[key])), set(PLACEHOLDER.findall(pt[key])))
                self.assertTrue(en[key].isascii() and pt[key].isascii(), key)
        for code in tb.WHY_CODES:  # the reasons a scan prints come from this table, not from the accented cards
            self.assertIn("why_" + code, en)

    def test_the_pt_br_side_is_the_old_output(self):
        pt = tb.MSG["pt-BR"]
        self.assertEqual(pt["untouched"], "NAO TOCAR: {name} ({why})")
        self.assertEqual(pt["why_base_branch"], "branch base do repositorio")
        self.assertEqual(pt["invalid"], "scan.json/batch.json invalidos:")
        self.assertEqual(pt["error"], "erro: {e}")

    def test_no_portuguese_literal_is_left_in_the_functions_that_print(self):
        tree = _ast.parse(Path(tb.__file__).read_text(encoding="utf-8"))
        found = []
        for fn in (n for n in _ast.walk(tree) if isinstance(n, _ast.FunctionDef) and n.name in PRINTING):
            for text in _literals(fn):
                if set(_re.split(r"[^a-z]+", text.lower())) & CLI_PT_WORDS:
                    found.append(f"{fn.name}: {text!r}")
        self.assertEqual(found, [], "Portuguese left outside MSG:\n" + "\n".join(found))

    def test_a_placeholder_named_like_an_argument_is_still_substituted(self):
        self.assertIn("scan.json: 'repo' is required (text)", tb.scan_problems({"items": []}, {"items": [], "base": "main"}))

    def test_one_takes_the_singular_form(self):
        self.addCleanup(setattr, tb, "CLI_LANG", tb.CLI_LANG)
        tb.CLI_LANG = "pt-BR"
        self.assertEqual(tb.say("apply", deleted=tb.say("n_deleted", n=1), skipped=tb.say("n_skipped", n=0)), "APPLY: 1 apagado, 0 pulados")
        self.assertEqual(tb.say("ok", n=1, id="b"), "ok: 1 item, lote b")
        tb.CLI_LANG = "en"
        self.assertEqual(tb.say("ok", n=1, id="b"), "ok: 1 item, batch b")
        self.assertEqual(tb.say("apply_dry", deleted=tb.say("n_would", n=1), skipped=tb.say("n_skipped", n=2)),
                         "APPLY (dry run): 1 would be deleted, 2 skipped")


class CommandLineLanguageTest(BoardRepo):
    def test_capybara_lang_chooses_the_cards_and_the_lines_when_there_is_no_flag(self):
        out = self.tmp / "board"
        with mock.patch.dict(_os.environ, {"CAPYBARA_LANG": "pt-BR"}):
            rc, stdout, _ = run_cli("scan", str(self.repo), "--gh", "off", "--out", str(out))
        self.assertEqual(rc, 0, stdout)
        self.assertEqual(json.loads((out / "batch.json").read_text(encoding="utf-8"))["lang"], "pt-BR")
        self.assertIn("NAO TOCAR: main (branch base do repositorio)", stdout)
        with mock.patch.dict(_os.environ, {"CAPYBARA_LANG": "pt-BR"}):
            rc, stdout, _ = run_cli("scan", str(self.repo), "--gh", "off", "--out", str(self.tmp / "b2"), "--lang", "en")
        self.assertIn("DO NOT TOUCH: main (base branch of the repository)", stdout)

    def test_a_bad_capybara_lang_is_ignored(self):
        with mock.patch.dict(_os.environ, {"CAPYBARA_LANG": "pt_BR"}):
            rc, stdout, err = run_cli("scan", str(self.repo), "--gh", "off", "--out", str(self.tmp / "board"))
        self.assertEqual((rc, err), (0, ""))
        self.assertIn("; language en", stdout)

    def test_the_flag_wins_over_the_language_the_scan_recorded(self):
        out = self.tmp / "board"
        run_cli("scan", str(self.repo), "--gh", "off", "--out", str(out), "--lang", "pt-BR")
        rc, stdout, _ = run_cli("check", str(out), "--lang", "en")
        self.assertEqual(rc, 0)
        self.assertTrue(stdout.startswith("ok: 5 items, batch tidy-r-"), stdout)
        rc, _, err = run_cli("apply", str(out))  # no decisions yet: refused in the scan's language
        self.assertEqual(rc, 2)
        self.assertIn("erro: decisions.json ausente ou ilegivel", err)

    def test_every_command_takes_lang_and_a_run_leaves_no_language_behind(self):
        for argv in (["scan", "."], ["check", "d"], ["apply", "d"], ["restore", "d", "T01"]):
            with self.subTest(cmd=argv[0]):
                self.assertEqual(tb.parser().parse_args(argv + ["--lang", "pt-BR"]).lang, "pt-BR")
                self.assertIsNone(tb.parser().parse_args(argv).lang)
        run_cli("scan", str(self.repo), "--gh", "off", "--out", str(self.tmp / "board"), "--lang", "pt-BR")
        self.assertEqual(tb.CLI_LANG, "en")  # main() put the default back
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/tidy-board/tests -p 'test_s*.py' 2>&1 | tail -n 3`

Expected: `FAILED (` with failures and errors: `tb.MSG`, `tb.say` and `tb.CLI_LANG` do not exist, every command still prints Portuguese and only `scan` takes `--lang`.

- [ ] **Step 4: The message table and the language of a run**

The table goes right before `check_lang`, which now speaks through it:


In `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py`, replace:

```python
def check_lang(lang):
    """A language is one of LANGS; anything else (a typo, a value edited into a file) is the person's error."""
    if lang not in LANGS:
        raise TidyError(f"idioma invalido: {lang!r} (use en ou pt-BR)")
    return lang
```

with:

```python
ENV_LANG = "CAPYBARA_LANG"  # one shell-wide default for every Capybara Toolbox script
CLI_LANG = DEFAULT_LANG  # the language of this run's messages: set by main(), refined by the scan a command reads

# Every message the command line prints, in both languages (the cards are TEXT, above). Same keys and
# {placeholders} in both (a test enforces it); both plain ASCII, so the pt-BR side is the accent-free Portuguese
# these commands always printed, and a key ending in `_1` is the form used when n == 1.
MSG = {
    "en": {
        "git_missing": "git not found in PATH", "git_failed": "git {args} failed: {err}",
        "not_repo": "not a git repository: {path}", "no_base": "the base '{base}' does not exist",
        "base_unknown": "could not detect the base branch; pass --base REF",
        "bad_lang": "invalid language: {lang} (use en or pt-BR)",
        "unreadable_dir": "could not read batch.json and scan.json in {d}: {e}",
        "p_scan_items": "scan.json: 'items' must be a list", "p_batch_items": "batch.json: 'items' must be a list",
        "p_required": "scan.json: '{key}' is required (text)", "p_obj": "{where}: must be an object",
        "p_id": "{where}: invalid 'id'", "p_dup": "{where}: duplicate id '{iid}'",
        "p_no_card": "{where}: '{iid}' has no card in batch.json",
        "p_kind": "{where}: 'kind' must be branch, worktree or stash", "p_proof": "{where}: 'proof' must be P1, P2, P3 or P4",
        "p_sha": "{where}: 'sha' must be a full commit id", "p_name": "{where}: 'name' is required",
        "p_path": "{where}: a worktree needs 'path'", "p_lang": "scan.json: 'lang' must be en or pt-BR",
        "p_group": "scan.json: invalid 'group'", "p_group_card": "batch.json: the group card G is missing",
        "p_group_proof": "scan.json: the group only takes P1 or P2 items ('{m}')",
        "p_no_entry": "batch.json: the card '{cid}' has no entry in scan.json",
        "untouched": "DO NOT TOUCH: {name} ({why})",
        "why_base_branch": "base branch of the repository", "why_current_branch": "current branch (in use by this worktree)",
        "why_main_worktree": "in use by the main worktree ({path})", "why_current_worktree": "current worktree",
        "why_locked": "locked worktree", "why_missing_dir": "folder missing (git worktree prune fixes it)",
        "why_unreadable": "could not read the state of the worktree",
        "why_dirty": "{n} changed or untracked file(s): deleting would lose work with no sha to recover",
        "nothing": "TIDY-BOARD: nothing to clean up",
        "dir_exists": "the folder {out} already exists (two scans in the same second); try again",
        "scan_items": "TIDY-BOARD ITENS: {n} ({counts}); base {base}; gh {gh}; language {lang}", "yes": "yes", "no": "no",
        "invalid": "invalid scan.json/batch.json:",
        "many_cards": "warning: {n} items; above {max} the review gets tiring (consider cleaning in two rounds)",
        "ok": "ok: {n} items, batch {id}", "ok_1": "ok: {n} item, batch {id}",
        "backup_other": "a backup with another sha already exists", "backup_failed": "could not create the backup: {err}",
        "gh_down": "gh unavailable: could not re-check the merged PR",
        "pr_moved": "the merged PR no longer matches the branch tip",
        "branch_gone": "the branch no longer exists", "tip_moved": "the tip changed since the scan",
        "is_base": "it is the base branch", "in_use": "it is in use in {path}",
        "unmerged": "it is no longer merged into the base", "branch_changed": "the branch changed during apply",
        "wt_gone": "the worktree no longer exists", "wt_main": "it is the main or the current worktree",
        "wt_locked": "the worktree is locked", "wt_unreadable": "could not read the state of the worktree",
        "wt_dirty": "it has {n} changed or untracked file(s)", "wt_head": "HEAD changed since the scan",
        "wt_switched": "the worktree switched branches since the scan", "wt_branch": "the branch {name}: {why}",
        "wt_remove_failed": "git worktree remove failed", "wt_branch_stayed": "worktree removed; the branch stayed: {err}",
        "stash_gone": "the stash no longer exists", "stash_changed": "the stash changed during apply",
        "stash_drop_failed": "git stash drop failed",
        "no_decisions": "decisions.json missing or unreadable: open the panel and finish it before apply",
        "bad_decisions": "decisions.json has an invalid shape",
        "old_decisions": "decisions.json belongs to another batch or round: I will not act on old decisions",
        "not_finished": "the panel was not finished (click Finish before apply)",
        "invalid_inline": "invalid scan.json/batch.json: {errs}", "repo_gone": "the repository of the scan no longer exists: {root}",
        "nothing_approved": "APPLY: nothing approved; nothing was deleted",
        "apply": "APPLY: {deleted}, {skipped}", "apply_dry": "APPLY (dry run): {deleted}, {skipped}",
        "n_deleted": "{n} deleted", "n_deleted_1": "{n} deleted", "n_would": "{n} would be deleted",
        "n_would_1": "{n} would be deleted", "n_skipped": "{n} skipped", "n_skipped_1": "{n} skipped",
        "not_deleted": "'{id}' was not deleted by this batch (see applied.json)",
        "commit_gone": "the commit {sha} no longer exists in this repository",
        "no_backup": "'{id}' has no backup (it was proven merged and its commits are in the base): "
                     "if you need it, recreate it with `git branch {target} {sha}`",
        "name_placeholder": "<name>", "stash_restored": "stash recreated", "branch_restored": "branch {name} recreated at {sha}",
        "wt_not_restored": " (the worktree is not recreated: git worktree add {path} {name})",
        "restore_failed": "git failed to restore", "error": "error: {e}",
    },
    "pt-BR": {
        "git_missing": "git nao encontrado no PATH", "git_failed": "git {args} falhou: {err}",
        "not_repo": "nao e um repositorio git: {path}", "no_base": "a base '{base}' nao existe",
        "base_unknown": "nao consegui detectar a branch base; passe --base REF",
        "bad_lang": "idioma invalido: {lang} (use en ou pt-BR)",
        "unreadable_dir": "nao consegui ler batch.json e scan.json em {d}: {e}",
        "p_scan_items": "scan.json: 'items' deve ser uma lista", "p_batch_items": "batch.json: 'items' deve ser uma lista",
        "p_required": "scan.json: '{key}' obrigatorio (texto)", "p_obj": "{where}: deve ser objeto",
        "p_id": "{where}: 'id' invalido", "p_dup": "{where}: id duplicado '{iid}'",
        "p_no_card": "{where}: '{iid}' nao tem card no batch.json",
        "p_kind": "{where}: 'kind' deve ser branch, worktree ou stash", "p_proof": "{where}: 'proof' deve ser P1, P2, P3 ou P4",
        "p_sha": "{where}: 'sha' deve ser um id de commit completo", "p_name": "{where}: 'name' obrigatorio",
        "p_path": "{where}: um worktree precisa de 'path'", "p_lang": "scan.json: 'lang' deve ser en ou pt-BR",
        "p_group": "scan.json: 'group' invalido", "p_group_card": "batch.json: falta o card G do grupo",
        "p_group_proof": "scan.json: o grupo so aceita itens P1 ou P2 ('{m}')",
        "p_no_entry": "batch.json: o card '{cid}' nao tem entrada no scan.json",
        "untouched": "NAO TOCAR: {name} ({why})",
        "why_base_branch": "branch base do repositorio", "why_current_branch": "branch atual (em uso por este worktree)",
        "why_main_worktree": "em uso pelo worktree principal ({path})", "why_current_worktree": "worktree atual",
        "why_locked": "worktree bloqueado (locked)", "why_missing_dir": "diretorio ausente (git worktree prune resolve)",
        "why_unreadable": "nao consegui ler o estado do worktree",
        "why_dirty": "{n} arquivo(s) alterado(s) ou nao rastreado(s): apagar perderia trabalho sem sha para recuperar",
        "nothing": "TIDY-BOARD: nada para limpar",
        "dir_exists": "a pasta {out} ja existe (dois scans no mesmo segundo); tente de novo",
        "scan_items": "TIDY-BOARD ITENS: {n} ({counts}); base {base}; gh {gh}; idioma {lang}", "yes": "sim", "no": "nao",
        "invalid": "scan.json/batch.json invalidos:",
        "many_cards": "aviso: {n} itens; acima de {max} a revisao cansa (considere limpar em duas rodadas)",
        "ok": "ok: {n} itens, lote {id}", "ok_1": "ok: {n} item, lote {id}",
        "backup_other": "ja existe um backup com outro sha", "backup_failed": "nao consegui criar o backup: {err}",
        "gh_down": "gh indisponivel: nao consegui reconferir o PR mergeado",
        "pr_moved": "o PR mergeado nao confere mais com a ponta da branch",
        "branch_gone": "a branch nao existe mais", "tip_moved": "a ponta mudou desde o scan",
        "is_base": "e a branch base", "in_use": "esta em uso em {path}",
        "unmerged": "deixou de estar mesclada na base", "branch_changed": "a branch mudou durante o apply",
        "wt_gone": "o worktree nao existe mais", "wt_main": "e o worktree principal ou o atual",
        "wt_locked": "o worktree esta bloqueado (locked)", "wt_unreadable": "nao consegui ler o estado do worktree",
        "wt_dirty": "tem {n} arquivo(s) alterado(s) ou nao rastreado(s)", "wt_head": "o HEAD mudou desde o scan",
        "wt_switched": "o worktree mudou de branch desde o scan", "wt_branch": "a branch {name}: {why}",
        "wt_remove_failed": "git worktree remove falhou", "wt_branch_stayed": "worktree removido; a branch ficou: {err}",
        "stash_gone": "o stash nao existe mais", "stash_changed": "o stash mudou durante o apply",
        "stash_drop_failed": "git stash drop falhou",
        "no_decisions": "decisions.json ausente ou ilegivel: suba o painel e conclua antes do apply",
        "bad_decisions": "decisions.json com formato invalido",
        "old_decisions": "decisions.json e de outro lote ou rodada: nao vou agir sobre decisoes antigas",
        "not_finished": "o painel nao foi concluido (clique em Concluir antes do apply)",
        "invalid_inline": "scan.json/batch.json invalidos: {errs}", "repo_gone": "o repositorio do scan nao existe mais: {root}",
        "nothing_approved": "APPLY: nada aprovado; nada foi apagado",
        "apply": "APPLY: {deleted}, {skipped}", "apply_dry": "APPLY (simulado): {deleted}, {skipped}",
        "n_deleted": "{n} apagados", "n_deleted_1": "{n} apagado", "n_would": "{n} seriam apagados",
        "n_would_1": "{n} seria apagado", "n_skipped": "{n} pulados", "n_skipped_1": "{n} pulado",
        "not_deleted": "'{id}' nao foi apagado por este lote (veja applied.json)",
        "commit_gone": "o commit {sha} nao existe mais neste repositorio",
        "no_backup": "'{id}' nao tem backup (estava provado como mesclado e seus commits estao na base): "
                     "se precisar, recrie com `git branch {target} {sha}`",
        "name_placeholder": "<nome>", "stash_restored": "stash recriado", "branch_restored": "branch {name} recriada em {sha}",
        "wt_not_restored": " (o worktree nao e recriado: git worktree add {path} {name})",
        "restore_failed": "git falhou ao restaurar", "error": "erro: {e}",
    },
}


def env_lang():
    """CAPYBARA_LANG when it is exactly one of LANGS. Any other value is ignored, silently: a shell setting must
    never break a command, and a warning on every run would be noise in the agent's context."""
    value = os.environ.get(ENV_LANG)
    return value if value in LANGS else None


def pick_lang(*candidates):
    """The first candidate that is one of LANGS (--lang, then the language a scan recorded), then CAPYBARA_LANG,
    then English. A recorded value is data: anything else is ignored here and refused by `check`."""
    for cand in candidates:
        if isinstance(cand, str) and cand in LANGS:
            return cand
    return env_lang() or DEFAULT_LANG


def use_lang(*candidates):
    """Set the language of this run's messages (see pick_lang) and return it. Only main() calls it."""
    global CLI_LANG
    CLI_LANG = pick_lang(*candidates)
    return CLI_LANG


def recorded_lang(folder):
    """The `lang` the scan in `folder` recorded, or None (no folder, no scan.json, not JSON). main() reads it before
    the command runs, so the command's lines and its errors speak the language of the board it works on."""
    if not folder:
        return None
    try:
        data = json.loads((Path(folder) / "scan.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, RecursionError):
        return None
    return data.get("lang") if isinstance(data, dict) else None


def say(msg_id, /, **values):
    """One command-line message in the language of this run; with n == 1 the `_1` form wins when there is one.
    The template is ours, the values are data (substituted, never parsed)."""
    table = MSG[CLI_LANG]
    if values.get("n") == 1 and msg_id + "_1" in table:
        msg_id += "_1"
    return table[msg_id].format(**values)


def check_lang(lang):
    """A language is one of LANGS; anything else (a typo, a value edited into a file) is the person's error."""
    if lang not in LANGS:
        raise TidyError(say("bad_lang", lang=repr(lang)))
    return lang
```

- [ ] **Step 5: Every message through `say()`**

The logic of each function is unchanged line for line; only the text moves to the table. `scan` uses the language of the run for the cards too, and the `NAO TOCAR:` reason is rendered from `MSG`:


In `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py`, replace everything from the line `def git(root, *args, input=None):` up to (not including) the line `def base_refs(root, base):` with:

```python
def git(root, *args, input=None):
    data = input.encode("utf-8") if isinstance(input, str) else input
    try:
        r = subprocess.run(["git", *GIT_FLAGS, "-C", str(root), *args], capture_output=True, input=data,
                           env={**os.environ, **GIT_ENV})
    except FileNotFoundError:
        raise TidyError(say("git_missing"))
    return Result(r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace"))


def git_ok(root, *args, input=None):
    r = git(root, *args, input=input)
    if r.rc != 0:
        raise TidyError(say("git_failed", args=" ".join(args), err=r.err.strip()))
    return r.out


def repo_root(path):
    r = git(path, "rev-parse", "--show-toplevel")
    if r.rc != 0:
        raise TidyError(say("not_repo", path=path))
    return Path(r.out.strip())


def rev(root, ref):
    """The commit id a ref points to, or None."""
    r = git(root, "rev-parse", "--verify", "--quiet", ref + "^{commit}")
    return r.out.strip() if r.rc == 0 else None


def detect_base(root, override=None):
    """--base, else the branch origin/HEAD points to, else the first of main, master, base, trunk."""
    if override:
        if rev(root, override) is None:
            raise TidyError(say("no_base", base=override))
        full = git(root, "rev-parse", "--symbolic-full-name", override).out.strip()
        return full[len("refs/heads/"):] if full.startswith("refs/heads/") else override
    r = git(root, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
    if r.rc == 0 and "/" in r.out.strip():
        short = r.out.strip().split("/", 1)[1]
        if rev(root, "refs/heads/" + short):
            return short
    for name in ("main", "master", "base", "trunk"):
        if rev(root, "refs/heads/" + name):
            return name
    raise TidyError(say("base_unknown"))


```

In `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py`, replace everything from the line `def load_dir(d):` up to (not including) the line `COMMANDS = {"scan": cmd_scan, "check": cmd_check}` with:

```python
def load_dir(d):
    d = Path(d)
    try:
        batch = json.loads((d / "batch.json").read_text(encoding="utf-8"))
        scan = json.loads((d / "scan.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise TidyError(say("unreadable_dir", d=d, e=e))
    return batch, scan


def scan_problems(batch, scan):
    """What is wrong with a batch.json + scan.json pair; empty when `apply` may trust it."""
    if not isinstance(scan, dict) or not isinstance(scan.get("items"), list):
        return [say("p_scan_items")]
    if not isinstance(batch, dict) or not isinstance(batch.get("items"), list):
        return [say("p_batch_items")]
    errs = []
    for key in ("repo", "base"):
        if not isinstance(scan.get(key), str) or not scan[key]:
            errs.append(say("p_required", key=key))
    card_ids = {c.get("id") for c in batch["items"] if isinstance(c, dict)}
    entries, seen = {}, set()
    for i, it in enumerate(scan["items"]):
        where = f"scan.json item {i}"
        if not isinstance(it, dict):
            errs.append(say("p_obj", where=where))
            continue
        iid = it.get("id")
        if not isinstance(iid, str) or not iid or iid == "G":
            errs.append(say("p_id", where=where))
            continue
        if iid in seen:
            errs.append(say("p_dup", where=where, iid=iid))
        seen.add(iid)
        entries[iid] = it
        if iid not in card_ids:
            errs.append(say("p_no_card", where=where, iid=iid))
        if it.get("kind") not in KINDS:
            errs.append(say("p_kind", where=where))
        if it.get("proof") not in PROOFS:
            errs.append(say("p_proof", where=where))
        if not isinstance(it.get("sha"), str) or not SHA.fullmatch(it["sha"]):
            errs.append(say("p_sha", where=where))
        if not isinstance(it.get("name"), str) or not it["name"]:
            errs.append(say("p_name", where=where))
        if it.get("kind") == "worktree" and not it.get("path"):
            errs.append(say("p_path", where=where))
    if scan.get("lang") is not None and scan["lang"] not in LANGS:  # an older scan has no lang: that is English
        errs.append(say("p_lang"))
    group = scan.get("group")
    if group is not None:
        if not isinstance(group, dict) or group.get("id") != "G" or not isinstance(group.get("members"), list):
            errs.append(say("p_group"))
        else:
            if "G" not in card_ids:
                errs.append(say("p_group_card"))
            for m in group["members"]:
                if m not in entries or entries[m].get("proof") not in SAFE_PROOFS:
                    errs.append(say("p_group_proof", m=m))
    for cid in sorted(c for c in card_ids if isinstance(c, str) and c != "G"):
        if cid not in entries:
            errs.append(say("p_no_entry", cid=cid))
    return errs


# ---------------------------------------------------------------- commands

def cmd_scan(a):
    root = repo_root(a.repo)
    base = detect_base(root, a.base)
    inv = inventory(root, base, a.gh)
    built = build_scan(root, inv, lang=CLI_LANG)  # one language per run: the cards, the files and these lines
    for u in inv["untouched"]:  # the reason comes from MSG (plain ASCII), not from the card table
        print(say("untouched", name=u["name"], why=say("why_" + u["why"], path=u.get("path", ""), n=u.get("count", 0))))
    if built is None:
        print(say("nothing"))
        return 0
    batch, scan = built
    out = Path(a.out) if a.out else root / ".tidy-board" / batch["batch_id"]
    if not a.out and out.exists():  # same batch id: the panel would resume decisions made for other cards
        raise TidyError(say("dir_exists", out=out))
    write_dir(out, batch, scan)
    counts = ", ".join(f"{p} {n}" for p in PROOFS if (n := sum(1 for i in scan["items"] if i["proof"] == p)))
    print(f"TIDY-BOARD DIR: {out}")  # the line tags are the same in both languages: the skill looks for them
    print(say("scan_items", n=len(scan["items"]), counts=counts, base=base, gh=say("yes" if scan["gh"] else "no"), lang=CLI_LANG))
    return 0


def cmd_check(a):
    batch, scan = load_dir(a.dir)
    errs = scan_problems(batch, scan)
    if errs:
        print(say("invalid") + "\n- " + "\n- ".join(errs), file=sys.stderr)
        return 1
    n = len(scan["items"])
    if n > WARN_CARDS:
        print(say("many_cards", n=n, max=WARN_CARDS), file=sys.stderr)
    print(say("ok", n=n, id=batch["batch_id"]))
    return 0


def parser():
    p = argparse.ArgumentParser(prog="tidy_board.py", description="Cards to clean up branches, worktrees and stashes.")
    p.add_argument("--version", action="version", version=f"tidy-board {VERSION}")
    sub = p.add_subparsers(dest="cmd", required=True)
    lang = argparse.ArgumentParser(add_help=False)  # every command takes --lang (the help text is English in both)
    lang.add_argument("--lang", choices=LANGS, default=None,
                      help="language of the messages, and of the cards for scan (default: the scan's lang, then CAPYBARA_LANG, then en)")
    s = sub.add_parser("scan", parents=[lang], help="read git (read-only) and write batch.json + scan.json")
    s.add_argument("repo", nargs="?", default=".")
    s.add_argument("--base", help="base branch (default: origin/HEAD, then main, master, base, trunk)")
    s.add_argument("--gh", choices=("auto", "off"), default="auto", help="use gh to prove merged PRs")
    s.add_argument("--out", help="batch folder (default: <repo>/.tidy-board/<batch_id>)")
    c = sub.add_parser("check", parents=[lang], help="validate batch.json + scan.json")
    c.add_argument("dir")
    a = sub.add_parser("apply", parents=[lang], help="re-verify each approved item and delete it")
    a.add_argument("dir")
    a.add_argument("--dry-run", action="store_true", help="show what it would do, deleting nothing")
    r = sub.add_parser("restore", parents=[lang], help="recreate a deleted item from its backup or its recorded sha")
    r.add_argument("dir")
    r.add_argument("id")
    return p


```

In `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py`, replace everything from the line `def make_backup(root, refname, sha):` up to (not including) the line `def apply_item(root, scan, it, dry):` with:

```python
def make_backup(root, refname, sha):
    """Create the backup ref; None when it is in place, otherwise the reason it could not be made."""
    current = git(root, "rev-parse", "--verify", "--quiet", refname).out.strip()
    if current == sha:
        return None
    if current:
        return say("backup_other")
    r = git(root, "update-ref", refname, sha, "")  # the empty old value means "must not exist yet"
    return None if r.rc == 0 else say("backup_failed", err=r.err.strip())


def merged_prs_once(root, scan):
    """gh is asked at most once per apply run, and only when a P2 item needs it (None: gh unusable)."""
    if "_prs" not in scan:
        scan["_prs"] = load_merged_prs(root, "auto")
    return scan["_prs"]


def pr_blocker(root, scan, name, sha):
    prs = merged_prs_once(root, scan)
    if prs is None:
        return say("gh_down")
    if not any(pr["oid"] == sha for pr in prs.get(name, [])):
        return say("pr_moved")
    return None


def branch_blocker(root, scan, name, sha, proof, held_by=None):
    """Why a branch must not be deleted now (None when it may): the scan is a photograph, this is the check."""
    tip = rev(root, "refs/heads/" + name)
    if tip is None:
        return say("branch_gone")
    if tip != sha:
        return say("tip_moved")
    if name in base_branch_names(root, scan["base"]):
        return say("is_base")
    held = checked_out_branches(root).get(name)
    if held and not (held_by and os.path.realpath(held) == os.path.realpath(held_by)):
        return say("in_use", path=held)
    merged = any(is_ancestor(root, sha, ref) for ref in base_refs(root, scan["base"]))
    if proof == "P1" and not merged:
        return say("unmerged")
    if proof == "P2" and not merged:  # P2 rested on gh at scan time: ask again, unless the history proves it now
        return pr_blocker(root, scan, name, sha)
    return None


def delete_branch(root, name, sha):
    """Delete the ref only if it still points at sha (a commit landing since the check makes git refuse), then
    drop the branch's config section the way `git branch -D` does (best effort)."""
    r = git(root, "update-ref", "-d", "refs/heads/" + name, sha)
    if r.rc == 0:
        git(root, "config", "--remove-section", "branch." + name)
    return r


def apply_branch(root, scan, it, dry):
    why = branch_blocker(root, scan, it["name"], it["sha"], it["proof"])
    if why:
        return skip(it, why)
    backup = backup_name(it) if it["proof"] in RISKY_PROOFS else None  # from the re-verified proof, not from a flag in scan.json
    if dry:
        return outcome(it, "would-delete", backup=backup)
    if backup:
        why = make_backup(root, backup, it["sha"])
        if why:
            return skip(it, why)
    r = delete_branch(root, it["name"], it["sha"])
    if r.rc != 0:
        return skip(it, r.err.strip() or say("branch_changed"))
    return outcome(it, "deleted", backup=backup)


def apply_worktree(root, scan, it, dry):
    path = it["path"]
    trees = list_worktrees(root)
    real = os.path.realpath(path)
    entry = next((wt for wt in trees if os.path.realpath(wt["worktree"]) == real), None)
    if entry is None or not Path(path).is_dir():
        return skip(it, say("wt_gone"))
    if real == os.path.realpath(trees[0]["worktree"]) or real == os.path.realpath(root):
        return skip(it, say("wt_main"))
    if "locked" in entry:
        return skip(it, say("wt_locked"))
    dirty = dirty_files(path)
    if dirty is None:
        return skip(it, say("wt_unreadable"))
    if dirty:
        return skip(it, say("wt_dirty", n=len(dirty)))
    head = git(path, "rev-parse", "--verify", "--quiet", "HEAD").out.strip()
    if head != it["sha"]:
        return skip(it, say("wt_head"))
    live = entry["branch"][len("refs/heads/"):] if entry.get("branch", "").startswith("refs/heads/") else None
    if live != it.get("branch"):
        return skip(it, say("wt_switched"))
    # what to delete and what to back up come from the live state and the re-verified proof, never from scan.json flags
    drop = live if (live and it["proof"] in SAFE_PROOFS and live not in base_branch_names(root, scan["base"])) else None
    if drop:
        why = branch_blocker(root, scan, drop, it["sha"], it["proof"], held_by=path)
        if why:
            return skip(it, say("wt_branch", name=drop, why=why))
    risky_head = live is None and (it["proof"] in RISKY_PROOFS or
                                   not any(is_ancestor(root, it["sha"], ref) for ref in base_refs(root, scan["base"])))
    backup = backup_name(it) if risky_head else None
    if dry:
        return outcome(it, "would-delete", backup=backup)
    if backup:
        why = make_backup(root, backup, it["sha"])
        if why:
            return skip(it, why)
    r = git(root, "worktree", "remove", path)  # never --force: a dirty tree must stop here
    if r.rc != 0:
        return skip(it, r.err.strip() or say("wt_remove_failed"))
    if drop:
        r = delete_branch(root, drop, it["sha"])
        if r.rc != 0:
            return outcome(it, "deleted", reason=say("wt_branch_stayed", err=r.err.strip()), backup=backup)
    return outcome(it, "deleted", backup=backup)


def apply_stash(root, it, dry):
    if it["sha"] not in [st["sha"] for st in list_stashes(root)]:
        return skip(it, say("stash_gone"))
    backup = backup_name(it)
    if dry:
        return outcome(it, "would-delete", backup=backup)
    why = make_backup(root, backup, it["sha"])
    if why:
        return skip(it, why)
    shas = [st["sha"] for st in list_stashes(root)]  # read again right before the drop: a stash pushed meanwhile moved the indexes
    if it["sha"] not in shas:
        return skip(it, say("stash_changed"))
    r = git(root, "stash", "drop", f"stash@{{{shas.index(it['sha'])}}}")
    if r.rc != 0:
        return skip(it, r.err.strip() or say("stash_drop_failed"))
    return outcome(it, "deleted", backup=backup)


```

In `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py`, replace everything from the line `def read_decisions(d, batch):` up to (not including) the line `def read_applied(d):` with:

```python
def read_decisions(d, batch):
    try:
        state = json.loads((Path(d) / "decisions.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise TidyError(say("no_decisions"))
    if not isinstance(state, dict) or not isinstance(state.get("items"), dict):
        raise TidyError(say("bad_decisions"))
    if state.get("batch_id") != batch.get("batch_id") or state.get("round") != int(batch.get("round", 1)):
        raise TidyError(say("old_decisions"))
    if state.get("finished") is not True:
        raise TidyError(say("not_finished"))
    return state["items"]


```

In `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py`, replace everything from the line `def cmd_apply(a):` up to (not including) the line `if __name__ == "__main__":` with:

```python
def cmd_apply(a):
    batch, scan = load_dir(a.dir)
    errs = scan_problems(batch, scan)
    if errs:
        raise TidyError(say("invalid_inline", errs="; ".join(errs)))
    decisions = read_decisions(a.dir, batch)
    root = Path(scan["repo"])
    if not root.is_dir() or git(root, "rev-parse", "--git-dir").rc != 0:
        raise TidyError(say("repo_gone", root=root))
    todo = approved_items(scan, decisions)
    if not todo:
        print(say("nothing_approved"))
        return 0
    results = []
    try:
        for it in todo:
            results.append(apply_item(root, scan, it, a.dry_run))
    finally:  # an interrupt or a crash mid-run must not lose the record of what was already deleted
        if results and not a.dry_run:
            save_applied(a.dir, results)
    for r in results:
        line = f"{r['action']:<12} {r['id']} {r['kind']} {r['name']}"
        if r.get("backup"):
            line += f"  (backup {r['backup']})"
        if r.get("reason"):
            line += f"  - {r['reason']}"
        print(line)
    done = sum(1 for r in results if r["action"] in ("deleted", "would-delete"))
    skipped = len(results) - done
    print(say("apply_dry" if a.dry_run else "apply", deleted=say("n_would" if a.dry_run else "n_deleted", n=done),
              skipped=say("n_skipped", n=skipped)))
    return 1 if skipped else 0


def cmd_restore(a):
    batch, scan = load_dir(a.dir)
    applied = read_applied(a.dir)
    entry = next((e for e in applied if e["id"] == a.id), None)
    if entry is None or entry.get("action") != "deleted":
        raise TidyError(say("not_deleted", id=a.id))
    root = Path(scan["repo"])
    sha = entry["sha"]
    if git(root, "cat-file", "-e", sha + "^{commit}").rc != 0:
        raise TidyError(say("commit_gone", sha=sha[:12]))
    if not entry.get("backup"):  # P1/P2: the commits are in the base, there is nothing to bring back from a backup
        item = next((i for i in scan["items"] if i["id"] == a.id), {})
        target = entry["name"] if entry["kind"] == "branch" else (item.get("branch") or say("name_placeholder"))
        raise TidyError(say("no_backup", id=a.id, target=target, sha=sha))
    if entry["kind"] == "stash":
        r = git(root, "stash", "store", "-m", f"tidy-board restore {sha[:12]}", sha)
        what = say("stash_restored")
    else:
        name = entry["name"] if entry["kind"] == "branch" else f"tidy-board/restored-{sha[:12]}"
        r = git(root, "branch", name, sha)
        what = say("branch_restored", name=name, sha=sha[:12])
        if entry["kind"] == "worktree":
            what += say("wt_not_restored", path=entry["name"], name=name)
    if r.rc != 0:
        raise TidyError(r.err.strip() or say("restore_failed"))
    git(root, "update-ref", "-d", entry["backup"])
    entry["action"] = "restored"
    write_private(Path(a.dir) / "applied.json", dump_json(applied))
    print(f"RESTORE: {what}")
    return 0


COMMANDS.update({"apply": cmd_apply, "restore": cmd_restore})


def main(argv=None):
    """Run one command. The language of its messages is set here, once: --lang, then the lang of the scan in the
    command's folder (check, apply, restore), then CAPYBARA_LANG, then en; scan uses that one language for its cards
    too. It is put back afterwards, so an in-process caller (the tests) never inherits another run's language."""
    global CLI_LANG
    args = parser().parse_args(argv)
    before = CLI_LANG
    use_lang(args.lang, recorded_lang(getattr(args, "dir", None)))
    try:
        return COMMANDS[args.cmd](args)
    except TidyError as e:
        print(say("error", e=e), file=sys.stderr)
        return 2
    finally:
        CLI_LANG = before


```

- [ ] **Step 6: Run the suite**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/tidy-board/tests 2>&1 | tail -n 3`

Expected: `Ran 153 tests` and `OK` (about two minutes).

- [ ] **Step 7: Release 0.2.0**

The release carries the cards (Task 4) and the command line (this task). Header comment, `VERSION`, the usage lines, the changelog (`DAY` is the day of execution) and the two sync tests that pin the released version:

In `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py`, replace:

```python
# tidy-board 0.1.1 - cards para limpar branches, worktrees e stashes; o apply reconfere e apaga (somente stdlib e git)
```

with:

```python
# tidy-board 0.2.0 - cards para limpar branches, worktrees e stashes; o apply reconfere e apaga (somente stdlib e git)
```

In `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py`, replace:

```python
VERSION = "0.1.1"
```

with:

```python
VERSION = "0.2.0"
```

In `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py`, replace:

```python
#   tidy_board.py scan    [REPO] [--base REF] [--gh auto|off] [--out DIR]   # le o git e escreve batch.json + scan.json
```

with:

```python
#   tidy_board.py scan    [REPO] [--base REF] [--gh auto|off] [--out DIR] [--lang en|pt-BR]   # le o git e escreve batch.json + scan.json
```

In `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py`, replace:

```python
#   tidy_board.py restore DIR ID                                           # recria o que foi apagado (backup ou sha)
```

with:

```python
#   tidy_board.py restore DIR ID                                           # recria o que foi apagado (backup ou sha)
# Todo comando aceita --lang en|pt-BR (padrao: o lang do scan.json, depois CAPYBARA_LANG, depois en).
```

In `plugins/tidy-board/CHANGELOG.md`, replace:

```markdown
## [Unreleased]

## [0.1.1] - 2026-10-15
```

with:

```markdown
## [Unreleased]

## [0.2.0] - DAY

### Added
- `scan --lang en|pt-BR` chooses the language of the cards: field labels, titles, effects, the group card, the "do not touch" reasons, the button wording (`labels`), the `confirm` texts, the subtitle and the age wording. The language is written to `batch.json` (`lang`, so the panel opens in it) and to `scan.json`. `check` rejects any other value in `scan.json`; an older scan without `lang` is read as English.
- The pt-BR cards are now written with accents.
- **Every command takes `--lang en|pt-BR`** for its messages (`scan`, `check`, `apply`, `restore`). Without it, `check`, `apply` and `restore` speak the language recorded in `scan.json`; `scan` uses one language for its cards and its output alike.
- **`CAPYBARA_LANG`** (`en` or `pt-BR`) is the default language when no flag and no recorded language decide; any other value is ignored. Every Capybara Toolbox script reads the same variable.

### Changed
- **The default is English**, for the cards and for the command line. A `scan` without `--lang` (and without `CAPYBARA_LANG`) writes English cards and prints English lines; pass `--lang pt-BR` for the Portuguese ones. The pt-BR command-line text is the accent-free Portuguese of 0.1.1, except that a count of one now takes the singular (`1 item`, `1 apagado`).
- In English `NAO TOCAR:` reads `DO NOT TOUCH:`, the error prefix is `error:` (pt-BR `erro:`) and the scan summary line ends with `; language <lang>` (pt-BR `; idioma <lang>`). The tags `TIDY-BOARD DIR:`, `TIDY-BOARD ITENS:`, `TIDY-BOARD:`, `APPLY:`, `RESTORE:` and `ok:` and the action words `deleted`, `skipped` and `would-delete` are the same in both languages. The `--help` text is English.
- The inventory holds codes, not text: the reasons an item is never offered, the merged-PR note and the remote note are rendered from a per-language table when the cards are built. `apply`, `restore` and `applied.json` are unchanged in shape: they read ids, shas and proofs, never a label; the `reason` of a skipped item is written in the language of the run.
- Requires ar-board 1.4.0 (the vendored engine) for the panel to honour `lang`.

## [0.1.1] - 2026-10-15
```

In `plugins/tidy-board/tests/test_package.py`, replace:

```python
script.write_text(script.read_text(encoding="utf-8").replace('VERSION = "0.1.1"', 'VERSION = "9.9.9"'), encoding="utf-8")
```

with:

```python
script.write_text(script.read_text(encoding="utf-8").replace('VERSION = "0.2.0"', 'VERSION = "9.9.9"'), encoding="utf-8")
```

In `plugins/tidy-board/tests/test_package.py`, replace:

```python
script.write_text(script.read_text(encoding="utf-8").replace("# tidy-board 0.1.1 - ", "# tidy-board 0.0.1 - "), encoding="utf-8")
```

with:

```python
script.write_text(script.read_text(encoding="utf-8").replace("# tidy-board 0.2.0 - ", "# tidy-board 0.0.1 - "), encoding="utf-8")
```

In `plugins/tidy-board/tests/test_package.py`, replace:

```python
        self.assertIn("header comment must say 'tidy-board 0.1.1'", out)
```

with:

```python
        self.assertIn("header comment must say 'tidy-board 0.2.0'", out)
```

Run: `python3 plugins/tidy-board/tools/sync.py && python3 tools/marketplace.py && python3 plugins/tidy-board/tools/sync.py --check && python3 tools/marketplace.py --check && echo in-sync`

Expected: `updated: .claude-plugin/plugin.json`, `updated: .claude-plugin/marketplace.json`, `in-sync`.

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/tidy-board/tests -p 'test_s*.py' 2>&1 | tail -n 3 && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/tidy-board/tests -p test_package.py 2>&1 | tail -n 3 && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests 2>&1 | tail -n 1`

Expected: `Ran 61 tests` (test_scan.py and test_skill.py), `Ran 12 tests` (test_package.py) and the catalog, each ending in `OK`.

- [ ] **Step 8: Commit**

Run:

```bash
git add -A
git commit -m "feat(tidy-board): the command line in English by default or pt-BR, --lang on every command, release 0.2.0" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

Expected: one commit (git status --short is empty afterwards).

### Task 5: todo-sweep: cards and report in a language, `scan --lang`

**Files:**
- Modify: `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py` (the table replaces `LABELS`; `age_reason` codes; the cards section is replaced; `cmd_scan`, `scan_problems`, `SECTIONS`, `report_markdown`, `cmd_report`, `parser`)
- Modify: `plugins/housekeeping/tests/test_ts_scan.py`, `test_ts_report.py`, `test_ts_cli.py`, `test_skills.py`; `plugins/housekeeping/skills/todo-sweep/examples/batch.example.json`, `scan.example.json`
- The housekeeping release (the three headers and `VERSION`s, `CHANGELOG.md`, the manifests) moved to the end of Task 5d, so 0.4.0 ships the cards of this task and the command line of Tasks 5b, 5c and 5d together.

**Interfaces:**
- Consumes: the engine's `validate` with `lang` (Task 3, through `capy_board.py`).
- Note: the command line stays Portuguese in this task; Task 5d moves it to a message table, before the housekeeping release.
- Produces: `LANGS`, `DEFAULT_LANG`, `AGE_REASONS`, `TEXT`, `LABELS[lang]`, `check_lang(lang)` (raises `SweepError`), `t(lang, key, **values)`, `area(file)` returning `''` at the root, `age_text(h, lang)`, `card_for(item_id, h, lang)`, `build_batch(batch_id, shown_hits, found, lang)`, `build_scan(batch_id, root, shown_hits, totals, lang)`, `SECTIONS` as `(json key, text key)` pairs, `report_markdown(scan, groups, lang)`, `scan --lang {en,pt-BR}` (default `en`), `lang` in `scan.json` and `report.json`, `scan_problems` refusing a bad `lang`.

- [ ] **Step 1: Record the baseline and update the tests that pin the old text**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/housekeeping/tests 2>&1 | tail -n 3`

Expected: `Ran 377 tests` and `OK` (about a minute).

The `Namespace` the tests build gains `lang="en"`; the reasons are pinned as codes; the titles, labels and field names as the English default; the report headings in English; the skill test compares the example with the table of its language:

In `plugins/housekeeping/tests/test_ts_scan.py`, replace:

```python
        base = dict(repo=str(self.repo), limit=20, max_blame=300, out=None)
```

with:

```python
        base = dict(repo=str(self.repo), limit=20, max_blame=300, out=None, lang="en")
```

In `plugins/housekeeping/tests/test_ts_scan.py`, replace:

```python
        self.assertEqual(hit["age_reason"], "linha nao commitada")

    def test_a_staged
```

with:

```python
        self.assertEqual(hit["age_reason"], "uncommitted")

    def test_a_staged
```

In `plugins/housekeeping/tests/test_ts_scan.py`, replace:

```python
        self.assertEqual(hit["age_reason"], "linha nao commitada")

    def test_when_blame
```

with:

```python
        self.assertEqual(hit["age_reason"], "uncommitted")

    def test_when_blame
```

In `plugins/housekeeping/tests/test_ts_scan.py`, replace:

```python
        self.assertIn("sem historico", hit["age_reason"])
```

with:

```python
        self.assertEqual(hit["age_reason"], "no_history")
```

In `plugins/housekeeping/tests/test_ts_scan.py`, replace:

```python
        self.assertEqual(hits[2]["age_reason"], "alem do limite de --max-blame")
```

with:

```python
        self.assertEqual(hits[2]["age_reason"], "max_blame")
```

In `plugins/housekeeping/tests/test_ts_scan.py`, replace:

```python
        self.assertTrue(all(h["age"] is None and "clone raso" in h["age_reason"] for h in hits), hits)
```

with:

```python
        self.assertTrue(all(h["age"] is None and h["age_reason"] == "shallow" for h in hits), hits)
```

In `plugins/housekeeping/tests/test_ts_scan.py`, replace:

```python
                         ["TODO em src/a.py:1: oldest", "FIXME em src/b.py:2: middle", "TODO em src/c.py:1: youngest"])
        self.assertEqual(batch["labels"]["approve"], {"text": "Resolver", "tone": "safe"})
        self.assertEqual(batch["labels"]["reject"], {"text": "Descartar", "tone": "danger"})
        self.assertEqual(batch["labels"]["maybe"], {"text": "Manter", "tone": "caution"})
        self.assertEqual(batch["batch_id"], out.name)
        card = {f["label"]: f["text"] for f in batch["items"][0]["fields"]}
        self.assertEqual(card["Onde"], "`src/a.py:1`")
        self.assertTrue(card["Idade"].startswith("300 dias"), card["Idade"])
        self.assertIn("   1  # TODO: oldest", card["Trecho"])
```

with:

```python
                         ["TODO in src/a.py:1: oldest", "FIXME in src/b.py:2: middle", "TODO in src/c.py:1: youngest"])
        self.assertEqual(batch["labels"]["approve"], {"text": "Resolve", "tone": "safe"})
        self.assertEqual(batch["labels"]["reject"], {"text": "Discard", "tone": "danger"})
        self.assertEqual(batch["labels"]["maybe"], {"text": "Keep", "tone": "caution"})
        self.assertEqual((batch["batch_id"], batch["lang"]), (out.name, "en"))
        card = {f["label"]: f["text"] for f in batch["items"][0]["fields"]}
        self.assertEqual(card["Where"], "`src/a.py:1`")
        self.assertTrue(card["Age"].startswith("300 days"), card["Age"])
        self.assertIn("   1  # TODO: oldest", card["Excerpt"])
        self.assertEqual(batch["items"][0]["meta"], {"Area": "src", "Age": "300 days"})
```

In `plugins/housekeeping/tests/test_ts_scan.py`, replace:

```python
        self.assertEqual((scan["schema"], scan["tool"], scan["round"], scan["repo"]), (1, "todo-sweep", 1, str(self.repo)))
```

with:

```python
        self.assertEqual((scan["schema"], scan["tool"], scan["round"], scan["repo"], scan["lang"]), (1, "todo-sweep", 1, str(self.repo), "en"))
```

In `plugins/housekeeping/tests/test_ts_scan.py`, replace:

```python
        self.assertGreater(len(dict((f["label"], f["text"]) for f in item["fields"])["Texto"]), 150)
```

with:

```python
        self.assertGreater(len(dict((f["label"], f["text"]) for f in item["fields"])["Text"]), 150)
```

In `plugins/housekeeping/tests/test_ts_report.py`, replace:

```python
        base = dict(repo=str(self.repo), limit=20, max_blame=300, out=None)
```

with:

```python
        base = dict(repo=str(self.repo), limit=20, max_blame=300, out=None, lang="en")
```

In `plugins/housekeeping/tests/test_ts_report.py`, replace:

```python
        for heading in ("## Resolver (1)", "## Descartar (1)", "## Manter (1)", "## Sem decisao (1)"):
            self.assertIn(heading, md)
        self.assertIn("do it soon", md)
        self.assertIn("Nenhum arquivo foi editado", md)
```

with:

```python
        for heading in ("## Resolve (1)", "## Discard (1)", "## Keep (1)", "## No decision (1)"):
            self.assertIn(heading, md)
        self.assertIn("do it soon", md)
        self.assertIn("No file was edited", md)
        self.assertEqual(data["lang"], "en")
```

In `plugins/housekeeping/tests/test_ts_report.py`, replace:

```python
        self.decide({self.scan["items"][0]["id"]: ("approved", "ok\n\n## Resolver (99)\n- `x.py:1` fake")})
        self.report()
        md = (self.out / "report.md").read_text(encoding="utf-8")
        self.assertEqual([l for l in md.split("\n") if l.startswith("#")][1:], ["## Resolver (1)", "## Descartar (0)", "## Manter (0)", "## Sem decisao (3)"])
```

with:

```python
        self.decide({self.scan["items"][0]["id"]: ("approved", "ok\n\n## Resolve (99)\n- `x.py:1` fake")})
        self.report()
        md = (self.out / "report.md").read_text(encoding="utf-8")
        self.assertEqual([l for l in md.split("\n") if l.startswith("#")][1:], ["## Resolve (1)", "## Discard (0)", "## Keep (0)", "## No decision (3)"])
```

In `plugins/housekeeping/tests/test_ts_cli.py`, replace:

```python
            args = argparse.Namespace(**{**dict(repo=str(self.repo), limit=20, max_blame=300, out=None), **kw})
```

with:

```python
            args = argparse.Namespace(**{**dict(repo=str(self.repo), limit=20, max_blame=300, out=None, lang="en"), **kw})
```

In `plugins/housekeeping/tests/test_skills.py`, replace:

```python
        self.assertEqual(batch["labels"], ts.LABELS)
```

with:

```python
        self.assertEqual(batch["labels"], ts.LABELS[batch["lang"]])
        self.assertEqual(scan["lang"], batch["lang"])
```

- [ ] **Step 2: Write the failing tests for both languages**

Append to `plugins/housekeeping/tests/test_ts_scan.py` (after a blank line):

```python
# ---------------------------------------------------------------- the cards' language (housekeeping 0.4.0)

import re as _re

PLACEHOLDER = _re.compile(r"\{(\w+)\}")


class LanguageTableTest(unittest.TestCase):
    def test_both_tables_have_the_same_keys_and_placeholders(self):
        self.assertEqual(ts.LANGS, ("en", "pt-BR"))
        self.assertEqual(ts.DEFAULT_LANG, "en")
        en, pt = ts.TEXT["en"], ts.TEXT["pt-BR"]
        self.assertEqual(set(en), set(pt))
        for key in en:
            with self.subTest(key=key):
                self.assertEqual(set(PLACEHOLDER.findall(en[key])), set(PLACEHOLDER.findall(pt[key])))
        self.assertEqual(set(ts.LABELS), set(ts.LANGS))
        for code in ts.AGE_REASONS:
            self.assertIn("reason_" + code, en)
        for _key, text_key in ts.SECTIONS:
            self.assertIn(text_key, en)

    def test_the_portuguese_table_has_accents(self):
        text = " ".join(ts.TEXT["pt-BR"].values())
        for word in ("última", "histórico", "Sem decisão", "relatório"):
            self.assertIn(word, text)

    def test_age_text_renders_the_reason_codes_in_both_languages(self):
        aged = {"age": {"days": 3, "time": 1_800_000_000, "commit": "abc1234"}, "age_reason": ""}
        self.assertEqual(ts.age_text(aged, "en"), "3 days (the line last changed on 2027-01-15, commit abc1234)")
        self.assertEqual(ts.age_text(aged, "pt-BR"), "3 dias (a linha mudou pela última vez em 2027-01-15, commit abc1234)")
        self.assertEqual(ts.age_text({"age": None, "age_reason": "uncommitted"}, "en"), "no age: uncommitted line")
        self.assertEqual(ts.age_text({"age": None, "age_reason": "shallow"}, "pt-BR"), "sem idade: limite de um clone raso (o histórico anterior não está aqui)")
        self.assertEqual(ts.age_text({"age": None, "age_reason": "whatever"}, "en"), "no age: whatever")  # an unknown code is shown, not a crash

    def test_an_unknown_language_is_refused(self):
        with self.assertRaises(ts.SweepError) as ctx:
            ts.check_lang("xx")
        self.assertIn("idioma invalido", str(ctx.exception))


class LanguageScanTest(SweepCase):
    def seed(self):
        self.commit({"src/a.py": "# TODO: oldest\n", "b.py": "x = 1\n"}, days_ago=300)
        self.commit({"b.py": "x = 1\n# FIXME: middle\n"}, days_ago=100)

    def test_pt_br_cards_are_the_old_ones_with_accents(self):
        self.seed()
        rc, out = self.scan(lang="pt-BR")
        batch = json.loads((out / "batch.json").read_text(encoding="utf-8"))
        scan = json.loads((out / "scan.json").read_text(encoding="utf-8"))
        self.assertEqual((rc, engine.validate(batch)), (0, []))
        self.assertEqual((batch["lang"], scan["lang"]), ("pt-BR", "pt-BR"))
        self.assertEqual([i["title"] for i in batch["items"]], ["TODO em src/a.py:1: oldest", "FIXME em b.py:2: middle"])
        self.assertEqual(batch["title"], "TODO e FIXME: 2 de 2")
        self.assertEqual(batch["labels"], ts.LABELS["pt-BR"])
        self.assertEqual(batch["labels"]["approve"]["text"], "Resolver")
        card = {f["label"]: f["text"] for f in batch["items"][0]["fields"]}
        self.assertEqual(list(card), ["Onde", "Texto", "Idade", "Trecho"])
        self.assertTrue(card["Idade"].startswith("300 dias (a linha mudou pela última vez em"), card["Idade"])
        self.assertEqual(batch["items"][0]["meta"], {"Área": "src", "Idade": "300 dias"})
        self.assertEqual(batch["items"][1]["meta"]["Área"], "(raiz)")
        self.assertEqual(batch["items"][1]["tag"], "FIXME - (raiz)")

    def test_english_cards_name_the_root_and_the_missing_age_in_english(self):
        self.commit({"a.py": "x = 1\n"}, days_ago=5)
        (self.repo / "a.py").write_text("x = 1\n# TODO: fresh\n", encoding="utf-8")
        _rc, out = self.scan()
        item = json.loads((out / "batch.json").read_text(encoding="utf-8"))["items"][0]
        card = {f["label"]: f["text"] for f in item["fields"]}
        self.assertEqual(item["tag"], "TODO - (root)")
        self.assertEqual(card["Age"], "no age: uncommitted line")
        self.assertEqual(item["meta"], {"Area": "(root)", "Age": "no age"})
        scan = json.loads((out / "scan.json").read_text(encoding="utf-8"))
        self.assertEqual(scan["items"][0]["age_reason"], "uncommitted")  # the sidecar keeps the code, not the text

    def test_both_languages_write_the_same_scan_apart_from_lang(self):
        self.seed()
        _rc, en = self.scan()
        _rc, pt = self.scan(lang="pt-BR")
        a = json.loads((en / "scan.json").read_text(encoding="utf-8"))
        b = json.loads((pt / "scan.json").read_text(encoding="utf-8"))
        for key in ("created", "batch_id", "lang"):
            a.pop(key), b.pop(key)
        self.assertEqual(a, b)

    def test_a_bad_lang_is_refused_before_anything_is_written(self):
        self.seed()
        with self.assertRaises(ts.SweepError) as ctx:
            ts.cmd_scan(self.args(lang="xx"))
        self.assertIn("idioma invalido", str(ctx.exception))
        self.assertFalse((self.repo / ".todo-sweep").exists())

    def test_check_accepts_both_languages_and_an_older_scan_without_lang_and_refuses_another_value(self):
        self.seed()
        _rc, out = self.scan(lang="pt-BR")
        self.assertEqual(ts.cmd_check(argparse.Namespace(dir=str(out))), 0)
        scan = json.loads((out / "scan.json").read_text(encoding="utf-8"))
        del scan["lang"]
        (out / "scan.json").write_text(json.dumps(scan), encoding="utf-8")
        self.assertEqual(ts.cmd_check(argparse.Namespace(dir=str(out))), 0)
        scan["lang"] = "xx"
        (out / "scan.json").write_text(json.dumps(scan), encoding="utf-8")
        self.assertEqual(ts.cmd_check(argparse.Namespace(dir=str(out))), 1)
```

Append to `plugins/housekeeping/tests/test_ts_report.py` (after a blank line):

```python
class LanguageReportTest(ReportCase):
    """The report follows the language recorded by the scan; the ledger and report.json keys never change."""

    def rescan(self, lang):
        for p in (self.repo / ".todo-sweep").glob("todo-sweep-*"):
            for f in p.iterdir():
                f.unlink()
            p.rmdir()
        ts.cmd_scan(self.args(lang=lang))
        self.out = sorted((self.repo / ".todo-sweep").glob("todo-sweep-*"))[-1]
        self.scan = json.loads((self.out / "scan.json").read_text(encoding="utf-8"))

    def test_a_pt_br_scan_gives_a_portuguese_report_with_the_same_json_keys(self):
        self.rescan("pt-BR")
        ids = [i["id"] for i in self.scan["items"]]
        self.decide({ids[0]: ("approved", "logo"), ids[1]: ("rejected", ""), ids[2]: ("maybe", "")})
        self.assertEqual(self.report(), 0)
        data = self.result()
        self.assertEqual(data["lang"], "pt-BR")
        self.assertEqual(data["counts"], {"resolver": 1, "descartar": 1, "manter": 1, "sem_decisao": 1})
        md = (self.out / "report.md").read_text(encoding="utf-8")
        self.assertTrue(md.startswith("# Relatório do todo-sweep - "), md[:60])
        for heading in ("## Resolver (1)", "## Descartar (1)", "## Manter (1)", "## Sem decisão (1)"):
            self.assertIn(heading, md)
        self.assertIn("Nenhum arquivo foi editado", md)
        self.assertIn("(90 dias)", md)
        self.assertEqual(sorted(e["decision"] for e in ts.load_ledger(self.repo).values()), ["discard", "keep"])

    def test_an_older_scan_without_lang_reports_in_english(self):
        scan = {k: v for k, v in self.scan.items() if k != "lang"}
        (self.out / "scan.json").write_text(json.dumps(scan), encoding="utf-8")
        self.decide({self.scan["items"][0]["id"]: ("approved", "")})
        self.assertEqual(self.report(), 0)
        self.assertEqual(self.result()["lang"], "en")
        self.assertIn("## Resolve (1)", (self.out / "report.md").read_text(encoding="utf-8"))

    def test_a_bad_lang_in_scan_json_is_refused_before_anything_is_written(self):
        for bad in ("xx", "", 1, ["en"]):
            (self.out / "scan.json").write_text(json.dumps(dict(self.scan, lang=bad)), encoding="utf-8")
            self.decide({self.scan["items"][0]["id"]: ("rejected", "")})
            with self.subTest(lang=bad), self.assertRaises(ts.SweepError) as ctx:
                self.report()
            self.assertIn("'lang'", str(ctx.exception))
            self.assertFalse((self.out / "report.json").exists())
            self.assertEqual(ts.load_ledger(self.repo), {})

    def test_a_ledger_written_by_a_pt_br_report_is_honoured_by_an_english_scan(self):
        self.rescan("pt-BR")
        ids = [i["id"] for i in self.scan["items"]]
        self.decide({ids[0]: ("rejected", ""), ids[1]: ("maybe", "")})
        self.report()
        ts.cmd_scan(self.args(lang="en"))
        newest = sorted((self.repo / ".todo-sweep").glob("todo-sweep-*"))[-1]
        again = json.loads((newest / "scan.json").read_text(encoding="utf-8"))
        self.assertEqual(again["lang"], "en")
        self.assertEqual(sorted(i["text"] for i in again["items"]), sorted(i["text"] for i in self.scan["items"][2:]))
        self.assertEqual(again["totals"]["decided_before"], 2)
```

Append to `plugins/housekeeping/tests/test_ts_cli.py` (after a blank line):

```python
class LanguageCliTest(CliCase):
    def test_lang_pt_br_flows_end_to_end_and_the_command_line_stays_portuguese(self):
        rc, out, _ = run_main(["scan", str(self.repo), "--lang", "pt-BR"])
        self.assertEqual(rc, 0, out)
        self.assertIn("3 TODO/FIXME achados", out)
        folder = Path(out.split("lote: ")[1].strip())
        batch = json.loads((folder / "batch.json").read_text(encoding="utf-8"))
        self.assertEqual((batch["lang"], batch["labels"]["approve"]["text"]), ("pt-BR", "Resolver"))
        self.assertEqual(engine.validate(batch), [])
        store = engine.Store(folder)
        store.set_item("T01", {"decision": "approved"})
        store.set_finished(True)
        rc, out, _ = run_main(["report", str(folder)])
        self.assertEqual(rc, 0, out)
        self.assertIn("REPORT: 1 resolver, 0 descartar, 0 manter, 2 sem decisao", out)
        self.assertIn("## Resolver (1)", (folder / "report.md").read_text(encoding="utf-8"))

    def test_an_unknown_lang_is_an_erro_line_with_exit_two_and_nothing_written(self):
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as ctx:
            ts.main(["scan", str(self.repo), "--lang", "xx"])
        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("erro: argumento --lang: comando invalido: 'xx'", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())
        self.assertFalse((self.repo / ".todo-sweep").exists())

    def test_help_documents_the_flag(self):
        r = subprocess.run([sys.executable, "-I", str(TODO_SWEEP), "scan", "--help"], capture_output=True, text=True)
        self.assertIn("--lang {en,pt-BR}", r.stdout)
```

- [ ] **Step 3: Run the new tests to see them fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/housekeeping/tests -k Language 2>&1 | tail -n 3`

Expected: `FAILED (`: ts.LANGS, ts.TEXT, check_lang and --lang do not exist yet.

- [ ] **Step 4: The table, the codes, the cards and the report**

`LABELS` is replaced by the languages, the reason codes, the table and the labels per language:

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace everything from the line `LABELS = {"approve": {"text": "Resolver", "tone": "safe"}, "reject": {"text": "Descartar", "tone": "danger"},` up to and including the next line that is exactly `          "maybe": {"text": "Manter", "tone": "caution"}}` with:

```python
LANGS = ("en", "pt-BR")  # languages of the cards and the report (`scan --lang`); the first is the default
DEFAULT_LANG = "en"
AGE_REASONS = ("max_blame", "no_history", "uncommitted", "shallow")  # codes kept in the hits and in scan.json

# Every card and report text, in both languages. Hits and scan.json hold codes (`age_reason`), never text;
# `t()` renders them. The two tables have the same keys and placeholders (a test enforces it).
TEXT = {
    "en": {
        "f_where": "Where", "f_text": "Text", "f_age": "Age", "f_excerpt": "Excerpt", "m_area": "Area", "m_age": "Age",
        "title": "{marker} in {place}", "no_text": "(no text)", "root": "(root)",
        "age": "{days} days (the line last changed on {day}, commit {commit})", "age_days": "{days} days",
        "no_age": "no age", "no_age_reason": "no age: {reason}",
        "reason_max_blame": "beyond the --max-blame limit", "reason_no_history": "no history (new file or the blame failed)",
        "reason_uncommitted": "uncommitted line", "reason_shallow": "limit of a shallow clone (the earlier history is not here)",
        "batch_title": "TODO and FIXME: {n} of {total}",
        "subtitle": "oldest first; Resolve, Discard or Keep, and the result is only a report",
        "report_title": "todo-sweep report - {batch}",
        "report_intro": "The lines are those of the moment of the scan. No file was edited by this tool.",
        "s_resolver": "Resolve", "s_descartar": "Discard", "s_manter": "Keep", "s_sem_decisao": "No decision",
    },
    "pt-BR": {
        "f_where": "Onde", "f_text": "Texto", "f_age": "Idade", "f_excerpt": "Trecho", "m_area": "Área", "m_age": "Idade",
        "title": "{marker} em {place}", "no_text": "(sem texto)", "root": "(raiz)",
        "age": "{days} dias (a linha mudou pela última vez em {day}, commit {commit})", "age_days": "{days} dias",
        "no_age": "sem idade", "no_age_reason": "sem idade: {reason}",
        "reason_max_blame": "além do limite de --max-blame", "reason_no_history": "sem histórico (arquivo novo ou o blame falhou)",
        "reason_uncommitted": "linha não commitada", "reason_shallow": "limite de um clone raso (o histórico anterior não está aqui)",
        "batch_title": "TODO e FIXME: {n} de {total}",
        "subtitle": "do mais antigo ao mais novo; Resolver, Descartar ou Manter, e o resultado é só um relatório",
        "report_title": "Relatório do todo-sweep - {batch}",
        "report_intro": "As linhas são as do momento do scan. Nenhum arquivo foi editado por esta ferramenta.",
        "s_resolver": "Resolver", "s_descartar": "Descartar", "s_manter": "Manter", "s_sem_decisao": "Sem decisão",
    },
}
LABELS = {  # the panel's own wording per language: A resolves, R discards, M keeps
    "en": {"approve": {"text": "Resolve", "tone": "safe"}, "reject": {"text": "Discard", "tone": "danger"},
           "maybe": {"text": "Keep", "tone": "caution"}},
    "pt-BR": {"approve": {"text": "Resolver", "tone": "safe"}, "reject": {"text": "Descartar", "tone": "danger"},
              "maybe": {"text": "Manter", "tone": "caution"}},
}
```

The hits carry codes instead of Portuguese reasons:

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
                         "todo_id": todo_id(rel, body, n), "age": None, "age_reason": "alem do limite de --max-blame"})
```

with:

```python
                         "todo_id": todo_id(rel, body, n), "age": None, "age_reason": "max_blame"})
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
                h["age_reason"] = "sem historico (arquivo novo ou o blame falhou)"
```

with:

```python
                h["age_reason"] = "no_history"
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
                h["age_reason"] = "linha nao commitada"
```

with:

```python
                h["age_reason"] = "uncommitted"
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
                h["age_reason"] = "limite de um clone raso (o historico anterior nao esta aqui)"
```

with:

```python
                h["age_reason"] = "shallow"
```

The cards section (from `shown` to `build_scan`) is replaced; `check_lang` and `t()` live at its top:

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace everything from the line `def shown(name):` up to (not including) the line `def unique_dir(parent, base):` with:

```python
def check_lang(lang):
    """A language is one of LANGS; anything else (a typo, a value edited into a file) is the person's error."""
    if lang not in LANGS:
        raise SweepError(f"idioma invalido: {lang!r} (use en ou pt-BR)")
    return lang


def t(lang, key, **values):
    """One card or report text in `lang`. The template is ours; the values are data, substituted and never parsed."""
    return TEXT[lang][key].format(**values)


def shown(name):
    """A name as the card shows it: a backtick would be read as the start of a code span."""
    return name.replace("`", "'")


def area(file):
    """The top folder of a file, or '' at the root (the card names the root in its own language)."""
    return file.split("/", 1)[0] if "/" in file else ""


def order_hits(hits):
    """Oldest first; what has no age comes after, in the order the files are listed."""
    aged = sorted((h for h in hits if h["age"]), key=lambda h: (-h["age"]["days"], h["file"], h["line"]))
    return aged + [h for h in hits if not h["age"]]


def age_text(h, lang):
    if h["age"]:
        day = time.strftime("%Y-%m-%d", time.gmtime(h["age"]["time"]))
        return t(lang, "age", days=h["age"]["days"], day=day, commit=h["age"]["commit"])
    reason = t(lang, "reason_" + h["age_reason"]) if h["age_reason"] in AGE_REASONS else h["age_reason"]
    return t(lang, "no_age_reason", reason=reason)


def card_for(item_id, h, lang):
    short = h["text"] if len(h["text"]) <= 90 else h["text"][:87] + "..."
    place = f"{shown(h['file'])}:{h['line']}"
    context = "\n".join(f"{n:>4}  {shown(text)}" for n, text in h["context"])
    where = shown(area(h["file"])) or t(lang, "root")
    return {"id": item_id, "tag": f"{h['marker']} - {where}",
            "title": t(lang, "title", marker=h["marker"], place=place) + (f": {shown(short)}" if short else ""),
            "fields": [{"label": t(lang, "f_where"), "text": f"`{place}`"},
                       {"label": t(lang, "f_text"), "text": shown(h["text"]) or t(lang, "no_text")},
                       {"label": t(lang, "f_age"), "text": age_text(h, lang)},
                       {"label": t(lang, "f_excerpt"), "text": context}],
            "meta": {t(lang, "m_area"): where, t(lang, "m_age"): t(lang, "age_days", days=h["age"]["days"]) if h["age"] else t(lang, "no_age")}}


def build_batch(batch_id, shown_hits, found, lang):
    width = max(2, len(str(len(shown_hits))))
    items = [card_for(f"T{i + 1:0{width}}", h, lang) for i, h in enumerate(shown_hits)]
    return {"batch_id": batch_id, "title": t(lang, "batch_title", n=len(shown_hits), total=found),
            "subtitle": t(lang, "subtitle"), "round": 1, "lang": lang, "labels": LABELS[lang], "items": items}


def build_scan(batch_id, root, shown_hits, totals, lang):
    items = []
    for i, h in enumerate(shown_hits):
        items.append({"id": f"T{i + 1:0{max(2, len(str(len(shown_hits))))}}", "todo_id": h["todo_id"], "file": h["file"],
                      "line": h["line"], "marker": h["marker"], "text": h["text"],
                      "age_days": h["age"]["days"] if h["age"] else None, "commit": h["age"]["commit"] if h["age"] else None,
                      "age_reason": h["age_reason"]})
    return {"schema": SCHEMA, "tool": "todo-sweep", "version": VERSION, "batch_id": batch_id, "repo": str(root),
            "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "round": 1, "lang": lang, "totals": totals, "items": items}
```

`cmd_scan` validates and passes the language, `check` refuses a bad `lang` in `scan.json`, the report follows the scan's language and records it, `scan` takes `--lang`:

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
def cmd_scan(a):
    check_counts(a)
    root = repo_root(a.repo)
```

with:

```python
def cmd_scan(a):
    check_counts(a)
    lang = check_lang(a.lang)
    root = repo_root(a.repo)
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
        write_all({out / "batch.json": dump_json(build_batch(batch_id, offered, len(fresh))),
                   out / "scan.json": dump_json(build_scan(batch_id, root, offered, totals))})
```

with:

```python
        write_all({out / "batch.json": dump_json(build_batch(batch_id, offered, len(fresh), lang)),
                   out / "scan.json": dump_json(build_scan(batch_id, root, offered, totals, lang))})
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
    if batch.get("batch_id") != scan.get("batch_id"):
        errs.append("batch.json e scan.json sao de lotes diferentes")
```

with:

```python
    if batch.get("batch_id") != scan.get("batch_id"):
        errs.append("batch.json e scan.json sao de lotes diferentes")
    if scan.get("lang") is not None and scan["lang"] not in LANGS:  # an older scan has no lang: that is English
        errs.append("scan.json: 'lang' deve ser en ou pt-BR")
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
SECTIONS = (("resolver", "Resolver"), ("descartar", "Descartar"), ("manter", "Manter"), ("sem_decisao", "Sem decisao"))
```

with:

```python
SECTIONS = (("resolver", "s_resolver"), ("descartar", "s_descartar"), ("manter", "s_manter"), ("sem_decisao", "s_sem_decisao"))  # JSON key, text key
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
    groups = {key: [] for key, _title in SECTIONS}
```

with:

```python
    groups = {key: [] for key, _text in SECTIONS}
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
def report_markdown(scan, groups):
    lines = [f"# Relatorio do todo-sweep - {md_line(scan['batch_id'])}", "",
             "As linhas sao as do momento do scan. Nenhum arquivo foi editado por esta ferramenta.", ""]
    for key, title in SECTIONS:
        lines += [f"## {title} ({len(groups[key])})", ""]
        for h in groups[key]:
            age = f"{h['age_days']} dias" if h["age_days"] is not None else "sem idade"
            lines.append(f"- `{md_line(h['file'])}:{h['line']}` {md_line(h['marker'])} {md_line(h['text']) or '(sem texto)'} ({age})"
```

with:

```python
def report_markdown(scan, groups, lang):
    lines = ["# " + t(lang, "report_title", batch=md_line(scan["batch_id"])), "", t(lang, "report_intro"), ""]
    for key, text_key in SECTIONS:
        lines += [f"## {t(lang, text_key)} ({len(groups[key])})", ""]
        for h in groups[key]:
            age = t(lang, "age_days", days=h["age_days"]) if h["age_days"] is not None else t(lang, "no_age")
            lines.append(f"- `{md_line(h['file'])}:{h['line']}` {md_line(h['marker'])} {md_line(h['text']) or t(lang, 'no_text')} ({age})"
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
    groups = group_items(scan, read_decisions(a.dir, batch))
    root = trusted_repo(scan, a.dir)
```

with:

```python
    lang = scan.get("lang") or DEFAULT_LANG  # an older scan has no lang: English; scan_problems refused any other value
    groups = group_items(scan, read_decisions(a.dir, batch))
    root = trusted_repo(scan, a.dir)
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
    data = {"schema": SCHEMA, "tool": "todo-sweep", "batch_id": scan["batch_id"], "round": batch.get("round", 1),
            "created": now_text, "counts": {key: len(groups[key]) for key, _t in SECTIONS}, **groups}
```

with:

```python
    data = {"schema": SCHEMA, "tool": "todo-sweep", "batch_id": scan["batch_id"], "round": batch.get("round", 1), "lang": lang,
            "created": now_text, "counts": {key: len(groups[key]) for key, _text in SECTIONS}, **groups}
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
        write_all({out / "report.json": dump_json(data), out / "report.md": report_markdown(scan, groups),
```

with:

```python
        write_all({out / "report.json": dump_json(data), out / "report.md": report_markdown(scan, groups, lang),
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
    s.add_argument("--out", help=f"pasta do lote (padrao: {WORK_DIR}/todo-sweep-AAAA-MM-DD)")
```

with:

```python
    s.add_argument("--out", help=f"pasta do lote (padrao: {WORK_DIR}/todo-sweep-AAAA-MM-DD)")
    s.add_argument("--lang", choices=LANGS, default=DEFAULT_LANG, help="idioma dos cards e do relatorio: en (padrao) ou pt-BR")
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
#   todo_sweep.py scan   [REPO] [--limit N] [--max-blame N] [--out DIR]   # acha os TODO/FIXME, mede a idade, escreve batch.json + scan.json
```

with:

```python
#   todo_sweep.py scan   [REPO] [--limit N] [--max-blame N] [--out DIR] [--lang en|pt-BR]   # acha os TODO/FIXME, mede a idade, escreve batch.json + scan.json
```

- [ ] **Step 5: The examples in the new default**

`batch.example.json` is rewritten as the English batch `scan` writes today (same TODOs, same ages); `scan.example.json` records the language and the version (the skill test compares the example with the table, so this comes before the suite runs):

Create `plugins/housekeeping/skills/todo-sweep/examples/batch.example.json`:

```json
{
  "batch_id": "todo-sweep-2026-10-14",
  "title": "TODO and FIXME: 3 of 3",
  "subtitle": "oldest first; Resolve, Discard or Keep, and the result is only a report",
  "round": 1,
  "lang": "en",
  "labels": {
    "approve": {
      "text": "Resolve",
      "tone": "safe"
    },
    "reject": {
      "text": "Discard",
      "tone": "danger"
    },
    "maybe": {
      "text": "Keep",
      "tone": "caution"
    }
  },
  "items": [
    {
      "id": "T01",
      "tag": "TODO - src",
      "title": "TODO in src/export.py:2: stream the rows instead of building a list",
      "fields": [
        {
          "label": "Where",
          "text": "`src/export.py:2`"
        },
        {
          "label": "Text",
          "text": "stream the rows instead of building a list"
        },
        {
          "label": "Age",
          "text": "412 days (the line last changed on 2025-08-28, commit 1a2b3c4)"
        },
        {
          "label": "Excerpt",
          "text": "   1  def export(rows):\n   2      # TODO: stream the rows instead of building a list\n   3      return list(rows)"
        }
      ],
      "meta": {
        "Area": "src",
        "Age": "412 days"
      }
    },
    {
      "id": "T02",
      "tag": "FIXME - src",
      "title": "FIXME in src/report.py:1: wrong for negative amounts",
      "fields": [
        {
          "label": "Where",
          "text": "`src/report.py:1`"
        },
        {
          "label": "Text",
          "text": "wrong for negative amounts"
        },
        {
          "label": "Age",
          "text": "95 days (the line last changed on 2026-07-11, commit 5d6e7f8)"
        },
        {
          "label": "Excerpt",
          "text": "   1  total = 0  # FIXME: wrong for negative amounts"
        }
      ],
      "meta": {
        "Area": "src",
        "Age": "95 days"
      }
    },
    {
      "id": "T03",
      "tag": "TODO - scripts",
      "title": "TODO in scripts/deploy.sh:1: ask before restarting the service",
      "fields": [
        {
          "label": "Where",
          "text": "`scripts/deploy.sh:1`"
        },
        {
          "label": "Text",
          "text": "ask before restarting the service"
        },
        {
          "label": "Age",
          "text": "8 days (the line last changed on 2026-10-06, commit 9a0b1c2)"
        },
        {
          "label": "Excerpt",
          "text": "   1  # TODO: ask before restarting the service\n   2  systemctl restart app"
        }
      ],
      "meta": {
        "Area": "scripts",
        "Age": "8 days"
      }
    }
  ]
}
```

In `plugins/housekeeping/skills/todo-sweep/examples/scan.example.json`, replace:

```json
  "version": "0.3.0",
```

with:

```json
  "version": "0.4.0",
```

In `plugins/housekeeping/skills/todo-sweep/examples/scan.example.json`, replace:

```json
  "round": 1,
  "totals": {
```

with:

```json
  "round": 1,
  "lang": "en",
  "totals": {
```

- [ ] **Step 6: Run the suite**

Run: `git add -A && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/housekeeping/tests 2>&1 | tail -n 3`

Expected: `Ran 393 tests` and `OK` (doc-truth's dogfooding test judges the git tree, hence the git add -A).

- [ ] **Step 7: Commit**

Run:

```bash
git add -A
git commit -m "feat(todo-sweep): cards and report in English by default or pt-BR with scan --lang" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

Expected: one commit (git status --short is empty afterwards).

### Task 5b: doc-truth: the messages in English or pt-BR, `--lang`

**Files:**
- Modify: `plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py` (`LANGS`, `MSG` and the language helpers after the constants; every message through `say()`; `--lang`; `main`)
- Modify: `plugins/housekeeping/tests/helpers.py`, `test_dt_cli.py`, `test_dt_parity_versions.py`

**Interfaces:**
- Consumes: the resolution order and `CAPYBARA_LANG` of Task 2b (doc-truth reads no batch: `--lang`, then `CAPYBARA_LANG`, then `en`).
- Produces: `LANGS`, `DEFAULT_LANG`, `ENV_LANG`, `CLI_LANG`, `MSG` (identical keys and placeholders, plain ASCII, pt-BR equal to the 0.3.1 output, `_1` singular forms), `env_lang()`, `pick_lang()`, `use_lang()`, `say(msg_id, /, **values)` (the helpers are duplicated on purpose: the scripts are standalone), `--lang {en,pt-BR}`. The report lines and every finding's `message` (text and `--json`) follow the language; a finding's `category`, `document`, `line`, `value` and `fingerprint` do not (the `parity` value `falta README.pt-BR.md` stays as it is, so an `allow` list keeps working in either language). The JSON shape and `schema` are unchanged.
- Consumed by Task 5d (the release), Task 6 (the doc-truth skill quotes `clean: no findings` with `limpo: nenhum achado` next to it) and every later `doc-truth` run in this plan (the expected line is now `clean: no findings`).

- [ ] **Step 1: Keep the environment out of the suite**

The housekeeping helpers are imported by every test file of the plugin, so this covers doc-truth, handoff and todo-sweep:


In `plugins/housekeeping/tests/helpers.py`, replace:

```python
import importlib.util
import os
import subprocess
```

with:

```python
import importlib.util
import os
import subprocess

os.environ.pop("CAPYBARA_LANG", None)  # the defaults the suite pins must not depend on the shell that runs it
```

- [ ] **Step 2: Update the tests that pin the old text and write the new ones**


In `plugins/housekeeping/tests/test_dt_cli.py`, replace:

```python
        self.assertIn("limpo: nenhum achado", out)
```

with:

```python
        self.assertIn("clean: no findings", out)
```

In `plugins/housekeeping/tests/test_dt_cli.py`, replace:

```python
        self.assertIn("nao e um repositorio git", err)
```

with:

```python
        self.assertIn("is not a git repository", err)
```

In `plugins/housekeeping/tests/test_dt_cli.py`, replace:

```python
        self.assertTrue(err.startswith("erro:"), err)
```

with:

```python
        self.assertTrue(err.startswith("error:"), err)
```

In `plugins/housekeeping/tests/test_dt_cli.py`, replace:

```python
        self.assertTrue(bad.stderr.startswith("erro:"), bad.stderr)
```

with:

```python
        self.assertTrue(bad.stderr.startswith("error:"), bad.stderr)
```

In `plugins/housekeeping/tests/test_dt_cli.py`, replace:

```python
        self.assertIn("git nao encontrado", r.stderr)
```

with:

```python
        self.assertIn("git not found", r.stderr)
```

In `plugins/housekeeping/tests/test_dt_parity_versions.py`, replace:

```python
        self.assertIn("o titulo 3 difere", found[0]["message"])
```

with:

```python
        self.assertIn("heading 3 differs", found[0]["message"])
```

In `plugins/housekeeping/tests/test_dt_parity_versions.py`, replace:

```python
        self.assertIn("3 titulos contra 2", dt.check_parity(ctx, docs)[0]["message"])
```

with:

```python
        self.assertIn("3 headings against 2", dt.check_parity(ctx, docs)[0]["message"])
```

The new tests: the table, an AST guard over the functions that print, the flag and the environment, the fingerprint that does not move with the language, the singular forms and a bad `--lang`.

Append to `plugins/housekeeping/tests/test_dt_cli.py` (after a blank line):

```python
# ---------------------------------------------------------------- the language of the messages (housekeeping 0.4.0)

import ast
import re
from unittest import mock

PLACEHOLDER = re.compile(r"\{(\w+)\}")
DT_PRINTING = ("git", "repo_root", "tracked_files", "load_config", "check_paths", "check_links", "check_parity",
               "check_versions", "check_plugin_lists", "report", "parser", "main")
DT_PT_WORDS = {"nao", "encontrado", "repositorio", "arquivo", "configuracao", "aninhado", "fundo", "demais", "deve",
               "objeto", "chave", "desconhecida", "lista", "textos", "caminho", "citado", "existe", "aponta", "algo",
               "titulo", "ancora", "versao", "portugues", "niveis", "diferem", "difere", "titulos", "contra", "bate",
               "manifesto", "catalogo", "plugin", "mas", "tem", "documentos", "conferidos", "achados", "limpo",
               "nenhum", "achado", "aceitos", "aceitar", "ponha", "erro", "padrao", "pasta", "saida", "somente",
               "leitura", "confere", "dizem"}


class LanguageTest(CliCase):
    def test_both_tables_have_the_same_keys_and_placeholders_and_are_plain_ascii(self):
        en, pt = dt.MSG["en"], dt.MSG["pt-BR"]
        self.assertEqual(set(en), set(pt))
        for key in en:
            with self.subTest(key=key):
                self.assertEqual(set(PLACEHOLDER.findall(en[key])), set(PLACEHOLDER.findall(pt[key])))
                self.assertTrue(en[key].isascii() and pt[key].isascii(), key)
        self.assertEqual(dt.MSG["pt-BR"]["clean"], "limpo: nenhum achado")  # the pt-BR side is the 0.3.1 output

    def test_no_portuguese_literal_is_left_in_the_functions_that_print(self):
        tree = ast.parse(DOC_TRUTH.read_text(encoding="utf-8"))
        found = []
        for fn in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in DT_PRINTING):
            body = fn.body[1:] if isinstance(fn.body[0], ast.Expr) and isinstance(fn.body[0].value, ast.Constant) else fn.body
            for node in (n for stmt in body for n in ast.walk(stmt)):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value != "falta ":  # a finding's value is data
                    if set(re.split(r"[^a-z]+", node.value.lower())) & DT_PT_WORDS:
                        found.append(f"{fn.name}: {node.value!r}")
        self.assertEqual(found, [], "Portuguese left outside MSG:\n" + "\n".join(found))

    def test_lang_and_the_environment_choose_the_language(self):
        self.docs({"README.md": "# T\n", "README.pt-BR.md": "# T\n"})
        self.assertIn("clean: no findings", run_main([str(self.repo)])[1])
        self.assertIn("doc-truth " + dt.VERSION + ": 2 documentos conferidos em", run_main([str(self.repo), "--lang", "pt-BR"])[1])
        with mock.patch.dict(os.environ, {"CAPYBARA_LANG": "pt-BR"}):
            self.assertIn("limpo: nenhum achado", run_main([str(self.repo)])[1])
            self.assertIn("clean: no findings", run_main([str(self.repo), "--lang", "en"])[1])
        with mock.patch.dict(os.environ, {"CAPYBARA_LANG": "portugues"}):
            rc, out, err = run_main([str(self.repo)])
        self.assertEqual((rc, err), (0, ""))
        self.assertIn("clean: no findings", out)
        self.assertEqual(dt.CLI_LANG, "en")  # main() put the default back

    def test_a_finding_keeps_its_value_and_fingerprint_in_both_languages(self):
        self.docs({"README.md": "# T\n`gone.md`\n", "docs/x/README.md": "# X\n"})
        en = json.loads(run_main([str(self.repo), "--json"])[1])["findings"]
        pt = json.loads(run_main([str(self.repo), "--json", "--lang", "pt-BR"])[1])["findings"]
        self.assertEqual([(f["value"], f["fingerprint"]) for f in en], [(f["value"], f["fingerprint"]) for f in pt])
        self.assertIn("falta README.pt-BR.md", [f["value"] for f in en])
        self.assertEqual([f["message"] for f in en][:1], ["the cited path does not exist: gone.md"])
        self.assertEqual([f["message"] for f in pt][:1], ["o caminho citado nao existe: gone.md"])

    def test_one_takes_the_singular_form(self):
        self.docs({"README.md": "# T\n`gone.md`\n"})
        out = run_main([str(self.repo)])[1]
        self.assertIn(": 1 document checked in ", out)
        self.assertIn("\n2 findings\n", out)
        out = run_main([str(self.repo), "--lang", "pt-BR"])[1]
        self.assertIn(": 1 documento conferido em ", out)

    def test_an_unknown_lang_is_a_usage_error(self):
        r = subprocess.run([sys.executable, "-I", str(DOC_TRUTH), str(self.repo), "--lang", "xx"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn("invalid choice: 'xx'", r.stderr)
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/housekeeping/tests -p 'test_dt*.py' 2>&1 | tail -n 3`

Expected: `FAILED (` with failures and errors: `dt.MSG` and `dt.CLI_LANG` do not exist, there is no `--lang` and the messages are Portuguese.

- [ ] **Step 4: The table, the helpers and every message through `say()`**

The table goes after the constants, the helpers after the error class; each message keeps its logic and only moves its text:


In `plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py`, replace:

```python
CONFIG_KEYS = ("exclude", "ignore_paths", "allow")

```

with:

```python
CONFIG_KEYS = ("exclude", "ignore_paths", "allow")
LANGS = ("en", "pt-BR")  # languages of the messages (--lang); the first is the default
DEFAULT_LANG = "en"
ENV_LANG = "CAPYBARA_LANG"  # one shell-wide default for every Capybara Toolbox script
CLI_LANG = DEFAULT_LANG  # the language of this run's messages, set by main()

# Every message doc-truth prints or puts in a finding, in both languages. Same keys and {placeholders} in both
# (a test enforces it); both plain ASCII, so the pt-BR side is the accent-free Portuguese of 0.3.1, and a key
# ending in `_1` is the form used when n == 1. A finding's `value` (and so its fingerprint) never depends on the
# language: an `allow` list written in one language keeps working in the other.
MSG = {
    "en": {
        "git_missing": "git not found ({e})", "not_repo": "{path} is not a git repository",
        "cfg_missing": "{path}: configuration file not found", "cfg_deep": "{path}: JSON nested too deep",
        "cfg_obj": "{path}: must be a JSON object", "cfg_key": "{path}: unknown key '{key}' (use {keys})",
        "cfg_list": "{path}: '{key}' must be a list of strings",
        "m_path": "the cited path does not exist: {tok}", "m_link": "the link points to something that does not exist: {target}",
        "m_anchor": "no heading for the anchor: {value}", "m_no_pt": "{rel} has no Portuguese version ({name})",
        "m_levels": "the heading levels of {rel} and {pt} differ ({where})", "where_heading": "heading {i} differs",
        "where_count": "{n} headings against {b}", "where_count_1": "{n} heading against {b}",
        "m_version": "version {v} does not match the manifest ({expected})",
        "m_plugins": "the catalog has the plugin {name}, but {rel} has no link to plugins/{name}",
        "checked": "doc-truth {version}: {n} documents checked in {root}",
        "checked_1": "doc-truth {version}: {n} document checked in {root}",
        "findings": "{n} findings", "findings_1": "{n} finding", "clean": "clean: no findings",
        "accepted": "({n} accepted by the allow list)", "accepted_1": "({n} accepted by the allow list)",
        "how_to_accept": 'To accept a finding, put its fingerprint in "allow" in {config}.', "error": "error: {e}",
    },
    "pt-BR": {
        "git_missing": "git nao encontrado ({e})", "not_repo": "{path} nao e um repositorio git",
        "cfg_missing": "{path}: arquivo de configuracao nao encontrado", "cfg_deep": "{path}: JSON aninhado fundo demais",
        "cfg_obj": "{path}: deve ser um objeto JSON", "cfg_key": "{path}: chave desconhecida '{key}' (use {keys})",
        "cfg_list": "{path}: '{key}' deve ser uma lista de textos",
        "m_path": "o caminho citado nao existe: {tok}", "m_link": "o link aponta para algo que nao existe: {target}",
        "m_anchor": "nao ha titulo para a ancora: {value}", "m_no_pt": "{rel} nao tem a versao em portugues ({name})",
        "m_levels": "os niveis de titulo de {rel} e {pt} diferem ({where})", "where_heading": "o titulo {i} difere",
        "where_count": "{n} titulos contra {b}", "where_count_1": "{n} titulo contra {b}",
        "m_version": "a versao {v} nao bate com o manifesto ({expected})",
        "m_plugins": "o catalogo tem o plugin {name}, mas {rel} nao tem link para plugins/{name}",
        "checked": "doc-truth {version}: {n} documentos conferidos em {root}",
        "checked_1": "doc-truth {version}: {n} documento conferido em {root}",
        "findings": "{n} achados", "findings_1": "{n} achado", "clean": "limpo: nenhum achado",
        "accepted": "({n} aceitos pela lista allow)", "accepted_1": "({n} aceito pela lista allow)",
        "how_to_accept": 'Para aceitar um achado, ponha o fingerprint em "allow" em {config}.', "error": "erro: {e}",
    },
}

```

In `plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py`, replace:

```python
class DocTruthError(Exception):
    """Something the person must fix before the check can run (exit code 2)."""

```

with:

```python
class DocTruthError(Exception):
    """Something the person must fix before the check can run (exit code 2)."""


def env_lang():
    """CAPYBARA_LANG when it is exactly one of LANGS. Any other value is ignored, silently: a shell setting must
    never break a command, and a warning on every run would be noise in the agent's context."""
    value = os.environ.get(ENV_LANG)
    return value if value in LANGS else None


def pick_lang(*candidates):
    """The first candidate that is one of LANGS (--lang), then CAPYBARA_LANG, then English."""
    for cand in candidates:
        if isinstance(cand, str) and cand in LANGS:
            return cand
    return env_lang() or DEFAULT_LANG


def use_lang(*candidates):
    """Set the language of this run's messages (see pick_lang) and return it."""
    global CLI_LANG
    CLI_LANG = pick_lang(*candidates)
    return CLI_LANG


def say(msg_id, /, **values):
    """One message in the language of this run; with n == 1 the `_1` form wins when there is one. The template is
    ours, the values are data (substituted, never parsed)."""
    table = MSG[CLI_LANG]
    if values.get("n") == 1 and msg_id + "_1" in table:
        msg_id += "_1"
    return table[msg_id].format(**values)

```

In `plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py`, replace:

```python
raise DocTruthError(f"git nao encontrado ({e.strerror or e})")
```

with:

```python
raise DocTruthError(say("git_missing", e=e.strerror or e))
```

In `plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py`, replace:

```python
    if r.returncode != 0:
        raise DocTruthError(f"{path} nao e um repositorio git")
```

with:

```python
    if r.returncode != 0:
        raise DocTruthError(say("not_repo", path=path))
```

In `plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py`, replace:

```python
        raise DocTruthError(f"{root} nao e um repositorio git")
```

with:

```python
        raise DocTruthError(say("not_repo", path=root))
```

In `plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py`, replace:

```python
raise DocTruthError(f"{path}: arquivo de configuracao nao encontrado")
```

with:

```python
raise DocTruthError(say("cfg_missing", path=path))
```

In `plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py`, replace:

```python
raise DocTruthError(f"{path}: JSON aninhado fundo demais")
```

with:

```python
raise DocTruthError(say("cfg_deep", path=path))
```

In `plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py`, replace:

```python
raise DocTruthError(f"{path}: deve ser um objeto JSON")
```

with:

```python
raise DocTruthError(say("cfg_obj", path=path))
```

In `plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py`, replace:

```python
raise DocTruthError(f"{path}: chave desconhecida '{key}' (use {', '.join(CONFIG_KEYS)})")
```

with:

```python
raise DocTruthError(say("cfg_key", path=path, key=key, keys=", ".join(CONFIG_KEYS)))
```

In `plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py`, replace:

```python
raise DocTruthError(f"{path}: '{key}' deve ser uma lista de textos")
```

with:

```python
raise DocTruthError(say("cfg_list", path=path, key=key))
```

In `plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py`, replace:

```python
out.append(finding("path", document, line, tok, f"o caminho citado nao existe: {tok}"))
```

with:

```python
out.append(finding("path", document, line, tok, say("m_path", tok=tok)))
```

In `plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py`, replace:

```python
out.append(finding("link", document, line, target, f"o link aponta para algo que nao existe: {target}"))
```

with:

```python
out.append(finding("link", document, line, target, say("m_link", target=target)))
```

In `plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py`, replace:

```python
out.append(finding("anchor", document, line, value, f"nao ha titulo para a ancora: {value}"))
```

with:

```python
out.append(finding("anchor", document, line, value, say("m_anchor", value=value)))
```

In `plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py`, replace:

```python
                out.append(finding("parity", rel, 1, "falta " + posixpath.basename(pt),
                                   f"{rel} nao tem a versao em portugues ({posixpath.basename(pt)})"))
```

with:

```python
                out.append(finding("parity", rel, 1, "falta " + posixpath.basename(pt),  # the value is data: same in both languages
                                   say("m_no_pt", rel=rel, name=posixpath.basename(pt))))
```

In `plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py`, replace:

```python
        where = f"o titulo {i + 1} difere" if i < min(len(a), len(b)) else f"{len(a)} titulos contra {len(b)}"
        out.append(finding("parity", rel, 1, ",".join(map(str, a)) + "|" + ",".join(map(str, b)),
                           f"os niveis de titulo de {rel} e {pt} diferem ({where})"))
```

with:

```python
        where = say("where_heading", i=i + 1) if i < min(len(a), len(b)) else say("where_count", n=len(a), b=len(b))
        out.append(finding("parity", rel, 1, ",".join(map(str, a)) + "|" + ",".join(map(str, b)),
                           say("m_levels", rel=rel, pt=pt, where=where)))
```

In `plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py`, replace:

```python
out.append(finding("version", rel, line, value, f"a versao {v} nao bate com o manifesto ({expected})"))
```

with:

```python
out.append(finding("version", rel, line, value, say("m_version", v=v, expected=expected)))
```

In `plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py`, replace:

```python
out.append(finding("plugins", rel, 1, name, f"o catalogo tem o plugin {name}, mas {rel} nao tem link para plugins/{name}"))
```

with:

```python
out.append(finding("plugins", rel, 1, name, say("m_plugins", name=name, rel=rel)))
```

In `plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py`, replace:

```python
    lines = [f"doc-truth {result['version']}: {result['documents']} documentos conferidos em {result['root']}"]
    kept = result["findings"]
    lines.append(f"{len(kept)} achados" if kept else "limpo: nenhum achado")
```

with:

```python
    lines = [say("checked", version=result["version"], n=result["documents"], root=result["root"])]
    kept = result["findings"]
    lines.append(say("findings", n=len(kept)) if kept else say("clean"))
```

In `plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py`, replace:

```python
        lines.append(f"({result['accepted']} aceitos pela lista allow)")
    if kept:
        lines += ["", f'Para aceitar um achado, ponha o fingerprint em "allow" em {CONFIG_NAME}.']
```

with:

```python
        lines.append(say("accepted", n=result["accepted"]))
    if kept:
        lines += ["", say("how_to_accept", config=CONFIG_NAME)]
```

In `plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py`, replace:

```python
    p = argparse.ArgumentParser(prog="doc_truth.py", description="Confere se o que os documentos de um repositorio dizem existe (somente leitura).")
    p.add_argument("path", nargs="?", default=".", help="o repositorio (padrao: a pasta atual)")
    p.add_argument("--json", action="store_true", help="saida em JSON (campo schema)")
    p.add_argument("--config", help=f"arquivo de configuracao (padrao: {CONFIG_NAME} na raiz do repositorio)")
```

with:

```python
    p = argparse.ArgumentParser(prog="doc_truth.py", description="Checks that what a repository's documents say exists (read-only).")
    p.add_argument("path", nargs="?", default=".", help="the repository (default: the current folder)")
    p.add_argument("--json", action="store_true", help="JSON output (schema field)")
    p.add_argument("--config", help=f"configuration file (default: {CONFIG_NAME} at the repository root)")
    p.add_argument("--lang", choices=LANGS, default=None, help="language of the messages (default: CAPYBARA_LANG, then en)")
```

In `plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py`, replace:

```python
def main(argv=None):
    args = parser().parse_args(argv)
    try:
        root = repo_root(args.path)
        config = load_config(root, args.config)
        result = run(root, config)
    except DocTruthError as e:
        print(f"erro: {e}", file=sys.stderr)
        return 2
    except (OSError, UnicodeError, RecursionError) as e:  # a safety net: no failure path may end in a traceback and exit 1
        print(f"erro: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else report(result))
    return 1 if result["findings"] else 0
```

with:

```python
def main(argv=None):
    """Run the check. The language of the messages is set here (--lang, then CAPYBARA_LANG, then en) and put back
    afterwards, so an in-process caller (the tests) never inherits the language of another run."""
    global CLI_LANG
    args = parser().parse_args(argv)
    before = CLI_LANG
    use_lang(args.lang)
    try:
        try:
            root = repo_root(args.path)
            config = load_config(root, args.config)
            result = run(root, config)
        except DocTruthError as e:
            print(say("error", e=e), file=sys.stderr)
            return 2
        except (OSError, UnicodeError, RecursionError) as e:  # a safety net: no failure path may end in a traceback and exit 1
            print(say("error", e=f"{type(e).__name__}: {e}"), file=sys.stderr)
            return 2
        print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else report(result))
        return 1 if result["findings"] else 0
    finally:
        CLI_LANG = before
```

- [ ] **Step 5: Run the suite and the tool on this repository**

Run: `git add -A && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/housekeeping/tests 2>&1 | tail -n 3 && python3 -I plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py . | tail -n 1 && python3 -I plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py . --lang pt-BR | tail -n 1`

Expected: `Ran 399 tests` and `OK`, then `clean: no findings` and `limpo: nenhum achado`.

- [ ] **Step 6: Commit**

Run:

```bash
git add -A
git commit -m "feat(doc-truth): messages in English by default or pt-BR with --lang" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

Expected: one commit (git status --short is empty afterwards).

### Task 5c: handoff: the note and the messages in English or pt-BR, `--lang`

**Files:**
- Modify: `plugins/housekeeping/skills/handoff/scripts/handoff.py` (`LANGS`, `NOTE`, `MSG` after the constants; the language helpers after the error class; every message through `say()`, every fixed text of a note through `note_text()`; `UNVERIFIED`, `SECTIONS`, `META_TITLE`, `META_RESERVED`, `META_EXPECTED`, `META_PART`, `GIT_PART` cover both languages; `mark_unverified`, `meta_rows`, `meta_section`, `missing_meta`, `git_section`, `missing_sections`, `render_note`, `write_note` take the note's language; `tool_spans` recognises a note in either language; `--lang` on every command; `main` and a new `run_command`)
- Modify: `plugins/housekeeping/tests/test_ho_core.py`, `test_ho_citations.py`, `test_ho_notes.py`, `test_ho_cli.py`, `test_skills.py`
- Replace: `plugins/housekeeping/skills/handoff/examples/note.example.md` (the example follows the new default: an English note)

**Interfaces:**
- Consumes: the helpers' design of Task 5b (`CAPYBARA_LANG`, `CLI_LANG` set only by `main`, `say(msg_id, /, **values)`).
- Produces: `NOTE` (the fixed texts of a note per language; the pt-BR side is byte for byte what 0.3.1 wrote, so **every note written before 0.4.0 is a pt-BR note**), `MSG`, `note_text(lang, key, **values)`; `UNVERIFIED`, `SECTIONS`, `META_TITLE` and `META_EXPECTED` become `{lang: ...}` dicts, `META_RESERVED` holds the tool's row keys of both languages; `write_note(root, draft, out_dir=None, base=None, lang=DEFAULT_LANG)`, `git_section(facts, lang=DEFAULT_LANG)`, `meta_section(rows, lang=DEFAULT_LANG)`, `mark_unverified(text, results, lang=DEFAULT_LANG)`, `missing_meta(rows, lang=DEFAULT_LANG)`, `missing_sections(draft, lang=DEFAULT_LANG)`; the data block of a new note records `"lang"` (a block without it is read as pt-BR); `--lang {en,pt-BR}` on `collect`, `write`, `verify` and `resume`.
- The rules (see the rulings): the note is written in the language of the `write` run (`--lang`, then `CAPYBARA_LANG`, then `en`); the agent's metainfo keys (`Model`/`Modelo`, `Original request`/`Pedido original`, `Status`) and section headings (`What was done`/`O que foi feito`, `Decisions and why`/`Decisoes e por que`, `Next steps`/`Proximos passos`, `What failed or got stuck`/`O que falhou ou travou`) count in either language, and a missing one is named in the note's language; the tool's own row keys are reserved in both languages; a citation already marked in either language is never marked again; `resume` and `verify` mask the tool's parts of a note in either language, with or without the data block; a note never sets the language of a run (an old note is Portuguese and must not turn an English session's output Portuguese).
- Consumed by Task 5d (the release) and Task 6 (the handoff skill tells the agent which keys and headings to write).

- [ ] **Step 1: Update the tests that pin the old text**

The note-format tests of `test_ho_notes.py` pin the exact layout of a pt-BR note, which is also the layout of every note written before this change: their helper now writes pt-BR notes explicitly, so they stay the backward-compatibility suite, and `EnglishNoteTest` (Step 2) pins the English default. Every command-line message they or the other files pin is English now.


In `plugins/housekeeping/tests/test_ho_core.py`, replace:

```python
        self.assertIn("git nao encontrado", str(ctx.exception))
```

with:

```python
        self.assertIn("git not found", str(ctx.exception))
```

In `plugins/housekeeping/tests/test_ho_citations.py`, replace:

```python
    def test_a_commit_that_does_not_exist(self):
        ok, sha, why = self.check("commit", "1234567")
        self.assertEqual((ok, sha), (False, None))
        self.assertIn("nao existe", why)
```

with:

```python
    def test_a_commit_that_does_not_exist(self):
        ok, sha, why = self.check("commit", "1234567")
        self.assertEqual((ok, sha), (False, None))
        self.assertIn("does not exist", why)
```

In `plugins/housekeeping/tests/test_ho_citations.py`, replace:

```python
        ok, _sha, why = self.check("file", "src/gone.py")
        self.assertFalse(ok)
        self.assertIn("nao existe", why)
```

with:

```python
        ok, _sha, why = self.check("file", "src/gone.py")
        self.assertFalse(ok)
        self.assertIn("does not exist", why)
```

In `plugins/housekeeping/tests/test_ho_citations.py`, replace:

```python
                self.assertIn("relativo", why)
```

with:

```python
                self.assertIn("relative to the repository root", why)
```

In `plugins/housekeeping/tests/test_ho_citations.py`, replace:

```python
        self.assertIn("sai do repositorio", why)
```

with:

```python
        self.assertIn("leaves the repository", why)
```

In `plugins/housekeeping/tests/test_ho_citations.py`, replace:

```python
        marked = ho.mark_unverified(text, ho.check_text(self.repo, text))
        self.assertEqual(marked, "Fixed `commit:%s` and `file:src/gone.py` [nao verificado] (see `branch:ghost` [nao verificado]).\n" % self.first[:7])
        again = ho.mark_unverified(marked, ho.check_text(self.repo, marked))
        self.assertEqual(again, marked)  # idempotent
```

with:

```python
        marked = ho.mark_unverified(text, ho.check_text(self.repo, text))
        self.assertEqual(marked, "Fixed `commit:%s` and `file:src/gone.py` [not verified] (see `branch:ghost` [not verified]).\n" % self.first[:7])
        again = ho.mark_unverified(marked, ho.check_text(self.repo, marked))
        self.assertEqual(again, marked)  # idempotent
        pt = ho.mark_unverified(text, ho.check_text(self.repo, text), "pt-BR")
        self.assertEqual(pt, "Fixed `commit:%s` and `file:src/gone.py` [nao verificado] (see `branch:ghost` [nao verificado]).\n" % self.first[:7])
        self.assertEqual(ho.mark_unverified(pt, ho.check_text(self.repo, pt)), pt)  # a mark in the other language counts
```

In `plugins/housekeeping/tests/test_ho_citations.py`, replace:

```python
        self.assertEqual(marked.count(ho.UNVERIFIED), 4)
```

with:

```python
        self.assertEqual(marked.count(ho.UNVERIFIED["en"]), 4)
```

In `plugins/housekeeping/tests/test_ho_notes.py`, replace:

```python
    def write(self, draft=None, **kw):
        return ho.write_note(self.repo, self.draft() if draft is None else draft, **kw)
```

with:

```python
    def write(self, draft=None, **kw):
        """A pt-BR note: these tests pin the layout every note written before 0.4.0 has, which is the pt-BR layout.
        EnglishNoteTest pins the English default."""
        kw.setdefault("lang", "pt-BR")
        return ho.write_note(self.repo, self.draft() if draft is None else draft, **kw)
```

In `plugins/housekeeping/tests/test_ho_notes.py`, replace:

```python
        self.assertIn("link simbolico", str(ctx.exception))
```

with:

```python
        self.assertIn("symbolic link", str(ctx.exception))
```

In `plugins/housekeeping/tests/test_ho_notes.py`, replace:

```python
        self.assertTrue(any("a ponta de main mudou" in m and "(1 commits novos)" in m for m in res["drift"]), res["drift"])
```

with:

```python
        self.assertTrue(any("the tip of main moved" in m and "(1 new commit)" in m for m in res["drift"]), res["drift"])
```

In `plugins/housekeeping/tests/test_ho_notes.py`, replace:

```python
        self.assertTrue(any("arquivos sujos novos: fresh.txt" in m or "fresh.txt" in m for m in res["drift"]))
```

with:

```python
        self.assertTrue(any("new dirty files: fresh.txt" in m for m in res["drift"]), res["drift"])
```

In `plugins/housekeeping/tests/test_ho_notes.py`, replace:

```python
        self.assertTrue(any("a branch era main e agora e other" in m for m in drift), drift)
        self.assertTrue(any("a frente/atras da base mudou: 0/0 -> 1/0" in m for m in drift), drift)
```

with:

```python
        self.assertTrue(any("the branch was main and is now other" in m for m in drift), drift)
        self.assertTrue(any("ahead/behind the base changed: 0/0 -> 1/0" in m for m in drift), drift)
```

In `plugins/housekeeping/tests/test_ho_notes.py`, replace:

```python
        self.assertIn("pasta", str(ctx.exception))
```

with:

```python
        self.assertIn("could not create the notes folder", str(ctx.exception))
```

In `plugins/housekeeping/tests/test_ho_notes.py`, replace:

```python
        self.assertIn("nao consegui ler", str(ctx.exception))
```

with:

```python
        self.assertIn("could not read the note", str(ctx.exception))
```

In `plugins/housekeeping/tests/test_ho_notes.py`, replace:

```python
        self.assertIn("linha 3", str(cm.exception))
```

with:

```python
        self.assertIn("line 3", str(cm.exception))
```

In `plugins/housekeeping/tests/test_ho_notes.py`, replace:

```python
        text = Path(ho.write_note(odd, "## O que foi feito\nx\n")["path"]).read_text(encoding="utf-8")
```

with:

```python
        text = Path(ho.write_note(odd, "## O que foi feito\nx\n", lang="pt-BR")["path"]).read_text(encoding="utf-8")
```

In `plugins/housekeeping/tests/test_ho_notes.py`, replace:

```python
        old = ("# Handoff - 2026-10-14 09:05 - main\n\n" + ho.git_section(facts) + "\n\n## O que foi feito\n`file:src/a.py`\n\n"
```

with:

```python
        old = ("# Handoff - 2026-10-14 09:05 - main\n\n" + ho.git_section(facts, "pt-BR") + "\n\n## O que foi feito\n`file:src/a.py`\n\n"
```

In `plugins/housekeeping/tests/test_ho_cli.py`, replace:

```python
        self.assertIn("## Estado do git", out)
```

with:

```python
        self.assertIn("## Git state", out)
        self.assertIn("## Estado do git", run_main(["collect", str(self.repo), "--lang", "pt-BR"])[1])
```

In `plugins/housekeeping/tests/test_ho_cli.py`, replace:

```python
        self.assertIn("aviso: falta a metainfo 'Pedido original'", out)
        self.assertNotIn("aviso: falta a metainfo 'Modelo'", out)
        note = Path(out.split("nota gravada em ")[1].splitlines()[0]).read_text(encoding="utf-8")
        self.assertIn("| Modelo | Claude Sonnet 5.5 |", note)
        rc, out, _ = run_main(["write", str(self.repo), "--draft", self.draft_file(draft), "--json"])
        self.assertEqual(json.loads(out)["missing_meta"], ["Pedido original"])
```

with:

```python
        self.assertIn("warning: metainfo 'Original request' is missing", out)  # a pt-BR key counts in an English note
        self.assertNotIn("warning: metainfo 'Model' is missing", out)
        note = Path(out.split("note saved to ")[1].splitlines()[0]).read_text(encoding="utf-8")
        self.assertIn("| Modelo | Claude Sonnet 5.5 |", note)  # the agent's key is kept as written
        rc, out, _ = run_main(["write", str(self.repo), "--draft", self.draft_file(draft), "--json"])
        self.assertEqual(json.loads(out)["missing_meta"], ["Original request"])
        rc, out, _ = run_main(["write", str(self.repo), "--draft", self.draft_file(draft), "--json", "--lang", "pt-BR"])
        self.assertEqual(json.loads(out)["missing_meta"], ["Pedido original"])
```

In `plugins/housekeeping/tests/test_ho_cli.py`, replace:

```python
        self.assertIn("erro: metainfo invalida na linha 2", err)
```

with:

```python
        self.assertIn("error: invalid metainfo on line 2", err)
```

In `plugins/housekeeping/tests/test_ho_cli.py`, replace:

```python
        self.assertIn("nota gravada em", out)
        self.assertIn("1 citacoes, 0 nao verificadas", out)
        self.assertIn("aviso: falta a secao 'Proximos passos'", out)
```

with:

```python
        self.assertIn("note saved to", out)
        self.assertIn("1 citation, 0 not verified", out)
        self.assertIn("warning: section 'Next steps' is missing", out)
```

In `plugins/housekeeping/tests/test_ho_cli.py`, replace:

```python
        self.assertIn("linha 2: branch:ghost  NAO VERIFICADO", out)
```

with:

```python
        self.assertIn("line 2: branch:ghost  NOT VERIFIED", out)
```

In `plugins/housekeeping/tests/test_ho_cli.py`, replace:

```python
        self.assertIn("nao consegui ler o rascunho", err)
```

with:

```python
        self.assertIn("could not read the draft", err)
```

In `plugins/housekeeping/tests/test_ho_cli.py`, replace:

```python
        self.assertIn("2 citacoes, 1 nao verificadas", out)
        self.assertIn("nope.py  NAO VERIFICADO", out)
```

with:

```python
        self.assertIn("2 citations, 1 not verified", out)
        self.assertIn("nope.py  NOT VERIFIED", out)
```

In `plugins/housekeeping/tests/test_ho_cli.py`, replace:

```python
        self.assertIn("nada mudou no git desde a nota", out)
        commit(self.repo, "later", {"b.txt": "b\n"})
        rc, out, _ = run_main(["resume", str(self.repo)])
        self.assertEqual(rc, 1)
        self.assertIn("mudou desde a nota:", out)
        self.assertIn("MUDOU (a ponta e outra)", out)
```

with:

```python
        self.assertIn("nothing changed in git since the note", out)
        commit(self.repo, "later", {"b.txt": "b\n"})
        rc, out, _ = run_main(["resume", str(self.repo)])
        self.assertEqual(rc, 1)
        self.assertIn("changed since the note:", out)
        self.assertIn("MOVED (the tip is another)", out)
```

In `plugins/housekeeping/tests/test_ho_cli.py`, replace:

```python
        self.assertIn("nao ha nota", err)
```

with:

```python
        self.assertIn("there is no note", err)
```

In `plugins/housekeeping/tests/test_ho_cli.py`, replace:

```python
    def assert_clean_error(self, argv, stdin=None, needle="erro:"):
```

with:

```python
    def assert_clean_error(self, argv, stdin=None, needle="error:"):
```

In `plugins/housekeeping/tests/test_ho_cli.py`, replace:

```python
        self.assert_clean_error(["verify", str(note), str(self.repo)], needle="nao consegui ler")
        self.assert_clean_error(["resume", str(self.repo)], needle="nao consegui ler")
```

with:

```python
        self.assert_clean_error(["verify", str(note), str(self.repo)], needle="could not read the note")
        self.assert_clean_error(["resume", str(self.repo), "--lang", "pt-BR"], needle="erro: nao consegui ler a nota")
```

In `plugins/housekeeping/tests/test_ho_cli.py`, replace:

```python
        self.assertIn(b"erro:", r.stderr)
```

with:

```python
        self.assertIn(b"error:", r.stderr)
```

In `plugins/housekeeping/tests/test_ho_cli.py`, replace:

```python
        self.assertIn("1 citacoes, 0 nao verificadas", out)
        rc, out, _ = run_main(["resume", str(self.repo)])
        self.assertEqual(rc, 0, out)
        self.assertIn("nada mudou no git desde a nota", out)
        self.assertIn("1 citacoes, 0 com problema", out)
        note = next((self.repo / ".handoff").glob("*.md"))
        rc, out, _ = run_main(["verify", str(note), str(self.repo)])
        self.assertEqual(rc, 0, out)
        self.assertIn("1 citacoes, 0 nao verificadas", out)
```

with:

```python
        self.assertIn("1 citation, 0 not verified", out)
        rc, out, _ = run_main(["resume", str(self.repo)])
        self.assertEqual(rc, 0, out)
        self.assertIn("nothing changed in git since the note", out)
        self.assertIn("1 citation, 0 with problems", out)
        note = next((self.repo / ".handoff").glob("*.md"))
        rc, out, _ = run_main(["verify", str(note), str(self.repo)])
        self.assertEqual(rc, 0, out)
        self.assertIn("1 citation, 0 not verified", out)
```

In `plugins/housekeeping/tests/test_skills.py`, replace:

```python
        for section in ho.SECTIONS:
            self.assertIn(f"## {section}", text)
```

with:

```python
        self.assertEqual(ho.parse_data(text)["lang"], "en")  # the example follows the default language
        for section in ho.SECTIONS["en"]:
            self.assertIn(f"## {section}", text)
```

In `plugins/housekeeping/tests/test_skills.py`, replace:

```python
        self.assertIn("\n\n" + ho.meta_section(meta) + "\n\n## Estado do git", text)
```

with:

```python
        self.assertIn("\n\n" + ho.meta_section(meta) + "\n\n## Git state", text)
```

- [ ] **Step 2: Write the new tests**

The tables, an AST guard over the functions that print, the English default note, keys and headings in either language, the reserved keys, the masking of the tool's parts in both languages with and without the data block, and a 0.3.1 note without `lang`:


Append to `plugins/housekeeping/tests/test_ho_notes.py` (after a blank line):

```python
# ---------------------------------------------------------------- the note's language (housekeeping 0.4.0)

import ast
import re

PLACEHOLDER = re.compile(r"\{(\w+)\}")
HO_PRINTING = ("git", "repo_root", "detect_base", "commit_by_id", "check_citation", "notes_folder", "clean_meta_text",
               "split_front", "clean_meta", "write_note", "drift", "read_note", "resume", "citation_lines", "parser",
               "read_draft", "main", "run_command")
HO_PT_WORDS = {"nao", "encontrado", "repositorio", "existe", "ambiguo", "citacao", "caracteres", "controle", "invalido",
               "hexadecimais", "nome", "expressao", "revisao", "remota", "caminho", "relativo", "raiz", "sai", "arquivo",
               "arvore", "trabalho", "link", "simbolico", "recuso", "escrever", "ler", "pasta", "metainfo", "invalida",
               "linha", "rascunho", "chave", "valor", "resuma", "repetida", "reservada", "ferramenta", "grava", "tipada",
               "cabecalho", "secao", "cabem", "gravado", "consegui", "criar", "nota", "notas", "gravar",
               "agora", "novos", "antigo", "ponta", "mudou", "frente", "atras", "sujos", "estao", "rode", "primeiro",
               "verificado", "verificadas", "conferencia", "bloco", "dados", "conferidas", "nada", "desde", "erro",
               "estrutura", "funda", "demais", "lida", "cabe", "falha", "leitura", "escrita", "gravada", "citacoes",
               "problema", "aviso", "falta", "fatos", "confere", "mostra", "recente", "padrao", "especifica", "entrada"}


class LanguageTablesTest(unittest.TestCase):
    def test_both_tables_have_the_same_keys_and_placeholders_and_are_plain_ascii(self):
        for table in (ho.NOTE, ho.MSG):
            en, pt = table["en"], table["pt-BR"]
            self.assertEqual(set(en), set(pt))
            for key in en:
                with self.subTest(key=key):
                    a, b = en[key], pt[key]
                    if isinstance(a, tuple):
                        self.assertEqual(len(a), len(b))
                        a, b = " ".join(a), " ".join(b)
                    self.assertEqual(set(PLACEHOLDER.findall(a)), set(PLACEHOLDER.findall(b)))
                    self.assertTrue(a.isascii() and b.isascii(), key)

    def test_the_pt_br_note_texts_are_those_of_0_3_1(self):
        pt = ho.NOTE["pt-BR"]
        self.assertEqual((pt["unverified"], pt["meta_title"], pt["git_title"]), (" [nao verificado]", "Metainfo da sessao", "## Estado do git"))
        self.assertEqual(pt["sections"], ("O que foi feito", "Decisoes e por que", "Proximos passos", "O que falhou ou travou"))
        self.assertEqual(pt["expected"], ("Modelo", "Pedido original", "Status"))
        self.assertEqual((pt["written_at"], pt["repository"]), ("Gravada em", "Repositorio"))

    def test_no_portuguese_literal_is_left_in_the_functions_that_print(self):
        tree = ast.parse(Path(ho.__file__).read_text(encoding="utf-8"))
        found = []
        for fn in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in HO_PRINTING):
            body = fn.body[1:] if isinstance(fn.body[0], ast.Expr) and isinstance(fn.body[0].value, ast.Constant) else fn.body
            for node in (n for stmt in body for n in ast.walk(stmt)):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if set(re.split(r"[^a-z]+", node.value.lower())) & HO_PT_WORDS:
                        found.append(f"{fn.name}: {node.value!r}")
        self.assertEqual(found, [], "Portuguese left outside NOTE and MSG:\n" + "\n".join(found))


class EnglishNoteTest(NoteCase):
    def note(self, draft, **kw):
        res = ho.write_note(self.repo, draft, **kw)
        return res, Path(res["path"]).read_text(encoding="utf-8")

    def test_the_default_note_is_english(self):
        draft = "---\nModel: m\nOriginal request: r\nStatus: s\n---\n## What was done\nFixed `file:src/a.py` and `file:gone.py`.\n"
        res, text = self.note(draft)
        self.assertTrue(text.startswith("# Handoff - 2026-10-14 09:05 - main\n\n| Session metainfo | |\n|---|---|\n| Model | m |\n"))
        self.assertIn("| Written at | 2026-10-14 09:05 |\n| Repository | r |\n\n## Git state\n", text)
        self.assertIn(f"- Branch: main, tip {self.first[:7]}", text)
        self.assertIn("- Against the base main: 0 ahead, 0 behind", text)
        self.assertIn("`file:gone.py` [not verified]", text)
        self.assertNotIn("`file:src/a.py` [not verified]", text)
        self.assertEqual(ho.parse_data(text)["lang"], "en")
        self.assertEqual(res["missing"], ["Decisions and why", "Next steps", "What failed or got stuck"])
        self.assertEqual(res["missing_meta"], [])

    def test_keys_and_headings_count_in_either_language(self):
        draft = "---\nModelo: m\nOriginal request: r\nstatus: s\n---\n## O que foi feito\nx\n## Decisions and why\ny\n"
        res, _ = self.note(draft)
        self.assertEqual(res["missing_meta"], [])
        self.assertEqual(res["missing"], ["Next steps", "What failed or got stuck"])
        res, _ = self.note(draft, lang="pt-BR")
        self.assertEqual(res["missing"], ["Proximos passos", "O que falhou ou travou"])

    def test_the_tools_keys_are_reserved_in_both_languages(self):
        for key in ("Written at", "Repository", "Gravada em", "Repositorio"):
            with self.subTest(key=key), self.assertRaises(ho.HandoffError):
                ho.write_note(self.repo, f"---\n{key}: x\n---\n## What was done\nx\n")

    def test_the_tool_parts_are_masked_in_either_language_with_or_without_the_data_block(self):
        commit(self.repo, "rename `file:old.py` and `branch:nope`", {"b.txt": "b\n"})
        for lang in ("en", "pt-BR"):
            with self.subTest(lang=lang):
                path = Path(ho.write_note(self.repo, "## What was done\n`file:src/a.py`\n", lang=lang)["path"])
                text = path.read_text(encoding="utf-8")
                self.assertEqual([c["value"] for c in ho.check_note(self.repo, text)], ["src/a.py"])
                cut = text[:text.index("<!-- handoff:data")]  # no data block: the patterns of both languages
                self.assertEqual([c["value"] for c in ho.check_note(self.repo, cut)], ["src/a.py"])
                path.unlink()

    def test_a_note_without_lang_in_its_data_block_is_read_as_pt_br(self):
        path = Path(ho.write_note(self.repo, "## O que foi feito\n`file:src/a.py`\n", lang="pt-BR")["path"])
        text = path.read_text(encoding="utf-8")
        self.assertIn('"lang":"pt-BR",', text)
        path.write_text(text.replace('"lang":"pt-BR",', ""), encoding="utf-8")  # what 0.3.1 wrote
        res = ho.resume(self.repo)
        self.assertEqual(([c["value"] for c in res["citations"]], res["drift"]), (["src/a.py"], []))
```

The command line in pt-BR prints the old lines, `CAPYBARA_LANG` is the default, a note does not set the language of `resume`, and every command takes `--lang`:

Append to `plugins/housekeeping/tests/test_ho_cli.py` (after a blank line):

```python
class LanguageCliTest(CliCase):
    def test_write_in_pt_br_prints_the_old_lines_and_writes_a_pt_br_note(self):
        rc, out, _ = run_main(["write", str(self.repo), "--draft", self.draft_file("## O que foi feito\n`branch:ghost`\n"), "--lang", "pt-BR"])
        self.assertEqual(rc, 1)
        self.assertIn("1 citacao, 1 nao verificada", out)
        self.assertIn("linha 2: branch:ghost  NAO VERIFICADO (a branch nao existe (local ou remota))", out)
        self.assertIn("aviso: falta a secao 'Proximos passos'", out)
        note = Path(out.split("nota gravada em ")[1].splitlines()[0]).read_text(encoding="utf-8")
        self.assertIn("`branch:ghost` [nao verificado]", note)
        self.assertIn("| Metainfo da sessao | |", note)

    def test_capybara_lang_is_the_default_and_the_flag_wins(self):
        with mock.patch.dict(os.environ, {"CAPYBARA_LANG": "pt-BR"}):
            self.assertIn("## Estado do git", run_main(["collect", str(self.repo)])[1])
            self.assertIn("## Git state", run_main(["collect", str(self.repo), "--lang", "en"])[1])
        with mock.patch.dict(os.environ, {"CAPYBARA_LANG": "ptbr"}):
            rc, out, err = run_main(["collect", str(self.repo)])
        self.assertEqual((rc, err), (0, ""))
        self.assertIn("## Git state", out)
        self.assertEqual(ho.CLI_LANG, "en")  # main() put the default back

    def test_a_note_does_not_set_the_language_of_resume(self):
        run_main(["write", str(self.repo), "--draft", self.draft_file("## O que foi feito\n`file:src/a.py`\n"), "--lang", "pt-BR"])
        rc, out, _ = run_main(["resume", str(self.repo)])
        self.assertEqual(rc, 0, out)
        self.assertIn("| Metainfo da sessao | |", out)  # the note, as it was written
        self.assertIn("--- checked now ---", out)  # the run's own lines, in the run's language
        self.assertIn("nothing changed in git since the note", out)

    def test_every_command_takes_lang_and_refuses_a_bad_one(self):
        for argv in (["collect"], ["write", "--draft", "x"], ["verify", "f"], ["resume"]):
            with self.subTest(cmd=argv[0]):
                self.assertEqual(ho.parser().parse_args(argv + ["--lang", "pt-BR"]).lang, "pt-BR")
        r = subprocess.run([sys.executable, "-I", str(HANDOFF), "collect", str(self.repo), "--lang", "xx"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn("invalid choice: 'xx'", r.stderr)
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/housekeeping/tests -p 'test_ho*.py' 2>&1 | tail -n 3`

Expected: `FAILED (` with failures and errors: `ho.NOTE`, `ho.MSG` and `write_note(..., lang=)` do not exist and every text is Portuguese.

- [ ] **Step 4: The tables and the helpers**


In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
RECENT = 5  # commits listed in the note

```

with:

```python
RECENT = 5  # commits listed in the note
LANGS = ("en", "pt-BR")  # languages of the note and of the messages (--lang); the first is the default
DEFAULT_LANG = "en"
ENV_LANG = "CAPYBARA_LANG"  # one shell-wide default for every Capybara Toolbox script
CLI_LANG = DEFAULT_LANG  # the language of this run's messages, set by main()

# The fixed texts the tool writes into a note, per language. The pt-BR side is exactly what 0.3.1 wrote (accent-
# free), so every note written before 0.4.0 is a pt-BR note. `resume` and `verify` recognise the tool's parts in
# either language, and the agent's metainfo keys and section headings are accepted in either language too.
NOTE = {
    "en": {
        "unverified": " [not verified]", "meta_title": "Session metainfo", "written_at": "Written at", "repository": "Repository",
        "expected": ("Model", "Original request", "Status"),
        "sections": ("What was done", "Decisions and why", "Next steps", "What failed or got stuck"),
        "git_title": "## Git state", "detached": "detached HEAD", "tip": ", tip {tip}", "no_commits": ", no commits",
        "vs_base": "- Against the base {base}: {ahead} ahead, {behind} behind", "no_base": "- Base: not found",
        "modified": "- Modified files: {n}", "untracked": "- New (untracked) files: {n}", "stashes": "- Stashes: {n}",
        "worktrees": "- Other worktrees: ", "commits": "- Recent commits:", "more": " and {n} more",
    },
    "pt-BR": {
        "unverified": " [nao verificado]", "meta_title": "Metainfo da sessao", "written_at": "Gravada em", "repository": "Repositorio",
        "expected": ("Modelo", "Pedido original", "Status"),
        "sections": ("O que foi feito", "Decisoes e por que", "Proximos passos", "O que falhou ou travou"),
        "git_title": "## Estado do git", "detached": "HEAD solta", "tip": ", ponta {tip}", "no_commits": ", sem commits",
        "vs_base": "- Em relacao a base {base}: {ahead} a frente, {behind} atras", "no_base": "- Base: nao encontrada",
        "modified": "- Arquivos modificados: {n}", "untracked": "- Arquivos novos (nao rastreados): {n}", "stashes": "- Stashes: {n}",
        "worktrees": "- Outros worktrees: ", "commits": "- Commits recentes:", "more": " e mais {n}",
    },
}

# Every message the command line prints, in both languages. Same keys and {placeholders} in both (a test enforces
# it); both plain ASCII, so the pt-BR side is the accent-free Portuguese of 0.3.1, and a key ending in `_1` is the
# form used when n == 1.
MSG = {
    "en": {
        "git_missing": "git not found ({e})", "not_repo": "{path} is not a git repository",
        "no_base": "the base '{base}' does not exist", "ambiguous": "the commit id is ambiguous",
        "no_commit": "the commit does not exist", "control": "the citation has control characters",
        "bad_commit": "invalid commit id (7 to 40 hexadecimal characters)",
        "bad_branch": "invalid branch name (it cannot be a revision expression)",
        "no_branch": "the branch does not exist (local or remote)",
        "not_relative": "the path must be relative to the repository root", "outside": "the path leaves the repository",
        "no_file": "the file does not exist in the working tree",
        "symlink": "{folder} is a symbolic link: I refuse to write or read through it (use --out to choose the folder)",
        "meta_control": "the metainfo has control characters",
        "meta_line": "invalid metainfo on line {line} of the draft: use 'Key: Value', one per line, between two '---'",
        "meta_empty": "the metainfo needs a key and a value",
        "meta_long": "metainfo '{key}': a key of up to {max_key} and a value of up to {max_value} characters (shorten it)",
        "meta_reserved": "metainfo '{key}': repeated or reserved key (the tool writes 'Written at' and 'Repository' itself)",
        "meta_citation": "metainfo '{key}': a typed citation (commit:, branch:, file:) does not go in the header, put it in a section",
        "draft_utf8": "the draft has characters that do not fit in UTF-8: nothing was written",
        "mkdir_failed": "could not create the notes folder {folder}: {e}", "create_failed": "could not create the note in {folder}: {e}",
        "write_failed": "could not write the note {path}: {e}",
        "d_branch": "the branch was {old} and is now {new}", "d_detached": "(detached HEAD)",
        "d_new_commits": " ({n} new commits)", "d_new_commits_1": " ({n} new commit)", "d_old_gone": " (the old commit no longer exists)",
        "d_tip": "the tip of {branch} moved: {old} -> {new}{extra}",
        "d_counts": "ahead/behind the base changed: {a}/{b} -> {c}/{d}",
        "d_gone": "dirty files that are gone: {names}", "d_new": "new dirty files: {names}", "more": " and {n} more",
        "read_failed": "could not read the note {path}: {e}", "no_note": "there is no note in {folder}/ (run `write` first)",
        "not_note": "{path} is not a note file", "not_file": "{path} is not a file",
        "line": "  line {line}: {type}:{value}  {flag}", "f_ok": "ok", "f_unverified": "NOT VERIFIED", "f_moved": "MOVED (the tip is another)",
        "draft_not_utf8": "could not read the draft: it is not valid UTF-8", "draft_failed": "could not read the draft: {e}",
        "saved": "note saved to {path}",
        "n_citations": "{n} citations", "n_citations_1": "{n} citation",
        "n_unverified": "{n} not verified", "n_unverified_1": "{n} not verified",
        "n_problems": "{n} with problems", "n_problems_1": "{n} with a problem",
        "missing_section": "warning: section '{name}' is missing", "missing_meta": "warning: metainfo '{name}' is missing",
        "checked_now": "--- checked now ---", "note": "note: {path}",
        "no_data": "the note has no data block: only the citations were checked",
        "changed": "changed since the note:", "unchanged": "nothing changed in git since the note",
        "error": "error: {e}", "too_deep": "a structure of the note is too deep to read",
        "not_utf8": "text that does not fit in UTF-8 ({e})", "io": "read or write failure ({e})",
    },
    "pt-BR": {
        "git_missing": "git nao encontrado ({e})", "not_repo": "{path} nao e um repositorio git",
        "no_base": "a base '{base}' nao existe", "ambiguous": "o id de commit e ambiguo",
        "no_commit": "o commit nao existe", "control": "a citacao tem caracteres de controle",
        "bad_commit": "id de commit invalido (7 a 40 caracteres hexadecimais)",
        "bad_branch": "nome de branch invalido (nao pode ser uma expressao de revisao)",
        "no_branch": "a branch nao existe (local ou remota)",
        "not_relative": "o caminho deve ser relativo a raiz do repositorio", "outside": "o caminho sai do repositorio",
        "no_file": "o arquivo nao existe na arvore de trabalho",
        "symlink": "{folder} e um link simbolico: recuso escrever ou ler por ele (use --out para escolher a pasta)",
        "meta_control": "a metainfo tem caracteres de controle",
        "meta_line": "metainfo invalida na linha {line} do rascunho: use 'Chave: Valor', uma por linha, entre dois '---'",
        "meta_empty": "a metainfo precisa de chave e valor",
        "meta_long": "metainfo '{key}': chave de ate {max_key} e valor de ate {max_value} caracteres (resuma)",
        "meta_reserved": "metainfo '{key}': chave repetida ou reservada (a ferramenta ja grava 'Gravada em' e 'Repositorio')",
        "meta_citation": "metainfo '{key}': citacao tipada (commit:, branch:, file:) nao entra no cabecalho, ponha-a numa secao",
        "draft_utf8": "o rascunho tem caracteres que nao cabem em UTF-8: nada foi gravado",
        "mkdir_failed": "nao consegui criar a pasta das notas {folder}: {e}", "create_failed": "nao consegui criar a nota em {folder}: {e}",
        "write_failed": "nao consegui gravar a nota {path}: {e}",
        "d_branch": "a branch era {old} e agora e {new}", "d_detached": "(HEAD solta)",
        "d_new_commits": " ({n} commits novos)", "d_new_commits_1": " ({n} commit novo)", "d_old_gone": " (o commit antigo nao existe mais)",
        "d_tip": "a ponta de {branch} mudou: {old} -> {new}{extra}",
        "d_counts": "a frente/atras da base mudou: {a}/{b} -> {c}/{d}",
        "d_gone": "arquivos sujos que ja nao estao: {names}", "d_new": "arquivos sujos novos: {names}", "more": " e mais {n}",
        "read_failed": "nao consegui ler a nota {path}: {e}", "no_note": "nao ha nota em {folder}/ (rode `write` primeiro)",
        "not_note": "{path} nao e um arquivo de nota", "not_file": "{path} nao e um arquivo",
        "line": "  linha {line}: {type}:{value}  {flag}", "f_ok": "ok", "f_unverified": "NAO VERIFICADO", "f_moved": "MUDOU (a ponta e outra)",
        "draft_not_utf8": "nao consegui ler o rascunho: nao e UTF-8 valido", "draft_failed": "nao consegui ler o rascunho: {e}",
        "saved": "nota gravada em {path}",
        "n_citations": "{n} citacoes", "n_citations_1": "{n} citacao",
        "n_unverified": "{n} nao verificadas", "n_unverified_1": "{n} nao verificada",
        "n_problems": "{n} com problema", "n_problems_1": "{n} com problema",
        "missing_section": "aviso: falta a secao '{name}'", "missing_meta": "aviso: falta a metainfo '{name}'",
        "checked_now": "--- conferencia agora ---", "note": "nota: {path}",
        "no_data": "a nota nao tem o bloco de dados: so as citacoes foram conferidas",
        "changed": "mudou desde a nota:", "unchanged": "nada mudou no git desde a nota",
        "error": "erro: {e}", "too_deep": "uma estrutura da nota e funda demais para ser lida",
        "not_utf8": "texto que nao cabe em UTF-8 ({e})", "io": "falha de leitura ou escrita ({e})",
    },
}

```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
class HandoffError(Exception):
    """Something the person must fix before the tool can run (exit code 2)."""

```

with:

```python
class HandoffError(Exception):
    """Something the person must fix before the tool can run (exit code 2)."""


def env_lang():
    """CAPYBARA_LANG when it is exactly one of LANGS. Any other value is ignored, silently: a shell setting must
    never break a command, and a warning on every run would be noise in the agent's context."""
    value = os.environ.get(ENV_LANG)
    return value if value in LANGS else None


def pick_lang(*candidates):
    """The first candidate that is one of LANGS (--lang), then CAPYBARA_LANG, then English. A note never sets the
    language of a run: an old note is Portuguese, and it must not turn an English session's output Portuguese."""
    for cand in candidates:
        if isinstance(cand, str) and cand in LANGS:
            return cand
    return env_lang() or DEFAULT_LANG


def use_lang(*candidates):
    """Set the language of this run's messages (see pick_lang) and return it."""
    global CLI_LANG
    CLI_LANG = pick_lang(*candidates)
    return CLI_LANG


def say(msg_id, /, **values):
    """One message in the language of this run; with n == 1 the `_1` form wins when there is one. The template is
    ours, the values are data (substituted, never parsed)."""
    table = MSG[CLI_LANG]
    if values.get("n") == 1 and msg_id + "_1" in table:
        msg_id += "_1"
    return table[msg_id].format(**values)


def note_text(lang, key, **values):
    """One fixed text of a note in `lang` (an unknown language is English)."""
    text = NOTE[lang if lang in LANGS else DEFAULT_LANG][key]
    return text.format(**values) if values else text

```

- [ ] **Step 5: Every message through `say()`, every fixed text of a note through `note_text()`**

Each function keeps its logic; the text moves to the tables, the note functions take the note's language, and the patterns that find the tool's parts of a note accept both languages:


In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
raise HandoffError(f"git nao encontrado ({e.strerror or e})")
```

with:

```python
raise HandoffError(say("git_missing", e=e.strerror or e))
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
raise HandoffError(f"{path} nao e um repositorio git")
```

with:

```python
raise HandoffError(say("not_repo", path=path))
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
raise HandoffError(f"a base '{override}' nao existe")
```

with:

```python
raise HandoffError(say("no_base", base=override))
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
UNVERIFIED = " [nao verificado]"
```

with:

```python
UNVERIFIED = {lang: NOTE[lang]["unverified"] for lang in LANGS}
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
    return None, ("o id de commit e ambiguo" if commits else "o commit nao existe")
```

with:

```python
    return None, say("ambiguous" if commits else "no_commit")
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
return False, None, "a citacao tem caracteres de controle"
```

with:

```python
return False, None, say("control")
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
return False, None, "id de commit invalido (7 a 40 caracteres hexadecimais)"
```

with:

```python
return False, None, say("bad_commit")
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
return False, None, "nome de branch invalido (nao pode ser uma expressao de revisao)"
```

with:

```python
return False, None, say("bad_branch")
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
return False, None, "a branch nao existe (local ou remota)"
```

with:

```python
return False, None, say("no_branch")
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
return False, None, "o caminho deve ser relativo a raiz do repositorio"
```

with:

```python
return False, None, say("not_relative")
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
return False, None, "o caminho sai do repositorio"
```

with:

```python
return False, None, say("outside")
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
return ((True, None, "") if target.exists() else (False, None, "o arquivo nao existe na arvore de trabalho"))
```

with:

```python
return ((True, None, "") if target.exists() else (False, None, say("no_file")))
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
def mark_unverified(text, results):
    """Append ` [nao verificado]` after each citation that failed, once: a note is never marked twice and no
    text is ever removed."""
    out, last = [], 0
    for r in results:
        out.append(text[last:r["end"]])
        last = r["end"]
        if not r["verified"] and not text.startswith(UNVERIFIED, r["end"]):
            out.append(UNVERIFIED)
```

with:

```python
def mark_unverified(text, results, lang=DEFAULT_LANG):
    """Append ` [not verified]` (pt-BR ` [nao verificado]`) after each citation that failed, once: a citation
    already marked in either language is never marked again and no text is ever removed."""
    out, last = [], 0
    for r in results:
        out.append(text[last:r["end"]])
        last = r["end"]
        if not r["verified"] and not any(text.startswith(mark, r["end"]) for mark in UNVERIFIED.values()):
            out.append(UNVERIFIED[lang if lang in LANGS else DEFAULT_LANG])
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
SECTIONS = ("O que foi feito", "Decisoes e por que", "Proximos passos", "O que falhou ou travou")
```

with:

```python
SECTIONS = {lang: NOTE[lang]["sections"] for lang in LANGS}  # the draft's headings: either language counts
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
        raise HandoffError(f"{folder} e um link simbolico: recuso escrever ou ler por ele (use --out para escolher a pasta)")
```

with:

```python
        raise HandoffError(say("symlink", folder=folder))
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
def names(items):
    shown = ", ".join(items[:SHOWN])
    return shown + (f" e mais {len(items) - SHOWN}" if len(items) > SHOWN else "")
```

with:

```python
def names(items, lang=None):
    """Up to SHOWN names; `lang` is a note's language, None the language of this run's messages."""
    shown = ", ".join(items[:SHOWN])
    if len(items) <= SHOWN:
        return shown
    return shown + (note_text(lang, "more", n=len(items) - SHOWN) if lang else say("more", n=len(items) - SHOWN))
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
META_TITLE = "Metainfo da sessao"
META_RESERVED = ("gravada em", "repositorio")  # rows the tool writes itself
META_EXPECTED = ("Modelo", "Pedido original", "Status")  # what the agent always knows: a missing one is a warning
```

with:

```python
META_TITLE = {lang: NOTE[lang]["meta_title"] for lang in LANGS}
META_RESERVED = tuple(NOTE[lang][k].lower() for lang in LANGS for k in ("written_at", "repository"))  # rows the tool writes itself
META_EXPECTED = {lang: NOTE[lang]["expected"] for lang in LANGS}  # what the agent always knows: a missing one is a warning
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
META_PART = re.compile(r"\| " + META_TITLE + r" \| \|\n(?:\|[^\n]*\n)*\n")
```

with:

```python
META_PART = re.compile(r"\| (?:" + "|".join(map(re.escape, META_TITLE.values())) + r") \| \|\n(?:\|[^\n]*\n)*\n")
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
raise HandoffError("a metainfo tem caracteres de controle")
```

with:

```python
raise HandoffError(say("meta_control"))
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
            raise HandoffError(f"metainfo invalida na linha {n + 1} do rascunho: use 'Chave: Valor', uma por linha, entre dois '---'")
```

with:

```python
            raise HandoffError(say("meta_line", line=n + 1))
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
raise HandoffError("a metainfo precisa de chave e valor")
```

with:

```python
raise HandoffError(say("meta_empty"))
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
            raise HandoffError(f"metainfo '{key[:20]}': chave de ate {MAX_META_KEY} e valor de ate {MAX_META_VALUE} caracteres (resuma)")
```

with:

```python
            raise HandoffError(say("meta_long", key=key[:20], max_key=MAX_META_KEY, max_value=MAX_META_VALUE))
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
            raise HandoffError(f"metainfo '{key}': chave repetida ou reservada (a ferramenta ja grava 'Gravada em' e 'Repositorio')")
```

with:

```python
            raise HandoffError(say("meta_reserved", key=key))
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
            raise HandoffError(f"metainfo '{key}': citacao tipada (commit:, branch:, file:) nao entra no cabecalho, ponha-a numa secao")
```

with:

```python
            raise HandoffError(say("meta_citation", key=key))
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
def meta_rows(root, agent_rows, when):
    """The header rows: the agent's, then what the tool knows by itself."""
    own = [("Gravada em", when), ("Repositorio", Path(root).name)]
```

with:

```python
def meta_rows(root, agent_rows, when, lang=DEFAULT_LANG):
    """The header rows: the agent's, then what the tool knows by itself (its keys in the note's language)."""
    own = [(note_text(lang, "written_at"), when), (note_text(lang, "repository"), Path(root).name)]
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
def meta_section(rows):
    esc = lambda text: text.replace("|", "\\|")
    return "\n".join([f"| {META_TITLE} | |", "|---|---|"] + [f"| {esc(k)} | {esc(v)} |" for k, v in rows])
```

with:

```python
def meta_section(rows, lang=DEFAULT_LANG):
    esc = lambda text: text.replace("|", "\\|")
    return "\n".join([f"| {note_text(lang, 'meta_title')} | |", "|---|---|"] + [f"| {esc(k)} | {esc(v)} |" for k, v in rows])
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
def missing_meta(rows):
    have = {k.lower() for k, _ in rows}
    return [name for name in META_EXPECTED if name.lower() not in have]
```

with:

```python
def missing_meta(rows, lang=DEFAULT_LANG):
    """The expected keys the agent left out, named in `lang`. A key counts in either language (`Model` or `Modelo`)."""
    have = {k.lower() for k, _ in rows}
    return [META_EXPECTED[lang][i] for i in range(len(META_EXPECTED[lang]))
            if not any(META_EXPECTED[other][i].lower() in have for other in LANGS)]
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
def git_section(facts):
    """The facts, as prose with no backtick spans (those are reserved for typed citations)."""
    branch = facts["branch"] or "(HEAD solta)"
    tip = f", ponta {facts['tip'][:7]}" if facts["tip"] else ", sem commits"
    lines = ["## Estado do git", "", f"- Branch: {branch}{tip}"]
    if facts["upstream"]:
        lines.append(f"- Upstream: {facts['upstream']}")
    if facts["base"] and facts["ahead"] is not None:
        lines.append(f"- Em relacao a base {facts['base']}: {facts['ahead']} a frente, {facts['behind']} atras")
    else:
        lines.append("- Base: nao encontrada")
    lines.append(f"- Arquivos modificados: {len(facts['modified'])}" + (f" ({names(facts['modified'])})" if facts["modified"] else ""))
    lines.append(f"- Arquivos novos (nao rastreados): {len(facts['untracked'])}" + (f" ({names(facts['untracked'])})" if facts["untracked"] else ""))
    lines.append(f"- Stashes: {facts['stashes']}")
    others = [w for w in facts["worktrees"][1:]]
    if others:
        lines.append("- Outros worktrees: " + ", ".join(f"{w['path']} ({w['branch'] or 'HEAD solta'})" for w in others))
    if facts["commits"]:
        lines += ["- Commits recentes:"] + [f"  - {c['sha']} {c['subject']}" for c in facts["commits"]]
    return "\n".join(lines)
```

with:

```python
def git_section(facts, lang=DEFAULT_LANG):
    """The facts, as prose with no backtick spans (those are reserved for typed citations), in `lang`."""
    n = lambda key, **values: note_text(lang, key, **values)
    branch = facts["branch"] or f"({n('detached')})"
    tip = n("tip", tip=facts["tip"][:7]) if facts["tip"] else n("no_commits")
    lines = [n("git_title"), "", f"- Branch: {branch}{tip}"]
    if facts["upstream"]:
        lines.append(f"- Upstream: {facts['upstream']}")
    if facts["base"] and facts["ahead"] is not None:
        lines.append(n("vs_base", base=facts["base"], ahead=facts["ahead"], behind=facts["behind"]))
    else:
        lines.append(n("no_base"))
    lines.append(n("modified", n=len(facts["modified"])) + (f" ({names(facts['modified'], lang)})" if facts["modified"] else ""))
    lines.append(n("untracked", n=len(facts["untracked"])) + (f" ({names(facts['untracked'], lang)})" if facts["untracked"] else ""))
    lines.append(n("stashes", n=facts["stashes"]))
    others = [w for w in facts["worktrees"][1:]]
    if others:
        lines.append(n("worktrees") + ", ".join(f"{w['path']} ({w['branch'] or n('detached')})" for w in others))
    if facts["commits"]:
        lines += [n("commits")] + [f"  - {c['sha']} {c['subject']}" for c in facts["commits"]]
    return "\n".join(lines)
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
def missing_sections(draft):
    return [name for name in SECTIONS if not re.search(rf"^#{{1,6}}[ \t]+{re.escape(name)}[ \t]*$", draft, re.M | re.I)]
```

with:

```python
def missing_sections(draft, lang=DEFAULT_LANG):
    """The sections the draft has no heading for, named in `lang`. A heading counts in either language."""
    has = lambda name: re.search(rf"^#{{1,6}}[ \t]+{re.escape(name)}[ \t]*$", draft, re.M | re.I)
    return [SECTIONS[lang][i] for i in range(len(SECTIONS[lang])) if not any(has(SECTIONS[other][i]) for other in LANGS)]
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
def render_note(facts, meta, draft, results, when):
    cites = [{"type": r["type"], "value": r["value"], "sha": r["sha"], "verified": r["verified"]} for r in results]
    data = {"schema": SCHEMA, "facts": facts, "meta": [list(r) for r in meta], "citations": cites}
    return (f"# Handoff - {when} - {facts['branch'] or 'HEAD solta'}\n\n" + meta_section(meta) + "\n\n" + git_section(facts) + "\n\n"
            + draft.strip("\n") + "\n\n" + data_block(data) + "\n")
```

with:

```python
def render_note(facts, meta, draft, results, when, lang=DEFAULT_LANG):
    """The note in `lang`; its data block records the language (a note written before 0.4.0 has none: pt-BR)."""
    cites = [{"type": r["type"], "value": r["value"], "sha": r["sha"], "verified": r["verified"]} for r in results]
    data = {"schema": SCHEMA, "lang": lang, "facts": facts, "meta": [list(r) for r in meta], "citations": cites}
    return (f"# Handoff - {when} - {facts['branch'] or note_text(lang, 'detached')}\n\n" + meta_section(meta, lang) + "\n\n"
            + git_section(facts, lang) + "\n\n" + draft.strip("\n") + "\n\n" + data_block(data) + "\n")
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
def write_note(root, draft, out_dir=None, base=None):
    """Check the draft's citations, mark the ones that fail, and save the note in a new file (never over another)."""
```

with:

```python
def write_note(root, draft, out_dir=None, base=None, lang=DEFAULT_LANG):
    """Check the draft's citations, mark the ones that fail, and save the note, in `lang`, in a new file (never over
    another)."""
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
    meta = meta_rows(root, agent_rows, when)
    text = render_note(facts, meta, mark_unverified(body, results), results, when)
```

with:

```python
    meta = meta_rows(root, agent_rows, when, lang)
    text = render_note(facts, meta, mark_unverified(body, results, lang), results, when, lang)
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
raise HandoffError("o rascunho tem caracteres que nao cabem em UTF-8: nada foi gravado")
```

with:

```python
raise HandoffError(say("draft_utf8"))
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
raise HandoffError(f"nao consegui criar a pasta das notas {folder}: {e.strerror or e}")
```

with:

```python
raise HandoffError(say("mkdir_failed", folder=folder, e=e.strerror or e))
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
raise HandoffError(f"nao consegui criar a nota em {folder}: {e.strerror or e}")
```

with:

```python
raise HandoffError(say("create_failed", folder=folder, e=e.strerror or e))
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
raise HandoffError(f"nao consegui gravar a nota {folder / name}: {e.strerror or e}")
```

with:

```python
raise HandoffError(say("write_failed", path=folder / name, e=e.strerror or e))
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
            "missing": missing_sections(body), "missing_meta": missing_meta(agent_rows)}
```

with:

```python
            "missing": missing_sections(body, lang), "missing_meta": missing_meta(agent_rows, lang)}
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
GIT_PART = re.compile(r"## Estado do git\n\n(?:[^\n]+\n)+")
```

with:

```python
GIT_PART = re.compile(r"(?:" + "|".join(re.escape(NOTE[lang]["git_title"]) for lang in LANGS) + r")\n\n(?:[^\n]+\n)+")
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
    title = TITLE.match(text)
    if title:
        pos = title.end()
        data = parse_data(text)
        meta = valid_meta(data.get("meta")) if data else None
        header = None
        if meta is not None:  # the exact rendering of the recorded rows, as for the git section below
            exact = meta_section(meta) + "\n\n"
            if text.startswith(exact, pos):
                header = pos + len(exact)
```

with:

```python
    title = TITLE.match(text)
    if title:
        pos = title.end()
        data = parse_data(text)
        meta = valid_meta(data.get("meta")) if data else None
        recorded = data.get("lang") if data and data.get("lang") in LANGS else "pt-BR"  # no lang: a note from before 0.4.0
        langs = [recorded] + [lang for lang in LANGS if lang != recorded]  # the recorded language first, then the other
        header = None
        if meta is not None:  # the exact rendering of the recorded rows, as for the git section below
            for lang in langs:
                exact = meta_section(meta, lang) + "\n\n"
                if text.startswith(exact, pos):
                    header = pos + len(exact)
                    break
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
        if data:  # the exact rendering of the recorded facts, so even a file name with a blank line in it is covered
            try:
                section = git_section(data["facts"]) + "\n"
                if text.startswith(section, header):
                    end = header + len(section)
            except (KeyError, TypeError, ValueError, AttributeError):
                end = None
```

with:

```python
        if data:  # the exact rendering of the recorded facts, so even a file name with a blank line in it is covered
            for lang in langs:
                try:
                    section = git_section(data["facts"], lang) + "\n"
                    if text.startswith(section, header):
                        end = header + len(section)
                        break
                except (KeyError, TypeError, ValueError, AttributeError):
                    end = None
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
        out.append(f"a branch era {then['branch'] or '(HEAD solta)'} e agora e {now['branch'] or '(HEAD solta)'}")
```

with:

```python
        out.append(say("d_branch", old=then["branch"] or say("d_detached"), new=now["branch"] or say("d_detached")))
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
            extra = f" ({count.strip()} commits novos)" if rc == 0 else ""
        else:
            extra = " (o commit antigo nao existe mais)"
        out.append(f"a ponta de {now['branch'] or 'HEAD'} mudou: {(then['tip'] or '-')[:7]} -> {(now['tip'] or '-')[:7]}{extra}")
```

with:

```python
            extra = say("d_new_commits", n=int(count.strip())) if rc == 0 and count.strip().isdigit() else ""
        else:
            extra = say("d_old_gone")
        out.append(say("d_tip", branch=now["branch"] or "HEAD", old=(then["tip"] or "-")[:7], new=(now["tip"] or "-")[:7], extra=extra))
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
        out.append(f"a frente/atras da base mudou: {then['ahead']}/{then['behind']} -> {now['ahead']}/{now['behind']}")
```

with:

```python
        out.append(say("d_counts", a=then["ahead"], b=then["behind"], c=now["ahead"], d=now["behind"]))
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
        out.append("arquivos sujos que ja nao estao: " + names(sorted(before - after)))
```

with:

```python
        out.append(say("d_gone", names=names(sorted(before - after))))
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
        out.append("arquivos sujos novos: " + names(sorted(after - before)))
```

with:

```python
        out.append(say("d_new", names=names(sorted(after - before))))
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
raise HandoffError(f"nao consegui ler a nota {path}: {e.strerror or e}")
```

with:

```python
raise HandoffError(say("read_failed", path=path, e=e.strerror or e))
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
raise HandoffError(f"nao ha nota em {NOTE_DIR}/ (rode `write` primeiro)")
```

with:

```python
raise HandoffError(say("no_note", folder=NOTE_DIR))
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
raise HandoffError(f"{path} nao e um arquivo de nota")
```

with:

```python
raise HandoffError(say("not_note", path=path))
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
def facts_report(facts):
    return git_section(facts)
```

with:

```python
def facts_report(facts):
    return git_section(facts, CLI_LANG)
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
        flag = "ok" if r["verified"] else "NAO VERIFICADO"
        if r.get("moved"):
            flag = "MUDOU (a ponta e outra)"
        out.append(f"  linha {r['line']}: {r['type']}:{r['value']}  {flag}" + (f" ({r['why']})" if r["why"] else ""))
```

with:

```python
        flag = say("f_ok") if r["verified"] else say("f_unverified")
        if r.get("moved"):
            flag = say("f_moved")
        out.append(say("line", line=r["line"], type=r["type"], value=r["value"], flag=flag) + (f" ({r['why']})" if r["why"] else ""))
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
    p = argparse.ArgumentParser(prog="handoff.py", description="Nota de fim de sessao com fatos do git e citacoes conferidas.")
    p.add_argument("--version", action="version", version=f"handoff {VERSION}")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect", help="os fatos do git, como JSON ou texto")
    c.add_argument("repo", nargs="?", default=".")
    c.add_argument("--base")
    c.add_argument("--json", action="store_true")
    w = sub.add_parser("write", help="confere as citacoes de um rascunho e grava a nota")
    w.add_argument("repo", nargs="?", default=".")
    w.add_argument("--draft", required=True, help="arquivo com o rascunho, ou - para a entrada padrao")
    w.add_argument("--out", help=f"pasta das notas (padrao: {NOTE_DIR}/ na raiz)")
    w.add_argument("--base")
    w.add_argument("--json", action="store_true")
    v = sub.add_parser("verify", help="confere as citacoes de uma nota ou rascunho")
    v.add_argument("file")
    v.add_argument("repo", nargs="?", default=".")
    v.add_argument("--json", action="store_true")
    r = sub.add_parser("resume", help="mostra a nota mais recente e o que mudou desde entao")
    r.add_argument("repo", nargs="?", default=".")
    r.add_argument("--file", help="uma nota especifica (padrao: a mais recente)")
    r.add_argument("--json", action="store_true")
    return p
```

with:

```python
    p = argparse.ArgumentParser(prog="handoff.py", description="End-of-session note with git facts and checked citations.")
    p.add_argument("--version", action="version", version=f"handoff {VERSION}")
    sub = p.add_subparsers(dest="cmd", required=True)
    lang = argparse.ArgumentParser(add_help=False)  # every command takes --lang (the help text is English in both)
    lang.add_argument("--lang", choices=LANGS, default=None,
                      help="language of the messages, and of the note for write (default: CAPYBARA_LANG, then en)")
    c = sub.add_parser("collect", parents=[lang], help="the git facts, as JSON or text")
    c.add_argument("repo", nargs="?", default=".")
    c.add_argument("--base")
    c.add_argument("--json", action="store_true")
    w = sub.add_parser("write", parents=[lang], help="check the citations of a draft and save the note")
    w.add_argument("repo", nargs="?", default=".")
    w.add_argument("--draft", required=True, help="file with the draft, or - for standard input")
    w.add_argument("--out", help=f"notes folder (default: {NOTE_DIR}/ at the root)")
    w.add_argument("--base")
    w.add_argument("--json", action="store_true")
    v = sub.add_parser("verify", parents=[lang], help="check the citations of a note or a draft")
    v.add_argument("file")
    v.add_argument("repo", nargs="?", default=".")
    v.add_argument("--json", action="store_true")
    r = sub.add_parser("resume", parents=[lang], help="show the newest note and what changed since then")
    r.add_argument("repo", nargs="?", default=".")
    r.add_argument("--file", help="a specific note (default: the newest)")
    r.add_argument("--json", action="store_true")
    return p
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
raise HandoffError("nao consegui ler o rascunho: nao e UTF-8 valido")
```

with:

```python
raise HandoffError(say("draft_not_utf8"))
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
raise HandoffError(f"nao consegui ler o rascunho: {e}")
```

with:

```python
raise HandoffError(say("draft_failed", e=e))
```

`main` sets the language of the run once and puts it back; the commands move to `run_command` unchanged apart from their text:

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace everything from the line `def main(argv=None):` up to (not including) the line `if __name__ == "__main__":` with:

```python
def main(argv=None):
    """Run one command. The language of its messages (and of the note `write` saves) is set here: --lang, then
    CAPYBARA_LANG, then en; it is put back afterwards, so an in-process caller (the tests) never inherits another
    run's language."""
    global CLI_LANG
    args = parser().parse_args(argv)
    before = CLI_LANG
    use_lang(args.lang)
    try:
        return run_command(args)
    finally:
        CLI_LANG = before


def run_command(args):
    try:
        root = repo_root(args.repo)
        if args.cmd == "collect":
            facts = collect(root, args.base)
            emit(args, facts, facts_report(facts))
            return 0
        if args.cmd == "write":
            res = write_note(root, read_draft(args.draft), args.out, args.base, CLI_LANG)
            bad = [c for c in res["citations"] if not c["verified"]]
            lines = [say("saved", path=res["path"]), say("n_citations", n=len(res["citations"])) + ", " + say("n_unverified", n=len(bad))]
            lines += citation_lines(bad)
            lines += [say("missing_section", name=name) for name in res["missing"]]
            lines += [say("missing_meta", name=name) for name in res["missing_meta"]]
            emit(args, {"schema": SCHEMA, "path": res["path"], "citations": clean_result(res["citations"]), "missing_sections": res["missing"],
                        "missing_meta": res["missing_meta"]}, "\n".join(lines))
            return 1 if bad else 0
        if args.cmd == "verify":
            path = Path(args.file)
            if path.is_symlink() or not path.is_file():
                raise HandoffError(say("not_file", path=path))
            results = check_note(root, read_note(path))
            bad = [c for c in results if not c["verified"]]
            emit(args, {"schema": SCHEMA, "citations": clean_result(results)},
                 "\n".join([say("n_citations", n=len(results)) + ", " + say("n_unverified", n=len(bad))] + citation_lines(results)))
            return 1 if bad else 0
        res = resume(root, args.file)
        bad = [c for c in res["citations"] if not c["verified"] or c["moved"]]
        changed = res["drift"] or []
        lines = [res["text"].rstrip("\n"), "", say("checked_now"), say("note", path=res["path"])]
        if res["drift"] is None:
            lines.append(say("no_data"))
        lines += ([say("changed")] + [f"  - {m}" for m in changed]) if changed else ([] if res["drift"] is None else [say("unchanged")])
        lines += [say("n_citations", n=len(res["citations"])) + ", " + say("n_problems", n=len(bad))] + citation_lines(bad)
        emit(args, {"schema": SCHEMA, "path": res["path"], "drift": res["drift"], "citations": clean_result(res["citations"])},
             "\n".join(lines))
        return 1 if (bad or changed) else 0
    except HandoffError as e:
        print(say("error", e=e), file=sys.stderr)
        return 2
    except RecursionError:  # the safety net: a failure of the system or of the text is exit 2, never a traceback
        print(say("error", e=say("too_deep")), file=sys.stderr)
        return 2
    except UnicodeError as e:
        print(say("error", e=say("not_utf8", e=e)), file=sys.stderr)
        return 2
    except OSError as e:
        print(say("error", e=say("io", e=e.strerror or e)), file=sys.stderr)
        return 2


```

- [ ] **Step 6: The example note in the new default**

The example is what the tool renders for an English `write` (the skill test compares its header with `meta_section` and its sections with `SECTIONS["en"]`):


Replace the whole file `plugins/housekeeping/skills/handoff/examples/note.example.md` with:

```markdown
# Handoff - 2026-10-14 09:05 - feat/export

| Session metainfo | |
|---|---|
| Model | Claude Sonnet 5.5 (`claude-sonnet-5-5`) |
| Original request | "add a CSV export" |
| Status | In progress: the writer exists, the header test is missing |
| Written at | 2026-10-14 09:05 |
| Repository | export-tool |

## Git state

- Branch: feat/export, tip 3f9a2c1
- Upstream: origin/feat/export
- Against the base base: 3 ahead, 0 behind
- Modified files: 1 (src/export.py)
- New (untracked) files: 0
- Stashes: 0
- Recent commits:
  - 3f9a2c1 export: write the header row
  - 8b41d07 export: add the CSV writer

## What was done
Added the CSV writer in `file:src/export.py:12` and its first test (`commit:8b41d07`).

## Decisions and why
Kept one file per export instead of a zip: the zip hid partial failures. The zip idea lives on `branch:spike/zip` and is not worth reviving.

## Next steps
1. Finish the header test in `file:tests/test_export.py:30`.
2. Then open the PR from `branch:feat/export`.

## What failed or got stuck
Streaming the rows with the old reader ran out of memory on the big fixture; see `file:docs/notes/memory.md` [not verified].

<!-- handoff:data {"schema":1,"lang":"en","meta":[["Model","Claude Sonnet 5.5 (`claude-sonnet-5-5`)"],["Original request","\"add a CSV export\""],["Status","In progress: the writer exists, the header test is missing"],["Written at","2026-10-14 09:05"],["Repository","export-tool"]],"facts":{"schema":1,"branch":"feat/export","tip":"3f9a2c1d4e5f60718293a4b5c6d7e8f901234567","upstream":"origin/feat/export","base":"base","ahead":3,"behind":0,"modified":["src/export.py"],"untracked":[],"stashes":0,"worktrees":[],"commits":[{"sha":"3f9a2c1","subject":"export: write the header row"},{"sha":"8b41d07","subject":"export: add the CSV writer"}]},"citations":[]} -->
```

- [ ] **Step 7: Run the suite**

Run: `git add -A && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/housekeeping/tests 2>&1 | tail -n 3`

Expected: `Ran 411 tests` and `OK`.

- [ ] **Step 8: Commit**

Run:

```bash
git add -A
git commit -m "feat(handoff): notes and messages in English by default or pt-BR with --lang; older notes still resume" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

Expected: one commit (git status --short is empty afterwards).

### Task 5d: todo-sweep: the command line in English or pt-BR, `--lang` on every command, release housekeeping 0.4.0

**Files:**
- Modify: `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py` (`MSG` and the language helpers before `LABELS`; every message through `say()`; `cmd_scan` and `cmd_report` resolve their content language with `pick_lang`; `Parser`, `parser` and `main`)
- Modify: `plugins/housekeeping/tests/test_ts_cli.py`, `test_ts_report.py`, `test_ts_scan.py`
- Release: the headers and `VERSION`s of `todo_sweep.py`, `doc_truth.py` and `handoff.py`, their usage comments, `plugins/housekeeping/CHANGELOG.md` (the 0.4.0 entry absorbs the `[Unreleased]` handoff metainfo bullets)
- Generated: `plugins/housekeeping/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`

**Interfaces:**
- Consumes: `LANGS`, `DEFAULT_LANG`, `TEXT`, `check_lang` (Task 5); the helpers' design of Task 5b.
- Produces: `ENV_LANG`, `CLI_LANG`, `MSG`, `env_lang()`, `pick_lang()`, `use_lang()`, `recorded_lang(folder)`, `lang_in_argv(argv)`, `say(msg_id, /, **values)`; `--lang {en,pt-BR}` on `scan`, `check` and `report` (default `None`). `main` sets the language once: `--lang`, then the `lang` of the `scan.json` in the command's folder (`check`, `report`), then `CAPYBARA_LANG`, then `en`; before argparse runs it reads `--lang` from `argv`, so a usage error is printed in that language (`error: argument ...` in English, the translated `erro: argumento ...` in pt-BR). `scan` writes its cards in the language of the run; `report` writes `report.md` in `--lang`, else the scan's language, and records it in `report.json` (this replaces R5's "no `--lang` of their own"). The tags `SCAN:`, `REPORT:` and `ok:` are the same in both languages; `lote:` reads `batch:` in English.
- Consumed by Task 6 (the todo-sweep skill quotes the English lines with the pt-BR ones next to them) and Task 7.

- [ ] **Step 1: Update the tests that pin the old command-line text**

Every board these tests scan without `--lang` is English, so their lines are English; the pt-BR flow of Task 5 keeps its Portuguese pins (it scans with `--lang pt-BR`, and `report` reads that language from the scan).


In `plugins/housekeeping/tests/test_ts_cli.py`, replace:

```python
        self.assertIn("3 TODO/FIXME achados", out)
        self.assertIn("mostrando 2", out)
        folder = Path(out.split("lote: ")[1].strip())
```

with:

```python
        self.assertIn("SCAN: 3 TODO/FIXME found, 0 already decided, 3 new, 0 without an age", out)
        self.assertIn("showing 2, oldest first", out)
        folder = Path(out.split("batch: ")[1].strip())
```

In `plugins/housekeeping/tests/test_ts_cli.py`, replace:

```python
        self.assertIn("REPORT: 1 resolver, 1 descartar, 0 manter, 0 sem decisao", out)
        rc, out, _ = run_main(["scan", str(self.repo)])
        self.assertIn("2 novos", out.replace("1 ja decididos, ", ""))  # one was remembered, two are still open
```

with:

```python
        self.assertIn("REPORT: 1 resolve, 1 discard, 0 keep, 0 no decision", out)
        self.assertIn("1 decision remembered in ", out)
        rc, out, _ = run_main(["scan", str(self.repo)])
        self.assertIn("1 already decided, 2 new", out)  # one was remembered, two are still open
```

In `plugins/housekeeping/tests/test_ts_cli.py`, replace:

```python
        self.assertIn("nada novo para mostrar", out)
```

with:

```python
        self.assertIn("nothing new to show", out)
```

In `plugins/housekeeping/tests/test_ts_cli.py`, replace:

```python
    def test_bad_counts_are_refused_in_portuguese_with_exit_two_and_nothing_written(self):
```

with:

```python
    def test_bad_counts_are_refused_with_exit_two_and_nothing_written(self):
```

In `plugins/housekeeping/tests/test_ts_cli.py`, replace:

```python
                self.assertEqual((rc, out), (2, ""))
                self.assertIn("erro:", err)
                self.assertIn(flag, err)
```

with:

```python
                self.assertEqual((rc, out), (2, ""))
                self.assertIn("error:", err)
                self.assertIn(flag, err)
```

In `plugins/housekeeping/tests/test_ts_cli.py`, replace:

```python
    def test_usage_errors_exit_two_with_an_erro_line(self):
```

with:

```python
    def test_usage_errors_exit_two_with_an_error_line_in_either_language(self):
```

In `plugins/housekeeping/tests/test_ts_cli.py`, replace:

```python
                self.assertEqual(ctx.exception.code, 2)
                self.assertIn("erro:", err.getvalue())
```

with:

```python
                self.assertEqual(ctx.exception.code, 2)
                self.assertIn("error:", err.getvalue())
                err = io.StringIO()
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
                    ts.main(argv + ["--lang", "pt-BR"])
                self.assertIn("erro: ", err.getvalue())  # argparse's words translated, as in 0.3.1
```

In `plugins/housekeeping/tests/test_ts_cli.py`, replace:

```python
    def test_a_corrupt_board_through_main_is_an_erro_line_and_exit_two_never_a_traceback(self):
```

with:

```python
    def test_a_corrupt_board_through_main_is_an_error_line_and_exit_two_never_a_traceback(self):
```

In `plugins/housekeeping/tests/test_ts_cli.py`, replace:

```python
                self.assertEqual((rc, out), (2, ""))
                self.assertTrue(err.startswith("erro:"), err)
                self.assertNotIn("Traceback", err)
```

with:

```python
                self.assertEqual((rc, out), (2, ""))
                self.assertTrue(err.startswith("error:"), err)
                self.assertNotIn("Traceback", err)
```

In `plugins/housekeeping/tests/test_ts_cli.py`, replace:

```python
    def test_an_unexpected_io_failure_is_still_an_erro_line_and_exit_two(self):
```

with:

```python
    def test_an_unexpected_io_failure_is_still_an_error_line_and_exit_two(self):
```

In `plugins/housekeeping/tests/test_ts_cli.py`, replace:

```python
                self.assertEqual((rc, out), (2, ""))
                self.assertTrue(err.startswith("erro:"), err)


```

with:

```python
                self.assertEqual((rc, out), (2, ""))
                self.assertTrue(err.startswith("error: unexpected failure ("), err)


```

In `plugins/housekeeping/tests/test_ts_cli.py`, replace:

```python
        self.assertIn("nao e um repositorio git", err)
```

with:

```python
        self.assertIn("is not a git repository", err)
```

In `plugins/housekeeping/tests/test_ts_cli.py`, replace:

```python
        self.assertIn("decisions.json ausente", err)
```

with:

```python
        self.assertIn("decisions.json missing or unreadable", err)
```

In `plugins/housekeeping/tests/test_ts_cli.py`, replace:

```python
        self.assertIn("3 TODO/FIXME achados", r.stdout)
```

with:

```python
        self.assertIn("3 TODO/FIXME found", r.stdout)
```

In `plugins/housekeeping/tests/test_ts_cli.py`, replace:

```python
    def test_lang_pt_br_flows_end_to_end_and_the_command_line_stays_portuguese(self):
```

with:

```python
    def test_lang_pt_br_flows_end_to_end_and_the_command_line_follows_it(self):
```

In `plugins/housekeeping/tests/test_ts_cli.py`, replace:

```python
        self.assertIn("REPORT: 1 resolver, 0 descartar, 0 manter, 2 sem decisao", out)
```

with:

```python
        self.assertIn("REPORT: 1 resolver, 0 descartar, 0 manter, 2 sem decisao", out)  # report reads the scan's language
        self.assertIn("0 decisoes lembradas em ", out)
```

In `plugins/housekeeping/tests/test_ts_cli.py`, replace:

```python
    def test_an_unknown_lang_is_an_erro_line_with_exit_two_and_nothing_written(self):
```

with:

```python
    def test_an_unknown_lang_is_an_error_line_with_exit_two_and_nothing_written(self):
```

In `plugins/housekeeping/tests/test_ts_cli.py`, replace:

```python
        self.assertIn("erro: argumento --lang: comando invalido: 'xx'", err.getvalue())
```

with:

```python
        self.assertIn("error: argument --lang: invalid choice: 'xx'", err.getvalue())
```

In `plugins/housekeeping/tests/test_ts_report.py`, replace:

```python
        self.assertIn("nao foi concluido", str(ctx.exception))
```

with:

```python
        self.assertIn("the panel was not finished", str(ctx.exception))
```

In `plugins/housekeeping/tests/test_ts_report.py`, replace:

```python
            self.assertIn("outro lote ou rodada", str(ctx.exception))
```

with:

```python
            self.assertIn("another batch or round", str(ctx.exception))
```

In `plugins/housekeeping/tests/test_ts_scan.py`, replace:

```python
        self.assertIn("link simbolico", str(ctx.exception))
```

with:

```python
        self.assertIn("symbolic link", str(ctx.exception))
```

In `plugins/housekeeping/tests/test_ts_scan.py`, replace:

```python
        self.assertIn("git nao encontrado", str(ctx.exception))
```

with:

```python
        self.assertIn("git not found", str(ctx.exception))
```

In `plugins/housekeeping/tests/test_ts_scan.py`, replace:

```python
        self.assertIn("nao consegui gravar", str(ctx.exception))
```

with:

```python
        self.assertIn("could not write", str(ctx.exception))
```

In `plugins/housekeeping/tests/test_ts_scan.py`, replace:

```python
            ts.check_lang("xx")
        self.assertIn("idioma invalido", str(ctx.exception))
```

with:

```python
            ts.check_lang("xx")
        self.assertIn("invalid language", str(ctx.exception))
```

In `plugins/housekeeping/tests/test_ts_scan.py`, replace:

```python
            ts.cmd_scan(self.args(lang="xx"))
        self.assertIn("idioma invalido", str(ctx.exception))
```

with:

```python
            ts.cmd_scan(self.args(lang="xx"))
        self.assertIn("invalid language", str(ctx.exception))
```

- [ ] **Step 2: Write the new tests**

The table, an AST guard over the functions that print, `CAPYBARA_LANG` for `scan`, `check` and `report` in the scan's language (their errors too), `report --lang`, the singular forms and `--lang` on every command:


Append to `plugins/housekeeping/tests/test_ts_cli.py` (after a blank line):

```python
# ---------------------------------------------------------------- the command line's language (housekeeping 0.4.0)

import ast as _ast
import os as _os
import re as _re

_PLACEHOLDER = _re.compile(r"\{(\w+)\}")
TS_PRINTING = ("git", "repo_root", "stage_private", "write_all", "scan_files", "work_dir", "load_ledger", "save_ledger",
               "check_lang", "make_folder", "refuse_old_decisions", "check_counts", "cmd_scan", "load_dir", "scan_problems",
               "cmd_check", "read_decisions", "trusted_repo", "cmd_report", "parser", "main")
TS_PT_WORDS = {"nao", "encontrado", "repositorio", "conteudo", "cabem", "nada", "gravado", "consegui", "gravar", "link",
               "simbolico", "recuso", "ilegivel", "corrija", "apague", "arquivo", "formato", "invalido", "criar", "pasta",
               "idioma", "ler", "ja", "tem", "lote", "anterior", "escolha", "outra", "decisoes", "deve", "numero", "inteiro",
               "recebi", "achados", "decididos", "novo", "novos", "mostrar", "sem", "idade", "aviso", "raso", "limite",
               "historico", "resolve", "primeiros", "medidos", "suba", "medir", "mostrando", "antigo", "ausente", "rode",
               "itens", "coincidem", "lotes", "diferentes", "problema", "suba", "painel", "conclua", "outro", "rodada",
               "concluido", "clique", "caminho", "absoluto", "existe", "raiz", "guardado", "invalidos", "resolver",
               "descartar", "manter", "decisao", "relatorio", "lembradas", "proximo", "oferece", "proximos", "erro",
               "falha", "inesperada", "acha", "escreve", "padrao", "quantos", "valida", "grava", "partir"}


class CommandLineTableTest(unittest.TestCase):
    def test_both_tables_have_the_same_keys_and_placeholders_and_are_plain_ascii(self):
        en, pt = ts.MSG["en"], ts.MSG["pt-BR"]
        self.assertEqual(set(en), set(pt))
        for key in en:
            with self.subTest(key=key):
                self.assertEqual(set(_PLACEHOLDER.findall(en[key])), set(_PLACEHOLDER.findall(pt[key])))
                self.assertTrue(en[key].isascii() and pt[key].isascii(), key)
        self.assertEqual(ts.MSG["pt-BR"]["report"], "REPORT: {resolve} resolver, {discard} descartar, {keep} manter, {none} sem decisao")

    def test_no_portuguese_literal_is_left_in_the_functions_that_print(self):
        tree = _ast.parse(TODO_SWEEP.read_text(encoding="utf-8"))
        found = []
        for fn in (n for n in _ast.walk(tree) if isinstance(n, _ast.FunctionDef) and n.name in TS_PRINTING):
            body = fn.body[1:] if isinstance(fn.body[0], _ast.Expr) and isinstance(fn.body[0].value, _ast.Constant) else fn.body
            for node in (n for stmt in body for n in _ast.walk(stmt)):
                if isinstance(node, _ast.Constant) and isinstance(node.value, str) and node.value not in {key for key, _text in ts.SECTIONS}:  # JSON keys are data
                    if set(_re.split(r"[^a-z]+", node.value.lower())) & TS_PT_WORDS:
                        found.append(f"{fn.name}: {node.value!r}")
        self.assertEqual(found, [], "Portuguese left outside MSG:\n" + "\n".join(found))


class CommandLineLanguageTest(CliCase):
    def scan(self, *extra, env=None):
        with mock.patch.dict(_os.environ, env or {}):
            rc, out, err = run_main(["scan", str(self.repo), *extra])
        self.assertEqual(rc, 0, err)
        return Path(out.split("batch: " if "batch: " in out else "lote: ")[1].strip()), out

    def test_capybara_lang_is_the_default_for_scan_and_the_flag_wins(self):
        folder, out = self.scan(env={"CAPYBARA_LANG": "pt-BR"})
        self.assertIn("SCAN: 3 TODO/FIXME achados, 0 ja decididos, 3 novos, 0 sem idade", out)
        self.assertEqual(json.loads((folder / "batch.json").read_text(encoding="utf-8"))["lang"], "pt-BR")
        _folder, out = self.scan("--out", str(self.tmp / "b2"), "--lang", "en", env={"CAPYBARA_LANG": "pt-BR"})
        self.assertIn("SCAN: 3 TODO/FIXME found", out)
        _folder, out = self.scan("--out", str(self.tmp / "b3"), env={"CAPYBARA_LANG": "portuguese"})
        self.assertIn("SCAN: 3 TODO/FIXME found", out)  # a bad value is ignored
        self.assertEqual(ts.CLI_LANG, "en")  # main() put the default back

    def test_check_and_report_speak_the_scans_language_even_in_their_errors(self):
        folder, _ = self.scan("--lang", "pt-BR")
        rc, out, _ = run_main(["check", str(folder)])
        self.assertEqual((rc, out), (0, "ok: 3 itens, lote %s\n" % folder.name))
        rc, _, err = run_main(["report", str(folder)])
        self.assertEqual(rc, 2)
        self.assertTrue(err.startswith("erro: decisions.json ausente ou ilegivel"), err)
        self.assertEqual(run_main(["check", str(folder), "--lang", "en"])[1], "ok: 3 items, batch %s\n" % folder.name)

    def test_report_lang_chooses_the_report_and_records_it(self):
        folder, _ = self.scan("--lang", "pt-BR")
        store = engine.Store(folder)
        store.set_item("T01", {"decision": "maybe"})
        store.set_finished(True)
        rc, out, _ = run_main(["report", str(folder), "--lang", "en"])
        self.assertEqual(rc, 0, out)
        self.assertIn("REPORT: 0 resolve, 0 discard, 1 keep, 2 no decision", out)
        self.assertIn("1 decision remembered in ", out)
        self.assertIn("## Keep (1)", (folder / "report.md").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((folder / "report.json").read_text(encoding="utf-8"))["lang"], "en")

    def test_one_takes_the_singular_form_in_pt_br(self):
        commit(self.repo, "only one", {"a.py": "x = 1\n", "b.py": "# TODO: only\n"})
        _folder, out = self.scan("--lang", "pt-BR")
        self.assertIn("SCAN: 1 TODO/FIXME achado, 0 ja decididos, 1 novo, 0 sem idade", out)

    def test_every_command_takes_lang(self):
        for argv in (["scan"], ["check", "d"], ["report", "d"]):
            with self.subTest(cmd=argv[0]):
                self.assertEqual(ts.parser().parse_args(argv + ["--lang", "pt-BR"]).lang, "pt-BR")
                self.assertIsNone(ts.parser().parse_args(argv).lang)
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/housekeeping/tests -p 'test_ts*.py' 2>&1 | tail -n 3`

Expected: `FAILED (` with failures and errors: `ts.MSG` and `ts.CLI_LANG` do not exist, only `scan` takes `--lang` and every line is Portuguese.

- [ ] **Step 4: The message table and the language helpers**


In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
LABELS = {  # the panel's own wording per language: A resolves, R discards, M keeps
```

with:

```python
ENV_LANG = "CAPYBARA_LANG"  # one shell-wide default for every Capybara Toolbox script
CLI_LANG = DEFAULT_LANG  # the language of this run's messages, set by main() only

# Every message the command line prints, in both languages (the cards and the report are TEXT, above). Same keys
# and {placeholders} in both (a test enforces it); both plain ASCII, so the pt-BR side is the accent-free
# Portuguese of 0.3.1, and a key ending in `_1` is the form used when n == 1.
MSG = {
    "en": {
        "git_missing": "git not found ({e})", "not_repo": "{path} is not a git repository",
        "not_utf8": "the content of {name} has characters that do not fit in UTF-8: nothing was written",
        "write_failed": "could not write {path}: {e}",
        "symlink": "{folder} is a symbolic link: I refuse to write or read through it",
        "ledger_unreadable": "{path} is unreadable: fix or delete the file",
        "ledger_shape": "{path} has an invalid shape: fix or delete the file",
        "mkdir_failed": "could not create the folder {path}: {e}", "bad_lang": "invalid language: {lang} (use en or pt-BR)",
        "listdir_failed": "could not read the folder {path}: {e}",
        "old_decisions_here": "{path} already has a decisions.json from an earlier batch: choose another folder with --out or delete the decisions",
        "bad_count": "{flag} must be a whole number >= 1 (got {value})",
        "found": "{n} TODO/FIXME found", "found_1": "{n} TODO/FIXME found",
        "decided": "{n} already decided", "decided_1": "{n} already decided", "new": "{n} new", "new_1": "{n} new",
        "unaged": "{n} without an age", "unaged_1": "{n} without an age",
        "scan_nothing": "SCAN: {found}, {decided}; nothing new to show", "scan": "SCAN: {found}, {decided}, {new}, {unaged}",
        "shallow": "warning: shallow clone: the lines at the edge of the history have no age (git fetch --unshallow fixes it)",
        "max_blame": "warning: only the first {n} were measured; raise --max-blame to measure more",
        "showing": "showing {n}, oldest first", "batch": "batch: {path}",
        "missing_file": "{path} missing or unreadable: run scan",
        "p_not_scan": "scan.json is not a todo-sweep scan (schema 1)", "p_no_items": "scan.json without 'items' or 'repo'",
        "p_batch_items": "batch.json without 'items'",
        "p_ids": "scan.json without 'batch_id' (text) or 'round' (integer), or batch.json with an invalid 'round'",
        "p_other_batch": "batch.json and scan.json are from different batches", "p_lang": "scan.json: 'lang' must be en or pt-BR",
        "p_items_differ": "the items of batch.json and scan.json do not match", "p_bad_item": "invalid item in scan.json: {item}",
        "problem": "problem: {e}", "ok": "ok: {n} items, batch {id}", "ok_1": "ok: {n} item, batch {id}",
        "no_decisions": "decisions.json missing or unreadable: open the panel and finish it before report",
        "bad_decisions": "decisions.json has an invalid shape",
        "old_decisions": "decisions.json belongs to another batch or round: I will not use old decisions",
        "not_finished": "the panel was not finished (click Finish before report)",
        "repo_absolute": "the repo of scan.json must be an absolute path: {value}",
        "repo_gone": "the repository of the scan no longer exists: {root}",
        "repo_not_root": "the repo of scan.json is not the root of a git repository: {root}",
        "repo_elsewhere": "the repo of scan.json ({root}) is not the repository this batch is kept in ({anchor})",
        "invalid": "invalid scan.json/batch.json: {errs}",
        "report": "REPORT: {resolve} resolve, {discard} discard, {keep} keep, {none} no decision",
        "report_file": "report: {path}",
        "remembered": "{n} decisions remembered in {ledger}; the next scan offers the next ones",
        "remembered_1": "{n} decision remembered in {ledger}; the next scan offers the next ones",
        "error": "error: {e}", "unexpected": "unexpected failure ({name}: {e})",
    },
    "pt-BR": {
        "git_missing": "git nao encontrado ({e})", "not_repo": "{path} nao e um repositorio git",
        "not_utf8": "o conteudo de {name} tem caracteres que nao cabem em UTF-8: nada foi gravado",
        "write_failed": "nao consegui gravar {path}: {e}",
        "symlink": "{folder} e um link simbolico: recuso escrever ou ler por ele",
        "ledger_unreadable": "{path} esta ilegivel: corrija ou apague o arquivo",
        "ledger_shape": "{path} tem formato invalido: corrija ou apague o arquivo",
        "mkdir_failed": "nao consegui criar a pasta {path}: {e}", "bad_lang": "idioma invalido: {lang} (use en ou pt-BR)",
        "listdir_failed": "nao consegui ler a pasta {path}: {e}",
        "old_decisions_here": "{path} ja tem decisions.json de um lote anterior: escolha outra pasta com --out ou apague as decisoes",
        "bad_count": "{flag} deve ser um numero inteiro >= 1 (recebi {value})",
        "found": "{n} TODO/FIXME achados", "found_1": "{n} TODO/FIXME achado",
        "decided": "{n} ja decididos", "decided_1": "{n} ja decidido", "new": "{n} novos", "new_1": "{n} novo",
        "unaged": "{n} sem idade", "unaged_1": "{n} sem idade",
        "scan_nothing": "SCAN: {found}, {decided}; nada novo para mostrar", "scan": "SCAN: {found}, {decided}, {new}, {unaged}",
        "shallow": "aviso: clone raso: as linhas no limite do historico ficam sem idade (git fetch --unshallow resolve)",
        "max_blame": "aviso: so os primeiros {n} foram medidos; suba --max-blame para medir mais",
        "showing": "mostrando {n}, do mais antigo ao mais novo", "batch": "lote: {path}",
        "missing_file": "{path} ausente ou ilegivel: rode o scan",
        "p_not_scan": "scan.json nao e um scan do todo-sweep (schema 1)", "p_no_items": "scan.json sem 'items' ou 'repo'",
        "p_batch_items": "batch.json sem 'items'",
        "p_ids": "scan.json sem 'batch_id' (texto) ou 'round' (inteiro), ou batch.json com 'round' invalido",
        "p_other_batch": "batch.json e scan.json sao de lotes diferentes", "p_lang": "scan.json: 'lang' deve ser en ou pt-BR",
        "p_items_differ": "os itens do batch.json e do scan.json nao coincidem", "p_bad_item": "item invalido no scan.json: {item}",
        "problem": "problema: {e}", "ok": "ok: {n} itens, lote {id}", "ok_1": "ok: {n} item, lote {id}",
        "no_decisions": "decisions.json ausente ou ilegivel: suba o painel e conclua antes do report",
        "bad_decisions": "decisions.json com formato invalido",
        "old_decisions": "decisions.json e de outro lote ou rodada: nao vou usar decisoes antigas",
        "not_finished": "o painel nao foi concluido (clique em Concluir antes do report)",
        "repo_absolute": "o repo do scan.json deve ser um caminho absoluto: {value}",
        "repo_gone": "o repositorio do scan nao existe mais: {root}",
        "repo_not_root": "o repo do scan.json nao e a raiz de um repositorio git: {root}",
        "repo_elsewhere": "o repo do scan.json ({root}) nao e o repositorio onde este lote esta guardado ({anchor})",
        "invalid": "scan.json/batch.json invalidos: {errs}",
        "report": "REPORT: {resolve} resolver, {discard} descartar, {keep} manter, {none} sem decisao",
        "report_file": "relatorio: {path}",
        "remembered": "{n} decisoes lembradas em {ledger}; o proximo scan oferece os proximos",
        "remembered_1": "{n} decisao lembrada em {ledger}; o proximo scan oferece os proximos",
        "error": "erro: {e}", "unexpected": "falha inesperada ({name}: {e})",
    },
}


def env_lang():
    """CAPYBARA_LANG when it is exactly one of LANGS. Any other value is ignored, silently: a shell setting must
    never break a command, and a warning on every run would be noise in the agent's context."""
    value = os.environ.get(ENV_LANG)
    return value if value in LANGS else None


def pick_lang(*candidates):
    """The first candidate that is one of LANGS (--lang, then the language a scan recorded), then CAPYBARA_LANG,
    then English. A recorded value is data: anything else is ignored here and refused by `check` and `report`."""
    for cand in candidates:
        if isinstance(cand, str) and cand in LANGS:
            return cand
    return env_lang() or DEFAULT_LANG


def use_lang(*candidates):
    """Set the language of this run's messages (see pick_lang) and return it. Only main() calls it."""
    global CLI_LANG
    CLI_LANG = pick_lang(*candidates)
    return CLI_LANG


def recorded_lang(folder):
    """The `lang` the scan in `folder` recorded, or None (no folder, no scan.json, not JSON). main() reads it before
    the command runs, so the command's lines and its errors speak the language of the board it works on."""
    if not folder:
        return None
    try:
        data = json.loads((Path(folder) / "scan.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, RecursionError):
        return None
    return data.get("lang") if isinstance(data, dict) else None


def lang_in_argv(argv):
    """The value of --lang as typed, read before argparse runs: its usage errors are printed while it parses."""
    for i, arg in enumerate(argv):
        if arg == "--lang" and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith("--lang="):
            return arg[len("--lang="):]
    return None


def say(msg_id, /, **values):
    """One command-line message in the language of this run; with n == 1 the `_1` form wins when there is one.
    The template is ours, the values are data (substituted, never parsed)."""
    table = MSG[CLI_LANG]
    if values.get("n") == 1 and msg_id + "_1" in table:
        msg_id += "_1"
    return table[msg_id].format(**values)
LABELS = {  # the panel's own wording per language: A resolves, R discards, M keeps
```

- [ ] **Step 5: Every message through `say()`**

Each function keeps its logic and only moves its text; `scan` and `report` resolve the language of what they write with `pick_lang`, and `main` is the only place that sets the language of the messages:


In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
raise SweepError(f"git nao encontrado ({e.strerror or e})")
```

with:

```python
raise SweepError(say("git_missing", e=e.strerror or e))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
raise SweepError(f"{path} nao e um repositorio git")
```

with:

```python
raise SweepError(say("not_repo", path=path))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
raise SweepError(f"o conteudo de {path.name} tem caracteres que nao cabem em UTF-8: nada foi gravado")
```

with:

```python
raise SweepError(say("not_utf8", name=path.name))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError as e:
        raise SweepError(f"nao consegui gravar {path}: {e.strerror or e}")
```

with:

```python
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError as e:
        raise SweepError(say("write_failed", path=path, e=e.strerror or e))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
        discard(tmp)
        raise SweepError(f"nao consegui gravar {path}: {e.strerror or e}")
```

with:

```python
        discard(tmp)
        raise SweepError(say("write_failed", path=path, e=e.strerror or e))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
raise SweepError(f"nao consegui gravar {', '.join(str(p) for p in files)}: {e.strerror or e}")
```

with:

```python
raise SweepError(say("write_failed", path=", ".join(str(p) for p in files), e=e.strerror or e))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
raise SweepError(f"{root} nao e um repositorio git")
```

with:

```python
raise SweepError(say("not_repo", path=root))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
raise SweepError(f"{folder} e um link simbolico: recuso escrever ou ler por ele")
```

with:

```python
raise SweepError(say("symlink", folder=folder))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
raise SweepError(f"{path} esta ilegivel: corrija ou apague o arquivo")
```

with:

```python
raise SweepError(say("ledger_unreadable", path=path))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
raise SweepError(f"{path} tem formato invalido: corrija ou apague o arquivo")
```

with:

```python
raise SweepError(say("ledger_shape", path=path))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
raise SweepError(f"nao consegui criar a pasta {path.parent}: {e.strerror or e}")
```

with:

```python
raise SweepError(say("mkdir_failed", path=path.parent, e=e.strerror or e))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
raise SweepError(f"idioma invalido: {lang!r} (use en ou pt-BR)")
```

with:

```python
raise SweepError(say("bad_lang", lang=repr(lang)))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
raise SweepError(f"nao consegui criar a pasta {out}: {e.strerror or e}")
```

with:

```python
raise SweepError(say("mkdir_failed", path=out, e=e.strerror or e))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
raise SweepError(f"nao consegui ler a pasta {out}: {e.strerror or e}")
```

with:

```python
raise SweepError(say("listdir_failed", path=out, e=e.strerror or e))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
raise SweepError(f"{out} ja tem decisions.json de um lote anterior: escolha outra pasta com --out ou apague as decisoes")
```

with:

```python
raise SweepError(say("old_decisions_here", path=out))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
raise SweepError(f"{flag} deve ser um numero inteiro >= 1 (recebi {value!r})")
```

with:

```python
raise SweepError(say("bad_count", flag=flag, value=repr(value)))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
    check_counts(a)
    lang = check_lang(a.lang)
```

with:

```python
    check_counts(a)
    lang = check_lang(getattr(a, "lang", None) or pick_lang())  # one language per run: the cards and these lines
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
        print(f"SCAN: {len(hits)} TODO/FIXME achados, {len(hits) - len(fresh)} ja decididos; nada novo para mostrar")
```

with:

```python
        print(say("scan_nothing", found=say("found", n=len(hits)), decided=say("decided", n=len(hits) - len(fresh))))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
    print(f"SCAN: {len(hits)} TODO/FIXME achados, {totals['decided_before']} ja decididos, {len(fresh)} novos, {len(unaged)} sem idade")
    if totals["shallow"]:
        print("aviso: clone raso: as linhas no limite do historico ficam sem idade (git fetch --unshallow resolve)")
    if len(unaged) and a.max_blame < len(fresh):
        print(f"aviso: so os primeiros {a.max_blame} foram medidos; suba --max-blame para medir mais")
    print(f"mostrando {len(offered)}, do mais antigo ao mais novo")
    print(f"lote: {out}")
```

with:

```python
    print(say("scan", found=say("found", n=len(hits)), decided=say("decided", n=totals["decided_before"]),
              new=say("new", n=len(fresh)), unaged=say("unaged", n=len(unaged))))
    if totals["shallow"]:
        print(say("shallow"))
    if len(unaged) and a.max_blame < len(fresh):
        print(say("max_blame", n=a.max_blame))
    print(say("showing", n=len(offered)))
    print(say("batch", path=out))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
raise SweepError(f"{Path(d) / name} ausente ou ilegivel: rode o scan")
```

with:

```python
raise SweepError(say("missing_file", path=Path(d) / name))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
return ["scan.json nao e um scan do todo-sweep (schema 1)"]
```

with:

```python
return [say("p_not_scan")]
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
return ["scan.json sem 'items' ou 'repo'"]
```

with:

```python
return [say("p_no_items")]
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
return ["batch.json sem 'items'"]
```

with:

```python
return [say("p_batch_items")]
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
return ["scan.json sem 'batch_id' (texto) ou 'round' (inteiro), ou batch.json com 'round' invalido"]
```

with:

```python
return [say("p_ids")]
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
errs.append("batch.json e scan.json sao de lotes diferentes")
```

with:

```python
errs.append(say("p_other_batch"))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
errs.append("scan.json: 'lang' deve ser en ou pt-BR")
```

with:

```python
errs.append(say("p_lang"))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
errs.append("os itens do batch.json e do scan.json nao coincidem")
```

with:

```python
errs.append(say("p_items_differ"))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
errs.append(f"item invalido no scan.json: {it!r}"[:120])
```

with:

```python
errs.append(say("p_bad_item", item=repr(it))[:120])
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
    for e in errs:
        print(f"problema: {e}")
    if not errs:
        print(f"ok: {len(scan['items'])} itens, lote {scan['batch_id']}")
```

with:

```python
    for e in errs:
        print(say("problem", e=e))
    if not errs:
        print(say("ok", n=len(scan["items"]), id=scan["batch_id"]))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
raise SweepError("decisions.json ausente ou ilegivel: suba o painel e conclua antes do report")
```

with:

```python
raise SweepError(say("no_decisions"))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
raise SweepError("decisions.json com formato invalido")
```

with:

```python
raise SweepError(say("bad_decisions"))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
raise SweepError("decisions.json e de outro lote ou rodada: nao vou usar decisoes antigas")
```

with:

```python
raise SweepError(say("old_decisions"))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
raise SweepError("o painel nao foi concluido (clique em Concluir antes do report)")
```

with:

```python
raise SweepError(say("not_finished"))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
raise SweepError(f"o repo do scan.json deve ser um caminho absoluto: {value!r}"[:200])
```

with:

```python
raise SweepError(say("repo_absolute", value=repr(value))[:200])
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
raise SweepError(f"o repositorio do scan nao existe mais: {root}")
```

with:

```python
raise SweepError(say("repo_gone", root=root))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
raise SweepError(f"o repo do scan.json nao e a raiz de um repositorio git: {root}")
```

with:

```python
raise SweepError(say("repo_not_root", root=root))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
raise SweepError(f"o repo do scan.json ({root}) nao e o repositorio onde este lote esta guardado ({anchor})")
```

with:

```python
raise SweepError(say("repo_elsewhere", root=root, anchor=anchor))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
        raise SweepError("scan.json/batch.json invalidos: " + "; ".join(errs))
    lang = scan.get("lang") or DEFAULT_LANG  # an older scan has no lang: English; scan_problems refused any other value
```

with:

```python
        raise SweepError(say("invalid", errs="; ".join(errs)))
    lang = pick_lang(getattr(a, "lang", None), scan.get("lang"))  # --lang, the scan's (an older one has none), CAPYBARA_LANG, en
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
    print(f"REPORT: {c['resolver']} resolver, {c['descartar']} descartar, {c['manter']} manter, {c['sem_decisao']} sem decisao")
    print(f"relatorio: {out / 'report.md'}")
    print(f"{c['descartar'] + c['manter']} decisoes lembradas em {ledger}; o proximo scan oferece os proximos")
```

with:

```python
    print(say("report", resolve=c["resolver"], discard=c["descartar"], keep=c["manter"], none=c["sem_decisao"]))
    print(say("report_file", path=out / "report.md"))
    print(say("remembered", n=c["descartar"] + c["manter"], ledger=ledger))
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
class Parser(argparse.ArgumentParser):
    """Usage mistakes end the way every other failure does: an `erro:` line on stderr and exit code 2."""

    def error(self, message):
        for pattern, text in USAGE_WORDS:
            message = re.sub(pattern, text, message)
        self.print_usage(sys.stderr)
        self.exit(2, f"erro: {message}\n")
```

with:

```python
class Parser(argparse.ArgumentParser):
    """Usage mistakes end the way every other failure does: an `error:` line (pt-BR `erro:`) on stderr and exit
    code 2. argparse speaks English; in pt-BR its words are translated as before."""

    def error(self, message):
        if CLI_LANG == "pt-BR":
            for pattern, text in USAGE_WORDS:
                message = re.sub(pattern, text, message)
        self.print_usage(sys.stderr)
        self.exit(2, say("error", e=message) + "\n")
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
    p = Parser(prog="todo_sweep.py", description="TODO e FIXME como cards num painel local; o resultado e um relatorio somente leitura.")
    p.add_argument("--version", action="version", version=f"todo-sweep {VERSION}")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="acha os TODO/FIXME e escreve batch.json + scan.json")
    s.add_argument("repo", nargs="?", default=".")
    s.add_argument("--limit", type=count, default=20, help="cards por lote (padrao 20)")
    s.add_argument("--max-blame", type=count, default=300, help="quantos medir com git blame (padrao 300)")
    s.add_argument("--out", help=f"pasta do lote (padrao: {WORK_DIR}/todo-sweep-AAAA-MM-DD)")
    s.add_argument("--lang", choices=LANGS, default=DEFAULT_LANG, help="idioma dos cards e do relatorio: en (padrao) ou pt-BR")
    c = sub.add_parser("check", help="valida batch.json + scan.json")
    c.add_argument("dir")
    r = sub.add_parser("report", help="grava report.md e report.json a partir das decisoes")
    r.add_argument("dir")
    return p
```

with:

```python
    p = Parser(prog="todo_sweep.py", description="TODO and FIXME as cards on a local panel; the result is a read-only report.")
    p.add_argument("--version", action="version", version=f"todo-sweep {VERSION}")
    sub = p.add_subparsers(dest="cmd", required=True)
    lang = Parser(add_help=False)  # every command takes --lang (the help text is English in both)
    lang.add_argument("--lang", choices=LANGS, default=None,
                      help="language of the messages, of the cards (scan) and of report.md (report); default: the scan's lang, then CAPYBARA_LANG, then en")
    s = sub.add_parser("scan", parents=[lang], help="find the TODO/FIXME and write batch.json + scan.json")
    s.add_argument("repo", nargs="?", default=".")
    s.add_argument("--limit", type=count, default=20, help="cards per batch (default 20)")
    s.add_argument("--max-blame", type=count, default=300, help="how many to measure with git blame (default 300)")
    s.add_argument("--out", help=f"batch folder (default: {WORK_DIR}/todo-sweep-YYYY-MM-DD)")
    c = sub.add_parser("check", parents=[lang], help="validate batch.json + scan.json")
    c.add_argument("dir")
    r = sub.add_parser("report", parents=[lang], help="write report.md and report.json from the decisions")
    r.add_argument("dir")
    return p
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
def main(argv=None):
    args = parser().parse_args(argv)
    try:
        return {"scan": cmd_scan, "check": cmd_check, "report": cmd_report}[args.cmd](args)
    except SweepError as e:
        print(f"erro: {e}", file=sys.stderr)
        return 2
    except (OSError, UnicodeError, RecursionError) as e:  # whatever a hostile folder or a full disk still throws
        print(f"erro: falha inesperada ({type(e).__name__}: {e})", file=sys.stderr)
        return 2
```

with:

```python
def main(argv=None):
    """Run one command. The language of its messages is set here, once: --lang, then the lang of the scan in the
    command's folder (check, report), then CAPYBARA_LANG, then en. It is put back afterwards, so an in-process
    caller (the tests) never inherits another run's language; the commands never set it."""
    global CLI_LANG
    argv = sys.argv[1:] if argv is None else list(argv)
    before = CLI_LANG
    use_lang(lang_in_argv(argv))  # a usage error is printed while argparse parses, before args exist
    try:
        args = parser().parse_args(argv)
        use_lang(args.lang, recorded_lang(getattr(args, "dir", None)))
        try:
            return {"scan": cmd_scan, "check": cmd_check, "report": cmd_report}[args.cmd](args)
        except SweepError as e:
            print(say("error", e=e), file=sys.stderr)
            return 2
        except (OSError, UnicodeError, RecursionError) as e:  # whatever a hostile folder or a full disk still throws
            print(say("error", e=say("unexpected", name=type(e).__name__, e=e)), file=sys.stderr)
            return 2
    finally:
        CLI_LANG = before
```

- [ ] **Step 6: Run the suite**

Run: `git add -A && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/housekeeping/tests 2>&1 | tail -n 3`

Expected: `Ran 418 tests` and `OK`.


- [ ] **Step 7: Release housekeeping 0.4.0**

The three scripts move together (one plugin, one version) and the release carries the work of Tasks 5, 5b, 5c and this task; `DAY` is the day of execution:

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
# todo-sweep 0.3.1 - 
```

with:

```python
# todo-sweep 0.4.0 - 
```

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
VERSION = "0.3.1"
```

with:

```python
VERSION = "0.4.0"
```

In `plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py`, replace:

```python
# doc-truth 0.3.1 - 
```

with:

```python
# doc-truth 0.4.0 - 
```

In `plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py`, replace:

```python
VERSION = "0.3.1"
```

with:

```python
VERSION = "0.4.0"
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
# handoff 0.3.1 - 
```

with:

```python
# handoff 0.4.0 - 
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
VERSION = "0.3.1"
```

with:

```python
VERSION = "0.4.0"
```

The usage comments say that every command takes `--lang`:

In `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py`, replace:

```python
# O painel e o capy_board.py desta skill (`serve DIR`). Nenhum arquivo-fonte e editado.
```

with:

```python
# Todo comando aceita --lang en|pt-BR (padrao: o lang do scan.json, depois CAPYBARA_LANG, depois en).
# O painel e o capy_board.py desta skill (`serve DIR`). Nenhum arquivo-fonte e editado.
```

In `plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py`, replace:

```python
#   doc_truth.py [PATH] [--json] [--config FILE]     # somente leitura; saida 0 limpo, 1 achados, 2 erro
```

with:

```python
#   doc_truth.py [PATH] [--json] [--config FILE] [--lang en|pt-BR]     # somente leitura; saida 0 limpo, 1 achados, 2 erro
```

In `plugins/housekeeping/skills/handoff/scripts/handoff.py`, replace:

```python
# Saida: 0 tudo conferido, 1 citacao nao verificada ou algo mudou, 2 erro.
```

with:

```python
# Todo comando aceita --lang en|pt-BR (padrao: CAPYBARA_LANG, depois en); write grava a nota nesse idioma.
# Saida: 0 tudo conferido, 1 citacao nao verificada ou algo mudou, 2 erro.
```

The changelog entry absorbs the two `[Unreleased]` bullets (the handoff metainfo header and `model: haiku`, which this release ships) and describes the language of the three tools:

In `plugins/housekeeping/CHANGELOG.md`, replace:

```markdown
## [Unreleased]

### Added
- handoff notes always start with a `Metainfo da sessao` table. The agent opens the draft with a `---` block of `Chave: Valor` lines (`Modelo`, `Pedido original` and `Status` are expected, anything else is optional); the tool adds `Gravada em` and `Repositorio`, records the rows in the data block, warns with `aviso: falta a metainfo '<key>'` when an expected one is missing, and refuses a duplicate or reserved key, a control character, an over-long row and a typed citation in the block. `resume` and `verify` never treat the header as citations; a note written before the header existed still resumes. `write --json` has a `missing_meta` list.
- The handoff skill asks for `model: haiku` in its frontmatter (the override lasts for the turn that runs the skill).

## [0.3.1] - 2026-10-15
```

with:

```markdown
## [Unreleased]

## [0.4.0] - DAY

### Added
- todo-sweep: `scan --lang en|pt-BR` chooses the language of the cards (field labels, titles, the age wording, `labels`, the subtitle) and of `report.md`. The language is written to `batch.json` (`lang`, so the panel opens in it) and to `scan.json`; `report` reads it from there and records it in `report.json` (`lang`). `check` and `report` refuse any other value in `scan.json`; an older scan without `lang` is read as English.
- todo-sweep: the pt-BR cards and report are now written with accents.
- **Every command of the three tools takes `--lang en|pt-BR`** for its messages: doc-truth, handoff (`collect`, `write`, `verify`, `resume`) and todo-sweep (`scan`, `check`, `report`). Without it, todo-sweep's `check` and `report` speak the language recorded in `scan.json`, and `report --lang` also chooses the language of `report.md`.
- **`CAPYBARA_LANG`** (`en` or `pt-BR`) is the default language when no flag and no recorded language decide; any other value is ignored. Every Capybara Toolbox script reads the same variable.
- handoff notes in English or pt-BR: `write` writes the note in the language of the run and records it in the data block (`lang`); the agent's metainfo keys and section headings count in either language; `resume` and `verify` read a note in either language, and a note written before 0.4.0 (pt-BR, no `lang` in its block) resumes unchanged.
- handoff notes always start with a metainfo table (`Session metainfo`, pt-BR `Metainfo da sessao`). The agent opens the draft with a `---` block of `Key: Value` lines (`Model`, `Original request` and `Status` are expected, pt-BR `Modelo`, `Pedido original` and `Status`; anything else is optional); the tool adds `Written at` and `Repository` (pt-BR `Gravada em` and `Repositorio`), records the rows in the data block, warns with `warning: metainfo '<key>' is missing` (pt-BR `aviso: falta a metainfo '<key>'`) when an expected one is missing, and refuses a duplicate or reserved key, a control character, an over-long row and a typed citation in the block. `resume` and `verify` never treat the header as citations; a note written before the header existed still resumes. `write --json` has a `missing_meta` list.
- The handoff skill asks for `model: haiku` in its frontmatter (the override lasts for the turn that runs the skill).

### Changed
- **The default is English** for the three tools: todo-sweep's cards and report, handoff's notes and every command-line message. Pass `--lang pt-BR` (or set `CAPYBARA_LANG=pt-BR`) for Portuguese. The pt-BR command-line text and the pt-BR note are the accent-free Portuguese of 0.3.1, except that a count of one now takes the singular (`1 item`, `1 citacao`, `1 TODO/FIXME achado`).
- In English the prefixes are `error:` and `warning:` (pt-BR `erro:` and `aviso:`), doc-truth prints `clean: no findings` (pt-BR `limpo: nenhum achado`), handoff marks a failed citation `[not verified]` (pt-BR `[nao verificado]`) and todo-sweep names its folder on a `batch:` line (pt-BR `lote:`). The tags `SCAN:`, `REPORT:` and `ok:` are the same in both languages. The `--help` text is English.
- doc-truth: a finding's `value` and `fingerprint` do not depend on the language (the `parity` value stays `falta README.pt-BR.md`), so an `allow` list keeps working in either language; only its `message` follows the language.
- todo-sweep: `age_reason` in the hits and in `scan.json` is a code (`max_blame`, `no_history`, `uncommitted`, `shallow`, or empty), rendered on the card in the chosen language. `report.json` keeps its keys (`resolver`, `descartar`, `manter`, `sem_decisao`) and the ledger its words (`discard`, `keep`): nothing a script reads depends on the language.
- The handoff example note is English, the new default.
- todo-sweep requires ar-board 1.4.0 (the vendored engine) for the panel to honour `lang`.

## [0.3.1] - 2026-10-15
```

Run: `python3 plugins/housekeeping/tools/sync.py && python3 tools/marketplace.py && python3 plugins/housekeeping/tools/sync.py --check && python3 tools/marketplace.py --check && echo in-sync`

Expected: `updated: .claude-plugin/plugin.json`, `updated: .claude-plugin/marketplace.json`, `in-sync`.

Run: `git add -A && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/housekeeping/tests 2>&1 | tail -n 3 && PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s plugins/housekeeping/tests 2>&1 | tail -n 3 && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests 2>&1 | tail -n 1`

Expected: `Ran 418 tests` and `OK` on both Pythons, then `OK` for the catalog.

- [ ] **Step 8: Commit**

Run:

```bash
git add -A
git commit -m "feat(todo-sweep): the command line in English by default or pt-BR, --lang on every command, release housekeeping 0.4.0" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

Expected: one commit (git status --short is empty afterwards).

### Task 5e: header-footer: messages and the weekday in English or pt-BR, `lang` in the config, release 0.4.0

**Files:**
- Modify: `plugins/header-footer/skills/header-footer/scripts/header_footer.py` (the usage docstring; `FIELD_HELP`, `MSG` and the language helpers replace `HEADER_FIELDS`/`FOOTER_FIELDS`; `WEEKDAYS` per language; `load_config` reads `lang`; `render_header` and `header_hook` take the language; every message through `say()`; `status` names the language; `main`, a new `split_lang` and `run_command`; header and `VERSION`)
- Modify: `plugins/header-footer/tests/helpers.py`, `test_header.py`, `test_cli.py`; `plugins/header-footer/CHANGELOG.md`
- Generated: `plugins/header-footer/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`

**Interfaces:**
- Consumes: the resolution order and `CAPYBARA_LANG` of Task 2b.
- Produces: `LANGS`, `DEFAULT_LANG`, `ENV_LANG`, `CLI_LANG`, `FIELD_HELP[lang][section]`, `HEADER_FIELDS`/`FOOTER_FIELDS` (the English help, so the names stay where the code and the tests look for them), `MSG`, `env_lang()`, `pick_lang(*candidates)`, `say(msg_id, /, **values)`, `WEEKDAYS[lang]`, `render_header(header, cwd, now, lang=DEFAULT_LANG)`, `print_status(st, cfg, source)`, `split_lang(args)`, `run_command(argv, stdin)`; an optional top-level `"lang"` in `header-footer.json` (`load_config` keeps it only when it is `en` or `pt-BR`; the CLI refuses another value, the hooks ignore it); the command `lang en|pt-BR|auto`; `--lang` anywhere on a CLI command (the hooks take none); `status --json` gains `"lang"`.
- What changes and what does not (see the rulings): the header's `weekday` (`Mon` … `Sun`, pt-BR `seg` … `dom`) and every message of the command line follow the language: `status`, its problems, `fields`, the toggles, the errors. The footer does not change in either language (it must stay byte-identical to the Node status line it ports: its texts are `running`/`waiting`/`idle`, numbers and units), and neither does `INSTRUCTION`, the text that goes with the `<reply-header>` line: it is addressed to the model. `hooks/hooks.json` and `PLUGIN_HOOKS` are unchanged. A `CAPYBARA_LANG` that is neither `en` nor `pt-BR` is ignored by the hooks and the commands and listed by `status` as a problem.
- Consumed by Task 6 (the header-footer skill, README and `CLAUDE.md`).

- [ ] **Step 1: Keep the environment out of the suite**


In `plugins/header-footer/tests/helpers.py`, replace:

```python
from unittest import mock

```

with:

```python
from unittest import mock

os.environ.pop("CAPYBARA_LANG", None)  # the defaults the suite pins must not depend on the shell that runs it

```

- [ ] **Step 2: Update the tests that pin the old text and write the new ones**


In `plugins/header-footer/tests/test_header.py`, replace:

```python
        self.assertEqual(self.hf.render_header(h, "/nonexistent", NOW), "🕐 sex · 16/10 · 09:05")
```

with:

```python
        self.assertEqual(self.hf.render_header(h, "/nonexistent", NOW), "🕐 Fri · 16/10 · 09:05")
        self.assertEqual(self.hf.render_header(h, "/nonexistent", NOW, "pt-BR"), "🕐 sex · 16/10 · 09:05")
```

In `plugins/header-footer/tests/test_cli.py`, replace:

```python
        self.assertIn("nao e JSON valido", err)
```

with:

```python
        self.assertIn("is not valid JSON", err)
```

In `plugins/header-footer/tests/test_cli.py`, replace:

```python
        self.assertTrue(any("duplicado" in p for p in st["problems"]))
```

with:

```python
        self.assertTrue(any("comes out twice" in p for p in st["problems"]))
```

In `plugins/header-footer/tests/test_cli.py`, replace:

```python
        return [p for p in self.status()[1]["problems"] if "nenhum hook" in p]
```

with:

```python
        return [p for p in self.status()[1]["problems"] if "no hook runs it" in p]
```

In `plugins/header-footer/tests/test_cli.py`, replace:

```python
        self.assertIn("tudo certo", strip_ansi(out))
```

with:

```python
        self.assertIn("all good", strip_ansi(out))
        rc, out, _ = self.run_cli("status", "--lang", "pt-BR")
        self.assertIn("tudo certo", strip_ansi(out))
```

The new tests: the tables, an AST guard over the functions that print, the weekday from the config then `CAPYBARA_LANG`, the instruction and the footer identical in both languages, the `lang` command, a bad flag or config value, and a bad `CAPYBARA_LANG` reported by `status` only:

Append to `plugins/header-footer/tests/test_cli.py` (after a blank line):

```python
# ---------------------------------------------------------------- the language (header-footer 0.4.0)

import ast
import re
from datetime import datetime

from helpers import SCRIPT

FRIDAY = datetime(2026, 10, 16, 9, 5, 7)
HF_PRINTING = ("load_config", "type_name", "state_hook", "load_settings", "collect_status", "preview_header",
               "preview_footer", "print_status", "parse_fields", "toggle", "main", "run_command", "split_lang")
HF_PT_WORDS = {"nao", "valido", "precisa", "objeto", "texto", "lista", "textos", "evento", "estado", "invalido", "antigo",
               "duplicado", "remova", "entrada", "campo", "desconhecido", "ligado", "desligado", "nenhum", "executa",
               "habilitado", "usuario", "projeto", "aponta", "rode", "copia", "versao", "novo", "gravado", "existe",
               "instalado", "sai", "vazio", "linha", "topo", "resposta", "quando", "diagnostico", "tudo", "certo",
               "informe", "menos", "disponiveis", "vale", "proximo", "outra", "troca", "ganha", "deste", "vou", "mao",
               "reinicie", "mudar", "registrados", "removidos", "uso", "formato", "funciona", "plataforma", "comando",
               "erro", "idioma", "padrao", "depois"}


class LanguageTablesTest(ConfigDirCase):
    def test_the_tables_agree_in_both_languages_and_the_messages_are_plain_ascii(self):
        en, pt = self.hf.MSG["en"], self.hf.MSG["pt-BR"]
        self.assertEqual(set(en), set(pt))
        for key in en:
            with self.subTest(key=key):
                self.assertEqual(set(re.findall(r"\{(\w+)\}", en[key])), set(re.findall(r"\{(\w+)\}", pt[key])))
                self.assertTrue(en[key].isascii() and pt[key].isascii(), key)
        for section in ("header", "footer"):
            self.assertEqual(list(self.hf.FIELD_HELP["en"][section]), list(self.hf.FIELD_HELP["pt-BR"][section]))
        self.assertEqual([len(days) for days in self.hf.WEEKDAYS.values()], [7, 7])
        self.assertEqual((pt["s_all_good"], pt["s_diagnosis"]), ("tudo certo", "DIAGNOSTICO"))  # the 0.3.0 output

    def test_no_portuguese_literal_is_left_in_the_functions_that_print(self):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        found = []
        for fn in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in HF_PRINTING):
            body = fn.body[1:] if isinstance(fn.body[0], ast.Expr) and isinstance(fn.body[0].value, ast.Constant) else fn.body
            for node in (n for stmt in body for n in ast.walk(stmt)):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if set(re.split(r"[^a-z]+", node.value.lower())) & HF_PT_WORDS:
                        found.append(f"{fn.name}: {node.value!r}")
        self.assertEqual(found, [], "Portuguese left outside MSG:\n" + "\n".join(found))


class LanguageTest(ConfigDirCase):
    def hook(self, prompt_id):
        payload = json.dumps({"session_id": "s1", "prompt": "hi", "prompt_id": prompt_id, "cwd": "/nonexistent"})
        return self.hf.header_hook(payload, now=FRIDAY)

    def test_the_weekday_follows_the_config_then_capybara_lang_and_the_instruction_stays_english(self):
        self.write_config({"header": {"fields": ["weekday"]}})
        self.assertTrue(self.hook("p1").startswith("<reply-header>🕐 Fri</reply-header>\n"))
        with mock.patch.dict(os.environ, {"CAPYBARA_LANG": "pt-BR"}):
            out = self.hook("p2")
        self.assertTrue(out.startswith("<reply-header>🕐 sex</reply-header>\n"))
        self.assertIn(self.hf.INSTRUCTION, out)  # addressed to the model: English in both languages
        self.write_config({"lang": "en", "header": {"fields": ["weekday"]}})
        with mock.patch.dict(os.environ, {"CAPYBARA_LANG": "pt-BR"}):
            self.assertTrue(self.hook("p3").startswith("<reply-header>🕐 Fri</reply-header>\n"))

    def test_the_footer_is_the_same_in_both_languages(self):
        payload = json.dumps({"model": {"display_name": "Opus"}, "context_window": {"remaining_percentage": 62},
                              "cost": {"total_cost_usd": 1.84}})
        outputs = []
        for lang in ("en", "pt-BR"):
            self.write_config({"lang": lang, "footer": {"fields": ["model", "context", "cost"]}})
            outputs.append(self.run_cli("footer", stdin=payload)[1])
        self.assertEqual(outputs[0], outputs[1])
        self.assertIn("Opus", outputs[0])

    def test_the_lang_command_saves_and_clears_the_config(self):
        rc, out, _ = self.run_cli("lang", "pt-BR")
        self.assertEqual((rc, out), (0, "lang: pt-BR\n"))
        self.assertEqual(self.read_json("header-footer.json")["lang"], "pt-BR")
        self.assertIn("IDIOMA: pt-BR (header-footer.json)", strip_ansi(self.run_cli("status")[1]))
        self.assertIn("  time     hora (header-format)", self.run_cli("fields")[1])
        self.assertIn("  time     time (header-format)", self.run_cli("fields", "--lang", "en")[1])
        rc, out, _ = self.run_cli("lang", "auto")
        self.assertEqual((rc, out), (0, "lang: auto (CAPYBARA_LANG, then en)\n"))
        self.assertNotIn("lang", self.read_json("header-footer.json"))
        rc, _, err = self.run_cli("lang", "pt")
        self.assertEqual((rc, err), (2, "error: usage: lang en|pt-BR|auto\n"))

    def test_a_bad_flag_or_a_bad_config_lang_is_a_usage_error_but_the_hooks_keep_working(self):
        rc, _, err = self.run_cli("status", "--lang", "xx")
        self.assertEqual((rc, err), (2, "error: --lang must be en or pt-BR\n"))
        self.write_config({"lang": "pt", "header": {"fields": ["weekday"]}})
        rc, _, err = self.run_cli("status")
        self.assertEqual(rc, 2)
        self.assertIn("lang must be en or pt-BR", err)
        self.assertTrue(self.hook("p1").startswith("<reply-header>🕐 Fri</reply-header>\n"))

    def test_a_bad_capybara_lang_is_a_status_problem_and_nothing_else(self):
        with mock.patch.dict(os.environ, {"CAPYBARA_LANG": "pt_BR"}):
            rc, out, err = self.run_cli("status", "--json")
            self.assertEqual(err, "")
            self.assertTrue(any("CAPYBARA_LANG=pt_BR is not en or pt-BR" in p for p in json.loads(out)["problems"]))
            self.assertEqual(json.loads(out)["lang"], "en")
        self.assertEqual(self.hf.CLI_LANG, "en")  # main() put the default back
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/header-footer/tests 2>&1 | tail -n 3`

Expected: `FAILED (` with failures and errors: `hf.MSG`, `hf.FIELD_HELP` and the `lang` command do not exist, the weekday is `sex` and the messages are Portuguese.

- [ ] **Step 4: The usage, the tables and the helpers**


In `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, replace:

```python
  python3 -I header_footer.py separator header|footer " · "
  python3 -I header_footer.py preview | fields

```

with:

```python
  python3 -I header_footer.py separator header|footer " · "
  python3 -I header_footer.py lang en|pt-BR|auto     # the language of the messages and of the weekday (auto: CAPYBARA_LANG, then en)
  python3 -I header_footer.py preview | fields

Every command except the hooks takes --lang en|pt-BR (default: the config's lang, then CAPYBARA_LANG, then en).
The footer and the instruction to Claude are the same in both languages.

```

In `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, replace:

```python
HEADER_FIELDS = {
    "time": "hora (header-format)",
    "date": "data (header-format --date)",
    "weekday": "dia da semana: seg..dom",
    "dir": "pasta atual",
    "repo": "nome do repositorio git",
    "branch": "branch git atual",
}
FOOTER_FIELDS = {
    "state": "running Nm enquanto o Claude trabalha, waiting quando espera voce, idle quando termina",
    "gsd": "bloco do GSD (modelo | tarefa | pasta | contexto), se o GSD estiver instalado",
    "model": "modelo",
    "dir": "pasta atual",
    "branch": "branch git atual",
    "context": "ctx N% usado",
    "tokens": "tokens acumulados da sessao (entrada e saida)",
    "limits": "janelas 5h/7d do plano e o tempo ate zerar",
    "cost": "custo estimado da sessao em US$",
    "clock": "relogio HH:MM",
}
```

with:

```python
LANGS = ("en", "pt-BR")  # languages of the messages and of the header's weekday; the first is the default
DEFAULT_LANG = "en"
ENV_LANG = "CAPYBARA_LANG"  # one shell-wide default for every Capybara Toolbox script
CLI_LANG = DEFAULT_LANG  # the language of this run's messages, set by main() only

# The help of each field (printed by `fields`), per language. The names are the config's: the same in both.
FIELD_HELP = {
    "en": {
        "header": {
            "time": "time (header-format)",
            "date": "date (header-format --date)",
            "weekday": "weekday: Mon..Sun",
            "dir": "current folder",
            "repo": "name of the git repository",
            "branch": "current git branch",
        },
        "footer": {
            "state": "running Nm while Claude works, waiting while it waits for you, idle when it stops",
            "gsd": "the GSD block (model | task | folder | context), when GSD is installed",
            "model": "model",
            "dir": "current folder",
            "branch": "current git branch",
            "context": "ctx N% used",
            "tokens": "session tokens so far (input and output)",
            "limits": "the plan's 5h/7d windows and the time until they reset",
            "cost": "estimated session cost in US$",
            "clock": "clock HH:MM",
        },
    },
    "pt-BR": {
        "header": {
            "time": "hora (header-format)",
            "date": "data (header-format --date)",
            "weekday": "dia da semana: seg..dom",
            "dir": "pasta atual",
            "repo": "nome do repositorio git",
            "branch": "branch git atual",
        },
        "footer": {
            "state": "running Nm enquanto o Claude trabalha, waiting quando espera voce, idle quando termina",
            "gsd": "bloco do GSD (modelo | tarefa | pasta | contexto), se o GSD estiver instalado",
            "model": "modelo",
            "dir": "pasta atual",
            "branch": "branch git atual",
            "context": "ctx N% usado",
            "tokens": "tokens acumulados da sessao (entrada e saida)",
            "limits": "janelas 5h/7d do plano e o tempo ate zerar",
            "cost": "custo estimado da sessao em US$",
            "clock": "relogio HH:MM",
        },
    },
}
HEADER_FIELDS = FIELD_HELP["en"]["header"]  # the names a header may show
FOOTER_FIELDS = FIELD_HELP["en"]["footer"]  # the names a footer may show

# Every message of the command line (and every `status` problem), in both languages. Same keys and {placeholders}
# in both (a test enforces it); both plain ASCII, so the pt-BR side is the accent-free Portuguese of 0.3.0. The
# footer is not here: it must stay byte-identical to the Node status line it ports, in either language.
MSG = {
    "en": {
        "cfg_json": "{path} is not valid JSON: {exc}", "cfg_obj": "{path} must be a JSON object",
        "cfg_type": "{path}: {key} must be {kind}", "t_bool": "true/false", "t_str": "text", "t_list": "a list of strings",
        "cfg_lang": "{path}: lang must be en or pt-BR",
        "bad_event": "invalid state event: {event} (use {events})",
        "p_legacy": "an older header hook in settings.json ({names}): with the plugin installed the header comes out twice; remove that entry from settings.json",
        "p_field": "unknown {section} field: {field}",
        "p_no_hook": "header on, but no hook runs it: the plugin is not enabled in the user's settings.json and there is no `wire-hooks` (a project settings.json, which status does not read, may still enable the plugin)",
        "p_footer": "footer on in the config, but statusLine does not point to this script: run `on footer`",
        "p_stale": "the copy in {path} is at version {copy}, the plugin at {version}: run `on footer` (or `wire-hooks`) again",
        "absent": "missing",
        "p_python": "the python written into settings.json no longer exists ({interp}): run `on footer` (or `wire-hooks`) again",
        "p_gsd": "the gsd field is configured, but GSD (or node) is not installed: the field comes out empty",
        "p_env": "CAPYBARA_LANG={value} is not en or pt-BR: it is ignored",
        "empty": "(empty)", "on": "on", "off": "off",
        "s_header": "HEADER (the line at the top of the reply)", "s_config": "  config:   {state}  fields={fields}",
        "s_hook": "  hook:     {hook}", "s_plugin_hook": "the plugin's hooks.json (when installed from the marketplace)",
        "s_footer": "FOOTER (status line)", "s_wiring": "  wiring:   {wiring}", "s_wired": "statusLine points to this script",
        "s_diagnosis": "DIAGNOSIS", "s_all_good": "all good", "s_lang": "LANGUAGE: {lang} ({source})",
        "src_flag": "--lang", "src_config": "header-footer.json", "src_env": "CAPYBARA_LANG", "src_default": "default",
        "no_field": "give at least one {section} field",
        "bad_fields": "unknown {section} field(s): {bad}. Available: {known}",
        "header_toggled": "header: {state} (takes effect on the next prompt)",
        "foreign_line": "another statusLine already exists ({command}); use `on footer --replace` to replace it (settings.json gets a backup)",
        "not_ours": "the current statusLine is not this script's; I will not remove it (edit settings.json by hand)",
        "footer_toggled": "footer: {state} (settings.json backed up; restart Claude Code if it does not change)",
        "hooks_wired": "hooks registered in settings.json (backed up): {events}",
        "hooks_unwired": "hooks removed from settings.json (backed up): {events}",
        "format_usage": 'usage: header-format "%H:%M" [--date]',
        "format_bad": "the format {fmt} does not work on this platform (on Windows, %-H does not exist)",
        "lang_usage": "usage: lang en|pt-BR|auto", "lang_set": "lang: {lang}", "lang_auto": "lang: auto (CAPYBARA_LANG, then en)",
        "bad_flag": "--lang must be en or pt-BR", "bad_command": "invalid command: {command} (use --help)", "error": "error: {e}",
    },
    "pt-BR": {
        "cfg_json": "{path} nao e JSON valido: {exc}", "cfg_obj": "{path} precisa ser um objeto JSON",
        "cfg_type": "{path}: {key} precisa ser {kind}", "t_bool": "true/false", "t_str": "texto", "t_list": "lista de textos",
        "cfg_lang": "{path}: lang precisa ser en ou pt-BR",
        "bad_event": "evento de estado invalido: {event} (use {events})",
        "p_legacy": "hook de header antigo no settings.json ({names}): com o plugin instalado o header sai duplicado; remova essa entrada do settings.json",
        "p_field": "campo de {section} desconhecido: {field}",
        "p_no_hook": "header ligado, mas nenhum hook o executa: o plugin nao esta habilitado no settings.json do usuario e nao ha `wire-hooks` (um settings.json de projeto, que o status nao le, ainda pode habilitar o plugin)",
        "p_footer": "footer ligado na config, mas a statusLine nao aponta para este script: rode `on footer`",
        "p_stale": "a copia em {path} esta na versao {copy}, o plugin na {version}: rode `on footer` (ou `wire-hooks`) de novo",
        "absent": "ausente",
        "p_python": "o python gravado no settings.json nao existe mais ({interp}): rode `on footer` (ou `wire-hooks`) de novo",
        "p_gsd": "campo gsd configurado, mas o GSD (ou o node) nao esta instalado: o campo sai vazio",
        "p_env": "CAPYBARA_LANG={value} nao e en nem pt-BR: fica ignorado",
        "empty": "(vazio)", "on": "ligado", "off": "desligado",
        "s_header": "HEADER (linha no topo da resposta)", "s_config": "  config:   {state}  campos={fields}",
        "s_hook": "  hook:     {hook}", "s_plugin_hook": "hooks.json do plugin (quando instalado pelo marketplace)",
        "s_footer": "FOOTER (status line)", "s_wiring": "  wiring:   {wiring}", "s_wired": "statusLine aponta para este script",
        "s_diagnosis": "DIAGNOSTICO", "s_all_good": "tudo certo", "s_lang": "IDIOMA: {lang} ({source})",
        "src_flag": "--lang", "src_config": "header-footer.json", "src_env": "CAPYBARA_LANG", "src_default": "padrao",
        "no_field": "informe ao menos um campo de {section}",
        "bad_fields": "campo(s) de {section} desconhecido(s): {bad}. Disponiveis: {known}",
        "header_toggled": "header: {state} (vale no proximo prompt)",
        "foreign_line": "ja existe outra statusLine ({command}); use `on footer --replace` para troca-la (o settings.json ganha backup)",
        "not_ours": "a statusLine atual nao e deste script; nao vou remove-la (edite o settings.json a mao)",
        "footer_toggled": "footer: {state} (settings.json com backup; reinicie o Claude Code se nao mudar)",
        "hooks_wired": "hooks registrados no settings.json (com backup): {events}",
        "hooks_unwired": "hooks removidos no settings.json (com backup): {events}",
        "format_usage": 'uso: header-format "%H:%M" [--date]',
        "format_bad": "formato {fmt} nao funciona nesta plataforma (no Windows, %-H nao existe)",
        "lang_usage": "uso: lang en|pt-BR|auto", "lang_set": "lang: {lang}", "lang_auto": "lang: auto (CAPYBARA_LANG, depois en)",
        "bad_flag": "--lang precisa ser en ou pt-BR", "bad_command": "comando invalido: {command} (use --help)", "error": "erro: {e}",
    },
}


def env_lang():
    """CAPYBARA_LANG when it is exactly one of LANGS, else None. A bad value never breaks a hook or a command;
    `status` lists it as a problem."""
    value = os.environ.get(ENV_LANG)
    return value if value in LANGS else None


def pick_lang(*candidates):
    """The first candidate that is one of LANGS (--lang, then the config's lang), then CAPYBARA_LANG, then en."""
    for cand in candidates:
        if isinstance(cand, str) and cand in LANGS:
            return cand
    return env_lang() or DEFAULT_LANG


def say(msg_id, /, **values):
    """One message in the language of this run. The template is ours, the values are data."""
    return MSG[CLI_LANG][msg_id].format(**values)
```

In `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, replace:

```python
WEEKDAYS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
```

with:

```python
WEEKDAYS = {"en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], "pt-BR": ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]}
```

In `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, replace:

```python
INSTRUCTION = (
```

with:

```python
# The instruction is addressed to the model, not to the user: it is English whatever the language.
INSTRUCTION = (
```

- [ ] **Step 5: The config's `lang`, the weekday and every message through `say()`**


In `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, replace:

```python
    except (OSError, ValueError) as exc:
        if strict:
            raise UsageError(f"{path} nao e JSON valido: {exc}")
        return cfg
    if not isinstance(raw, dict):
        if strict:
            raise UsageError(f"{path} precisa ser um objeto JSON")
        return cfg
```

with:

```python
    except (OSError, ValueError) as exc:
        if strict:
            raise UsageError(say("cfg_json", path=path, exc=exc))
        return cfg
    if not isinstance(raw, dict):
        if strict:
            raise UsageError(say("cfg_obj", path=path))
        return cfg
```

In `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, replace:

```python
                    raise UsageError(f"{path}: {section}.{key} precisa ser {type_name(DEFAULTS[section][key])}")
                continue
            cfg[section][key] = value
    return cfg
```

with:

```python
                    raise UsageError(say("cfg_type", path=path, key=f"{section}.{key}", kind=type_name(DEFAULTS[section][key])))
                continue
            cfg[section][key] = value
    lang = raw.get("lang")  # top level, optional: the language of the header's weekday and of the messages
    if lang in LANGS:
        cfg["lang"] = lang
    elif lang is not None and strict:
        raise UsageError(say("cfg_lang", path=path))
    return cfg
```

In `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, replace:

```python
    return {bool: "true/false", str: "texto", list: "lista de textos"}[type(default)]
```

with:

```python
    return say({bool: "t_bool", str: "t_str", list: "t_list"}[type(default)])
```

In `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, replace:

```python
def render_header(header, cwd, now):
    """The header line, or "" when every field came out empty."""
    values = {
        "time": lambda: format_time(now, header, "time_format"),
        "date": lambda: format_time(now, header, "date_format"),
        "weekday": lambda: WEEKDAYS[now.weekday()],
```

with:

```python
def render_header(header, cwd, now, lang=DEFAULT_LANG):
    """The header line, or "" when every field came out empty. Only the weekday depends on `lang`."""
    values = {
        "time": lambda: format_time(now, header, "time_format"),
        "date": lambda: format_time(now, header, "date_format"),
        "weekday": lambda: WEEKDAYS[lang if lang in LANGS else DEFAULT_LANG][now.weekday()],
```

In `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, replace:

```python
def header_hook(stdin_text, now=None):
    header = load_config()["header"]
```

with:

```python
def header_hook(stdin_text, now=None):
    cfg = load_config()
    header = cfg["header"]
```

In `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, replace:

```python
    line = render_header(header, payload.get("cwd") or os.getcwd(), now)
```

with:

```python
    line = render_header(header, payload.get("cwd") or os.getcwd(), now, pick_lang(cfg.get("lang")))
```

In `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, replace:

```python
        raise UsageError(f"evento de estado invalido: {event} (use {', '.join(STATE_EVENTS)})")
```

with:

```python
        raise UsageError(say("bad_event", event=event, events=", ".join(STATE_EVENTS)))
```

In `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, replace:

```python
    except ValueError as exc:
        raise UsageError(f"{path} nao e JSON valido: {exc}")
    if not isinstance(data, dict):
        raise UsageError(f"{path} precisa ser um objeto JSON")
    return data
```

with:

```python
    except ValueError as exc:
        raise UsageError(say("cfg_json", path=path, exc=exc))
    if not isinstance(data, dict):
        raise UsageError(say("cfg_obj", path=path))
    return data
```

In `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, replace:

```python
        problems.append("hook de header antigo no settings.json (" + ", ".join(sorted({n for n in LEGACY_HEADER_HOOKS if any(n in c for c in legacy)}))
                        + "): com o plugin instalado o header sai duplicado; remova essa entrada do settings.json")
```

with:

```python
        problems.append(say("p_legacy", names=", ".join(sorted({n for n in LEGACY_HEADER_HOOKS if any(n in c for c in legacy)}))))
```

In `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, replace:

```python
                problems.append(f"campo de {section} desconhecido: {f}")
```

with:

```python
                problems.append(say("p_field", section=section, field=f))
```

In `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, replace:

```python
        problems.append("header ligado, mas nenhum hook o executa: o plugin nao esta habilitado no settings.json do usuario e "
                        "nao ha `wire-hooks` (um settings.json de projeto, que o status nao le, ainda pode habilitar o plugin)")
```

with:

```python
        problems.append(say("p_no_hook"))
```

In `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, replace:

```python
        problems.append("footer ligado na config, mas a statusLine nao aponta para este script: rode `on footer`")
```

with:

```python
        problems.append(say("p_footer"))
```

In `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, replace:

```python
        problems.append(f"a copia em {stable_script()} esta na versao {copy_version or 'ausente'}, o plugin na {VERSION}: rode `on footer` (ou `wire-hooks`) de novo")
```

with:

```python
        problems.append(say("p_stale", path=stable_script(), copy=copy_version or say("absent"), version=VERSION))
```

In `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, replace:

```python
        problems.append(f"o python gravado no settings.json nao existe mais ({interp}): rode `on footer` (ou `wire-hooks`) de novo")
```

with:

```python
        problems.append(say("p_python", interp=interp))
```

In `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, replace:

```python
        problems.append("campo gsd configurado, mas o GSD (ou o node) nao esta instalado: o campo sai vazio")
    return {
        "version": VERSION,
        "config": str(config_path()),
```

with:

```python
        problems.append(say("p_gsd"))
    raw_env = os.environ.get(ENV_LANG)
    if raw_env is not None and raw_env not in LANGS:  # ignored everywhere; this is where the person learns why
        problems.append(say("p_env", value=raw_env))
    return {
        "version": VERSION,
        "config": str(config_path()),
        "lang": CLI_LANG,
```

In `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, replace:

```python
def preview_header(cfg):
    return render_header(cfg["header"], os.getcwd(), datetime.now()) or "(vazio)"


def preview_footer(cfg):
    return render_footer(sample_footer_payload(), footer=cfg["footer"]) or "(vazio)"


def print_status(st, cfg):
    h, f = st["header"], st["footer"]
    print("HEADER (linha no topo da resposta)")
    print(f"  config:   {'ligado' if h['enabled'] else 'desligado'}  campos={','.join(h['fields'])}")
    print(f"  hook:     {'settings.json' if h['settings_hook'] else 'hooks.json do plugin (quando instalado pelo marketplace)'}")
    print(f"  preview:  {preview_header(cfg)}")
    print("FOOTER (status line)")
    print(f"  config:   {'ligado' if f['enabled'] else 'desligado'}  campos={','.join(f['fields'])}")
    print(f"  wiring:   {'statusLine aponta para este script' if f['wired'] else 'statusLine = ' + json.dumps(f['status_line'])}")
    print(f"  preview:  {preview_footer(cfg)}")
    print("DIAGNOSTICO")
    for p in st["problems"] or ["tudo certo"]:
        print(f"  {'! ' if st['problems'] else 'ok '}{p}")
```

with:

```python
def preview_header(cfg):
    """The header as the hook renders it now: its weekday follows the config's lang, then CAPYBARA_LANG."""
    return render_header(cfg["header"], os.getcwd(), datetime.now(), pick_lang(cfg.get("lang"))) or say("empty")


def preview_footer(cfg):
    return render_footer(sample_footer_payload(), footer=cfg["footer"]) or say("empty")


def print_status(st, cfg, source="src_default"):
    h, f = st["header"], st["footer"]
    print(say("s_header"))
    print(say("s_config", state=say("on" if h["enabled"] else "off"), fields=",".join(h["fields"])))
    print(say("s_hook", hook="settings.json" if h["settings_hook"] else say("s_plugin_hook")))
    print(f"  preview:  {preview_header(cfg)}")
    print(say("s_footer"))
    print(say("s_config", state=say("on" if f["enabled"] else "off"), fields=",".join(f["fields"])))
    print(say("s_wiring", wiring=say("s_wired") if f["wired"] else "statusLine = " + json.dumps(f["status_line"])))
    print(f"  preview:  {preview_footer(cfg)}")
    print(say("s_lang", lang=st["lang"], source=say(source)))
    print(say("s_diagnosis"))
    for p in st["problems"] or [say("s_all_good")]:
        print(f"  {'! ' if st['problems'] else 'ok '}{p}")
```

In `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, replace:

```python
        raise UsageError(f"informe ao menos um campo de {section}")
    bad = [f for f in fields if f not in known]
    if bad:
        raise UsageError(f"campo(s) de {section} desconhecido(s): {', '.join(bad)}. Disponiveis: {', '.join(known)}")
```

with:

```python
        raise UsageError(say("no_field", section=section))
    bad = [f for f in fields if f not in known]
    if bad:
        raise UsageError(say("bad_fields", section=section, bad=", ".join(bad), known=", ".join(known)))
```

In `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, replace:

```python
        print(f"header: {'ligado' if on else 'desligado'} (vale no proximo prompt)")
```

with:

```python
        print(say("header_toggled", state=say("on" if on else "off")))
```

In `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, replace:

```python
        raise UsageError("ja existe outra statusLine (" + json.dumps(settings["statusLine"].get("command"))
                         + "); use `on footer --replace` para troca-la (o settings.json ganha backup)")
```

with:

```python
        raise UsageError(say("foreign_line", command=json.dumps(settings["statusLine"].get("command"))))
```

In `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, replace:

```python
        raise UsageError("a statusLine atual nao e deste script; nao vou remove-la (edite o settings.json a mao)")
```

with:

```python
        raise UsageError(say("not_ours"))
```

In `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, replace:

```python
    print(f"footer: {'ligado' if on else 'desligado'} (settings.json com backup; reinicie o Claude Code se nao mudar)")
```

with:

```python
    print(say("footer_toggled", state=say("on" if on else "off")))
```

`main` keeps `--help` and puts the language back after the run; `run_command` reads `--lang` anywhere in the arguments, sets the language (the hooks: the config, then `CAPYBARA_LANG`), and gains the `lang` command:

In `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, replace everything from the line `def main(argv, stdin=None):` up to (not including) the line `def utf8_stdio():` with:

```python
def split_lang(args):
    """(the value of --lang or None, the other arguments). `--lang X` and `--lang=X` may stand anywhere."""
    flag, rest, i = None, [], 0
    while i < len(args):
        if args[i] == "--lang":
            flag = args[i + 1] if i + 1 < len(args) else ""
            i += 2
            continue
        if args[i].startswith("--lang="):
            flag = args[i][len("--lang="):]
        else:
            rest.append(args[i])
        i += 1
    return flag, rest


def main(argv, stdin=None):
    """Run one command. The language of its messages is set here: --lang, then the config's lang, then
    CAPYBARA_LANG, then en (the hooks take no flags: the config, then CAPYBARA_LANG). It is put back afterwards,
    so an in-process caller (the tests) never inherits another run's language."""
    global CLI_LANG
    stdin = stdin if stdin is not None else sys.stdin
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    before = CLI_LANG
    try:
        return run_command(argv, stdin)
    finally:
        CLI_LANG = before


def run_command(argv, stdin):
    global CLI_LANG
    cmd, (flag, args) = argv[0], split_lang(argv[1:])
    CLI_LANG = pick_lang(load_config().get("lang"))  # what a broken config or a bad flag is reported in
    try:
        if cmd == "header-hook":
            sys.stdout.write(header_hook(stdin.read()))
            return 0
        if cmd == "footer":
            sys.stdout.write(render_footer(stdin.read()))
            return 0
        if cmd == "state-hook" and len(args) == 1:
            state_hook(args[0], stdin.read())
            return 0
        if flag is not None and flag not in LANGS:
            raise UsageError(say("bad_flag"))
        CLI_LANG = pick_lang(flag)  # a broken config is reported in --lang, else CAPYBARA_LANG, else en
        cfg = load_config(strict=True)
        CLI_LANG = pick_lang(flag, cfg.get("lang"))
        source = "src_flag" if flag else "src_config" if cfg.get("lang") else "src_env" if env_lang() else "src_default"
        if cmd == "status":
            st = collect_status(cfg, load_settings())
            if "--json" in args:
                print(dump_json(st), end="")
            else:
                print_status(st, cfg, source)
            return 1 if st["problems"] else 0
        if cmd in ("on", "off") and args[:1] in (["header"], ["footer"]) and set(args[1:]) <= {"--replace"}:
            toggle(cfg, args[0], cmd == "on", replace="--replace" in args)
        elif cmd in ("wire-hooks", "unwire-hooks") and not args:
            settings = load_settings()
            if cmd == "wire-hooks":
                install_stable_copy()
            wire_hooks(settings, cmd == "wire-hooks")
            save_settings(settings)
            print(say("hooks_wired" if cmd == "wire-hooks" else "hooks_unwired", events=", ".join(PLUGIN_HOOKS)))
        elif cmd == "header-fields" and len(args) == 1:
            set_and_show(cfg, "header", "fields", parse_fields(args[0], HEADER_FIELDS, "header"))
        elif cmd == "footer-fields" and len(args) == 1:
            set_and_show(cfg, "footer", "fields", parse_fields(args[0], FOOTER_FIELDS, "footer"))
        elif cmd == "header-format" and args:
            key = "date_format" if "--date" in args else "time_format"
            fmt = [a for a in args if a != "--date"]
            if len(fmt) != 1 or "%" not in fmt[0]:
                raise UsageError(say("format_usage"))
            try:
                datetime.now().strftime(fmt[0])
            except ValueError:
                raise UsageError(say("format_bad", fmt=fmt[0]))
            set_and_show(cfg, "header", key, fmt[0])
        elif cmd == "header-icon" and len(args) == 1:
            set_and_show(cfg, "header", "icon", args[0])
        elif cmd == "separator" and len(args) == 2 and args[0] in ("header", "footer"):
            set_and_show(cfg, args[0], "separator", args[1])
        elif cmd == "lang" and len(args) == 1 and args[0] in LANGS + ("auto",):
            if args[0] == "auto":
                cfg.pop("lang", None)
            else:
                cfg["lang"] = args[0]
            save_config(cfg)
            CLI_LANG = pick_lang(flag, cfg.get("lang"))
            print(say("lang_auto") if args[0] == "auto" else say("lang_set", lang=args[0]))
        elif cmd == "lang":
            raise UsageError(say("lang_usage"))
        elif cmd == "preview" and not args:
            print(f"header: {preview_header(cfg)}")
            print(f"footer: {preview_footer(cfg)}")
        elif cmd == "fields" and not args:
            for section in ("header", "footer"):
                print(section.upper())
                for k, v in FIELD_HELP[CLI_LANG][section].items():
                    print(f"  {k:8} {v}")
        else:
            raise UsageError(say("bad_command", command=" ".join(argv)))
    except UsageError as exc:
        print(say("error", e=exc), file=sys.stderr)
        return 2
    return 0


```

- [ ] **Step 6: Run the suite**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/header-footer/tests 2>&1 | tail -n 3 && PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s plugins/header-footer/tests 2>&1 | tail -n 3`

Expected: `Ran 94 tests` and `OK` on both Pythons.

- [ ] **Step 7: Release 0.4.0**

`DAY` is the day of execution:


In `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, replace:

```python
# header-footer 0.3.0 - 
```

with:

```python
# header-footer 0.4.0 - 
```

In `plugins/header-footer/skills/header-footer/scripts/header_footer.py`, replace:

```python
VERSION = "0.3.0"
```

with:

```python
VERSION = "0.4.0"
```

In `plugins/header-footer/CHANGELOG.md`, replace:

```markdown
## [Unreleased]

## [0.3.0] - 2026-10-19
```

with:

```markdown
## [Unreleased]

## [0.4.0] - DAY

### Added
- **The language** of the messages and of the header's weekday: English by default, pt-BR on request. `header-footer.json` takes a top-level `"lang"` (`"en"` or `"pt-BR"`), the new command `lang en|pt-BR|auto` sets or clears it, every command takes `--lang`, and the environment variable `CAPYBARA_LANG` is the default when the config has none (every Capybara Toolbox script reads the same variable). The hooks take no flags: they read the config, then `CAPYBARA_LANG`.
- `status` names the language in use and where it came from (`LANGUAGE: en (default)`), lists a `CAPYBARA_LANG` that is neither `en` nor `pt-BR` as a problem (every other path ignores it) and has a `lang` key in `--json`.

### Changed
- **The default is English**: the `weekday` field shows `Mon` … `Sun` (pt-BR `seg` … `dom`), and every message of the command line (`status` and its problems, `fields`, the toggles, the errors: `error:`, pt-BR `erro:`) is English unless `lang` or `CAPYBARA_LANG` says `pt-BR`. The pt-BR text is the accent-free Portuguese of 0.3.0. The `--help` text was already English.
- The footer and the instruction that goes with the `<reply-header>` line are the same in both languages: the footer stays byte-identical to the Node status line it ports, and the instruction is addressed to the model.

## [0.3.0] - 2026-10-19
```

Run: `python3 plugins/header-footer/tools/sync.py && python3 tools/marketplace.py && python3 plugins/header-footer/tools/sync.py --check && python3 tools/marketplace.py --check && echo in-sync`

Expected: `updated: .claude-plugin/plugin.json`, `updated: .claude-plugin/marketplace.json`, `in-sync`.

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/header-footer/tests 2>&1 | tail -n 3 && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests 2>&1 | tail -n 1`

Expected: `Ran 94 tests` and `OK`, then `OK` for the catalog.

- [ ] **Step 8: Commit**

Run:

```bash
git add -A
git commit -m "feat(header-footer): messages and the weekday in English by default or pt-BR, lang in the config, release 0.4.0" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

Expected: one commit (git status --short is empty afterwards).

### Task 6: The skills, the examples and the docs

**Files:**
- Modify: `plugins/ar-board/skills/ar-board/SKILL.md`, `plugins/ar-board/skills/question-board/SKILL.md`, `plugins/tidy-board/skills/tidy-board/SKILL.md`, `plugins/housekeeping/skills/todo-sweep/SKILL.md`, `plugins/housekeeping/skills/doc-truth/SKILL.md`, `plugins/housekeeping/skills/handoff/SKILL.md`, `plugins/header-footer/skills/header-footer/SKILL.md`; `plugins/ar-board/skills/ar-board/examples/batch.example.json`, `plugins/ar-board/skills/question-board/examples/batch.example.json`; the eight plugin READMEs that have a language line (`plugins/{ar-board,tidy-board,housekeeping,header-footer}/README.md` and `README.pt-BR.md`), and in the tidy-board, housekeeping and header-footer ones the short mentions of the buttons, the note headings and the weekday; `plugins/ar-board/docs/reference.md`, `plugins/ar-board/docs/pt-BR/guia-completo.md`; `CLAUDE.md`
- Generated: `plugins/ar-board/dist/*.SKILL.md` (from the two ar-board skills)
- Not changed: `publish-check` (its skill, READMEs and output are English already), the root READMEs (no language line). The long reference documents (`docs/reference.md`, `docs/pt-BR/guia-completo.md`) are not translated: their header says what their Portuguese quotes are.

**Interfaces:**
- Consumes: the flags, fields and messages of Tasks 1, 2b, 4, 4b, 5, 5b, 5c, 5d and 5e.
- Produces: skills that name each panel literal and each command-line line in English first with the pt-BR wording next to it, tell the agent to ask for the language the user writes in (`lang` in the batch; `--lang` on `scan`, on `write` and on every command; `lang` in header-footer's config) and accept "done" or "terminei" as the finish signal; docs that say that every user-visible text is English by default and pt-BR on request, and how to ask for it (`lang`, `--lang`, `CAPYBARA_LANG`).

- [ ] **Step 1: Confirm which skills mention the panel's language**

Run: `grep -l -E "terminei|Concluir|Copiar|avancar|panel" plugins/*/skills/*/SKILL.md`

Expected: exactly the four panel skills: `plugins/ar-board/skills/ar-board/SKILL.md`, `plugins/ar-board/skills/question-board/SKILL.md`, `plugins/housekeeping/skills/todo-sweep/SKILL.md`, `plugins/tidy-board/skills/tidy-board/SKILL.md` (doc-truth, handoff and header-footer mention Portuguese only for their command-line output and, for handoff, the note's fixed texts; Step 4b covers them).

- [ ] **Step 2: The four panel skills**

Each edit keeps the rule and renames the literal: English first, pt-BR next to it; the agent is told how to choose the language; the finish signal accepts both words. The reference batches inside the two ar-board skills are Portuguese, so they set `"lang": "pt-BR"`.

In `plugins/ar-board/skills/ar-board/SKILL.md`, replace:

```markdown
When the user says "done" (the panel tells them to say "terminei"), you read the decisions straight from disk.
```

with:

```markdown
When the user says "done" (the panel's banner asks for "done"; the pt-BR panel asks for "terminei"), you read the decisions straight from disk.
```

In `plugins/ar-board/skills/ar-board/SKILL.md`, replace:

```markdown
Reply to the user in the user's language. Write card content (titles, fields, risks, concepts) in that language too. The panel's own buttons and labels are in Portuguese.
```

with:

```markdown
Reply to the user in the user's language. Write card content (titles, fields, risks, concepts) in that language too. The panel's own buttons and labels exist in English (the default) and in pt-BR: set `"lang": "pt-BR"` in the batch when the user writes in Portuguese, and `"lang": "en"` (or omit it) otherwise. The user can also switch the panel with the EN/PT toggle in its header; that never changes the cards. The command line (`check`, `summary`, `wait`) speaks the batch's `lang` too (`--lang` overrides it on every command). The panel and command-line literals below are written in English first, with the pt-BR wording next to them.
```

In `plugins/ar-board/skills/ar-board/SKILL.md`, replace:

```markdown
- `risk`: honest. Give `level` and what can go wrong. Use `baixo`, `médio` or `alto` (low, medium, high) as the level: the panel colours only these three words and shows any other level in the medium colour.
```

with:

```markdown
- `risk`: honest. Give `level` and what can go wrong. Use `low`, `medium` or `high` (or `baixo`, `médio`, `alto`) as the level: the panel colours only these words and shows any other level in the medium colour.
```

In `plugins/ar-board/skills/ar-board/SKILL.md`, replace:

````markdown
python3 -I "${CLAUDE_SKILL_DIR}/scripts/ar_board.py" serve .ar-board/<batch_id> --open
```

The output contains
````

with:

````markdown
python3 -I "${CLAUDE_SKILL_DIR}/scripts/ar_board.py" serve .ar-board/<batch_id> --open
```

`--lang en|pt-BR` overrides the batch's `lang` for the language the panel opens in (`build` takes it too).

The output contains
````

In `plugins/ar-board/skills/ar-board/SKILL.md`, replace:

```markdown
A checkbox at the top (`avancar ao decidir`, "advance on decide") turns the automatic advance off.
```

with:

```markdown
A checkbox at the top (`advance on decide`; pt-BR `avançar ao decidir`) turns the automatic advance off.
```

In `plugins/ar-board/skills/ar-board/SKILL.md`, replace:

```markdown
It ends when the user clicks **Concluir** ("Finish"), and the result arrives as a notification.
```

with:

```markdown
It ends when the user clicks **Finish and notify the agent** (pt-BR `Concluir e avisar o agente`), and the result arrives as a notification.
```

In `plugins/ar-board/skills/ar-board/SKILL.md`, replace:

```markdown
Ask the user to decide there and click **Copiar** ("Copy"), then paste back
```

with:

```markdown
Ask the user to decide there and click **Copy** (pt-BR `Copiar`), then paste back
```

In `plugins/ar-board/skills/ar-board/SKILL.md`, replace:

```markdown
When the user says "done" (the panel tells them to say "terminei") or `wait` returns, run:
```

with:

```markdown
When the user says "done" (the English banner) or "terminei" (the pt-BR banner), or `wait` returns, run:
```

In `plugins/ar-board/skills/ar-board/SKILL.md`, replace:

```markdown
If the output says `Concluido pelo usuario: NAO (parcial)` ("Finished by the user: NO (partial)"), the user left before clicking `Concluir`. Work with what was decided.
```

with:

```markdown
If the output says `Finished by the user: NO (partial)` (pt-BR `Concluido pelo usuario: NAO (parcial)`), the user left before clicking **Finish and notify the agent** (pt-BR `Concluir e avisar o agente`). Work with what was decided.
```

In `plugins/ar-board/skills/ar-board/SKILL.md`, replace:

```markdown
  "subtitle": "Cada card: o que muda, por quê e o risco.",
  "round": 1,
  "items": [
```

with:

```markdown
  "subtitle": "Cada card: o que muda, por quê e o risco.",
  "round": 1,
  "lang": "pt-BR",
  "items": [
```

In `plugins/ar-board/skills/ar-board/SKILL.md`, replace:

```markdown
The example above is in Portuguese. Write the same fields in the user's language.

Required fields: `batch_id`, `title`, `items[].id` (unique), `items[].title`. Types (`check` rejects anything else):
- `round` is an integer >= 1.
```

with:

```markdown
The example above is in Portuguese, so it sets `"lang": "pt-BR"`. Write the same fields in the user's language and set `lang` to match.

Required fields: `batch_id`, `title`, `items[].id` (unique), `items[].title`. Types (`check` rejects anything else):
- `round` is an integer >= 1.
- `lang` is `"en"` or `"pt-BR"` (omitted = `"en"`).
```

In `plugins/ar-board/skills/question-board/SKILL.md`, replace:

```markdown
(or writes an "Outra resposta" ("Other answer"), or asks for more context), reviews everything on a final screen and says "done" (the panel tells them to say "terminei").
```

with:

```markdown
(or writes an "Other answer" (pt-BR "Outra resposta"), or asks for more context), reviews everything on a final screen and says "done" (the pt-BR panel asks for "terminei").
```

In `plugins/ar-board/skills/question-board/SKILL.md`, replace:

```markdown
Reply to the user in the user's language. Write question and card content (titles, context, options, effects) in that language too. The panel's own buttons and labels are in Portuguese.
```

with:

```markdown
Reply to the user in the user's language. Write question and card content (titles, context, options, effects) in that language too. The panel's own buttons and labels exist in English (the default) and in pt-BR: set `"lang": "pt-BR"` in the batch when the user writes in Portuguese, and `"lang": "en"` (or omit it) otherwise. The user can also switch the panel with the EN/PT toggle in its header; that never changes the questions. The command line (`check`, `summary`, `wait`) speaks the batch's `lang` too (`--lang` overrides it on every command). The panel and command-line literals below are written in English first, with the pt-BR wording next to them.
```

In `plugins/ar-board/skills/question-board/SKILL.md`, replace:

```markdown
The option "Outra resposta..." counts toward `max`.
```

with:

```markdown
The option "Other answer..." (pt-BR "Outra resposta...") counts toward `max`.
```

In `plugins/ar-board/skills/question-board/SKILL.md`, replace:

```markdown
- The panel adds the option **"Outra resposta..."** ("Other answer...") by itself to every question that has options.
```

with:

```markdown
- The panel adds the option **"Other answer..."** (pt-BR "Outra resposta...") by itself to every question that has options.
```

In `plugins/ar-board/skills/question-board/SKILL.md`, replace:

````markdown
python3 -I "${CLAUDE_SKILL_DIR}/scripts/ar_board.py" serve .ar-board/<batch_id> --open
```

The output contains
````

with:

````markdown
python3 -I "${CLAUDE_SKILL_DIR}/scripts/ar_board.py" serve .ar-board/<batch_id> --open
```

`--lang en|pt-BR` overrides the batch's `lang` for the language the panel opens in (`build` takes it too).

The output contains
````

In `plugins/ar-board/skills/question-board/SKILL.md`, replace:

```markdown
**1-9** picks the option (the last one is "Outra resposta..."),
```

with:

```markdown
**1-9** picks the option (the last one is "Other answer...", pt-BR "Outra resposta..."),
```

In `plugins/ar-board/skills/question-board/SKILL.md`, replace:

```markdown
A checkbox (`avancar ao decidir`, "advance on decide") turns that off.
```

with:

```markdown
A checkbox (`advance on decide`; pt-BR `avançar ao decidir`) turns that off.
```

In `plugins/ar-board/skills/question-board/SKILL.md`, replace:

```markdown
Ask the user to answer there and click **Copiar** ("Copy") on the review screen,
```

with:

```markdown
Ask the user to answer there and click **Copy the result** (pt-BR `Copiar resultado`) on the review screen,
```

In `plugins/ar-board/skills/question-board/SKILL.md`, replace:

```markdown
When the user says "done" (the panel tells them to say "terminei") or `wait` returns, run:
```

with:

```markdown
When the user says "done" (the English banner) or "terminei" (the pt-BR banner), or `wait` returns, run:
```

In `plugins/ar-board/skills/question-board/SKILL.md`, replace:

```markdown
  "title": "5 perguntas antes de construir o tidy-board",
  "round": 1,
  "items": [
```

with:

```markdown
  "title": "5 perguntas antes de construir o tidy-board",
  "round": 1,
  "lang": "pt-BR",
  "items": [
```

In `plugins/ar-board/skills/question-board/SKILL.md`, replace:

```markdown
The example above is in Portuguese. Write the same fields in the user's language.

Required fields of a question:
```

with:

```markdown
The example above is in Portuguese, so it sets `"lang": "pt-BR"`. Write the same fields in the user's language and set `lang` to match (`"en"` or `"pt-BR"`; omitted = `"en"`).

Required fields of a question:
```

In `plugins/tidy-board/skills/tidy-board/SKILL.md`, replace:

```markdown
only what the user approves (Apagar, "Delete") is deleted,
```

with:

```markdown
only what the user approves (Delete; pt-BR Apagar) is deleted,
```

In `plugins/tidy-board/skills/tidy-board/SKILL.md`, replace:

```markdown
The user decides **Apagar** ("Delete") / **Manter** ("Keep") / **Depois** ("Later").
```

with:

```markdown
The user decides **Delete** / **Keep** / **Later** (pt-BR **Apagar** / **Manter** / **Depois**).
```

In `plugins/tidy-board/skills/tidy-board/SKILL.md`, replace:

```markdown
Reply to the user in the user's language. The panel and the card text that `scan` writes are in Portuguese: explain them to the user in the user's language. Never edit `batch.json` or `scan.json` to translate them.
```

with:

```markdown
Reply to the user in the user's language. The panel and the cards that `scan` writes exist in English (the default) and in pt-BR: run `scan --lang pt-BR` when the user writes in Portuguese, and `scan` (or `--lang en`) otherwise. The user can also switch the panel's own buttons with the EN/PT toggle in its header; the cards stay in the language of the scan. Every line the tool prints follows the same language (`check`, `apply` and `restore` read it from `scan.json`; `--lang` overrides it on every command). Never edit `batch.json` or `scan.json` to translate them. The literals below are written in English first, with the pt-BR wording next to them.
```

In `plugins/tidy-board/skills/tidy-board/SKILL.md`, replace:

```markdown
They appear under `Nao tocar` ("Do not touch") on the first card, with the reason.
```

with:

```markdown
They appear under `Do not touch` (pt-BR `Não tocar`) on the first card, with the reason.
```

In `plugins/tidy-board/skills/tidy-board/SKILL.md`, replace:

````markdown
python3 -I "${CLAUDE_SKILL_DIR}/scripts/tidy_board.py" scan [REPO] [--base REF] [--gh off]
```

`scan` does not fetch anything from the network and does not change the repository.
````

with:

````markdown
python3 -I "${CLAUDE_SKILL_DIR}/scripts/tidy_board.py" scan [REPO] [--base REF] [--gh off] [--lang en|pt-BR]
```

`scan` does not fetch anything from the network and does not change the repository. `--lang` (default: `CAPYBARA_LANG`, then `en`) is the language of the cards and of every line the tool prints; the summary line ends with `language <lang>` (pt-BR `idioma <lang>`).
````

In `plugins/tidy-board/skills/tidy-board/SKILL.md`, replace:

```markdown
- **A = Apagar** ("Delete"), **R = Manter** ("Keep"), **M = Depois** ("Later"), **S** skips.
```

with:

```markdown
- **A = Delete**, **R = Keep**, **M = Later** (pt-BR **Apagar** / **Manter** / **Depois**), **S** skips.
```

In `plugins/tidy-board/skills/tidy-board/SKILL.md`, replace:

```markdown
that the user does not mark Manter or Depois. A Manter or Depois on an item always beats the group.
```

with:

```markdown
that the user does not mark Keep or Later (pt-BR Manter or Depois). A Keep or Later on an item always beats the group.
```

In `plugins/tidy-board/skills/tidy-board/SKILL.md`, replace:

```markdown
- At the end the user clicks **Concluir** (the button reads `Concluir e avisar o agente`, "Finish and notify the agent") and tells you `terminei` ("I'm done"). If the user answers in another language, accept the equivalent ("done", "finished"), but only when it clearly says the panel is finished. Anything vaguer ("ok", "go on") is not the signal: ask the user to finish the panel. The panel itself says `Concluido. Volte ao Claude Code e diga "terminei"` ("Finished. Go back to Claude Code and say "terminei""). If items are left without a decision (normal when the group card is used), the panel asks `N itens sem decisao. Concluir mesmo assim?` ("N items without a decision. Finish anyway?"). The user only has to confirm.
```

with:

```markdown
- At the end the user clicks **Finish and notify the agent** (pt-BR `Concluir e avisar o agente`) and tells you `done` (pt-BR `terminei`). Accept either, or a clear equivalent ("finished"), but only when it clearly says the panel is finished. Anything vaguer ("ok", "go on") is not the signal: ask the user to finish the panel. The panel itself says `Finished. Go back to Claude Code and say "done"` (pt-BR `Concluído. Volte ao Claude Code e diga "terminei"`). If items are left without a decision (normal when the group card is used), the panel asks `Undecided items: N. Finish anyway?` (pt-BR `Itens sem decisão: N. Concluir mesmo assim?`). The user only has to confirm.
```

In `plugins/tidy-board/skills/tidy-board/SKILL.md`, replace:

```markdown
After the finish signal (`terminei`), **always** simulate first and show the user the dry-run list. The panel's counter counts the group card as one item, and the items it covers appear as `sem decisao` ("no decision").
```

with:

```markdown
After the finish signal (`done` / `terminei`), **always** simulate first and show the user the dry-run list. The panel's counter counts the group card as one item, and the items it covers appear as `undecided` (pt-BR `sem decisão`).
```

In `plugins/tidy-board/skills/tidy-board/SKILL.md`, replace:

```markdown
| `scan [REPO] [--base REF] [--gh auto\|off] [--out DIR]` | reads git and writes `batch.json` + `scan.json` | 0 ok |
```

with:

```markdown
| `scan [REPO] [--base REF] [--gh auto\|off] [--out DIR] [--lang en\|pt-BR]` | reads git and writes `batch.json` + `scan.json` in that language (default `en`) | 0 ok |
```

In `plugins/housekeeping/skills/todo-sweep/SKILL.md`, replace:

```markdown
the user marks Resolver ("Resolve"), Descartar ("Discard") or Manter ("Keep"), and the result is a read-only report;
```

with:

```markdown
the user marks Resolve, Discard or Keep (pt-BR Resolver, Descartar, Manter), and the result is a read-only report;
```

In `plugins/housekeeping/skills/todo-sweep/SKILL.md`, replace:

```markdown
The user marks `Resolver` ("Resolve", key `A`), `Descartar` ("Discard", key `R`) or `Manter` ("Keep", key `M`), and the result is a **read-only report**.
```

with:

```markdown
The user marks `Resolve` (key `A`), `Discard` (key `R`) or `Keep` (key `M`; pt-BR `Resolver`, `Descartar`, `Manter`), and the result is a **read-only report**.
```

In `plugins/housekeeping/skills/todo-sweep/SKILL.md`, replace:

```markdown
Below, "TODO" means a `TODO` or `FIXME` marker. The three labels are always written in Portuguese, as the panel shows them.
```

with:

```markdown
Below, "TODO" means a `TODO` or `FIXME` marker. The panel literals are written in English first, with the pt-BR wording next to them.
```

In `plugins/housekeeping/skills/todo-sweep/SKILL.md`, replace:

```markdown
`Descartar` and `Manter` decisions are recorded in `.todo-sweep/ledger.json` when you run `report` (step 3): the next `scan` offers the next TODOs, not the same ones. `Resolver` decisions and TODOs left undecided are not recorded:
```

with:

```markdown
Discard and Keep decisions are recorded in `.todo-sweep/ledger.json` when you run `report` (step 3): the next `scan` offers the next TODOs, not the same ones. Resolve decisions and TODOs left undecided are not recorded:
```

In `plugins/housekeeping/skills/todo-sweep/SKILL.md`, replace:

```markdown
Reply to the user in the user's language. You do not write the cards: `scan` writes them, and the panel and `report.md` are in Portuguese. Explain the panel, the cards and the report to the user in the user's language. Never edit `batch.json` or `scan.json` to translate them.
```

with:

```markdown
Reply to the user in the user's language. You do not write the cards: `scan` writes them. The cards, the panel and `report.md` exist in English (the default) and in pt-BR: run `scan --lang pt-BR` when the user writes in Portuguese, and `scan` (or `--lang en`) otherwise; `check` and `report` follow the language of the scan by themselves (and so do their lines; `--lang` overrides it). The user can also switch the panel's own buttons with the EN/PT toggle in its header. Never edit `batch.json` or `scan.json` to translate them.
```

In `plugins/housekeeping/skills/todo-sweep/SKILL.md`, replace:

```markdown
Options: `--limit N` (cards per batch, default 20), `--max-blame N` (how many to measure with `git blame`, default 300) and `--out <pasta>`.
```

with:

```markdown
Options: `--limit N` (cards per batch, default 20), `--max-blame N` (how many to measure with `git blame`, default 300), `--lang en|pt-BR` (the language of the cards, of the report and of every line the tool prints; default: `CAPYBARA_LANG`, then `en`) and `--out <pasta>`.
```

In `plugins/housekeeping/skills/todo-sweep/SKILL.md`, replace:

```markdown
remind them of the shortcuts: **A** `Resolver`, **R** `Descartar`, **M** `Manter`, **S** skip (`Pular`), **C** comment (**Esc** leaves the field), arrow keys navigate; **Concluir** ("Finish"; the button reads `Concluir e avisar o agente`, "Finish and notify the agent") marks the panel as finished.
```

with:

```markdown
remind them of the shortcuts: **A** `Resolve`, **R** `Discard`, **M** `Keep` (pt-BR `Resolver`, `Descartar`, `Manter`), **S** skip, **C** comment (**Esc** leaves the field), arrow keys navigate; **Finish and notify the agent** (pt-BR `Concluir e avisar o agente`) marks the panel as finished.
```

In `plugins/housekeeping/skills/todo-sweep/SKILL.md`, replace:

```markdown
The panel tells the user to go back to Claude Code and say `terminei` ("I have finished") after clicking `Concluir`. Treat `terminei`, or a clear equivalent such as "done" or "finished", as the finish signal.
```

with:

```markdown
The panel tells the user to go back to Claude Code and say `done` (pt-BR `terminei`) after clicking **Finish**. Treat `done`, `terminei` or a clear equivalent such as "finished" as the finish signal.
```

In `plugins/housekeeping/skills/todo-sweep/SKILL.md`, replace:

```markdown
It runs only if the user clicked `Concluir` (the panel is finished)
```

with:

```markdown
It runs only if the user clicked **Finish** (the panel is finished)
```

In `plugins/housekeeping/skills/todo-sweep/SKILL.md`, replace:

```markdown
usually they must click `Concluir` first. It writes `report.md` and `report.json` in the batch (`Resolver`, `Descartar`, `Manter` and `Sem decisao`, with the user's comments) and records the `Descartar` and `Manter` decisions in `ledger.json`. `Sem decisao` means "No decision". The report sections carry those four titles, and the tool prints `REPORT: <N> resolver, <N> descartar, <N> manter, <N> sem decisao`. Present the counts and what ended up under `Resolver`.
```

with:

```markdown
usually they must click **Finish** first. It writes `report.md` and `report.json` in the batch (sections `Resolve`, `Discard`, `Keep` and `No decision`; pt-BR `Resolver`, `Descartar`, `Manter`, `Sem decisão`; with the user's comments) and records the Discard and Keep decisions in `ledger.json`. The tool prints `REPORT: <N> resolve, <N> discard, <N> keep, <N> no decision` (pt-BR `REPORT: <N> resolver, <N> descartar, <N> manter, <N> sem decisao`). Present the counts and what ended up under Resolve.
```

In `plugins/housekeeping/skills/todo-sweep/SKILL.md`, replace:

```markdown
resolve the TODOs under `Resolver`, or delete the comments under `Descartar`.
```

with:

```markdown
resolve the TODOs under Resolve, or delete the comments under Discard.
```

In `plugins/housekeeping/skills/todo-sweep/SKILL.md`, replace:

```markdown
The ones under `Manter` stay as they are.
```

with:

```markdown
The ones under Keep stay as they are.
```

- [ ] **Step 3: The two ar-board examples**

Their content is English, so they record it:

In `plugins/ar-board/skills/ar-board/examples/batch.example.json`, replace:

```json
  "round": 1,
  "items": [
```

with:

```json
  "round": 1,
  "lang": "en",
  "items": [
```

In `plugins/ar-board/skills/question-board/examples/batch.example.json`, replace:

```json
  "round": 1,
  "items": [
```

with:

```json
  "round": 1,
  "lang": "en",
  "items": [
```

- [ ] **Step 4: The READMEs' language lines, the ar-board docs and CLAUDE.md**

In `plugins/ar-board/README.md`, replace:

```markdown
- **Languages:** the skill is in English; the panel UI and the CLI messages are in Portuguese; the documentation is in English
```

with:

```markdown
- **Languages:** the skill is in English; the panel and the CLI messages are in English by default and in pt-BR on request (`lang` in the batch, `--lang` on every command, the `CAPYBARA_LANG` environment variable, or the panel's EN/PT toggle); the documentation is in English
```

In `plugins/ar-board/README.pt-BR.md`, replace:

```markdown
- **Idiomas:** a skill está em inglês; o painel e as mensagens da linha de comando estão em português; a documentação está em inglês
```

with:

```markdown
- **Idiomas:** a skill está em inglês; o painel e as mensagens da linha de comando saem em inglês por padrão e em pt-BR quando pedido (`lang` no batch, `--lang` em todo comando, a variável de ambiente `CAPYBARA_LANG` ou o seletor EN/PT do painel); a documentação está em inglês
```

In `plugins/tidy-board/README.md`, replace:

```markdown
- **Languages:** the skill is in English; the panel, the card text and the CLI messages are in Portuguese; the documentation is in English
```

with:

```markdown
- **Languages:** the skill is in English; the panel, the cards and the CLI messages are in English by default or in pt-BR (`scan --lang pt-BR`, `--lang` on every command, or `CAPYBARA_LANG`); the documentation is in English
```

In `plugins/tidy-board/README.pt-BR.md`, replace:

```markdown
- **Idiomas:** a skill está em inglês; o painel, o texto dos cards e as mensagens da linha de comando estão em português; a documentação principal está em inglês
```

with:

```markdown
- **Idiomas:** a skill está em inglês; o painel, os cards e as mensagens da linha de comando saem em inglês por padrão ou em pt-BR (`scan --lang pt-BR`, `--lang` em todo comando ou `CAPYBARA_LANG`); a documentação principal está em inglês
```

In `plugins/housekeeping/README.md`, replace:

```markdown
- **Languages:** the skills are in English; the tools' output, the todo-sweep panel and its cards are in Portuguese; the documentation is in English
```

with:

```markdown
- **Languages:** the skills are in English; the tools' output, the handoff notes, the todo-sweep panel, its cards and its report are in English by default or in pt-BR (`--lang pt-BR` on every command, or `CAPYBARA_LANG`); the documentation is in English
```

In `plugins/housekeeping/README.pt-BR.md`, replace:

```markdown
- **Idiomas:** as skills estão em inglês; a saída das ferramentas, o painel do todo-sweep e seus cards estão em português; a documentação está em inglês
```

with:

```markdown
- **Idiomas:** as skills estão em inglês; a saída das ferramentas, as notas do handoff, o painel do todo-sweep, seus cards e seu relatório saem em inglês por padrão ou em pt-BR (`--lang pt-BR` em todo comando ou `CAPYBARA_LANG`); a documentação está em inglês
```

In `plugins/ar-board/docs/reference.md`, replace:

```markdown
This document is a reference. Strings quoted in Portuguese (CLI output, validation messages, UI labels) are the program's real output, which is written without accents.
```

with:

```markdown
This document is a reference. Strings quoted in Portuguese are the program's pt-BR wording as it was before 1.4.0, without accents. Since 1.4.0 the panel and the command line speak English by default and pt-BR on request (`lang`, `--lang`, `CAPYBARA_LANG`); the pt-BR command line is still accent-free and the pt-BR panel is written with accents (see [Visual design, responsiveness and accessibility](#visual-design-responsiveness-and-accessibility)).
```

In `plugins/ar-board/docs/reference.md`, replace:

```markdown
| **Completion banner** | `Concluido. Volte ao Claude Code e diga "terminei" — o agente le as decisoes sozinho.` |
```

with:

```markdown
| **Completion banner** | `Finished. Go back to Claude Code and say "done" — the agent reads the decisions by itself.` (pt-BR: `Concluído. Volte ao Claude Code e diga "terminei" — o agente lê as decisões sozinho.`) |
```

In `plugins/ar-board/docs/reference.md`, replace:

```markdown
The level is normalized (lowercase, accents removed) and selects the color: `baixo` green, `medio` amber, `alto` red.
```

with:

```markdown
The level is normalized (lowercase, accents removed) and selects the color: `baixo` or `low` green, `medio` or `medium` amber, `alto` or `high` red.
```

In `plugins/ar-board/docs/reference.md`, replace:

```markdown
| `serve DIR` | `--port N` (default 0 = random free port), `--open`, `--exit-on-finish` |
```

with:

```markdown
| `serve DIR` | `--port N` (default 0 = random free port), `--open`, `--exit-on-finish`, `--lang en\|pt-BR` |
```

In `plugins/ar-board/docs/reference.md`, replace:

```markdown
| `build DIR` | none | `AR-BOARD ARQUIVO: <path>/board.html` | 0 |
```

with:

```markdown
| `build DIR` | `--lang en\|pt-BR` | `AR-BOARD ARQUIVO: <path>/board.html` | 0 |
```

In `plugins/ar-board/docs/reference.md`, replace:

```markdown
- UI messages and labels are in Portuguese without accents, by project convention (the page is served and saved as UTF-8); card content accepts any Unicode
```

with:

```markdown
- **Language:** the panel's own text is English by default and pt-BR on demand: `lang` in `batch.json`, `--lang` on `serve` and `build`, or the EN/PT toggle in the header, which is remembered in the browser (`localStorage` key `ar-board:lang`) and wins over the other two. Both tables ship inside the page (`I18N` in the script), so the offline page switches too; nothing about the language is stored in `decisions.json`. The pt-BR wording is written with accents. Card content accepts any Unicode
```

In `plugins/ar-board/docs/pt-BR/guia-completo.md`, replace:

```markdown
- **Textos citados:** mensagens da interface e da linha de comando aparecem aqui exatamente como o programa as escreve, ou seja, sem acentos (convenção do projeto; a página é UTF-8).
```

with:

```markdown
- **Textos citados:** os textos em português citados aqui são a versão pt-BR do programa como era antes da 1.4.0, sem acentos. Desde a 1.4.0 o painel e a linha de comando saem em inglês por padrão e em pt-BR quando pedido (`lang`, `--lang`, `CAPYBARA_LANG`); a linha de comando em pt-BR continua sem acentos e o painel em pt-BR é escrito com acentos (ver §19).
```

In `plugins/ar-board/docs/pt-BR/guia-completo.md`, replace:

```markdown
| **Banner de conclusão** | `Concluido. Volte ao Claude Code e diga "terminei" — o agente le as decisoes sozinho.` |
```

with:

```markdown
| **Banner de conclusão** | `Concluído. Volte ao Claude Code e diga "terminei" — o agente lê as decisões sozinho.` (em inglês: `Finished. Go back to Claude Code and say "done" — the agent reads the decisions by itself.`) |
```

In `plugins/ar-board/docs/pt-BR/guia-completo.md`, replace:

```markdown
escolhe a cor: `baixo` verde, `médio`/`medio` âmbar, `alto` vermelho.
```

with:

```markdown
escolhe a cor: `baixo` ou `low` verde, `médio`/`medio` ou `medium` âmbar, `alto` ou `high` vermelho.
```

In `plugins/ar-board/docs/pt-BR/guia-completo.md`, replace:

```markdown
| `serve DIR` | `--port N` (padrão 0 = porta livre aleatória), `--open`, `--exit-on-finish` |
```

with:

```markdown
| `serve DIR` | `--port N` (padrão 0 = porta livre aleatória), `--open`, `--exit-on-finish`, `--lang en\|pt-BR` |
```

In `plugins/ar-board/docs/pt-BR/guia-completo.md`, replace:

```markdown
| `build DIR` | — | `AR-BOARD ARQUIVO: <caminho>/board.html` | 0 |
```

with:

```markdown
| `build DIR` | `--lang en\|pt-BR` | `AR-BOARD ARQUIVO: <caminho>/board.html` | 0 |
```

In `plugins/ar-board/docs/pt-BR/guia-completo.md`, replace:

```markdown
- Mensagens e rótulos estão em português sem acentos dentro da página, por convenção do projeto (a página é servida e gravada em UTF-8); o conteúdo dos cards aceita qualquer Unicode
```

with:

```markdown
- **Idioma:** o texto do próprio painel sai em inglês por padrão e em pt-BR quando pedido: `lang` no `batch.json`, `--lang` em `serve` e `build`, ou o seletor EN/PT no cabeçalho, que fica guardado no navegador (chave `ar-board:lang` do `localStorage`) e vence os outros dois. As duas tabelas viajam dentro da página (`I18N` no script), então a página offline também alterna; nada sobre o idioma vai para o `decisions.json`. O pt-BR é escrito com acentos. O conteúdo dos cards aceita qualquer Unicode
```

In `CLAUDE.md`, replace:

```markdown
while the panel UI, the card text the tools generate and the CLI messages of ar-board, tidy-board, housekeeping and header-footer are Portuguese (publish-check prints English).
```

with:

```markdown
while everything the user sees is English by default and pt-BR on request: the panel UI, the cards and reports the tools generate, handoff's notes, header-footer's weekday and the CLI messages of every script (`lang` in a batch or in `header-footer.json`, `--lang` on every command, the `CAPYBARA_LANG` environment variable, an EN/PT toggle in the panel's header; publish-check prints English only).
```

In `CLAUDE.md`, replace:

```markdown
- In-page UI strings are accent-free Portuguese by project convention (the page itself is UTF-8); card content may be any Unicode.
```

with:

```markdown
- Every user-visible string of the panel lives in the `I18N` table of `ar_board.py` (`en` and `pt-BR`, the latter with accents; a test pins equal keys and placeholders and another flags any literal left in `PAGE`). The tool tables (`TEXT` and `LABELS` in the tidy-board and todo-sweep scripts) carry both languages too; everything a script parses (ids, proofs, decisions, ledger words, JSON keys, `age_reason` codes) stays language independent. The CLI messages of every script but publish-check live in a `MSG` table per script (`en` and `pt-BR`, both plain ASCII, so the pt-BR side stays accent-free; a test per script pins the parity and an AST guard flags any Portuguese literal left in the functions that print); the language resolves `--lang`, then the batch's or scan's `lang`, then `CAPYBARA_LANG`, then `en`, and only `main()` sets it. Card content may be any Unicode.
```

- [ ] **Step 4b: The command line, the notes and the short mentions of the buttons**

The command line of every script is English by default since Tasks 2b to 5e, so every line a skill or a README quotes gets its English form first and the pt-BR one next to it; the tidy-board, housekeeping and header-footer READMEs also name the English buttons, note headings and weekday first. These edits apply to the files as Steps 2 and 4 left them.

In `plugins/tidy-board/skills/tidy-board/SKILL.md`, replace:

```markdown
- The `NAO TOCAR:` lines.
```

with:

```markdown
- The `DO NOT TOUCH:` lines (pt-BR `NAO TOCAR:`): what is never offered, and why.
```

In `plugins/tidy-board/skills/tidy-board/SKILL.md`, replace:

```markdown
If the output says `nada para limpar` ("nothing to clean"), stop and tell the user so.
```

with:

```markdown
If the output says `TIDY-BOARD: nothing to clean up` (pt-BR `TIDY-BOARD: nada para limpar`), stop and tell the user so.
```

In `plugins/tidy-board/skills/tidy-board/SKILL.md`, replace:

```markdown
Above 40 items `check` prints a warning (`aviso: ...`).
```

with:

```markdown
Above 40 items `check` prints a warning (`warning: ...`, pt-BR `aviso: ...`).
```

In `plugins/tidy-board/skills/tidy-board/SKILL.md`, replace:

```markdown
| `restore DIR ID` | recreates a deleted item that has a backup | 0 ok, 2 error |
```

with:

```markdown
| `restore DIR ID` | recreates a deleted item that has a backup | 0 ok, 2 error |

Every command takes `--lang en|pt-BR`. Without it, `check`, `apply` and `restore` speak the language the scan recorded; `scan` uses `CAPYBARA_LANG`, then English. The tags `TIDY-BOARD DIR:`, `TIDY-BOARD ITENS:`, `APPLY:` and `RESTORE:` and the action words `deleted`, `skipped` and `would-delete` are the same in both languages; errors start with `error:` (pt-BR `erro:`).
```

In `plugins/housekeeping/skills/todo-sweep/SKILL.md`, replace:

```markdown
`<lote>` is the batch folder ("batch"), the one printed on the `lote:` line of the `scan` output.
```

with:

```markdown
`<lote>` is the batch folder ("batch"), the one printed on the `batch:` line of the `scan` output (pt-BR `lote:`).
```

In `plugins/housekeeping/skills/todo-sweep/SKILL.md`, replace:

```markdown
Read the summary line (`SCAN: ...`) and **pass the warnings on to the user**: the counts in the `SCAN:` line, and every line that starts with `aviso:` ("warning", for example about a shallow clone or about `--max-blame`). Report how many TODOs were found and how many were already decided (`ja decididos`); how many ended up with **no age** (`sem idade`): a line that is not committed, the limit of a shallow clone (`clone raso`), or beyond `--max-blame`. If there is nothing new, `scan` says so (`nada novo para mostrar`, "nothing new to show") and does not save a batch.
```

with:

```markdown
Read the summary line (`SCAN: ...`) and **pass the warnings on to the user**: the counts in the `SCAN:` line, and every line that starts with `warning:` (pt-BR `aviso:`; for example about a shallow clone or about `--max-blame`). Report how many TODOs were found and how many were already decided (`already decided`, pt-BR `ja decididos`); how many ended up **without an age** (pt-BR `sem idade`): a line that is not committed, the limit of a shallow clone, or beyond `--max-blame`. If there is nothing new, `scan` says so (`nothing new to show`, pt-BR `nada novo para mostrar`) and does not save a batch.
```

In `plugins/housekeeping/skills/todo-sweep/SKILL.md`, replace:

```markdown
otherwise it refuses with exit code 2 and an `erro:` line.
```

with:

```markdown
otherwise it refuses with exit code 2 and an `error:` line (pt-BR `erro:`).
```

In `plugins/housekeeping/skills/doc-truth/SKILL.md`, replace:

```markdown
Reply to the user in the user's language. The tool prints its output in Portuguese without accents (for example `limpo: nenhum achado`, "clean: no findings"): when you present the findings, explain them in the user's language and keep the category names, paths and fingerprints exactly as printed.
```

with:

```markdown
Reply to the user in the user's language. The tool prints its output in English by default; run it with `--lang pt-BR` when the user writes in Portuguese (accent-free Portuguese; `CAPYBARA_LANG` may set the default for the whole shell). When you present the findings, explain them in the user's language and keep the category names, values, paths and fingerprints exactly as printed: a finding's value and fingerprint are the same in both languages, only its message changes.
```

In `plugins/housekeeping/skills/doc-truth/SKILL.md`, replace:

```markdown
The output starts with `doc-truth <version>: <N> documentos conferidos em <path>` ("N documents checked in <path>"). It then prints `limpo: nenhum achado` ("clean: no findings") or `<N> achados` ("N findings").
```

with:

```markdown
The output starts with `doc-truth <version>: <N> documents checked in <path>` (pt-BR `<N> documentos conferidos em <path>`). It then prints `clean: no findings` (pt-BR `limpo: nenhum achado`) or `<N> findings` (pt-BR `<N> achados`).
```

In `plugins/housekeeping/skills/doc-truth/SKILL.md`, replace:

```markdown
(the finding reads `falta README.pt-BR.md`, "README.pt-BR.md is missing").
```

with:

```markdown
(the finding's value reads `falta README.pt-BR.md`, "README.pt-BR.md is missing", in both languages: it is data, so an accepted fingerprint stays valid).
```

In `plugins/housekeeping/skills/handoff/SKILL.md`, replace:

```markdown
whatever does not exist is marked "[nao verificado]" ("not verified").
```

with:

```markdown
whatever does not exist is marked "[not verified]" (pt-BR "[nao verificado]").
```

In `plugins/housekeeping/skills/handoff/SKILL.md`, replace:

```markdown
and a citation that does not exist is marked `[nao verificado]` ("not verified"), without deleting anything.
```

with:

```markdown
and a citation that does not exist is marked `[not verified]` (pt-BR `[nao verificado]`), without deleting anything.
```

In `plugins/housekeeping/skills/handoff/SKILL.md`, replace:

```markdown
Reply to the user in the user's language. Write the content of the note in the user's language too. Keep these fixed texts exactly as given below: the four section headings, the metainfo keys and the `[nao verificado]` mark are Portuguese without accents, and the citation prefixes `commit:`, `branch:` and `file:` are English. The tool relies on them.
```

with:

```markdown
Reply to the user in the user's language. Write the content of the note in the user's language too, and save the note in that language: the tool writes English by default, so pass `--lang pt-BR` to `write` when the user writes in Portuguese (`CAPYBARA_LANG` may set the default for the whole shell). The fixed texts the tool writes (the header, the git section, the mark of a failed citation) follow that language. Keep the metainfo keys and the four section headings exactly as given below, in English or in their accent-free pt-BR form (both count, whatever the note's language), and the citation prefixes `commit:`, `branch:` and `file:` as they are. The tool relies on them.
```

In `plugins/housekeeping/skills/handoff/SKILL.md`, replace:

```markdown
Every note starts with a header table, `Metainfo da sessao` ("Session metainfo"), and the tool always writes it. You supply its rows as a block at the very top of the draft: a line `---`, one `Chave: Valor` ("Key: Value") per line, a line `---`. The keys are fixed Portuguese text without accents; the values are in the user's language.
```

with:

```markdown
Every note starts with a header table, `Session metainfo` (pt-BR `Metainfo da sessao`), and the tool always writes it. You supply its rows as a block at the very top of the draft: a line `---`, one `Key: Value` per line, a line `---`. The expected keys are fixed text (English, or their pt-BR form); the values are in the user's language.
```

In `plugins/housekeeping/skills/handoff/SKILL.md`, replace:

```markdown
Nome da sessao: config sonarqube
Modelo: Claude Sonnet 5.5 (`claude-sonnet-5-5`)
Sessao: <the session link, only if this conversation gave you one>
Pedido original: "analise o code base do backend e proponha as regras"
Status: Proposta. Nada aplicado, sem decisao do time.
```

with:

```markdown
Session name: config sonarqube
Model: Claude Sonnet 5.5 (`claude-sonnet-5-5`)
Session: <the session link, only if this conversation gave you one>
Original request: "analyse the backend code base and propose the rules"
Status: Proposal. Nothing applied, no team decision yet.
```

In `plugins/housekeeping/skills/handoff/SKILL.md`, replace:

```markdown
- Always give `Modelo` (the model running this skill, name and id as your system prompt states them), `Pedido original` (the user's first request, shortened) and `Status` (where the work stands: done, proposal, blocked). The tool prints `aviso: falta a metainfo '<key>'` ("warning: metainfo '<key>' is missing") for each one you leave out; add it and write the note again.
```

with:

```markdown
- Always give `Model` (pt-BR `Modelo`: the model running this skill, name and id as your system prompt states them), `Original request` (pt-BR `Pedido original`: the user's first request, shortened) and `Status` (where the work stands: done, proposal, blocked). The tool prints `warning: metainfo '<key>' is missing` (pt-BR `aviso: falta a metainfo '<key>'`) for each one you leave out; add it and write the note again.
```

In `plugins/housekeeping/skills/handoff/SKILL.md`, replace:

```markdown
for example `Nome da sessao` (the session name, only if the user gave one), `Data` (the day of the session, when it is not today), `Sessao` (the session link, only if this conversation gave you one), `Repo analisado`, `Ferramentas usadas`, `Escopo`, `Memoria`.
```

with:

```markdown
for example `Session name` (only if the user gave one), `Date` (the day of the session, when it is not today), `Session` (the session link, only if this conversation gave you one), `Repo analysed`, `Tools used`, `Scope`, `Memory`, in the note's language.
```

In `plugins/housekeeping/skills/handoff/SKILL.md`, replace:

```markdown
- The tool adds `Gravada em` ("Written at") and `Repositorio` itself; do not write those keys.
```

with:

```markdown
- The tool adds `Written at` and `Repository` (pt-BR `Gravada em` and `Repositorio`) itself; do not write those keys, in either language.
```

In `plugins/housekeeping/skills/handoff/SKILL.md`, replace:

```markdown
A line of the block that is not `Chave: Valor` is an error too,
```

with:

```markdown
A line of the block that is not `Key: Value` is an error too,
```

In `plugins/housekeeping/skills/handoff/SKILL.md`, replace:

````markdown
Write the rest of the draft with **these four headings**, in this order, without accents (the tool only warns if one is missing; it never adds or invents a section):

```markdown
## O que foi feito
## Decisoes e por que
## Proximos passos
## O que falhou ou travou
```

The meaning of the headings is "What was done", "Decisions and why", "Next steps" and "What failed or got stuck". Keep the Portuguese heading text exactly as shown. Write the content under each heading in the user's language.
````

with:

````markdown
Write the rest of the draft with **these four headings**, in this order (the tool only warns if one is missing; it never adds or invents a section):

```markdown
## What was done
## Decisions and why
## Next steps
## What failed or got stuck
```

In a pt-BR note use their pt-BR form, without accents: `## O que foi feito`, `## Decisoes e por que`, `## Proximos passos`, `## O que falhou ou travou` (either form counts). Keep the heading text exactly as shown. Write the content under each heading in the user's language.
````

In `plugins/housekeeping/skills/handoff/SKILL.md`, replace:

```markdown
(a section titled `## Estado do git`, "Git state")
```

with:

```markdown
(a section titled `## Git state`, pt-BR `## Estado do git`)
```

In `plugins/housekeeping/skills/handoff/SKILL.md`, replace:

```markdown
python3 -I "${CLAUDE_SKILL_DIR}/scripts/handoff.py" write <repositório> --draft - <<'EOF'
---
Modelo: ...
Pedido original: ...
Status: ...
---
## O que foi feito
...
EOF
```

with:

```markdown
python3 -I "${CLAUDE_SKILL_DIR}/scripts/handoff.py" write <repositório> --draft - <<'EOF'
---
Model: ...
Original request: ...
Status: ...
---
## What was done
...
EOF
```

In `plugins/housekeeping/skills/handoff/SKILL.md`, replace:

```markdown
The tool prints `nota gravada em <path>` ("note saved to <path>"), then `<N> citacoes, <M> nao verificadas` ("N citations, M not verified"). Read that output. If there are unverified citations, say which ones and **propose a fix** (a new `write` creates another note). If it prints `aviso: falta a secao '<name>'` ("warning: section '<name>' is missing") or `aviso: falta a metainfo '<key>'`, say which one.
```

with:

```markdown
For a pt-BR note add `--lang pt-BR` after `write <repositório>` and use the pt-BR keys and headings. The tool prints `note saved to <path>` (pt-BR `nota gravada em <path>`), then `<N> citations, <M> not verified` (pt-BR `<N> citacoes, <M> nao verificadas`). Read that output. If there are unverified citations, say which ones and **propose a fix** (a new `write` creates another note). If it prints `warning: section '<name>' is missing` or `warning: metainfo '<key>' is missing` (pt-BR `aviso: falta a secao '<name>'`, `aviso: falta a metainfo '<key>'`), say which one.
```

In `plugins/housekeeping/skills/handoff/SKILL.md`, replace:

```markdown
**Present the differences before acting**, and do not resume the note's plan blindly: the repository may have moved.
```

with:

```markdown
**Present the differences before acting**, and do not resume the note's plan blindly: the repository may have moved. `resume` and `verify` read a note in either language, including the ones written before 0.4.0 (pt-BR); their own lines follow `--lang`, never the note.
```

In `plugins/housekeeping/skills/handoff/SKILL.md`, replace:

```markdown
`Sessao` may hold a session link,
```

with:

```markdown
`Session` (pt-BR `Sessao`) may hold a session link,
```

In `plugins/header-footer/skills/header-footer/SKILL.md`, replace:

```markdown
Reply to the user in the user's language. The script's messages are Portuguese: explain them in the user's language.
```

with:

```markdown
Reply to the user in the user's language. The script's messages and the header's `weekday` are English by default and pt-BR when `lang` in `header-footer.json` (the `lang` command) or `CAPYBARA_LANG` says so; every command also takes `--lang`. When the user writes in Portuguese, run the commands with `--lang pt-BR`, and offer `lang pt-BR` if they want the messages and the weekday in Portuguese for good. The footer and the instruction that goes with the header line are the same in both languages.
```

In `plugins/header-footer/skills/header-footer/SKILL.md`, replace:

```markdown
| see both now | `preview` |
```

with:

```markdown
| see both now | `preview` |
| messages and weekday in Portuguese (or back) | `lang pt-BR` / `lang en` (`lang auto` follows `CAPYBARA_LANG`) |
```

In `plugins/header-footer/README.md`, replace:

```markdown
- **Languages:** the skill is in English; the CLI messages are Portuguese; the documentation is in English
```

with:

```markdown
- **Languages:** the skill is in English; the CLI messages and the header's weekday are English by default and pt-BR on request (`lang` in the config, `--lang`, or `CAPYBARA_LANG`); the footer is the same in both; the documentation is in English
```

In `plugins/header-footer/README.pt-BR.md`, replace:

```markdown
- **Idiomas:** a skill é em inglês; as mensagens da CLI são em português; a documentação é em inglês
```

with:

```markdown
- **Idiomas:** a skill é em inglês; as mensagens da CLI e o dia da semana do header saem em inglês por padrão e em pt-BR quando pedido (`lang` na config, `--lang` ou `CAPYBARA_LANG`); o footer é o mesmo nos dois; a documentação é em inglês
```

In `plugins/header-footer/README.md`, replace:

```markdown
| `weekday` | `seg` … `dom` |
```

with:

```markdown
| `weekday` | `Mon` … `Sun` (pt-BR `seg` … `dom`) |
```

In `plugins/header-footer/README.pt-BR.md`, replace:

```markdown
| `weekday` | `seg` … `dom` |
```

with:

```markdown
| `weekday` | `seg` … `dom` em pt-BR, `Mon` … `Sun` em inglês |
```

In `plugins/tidy-board/README.md`, replace:

```markdown
you decide **Apagar** (delete), **Manter** (keep) or **Depois** (later) with the keyboard;
```

with:

```markdown
you decide **Delete**, **Keep** or **Later** (pt-BR **Apagar**, **Manter**, **Depois**) with the keyboard;
```

In `plugins/tidy-board/README.md`, replace:

```markdown
`A` = Apagar, `R` = Manter, `M` = Depois.
```

with:

```markdown
`A` = Delete, `R` = Keep, `M` = Later (pt-BR Apagar, Manter, Depois).
```

In `plugins/tidy-board/README.md`, replace:

```markdown
a Manter or Depois on an item always beats the group,
```

with:

```markdown
a Keep or Later (pt-BR Manter, Depois) on an item always beats the group,
```

In `plugins/tidy-board/README.pt-BR.md`, replace:

```markdown
você decide **Apagar**, **Manter** ou **Depois** com o teclado;
```

with:

```markdown
você decide **Delete**, **Keep** ou **Later** (em pt-BR **Apagar**, **Manter**, **Depois**) com o teclado;
```

In `plugins/tidy-board/README.pt-BR.md`, replace:

```markdown
`A` = Apagar, `R` = Manter, `M` = Depois.
```

with:

```markdown
`A` = Delete, `R` = Keep, `M` = Later (em pt-BR Apagar, Manter, Depois).
```

In `plugins/tidy-board/README.pt-BR.md`, replace:

```markdown
um Manter ou Depois no item sempre vence o grupo,
```

with:

```markdown
um Keep ou Later (em pt-BR Manter, Depois) no item sempre vence o grupo,
```

In `plugins/housekeeping/README.md`, replace:

```markdown
The agent's draft has four sections (`O que foi feito`, `Decisoes e por que`, `Proximos passos`, `O que falhou ou travou`)
```

with:

```markdown
The note is English by default and pt-BR with `--lang pt-BR`. The agent's draft has four sections (`What was done`, `Decisions and why`, `Next steps`, `What failed or got stuck`; their pt-BR forms count too)
```

In `plugins/housekeeping/README.md`, replace:

```markdown
A citation that does not exist is kept and followed by ` [nao verificado]`, once;
```

with:

```markdown
A citation that does not exist is kept and followed by ` [not verified]` (pt-BR ` [nao verificado]`), once;
```

In `plugins/housekeeping/README.md`, replace:

```markdown
# the panel: A Resolver, R Descartar, M Manter
```

with:

```markdown
# the panel: A Resolve, R Discard, M Keep
```

In `plugins/housekeeping/README.md`, replace:

```markdown
Descartar and Manter are also remembered in `.todo-sweep/ledger.json`
```

with:

```markdown
Discard and Keep (pt-BR Descartar, Manter) are also remembered in `.todo-sweep/ledger.json`
```

In `plugins/housekeeping/README.md`, replace:

```markdown
Resolver is not remembered,
```

with:

```markdown
Resolve is not remembered,
```

In `plugins/housekeeping/README.pt-BR.md`, replace:

```markdown
O rascunho do agente tem quatro seções (`O que foi feito`, `Decisoes e por que`, `Proximos passos`, `O que falhou ou travou`)
```

with:

```markdown
A nota sai em inglês por padrão e em pt-BR com `--lang pt-BR`. O rascunho do agente tem quatro seções (`What was done`, `Decisions and why`, `Next steps`, `What failed or got stuck`, ou em pt-BR `O que foi feito`, `Decisoes e por que`, `Proximos passos`, `O que falhou ou travou`)
```

In `plugins/housekeeping/README.pt-BR.md`, replace:

```markdown
Uma citação que não existe é mantida e seguida de ` [nao verificado]`, uma vez;
```

with:

```markdown
Uma citação que não existe é mantida e seguida de ` [not verified]` (em pt-BR ` [nao verificado]`), uma vez;
```

In `plugins/housekeeping/README.pt-BR.md`, replace:

```markdown
# o painel: A Resolver, R Descartar, M Manter
```

with:

```markdown
# o painel: A Resolve, R Discard, M Keep (em pt-BR Resolver, Descartar, Manter)
```

In `plugins/ar-board/docs/reference.md`, replace:

```markdown
| `check DIR` | none | `ok: N itens, lote <id>, rodada <R>` |
```

with:

```markdown
| `check DIR` | `--lang en\|pt-BR` | `ok: N items, batch <id>, round <R>` (pt-BR `ok: N itens, lote <id>, rodada <R>`) |
```

In `plugins/ar-board/docs/reference.md`, replace:

```markdown
| `wait DIR` | `--timeout S` (0 = wait indefinitely) | Markdown summary when concluded; `TIMEOUT: o usuario ainda nao concluiu o lote.` on timeout |
```

with:

```markdown
| `wait DIR` | `--timeout S` (0 = wait indefinitely), `--lang en\|pt-BR` | Markdown summary when concluded; `TIMEOUT: the user has not finished the batch yet.` (pt-BR `TIMEOUT: o usuario ainda nao concluiu o lote.`) on timeout |
```

In `plugins/ar-board/docs/reference.md`, replace:

```markdown
| `summary DIR` | `--json` |
```

with:

```markdown
| `summary DIR` | `--json`, `--lang en\|pt-BR` |
```

In `plugins/ar-board/docs/reference.md`, replace:

```markdown
All commands load and validate `batch.json` first. A missing file exits with `nao encontrei <path>`;
```

with:

```markdown
All commands load and validate `batch.json` first, and print in the language of the run: `--lang`, then the batch's `lang`, then `CAPYBARA_LANG`, then English. A missing file exits with `could not find <path>` (pt-BR `nao encontrei <path>`);
```

In `plugins/ar-board/docs/pt-BR/guia-completo.md`, replace:

```markdown
| `check DIR` | — | `ok: N itens, lote <id>, rodada <R>` |
```

with:

```markdown
| `check DIR` | `--lang en\|pt-BR` | `ok: N items, batch <id>, round <R>` (em pt-BR `ok: N itens, lote <id>, rodada <R>`) |
```

In `plugins/ar-board/docs/pt-BR/guia-completo.md`, replace:

```markdown
| `wait DIR` | `--timeout S` (0 = espera indefinidamente) |
```

with:

```markdown
| `wait DIR` | `--timeout S` (0 = espera indefinidamente), `--lang en\|pt-BR` |
```

In `plugins/ar-board/docs/pt-BR/guia-completo.md`, replace:

```markdown
| `summary DIR` | `--json` |
```

with:

```markdown
| `summary DIR` | `--json`, `--lang en\|pt-BR` |
```

In `CLAUDE.md`, replace:

```markdown
writes an ar-board batch (labels Resolver, Descartar, Manter) plus a `scan.json` sidecar
```

with:

```markdown
writes an ar-board batch (labels Resolve, Discard, Keep; pt-BR Resolver, Descartar, Manter) plus a `scan.json` sidecar
```

In `CLAUDE.md`, replace:

```markdown
is checked, kept and marked `[nao verificado]` when it fails
```

with:

```markdown
is checked, kept and marked `[not verified]` (pt-BR `[nao verificado]`) when it fails
```

In `CLAUDE.md`, replace:

```markdown
remembers Descartar and Manter in
```

with:

```markdown
remembers Discard and Keep in
```

In `CLAUDE.md`, replace:

```markdown
The config is `header-footer.json` in the Claude config directory and every path honours `CLAUDE_CONFIG_DIR`, which is how the tests isolate themselves.
```

with:

```markdown
The config is `header-footer.json` in the Claude config directory and every path honours `CLAUDE_CONFIG_DIR`, which is how the tests isolate themselves; its optional top-level `lang` (the `lang` command) chooses the language of the messages and of the `weekday` field, while the footer and the instruction sent with the header line are the same in both languages.
```

- [ ] **Step 5: Regenerate the single-file variants and check the documents**

Run: `python3 plugins/ar-board/tools/sync.py && git add -A && python3 -I plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py . | sed -n 2p && python3 -I plugins/publish-check/skills/publish-check/scripts/publish_check.py . | sed -n 2p`

Expected: `updated: dist/ar-board-single-file.SKILL.md`, `updated: dist/question-board-single-file.SKILL.md`, then `clean: no findings` twice (doc-truth, which speaks English since Task 5b, and publish-check).

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/ar-board/tests -p 'test_[lpv]*.py' 2>&1 | tail -n 1 && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/tidy-board/tests -p test_skill.py 2>&1 | tail -n 1 && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/housekeeping/tests -p test_skills.py 2>&1 | tail -n 1`

Expected: `OK` three times (the examples still validate, the skills still run the bundled scripts, the repository documents tell the truth).

- [ ] **Step 6: Commit**

Run:

```bash
git add -A
git commit -m "docs: the skills ask for the language; the docs say every user-visible text is English or pt-BR" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

Expected: one commit (git status --short is empty afterwards).

### Task 7: Close the spec, look at the panel, verify the whole thing

**Files:**
- Modify: `docs/refinements/panel-i18n.md` (status and the amendments)
- No new code.

**Interfaces:**
- Consumes: everything. Produces: the closed spec and the evidence that the four plugins work together in both languages.

- [ ] **Step 1: Close the spec**

In `docs/refinements/panel-i18n.md`, replace:

```markdown
- **Status:** refined and planned; amended on 2026-10-22 by the owner's decision P08 (the command-line output joins the scope); the plan is [docs/plans/panel-i18n.md](../plans/panel-i18n.md)
```

with:

```markdown
- **Status:** built (ar-board 1.4.0, tidy-board 0.2.0, housekeeping 0.4.0, header-footer 0.4.0); the plan is [docs/plans/panel-i18n.md](../plans/panel-i18n.md)
```

In `docs/refinements/panel-i18n.md`, replace:

```markdown
- The pt-BR wording of the panel and of the cards: drafted by the agent, to be skimmed by the owner.
```

with:

```markdown
- The pt-BR wording of the panel and of the cards: drafted by the agent, to be skimmed by the owner.

## Amendments made while planning and building

- **Codes, not text, below the cards.** tidy-board's inventory holds reason codes (`base_branch`, `current_branch`, `main_worktree`, `current_worktree`, `locked`, `missing_dir`, `unreadable`, `dirty`), `pr` as `None`/`{}`/`{number, tip_matches}` and `remote` as `None`/`exists`/`removed`/`none`; todo-sweep's `age_reason` is a code (`max_blame`, `no_history`, `uncommitted`, `shallow`). The text is rendered from the tables when the cards are built. `scan.json` keeps its shape (tidy-board writes the rendered reasons there, in the scan's language).
- **`report.json`** keeps its keys (`resolver`, `descartar`, `manter`, `sem_decisao`) and records `lang`; only `report.md` follows the language (`report --lang`, else the scan's).
- **The shipped examples follow the new default** (`"lang": "en"`, English labels, an English handoff note); the Portuguese reference batches inside the ar-board and question-board skills set `"lang": "pt-BR"`.
- **A bad `--lang`** exits 2 through argparse (`invalid choice`) on every command; todo-sweep's own parser prints it as an `error:` line (pt-BR `erro:`) and header-footer as a usage error. Nothing is written.
- **The panel's two count phrases** are worded without number agreement (`Batch: x · items: 3 · round 1`, `Undecided items: 1. Finish anyway?`); the command line takes the singular for a count of one.
```

- [ ] **Step 2: Look at the panel in a browser, in both languages**

The suite does not execute the page's JavaScript, so this check is done by hand. The checklist is also the manual test record: tick every line.

Make a scratch batch and serve it:

```bash
D=$(mktemp -d)/i18n-check && mkdir -p "$D" && cat > "$D/batch.json" <<'JSON'
{"batch_id": "i18n-check", "title": "Language check", "round": 1,
 "labels": {"approve": {"text": "Ship it", "tone": "safe"}},
 "items": [
  {"id": "A01", "title": "First proposal", "fields": [{"label": "What", "text": "Do `x`"}], "risk": {"level": "low", "text": "none"}, "confirm": "Are you sure?"},
  {"id": "A02", "title": "Second proposal", "risk": {"level": "médio"}},
  {"id": "Q01", "title": "Which one?", "fields": [{"label": "Context", "text": "c"}], "choices": [{"id": "a", "label": "A", "effect": "ea"}, {"id": "b", "label": "B"}], "recommended": ["a"], "why": "because"}
 ]}
JSON
python3 -I plugins/ar-board/skills/ar-board/scripts/ar_board.py check "$D"
python3 -I plugins/ar-board/skills/ar-board/scripts/ar_board.py check "$D" --lang pt-BR
python3 -I plugins/ar-board/skills/ar-board/scripts/ar_board.py serve "$D" --open
```

- [ ] `check` printed `ok: 3 items, batch i18n-check, round 1`, then `ok: 3 itens, lote i18n-check, rodada 1`; `serve` printed the `AR-BOARD URL:` and `AR-BOARD DECISOES:` lines (the same tags in both languages).

- [ ] The page opens in English: subtitle `Batch: i18n-check · items: 3 · round 1`, badge `● live`, key bar `A ship it · R reject · M maybe · 1-9 choose · Enter confirm · M more context · S skip · C comment · Esc leave the field · ← → navigate`, checkbox `advance on decide`, buttons `Ship it`, `✗ Reject`, `≈ Maybe`, `Skip`, `← Previous`, `Next →`, result box `RESULT` with `✓ 0 ship it ✗ 0 rejected ≈ 0 maybe 3 undecided 0 answered`, button `Review and finish`. The risk pill of A01 is green (`low`), the one of A02 amber (`médio`).
- [ ] Click **PT** in the header: everything above switches at once, without a reload (the card number and the decisions stay): `Lote: i18n-check · itens: 3 · rodada 1`, `● ao vivo`, `aprovar/rejeitar/talvez/...`, `avançar ao decidir`, `≈ Talvez`, `Pular`, `← Anterior`, `Próximo →`, `RESULTADO`, `sem decisão`, `Revisar e concluir`. The custom label `Ship it` (and `ship it` in the key bar and the counters) does not change: it is card content. The `<html lang>` attribute reads `pt-BR` (DevTools).
- [ ] Press **A** on A01: the card arms (`Confirmar: ship it` on the button, the banner `Are you sure?` plus `Aperte A de novo (ou clique em Confirmar) para confirmar; Esc cancela.`); press **Esc**: the hint `Confirmação cancelada.`; press **A** twice: the chip reads `Ship it`, the hint `Ship it: A01 — use ← para voltar e comentar`, the panel advanced to A02.
- [ ] Reload the page: it is still in pt-BR (the toggle is remembered). In DevTools run `localStorage.setItem('ar-board:lang', 'xx')` and reload: the page opens in English (the invalid saved value is ignored; `BOOT.lang` wins). Click **PT** again.
- [ ] On Q01 (`Which one?`): the options read `A`, `B` and `Outra resposta...` (`o texto do campo ao lado vira a resposta`), `★ recomendada` next to A, `★ Por que recomendamos: because`, the button `Preciso de mais contexto`. Press **1**, then click **Revisar e concluir**: the review screen reads `Revise suas respostas (2 de 3)` (A02 is still undecided), the answered rows have `alterar`, A02 has `(sem resposta)` and `responder`, the buttons `Voltar e corrigir` and `Confirmar e avisar o agente`. Click **EN**: `Review your answers (2 of 3)`, `change`, `(no answer)`, `answer`, `Go back and fix`, `Confirm and notify the agent`, plus `1 without an answer: the agent will ask in the chat and never assumes the recommended option.` Click **Go back and fix**, go to Q01 and press **1** again to clear its answer (**S** only moves on), click **Review and finish**: `Review your answers (1 of 3)` and `2 without an answer: ...`.
- [ ] Click **Confirm and notify the agent**: the green banner reads `Finished. Go back to Claude Code and say "done" — the agent reads the decisions by itself.`; click **PT**: `Concluído. Volte ao Claude Code e diga "terminei" — o agente lê as decisões sozinho.`. Click **Limpar**: the dialog reads `Limpar todas as decisões e comentários deste lote?` (cancel it). Then a proposal-only batch (remove Q01 from the file, restart `serve`): with one item undecided, **Concluir e avisar o agente** asks `Itens sem decisão: 1. Concluir mesmo assim?` (in English: `Undecided items: 1. Finish anyway?`).
- [ ] Stop the server (`Ctrl+C`). Run `python3 -I plugins/ar-board/skills/ar-board/scripts/ar_board.py build "$D" --lang pt-BR` (it prints `AR-BOARD ARQUIVO: .../board.html`) and open `"$D/board.html"` in the browser: it opens in pt-BR with the badge `arquivo local — use Copiar`; **EN** switches it to `local file — use Copy` without a reload; **Copiar**/**Copy** flashes `Copiado!`/`Copied!` and the pasted text starts with `AR-BOARD-RESULT` followed by the same JSON shape as before (no `lang`).
- [ ] The tools: in any git repository with a stale branch, `python3 -I plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py scan <repo> --lang pt-BR --gh off` then `python3 -I plugins/tidy-board/skills/tidy-board/scripts/capy_board.py serve <folder> --open`: the buttons read **Apagar**, **Manter**, **Depois**, the fields `Prova`, `Último`, `Vs base`, `Efeito`, the panel chrome opens in pt-BR; the same `scan` without `--lang` gives **Delete**, **Keep**, **Later**, `Proof`, `Last`, `Effect` and an English chrome. `todo_sweep.py scan <repo>` likewise gives `Where`, `Text`, `Age`, `Excerpt` and **Resolve**/**Discard**/**Keep**. In both tools the command line follows: `DO NOT TOUCH:` and `language en` without `--lang`, `NAO TOCAR:` and `idioma pt-BR` with it; `SCAN: ... found` against `SCAN: ... achados`.

- [ ] **Step 3: Run the whole verification**

Run: `git add -A && for d in tests plugins/ar-board/tests plugins/publish-check/tests plugins/housekeeping/tests plugins/tidy-board/tests plugins/header-footer/tests; do PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s $d 2>&1 | grep -v '^AR-BOARD' | tail -n 3; done`

Expected: six runs ending in `OK`: `Ran 11 tests`, `Ran 249 tests`, `Ran 105 tests`, `Ran 418 tests`, `Ran 153 tests`, `Ran 94 tests` (housekeeping and tidy-board take about three minutes together).

Run: `for d in plugins/ar-board/tests plugins/publish-check/tests plugins/housekeeping/tests plugins/tidy-board/tests plugins/header-footer/tests; do PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s $d 2>&1 | grep -v '^AR-BOARD' | tail -n 3; done`

Expected: the same five counts ending in `OK` on Python 3.9.6 (the system python on macOS).

Run: `python3 plugins/ar-board/tools/sync.py --check && python3 plugins/tidy-board/tools/sync.py --check && python3 plugins/publish-check/tools/sync.py --check && python3 plugins/housekeeping/tools/sync.py --check && python3 plugins/header-footer/tools/sync.py --check && python3 tools/marketplace.py --check && echo all-in-sync`

Expected: `all-in-sync`.

Run: `claude plugin validate . 2>&1 | tail -n 1 && python3 -I plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py . | sed -n 2p && python3 -I plugins/publish-check/skills/publish-check/scripts/publish_check.py . | sed -n 2p`

Expected: `Validation passed`, then `clean: no findings` twice (doc-truth and publish-check).

- [ ] **Step 4: Commit**

Run:

```bash
git add -A
git commit -m "docs(panel-i18n): close the refinement with what the work changed" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

Expected: one commit; `git log --oneline base..HEAD` then lists the commit that amended the spec and this plan followed by the thirteen commits of Tasks 1, 2, 2b, 3, 4, 4b, 5, 5b, 5c, 5d, 5e, 6 and 7. The branch is merged locally into base only when the owner says so (no push, no PR).

## Verification of this plan

The first version of this plan (Tasks 0-7, without the command line) was executed end to end before it was committed, twice, in scratch clones outside the working tree, and a pre-flight replay on 2026-10-22 applied 178 of its 180 file instructions cleanly (the two misses were the stale quotes of the housekeeping CHANGELOG and of `CLAUDE.md`, fixed in Tasks 5d and 6) and found the counts, branch, checklist and copy problems corrected here. The page was opened in a real browser from the first clone; the manual check of Task 7 is still the executor's to tick.

The amendment for the command line (Tasks 2b, 4b, 5b, 5c, 5d and 5e, the moved releases, and the edits to Tasks 0-7) was written from code that ran: each new task was first applied to a scratch clone at the state the preceding tasks leave, its suite run until green, and its instructions then generated from that code. The amended plan was then replayed mechanically in a fresh clone (every `Create`, `Replace the whole file`, `Append`, replace and span instruction of Tasks 1 to 7, in order: all applied, none missed), followed by the sync tools and the checks of Task 7 Step 3: catalog 11, ar-board 249, publish-check 105, tidy-board 153, housekeeping 418 and header-footer 94 tests, all `OK` on the machine's Python and on `/usr/bin/python3` 3.9.6; every sync `--check` clean, `claude plugin validate .` passed, doc-truth and publish-check `clean: no findings`. The individual `Run:`/`Expected:` pairs of the new tasks were checked by hand against those runs, not by an automatic comparison; the browser was not opened again (the page changes of the amendment are two reworded strings of the table).

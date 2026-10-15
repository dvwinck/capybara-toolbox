# Switchable panel language Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the ar-board panel speak English by default and pt-BR on demand (a `lang` field in the batch, `--lang` on `serve`/`build`, an EN/PT toggle remembered in the browser), make tidy-board and todo-sweep write their cards (and the todo-sweep report) in a chosen language with `scan --lang`, and have the skills ask for the language the user writes in; released as ar-board 1.4.0, tidy-board 0.2.0 and housekeeping 0.4.0.

**Architecture:** Every user-visible string of the page moves out of the markup and the JavaScript into one Python table, `I18N = {"en": {...}, "pt-BR": {...}}`, injected through the boot data the page already receives (no CSP change; the offline `build` page switches too). The page resolves its language as saved toggle, then `--lang`, then batch `lang`, then `en`, and asks `T('key')` for every text; a parity test pins the two tables and a guard test scans `PAGE` for any literal left outside the table. tidy-board and todo-sweep get a `TEXT`/`LABELS` table per language and one `t(lang, key, **values)` function; their inventories and sidecars hold **codes** (proof levels, reason codes, `age_reason` codes, PR and remote states), never text, so `apply`, `restore`, `report` and the ledger are language independent. The engine is vendored (byte copy) into tidy-board and housekeeping, so every engine change is followed by the three sync tools.

**Tech Stack:** Python 3.9+ standard library (`unittest`, throwaway git repositories), plain HTML/CSS/JavaScript inside the `PAGE` string (not executed by the suite; `node --check` in CI, a manual browser check at the end).

**Spec:** [docs/refinements/panel-i18n.md](../refinements/panel-i18n.md) (decisions P01-P07, rulings R1-R7). Conventions this plan follows: [CLAUDE.md](../../CLAUDE.md). The spec wins where the two disagree; the rulings this plan adds are listed under *Rulings made while planning*.

## Global Constraints

- Python standard library only, Python 3.9 compatible (no `match`, no `X | Y` runtime types, no `str.removeprefix`); `git` is required by tidy-board and housekeeping. The plan was verified on the machine's default Python (3.15) and on the system Python 3.9.6.
- No network, anywhere.
- Never edit generated files by hand: `plugin.json`, `marketplace.json`, the vendored `capy_board.py` copies, `dist/*.SKILL.md`, `question-board/scripts/ar_board.py`. Run the sync tools in the order CLAUDE.md gives: `python3 plugins/ar-board/tools/sync.py`, then `python3 plugins/tidy-board/tools/sync.py` and `python3 plugins/housekeeping/tools/sync.py`, then `python3 tools/marketplace.py`.
- One plugin version for all scripts of housekeeping: `doc_truth.py`, `handoff.py` and `todo_sweep.py` carry the same `VERSION` and header comment, and `plugins/housekeeping/tools/sync.py --check` fails otherwise.
- UI strings and card text per the spec: English default, pt-BR with accents (the page and the files are UTF-8). The command-line output of the engine and the tools stays accent-free Portuguese; the `NAO TOCAR:` reasons tidy-board prints are the pt-BR card text (with accents), see the rulings.
- Commit hygiene: every commit is authored with the owner's personal address, which the repo-local git config already pins (print it with `git config --local user.email`; never the work address). Wherever this plan writes `OWNER_EMAIL`, that is the address. The message ends with the single line `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` and NO claude.ai session link (publish-check flags it); plain multi-line body.
- No push and no PR unless the owner asks. `git add -A` before doc-truth (it judges the git tree). `PYTHONDONTWRITEBYTECODE=1` for tests.
- Dates in changelogs are the execution day: wherever this plan writes `DAY`, write the output of `date +%Y-%m-%d`.
- Lessons from the housekeeping build: every new failure path ends in `erro: ...` (or the engine's `batch.json invalido:` list) and exit 2 (engine `check`: exit 1), never a traceback; `lang` values read from files are data (validated against `LANGS`, never used as code, as a format string or in a path); nothing is parsed from label text; tests that pin text are updated, never deleted; each task ends green on its own suite (the transient reds are named where they happen).

## Review Focus

Failure modes the spec implies but a first pass would not test; each line has a test in the task that owns the code.

- **A leftover literal on the page** (a Portuguese or English string left in the markup or the JavaScript outside the table, so one language shows the other's text): `PageLanguageGuardTest.test_no_literal_of_the_page_reads_as_text_outside_the_table` scans every JS string literal and every markup text node and prints what it finds (Task 2).
- **Table key or placeholder drift** (a key missing in one language, a `{placeholder}` renamed on one side, a key the page asks for that no table has, a table key no page uses): `TableTest.test_the_two_tables_have_the_same_keys_and_the_same_placeholders` (Task 1) and `PageLanguageGuardTest.test_every_key_the_page_uses_exists_and_every_key_of_the_table_is_used` (Task 2); the same parity test exists for the two tool tables (Tasks 4 and 5).
- **The toggle with an invalid saved value** (`localStorage` holding `xx` or a stale value): the page keeps `BOOT.lang`; `test_the_precedence_is_saved_toggle_then_boot_then_english` pins the exact guard and the manual check reloads with a bad value (Tasks 2 and 7).
- **A batch with a bad `lang`** (`"pt"`, `"EN"`, `""`, a number, a list): `check` lists `campo 'lang' deve ser en ou pt-BR` and exits 1; `render_page` falls back to English instead of breaking the page (`ValidateLangTest`, `ResolveLangTest`, Task 1).
- **An older batch or scan without `lang`**: the page opens in English; tidy-board `check` and todo-sweep `check`/`report` accept a `scan.json` without `lang` and read it as English (`ResolveLangTest`, Task 1; `LanguageBoardTest`, Task 4; `LanguageReportTest.test_an_older_scan_without_lang_reports_in_english`, Task 5).
- **A `decisions.json`, ledger or `applied.json` produced in one language and read after a rerun in the other**: nothing in them carries a language (`test_the_export_and_the_decisions_carry_no_language`, Task 2); a pt-BR tidy-board batch is applied and restored exactly like an English one (`LanguageApplyTest`, Task 4); a ledger written by a pt-BR report is honoured by an English scan (`LanguageReportTest.test_a_ledger_written_by_a_pt_br_report_is_honoured_by_an_english_scan`, Task 5).
- **Label text containing markup or backticks** (a batch `labels` text such as `<img onerror=1>`, a branch name with a backtick): labels are escaped wherever they reach the DOM (the existing `LabelsPageGuardsTest`, kept, plus `test_batch_labels_and_confirm_are_card_content_shown_as_written`, Task 2); the tool tables are plain text and every value a tool substitutes passes `safe_text`/`shown` (`test_reasons_pr_remote_and_age_render_in_both_languages`, Task 4; `test_backticks_in_names_cannot_open_a_code_span_on_the_card`, kept, Task 5).
- **`scan --lang` with a bad value**: refused by argparse before anything is written, exit 2 (`LanguageCliTest`, Tasks 4 and 5; todo-sweep prints its `erro:` line); a bad value edited into `scan.json` is refused by `check` and by `report` before anything is written (Tasks 4 and 5).
- **`report` on a batch whose scan has no `lang`** (an older scan): English headings, `report.json` records `"lang": "en"` (Task 5).

## Rulings made while planning

Each one is written into the spec's amendments in Task 7; the owner may veto any of them.

- **`lang: null` counts as omitted**, like every other optional key of the batch (`tag`, `meta`, `risk`, `fields`); `check` rejects every other non-string. The spec says "a non-string" is rejected: `null` is the one exception, for consistency with the engine's convention.
- **The `NAO TOCAR:` lines of tidy-board's scan print the reason in pt-BR, with accents** (`NAO TOCAR: main (branch base do repositório)`): the reason is card text rendered from the pt-BR table, the prefix and the rest of the command line stay accent-free Portuguese (R6). Printing the English reason would mix languages on one line; keeping a third, accent-free rendering would mean a third table.
- **todo-sweep's `age_reason` becomes a code** (`max_blame`, `no_history`, `uncommitted`, `shallow`, or empty) in the hits and in `scan.json`, rendered on the card in the chosen language. It is read by nothing else; the tests that pinned the Portuguese text now pin the code.
- **tidy-board's inventory holds codes**: `untouched[].why` is a code (`base_branch`, `current_branch`, `main_worktree` with `path`, `current_worktree`, `locked`, `missing_dir`, `unreadable`, `dirty` with `count`), `pr` is `None` / `{}` / `{number, tip_matches}` and `remote` is `None` / `exists` / `removed` / `none`. `scan.json` keeps its shape: `untouched[].why` is written there as the rendered text in the scan's language, as before.
- **`report.json` keeps its keys** (`resolver`, `descartar`, `manter`, `sem_decisao`) and gains `lang`; only `report.md`'s headings and lines follow the language. The spec's "report.json headings" are those keys, which scripts read.
- **`test_question_summary.py` is not changed**: it pins the text `summary`, which is command-line output and stays Portuguese (spec, *The engine*, last bullet). The spec listed it among the files to update; the four others are updated.
- **The shipped examples follow the new default**: tidy-board's and todo-sweep's examples carry `"lang": "en"` and English labels (the tests compare them with what `scan` writes); ar-board's and question-board's examples (English content) carry `"lang": "en"`, and the Portuguese reference batches inside the two SKILL.md files carry `"lang": "pt-BR"`.
- **Docs beyond the language lines**: besides the READMEs' language lines and `CLAUDE.md`, only the lines of `docs/reference.md` and `docs/pt-BR/guia-completo.md` that state the panel's language, the CLI tables (`--lang`), the risk words and the completion banner are touched. The other Portuguese UI strings quoted there are the pt-BR wording and stay (translating the documentation is out of scope).
- **A bad `--lang` on tidy-board exits 2 through argparse** (`usage:` plus `invalid choice`), like its `--gh`; todo-sweep's own `Parser` turns it into an `erro:` line. Neither writes anything.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `plugins/ar-board/skills/ar-board/scripts/ar_board.py` | `LANGS`, `DEFAULT_LANG`, the `I18N` table, `resolve_lang`, `lang` validation, `--lang` on `serve`/`build`, the boot data, and the `PAGE` string (markup, CSS, JavaScript with `T()`, `applyLang()`, the toggle). |
| `plugins/ar-board/skills/question-board/scripts/ar_board.py`, `plugins/tidy-board/skills/tidy-board/scripts/capy_board.py`, `plugins/housekeeping/skills/todo-sweep/scripts/capy_board.py`, `plugins/ar-board/dist/*.SKILL.md` | Generated byte copies of the engine and the single-file variants: regenerated by the sync tools, never edited. |
| `plugins/ar-board/tests/test_lang.py` (new), `test_page.py`, `test_labels_confirm.py`, `test_cli.py`, `test_validate.py` | Table parity, validation, resolution, boot data, CLI flags; the page guards; the pinned Portuguese literals updated. |
| `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py` | `LANGS`, `TEXT`, `LABELS`, `t()`, `check_lang`, codes in `inventory`, `reason_text`/`pr_text`/`remote_text`, cards and `build_scan` in a language, `--lang`, `lang` in `scan.json`. |
| `plugins/tidy-board/tests/test_scan.py`, `test_inventory.py`, `test_apply.py`, `test_skill.py`, `test_package.py`, `plugins/tidy-board/skills/tidy-board/examples/*.json` | Both languages tested; the examples in the new default. |
| `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py` | `LANGS`, `TEXT`, `LABELS`, `AGE_REASONS`, `t()`, `check_lang`, cards and the report in a language, `--lang`, `lang` in `scan.json` and `report.json`. |
| `plugins/housekeeping/tests/test_ts_scan.py`, `test_ts_report.py`, `test_ts_cli.py`, `test_skills.py`, `plugins/housekeeping/skills/todo-sweep/examples/*.json` | Both languages tested; the examples in the new default. |
| `plugins/*/CHANGELOG.md`, `plugins/*/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | Releases 1.4.0, 0.2.0 and 0.4.0 (the manifests and the catalog through the sync tools). |
| The four panel skills (`ar-board`, `question-board`, `tidy-board`, `todo-sweep` `SKILL.md`), the examples, the plugin READMEs (EN and pt-BR), `plugins/ar-board/docs/*`, `CLAUDE.md`, `docs/refinements/panel-i18n.md` | The agent asks for the language; the docs say what is English, what is pt-BR and what stays Portuguese. |

---

### Task 0: Pre-flight: the branch and the baseline

**Files:**
- No files.

**Interfaces:**
- Produces: the branch `feat/panel-i18n`, cut from `docs/panel-i18n` (the branch that holds the spec and this plan).

- [ ] **Step 1: Cut the branch and check who commits**

The spec and this plan are committed on `docs/panel-i18n`. The work goes on a branch cut from it, and every commit is authored with the owner's personal address (the repo-local git config, never the work address).

Run: `git switch -c feat/panel-i18n && git config --local user.email`

Expected: the branch is created and the owner's personal address (OWNER_EMAIL) is printed; a livon.io address means stop and fix the config.

- [ ] **Step 2: Record the baseline**

Run: `for d in tests plugins/ar-board/tests plugins/publish-check/tests; do PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s $d 2>&1 | tail -n 3; done`

Expected: three runs ending in `OK`: catalog `Ran 11 tests`, ar-board `Ran 202 tests`, publish-check `Ran 105 tests`. The tidy-board suite (133 tests, about two minutes) and the housekeeping suite (356 tests, about a minute) are run when their tasks start.

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
        "subtitle": "Batch: {id} · {n} items · round {round}", "risk": "Risk",
        "decided_hint": "{label}: {id} — use ← to go back and comment",
        "result": "Result", "note_label": "General note on the batch (batch_note)",
        "note_placeholder": "General remark about this whole batch...",
        "finish": "Finish and notify the agent", "review_finish": "Review and finish", "download": "Download JSON",
        "copy": "Copy", "copied": "Copied!", "clear": "Clear",
        "clear_confirm": "Clear every decision and comment of this batch?",
        "finish_anyway": "{n} items without a decision. Finish anyway?",
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
        "subtitle": "Lote: {id} · {n} itens · rodada {round}", "risk": "Risco",
        "decided_hint": "{label}: {id} — use ← para voltar e comentar",
        "result": "Resultado", "note_label": "Nota geral do lote (batch_note)",
        "note_placeholder": "Observação geral sobre este lote inteiro...",
        "finish": "Concluir e avisar o agente", "review_finish": "Revisar e concluir", "download": "Baixar JSON",
        "copy": "Copiar", "copied": "Copiado!", "clear": "Limpar",
        "clear_confirm": "Limpar todas as decisões e comentários deste lote?",
        "finish_anyway": "{n} itens sem decisão. Concluir mesmo assim?",
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
python3 - <<'PY'
import importlib.util, re, pathlib
spec = importlib.util.spec_from_file_location("ab", "plugins/ar-board/skills/ar-board/scripts/ar_board.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
pathlib.Path("/tmp/panel.js").write_text("\n".join(re.findall(r"<script>(.*?)</script>", m.PAGE, re.S)), encoding="utf-8")
PY
node --check /tmp/panel.js && echo node-ok || echo 'node is not installed: CI will parse the script'
```

Expected: `node-ok` (or the fallback message).

- [ ] **Step 6: Commit**

Run:

```bash
git add -A
git commit -m "feat(ar-board): the page reads every string from the I18N table and gets an EN/PT toggle" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

Expected: one commit (git status --short is empty afterwards).

### Task 3: Release ar-board 1.4.0 and regenerate the vendored copies

**Files:**
- Modify: `plugins/ar-board/skills/ar-board/scripts/ar_board.py` (header comment and `VERSION`), `plugins/ar-board/CHANGELOG.md`
- Generated (by the sync tools): `plugins/ar-board/.claude-plugin/plugin.json`, `plugins/ar-board/dist/*.SKILL.md`, `plugins/ar-board/skills/question-board/scripts/ar_board.py`, `plugins/tidy-board/skills/tidy-board/scripts/capy_board.py`, `plugins/housekeeping/skills/todo-sweep/scripts/capy_board.py`, `.claude-plugin/marketplace.json`

**Interfaces:**
- Produces: ar-board 1.4.0 everywhere the version appears; the engine that Tasks 4 and 5 vendor (their `check` must accept `lang`).

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
- An **EN/PT toggle** in the header, next to the live/offline badge. It switches the chrome at once, sets `<html lang>` and is remembered in the browser (`localStorage` key `ar-board:lang`). Precedence: the saved toggle, then `--lang`, then the batch's `lang`, then English. A saved value that is not one of the two is ignored.
- Risk levels `low`, `medium` and `high` are coloured like `baixo`, `medio` and `alto` (accents and case still ignored); the CSS classes do not change.

### Changed
- The pt-BR wording of the panel is now written with accents (the page is UTF-8). The command-line output of `check`, `summary` and `wait`, the HTTP error bodies and the text `summary` stay accent-free Portuguese, as before.
- Batch-level `labels` and per-item `confirm` are card content: they are shown as written and do not follow the toggle. The key letters (`A`, `R`, `M`, `S`, `C`) are the same in both languages.
- `decisions.json` and the offline `AR-BOARD-RESULT` export have the same shape as before; nothing about the language is stored in them.

## [1.3.1] - 2026-10-15
```

- [ ] **Step 2: Sync everything and check**

Run: `python3 plugins/ar-board/tools/sync.py && python3 plugins/tidy-board/tools/sync.py && python3 plugins/housekeeping/tools/sync.py && python3 tools/marketplace.py && python3 plugins/ar-board/tools/sync.py --check && python3 plugins/tidy-board/tools/sync.py --check && python3 plugins/housekeeping/tools/sync.py --check && python3 tools/marketplace.py --check && echo all-in-sync`

Expected: `updated:` lines for `.claude-plugin/plugin.json`, the two `dist/` variants, the question-board copy, the two `capy_board.py` and `.claude-plugin/marketplace.json`, then `all-in-sync`.

Run: `grep -c '"version": "1.4.0"' plugins/ar-board/.claude-plugin/plugin.json .claude-plugin/marketplace.json && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/ar-board/tests 2>&1 | grep -v '^AR-BOARD' | tail -n 3 && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests 2>&1 | tail -n 1`

Expected: `plugins/ar-board/.claude-plugin/plugin.json:1`, `.claude-plugin/marketplace.json:1`, `Ran 232 tests` and `OK` twice (ar-board and the catalog).

- [ ] **Step 3: Commit**

Run:

```bash
git add -A
git commit -m "chore(ar-board): release 1.4.0 and regenerate the vendored engine copies" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

Expected: one commit (git status --short is empty afterwards).

### Task 4: tidy-board: cards in a language, `scan --lang`, release 0.2.0

**Files:**
- Modify: `plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py` (the table replaces `PROOF_TEXT`; `pr_note`/`remote_note` become `pr_info`/`remote_state`; `inventory` stores codes; the cards section is replaced; `scan_problems`, `cmd_scan`, `parser`, header and `VERSION`)
- Modify: `plugins/tidy-board/tests/test_inventory.py`, `test_scan.py`, `test_apply.py`, `test_skill.py`, `test_package.py`; `plugins/tidy-board/skills/tidy-board/examples/batch.example.json`, `scan.example.json`; `plugins/tidy-board/CHANGELOG.md`
- Generated: `plugins/tidy-board/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`

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

`check` refuses a bad `lang` in `scan.json`, `scan` takes `--lang`, prints the `NAO TOCAR:` reasons in pt-BR (the command line stays Portuguese) and names the language on its summary line:

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
    for u in inv["untouched"]:  # the command line stays Portuguese whatever the cards' language
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

- [ ] **Step 7: Release 0.2.0**

Header comment, `VERSION`, the usage line, the changelog (`DAY` is the day of execution) and the two sync tests that pin the released version:

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

### Changed
- **The default is English.** A `scan` without `--lang` writes English cards; pass `--lang pt-BR` for the Portuguese ones.
- The inventory holds codes, not text: the reasons an item is never offered, the merged-PR note and the remote note are rendered from a per-language table when the cards are built. `apply`, `restore` and the ledger of `applied.json` are unchanged: they read ids, shas and proofs, never a label.
- The command-line output stays Portuguese (`NAO TOCAR:` lines, the scan summary, `apply`'s per-item lines, errors). The scan summary line ends with `; idioma <lang>`.
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

Expected: `Ran 52 tests` (test_scan.py and test_skill.py), `Ran 12 tests` (test_package.py) and the catalog, each ending in `OK`.

- [ ] **Step 8: Commit**

Run:

```bash
git add -A
git commit -m "feat(tidy-board): cards in English by default or pt-BR with scan --lang, release 0.2.0" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

Expected: one commit (git status --short is empty afterwards).

### Task 5: todo-sweep: cards and report in a language, `scan --lang`, release housekeeping 0.4.0

**Files:**
- Modify: `plugins/housekeeping/skills/todo-sweep/scripts/todo_sweep.py` (the table replaces `LABELS`; `age_reason` codes; the cards section is replaced; `cmd_scan`, `scan_problems`, `SECTIONS`, `report_markdown`, `cmd_report`, `parser`, header and `VERSION`)
- Modify: `plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py`, `plugins/housekeeping/skills/handoff/scripts/handoff.py` (header and `VERSION` only: one plugin, one version)
- Modify: `plugins/housekeeping/tests/test_ts_scan.py`, `test_ts_report.py`, `test_ts_cli.py`, `test_skills.py`; `plugins/housekeeping/skills/todo-sweep/examples/batch.example.json`, `scan.example.json`; `plugins/housekeeping/CHANGELOG.md`
- Generated: `plugins/housekeeping/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`

**Interfaces:**
- Consumes: the engine's `validate` with `lang` (Task 3, through `capy_board.py`).
- Produces: `LANGS`, `DEFAULT_LANG`, `AGE_REASONS`, `TEXT`, `LABELS[lang]`, `check_lang(lang)` (raises `SweepError`), `t(lang, key, **values)`, `area(file)` returning `''` at the root, `age_text(h, lang)`, `card_for(item_id, h, lang)`, `build_batch(batch_id, shown_hits, found, lang)`, `build_scan(batch_id, root, shown_hits, totals, lang)`, `SECTIONS` as `(json key, text key)` pairs, `report_markdown(scan, groups, lang)`, `scan --lang {en,pt-BR}` (default `en`), `lang` in `scan.json` and `report.json`, `scan_problems` refusing a bad `lang`.

- [ ] **Step 1: Record the baseline and update the tests that pin the old text**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/housekeeping/tests 2>&1 | tail -n 3`

Expected: `Ran 356 tests` and `OK` (about a minute).

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

Expected: `Ran 372 tests` and `OK` (doc-truth's dogfooding test judges the git tree, hence the git add -A).

- [ ] **Step 7: Release housekeeping 0.4.0**

The three scripts move together (one plugin, one version); `DAY` is the day of execution:

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

In `plugins/housekeeping/CHANGELOG.md`, replace:

```markdown
## [Unreleased]

## [0.3.1] - 2026-10-15
```

with:

```markdown
## [Unreleased]

## [0.4.0] - DAY

### Added
- todo-sweep: `scan --lang en|pt-BR` chooses the language of the cards (field labels, titles, the age wording, `labels`, the subtitle) and of `report.md`. The language is written to `batch.json` (`lang`, so the panel opens in it) and to `scan.json`; `report` reads it from there and records it in `report.json` (`lang`). `check` and `report` refuse any other value in `scan.json`; an older scan without `lang` is read as English.
- todo-sweep: the pt-BR cards and report are now written with accents.

### Changed
- **todo-sweep's default is English.** A `scan` without `--lang` writes English cards and an English `report.md`; pass `--lang pt-BR` for Portuguese.
- todo-sweep: `age_reason` in the hits and in `scan.json` is a code (`max_blame`, `no_history`, `uncommitted`, `shallow`, or empty), rendered on the card in the chosen language. `report.json` keeps its keys (`resolver`, `descartar`, `manter`, `sem_decisao`) and the ledger its words (`discard`, `keep`): nothing a script reads depends on the language.
- The command-line output of the three tools stays Portuguese. doc-truth and handoff change only their version number (one plugin, one version).
- todo-sweep requires ar-board 1.4.0 (the vendored engine) for the panel to honour `lang`.

## [0.3.1] - 2026-10-15
```

Run: `python3 plugins/housekeeping/tools/sync.py && python3 tools/marketplace.py && python3 plugins/housekeeping/tools/sync.py --check && python3 tools/marketplace.py --check && echo in-sync`

Expected: `updated: .claude-plugin/plugin.json`, `updated: .claude-plugin/marketplace.json`, `in-sync`.

Run: `git add -A && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/housekeeping/tests 2>&1 | tail -n 3 && PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s plugins/housekeeping/tests 2>&1 | tail -n 3 && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests 2>&1 | tail -n 1`

Expected: `Ran 372 tests` and `OK` on both Pythons, then `OK` for the catalog.

- [ ] **Step 8: Commit**

Run:

```bash
git add -A
git commit -m "feat(todo-sweep): cards and report in English by default or pt-BR with scan --lang, release housekeeping 0.4.0" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

Expected: one commit (git status --short is empty afterwards).

### Task 6: The skills, the examples and the docs

**Files:**
- Modify: `plugins/ar-board/skills/ar-board/SKILL.md`, `plugins/ar-board/skills/question-board/SKILL.md`, `plugins/tidy-board/skills/tidy-board/SKILL.md`, `plugins/housekeeping/skills/todo-sweep/SKILL.md`; `plugins/ar-board/skills/ar-board/examples/batch.example.json`, `plugins/ar-board/skills/question-board/examples/batch.example.json`; the six plugin READMEs that have a language line (`plugins/{ar-board,tidy-board,housekeeping}/README.md` and `README.pt-BR.md`); `plugins/ar-board/docs/reference.md`, `plugins/ar-board/docs/pt-BR/guia-completo.md`; `CLAUDE.md`
- Generated: `plugins/ar-board/dist/*.SKILL.md` (from the two ar-board skills)
- Not changed: `doc-truth`, `handoff` and `publish-check` `SKILL.md` (they do not mention the panel; a grep proves it), `publish-check`'s READMEs, the root READMEs (no language line).

**Interfaces:**
- Consumes: the flags and fields of Tasks 1, 4 and 5.
- Produces: skills that name each panel literal in English first with the pt-BR wording next to it, tell the agent to ask for the language the user writes in (`lang` in the batch; `--lang` on `scan`) and accept "done" or "terminei" as the finish signal; docs that say what is English, what is pt-BR and what stays Portuguese.

- [ ] **Step 1: Confirm which skills mention the panel's language**

Run: `grep -l -E "terminei|Concluir|Copiar|avancar|panel" plugins/*/skills/*/SKILL.md`

Expected: exactly the four panel skills: `plugins/ar-board/skills/ar-board/SKILL.md`, `plugins/ar-board/skills/question-board/SKILL.md`, `plugins/housekeeping/skills/todo-sweep/SKILL.md`, `plugins/tidy-board/skills/tidy-board/SKILL.md` (doc-truth and handoff mention Portuguese only for the tool output and the note headings, which do not change).

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
Reply to the user in the user's language. Write card content (titles, fields, risks, concepts) in that language too. The panel's own buttons and labels exist in English (the default) and in pt-BR: set `"lang": "pt-BR"` in the batch when the user writes in Portuguese, and `"lang": "en"` (or omit it) otherwise. The user can also switch the panel with the EN/PT toggle in its header; that never changes the cards. The panel literals below are written in English first, with the pt-BR wording next to them.
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
the user left before clicking `Concluir`. Work with what was decided.
```

with:

```markdown
the user left before clicking **Finish and notify the agent** (pt-BR `Concluir e avisar o agente`). Work with what was decided.
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
Reply to the user in the user's language. Write question and card content (titles, context, options, effects) in that language too. The panel's own buttons and labels exist in English (the default) and in pt-BR: set `"lang": "pt-BR"` in the batch when the user writes in Portuguese, and `"lang": "en"` (or omit it) otherwise. The user can also switch the panel with the EN/PT toggle in its header; that never changes the questions. The panel literals below are written in English first, with the pt-BR wording next to them.
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
Reply to the user in the user's language. The panel and the cards that `scan` writes exist in English (the default) and in pt-BR: run `scan --lang pt-BR` when the user writes in Portuguese, and `scan` (or `--lang en`) otherwise. The user can also switch the panel's own buttons with the EN/PT toggle in its header; the cards stay in the language of the scan. Never edit `batch.json` or `scan.json` to translate them. The literals below are written in English first, with the pt-BR wording next to them.
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

`scan` does not fetch anything from the network and does not change the repository. `--lang` (default `en`) is the language of the cards; the summary line ends with `idioma <lang>`.
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
- At the end the user clicks **Finish and notify the agent** (pt-BR `Concluir e avisar o agente`) and tells you `done` (pt-BR `terminei`). Accept either, or a clear equivalent ("finished"), but only when it clearly says the panel is finished. Anything vaguer ("ok", "go on") is not the signal: ask the user to finish the panel. The panel itself says `Finished. Go back to Claude Code and say "done"` (pt-BR `Concluído. Volte ao Claude Code e diga "terminei"`). If items are left without a decision (normal when the group card is used), the panel asks `N items without a decision. Finish anyway?` (pt-BR `N itens sem decisão. Concluir mesmo assim?`). The user only has to confirm.
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
Reply to the user in the user's language. You do not write the cards: `scan` writes them. The cards, the panel and `report.md` exist in English (the default) and in pt-BR: run `scan --lang pt-BR` when the user writes in Portuguese, and `scan` (or `--lang en`) otherwise; `report` follows the language of the scan by itself. The user can also switch the panel's own buttons with the EN/PT toggle in its header. Never edit `batch.json` or `scan.json` to translate them.
```

In `plugins/housekeeping/skills/todo-sweep/SKILL.md`, replace:

```markdown
Options: `--limit N` (cards per batch, default 20), `--max-blame N` (how many to measure with `git blame`, default 300) and `--out <pasta>`.
```

with:

```markdown
Options: `--limit N` (cards per batch, default 20), `--max-blame N` (how many to measure with `git blame`, default 300), `--lang en|pt-BR` (the language of the cards and of the report, default `en`) and `--out <pasta>`.
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
usually they must click **Finish** first. It writes `report.md` and `report.json` in the batch (sections `Resolve`, `Discard`, `Keep` and `No decision`; pt-BR `Resolver`, `Descartar`, `Manter`, `Sem decisão`; with the user's comments) and records the Discard and Keep decisions in `ledger.json`. The tool prints `REPORT: <N> resolver, <N> descartar, <N> manter, <N> sem decisao` (always in Portuguese). Present the counts and what ended up under Resolve.
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
- **Languages:** the skill is in English; the panel is in English by default and switchable to pt-BR (`lang` in the batch, `--lang` on `serve` and `build`, or the EN/PT toggle in its header); the CLI messages are in Portuguese; the documentation is in English
```

In `plugins/ar-board/README.pt-BR.md`, replace:

```markdown
- **Idiomas:** a skill está em inglês; o painel e as mensagens da linha de comando estão em português; a documentação está em inglês
```

with:

```markdown
- **Idiomas:** a skill está em inglês; o painel abre em inglês e muda para pt-BR (`lang` no batch, `--lang` em `serve` e `build`, ou o seletor EN/PT no cabeçalho); as mensagens da linha de comando estão em português; a documentação está em inglês
```

In `plugins/tidy-board/README.md`, replace:

```markdown
- **Languages:** the skill is in English; the panel, the card text and the CLI messages are in Portuguese; the documentation is in English
```

with:

```markdown
- **Languages:** the skill is in English; the panel and the cards are in English by default or in pt-BR (`scan --lang pt-BR`); the CLI messages are in Portuguese; the documentation is in English
```

In `plugins/tidy-board/README.pt-BR.md`, replace:

```markdown
- **Idiomas:** a skill está em inglês; o painel, o texto dos cards e as mensagens da linha de comando estão em português; a documentação principal está em inglês
```

with:

```markdown
- **Idiomas:** a skill está em inglês; o painel e os cards saem em inglês por padrão ou em pt-BR (`scan --lang pt-BR`); as mensagens da linha de comando estão em português; a documentação principal está em inglês
```

In `plugins/housekeeping/README.md`, replace:

```markdown
- **Languages:** the skills are in English; the tools' output, the todo-sweep panel and its cards are in Portuguese; the documentation is in English
```

with:

```markdown
- **Languages:** the skills are in English; the tools' output is in Portuguese; the todo-sweep panel, its cards and its report are in English by default or in pt-BR (`scan --lang pt-BR`); the documentation is in English
```

In `plugins/housekeeping/README.pt-BR.md`, replace:

```markdown
- **Idiomas:** as skills estão em inglês; a saída das ferramentas, o painel do todo-sweep e seus cards estão em português; a documentação está em inglês
```

with:

```markdown
- **Idiomas:** as skills estão em inglês; a saída das ferramentas está em português; o painel do todo-sweep, seus cards e seu relatório saem em inglês por padrão ou em pt-BR (`scan --lang pt-BR`); a documentação está em inglês
```

In `plugins/ar-board/docs/reference.md`, replace:

```markdown
This document is a reference. Strings quoted in Portuguese (CLI output, validation messages, UI labels) are the program's real output, which is written without accents.
```

with:

```markdown
This document is a reference. CLI output and validation messages are quoted as the program writes them, in Portuguese without accents. Panel labels are quoted in their pt-BR wording; the panel opens in English by default (see [Visual design, responsiveness and accessibility](#visual-design-responsiveness-and-accessibility)).
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
- **Textos citados:** as mensagens da linha de comando aparecem aqui exatamente como o programa as escreve, sem acentos; os rótulos do painel aparecem na versão pt-BR (o painel abre em inglês por padrão; ver §19).
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
while the panel UI, the card text the tools generate and the CLI messages of ar-board, tidy-board and housekeeping are Portuguese (publish-check prints English).
```

with:

```markdown
while the panel UI and the cards the tools generate are English by default and pt-BR on demand (`lang` in the batch, `--lang` on `serve`/`build`/`scan`, an EN/PT toggle in the panel's header), and the CLI messages of ar-board, tidy-board and housekeeping are Portuguese (publish-check prints English).
```

In `CLAUDE.md`, replace:

```markdown
- In-page UI strings are accent-free Portuguese by project convention (the page itself is UTF-8); card content may be any Unicode.
```

with:

```markdown
- Every user-visible string of the panel lives in the `I18N` table of `ar_board.py` (`en` and `pt-BR`, the latter with accents; a test pins equal keys and placeholders and another flags any literal left in `PAGE`). The tool tables (`TEXT` and `LABELS` in the tidy-board and todo-sweep scripts) carry both languages too; everything a script parses (ids, proofs, decisions, ledger words, JSON keys, `age_reason` codes) stays language independent. CLI messages stay accent-free Portuguese; card content may be any Unicode.
```

- [ ] **Step 5: Regenerate the single-file variants and check the documents**

Run: `python3 plugins/ar-board/tools/sync.py && git add -A && python3 -I plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py . | sed -n 2p && python3 -I plugins/publish-check/skills/publish-check/scripts/publish_check.py . | sed -n 2p`

Expected: `updated: dist/ar-board-single-file.SKILL.md`, `updated: dist/question-board-single-file.SKILL.md`, then `limpo: nenhum achado` and `clean: no findings`.

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/ar-board/tests -p 'test_[lpv]*.py' 2>&1 | tail -n 1 && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/tidy-board/tests -p test_skill.py 2>&1 | tail -n 1 && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s plugins/housekeeping/tests -p test_skills.py 2>&1 | tail -n 1`

Expected: `OK` three times (the examples still validate, the skills still run the bundled scripts, the repository documents tell the truth).

- [ ] **Step 6: Commit**

Run:

```bash
git add -A
git commit -m "docs: the skills ask for the panel language; the docs say the panel and the cards are English or pt-BR" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

Expected: one commit (git status --short is empty afterwards).

### Task 7: Close the spec, look at the panel, verify the whole thing

**Files:**
- Modify: `docs/refinements/panel-i18n.md` (status and the amendments)
- No new code.

**Interfaces:**
- Consumes: everything. Produces: the closed spec and the evidence that the three plugins work together in both languages.

- [ ] **Step 1: Close the spec**

In `docs/refinements/panel-i18n.md`, replace:

```markdown
- **Status:** refined, awaiting the owner's review of this written spec (no plan yet)
```

with:

```markdown
- **Status:** built (ar-board 1.4.0, tidy-board 0.2.0, housekeeping 0.4.0); the plan is [docs/plans/panel-i18n.md](../plans/panel-i18n.md)
```

In `docs/refinements/panel-i18n.md`, replace:

```markdown
- The pt-BR wording of the panel and of the cards: drafted by the agent, to be skimmed by the owner.
```

with:

```markdown
- The pt-BR wording of the panel and of the cards: drafted by the agent, to be skimmed by the owner.

## Amendments made while planning and building

- **`lang: null` counts as omitted** in the batch, like every other optional key; every other non-string and every other string is rejected by `check`.
- **Codes, not text, below the cards.** tidy-board's inventory holds reason codes (`base_branch`, `current_branch`, `main_worktree`, `current_worktree`, `locked`, `missing_dir`, `unreadable`, `dirty`), `pr` as `None`/`{}`/`{number, tip_matches}` and `remote` as `None`/`exists`/`removed`/`none`; todo-sweep's `age_reason` is a code (`max_blame`, `no_history`, `uncommitted`, `shallow`). The text is rendered from the tables when the cards are built. `scan.json` keeps its shape (tidy-board writes the rendered reasons there, in the scan's language).
- **The `NAO TOCAR:` lines** of tidy-board's scan print the reason in pt-BR with accents (it is card text); the prefix and the rest of the command line stay accent-free Portuguese. The scan summary line ends with `; idioma <lang>`.
- **`report.json`** keeps its keys (`resolver`, `descartar`, `manter`, `sem_decisao`) and records `lang`; only `report.md` follows the language.
- **`test_question_summary.py` was not changed**: it pins the text `summary`, which is command-line output.
- **The shipped examples follow the new default** (`"lang": "en"`, English labels); the Portuguese reference batches inside the ar-board and question-board skills set `"lang": "pt-BR"`.
- **A bad `--lang`** exits 2 through argparse on tidy-board (like `--gh`) and as an `erro:` line on todo-sweep; neither writes anything.
- **Docs beyond the language lines**: only the lines that state the panel's language, the CLI tables, the risk words and the completion banner of `docs/reference.md` and `docs/pt-BR/guia-completo.md` were touched.
```

- [ ] **Step 2: Look at the panel in a browser, in both languages**

The suite does not execute the page's JavaScript, so this check is done by hand. The checklist is also the manual test record: tick every line.

Make a scratch batch and serve it:

```bash
mkdir -p /tmp/i18n-check && cat > /tmp/i18n-check/batch.json <<'JSON'
{"batch_id": "i18n-check", "title": "Language check", "round": 1,
 "labels": {"approve": {"text": "Ship it", "tone": "safe"}},
 "items": [
  {"id": "A01", "title": "First proposal", "fields": [{"label": "What", "text": "Do `x`"}], "risk": {"level": "low", "text": "none"}, "confirm": "Are you sure?"},
  {"id": "A02", "title": "Second proposal", "risk": {"level": "médio"}},
  {"id": "Q01", "title": "Which one?", "fields": [{"label": "Context", "text": "c"}], "choices": [{"id": "a", "label": "A", "effect": "ea"}, {"id": "b", "label": "B"}], "recommended": ["a"], "why": "because"}
 ]}
JSON
python3 -I plugins/ar-board/skills/ar-board/scripts/ar_board.py check /tmp/i18n-check
python3 -I plugins/ar-board/skills/ar-board/scripts/ar_board.py serve /tmp/i18n-check --open
```

- [ ] The page opens in English: subtitle `Batch: i18n-check · 3 items · round 1`, badge `● live`, key bar `A ship it · R reject · M maybe · 1-9 choose · Enter confirm · M more context · S skip · C comment · Esc leave the field · ← → navigate`, checkbox `advance on decide`, buttons `Ship it`, `✗ Reject`, `≈ Maybe`, `Skip`, `← Previous`, `Next →`, result box `RESULT` with `✓ 0 ship it ✗ 0 rejected ≈ 0 maybe 3 undecided 0 answered`, button `Review and finish`. The risk pill of A01 is green (`low`), the one of A02 amber (`médio`).
- [ ] Click **PT** in the header: everything above switches at once, without a reload (the card number and the decisions stay): `Lote: i18n-check · 3 itens · rodada 1`, `● ao vivo`, `aprovar/rejeitar/talvez/...`, `avançar ao decidir`, `≈ Talvez`, `Pular`, `← Anterior`, `Próximo →`, `RESULTADO`, `sem decisão`, `Revisar e concluir`. The custom label `Ship it` (and `ship it` in the key bar and the counters) does not change: it is card content. The `<html lang>` attribute reads `pt-BR` (DevTools).
- [ ] Press **A** on A01: the card arms (`Confirmar: ship it` on the button, the banner `Are you sure?` plus `Aperte A de novo (ou clique em Confirmar) para confirmar; Esc cancela.`); press **Esc**: the hint `Confirmação cancelada.`; press **A** twice: the chip reads `Ship it`, the hint `Ship it: A01 — use ← para voltar e comentar`, the panel advanced to A02.
- [ ] Reload the page: it is still in pt-BR (the toggle is remembered). In DevTools run `localStorage.setItem('ar-board:lang', 'xx')` and reload: the page opens in English (the invalid saved value is ignored; `BOOT.lang` wins). Click **PT** again.
- [ ] On Q01 (`Which one?`): the options read `A`, `B` and `Outra resposta...` (`o texto do campo ao lado vira a resposta`), `★ recomendada` next to A, `★ Por que recomendamos: because`, the button `Preciso de mais contexto`. Press **1**, then click **Revisar e concluir**: the review screen reads `Revise suas respostas (3 de 3)`, each row has `alterar`, the buttons `Voltar e corrigir` and `Confirmar e avisar o agente`. Click **EN**: `Review your answers (3 of 3)`, `change`, `Go back and fix`, `Confirm and notify the agent`. Click **Go back and fix**, press **S** on Q01 to leave it unanswered, click **Review and finish**: `(no answer)` and `answer`, plus `1 without an answer: the agent will ask in the chat and never assumes the recommended option.`
- [ ] Click **Confirm and notify the agent**: the green banner reads `Finished. Go back to Claude Code and say "done" — the agent reads the decisions by itself.`; click **PT**: `Concluído. Volte ao Claude Code e diga "terminei" — o agente lê as decisões sozinho.`. Click **Limpar**: the dialog reads `Limpar todas as decisões e comentários deste lote?` (cancel it). Then a proposal-only batch (remove Q01 from the file, restart `serve`): with one item undecided, **Concluir e avisar o agente** asks `1 itens sem decisão. Concluir mesmo assim?` (in English: `1 items without a decision. Finish anyway?`).
- [ ] Stop the server (`Ctrl+C`). Run `python3 -I plugins/ar-board/skills/ar-board/scripts/ar_board.py build /tmp/i18n-check --lang pt-BR` and open `/tmp/i18n-check/board.html` in the browser: it opens in pt-BR with the badge `arquivo local — use Copiar`; **EN** switches it to `local file — use Copy` without a reload; **Copiar**/**Copy** flashes `Copiado!`/`Copied!` and the pasted text starts with `AR-BOARD-RESULT` followed by the same JSON shape as before (no `lang`).
- [ ] The tools: in any git repository with a stale branch, `python3 -I plugins/tidy-board/skills/tidy-board/scripts/tidy_board.py scan <repo> --lang pt-BR --gh off` then `python3 -I plugins/tidy-board/skills/tidy-board/scripts/capy_board.py serve <folder> --open`: the buttons read **Apagar**, **Manter**, **Depois**, the fields `Prova`, `Último`, `Vs base`, `Efeito`, the panel chrome opens in pt-BR; the same `scan` without `--lang` gives **Delete**, **Keep**, **Later**, `Proof`, `Last`, `Effect` and an English chrome. `todo_sweep.py scan <repo>` likewise gives `Where`, `Text`, `Age`, `Excerpt` and **Resolve**/**Discard**/**Keep**.

- [ ] **Step 3: Run the whole verification**

Run: `git add -A && for d in tests plugins/ar-board/tests plugins/publish-check/tests plugins/housekeeping/tests plugins/tidy-board/tests; do PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s $d 2>&1 | grep -v '^AR-BOARD' | tail -n 3; done`

Expected: five runs ending in `OK`: `Ran 11 tests`, `Ran 232 tests`, `Ran 105 tests`, `Ran 372 tests`, `Ran 144 tests` (the last two take about three minutes together).

Run: `for d in plugins/ar-board/tests plugins/publish-check/tests plugins/housekeeping/tests plugins/tidy-board/tests; do PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s $d 2>&1 | grep -v '^AR-BOARD' | tail -n 3; done`

Expected: the same four counts ending in `OK` on Python 3.9.6 (the system python on macOS).

Run: `python3 plugins/ar-board/tools/sync.py --check && python3 plugins/tidy-board/tools/sync.py --check && python3 plugins/publish-check/tools/sync.py --check && python3 plugins/housekeeping/tools/sync.py --check && python3 tools/marketplace.py --check && echo all-in-sync`

Expected: `all-in-sync`.

Run: `claude plugin validate . 2>&1 | tail -n 1 && python3 -I plugins/housekeeping/skills/doc-truth/scripts/doc_truth.py . | sed -n 2p && python3 -I plugins/publish-check/skills/publish-check/scripts/publish_check.py . | sed -n 2p`

Expected: `Validation passed`, `limpo: nenhum achado` and `clean: no findings`.

- [ ] **Step 4: Commit**

Run:

```bash
git add -A
git commit -m "docs(panel-i18n): close the refinement with what the work changed" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

Expected: one commit; git log --oneline docs/panel-i18n..HEAD then lists the seven commits of Tasks 1 to 7. The branch is merged locally into base only when the owner says so (no push, no PR).

## Verification of this plan

This plan was executed end to end before it was committed, twice, in scratch clones of the repository outside the working tree: once while it was written (the code above is the code that ran), and once more by a replay that parses this very document and performs every instruction in a fresh clone (every `Create`, `Append`, replace and span block, every `Run:`), comparing each backticked fragment of every `Expected:` line with the real output. The second replay matched all 33 Run/Expected pairs (the first one had found four wrong expectations and one wrong step order, fixed above). Final counts of the replayed branch: catalog 11, ar-board 232 (was 202), publish-check 105, housekeeping 372 (was 356), tidy-board 144 (was 133), all `OK` on the machine's Python 3.15 and, for the four plugin suites, on `/usr/bin/python3` 3.9.6; the five sync `--check`s, `claude plugin validate .`, doc-truth and publish-check clean; seven commits on `feat/panel-i18n`. The page was also opened in a real browser from the first clone (live `serve` page and a `build --lang pt-BR` page): the toggle, the precedence with an invalid saved value, the armed confirmation, the hints, the counters, the question card, the review screen, the finish and clear dialogs and the offline badge read as the tables say. The manual check of Task 7 is still the executor's to tick.


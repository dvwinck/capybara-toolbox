# Changelog

All notable changes to the **housekeeping** plugin are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-10-23

### Added
- todo-sweep: `scan --lang en|pt-BR` chooses the language of the cards (field labels, titles, the age wording, `labels`, the subtitle) and of `report.md`. The language is written to `batch.json` (`lang`, so the panel opens in it) and to `scan.json`; `report` reads it from there and records it in `report.json` (`lang`). `check` and `report` refuse any other value in `scan.json`; an older scan without `lang` falls back to `CAPYBARA_LANG`, then English.
- todo-sweep: the pt-BR cards and report are now written with accents.
- **Every command of the three tools takes `--lang en|pt-BR`** for its messages: doc-truth, handoff (`collect`, `write`, `verify`, `resume`) and todo-sweep (`scan`, `check`, `report`). Without it, todo-sweep's `check` and `report` speak the language recorded in `scan.json`, and `report --lang` also chooses the language of `report.md`.
- **`CAPYBARA_LANG`** (`en` or `pt-BR`) is the default language when no flag and no recorded language decide; any other value is ignored. Every Capybara Toolbox tool that speaks pt-BR reads the same variable; publish-check prints English only.
- handoff notes in English or pt-BR: `write` writes the note in the language of the run and records it in the data block (`lang`); the agent's metainfo keys and section headings count in either language; `resume` and `verify` read a note in either language, and a note written before 0.4.0 (pt-BR, no `lang` in its block) resumes unchanged.
- handoff notes always start with a metainfo table (`Session metainfo`, pt-BR `Metainfo da sessao`). The agent opens the draft with a `---` block of `Key: Value` lines (`Model`, `Original request` and `Status` are expected, pt-BR `Modelo`, `Pedido original` and `Status`; anything else is optional); the tool adds `Written at` and `Repository` (pt-BR `Gravada em` and `Repositorio`), records the rows in the data block, warns with `warning: metainfo '<key>' is missing` (pt-BR `aviso: falta a metainfo '<key>'`) when an expected one is missing, and refuses a duplicate or reserved key, a control character, an over-long row and a typed citation in the block. `resume` and `verify` never treat the header as citations; a note written before the header existed still resumes. `write --json` has a `missing_meta` list.
- handoff: the `--json` values follow the language of the run: `citations[].why`, `drift[]` and the names in `missing_sections` and `missing_meta` (in 0.3.1 they were always Portuguese), so a consumer must not match them literally. Only those text fields change; the keys and the other values (`type`, `value`, `sha`, `verified`, `line`, the `collect --json` facts) do not depend on the language, as with doc-truth's `message`.
- The handoff skill asks for `model: haiku` in its frontmatter (the override lasts for the turn that runs the skill).

### Changed
- **The default is English** for the three tools: todo-sweep's cards and report, handoff's notes and every command-line message. Pass `--lang pt-BR` (or set `CAPYBARA_LANG=pt-BR`) for Portuguese. The pt-BR command-line text and the pt-BR note are the accent-free Portuguese of 0.3.1, except that a count of one now takes the singular (`1 item`, `1 citacao`, `1 TODO/FIXME achado`).
- In English the prefixes are `error:` and `warning:` (pt-BR `erro:` and `aviso:`), doc-truth prints `clean: no findings` (pt-BR `limpo: nenhum achado`), handoff marks a failed citation `[not verified]` (pt-BR `[nao verificado]`) and todo-sweep names its folder on a `batch:` line (pt-BR `lote:`). The tags `SCAN:`, `REPORT:` and `ok:` are the same in both languages. The `--help` text is English.
- doc-truth: a finding's `value` and `fingerprint` do not depend on the language (the `parity` value stays `falta README.pt-BR.md`), so an `allow` list keeps working in either language; only its `message` follows the language.
- todo-sweep: `age_reason` in the hits and in `scan.json` is a code (`max_blame`, `no_history`, `uncommitted`, `shallow`, or empty), rendered on the card in the chosen language. `report.json` keeps its keys (`resolver`, `descartar`, `manter`, `sem_decisao`) and the ledger its words (`discard`, `keep`): nothing a script reads depends on the language.
- The handoff example note is English, the new default.
- todo-sweep requires ar-board 1.4.0 (the vendored engine) for the panel to honour `lang`.

## [0.3.1] - 2026-10-15

### Changed
- The three skills (doc-truth, handoff, todo-sweep) were rewritten in English for LLM use; the examples were reviewed and left unchanged: they mirror what the tools write. The panel and script output stay in Portuguese. Behaviour and scripts are unchanged apart from the version.
- The vendored engine copy `capy_board.py` was refreshed to ar-board 1.3.1 (header and version only).

### Fixed
- The todo-sweep skill no longer tells the agent to delete "the whole comment line" of a `Descartar` TODO: that would remove the code of a trailing comment. It now says to remove only the comment (the line only when the comment is alone on it).

## [0.3.0] - 2026-10-14

### Added
- The third skill, **todo-sweep** (`todo_sweep.py`): `TODO` and `FIXME` comments as cards on a local board, oldest first, 20 per batch; your decision is recorded in a read-only report and no source file is ever edited.
- `scan` finds the markers inside comments of tracked text files (markdown, binary and files over 1 MB are skipped), takes each one's age from `git blame` (author time; `--max-blame`, default 300; uncommitted lines and a shallow clone's boundary commits have no age), and writes an ar-board batch plus a `scan.json` sidecar into `.todo-sweep/<batch>/`.
- The panel wording is Resolver, Descartar and Manter through the ar-board `labels`. `report` needs a concluded board for the current round and writes `report.md` and `report.json`; each Manter and Descartar is also remembered in `.todo-sweep/ledger.json`, so the next scan offers the next 20 and not the same ones. A TODO is identified by its file and text, never by its line.
- A generated byte copy of the ar-board engine (`capy_board.py`, ar-board 1.3.0) ships inside the skill; `tools/sync.py --check` fails on drift.
- All three scripts now carry the plugin version (0.3.0).

## [0.2.0] - 2026-10-14

### Added
- The second skill, **handoff** (`handoff.py`): an end-of-session note whose git facts come from git and whose citations are checked before the note is saved, and again when it is resumed.
- `collect` prints the git facts as JSON: branch, tip, upstream, commits ahead of and behind the base (`--base`, else the remote default branch, else `base`, `main`, `master`), modified and untracked files, stashes, linked worktrees and the last commits.
- Citations are typed: `` `commit:abc1234` ``, `` `branch:feat/x` `` and `` `file:path/to/f.py:42` ``; only typed spans are verified and an untyped backtick is prose. `write` takes the agent's draft, keeps every word of it, appends ` [nao verificado]` (once) after a citation that fails and saves `.handoff/AAAA-MM-DD-hhmmss.md` with the git section and a machine-readable data block; `verify` checks any note or draft.
- `resume` prints the newest note and compares it with the repository now: a moved branch tip, a changed ahead/behind count, files modified then and not now (or the reverse), stashes, and every citation again. It never acts on its own.
- Exit code 0 when every citation is verified and nothing drifted, 1 otherwise, 2 on error; `--json` has a `schema` field. Never writes outside the notes folder, never uses the network.
- All three scripts now carry the plugin version (0.2.0).

## [0.1.0] - 2026-10-14

### Added
- First release: the plugin and its first skill, **doc-truth** (`doc_truth.py`): a read-only check that what a repository's markdown documents say exists.
- Four checks over every git-tracked `.md` (minus `exclude`): paths cited in backticks and code fences exist in the git tree; relative links and `#anchors` resolve (GitHub slug rules); an `<name>.md` and its `<name>.pt-BR.md` have the same sequence of heading levels, and a `README.md` has a Portuguese counterpart; a version written next to a plugin's name matches its `plugin.json`, and the root READMEs link every plugin of the catalog.
- `.doc-truth.json` with `exclude` (globs), `ignore_paths` (globs for files created at run time) and `allow` (fingerprints of accepted findings; a fingerprint is `sha256(category|document|value)[:16]`, never the line). Unknown keys are an error.
- A readable report, `--json` with a `schema` field, exit code 0 clean, 1 findings, 2 error. It never writes to the repository, never runs a documented command and never uses the network.

---
name: handoff
description: Writes an end-of-session note so the next session can resume the work, with the git facts collected by the tool (branch, commits ahead of the base, modified files, stashes) and the citations checked before saving - whatever does not exist is marked "[not verified]" (pt-BR "[nao verificado]"). Use when the user asks to end the session leaving a handoff, to write a handover note, or to resume one, for example "faz o handoff", "deixa uma nota pra próxima sessão", "retome o handoff", "handoff", "write a handoff note", "resume the handoff", "end of session notes". Triggers - /handoff or /housekeeping:handoff.
model: haiku
---

# handoff (end-of-session note with checked facts)

Writes a note that lets a new session, without your memory, continue the work. Two things set it apart from a note written from memory. First, the **git facts** (branch, tip, commits ahead of the base, modified files, stashes, worktrees) come from git, not from you. Second, every **citation** you write (commit, branch, file) is checked before the note is saved, and a citation that does not exist is marked `[not verified]` (pt-BR `[nao verificado]`), without deleting anything. It needs `python3` (stdlib) and `git`; it does not use the network.

Reply to the user in the user's language. Write the content of the note in the user's language too, and save the note in that language: the tool writes English by default, so pass `--lang pt-BR` to `write` when the user writes in Portuguese (`CAPYBARA_LANG` may set the default for the whole shell). The fixed texts the tool writes (the header, the git section, the mark of a failed citation) follow that language. Keep the metainfo keys and the four section headings exactly as given below, in English or in their accent-free pt-BR form (both count, whatever the note's language), and the citation prefixes `commit:`, `branch:` and `file:` as they are. The tool relies on them.

## When to use

Use it when the user asks for a handover note or to resume one. Never offer it on your own. Resuming happens only on request: no hook, no automatic offer.

## Flow

### 0. Locate the script

The script ships with this skill: `${CLAUDE_SKILL_DIR}/scripts/handoff.py`. Use it directly, always with `python3 -I`.

```bash
test -f "${CLAUDE_SKILL_DIR}/scripts/handoff.py" && echo OK || echo FALTA
```

`OK` means the script exists. `FALTA` means "missing".

If `${CLAUDE_SKILL_DIR}` shows up unexpanded, use the path shown as "Base directory for this skill" when the skill was loaded, written out in full in every command.

In the commands below, `<repositório>` is the repository path ("repository").

### 1. Write the draft

#### The metainfo block

Every note starts with a header table, `Session metainfo` (pt-BR `Metainfo da sessao`), and the tool always writes it. You supply its rows as a block at the very top of the draft: a line `---`, one `Key: Value` per line, a line `---`. The expected keys are fixed text (English, or their pt-BR form); the values are in the user's language.

```markdown
---
Session name: config sonarqube
Model: Claude Sonnet 5.5 (`claude-sonnet-5-5`)
Session: <the session link, only if this conversation gave you one>
Original request: "analyse the backend code base and propose the rules"
Status: Proposal. Nothing applied, no team decision yet.
---
```

- Always give `Model` (pt-BR `Modelo`: the model running this skill, name and id as your system prompt states them), `Original request` (pt-BR `Pedido original`: the user's first request, shortened) and `Status` (where the work stands: done, proposal, blocked). The tool prints `warning: metainfo '<key>' is missing` (pt-BR `aviso: falta a metainfo '<key>'`) for each one you leave out; add it and write the note again.
- Add the rows that help someone resuming and that you actually know, for example `Session name` (only if the user gave one), `Date` (the day of the session, when it is not today), `Session` (the session link, only if this conversation gave you one), `Repo analysed`, `Tools used`, `Scope`, `Memory`, in the note's language. Leave a row out rather than guess it.
- The tool adds `Written at` and `Repository` (pt-BR `Gravada em` and `Repositorio`) itself; do not write those keys, in either language.
- One line per row, at most 40 characters of key and 1000 of value; a `|` is escaped for you. A duplicate key, a control character or a typed citation (`commit:`, `branch:`, `file:`) in a row is an error and nothing is saved: citations go in the sections, where they are checked. A line of the block that is not `Key: Value` is an error too, and a draft that opens with a `---` rule meant as a divider must start with the block or a heading instead.

#### The four sections

Write the rest of the draft with **these four headings**, in this order (the tool only warns if one is missing; it never adds or invents a section):

```markdown
## What was done
## Decisions and why
## Next steps
## What failed or got stuck
```

In a pt-BR note use their pt-BR form, without accents: `## O que foi feito`, `## Decisoes e por que`, `## Proximos passos`, `## O que falhou ou travou` (either form counts). Keep the heading text exactly as shown. Write the content under each heading in the user's language.

Do not put the git state in the draft: the tool adds it after the header (a section titled `## Git state`, pt-BR `## Estado do git`). In each section be concrete: what changed, what was decided and what was discarded (with the reason, so nobody repeats the discussion), the first thing to do when resuming, and the attempts that did not work.

**Cite with a type.** Only these forms, between backticks, are checked; a backtick span with no type is plain text:

- `` `commit:abc1234` ``: a commit (7 to 40 hexadecimal characters);
- `` `branch:nome` ``: a local or remote branch (`origin/main`); `nome` is the branch name ("name");
- `` `file:caminho/do/arquivo.py:42` ``: a file relative to the repository root, with an optional line number; `caminho/do/arquivo.py` is "path/to/file.py".

Cite only what you have seen exist in this session. If the note has no typed citation, nothing is checked: tell the user so.

### 2. Save

```bash
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

The note goes to `.handoff/AAAA-MM-DD-hhmmss.md` (`AAAA-MM-DD` is YYYY-MM-DD and `hhmmss` is the time; the file is private, one per run, and never overwrites another). Exit codes: `0` everything checked (every citation verified; a missing section or metainfo row is only a warning and does not change the exit code), `1` some citation not verified (the note was saved with the mark), `2` error. For a pt-BR note add `--lang pt-BR` after `write <repositório>` and use the pt-BR keys and headings. The tool prints `note saved to <path>` (pt-BR `nota gravada em <path>`), then `<N> citations, <M> not verified` (pt-BR `<N> citacoes, <M> nao verificadas`). Read that output. If there are unverified citations, say which ones and **propose a fix** (a new `write` creates another note). If it prints `warning: section '<name>' is missing` or `warning: metainfo '<key>' is missing` (pt-BR `aviso: falta a secao '<name>'`, `aviso: falta a metainfo '<key>'`), say which one.

`collect` shows only the git facts. `verify <arquivo>` checks the citations of any note or draft without changing the file (`<arquivo>` is "file").

With `--json` (on `write`, `verify` or `resume`) the text fields follow the language of the run: `citations[].why`, `drift[]` and the names in `missing_sections` and `missing_meta` are English or pt-BR, so never match them literally. Read the keys and the other values (`type`, `value`, `sha`, `verified`, `line`) instead; they do not depend on the language.

### 3. Resume (only on request)

```bash
python3 -I "${CLAUDE_SKILL_DIR}/scripts/handoff.py" resume <repositório>
```

It shows the most recent note (`--file` picks another one), checks every citation again, and lists what changed since the note was written: the tip of a branch that moved, the ahead/behind count against the base, modified files that disappeared or appeared, stashes. Exit code `0` with nothing new, `1` with a change or a citation with a problem. **Present the differences before acting**, and do not resume the note's plan blindly: the repository may have moved. `resume` and `verify` read a note in either language, including the ones written before 0.4.0 (pt-BR); their own lines follow `--lang`, never the note.

## Rules

- `.handoff/` must not go into git: notes may cite internal paths or pasted text. The tool does not edit `.gitignore`. Suggest the line `.handoff/` and add it only with the user's OK. Never publish or commit a note.
- Never write something you did not verify as if it were a fact. If you are not sure, say in the note that it is an assumption.
- The header is plain text for the person resuming: it is never checked. `Session` (pt-BR `Sessao`) may hold a session link, which is another reason a note never goes into git.
- Read-only on the repository: the tool only writes the note, and it refuses a `.handoff` folder that is a symbolic link. Never run it on a repository you do not trust: git reads that repository's local configuration. If `git` is not on the PATH, tell the user so.

# housekeeping

Small tools that keep a repository and a work session honest. One plugin, several skills, added one release at a time: **doc-truth** checks that what a repository's documents say actually exists, and **handoff** writes an end-of-session note whose git facts and citations are verified; more follow. Everything is read-only, offline, and Python standard library plus `git`.

- **Version:** see [CHANGELOG](CHANGELOG.md) · **Requires:** `python3` (standard library only) and `git`.
- **Languages:** the skills are in Portuguese; the documentation is in English ([README.pt-BR.md](README.pt-BR.md) is the Portuguese counterpart).

## Install

```text
/plugin marketplace add dvwinck/capybara-toolbox
/plugin install housekeeping@capybara-toolbox
```

Or copy the skills without the plugin system: `./install.sh housekeeping` from a clone.

## Skills

### doc-truth

Reads every git-tracked `.md` file and checks what it claims against the repository. Ask Claude *"check the docs"* or call `/housekeeping:doc-truth`, or run it yourself:

```bash
S=plugins/housekeeping/skills/doc-truth/scripts
python3 -I $S/doc_truth.py            # this repository
python3 -I $S/doc_truth.py --json     # machine-readable, with a schema field
```

Exit code `0` clean, `1` findings, `2` error (not a git repository, bad config). It never writes, never runs a command a document cites and never uses the network.

| Category | What it checks |
| --- | --- |
| `path` | A path cited in backticks or in a code block exists in the **git tree** (not only on your disk, so a local run and CI agree). Placeholders (`<name>`, `PATH`), URLs, flags, absolute paths, tree diagrams and choices such as `A/R/M` are not paths. |
| `link`, `anchor` | A relative link points to something that exists, and a `#anchor` matches a heading of the target (GitHub's slug rules: accents kept, `-1` for repeats, fenced `#` lines are not headings). |
| `parity` | `<name>.md` and `<name>.pt-BR.md` have the same sequence of heading levels (headings are translated, so the text is not compared), and a `README.md` has a `README.pt-BR.md`. |
| `version`, `plugins` | A version written on the same line as a plugin's name matches that plugin's `plugin.json`, and the root READMEs link every plugin of the catalog. |

Configuration is `.doc-truth.json` at the repository root (an unknown key is an error):

```json
{
  "exclude": ["docs/plans/**", "**/CHANGELOG.md"],
  "ignore_paths": [".ar-board/", "decisions.json"],
  "allow": []
}
```

- `exclude`: documents that are not checked (historical, generated). They stay valid link targets.
- `ignore_paths`: paths that do not exist in the tree on purpose (created at run time, or written as shorthand). A pattern with no `/` matches a name in any folder; with a `/` inside it starts at the repository root; `**` crosses folders and `*` does not.
- `allow`: fingerprints of accepted findings. A fingerprint is a hash of the category, the document and the value, never the line, so an edit above an accepted finding does not bring it back.

It is a heuristic: a path in prose that is only an example will be reported, and `ignore_paths` or `allow` is how you say so.

### handoff

An end-of-session note a fresh session can pick up from. Ask Claude *"write a handoff"* or call `/housekeeping:handoff`, or run it yourself:

```bash
S=plugins/housekeeping/skills/handoff/scripts
python3 -I $S/handoff.py collect                          # the git facts only
python3 -I $S/handoff.py write --draft draft.md           # check the citations, save .handoff/<date>-<time>.md
python3 -I $S/handoff.py verify draft.md                  # check the citations of any note, never edits it
python3 -I $S/handoff.py resume                           # the newest note, and what changed since
```

The git facts (branch, tip, commits ahead of and behind the base, modified and untracked files, stashes, linked worktrees, the last commits) come from git, not from memory. The agent's draft has four sections (`O que foi feito`, `Decisoes e por que`, `Proximos passos`, `O que falhou ou travou`) and its citations are **typed**: `` `commit:abc1234` ``, `` `branch:feat/x` `` and `` `file:path/to/f.py:42` ``. Only typed spans are checked and an untyped backtick is prose. A citation that does not exist is kept and followed by ` [nao verificado]`, once; nothing is ever removed from the draft. The note ends with a machine-readable data block (the facts and the citations as they were), which is how `resume` can tell what drifted: a branch tip that moved, a changed ahead/behind count, files that were modified then and not now, stashes, and every citation again.

Exit code `0` when every citation is verified (and, for `resume`, nothing drifted), `1` otherwise, `2` on error; `--json` has a `schema` field. `.handoff/` is not added to `.gitignore` for you: notes can name internal paths, so keep them out of git. Resuming happens only when you ask; there is no hook and no automatic offer.

## Safety

Every tool in this plugin leaves your tracked files alone, none of them uses the network, and none runs a command a document cites. handoff writes only its notes, in `.handoff/` (keep it out of git: notes can quote internal paths, and a `.handoff` that is a symlink is refused). They do trust the repository's own git configuration (git reads it), so do not run them on a repository you do not trust.

## Development

```bash
python3 -m unittest discover -s plugins/housekeeping/tests   # from the repository root
python3 plugins/housekeeping/tools/sync.py                    # after changing a script: the manifest follows its VERSION
```

Each script carries the plugin's `VERSION` and a release bumps them together; see [CONTRIBUTING](../../CONTRIBUTING.md).

# tidy-board

Clean up stale git **branches, worktrees and stashes** from a local board. Every candidate is a card that shows how sure the tool is that it is finished; you decide **Apagar** (delete), **Manter** (keep) or **Depois** (later) with the keyboard; a separate `apply` step re-checks each approved item at the moment it deletes it. Nothing is deleted without your approval, and anything that exists in one place only is backed up first.

- **Version:** see [CHANGELOG](CHANGELOG.md) · **Requires:** `python3` (standard library only) and `git`; `gh` is optional (it proves merged pull requests). `scan` and `apply` never use the network except through `gh`, read-only and only when it is installed (`scan` to prove merged pull requests, `apply` to re-check the P2 items); `restore` uses none.
- **Languages:** the skill and the panel are in Portuguese; the documentation is in English ([README.pt-BR.md](README.pt-BR.md) is the Portuguese counterpart).
- **Scope:** one repository per board, local refs only. `origin` is never touched.

## Install

```text
/plugin marketplace add dvwinck/capybara-toolbox
/plugin install tidy-board@capybara-toolbox
```

Or copy the skill without the plugin system: `./install.sh tidy-board` from a clone.

## How it works

1. **`scan`** reads the repository (no fetch, no network, read-only) and writes an [ar-board](../ar-board) batch plus a `scan.json` sidecar into `.tidy-board/<batch>/`.
2. **The panel** (a generated copy of the ar-board engine, `capy_board.py`) shows one card per item. `A` = Apagar, `R` = Manter, `M` = Depois. Items that are not provably merged need a **second `A`** to confirm.
3. **`apply`** refuses to run unless the board was concluded, then re-verifies every approved item right before deleting it and writes `applied.json`.
4. **`restore`** brings back what was deleted by mistake.

Ask Claude *"clean up my stale branches"* or call `/tidy-board:tidy-board`; the skill drives these steps. Or run the tool yourself:

```bash
S=plugins/tidy-board/skills/tidy-board/scripts
python3 -I $S/tidy_board.py scan            # writes .tidy-board/<batch>/
python3 -I $S/capy_board.py serve .tidy-board/<batch> --open
python3 -I $S/tidy_board.py apply .tidy-board/<batch> --dry-run
python3 -I $S/tidy_board.py apply .tidy-board/<batch>
```

## Proof levels

| Level | Criterion | Treatment |
| --- | --- | --- |
| **P1** | The tip is an ancestor of the base (`git merge-base --is-ancestor`). | Safe. Covered by the group card. |
| **P2** | `gh` reports a merged PR whose head sha equals the branch tip. | Safe. Covered by the group card. |
| **P3** | Every patch of the branch is already in the base (cherry-pick, rebase), or the branch's whole diff equals one recent base commit's diff (a squash). The comparison looks at the last 500 base commits. | Probable. Second `A` and a backup ref. |
| **P4** | Anything else: the commits exist nowhere else. Stashes are always P4. | Alert, second `A` and a backup ref. |

A false negative is safe (an item stays P4 and is protected). The dangerous error is a false positive, which is why P3 never joins a bulk action and always gets a backup. "Upstream is gone" is shown as a hint but never raises the level: a remote branch can be deleted without being merged. Without `gh` the highest level is P1.

The base is `--base`, else the branch `origin/HEAD` points to, else the first of `main`, `master`, `base`, `trunk`. A branch counts as merged if it is an ancestor of the local base or of `origin/<base>`.

## The group card

The first card (`G`) says "delete the N items proved as merged" and lists them. It applies to every P1/P2 item **without a decision of its own**: a Manter or Depois on an item always beats the group, and P3, P4 and stashes ignore it entirely. An item with no decision is kept.

## What is never offered

The base branch, the current branch, any branch checked out in a worktree (the worktree is the card), and any worktree with tracked changes or untracked files (deleting it would lose work with no sha to recover). They are listed in the first card as **Nao tocar**, with the reason.

A clean worktree that holds files git ignores (a `.env`, `node_modules/`) **is** offered, but its card lists them, asks for a second `A` and keeps it out of the group card: removing the folder deletes them, they are in no commit and they get no backup.

## What `apply` re-checks

Per item, at deletion time (the scan is only a photograph):

- **Branch:** it still exists, its tip is still the scanned sha, it is not the base and not checked out anywhere, and for P1 it is still merged. For P2 it asks `gh` again (once per run) that the merged PR still has this tip, unless the history now proves the branch merged; if `gh` is unavailable the item is skipped. Deleted with a conditional `git update-ref -d`, which git refuses if the branch moved since the check.
- **Worktree:** it still exists, is not locked, is clean (no tracked changes, no untracked files) and its HEAD is the scanned sha. Removed with `git worktree remove` **without `--force`**, then its branch if that branch is P1/P2. A worktree on unique work is removed but its branch stays.
- **Stash:** found again by its commit sha (never by `stash@{n}`, which shifts) and dropped.
- Before deleting a P3/P4 branch, a stash or a detached worktree, it creates `refs/tidy-board/backup/...` (and skips the item if it cannot).

An item that fails a check is **skipped with the reason**, never forced. Exit codes: `0` everything done, `1` something was skipped, `2` refused (board not concluded, decisions from another batch or round, invalid files).

## Recovery

`applied.json` records every item with its sha (and its backup ref). `tidy_board.py restore <dir> <ID>` recreates a branch, a stash or a detached worktree's head from its **backup ref** and releases the backup. Items proved as merged (P1, P2) have no backup, because their commits are in the base: `restore` refuses and prints the `git branch <name> <sha>` to run by hand. A removed worktree is never recreated; the command prints the `git worktree add` to run. Backup refs accumulate in the repository: delete one with `git update-ref -d <ref>` when you no longer need it.

## Files

| File | Written by | Holds |
| --- | --- | --- |
| `batch.json` | `scan` | the board (cards, labels, `confirm` on risky items) |
| `scan.json` | `scan` | what `apply` re-checks: kind, name, sha, proof, base, group, untouched list |
| `decisions.json` | the panel | your decisions |
| `applied.json` | `apply`, `restore` | what was deleted, skipped or restored, with sha and backup |

Add `.tidy-board/` to your `.gitignore`: the files name your branches and paths and are written with mode `0600`.

## Limits

- tidy-board runs `git` inside your repository. It ignores the repository's hooks, filesystem monitor and external diff programs, but like any git command it still trusts the rest of the repository's local config: do not run it on a repository you do not trust.
- Squash detection is a heuristic: a rebased or conflict-resolved squash usually lands in P4 (protected, just more tedious).
- The panel's counters count the group card as one item, and items the group covers show as "sem decisao" there. `apply --dry-run` lists exactly what would be deleted; the skill always shows it first.
- A branch whose PR was force-pushed after the merge no longer matches the PR's head and falls to P3 or P4.
- Remote branches, tags, several repositories per board and scheduled cleanup are out of scope.
- The panel's JavaScript is not covered by the unit tests; it was checked by hand in a browser (light theme).

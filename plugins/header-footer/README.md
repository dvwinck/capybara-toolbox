# header-footer

A **header line at the top of every Claude reply** (time, date, weekday, folder, repository, branch) and a **configurable status-line footer** (whether Claude is running, waiting or idle, session tokens, plan limits, clock, branch, model, context, cost), both driven by one config file and changed with one command.

- **Version:** see [CHANGELOG](CHANGELOG.md) · **Requires:** `python3` (standard library only); `git` for the branch and repository fields; `node` only for the optional `gsd` field.
- **Languages:** the skill is in English; the CLI messages and the header's weekday are English by default and pt-BR on request (`lang` in the config, `--lang`, or `CAPYBARA_LANG`); the footer is the same in both; the documentation is in English ([README.pt-BR.md](README.pt-BR.md) is the Portuguese counterpart).

## Why

Claude has no clock. Asked to stamp its replies, it guesses, and a guessed time is worse than none. Here a hook computes the line (time, branch and so on) and hands it to Claude with the instruction to copy it verbatim, so the header is either right or absent.

## Install

```text
/plugin marketplace add dvwinck/capybara-toolbox
/plugin install header-footer@capybara-toolbox
```

The plugin registers its hooks (the header and the `state` field) by itself. The footer needs one more step, because a plugin cannot set the status line: ask Claude *"turn the footer on"*, or run the script with `on footer` (see below).

Without the plugin system: `./install.sh header-footer` from a clone, then `wire-hooks` and `on footer`.

## Use

Ask Claude in plain language (*"put the branch in the header"*, *"remove the clock from the footer"*, *"why is the time not showing?"*), call `/header-footer:header-footer`, or run the script:

```bash
S=plugins/header-footer/skills/header-footer/scripts/header_footer.py
python3 -I $S status                          # config, wiring, preview, diagnosis
python3 -I $S on footer                       # point the status line at the footer (backs settings.json up)
python3 -I $S header-fields time,branch       # the list replaces the current one
python3 -I $S header-format "%H:%M:%S"        # strftime; add --date for the date field
python3 -I $S footer-fields model,branch,tokens,limits,clock
python3 -I $S fields                          # every field
```

| Header field | Shows |
| --- | --- |
| `time`, `date` | time and date, in the configured `strftime` formats |
| `weekday` | `Mon` … `Sun` (pt-BR `seg` … `dom`) |
| `dir`, `repo`, `branch` | current folder, git repository name, git branch |

| Footer field | Shows |
| --- | --- |
| `state` | `● running 3m` while Claude works (time since the prompt), `◐ waiting` while it waits for a permission or an answer, `○ idle` when it stops or you interrupt it (Esc, or a denied permission) |
| `tokens` | input and output tokens of the whole session, summed over the transcript |
| `limits` | the 5-hour and 7-day plan windows, with the time until each resets |
| `clock`, `model`, `dir`, `branch` | what the name says |
| `context`, `cost` | context window used, estimated session cost |
| `gsd` | the GSD status line, when GSD is installed |

The config is `header-footer.json` in the Claude config directory (`~/.claude`, or `CLAUDE_CONFIG_DIR`); see [the example](skills/header-footer/examples/header-footer.example.json). Field and format changes take effect at once; turning the footer on or off edits `settings.json` and may need a restart.

## How it touches your setup

- **`settings.json` only through the CLI**: a timestamped backup first (the five newest are kept), an atomic write that keeps the file mode and writes through a symlinked `settings.json`, and only its own entries. A status line from another tool is replaced only with `--replace`.
- **A stable copy**: the status line points to a copy of the script in the Claude config directory, because the plugin's own path changes with every update. After an update, `status` says when the copy is older; `on footer` refreshes it. The status line runs every 10 seconds (`refreshInterval`), so the `state` timer and the clock move while nothing else happens.
- **A stable interpreter**: `on footer` and `wire-hooks` write `python3` from your `PATH` when it is the interpreter running the command (Homebrew's versioned path disappears on upgrade), and `status` reports an interpreter that no longer exists.
- **No double header**: if an older header hook is still in `settings.json`, both run but only the first prints for a given prompt, and `status` tells you to remove the old one. `status` also says when the header is on but no hook runs it.

## Platforms

- **macOS and Linux**: supported. On macOS, `python3` and `git` need the Command Line Tools or Homebrew; without them the system stubs open an install dialog.
- **Windows**: the script writes UTF-8 whatever the console code page, and refuses time formats Windows cannot render (such as `%-H`). Claude Code runs hooks in Git Bash or PowerShell, where `python3` usually does not exist, so the plugin's own hooks may not run: install with `wire-hooks` and `on footer`, which write the absolute interpreter path with forward slashes.

## Limits

- The header is an instruction to Claude, not a rendered UI element: Claude copies the line at the top of its first reply of the turn. The hook makes the content exact; it cannot force the model to place it.
- The `state` field learns about an interrupt from the transcript, because Claude Code runs no hook on Esc or on a denied permission.
- The footer's token total is read from the transcript file, whose format is not a public contract; if it changes, the field shows nothing rather than a wrong number.

## Develop

```bash
python3 -m unittest discover -s tests      # temporary config directories; git for the branch tests
python3 tools/sync.py --check              # version, manifest, changelog
```

The script's `VERSION` is the single source of truth; after changing it run `python3 tools/sync.py` and `python3 ../../tools/marketplace.py`.

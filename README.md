<p align="center">
  <img src="assets/banner.svg" alt="Capybara Toolbox: calm, capable skills and plugins for Claude Code" width="100%">
</p>

<p align="center">
  <a href="https://github.com/dvwinck/capybara-toolbox/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/dvwinck/capybara-toolbox/actions/workflows/ci.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-6E9E5B.svg"></a>
  <img alt="Python: standard library only" src="https://img.shields.io/badge/python-stdlib%20only-C8553D.svg">
  <a href="README.pt-BR.md"><img alt="Leia em português" src="https://img.shields.io/badge/leia-portugu%C3%AAs-E8A33D.svg"></a>
</p>

# Capybara Toolbox

A small, carefully built collection of skills and plugins for [Claude Code](https://claude.com/claude-code). Every plugin is self-contained, dependency-free where it can be, tested, and installable with two commands from the plugin marketplace.

## What's inside

| Plugin | What it does | Changes |
| --- | --- | --- |
| [**ar-board**](plugins/ar-board) | A local approve/reject board. The agent proposes N options, you judge them one by one with the keyboard (`A` approve, `R` reject, `M` maybe) and leave comments; the agent then acts only on what you approved and remembers your preferences for the next rounds. | [CHANGELOG](plugins/ar-board/CHANGELOG.md) |

## Install

Inside Claude Code:

```text
/plugin marketplace add dvwinck/capybara-toolbox
/plugin install ar-board@capybara-toolbox
```

Restart Claude Code, then ask for a board in plain language, for example *"give me 10 improvements for this repo as an AR board"*. The skill is also available explicitly as `/ar-board:ar-board`.

<details>
<summary>Other ways to install</summary>

**From a local clone** (no GitHub access needed):

```bash
git clone https://github.com/dvwinck/capybara-toolbox.git
```

```text
/plugin marketplace add ./capybara-toolbox
/plugin install ar-board@capybara-toolbox
```

**Without the plugin system** — copy a plugin's skills into `~/.claude/skills`:

```bash
./install.sh --list            # available plugins
./install.sh ar-board          # install or upgrade
./install.sh ar-board --uninstall
```

**Single-file variant** — [`plugins/ar-board/dist/ar-board-single-file.SKILL.md`](plugins/ar-board/dist/ar-board-single-file.SKILL.md) is a self-contained `SKILL.md` with the server script embedded (it installs the script into `~/.claude/ar-board/` on first use), for surfaces that accept a lone `SKILL.md`. The plugin install above is the supported route.

> **Pick one route.** Installing through the marketplace *and* with `install.sh` leaves two copies of the same skill (`/ar-board:ar-board` and `/ar-board`). Uninstall one of them (`claude plugin uninstall ar-board@capybara-toolbox` or `./install.sh ar-board --uninstall`).

</details>

## Repository layout

```text
.
├── .claude-plugin/marketplace.json   # the catalog (name: capybara-toolbox)
├── plugins/
│   └── ar-board/                     # one self-contained plugin
│       ├── .claude-plugin/plugin.json
│       ├── skills/ar-board/          # SKILL.md, scripts/, examples/
│       ├── tests/  tools/  docs/  dist/
│       └── CHANGELOG.md
├── tools/marketplace.py              # keeps the catalog in sync with the plugins
├── tests/                            # catalog tests
├── assets/                           # logo and banner (SVG)
└── install.sh                        # manual installer
```

## Contributing

Issues and pull requests are welcome; start with [CONTRIBUTING.md](CONTRIBUTING.md). Security reports: [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE) © 2026 Diogo Winck

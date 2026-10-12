<p align="center">
  <img src="assets/icon.svg" alt="ar-board: a capybara holding an approve/reject card" width="140">
</p>

# ar-board

A local **approve/reject board** for [Claude Code](https://claude.com/claude-code). The agent proposes N options; you judge them one by one with the keyboard and say *why*; when you are done the agent reads your decisions straight from disk, acts only on what you approved and keeps your preferences for the next rounds.

- **Version:** see [CHANGELOG](CHANGELOG.md) · **Requires:** `python3` (standard library only, no `pip`, no Node, no network)
- **Languages:** the skill and the panel UI are in Portuguese; the documentation is in English ([reference](docs/reference.md)) and Portuguese ([guia completo](docs/pt-BR/guia-completo.md)).

## Install

```text
/plugin marketplace add dvwinck/capybara-toolbox
/plugin install ar-board@capybara-toolbox
```

Other routes (manual copy, claude.ai single-file skill): see the [repository README](../../README.md#install).

## Use

Ask in plain language — *"give me 10 architecture improvements as an AR board"* — or call `/ar-board:ar-board`. Claude then:

1. reads your past preferences (`.ar-board/preferences.md`) so it does not repeat what you rejected;
2. writes `.ar-board/<batch_id>/batch.json` and starts the panel on `127.0.0.1` (random port, per-run token);
3. waits while you judge the cards, then runs `summary` on your decisions;
4. acts **only on approved items**, asks you to confirm the preference rules it inferred, and can open a refinement round.

### Keyboard

| Key | Action |
| --- | --- |
| `A` / `R` / `M` | Approve / reject / maybe (press again to undo) |
| `S` | Skip to the next card (not a decision) |
| `C` / `Esc` | Focus the comment field / leave it |
| `←` / `→` | Previous / next card |

Decisions and comments autosave to `decisions.json`; **Concluir** tells the agent you are done. Holding a key down never decides in a burst.

## What it writes

```text
<your project>/.ar-board/
├── preferences.md          # accumulated taste, read on the next rounds
└── <batch_id>/
    ├── batch.json          # written by the agent
    ├── decisions.json      # written by the panel (private, mode 0600)
    └── decisions.r1.json   # archived earlier rounds
```

Add `.ar-board/` to `.gitignore`: comments may contain internal information.

## Documentation

- [Reference](docs/reference.md) — panel, CLI, HTTP API, `batch.json` validation, security model, limits, troubleshooting.
- [Guia completo (pt-BR)](docs/pt-BR/guia-completo.md)
- [Changelog](CHANGELOG.md)

## Development

```bash
python3 -m unittest discover -s plugins/ar-board/tests   # from the repository root
python3 plugins/ar-board/tools/sync.py                    # after changing the script: manifest + single-file variant
```

The script is `skills/ar-board/scripts/ar_board.py` and is the plugin's source of truth; see [CONTRIBUTING](../../CONTRIBUTING.md).

*Independent implementation inspired by the "AR board" idea shown in the video "Minha NOVA SKILL Favorita do Claude Code" (Maestros da IA); it uses no code or material from the original skill and has no affiliation with the channel.*

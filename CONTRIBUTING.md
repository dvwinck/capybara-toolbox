# Contributing to Capybara Toolbox

Thanks for helping. This repository is a Claude Code plugin marketplace; every plugin lives in its own self-contained directory under `plugins/`.

## Setup

Requirements: Python 3.9+ (standard library only) and git. Optional: the `claude` CLI to validate and install the marketplace for real.

```bash
git clone https://github.com/dvwinck/capybara-toolbox.git
cd capybara-toolbox
```

## Run the checks

```bash
python3 -m unittest discover -s tests                      # catalog tests
python3 -m unittest discover -s plugins/ar-board/tests     # ar-board suite
python3 tools/marketplace.py --check                       # catalog matches the plugins
python3 plugins/ar-board/tools/sync.py --check             # ar-board version, manifest, single-file variant
claude plugin validate .                                   # optional: manifests, with the real CLI
```

CI runs the same commands on every push and pull request.

## Working on a plugin

- The **script's `VERSION`** is the single source of truth for a plugin's version. After changing a plugin, run its sync tool (`python3 plugins/ar-board/tools/sync.py`) and then `python3 tools/marketplace.py`; they update the manifest, the generated files and the catalog. Never edit generated files by hand (`plugins/ar-board/dist/`).
- Bumping a version needs a matching `## [x.y.z]` entry in the plugin's `CHANGELOG.md` and the script's header comment; the sync tool reports what is missing.
- Write the failing test first, watch it fail, then fix. Keep the standard-library-only constraint.
- Behavior changes belong in the plugin's docs (`docs/reference.md`, and `docs/pt-BR/guia-completo.md` while it is maintained).

## Adding a plugin

1. Create `plugins/<name>/` with `.claude-plugin/plugin.json` (name, description, version, author, license) and `skills/<skill>/SKILL.md`.
2. Add an entry to `.claude-plugin/marketplace.json` (`"source": "./plugins/<name>"`), then run `python3 tools/marketplace.py`.
3. Give the plugin its own `README.md`, `CHANGELOG.md` and `tests/`, and extend `.github/workflows/ci.yml` with its test command.
4. List it in the root `README.md` table.

## Commits and pull requests

- Small, focused commits with imperative subjects (`fix: ...`, `feat: ...`, `docs: ...`, `test: ...`, `chore: ...`).
- Describe the behavior change and how you verified it. UI changes: say how you checked them in a browser (the suite does not execute the page's JavaScript).
- Do not commit secrets or machine-specific paths.

By contributing you agree that your contributions are licensed under the [MIT License](LICENSE) and that you follow the [Code of Conduct](CODE_OF_CONDUCT.md).

# publish-check

A read-only scan of a git repository, **working tree and full history**, for what should not become public: Claude conversation links, absolute home paths, e-mail addresses and your own list of internal names. Run it right before a repository, branch or pull request goes public.

- **Version:** see [CHANGELOG](CHANGELOG.md) · **Requires:** `python3` (standard library only) and `git`; no network.
- **Languages:** the skill is in English; the documentation is in English ([README.pt-BR.md](README.pt-BR.md) is the Portuguese counterpart).
- **Not a secret scanner.** Keys and tokens are out of scope on purpose; use a dedicated tool such as [gitleaks](https://github.com/gitleaks/gitleaks). gitleaks does not read commit messages or author fields, which is the gap this tool fills.

## Install

```text
/plugin marketplace add dvwinck/capybara-toolbox
/plugin install publish-check@capybara-toolbox
```

Or copy the skill without the plugin system: `./install.sh publish-check` from a clone.

## What it finds

| Category | Examples |
| --- | --- |
| `session-link` | `claude.ai/code/session_...`, `claude.ai/chat/...`, `claude.ai/share/...` |
| `home-path` | `/Users/<name>`, `/home/<name>`, `C:\Users\<name>` (placeholders and CI users such as `/home/runner` are ignored) |
| `email` | addresses in text, in author and in committer fields (`noreply` and `example.*` addresses are ignored) |
| `denylist` | any internal name you list, case-insensitive |

Where it looks: tracked and non-ignored files of the working tree, plus every ref except the stash: every commit message, author and committer, every file, branch and tag name, every added line of every patch (a merge commit is compared with its first parent, so what a merge itself changed is covered; files marked `binary` or `-diff` in `.gitattributes` are read as text) and annotated tags. Stash and reflog are not scanned (they are not pushed).

## Use

Ask Claude *"check this repo before I publish it"*, call `/publish-check:publish-check`, or run the script directly:

```bash
python3 -I plugins/publish-check/skills/publish-check/scripts/publish_check.py [PATH]
```

| Option | Meaning |
| --- | --- |
| `--json` | machine-readable report (`schema` 1) |
| `--since WHEN`, `--max-commits N` | limit the history scanned |
| `--denylist FILE` | internal names, one per line; keep this file **outside** the repository |
| `--config FILE` | config file (default: `.publish-check.json` in the repository, when present) |

Exit code: `0` clean, `1` findings, `2` error. On a shallow clone (for example a default CI checkout) the report warns that only part of the history was scanned; use `fetch-depth: 0` or `git fetch --unshallow`. Reported values are partly masked (`j***@acme.dev`, `/Users/***`), so the report does not leak what it finds.

### Accepting false positives

`.publish-check.json`:

```json
{
  "denylist": ["Internal-Project-Name"],
  "allow": ["0123456789abcdef"]
}
```

`allow` takes the `fingerprint` printed under each finding. A fingerprint covers category, kind of place, file (when there is one) and the value, but not the commit id: an address that is the author of every commit is accepted once, while a new value or a new file is a new finding. If the repository is public, do not commit a `denylist` (it would leak the list): use `--denylist` with a file outside the repository, or git-ignore `.publish-check.json`.

### Automating

- `examples/pre-push.sh`: a git `pre-push` hook (copy it yourself; nothing installs hooks for you).
- `examples/ci-step.yml`: a GitHub Actions step (`fetch-depth: 0` so the whole history is scanned).

## Limits

- In the working tree it reads text: binary files, and text files larger than 50 MB, are **not scanned** and the report counts them ("N files skipped"). In history, patches are read as text even for files marked binary.
- A limited scan says so: `--since`, `--max-commits`, shallow clones and partial clones are all reported (`limits`, `shallow`, `partial` in the JSON), so "clean" is never silently partial. Encoded or deliberately split values (base64, a name broken over two lines) are not detected.
- Submodule contents are not scanned (scan each submodule as its own repository); file names, branch names and tag names are.
- Patterns are heuristic: expect to accept a few false positives, and treat "clean" as "nothing found by these four checks", not as a guarantee.
- A `.publish-check.json` inside the scanned repository is trusted: a pull request can add `allow` entries that hide findings. The report always prints how many findings the allow list accepted; in CI, prefer `--config` pointing at a file you control.
- Scanning is read-only and hardened against hostile repositories, but it is not a sandbox. Every git call runs without optional locks, with `core.fsmonitor`, signature verification (`gpg.program`), lazy fetching of missing objects (`protocol.allow=never`, `GIT_NO_LAZY_FETCH`), replace refs and grafts all disabled, and diffs are read without external diff or textconv drivers. A repository's own config could otherwise make git run a program or reach the network. For a repository you do not trust at all, scan a fresh clone in a throwaway environment.
- If git fails on any step the scan stops with exit code 2 instead of reporting a partial "clean".

## When something is found

publish-check never rewrites history. For findings that are already in commits, follow [docs/remediation.md](docs/remediation.md): back up first, rewrite, verify, and mind that a rewrite changes every commit id after the first changed commit.

## Develop

```bash
python3 -m unittest discover -s tests      # temporary repositories with planted leaks; needs git
python3 tools/sync.py --check              # version, manifest, changelog
```

The script's `VERSION` is the single source of truth; after changing it run `python3 tools/sync.py` and `python3 ../../tools/marketplace.py`.

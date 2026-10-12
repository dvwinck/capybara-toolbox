#!/usr/bin/env python3
"""Keeps the ar-board plugin consistent from one source of truth: the script's VERSION.

It propagates the version into .claude-plugin/plugin.json, and generates
dist/ar-board-single-file.SKILL.md: a self-contained variant of the skill with the script
embedded, for surfaces that accept a lone SKILL.md (the plugin install is the supported
route). In that variant the bundled-script path is replaced by ~/.claude/ar-board/ar_board.py,
where the variant's step 0 installs the script. It also reports problems it cannot fix by
itself (missing CHANGELOG entry, stale header comment, missing markers).

Usage (from the plugin directory or anywhere):
  python3 tools/sync.py           # write whatever is out of sync
  python3 tools/sync.py --check   # only verify (exit 1 if anything differs or is wrong)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = "skills/ar-board"
SCRIPT = f"{SKILL_DIR}/scripts/ar_board.py"
SKILL = f"{SKILL_DIR}/SKILL.md"
PLUGIN = ".claude-plugin/plugin.json"
SINGLE = "dist/ar-board-single-file.SKILL.md"
CHANGELOG = "CHANGELOG.md"

INPUTS = [SCRIPT, SKILL, PLUGIN, CHANGELOG]
GENERATED = [PLUGIN, SINGLE]

LOCATE = r"(?s)<!-- ar-board:locate-script -->.*?<!-- /ar-board:locate-script -->\n"
BUNDLED = "${CLAUDE_SKILL_DIR}/scripts/ar_board.py"  # how the lean SKILL.md names the script
INSTALLED = "$HOME/.claude/ar-board/ar_board.py"  # where the single-file variant installs it
SINGLE_STEP0 = """### 0. Instalar o script (uma vez por máquina)

```bash
test -f "{installed}" && grep -q 'ar-board {version}' "{installed}" && echo OK || echo FALTA
```

Se faltar (ou a versão for anterior), crie com `mkdir -p ~/.claude/ar-board` e grave o conteúdo da seção **Script** no fim deste arquivo em `~/.claude/ar-board/ar_board.py` (cópia literal, sem alterar). Os comandos abaixo usam esse caminho. Requer apenas `python3` (stdlib).
"""


def read(root, rel):
    return (root / rel).read_text(encoding="utf-8")


def dump_json(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def sub_once(pattern, repl, text, what):
    """re.sub that requires exactly one match: a vanished anchor must not pass silently."""
    out, n = re.subn(pattern, repl, text)
    if n != 1:
        raise SystemExit(f"sync: anchor not found ({n} matches, expected 1): {what}")
    return out


def script_version(script):
    return re.search(r'^VERSION = "(\d+\.\d+\.\d+)"', script, re.M).group(1)


def build(root):
    """Return {relative path: expected content} for every generated file."""
    script = read(root, SCRIPT)
    version = script_version(script)

    plugin = json.loads(read(root, PLUGIN))
    plugin["version"] = version

    skill = read(root, SKILL)
    single = sub_once(LOCATE, lambda m: SINGLE_STEP0.format(version=version, installed=INSTALLED), skill,
                      "SKILL.md locate-script markers")
    if BUNDLED not in single:
        raise SystemExit(f"sync: {SKILL} no longer runs the script as {BUNDLED}")
    single = single.replace(BUNDLED, INSTALLED)
    single = single.rstrip("\n") + "\n\n## Script\n\nGrave este conteúdo, sem alterações, em `~/.claude/ar-board/ar_board.py`:\n\n```python\n" + script.rstrip("\n") + "\n```\n"

    return {PLUGIN: dump_json(plugin), SINGLE: single}


def problems(root):
    """Things the tool cannot fix by itself; each one is a message."""
    out = []
    script = read(root, SCRIPT)
    version = script_version(script)
    if not re.search(rf"^# ar-board {re.escape(version)} - ", script, re.M):
        out.append(f"{SCRIPT}: header comment must say 'ar-board {version}' (VERSION is {version})")
    if not re.search(rf"^## \[{re.escape(version)}\]", read(root, CHANGELOG), re.M):
        out.append(f"{CHANGELOG}: no '## [{version}]' entry")
    return out


def main(argv, root=ROOT):
    files = build(root)
    found = problems(root)
    stale = [rel for rel, text in files.items() if not (root / rel).exists() or read(root, rel) != text]
    if "--check" in argv:
        for rel in stale:
            print(f"out of sync: {rel}")
        for msg in found:
            print(f"problem: {msg}")
        return 1 if (stale or found) else 0
    for rel in stale:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(files[rel], encoding="utf-8")
        print(f"updated: {rel}")
    for msg in found:
        print(f"problem: {msg}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

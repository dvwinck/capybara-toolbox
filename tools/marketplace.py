#!/usr/bin/env python3
"""Keeps .claude-plugin/marketplace.json consistent with the plugins on disk.

For every catalog entry with a local source it checks that the plugin directory and its
.claude-plugin/plugin.json exist and agree on the name, and it syncs `version` and
`description` from plugin.json (the plugin is the source of truth). It also reports plugin
directories that are missing from the catalog.

Usage:
  python3 tools/marketplace.py           # write whatever is out of sync
  python3 tools/marketplace.py --check   # only verify (exit 1 on any difference or problem)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKET = ".claude-plugin/marketplace.json"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def build(root):
    """Return (expected marketplace.json text, list of problems)."""
    market = read_json(root / MARKET)
    problems = []
    listed = set()
    for entry in market.get("plugins", []):
        source = entry.get("source")
        if not isinstance(source, str) or not source.startswith("./"):
            problems.append(f"{entry.get('name')}: only local './...' sources are supported by this tool")
            continue
        pdir = root / source
        listed.add(pdir.resolve())
        manifest_path = pdir / ".claude-plugin" / "plugin.json"
        if not manifest_path.exists():
            problems.append(f"{entry['name']}: {source}/.claude-plugin/plugin.json not found")
            continue
        manifest = read_json(manifest_path)
        if manifest.get("name") != entry["name"]:
            problems.append(f"{entry['name']}: plugin.json name is '{manifest.get('name')}'")
        for key in ("version", "description"):
            if key in manifest:
                entry[key] = manifest[key]
    plugins_dir = root / "plugins"
    if plugins_dir.is_dir():
        for d in sorted(plugins_dir.iterdir()):
            if d.is_dir() and d.resolve() not in listed:
                problems.append(f"plugins/{d.name}: directory is not listed in {MARKET}")
    return dump_json(market), problems


def main(argv, root=ROOT):
    expected, problems = build(root)
    current = (root / MARKET).read_text(encoding="utf-8")
    drift = current != expected
    if "--check" in argv:
        if drift:
            print(f"out of sync: {MARKET}")
        for msg in problems:
            print(f"problem: {msg}")
        return 1 if (drift or problems) else 0
    if drift:
        (root / MARKET).write_text(expected, encoding="utf-8")
        print(f"updated: {MARKET}")
    for msg in problems:
        print(f"problem: {msg}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

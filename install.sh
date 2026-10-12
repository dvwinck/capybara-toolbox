#!/usr/bin/env bash
# Manual (non-marketplace) install of a Capybara Toolbox plugin's skills into ~/.claude/skills.
# Preferred route: the Claude Code marketplace (see README.md). Use this if you can't.
#
#   ./install.sh --list                 list available plugins
#   ./install.sh <plugin>               install or upgrade every skill of the plugin
#   ./install.sh <plugin> --uninstall   remove them
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGINS="$HERE/plugins"
SKILLS_HOME="$HOME/.claude/skills"

usage() { echo "usage: $0 --list | <plugin> [--uninstall]" >&2; exit 2; }
[ "$#" -ge 1 ] && [ "$#" -le 2 ] || usage

if [ "$1" = "--list" ]; then
  for d in "$PLUGINS"/*/; do [ -d "${d}skills" ] && basename "$d"; done
  exit 0
fi

PLUGIN="$1"
[ -d "$PLUGINS/$PLUGIN/skills" ] || { echo "unknown plugin '$PLUGIN' (try --list)" >&2; exit 1; }

case "${2:-}" in
  "" | --uninstall) ;;
  *) usage ;;
esac

installed=0
for src in "$PLUGINS/$PLUGIN"/skills/*/; do
  name="$(basename "$src")"
  if [ "${2:-}" = "--uninstall" ]; then
    rm -rf "$SKILLS_HOME/$name"
    echo "removed $SKILLS_HOME/$name"
    continue
  fi
  [ -f "${src}SKILL.md" ] || { echo "skipping $name: no SKILL.md" >&2; continue; }
  mkdir -p "$SKILLS_HOME"
  rm -rf "$SKILLS_HOME/$name"
  cp -R "${src%/}" "$SKILLS_HOME/$name"
  # bytecode caches from a local test run are not part of the skill
  find "$SKILLS_HOME/$name" \( -name __pycache__ -type d -prune -exec rm -rf {} + \) -o \( -name '*.pyc' -type f -exec rm -f {} + \)
  echo "installed $name -> $SKILLS_HOME/$name"
  installed=$((installed + 1))
done

if [ "${2:-}" != "--uninstall" ]; then
  [ "$installed" -gt 0 ] || { echo "nothing installed" >&2; exit 1; }
  echo "Restart Claude Code to load the skill(s)."
fi

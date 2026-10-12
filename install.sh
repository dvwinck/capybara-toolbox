#!/usr/bin/env bash
# Instala o ar-board: script em ~/.claude/ar-board e skill em ~/.claude/skills/ar-board
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
command -v python3 >/dev/null || { echo "python3 nao encontrado"; exit 1; }
mkdir -p "$HOME/.claude/ar-board" "$HOME/.claude/skills/ar-board"
cp "$HERE/scripts/ar_board.py" "$HOME/.claude/ar-board/ar_board.py"
cp "$HERE/SKILL.md" "$HOME/.claude/skills/ar-board/SKILL.md"
grep -q 'ar-board 1.0.2' "$HOME/.claude/ar-board/ar_board.py" || { echo "versao inesperada do script"; exit 1; }
T="$(mktemp -d)"; cp "$HERE/examples/batch.example.json" "$T/batch.json"
python3 -I "$HOME/.claude/ar-board/ar_board.py" check "$T"; rm -rf "$T"
echo "ar-board 1.0.2 instalado:"
echo "  script: $HOME/.claude/ar-board/ar_board.py"
echo "  skill : $HOME/.claude/skills/ar-board/SKILL.md"
echo "Use: /ar-board <tema>   (reinicie a sessao do Claude Code para a skill aparecer)"

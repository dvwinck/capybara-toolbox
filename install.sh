#!/usr/bin/env bash
# Instala o ar-board: script em ~/.claude/ar-board e skill em ~/.claude/skills/ar-board
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
command -v python3 >/dev/null || { echo "python3 nao encontrado"; exit 1; }

if command -v shasum >/dev/null; then SUM=(shasum -a 256 -c)
elif command -v sha256sum >/dev/null; then SUM=(sha256sum -c)
else SUM=(); echo "aviso: sem shasum/sha256sum, integridade do pacote nao conferida"; fi
if [ "${#SUM[@]}" -gt 0 ]; then
  (cd "$HERE" && "${SUM[@]}" CHECKSUMS.sha256 >/dev/null) \
    || { echo "CHECKSUMS.sha256 nao confere: pacote alterado ou corrompido"; exit 1; }
fi

mkdir -p "$HOME/.claude/ar-board" "$HOME/.claude/skills/ar-board"
cp "$HERE/scripts/ar_board.py" "$HOME/.claude/ar-board/ar_board.py"
cp "$HERE/SKILL.md" "$HOME/.claude/skills/ar-board/SKILL.md"
grep -q 'ar-board 1.0.3' "$HOME/.claude/ar-board/ar_board.py" || { echo "versao inesperada do script"; exit 1; }
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
cp "$HERE/examples/batch.example.json" "$T/batch.json"
python3 -I "$HOME/.claude/ar-board/ar_board.py" check "$T"
echo "ar-board 1.0.3 instalado:"
echo "  script: $HOME/.claude/ar-board/ar_board.py"
echo "  skill : $HOME/.claude/skills/ar-board/SKILL.md"
echo "Use: /ar-board <tema>   (reinicie a sessao do Claude Code para a skill aparecer)"

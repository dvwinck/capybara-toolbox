#!/usr/bin/env python3
"""Mantem o pacote coerente a partir de scripts/ar_board.py (fonte da verdade).

Embute o script no SKILL.md, propaga a versao (VERSION) para README/SKILL/install.sh,
regrava o hash do script no README e regenera CHECKSUMS.sha256.

Uso:
  python3 tools/sync.py           # grava o que estiver fora de sincronia
  python3 tools/sync.py --check   # so confere (exit 1 se algo divergir)
"""
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ["README.md", "SKILL.md", "install.sh", "scripts/ar_board.py", "examples/batch.example.json"]


def read(root, rel):
    return (root / rel).read_text(encoding="utf-8")


def build(root):
    """Devolve {caminho relativo: conteudo esperado} dos arquivos gerenciados."""
    script = read(root, "scripts/ar_board.py")
    version = re.search(r'^VERSION = "(\d+\.\d+\.\d+)"', script, re.M).group(1)
    digest = hashlib.sha256(script.encode("utf-8")).hexdigest()

    def bump(text):
        text = re.sub(r"ar-board \d+\.\d+\.\d+", f"ar-board {version}", text)
        return re.sub(r"ar-board-\d+\.\d+\.\d+\.zip", f"ar-board-{version}.zip", text)

    readme = bump(read(root, "README.md"))
    readme = re.sub(r"(\*\*Versão:\*\* )\d+\.\d+\.\d+", rf"\g<1>{version}", readme)
    readme = re.sub(
        r"(\*\*SHA-256 do script v)\d+\.\d+\.\d+(:\*\* `)[0-9a-f]{64}`",
        rf"\g<1>{version}\g<2>{digest}`",
        readme,
    )
    skill = bump(read(root, "SKILL.md"))
    skill = re.sub(
        r"(?s)(## Script\n.*?```python\n).*?(\n```\n)",
        lambda m: m.group(1) + script.rstrip("\n") + m.group(2),
        skill,
    )
    install = bump(read(root, "install.sh"))

    out = {"README.md": readme, "SKILL.md": skill, "install.sh": install}
    contents = {**out, "scripts/ar_board.py": script, "examples/batch.example.json": read(root, "examples/batch.example.json")}
    out["CHECKSUMS.sha256"] = "".join(
        f"{hashlib.sha256(contents[rel].encode('utf-8')).hexdigest()}  {rel}\n" for rel in DIST
    )
    return out


def main(argv, root=ROOT):
    files = build(root)
    stale = [rel for rel, text in files.items() if read(root, rel) != text]
    if "--check" in argv:
        for rel in stale:
            print(f"fora de sincronia: {rel}")
        return 1 if stale else 0
    for rel in stale:
        (root / rel).write_text(files[rel], encoding="utf-8")
        print(f"atualizado: {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

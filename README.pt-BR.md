<p align="center">
  <img src="assets/banner.svg" alt="Capybara Toolbox: skills e plugins calmos e competentes para o Claude Code" width="100%">
</p>

<p align="center">
  <a href="https://github.com/dvwinck/capybara-toolbox/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/dvwinck/capybara-toolbox/actions/workflows/ci.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="Licença: MIT" src="https://img.shields.io/badge/licen%C3%A7a-MIT-6E9E5B.svg"></a>
  <img alt="Python: somente biblioteca padrão" src="https://img.shields.io/badge/python-s%C3%B3%20stdlib-C8553D.svg">
  <a href="README.md"><img alt="Read in English" src="https://img.shields.io/badge/read%20in-english-E8A33D.svg"></a>
</p>

# Capybara Toolbox

Uma coleção pequena e cuidadosa de skills e plugins para o [Claude Code](https://claude.com/claude-code). Cada plugin é autocontido, testado, sem dependências quando possível e instalável com dois comandos pelo marketplace de plugins.

## O que tem aqui

| Plugin | O que faz | Mudanças |
| --- | --- | --- |
| [**ar-board**](plugins/ar-board/README.pt-BR.md) | Painel local de aprovar/rejeitar. O agente propõe N opções, você julga uma a uma com o teclado (`A` aprova, `R` rejeita, `M` talvez) e comenta; depois o agente age só sobre o que você aprovou e guarda suas preferências para as próximas rodadas. | [CHANGELOG](plugins/ar-board/CHANGELOG.md) |

## Instalação

Dentro do Claude Code:

```text
/plugin marketplace add dvwinck/capybara-toolbox
/plugin install ar-board@capybara-toolbox
```

Reinicie o Claude Code e peça um painel em linguagem natural, por exemplo *"me dê 10 melhorias para este repositório num AR board"*. A skill também pode ser chamada de forma explícita: `/ar-board:ar-board`.

<details>
<summary>Outras formas de instalar</summary>

**A partir de um clone local** (sem acesso ao GitHub):

```bash
git clone https://github.com/dvwinck/capybara-toolbox.git
```

```text
/plugin marketplace add ./capybara-toolbox
/plugin install ar-board@capybara-toolbox
```

**Sem o sistema de plugins** — copia as skills do plugin para `~/.claude/skills`:

```bash
./install.sh --list            # plugins disponíveis
./install.sh ar-board          # instala ou atualiza
./install.sh ar-board --uninstall
```

**Variante de arquivo único** — [`plugins/ar-board/dist/ar-board-single-file.SKILL.md`](plugins/ar-board/dist/ar-board-single-file.SKILL.md) é um `SKILL.md` autocontido, com o script do servidor embutido (ele instala o script em `~/.claude/ar-board/` no primeiro uso), para ambientes que aceitam um `SKILL.md` avulso. A instalação pelo plugin, acima, é a forma suportada.

> **Escolha uma forma só.** Instalar pelo marketplace *e* pelo `install.sh` deixa duas cópias da mesma skill (`/ar-board:ar-board` e `/ar-board`). Desinstale uma delas (`claude plugin uninstall ar-board@capybara-toolbox` ou `./install.sh ar-board --uninstall`).

</details>

## Estrutura do repositório

```text
.
├── .claude-plugin/marketplace.json   # o catálogo (nome: capybara-toolbox)
├── plugins/
│   └── ar-board/                     # um plugin autocontido
│       ├── .claude-plugin/plugin.json
│       ├── skills/ar-board/          # SKILL.md, scripts/, examples/
│       ├── tests/  tools/  docs/  dist/
│       └── CHANGELOG.md
├── tools/marketplace.py              # mantém o catálogo em sincronia com os plugins
├── tests/                            # testes do catálogo
├── assets/                           # logo e banner (SVG)
└── install.sh                        # instalador manual
```

## Contribuir e segurança

Veja [CONTRIBUTING.md](CONTRIBUTING.md) (em inglês) e [SECURITY.md](SECURITY.md). Licença: [MIT](LICENSE).

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
| [**ar-board**](plugins/ar-board/README.pt-BR.md) | Painel local de aprovar/rejeitar. O agente propõe N opções, você julga uma a uma com o teclado (`A` aprova, `R` rejeita, `M` talvez) e comenta; depois o agente age só sobre o que você aprovou e guarda suas preferências para as próximas rodadas. Os painéis podem usar palavras e cores próprias para as três escolhas (por exemplo Apagar / Manter / Depois) e pedir um segundo toque em cards arriscados. Inclui também o question-board, um formulário para uma rodada de perguntas independentes. | [CHANGELOG](plugins/ar-board/CHANGELOG.md) |
| [**publish-check**](plugins/publish-check/README.pt-BR.md) | Varredura somente leitura de um repositório git, árvore e histórico completo, atrás de links de conversa do Claude, caminhos da sua máquina, e-mails e nomes internos seus, para rodar logo antes de algo ficar público. Não é um scanner de segredos. | [CHANGELOG](plugins/publish-check/CHANGELOG.md) |
| [**tidy-board**](plugins/tidy-board/README.pt-BR.md) | Branches, worktrees e stashes obsoletos do git como cards em um painel local. Cada card mostra a prova de que já foi mesclado; você escolhe apagar, manter ou depois; um `apply` separado reconfere cada item aprovado antes de apagar, e o que existe em um lugar só ganha backup antes. | [CHANGELOG](plugins/tidy-board/CHANGELOG.md) |

## Instalação

Dentro do Claude Code:

```text
/plugin marketplace add dvwinck/capybara-toolbox
/plugin install ar-board@capybara-toolbox
/plugin install publish-check@capybara-toolbox
/plugin install tidy-board@capybara-toolbox
```

Instale só os plugins que quiser, reinicie o Claude Code e peça em linguagem natural ou chame a skill pelo nome:

| Plugin | Peça ao Claude | Ou chame |
| --- | --- | --- |
| ar-board | *"me dê 10 melhorias para este repositório num AR board"* | `/ar-board:ar-board`, `/ar-board:question-board` |
| publish-check | *"varre este repositório atrás de vazamentos antes de eu publicar"* | `/publish-check:publish-check` |
| tidy-board | *"limpa meus branches velhos"* | `/tidy-board:tidy-board` |

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
│   ├── ar-board/                     # cada plugin é autocontido
│   ├── publish-check/
│   └── tidy-board/                   # embute uma cópia gerada do motor do ar-board
│       ├── .claude-plugin/plugin.json
│       ├── skills/tidy-board/        # SKILL.md, scripts/, examples/
│       ├── tests/  tools/
│       └── CHANGELOG.md
├── tools/marketplace.py              # mantém o catálogo em sincronia com os plugins
├── tests/                            # testes do catálogo
├── assets/                           # logo e banner (SVG)
└── install.sh                        # instalador manual
```

## Contribuir e segurança

Veja [CONTRIBUTING.md](CONTRIBUTING.md) (em inglês) e [SECURITY.md](SECURITY.md). Licença: [MIT](LICENSE).

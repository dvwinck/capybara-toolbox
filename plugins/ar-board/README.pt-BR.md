<p align="center">
  <img src="assets/icon.svg" alt="ar-board: uma capivara segurando um cartão de aprovar/rejeitar" width="140">
</p>

# ar-board

**Painel local de aprovar/rejeitar** para o [Claude Code](https://claude.com/claude-code). O agente propõe N opções; você julga uma a uma com o teclado e diz *por quê*; ao terminar, o agente lê as decisões direto do disco, age só sobre o que foi aprovado e guarda suas preferências para as próximas rodadas.

- **Versão:** veja o [CHANGELOG](CHANGELOG.md) · **Requer:** `python3` (somente biblioteca padrão; sem `pip`, sem Node, sem rede)
- **Idiomas:** a skill está em inglês; o painel e as mensagens da linha de comando saem em inglês por padrão e em pt-BR quando pedido (`lang` no batch, `--lang` em todo comando, a variável de ambiente `CAPYBARA_LANG` ou o seletor EN/PT do painel); a documentação está em inglês ([reference](docs/reference.md)) e em português ([guia completo](docs/pt-BR/guia-completo.md)).

## Instalação

```text
/plugin marketplace add dvwinck/capybara-toolbox
/plugin install ar-board@capybara-toolbox
```

Outras formas (cópia manual com `install.sh`, variante autocontida de arquivo único): veja o [README do repositório](../../README.pt-BR.md). Use uma forma só: marketplace e `install.sh` juntos deixam duas cópias da skill.

## Uso

Peça em linguagem natural — *"me dê 10 melhorias de arquitetura num AR board"* — ou chame `/ar-board:ar-board`. O Claude então lê suas preferências anteriores, escreve o `batch.json`, sobe o painel em `127.0.0.1` (porta aleatória, token por execução), espera você julgar os cards, lê o `summary`, age **só nos aprovados**, pede para você confirmar as regras de preferência que inferiu e pode abrir uma rodada de refinamento.

### Teclado

| Tecla | Ação |
| --- | --- |
| `A` / `R` / `M` | Aprova / rejeita / talvez (apertar de novo desfaz) |
| `S` | Pula para o próximo card (não é decisão) |
| `C` / `Esc` | Foca o campo de comentário / sai dele |
| `←` / `→` | Card anterior / próximo |

Tudo é salvo sozinho em `decisions.json`; **Finish and notify the agent** (em pt-BR **Concluir e avisar o agente**) avisa o agente. Segurar uma tecla nunca decide em rajada.

## O que ele escreve

```text
<seu projeto>/.ar-board/
├── preferences.md          # gosto acumulado, lido nas próximas rodadas
└── <batch_id>/
    ├── batch.json          # escrito pelo agente
    ├── decisions.json      # escrito pelo painel (privado, modo 0600)
    └── decisions.r1.json   # rodadas anteriores arquivadas
```

Coloque `.ar-board/` no `.gitignore`: os comentários podem ter informação interna.

## Segunda skill: question-board

Quando o agente precisa de várias respostas independentes antes de continuar, ele pode reuni-las num formulário em vez de uma rodada longa no chat (`/ar-board:question-board`). Cada pergunta mostra o contexto e opções numeradas; você aperta `1`-`9`, escreve a sua própria resposta ("Outra resposta...") ou aperta `M` para pedir mais contexto. A opção recomendada leva uma estrela e o motivo, mas nunca vem selecionada. Uma tela de revisão lista todas as respostas antes de avisar o agente, e o que ficar sem resposta volta como pendente (o agente pergunta no chat; nunca assume a recomendada).

Use o ar-board para *julgar propostas* (A/R/M) e o question-board para *responder perguntas*. Os dois usam o mesmo motor e painel locais. Atualize as duas skills juntas.

## Documentação

- [Guia completo (pt-BR)](docs/pt-BR/guia-completo.md)
- [Reference (inglês)](docs/reference.md)
- [Changelog](CHANGELOG.md)

## Desenvolvimento

```bash
python3 -m unittest discover -s plugins/ar-board/tests   # na raiz do repositório
python3 plugins/ar-board/tools/sync.py                    # depois de mudar o script: manifesto + variante de arquivo único
```

O script é `skills/ar-board/scripts/ar_board.py` e é a fonte da verdade do plugin; veja o [CONTRIBUTING](../../CONTRIBUTING.md).

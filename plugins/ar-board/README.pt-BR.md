<p align="center">
  <img src="assets/icon.svg" alt="ar-board: uma capivara segurando um cartão de aprovar/rejeitar" width="140">
</p>

# ar-board

**Painel local de aprovar/rejeitar** para o [Claude Code](https://claude.com/claude-code). O agente propõe N opções; você julga uma a uma com o teclado e diz *por quê*; ao terminar, o agente lê as decisões direto do disco, age só sobre o que foi aprovado e guarda suas preferências para as próximas rodadas.

- **Versão:** veja o [CHANGELOG](CHANGELOG.md) · **Requer:** `python3` (somente biblioteca padrão; sem `pip`, sem Node, sem rede)

## Instalação

```text
/plugin marketplace add dvwinck/capybara-toolbox
/plugin install ar-board@capybara-toolbox
```

Outras formas (cópia manual, skill de arquivo único no claude.ai): veja o [README do repositório](../../README.pt-BR.md).

## Uso

Peça em linguagem natural — *"me dê 10 melhorias de arquitetura num AR board"* — ou chame `/ar-board:ar-board`. O Claude então lê suas preferências anteriores, escreve o `batch.json`, sobe o painel em `127.0.0.1` (porta aleatória, token por execução), espera você julgar os cards, lê o `summary`, age **só nos aprovados**, pede para você confirmar as regras de preferência que inferiu e pode abrir uma rodada de refinamento.

| Tecla | Ação |
| --- | --- |
| `A` / `R` / `M` | Aprova / rejeita / talvez (apertar de novo desfaz) |
| `S` | Pula para o próximo card (não é decisão) |
| `C` / `Esc` | Foca o campo de comentário / sai dele |
| `←` / `→` | Card anterior / próximo |

Tudo é salvo sozinho em `decisions.json`; **Concluir** avisa o agente. Segurar uma tecla nunca decide em rajada. Coloque `.ar-board/` no `.gitignore`: os comentários podem ter informação interna.

## Documentação

- [Guia completo (pt-BR)](docs/pt-BR/guia-completo.md)
- [Reference (inglês)](docs/reference.md)
- [Changelog](CHANGELOG.md)

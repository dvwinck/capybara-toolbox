# housekeeping

Ferramentas pequenas que mantêm um repositório e uma sessão de trabalho honestos. Um plugin, várias skills, acrescentadas uma por versão: o **doc-truth** confere se o que os documentos de um repositório dizem existe de verdade, o **handoff** escreve uma nota de fim de sessão com os fatos do git e as citações conferidos, e o **todo-sweep** faz a triagem de comentários `TODO` e `FIXME` num painel local. Tudo é somente leitura, sem rede, com a biblioteca padrão do Python e `git`.

- **Versão:** veja o [CHANGELOG](CHANGELOG.md) · **Requer:** `python3` (somente biblioteca padrão) e `git`.
- **Idiomas:** as skills estão em português; a documentação está em inglês e este arquivo é a versão em português ([README.md](README.md)).

## Instalação

```text
/plugin marketplace add dvwinck/capybara-toolbox
/plugin install housekeeping@capybara-toolbox
```

Ou copie as skills sem o sistema de plugins: `./install.sh housekeeping` a partir de um clone.

## Skills

### doc-truth

Lê todo `.md` rastreado pelo git e confere o que ele afirma contra o repositório. Peça ao Claude *"confere os docs"* ou chame `/housekeeping:doc-truth`, ou rode você mesmo:

```bash
S=plugins/housekeeping/skills/doc-truth/scripts
python3 -I $S/doc_truth.py            # este repositório
python3 -I $S/doc_truth.py --json     # para máquinas, com o campo schema
```

Saída `0` limpo, `1` com achados, `2` erro (não é repositório git, config inválida). Nunca escreve, nunca roda um comando citado num documento e não usa a rede.

| Categoria | O que confere |
| --- | --- |
| `path` | Um caminho citado entre crases ou em bloco de código existe na **árvore do git** (não só no seu disco, para o resultado ser o mesmo no CI). Marcadores (`<nome>`, `PATH`), URLs, flags, caminhos absolutos, diagramas de árvore e escolhas como `A/R/M` não são caminhos. |
| `link`, `anchor` | Um link relativo aponta para algo que existe, e uma `#âncora` bate com um título do alvo (regras de slug do GitHub: acentos mantidos, `-1` para repetidos, linhas com `#` dentro de bloco de código não são títulos). |
| `parity` | `<name>.md` e `<name>.pt-BR.md` têm a mesma sequência de níveis de título (os títulos são traduzidos, então o texto não é comparado), e todo `README.md` tem um `README.pt-BR.md`. |
| `version`, `plugins` | Uma versão escrita na mesma linha do nome de um plugin bate com o `plugin.json` dele, e os READMEs da raiz linkam todos os plugins do catálogo. |

A configuração é o `.doc-truth.json` na raiz do repositório (chave desconhecida é erro):

```json
{
  "exclude": ["docs/plans/**", "**/CHANGELOG.md"],
  "ignore_paths": [".ar-board/", "decisions.json"],
  "allow": []
}
```

- `exclude`: documentos que não são conferidos (históricos, gerados). Continuam valendo como alvo de link.
- `ignore_paths`: caminhos que não existem na árvore de propósito (criados em execução, ou escritos como abreviação). Um padrão sem `/` vale para o nome em qualquer pasta; com `/` no meio, parte da raiz, e o mesmo vale para um com `/` no início, que diz "só esta abreviação" (`/SKILL.md` cala uma citação escrita `SKILL.md`, nunca uma escrita com uma pasta na frente que não existe); `**` atravessa pastas e `*` não.
- `allow`: fingerprints de achados aceitos. O fingerprint é um hash da categoria, do documento e do valor, nunca da linha: uma edição acima de um achado aceito não o traz de volta.

É uma heurística: um caminho em texto corrido que é só um exemplo será reportado, e `ignore_paths` ou `allow` é como você diz isso.

### handoff

Uma nota de fim de sessão de onde uma sessão nova consegue continuar. Peça ao Claude *"faz o handoff"* ou chame `/housekeeping:handoff`, ou rode você mesmo:

```bash
S=plugins/housekeeping/skills/handoff/scripts
python3 -I $S/handoff.py collect                          # só os fatos do git
python3 -I $S/handoff.py write --draft draft.md           # confere as citações e grava .handoff/<data>-<hora>.md
python3 -I $S/handoff.py verify draft.md                  # confere as citações de qualquer nota, sem editá-la
python3 -I $S/handoff.py resume                           # a nota mais recente e o que mudou desde então
```

Os fatos do git (branch, ponta, commits a frente e atrás da base, arquivos modificados e novos, stashes, worktrees, os últimos commits) vêm do git, não da memória. O rascunho do agente tem quatro seções (`O que foi feito`, `Decisoes e por que`, `Proximos passos`, `O que falhou ou travou`) e as citações são **tipadas**: `` `commit:abc1234` ``, `` `branch:feat/x` `` e `` `file:caminho/do/f.py:42` ``. Só os trechos tipados são conferidos e uma crase sem tipo é texto. Uma citação que não existe é mantida e seguida de ` [nao verificado]`, uma vez; nada é removido do rascunho. A nota termina com um bloco de dados para máquinas (os fatos e as citações como eram), que é como o `resume` sabe o que mudou: a ponta de uma branch que andou, a contagem a frente/atrás que mudou, arquivos que estavam modificados e não estão mais, stashes, e cada citação de novo.

Saída `0` quando toda citação está verificada (e, no `resume`, nada mudou), `1` caso contrário, `2` em erro; `--json` tem o campo `schema`. O `.handoff/` não é acrescentado ao `.gitignore` por você: as notas podem citar caminhos internos, então mantenha-as fora do git. Retomar só acontece quando você pede; não há hook nem oferta automática.

### todo-sweep

Comentários `TODO` e `FIXME` como cards num painel local, do mais antigo ao mais novo. Peça ao Claude *"faz a triagem dos TODOs"* ou chame `/housekeeping:todo-sweep`, ou rode você mesmo:

```bash
S=plugins/housekeeping/skills/todo-sweep/scripts
python3 -I $S/todo_sweep.py scan                                  # acha, mede a idade e escreve .todo-sweep/<lote>/
python3 -I $S/capy_board.py serve .todo-sweep/<lote> --open       # o painel: A Resolver, R Descartar, M Manter
python3 -I $S/todo_sweep.py report .todo-sweep/<lote>             # report.md e report.json a partir das suas decisões
```

O `scan` procura, dentro dos comentários dos arquivos de texto rastreados (markdown, binários, arquivos maiores que 1 MB e links simbólicos ficam de fora), `TODO` e `FIXME` em maiúsculas, como palavra inteira: um comentário que começa a linha (`#`, `//`, `--`, `/*`, `*`, `;`) ou que segue código. É uma heurística: um `# TODO` dentro de uma string também conta. A idade vem do `git blame` da linha (horário do autor, ou seja, a idade da última mudança da linha: um reformat a zera); linhas não commitadas e o limite de um clone raso ficam sem idade e dizem o motivo, e o `--max-blame` (padrão 300) limita quantos são medidos. Os cards vão do mais antigo ao mais novo, 20 por lote (`--limit`).

A decisão só é registrada: o `report` exige um painel concluído na rodada atual e grava um relatório somente leitura, e **nenhum arquivo-fonte é editado**. Descartar e Manter também ficam lembrados em `.todo-sweep/ledger.json` por um hash do arquivo e do texto (nunca da linha), então o próximo scan oferece os próximos TODOs e não os mesmos; Resolver não é lembrado, então esse TODO continua na lista até sumir do código. O painel é uma cópia gerada, byte a byte, do motor do ar-board (`capy_board.py`), e a skill continua instalável sozinha.

## Segurança

Todas as ferramentas deste plugin deixam os seus arquivos rastreados em paz, nenhuma usa a rede e nenhuma roda um comando citado num documento. O handoff escreve só as suas notas, em `.handoff/`, e o todo-sweep só os seus lotes, relatórios e registro, em `.todo-sweep/` (mantenha as duas fora do git: podem citar caminhos internos e código, e uma pasta que seja link simbólico é recusada). Elas confiam na configuração do próprio git do repositório (o git a lê), então não as rode num repositório em que você não confia.

## Desenvolvimento

```bash
python3 -m unittest discover -s plugins/housekeeping/tests   # na raiz do repositório
python3 plugins/housekeeping/tools/sync.py                    # depois de mudar um script: o manifesto segue o VERSION
```

Cada script carrega o `VERSION` do plugin e um lançamento atualiza todos juntos; veja o [CONTRIBUTING](../../CONTRIBUTING.md).

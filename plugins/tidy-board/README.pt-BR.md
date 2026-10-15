# tidy-board

Limpa **branches, worktrees e stashes** obsoletos do git a partir de um painel local. Cada candidato é um card que mostra o quanto a ferramenta tem certeza de que ele terminou; você decide **Apagar**, **Manter** ou **Depois** com o teclado; um passo separado, o `apply`, reconfere cada item aprovado no momento em que o apaga. Nada é apagado sem a sua aprovação, e o que existe em um lugar só ganha um backup antes.

- **Versão:** veja o [CHANGELOG](CHANGELOG.md) · **Requer:** `python3` (somente biblioteca padrão) e `git`; o `gh` é opcional (prova PRs mergeados). `scan` e `apply` só usam a rede por meio do `gh`, somente leitura e apenas se ele estiver instalado (o `scan` para provar PRs mergeados, o `apply` para reconferir os itens P2); o `restore` não usa nenhuma.
- **Idiomas:** a skill está em inglês; o painel, o texto dos cards e as mensagens da linha de comando estão em português; a documentação principal está em inglês ([README.md](README.md)).
- **Escopo:** um repositório por painel, só refs locais. O `origin` nunca é tocado.

## Instalação

```text
/plugin marketplace add dvwinck/capybara-toolbox
/plugin install tidy-board@capybara-toolbox
```

Ou copie a skill sem o sistema de plugins: `./install.sh tidy-board` a partir de um clone.

## Como funciona

1. **`scan`** lê o repositório (sem fetch, sem rede, somente leitura) e escreve um batch do [ar-board](../ar-board) e um `scan.json` em `.tidy-board/<lote>/`.
2. **O painel** (uma cópia gerada do engine do ar-board, `capy_board.py`) mostra um card por item. `A` = Apagar, `R` = Manter, `M` = Depois. Itens sem prova de merge pedem um **segundo `A`** para confirmar.
3. **`apply`** só roda se o painel foi concluído; reconfere cada item aprovado logo antes de apagar e escreve o `applied.json`.
4. **`restore`** traz de volta o que foi apagado por engano.

Peça ao Claude *"limpa minhas branches antigas"* ou chame `/tidy-board:tidy-board`; a skill conduz os passos. Ou rode a ferramenta você mesmo:

```bash
S=plugins/tidy-board/skills/tidy-board/scripts
python3 -I $S/tidy_board.py scan            # escreve .tidy-board/<lote>/
python3 -I $S/capy_board.py serve .tidy-board/<lote> --open
python3 -I $S/tidy_board.py apply .tidy-board/<lote> --dry-run
python3 -I $S/tidy_board.py apply .tidy-board/<lote>
```

## Níveis de prova

| Nível | Critério | Tratamento |
| --- | --- | --- |
| **P1** | A ponta é ancestral da base (`git merge-base --is-ancestor`). | Seguro. Coberto pelo card de grupo. |
| **P2** | O `gh` mostra um PR mergeado cuja ponta é a da branch. | Seguro. Coberto pelo card de grupo. |
| **P3** | Todos os patches da branch já estão na base (cherry-pick, rebase), ou o diff inteiro dela é igual ao de um commit recente da base (squash). A comparação olha os últimos 500 commits da base. | Provável. Segundo `A` e ref de backup. |
| **P4** | Qualquer outro caso: os commits não existem em outro lugar. Stashes são sempre P4. | Alerta, segundo `A` e ref de backup. |

Um falso negativo é seguro (o item fica P4 e protegido). O erro perigoso é o falso positivo, por isso o P3 nunca entra em ação em massa e sempre ganha backup. "Upstream apagado" aparece como dica, mas nunca sobe o nível: um remoto pode ser apagado sem merge. Sem o `gh`, o nível máximo é P1.

A base é `--base`, senão a branch para a qual `origin/HEAD` aponta, senão a primeira entre `main`, `master`, `base`, `trunk`. Uma branch conta como mesclada se for ancestral da base local ou de `origin/<base>`.

## O card de grupo

O primeiro card (`G`) diz "apagar os N itens provados como mergeados" e os lista. Vale para todo item P1/P2 **sem decisão própria**: um Manter ou Depois no item sempre vence o grupo, e P3, P4 e stashes o ignoram por completo. Item sem decisão fica como está.

## O que nunca é oferecido

A branch base, a branch atual, qualquer branch em uso por um worktree (o worktree é o card) e qualquer worktree com alterações rastreadas ou arquivos não rastreados (apagá-lo perderia trabalho sem sha para recuperar). Eles aparecem no primeiro card como **Nao tocar**, com o motivo.

Um worktree limpo que guarda arquivos ignorados pelo git (um `.env`, `node_modules/`) **é** oferecido, mas o card os lista, pede um segundo `A` e o deixa fora do card de grupo: remover a pasta apaga esses arquivos, que não estão em nenhum commit e não têm backup.

## O que o `apply` reconfere

Por item, na hora de apagar (o scan é só uma fotografia):

- **Branch:** ainda existe, a ponta continua o sha do scan, não é a base nem está em uso em algum worktree e, no P1, continua mesclada. No P2 ele pergunta ao `gh` de novo (uma vez por execução) se o PR mergeado ainda tem essa ponta, a menos que o histórico já prove a branch mesclada; se o `gh` não estiver disponível, o item é pulado. Apagada com um `git update-ref -d` condicional, que o git recusa se a branch se mexeu desde a checagem.
- **Worktree:** ainda existe, não está bloqueado, está limpo (sem alterações nem arquivos não rastreados) e o HEAD é o sha do scan. Removido com `git worktree remove` **sem `--force`**, e depois a branch dele se for P1/P2. Um worktree com trabalho único é removido, mas a branch fica.
- **Stash:** reencontrado pelo sha do commit (nunca por `stash@{n}`, que muda de posição) e descartado.
- Antes de apagar uma branch P3/P4, um stash ou um worktree solto, cria `refs/tidy-board/backup/...` (e pula o item se não conseguir).

Um item que falha numa checagem é **pulado com o motivo**, nunca forçado. Códigos de saída: `0` tudo feito, `1` algo foi pulado, `2` recusado (painel não concluído, decisões de outro lote ou rodada, arquivos inválidos).

## Recuperação

O `applied.json` registra cada item com o sha (e a ref de backup). `tidy_board.py restore <pasta> <ID>` recria uma branch, um stash ou a ponta de um worktree solto a partir da **ref de backup** e libera o backup. Itens provados como mesclados (P1, P2) não têm backup, porque seus commits estão na base: o `restore` recusa e mostra o `git branch <nome> <sha>` a rodar à mão. Um worktree removido nunca é recriado; o comando mostra o `git worktree add` a rodar. Os backups se acumulam no repositório: apague um com `git update-ref -d <ref>` quando não precisar mais.

## Arquivos

| Arquivo | Escrito por | Contém |
| --- | --- | --- |
| `batch.json` | `scan` | o painel (cards, rótulos, `confirm` nos itens de risco) |
| `scan.json` | `scan` | o que o `apply` reconfere: tipo, nome, sha, prova, base, grupo, lista de "nao tocar" |
| `decisions.json` | o painel | suas decisões |
| `applied.json` | `apply`, `restore` | o que foi apagado, pulado ou restaurado, com sha e backup |

Coloque `.tidy-board/` no `.gitignore`: os arquivos citam suas branches e caminhos e são gravados com modo `0600`.

## Limites

- O tidy-board roda o `git` dentro do seu repositório. Ele ignora os hooks, o monitor de sistema de arquivos e os programas de diff externo do repositório, mas, como qualquer comando git, ainda confia no resto da configuração local: não o rode em um repositório em que você não confia.
- A detecção de squash é uma heurística: um squash com rebase ou conflito resolvido costuma cair em P4 (protegido, só mais trabalhoso).
- Os contadores do painel contam o card de grupo como um item, e os itens que o grupo cobre aparecem como "sem decisao" ali. O `apply --dry-run` lista exatamente o que seria apagado; a skill sempre o mostra antes.
- Uma branch cujo PR sofreu force-push depois do merge deixa de bater com a ponta do PR e cai em P3 ou P4.
- Branches remotas, tags, vários repositórios por painel e limpeza agendada estão fora do escopo.
- O JavaScript do painel não é coberto pelos testes unitários; foi conferido à mão em um navegador (tema claro).

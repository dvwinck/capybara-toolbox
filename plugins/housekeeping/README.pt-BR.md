# housekeeping

Ferramentas pequenas que mantêm um repositório e uma sessão de trabalho honestos. Um plugin, várias skills, acrescentadas uma por versão: o **doc-truth** confere se o que os documentos de um repositório dizem existe de verdade; outras virão. Tudo é somente leitura, sem rede, com a biblioteca padrão do Python e `git`.

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
- `ignore_paths`: caminhos que não existem na árvore de propósito (criados em execução, ou escritos como abreviação). Um padrão sem `/` vale para o nome em qualquer pasta; com `/` no meio, parte da raiz; `**` atravessa pastas e `*` não.
- `allow`: fingerprints de achados aceitos. O fingerprint é um hash da categoria, do documento e do valor, nunca da linha: uma edição acima de um achado aceito não o traz de volta.

É uma heurística: um caminho em texto corrido que é só um exemplo será reportado, e `ignore_paths` ou `allow` é como você diz isso.

## Segurança

Todas as ferramentas deste plugin deixam os seus arquivos rastreados em paz, nenhuma usa a rede e nenhuma roda um comando citado num documento. Elas confiam na configuração do próprio git do repositório (o git a lê), então não as rode num repositório em que você não confia.

## Desenvolvimento

```bash
python3 -m unittest discover -s plugins/housekeeping/tests   # na raiz do repositório
python3 plugins/housekeeping/tools/sync.py                    # depois de mudar um script: o manifesto segue o VERSION
```

Cada script carrega o `VERSION` do plugin e um lançamento atualiza todos juntos; veja o [CONTRIBUTING](../../CONTRIBUTING.md).

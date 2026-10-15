---
name: doc-truth
description: Confere se o que os documentos de um repositório dizem existe - caminhos citados, links e âncoras, paridade entre README.md e README.pt-BR.md, e versões e lista de plugins contra os manifestos. Somente leitura, sem rede, saída 0/1/2. Use quando o usuário pedir para conferir, auditar ou validar a documentação - "os docs estão certos?", "tem link quebrado?", "o README cita arquivo que não existe?", "o README em português está igual ao em inglês?". Also use when the user says "doc-truth", "check the docs", "verify documentation paths and links" or "do the READMEs match". Gatilhos - /doc-truth ou /housekeeping:doc-truth.
---

# doc-truth (os documentos dizem a verdade?)

Lê todo `.md` rastreado pelo git e confere o que ele afirma contra o repositório: o caminho citado existe, o link e a âncora levam a algum lugar, o `README.md` e o `README.pt-BR.md` têm a mesma estrutura, a versão escrita ao lado do nome de um plugin é a do manifesto. É **somente leitura**: nunca altera o repositório, nunca roda um comando citado e não usa a rede. Requer `python3` (stdlib) e `git`.

Não confere links externos (`https://...`) nem se uma descrição está certa, só se o que ela aponta existe.

## Quando usar

Quando o usuário pedir para conferir a documentação: depois de editar READMEs ou `docs/`, antes de um lançamento, ou numa dúvida ("o README ainda cita esse arquivo?"). Não se ofereça sozinho: é uma ferramenta de pedido explícito.

## Fluxo

### 0. Localizar o script

O script acompanha esta skill: `${CLAUDE_SKILL_DIR}/scripts/doc_truth.py`. Use-o direto, sempre com `python3 -I`.

```bash
test -f "${CLAUDE_SKILL_DIR}/scripts/doc_truth.py" && echo OK || echo FALTA
```

Se `${CLAUDE_SKILL_DIR}` aparecer sem ser substituído, use no lugar dele o caminho mostrado como "Base directory for this skill" quando a skill foi carregada, escrito por extenso em cada comando.

### 1. Rodar

```bash
python3 -I "${CLAUDE_SKILL_DIR}/scripts/doc_truth.py" <repositório>
```

Opções: `--json` (campo `schema`) e `--config <arquivo>`. Se existir `.doc-truth.json` na raiz, ele é lido sozinho. Código de saída: `0` limpo, `1` com achados, `2` erro (não é repositório git, config inválida).

### 2. Apresentar

Mostre os achados por categoria, como o relatório os imprime, e diga quantos documentos foram conferidos:

- `path`: um caminho citado entre crases ou em bloco de código não existe **na árvore do git** (o que está só no seu disco não conta, para o resultado ser o mesmo no CI). Proponha corrigir o texto, ou, se for um arquivo criado em execução (`decisions.json`), pôr o nome em `ignore_paths`;
- `link` e `anchor`: o link aponta para algo que não existe, ou não há título para a âncora (regras de slug do GitHub);
- `parity`: `<name>.md` e `<name>.pt-BR.md` têm sequências de níveis de título diferentes, ou um `README.md` não tem o `README.pt-BR.md`;
- `version`: uma versão `X.Y.Z` na mesma linha do nome de um plugin não bate com o `plugin.json`; `plugins`: o catálogo tem um plugin que o README da raiz não linka.

Se o relatório disser "aceitos pela lista allow", diga quantos achados o `.doc-truth.json` já aceitou.

### 3. Corrigir só com pedido

A skill relata. Corrigir o texto de um documento é uma edição comum, que você só faz quando o usuário pedir, mostrando o que muda. **Não edite `.doc-truth.json`** (nem `allow`, nem `exclude`) sem o OK do usuário: aceitar um achado é decisão dele. Para aceitar, o usuário põe o `fingerprint` do achado em `allow`; ele não depende do número da linha.

## Configuração (`.doc-truth.json`)

```json
{
  "exclude": ["docs/plans/**", "**/CHANGELOG.md"],
  "ignore_paths": [".ar-board/", "decisions.json"],
  "allow": []
}
```

- `exclude`: documentos que não são conferidos (históricos, gerados). Eles continuam valendo como alvo de link.
- `ignore_paths`: caminhos que não existem na árvore de propósito (criados em execução). Um padrão sem `/` vale para o nome em qualquer pasta; com `/` no meio, parte da raiz, e o mesmo vale para um com `/` no início (`/SKILL.md` cala só a abreviação `SKILL.md`, não um caminho completo com pasta que não existe); `**` atravessa pastas e `*` não.
- `allow`: fingerprints de achados aceitos.
- Chave desconhecida é erro (saída 2).

## Regras

- Somente leitura, sem rede. Nunca rode um comando que um documento cita.
- Diagramas de árvore (linhas com `├──`) não são conferidos: são desenhos.
- Não rode em um repositório em que você não confia: o git lê a configuração local dele. Se `git` não existir no PATH, diga isso ao usuário em vez de tentar outra forma.

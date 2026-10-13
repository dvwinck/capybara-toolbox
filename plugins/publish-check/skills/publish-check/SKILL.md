---
name: publish-check
description: Varredura somente leitura de um repositório git (árvore e histórico completo) atrás de vazamentos antes de publicar - links de conversa do Claude, caminhos da sua máquina (/Users/<nome>), e-mails e nomes internos. Use quando o usuário for tornar algo público - criar repositório público, abrir PR para repositório público ou dar push em remoto público - ou pedir para checar vazamentos antes de publicar. Also use when the user says "publish-check", "check this repo before I publish", "scan history for leaks" or "is it safe to make this repo public". Gatilhos - /publish-check ou /publish-check:publish-check.
---

# publish-check (checagem antes de publicar)

Procura, na árvore de trabalho e em **todo o histórico git**, o que não deveria ficar público: links de conversa do Claude (`claude.ai/code/session...`, `/chat/...`, `/share/...`), caminhos da máquina de alguém (`/Users/<nome>`, `/home/<nome>`, `C:\Users\<nome>`), e-mails (texto, autor e committer) e uma lista de nomes internos do dono. É **somente leitura**: nunca altera o repositório nem reescreve histórico. Requer `python3` (stdlib) e `git`.

Não procura segredos (chaves, tokens): para isso use um scanner de segredos, como o gitleaks. Diga isso ao usuário no relatório.

## Quando usar

Antes de tornar algo público: criar um repositório público, abrir PR para um repositório público ou dar push para um remoto público. **Ofereça** rodar a checagem e **nunca bloqueie**: a decisão de publicar é do usuário. Em repositórios privados que não vão ser publicados, não ofereça.

## Fluxo

### 0. Localizar o script

O script acompanha esta skill: `${CLAUDE_SKILL_DIR}/scripts/publish_check.py`. Use-o direto, sempre com `python3 -I`.

```bash
test -f "${CLAUDE_SKILL_DIR}/scripts/publish_check.py" && echo OK || echo FALTA
```

Se `${CLAUDE_SKILL_DIR}` aparecer sem ser substituído, use no lugar dele o caminho mostrado como "Base directory for this skill" quando a skill foi carregada, escrito por extenso em cada comando.

### 1. Confirmar que o repositório vai (ou já está) público

Se não estiver claro, pergunte. Se o `gh` existir, `gh repo view --json visibility -q .visibility` mostra a visibilidade de um repositório já no GitHub. Não presuma.

### 2. Rodar

```bash
python3 -I "${CLAUDE_SKILL_DIR}/scripts/publish_check.py" <repositório>
```

Opções úteis: `--json`, `--since <data>`, `--max-commits N` (repositórios grandes), `--denylist <arquivo>` (nomes internos, um por linha, **fora** do repositório) e `--config <arquivo>`. Se existir `.publish-check.json` na raiz, ele é lido sozinho: chaves `denylist` (nomes internos) e `allow` (fingerprints de achados aceitos).

Código de saída: `0` limpo, `1` com achados, `2` erro (não é repositório git, config inválida, `git` ausente).

### 3. Apresentar

Mostre os achados agrupados por categoria, como o relatório os imprime: os valores já vêm parcialmente mascarados (`j***@dominio.dev`, `/Users/***`); **não** reproduza o valor completo em outro lugar. Diga quantos arquivos e commits foram varridos. Para cada categoria explique o que fazer, sem executar nada:

- achado só na **árvore**: editar o arquivo e commitar;
- achado no **histórico** (mensagem, autor, patch, tag): só some reescrevendo o histórico. Aponte `docs/remediation.md` (dentro do plugin), lembre de fazer backup antes e de que todos os SHAs mudam. **Nunca reescreva histórico por conta própria**, nem ofereça rodar a reescrita sem pedido explícito do usuário;
- se o relatório disser **skipped** (arquivos binários, ilegíveis ou muito grandes), esses arquivos **não foram verificados**: diga isso; se mostrar "accepted by the allow list", diga quantos achados foram aceitos e por quem (o `allow` do `.publish-check.json`);
- se o relatório avisar **shallow clone**, o resultado é parcial (só parte do histórico foi varrida): diga isso e sugira `git fetch --unshallow` antes de confiar em "limpo";
- achado que é falso positivo (um e-mail público de propósito, um caminho de exemplo): o usuário pode aceitá-lo adicionando o `fingerprint` ao `allow` de `.publish-check.json`. Só edite esse arquivo com o OK do usuário.

### 4. Fechar

Resuma: limpo, ou N achados em M categorias e o que o usuário decidiu. A decisão de publicar continua dele.

## Regras

- Somente leitura. Nunca rode comandos que reescrevem histórico (`filter-branch`, `filter-repo`) nem envie com força para o remoto.
- A lista de nomes internos (`denylist`) é sensível: se o repositório for público, mantenha-a em arquivo **fora** dele (`--denylist`), ou em `.publish-check.json` ignorado pelo git (`.gitignore` ou `.git/info/exclude`). Um `.publish-check.json` com `denylist` commitado em repositório público vaza a própria lista, e a ferramenta vai acusar isso.
- O relatório tem nomes de arquivos e mensagens de commit: trate-o como interno até o usuário decidir.
- Se `git` não existir no PATH, diga isso ao usuário em vez de tentar outra forma.

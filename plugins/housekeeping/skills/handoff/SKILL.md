---
name: handoff
description: Nota de fim de sessão para a próxima sessão retomar o trabalho, com os fatos do git coletados pela ferramenta (branch, commits a frente da base, arquivos modificados, stashes) e as citações conferidas antes de gravar - o que não existe fica marcado "[nao verificado]". Use quando o usuário pedir para encerrar a sessão deixando um handoff, escrever uma nota de passagem, ou retomar uma - "faz o handoff", "deixa uma nota pra próxima sessão", "retome o handoff". Also use when the user says "handoff", "write a handoff note", "resume the handoff" or "end of session notes". Gatilhos - /handoff ou /housekeeping:handoff.
---

# handoff (nota de fim de sessão com fatos conferidos)

Escreve uma nota para uma sessão nova, sem a sua memória, continuar o trabalho. Dois cuidados a distinguem de uma nota escrita de cabeça: os **fatos do git** (branch, ponta, commits a frente da base, arquivos modificados, stashes, worktrees) vêm do git, não de você; e toda **citação** que você escreve (commit, branch, arquivo) é conferida antes de a nota ser gravada, e a que não existe fica marcada `[nao verificado]`, sem apagar nada. Requer `python3` (stdlib) e `git`; não usa a rede.

## Quando usar

Quando o usuário pedir uma nota de passagem ou para retomar uma. Não se ofereça sozinho. Retomar só acontece sob pedido: nenhum hook, nenhuma oferta automática.

## Fluxo

### 0. Localizar o script

O script acompanha esta skill: `${CLAUDE_SKILL_DIR}/scripts/handoff.py`. Use-o direto, sempre com `python3 -I`.

```bash
test -f "${CLAUDE_SKILL_DIR}/scripts/handoff.py" && echo OK || echo FALTA
```

Se `${CLAUDE_SKILL_DIR}` aparecer sem ser substituído, use no lugar dele o caminho mostrado como "Base directory for this skill" quando a skill foi carregada, escrito por extenso em cada comando.

### 1. Escrever o rascunho

Escreva o rascunho com **estes quatro títulos**, nesta ordem, sem acentos (a ferramenta avisa se faltar algum, e nunca inventa o conteúdo):

```markdown
## O que foi feito
## Decisoes e por que
## Proximos passos
## O que falhou ou travou
```

O estado do git não entra no rascunho: a ferramenta o acrescenta no topo da nota. Em cada seção seja concreto: o que mudou, o que foi decidido e descartado (com o motivo, para ninguém refazer a discussão), a primeira coisa a fazer ao retomar, e as tentativas que não deram certo.

**Cite com tipo.** Só estas formas, entre crases, são conferidas; uma crase sem tipo é texto:

- `` `commit:abc1234` ``: um commit (7 a 40 caracteres hexadecimais);
- `` `branch:nome` ``: uma branch local ou remota (`origin/main`);
- `` `file:caminho/do/arquivo.py:42` ``: um arquivo relativo à raiz do repositório, com a linha opcional.

Cite só o que você viu existir nesta sessão. Se a nota não tiver nenhuma citação tipada, nada é conferido: diga isso ao usuário.

### 2. Gravar

```bash
python3 -I "${CLAUDE_SKILL_DIR}/scripts/handoff.py" write <repositório> --draft - <<'EOF'
## O que foi feito
...
EOF
```

A nota vai para `.handoff/AAAA-MM-DD-hhmmss.md` (privada, uma por execução, nunca sobrescreve outra). Código de saída: `0` tudo conferido, `1` alguma citação não verificada (a nota foi gravada com a marca), `2` erro. Leia o relatório: se houver citações não verificadas, diga quais e **proponha corrigir** (um novo `write` cria outra nota); se houver "aviso: falta a secao", diga qual.

`collect` mostra só os fatos do git; `verify <arquivo>` confere as citações de qualquer nota ou rascunho sem alterar o arquivo.

### 3. Retomar (só sob pedido)

```bash
python3 -I "${CLAUDE_SKILL_DIR}/scripts/handoff.py" resume <repositório>
```

Mostra a nota mais recente (`--file` escolhe outra), confere de novo cada citação e lista o que mudou desde que ela foi escrita: a ponta de uma branch que andou, a contagem a frente/atrás da base, arquivos modificados que sumiram ou apareceram, stashes. Saída `0` sem nada novo, `1` com mudança ou citação com problema. **Apresente as diferenças antes de agir** e não retome o plano da nota às cegas: o repositório pode ter andado.

## Regras

- `.handoff/` não deve ir para o git: as notas podem citar caminhos internos ou texto colado. A ferramenta não edita `.gitignore`; sugira a linha `.handoff/` e só a acrescente com o OK do usuário. Não publique nem commite uma nota.
- Não escreva na nota algo que você não verificou como se fosse fato: o que não for certo, diga que é suposição.
- Somente leitura no repositório: a ferramenta só escreve a nota, e recusa uma pasta `.handoff` que seja link simbólico. Não rode em um repositório em que você não confia: o git lê a configuração local dele. Se `git` não existir no PATH, diga isso ao usuário.

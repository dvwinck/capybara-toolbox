# ar-board — guia completo (pt-BR)

Painel local de **aprovar/rejeitar** para o Claude Code. O agente propõe N opções, você julga uma a uma com o teclado (e comenta o porquê), e ao dizer "terminei" o agente lê o resultado direto do disco, age só sobre o que foi aprovado e guarda suas preferências para as próximas rodadas.

- **Versão:** 1.1.0 (histórico no [CHANGELOG](../../CHANGELOG.md)).
- **Dependências:** `python3` (somente biblioteca padrão; o código usa apenas recursos de 3.7+). Sem `pip`, sem Node, sem rede externa.
- **Formato:** plugin do marketplace Capybara Toolbox, com uma skill (`SKILL.md`) que traz o servidor junto (`scripts/ar_board.py`).
- **Outros documentos:** a referência técnica em inglês está em [reference.md](../reference.md).

## Índice

1. [Para que serve](#1-para-que-serve)
2. [Arquitetura e fluxo](#2-arquitetura-e-fluxo)
3. [Instalação](#3-instalação)
4. [Anatomia do painel](#4-anatomia-do-painel)
5. [O card em detalhe](#5-o-card-em-detalhe)
6. [Decisões e estados](#6-decisões-e-estados)
7. [Teclado em detalhe](#7-teclado-em-detalhe)
8. [Comentários, nota do lote e autosave](#8-comentários-nota-do-lote-e-autosave)
9. [Concluir: o ciclo de vida do `finished`](#9-concluir-o-ciclo-de-vida-do-finished)
10. [Persistência, retomada e rodadas](#10-persistência-retomada-e-rodadas)
11. [Modo ao vivo × modo offline](#11-modo-ao-vivo--modo-offline)
12. [Exportação: Copiar e Baixar JSON](#12-exportação-copiar-e-baixar-json)
13. [Referência da linha de comando](#13-referência-da-linha-de-comando)
14. [API HTTP interna](#14-api-http-interna)
15. [Validação do `batch.json`](#15-validação-do-batchjson)
16. [Segurança](#16-segurança)
17. [O lado do agente (a skill)](#17-o-lado-do-agente-a-skill)
18. [Aprendizado de preferências](#18-aprendizado-de-preferências)
19. [Visual, responsividade e acessibilidade](#19-visual-responsividade-e-acessibilidade)
20. [Limites e comportamentos conhecidos](#20-limites-e-comportamentos-conhecidos)
21. [Testes e histórico de versões](#21-testes-e-histórico-de-versões)
22. [Solução de problemas](#22-solução-de-problemas)
23. [Estrutura de arquivos](#23-estrutura-de-arquivos)

Veja também os [Créditos](#créditos).

---

## 1. Para que serve

Use quando a decisão é humana por natureza (gosto, prioridade, risco) e existem várias alternativas independentes:

- ideias de features, temas de vídeo, nomes, variações visuais;
- melhorias de arquitetura de um agente ("10 aprimoramentos, aprova os que fizerem sentido");
- microtemplates de um site, copies, carrosséis;
- qualquer lote em que "aprovar tudo" seja arriscado e "aprovar nada" seja desperdício.

Não use quando existe uma única resposta correta, quando você já escolheu, ou quando prefere deixar o agente rodar sozinho até o fim. O AR board é o meio-termo entre os dois extremos: mais barato em tokens que um loop autônomo, e mais rápido e mais informado que aprovar cada passo no chat.

Por que funciona: ler e julgar um card estruturado (o que muda, por quê, risco) leva segundos, não exige entender toda a arquitetura, e o comentário que você deixa em cada item é o que o agente usa para se calibrar.

## 2. Arquitetura e fluxo

```
agente (Claude Code)                          você (navegador)
  │                                             │
  │ 1. lê .ar-board/preferences.md              │
  │ 2. escreve batch.json + check               │
  │ 3. serve (background) ──── URL + token ───► abre http://127.0.0.1:PORTA/?t=TOKEN
  │                                             │ 4. A / R / M, comentários, nota do lote
  │                                             │    └─► POST /api/* ─► decisions.json (a cada tecla)
  │ ◄──────────── "terminei" ───────────────────┘ 5. Concluir (opcional)
  │ 6. summary  (lê decisions.json)
  ▼
 7. age nos aprovados · extrai preferências · próxima rodada
```

Peças:

- **`ar_board.py`**: um único script Python (`skills/ar-board/scripts/ar_board.py`, dentro da skill) com servidor HTTP (`http.server`), validação, resumo e gerador de página offline. A página HTML/CSS/JS está embutida no próprio script.
- **`batch.json`**: escrito pelo agente; define título, rodada e os itens.
- **`decisions.json`**: escrito pelo servidor; é o "canal" entre painel e agente. Não há socket nem fila: o agente simplesmente lê o arquivo (por `summary` ou `wait`).
- **`preferences.md`**: memória acumulada de gosto, mantida pelo agente.

## 3. Instalação

### Pelo marketplace (recomendado)

O ar-board faz parte do marketplace **Capybara Toolbox**. No Claude Code:

```
/plugin marketplace add <caminho-ou-repositório>
/plugin install ar-board@capybara-toolbox
```

Reinicie o Claude Code. A skill fica com namespace do plugin: ela pode ser acionada por linguagem natural, e a forma explícita é `/ar-board:ar-board`.

### Alternativa sem marketplace

A partir de um clone do repositório:

```bash
./install.sh ar-board              # copia a pasta da skill para ~/.claude/skills/ar-board
./install.sh ar-board --uninstall  # remove
```

### Alternativa para o claude.ai (*Customize → Skills*)

Cole o conteúdo de `plugins/ar-board/dist/ar-board-single-file.SKILL.md`. É a mesma skill com o script embutido (arquivo gerado por `tools/sync.py`); no primeiro uso, ela grava o servidor em `~/.claude/ar-board/ar_board.py`. Esse é o único caso em que o script vive em `~/.claude/ar-board/`.

### Depois de instalar

- Sugestão para repositórios: adicione `.ar-board/` ao `.gitignore`, pois os comentários podem conter informação interna.
- Uso: peça em linguagem natural ou invoque a skill, por exemplo:

> /ar-board:ar-board me dê 10 melhorias de arquitetura para o agente motion-designer

## 4. Anatomia do painel

De cima para baixo:

| Região | O que mostra | Detalhes |
|---|---|---|
| **Cabeçalho** | Título do lote, subtítulo, e linha de contexto | A linha de contexto é `<subtitle> · Lote: <batch_id> · <N> itens · rodada <R>`. O `<title>` da aba do navegador é o título do lote. |
| **Badge de conexão** | `● ao vivo` (verde), `sem conexão — use Copiar` (âmbar) ou `arquivo local — use Copiar` (âmbar) | Muda sozinho conforme cada gravação no servidor dá certo ou falha (ver §11). |
| **Barra de atalhos** | Legenda das teclas, caixa "avançar ao decidir" e a linha de aviso | A linha de aviso (`#hint`) aparece por 4,5 s após cada avanço automático. |
| **Barra de progresso** | Fração de itens com decisão | Largura = (total − sem decisão) ÷ total. `Talvez` conta como decidido. |
| **Card** (esquerda) | Posição `n/N · id · tag`, selo da decisão atual, título, imagem opcional, campos, risco | Ver §5. |
| **Painel lateral** (direita) | Metadados, campo de comentário, botões Aprovar/Rejeitar/Talvez/Pular/Anterior/Próximo, chips numerados | O botão da decisão atual fica com contorno destacado. |
| **Chips** | Um botão numerado por item | Colorido pela decisão (verde/vermelho/âmbar; neutro sem decisão); o item atual tem anel de destaque; passar o mouse mostra o título; clicar salta para o item. |
| **Resultado** | Contadores, nota geral do lote, botões Concluir/Baixar JSON/Copiar/Limpar | Contadores: `✓ aprovados · ✗ rejeitados · ≈ talvez · sem decisão`. |
| **Banner de conclusão** | "Concluído. Volte ao Claude Code e diga "terminei"…" | Só aparece enquanto o lote está concluído (ver §9). |

Em telas estreitas (≤ 860 px) o painel lateral passa para baixo do card.

## 5. O card em detalhe

Cada item do `batch.json` vira um card com esta ordem de renderização:

1. **Pílula** `n/N · id · tag` (a `tag` é opcional) e, se houver decisão, o **selo** `Aprovado`/`Rejeitado`/`Talvez` ao lado.
2. **Título** (`title`), em destaque.
3. **Imagem** (`image`), se existir (ver abaixo).
4. **Caixa de campos**: cada entrada de `fields` vira uma linha `RÓTULO | texto`, na ordem em que foi escrita.
5. **Linha `RISCO`**, sempre por último dentro da caixa, se `risk` existir.
6. **Metadados** (`meta`) no topo do painel lateral, como pares chave/valor.

Detalhes de cada elemento:

- **`fields`**: lista livre de `{label, text}`. Convenção recomendada: `O que`, `Por quê`, e `Conceito` quando houver jargão. O rótulo é exibido em maiúsculas pequenas. Um item sem `fields` é válido (mostra só título e risco).
- **Texto**: tudo é escapado antes de ir para o HTML. Só duas coisas são interpretadas: `` `código` `` vira `<code>` e quebra de linha (`\n`) vira `<br>`. Não há negrito, links nem outras marcações; HTML digitado aparece como texto literal (testado com `<script>`, `<b>` e `<i>`).
- **`risk`**: `{level, text}`. O nível é normalizado (minúsculas, sem acento) e escolhe a cor: `baixo` verde, `médio`/`medio` âmbar, `alto` vermelho. Qualquer outro valor usa o estilo âmbar, mas o texto exibido é o original. A pílula mostra `nível — texto`.
- **`meta`**: objeto simples; cada par vira uma linha no painel lateral (ex.: `Área`, `Escala atual`, `Esforço`). Valores não-string são convertidos para texto.
- **`image`**: caminho **relativo à pasta do lote**, com extensão `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp` ou `.svg`. No modo ao vivo é servida pelo próprio servidor (ver §14); no `build` é embutida como `data:` URI (ver §11). Também aceita um `data:` URI diretamente.
- **`id`**: string única por lote (ex.: `A01`). É a chave em `decisions.json` e aparece na pílula e nos avisos.

Quantidade de itens: sem limite técnico; testado com 50. A recomendação da skill é 10 por padrão.

## 6. Decisões e estados

Cada item está em exatamente um destes estados:

| Estado | Valor em `decisions.json` | Cor | Como o agente trata |
|---|---|---|---|
| Aprovado | `"approved"` | verde | É executado. |
| Rejeitado | `"rejected"` | vermelho | Nunca executado; vira preferência negativa. |
| Talvez | `"maybe"` | âmbar | Não executado; vira pergunta ou entra na próxima rodada. |
| Sem decisão | (ausente) | neutro | Tratado como **não aprovado**. |

Regras de comportamento:

- **Alternância (toggle):** apertar a mesma decisão de novo **desfaz** (volta a "sem decisão"). Trocar de `A` para `R` simplesmente substitui.
- **Pular não é decisão:** `S` e o botão *Pular* só navegam para o próximo item, sem registrar nada. Não existe estado "pulado".
- **Comentário é independente da decisão:** um item pode ter comentário sem decisão (fica "sem decisão" com comentário) e vice-versa. Um item sem decisão e sem comentário não aparece em `decisions.json`.
- **Timestamp por item:** `at` é atualizado a cada alteração de decisão ou comentário daquele item.
- **Contadores e progresso** são recalculados a cada renderização, a partir do estado local.

## 7. Teclado em detalhe

| Tecla | Ação | Observações |
|---|---|---|
| `A` | Aprovar | Alterna (ver §6). Funciona com Shift (é insensível a maiúsculas). |
| `R` | Rejeitar | Idem. |
| `M` | Talvez | Idem. |
| `S` | Pular | Vai ao próximo item sem registrar decisão. |
| `C` | Focar o comentário | Impede o `c` de ser digitado no campo (`preventDefault`). |
| `Esc` | Sair do campo de texto | Tira o foco do textarea e devolve os atalhos. |
| `→` / `←` | Próximo / anterior | Param nas pontas (não dão a volta). |

Regras que evitam acidentes:

- **Campo de texto protege os atalhos:** dentro de um `<textarea>` (comentário ou nota do lote) nenhuma tecla é atalho, exceto `Esc`. Setas movem o cursor, não os itens. (Testado: digitar "arma" no campo não aprovou nada.)
- **Modificadores são ignorados:** qualquer combinação com `Ctrl`, `Cmd` ou `Alt` passa direto, então `Ctrl+R` (recarregar), `Ctrl+C` etc. continuam funcionando.
- **Foco em botões/checkbox não bloqueia os atalhos:** depois de clicar na caixa "avançar ao decidir", `A/R/M` continuam valendo. `Espaço`/`Enter` no botão focado o aciona normalmente.
- **Cliques fazem o mesmo que teclas:** os botões e os chips têm o mesmo efeito dos atalhos.
- **Tecla segurada não decide em rajada:** o auto-repeat de `A`, `R` e `M` é ignorado (uma pressão = uma decisão). Segurar `Enter` num botão focado também é ignorado (só a primeira pressão aciona o botão), o que evita repetir, por exemplo, **Concluir** ou **Limpar**. Setas e `S` continuam repetindo.

### Avanço automático

Por padrão, depois de uma decisão (`A`, `R` ou `M` que **defina** um estado) o painel passa sozinho ao próximo item e mostra o aviso `<Estado>: <id> — use ← para voltar e comentar` por 4,5 s. Detalhes:

- Não avança no último item, nem quando a tecla apenas **desfez** a decisão.
- A caixa **"avançar ao decidir"** desliga o comportamento; a preferência fica no `localStorage` do navegador (chave `ar-board:auto`) e vale para todos os lotes naquele navegador.
- Fluxo rápido com avanço ligado: `A`, `R`, `A`… e, quando quiser justificar, `←` `C` (digita) `Esc` `→`.
- Fluxo de comentar antes de decidir: `C` (digita) `Esc` `R`.

## 8. Comentários, nota do lote e autosave

- **Comentário por item:** o campo do painel lateral pertence ao item exibido. Vale para qualquer decisão (inclusive nenhuma). Limite de **5.000 caracteres** (o servidor corta o excedente).
- **Nota geral do lote** (`batch_note`): campo na seção Resultado, para observações sobre o lote inteiro. Mesmo limite.
- **Autosave com debounce de 350 ms:** cada digitação reinicia um temporizador por campo; o envio ocorre 350 ms após a última tecla. Existe um temporizador independente por item, então trocar de item no meio da digitação não perde nada.
- **Descarga imediata (flush)** dos envios pendentes quando: a aba fica oculta (`visibilitychange`), a página é fechada ou recarregada (`pagehide`, com `fetch keepalive`), ou você clica em **Concluir**. Isso elimina a perda de texto digitado nos últimos 350 ms.
- **Ordem garantida no Concluir:** primeiro todos os envios pendentes, depois a gravação de "concluído".
- **Se o servidor cair:** o badge vira `sem conexão — use Copiar`, o estado continua no navegador (e é guardado em `localStorage` como segurança) e você pode usar **Copiar** para entregar o resultado no chat. Decisões e comentários feitos nesse intervalo **não** chegam ao `decisions.json`.
- **Comentário vazio** (só espaços) remove o comentário do item.

## 9. Concluir: o ciclo de vida do `finished`

`finished` é o sinal "terminei de julgar este lote". Quem o lê: `wait` (que só retorna quando for `true`) e `summary` (que mostra `Concluído: sim` ou `NÃO (parcial)`).

| Evento | Efeito em `finished` |
|---|---|
| Clicar **Concluir e avisar o agente** (e o servidor confirmar) | vira `true`; grava `finished_at` |
| Alterar decisão ou comentário de qualquer item (servidor) | volta a `false`; apaga `finished_at` |
| Digitar comentário (painel) | o banner de conclusão some na hora (sincronizado com o servidor) |
| Editar a nota geral do lote | **não** altera |
| **Limpar** | volta a `false`; apaga `finished_at` |
| Reiniciar o servidor na mesma rodada | volta a `false` (e `finished_at` é descartado); decisões, comentários e nota são mantidos, então é preciso clicar **Concluir** de novo |

Comportamento do botão **Concluir**:

1. Se houver itens sem decisão, pede confirmação: "N itens sem decisão. Concluir mesmo assim?".
2. Descarrega os envios pendentes (§8).
3. Grava a conclusão. O banner verde **só aparece depois da confirmação do servidor**; se a gravação falhar, aparece um alerta orientando a usar **Copiar**.
4. Com `--exit-on-finish`, o servidor encerra 0,6 s depois.

Comportamento do botão **Limpar** (pede confirmação):

1. Cancela os autosaves pendentes e **espera as requisições em andamento terminarem** antes de enviar o reset, para que um comentário atrasado não ressuscite o item depois da limpeza.
2. O servidor zera decisões, comentários e nota do lote, volta `finished` a `false` e remove `finished_at`.
3. O painel volta ao primeiro item.

Concluir é opcional: se você apenas disser "terminei" no chat, o agente roda `summary`, que acusa `NÃO (parcial)` e trata itens sem decisão como não aprovados.

## 10. Persistência, retomada e rodadas

### `decisions.json`

```json
{
  "batch_id": "arq-motion-2026-10-12",
  "round": 1,
  "started_at": "2026-10-12T09:59:32-0300",
  "updated_at": "2026-10-12T10:03:10-0300",
  "finished": true,
  "finished_at": "2026-10-12T10:03:10-0300",
  "batch_note": "evitar mudanças destrutivas",
  "items": {
    "A01": {"decision": "approved", "comment": "migrar histórico antes", "at": "2026-10-12T10:01:02-0300"},
    "A02": {"decision": "rejected", "comment": "já temos isso no CI", "at": "2026-10-12T10:01:20-0300"}
  }
}
```

- `items` é um mapa só com os itens que têm decisão e/ou comentário.
- **Escrita atômica:** o servidor grava em `decisions.tmp` e troca com `os.replace`, então leitores (como o `wait`) nunca veem arquivo pela metade. Toda escrita é serializada por um lock.
- `updated_at` muda a cada gravação; `started_at` é fixo na criação do estado.

### Retomada

Ao iniciar, o servidor lê `decisions.json` da pasta:

- mesmo `batch_id` **e** mesma `round` → **retoma** (decisões, comentários e nota voltam como estavam; `finished` volta a `false` e `finished_at` é descartado, então é preciso clicar **Concluir** de novo). Recarregar a página ou reiniciar o servidor não perde nenhum julgamento;
- `batch_id` ou `round` diferentes → o arquivo antigo é **arquivado** e começa um estado novo;
- arquivo ilegível/corrompido, JSON que não é um objeto, ou JSON válido com formato interno errado (`items` que não é objeto, entrada de item que não é objeto, `decision` desconhecida, `comment` ou `batch_note` que não são texto) → é tratado como ilegível e começa um estado novo (sobrescreve);
- `wait` e `summary` só consideram um `decisions.json` do mesmo `batch_id` e da mesma `round` do `batch.json`; se for de outro lote/rodada, ilegível, com formato interno inválido ou não for um objeto JSON, é ignorado e tudo conta como sem decisão. Isso impede agir sobre aprovações antigas enquanto o servidor da nova rodada ainda não subiu.

### Rodadas

Para refinar, o agente cria um novo `batch.json` com o **mesmo** `batch_id` e `"round": N+1`. Ao subir o servidor:

- o `decisions.json` anterior é movido para `decisions.r<N>.json`;
- se esse nome já existir, usa sufixo numérico: `decisions.r<N>.1.json`, `.2.json`… (nada é sobrescrito);
- a nova rodada começa vazia e a interface mostra `rodada N+1`.

### Pontos a saber

- **`batch.json` é lido uma vez, na partida.** Alterá-lo com o servidor no ar não muda o painel; reinicie o `serve`. Decisões de ids que deixaram de existir ficam no arquivo mas são ignoradas por `summary` e pelos contadores.
- **Duas abas abertas não se sincronizam:** cada aba carrega o estado ao abrir e grava por conta própria (vale a última gravação). Use uma aba por lote.
- Recarregar a aba traz de volta o estado salvo no servidor.
- Ao abrir (ou recarregar), o painel começa no primeiro item sem decisão.

## 11. Modo ao vivo × modo offline

| | **Ao vivo** (`serve`) | **Offline** (`build`) |
|---|---|---|
| Como abre | URL `http://127.0.0.1:PORTA/?t=TOKEN` | Arquivo `board.html` (autocontido) |
| Gravação | Cada ação vai ao servidor e para `decisions.json` | Só no navegador (`localStorage`) |
| Badge | `● ao vivo` / `sem conexão — use Copiar` | `arquivo local — use Copiar` |
| Botão Concluir | Visível | Oculto |
| Entrega ao agente | O agente lê `decisions.json` | Você clica em **Copiar** e cola `AR-BOARD-RESULT…` no chat |
| Imagens | Servidas por `/files/…` | Embutidas como `data:` URI se tiverem **menos de 2 MB**; maiores ou inválidas são omitidas sem aviso |
| Quando usar | Máquina local | Sessão em nuvem/remota (o navegador não alcança o `localhost` do agente), ou quando quiser decidir fora do terminal |

Detalhes do offline:

- O progresso é guardado em `localStorage` sob a chave `ar-board:<batch_id>:r<round>` e restaurado ao reabrir o arquivo no mesmo navegador (itens e nota do lote).
- Se o `localStorage` estiver indisponível (janela privada, bloqueio), tudo continua funcionando em memória; só não há restauração ao recarregar. Todo acesso a `localStorage` é protegido por `try/catch`.
- O agente trata o JSON colado como se fosse o `decisions.json` (ver formato em §12).

## 12. Exportação: Copiar e Baixar JSON

Disponíveis nos dois modos, para quando o servidor cair ou no fluxo offline.

**Copiar** coloca na área de transferência a linha `AR-BOARD-RESULT` seguida do JSON:

```
AR-BOARD-RESULT
{
  "batch_id": "arq-motion-2026-10-12",
  "round": 1,
  "finished": false,
  "batch_note": "…",
  "items": [
    {"id": "A01", "title": "…", "decision": "approved", "comment": "…"},
    {"id": "A02", "title": "…", "decision": null, "comment": ""}
  ]
}
```

- Diferente do `decisions.json`, aqui `items` é uma **lista com todos os itens**, `decision` é `null` quando não há decisão e `comment` é `""` quando não há comentário.
- Usa a API de área de transferência do navegador e, se ela falhar, um fallback com `execCommand('copy')`. O botão mostra "Copiado!" por 1,4 s.

**Baixar JSON** salva o mesmo objeto (sem a linha `AR-BOARD-RESULT`) como `ar-board-<batch_id>-r<round>.json`.

## 13. Referência da linha de comando

Todos os comandos recebem a pasta do lote (`.ar-board/<batch_id>`). Rode com `python3 -I` (modo isolado: ignora variáveis de ambiente e o diretório atual no `sys.path`).

```bash
S=<pasta base da skill>/scripts/ar_board.py
```

O script acompanha a skill: é o `skills/ar-board/scripts/ar_board.py` do plugin, chamado a partir da pasta base da skill (o caminho aparece como "Base directory for this skill" quando a skill é carregada). Só a variante de arquivo único usa `~/.claude/ar-board/ar_board.py`.

| Comando | Opções | Saída | Código de saída |
|---|---|---|---|
| `check DIR` | — | `ok: N itens, lote <id>, rodada <R>` | 0; `1` com a lista de erros se o `batch.json` for inválido |
| `serve DIR` | `--port N` (padrão 0 = porta livre aleatória), `--open`, `--exit-on-finish` | `AR-BOARD URL: …` e `AR-BOARD DECISOES: <caminho>` | 0 ao encerrar |
| `wait DIR` | `--timeout S` (0 = espera indefinidamente) | Resumo em Markdown quando concluído; `TIMEOUT: …` se estourar | 0 concluído; **2** timeout |
| `summary DIR` | `--json` | Resumo em Markdown ou JSON | 0 |
| `build DIR` | — | `AR-BOARD ARQUIVO: <caminho>/board.html` | 0 |

### `serve`

- Escuta **somente** em `127.0.0.1`. Gera um token aleatório por execução e cria `server.json` (`url`, `pid`, `started_at`; permissão `0600`).
- `--open` chama `webbrowser.open`; em ambiente sem navegador não faz nada (copie a URL impressa).
- Porta fixa (`--port N`) falha com erro se já estiver em uso.
- Encerramento limpo (remove `server.json`) com `Ctrl+C`, `SIGTERM` (o `kill <pid>` que a skill recomenda) ou `--exit-on-finish`. `SIGKILL` não permite limpeza e deixa um `server.json` obsoleto (inofensivo).
- Pensado para rodar em segundo plano (`run_in_background`) e imprimir a URL.
- A porta é aberta antes de qualquer arquivamento de rodada: porta ocupada aborta sem tocar nos arquivos.

### `wait`

Consulta `decisions.json` a cada 1 s e termina quando `finished` for `true`, imprimindo o mesmo resumo do `summary`. Ignora decisões de outro lote/rodada (ver §10). Em segundo plano, o término chega ao agente como notificação, funcionando como alternativa ao "terminei" digitado.

### `summary`

Lê o `decisions.json` da pasta (se não existir, trata tudo como sem decisão). Formato Markdown:

```
# AR board - <título> (lote <batch_id>, rodada <N>)
Concluido pelo usuario: sim            # ou: NAO (parcial)

## Aprovados (1)
- A01 - <título do item>
    comentario do usuario: 'migrar historico antes'

## Rejeitados (n)
## Talvez (n)
## Sem decisao (n)

## Nota geral do lote
<texto>
```

Os comentários saem como `repr` (aspas simples, quebras de linha como `\n`), o que preserva o texto exato. Com `--json`: `{batch_id, round, finished, batch_note, approved[], rejected[], maybe[], pending[]}`, e cada item é `{id, title, comment}`.

### `build`

Gera `board.html` na pasta do lote: mesma interface, `live=false`, token vazio, imagens embutidas (< 2 MB), estado inicial vazio.

## 14. API HTTP interna

Usada pela própria página; documentada para depuração. Toda requisição passa por duas verificações: cabeçalho `Host` precisa ser `127.0.0.1` ou `localhost`, e o token precisa bater (comparação em tempo constante). Falha → `403 {"error":"forbidden"}`.

| Método e caminho | Autenticação | Corpo | Resposta |
|---|---|---|---|
| `GET /` | `?t=TOKEN` | — | A página HTML do painel (com o lote e o estado embutidos) |
| `GET /api/state` | `?t=` ou cabeçalho | — | Cópia do estado atual (o mesmo JSON do `decisions.json`) |
| `GET /files/<caminho>` | `?t=TOKEN` | — | Imagem do lote; `404` fora da pasta, com extensão não permitida ou inexistente |
| `POST /api/item` | cabeçalho `X-AR-Token` | `{id, decision?, comment?}` | `{"ok":true}` |
| `POST /api/note` | cabeçalho | `{text}` | `{"ok":true}` |
| `POST /api/finish` | cabeçalho | `{finished?: bool}` (padrão `true` se omitido) | `{"ok":true}` |
| `POST /api/reset` | cabeçalho | `{}` | `{"ok":true}` |

Detalhes:

- `decision` aceita `"approved"`, `"rejected"`, `"maybe"` ou `null` (limpa). Qualquer outro valor, de qualquer tipo → `400 {"error":"decisao invalida"}`.
- `id` que não seja uma string existente no lote (inclusive lista ou número) → `400 {"error":"id desconhecido"}`.
- `/api/finish`: `finished` precisa ser booleano; qualquer outro tipo → `400 {"error":"finished deve ser booleano"}`.
- `comment` precisa ser string (senão `400`); é cortado em 5.000 caracteres; vazio remove o comentário.
- Corpo acima de **1 MB** → `413`. JSON inválido → `400` com a mensagem do parser. Caminho desconhecido (autenticado) → `404`.
- Métodos não implementados (`HEAD`, `PUT`…) recebem o erro padrão do `http.server` (`501`).
- Uma requisição rejeitada (400) **não altera o estado**: a validação roda inteira antes de qualquer gravação.
- `Content-Length` negativo ou inválido → `400`. Token com caracteres não-ASCII → `403`.
- Respostas levam `Cache-Control: no-store`, `X-Content-Type-Options: nosniff` e `Referrer-Policy: no-referrer`. A página leva ainda uma CSP restritiva (§16).
- O servidor é multithread; escritas e leituras do estado são serializadas por lock. Em teste, 2.400 requisições concorrentes (16 threads, mistura de gravações e leituras) terminaram sem erro e com o JSON íntegro.

## 15. Validação do `batch.json`

`check` (e qualquer outro comando que carregue o lote) aplica estas regras e lista **todos** os erros de uma vez:

| Regra | Mensagem |
|---|---|
| A raiz deve ser um objeto | `a raiz do batch.json deve ser um objeto` |
| `batch_id` e `title`: strings não vazias | `campo '<k>' e obrigatorio (string)` |
| `items`: lista não vazia | `'items' deve ser uma lista nao vazia` |
| Cada item é um objeto | `item <i>: deve ser objeto` |
| `id`: string não vazia e única | `item <i>: 'id' obrigatorio` / `id duplicado '<id>'` |
| `title` do item: string não vazia | `item <i>: 'title' obrigatorio` |
| `fields`: lista de `{label, text}` com texto | `item <i>: 'fields' deve ser lista de {label, text} (texto)` |
| `round` (se presente): inteiro >= 1 | `campo 'round' deve ser inteiro >= 1` |
| `tag` / `image` (se presentes): string | `item <i>: '<k>' deve ser string` |
| `meta` (se presente): objeto | `item <i>: 'meta' deve ser objeto` |
| `risk` (se presente): objeto com `level`/`text` em texto | `item <i>: 'risk' deve ser objeto com 'level' e 'text' em texto` |

JSON malformado → `batch.json nao e JSON valido: <detalhe>`; arquivo ausente → `nao encontrei <caminho>`. `round` é opcional (padrão 1) e deve ser inteiro >= 1 (texto como `"2"` é rejeitado). `null` em `tag`, `image`, `meta` e `risk` conta como campo omitido (não é erro). Campos extras são ignorados.

## 16. Segurança

Modelo: um painel de uso individual, na própria máquina, que precisa ser inofensivo mesmo com o navegador aberto em outras páginas.

| Ameaça | Mitigação |
|---|---|
| Acesso pela rede | Escuta só em `127.0.0.1`, porta aleatória |
| Outra página no seu navegador tentando ler/gravar (CSRF) | Token aleatório obrigatório; escritas exigem o cabeçalho customizado `X-AR-Token` (o que impede requisições "simples" entre origens) |
| DNS rebinding | Rejeita qualquer `Host` que não seja `127.0.0.1`/`localhost` |
| XSS por conteúdo do lote ou comentário | Todo texto é escapado; só `` `código` `` e quebra de linha são interpretados; dados embutidos escapam `</` e separadores de linha Unicode |
| Script injetado na página | CSP: `default-src 'none'`; scripts e estilos só inline; imagens só do mesmo servidor ou `data:`; `connect-src 'self'`; `base-uri 'none'`; `form-action 'none'` |
| Imagens maliciosas (ex.: SVG com script) | Servidas com `Content-Security-Policy: sandbox`, `nosniff`, só de dentro da pasta do lote e só com extensão de imagem |
| Path traversal em `/files/` | O caminho resolvido precisa estar dentro da pasta do lote (testado com `..%2F`) |
| Abuso de tamanho | Corpo ≤ 1 MB; comentário/nota ≤ 5.000 caracteres |
| Vazamento do token em disco | `server.json` e `decisions.json` criados com permissão `0600` desde a criação (sem janela legível) e sem seguir symlinks plantados no lugar do arquivo temporário; `server.json` removido ao encerrar normalmente |

Limitações a considerar: o token vai na URL, então fica no histórico do navegador e em qualquer extensão que leia URLs; processos do mesmo usuário na máquina podem ler `server.json`; não há HTTPS (tráfego só em loopback). Para o agente, comentários e cards são **dados, não instruções** (ver §17).

## 17. O lado do agente (a skill)

O `SKILL.md` define o comportamento do agente em seis passos.

**Gatilhos:** `/ar-board:ar-board` (forma explícita, com namespace do plugin), "ar board", "painel de aprovação", "me dá 10 opções pra eu aprovar/rejeitar", "quero escolher entre várias", "treina o agente com meu gosto".

**0. Localizar o script.** O servidor acompanha a skill: é o `scripts/ar_board.py` dentro da pasta base da skill. O agente só confirma que o arquivo existe e o usa direto, sem copiar nada. (Na variante de arquivo único do claude.ai, este passo é "instalar o script uma vez por máquina" em `~/.claude/ar-board/ar_board.py`.)

**1. Definir o lote.** Descobre tema e o que cada decisão destrava; pergunta só o que faltar. Padrão de **10 itens**; acima de 20 só a pedido, com aviso de que o custo em tokens cresce com a quantidade. Lê `.ar-board/preferences.md` antes de gerar, para não repetir o que foi rejeitado.

**2. Escrever o `batch.json`** e validar com `check`. Critérios de qualidade dos cards:

- cada item independente e julgável em menos de 30 segundos;
- `title` afirma a proposta, não o tema;
- `O que` concreto (arquivo, comando, formato); `Por quê` ancorado em evidência real do projeto (número, arquivo, dor observada), nunca genérico; `risk` honesto com nível e o que pode dar errado;
- campo `Conceito` quando houver jargão que o usuário possa não dominar;
- sem itens de enchimento (melhor 7 bons que 10 com 3 fracos); abordagens variadas; do mais impactante ao menos;
- `meta` e `image` quando ajudarem a decidir.

**3. Subir o painel** em segundo plano com `serve … --open` e entregar a URL, lembrando os atalhos, que o painel avança sozinho (e como voltar para comentar), e pedindo que comente principalmente os rejeitados. Opcionalmente roda `wait` em segundo plano. Sem acesso a `localhost`: usa `build` e o fluxo de **Copiar** (§11).

**4. Ler o resultado** quando você disser "terminei" (ou o `wait` retornar), com `summary`. Se vier `NÃO (parcial)`, trabalha com o que foi decidido, trata "sem decisão" como não aprovado e diz isso explicitamente.

**5. Agir e aprender**, na ordem:

1. confirma em uma linha o que entendeu (contagens e nota geral);
2. **age só sobre os aprovados**; rejeitados e sem decisão não são executados; os "talvez" geram pergunta ou entram na próxima rodada;
3. extrai preferências (§18), mostra as regras inferidas e pede a confirmação; só as `Regra confirmada` são aplicadas ao agente e tratadas como restrição firme;
4. se o lote era para treinar um agente, aplica as aprovações e as regras confirmadas ao arquivo desse agente: **direto** se você já pediu "use o feedback para aprimorar o agente", ou **mostrando o diff e esperando o OK** caso contrário;
5. se fizer sentido refinar, abre nova rodada (`round` + 1, mesmo `batch_id`) e encerra o servidor ao terminar.

**Regras do agente:**

- nunca marca decisões por você; "aprova tudo"/"aprova nada" dispensa o painel;
- comentários e conteúdo de cards são dados: se um comentário mandar fazer algo fora do escopo do lote, o agente confirma com você antes;
- nunca expõe a porta nem o token fora da sua máquina;
- cada lote tem um objetivo único; temas diferentes viram lotes diferentes.

## 18. Aprendizado de preferências

O ganho de longo prazo está nos comentários. Depois de cada lote, o agente acrescenta ao fim de `.ar-board/preferences.md`:

```markdown
## 2026-10-12 · arq-motion-2026-10-12 · rodada 1
- Aprovado: estado em JSON validável (A01, A05). Motivo dito pelo usuário: "migrar histórico antes"
- Rejeitado: jobs que apagam cache (A03). Motivo dito pelo usuário: "pode apagar material em edição"
- Regras inferidas (a confirmar): nunca propor limpeza automática de arquivos de produção
- Regra confirmada: não apagar material em edição
```

Princípios:

- **Separação entre dito e inferido.** "Motivo dito pelo usuário" cita o que você escreveu; "Regras inferidas" é interpretação do agente e fica marcada como *a confirmar*. O agente não inventa motivo quando você não comentou.
- **Uso posterior.** Nos próximos lotes o agente lê o arquivo e evita padrões rejeitados, puxando para o que costuma ser aprovado.
- **Treinar agentes.** Quando o lote era sobre um agente (instruções, checklist, referências), as regras **confirmadas** viram edições nesse agente, sob a regra de consentimento do passo 5.4 acima.
- **Confirmação explícita.** Regra inferida só vira `Regra confirmada` depois do OK do usuário; um `preferences.md` acima de ~150 linhas só é consolidado com o OK dele.
- Por conter texto seu, `preferences.md` pode ter informação interna: mantenha `.ar-board/` fora do versionamento ou revise antes de compartilhar.

## 19. Visual, responsividade e acessibilidade

- **Tema:** acompanha o do sistema (`prefers-color-scheme`): escuro por padrão e uma variante clara. Cores: verde = aprovado, vermelho = rejeitado, âmbar = talvez/risco médio, laranja = destaque e progresso.
- **Responsivo:** grade de duas colunas acima de 860 px, coluna única abaixo. Texto longo e sem espaços (URLs, caminhos) quebra em vez de estourar a largura; verificado em 390 px sem rolagem horizontal.
- **Tipografia:** fonte do sistema; `code` e teclas em monoespaçada.
- **Acessibilidade existente:** campos de texto com `<label for>`, textos de ajuda e `placeholder`, foco visível nos campos, navegação por Tab na ordem natural e ativação de botões por Enter/Espaço (Enter segurado não repete; ver §7), rótulo textual em todos os botões, informação de estado nunca só por cor (o selo e os contadores têm texto).
- **Ainda não coberto:** regiões `aria-live` para os avisos (o aviso de avanço e o banner não são anunciados por leitores de tela) e verificação formal de contraste (auditoria WCAG completa).
- Mensagens e rótulos estão em português sem acentos dentro da página (por simplicidade de codificação); o conteúdo dos cards aceita qualquer Unicode (testado com acentos e caracteres CJK).

## 20. Limites e comportamentos conhecidos

- Uma pessoa por lote; sem sincronização entre abas ou entre pessoas (vale a última gravação).
- O `batch.json` não é recarregado com o servidor no ar.
- Porta fixa em uso gera erro de inicialização; prefira a porta automática.
- Em `--open` sem navegador padrão nada abre; copie a URL.
- Texto dos cards é só texto simples com `` `código` `` e quebras de linha (sem Markdown completo).
- Com mais de ~50 itens a barra de chips fica longa (funciona, mas a revisão item a item fica cansativa; prefira lotes menores e várias rodadas).
- Imagens maiores que 2 MB são ignoradas silenciosamente no `build`.
- Python: a suíte automatizada (`python3 -m unittest discover -s plugins/ar-board/tests`) roda em 3.15 no ambiente do autor; o código usa apenas recursos de 3.7+ e não depende de pacotes externos.
- O fluxo completo dentro de uma sessão real do Claude Code (agente lendo o resultado) foi exercitado por script e navegador, mas não observado de ponta a ponta numa sessão interativa.

## 21. Testes e histórico de versões

**Suíte automatizada** (`plugins/ar-board/tests/`, só `unittest`), a partir da raiz do repositório:

```bash
python3 -m unittest discover -s plugins/ar-board/tests -v
```

Cobre estado, retomada e rodadas (incluindo `wait`/`summary` × rodada antiga e `decisions.json` com formato interno inválido), atomicidade e tipos inválidos nos endpoints, validação do `batch.json`, permissões de arquivo, porta ocupada, as guardas do JavaScript embutido na página e a coerência do plugin (`tools/sync.py --check` e o `install.sh`). A suíte não executa JavaScript: o comportamento da interface no navegador (tecla segurada, Limpar, abertura no primeiro item pendente) é conferido à mão.

Historicamente (versões 1.0.x) a validação era uma bateria manual, feita em Chromium headless: fluxo completo com teclado, concorrência, limites, segurança, layout em 390 px e um ensaio de "agente novo". Ela foi substituída pela suíte acima e não é mais mantida.

**Histórico de versões:** veja o [CHANGELOG](../../CHANGELOG.md).

## 22. Solução de problemas

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| Página retorna `403` | URL sem `?t=TOKEN` ou token de uma execução anterior | Use a URL impressa pelo `serve` na execução atual |
| Badge "sem conexão — use Copiar" | O servidor foi encerrado | Reinicie o `serve` (o estado é retomado) ou use **Copiar** |
| `batch.json invalido` | Campo obrigatório ausente ou `id` duplicado | Rode `check` e corrija os itens listados |
| Navegador não abre sozinho | Ambiente sem navegador padrão | Abra manualmente a URL impressa |
| Comentário caiu no item seguinte | Avanço automático após A/R/M | Volte com `←` antes de `C`, ou desligue "avançar ao decidir" |
| `summary` diz "NÃO (parcial)" | Saiu sem clicar em Concluir | Itens sem decisão contam como não aprovados |
| `wait` não retorna | O lote não foi concluído, foi reaberto por uma edição ou o servidor foi reiniciado | Clique em **Concluir** de novo (editar decisão/comentário ou reiniciar o servidor zera o `finished`) |
| Rodada nova não aparece | `batch.json` alterado com o servidor no ar | Reinicie o `serve` |
| Existem `decisions.rN.json` | Arquivamento automático de rodadas anteriores | Esperado; guarde ou apague |
| Imagem do card não aparece (offline) | Arquivo > 2 MB, extensão não permitida ou fora da pasta do lote | Reduza a imagem ou use `data:` URI |
| `server.json` antigo na pasta | Servidor encerrado com `SIGKILL` | Pode apagar; é regenerado no próximo `serve` |

## 23. Estrutura de arquivos

```
plugins/ar-board/
├── .claude-plugin/plugin.json
├── skills/ar-board/
│   ├── SKILL.md
│   ├── scripts/ar_board.py          # servidor (stdlib)
│   └── examples/batch.example.json
├── dist/ar-board-single-file.SKILL.md   # gerado: skill com o script embutido
├── tests/  tools/sync.py  docs/
<projeto>/.ar-board/
├── preferences.md                    # preferências acumuladas, lidas nas próximas rodadas
└── <batch_id>/
    ├── batch.json                    # escrito pelo agente
    ├── decisions.json                # escrito pelo painel (rodada atual)
    ├── decisions.r1.json             # rodadas arquivadas (sufixos .1, .2… se houver colisão)
    ├── server.json                   # url/pid/token do servidor em execução (0600)
    ├── board.html                    # só no modo offline (build)
    └── *.png                         # imagens opcionais dos cards
```

`tools/sync.py` mantém o plugin coerente a partir da `VERSION` do script: propaga a versão para o `plugin.json` e gera a variante de arquivo único em `dist/`.

## Créditos

Inspirada na ideia do "AR board" mostrada no vídeo *Minha NOVA SKILL Favorita do Claude Code* (Maestros da IA). É uma implementação independente, escrita a partir do que o vídeo demonstra; não usa código nem material da skill original e não tem vínculo com o canal.

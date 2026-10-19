# header-footer

Uma **linha de header no topo de cada resposta do Claude** (hora, data, dia da semana, pasta, repositório, branch) e um **footer configurável na status line** (se o Claude está trabalhando, esperando ou parado, tokens da sessão, limites do plano, relógio, branch, modelo, contexto, custo), os dois guiados por um arquivo de configuração e alterados com um comando.

- **Versão:** veja o [CHANGELOG](CHANGELOG.md) · **Requer:** `python3` (só biblioteca padrão); `git` para os campos de branch e repositório; `node` só para o campo opcional `gsd`.
- **Idiomas:** a skill é em inglês; as mensagens da CLI são em português; a documentação é em inglês ([README.md](README.md)) e este é o equivalente em português.

## Por quê

O Claude não tem relógio. Quando pedem que ele marque a hora nas respostas, ele chuta, e uma hora chutada é pior que nenhuma. Aqui um hook calcula a linha (hora, branch etc.) e entrega ao Claude com a instrução de copiá-la literalmente, então o header ou está certo ou não aparece.

## Instalação

```text
/plugin marketplace add dvwinck/capybara-toolbox
/plugin install header-footer@capybara-toolbox
```

O plugin registra os hooks dele (o header e o campo `state`) sozinho. O footer precisa de mais um passo, porque plugin não consegue definir a status line: peça ao Claude *"liga o footer"* ou rode o script com `on footer` (veja abaixo).

Sem o sistema de plugins: `./install.sh header-footer` a partir de um clone, depois `wire-hooks` e `on footer`.

## Uso

Peça ao Claude em linguagem natural (*"põe a branch no header"*, *"tira o relógio do footer"*, *"por que a hora não aparece?"*), chame `/header-footer:header-footer` ou rode o script:

```bash
S=plugins/header-footer/skills/header-footer/scripts/header_footer.py
python3 -I $S status                          # config, ligação, preview, diagnóstico
python3 -I $S on footer                       # aponta a status line para o footer (faz backup do settings.json)
python3 -I $S header-fields time,branch       # a lista substitui a atual
python3 -I $S header-format "%H:%M:%S"        # strftime; acrescente --date para o campo de data
python3 -I $S footer-fields model,branch,tokens,limits,clock
python3 -I $S fields                          # todos os campos
```

| Campo do header | Mostra |
| --- | --- |
| `time`, `date` | hora e data, nos formatos `strftime` configurados |
| `weekday` | `seg` … `dom` |
| `dir`, `repo`, `branch` | pasta atual, nome do repositório git, branch git |

| Campo do footer | Mostra |
| --- | --- |
| `state` | `● running 3m` enquanto o Claude trabalha (tempo desde o prompt), `◐ waiting` enquanto espera uma permissão ou resposta sua, `○ idle` quando termina ou quando você interrompe (Esc, ou uma permissão negada) |
| `tokens` | tokens de entrada e saída da sessão inteira, somados a partir do transcript |
| `limits` | as janelas de 5 horas e 7 dias do plano, com o tempo até cada uma zerar |
| `clock`, `model`, `dir`, `branch` | o que o nome diz |
| `context`, `cost` | contexto usado, custo estimado da sessão |
| `gsd` | a status line do GSD, quando o GSD está instalado |

A configuração é o `header-footer.json` na pasta de configuração do Claude (`~/.claude`, ou `CLAUDE_CONFIG_DIR`); veja [o exemplo](skills/header-footer/examples/header-footer.example.json). Mudanças de campo e formato valem na hora; ligar ou desligar o footer edita o `settings.json` e pode exigir reiniciar.

## Como ele mexe na sua configuração

- **`settings.json` só pela CLI**: backup com data e hora antes (ficam os cinco mais recentes), escrita atômica que mantém a permissão do arquivo e grava através de um `settings.json` que seja symlink, e só nas entradas dele. A status line de outra ferramenta só é trocada com `--replace`.
- **Uma cópia estável**: a status line aponta para uma cópia do script na pasta de configuração do Claude, porque o caminho do plugin muda a cada atualização. Depois de atualizar, o `status` avisa quando a cópia ficou mais velha; `on footer` renova a cópia. A status line roda a cada 10 segundos (`refreshInterval`), então o tempo do `state` e o relógio andam mesmo sem outros eventos.
- **Um interpretador estável**: `on footer` e `wire-hooks` gravam o `python3` do seu `PATH` quando ele é o interpretador que roda o comando (o caminho versionado do Homebrew some num upgrade), e o `status` avisa quando o interpretador gravado não existe mais.
- **Sem header duplicado**: se um hook de header antigo ainda estiver no `settings.json`, os dois rodam mas só o primeiro imprime para cada prompt, e o `status` avisa para remover o antigo. O `status` também avisa quando o header está ligado mas nenhum hook o executa.

## Plataformas

- **macOS e Linux**: suportados. No macOS, `python3` e `git` precisam das Command Line Tools ou do Homebrew; sem eles, os atalhos do sistema abrem uma janela de instalação.
- **Windows**: o script escreve UTF-8 qualquer que seja o código de página do console e recusa formatos de hora que o Windows não renderiza (como `%-H`). O Claude Code roda os hooks no Git Bash ou no PowerShell, onde o `python3` geralmente não existe, então os hooks do próprio plugin podem não rodar: instale com `wire-hooks` e `on footer`, que gravam o caminho absoluto do interpretador com barras normais.

## Limites

- O header é uma instrução ao Claude, não um elemento de interface: o Claude copia a linha no topo da primeira resposta do turno. O hook garante o conteúdo exato; não consegue obrigar o modelo a colocá-lo.
- O campo `state` fica sabendo de uma interrupção pelo transcript, porque o Claude Code não roda hook no Esc nem numa permissão negada.
- O total de tokens do footer vem do arquivo de transcript, cujo formato não é um contrato público; se mudar, o campo fica vazio em vez de mostrar um número errado.

## Desenvolver

```bash
python3 -m unittest discover -s tests      # pastas de configuração temporárias; git para os testes de branch
python3 tools/sync.py --check              # versão, manifesto, changelog
```

O `VERSION` do script é a única fonte da verdade; depois de mudá-lo rode `python3 tools/sync.py` e `python3 ../../tools/marketplace.py`.

# publish-check

Varredura **somente leitura** de um repositório git, **árvore de trabalho e histórico completo**, atrás do que não deveria ficar público: links de conversa do Claude, caminhos absolutos da sua máquina, e-mails e a sua lista de nomes internos. Rode logo antes de um repositório, branch ou PR ficar público.

- **Versão:** veja o [CHANGELOG](CHANGELOG.md) · **Requer:** `python3` (somente biblioteca padrão) e `git`; sem rede.
- **Idiomas:** a skill está em inglês; a documentação principal é em inglês ([README.md](README.md)).
- **Não é um scanner de segredos.** Chaves e tokens ficam de fora de propósito; use uma ferramenta própria, como o [gitleaks](https://github.com/gitleaks/gitleaks). O gitleaks não lê mensagens de commit nem os campos de autor, que é a lacuna que esta ferramenta cobre.

## Instalação

```text
/plugin marketplace add dvwinck/capybara-toolbox
/plugin install publish-check@capybara-toolbox
```

Ou copie a skill sem o sistema de plugins: `./install.sh publish-check`, a partir de um clone.

## O que encontra

| Categoria | Exemplos |
| --- | --- |
| `session-link` | `claude.ai/code/session_...`, `claude.ai/chat/...`, `claude.ai/share/...` |
| `home-path` | `/Users/<nome>`, `/home/<nome>`, `C:\Users\<nome>` (placeholders e usuários de CI como `/home/runner` são ignorados) |
| `email` | endereços no texto, no autor e no committer (endereços `noreply` e `example.*` são ignorados) |
| `denylist` | qualquer nome interno da sua lista, sem diferenciar maiúsculas |

Onde procura: arquivos rastreados e não ignorados da árvore de trabalho, mais todas as refs exceto o stash: toda mensagem de commit, autor e committer, todo nome de arquivo, branch e tag, toda linha adicionada em todo patch (um commit de merge é comparado com o primeiro pai, então o que o próprio merge alterou é coberto; arquivos marcados `binary` ou `-diff` no `.gitattributes` são lidos como texto) e as tags anotadas. Stash e reflog não são varridos (não vão no push).

## Uso

Peça ao Claude *"cheque este repositório antes de eu publicar"*, chame `/publish-check:publish-check` ou rode o script direto:

```bash
python3 -I plugins/publish-check/skills/publish-check/scripts/publish_check.py [CAMINHO]
```

| Opção | Significado |
| --- | --- |
| `--json` | relatório para máquina (`schema` 1) |
| `--since QUANDO`, `--max-commits N` | limitam o histórico varrido |
| `--denylist ARQUIVO` | nomes internos, um por linha; mantenha este arquivo **fora** do repositório |
| `--config ARQUIVO` | arquivo de config (padrão: `.publish-check.json` no repositório, se existir) |

Código de saída: `0` limpo, `1` com achados, `2` erro. Em um clone raso (por exemplo o checkout padrão do CI) o relatório avisa que só parte do histórico foi varrida; use `fetch-depth: 0` ou `git fetch --unshallow`. Os valores aparecem parcialmente mascarados (`j***@acme.dev`, `/Users/***`), para o relatório não vazar o que encontra.

### Aceitar falsos positivos

`.publish-check.json`:

```json
{
  "denylist": ["Nome-Interno-do-Projeto"],
  "allow": ["0123456789abcdef"]
}
```

`allow` recebe o `fingerprint` impresso abaixo de cada achado. O fingerprint cobre categoria, tipo de local, arquivo (quando há) e o valor, mas não o id do commit: um endereço que é o autor de todos os commits é aceito uma vez, e um valor novo ou um arquivo novo é um achado novo. Se o repositório for público, não commite uma `denylist` (ela vazaria a lista): use `--denylist` com um arquivo fora do repositório, ou ignore o `.publish-check.json` no git.

### Automatizar

- `examples/pre-push.sh`: um hook `pre-push` do git (você copia; nada instala hooks por você).
- `examples/ci-step.yml`: um passo do GitHub Actions (`fetch-depth: 0` para varrer o histórico inteiro).

## Limites

- Na árvore de trabalho ele lê texto: arquivos binários e arquivos de texto maiores que 50 MB **não são varridos** e o relatório os conta ("N files skipped"). No histórico, os patches são lidos como texto mesmo para arquivos marcados como binários.
- Uma varredura limitada avisa: `--since`, `--max-commits`, clones rasos e clones parciais são todos informados (`limits`, `shallow`, `partial` no JSON), então "limpo" nunca fica parcial em silêncio. Valores codificados ou propositalmente quebrados (base64, um nome dividido em duas linhas) não são detectados.
- O conteúdo de submódulos não é varrido (varra cada submódulo como um repositório próprio); nomes de arquivos, branches e tags são varridos.
- Os padrões são heurísticos: espere aceitar alguns falsos positivos e trate "limpo" como "nada encontrado por estas quatro checagens", não como garantia.
- Um `.publish-check.json` dentro do repositório varrido é confiável por definição: um pull request pode adicionar entradas em `allow` que escondem achados. O relatório sempre mostra quantos achados a lista de aceitos absorveu; no CI, prefira `--config` apontando para um arquivo que você controla.
- A varredura é somente leitura e endurecida contra repositórios hostis, mas não é um sandbox. Todo comando git roda sem travas opcionais, com `core.fsmonitor`, verificação de assinatura (`gpg.program`), busca preguiçosa de objetos ausentes (`protocol.allow=never`, `GIT_NO_LAZY_FETCH`), replace refs e grafts desativados, e os diffs são lidos sem drivers de diff externo nem de textconv. A config do próprio repositório poderia, de outro modo, fazer o git executar um programa ou acessar a rede. Para um repositório em que você não confia, varra um clone novo em um ambiente descartável.
- Se o git falhar em qualquer etapa, a varredura para com código de saída 2, em vez de relatar um "limpo" parcial.

## Quando encontrar algo

O publish-check nunca reescreve histórico. Para achados que já estão em commits, siga [docs/remediation.md](docs/remediation.md) (em inglês): faça backup, reescreva, verifique, e lembre que a reescrita muda o id de todos os commits a partir do primeiro alterado.

## Desenvolvimento

```bash
python3 -m unittest discover -s tests      # repositórios temporários com vazamentos plantados; precisa de git
python3 tools/sync.py --check              # versão, manifesto, changelog
```

O `VERSION` do script é a única fonte da versão; depois de mudá-lo rode `python3 tools/sync.py` e `python3 ../../tools/marketplace.py`.

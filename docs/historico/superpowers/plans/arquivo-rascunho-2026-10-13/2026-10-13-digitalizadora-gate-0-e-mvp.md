# Digitalizadora — Gate 0 + MVP: plano de implementação

> **RASCUNHO NÃO REVISADO (2026-10-13).** Escrito por 5 agentes e conferido por um verificador estático. A revisão adversarial já foi feita, **mas nada dela foi aplicado a este texto**. Antes de executar qualquer tarefa, aplique as [mudanças de contrato pendentes](../2026-10-13-mudancas-de-contrato-pendentes.md) e os [achados da revisão](../2026-10-13-achados-da-revisao.md) (2 bloqueantes e 15 graves). O spec manda: onde este plano divergir dele, o plano está errado.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Para quem executa:** cada tarefa foi escrita para ser executada por alguém sem contexto prévio. Leia o spec antes de começar. **Nada neste plano foi executado ainda**, e a implementação só começa depois que você aprovar o spec e este plano.

**Objetivo:** validar a impressora (Gate 0) e entregar um app local em que um clique (ou a tecla Espaço) digitaliza uma página da mesa da HP DeskJet Ink Advantage 2874 pelo protocolo eSCL e salva um PDF ou um JPG, com nome automático, numa pasta escolhida.

**Arquitetura:** servidor FastAPI em `127.0.0.1` + página web local, iniciado pelo Terminal.app; cliente eSCL direto (`httpx`) atrás de uma porta `ScannerGateway`; o JPEG do scanner é o mestre e o PDF é montado com `img2pdf` sem recompressão; camadas controllers → services → domain ← repositories/infrastructure, com injeção por construtor numa raiz de composição.

**Tecnologias:** Python 3.12 (venv do projeto), FastAPI, uvicorn, httpx, python-zeroconf, Pillow, img2pdf, pikepdf; pytest + pytest-asyncio; ruff; HTML, CSS e JavaScript sem etapa de build.

**Spec:** [docs/superpowers/specs/2026-10-13-digitalizadora-design.md](../../specs/2026-10-13-digitalizadora-design.md). Os contratos da seção 6 do spec são a autoridade para nomes e assinaturas; se um passo deste plano divergir deles, o spec vence e o plano deve ser corrigido.

## Rastreabilidade com o seu pedido (md.md)

| Você pediu | Onde está no plano |
|---|---|
| Software local para o MacBook | T1 (esqueleto), T13 (launcher, Makefile, README) |
| Digitalizar com a HP DeskJet Ink Advantage 2874 | T0 (Gate 0), T3–T5 e T9 (eSCL, descoberta, conexão) |
| Facilitar uma quantidade gigante de documentos e fotos | T7 (nome automático, nunca sobrescreve), T8 (guarda de espaço), T11–T12 (um clique ou Espaço, sem diálogos); várias páginas por PDF é a Fase 2 do roadmap do spec |
| Um botão que digitaliza e cria PDF ou JPG | T10 (serviço de digitalização), T11 (API), T12 (interface), T14 (teste de ponta a ponta) |
| Opção no software para escolher PDF ou JPG | T6 (codificador), T11 (ajustes), T12 (seletor na interface) |

## Restrições globais

- **Plataforma:** macOS 15.x em Apple Silicon; Python 3.12 ou mais novo, somente no `.venv` do projeto (nada é instalado no Python global).
- **Dependências:** exatamente as da seção 6.7 do spec; qualquer outra exige decisão do usuário.
- **Idioma:** interface, mensagens ao usuário, README e documentos em português do Brasil; código, identificadores, mensagens de commit e nomes de teste em inglês.
- **Nomes (regras do usuário):** arquivos em kebab-case; classes em PascalCase; funções e variáveis em snake_case (também em JavaScript); constantes em UPPER_SNAKE_CASE; tabelas em snake_case; sem abreviações (`id`, `url`, `dpi`…). **Exceção D6, a aprovar:** módulos Python (inclusive os de teste) em snake_case.
- **Clean Code:** no máximo 3 parâmetros por função ou método (construtores incluídos); sem parâmetros booleanos de modo; constantes nomeadas; type hints nas interfaces públicas; comentários só para o porquê; sem código comentado; um conceito por teste; cada teste abaixo de 100 ms.
- **Arquitetura:** controllers → services → domain ← repositories/infrastructure; injeção de dependência só por construtor; nenhuma instância concreta fora de `composition_root.py`; tempo só pela porta `Clock`; esperas só por um `sleep` injetado.
- **Rede local do app:** servidor somente em `127.0.0.1`; `Host` validado; cabeçalho `X-Requested-With: digitalizadora` obrigatório em `POST`, `PUT`, `PATCH` e `DELETE`; sem CORS.
- **Impressora:** requisições eSCL sequenciais; sempre `DELETE` do trabalho; HTTP por padrão; sempre `image/jpeg`; sempre o vidro inteiro (sem recorte na v1); nunca fixar porta ou caminho.
- **Rede Local do macOS:** testes manuais e uso real pelo Terminal.app, nunca pelo terminal do VS Code.
- **Disco:** poucos GB livres no disco interno; a pasta de saída deve ficar num disco externo para volumes grandes.
- **Aprovação:** nenhuma tarefa deste plano começa antes da aprovação do spec e do plano.

## Foco da revisão (Review Focus)

Os cinco modos de falha com mais chance de atingir quem usa o software, do mais provável para o menos, e a tarefa cujo teste os fixa:

1. **Impressora dormindo, offline ou com IP novo ao apertar Digitalizar:** deve virar `scanner_unreachable` com mensagem clara e tentar de novo pelo UUID, nunca travar nem digitalizar duas vezes (T5, T9).
2. **Espaço repetido ou clique duplo durante uma digitalização:** a segunda chamada vira `409`/`scan_already_running` sem corromper a digitalização em andamento e sem página duplicada (T10, T11, T12).
3. **Pasta de saída ausente (disco externo desconectado) ou cheia:** `output_folder_unavailable` ou `insufficient_storage` antes de pedir a página à impressora (T7, T8, T14).
4. **Imagem inesperada vinda do scanner (não é JPEG, está corrompida, não tem densidade JFIF):** `scan_failed`, e o PDF sai com o tamanho de página certo mesmo sem JFIF (T5, T6).
5. **Processo interrompido durante a gravação e colisão de nomes:** nunca fica arquivo parcial com o nome final, nunca sobrescreve, e o contador continua depois de buracos (T7).

Também coberto: Rede Local bloqueada (`errno 65`) vira `local_network_blocked` com orientação própria (T5, T9).

---

## Mapa das tarefas

| Tarefa | Título |
|---|---|
| T0 | Gate 0, validar a impressora (manual, sem código do produto) |
| T1 | Esqueleto do projeto |
| T2 | Modelos de domínio, erros, política de nomes, portas e relógio |
| T3 | Funções do protocolo eSCL e fixtures XML |
| T4 | Simulador: impressora eSCL falsa (ASGI) |
| T5 | EsclScannerGateway |
| T6 | Pipeline de codificação (resolução do JPEG, PDF, miniatura e ScanEncoder) |
| T7 | Repositórios (gravação atômica, pasta de saída e JSON) |
| T8 | StorageGuardService e ScanOutputService |
| T9 | Descoberta Bonjour e PrinterConnectionService |
| T10 | Acompanhamento de progresso, ScanService e estado da aplicação |
| T11 | Serviço de ajustes, catálogo de erros, guarda de requisições, controllers e fábrica da aplicação |
| T12 | Interface web (arquivos estáticos) |
| T13 | Configuração, raiz de composição, pontos de entrada, launcher, Makefile e README |
| T14 | Teste de integração, teste de hardware e checklist de aceitação |

---

## Fase 0 — Gate 0: validar a impressora (antes de qualquer código)

### Task 0: Gate 0, validar a impressora (manual, sem código do produto)

**Objetivo:** Descobrir, com a impressora ligada, se ela responde em eSCL e medir tempo e tamanho por página, para decidir se o MVP segue o plano.

**Files:**
- Create: `scripts/probe-printer.sh`
- Create: `docs/spike-0/README.md`
- Create: `docs/spike-0/results-template.md`
- Create: `docs/spike-0/captures/.gitkeep`

**Interfaces:**
- Consumes: nada (a pasta ainda não é um repositório Git e não tem Python do projeto).
- Produces: `scripts/probe-printer.sh <host> [port=8080] [base_path=eSCL]`, que grava `docs/spike-0/captures/<data UTC>/` com `capabilities.xml`, `capabilities.headers`, `status.xml`, `scan-request.xml`, `post.headers`, `scan.jpg`, `summary.txt`; variáveis de ambiente opcionais `PROBE_DOTS_PER_INCH` (padrão 300) e `PROBE_COLOR_MODE` (padrão `RGB24`); o formulário `docs/spike-0/results.md` (feito pelo usuário) e uma decisão registrada nele. O XML de `scan-request.xml` é exatamente o que a Task 3 (`build_scan_settings_xml`) vai gerar para 300 dpi em cor.

Esta task não segue TDD (é validação manual contra hardware) e **não termina em commit**: a pasta ainda não é um repositório. O primeiro commit da Task 1 inclui estes arquivos. As capturas contêm o MAC e o UUID da impressora; o `.gitignore` da Task 1 ignora `docs/spike-0/captures/*` (exceto `.gitkeep`).

- [ ] **Passo 1: Criar o script de sondagem**

Criar as pastas e o arquivo:

```bash
mkdir -p scripts docs/spike-0/captures
```

Arquivo `scripts/probe-printer.sh`:

```bash
#!/usr/bin/env bash
# Gate 0: talks to the printer in eSCL (AirScan) with curl and saves every answer.
# Usage: scripts/probe-printer.sh <host> [port=8080] [base_path=eSCL]
# Optional environment: PROBE_DOTS_PER_INCH (default 300) and PROBE_COLOR_MODE (RGB24 or Grayscale8).
# Needs only macOS tools (bash 3.2, curl, grep, sed, sips, file). Run it from Terminal.app.

set -u -o pipefail

readonly CONNECT_TIMEOUT_SECONDS=5
readonly REQUEST_TIMEOUT_SECONDS=30
readonly DOCUMENT_TIMEOUT_SECONDS=60
readonly POLL_INTERVAL_SECONDS=2
readonly POLL_LIMIT_SECONDS=180
readonly FALLBACK_MAXIMUM_WIDTH=2550
readonly FALLBACK_MAXIMUM_HEIGHT=3507
readonly DEFAULT_DOTS_PER_INCH=300
readonly DEFAULT_COLOR_MODE=RGB24
readonly DEFAULT_PORT=8080
readonly DEFAULT_BASE_PATH=eSCL
readonly INTERRUPTED_EXIT_STATUS=130
readonly PWG_NAMESPACE='http://www.pwg.org/schemas/2010/12/sm'
readonly SCAN_NAMESPACE='http://schemas.hp.com/imaging/escl/2011/05/03'

print_usage() {
  printf 'Uso: %s <host> [porta=%s] [caminho_base=%s]\n' "$0" "$DEFAULT_PORT" "$DEFAULT_BASE_PATH" >&2
  printf 'Exemplo: %s 192.168.0.40\n' "$0" >&2
}

if [ "$#" -lt 1 ] || [ "$#" -gt 3 ]; then
  print_usage
  exit 2
fi

host="$1"
port="${2:-$DEFAULT_PORT}"
base_path="${3:-$DEFAULT_BASE_PATH}"
scan_dots_per_inch="${PROBE_DOTS_PER_INCH:-$DEFAULT_DOTS_PER_INCH}"
scan_color_mode="${PROBE_COLOR_MODE:-$DEFAULT_COLOR_MODE}"
origin="http://${host}:${port}"
script_directory="$(cd "$(dirname "$0")" && pwd)"
project_root="$(dirname "$script_directory")"
capture_directory="${project_root}/docs/spike-0/captures/$(date -u +%Y%m%dT%H%M%SZ)"
summary_file="${capture_directory}/summary.txt"
job_path=""
job_deleted=0
last_http_status=""
last_curl_exit=0

mkdir -p "$capture_directory" || exit 1

record_summary() {
  printf '%s\n' "$1" >> "$summary_file"
}

# Sets last_http_status and last_curl_exit; never follows redirects.
send_request() {
  local method="$1" request_path="$2" headers_file="$3" body_file="$4" timeout_seconds="$5"
  shift 5
  last_http_status="$(curl --silent --show-error \
    --connect-timeout "$CONNECT_TIMEOUT_SECONDS" --max-time "$timeout_seconds" \
    --request "$method" --dump-header "$headers_file" --output "$body_file" \
    --write-out '%{http_code}' "$@" "${origin}${request_path}" \
    2> "${capture_directory}/curl-error.txt")"
  last_curl_exit=$?
}

fail_unreachable() {
  printf 'ERRO: a impressora não respondeu em %s/%s (curl código %s).\n' \
    "$origin" "$base_path" "$last_curl_exit" >&2
  printf 'Confira: impressora ligada, luz do Wi-Fi fixa, mesma rede do Mac, VPN desligada,\n' >&2
  printf 'e este comando rodando no Terminal.app (não no terminal do VS Code).\n' >&2
  cat "${capture_directory}/curl-error.txt" >&2
  exit 1
}

fail_unexpected_status() {
  printf 'ERRO: %s respondeu HTTP %s; esperado %s. Confira a porta e o caminho base.\n' \
    "$1" "$last_http_status" "$2" >&2
  exit 1
}

read_element_number() {
  grep -o "[<:]$2>[0-9]*<" "$1" | head -1 | sed -e 's/[^0-9]//g'
}

delete_job() {
  if [ -n "$job_path" ] && [ "$job_deleted" -eq 0 ]; then
    job_deleted=1
    send_request DELETE "$job_path" "${capture_directory}/delete.headers" \
      "${capture_directory}/delete-response.txt" "$REQUEST_TIMEOUT_SECONDS"
    record_summary "DELETE ${job_path} -> HTTP ${last_http_status} (curl ${last_curl_exit})"
  fi
}

print_summary() {
  printf '\n===== Resumo do Gate 0 =====\n'
  printf 'Capturas em: %s\n' "$capture_directory"
  cat "$summary_file"
}

finish() {
  local exit_status=$?
  trap - EXIT
  delete_job
  print_summary
  exit "$exit_status"
}

trap finish EXIT
trap 'exit $INTERRUPTED_EXIT_STATUS' INT TERM

record_summary "Host: ${host}  Porta: ${port}  Caminho base: ${base_path}"
record_summary "Data (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)"

send_request GET "/${base_path}/ScannerCapabilities" "${capture_directory}/capabilities.headers" \
  "${capture_directory}/capabilities.xml" "$REQUEST_TIMEOUT_SECONDS"
if [ "$last_curl_exit" -ne 0 ]; then
  record_summary "GET ScannerCapabilities -> sem resposta (curl ${last_curl_exit})"
  fail_unreachable
fi
record_summary "GET ScannerCapabilities -> HTTP ${last_http_status}"
if [ "$last_http_status" != "200" ]; then
  fail_unexpected_status "ScannerCapabilities" "200"
fi
server_header="$(grep -i '^server:' "${capture_directory}/capabilities.headers" | head -1 | tr -d '\r')"
record_summary "Cabeçalho Server: ${server_header#*: }"

send_request GET "/${base_path}/ScannerStatus" "${capture_directory}/status.headers" \
  "${capture_directory}/status.xml" "$REQUEST_TIMEOUT_SECONDS"
record_summary "GET ScannerStatus -> HTTP ${last_http_status} (curl ${last_curl_exit})"
scanner_state="$(grep -o '[<:]State>[A-Za-z]*<' "${capture_directory}/status.xml" 2> /dev/null \
  | head -1 | sed -e 's/^[<:]State>//' -e 's/<$//')"
record_summary "Estado do scanner: ${scanner_state:-não encontrado}"

maximum_width="$(read_element_number "${capture_directory}/capabilities.xml" MaxWidth)"
maximum_height="$(read_element_number "${capture_directory}/capabilities.xml" MaxHeight)"
maximum_width="${maximum_width:-$FALLBACK_MAXIMUM_WIDTH}"
maximum_height="${maximum_height:-$FALLBACK_MAXIMUM_HEIGHT}"
record_summary "Vidro (1/300 pol.): ${maximum_width} x ${maximum_height}"

scan_request="<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
scan_request+="<scan:ScanSettings xmlns:pwg=\"${PWG_NAMESPACE}\" xmlns:scan=\"${SCAN_NAMESPACE}\">"
scan_request+="<pwg:Version>2.0</pwg:Version>"
scan_request+="<pwg:ScanRegions><pwg:ScanRegion>"
scan_request+="<pwg:ContentRegionUnits>escl:ThreeHundredthsOfInches</pwg:ContentRegionUnits>"
scan_request+="<pwg:XOffset>0</pwg:XOffset><pwg:YOffset>0</pwg:YOffset>"
scan_request+="<pwg:Width>${maximum_width}</pwg:Width><pwg:Height>${maximum_height}</pwg:Height>"
scan_request+="</pwg:ScanRegion></pwg:ScanRegions>"
scan_request+="<pwg:InputSource>Platen</pwg:InputSource>"
scan_request+="<scan:ColorMode>${scan_color_mode}</scan:ColorMode>"
scan_request+="<pwg:DocumentFormat>image/jpeg</pwg:DocumentFormat>"
scan_request+="<scan:XResolution>${scan_dots_per_inch}</scan:XResolution>"
scan_request+="<scan:YResolution>${scan_dots_per_inch}</scan:YResolution>"
scan_request+="</scan:ScanSettings>"
printf '%s' "$scan_request" > "${capture_directory}/scan-request.xml"

printf 'Digitalizando a %s dpi (%s). A folha precisa estar no vidro, com a tampa fechada.\n' "$scan_dots_per_inch" "$scan_color_mode"
SECONDS=0
send_request POST "/${base_path}/ScanJobs" "${capture_directory}/post.headers" \
  "${capture_directory}/post-response.txt" "$REQUEST_TIMEOUT_SECONDS" \
  --header 'Content-Type: text/xml' --data-binary "@${capture_directory}/scan-request.xml"
if [ "$last_curl_exit" -ne 0 ]; then
  record_summary "POST ScanJobs -> sem resposta (curl ${last_curl_exit})"
  fail_unreachable
fi
record_summary "POST ScanJobs -> HTTP ${last_http_status}"
if [ "$last_http_status" != "201" ]; then
  fail_unexpected_status "POST ScanJobs" "201"
fi

location_header="$(grep -i '^location:' "${capture_directory}/post.headers" | head -1 \
  | sed -e 's/^[Ll][Oo][Cc][Aa][Tt][Ii][Oo][Nn]:[[:space:]]*//' | tr -d '\r')"
job_path="$(printf '%s' "$location_header" \
  | sed -e 's#^[A-Za-z][A-Za-z0-9+.-]*://[^/]*##' -e 's#/*$##')"
record_summary "Location: ${location_header}  (caminho usado: ${job_path})"
if [ -z "$job_path" ]; then
  printf 'ERRO: a impressora aceitou o trabalho (HTTP 201) mas não enviou o cabeçalho Location.\n' >&2
  exit 1
fi

while [ "$SECONDS" -lt "$POLL_LIMIT_SECONDS" ]; do
  send_request GET "${job_path}/NextDocument" "${capture_directory}/document.headers" \
    "${capture_directory}/scan.jpg.part" "$DOCUMENT_TIMEOUT_SECONDS"
  printf '  [%ss] NextDocument -> HTTP %s (curl %s)\n' "$SECONDS" "$last_http_status" "$last_curl_exit"
  if [ "$last_curl_exit" -ne 0 ] || [ "$last_http_status" = "503" ]; then
    sleep "$POLL_INTERVAL_SECONDS"
  elif [ "$last_http_status" = "200" ]; then
    mv "${capture_directory}/scan.jpg.part" "${capture_directory}/scan.jpg"
    break
  else
    break
  fi
done
elapsed_seconds="$SECONDS"
record_summary "GET NextDocument -> HTTP ${last_http_status} (curl ${last_curl_exit})"

if [ ! -f "${capture_directory}/scan.jpg" ]; then
  printf 'ERRO: nenhuma imagem recebida em %s s (último HTTP %s).\n' "$elapsed_seconds" "$last_http_status" >&2
  exit 1
fi

record_summary "scan.jpg: $(wc -c < "${capture_directory}/scan.jpg" | tr -d ' ') bytes"
pixel_size="$(sips -g pixelWidth -g pixelHeight "${capture_directory}/scan.jpg" | grep pixel \
  | sed -e 's/^ *//' | tr '\n' ' ' | sed -e 's/ *$//')"
record_summary "Tamanho em pixels: ${pixel_size}"
record_summary "file: $(file -b "${capture_directory}/scan.jpg")"
record_summary "Tempo do disparo até o arquivo: ${elapsed_seconds} s"
```

- [ ] **Passo 2: Criar a documentação do Gate 0**

Arquivo `docs/spike-0/README.md`:

````markdown
# Gate 0: validar a impressora antes de escrever código

Objetivo: descobrir, com a impressora **ligada**, se a HP DeskJet Ink Advantage 2874 fala eSCL (AirScan) e quanto tempo e espaço cada página consome. O resultado decide se o projeto segue o plano do MVP ou muda de caminho. Referência: seção 9 do design (`docs/superpowers/specs/2026-10-13-digitalizadora-design.md`).

## Preparação

- [ ] Impressora ligada e a luz do Wi-Fi **fixa** (piscando = ainda conectando).
- [ ] Mac na mesma rede Wi-Fi da impressora (a impressora só usa 2,4 GHz).
- [ ] **VPN desligada** (o FortiClient está instalado).
- [ ] Abrir o **Terminal.app** (não o terminal do VS Code nem o do Claude Code: o macOS só libera a Rede Local para processos iniciados pelo Terminal.app).
- [ ] **Não** atualizar o firmware da impressora nem o macOS até terminar o Gate 0.
- [ ] Uma folha de papel comum no vidro, com a tampa fechada, para os passos 0.4 a 0.7.
- [ ] No Terminal.app, ir para a pasta do projeto e criar as variáveis usadas abaixo (troque pelos valores do passo 0.2):

```bash
cd /Users/usuario/Code/digitalizadora
export PRINTER_HOST=192.168.0.40
export PRINTER_PORT=8080
```

Tudo o que for salvo em `docs/spike-0/captures/` contém o MAC e o UUID da impressora: a pasta é ignorada pelo Git (só o `.gitkeep` entra). Não copie esses arquivos para um repositório público.

## Passos

Anote cada resultado em `docs/spike-0/results.md` (copie `results-template.md`).

### 0.1 Botão Informação

Aperte o botão **Informação** da impressora: ela imprime IP, nome (`HP...local`) e versão do firmware.

Anote: IP, nome, firmware. Reserve o IP no roteador (o MAC termina em `00:00:01`).

### 0.2 Bonjour

Cada comando fica rodando; aperte **Ctrl-C** depois de uns 5 segundos.

```bash
dns-sd -B _uscan._tcp local.
dns-sd -B _uscans._tcp local.
dns-sd -B _ipp._tcp local.
```

Copie o nome da coluna "Instance Name" do primeiro comando (por exemplo `HP DeskJet 2800 series [000001]`) e rode, também com Ctrl-C depois de 5 segundos:

```bash
dns-sd -L "HP DeskJet 2800 series [000001]" _uscan._tcp local.
```

Esperado: uma linha com o nome do host, a porta (provavelmente 8080) e as chaves TXT.

Anote: se `_uscan._tcp` aparece, a porta e todas as chaves TXT (`rs`, `ty`, `is`, `cs`, `pdl`, `UUID`...). Se nada aparece, vá direto à tabela de decisão.

### 0.3 Capacidades e estado

```bash
mkdir -p docs/spike-0/captures/manual
curl -sS --connect-timeout 5 --max-time 30 \
  -D docs/spike-0/captures/manual/capabilities.headers \
  -o docs/spike-0/captures/manual/capabilities.xml \
  "http://$PRINTER_HOST:$PRINTER_PORT/eSCL/ScannerCapabilities"
curl -sS --connect-timeout 5 --max-time 30 \
  -o docs/spike-0/captures/manual/status.xml \
  "http://$PRINTER_HOST:$PRINTER_PORT/eSCL/ScannerStatus"
```

Esperado: `capabilities.xml` com `ScannerCapabilities` e `status.xml` com `Idle`. Para extrair os valores:

```bash
grep -oE 'Max(Width|Height)>[0-9]+' docs/spike-0/captures/manual/capabilities.xml
grep -oE 'XResolution>[0-9]+' docs/spike-0/captures/manual/capabilities.xml | sort -u -t'>' -k2 -n
grep -oE 'ColorMode>[A-Za-z0-9]+' docs/spike-0/captures/manual/capabilities.xml | sort -u
grep -oE 'DocumentFormat(Ext)?>[A-Za-z0-9/.+-]+' docs/spike-0/captures/manual/capabilities.xml | sort -u
grep -i '^server:' docs/spike-0/captures/manual/capabilities.headers
```

Anote: `MaxWidth` e `MaxHeight` (o plano espera 2550 e 3507), as resoluções (600 e 1200 aparecem?), os modos de cor (`BlackAndWhite1` aparece?), os formatos (`image/jpeg` precisa aparecer) e o cabeçalho `Server`.

### 0.4 Uma digitalização de ponta a ponta

```bash
scripts/probe-printer.sh "$PRINTER_HOST" "$PRINTER_PORT"
```

O script cria `docs/spike-0/captures/<data UTC>/`, digitaliza a 300 dpi em cor (JPEG), espera o `NextDocument`, apaga o trabalho e imprime um resumo.

Esperado no resumo: `POST ScanJobs -> HTTP 201`, `GET NextDocument -> HTTP 200`, `DELETE ... -> HTTP 200` (ou 204), `scan.jpg` com alguns MB e a linha `file` começando com `JPEG image data, JFIF`.

Anote: o tempo do disparo até o arquivo, o tamanho em bytes (divida por 1048576 para MB), os pixels (a 300 dpi de uma folha cheia, cerca de 2550 x 3507), e se a linha `file` mostra `density 300x300`. Para ver a resolução e o perfil gravados na imagem:

```bash
sips -g dpiWidth -g dpiHeight -g profile docs/spike-0/captures/<data UTC>/scan.jpg
```

Se o script terminar com `ERRO`, copie a mensagem e o conteúdo de `summary.txt` da pasta da execução para o `results.md`.

### 0.5 Captura de Imagem

Abra o app **Captura de Imagem** (Image Capture). A impressora aparece em "Dispositivos" ou "Compartilhados"? Escolha o modo **Mesa** (Flatbed), 300 dpi, e digitalize uma folha.

Anote: se aparece, onde aparece, se a digitalização funcionou e a build do macOS:

```bash
sw_vers
```

### 0.6 Matriz de tempo e tamanho

Com a folha no vidro, rode todas as combinações (leva alguns minutos; a pausa de 10 s deixa a impressora voltar a `Idle`):

```bash
for dots in 150 200 300 600; do
  for mode in RGB24 Grayscale8; do
    echo "== ${dots} dpi ${mode}"
    PROBE_DOTS_PER_INCH=$dots PROBE_COLOR_MODE=$mode \
      scripts/probe-printer.sh "$PRINTER_HOST" "$PRINTER_PORT" \
      | grep -E 'scan.jpg:|Tamanho em pixels|Tempo do disparo|ERRO'
    sleep 10
  done
done
```

Anote, por combinação: segundos por página e MB por página. Atenção especial a 600 dpi em cor: se falhar, estourar 120 s ou devolver uma imagem menor que a pedida, anote.

### 0.7 Sono

Deixe a impressora parada por 10 minutos (ela entra em repouso depois de uns 5) e repita o 0.2 e o 0.3 sem encostar nela:

```bash
sleep 600
dns-sd -B _uscan._tcp local.
curl -sS -o /dev/null -w 'HTTP %{http_code} em %{time_total} s\n' \
  --connect-timeout 5 --max-time 30 \
  "http://$PRINTER_HOST:$PRINTER_PORT/eSCL/ScannerStatus"
scripts/probe-printer.sh "$PRINTER_HOST" "$PRINTER_PORT"
```

Anote: se ela ainda anuncia `_uscan._tcp` e responde dormindo, o atraso do primeiro pedido (`time_total`) e se a digitalização acorda a impressora.

### 0.8 Rede Local do macOS

Abra o terminal do **VS Code** (não o Terminal.app), crie as duas variáveis outra vez (`export PRINTER_HOST=...` e `export PRINTER_PORT=...`) e rode:

```bash
curl -sS --connect-timeout 5 --max-time 10 -o /dev/null -w 'HTTP %{http_code}\n' \
  "http://$PRINTER_HOST:$PRINTER_PORT/eSCL/ScannerStatus"
```

Esperado: `HTTP 200` (a restrição não vale nesta máquina) ou `curl: (7) Failed to connect ... No route to host` (confirma que só o Terminal.app é liberado).

## Decisão

| Resultado | O que fazer |
|---|---|
| `_uscan._tcp` aparece, capacidades e scan por `curl` funcionam | Seguir com o MVP; trocar as fixtures sintéticas pelo XML real |
| Não aparece, mas a página da impressora (EWS) tem opção de eSCL/AirPrint/Webscan | Ativar, repetir 0.2 |
| Não há eSCL | O app HP e o VueScan falam outros protocolos (LEDM/REST). Reavaliar: (a) um adaptador HP LEDM atrás de `ScannerGateway` (o resto do projeto não muda), ou (b) desistir de software próprio e usar app HP/NAPS2/VueScan. Decisão sua, com os dados do Gate 0 |
| eSCL funciona, mas 600 dpi em cor falha ou fica lento | Limitar o preset `PHOTO` a 400 dpi |

Registre a decisão no fim do `results.md`.
````

Arquivo `docs/spike-0/results-template.md`:

```markdown
# Resultados do Gate 0

Copie este arquivo para `docs/spike-0/results.md` e preencha. Não escreva o MAC completo da impressora aqui.

- Data do Gate 0: ____-__-__
- Build do macOS (saída de `sw_vers`): ProductName ________  ProductVersion ________  BuildVersion ________
- Impressora: IP ________  nome Bonjour ________  firmware ________
- VPN desligada: sim / não   Terminal usado: Terminal.app / outro: ________

## Passos

| Passo | Comando | Resultado | Data |
|---|---|---|---|
| 0.1 | Botão Informação | IP, nome e firmware: | |
| 0.2 | `dns-sd -B _uscan._tcp local.` | `_uscan._tcp` aparece? porta? chaves TXT: | |
| 0.2 | `dns-sd -B _uscans._tcp local.` e `_ipp._tcp` | aparecem? | |
| 0.3 | `curl .../eSCL/ScannerCapabilities` e `.../ScannerStatus` | MaxWidth x MaxHeight; resoluções; modos de cor; formatos; Server: | |
| 0.4 | `scripts/probe-printer.sh $PRINTER_HOST $PRINTER_PORT` | HTTP do POST; segundos até o arquivo; bytes; pixels; JFIF e densidade: | |
| 0.5 | Captura de Imagem, mesa, 300 dpi | aparece em Dispositivos/Compartilhados? funcionou? | |
| 0.6 | Matriz 150/200/300/600 dpi, RGB24/Grayscale8 | tabela abaixo | |
| 0.7 | Sono de 10 minutos, repetir 0.2 e 0.3, depois um scan | responde dormindo? atraso do primeiro pedido (s)? o scan acordou a impressora? | |
| 0.8 | `curl` pelo terminal do VS Code | HTTP 200 ou `No route to host`? | |

## Matriz do passo 0.6

| dpi | modo | segundos | MB | observações |
|---|---|---|---|---|
| 150 | RGB24 | | | |
| 150 | Grayscale8 | | | |
| 200 | RGB24 | | | |
| 200 | Grayscale8 | | | |
| 300 | RGB24 | | | |
| 300 | Grayscale8 | | | |
| 600 | RGB24 | | | |
| 600 | Grayscale8 | | | |

## Decisão (tabela da seção 9 do design)

- Resultado observado: ________
- Ação escolhida: ________
- Presets a recalibrar (por exemplo PHOTO a 400 dpi): ________
```

Arquivo vazio para manter a pasta de capturas:

```bash
touch docs/spike-0/captures/.gitkeep
```

- [ ] **Passo 3: Tornar o script executável**

Run: `chmod +x scripts/probe-printer.sh && ls -l scripts/probe-printer.sh`
Expected: uma linha começando com `-rwxr-xr-x` e terminando em `scripts/probe-printer.sh`.

- [ ] **Passo 4: Conferir a sintaxe do script**

Run: `bash -n scripts/probe-printer.sh; echo "status=$?"`
Expected: nenhuma mensagem de erro; a única linha impressa é `status=0`.

- [ ] **Passo 5: Ensaio contra uma porta fechada (sem a impressora)**

Run: `scripts/probe-printer.sh 127.0.0.1 9; echo "status=$?"`
Expected: a mensagem em português abaixo (o caminho da pasta de capturas muda), depois o resumo e `status=1`:

```text
ERRO: a impressora não respondeu em http://127.0.0.1:9/eSCL (curl código 7).
Confira: impressora ligada, luz do Wi-Fi fixa, mesma rede do Mac, VPN desligada,
e este comando rodando no Terminal.app (não no terminal do VS Code).
curl: (7) Failed to connect to 127.0.0.1 port 9 ...

===== Resumo do Gate 0 =====
GET ScannerCapabilities -> sem resposta (curl 7)
status=1
```

Run: `scripts/probe-printer.sh; echo "status=$?"`
Expected: a linha `Uso: scripts/probe-printer.sh <host> [porta=8080] [caminho_base=eSCL]`, o exemplo e `status=2`.

Limpar as pastas criadas pelo ensaio (o `.gitkeep` fica):

Run: `find docs/spike-0/captures -mindepth 1 -maxdepth 1 -type d -exec rm -r {} + ; ls -A docs/spike-0/captures`
Expected: apenas `.gitkeep`.

- [ ] **Passo 6: Preparar o Gate 0 real**

Seguir a seção "Preparação" de `docs/spike-0/README.md`: impressora ligada com a luz do Wi-Fi fixa, Mac na mesma rede, VPN desligada, **Terminal.app** (não o terminal do VS Code), sem atualizar firmware nem macOS, uma folha no vidro. Depois:

```bash
cd /Users/usuario/Code/digitalizadora
cp docs/spike-0/results-template.md docs/spike-0/results.md
```

Run: `sw_vers`
Expected: três linhas (`ProductName`, `ProductVersion`, `BuildVersion`); copiar para o topo de `docs/spike-0/results.md`.

- [ ] **Passo 7: Passo 0.1, botão Informação**

Apertar o botão **Informação** da impressora.
Expected: a impressora imprime uma página com IP, nome (`HP...local`) e firmware. Anotar os três em `results.md`; reservar o IP no roteador (MAC termina em `00:00:01`); depois `export PRINTER_HOST=<IP>` e `export PRINTER_PORT=8080` no Terminal.app.

- [ ] **Passo 8: Passo 0.2, Bonjour**

Run (Ctrl-C depois de 5 s em cada um): `dns-sd -B _uscan._tcp local.` e depois `dns-sd -B _uscans._tcp local.` e `dns-sd -B _ipp._tcp local.`
Expected: para `_uscan._tcp`, uma linha `Add` com o nome `HP DeskJet 2800 series [000001]` (ou parecido). Se não aparecer nada, anotar e ir ao Passo 15 (decisão).

Run (Ctrl-C depois de 5 s): `dns-sd -L "HP DeskJet 2800 series [000001]" _uscan._tcp local.` (usar o nome exato visto na coluna Instance Name)
Expected: nome do host, porta (esperada 8080) e as chaves TXT (`rs`, `ty`, `is`, `cs`, `pdl`, `UUID`...). Anotar tudo no `results.md`.

- [ ] **Passo 9: Passo 0.3, capacidades e estado**

Run: os dois `curl` da seção 0.3 de `docs/spike-0/README.md`, depois os cinco `grep`.
Expected: `capabilities.xml` com a raiz `ScannerCapabilities`; `MaxWidth>2550` e `MaxHeight>3507` (ou valores próximos); resoluções incluindo `300`; `ColorMode>RGB24`; `DocumentFormat>image/jpeg`; `status.xml` com `Idle`. Anotar os valores, se 600 e 1200 aparecem e o cabeçalho `Server`.

- [ ] **Passo 10: Passo 0.4, uma digitalização de ponta a ponta**

Run: `scripts/probe-printer.sh "$PRINTER_HOST" "$PRINTER_PORT"`
Expected: linhas `NextDocument -> HTTP 503` repetidas a cada 2 s e depois `HTTP 200`; no resumo, `POST ScanJobs -> HTTP 201`, `scan.jpg: <bytes> bytes`, `Tamanho em pixels: pixelWidth: ~2550 pixelHeight: ~3507`, a linha `file:` com `JPEG image data, JFIF`, `Tempo do disparo até o arquivo: N s` e `DELETE ... -> HTTP 200` (ou 204). Abrir `scan.jpg` e conferir que é a folha do vidro. Anotar tempo, bytes, pixels, JFIF e densidade.

- [ ] **Passo 11: Passo 0.5, Captura de Imagem**

Abrir o app Captura de Imagem, procurar a impressora em Dispositivos/Compartilhados e digitalizar uma folha em modo Mesa a 300 dpi.
Expected: a impressora aparece e a digitalização grava um arquivo. Anotar o resultado e a build do macOS (`sw_vers`).

- [ ] **Passo 12: Passo 0.6, matriz de tempo e tamanho**

Run: o laço `for dots in 150 200 300 600 ...` da seção 0.6 de `docs/spike-0/README.md`.
Expected: oito blocos `== <dpi> dpi <modo>`, cada um com `scan.jpg: ... bytes`, `Tamanho em pixels` e `Tempo do disparo ...` (ou `ERRO`). Preencher a tabela do `results.md` (segundos e MB por página; MB = bytes / 1048576).

- [ ] **Passo 13: Passo 0.7, sono**

Run: os comandos da seção 0.7 de `docs/spike-0/README.md` (começam com `sleep 600`).
Expected: `dns-sd` ainda lista `_uscan._tcp` (ou não), o `curl` imprime `HTTP 200 em N s` com o atraso do primeiro pedido, e o script completa a digitalização. Anotar se respondeu dormindo, o atraso e se o scan acordou a impressora.

- [ ] **Passo 14: Passo 0.8, Rede Local pelo terminal do VS Code**

Run (no terminal do VS Code, depois de recriar `PRINTER_HOST` e `PRINTER_PORT`): `curl -sS --connect-timeout 5 --max-time 10 -o /dev/null -w 'HTTP %{http_code}\n' "http://$PRINTER_HOST:$PRINTER_PORT/eSCL/ScannerStatus"`
Expected: `HTTP 200` ou `curl: (7) Failed to connect ... No route to host`. Anotar qual (o segundo confirma que só o Terminal.app é liberado).

- [ ] **Passo 15: Registrar os resultados e decidir**

Preencher a tabela e a seção "Decisão" de `docs/spike-0/results.md` aplicando a tabela de decisão de `docs/spike-0/README.md`:

| Resultado | Ação |
|---|---|
| `_uscan._tcp` aparece, capacidades e scan por `curl` funcionam | Seguir com a Task 1; depois da Task 3, comparar a fixture sintética com `capabilities.xml` real (Passo final da Task 3) |
| Não aparece, mas a página da impressora (EWS) tem eSCL/AirPrint/Webscan | Ativar e repetir o Passo 8 |
| Não há eSCL | Parar o plano e levar o `results.md` ao usuário: adaptador HP LEDM atrás de `ScannerGateway` ou usar app HP/NAPS2/VueScan |
| eSCL funciona, mas 600 dpi em cor falha ou fica lento | Seguir, anotando que o preset `PHOTO` passa a 400 dpi (ajuste feito na Task 2, `PHOTO_DOTS_PER_INCH`) |

Expected: `docs/spike-0/results.md` completo, com a build do macOS, a tabela e a decisão escrita. Sem commit nesta task.

## Fase 1 — MVP: um clique, um arquivo

### Task 1: Esqueleto do projeto

**Objetivo:** Criar o repositório Git, o ambiente `.venv`, o `pyproject.toml`, as pastas de pacotes e a configuração de testes, e fazer o primeiro commit (que também leva a Task 0 e os documentos).

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `Makefile`
- Create: `README.md`
- Create: `src/digitalizadora/__init__.py`
- Create: `src/digitalizadora/domain/__init__.py`
- Create: `src/digitalizadora/services/__init__.py`
- Create: `src/digitalizadora/repositories/__init__.py`
- Create: `src/digitalizadora/infrastructure/__init__.py`
- Create: `src/digitalizadora/infrastructure/escl/__init__.py`
- Create: `src/digitalizadora/controllers/__init__.py`
- Create: `src/digitalizadora/simulator/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/fakes/__init__.py`
- Create: `tests/fixtures/.gitkeep`
- Create: `tests/domain/__init__.py`
- Create: `tests/services/__init__.py`
- Create: `tests/repositories/__init__.py`
- Create: `tests/infrastructure/__init__.py`
- Create: `tests/controllers/__init__.py`
- Create: `tests/simulator/__init__.py`
- Create: `tests/integration/__init__.py`
- Create: `tests/hardware/__init__.py`
- Create: `tests/web/__init__.py`
- Test: `tests/test_smoke.py`
- Test: `tests/test_hardware_marker.py`

**Interfaces:**
- Consumes: os arquivos da Task 0 (`scripts/`, `docs/spike-0/`), só para entrarem no primeiro commit.
- Produces: o pacote importável `digitalizadora` com `digitalizadora.__version__ == "0.1.0"`; todos os pacotes vazios das camadas (`domain`, `services`, `repositories`, `infrastructure`, `infrastructure.escl`, `controllers`, `simulator`) e das pastas de teste; `make setup`, `make test` e `make lint`; o marcador `hardware` (pulado a menos que `DIGITALIZADORA_HARDWARE_TESTS=1`); `asyncio_mode = "auto"`; `pythonpath = ["."]`, que permite `from tests.fakes... import ...`.

- [ ] **Passo 1: Criar o repositório e conferir o Python**

Run: `git init -b main`
Expected: `Initialized empty Git repository in /Users/usuario/Code/digitalizadora/.git/`

Run: `python3 -c "import sys; assert sys.version_info >= (3, 12), sys.version; print(sys.version.split()[0])"`
Expected: um número `3.12.x` ou maior (nesta máquina, `3.12.3`). Se aparecer `AssertionError`, usar `python3.12` no lugar de `python3` nos passos seguintes e em `make setup PYTHON=python3.12`.

- [ ] **Passo 2: Criar os arquivos de configuração**

Arquivo `pyproject.toml` (as dependências são exatamente as da seção 6.7 do design):

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "digitalizadora"
version = "0.1.0"
description = "Digitaliza uma página por clique na HP DeskJet Ink Advantage 2874 pelo protocolo eSCL."
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn>=0.30",
    "httpx>=0.27",
    "zeroconf>=0.151",
    "pillow>=12",
    "img2pdf>=0.6.3",
    "pikepdf>=10",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.24",
    "ruff",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
digitalizadora = ["web/static/*"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
pythonpath = ["."]
testpaths = ["tests"]
markers = [
    "hardware: needs the real printer; runs only with DIGITALIZADORA_HARDWARE_TESTS=1",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "B", "UP"]
# The design contracts (section 6.1) declare enums as (str, Enum), not StrEnum.
ignore = ["UP042"]
```

Arquivo `.gitignore`:

```gitignore
.venv/
__pycache__/
*.egg-info/
.pytest_cache/
.ruff_cache/
.DS_Store
docs/spike-0/captures/*
!docs/spike-0/captures/.gitkeep
```

Arquivo `Makefile` (as linhas de comando começam com **TAB**, não com espaços):

```make
.PHONY: setup test lint

PYTHON ?= python3
VIRTUAL_ENVIRONMENT := .venv

setup:
	$(PYTHON) -m venv $(VIRTUAL_ENVIRONMENT)
	$(VIRTUAL_ENVIRONMENT)/bin/pip install -e ".[dev]"

test:
	$(VIRTUAL_ENVIRONMENT)/bin/pytest

lint:
	$(VIRTUAL_ENVIRONMENT)/bin/ruff check src tests
```

Arquivo `README.md` (a Task 13 o substitui pela versão completa):

````markdown
# Digitalizadora

App local para o MacBook: abre uma página em `http://127.0.0.1:8765` com um botão **Digitalizar** (ou a tecla Espaço), digitaliza uma página do vidro da HP DeskJet Ink Advantage 2874 pelo protocolo eSCL e grava um PDF ou um JPG com nome automático.

Estado: em construção (MVP). O desenho está em `docs/superpowers/specs/2026-10-13-digitalizadora-design.md` e a validação da impressora (Gate 0) em `docs/spike-0/README.md`.

## Desenvolvimento

```bash
make setup   # cria o .venv e instala o projeto com as ferramentas de desenvolvimento
make test    # roda os testes
make lint    # confere o estilo com o ruff
```

Os testes que usam a impressora real ficam marcados com `hardware` e só rodam com `DIGITALIZADORA_HARDWARE_TESTS=1`.
````

- [ ] **Passo 3: Criar os pacotes vazios**

O pacote raiz fica vazio por enquanto (a versão entra no Passo 6, depois do teste que falha):

```bash
mkdir -p src/digitalizadora/domain src/digitalizadora/services src/digitalizadora/repositories \
  src/digitalizadora/infrastructure/escl src/digitalizadora/controllers src/digitalizadora/simulator \
  tests/fakes tests/fixtures tests/domain tests/services tests/repositories tests/infrastructure \
  tests/controllers tests/simulator tests/integration tests/hardware tests/web
touch src/digitalizadora/__init__.py src/digitalizadora/domain/__init__.py \
  src/digitalizadora/services/__init__.py src/digitalizadora/repositories/__init__.py \
  src/digitalizadora/infrastructure/__init__.py src/digitalizadora/infrastructure/escl/__init__.py \
  src/digitalizadora/controllers/__init__.py src/digitalizadora/simulator/__init__.py \
  tests/__init__.py tests/fakes/__init__.py tests/domain/__init__.py tests/services/__init__.py \
  tests/repositories/__init__.py tests/infrastructure/__init__.py tests/controllers/__init__.py \
  tests/simulator/__init__.py tests/integration/__init__.py tests/hardware/__init__.py \
  tests/web/__init__.py tests/fixtures/.gitkeep
```

Run: `find src tests -name '__init__.py' | wc -l | tr -d ' '`
Expected: `19`

- [ ] **Passo 4: Criar o ambiente virtual e instalar**

Precisa de rede e leva alguns minutos.

Run: `python3 -m venv .venv`
Expected: sem saída; a pasta `.venv/` existe.

Run: `.venv/bin/pip install -e ".[dev]"`
Expected: termina com uma linha `Successfully installed ... digitalizadora-0.1.0 ... pytest-... pytest-asyncio-... ruff-...` (a lista inclui fastapi, httpx, zeroconf, pillow, img2pdf e pikepdf).

Run: `.venv/bin/python -c "import digitalizadora; print(digitalizadora.__file__)"`
Expected: um caminho terminando em `src/digitalizadora/__init__.py` (instalação editável).

- [ ] **Passo 5: Escrever o teste de fumaça que falha**

Arquivo `tests/test_smoke.py`:

```python
from importlib.metadata import version

import digitalizadora


def test_package_exposes_its_version() -> None:
    assert digitalizadora.__version__ == "0.1.0"


def test_package_version_matches_the_installed_metadata() -> None:
    assert version("digitalizadora") == digitalizadora.__version__
```

- [ ] **Passo 6: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/test_smoke.py -v`
Expected: `2 failed`; o primeiro com `AttributeError: module 'digitalizadora' has no attribute '__version__'`.

- [ ] **Passo 7: Implementar o mínimo**

Arquivo `src/digitalizadora/__init__.py`:

```python
__version__ = "0.1.0"
```

- [ ] **Passo 8: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/test_smoke.py -v`
Expected: `2 passed`

- [ ] **Passo 9: Escrever o teste do marcador `hardware` que falha**

Há um único mecanismo para pular testes de hardware: o gancho `pytest_collection_modifyitems` do `conftest.py` (sem `addopts -m`). O teste chama o gancho com itens falsos e controla a variável de ambiente com `monkeypatch`.

Arquivo `tests/test_hardware_marker.py`:

```python
import pytest

from tests.conftest import (
    HARDWARE_MARKER_NAME,
    HARDWARE_TESTS_VARIABLE,
    pytest_collection_modifyitems,
)


class FakeTestItem:
    def __init__(self, marker_names: set[str]) -> None:
        self.marker_names = marker_names
        self.added_markers: list[object] = []

    def get_closest_marker(self, name: str) -> object | None:
        return object() if name in self.marker_names else None

    def add_marker(self, marker: object) -> None:
        self.added_markers.append(marker)


def apply_hook(items: list[FakeTestItem]) -> None:
    pytest_collection_modifyitems(items=items)


def test_hardware_tests_are_skipped_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(HARDWARE_TESTS_VARIABLE, raising=False)
    hardware_item = FakeTestItem({HARDWARE_MARKER_NAME})

    apply_hook([hardware_item])

    assert len(hardware_item.added_markers) == 1


def test_regular_tests_are_never_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(HARDWARE_TESTS_VARIABLE, raising=False)
    regular_item = FakeTestItem(set())

    apply_hook([regular_item])

    assert regular_item.added_markers == []


def test_hardware_tests_run_when_the_variable_is_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(HARDWARE_TESTS_VARIABLE, "1")
    hardware_item = FakeTestItem({HARDWARE_MARKER_NAME})

    apply_hook([hardware_item])

    assert hardware_item.added_markers == []


@pytest.mark.parametrize("value", ["0", "", "true"])
def test_hardware_tests_stay_skipped_for_any_other_value(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(HARDWARE_TESTS_VARIABLE, value)
    hardware_item = FakeTestItem({HARDWARE_MARKER_NAME})

    apply_hook([hardware_item])

    assert len(hardware_item.added_markers) == 1
```

- [ ] **Passo 10: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/test_hardware_marker.py -v`
Expected: erro de coleta `ModuleNotFoundError: No module named 'tests.conftest'` (o `conftest.py` ainda não existe) e `1 error`.

- [ ] **Passo 11: Implementar o gancho**

Arquivo `tests/conftest.py`:

```python
import os

import pytest

HARDWARE_TESTS_VARIABLE = "DIGITALIZADORA_HARDWARE_TESTS"
HARDWARE_TESTS_ENABLED_VALUE = "1"
HARDWARE_MARKER_NAME = "hardware"
HARDWARE_SKIP_REASON = (
    f"hardware test: set {HARDWARE_TESTS_VARIABLE}={HARDWARE_TESTS_ENABLED_VALUE} to run it"
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if os.environ.get(HARDWARE_TESTS_VARIABLE) == HARDWARE_TESTS_ENABLED_VALUE:
        return
    skip_hardware = pytest.mark.skip(reason=HARDWARE_SKIP_REASON)
    for item in items:
        if item.get_closest_marker(HARDWARE_MARKER_NAME) is not None:
            item.add_marker(skip_hardware)
```

- [ ] **Passo 12: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/test_hardware_marker.py -v`
Expected: `6 passed`

- [ ] **Passo 13: Rodar tudo e o lint**

Run: `.venv/bin/pytest`
Expected: `8 passed` (e nenhum aviso de marcador desconhecido nem de `asyncio_default_fixture_loop_scope`).

Run: `.venv/bin/ruff check src tests`
Expected: `All checks passed!`

Run: `make test lint`
Expected: `8 passed` e depois `All checks passed!` (confirma os alvos do Makefile).

- [ ] **Passo 14: Primeiro commit**

O commit leva também `md.md`, os documentos (`docs/`: design, plano, digest da pesquisa, `docs/spike-0/` da Task 0) e `scripts/`. As capturas do Gate 0 não entram (ignoradas pelo `.gitignore`, exceto `.gitkeep`).

Run: `git add .gitignore Makefile README.md pyproject.toml md.md docs scripts src tests`
Expected: sem saída.

Run: `git status --short | grep -E '\.venv|captures/[0-9]|\.egg-info' ; echo "linhas=$?"`
Expected: nenhuma linha antes de `linhas=1` (nada de `.venv`, `*.egg-info` nem capturas preparados).

Run: `git ls-files docs/spike-0/captures`
Expected: apenas `docs/spike-0/captures/.gitkeep`.

Se `docs/spike-0/results.md` existir, conferir que não contém o MAC completo da impressora antes de seguir.

Run: `git commit -m "chore: scaffold project, Gate 0 probe script and design documents"`
Expected: `[main (root-commit) ...] chore: scaffold project, Gate 0 probe script and design documents`

### Task 2: Modelos de domínio, erros, política de nomes, portas e relógio

**Objetivo:** Criar o núcleo sem dependências externas do projeto (modelos imutáveis, erros com código, regra de nome de arquivo, portas e o relógio do sistema) com os dublês de teste `FixedClock` e `build_sample_jpeg`.

**Files:**
- Create: `src/digitalizadora/domain/output_format.py`
- Create: `src/digitalizadora/domain/color_mode.py`
- Create: `src/digitalizadora/domain/scan_settings.py`
- Create: `src/digitalizadora/domain/scan_preset.py`
- Create: `src/digitalizadora/domain/scan_request.py`
- Create: `src/digitalizadora/domain/scan_job.py`
- Create: `src/digitalizadora/domain/scanner_endpoint.py`
- Create: `src/digitalizadora/domain/scanner_capabilities.py`
- Create: `src/digitalizadora/domain/scanner_status.py`
- Create: `src/digitalizadora/domain/scanned_image.py`
- Create: `src/digitalizadora/domain/encoded_scan.py`
- Create: `src/digitalizadora/domain/scan_result.py`
- Create: `src/digitalizadora/domain/stored_scan.py`
- Create: `src/digitalizadora/domain/application_settings.py`
- Create: `src/digitalizadora/domain/scan_progress.py`
- Create: `src/digitalizadora/domain/errors.py`
- Create: `src/digitalizadora/domain/scan_file_naming_policy.py`
- Create: `src/digitalizadora/domain/ports.py`
- Create: `src/digitalizadora/infrastructure/system_clock.py`
- Create: `tests/fakes/fixed_clock.py`
- Create: `tests/fakes/sample_images.py`
- Test: `tests/domain/test_output_format.py`
- Test: `tests/domain/test_scan_preset.py`
- Test: `tests/domain/test_application_settings.py`
- Test: `tests/domain/test_scanner_capabilities.py`
- Test: `tests/domain/test_scanner_status.py`
- Test: `tests/domain/test_errors.py`
- Test: `tests/domain/test_scan_file_naming_policy.py`
- Test: `tests/domain/test_immutable_models.py`
- Test: `tests/domain/test_ports.py`
- Test: `tests/infrastructure/test_system_clock.py`
- Test: `tests/fakes/test_fixed_clock.py`
- Test: `tests/fakes/test_sample_images.py`

**Interfaces:**
- Consumes: apenas o esqueleto da Task 1 (pacotes vazios, `pytest`, `ruff`, `Pillow` do ambiente).
- Produces (nomes e assinaturas exatamente os da seção 6.1 do design):
  - `digitalizadora.domain.output_format.OutputFormat` (`PDF = "pdf"`, `JPEG = "jpg"`, propriedade `file_extension`)
  - `digitalizadora.domain.color_mode.ColorMode` (`COLOR`, `GRAYSCALE`)
  - `digitalizadora.domain.scan_settings.ScanSettings(dots_per_inch: int, color_mode: ColorMode)`
  - `digitalizadora.domain.scan_preset.ScanPreset` (`DOCUMENT`, `DOCUMENT_ECONOMY`, `PHOTO`, propriedade `settings`)
  - `digitalizadora.domain.scan_request.ScanRequest(settings, output_format)`; `digitalizadora.domain.scan_job.ScanJob(request, started_at)`
  - `digitalizadora.domain.scanner_endpoint.ScannerEndpoint(base_address, display_name, universally_unique_identifier=None)`
  - `digitalizadora.domain.scanner_capabilities.ScannerCapabilities(make_and_model, platen_maximum_width, platen_maximum_height, supported_resolutions, supported_color_modes, supported_document_formats)` com `closest_supported_resolution(requested_dots_per_inch: int) -> int` e `supports_color_mode(escl_color_mode: str) -> bool`
  - `digitalizadora.domain.scanner_status.ScannerState` e `ScannerStatus(state)` com `is_ready`
  - `digitalizadora.domain.scanned_image.ScannedImage(content, media_type)`; `encoded_scan.EncodedScan(content, output_format, created_at, thumbnail_jpeg)`; `scan_result.ScanResult(output_path, output_format, scanned_at, size_in_bytes)`; `stored_scan.StoredScan(result, thumbnail_jpeg)`
  - `digitalizadora.domain.application_settings.ApplicationSettings(output_folder, output_format, scan_preset)` com `to_scan_request() -> ScanRequest`
  - `digitalizadora.domain.scan_progress.ScanPhase` e `ScanProgressSnapshot(phase, scans_completed, last_result, last_error_code)`
  - `digitalizadora.domain.errors`: `DigitalizadoraError` (atributo de classe `code`) e as dez subclasses do design
  - `digitalizadora.domain.scan_file_naming_policy.ScanFileNamingPolicy` com `build_file_name(scanned_at, sequence_number, output_format) -> str` e `extract_sequence_number(file_name, scanned_at) -> int | None`
  - `digitalizadora.domain.ports`: `Clock`, `ScannerGateway`, `ScannerGatewayProvider`, `ScannerDiscovery`, `ScannerEndpointRepository`, `ApplicationSettingsRepository`, `ScanOutputRepository`
  - `digitalizadora.infrastructure.system_clock.SystemClock.now() -> datetime` (horário local com fuso)
  - `tests.fakes.fixed_clock.FixedClock(moment)` com `now()` e `advance(seconds)`
  - `tests.fakes.sample_images.build_sample_jpeg(width_pixels=64, height_pixels=48, dots_per_inch=None) -> bytes`

Observação: se o Gate 0 decidiu limitar o preset `PHOTO` a 400 dpi, troque `PHOTO_DOTS_PER_INCH = 600` por `400` no Passo 3 e `600` por `400` na linha do `PHOTO` do teste do Passo 1.

#### Ciclo 1: formato de saída, preset e ajustes da aplicação

- [ ] **Passo 1: Escrever os testes que falham**

Arquivo `tests/domain/test_output_format.py`:

```python
import pytest

from digitalizadora.domain.output_format import OutputFormat


@pytest.mark.parametrize(
    ("output_format", "expected_extension"),
    [(OutputFormat.PDF, "pdf"), (OutputFormat.JPEG, "jpg")],
)
def test_file_extension_matches_format(
    output_format: OutputFormat, expected_extension: str
) -> None:
    assert output_format.file_extension == expected_extension


def test_format_is_created_from_its_stored_text() -> None:
    assert OutputFormat("jpg") is OutputFormat.JPEG
```

Arquivo `tests/domain/test_scan_preset.py`:

```python
import pytest

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.scan_preset import ScanPreset


@pytest.mark.parametrize(
    ("preset", "expected_dots_per_inch", "expected_color_mode"),
    [
        (ScanPreset.DOCUMENT, 300, ColorMode.COLOR),
        (ScanPreset.DOCUMENT_ECONOMY, 200, ColorMode.GRAYSCALE),
        (ScanPreset.PHOTO, 600, ColorMode.COLOR),
    ],
)
def test_preset_settings_table(
    preset: ScanPreset, expected_dots_per_inch: int, expected_color_mode: ColorMode
) -> None:
    assert preset.settings.dots_per_inch == expected_dots_per_inch
    assert preset.settings.color_mode is expected_color_mode


def test_preset_is_created_from_its_stored_text() -> None:
    assert ScanPreset("document_economy") is ScanPreset.DOCUMENT_ECONOMY
```

Arquivo `tests/domain/test_application_settings.py`:

```python
from pathlib import Path

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset


def test_to_scan_request_combines_preset_settings_and_output_format() -> None:
    application_settings = ApplicationSettings(
        output_folder=Path("/Volumes/Scans"),
        output_format=OutputFormat.JPEG,
        scan_preset=ScanPreset.PHOTO,
    )

    scan_request = application_settings.to_scan_request()

    assert scan_request.settings == ScanPreset.PHOTO.settings
    assert scan_request.output_format is OutputFormat.JPEG
```

- [ ] **Passo 2: Rodar os testes e ver falhar**

Run: `.venv/bin/pytest tests/domain/test_output_format.py tests/domain/test_scan_preset.py tests/domain/test_application_settings.py -v`
Expected: `3 errors` de coleta; por exemplo `ModuleNotFoundError: No module named 'digitalizadora.domain.output_format'`.

- [ ] **Passo 3: Implementar o mínimo**

Arquivo `src/digitalizadora/domain/output_format.py`:

```python
from enum import Enum


class OutputFormat(str, Enum):
    PDF = "pdf"
    JPEG = "jpg"

    @property
    def file_extension(self) -> str:
        return self.value
```

Arquivo `src/digitalizadora/domain/color_mode.py`:

```python
from enum import Enum


class ColorMode(str, Enum):
    COLOR = "color"
    GRAYSCALE = "grayscale"
```

Arquivo `src/digitalizadora/domain/scan_settings.py`:

```python
from dataclasses import dataclass

from digitalizadora.domain.color_mode import ColorMode


@dataclass(frozen=True)
class ScanSettings:
    dots_per_inch: int
    color_mode: ColorMode
```

Arquivo `src/digitalizadora/domain/scan_preset.py`:

```python
from collections.abc import Mapping
from enum import Enum
from types import MappingProxyType

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.scan_settings import ScanSettings

DOCUMENT_DOTS_PER_INCH = 300
DOCUMENT_ECONOMY_DOTS_PER_INCH = 200
PHOTO_DOTS_PER_INCH = 600


class ScanPreset(str, Enum):
    DOCUMENT = "document"
    DOCUMENT_ECONOMY = "document_economy"
    PHOTO = "photo"

    @property
    def settings(self) -> ScanSettings:
        return SETTINGS_BY_PRESET[self]


SETTINGS_BY_PRESET: Mapping[ScanPreset, ScanSettings] = MappingProxyType(
    {
        ScanPreset.DOCUMENT: ScanSettings(DOCUMENT_DOTS_PER_INCH, ColorMode.COLOR),
        ScanPreset.DOCUMENT_ECONOMY: ScanSettings(
            DOCUMENT_ECONOMY_DOTS_PER_INCH, ColorMode.GRAYSCALE
        ),
        ScanPreset.PHOTO: ScanSettings(PHOTO_DOTS_PER_INCH, ColorMode.COLOR),
    }
)
```

Arquivo `src/digitalizadora/domain/scan_request.py`:

```python
from dataclasses import dataclass

from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_settings import ScanSettings


@dataclass(frozen=True)
class ScanRequest:
    settings: ScanSettings
    output_format: OutputFormat
```

Arquivo `src/digitalizadora/domain/application_settings.py`:

```python
from dataclasses import dataclass
from pathlib import Path

from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_request import ScanRequest


@dataclass(frozen=True)
class ApplicationSettings:
    output_folder: Path
    output_format: OutputFormat
    scan_preset: ScanPreset

    def to_scan_request(self) -> ScanRequest:
        return ScanRequest(settings=self.scan_preset.settings, output_format=self.output_format)
```

- [ ] **Passo 4: Rodar os testes e ver passar**

Run: `.venv/bin/pytest tests/domain/test_output_format.py tests/domain/test_scan_preset.py tests/domain/test_application_settings.py -v`
Expected: `8 passed`

#### Ciclo 2: capacidades e estado do scanner

- [ ] **Passo 5: Escrever os testes que falham**

Os casos de fronteira de `closest_supported_resolution` (suportadas 150, 300, 600): igual, entre duas (um acima e um abaixo de cada limite), abaixo do mínimo, acima do máximo, lista vazia e lista fora de ordem.

Arquivo `tests/domain/test_scanner_capabilities.py`:

```python
import pytest

from digitalizadora.domain.scanner_capabilities import ScannerCapabilities


def build_capabilities(
    resolutions: tuple[int, ...] = (150, 300, 600),
    color_modes: tuple[str, ...] = ("RGB24", "Grayscale8"),
) -> ScannerCapabilities:
    return ScannerCapabilities(
        make_and_model="HP DeskJet 2800 series",
        platen_maximum_width=2550,
        platen_maximum_height=3507,
        supported_resolutions=resolutions,
        supported_color_modes=color_modes,
        supported_document_formats=("image/jpeg",),
    )


@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        (300, 300),
        (200, 300),
        (150, 150),
        (100, 150),
        (1, 150),
        (151, 300),
        (299, 300),
        (301, 600),
        (600, 600),
        (601, 600),
        (1200, 600),
    ],
)
def test_closest_supported_resolution(requested: int, expected: int) -> None:
    assert build_capabilities().closest_supported_resolution(requested) == expected


def test_closest_supported_resolution_returns_request_when_scanner_lists_none() -> None:
    assert build_capabilities(resolutions=()).closest_supported_resolution(250) == 250


def test_closest_supported_resolution_does_not_depend_on_list_order() -> None:
    capabilities = build_capabilities(resolutions=(600, 150, 300))

    assert capabilities.closest_supported_resolution(200) == 300


@pytest.mark.parametrize(
    ("escl_color_mode", "expected"),
    [
        ("RGB24", True),
        ("Grayscale8", True),
        ("BlackAndWhite1", False),
        ("rgb24", False),
        ("", False),
    ],
)
def test_supports_color_mode(escl_color_mode: str, expected: bool) -> None:
    assert build_capabilities().supports_color_mode(escl_color_mode) is expected


def test_supports_color_mode_is_false_when_scanner_lists_none() -> None:
    assert build_capabilities(color_modes=()).supports_color_mode("RGB24") is False
```

Arquivo `tests/domain/test_scanner_status.py`:

```python
import pytest

from digitalizadora.domain.scanner_status import ScannerState, ScannerStatus


def test_status_is_ready_when_idle() -> None:
    assert ScannerStatus(ScannerState.IDLE).is_ready is True


@pytest.mark.parametrize(
    "state",
    [state for state in ScannerState if state is not ScannerState.IDLE],
)
def test_status_is_not_ready_in_any_other_state(state: ScannerState) -> None:
    assert ScannerStatus(state).is_ready is False
```

- [ ] **Passo 6: Rodar os testes e ver falhar**

Run: `.venv/bin/pytest tests/domain/test_scanner_capabilities.py tests/domain/test_scanner_status.py -v`
Expected: `2 errors`; `ModuleNotFoundError: No module named 'digitalizadora.domain.scanner_capabilities'`.

- [ ] **Passo 7: Implementar o mínimo**

Arquivo `src/digitalizadora/domain/scanner_capabilities.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ScannerCapabilities:
    make_and_model: str
    platen_maximum_width: int
    platen_maximum_height: int
    supported_resolutions: tuple[int, ...]
    supported_color_modes: tuple[str, ...]
    supported_document_formats: tuple[str, ...]

    def closest_supported_resolution(self, requested_dots_per_inch: int) -> int:
        if not self.supported_resolutions:
            return requested_dots_per_inch
        sufficient_resolutions = [
            resolution
            for resolution in self.supported_resolutions
            if resolution >= requested_dots_per_inch
        ]
        if sufficient_resolutions:
            return min(sufficient_resolutions)
        return max(self.supported_resolutions)

    def supports_color_mode(self, escl_color_mode: str) -> bool:
        return escl_color_mode in self.supported_color_modes
```

Arquivo `src/digitalizadora/domain/scanner_status.py`:

```python
from dataclasses import dataclass
from enum import Enum


class ScannerState(str, Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    TESTING = "testing"
    STOPPED = "stopped"
    DOWN = "down"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ScannerStatus:
    state: ScannerState

    @property
    def is_ready(self) -> bool:
        return self.state is ScannerState.IDLE
```

- [ ] **Passo 8: Rodar os testes e ver passar**

Run: `.venv/bin/pytest tests/domain/test_scanner_capabilities.py tests/domain/test_scanner_status.py -v`
Expected: `25 passed`

#### Ciclo 3: erros e política de nomes de arquivo

- [ ] **Passo 9: Escrever os testes que falham**

A política de nomes cobre o modo de falha 5 do design (colisão de nomes): o número de sequência nunca é truncado (99999 e 100000), e um arquivo `.part` de gravação interrompida nunca é confundido com um arquivo final.

Arquivo `tests/domain/test_errors.py`:

```python
import pytest

from digitalizadora.domain import errors


@pytest.mark.parametrize(
    ("error_class", "expected_code"),
    [
        (errors.DigitalizadoraError, "unexpected_error"),
        (errors.ScannerUnreachableError, "scanner_unreachable"),
        (errors.LocalNetworkBlockedError, "local_network_blocked"),
        (errors.ScannerBusyError, "scanner_busy"),
        (errors.ScanRejectedError, "scan_rejected"),
        (errors.ScanFailedError, "scan_failed"),
        (errors.ScanTimedOutError, "scan_timed_out"),
        (errors.ScanAlreadyRunningError, "scan_already_running"),
        (errors.InsufficientStorageError, "insufficient_storage"),
        (errors.OutputFolderUnavailableError, "output_folder_unavailable"),
        (errors.InvalidSettingsError, "invalid_settings"),
    ],
)
def test_error_class_exposes_its_code(
    error_class: type[errors.DigitalizadoraError], expected_code: str
) -> None:
    assert error_class("internal detail").code == expected_code


def test_local_network_blocked_is_a_scanner_unreachable_error() -> None:
    assert issubclass(errors.LocalNetworkBlockedError, errors.ScannerUnreachableError)


def test_every_error_derives_from_the_base_error() -> None:
    error_classes = [
        value
        for value in vars(errors).values()
        if isinstance(value, type) and issubclass(value, Exception)
    ]

    assert all(issubclass(error_class, errors.DigitalizadoraError) for error_class in error_classes)
```

Arquivo `tests/domain/test_scan_file_naming_policy.py`:

```python
from datetime import datetime, timedelta, timezone

import pytest

from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_file_naming_policy import ScanFileNamingPolicy

SCANNED_AT = datetime(2026, 10, 13, 15, 30, 12, tzinfo=timezone(timedelta(hours=-3)))
OTHER_DAY = datetime(2026, 10, 14, 0, 0, 1, tzinfo=timezone(timedelta(hours=-3)))


@pytest.mark.parametrize(
    ("sequence_number", "output_format", "expected_name"),
    [
        (7, OutputFormat.PDF, "2026-10-13_00007.pdf"),
        (7, OutputFormat.JPEG, "2026-10-13_00007.jpg"),
        (1, OutputFormat.PDF, "2026-10-13_00001.pdf"),
        (99999, OutputFormat.PDF, "2026-10-13_99999.pdf"),
        (100000, OutputFormat.PDF, "2026-10-13_100000.pdf"),
    ],
)
def test_build_file_name(
    sequence_number: int, output_format: OutputFormat, expected_name: str
) -> None:
    policy = ScanFileNamingPolicy()

    assert policy.build_file_name(SCANNED_AT, sequence_number, output_format) == expected_name


@pytest.mark.parametrize(
    ("file_name", "expected_sequence_number"),
    [
        ("2026-10-13_00007.pdf", 7),
        ("2026-10-13_00007.jpg", 7),
        ("2026-10-13_00001.pdf", 1),
        ("2026-10-13_99999.jpg", 99999),
        ("2026-10-13_100000.pdf", 100000),
    ],
)
def test_extract_sequence_number_of_a_name_from_the_same_day(
    file_name: str, expected_sequence_number: int
) -> None:
    assert ScanFileNamingPolicy().extract_sequence_number(file_name, SCANNED_AT) == (
        expected_sequence_number
    )


def test_extract_sequence_number_ignores_a_name_from_another_date() -> None:
    assert ScanFileNamingPolicy().extract_sequence_number("2026-10-13_00007.pdf", OTHER_DAY) is None


@pytest.mark.parametrize(
    "file_name",
    [
        "notes.txt",
        "",
        "2026-10-13_00007.png",
        "2026-10-13_00007.pdf.part",
        "2026-10-13_00007",
        "2026-10-13_0007.pdf",
        "2026-10-13_00000.pdf",
        "2026-10-13_abcde.pdf",
        "x2026-10-13_00007.pdf",
    ],
)
def test_extract_sequence_number_rejects_names_outside_the_pattern(file_name: str) -> None:
    assert ScanFileNamingPolicy().extract_sequence_number(file_name, SCANNED_AT) is None
```

- [ ] **Passo 10: Rodar os testes e ver falhar**

Run: `.venv/bin/pytest tests/domain/test_errors.py tests/domain/test_scan_file_naming_policy.py -v`
Expected: `2 errors`; `ImportError: cannot import name 'errors' from 'digitalizadora.domain'` e `ModuleNotFoundError: No module named 'digitalizadora.domain.scan_file_naming_policy'`.

- [ ] **Passo 11: Implementar o mínimo**

Arquivo `src/digitalizadora/domain/errors.py`:

```python
class DigitalizadoraError(Exception):
    code = "unexpected_error"


class ScannerUnreachableError(DigitalizadoraError):
    code = "scanner_unreachable"


class LocalNetworkBlockedError(ScannerUnreachableError):
    code = "local_network_blocked"


class ScannerBusyError(DigitalizadoraError):
    code = "scanner_busy"


class ScanRejectedError(DigitalizadoraError):
    code = "scan_rejected"


class ScanFailedError(DigitalizadoraError):
    code = "scan_failed"


class ScanTimedOutError(DigitalizadoraError):
    code = "scan_timed_out"


class ScanAlreadyRunningError(DigitalizadoraError):
    code = "scan_already_running"


class InsufficientStorageError(DigitalizadoraError):
    code = "insufficient_storage"


class OutputFolderUnavailableError(DigitalizadoraError):
    code = "output_folder_unavailable"


class InvalidSettingsError(DigitalizadoraError):
    code = "invalid_settings"
```

Arquivo `src/digitalizadora/domain/scan_file_naming_policy.py`:

```python
import re
from datetime import datetime

from digitalizadora.domain.output_format import OutputFormat

DATE_FORMAT = "%Y-%m-%d"
SEQUENCE_NUMBER_MINIMUM_DIGITS = 5
FIRST_SEQUENCE_NUMBER = 1
FILE_EXTENSIONS_PATTERN = "|".join(
    re.escape(output_format.file_extension) for output_format in OutputFormat
)


class ScanFileNamingPolicy:
    def build_file_name(
        self, scanned_at: datetime, sequence_number: int, output_format: OutputFormat
    ) -> str:
        date_text = scanned_at.strftime(DATE_FORMAT)
        padded_sequence = f"{sequence_number:0{SEQUENCE_NUMBER_MINIMUM_DIGITS}d}"
        return f"{date_text}_{padded_sequence}.{output_format.file_extension}"

    def extract_sequence_number(self, file_name: str, scanned_at: datetime) -> int | None:
        date_text = re.escape(scanned_at.strftime(DATE_FORMAT))
        pattern = (
            rf"{date_text}_([0-9]{{{SEQUENCE_NUMBER_MINIMUM_DIGITS},}})"
            rf"\.(?:{FILE_EXTENSIONS_PATTERN})"
        )
        match = re.fullmatch(pattern, file_name)
        if match is None:
            return None
        sequence_number = int(match.group(1))
        if sequence_number < FIRST_SEQUENCE_NUMBER:
            return None
        return sequence_number
```

- [ ] **Passo 12: Rodar os testes e ver passar**

Run: `.venv/bin/pytest tests/domain/test_errors.py tests/domain/test_scan_file_naming_policy.py -v`
Expected: `33 passed`

#### Ciclo 4: demais modelos imutáveis e portas

- [ ] **Passo 13: Escrever os testes que falham**

Arquivo `tests/domain/test_immutable_models.py`:

```python
import dataclasses
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.encoded_scan import EncodedScan
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_job import ScanJob
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_progress import ScanPhase, ScanProgressSnapshot
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.domain.scanner_capabilities import ScannerCapabilities
from digitalizadora.domain.scanner_endpoint import ScannerEndpoint
from digitalizadora.domain.scanner_status import ScannerState, ScannerStatus
from digitalizadora.domain.stored_scan import StoredScan

MOMENT = datetime(2026, 10, 13, 15, 30, 12, tzinfo=timezone(timedelta(hours=-3)))
SETTINGS = ScanSettings(dots_per_inch=300, color_mode=ColorMode.COLOR)
REQUEST = ScanRequest(settings=SETTINGS, output_format=OutputFormat.PDF)
RESULT = ScanResult(
    output_path=Path("/tmp/scan.pdf"),
    output_format=OutputFormat.PDF,
    scanned_at=MOMENT,
    size_in_bytes=10,
)
MODELS = [
    SETTINGS,
    REQUEST,
    ScanJob(request=REQUEST, started_at=MOMENT),
    ScannerEndpoint(base_address="http://192.168.0.40:8080/eSCL", display_name="HP"),
    ScannerCapabilities("HP", 2550, 3507, (300,), ("RGB24",), ("image/jpeg",)),
    ScannerStatus(ScannerState.IDLE),
    ScannedImage(content=b"\xff\xd8", media_type="image/jpeg"),
    EncodedScan(b"x", OutputFormat.JPEG, MOMENT, b"t"),
    RESULT,
    StoredScan(result=RESULT, thumbnail_jpeg=b"t"),
    ApplicationSettings(Path("/tmp"), OutputFormat.PDF, ScanPreset.DOCUMENT),
    ScanProgressSnapshot(ScanPhase.IDLE, 0, None, None),
]


@pytest.mark.parametrize("model", MODELS, ids=lambda model: type(model).__name__)
def test_domain_model_is_immutable(model: object) -> None:
    first_field_name = dataclasses.fields(model)[0].name

    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(model, first_field_name, None)


def test_scanner_endpoint_identifier_is_optional() -> None:
    endpoint = ScannerEndpoint(base_address="http://192.168.0.40:8080/eSCL", display_name="HP")

    assert endpoint.universally_unique_identifier is None
```

Arquivo `tests/domain/test_ports.py`:

```python
import inspect
from typing import Protocol

from digitalizadora.domain import ports

EXPECTED_PORT_NAMES = {
    "Clock",
    "ScannerGateway",
    "ScannerGatewayProvider",
    "ScannerDiscovery",
    "ScannerEndpointRepository",
    "ApplicationSettingsRepository",
    "ScanOutputRepository",
}


def defined_classes() -> dict[str, type]:
    return {
        name: member
        for name, member in inspect.getmembers(ports, inspect.isclass)
        if member.__module__ == ports.__name__
    }


def test_ports_module_defines_exactly_the_contract_ports() -> None:
    assert set(defined_classes()) == EXPECTED_PORT_NAMES


def test_every_port_is_a_protocol() -> None:
    assert all(Protocol in port.__bases__ for port in defined_classes().values())
```

- [ ] **Passo 14: Rodar os testes e ver falhar**

Run: `.venv/bin/pytest tests/domain/test_immutable_models.py tests/domain/test_ports.py -v`
Expected: `2 errors`; `ModuleNotFoundError: No module named 'digitalizadora.domain.encoded_scan'` e `ImportError: cannot import name 'ports' from 'digitalizadora.domain'`.

- [ ] **Passo 15: Implementar o mínimo**

Arquivo `src/digitalizadora/domain/scan_job.py`:

```python
from dataclasses import dataclass
from datetime import datetime

from digitalizadora.domain.scan_request import ScanRequest


@dataclass(frozen=True)
class ScanJob:
    request: ScanRequest
    started_at: datetime
```

Arquivo `src/digitalizadora/domain/scanner_endpoint.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ScannerEndpoint:
    base_address: str
    display_name: str
    universally_unique_identifier: str | None = None
```

Arquivo `src/digitalizadora/domain/scanned_image.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ScannedImage:
    content: bytes
    media_type: str
```

Arquivo `src/digitalizadora/domain/encoded_scan.py`:

```python
from dataclasses import dataclass
from datetime import datetime

from digitalizadora.domain.output_format import OutputFormat


@dataclass(frozen=True)
class EncodedScan:
    content: bytes
    output_format: OutputFormat
    created_at: datetime
    thumbnail_jpeg: bytes
```

Arquivo `src/digitalizadora/domain/scan_result.py`:

```python
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from digitalizadora.domain.output_format import OutputFormat


@dataclass(frozen=True)
class ScanResult:
    output_path: Path
    output_format: OutputFormat
    scanned_at: datetime
    size_in_bytes: int
```

Arquivo `src/digitalizadora/domain/stored_scan.py`:

```python
from dataclasses import dataclass

from digitalizadora.domain.scan_result import ScanResult


@dataclass(frozen=True)
class StoredScan:
    result: ScanResult
    thumbnail_jpeg: bytes
```

Arquivo `src/digitalizadora/domain/scan_progress.py`:

```python
from dataclasses import dataclass
from enum import Enum

from digitalizadora.domain.scan_result import ScanResult


class ScanPhase(str, Enum):
    IDLE = "idle"
    PREPARING = "preparing"
    SCANNING = "scanning"
    SAVING = "saving"


@dataclass(frozen=True)
class ScanProgressSnapshot:
    phase: ScanPhase
    scans_completed: int
    last_result: ScanResult | None
    last_error_code: str | None
```

Arquivo `src/digitalizadora/domain/ports.py` (somente as definições `Protocol` da seção 6.1; nenhuma implementação):

```python
from datetime import datetime
from pathlib import Path
from typing import Protocol

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.encoded_scan import EncodedScan
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.domain.scanner_capabilities import ScannerCapabilities
from digitalizadora.domain.scanner_endpoint import ScannerEndpoint
from digitalizadora.domain.scanner_status import ScannerStatus


class Clock(Protocol):
    def now(self) -> datetime: ...


class ScannerGateway(Protocol):
    async def read_capabilities(self) -> ScannerCapabilities: ...

    async def read_status(self) -> ScannerStatus: ...

    async def scan_page(self, settings: ScanSettings) -> ScannedImage: ...


class ScannerGatewayProvider(Protocol):
    async def acquire_gateway(self) -> ScannerGateway: ...


class ScannerDiscovery(Protocol):
    async def discover(self, timeout_seconds: float) -> list[ScannerEndpoint]: ...


class ScannerEndpointRepository(Protocol):
    def load(self) -> ScannerEndpoint | None: ...

    def save(self, endpoint: ScannerEndpoint) -> None: ...

    def clear(self) -> None: ...


class ApplicationSettingsRepository(Protocol):
    def load(self) -> ApplicationSettings: ...

    def save(self, settings: ApplicationSettings) -> None: ...


class ScanOutputRepository(Protocol):
    def output_folder(self) -> Path: ...

    def save(self, encoded_scan: EncodedScan) -> Path: ...
```

- [ ] **Passo 16: Rodar os testes e ver passar**

Run: `.venv/bin/pytest tests/domain/test_immutable_models.py tests/domain/test_ports.py -v`
Expected: `15 passed`

#### Ciclo 5: relógio do sistema e dublês de teste

- [ ] **Passo 17: Escrever os testes que falham**

Arquivo `tests/infrastructure/test_system_clock.py`:

```python
from datetime import UTC, datetime, timedelta

from digitalizadora.infrastructure.system_clock import SystemClock

MAXIMUM_CLOCK_DIFFERENCE = timedelta(seconds=5)


def test_now_is_timezone_aware() -> None:
    assert SystemClock().now().utcoffset() is not None


def test_now_is_the_current_moment() -> None:
    difference = abs(SystemClock().now() - datetime.now(UTC))

    assert difference < MAXIMUM_CLOCK_DIFFERENCE
```

Arquivo `tests/fakes/test_fixed_clock.py`:

```python
from datetime import datetime, timedelta, timezone

from tests.fakes.fixed_clock import FixedClock

MOMENT = datetime(2026, 10, 13, 15, 30, 12, tzinfo=timezone(timedelta(hours=-3)))


def test_now_returns_the_given_moment_until_advanced() -> None:
    clock = FixedClock(MOMENT)

    assert clock.now() == MOMENT
    assert clock.now() == MOMENT


def test_advance_moves_time_forward_by_the_given_seconds() -> None:
    clock = FixedClock(MOMENT)

    clock.advance(90.5)

    assert clock.now() == MOMENT + timedelta(seconds=90.5)


def test_advance_accumulates() -> None:
    clock = FixedClock(MOMENT)

    clock.advance(1)
    clock.advance(2)

    assert clock.now() == MOMENT + timedelta(seconds=3)
```

Arquivo `tests/fakes/test_sample_images.py`:

```python
import io

from PIL import Image

from tests.fakes.sample_images import build_sample_jpeg

JPEG_START_OF_IMAGE = b"\xff\xd8"


def open_image(content: bytes) -> Image.Image:
    return Image.open(io.BytesIO(content))


def test_sample_is_a_decodable_jpeg_with_the_default_size() -> None:
    content = build_sample_jpeg()

    assert content.startswith(JPEG_START_OF_IMAGE)
    assert open_image(content).size == (64, 48)


def test_sample_uses_the_requested_size() -> None:
    assert open_image(build_sample_jpeg(width_pixels=10, height_pixels=20)).size == (10, 20)


def test_sample_with_a_single_pixel_is_valid() -> None:
    assert open_image(build_sample_jpeg(width_pixels=1, height_pixels=1)).size == (1, 1)


def test_sample_writes_the_requested_density() -> None:
    image = open_image(build_sample_jpeg(dots_per_inch=300))

    assert image.info["dpi"] == (300, 300)


def test_sample_without_density_has_no_dots_per_inch() -> None:
    assert "dpi" not in open_image(build_sample_jpeg()).info


def test_sample_is_not_a_flat_color() -> None:
    image = open_image(build_sample_jpeg()).convert("RGB")

    assert image.getpixel((0, 0)) != image.getpixel((63, 47))
```

- [ ] **Passo 18: Rodar os testes e ver falhar**

Run: `.venv/bin/pytest tests/infrastructure/test_system_clock.py tests/fakes/test_fixed_clock.py tests/fakes/test_sample_images.py -v`
Expected: `3 errors`; `ModuleNotFoundError: No module named 'digitalizadora.infrastructure.system_clock'` e `ModuleNotFoundError: No module named 'tests.fakes.fixed_clock'`.

- [ ] **Passo 19: Implementar o mínimo**

Arquivo `src/digitalizadora/infrastructure/system_clock.py`:

```python
from datetime import datetime


class SystemClock:
    def now(self) -> datetime:
        return datetime.now().astimezone()
```

Arquivo `tests/fakes/fixed_clock.py`:

```python
from datetime import datetime, timedelta


class FixedClock:
    def __init__(self, moment: datetime) -> None:
        self._moment = moment

    def now(self) -> datetime:
        return self._moment

    def advance(self, seconds: float) -> None:
        self._moment = self._moment + timedelta(seconds=seconds)
```

Arquivo `tests/fakes/sample_images.py` (gradiente horizontal no vermelho e vertical no verde, para o JPEG não ser trivialmente pequeno; sem `dots_per_inch` o JFIF fica com a densidade padrão do libjpeg, sem unidade, que é o caso "sem densidade" usado pelos testes da Task 6):

```python
import io

from PIL import Image

JPEG_QUALITY = 85
CHANNEL_MAXIMUM = 255


def build_sample_jpeg(
    width_pixels: int = 64,
    height_pixels: int = 48,
    dots_per_inch: int | None = None,
) -> bytes:
    size = (width_pixels, height_pixels)
    horizontal_ramp = [
        round(column * CHANNEL_MAXIMUM / max(width_pixels - 1, 1)) for column in range(width_pixels)
    ]
    vertical_ramp = [
        round(row * CHANNEL_MAXIMUM / max(height_pixels - 1, 1)) for row in range(height_pixels)
    ]
    red_channel = Image.frombytes("L", size, bytes(horizontal_ramp) * height_pixels)
    green_channel = Image.frombytes(
        "L", size, b"".join(bytes([level]) * width_pixels for level in vertical_ramp)
    )
    blue_channel = Image.new("L", size, CHANNEL_MAXIMUM // 2)
    image = Image.merge("RGB", (red_channel, green_channel, blue_channel))
    save_options: dict[str, object] = {"quality": JPEG_QUALITY}
    if dots_per_inch is not None:
        save_options["dpi"] = (dots_per_inch, dots_per_inch)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", **save_options)
    return buffer.getvalue()
```

- [ ] **Passo 20: Rodar os testes e ver passar**

Run: `.venv/bin/pytest tests/infrastructure/test_system_clock.py tests/fakes/test_fixed_clock.py tests/fakes/test_sample_images.py -v`
Expected: `11 passed`

#### Fechamento

- [ ] **Passo 21: Rodar a suíte inteira e o lint**

Run: `.venv/bin/pytest -q`
Expected: `100 passed` (8 da Task 1 e 92 desta task), cada teste abaixo de 100 ms.

Run: `.venv/bin/ruff check src tests`
Expected: `All checks passed!`

- [ ] **Passo 22: Commit**

```bash
git add src/digitalizadora/domain src/digitalizadora/infrastructure/system_clock.py \
  tests/domain tests/infrastructure/test_system_clock.py tests/fakes
git commit -m "feat: add domain models, errors, naming policy, ports and system clock"
```

### Task 3: Funções do protocolo eSCL e fixtures XML

**Objetivo:** Escrever as quatro funções puras que montam e interpretam os documentos eSCL (`build_scan_settings_xml`, `parse_scanner_capabilities`, `parse_scanner_status`, `extract_job_path`) e as fixtures XML usadas pelos testes.

**Files:**
- Create: `src/digitalizadora/infrastructure/escl/escl_protocol.py`
- Create: `tests/fixtures/escl/scanner-capabilities-hp-deskjet-2800.xml`
- Create: `tests/fixtures/escl/scanner-status-idle.xml`
- Create: `tests/fixtures/escl/scanner-status-processing.xml`
- Create: `tests/fakes/fixture_files.py`
- Test: `tests/infrastructure/test_escl_protocol.py`

**Interfaces:**
- Consumes (Task 2): `ScanSettings(dots_per_inch, color_mode)`, `ColorMode`, `ScannerCapabilities` (com `closest_supported_resolution` e `supports_color_mode`), `ScannerStatus`, `ScannerState`, `ScanFailedError`, `ScanRejectedError`.
- Produces (módulo `digitalizadora.infrastructure.escl.escl_protocol`):
  - `ESCL_UNITS_PER_INCH = 300`
  - `build_scan_settings_xml(settings: ScanSettings, capabilities: ScannerCapabilities) -> bytes` (uma linha, declaração XML, dois namespaces, ordem canônica; `ScanRejectedError` se faltar o modo de cor ou `image/jpeg`)
  - `parse_scanner_capabilities(document: bytes) -> ScannerCapabilities` (`ScanFailedError` para XML inválido, documento de outro tipo, vidro ausente, medida inválida ou `<!ENTITY`)
  - `parse_scanner_status(document: bytes) -> ScannerStatus` (estado desconhecido vira `ScannerState.UNKNOWN`)
  - `extract_job_path(location_header: str) -> str` (só o caminho; `ScanFailedError` se vazio)
  - `tests.fakes.fixture_files.read_escl_fixture(file_name: str) -> bytes`
  - As fixtures `tests/fixtures/escl/*.xml`, **sintéticas** até o Gate 0 fornecer a captura real.

Decisões de formato (conferidas no fonte do sane-airscan `airscan-escl.c` e `airscan-xml.c`, e no `EsclClient.cs` do NAPS2): prefixos `pwg` e `scan` declarados no elemento raiz nessa ordem; `pwg:Version`, `pwg:ScanRegions` (com `pwg:ScanRegion`: `pwg:ContentRegionUnits`, `pwg:XOffset`, `pwg:YOffset`, `pwg:Width`, `pwg:Height`), `pwg:InputSource`, `scan:ColorMode`, `pwg:DocumentFormat`, `scan:XResolution`, `scan:YResolution`; o texto literal `escl:ThreeHundredthsOfInches` sem declarar o prefixo `escl`; declaração `<?xml version="1.0" encoding="UTF-8"?>` colada ao elemento raiz, como o sane-airscan faz no modo compacto. É o mesmo texto que `scripts/probe-printer.sh` (Task 0) envia à impressora real.

- [ ] **Passo 1: Criar as fixtures XML e o leitor de fixtures**

Estes arquivos são dados de teste (sem comportamento próprio). O leitor é exercitado pelos testes do Passo 3.

Arquivo `tests/fixtures/escl/scanner-capabilities-hp-deskjet-2800.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!-- SYNTHETIC fixture: hand-written to match the structure of eSCL 2.x capability documents
     (element names checked against sane-airscan airscan-escl.c and the NAPS2 EsclClient source).
     It is NOT a capture from the real printer. Gate 0 (docs/spike-0) replaces it with the real
     ScannerCapabilities capture. Printer identifiers below are fake. -->
<scan:ScannerCapabilities xmlns:pwg="http://www.pwg.org/schemas/2010/12/sm" xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03">
  <pwg:Version>2.63</pwg:Version>
  <pwg:MakeAndModel>HP DeskJet 2800 series</pwg:MakeAndModel>
  <pwg:SerialNumber>SYNTHETIC0001</pwg:SerialNumber>
  <scan:Manufacturer>HP</scan:Manufacturer>
  <scan:UUID>00000000-0000-0000-0000-000000000000</scan:UUID>
  <scan:AdminURI>http://printer.example.invalid/</scan:AdminURI>
  <scan:Platen>
    <scan:PlatenInputCaps>
      <scan:MinWidth>16</scan:MinWidth>
      <scan:MaxWidth>2550</scan:MaxWidth>
      <scan:MinHeight>16</scan:MinHeight>
      <scan:MaxHeight>3507</scan:MaxHeight>
      <scan:MaxScanRegions>1</scan:MaxScanRegions>
      <scan:SettingProfiles>
        <scan:SettingProfile>
          <scan:ColorModes>
            <scan:ColorMode>BlackAndWhite1</scan:ColorMode>
            <scan:ColorMode>Grayscale8</scan:ColorMode>
            <scan:ColorMode>RGB24</scan:ColorMode>
          </scan:ColorModes>
          <scan:ContentTypes>
            <pwg:ContentType>Photo</pwg:ContentType>
            <pwg:ContentType>Text</pwg:ContentType>
          </scan:ContentTypes>
          <scan:DocumentFormats>
            <pwg:DocumentFormat>application/pdf</pwg:DocumentFormat>
            <pwg:DocumentFormat>image/jpeg</pwg:DocumentFormat>
            <scan:DocumentFormatExt>application/pdf</scan:DocumentFormatExt>
            <scan:DocumentFormatExt>image/jpeg</scan:DocumentFormatExt>
          </scan:DocumentFormats>
          <scan:SupportedResolutions>
            <scan:DiscreteResolutions>
              <scan:DiscreteResolution>
                <scan:XResolution>75</scan:XResolution>
                <scan:YResolution>75</scan:YResolution>
              </scan:DiscreteResolution>
              <scan:DiscreteResolution>
                <scan:XResolution>100</scan:XResolution>
                <scan:YResolution>100</scan:YResolution>
              </scan:DiscreteResolution>
              <scan:DiscreteResolution>
                <scan:XResolution>150</scan:XResolution>
                <scan:YResolution>150</scan:YResolution>
              </scan:DiscreteResolution>
              <scan:DiscreteResolution>
                <scan:XResolution>200</scan:XResolution>
                <scan:YResolution>200</scan:YResolution>
              </scan:DiscreteResolution>
              <scan:DiscreteResolution>
                <scan:XResolution>300</scan:XResolution>
                <scan:YResolution>300</scan:YResolution>
              </scan:DiscreteResolution>
              <scan:DiscreteResolution>
                <scan:XResolution>600</scan:XResolution>
                <scan:YResolution>600</scan:YResolution>
              </scan:DiscreteResolution>
              <scan:DiscreteResolution>
                <scan:XResolution>1200</scan:XResolution>
                <scan:YResolution>1200</scan:YResolution>
              </scan:DiscreteResolution>
            </scan:DiscreteResolutions>
          </scan:SupportedResolutions>
        </scan:SettingProfile>
      </scan:SettingProfiles>
      <scan:SupportedIntents>
        <scan:Intent>Document</scan:Intent>
        <scan:Intent>Photo</scan:Intent>
        <scan:Intent>Preview</scan:Intent>
      </scan:SupportedIntents>
    </scan:PlatenInputCaps>
  </scan:Platen>
</scan:ScannerCapabilities>
```

Arquivo `tests/fixtures/escl/scanner-status-idle.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!-- SYNTHETIC fixture: structure follows eSCL 2.x ScannerStatus documents; replace with the real
     ScannerStatus capture of Gate 0 (docs/spike-0). -->
<scan:ScannerStatus xmlns:pwg="http://www.pwg.org/schemas/2010/12/sm" xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03">
  <pwg:Version>2.63</pwg:Version>
  <pwg:State>Idle</pwg:State>
</scan:ScannerStatus>
```

Arquivo `tests/fixtures/escl/scanner-status-processing.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!-- SYNTHETIC fixture: structure follows eSCL 2.x ScannerStatus documents; replace with the real
     ScannerStatus capture of Gate 0 (docs/spike-0). -->
<scan:ScannerStatus xmlns:pwg="http://www.pwg.org/schemas/2010/12/sm" xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03">
  <pwg:Version>2.63</pwg:Version>
  <pwg:State>Processing</pwg:State>
  <scan:Jobs>
    <scan:JobInfo>
      <pwg:JobUri>/eSCL/ScanJobs/1</pwg:JobUri>
      <pwg:JobState>Processing</pwg:JobState>
    </scan:JobInfo>
  </scan:Jobs>
</scan:ScannerStatus>
```

Arquivo `tests/fakes/fixture_files.py`:

```python
from pathlib import Path

ESCL_FIXTURE_FOLDER = Path(__file__).resolve().parent.parent / "fixtures" / "escl"


def read_escl_fixture(file_name: str) -> bytes:
    return (ESCL_FIXTURE_FOLDER / file_name).read_bytes()
```

#### Ciclo 1: capacidades do scanner

- [ ] **Passo 2: Escrever os testes que falham**

Arquivo `tests/infrastructure/test_escl_protocol.py`:

```python
import pytest

from digitalizadora.domain.errors import ScanFailedError
from digitalizadora.domain.scanner_capabilities import ScannerCapabilities
from digitalizadora.infrastructure.escl.escl_protocol import (
    ESCL_UNITS_PER_INCH,
    parse_scanner_capabilities,
)
from tests.fakes.fixture_files import read_escl_fixture

CAPABILITIES_FIXTURE = "scanner-capabilities-hp-deskjet-2800.xml"
CAPABILITIES_WITH_OTHER_PREFIXES = b"""<?xml version="1.0"?>
<a:ScannerCapabilities xmlns:a="http://schemas.hp.com/imaging/escl/2011/05/03"
    xmlns:b="http://www.pwg.org/schemas/2010/12/sm">
  <b:MakeAndModel>Other Brand</b:MakeAndModel>
  <a:Platen><a:PlatenInputCaps>
    <a:MaxWidth>1000</a:MaxWidth><a:MaxHeight>2000</a:MaxHeight>
    <a:SettingProfiles><a:SettingProfile>
      <a:ColorModes><a:ColorMode>RGB24</a:ColorMode></a:ColorModes>
      <a:DocumentFormats><b:DocumentFormat>image/jpeg</b:DocumentFormat></a:DocumentFormats>
      <a:SupportedResolutions><a:DiscreteResolutions>
        <a:DiscreteResolution><a:XResolution>600</a:XResolution></a:DiscreteResolution>
        <a:DiscreteResolution><a:XResolution>300</a:XResolution></a:DiscreteResolution>
      </a:DiscreteResolutions></a:SupportedResolutions>
    </a:SettingProfile></a:SettingProfiles>
  </a:PlatenInputCaps></a:Platen>
</a:ScannerCapabilities>"""


def load_capabilities() -> ScannerCapabilities:
    return parse_scanner_capabilities(read_escl_fixture(CAPABILITIES_FIXTURE))


def test_capabilities_fixture_reports_the_model() -> None:
    assert load_capabilities().make_and_model == "HP DeskJet 2800 series"


def test_capabilities_fixture_reports_the_platen_size_in_escl_units() -> None:
    capabilities = load_capabilities()

    assert (capabilities.platen_maximum_width, capabilities.platen_maximum_height) == (2550, 3507)


def test_capabilities_fixture_reports_resolutions_in_ascending_order() -> None:
    assert load_capabilities().supported_resolutions == (75, 100, 150, 200, 300, 600, 1200)


def test_capabilities_fixture_reports_color_modes() -> None:
    expected_color_modes = ("BlackAndWhite1", "Grayscale8", "RGB24")

    assert load_capabilities().supported_color_modes == expected_color_modes


def test_capabilities_fixture_reports_document_formats_without_duplicates() -> None:
    expected_formats = ("application/pdf", "image/jpeg")

    assert load_capabilities().supported_document_formats == expected_formats


def test_capabilities_parse_ignores_namespace_prefixes_and_sorts_resolutions() -> None:
    capabilities = parse_scanner_capabilities(CAPABILITIES_WITH_OTHER_PREFIXES)

    assert capabilities == ScannerCapabilities(
        make_and_model="Other Brand",
        platen_maximum_width=1000,
        platen_maximum_height=2000,
        supported_resolutions=(300, 600),
        supported_color_modes=("RGB24",),
        supported_document_formats=("image/jpeg",),
    )


def test_capabilities_parse_rejects_malformed_xml() -> None:
    with pytest.raises(ScanFailedError, match="not valid XML"):
        parse_scanner_capabilities(b"<ScannerCapabilities><unclosed>")


def test_capabilities_parse_rejects_an_empty_document() -> None:
    with pytest.raises(ScanFailedError, match="not valid XML"):
        parse_scanner_capabilities(b"")


def test_capabilities_parse_rejects_a_document_of_another_kind() -> None:
    with pytest.raises(ScanFailedError, match="ScannerCapabilities"):
        parse_scanner_capabilities(b"<ScannerStatus/>")


def test_capabilities_parse_rejects_missing_platen_capabilities() -> None:
    document = b"<ScannerCapabilities><MakeAndModel>X</MakeAndModel></ScannerCapabilities>"

    with pytest.raises(ScanFailedError, match="platen"):
        parse_scanner_capabilities(document)


def test_capabilities_parse_rejects_a_platen_without_maximum_width() -> None:
    document = b"<ScannerCapabilities><Platen><PlatenInputCaps/></Platen></ScannerCapabilities>"

    with pytest.raises(ScanFailedError, match="MaxWidth"):
        parse_scanner_capabilities(document)


def test_capabilities_parse_rejects_a_non_numeric_maximum_width() -> None:
    document = (
        b"<ScannerCapabilities><Platen><PlatenInputCaps><MaxWidth>wide</MaxWidth>"
        b"</PlatenInputCaps></Platen></ScannerCapabilities>"
    )

    with pytest.raises(ScanFailedError, match="MaxWidth"):
        parse_scanner_capabilities(document)


def test_units_per_inch_is_three_hundred() -> None:
    assert ESCL_UNITS_PER_INCH == 300
```

- [ ] **Passo 3: Rodar os testes e ver falhar**

Run: `.venv/bin/pytest tests/infrastructure/test_escl_protocol.py -v`
Expected: `1 error`; `ModuleNotFoundError: No module named 'digitalizadora.infrastructure.escl.escl_protocol'`.

- [ ] **Passo 4: Implementar o mínimo**

O analisador compara só o nome local dos elementos (descarta o `{namespace}` que o `ElementTree` coloca na frente), então prefixos diferentes funcionam.

Arquivo `src/digitalizadora/infrastructure/escl/escl_protocol.py`:

```python
import xml.etree.ElementTree as ElementTree
from collections.abc import Sequence

from digitalizadora.domain.errors import ScanFailedError
from digitalizadora.domain.scanner_capabilities import ScannerCapabilities

# Unit of platen_maximum_width and platen_maximum_height: 1/300 of an inch.
ESCL_UNITS_PER_INCH = 300
CAPABILITIES_ROOT_NAME = "ScannerCapabilities"
PLATEN_CAPABILITIES_PATH = ("Platen", "PlatenInputCaps")
COLOR_MODE_PATH = ("SettingProfiles", "SettingProfile", "ColorModes", "ColorMode")
DOCUMENT_FORMAT_PATH = ("SettingProfiles", "SettingProfile", "DocumentFormats", "DocumentFormat")
RESOLUTION_PATH = (
    "SettingProfiles",
    "SettingProfile",
    "SupportedResolutions",
    "DiscreteResolutions",
    "DiscreteResolution",
    "XResolution",
)


def parse_scanner_capabilities(document: bytes) -> ScannerCapabilities:
    root = _parse_document(document)
    _require_root_name(root, CAPABILITIES_ROOT_NAME)
    platen_capabilities = _elements_at(root, PLATEN_CAPABILITIES_PATH)
    if not platen_capabilities:
        raise ScanFailedError("Scanner capabilities do not describe a platen")
    platen = platen_capabilities[0]
    resolutions = {
        _parse_integer(element.text, "XResolution")
        for element in _elements_at(platen, RESOLUTION_PATH)
    }
    return ScannerCapabilities(
        make_and_model=_child_text(root, "MakeAndModel"),
        platen_maximum_width=_read_integer(platen, "MaxWidth"),
        platen_maximum_height=_read_integer(platen, "MaxHeight"),
        supported_resolutions=tuple(sorted(resolutions)),
        supported_color_modes=_unique_texts(_elements_at(platen, COLOR_MODE_PATH)),
        supported_document_formats=_unique_texts(_elements_at(platen, DOCUMENT_FORMAT_PATH)),
    )


def _parse_document(document: bytes) -> ElementTree.Element:
    try:
        return ElementTree.fromstring(document)
    except ElementTree.ParseError as error:
        raise ScanFailedError(f"The eSCL document is not valid XML: {error}") from error


def _local_name(tag: str) -> str:
    return tag.rpartition("}")[2]


def _children_named(parent: ElementTree.Element, name: str) -> list[ElementTree.Element]:
    return [child for child in parent if _local_name(child.tag) == name]


def _elements_at(start: ElementTree.Element, path: Sequence[str]) -> list[ElementTree.Element]:
    current = [start]
    for name in path:
        current = [child for element in current for child in _children_named(element, name)]
    return current


def _child_text(parent: ElementTree.Element, name: str) -> str:
    children = _children_named(parent, name)
    if not children or children[0].text is None:
        return ""
    return children[0].text.strip()


def _unique_texts(elements: Sequence[ElementTree.Element]) -> tuple[str, ...]:
    texts = (element.text.strip() for element in elements if element.text)
    return tuple(dict.fromkeys(text for text in texts if text))


def _parse_integer(text: str | None, field_name: str) -> int:
    try:
        return int((text or "").strip())
    except ValueError as error:
        raise ScanFailedError(f"The eSCL field {field_name} is not an integer") from error


def _read_integer(parent: ElementTree.Element, name: str) -> int:
    children = _children_named(parent, name)
    if not children:
        raise ScanFailedError(f"The eSCL document has no {name}")
    return _parse_integer(children[0].text, name)


def _require_root_name(root: ElementTree.Element, expected_name: str) -> None:
    if _local_name(root.tag) != expected_name:
        raise ScanFailedError(f"Expected an eSCL {expected_name} document, got {root.tag}")
```

- [ ] **Passo 5: Rodar os testes e ver passar**

Run: `.venv/bin/pytest tests/infrastructure/test_escl_protocol.py -v`
Expected: `13 passed`

#### Ciclo 2: XML do `ScanSettings`

- [ ] **Passo 6: Escrever os testes que falham**

Em `tests/infrastructure/test_escl_protocol.py`: (a) trocar o bloco de imports (do início do arquivo até a linha `CAPABILITIES_FIXTURE = ...`, inclusive) por:

```python
import dataclasses

import pytest

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import ScanFailedError, ScanRejectedError
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanner_capabilities import ScannerCapabilities
from digitalizadora.infrastructure.escl.escl_protocol import (
    ESCL_UNITS_PER_INCH,
    build_scan_settings_xml,
    parse_scanner_capabilities,
)
from tests.fakes.fixture_files import read_escl_fixture

CAPABILITIES_FIXTURE = "scanner-capabilities-hp-deskjet-2800.xml"
```

(b) inserir a constante abaixo logo acima de `def load_capabilities`:

```python
XML_DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>'
SCAN_SETTINGS_OPENING = (
    '<scan:ScanSettings xmlns:pwg="http://www.pwg.org/schemas/2010/12/sm"'
    ' xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03">'
)
EXPECTED_SCAN_SETTINGS_TEMPLATE = (
    XML_DECLARATION
    + SCAN_SETTINGS_OPENING
    + "<pwg:Version>2.0</pwg:Version>"
    + "<pwg:ScanRegions><pwg:ScanRegion>"
    + "<pwg:ContentRegionUnits>escl:ThreeHundredthsOfInches</pwg:ContentRegionUnits>"
    + "<pwg:XOffset>0</pwg:XOffset><pwg:YOffset>0</pwg:YOffset>"
    + "<pwg:Width>2550</pwg:Width><pwg:Height>3507</pwg:Height>"
    + "</pwg:ScanRegion></pwg:ScanRegions>"
    + "<pwg:InputSource>Platen</pwg:InputSource>"
    + "<scan:ColorMode>{color_mode}</scan:ColorMode>"
    + "<pwg:DocumentFormat>image/jpeg</pwg:DocumentFormat>"
    + "<scan:XResolution>{resolution}</scan:XResolution>"
    + "<scan:YResolution>{resolution}</scan:YResolution>"
    + "</scan:ScanSettings>"
)
```

(c) acrescentar ao final do arquivo:

```python


@pytest.mark.parametrize(
    ("settings", "expected_color_mode", "expected_resolution"),
    [
        (ScanSettings(300, ColorMode.COLOR), "RGB24", 300),
        (ScanSettings(200, ColorMode.GRAYSCALE), "Grayscale8", 200),
        (ScanSettings(250, ColorMode.COLOR), "RGB24", 300),
        (ScanSettings(450, ColorMode.COLOR), "RGB24", 600),
        (ScanSettings(5000, ColorMode.GRAYSCALE), "Grayscale8", 1200),
    ],
)
def test_scan_settings_xml_is_exact(
    settings: ScanSettings, expected_color_mode: str, expected_resolution: int
) -> None:
    document = build_scan_settings_xml(settings, load_capabilities())

    assert document == EXPECTED_SCAN_SETTINGS_TEMPLATE.format(
        color_mode=expected_color_mode, resolution=expected_resolution
    ).encode("utf-8")


def test_scan_settings_xml_is_a_single_line() -> None:
    document = build_scan_settings_xml(ScanSettings(300, ColorMode.COLOR), load_capabilities())

    assert b"\n" not in document


def test_scan_settings_xml_uses_the_platen_size_of_the_scanner() -> None:
    capabilities = dataclasses.replace(
        load_capabilities(), platen_maximum_width=2551, platen_maximum_height=3508
    )

    document = build_scan_settings_xml(ScanSettings(300, ColorMode.COLOR), capabilities)

    assert b"<pwg:Width>2551</pwg:Width><pwg:Height>3508</pwg:Height>" in document


@pytest.mark.parametrize("color_modes", [("RGB24",), ()])
def test_scan_settings_xml_rejects_an_unsupported_grayscale_mode(
    color_modes: tuple[str, ...],
) -> None:
    capabilities = dataclasses.replace(load_capabilities(), supported_color_modes=color_modes)

    with pytest.raises(ScanRejectedError, match="Grayscale8"):
        build_scan_settings_xml(ScanSettings(200, ColorMode.GRAYSCALE), capabilities)


def test_scan_settings_xml_rejects_a_scanner_without_color() -> None:
    capabilities = dataclasses.replace(
        load_capabilities(), supported_color_modes=("Grayscale8", "BlackAndWhite1")
    )

    with pytest.raises(ScanRejectedError, match="RGB24"):
        build_scan_settings_xml(ScanSettings(300, ColorMode.COLOR), capabilities)


@pytest.mark.parametrize("document_formats", [("application/pdf",), ()])
def test_scan_settings_xml_rejects_a_scanner_that_does_not_offer_jpeg(
    document_formats: tuple[str, ...],
) -> None:
    capabilities = dataclasses.replace(
        load_capabilities(), supported_document_formats=document_formats
    )

    with pytest.raises(ScanRejectedError, match="image/jpeg"):
        build_scan_settings_xml(ScanSettings(300, ColorMode.COLOR), capabilities)


def test_scan_settings_xml_keeps_the_request_when_the_scanner_lists_no_resolution() -> None:
    capabilities = dataclasses.replace(load_capabilities(), supported_resolutions=())

    document = build_scan_settings_xml(ScanSettings(250, ColorMode.COLOR), capabilities)

    assert b"<scan:XResolution>250</scan:XResolution>" in document
```

- [ ] **Passo 7: Rodar os testes e ver falhar**

Run: `.venv/bin/pytest tests/infrastructure/test_escl_protocol.py -v`
Expected: `1 error`; `ImportError: cannot import name 'build_scan_settings_xml' from 'digitalizadora.infrastructure.escl.escl_protocol'`.

- [ ] **Passo 8: Implementar o mínimo**

Em `src/digitalizadora/infrastructure/escl/escl_protocol.py`: (a) trocar o bloco de imports e constantes (tudo o que está acima de `def parse_scanner_capabilities`) por:

```python
import xml.etree.ElementTree as ElementTree
from collections.abc import Sequence
from types import MappingProxyType

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import ScanFailedError, ScanRejectedError
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanner_capabilities import ScannerCapabilities

# Unit of platen_maximum_width and platen_maximum_height: 1/300 of an inch.
ESCL_UNITS_PER_INCH = 300
PWG_NAMESPACE = "http://www.pwg.org/schemas/2010/12/sm"
SCAN_NAMESPACE = "http://schemas.hp.com/imaging/escl/2011/05/03"
ESCL_VERSION = "2.0"
REGION_UNITS_NAME = "escl:ThreeHundredthsOfInches"
REGION_ORIGIN = 0
INPUT_SOURCE_PLATEN = "Platen"
JPEG_MEDIA_TYPE = "image/jpeg"
XML_DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>'
CAPABILITIES_ROOT_NAME = "ScannerCapabilities"
PLATEN_CAPABILITIES_PATH = ("Platen", "PlatenInputCaps")
COLOR_MODE_PATH = ("SettingProfiles", "SettingProfile", "ColorModes", "ColorMode")
DOCUMENT_FORMAT_PATH = ("SettingProfiles", "SettingProfile", "DocumentFormats", "DocumentFormat")
RESOLUTION_PATH = (
    "SettingProfiles",
    "SettingProfile",
    "SupportedResolutions",
    "DiscreteResolutions",
    "DiscreteResolution",
    "XResolution",
)
ESCL_COLOR_MODE_BY_COLOR_MODE = MappingProxyType(
    {ColorMode.COLOR: "RGB24", ColorMode.GRAYSCALE: "Grayscale8"}
)
```

(b) inserir a função abaixo logo acima de `def _parse_document` (duas linhas em branco antes e depois):

```python


def build_scan_settings_xml(settings: ScanSettings, capabilities: ScannerCapabilities) -> bytes:
    escl_color_mode = ESCL_COLOR_MODE_BY_COLOR_MODE[settings.color_mode]
    if not capabilities.supports_color_mode(escl_color_mode):
        raise ScanRejectedError(f"Scanner does not support the color mode {escl_color_mode}")
    if JPEG_MEDIA_TYPE not in capabilities.supported_document_formats:
        raise ScanRejectedError(f"Scanner does not offer the document format {JPEG_MEDIA_TYPE}")
    resolution = capabilities.closest_supported_resolution(settings.dots_per_inch)
    region = _element(
        "pwg:ScanRegion",
        _element("pwg:ContentRegionUnits", REGION_UNITS_NAME)
        + _element("pwg:XOffset", REGION_ORIGIN)
        + _element("pwg:YOffset", REGION_ORIGIN)
        + _element("pwg:Width", capabilities.platen_maximum_width)
        + _element("pwg:Height", capabilities.platen_maximum_height),
    )
    root_content = (
        _element("pwg:Version", ESCL_VERSION)
        + _element("pwg:ScanRegions", region)
        + _element("pwg:InputSource", INPUT_SOURCE_PLATEN)
        + _element("scan:ColorMode", escl_color_mode)
        + _element("pwg:DocumentFormat", JPEG_MEDIA_TYPE)
        + _element("scan:XResolution", resolution)
        + _element("scan:YResolution", resolution)
    )
    root_opening = f'<scan:ScanSettings xmlns:pwg="{PWG_NAMESPACE}" xmlns:scan="{SCAN_NAMESPACE}">'
    document = f"{XML_DECLARATION}{root_opening}{root_content}</scan:ScanSettings>"
    return document.encode("utf-8")
```

(c) acrescentar ao final do arquivo:

```python


def _element(name: str, content: object) -> str:
    return f"<{name}>{content}</{name}>"
```

- [ ] **Passo 9: Rodar os testes e ver passar**

Run: `.venv/bin/pytest tests/infrastructure/test_escl_protocol.py -v`
Expected: `26 passed`

#### Ciclo 3: estado do scanner

- [ ] **Passo 10: Escrever os testes que falham**

Em `tests/infrastructure/test_escl_protocol.py`: (a) trocar o bloco de imports (do início do arquivo até a linha `CAPABILITIES_FIXTURE = ...`, inclusive) por:

```python
import dataclasses

import pytest

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import ScanFailedError, ScanRejectedError
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanner_capabilities import ScannerCapabilities
from digitalizadora.domain.scanner_status import ScannerState
from digitalizadora.infrastructure.escl.escl_protocol import (
    ESCL_UNITS_PER_INCH,
    build_scan_settings_xml,
    parse_scanner_capabilities,
    parse_scanner_status,
)
from tests.fakes.fixture_files import read_escl_fixture

CAPABILITIES_FIXTURE = "scanner-capabilities-hp-deskjet-2800.xml"
```

(b) inserir a constante abaixo logo acima de `def load_capabilities`:

```python
STATUS_TEMPLATE = (
    '<scan:ScannerStatus xmlns:pwg="http://www.pwg.org/schemas/2010/12/sm"'
    ' xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03">'
    "<pwg:Version>2.63</pwg:Version><pwg:State>{state}</pwg:State></scan:ScannerStatus>"
)
```

(c) acrescentar ao final do arquivo:

```python


@pytest.mark.parametrize(
    ("escl_state_name", "expected_state"),
    [
        ("Idle", ScannerState.IDLE),
        ("Processing", ScannerState.PROCESSING),
        ("Testing", ScannerState.TESTING),
        ("Stopped", ScannerState.STOPPED),
        ("Down", ScannerState.DOWN),
        ("Hibernating", ScannerState.UNKNOWN),
        ("", ScannerState.UNKNOWN),
    ],
)
def test_status_parse_maps_the_state_name(
    escl_state_name: str, expected_state: ScannerState
) -> None:
    document = STATUS_TEMPLATE.format(state=escl_state_name).encode("utf-8")

    assert parse_scanner_status(document).state is expected_state


def test_status_parse_reads_the_idle_fixture() -> None:
    assert parse_scanner_status(read_escl_fixture("scanner-status-idle.xml")).is_ready is True


def test_status_parse_reads_the_processing_fixture() -> None:
    status = parse_scanner_status(read_escl_fixture("scanner-status-processing.xml"))

    assert status.state is ScannerState.PROCESSING


def test_status_parse_without_a_state_element_is_unknown() -> None:
    assert parse_scanner_status(b"<ScannerStatus/>").state is ScannerState.UNKNOWN


def test_status_parse_rejects_a_document_of_another_kind() -> None:
    with pytest.raises(ScanFailedError, match="ScannerStatus"):
        parse_scanner_status(read_escl_fixture(CAPABILITIES_FIXTURE))


def test_status_parse_rejects_malformed_xml() -> None:
    with pytest.raises(ScanFailedError, match="not valid XML"):
        parse_scanner_status(b"<ScannerStatus><State>Idle</ScannerStatus>")
```

- [ ] **Passo 11: Rodar os testes e ver falhar**

Run: `.venv/bin/pytest tests/infrastructure/test_escl_protocol.py -v`
Expected: `1 error`; `ImportError: cannot import name 'parse_scanner_status' from 'digitalizadora.infrastructure.escl.escl_protocol'`.

- [ ] **Passo 12: Implementar o mínimo**

Em `src/digitalizadora/infrastructure/escl/escl_protocol.py`: (a) trocar o bloco de imports e constantes (tudo acima de `def parse_scanner_capabilities`) por:

```python
import xml.etree.ElementTree as ElementTree
from collections.abc import Sequence
from types import MappingProxyType

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import ScanFailedError, ScanRejectedError
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanner_capabilities import ScannerCapabilities
from digitalizadora.domain.scanner_status import ScannerState, ScannerStatus

# Unit of platen_maximum_width and platen_maximum_height: 1/300 of an inch.
ESCL_UNITS_PER_INCH = 300
PWG_NAMESPACE = "http://www.pwg.org/schemas/2010/12/sm"
SCAN_NAMESPACE = "http://schemas.hp.com/imaging/escl/2011/05/03"
ESCL_VERSION = "2.0"
REGION_UNITS_NAME = "escl:ThreeHundredthsOfInches"
REGION_ORIGIN = 0
INPUT_SOURCE_PLATEN = "Platen"
JPEG_MEDIA_TYPE = "image/jpeg"
XML_DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>'
CAPABILITIES_ROOT_NAME = "ScannerCapabilities"
STATUS_ROOT_NAME = "ScannerStatus"
PLATEN_CAPABILITIES_PATH = ("Platen", "PlatenInputCaps")
COLOR_MODE_PATH = ("SettingProfiles", "SettingProfile", "ColorModes", "ColorMode")
DOCUMENT_FORMAT_PATH = ("SettingProfiles", "SettingProfile", "DocumentFormats", "DocumentFormat")
RESOLUTION_PATH = (
    "SettingProfiles",
    "SettingProfile",
    "SupportedResolutions",
    "DiscreteResolutions",
    "DiscreteResolution",
    "XResolution",
)
ESCL_COLOR_MODE_BY_COLOR_MODE = MappingProxyType(
    {ColorMode.COLOR: "RGB24", ColorMode.GRAYSCALE: "Grayscale8"}
)
SCANNER_STATE_BY_ESCL_NAME = MappingProxyType(
    {
        "Idle": ScannerState.IDLE,
        "Processing": ScannerState.PROCESSING,
        "Testing": ScannerState.TESTING,
        "Stopped": ScannerState.STOPPED,
        "Down": ScannerState.DOWN,
    }
)
```

(b) inserir a função abaixo logo acima de `def _parse_document`:

```python


def parse_scanner_status(document: bytes) -> ScannerStatus:
    root = _parse_document(document)
    _require_root_name(root, STATUS_ROOT_NAME)
    state_name = _child_text(root, "State")
    return ScannerStatus(SCANNER_STATE_BY_ESCL_NAME.get(state_name, ScannerState.UNKNOWN))
```

- [ ] **Passo 13: Rodar os testes e ver passar**

Run: `.venv/bin/pytest tests/infrastructure/test_escl_protocol.py -v`
Expected: `38 passed`

#### Ciclo 4: caminho do trabalho (`Location`)

- [ ] **Passo 14: Escrever os testes que falham**

Cobre o modo de falha de endereço novo do design: o cabeçalho `Location` pode trazer o endereço antigo ou um host estranho, e só o caminho é usado.

Em `tests/infrastructure/test_escl_protocol.py`: (a) trocar o bloco de imports (do início do arquivo até a linha `CAPABILITIES_FIXTURE = ...`, inclusive) por:

```python
import dataclasses

import pytest

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import ScanFailedError, ScanRejectedError
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanner_capabilities import ScannerCapabilities
from digitalizadora.domain.scanner_status import ScannerState
from digitalizadora.infrastructure.escl.escl_protocol import (
    ESCL_UNITS_PER_INCH,
    build_scan_settings_xml,
    extract_job_path,
    parse_scanner_capabilities,
    parse_scanner_status,
)
from tests.fakes.fixture_files import read_escl_fixture

CAPABILITIES_FIXTURE = "scanner-capabilities-hp-deskjet-2800.xml"
```

(b) acrescentar ao final do arquivo:

```python


@pytest.mark.parametrize(
    "location_header",
    [
        "http://192.168.0.40:8080/eSCL/ScanJobs/12",
        "/eSCL/ScanJobs/12",
        "/eSCL/ScanJobs/12/",
        "http://other-host.example:9999/eSCL/ScanJobs/12",
        "http://[fe80::1]:8080/eSCL/ScanJobs/12",
        "/eSCL/ScanJobs/12?token=abc",
        "  /eSCL/ScanJobs/12  ",
    ],
)
def test_extract_job_path_keeps_only_the_path(location_header: str) -> None:
    assert extract_job_path(location_header) == "/eSCL/ScanJobs/12"


@pytest.mark.parametrize(
    "location_header",
    ["", "   ", "/", "http://192.168.0.40:8080", "http://192.168.0.40:8080/"],
)
def test_extract_job_path_rejects_a_location_without_a_path(location_header: str) -> None:
    with pytest.raises(ScanFailedError, match="job location"):
        extract_job_path(location_header)
```

- [ ] **Passo 15: Rodar os testes e ver falhar**

Run: `.venv/bin/pytest tests/infrastructure/test_escl_protocol.py -v`
Expected: `1 error`; `ImportError: cannot import name 'extract_job_path' from 'digitalizadora.infrastructure.escl.escl_protocol'`.

- [ ] **Passo 16: Implementar o mínimo**

Em `src/digitalizadora/infrastructure/escl/escl_protocol.py`: (a) trocar o bloco de imports e constantes (tudo acima de `def parse_scanner_capabilities`) por:

```python
import xml.etree.ElementTree as ElementTree
from collections.abc import Sequence
from types import MappingProxyType
from urllib.parse import urlsplit

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import ScanFailedError, ScanRejectedError
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanner_capabilities import ScannerCapabilities
from digitalizadora.domain.scanner_status import ScannerState, ScannerStatus

# Unit of platen_maximum_width and platen_maximum_height: 1/300 of an inch.
ESCL_UNITS_PER_INCH = 300
PWG_NAMESPACE = "http://www.pwg.org/schemas/2010/12/sm"
SCAN_NAMESPACE = "http://schemas.hp.com/imaging/escl/2011/05/03"
ESCL_VERSION = "2.0"
REGION_UNITS_NAME = "escl:ThreeHundredthsOfInches"
REGION_ORIGIN = 0
INPUT_SOURCE_PLATEN = "Platen"
JPEG_MEDIA_TYPE = "image/jpeg"
XML_DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>'
CAPABILITIES_ROOT_NAME = "ScannerCapabilities"
STATUS_ROOT_NAME = "ScannerStatus"
PLATEN_CAPABILITIES_PATH = ("Platen", "PlatenInputCaps")
COLOR_MODE_PATH = ("SettingProfiles", "SettingProfile", "ColorModes", "ColorMode")
DOCUMENT_FORMAT_PATH = ("SettingProfiles", "SettingProfile", "DocumentFormats", "DocumentFormat")
RESOLUTION_PATH = (
    "SettingProfiles",
    "SettingProfile",
    "SupportedResolutions",
    "DiscreteResolutions",
    "DiscreteResolution",
    "XResolution",
)
ESCL_COLOR_MODE_BY_COLOR_MODE = MappingProxyType(
    {ColorMode.COLOR: "RGB24", ColorMode.GRAYSCALE: "Grayscale8"}
)
SCANNER_STATE_BY_ESCL_NAME = MappingProxyType(
    {
        "Idle": ScannerState.IDLE,
        "Processing": ScannerState.PROCESSING,
        "Testing": ScannerState.TESTING,
        "Stopped": ScannerState.STOPPED,
        "Down": ScannerState.DOWN,
    }
)
```

(b) inserir a função abaixo logo acima de `def _parse_document`:

```python


def extract_job_path(location_header: str) -> str:
    path = urlsplit(location_header.strip()).path.rstrip("/")
    if not path:
        raise ScanFailedError("The scanner returned a job location without a path")
    return path
```

- [ ] **Passo 17: Rodar os testes e ver passar**

Run: `.venv/bin/pytest tests/infrastructure/test_escl_protocol.py -v`
Expected: `50 passed`

#### Ciclo 5: entidades XML e `<!doctype` em minúsculas

Como `defusedxml` não é dependência, o analisador recusa qualquer documento com `<!ENTITY` (defesa contra expansão de entidades) e normaliza `<!doctype` para `<!DOCTYPE`, porque o `expat` só aceita a forma em maiúsculas (firmware HP, NAPS2 #654).

- [ ] **Passo 18: Escrever os testes que falham**

Em `tests/infrastructure/test_escl_protocol.py`: (a) inserir a constante abaixo logo acima de `def load_capabilities`:

```python
ENTITY_DOCUMENT = (
    b'<?xml version="1.0"?><!DOCTYPE bomb [<!ENTITY laugh "ha">]>'
    b"<ScannerStatus><State>&laugh;</State></ScannerStatus>"
)
```

(b) acrescentar ao final do arquivo (o bloco de imports não muda):

```python


@pytest.mark.parametrize("parser", [parse_scanner_capabilities, parse_scanner_status])
def test_parsers_refuse_documents_that_declare_entities(
    parser: Callable[[bytes], object],
) -> None:
    with pytest.raises(ScanFailedError, match="entities"):
        parser(ENTITY_DOCUMENT)


def test_entity_refusal_ignores_letter_case() -> None:
    document = ENTITY_DOCUMENT.replace(b"<!ENTITY", b"<!entity")

    with pytest.raises(ScanFailedError, match="entities"):
        parse_scanner_status(document)


def test_capabilities_parse_accepts_a_lowercase_doctype() -> None:
    document = read_escl_fixture(CAPABILITIES_FIXTURE).replace(
        b"?>\n", b"?>\n<!doctype html>\n", 1
    )

    assert parse_scanner_capabilities(document).platen_maximum_width == 2550


def test_status_parse_accepts_a_lowercase_doctype() -> None:
    document = b"<!doctype html><ScannerStatus><State>Idle</State></ScannerStatus>"

    assert parse_scanner_status(document).state is ScannerState.IDLE
```

- [ ] **Passo 19: Rodar os testes e ver falhar**

Run: `.venv/bin/pytest tests/infrastructure/test_escl_protocol.py -v`
Expected: `5 failed, 50 passed`; as falhas são `Failed: DID NOT RAISE`, `Regex pattern did not match` (entidades) e `ScanFailedError: The eSCL document is not valid XML` (doctype em minúsculas).

- [ ] **Passo 20: Implementar o mínimo**

Em `src/digitalizadora/infrastructure/escl/escl_protocol.py`: (a) trocar o bloco de imports e constantes (tudo acima de `def parse_scanner_capabilities`) por:

```python
import re
import xml.etree.ElementTree as ElementTree
from collections.abc import Sequence
from types import MappingProxyType
from urllib.parse import urlsplit

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import ScanFailedError, ScanRejectedError
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanner_capabilities import ScannerCapabilities
from digitalizadora.domain.scanner_status import ScannerState, ScannerStatus

# Unit of platen_maximum_width and platen_maximum_height: 1/300 of an inch.
ESCL_UNITS_PER_INCH = 300
PWG_NAMESPACE = "http://www.pwg.org/schemas/2010/12/sm"
SCAN_NAMESPACE = "http://schemas.hp.com/imaging/escl/2011/05/03"
ESCL_VERSION = "2.0"
REGION_UNITS_NAME = "escl:ThreeHundredthsOfInches"
REGION_ORIGIN = 0
INPUT_SOURCE_PLATEN = "Platen"
JPEG_MEDIA_TYPE = "image/jpeg"
XML_DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>'
CAPABILITIES_ROOT_NAME = "ScannerCapabilities"
STATUS_ROOT_NAME = "ScannerStatus"
PLATEN_CAPABILITIES_PATH = ("Platen", "PlatenInputCaps")
COLOR_MODE_PATH = ("SettingProfiles", "SettingProfile", "ColorModes", "ColorMode")
DOCUMENT_FORMAT_PATH = ("SettingProfiles", "SettingProfile", "DocumentFormats", "DocumentFormat")
RESOLUTION_PATH = (
    "SettingProfiles",
    "SettingProfile",
    "SupportedResolutions",
    "DiscreteResolutions",
    "DiscreteResolution",
    "XResolution",
)
ESCL_COLOR_MODE_BY_COLOR_MODE = MappingProxyType(
    {ColorMode.COLOR: "RGB24", ColorMode.GRAYSCALE: "Grayscale8"}
)
SCANNER_STATE_BY_ESCL_NAME = MappingProxyType(
    {
        "Idle": ScannerState.IDLE,
        "Processing": ScannerState.PROCESSING,
        "Testing": ScannerState.TESTING,
        "Stopped": ScannerState.STOPPED,
        "Down": ScannerState.DOWN,
    }
)
ENTITY_DECLARATION_PATTERN = re.compile(rb"<!ENTITY", re.IGNORECASE)
DOCUMENT_TYPE_PATTERN = re.compile(rb"<!doctype", re.IGNORECASE)
NORMALIZED_DOCUMENT_TYPE = b"<!DOCTYPE"
```

(b) substituir a função `_parse_document` inteira por:

```python
def _parse_document(document: bytes) -> ElementTree.Element:
    if ENTITY_DECLARATION_PATTERN.search(document):
        raise ScanFailedError("The eSCL document declares XML entities, which are refused")
    normalized_document = DOCUMENT_TYPE_PATTERN.sub(NORMALIZED_DOCUMENT_TYPE, document)
    try:
        return ElementTree.fromstring(normalized_document)
    except ElementTree.ParseError as error:
        raise ScanFailedError(f"The eSCL document is not valid XML: {error}") from error
```

- [ ] **Passo 21: Rodar os testes e ver passar**

Run: `.venv/bin/pytest tests/infrastructure/test_escl_protocol.py -v`
Expected: `55 passed`

#### Fechamento

- [ ] **Passo 22: Rodar a suíte inteira e o lint**

Run: `.venv/bin/pytest -q`
Expected: `155 passed` (100 das Tasks 1 e 2 e 55 desta task).

Run: `.venv/bin/ruff check src tests`
Expected: `All checks passed!`

- [ ] **Passo 23: Conferir a captura real do Gate 0 (somente se o Gate 0 já foi feito)**

A fixture é sintética. Se existir `docs/spike-0/captures/manual/capabilities.xml` (Passo 9 da Task 0) ou `docs/spike-0/captures/<data UTC>/capabilities.xml` (Passo 10), conferir que o analisador entende o XML real:

```bash
.venv/bin/python -c "
from pathlib import Path
from digitalizadora.infrastructure.escl.escl_protocol import parse_scanner_capabilities
print(parse_scanner_capabilities(Path('docs/spike-0/captures/manual/capabilities.xml').read_bytes()))
"
```
Expected: uma linha `ScannerCapabilities(make_and_model='HP DeskJet ...', platen_maximum_width=2550, platen_maximum_height=3507, supported_resolutions=(...), ...)` com os valores reais. Se aparecer `ScanFailedError`, o formato real difere do sintético: **parar e levar a mensagem e o XML ao usuário** (não editar o analisador às cegas). Esta verificação não gera arquivos nem commit; trocar a fixture sintética pelo XML real é um passo à parte, que exige atualizar os valores esperados dos testes do Ciclo 1.

- [ ] **Passo 24: Commit**

```bash
git add src/digitalizadora/infrastructure/escl/escl_protocol.py tests/fixtures/escl \
  tests/fakes/fixture_files.py tests/infrastructure/test_escl_protocol.py
git commit -m "feat: add pure eSCL protocol functions and synthetic fixtures"
```

### Task 4: Simulador: impressora eSCL falsa (ASGI)

**Objetivo:** Criar o aplicativo ASGI que imita uma impressora eSCL (capacidades, estado, trabalhos, páginas sintéticas e falhas injetáveis) para os testes e para `make simulator`.

**Files:**
- Create: `src/digitalizadora/simulator/fake_escl_scanner_app.py`
- Test: `tests/simulator/test_fake_escl_scanner_app.py`

**Interfaces:**
- Consumes:
  - Task 1: pacotes `digitalizadora.simulator` e `tests.simulator` (os `__init__.py` já existem); dependências `fastapi`, `httpx` e `pillow` instaladas no `.venv`.
  - Task 2: `digitalizadora.domain.color_mode.ColorMode`, `digitalizadora.domain.scan_settings.ScanSettings`, `digitalizadora.domain.scanner_status.ScannerState`.
  - Task 3: `digitalizadora.infrastructure.escl.escl_protocol` com `ESCL_UNITS_PER_INCH`, `build_scan_settings_xml(settings, capabilities) -> bytes`, `parse_scanner_capabilities(document: bytes) -> ScannerCapabilities`, `parse_scanner_status(document: bytes) -> ScannerStatus`.
- Produces:
  - `FakeScannerBehavior(busy_polls_before_document=1, initial_state="Idle", post_status_code=201, document_status_code=200)` (dataclass mutável) e `create_fake_escl_scanner_app(behavior: FakeScannerBehavior) -> FastAPI`, exatamente como a seção 6.6 da spec.
  - `build_capabilities_document(color_modes: Sequence[str]) -> bytes` e `build_status_document(state_name: str) -> bytes`: geradores do XML de capacidades e de estado, reutilizados pelos testes do gateway (Task 5) e pelo teste de integração (Task 14).
  - Constantes públicas `PLATEN_MAXIMUM_WIDTH = 2550`, `PLATEN_MAXIMUM_HEIGHT = 3507`, `SUPPORTED_RESOLUTIONS`, `SUPPORTED_COLOR_MODES = ("RGB24", "Grayscale8")`.
  - Rotas sob `/eSCL`: `GET ScannerCapabilities`, `GET ScannerStatus`, `POST ScanJobs` (201 + `Location: /eSCL/ScanJobs/<n>`), `GET ScanJobs/{n}/NextDocument` (503, depois 200 `image/jpeg`, depois 404), `DELETE ScanJobs/{n}`.

**Notas da tarefa**
- API verificada: `ImageFont.load_default(size=...)` existe no Pillow 10.1 ou mais novo (conferido com `inspect.signature` no Pillow 10.4.0; o projeto exige Pillow 12 ou mais novo). A fonte embutida não tem o glifo "á" (confirmado renderizando a página), por isso o rótulo é "Pagina N".
- O simulador roda sem fixtures: o XML de capacidades vem de `build_capabilities_document`. O `__main__` do simulador (`python -m digitalizadora.simulator`, `make simulator`, uvicorn na porta 8080) é da Task 13.
- Os handlers são `async def` métodos de `FakeEsclScanner`, registrados com `FastAPI.add_api_route`; o estado dos trabalhos fica na instância (nenhum estado global), então cada `create_fake_escl_scanner_app` é uma impressora independente.
- Estado: `GET ScannerStatus` devolve `Processing` entre o `POST` e a entrega do documento (ou o `DELETE` do trabalho); depois volta para `behavior.initial_state` ("Idle" por padrão). Um `initial_state` ocupado (por exemplo "Processing") permanece assim, o que permite testar a espera por impressora ocupada.
- Suposição sobre a Task 3: `parse_scanner_capabilities` lê a estrutura padrão do eSCL de forma independente de namespace (`Platen/PlatenInputCaps` com `MaxWidth`, `MaxHeight`, `ColorModes/ColorMode`, `DocumentFormats/DocumentFormat` e `SupportedResolutions/DiscreteResolutions/DiscreteResolution/XResolution`) e `parse_scanner_status` lê `State` ("Idle", "Processing"...). O primeiro ciclo de testes da Task 4 falha logo se o parser da Task 3 esperar outra forma, e nesse caso o XML-modelo é que deve ser ajustado.
- Review Focus: este simulador sustenta os modos de falha 1 (impressora ocupada ou recusando: 503, 409) e 4 (imagem sem densidade JFIF: a página sai sem `dpi` de propósito) nas Tasks 5, 6 e 14.

- [ ] **Passo 1: Escrever o teste que falha** (ciclo 1: Capacidades e estado)

O primeiro comportamento é o mais simples: a impressora falsa descreve o vidro (2550 x 3507 em 1/300 de polegada), as resoluções, os modos de cor e os formatos, e informa o estado inicial. O simulador vive dentro do pacote e **não lê fixtures de teste**: o XML de capacidades sai de uma função-modelo, coerente com `parse_scanner_capabilities` da Task 3.

Crie `tests/simulator/test_fake_escl_scanner_app.py` com o conteúdo:

```python
import httpx

from digitalizadora.domain.scanner_status import ScannerState
from digitalizadora.infrastructure.escl.escl_protocol import (
    parse_scanner_capabilities,
    parse_scanner_status,
)
from digitalizadora.simulator.fake_escl_scanner_app import (
    FakeScannerBehavior,
    create_fake_escl_scanner_app,
)

SCANNER_BASE_ADDRESS = "http://scanner.test"
CAPABILITIES_PATH = "/eSCL/ScannerCapabilities"
STATUS_PATH = "/eSCL/ScannerStatus"


def build_client(behavior: FakeScannerBehavior | None = None) -> httpx.AsyncClient:
    app = create_fake_escl_scanner_app(behavior or FakeScannerBehavior())
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=SCANNER_BASE_ADDRESS)


async def read_state(client: httpx.AsyncClient) -> ScannerState:
    response = await client.get(STATUS_PATH)
    return parse_scanner_status(response.content).state


async def test_capabilities_report_the_platen_size() -> None:
    async with build_client() as client:
        response = await client.get(CAPABILITIES_PATH)
    capabilities = parse_scanner_capabilities(response.content)
    assert (capabilities.platen_maximum_width, capabilities.platen_maximum_height) == (2550, 3507)


async def test_capabilities_report_the_supported_resolutions_in_ascending_order() -> None:
    async with build_client() as client:
        response = await client.get(CAPABILITIES_PATH)
    capabilities = parse_scanner_capabilities(response.content)
    assert capabilities.supported_resolutions == (75, 100, 150, 200, 300, 600)


async def test_capabilities_report_color_and_grayscale_modes() -> None:
    async with build_client() as client:
        response = await client.get(CAPABILITIES_PATH)
    capabilities = parse_scanner_capabilities(response.content)
    assert set(capabilities.supported_color_modes) == {"RGB24", "Grayscale8"}


async def test_capabilities_report_jpeg_and_pdf_formats() -> None:
    async with build_client() as client:
        response = await client.get(CAPABILITIES_PATH)
    capabilities = parse_scanner_capabilities(response.content)
    assert set(capabilities.supported_document_formats) == {"image/jpeg", "application/pdf"}


async def test_status_is_idle_by_default() -> None:
    async with build_client() as client:
        assert await read_state(client) is ScannerState.IDLE


async def test_status_reports_a_busy_initial_state() -> None:
    async with build_client(FakeScannerBehavior(initial_state="Processing")) as client:
        assert await read_state(client) is ScannerState.PROCESSING
```

- [ ] **Passo 2: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/simulator/test_fake_escl_scanner_app.py -v`

Expected: o pytest aborta na coleta com `ModuleNotFoundError: No module named 'digitalizadora.simulator.fake_escl_scanner_app'` (resumo: `1 error`).

- [ ] **Passo 3: Implementar o mínimo**

Crie o simulador com as constantes do vidro, os geradores dos documentos XML, o comportamento configurável e as duas primeiras rotas.

Crie `src/digitalizadora/simulator/fake_escl_scanner_app.py` com o conteúdo:

```python
"""Fake eSCL scanner served as an ASGI application.

Used by the automated tests through httpx.ASGITransport and by `make simulator`.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from http import HTTPStatus

from fastapi import FastAPI, Response

SCANNER_PATH_PREFIX = "/eSCL"
PLATEN_MAXIMUM_WIDTH = 2550
PLATEN_MAXIMUM_HEIGHT = 3507
PLATEN_MINIMUM_SIZE = 16
MAXIMUM_SCAN_REGIONS = 1
ESCL_VERSION = "2.63"
SUPPORTED_RESOLUTIONS = (75, 100, 150, 200, 300, 600)
SUPPORTED_COLOR_MODES = ("RGB24", "Grayscale8")
SUPPORTED_DOCUMENT_FORMATS = ("image/jpeg", "application/pdf")
IDLE_STATE_NAME = "Idle"
XML_MEDIA_TYPE = "text/xml"
NAMESPACE_DECLARATIONS = (
    'xmlns:pwg="http://www.pwg.org/schemas/2010/12/sm" '
    'xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03"'
)


@dataclass
class FakeScannerBehavior:
    busy_polls_before_document: int = 1
    initial_state: str = IDLE_STATE_NAME
    post_status_code: int = HTTPStatus.CREATED
    document_status_code: int = HTTPStatus.OK


def build_capabilities_document(color_modes: Sequence[str]) -> bytes:
    color_mode_elements = "".join(f"<scan:ColorMode>{mode}</scan:ColorMode>" for mode in color_modes)
    format_elements = "".join(
        f"<pwg:DocumentFormat>{document_format}</pwg:DocumentFormat>"
        for document_format in SUPPORTED_DOCUMENT_FORMATS
    )
    resolution_elements = "".join(
        "<scan:DiscreteResolution>"
        f"<scan:XResolution>{resolution}</scan:XResolution>"
        f"<scan:YResolution>{resolution}</scan:YResolution>"
        "</scan:DiscreteResolution>"
        for resolution in SUPPORTED_RESOLUTIONS
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<scan:ScannerCapabilities {NAMESPACE_DECLARATIONS}>"
        f"<pwg:Version>{ESCL_VERSION}</pwg:Version>"
        "<pwg:MakeAndModel>Fake eSCL Scanner</pwg:MakeAndModel>"
        "<scan:Platen><scan:PlatenInputCaps>"
        f"<scan:MinWidth>{PLATEN_MINIMUM_SIZE}</scan:MinWidth>"
        f"<scan:MaxWidth>{PLATEN_MAXIMUM_WIDTH}</scan:MaxWidth>"
        f"<scan:MinHeight>{PLATEN_MINIMUM_SIZE}</scan:MinHeight>"
        f"<scan:MaxHeight>{PLATEN_MAXIMUM_HEIGHT}</scan:MaxHeight>"
        f"<scan:MaxScanRegions>{MAXIMUM_SCAN_REGIONS}</scan:MaxScanRegions>"
        "<scan:SettingProfiles><scan:SettingProfile>"
        f"<scan:ColorModes>{color_mode_elements}</scan:ColorModes>"
        f"<scan:DocumentFormats>{format_elements}</scan:DocumentFormats>"
        f"<scan:SupportedResolutions><scan:DiscreteResolutions>{resolution_elements}"
        "</scan:DiscreteResolutions></scan:SupportedResolutions>"
        "</scan:SettingProfile></scan:SettingProfiles>"
        "</scan:PlatenInputCaps></scan:Platen>"
        "</scan:ScannerCapabilities>"
    ).encode("utf-8")


def build_status_document(state_name: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<scan:ScannerStatus {NAMESPACE_DECLARATIONS}>"
        f"<pwg:Version>{ESCL_VERSION}</pwg:Version>"
        f"<pwg:State>{state_name}</pwg:State>"
        "</scan:ScannerStatus>"
    ).encode("utf-8")


class FakeEsclScanner:
    def __init__(self, behavior: FakeScannerBehavior) -> None:
        self._behavior = behavior

    async def read_capabilities(self) -> Response:
        return Response(content=build_capabilities_document(SUPPORTED_COLOR_MODES), media_type=XML_MEDIA_TYPE)

    async def read_status(self) -> Response:
        return Response(content=build_status_document(self._behavior.initial_state), media_type=XML_MEDIA_TYPE)


def create_fake_escl_scanner_app(behavior: FakeScannerBehavior) -> FastAPI:
    scanner = FakeEsclScanner(behavior)
    app = FastAPI(title="Fake eSCL scanner", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_api_route(f"{SCANNER_PATH_PREFIX}/ScannerCapabilities", scanner.read_capabilities, methods=["GET"])
    app.add_api_route(f"{SCANNER_PATH_PREFIX}/ScannerStatus", scanner.read_status, methods=["GET"])
    return app
```

- [ ] **Passo 4: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/simulator/test_fake_escl_scanner_app.py -v`

Expected: `6 passed`.

- [ ] **Passo 5: Escrever o teste que falha** (ciclo 2: Ciclo de vida de um trabalho)

Agora o trabalho de digitalização: `POST ScanJobs` cria o trabalho (201 + `Location`, numeração a partir de 1); `NextDocument` responde 503 durante `busy_polls_before_document` consultas e então entrega um JPEG uma única vez (depois 404); o estado vira `Processing` enquanto o trabalho está aberto; `DELETE` encerra o trabalho. A página sintética ainda é um JPEG mínimo de 1x1 pixel; o conteúdo real vem no ciclo seguinte.

Substitua o bloco de importações de `tests/simulator/test_fake_escl_scanner_app.py` (as linhas `import` e `from` do topo do arquivo) por:

```python
from http import HTTPStatus

import httpx

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanner_status import ScannerState
from digitalizadora.infrastructure.escl.escl_protocol import (
    parse_scanner_capabilities,
    parse_scanner_status,
)
from digitalizadora.simulator.fake_escl_scanner_app import (
    PLATEN_MAXIMUM_HEIGHT,
    PLATEN_MAXIMUM_WIDTH,
    FakeScannerBehavior,
    create_fake_escl_scanner_app,
)
```

Em `tests/simulator/test_fake_escl_scanner_app.py`, logo depois de `STATUS_PATH`, acrescente:

```python
SCAN_JOBS_PATH = "/eSCL/ScanJobs"
FIRST_JOB_PATH = "/eSCL/ScanJobs/1"
FIRST_DOCUMENT_PATH = "/eSCL/ScanJobs/1/NextDocument"
FAST_RESOLUTION = 75
JPEG_START_OF_IMAGE = b"\xff\xd8"
```

Em `tests/simulator/test_fake_escl_scanner_app.py`, logo depois de `read_state`, acrescente:

```python
def build_settings_document(dots_per_inch: int, color_mode: str) -> bytes:
    return (
        '<scan:ScanSettings xmlns:pwg="http://www.pwg.org/schemas/2010/12/sm" '
        'xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03">'
        "<pwg:Version>2.0</pwg:Version><pwg:ScanRegions><pwg:ScanRegion>"
        "<pwg:ContentRegionUnits>escl:ThreeHundredthsOfInches</pwg:ContentRegionUnits>"
        f"<pwg:Width>{PLATEN_MAXIMUM_WIDTH}</pwg:Width><pwg:Height>{PLATEN_MAXIMUM_HEIGHT}</pwg:Height>"
        "</pwg:ScanRegion></pwg:ScanRegions><pwg:InputSource>Platen</pwg:InputSource>"
        f"<scan:ColorMode>{color_mode}</scan:ColorMode>"
        "<pwg:DocumentFormat>image/jpeg</pwg:DocumentFormat>"
        f"<scan:XResolution>{dots_per_inch}</scan:XResolution>"
        f"<scan:YResolution>{dots_per_inch}</scan:YResolution></scan:ScanSettings>"
    ).encode("utf-8")


async def post_scan_job(
    client: httpx.AsyncClient, dots_per_inch: int = FAST_RESOLUTION, color_mode: str = "RGB24"
) -> httpx.Response:
    return await client.post(
        SCAN_JOBS_PATH,
        content=build_settings_document(dots_per_inch, color_mode),
        headers={"Content-Type": "text/xml"},
    )
```

Acrescente ao final de `tests/simulator/test_fake_escl_scanner_app.py`:

```python
async def test_post_answers_201_with_the_location_of_the_first_job() -> None:
    async with build_client() as client:
        response = await post_scan_job(client)
    assert (response.status_code, response.headers["Location"]) == (HTTPStatus.CREATED, FIRST_JOB_PATH)


async def test_second_job_receives_the_next_number() -> None:
    async with build_client() as client:
        await post_scan_job(client)
        response = await post_scan_job(client)
    assert response.headers["Location"] == "/eSCL/ScanJobs/2"


async def test_next_document_answers_503_while_busy_polls_remain_then_200() -> None:
    async with build_client(FakeScannerBehavior(busy_polls_before_document=3)) as client:
        await post_scan_job(client)
        statuses = [(await client.get(FIRST_DOCUMENT_PATH)).status_code for _ in range(4)]
    assert statuses == [503, 503, 503, 200]


async def test_next_document_with_zero_busy_polls_delivers_immediately() -> None:
    async with build_client(FakeScannerBehavior(busy_polls_before_document=0)) as client:
        await post_scan_job(client)
        response = await client.get(FIRST_DOCUMENT_PATH)
    assert response.status_code == HTTPStatus.OK


async def test_next_document_delivers_a_jpeg_page() -> None:
    async with build_client(FakeScannerBehavior(busy_polls_before_document=0)) as client:
        await post_scan_job(client)
        response = await client.get(FIRST_DOCUMENT_PATH)
    assert (response.headers["Content-Type"], response.content[:2]) == ("image/jpeg", JPEG_START_OF_IMAGE)


async def test_next_document_answers_404_after_the_page_was_delivered() -> None:
    async with build_client(FakeScannerBehavior(busy_polls_before_document=0)) as client:
        await post_scan_job(client)
        await client.get(FIRST_DOCUMENT_PATH)
        response = await client.get(FIRST_DOCUMENT_PATH)
    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_next_document_of_an_unknown_job_answers_404() -> None:
    async with build_client() as client:
        response = await client.get(FIRST_DOCUMENT_PATH)
    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_delete_removes_the_job() -> None:
    async with build_client(FakeScannerBehavior(busy_polls_before_document=0)) as client:
        await post_scan_job(client)
        deletion = await client.delete(FIRST_JOB_PATH)
        document = await client.get(FIRST_DOCUMENT_PATH)
    assert (deletion.status_code, document.status_code) == (HTTPStatus.OK, HTTPStatus.NOT_FOUND)


async def test_delete_of_an_unknown_job_answers_404() -> None:
    async with build_client() as client:
        response = await client.delete(FIRST_JOB_PATH)
    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_status_is_processing_between_the_post_and_the_delivery() -> None:
    async with build_client() as client:
        await post_scan_job(client)
        assert await read_state(client) is ScannerState.PROCESSING


async def test_status_is_idle_after_the_document_was_delivered() -> None:
    async with build_client(FakeScannerBehavior(busy_polls_before_document=0)) as client:
        await post_scan_job(client)
        await client.get(FIRST_DOCUMENT_PATH)
        assert await read_state(client) is ScannerState.IDLE


async def test_status_is_idle_after_the_job_was_deleted() -> None:
    async with build_client() as client:
        await post_scan_job(client)
        await client.delete(FIRST_JOB_PATH)
        assert await read_state(client) is ScannerState.IDLE
```

- [ ] **Passo 6: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/simulator/test_fake_escl_scanner_app.py -v`

Expected: resumo `7 failed, 11 passed`; falham `test_post_answers_201_with_the_location_of_the_first_job`, `test_second_job_receives_the_next_number`, `test_next_document_answers_503_while_busy_polls_remain_then_200` e mais 4 (erros: `KeyError`, `AssertionError`). Os demais já passam.

- [ ] **Passo 7: Implementar o mínimo**

Acrescente as constantes de estado e de tipo de mídia, o leitor do `ScanSettings`, a página mínima e o trabalho em memória; depois substitua a classe `FakeEsclScanner` e a função `create_fake_escl_scanner_app` pelas versões com os cinco handlers.

Substitua o bloco de importações de `src/digitalizadora/simulator/fake_escl_scanner_app.py` (as linhas `import` e `from` do topo do arquivo) por:

```python
import io
import xml.etree.ElementTree as ElementTree
from collections.abc import Sequence
from dataclasses import dataclass
from http import HTTPStatus

from fastapi import FastAPI, Request, Response
from PIL import Image
```

Em `src/digitalizadora/simulator/fake_escl_scanner_app.py`, logo depois de `NAMESPACE_DECLARATIONS`, acrescente:

```python
PROCESSING_STATE_NAME = "Processing"
JPEG_MEDIA_TYPE = "image/jpeg"
FIRST_JOB_NUMBER = 1
```

Em `src/digitalizadora/simulator/fake_escl_scanner_app.py`, logo depois de `build_status_document`, acrescente:

```python
class InvalidScanSettingsError(ValueError):
    """The posted ScanSettings document cannot be served."""


@dataclass(frozen=True)
class RequestedScan:
    region_width: int
    region_height: int
    dots_per_inch: int
    color_mode: str


PILLOW_MODE_BY_COLOR_MODE = {"RGB24": "RGB", "Grayscale8": "L"}


def _local_name(tag: str) -> str:
    return tag.rpartition("}")[2]


def parse_requested_scan(document: bytes) -> RequestedScan:
    try:
        root = ElementTree.fromstring(document)
    except ElementTree.ParseError as error:
        raise InvalidScanSettingsError("ScanSettings is not well-formed XML") from error
    values = {_local_name(element.tag): (element.text or "").strip() for element in root.iter()}
    try:
        return RequestedScan(
            region_width=int(values["Width"]),
            region_height=int(values["Height"]),
            dots_per_inch=int(values["XResolution"]),
            color_mode=values["ColorMode"],
        )
    except (KeyError, ValueError) as error:
        raise InvalidScanSettingsError("ScanSettings lacks a required number or color mode") from error


def build_synthetic_page(requested_scan: RequestedScan, page_number: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("L", (1, 1), "white").save(buffer, format="JPEG")
    return buffer.getvalue()


@dataclass
class _ScanJob:
    job_number: int
    requested_scan: RequestedScan
    busy_polls_remaining: int
    page_delivered: bool = False
```

Em `src/digitalizadora/simulator/fake_escl_scanner_app.py`, substitua por inteiro `FakeEsclScanner` por:

```python
class FakeEsclScanner:
    def __init__(self, behavior: FakeScannerBehavior) -> None:
        self._behavior = behavior
        self._jobs: dict[int, _ScanJob] = {}
        self._next_job_number = FIRST_JOB_NUMBER

    async def read_capabilities(self) -> Response:
        return Response(content=build_capabilities_document(SUPPORTED_COLOR_MODES), media_type=XML_MEDIA_TYPE)

    async def read_status(self) -> Response:
        return Response(content=build_status_document(self._current_state_name()), media_type=XML_MEDIA_TYPE)

    async def create_job(self, request: Request) -> Response:
        requested_scan = parse_requested_scan(await request.body())
        job_number = self._next_job_number
        self._next_job_number += 1
        self._jobs[job_number] = _ScanJob(job_number, requested_scan, self._behavior.busy_polls_before_document)
        return Response(
            status_code=HTTPStatus.CREATED,
            headers={"Location": f"{SCANNER_PATH_PREFIX}/ScanJobs/{job_number}"},
        )

    async def next_document(self, job_number: int) -> Response:
        job = self._jobs.get(job_number)
        if job is None or job.page_delivered:
            return Response(status_code=HTTPStatus.NOT_FOUND)
        if job.busy_polls_remaining > 0:
            job.busy_polls_remaining -= 1
            return Response(status_code=HTTPStatus.SERVICE_UNAVAILABLE)
        job.page_delivered = True
        page = build_synthetic_page(job.requested_scan, job.job_number)
        return Response(content=page, media_type=JPEG_MEDIA_TYPE)

    async def delete_job(self, job_number: int) -> Response:
        if self._jobs.pop(job_number, None) is None:
            return Response(status_code=HTTPStatus.NOT_FOUND)
        return Response(status_code=HTTPStatus.OK)

    def _current_state_name(self) -> str:
        if any(not job.page_delivered for job in self._jobs.values()):
            return PROCESSING_STATE_NAME
        return self._behavior.initial_state
```

Em `src/digitalizadora/simulator/fake_escl_scanner_app.py`, substitua por inteiro `create_fake_escl_scanner_app` por:

```python
def create_fake_escl_scanner_app(behavior: FakeScannerBehavior) -> FastAPI:
    scanner = FakeEsclScanner(behavior)
    app = FastAPI(title="Fake eSCL scanner", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_api_route(f"{SCANNER_PATH_PREFIX}/ScannerCapabilities", scanner.read_capabilities, methods=["GET"])
    app.add_api_route(f"{SCANNER_PATH_PREFIX}/ScannerStatus", scanner.read_status, methods=["GET"])
    app.add_api_route(f"{SCANNER_PATH_PREFIX}/ScanJobs", scanner.create_job, methods=["POST"])
    job_path = f"{SCANNER_PATH_PREFIX}/ScanJobs/{{job_number}}"
    app.add_api_route(f"{job_path}/NextDocument", scanner.next_document, methods=["GET"])
    app.add_api_route(job_path, scanner.delete_job, methods=["DELETE"])
    return app
```

- [ ] **Passo 8: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/simulator/test_fake_escl_scanner_app.py -v`

Expected: `18 passed`.

- [ ] **Passo 9: Escrever o teste que falha** (ciclo 3: Conteúdo da página sintética)

A página tem (Width x dots_per_inch // 300) x (Height x dots_per_inch // 300) pixels, é RGB ou L conforme o modo de cor, tem fundo branco, uma moldura escura a 2% das bordas e o texto "Pagina N", e **não carrega densidade (dpi)**: o aplicativo é que precisa gravá-la. O texto não leva acento porque a fonte embutida do Pillow (`ImageFont.load_default`) não tem o glifo "á" e o desenharia como um quadrado. O ciclo ainda confirma que o simulador aceita o documento gerado pela função real da Task 3.

Substitua o bloco de importações de `tests/simulator/test_fake_escl_scanner_app.py` (as linhas `import` e `from` do topo do arquivo) por:

```python
import io
from http import HTTPStatus

import httpx
from PIL import Image

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanner_status import ScannerState
from digitalizadora.infrastructure.escl.escl_protocol import (
    ESCL_UNITS_PER_INCH,
    build_scan_settings_xml,
    parse_scanner_capabilities,
    parse_scanner_status,
)
from digitalizadora.simulator.fake_escl_scanner_app import (
    PLATEN_MAXIMUM_HEIGHT,
    PLATEN_MAXIMUM_WIDTH,
    FakeScannerBehavior,
    create_fake_escl_scanner_app,
    frame_margins_in_pixels,
)
```

Em `tests/simulator/test_fake_escl_scanner_app.py`, logo depois de `JPEG_START_OF_IMAGE`, acrescente:

```python
DARK_LEVEL_LIMIT = 100
LIGHT_LEVEL_LIMIT = 240
```

Em `tests/simulator/test_fake_escl_scanner_app.py`, logo depois de `post_scan_job`, acrescente:

```python
async def read_scanned_page(client: httpx.AsyncClient, color_mode: str = "RGB24") -> Image.Image:
    await post_scan_job(client, color_mode=color_mode)
    response = await client.get(FIRST_DOCUMENT_PATH)
    return Image.open(io.BytesIO(response.content))
```

Acrescente ao final de `tests/simulator/test_fake_escl_scanner_app.py`:

```python
async def test_page_size_follows_the_region_and_the_resolution() -> None:
    async with build_client(FakeScannerBehavior(busy_polls_before_document=0)) as client:
        image = await read_scanned_page(client)
    assert image.size == (
        PLATEN_MAXIMUM_WIDTH * FAST_RESOLUTION // ESCL_UNITS_PER_INCH,
        PLATEN_MAXIMUM_HEIGHT * FAST_RESOLUTION // ESCL_UNITS_PER_INCH,
    )


async def test_color_mode_rgb24_returns_an_rgb_image() -> None:
    async with build_client(FakeScannerBehavior(busy_polls_before_document=0)) as client:
        image = await read_scanned_page(client, color_mode="RGB24")
    assert image.mode == "RGB"


async def test_color_mode_grayscale8_returns_a_luminance_image() -> None:
    async with build_client(FakeScannerBehavior(busy_polls_before_document=0)) as client:
        image = await read_scanned_page(client, color_mode="Grayscale8")
    assert image.mode == "L"


async def test_page_carries_no_resolution_metadata() -> None:
    async with build_client(FakeScannerBehavior(busy_polls_before_document=0)) as client:
        image = await read_scanned_page(client)
    assert "dpi" not in image.info


async def test_page_has_a_dark_frame_close_to_the_edges() -> None:
    async with build_client(FakeScannerBehavior(busy_polls_before_document=0)) as client:
        image = await read_scanned_page(client)
    width_pixels, height_pixels = image.size
    margin_x, _ = frame_margins_in_pixels(image.size)
    frame_pixel = image.convert("L").getpixel((margin_x + 1, height_pixels // 2))
    assert frame_pixel < DARK_LEVEL_LIMIT


async def test_page_background_is_white() -> None:
    async with build_client(FakeScannerBehavior(busy_polls_before_document=0)) as client:
        image = await read_scanned_page(client)
    width_pixels, height_pixels = image.size
    assert image.convert("L").getpixel((width_pixels // 2, height_pixels // 2)) > LIGHT_LEVEL_LIMIT


async def test_accepts_the_settings_document_built_by_the_protocol_module() -> None:
    async with build_client(FakeScannerBehavior(busy_polls_before_document=0)) as client:
        capabilities = parse_scanner_capabilities((await client.get(CAPABILITIES_PATH)).content)
        settings_document = build_scan_settings_xml(ScanSettings(FAST_RESOLUTION, ColorMode.GRAYSCALE), capabilities)
        await client.post(SCAN_JOBS_PATH, content=settings_document, headers={"Content-Type": "text/xml"})
        image = Image.open(io.BytesIO((await client.get(FIRST_DOCUMENT_PATH)).content))
    expected_size = (
        PLATEN_MAXIMUM_WIDTH * FAST_RESOLUTION // ESCL_UNITS_PER_INCH,
        PLATEN_MAXIMUM_HEIGHT * FAST_RESOLUTION // ESCL_UNITS_PER_INCH,
    )
    assert (image.mode, image.size) == ("L", expected_size)
```

- [ ] **Passo 10: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/simulator/test_fake_escl_scanner_app.py -v`

Expected: o pytest aborta na coleta com `ImportError: cannot import name 'frame_margins_in_pixels' from 'digitalizadora.simulator.fake_escl_scanner_app'` (resumo: `1 error`).

- [ ] **Passo 11: Implementar o mínimo**

Acrescente as constantes e os desenhistas da página e substitua `build_synthetic_page` pela versão completa.

Substitua o bloco de importações de `src/digitalizadora/simulator/fake_escl_scanner_app.py` (as linhas `import` e `from` do topo do arquivo) por:

```python
import io
import xml.etree.ElementTree as ElementTree
from collections.abc import Sequence
from dataclasses import dataclass
from http import HTTPStatus

from fastapi import FastAPI, Request, Response
from PIL import Image, ImageDraw, ImageFont

from digitalizadora.infrastructure.escl.escl_protocol import ESCL_UNITS_PER_INCH
```

Em `src/digitalizadora/simulator/fake_escl_scanner_app.py`, logo depois de `parse_requested_scan`, acrescente:

```python
FRAME_MARGIN_RATIO = 0.02
FRAME_LINE_WIDTH_PIXELS = 3
INK_COLOR = "#282828"
LABEL_HEIGHT_DIVISOR = 15
LABEL_OFFSET_IN_MARGINS = 2
PAGE_LABEL_PREFIX = "Pagina"
JPEG_QUALITY = 85


def page_size_in_pixels(requested_scan: RequestedScan) -> tuple[int, int]:
    width_pixels = requested_scan.region_width * requested_scan.dots_per_inch // ESCL_UNITS_PER_INCH
    height_pixels = requested_scan.region_height * requested_scan.dots_per_inch // ESCL_UNITS_PER_INCH
    return width_pixels, height_pixels


def frame_margins_in_pixels(size_in_pixels: tuple[int, int]) -> tuple[int, int]:
    width_pixels, height_pixels = size_in_pixels
    return int(width_pixels * FRAME_MARGIN_RATIO), int(height_pixels * FRAME_MARGIN_RATIO)


def _draw_frame(draw: ImageDraw.ImageDraw, size_in_pixels: tuple[int, int]) -> None:
    width_pixels, height_pixels = size_in_pixels
    margin_x, margin_y = frame_margins_in_pixels(size_in_pixels)
    draw.rectangle(
        (margin_x, margin_y, width_pixels - 1 - margin_x, height_pixels - 1 - margin_y),
        outline=INK_COLOR,
        width=FRAME_LINE_WIDTH_PIXELS,
    )


def _draw_label(draw: ImageDraw.ImageDraw, size_in_pixels: tuple[int, int], page_number: int) -> None:
    font = ImageFont.load_default(size=size_in_pixels[1] // LABEL_HEIGHT_DIVISOR)
    margin_x, margin_y = frame_margins_in_pixels(size_in_pixels)
    label_position = (margin_x * LABEL_OFFSET_IN_MARGINS, margin_y * LABEL_OFFSET_IN_MARGINS)
    draw.text(label_position, f"{PAGE_LABEL_PREFIX} {page_number}", fill=INK_COLOR, font=font)
```

Em `src/digitalizadora/simulator/fake_escl_scanner_app.py`, substitua por inteiro `build_synthetic_page` por:

```python
def build_synthetic_page(requested_scan: RequestedScan, page_number: int) -> bytes:
    size_in_pixels = page_size_in_pixels(requested_scan)
    image = Image.new(PILLOW_MODE_BY_COLOR_MODE[requested_scan.color_mode], size_in_pixels, "white")
    draw = ImageDraw.Draw(image)
    _draw_frame(draw, size_in_pixels)
    _draw_label(draw, size_in_pixels, page_number)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY)
    return buffer.getvalue()
```

- [ ] **Passo 12: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/simulator/test_fake_escl_scanner_app.py -v`

Expected: `25 passed`.

- [ ] **Passo 13: Escrever o teste que falha** (ciclo 4: Falhas injetadas e pedidos inválidos)

O simulador precisa reproduzir os maus comportamentos reais: `post_status_code` diferente de 201 (409 e 503) responde sem `Location` e sem criar trabalho; `document_status_code` diferente de 200 substitui a entrega (mas só depois das respostas 503); XML malformado, resolução ausente ou zero e modo de cor desconhecido recebem 400.

Substitua o bloco de importações de `tests/simulator/test_fake_escl_scanner_app.py` (as linhas `import` e `from` do topo do arquivo) por:

```python
import io
from http import HTTPStatus

import httpx
import pytest
from PIL import Image

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanner_status import ScannerState
from digitalizadora.infrastructure.escl.escl_protocol import (
    ESCL_UNITS_PER_INCH,
    build_scan_settings_xml,
    parse_scanner_capabilities,
    parse_scanner_status,
)
from digitalizadora.simulator.fake_escl_scanner_app import (
    PLATEN_MAXIMUM_HEIGHT,
    PLATEN_MAXIMUM_WIDTH,
    FakeScannerBehavior,
    create_fake_escl_scanner_app,
    frame_margins_in_pixels,
)
```

Acrescente ao final de `tests/simulator/test_fake_escl_scanner_app.py`:

```python
@pytest.mark.parametrize("status_code", [HTTPStatus.CONFLICT, HTTPStatus.SERVICE_UNAVAILABLE])
async def test_post_status_code_is_returned_without_a_location(status_code: int) -> None:
    async with build_client(FakeScannerBehavior(post_status_code=status_code)) as client:
        response = await post_scan_job(client)
    assert (response.status_code, "Location" in response.headers) == (status_code, False)


async def test_a_refused_post_does_not_make_the_scanner_busy() -> None:
    async with build_client(FakeScannerBehavior(post_status_code=HTTPStatus.CONFLICT)) as client:
        await post_scan_job(client)
        assert await read_state(client) is ScannerState.IDLE


async def test_document_status_code_replaces_the_success_answer() -> None:
    behavior = FakeScannerBehavior(busy_polls_before_document=0, document_status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
    async with build_client(behavior) as client:
        await post_scan_job(client)
        response = await client.get(FIRST_DOCUMENT_PATH)
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


async def test_busy_polls_still_come_before_the_replaced_document_answer() -> None:
    behavior = FakeScannerBehavior(busy_polls_before_document=1, document_status_code=HTTPStatus.NOT_FOUND)
    async with build_client(behavior) as client:
        await post_scan_job(client)
        statuses = [(await client.get(FIRST_DOCUMENT_PATH)).status_code for _ in range(2)]
    assert statuses == [503, 404]


async def test_malformed_settings_answer_400() -> None:
    async with build_client() as client:
        response = await client.post(
            SCAN_JOBS_PATH, content=b"<scan:ScanSettings", headers={"Content-Type": "text/xml"}
        )
    assert response.status_code == HTTPStatus.BAD_REQUEST


async def test_settings_without_resolution_answer_400() -> None:
    document = build_settings_document(FAST_RESOLUTION, "RGB24").replace(b"XResolution", b"Ignored")
    async with build_client() as client:
        response = await client.post(SCAN_JOBS_PATH, content=document, headers={"Content-Type": "text/xml"})
    assert response.status_code == HTTPStatus.BAD_REQUEST


async def test_unsupported_color_mode_answers_400() -> None:
    async with build_client() as client:
        response = await post_scan_job(client, color_mode="BlackAndWhite1")
    assert response.status_code == HTTPStatus.BAD_REQUEST


async def test_zero_resolution_answers_400() -> None:
    async with build_client() as client:
        response = await post_scan_job(client, dots_per_inch=0)
    assert response.status_code == HTTPStatus.BAD_REQUEST
```

- [ ] **Passo 14: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/simulator/test_fake_escl_scanner_app.py -v`

Expected: resumo `9 failed, 25 passed`; falham `test_post_status_code_is_returned_without_a_location`, `test_a_refused_post_does_not_make_the_scanner_busy`, `test_document_status_code_replaces_the_success_answer` e mais 5 (erros: `AssertionError`, `InvalidScanSettingsError`). Os demais já passam.

- [ ] **Passo 15: Implementar o mínimo**

Acrescente o registro (`logger`), a validação `ensure_servable` e substitua os métodos `create_job` e `next_document` pelas versões finais.

Substitua o bloco de importações de `src/digitalizadora/simulator/fake_escl_scanner_app.py` (as linhas `import` e `from` do topo do arquivo) por:

```python
import io
import logging
import xml.etree.ElementTree as ElementTree
from collections.abc import Sequence
from dataclasses import dataclass
from http import HTTPStatus

from fastapi import FastAPI, Request, Response
from PIL import Image, ImageDraw, ImageFont

from digitalizadora.infrastructure.escl.escl_protocol import ESCL_UNITS_PER_INCH
```

Em `src/digitalizadora/simulator/fake_escl_scanner_app.py`, logo depois do bloco de importações, acrescente:

```python
logger = logging.getLogger(__name__)
```

Em `src/digitalizadora/simulator/fake_escl_scanner_app.py`, logo depois de `JPEG_QUALITY`, acrescente:

```python
MINIMUM_PAGE_SIZE_PIXELS = 1
```

Em `src/digitalizadora/simulator/fake_escl_scanner_app.py`, logo depois de `page_size_in_pixels`, acrescente:

```python
def ensure_servable(requested_scan: RequestedScan) -> None:
    if requested_scan.color_mode not in PILLOW_MODE_BY_COLOR_MODE:
        raise InvalidScanSettingsError(f"Unsupported color mode {requested_scan.color_mode}")
    if min(page_size_in_pixels(requested_scan)) < MINIMUM_PAGE_SIZE_PIXELS:
        raise InvalidScanSettingsError("The requested region is smaller than one pixel")
```

Em `src/digitalizadora/simulator/fake_escl_scanner_app.py`, substitua por inteiro o método `create_job` da classe `FakeEsclScanner` por (as reticências `...` representam o resto da classe, que não muda):

```python
class FakeEsclScanner:
    ...

    async def create_job(self, request: Request) -> Response:
        if self._behavior.post_status_code != HTTPStatus.CREATED:
            return Response(status_code=self._behavior.post_status_code)
        try:
            requested_scan = parse_requested_scan(await request.body())
            ensure_servable(requested_scan)
        except InvalidScanSettingsError as error:
            logger.info("Rejected scan settings: %s", error)
            return Response(status_code=HTTPStatus.BAD_REQUEST)
        job_number = self._next_job_number
        self._next_job_number += 1
        self._jobs[job_number] = _ScanJob(job_number, requested_scan, self._behavior.busy_polls_before_document)
        return Response(
            status_code=HTTPStatus.CREATED,
            headers={"Location": f"{SCANNER_PATH_PREFIX}/ScanJobs/{job_number}"},
        )
```

Em `src/digitalizadora/simulator/fake_escl_scanner_app.py`, substitua por inteiro o método `next_document` da classe `FakeEsclScanner` por (as reticências `...` representam o resto da classe, que não muda):

```python
class FakeEsclScanner:
    ...

    async def next_document(self, job_number: int) -> Response:
        job = self._jobs.get(job_number)
        if job is None or job.page_delivered:
            return Response(status_code=HTTPStatus.NOT_FOUND)
        if job.busy_polls_remaining > 0:
            job.busy_polls_remaining -= 1
            return Response(status_code=HTTPStatus.SERVICE_UNAVAILABLE)
        if self._behavior.document_status_code != HTTPStatus.OK:
            return Response(status_code=self._behavior.document_status_code)
        job.page_delivered = True
        page = build_synthetic_page(job.requested_scan, job.job_number)
        return Response(content=page, media_type=JPEG_MEDIA_TYPE)
```

- [ ] **Passo 16: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/simulator/test_fake_escl_scanner_app.py -v`

Expected: `34 passed`.

- [ ] **Passo 17: Rodar a verificação estática e a lentidão dos testes**

Run: `make lint && .venv/bin/pytest tests/simulator/test_fake_escl_scanner_app.py --durations=3`

Expected: o lint sem erros do ruff e `34 passed`, com os três testes mais lentos abaixo de 100 ms.

- [ ] **Passo 18: Commit**

```bash
git add src/digitalizadora/simulator/fake_escl_scanner_app.py tests/simulator/test_fake_escl_scanner_app.py
git commit -m "feat(simulator): add the fake eSCL scanner ASGI application"
```

### Task 5: EsclScannerGateway

**Objetivo:** Implementar o adaptador `EsclScannerGateway`, que executa o fluxo eSCL completo (estado, `POST`, `NextDocument`, `DELETE`) sobre um `httpx.AsyncClient` injetado, com tempos e esperas injetados.

**Files:**
- Create: `src/digitalizadora/infrastructure/escl/escl_scanner_gateway.py`
- Create: `tests/fakes/recording_sleep.py`
- Test: `tests/infrastructure/test_escl_scanner_gateway.py`

**Interfaces:**
- Consumes:
  - Task 2: `ColorMode`, `ScanSettings`, `ScannedImage`, `ScannerCapabilities` (com `supports_color_mode`), `ScannerStatus` (com `is_ready`), `ScannerState`, os erros de `digitalizadora.domain.errors` e `tests/fakes/sample_images.py::build_sample_jpeg`.
  - Task 3: `build_scan_settings_xml(settings, capabilities) -> bytes`, `parse_scanner_capabilities(document: bytes)`, `parse_scanner_status(document: bytes)` e `extract_job_path(location_header: str) -> str` (devolve só o caminho, começando por `/`, ignorando o host do cabeçalho).
  - Task 4: `create_fake_escl_scanner_app`, `FakeScannerBehavior`, `build_capabilities_document(color_modes)`, `build_status_document(state_name)` e `SUPPORTED_COLOR_MODES` de `digitalizadora.simulator.fake_escl_scanner_app`.
- Produces:
  - `digitalizadora.infrastructure.escl.escl_scanner_gateway.EsclGatewayTiming` (dataclass congelada: `sleep`, `monotonic_clock`, `document_poll_interval_seconds=1.5`, `busy_wait_seconds=30.0`, `scan_timeout_seconds=300.0`, `cleanup_timeout_seconds=10.0`).
  - `EsclScannerGateway(http_client: httpx.AsyncClient, base_address: str, timing: EsclGatewayTiming)` com `read_capabilities()` (em cache), `read_status()` e `scan_page(settings) -> ScannedImage`; implementa `ScannerGateway`. Nunca cria o cliente HTTP: o composition root (Task 13) o entrega, com `follow_redirects=False`.
  - `tests/fakes/recording_sleep.py::RecordingSleep` (`delays: list[float]`, `async __call__(seconds)`), usado também pelos testes das Tasks 10 e 14.

**Notas da tarefa**
- API do `httpx` 0.27.2 verificada no Python global: `AsyncClient.build_request(method, url, *, content, headers, timeout)`, `AsyncClient.send(request, *, follow_redirects=...)`, `Timeout(timeout, *, connect=...)`, `MockTransport(handler)` (o handler pode ser assíncrono e pode lançar exceções), `ASGITransport(app=...)`, `AsyncBaseTransport.handle_async_request`, `Response.is_error` e a hierarquia `ConnectError` ⊂ `NetworkError` ⊂ `TransportError`.
- Suposição sobre a Task 3: `extract_job_path` devolve só o caminho do cabeçalho `Location` (começando em `/`) e ignora o host; o gateway ainda remove uma barra final. Os testes do gateway usam o parser real da Task 3 sobre o XML do simulador.
- `errno.EHOSTUNREACH` vale 65 no macOS (o alvo do projeto); o código e o teste usam a constante do módulo `errno`, não o número.
- Relógio determinístico: `SleepDrivenClock` (no módulo de teste) devolve a soma das esperas registradas por `RecordingSleep`; assim `monotonic_clock` só avança quando o gateway espera e nenhum teste dorme de verdade.
- Review Focus: modo 1 (impressora ocupada, recusando, offline ou bloqueada pela Rede Local) e modo 4 (resposta que não é JPEG: PDF, corpo vazio, tipo ausente).

- [ ] **Passo 1: Escrever o teste que falha** (ciclo 1: Digitalização feliz contra a impressora falsa)

O primeiro ciclo cobre o caminho feliz de ponta a ponta contra o simulador da Task 4 (via `httpx.ASGITransport`): a imagem volta como `ScannedImage` JPEG, o `DELETE` do trabalho é enviado exatamente uma vez, o corpo do `POST` é exatamente o que `build_scan_settings_xml` gera, o `Content-Type` é `text/xml` e as capacidades são lidas uma única vez por gateway. `RecordingSleep` registra as esperas sem dormir, e `SleepDrivenClock` faz o tempo "decorrer" apenas quando o gateway espera, o que torna todos os testes de prazo determinísticos. Aqui o simulador entrega a página sem respostas 503 (`busy_polls_before_document=0`); a espera pelo documento chega no ciclo 5.

Crie `tests/fakes/recording_sleep.py` com o conteúdo:

```python
class RecordingSleep:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)
```

Crie `tests/infrastructure/test_escl_scanner_gateway.py` com o conteúdo:

```python
from dataclasses import dataclass

import httpx

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanner_status import ScannerState
from digitalizadora.infrastructure.escl.escl_protocol import (
    build_scan_settings_xml,
    parse_scanner_capabilities,
)
from digitalizadora.infrastructure.escl.escl_scanner_gateway import (
    EsclGatewayTiming,
    EsclScannerGateway,
)
from digitalizadora.simulator.fake_escl_scanner_app import (
    SUPPORTED_COLOR_MODES,
    FakeScannerBehavior,
    build_capabilities_document,
    create_fake_escl_scanner_app,
)
from tests.fakes.recording_sleep import RecordingSleep

SCANNER_HOST = "scanner.test"
BASE_ADDRESS = f"http://{SCANNER_HOST}/eSCL"
JOB_PATH = "/eSCL/ScanJobs/1"
CAPABILITIES_ROUTE = "GET /eSCL/ScannerCapabilities"
POST_ROUTE = "POST /eSCL/ScanJobs"
DELETE_ROUTE = f"DELETE {JOB_PATH}"
SCAN_SETTINGS = ScanSettings(dots_per_inch=75, color_mode=ColorMode.COLOR)
TEST_BUSY_WAIT_SECONDS = 6.0
TEST_SCAN_TIMEOUT_SECONDS = 6.0


class RecordingTransport(httpx.AsyncBaseTransport):
    def __init__(self, inner_transport: httpx.AsyncBaseTransport) -> None:
        self._inner_transport = inner_transport
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return await self._inner_transport.handle_async_request(request)

    def count(self, route: str) -> int:
        return sum(1 for request in self.requests if f"{request.method} {request.url.path}" == route)

    def find(self, route: str) -> httpx.Request:
        return next(request for request in self.requests if f"{request.method} {request.url.path}" == route)


class SleepDrivenClock:
    def __init__(self, recording_sleep: RecordingSleep) -> None:
        self._recording_sleep = recording_sleep

    def __call__(self) -> float:
        return sum(self._recording_sleep.delays)


@dataclass(frozen=True)
class GatewayHarness:
    gateway: EsclScannerGateway
    transport: RecordingTransport
    sleep: RecordingSleep


def build_harness(
    inner_transport: httpx.AsyncBaseTransport,
    busy_wait_seconds: float = TEST_BUSY_WAIT_SECONDS,
    scan_timeout_seconds: float = TEST_SCAN_TIMEOUT_SECONDS,
) -> GatewayHarness:
    sleep = RecordingSleep()
    transport = RecordingTransport(inner_transport)
    timing = EsclGatewayTiming(
        sleep=sleep,
        monotonic_clock=SleepDrivenClock(sleep),
        busy_wait_seconds=busy_wait_seconds,
        scan_timeout_seconds=scan_timeout_seconds,
    )
    http_client = httpx.AsyncClient(transport=transport, follow_redirects=True)
    return GatewayHarness(EsclScannerGateway(http_client, BASE_ADDRESS, timing), transport, sleep)


def fake_scanner_harness(behavior: FakeScannerBehavior | None = None) -> GatewayHarness:
    app = create_fake_escl_scanner_app(behavior or FakeScannerBehavior())
    return build_harness(httpx.ASGITransport(app=app))


def immediate_document_harness() -> GatewayHarness:
    return fake_scanner_harness(FakeScannerBehavior(busy_polls_before_document=0))


async def test_scan_page_returns_a_jpeg_image() -> None:
    harness = immediate_document_harness()
    scanned_image = await harness.gateway.scan_page(SCAN_SETTINGS)
    assert (scanned_image.media_type, scanned_image.content[:2]) == ("image/jpeg", b"\xff\xd8")


async def test_scan_page_sends_exactly_one_delete_after_a_success() -> None:
    harness = immediate_document_harness()
    await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.transport.count(DELETE_ROUTE) == 1


async def test_post_body_is_the_scan_settings_document() -> None:
    harness = immediate_document_harness()
    await harness.gateway.scan_page(SCAN_SETTINGS)
    capabilities = parse_scanner_capabilities(build_capabilities_document(SUPPORTED_COLOR_MODES))
    assert harness.transport.find(POST_ROUTE).content == build_scan_settings_xml(SCAN_SETTINGS, capabilities)


async def test_post_declares_a_text_xml_body() -> None:
    harness = immediate_document_harness()
    await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.transport.find(POST_ROUTE).headers["Content-Type"] == "text/xml"


async def test_read_capabilities_is_cached_per_gateway() -> None:
    harness = immediate_document_harness()
    first = await harness.gateway.read_capabilities()
    second = await harness.gateway.read_capabilities()
    assert (first, harness.transport.count(CAPABILITIES_ROUTE)) == (second, 1)


async def test_scan_page_reuses_the_cached_capabilities() -> None:
    harness = immediate_document_harness()
    await harness.gateway.read_capabilities()
    await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.transport.count(CAPABILITIES_ROUTE) == 1


async def test_read_status_parses_the_scanner_status() -> None:
    harness = immediate_document_harness()
    status = await harness.gateway.read_status()
    assert status.state is ScannerState.IDLE
```

- [ ] **Passo 2: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/infrastructure/test_escl_scanner_gateway.py -v`

Expected: o pytest aborta na coleta com `ModuleNotFoundError: No module named 'digitalizadora.infrastructure.escl.escl_scanner_gateway'` (resumo: `1 error`).

- [ ] **Passo 3: Implementar o mínimo**

Crie o gateway com as constantes de caminho, o `EsclGatewayTiming` completo e a primeira versão do fluxo (sem validações; elas chegam nos próximos ciclos).

Crie `src/digitalizadora/infrastructure/escl/escl_scanner_gateway.py` com o conteúdo:

```python
"""eSCL scanner gateway: speaks HTTP to the printer through an injected httpx client."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.domain.scanner_capabilities import ScannerCapabilities
from digitalizadora.domain.scanner_status import ScannerStatus
from digitalizadora.infrastructure.escl.escl_protocol import (
    build_scan_settings_xml,
    extract_job_path,
    parse_scanner_capabilities,
    parse_scanner_status,
)

CAPABILITIES_PATH = "ScannerCapabilities"
STATUS_PATH = "ScannerStatus"
SCAN_JOBS_PATH = "ScanJobs"
NEXT_DOCUMENT_PATH = "NextDocument"
XML_MEDIA_TYPE = "text/xml"
JPEG_MEDIA_TYPE = "image/jpeg"
LOCATION_HEADER = "Location"
CONNECT_TIMEOUT_SECONDS = 5.0
READ_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class EsclGatewayTiming:
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    monotonic_clock: Callable[[], float] = time.monotonic
    document_poll_interval_seconds: float = 1.5
    busy_wait_seconds: float = 30.0
    scan_timeout_seconds: float = 300.0
    cleanup_timeout_seconds: float = 10.0


def _build_scanned_image(response: httpx.Response) -> ScannedImage:
    return ScannedImage(content=response.content, media_type=JPEG_MEDIA_TYPE)


class EsclScannerGateway:
    def __init__(self, http_client: httpx.AsyncClient, base_address: str, timing: EsclGatewayTiming) -> None:
        self._http_client = http_client
        self._base_address = base_address.rstrip("/")
        self._timing = timing
        address_parts = urlsplit(self._base_address)
        self._origin = f"{address_parts.scheme}://{address_parts.netloc}"
        self._default_timeout = httpx.Timeout(READ_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS)
        self._capabilities: ScannerCapabilities | None = None

    async def read_capabilities(self) -> ScannerCapabilities:
        if self._capabilities is None:
            response = await self._get_document(CAPABILITIES_PATH)
            self._capabilities = parse_scanner_capabilities(response.content)
        return self._capabilities

    async def read_status(self) -> ScannerStatus:
        response = await self._get_document(STATUS_PATH)
        return parse_scanner_status(response.content)

    async def scan_page(self, settings: ScanSettings) -> ScannedImage:
        capabilities = await self.read_capabilities()
        job_path = await self._post_job(settings, capabilities)
        try:
            return await self._download_page(job_path)
        finally:
            await self._delete_job(job_path)

    async def _post_job(self, settings: ScanSettings, capabilities: ScannerCapabilities) -> str:
        request = self._http_client.build_request(
            "POST",
            f"{self._base_address}/{SCAN_JOBS_PATH}",
            content=build_scan_settings_xml(settings, capabilities),
            headers={"Content-Type": XML_MEDIA_TYPE},
            timeout=self._default_timeout,
        )
        response = await self._send_request(request)
        return extract_job_path(response.headers[LOCATION_HEADER]).rstrip("/")

    async def _download_page(self, job_path: str) -> ScannedImage:
        request = self._http_client.build_request(
            "GET",
            f"{self._origin}{job_path}/{NEXT_DOCUMENT_PATH}",
            timeout=self._default_timeout,
        )
        return _build_scanned_image(await self._send_request(request))

    async def _delete_job(self, job_path: str) -> None:
        request = self._http_client.build_request(
            "DELETE",
            f"{self._origin}{job_path}",
            timeout=httpx.Timeout(self._timing.cleanup_timeout_seconds),
        )
        await self._send_request(request)

    async def _get_document(self, resource_name: str) -> httpx.Response:
        request = self._http_client.build_request(
            "GET",
            f"{self._base_address}/{resource_name}",
            timeout=self._default_timeout,
        )
        return await self._send_request(request)

    async def _send_request(self, request: httpx.Request) -> httpx.Response:
        return await self._http_client.send(request)
```

- [ ] **Passo 4: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/infrastructure/test_escl_scanner_gateway.py -v`

Expected: `7 passed`.

- [ ] **Passo 5: Escrever o teste que falha** (ciclo 2: Respostas de estado e capacidades; modo de cor não suportado)

Uma resposta diferente de 200 para `ScannerStatus` ou `ScannerCapabilities` significa que o equipamento não está servindo eSCL direito: `ScannerUnreachableError`. E um modo de cor que as capacidades não anunciam é recusado antes de qualquer `POST` (`ScanRejectedError`). Os testes passam a usar `httpx.MockTransport` com respostas roteirizadas (`ScriptedResponses`); `healthy_scripts()` descreve uma impressora saudável e cada teste troca só a rota que lhe interessa.

Substitua o bloco de importações de `tests/infrastructure/test_escl_scanner_gateway.py` (as linhas `import` e `from` do topo do arquivo) por:

```python
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from http import HTTPStatus

import httpx
import pytest

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import ScannerUnreachableError, ScanRejectedError
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanner_status import ScannerState
from digitalizadora.infrastructure.escl.escl_protocol import (
    build_scan_settings_xml,
    parse_scanner_capabilities,
)
from digitalizadora.infrastructure.escl.escl_scanner_gateway import (
    EsclGatewayTiming,
    EsclScannerGateway,
)
from digitalizadora.simulator.fake_escl_scanner_app import (
    SUPPORTED_COLOR_MODES,
    FakeScannerBehavior,
    build_capabilities_document,
    build_status_document,
    create_fake_escl_scanner_app,
)
from tests.fakes.recording_sleep import RecordingSleep
from tests.fakes.sample_images import build_sample_jpeg
```

Em `tests/infrastructure/test_escl_scanner_gateway.py`, logo depois de `TEST_SCAN_TIMEOUT_SECONDS`, acrescente:

```python
STATUS_ROUTE = "GET /eSCL/ScannerStatus"
DOCUMENT_ROUTE = f"GET {JOB_PATH}/NextDocument"
```

Em `tests/infrastructure/test_escl_scanner_gateway.py`, logo depois de `DOCUMENT_ROUTE`, acrescente:

```python
@dataclass(frozen=True)
class Reply:
    status_code: int
    content: bytes = b""
    headers: Mapping[str, str] = field(default_factory=dict)

    def to_response(self) -> httpx.Response:
        return httpx.Response(self.status_code, content=self.content, headers=dict(self.headers))


class ScriptedResponses:
    def __init__(self, scripts: Mapping[str, Sequence[Reply | Exception]]) -> None:
        self._pending = {route: list(replies) for route, replies in scripts.items()}

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        replies = self._pending[f"{request.method} {request.url.path}"]
        reply = replies.pop(0) if len(replies) > 1 else replies[0]
        if isinstance(reply, Exception):
            raise reply
        return reply.to_response()
```

Em `tests/infrastructure/test_escl_scanner_gateway.py`, logo depois de `immediate_document_harness`, acrescente:

```python
def healthy_scripts() -> dict[str, list[Reply | Exception]]:
    return {
        CAPABILITIES_ROUTE: [Reply(HTTPStatus.OK, build_capabilities_document(SUPPORTED_COLOR_MODES))],
        STATUS_ROUTE: [Reply(HTTPStatus.OK, build_status_document("Idle"))],
        POST_ROUTE: [Reply(HTTPStatus.CREATED, headers={"Location": JOB_PATH})],
        DOCUMENT_ROUTE: [Reply(HTTPStatus.OK, build_sample_jpeg(), {"Content-Type": "image/jpeg"})],
        DELETE_ROUTE: [Reply(HTTPStatus.OK)],
    }


def scripted_harness(overrides: Mapping[str, Sequence[Reply | Exception]] | None = None) -> GatewayHarness:
    scripts = {**healthy_scripts(), **(overrides or {})}
    return build_harness(httpx.MockTransport(ScriptedResponses(scripts)))
```

Acrescente ao final de `tests/infrastructure/test_escl_scanner_gateway.py`:

```python
async def test_status_answer_other_than_200_means_unreachable() -> None:
    harness = scripted_harness({STATUS_ROUTE: [Reply(HTTPStatus.SERVICE_UNAVAILABLE)]})
    with pytest.raises(ScannerUnreachableError):
        await harness.gateway.read_status()


async def test_capabilities_answer_other_than_200_means_unreachable() -> None:
    harness = scripted_harness({CAPABILITIES_ROUTE: [Reply(HTTPStatus.INTERNAL_SERVER_ERROR)]})
    with pytest.raises(ScannerUnreachableError):
        await harness.gateway.read_capabilities()


async def test_unsupported_color_mode_is_rejected() -> None:
    color_only = build_capabilities_document(("RGB24",))
    harness = scripted_harness({CAPABILITIES_ROUTE: [Reply(HTTPStatus.OK, color_only)]})
    with pytest.raises(ScanRejectedError):
        await harness.gateway.scan_page(ScanSettings(dots_per_inch=75, color_mode=ColorMode.GRAYSCALE))


async def test_unsupported_color_mode_sends_no_scan_job() -> None:
    color_only = build_capabilities_document(("RGB24",))
    harness = scripted_harness({CAPABILITIES_ROUTE: [Reply(HTTPStatus.OK, color_only)]})
    with pytest.raises(ScanRejectedError):
        await harness.gateway.scan_page(ScanSettings(dots_per_inch=75, color_mode=ColorMode.GRAYSCALE))
    assert harness.transport.count(POST_ROUTE) == 0
```

- [ ] **Passo 6: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/infrastructure/test_escl_scanner_gateway.py -v`

Expected: resumo `4 failed, 7 passed`; falham `test_status_answer_other_than_200_means_unreachable`, `test_capabilities_answer_other_than_200_means_unreachable`, `test_unsupported_color_mode_is_rejected` e mais 1 (erros: `ParseError`, `AssertionError`). Os demais já passam.

- [ ] **Passo 7: Implementar o mínimo**

Acrescente o mapa de modos de cor, a função de validação e substitua `scan_page` e `_get_document`.

Substitua o bloco de importações de `src/digitalizadora/infrastructure/escl/escl_scanner_gateway.py` (as linhas `import` e `from` do topo do arquivo) por:

```python
import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from http import HTTPStatus
from urllib.parse import urlsplit

import httpx

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import ScannerUnreachableError, ScanRejectedError
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.domain.scanner_capabilities import ScannerCapabilities
from digitalizadora.domain.scanner_status import ScannerStatus
from digitalizadora.infrastructure.escl.escl_protocol import (
    build_scan_settings_xml,
    extract_job_path,
    parse_scanner_capabilities,
    parse_scanner_status,
)
```

Em `src/digitalizadora/infrastructure/escl/escl_scanner_gateway.py`, logo depois de `READ_TIMEOUT_SECONDS`, acrescente:

```python
ESCL_COLOR_MODE_BY_COLOR_MODE = {
    ColorMode.COLOR: "RGB24",
    ColorMode.GRAYSCALE: "Grayscale8",
}
```

Em `src/digitalizadora/infrastructure/escl/escl_scanner_gateway.py`, logo depois de `EsclGatewayTiming`, acrescente:

```python
def _ensure_color_mode_is_supported(settings: ScanSettings, capabilities: ScannerCapabilities) -> None:
    escl_color_mode = ESCL_COLOR_MODE_BY_COLOR_MODE[settings.color_mode]
    if not capabilities.supports_color_mode(escl_color_mode):
        raise ScanRejectedError(f"The scanner does not support the color mode {escl_color_mode}")
```

Em `src/digitalizadora/infrastructure/escl/escl_scanner_gateway.py`, substitua por inteiro o método `scan_page` da classe `EsclScannerGateway` por (as reticências `...` representam o resto da classe, que não muda):

```python
class EsclScannerGateway:
    ...

    async def scan_page(self, settings: ScanSettings) -> ScannedImage:
        capabilities = await self.read_capabilities()
        _ensure_color_mode_is_supported(settings, capabilities)
        job_path = await self._post_job(settings, capabilities)
        try:
            return await self._download_page(job_path)
        finally:
            await self._delete_job(job_path)
```

Em `src/digitalizadora/infrastructure/escl/escl_scanner_gateway.py`, substitua por inteiro o método `_get_document` da classe `EsclScannerGateway` por (as reticências `...` representam o resto da classe, que não muda):

```python
class EsclScannerGateway:
    ...

    async def _get_document(self, resource_name: str) -> httpx.Response:
        request = self._http_client.build_request(
            "GET",
            f"{self._base_address}/{resource_name}",
            timeout=self._default_timeout,
        )
        response = await self._send_request(request)
        if response.status_code != HTTPStatus.OK:
            raise ScannerUnreachableError(f"{resource_name} answered {response.status_code}")
        return response
```

- [ ] **Passo 8: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/infrastructure/test_escl_scanner_gateway.py -v`

Expected: `11 passed`.

- [ ] **Passo 9: Escrever o teste que falha** (ciclo 3: Falhas de rede e higiene das requisições)

Regras 7 e 8 do protocolo: `httpx.ConnectError`, tempo de conexão esgotado e demais erros de transporte viram `ScannerUnreachableError`; quando algum elo da cadeia de causas é um `OSError` com `errno.EHOSTUNREACH` (65 no macOS) vira `LocalNetworkBlockedError`. Toda requisição pede `Connection: close` (sem reaproveitar conexão) e nenhum redirecionamento é seguido, mesmo que o cliente injetado tenha `follow_redirects=True` (o `build_harness` dos testes configura o cliente de propósito "errado" para provar isso). O `httpx` encadeia a causa original em duas camadas (`httpx.ConnectError` ← `httpcore.ConnectError` ← `OSError`), por isso o teste percorre a cadeia inteira.

Substitua o bloco de importações de `tests/infrastructure/test_escl_scanner_gateway.py` (as linhas `import` e `from` do topo do arquivo) por:

```python
import errno
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from http import HTTPStatus

import httpx
import pytest

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import (
    LocalNetworkBlockedError,
    ScannerUnreachableError,
    ScanRejectedError,
)
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanner_status import ScannerState
from digitalizadora.infrastructure.escl.escl_protocol import (
    build_scan_settings_xml,
    parse_scanner_capabilities,
)
from digitalizadora.infrastructure.escl.escl_scanner_gateway import (
    EsclGatewayTiming,
    EsclScannerGateway,
)
from digitalizadora.simulator.fake_escl_scanner_app import (
    SUPPORTED_COLOR_MODES,
    FakeScannerBehavior,
    build_capabilities_document,
    build_status_document,
    create_fake_escl_scanner_app,
)
from tests.fakes.recording_sleep import RecordingSleep
from tests.fakes.sample_images import build_sample_jpeg
```

Acrescente ao final de `tests/infrastructure/test_escl_scanner_gateway.py`:

```python
async def test_connection_refused_means_unreachable() -> None:
    harness = scripted_harness({STATUS_ROUTE: [httpx.ConnectError("connection refused")]})
    with pytest.raises(ScannerUnreachableError) as raised:
        await harness.gateway.read_status()
    assert raised.value.code == "scanner_unreachable"


async def test_connect_timeout_means_unreachable() -> None:
    harness = scripted_harness({STATUS_ROUTE: [httpx.ConnectTimeout("no answer")]})
    with pytest.raises(ScannerUnreachableError) as raised:
        await harness.gateway.read_status()
    assert raised.value.code == "scanner_unreachable"


async def test_host_unreachable_cause_means_local_network_blocked() -> None:
    blocked = httpx.ConnectError("no route to host")
    blocked.__cause__ = OSError(errno.EHOSTUNREACH, "No route to host")
    harness = scripted_harness({STATUS_ROUTE: [blocked]})
    with pytest.raises(LocalNetworkBlockedError):
        await harness.gateway.read_status()


async def test_host_unreachable_found_deeper_in_the_cause_chain_means_local_network_blocked() -> None:
    blocked = httpx.ConnectError("no route to host")
    blocked.__cause__ = RuntimeError("transport failure")
    blocked.__cause__.__cause__ = OSError(errno.EHOSTUNREACH, "No route to host")
    harness = scripted_harness({STATUS_ROUTE: [blocked]})
    with pytest.raises(LocalNetworkBlockedError):
        await harness.gateway.read_status()


async def test_other_operating_system_errors_stay_plain_unreachable() -> None:
    refused = httpx.ConnectError("connection refused")
    refused.__cause__ = OSError(errno.ECONNREFUSED, "Connection refused")
    harness = scripted_harness({STATUS_ROUTE: [refused]})
    with pytest.raises(ScannerUnreachableError) as raised:
        await harness.gateway.read_status()
    assert raised.value.code == "scanner_unreachable"


async def test_every_request_asks_the_scanner_to_close_the_connection() -> None:
    harness = immediate_document_harness()
    await harness.gateway.scan_page(SCAN_SETTINGS)
    assert {request.headers["Connection"] for request in harness.transport.requests} == {"close"}


async def test_redirects_are_not_followed_even_when_the_client_would_follow_them() -> None:
    redirect = Reply(HTTPStatus.FOUND, headers={"Location": "http://203.0.113.9/elsewhere"})
    harness = scripted_harness({STATUS_ROUTE: [redirect]})
    with pytest.raises(ScannerUnreachableError):
        await harness.gateway.read_status()
    assert [request.url.host for request in harness.transport.requests] == [SCANNER_HOST]
```

- [ ] **Passo 10: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/infrastructure/test_escl_scanner_gateway.py -v`

Expected: resumo `7 failed, 11 passed`; falham `test_connection_refused_means_unreachable`, `test_connect_timeout_means_unreachable`, `test_host_unreachable_cause_means_local_network_blocked` e mais 4 (erros: `ConnectError`, `ConnectTimeout`, `AssertionError`, `KeyError`). Os demais já passam.

- [ ] **Passo 11: Implementar o mínimo**

Acrescente as constantes, os dois tradutores de erro de transporte e substitua `_send_request`.

Substitua o bloco de importações de `src/digitalizadora/infrastructure/escl/escl_scanner_gateway.py` (as linhas `import` e `from` do topo do arquivo) por:

```python
import asyncio
import errno
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from http import HTTPStatus
from urllib.parse import urlsplit

import httpx

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import (
    LocalNetworkBlockedError,
    ScannerUnreachableError,
    ScanRejectedError,
)
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.domain.scanner_capabilities import ScannerCapabilities
from digitalizadora.domain.scanner_status import ScannerStatus
from digitalizadora.infrastructure.escl.escl_protocol import (
    build_scan_settings_xml,
    extract_job_path,
    parse_scanner_capabilities,
    parse_scanner_status,
)
```

Em `src/digitalizadora/infrastructure/escl/escl_scanner_gateway.py`, logo depois de `READ_TIMEOUT_SECONDS`, acrescente:

```python
CLOSE_CONNECTION_HEADERS = {"Connection": "close"}
LOCAL_NETWORK_BLOCKED_ERRNO = errno.EHOSTUNREACH
```

Em `src/digitalizadora/infrastructure/escl/escl_scanner_gateway.py`, logo depois de `_ensure_color_mode_is_supported`, acrescente:

```python
def _is_local_network_blocked(error: httpx.TransportError) -> bool:
    cause = error.__cause__
    while cause is not None:
        if isinstance(cause, OSError) and cause.errno == LOCAL_NETWORK_BLOCKED_ERRNO:
            return True
        cause = cause.__cause__
    return False


def _translate_transport_error(error: httpx.TransportError) -> ScannerUnreachableError:
    if _is_local_network_blocked(error):
        return LocalNetworkBlockedError(f"The operating system blocked local network access: {error}")
    return ScannerUnreachableError(f"The scanner could not be reached: {error}")
```

Em `src/digitalizadora/infrastructure/escl/escl_scanner_gateway.py`, substitua por inteiro o método `_send_request` da classe `EsclScannerGateway` por (as reticências `...` representam o resto da classe, que não muda):

```python
class EsclScannerGateway:
    ...

    async def _send_request(self, request: httpx.Request) -> httpx.Response:
        request.headers.update(CLOSE_CONNECTION_HEADERS)
        try:
            return await self._http_client.send(request, follow_redirects=False)
        except httpx.TransportError as error:
            raise _translate_transport_error(error) from error
```

- [ ] **Passo 12: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/infrastructure/test_escl_scanner_gateway.py -v`

Expected: `18 passed`.

- [ ] **Passo 13: Escrever o teste que falha** (ciclo 4: Espera pela impressora e respostas do POST)

Regras 3 e 4: antes do `POST`, o gateway consulta o estado; se não estiver `Idle`, espera de 2 em 2 segundos até `busy_wait_seconds` e então levanta `ScannerBusyError`. O `POST` aceita só 201 com `Location`: 503 vira `ScannerBusyError`, 400 e 409 viram `ScanRejectedError`, qualquer outro status ou um 201 sem `Location` vira `ScanFailedError`, e nenhum `DELETE` é enviado quando não há trabalho. Um `Location` com host estranho nunca desvia as requisições seguintes: elas continuam indo para o host do `base_address`.

Substitua o bloco de importações de `tests/infrastructure/test_escl_scanner_gateway.py` (as linhas `import` e `from` do topo do arquivo) por:

```python
import errno
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from http import HTTPStatus

import httpx
import pytest

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import (
    LocalNetworkBlockedError,
    ScanFailedError,
    ScannerBusyError,
    ScannerUnreachableError,
    ScanRejectedError,
)
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanner_status import ScannerState
from digitalizadora.infrastructure.escl.escl_protocol import (
    build_scan_settings_xml,
    parse_scanner_capabilities,
)
from digitalizadora.infrastructure.escl.escl_scanner_gateway import (
    EsclGatewayTiming,
    EsclScannerGateway,
)
from digitalizadora.simulator.fake_escl_scanner_app import (
    SUPPORTED_COLOR_MODES,
    FakeScannerBehavior,
    build_capabilities_document,
    build_status_document,
    create_fake_escl_scanner_app,
)
from tests.fakes.recording_sleep import RecordingSleep
from tests.fakes.sample_images import build_sample_jpeg
```

Em `tests/infrastructure/test_escl_scanner_gateway.py`, logo depois de `DOCUMENT_ROUTE`, acrescente:

```python
READINESS_INTERVAL_SECONDS = 2.0
```

Acrescente ao final de `tests/infrastructure/test_escl_scanner_gateway.py`:

```python
async def test_scanner_that_is_busy_and_then_idle_is_waited_for() -> None:
    busy_then_idle = [
        Reply(HTTPStatus.OK, build_status_document("Processing")),
        Reply(HTTPStatus.OK, build_status_document("Idle")),
    ]
    harness = scripted_harness({STATUS_ROUTE: busy_then_idle})
    await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.sleep.delays == [READINESS_INTERVAL_SECONDS]


async def test_scanner_busy_past_the_waiting_limit_raises_scanner_busy() -> None:
    harness = fake_scanner_harness(FakeScannerBehavior(initial_state="Processing"))
    with pytest.raises(ScannerBusyError):
        await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.sleep.delays == [READINESS_INTERVAL_SECONDS] * 3


async def test_scanner_that_becomes_idle_just_before_the_limit_is_still_used() -> None:
    busy = Reply(HTTPStatus.OK, build_status_document("Processing"))
    idle = Reply(HTTPStatus.OK, build_status_document("Idle"))
    harness = scripted_harness({STATUS_ROUTE: [busy, busy, idle]})
    scanned_image = await harness.gateway.scan_page(SCAN_SETTINGS)
    assert (scanned_image.media_type, harness.sleep.delays) == ("image/jpeg", [READINESS_INTERVAL_SECONDS] * 2)


async def test_busy_scanner_receives_no_scan_job() -> None:
    harness = fake_scanner_harness(FakeScannerBehavior(initial_state="Processing"))
    with pytest.raises(ScannerBusyError):
        await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.transport.count(POST_ROUTE) == 0


async def test_post_answer_503_raises_scanner_busy() -> None:
    harness = fake_scanner_harness(FakeScannerBehavior(post_status_code=HTTPStatus.SERVICE_UNAVAILABLE))
    with pytest.raises(ScannerBusyError):
        await harness.gateway.scan_page(SCAN_SETTINGS)


@pytest.mark.parametrize("status_code", [HTTPStatus.BAD_REQUEST, HTTPStatus.CONFLICT])
async def test_post_answers_400_and_409_raise_scan_rejected(status_code: int) -> None:
    harness = fake_scanner_harness(FakeScannerBehavior(post_status_code=status_code))
    with pytest.raises(ScanRejectedError):
        await harness.gateway.scan_page(SCAN_SETTINGS)


async def test_post_answer_500_raises_scan_failed() -> None:
    harness = fake_scanner_harness(FakeScannerBehavior(post_status_code=HTTPStatus.INTERNAL_SERVER_ERROR))
    with pytest.raises(ScanFailedError):
        await harness.gateway.scan_page(SCAN_SETTINGS)


async def test_post_answer_201_without_location_raises_scan_failed() -> None:
    harness = scripted_harness({POST_ROUTE: [Reply(HTTPStatus.CREATED)]})
    with pytest.raises(ScanFailedError):
        await harness.gateway.scan_page(SCAN_SETTINGS)


async def test_refused_post_sends_no_delete() -> None:
    harness = fake_scanner_harness(FakeScannerBehavior(post_status_code=HTTPStatus.CONFLICT))
    with pytest.raises(ScanRejectedError):
        await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.transport.count(DELETE_ROUTE) == 0


async def test_location_with_a_foreign_host_never_redirects_the_next_requests() -> None:
    foreign_location = Reply(HTTPStatus.CREATED, headers={"Location": f"http://203.0.113.9:9999{JOB_PATH}"})
    harness = scripted_harness({POST_ROUTE: [foreign_location]})
    await harness.gateway.scan_page(SCAN_SETTINGS)
    assert {request.url.host for request in harness.transport.requests} == {SCANNER_HOST}
```

- [ ] **Passo 14: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/infrastructure/test_escl_scanner_gateway.py -v`

Expected: resumo `10 failed, 19 passed`; falham `test_scanner_that_is_busy_and_then_idle_is_waited_for`, `test_scanner_busy_past_the_waiting_limit_raises_scanner_busy`, `test_scanner_that_becomes_idle_just_before_the_limit_is_still_used` e mais 6 (erros: `AssertionError`, `KeyError`). Os demais já passam.

- [ ] **Passo 15: Implementar o mínimo**

Acrescente as constantes, o mapa de falhas do `POST` e o método `_wait_until_ready`; substitua `scan_page` e `_post_job` pelas versões finais.

Substitua o bloco de importações de `src/digitalizadora/infrastructure/escl/escl_scanner_gateway.py` (as linhas `import` e `from` do topo do arquivo) por:

```python
import asyncio
import errno
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from http import HTTPStatus
from urllib.parse import urlsplit

import httpx

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import (
    DigitalizadoraError,
    LocalNetworkBlockedError,
    ScanFailedError,
    ScannerBusyError,
    ScannerUnreachableError,
    ScanRejectedError,
)
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.domain.scanner_capabilities import ScannerCapabilities
from digitalizadora.domain.scanner_status import ScannerStatus
from digitalizadora.infrastructure.escl.escl_protocol import (
    build_scan_settings_xml,
    extract_job_path,
    parse_scanner_capabilities,
    parse_scanner_status,
)
```

Em `src/digitalizadora/infrastructure/escl/escl_scanner_gateway.py`, logo depois de `LOCAL_NETWORK_BLOCKED_ERRNO`, acrescente:

```python
READINESS_POLL_INTERVAL_SECONDS = 2.0
```

Em `src/digitalizadora/infrastructure/escl/escl_scanner_gateway.py`, logo depois de `ESCL_COLOR_MODE_BY_COLOR_MODE`, acrescente:

```python
POST_FAILURE_BY_STATUS: dict[int, type[DigitalizadoraError]] = {
    HTTPStatus.SERVICE_UNAVAILABLE: ScannerBusyError,
    HTTPStatus.BAD_REQUEST: ScanRejectedError,
    HTTPStatus.CONFLICT: ScanRejectedError,
}
```

Em `src/digitalizadora/infrastructure/escl/escl_scanner_gateway.py`, acrescente ao final da classe `EsclScannerGateway` (depois do último método; as reticências `...` representam o resto da classe):

```python
class EsclScannerGateway:
    ...

    async def _wait_until_ready(self) -> None:
        started_at = self._timing.monotonic_clock()
        while not (await self.read_status()).is_ready:
            if self._timing.monotonic_clock() - started_at >= self._timing.busy_wait_seconds:
                raise ScannerBusyError("The scanner stayed busy past the waiting limit")
            await self._timing.sleep(READINESS_POLL_INTERVAL_SECONDS)
```

Em `src/digitalizadora/infrastructure/escl/escl_scanner_gateway.py`, substitua por inteiro o método `scan_page` da classe `EsclScannerGateway` por (as reticências `...` representam o resto da classe, que não muda):

```python
class EsclScannerGateway:
    ...

    async def scan_page(self, settings: ScanSettings) -> ScannedImage:
        capabilities = await self.read_capabilities()
        _ensure_color_mode_is_supported(settings, capabilities)
        await self._wait_until_ready()
        job_path = await self._post_job(settings, capabilities)
        try:
            return await self._download_page(job_path)
        finally:
            await self._delete_job(job_path)
```

Em `src/digitalizadora/infrastructure/escl/escl_scanner_gateway.py`, substitua por inteiro o método `_post_job` da classe `EsclScannerGateway` por (as reticências `...` representam o resto da classe, que não muda):

```python
class EsclScannerGateway:
    ...

    async def _post_job(self, settings: ScanSettings, capabilities: ScannerCapabilities) -> str:
        request = self._http_client.build_request(
            "POST",
            f"{self._base_address}/{SCAN_JOBS_PATH}",
            content=build_scan_settings_xml(settings, capabilities),
            headers={"Content-Type": XML_MEDIA_TYPE},
            timeout=self._default_timeout,
        )
        response = await self._send_request(request)
        if response.status_code != HTTPStatus.CREATED:
            failure_type = POST_FAILURE_BY_STATUS.get(response.status_code, ScanFailedError)
            raise failure_type(f"POST {SCAN_JOBS_PATH} answered {response.status_code}")
        location = response.headers.get(LOCATION_HEADER)
        if not location:
            raise ScanFailedError(f"POST {SCAN_JOBS_PATH} answered 201 without a {LOCATION_HEADER} header")
        return extract_job_path(location).rstrip("/")
```

- [ ] **Passo 16: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/infrastructure/test_escl_scanner_gateway.py -v`

Expected: `29 passed`.

- [ ] **Passo 17: Escrever o teste que falha** (ciclo 5: Esperar a página: 503, 404, 500 e prazo máximo)

Regra 5: `NextDocument` responde 503 enquanto a página não está pronta (esperar `document_poll_interval_seconds` e repetir), 404 antes da primeira página é repetido um número limitado de vezes (`MAXIMUM_NOT_FOUND_RETRIES`) e depois vira `ScanFailedError`, 500 vira `ScanFailedError`, e passar de `scan_timeout_seconds` (medido pelo relógio injetado) vira `ScanTimedOutError`. Um `httpx.ReadTimeout` nessa requisição também é `ScanTimedOutError`. Em todos os casos o `DELETE` ainda é enviado. A requisição de `NextDocument` usa como tempo de leitura o próprio `scan_timeout_seconds` (conexão 5 s); as demais usam conexão 5 s e leitura 30 s.

Substitua o bloco de importações de `tests/infrastructure/test_escl_scanner_gateway.py` (as linhas `import` e `from` do topo do arquivo) por:

```python
import errno
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from http import HTTPStatus

import httpx
import pytest

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import (
    LocalNetworkBlockedError,
    ScanFailedError,
    ScannerBusyError,
    ScannerUnreachableError,
    ScanRejectedError,
    ScanTimedOutError,
)
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanner_status import ScannerState
from digitalizadora.infrastructure.escl.escl_protocol import (
    build_scan_settings_xml,
    parse_scanner_capabilities,
)
from digitalizadora.infrastructure.escl.escl_scanner_gateway import (
    EsclGatewayTiming,
    EsclScannerGateway,
)
from digitalizadora.simulator.fake_escl_scanner_app import (
    SUPPORTED_COLOR_MODES,
    FakeScannerBehavior,
    build_capabilities_document,
    build_status_document,
    create_fake_escl_scanner_app,
)
from tests.fakes.recording_sleep import RecordingSleep
from tests.fakes.sample_images import build_sample_jpeg
```

Em `tests/infrastructure/test_escl_scanner_gateway.py`, logo depois de `READINESS_INTERVAL_SECONDS`, acrescente:

```python
POLL_INTERVAL_SECONDS = 1.5
EXPECTED_CONNECT_TIMEOUT_SECONDS = 5.0
EXPECTED_READ_TIMEOUT_SECONDS = 30.0
```

Em `tests/infrastructure/test_escl_scanner_gateway.py`, logo depois de `immediate_document_harness`, acrescente:

```python
def failing_document_harness(status_code: int) -> GatewayHarness:
    return fake_scanner_harness(FakeScannerBehavior(busy_polls_before_document=0, document_status_code=status_code))
```

Acrescente ao final de `tests/infrastructure/test_escl_scanner_gateway.py`:

```python
async def test_next_document_busy_answers_are_polled_every_interval() -> None:
    harness = fake_scanner_harness(FakeScannerBehavior(busy_polls_before_document=3))
    await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.sleep.delays == [POLL_INTERVAL_SECONDS] * 3


async def test_next_document_404_before_any_page_is_retried_a_bounded_number_of_times() -> None:
    harness = failing_document_harness(HTTPStatus.NOT_FOUND)
    with pytest.raises(ScanFailedError):
        await harness.gateway.scan_page(SCAN_SETTINGS)
    assert (harness.transport.count(DOCUMENT_ROUTE), harness.sleep.delays) == (4, [POLL_INTERVAL_SECONDS] * 3)


async def test_next_document_404_that_clears_on_the_last_allowed_retry_still_delivers() -> None:
    not_found = Reply(HTTPStatus.NOT_FOUND)
    page = Reply(HTTPStatus.OK, build_sample_jpeg(), {"Content-Type": "image/jpeg"})
    harness = scripted_harness({DOCUMENT_ROUTE: [not_found, not_found, not_found, page]})
    scanned_image = await harness.gateway.scan_page(SCAN_SETTINGS)
    assert (scanned_image.media_type, harness.sleep.delays) == ("image/jpeg", [POLL_INTERVAL_SECONDS] * 3)


async def test_next_document_404_still_sends_the_delete() -> None:
    harness = failing_document_harness(HTTPStatus.NOT_FOUND)
    with pytest.raises(ScanFailedError):
        await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.transport.count(DELETE_ROUTE) == 1


async def test_next_document_500_raises_scan_failed() -> None:
    harness = failing_document_harness(HTTPStatus.INTERNAL_SERVER_ERROR)
    with pytest.raises(ScanFailedError):
        await harness.gateway.scan_page(SCAN_SETTINGS)


async def test_next_document_500_still_sends_the_delete() -> None:
    harness = failing_document_harness(HTTPStatus.INTERNAL_SERVER_ERROR)
    with pytest.raises(ScanFailedError):
        await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.transport.count(DELETE_ROUTE) == 1


async def test_exceeding_the_scan_timeout_raises_scan_timed_out() -> None:
    harness = scripted_harness({DOCUMENT_ROUTE: [Reply(HTTPStatus.SERVICE_UNAVAILABLE)]})
    with pytest.raises(ScanTimedOutError):
        await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.sleep.delays == [POLL_INTERVAL_SECONDS] * 4


async def test_exceeding_the_scan_timeout_still_sends_the_delete() -> None:
    harness = scripted_harness({DOCUMENT_ROUTE: [Reply(HTTPStatus.SERVICE_UNAVAILABLE)]})
    with pytest.raises(ScanTimedOutError):
        await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.transport.count(DELETE_ROUTE) == 1


async def test_read_timeout_while_waiting_for_the_page_raises_scan_timed_out() -> None:
    harness = scripted_harness({DOCUMENT_ROUTE: [httpx.ReadTimeout("scanner went silent")]})
    with pytest.raises(ScanTimedOutError):
        await harness.gateway.scan_page(SCAN_SETTINGS)


async def test_read_timeout_while_waiting_for_the_page_still_sends_the_delete() -> None:
    harness = scripted_harness({DOCUMENT_ROUTE: [httpx.ReadTimeout("scanner went silent")]})
    with pytest.raises(ScanTimedOutError):
        await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.transport.count(DELETE_ROUTE) == 1


async def test_next_document_request_waits_as_long_as_the_scan_timeout() -> None:
    harness = scripted_harness()
    await harness.gateway.scan_page(SCAN_SETTINGS)
    timeout = harness.transport.find(DOCUMENT_ROUTE).extensions["timeout"]
    assert (timeout["connect"], timeout["read"]) == (EXPECTED_CONNECT_TIMEOUT_SECONDS, TEST_SCAN_TIMEOUT_SECONDS)


async def test_other_requests_use_the_default_timeouts() -> None:
    harness = scripted_harness()
    await harness.gateway.read_status()
    timeout = harness.transport.find(STATUS_ROUTE).extensions["timeout"]
    assert (timeout["connect"], timeout["read"]) == (EXPECTED_CONNECT_TIMEOUT_SECONDS, EXPECTED_READ_TIMEOUT_SECONDS)
```

- [ ] **Passo 18: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/infrastructure/test_escl_scanner_gateway.py -v`

Expected: resumo `11 failed, 30 passed`; falham `test_next_document_busy_answers_are_polled_every_interval`, `test_next_document_404_before_any_page_is_retried_a_bounded_number_of_times`, `test_next_document_404_that_clears_on_the_last_allowed_retry_still_delivers` e mais 8 (erros: `AssertionError`, `ScannerUnreachableError`). Os demais já passam.

- [ ] **Passo 19: Implementar o mínimo**

Acrescente a constante de tentativas, substitua `_download_page` pelo laço de espera e acrescente `_get_next_document`.

Substitua o bloco de importações de `src/digitalizadora/infrastructure/escl/escl_scanner_gateway.py` (as linhas `import` e `from` do topo do arquivo) por:

```python
import asyncio
import errno
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from http import HTTPStatus
from urllib.parse import urlsplit

import httpx

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import (
    DigitalizadoraError,
    LocalNetworkBlockedError,
    ScanFailedError,
    ScannerBusyError,
    ScannerUnreachableError,
    ScanRejectedError,
    ScanTimedOutError,
)
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.domain.scanner_capabilities import ScannerCapabilities
from digitalizadora.domain.scanner_status import ScannerStatus
from digitalizadora.infrastructure.escl.escl_protocol import (
    build_scan_settings_xml,
    extract_job_path,
    parse_scanner_capabilities,
    parse_scanner_status,
)
```

Em `src/digitalizadora/infrastructure/escl/escl_scanner_gateway.py`, logo depois de `READINESS_POLL_INTERVAL_SECONDS`, acrescente:

```python
MAXIMUM_NOT_FOUND_RETRIES = 3
```

Em `src/digitalizadora/infrastructure/escl/escl_scanner_gateway.py`, substitua por inteiro o método `_download_page` da classe `EsclScannerGateway` por (as reticências `...` representam o resto da classe, que não muda):

```python
class EsclScannerGateway:
    ...

    async def _download_page(self, job_path: str) -> ScannedImage:
        started_at = self._timing.monotonic_clock()
        not_found_count = 0
        while True:
            response = await self._get_next_document(job_path)
            if response.status_code == HTTPStatus.OK:
                return _build_scanned_image(response)
            if response.status_code == HTTPStatus.NOT_FOUND:
                not_found_count += 1
                if not_found_count > MAXIMUM_NOT_FOUND_RETRIES:
                    raise ScanFailedError("The scanner never produced a page for the job")
            elif response.status_code != HTTPStatus.SERVICE_UNAVAILABLE:
                raise ScanFailedError(f"{NEXT_DOCUMENT_PATH} answered {response.status_code}")
            if self._timing.monotonic_clock() - started_at >= self._timing.scan_timeout_seconds:
                raise ScanTimedOutError("The scanner took too long to deliver the page")
            await self._timing.sleep(self._timing.document_poll_interval_seconds)
```

Em `src/digitalizadora/infrastructure/escl/escl_scanner_gateway.py`, acrescente ao final da classe `EsclScannerGateway` (depois do último método; as reticências `...` representam o resto da classe):

```python
class EsclScannerGateway:
    ...

    async def _get_next_document(self, job_path: str) -> httpx.Response:
        request = self._http_client.build_request(
            "GET",
            f"{self._origin}{job_path}/{NEXT_DOCUMENT_PATH}",
            timeout=httpx.Timeout(self._timing.scan_timeout_seconds, connect=CONNECT_TIMEOUT_SECONDS),
        )
        try:
            return await self._send_request(request)
        except ScannerUnreachableError as error:
            if isinstance(error.__cause__, httpx.ReadTimeout):
                raise ScanTimedOutError("The scanner stopped answering while the page was being delivered") from error
            raise
```

- [ ] **Passo 20: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/infrastructure/test_escl_scanner_gateway.py -v`

Expected: `41 passed`.

- [ ] **Passo 21: Escrever o teste que falha** (ciclo 6: Limpeza do trabalho e validação da imagem)

Regras 6 e 9: a falha do `DELETE` (erro de rede ou status de erro) é registrada e nunca esconde o erro original nem estraga um sucesso; a resposta só vale se o tipo de mídia for `image/jpeg` (parâmetros como `; charset=binary` são ignorados) e os bytes começarem com `FF D8`. Um PDF, um corpo vazio, um corpo sem tipo ou um PDF rotulado como JPEG viram `ScanFailedError`, sempre com o `DELETE` enviado. (Um JPEG corrompido que ainda começa com `FF D8` é tratado pelos serviços de imagem da Task 6.)

Acrescente ao final de `tests/infrastructure/test_escl_scanner_gateway.py`:

```python
async def test_delete_that_fails_after_a_success_is_ignored() -> None:
    harness = scripted_harness({DELETE_ROUTE: [httpx.ConnectError("scanner went away")]})
    scanned_image = await harness.gateway.scan_page(SCAN_SETTINGS)
    assert scanned_image.media_type == "image/jpeg"


async def test_delete_that_fails_does_not_hide_the_original_error() -> None:
    failing_scan = {
        DOCUMENT_ROUTE: [Reply(HTTPStatus.INTERNAL_SERVER_ERROR)],
        DELETE_ROUTE: [httpx.ConnectError("scanner went away")],
    }
    harness = scripted_harness(failing_scan)
    with pytest.raises(ScanFailedError):
        await harness.gateway.scan_page(SCAN_SETTINGS)


async def test_delete_answered_with_an_error_status_is_ignored() -> None:
    harness = scripted_harness({DELETE_ROUTE: [Reply(HTTPStatus.NOT_FOUND)]})
    scanned_image = await harness.gateway.scan_page(SCAN_SETTINGS)
    assert scanned_image.media_type == "image/jpeg"


async def test_body_with_pdf_magic_bytes_raises_scan_failed() -> None:
    pdf_page = Reply(HTTPStatus.OK, b"%PDF-1.4 fake", {"Content-Type": "application/pdf"})
    harness = scripted_harness({DOCUMENT_ROUTE: [pdf_page]})
    with pytest.raises(ScanFailedError):
        await harness.gateway.scan_page(SCAN_SETTINGS)


async def test_pdf_body_labelled_as_jpeg_raises_scan_failed() -> None:
    mislabelled_page = Reply(HTTPStatus.OK, b"%PDF-1.4 fake", {"Content-Type": "image/jpeg"})
    harness = scripted_harness({DOCUMENT_ROUTE: [mislabelled_page]})
    with pytest.raises(ScanFailedError):
        await harness.gateway.scan_page(SCAN_SETTINGS)


async def test_empty_body_raises_scan_failed() -> None:
    empty_page = Reply(HTTPStatus.OK, b"", {"Content-Type": "image/jpeg"})
    harness = scripted_harness({DOCUMENT_ROUTE: [empty_page]})
    with pytest.raises(ScanFailedError):
        await harness.gateway.scan_page(SCAN_SETTINGS)


async def test_jpeg_body_without_a_media_type_raises_scan_failed() -> None:
    untyped_page = Reply(HTTPStatus.OK, build_sample_jpeg())
    harness = scripted_harness({DOCUMENT_ROUTE: [untyped_page]})
    with pytest.raises(ScanFailedError):
        await harness.gateway.scan_page(SCAN_SETTINGS)


async def test_media_type_parameters_are_ignored() -> None:
    parameterised_page = Reply(HTTPStatus.OK, build_sample_jpeg(), {"Content-Type": "image/jpeg; charset=binary"})
    harness = scripted_harness({DOCUMENT_ROUTE: [parameterised_page]})
    scanned_image = await harness.gateway.scan_page(SCAN_SETTINGS)
    assert scanned_image.media_type == "image/jpeg"


async def test_invalid_page_still_sends_the_delete() -> None:
    pdf_page = Reply(HTTPStatus.OK, b"%PDF-1.4 fake", {"Content-Type": "application/pdf"})
    harness = scripted_harness({DOCUMENT_ROUTE: [pdf_page]})
    with pytest.raises(ScanFailedError):
        await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.transport.count(DELETE_ROUTE) == 1
```

- [ ] **Passo 22: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/infrastructure/test_escl_scanner_gateway.py -v`

Expected: resumo `7 failed, 43 passed`; falham `test_delete_that_fails_after_a_success_is_ignored`, `test_delete_that_fails_does_not_hide_the_original_error`, `test_body_with_pdf_magic_bytes_raises_scan_failed` e mais 4 (erros: `ScannerUnreachableError`, `AssertionError`). Os demais já passam.

- [ ] **Passo 23: Implementar o mínimo**

Acrescente a constante do marcador JPEG e o `logger`, e substitua `_build_scanned_image` e `_delete_job` pelas versões finais.

Substitua o bloco de importações de `src/digitalizadora/infrastructure/escl/escl_scanner_gateway.py` (as linhas `import` e `from` do topo do arquivo) por:

```python
import asyncio
import errno
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from http import HTTPStatus
from urllib.parse import urlsplit

import httpx

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import (
    DigitalizadoraError,
    LocalNetworkBlockedError,
    ScanFailedError,
    ScannerBusyError,
    ScannerUnreachableError,
    ScanRejectedError,
    ScanTimedOutError,
)
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.domain.scanner_capabilities import ScannerCapabilities
from digitalizadora.domain.scanner_status import ScannerStatus
from digitalizadora.infrastructure.escl.escl_protocol import (
    build_scan_settings_xml,
    extract_job_path,
    parse_scanner_capabilities,
    parse_scanner_status,
)
```

Em `src/digitalizadora/infrastructure/escl/escl_scanner_gateway.py`, logo depois do bloco de importações, acrescente:

```python
logger = logging.getLogger(__name__)
```

Em `src/digitalizadora/infrastructure/escl/escl_scanner_gateway.py`, logo depois de `JPEG_MEDIA_TYPE`, acrescente:

```python
JPEG_START_OF_IMAGE = b"\xff\xd8"
```

Em `src/digitalizadora/infrastructure/escl/escl_scanner_gateway.py`, substitua por inteiro `_build_scanned_image` por:

```python
def _build_scanned_image(response: httpx.Response) -> ScannedImage:
    media_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
    if media_type != JPEG_MEDIA_TYPE:
        raise ScanFailedError(f"The scanner returned {media_type or 'an untyped body'} instead of {JPEG_MEDIA_TYPE}")
    if not response.content.startswith(JPEG_START_OF_IMAGE):
        raise ScanFailedError("The scanner body does not start with the JPEG marker")
    return ScannedImage(content=response.content, media_type=JPEG_MEDIA_TYPE)
```

Em `src/digitalizadora/infrastructure/escl/escl_scanner_gateway.py`, substitua por inteiro o método `_delete_job` da classe `EsclScannerGateway` por (as reticências `...` representam o resto da classe, que não muda):

```python
class EsclScannerGateway:
    ...

    async def _delete_job(self, job_path: str) -> None:
        request = self._http_client.build_request(
            "DELETE",
            f"{self._origin}{job_path}",
            timeout=httpx.Timeout(self._timing.cleanup_timeout_seconds),
        )
        try:
            await self._send_request(request)
        except DigitalizadoraError as error:
            logger.warning("Could not delete the scan job %s: %s", job_path, error)
```

- [ ] **Passo 24: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/infrastructure/test_escl_scanner_gateway.py -v`

Expected: `50 passed`.

- [ ] **Passo 25: Rodar a verificação estática e a lentidão dos testes**

Run: `make lint && .venv/bin/pytest tests/infrastructure/test_escl_scanner_gateway.py --durations=3`

Expected: o lint sem erros do ruff e `50 passed`, com os três testes mais lentos abaixo de 100 ms.

- [ ] **Passo 26: Commit**

```bash
git add src/digitalizadora/infrastructure/escl/escl_scanner_gateway.py tests/fakes/recording_sleep.py tests/infrastructure/test_escl_scanner_gateway.py
git commit -m "feat(escl): add the eSCL scanner gateway with timing and cleanup rules"
```

### Task 6: Pipeline de codificação (resolução do JPEG, PDF, miniatura e ScanEncoder)

**Objetivo:** Transformar o JPEG que veio do scanner no arquivo final (JPG com densidade correta ou PDF com página em tamanho real) mais uma miniatura de 480 px, sem nunca recomprimir a imagem principal.

**Files:**
- Create: `src/digitalizadora/services/jpeg_resolution_service.py`
- Create: `src/digitalizadora/services/pdf_assembly_service.py`
- Create: `src/digitalizadora/services/thumbnail_service.py`
- Create: `src/digitalizadora/services/scan_encoder.py`
- Test: `tests/services/test_jpeg_resolution_service.py`
- Test: `tests/services/test_pdf_assembly_service.py`
- Test: `tests/services/test_thumbnail_service.py`
- Test: `tests/services/test_scan_encoder.py`

**Interfaces:**
- Consumes (Task 2): `digitalizadora.domain.errors.ScanFailedError`, `digitalizadora.domain.errors.InvalidSettingsError`, `digitalizadora.domain.scanned_image.ScannedImage(content: bytes, media_type: str)`, `digitalizadora.domain.scan_job.ScanJob(request, started_at)`, `digitalizadora.domain.scan_request.ScanRequest(settings, output_format)`, `digitalizadora.domain.scan_settings.ScanSettings(dots_per_inch, color_mode)`, `digitalizadora.domain.color_mode.ColorMode`, `digitalizadora.domain.output_format.OutputFormat`, `digitalizadora.domain.encoded_scan.EncodedScan(content, output_format, created_at, thumbnail_jpeg)`, `tests.fakes.sample_images.build_sample_jpeg(width_pixels=64, height_pixels=48, dots_per_inch=None) -> bytes` (JPEG do Pillow; sem `dots_per_inch` o Pillow grava JFIF com densidade 1:1 e unidade 0), `tests.fakes.fixed_clock.FixedClock(moment).now()`.
- Produces:
  - `JpegResolutionService.with_resolution(self, jpeg_content: bytes, dots_per_inch: int) -> bytes`
  - `PdfDocumentSpecification(dots_per_inch: int, title: str, created_at: datetime)` (dataclass congelada) e `PdfAssemblyService.build_pdf(self, jpeg_pages: Sequence[bytes], specification: PdfDocumentSpecification) -> bytes`
  - `ThumbnailService.build_thumbnail(self, jpeg_content: bytes, maximum_edge_pixels: int) -> bytes`
  - `ScanEncoder(jpeg_resolution_service, pdf_assembly_service, thumbnail_service)` com `encode(self, scanned_image: ScannedImage, job: ScanJob) -> EncodedScan`, e a constante `THUMBNAIL_MAXIMUM_EDGE_PIXELS = 480` em `digitalizadora.services.scan_encoder`.

Notas de verificação (feitas antes de escrever o plano): no código-fonte do `img2pdf` 0.6.3 (sdist do PyPI), `img2pdf.convert(*images, outputstream=None, **kwargs)` devolve `bytes` quando `outputstream` não é passado; `Rotation` e `Engine` são `enum.Enum` (`img2pdf.Rotation.ifvalid`, `img2pdf.Engine.pikepdf`); `creationdate` e `moddate` recebem `datetime` (com fuso, são convertidos para UTC); o JPEG entra no PDF como bytes originais com `/Filter /DCTDecode`; entrada ilegível levanta `img2pdf.ImageOpenError`; lista vazia levanta `ValueError`. O `img2pdf` só lê o cabeçalho do JPEG (não decodifica os pixels), por isso uma imagem cortada no meio entra no PDF sem erro; quem detecta JPEG corrompido é a miniatura, que decodifica tudo e roda antes de montar o PDF. Passamos `io.BytesIO(página)` em vez de `bytes` porque o `img2pdf` tenta abrir `bytes` como nome de arquivo antes de tratá-los como conteúdo.

#### Ciclo 1: reescrever a densidade de um JFIF existente

- [ ] **Passo 1: Escrever o teste que falha**

Criar `tests/services/test_jpeg_resolution_service.py`:

```python
import io

import pytest
from PIL import Image

from digitalizadora.domain.errors import InvalidSettingsError, ScanFailedError
from digitalizadora.services.jpeg_resolution_service import JpegResolutionService
from tests.fakes.sample_images import build_sample_jpeg

START_OF_IMAGE = b"\xff\xd8"
START_OF_SCAN_MARKER = b"\xff\xda"
APPLICATION_0_MARKER = b"\xff\xe0"
APPLICATION_1_MARKER = b"\xff\xe1"
JFIF_SEGMENT_SIZE_IN_BYTES = 18
EXIF_DESCRIPTION_TAG = 0x010E
EXIF_DESCRIPTION = "Digitalizadora"


def read_dots_per_inch(jpeg_content: bytes) -> tuple[int, int] | None:
    with Image.open(io.BytesIO(jpeg_content)) as image:
        return image.info.get("dpi")


def read_exif_description(jpeg_content: bytes) -> str | None:
    with Image.open(io.BytesIO(jpeg_content)) as image:
        return image.getexif().get(EXIF_DESCRIPTION_TAG)


def build_jpeg_with_exif() -> bytes:
    image = Image.new("RGB", (64, 48), "white")
    exif = image.getexif()
    exif[EXIF_DESCRIPTION_TAG] = EXIF_DESCRIPTION
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif.tobytes())
    return buffer.getvalue()


def strip_jfif_segment(jpeg_content: bytes) -> bytes:
    """Remove the JFIF segment that Pillow writes right after the start of image."""
    assert jpeg_content[2:4] == APPLICATION_0_MARKER
    segment_length = int.from_bytes(jpeg_content[4:6], "big")
    return jpeg_content[:2] + jpeg_content[2 + 2 + segment_length:]


def test_rewrites_the_density_of_an_existing_jfif_segment():
    rewritten = JpegResolutionService().with_resolution(build_sample_jpeg(), 300)

    assert read_dots_per_inch(rewritten) == (300, 300)


def test_rewrites_a_density_that_was_already_set():
    original = build_sample_jpeg(dots_per_inch=72)

    rewritten = JpegResolutionService().with_resolution(original, 600)

    assert read_dots_per_inch(rewritten) == (600, 600)


def test_rewriting_keeps_the_length_of_the_file():
    original = build_sample_jpeg()

    rewritten = JpegResolutionService().with_resolution(original, 300)

    assert len(rewritten) == len(original)


def test_rewriting_keeps_the_scan_data_byte_for_byte():
    original = build_sample_jpeg()

    rewritten = JpegResolutionService().with_resolution(original, 300)

    original_scan = original[original.index(START_OF_SCAN_MARKER):]
    assert rewritten[rewritten.index(START_OF_SCAN_MARKER):] == original_scan


def test_rewriting_keeps_the_exif_segment_that_follows_the_jfif_segment():
    original = build_jpeg_with_exif()

    rewritten = JpegResolutionService().with_resolution(original, 300)

    assert read_exif_description(rewritten) == EXIF_DESCRIPTION
```

- [ ] **Passo 2: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/services/test_jpeg_resolution_service.py -v`
Expected: erro de coleta `ModuleNotFoundError: No module named 'digitalizadora.services.jpeg_resolution_service'` (0 testes executados).

- [ ] **Passo 3: Implementar o mínimo**

Criar `src/digitalizadora/services/jpeg_resolution_service.py`:

```python
START_OF_IMAGE = b"\xff\xd8"
START_OF_SCAN_MARKER_BYTE = 0xDA
APPLICATION_0_MARKER_BYTE = 0xE0
JFIF_IDENTIFIER = b"JFIF\x00"
BYTE_ORDER = "big"

MARKER_SIZE_IN_BYTES = 2
LENGTH_FIELD_SIZE_IN_BYTES = 2
SEGMENT_HEADER_SIZE_IN_BYTES = MARKER_SIZE_IN_BYTES + LENGTH_FIELD_SIZE_IN_BYTES
DENSITY_FIELD_SIZE_IN_BYTES = 2

JFIF_UNITS_OFFSET = 7
JFIF_X_DENSITY_OFFSET = 8
JFIF_Y_DENSITY_OFFSET = 10
JFIF_UNITS_DOTS_PER_INCH = 1


def find_jfif_payload_start(jpeg_content: bytes) -> int | None:
    """Return where the JFIF payload starts, or None when no JFIF segment precedes the scan data."""
    position = len(START_OF_IMAGE)
    while jpeg_content[position + 1] != START_OF_SCAN_MARKER_BYTE:
        marker = jpeg_content[position + 1]
        payload_start = position + SEGMENT_HEADER_SIZE_IN_BYTES
        if marker == APPLICATION_0_MARKER_BYTE and jpeg_content.startswith(JFIF_IDENTIFIER, payload_start):
            return payload_start
        segment_length = int.from_bytes(jpeg_content[position + MARKER_SIZE_IN_BYTES:payload_start], BYTE_ORDER)
        position += MARKER_SIZE_IN_BYTES + segment_length
    return None


class JpegResolutionService:
    def with_resolution(self, jpeg_content: bytes, dots_per_inch: int) -> bytes:
        density_field = dots_per_inch.to_bytes(DENSITY_FIELD_SIZE_IN_BYTES, BYTE_ORDER)
        payload_start = find_jfif_payload_start(jpeg_content)
        rewritten = bytearray(jpeg_content)
        rewritten[payload_start + JFIF_UNITS_OFFSET] = JFIF_UNITS_DOTS_PER_INCH
        x_start = payload_start + JFIF_X_DENSITY_OFFSET
        y_start = payload_start + JFIF_Y_DENSITY_OFFSET
        rewritten[x_start:x_start + DENSITY_FIELD_SIZE_IN_BYTES] = density_field
        rewritten[y_start:y_start + DENSITY_FIELD_SIZE_IN_BYTES] = density_field
        return bytes(rewritten)
```

- [ ] **Passo 4: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/services/test_jpeg_resolution_service.py -v`
Expected: `5 passed`

#### Ciclo 2: inserir o JFIF que falta, rejeitar JPEG malformado e validar a resolução

- [ ] **Passo 5: Escrever os testes que falham**

Acrescentar ao final de `tests/services/test_jpeg_resolution_service.py`:

```python
def test_inserts_a_jfif_segment_when_the_file_has_none():
    original = strip_jfif_segment(build_sample_jpeg())

    inserted = JpegResolutionService().with_resolution(original, 300)

    assert read_dots_per_inch(inserted) == (300, 300)


def test_insertion_adds_exactly_one_jfif_segment():
    original = strip_jfif_segment(build_sample_jpeg())

    inserted = JpegResolutionService().with_resolution(original, 300)

    assert len(inserted) == len(original) + JFIF_SEGMENT_SIZE_IN_BYTES


def test_insertion_keeps_the_scan_data_byte_for_byte():
    original = strip_jfif_segment(build_sample_jpeg())

    inserted = JpegResolutionService().with_resolution(original, 300)

    original_scan = original[original.index(START_OF_SCAN_MARKER):]
    assert inserted[inserted.index(START_OF_SCAN_MARKER):] == original_scan


def test_insertion_keeps_an_exif_segment_that_comes_first():
    original = strip_jfif_segment(build_jpeg_with_exif())
    assert original[2:4] == APPLICATION_1_MARKER

    inserted = JpegResolutionService().with_resolution(original, 300)

    assert inserted[:2] == START_OF_IMAGE
    assert inserted[2 + JFIF_SEGMENT_SIZE_IN_BYTES:] == original[2:]
    assert read_exif_description(inserted) == EXIF_DESCRIPTION


MALFORMED_JPEG_CONTENTS = [
    b"",
    b"GIF89a this is not a JPEG",
    START_OF_IMAGE,
    START_OF_IMAGE + APPLICATION_1_MARKER + b"\x00\x04\x00\x00",
    START_OF_IMAGE + b"garbage right after the start of image",
    START_OF_IMAGE + APPLICATION_0_MARKER + b"\x00\x00" + b"x" * 20,
    START_OF_IMAGE + APPLICATION_0_MARKER + b"\x00\x08JFIF\x00\x01" + START_OF_SCAN_MARKER + b"\x00\x02",
    build_sample_jpeg()[:10],
]


@pytest.mark.parametrize("malformed_content", MALFORMED_JPEG_CONTENTS)
def test_rejects_content_that_is_not_a_well_formed_jpeg_header(malformed_content):
    with pytest.raises(ScanFailedError):
        JpegResolutionService().with_resolution(malformed_content, 300)


@pytest.mark.parametrize("invalid_dots_per_inch", [-1, 0, 65536])
def test_rejects_a_resolution_outside_the_jfif_range(invalid_dots_per_inch):
    with pytest.raises(InvalidSettingsError):
        JpegResolutionService().with_resolution(build_sample_jpeg(), invalid_dots_per_inch)


@pytest.mark.parametrize("limit_dots_per_inch", [1, 65535])
def test_accepts_the_limits_of_the_jfif_range(limit_dots_per_inch):
    result = JpegResolutionService().with_resolution(build_sample_jpeg(), limit_dots_per_inch)

    assert read_dots_per_inch(result) == (limit_dots_per_inch, limit_dots_per_inch)
```

- [ ] **Passo 6: Rodar os testes e ver falhar**

Run: `.venv/bin/pytest tests/services/test_jpeg_resolution_service.py -v`
Expected: `7 passed, 15 failed`. Passam os 5 testes do ciclo 1 e os 2 de limites (1 e 65535). Falham: os 4 de inserção com `TypeError: unsupported operand type(s) for +: 'NoneType' and 'int'`; os 8 de JPEG malformado com `IndexError: index out of range` ou `Failed: DID NOT RAISE <class 'digitalizadora.domain.errors.ScanFailedError'>`; os 3 de resolução inválida com `OverflowError` (`-1`, `65536`) ou `Failed: DID NOT RAISE <class 'digitalizadora.domain.errors.InvalidSettingsError'>` (`0`).

- [ ] **Passo 7: Implementar**

Substituir `src/digitalizadora/services/jpeg_resolution_service.py` (arquivo inteiro):

```python
from digitalizadora.domain.errors import InvalidSettingsError, ScanFailedError

START_OF_IMAGE = b"\xff\xd8"
MARKER_PREFIX_BYTE = 0xFF
START_OF_SCAN_MARKER_BYTE = 0xDA
APPLICATION_0_MARKER_BYTE = 0xE0
JFIF_IDENTIFIER = b"JFIF\x00"
BYTE_ORDER = "big"

MARKER_SIZE_IN_BYTES = 2
LENGTH_FIELD_SIZE_IN_BYTES = 2
SEGMENT_HEADER_SIZE_IN_BYTES = MARKER_SIZE_IN_BYTES + LENGTH_FIELD_SIZE_IN_BYTES
DENSITY_FIELD_SIZE_IN_BYTES = 2

JFIF_UNITS_OFFSET = 7
JFIF_X_DENSITY_OFFSET = 8
JFIF_Y_DENSITY_OFFSET = 10
JFIF_PAYLOAD_SIZE_NEEDED_FOR_DENSITY = JFIF_Y_DENSITY_OFFSET + DENSITY_FIELD_SIZE_IN_BYTES
JFIF_UNITS_DOTS_PER_INCH = 1
JFIF_VERSION = bytes([1, 1])
JFIF_NO_THUMBNAIL = b"\x00\x00"

MINIMUM_DOTS_PER_INCH = 1
MAXIMUM_DOTS_PER_INCH = 65535


def find_jfif_payload_start(jpeg_content: bytes) -> int | None:
    """Return where the JFIF payload starts, or None when no JFIF segment precedes the scan data."""
    position = len(START_OF_IMAGE)
    while True:
        header_end = position + SEGMENT_HEADER_SIZE_IN_BYTES
        if header_end > len(jpeg_content) or jpeg_content[position] != MARKER_PREFIX_BYTE:
            raise ScanFailedError("The JPEG marker segments are truncated or malformed")
        marker = jpeg_content[position + 1]
        if marker == START_OF_SCAN_MARKER_BYTE:
            return None
        segment_length = int.from_bytes(jpeg_content[position + MARKER_SIZE_IN_BYTES:header_end], BYTE_ORDER)
        segment_end = position + MARKER_SIZE_IN_BYTES + segment_length
        if segment_length < LENGTH_FIELD_SIZE_IN_BYTES or segment_end > len(jpeg_content):
            raise ScanFailedError("A JPEG segment declares an impossible length")
        is_jfif = marker == APPLICATION_0_MARKER_BYTE and jpeg_content.startswith(JFIF_IDENTIFIER, header_end)
        if is_jfif:
            if segment_end - header_end < JFIF_PAYLOAD_SIZE_NEEDED_FOR_DENSITY:
                raise ScanFailedError("The JFIF segment is too short to hold a density")
            return header_end
        position = segment_end


def build_jfif_segment(density_field: bytes) -> bytes:
    payload = (
        JFIF_IDENTIFIER
        + JFIF_VERSION
        + bytes([JFIF_UNITS_DOTS_PER_INCH])
        + density_field
        + density_field
        + JFIF_NO_THUMBNAIL
    )
    length_field = (len(payload) + LENGTH_FIELD_SIZE_IN_BYTES).to_bytes(LENGTH_FIELD_SIZE_IN_BYTES, BYTE_ORDER)
    return bytes([MARKER_PREFIX_BYTE, APPLICATION_0_MARKER_BYTE]) + length_field + payload


class JpegResolutionService:
    def with_resolution(self, jpeg_content: bytes, dots_per_inch: int) -> bytes:
        if not MINIMUM_DOTS_PER_INCH <= dots_per_inch <= MAXIMUM_DOTS_PER_INCH:
            raise InvalidSettingsError(f"Resolution must be between 1 and 65535 dots per inch, got {dots_per_inch}")
        if not jpeg_content.startswith(START_OF_IMAGE):
            raise ScanFailedError("The scanned content is not a JPEG image")
        density_field = dots_per_inch.to_bytes(DENSITY_FIELD_SIZE_IN_BYTES, BYTE_ORDER)
        payload_start = find_jfif_payload_start(jpeg_content)
        if payload_start is None:
            return START_OF_IMAGE + build_jfif_segment(density_field) + jpeg_content[len(START_OF_IMAGE):]
        rewritten = bytearray(jpeg_content)
        rewritten[payload_start + JFIF_UNITS_OFFSET] = JFIF_UNITS_DOTS_PER_INCH
        x_start = payload_start + JFIF_X_DENSITY_OFFSET
        y_start = payload_start + JFIF_Y_DENSITY_OFFSET
        rewritten[x_start:x_start + DENSITY_FIELD_SIZE_IN_BYTES] = density_field
        rewritten[y_start:y_start + DENSITY_FIELD_SIZE_IN_BYTES] = density_field
        return bytes(rewritten)
```

- [ ] **Passo 8: Rodar os testes e ver passar**

Run: `.venv/bin/pytest tests/services/test_jpeg_resolution_service.py -v`
Expected: `22 passed` (5 do ciclo 1, 4 de inserção, 8 de JPEG malformado, 3 de resolução inválida, 2 de limites).

#### Ciclo 3: PdfAssemblyService

- [ ] **Passo 9: Escrever o teste que falha**

Criar `tests/services/test_pdf_assembly_service.py`:

```python
import io
from datetime import datetime, timedelta, timezone

import pikepdf
import pytest
from PIL import Image

from digitalizadora.domain.errors import ScanFailedError
from digitalizadora.services.pdf_assembly_service import PdfAssemblyService, PdfDocumentSpecification
from tests.fakes.sample_images import build_sample_jpeg

A4_WIDTH_PIXELS_AT_300_DOTS_PER_INCH = 2550
A4_HEIGHT_PIXELS_AT_300_DOTS_PER_INCH = 3507
A4_WIDTH_IN_POINTS = 612.0
A4_HEIGHT_IN_POINTS = 841.68
POINT_TOLERANCE = 0.01
CREATED_AT = datetime(2026, 10, 13, 15, 30, 12, tzinfo=timezone(timedelta(hours=-3)))
TITLE = "Digitalização 2026-10-13 15:30:12"
SPECIFICATION = PdfDocumentSpecification(dots_per_inch=300, title=TITLE, created_at=CREATED_AT)


@pytest.fixture(scope="module")
def a4_jpeg_at_300_dots_per_inch() -> bytes:
    image = Image.new("RGB", (A4_WIDTH_PIXELS_AT_300_DOTS_PER_INCH, A4_HEIGHT_PIXELS_AT_300_DOTS_PER_INCH), "gray")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def open_pdf(pdf_content: bytes) -> pikepdf.Pdf:
    return pikepdf.open(io.BytesIO(pdf_content))


def test_a4_page_has_the_size_of_the_glass_at_the_fixed_resolution(a4_jpeg_at_300_dots_per_inch):
    pdf_content = PdfAssemblyService().build_pdf([a4_jpeg_at_300_dots_per_inch], SPECIFICATION)

    with open_pdf(pdf_content) as pdf:
        left, bottom, width, height = [float(value) for value in pdf.pages[0].mediabox]
    assert (left, bottom) == (0.0, 0.0)
    assert width == pytest.approx(A4_WIDTH_IN_POINTS, abs=POINT_TOLERANCE)
    assert height == pytest.approx(A4_HEIGHT_IN_POINTS, abs=POINT_TOLERANCE)


def test_page_size_ignores_the_density_stored_in_the_jpeg():
    jpeg_stored_at_72 = build_sample_jpeg(width_pixels=300, height_pixels=150, dots_per_inch=72)

    pdf_content = PdfAssemblyService().build_pdf([jpeg_stored_at_72], SPECIFICATION)

    with open_pdf(pdf_content) as pdf:
        _, _, width, height = [float(value) for value in pdf.pages[0].mediabox]
    assert (width, height) == pytest.approx((72.0, 36.0), abs=POINT_TOLERANCE)


def test_each_jpeg_becomes_one_page():
    pages = [build_sample_jpeg(), build_sample_jpeg()]

    pdf_content = PdfAssemblyService().build_pdf(pages, SPECIFICATION)

    with open_pdf(pdf_content) as pdf:
        assert len(pdf.pages) == 2


def test_jpeg_is_embedded_without_recompression():
    jpeg_content = build_sample_jpeg()

    pdf_content = PdfAssemblyService().build_pdf([jpeg_content], SPECIFICATION)

    with open_pdf(pdf_content) as pdf:
        image_stream = next(iter(pdf.pages[0].get_images().values()))
        assert str(image_stream["/Filter"]) == "/DCTDecode"
        assert image_stream.read_raw_bytes() == jpeg_content


def test_title_is_stored_in_the_document_information():
    pdf_content = PdfAssemblyService().build_pdf([build_sample_jpeg()], SPECIFICATION)

    with open_pdf(pdf_content) as pdf:
        assert str(pdf.docinfo["/Title"]) == TITLE


def test_creator_is_digitalizadora():
    pdf_content = PdfAssemblyService().build_pdf([build_sample_jpeg()], SPECIFICATION)

    with open_pdf(pdf_content) as pdf:
        assert str(pdf.docinfo["/Creator"]) == "Digitalizadora"


def test_creation_date_is_stored_in_universal_time():
    pdf_content = PdfAssemblyService().build_pdf([build_sample_jpeg()], SPECIFICATION)

    with open_pdf(pdf_content) as pdf:
        assert str(pdf.docinfo["/CreationDate"]) == "D:20261013183012Z"


def test_empty_page_list_raises_scan_failed():
    with pytest.raises(ScanFailedError):
        PdfAssemblyService().build_pdf([], SPECIFICATION)


@pytest.mark.parametrize("unreadable_page", [b"", b"not an image", build_sample_jpeg()[:10]])
def test_unreadable_page_raises_scan_failed(unreadable_page):
    with pytest.raises(ScanFailedError):
        PdfAssemblyService().build_pdf([unreadable_page], SPECIFICATION)
```

- [ ] **Passo 10: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/services/test_pdf_assembly_service.py -v`
Expected: erro de coleta `ModuleNotFoundError: No module named 'digitalizadora.services.pdf_assembly_service'`.

- [ ] **Passo 11: Implementar**

Criar `src/digitalizadora/services/pdf_assembly_service.py`:

```python
import io
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

import img2pdf

from digitalizadora.domain.errors import ScanFailedError

PDF_CREATOR = "Digitalizadora"


@dataclass(frozen=True)
class PdfDocumentSpecification:
    dots_per_inch: int
    title: str
    created_at: datetime


class PdfAssemblyService:
    def build_pdf(self, jpeg_pages: Sequence[bytes], specification: PdfDocumentSpecification) -> bytes:
        if not jpeg_pages:
            raise ScanFailedError("A PDF needs at least one page")
        fixed_resolution = (specification.dots_per_inch, specification.dots_per_inch)
        try:
            return img2pdf.convert(
                *[io.BytesIO(page) for page in jpeg_pages],
                layout_fun=img2pdf.get_fixed_dpi_layout_fun(fixed_resolution),
                title=specification.title,
                creator=PDF_CREATOR,
                creationdate=specification.created_at,
                moddate=specification.created_at,
                engine=img2pdf.Engine.pikepdf,
                rotation=img2pdf.Rotation.ifvalid,
            )
        except img2pdf.ImageOpenError as error:
            raise ScanFailedError("A scanned page could not be read as an image") from error
```

- [ ] **Passo 12: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/services/test_pdf_assembly_service.py -v`
Expected: `11 passed` (os 3 casos do teste parametrizado contam separadamente).

#### Ciclo 4: ThumbnailService

- [ ] **Passo 13: Escrever o teste que falha**

Criar `tests/services/test_thumbnail_service.py`:

```python
import io

import pytest
from PIL import Image, JpegImagePlugin

from digitalizadora.domain.errors import ScanFailedError
from digitalizadora.services.thumbnail_service import ThumbnailService
from tests.fakes.sample_images import build_sample_jpeg

START_OF_IMAGE = b"\xff\xd8"
LUMINANCE_QUANTIZATION_AT_QUALITY_EIGHTY = 6


def read_size(jpeg_content: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(jpeg_content)) as image:
        return image.size


def test_longest_edge_is_reduced_to_the_maximum():
    thumbnail = ThumbnailService().build_thumbnail(build_sample_jpeg(400, 200), 100)

    assert max(read_size(thumbnail)) == 100


def test_aspect_ratio_is_kept_within_one_pixel():
    thumbnail = ThumbnailService().build_thumbnail(build_sample_jpeg(300, 400), 100)

    width, height = read_size(thumbnail)
    assert height == 100
    assert abs(width - 75) <= 1


def test_edge_exactly_at_the_maximum_is_kept():
    thumbnail = ThumbnailService().build_thumbnail(build_sample_jpeg(100, 50), 100)

    assert read_size(thumbnail) == (100, 50)


def test_edge_one_pixel_above_the_maximum_is_reduced():
    thumbnail = ThumbnailService().build_thumbnail(build_sample_jpeg(101, 51), 100)

    assert max(read_size(thumbnail)) == 100


def test_small_image_is_not_enlarged():
    thumbnail = ThumbnailService().build_thumbnail(build_sample_jpeg(64, 48), 480)

    assert read_size(thumbnail) == (64, 48)


def test_output_is_a_jpeg():
    thumbnail = ThumbnailService().build_thumbnail(build_sample_jpeg(), 480)

    assert thumbnail.startswith(START_OF_IMAGE)


def test_output_is_encoded_with_quality_eighty():
    thumbnail = ThumbnailService().build_thumbnail(build_sample_jpeg(), 480)

    with Image.open(io.BytesIO(thumbnail)) as image:
        assert image.quantization[0][0] == LUMINANCE_QUANTIZATION_AT_QUALITY_EIGHTY


def test_requests_the_jpeg_draft_mode_before_decoding(monkeypatch):
    recorded_requests = []
    original_draft = JpegImagePlugin.JpegImageFile.draft

    def recording_draft(image, mode, size):
        recorded_requests.append((mode, size))
        return original_draft(image, mode, size)

    monkeypatch.setattr(JpegImagePlugin.JpegImageFile, "draft", recording_draft)

    ThumbnailService().build_thumbnail(build_sample_jpeg(400, 200), 100)

    assert recorded_requests[0] == ("RGB", (100, 100))


@pytest.mark.parametrize("unreadable_content", [b"", b"not an image", build_sample_jpeg()[:-30]])
def test_unreadable_content_raises_scan_failed(unreadable_content):
    with pytest.raises(ScanFailedError):
        ThumbnailService().build_thumbnail(unreadable_content, 480)
```

- [ ] **Passo 14: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/services/test_thumbnail_service.py -v`
Expected: erro de coleta `ModuleNotFoundError: No module named 'digitalizadora.services.thumbnail_service'`.

- [ ] **Passo 15: Implementar**

Criar `src/digitalizadora/services/thumbnail_service.py`:

```python
import io

from PIL import Image

from digitalizadora.domain.errors import ScanFailedError

THUMBNAIL_JPEG_QUALITY = 80
DRAFT_COLOR_MODE = "RGB"


class ThumbnailService:
    def build_thumbnail(self, jpeg_content: bytes, maximum_edge_pixels: int) -> bytes:
        edge_limit = (maximum_edge_pixels, maximum_edge_pixels)
        buffer = io.BytesIO()
        try:
            with Image.open(io.BytesIO(jpeg_content)) as image:
                image.draft(DRAFT_COLOR_MODE, edge_limit)
                image.load()
                image.thumbnail(edge_limit)
                image.save(buffer, format="JPEG", quality=THUMBNAIL_JPEG_QUALITY)
        except OSError as error:
            raise ScanFailedError("The scanned image could not be decoded for the thumbnail") from error
        return buffer.getvalue()
```

- [ ] **Passo 16: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/services/test_thumbnail_service.py -v`
Expected: `11 passed`

#### Ciclo 5: ScanEncoder com saída JPG e validação do tipo de mídia

- [ ] **Passo 17: Escrever o teste que falha**

Criar `tests/services/test_scan_encoder.py`:

```python
import io
from datetime import datetime, timedelta, timezone

import pikepdf
import pytest
from PIL import Image

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import ScanFailedError
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_job import ScanJob
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.services.jpeg_resolution_service import JpegResolutionService
from digitalizadora.services.pdf_assembly_service import PdfAssemblyService
from digitalizadora.services.scan_encoder import THUMBNAIL_MAXIMUM_EDGE_PIXELS, ScanEncoder
from digitalizadora.services.thumbnail_service import ThumbnailService
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.sample_images import build_sample_jpeg

STARTED_AT = datetime(2026, 10, 13, 15, 30, 12, tzinfo=timezone(timedelta(hours=-3)))
START_OF_IMAGE = b"\xff\xd8"
START_OF_SCAN_MARKER = b"\xff\xda"
POINT_TOLERANCE = 0.01


def build_encoder() -> ScanEncoder:
    return ScanEncoder(JpegResolutionService(), PdfAssemblyService(), ThumbnailService())


def build_job(output_format: OutputFormat, dots_per_inch: int = 300) -> ScanJob:
    request = ScanRequest(ScanSettings(dots_per_inch, ColorMode.COLOR), output_format)
    return ScanJob(request, FixedClock(STARTED_AT).now())


def build_scanned_image(width_pixels: int = 64, height_pixels: int = 48) -> ScannedImage:
    return ScannedImage(build_sample_jpeg(width_pixels, height_pixels), "image/jpeg")


def read_jpeg_size(jpeg_content: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(jpeg_content)) as image:
        return image.size


def test_jpeg_output_carries_the_requested_density():
    encoded = build_encoder().encode(build_scanned_image(), build_job(OutputFormat.JPEG, 600))

    with Image.open(io.BytesIO(encoded.content)) as image:
        assert image.info["dpi"] == (600, 600)


def test_jpeg_output_keeps_the_scanned_pixels():
    scanned_image = build_scanned_image()

    encoded = build_encoder().encode(scanned_image, build_job(OutputFormat.JPEG))

    original_scan = scanned_image.content[scanned_image.content.index(START_OF_SCAN_MARKER):]
    assert encoded.content[encoded.content.index(START_OF_SCAN_MARKER):] == original_scan


def test_output_format_is_propagated():
    encoded = build_encoder().encode(build_scanned_image(), build_job(OutputFormat.JPEG))

    assert encoded.output_format is OutputFormat.JPEG


def test_created_at_is_the_job_start():
    encoded = build_encoder().encode(build_scanned_image(), build_job(OutputFormat.JPEG))

    assert encoded.created_at == STARTED_AT


def test_thumbnail_is_a_jpeg_limited_to_the_thumbnail_edge():
    scanned_image = build_scanned_image(width_pixels=1000, height_pixels=800)

    encoded = build_encoder().encode(scanned_image, build_job(OutputFormat.JPEG))

    assert encoded.thumbnail_jpeg.startswith(START_OF_IMAGE)
    assert max(read_jpeg_size(encoded.thumbnail_jpeg)) == THUMBNAIL_MAXIMUM_EDGE_PIXELS


def test_wrong_media_type_raises_scan_failed():
    scanned_image = ScannedImage(build_sample_jpeg(), "image/png")

    with pytest.raises(ScanFailedError):
        build_encoder().encode(scanned_image, build_job(OutputFormat.JPEG))


@pytest.mark.parametrize("unexpected_content", [b"", b"%PDF-1.4 not an image", build_sample_jpeg()[:-30]])
def test_unexpected_content_raises_scan_failed(unexpected_content):
    scanned_image = ScannedImage(unexpected_content, "image/jpeg")

    with pytest.raises(ScanFailedError):
        build_encoder().encode(scanned_image, build_job(OutputFormat.JPEG))
```

- [ ] **Passo 18: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/services/test_scan_encoder.py -v`
Expected: erro de coleta `ModuleNotFoundError: No module named 'digitalizadora.services.scan_encoder'`.

- [ ] **Passo 19: Implementar o mínimo**

Criar `src/digitalizadora/services/scan_encoder.py`:

```python
from digitalizadora.domain.encoded_scan import EncodedScan
from digitalizadora.domain.errors import ScanFailedError
from digitalizadora.domain.scan_job import ScanJob
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.services.jpeg_resolution_service import JpegResolutionService
from digitalizadora.services.pdf_assembly_service import PdfAssemblyService
from digitalizadora.services.thumbnail_service import ThumbnailService

EXPECTED_MEDIA_TYPE = "image/jpeg"
THUMBNAIL_MAXIMUM_EDGE_PIXELS = 480


class ScanEncoder:
    def __init__(
        self,
        jpeg_resolution_service: JpegResolutionService,
        pdf_assembly_service: PdfAssemblyService,
        thumbnail_service: ThumbnailService,
    ) -> None:
        self._jpeg_resolution_service = jpeg_resolution_service
        self._pdf_assembly_service = pdf_assembly_service
        self._thumbnail_service = thumbnail_service

    def encode(self, scanned_image: ScannedImage, job: ScanJob) -> EncodedScan:
        if scanned_image.media_type != EXPECTED_MEDIA_TYPE:
            raise ScanFailedError(f"Expected {EXPECTED_MEDIA_TYPE} from the scanner, got {scanned_image.media_type}")
        request = job.request
        normalised_jpeg = self._jpeg_resolution_service.with_resolution(
            scanned_image.content, request.settings.dots_per_inch
        )
        thumbnail_jpeg = self._thumbnail_service.build_thumbnail(normalised_jpeg, THUMBNAIL_MAXIMUM_EDGE_PIXELS)
        return EncodedScan(
            content=normalised_jpeg,
            output_format=request.output_format,
            created_at=job.started_at,
            thumbnail_jpeg=thumbnail_jpeg,
        )
```

- [ ] **Passo 20: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/services/test_scan_encoder.py -v`
Expected: `9 passed`

#### Ciclo 6: ScanEncoder com saída PDF

- [ ] **Passo 21: Escrever os testes que falham**

Acrescentar ao final de `tests/services/test_scan_encoder.py`:

```python
def test_pdf_output_has_one_page():
    encoded = build_encoder().encode(build_scanned_image(), build_job(OutputFormat.PDF))

    with pikepdf.open(io.BytesIO(encoded.content)) as pdf:
        assert len(pdf.pages) == 1


def test_pdf_title_carries_the_job_start_time():
    encoded = build_encoder().encode(build_scanned_image(), build_job(OutputFormat.PDF))

    with pikepdf.open(io.BytesIO(encoded.content)) as pdf:
        assert str(pdf.docinfo["/Title"]) == "Digitalização 2026-10-13 15:30:12"


def test_pdf_page_size_follows_the_requested_resolution():
    scanned_image = build_scanned_image(width_pixels=600, height_pixels=300)

    encoded = build_encoder().encode(scanned_image, build_job(OutputFormat.PDF, dots_per_inch=600))

    with pikepdf.open(io.BytesIO(encoded.content)) as pdf:
        _, _, width, height = [float(value) for value in pdf.pages[0].mediabox]
    assert (width, height) == pytest.approx((72.0, 36.0), abs=POINT_TOLERANCE)


def test_pdf_output_still_builds_a_thumbnail():
    encoded = build_encoder().encode(build_scanned_image(), build_job(OutputFormat.PDF))

    assert encoded.thumbnail_jpeg.startswith(START_OF_IMAGE)


def test_pdf_output_reports_the_pdf_format():
    encoded = build_encoder().encode(build_scanned_image(), build_job(OutputFormat.PDF))

    assert encoded.output_format is OutputFormat.PDF


def test_truncated_jpeg_is_rejected_even_when_a_pdf_is_requested():
    truncated_image = ScannedImage(build_sample_jpeg()[:-30], "image/jpeg")

    with pytest.raises(ScanFailedError):
        build_encoder().encode(truncated_image, build_job(OutputFormat.PDF))
```

- [ ] **Passo 22: Rodar os testes e ver falhar**

Run: `.venv/bin/pytest tests/services/test_scan_encoder.py -v`
Expected: `12 passed, 3 failed`. Falham `test_pdf_output_has_one_page`, `test_pdf_title_carries_the_job_start_time` e `test_pdf_page_size_follows_the_requested_resolution`, todos com `pikepdf._core.PdfError: ... unable to find trailer dictionary while recovering damaged file` (o conteúdo ainda é um JPEG, não um PDF). Os outros 12 passam (incluindo `test_truncated_jpeg_is_rejected_even_when_a_pdf_is_requested`, que já passa porque a miniatura decodifica a imagem inteira).

- [ ] **Passo 23: Implementar**

Substituir `src/digitalizadora/services/scan_encoder.py` (arquivo inteiro):

```python
from digitalizadora.domain.encoded_scan import EncodedScan
from digitalizadora.domain.errors import ScanFailedError
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_job import ScanJob
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.services.jpeg_resolution_service import JpegResolutionService
from digitalizadora.services.pdf_assembly_service import PdfAssemblyService, PdfDocumentSpecification
from digitalizadora.services.thumbnail_service import ThumbnailService

EXPECTED_MEDIA_TYPE = "image/jpeg"
THUMBNAIL_MAXIMUM_EDGE_PIXELS = 480
PDF_TITLE_TEMPLATE = "Digitalização {started_at:%Y-%m-%d %H:%M:%S}"


class ScanEncoder:
    def __init__(
        self,
        jpeg_resolution_service: JpegResolutionService,
        pdf_assembly_service: PdfAssemblyService,
        thumbnail_service: ThumbnailService,
    ) -> None:
        self._jpeg_resolution_service = jpeg_resolution_service
        self._pdf_assembly_service = pdf_assembly_service
        self._thumbnail_service = thumbnail_service

    def encode(self, scanned_image: ScannedImage, job: ScanJob) -> EncodedScan:
        if scanned_image.media_type != EXPECTED_MEDIA_TYPE:
            raise ScanFailedError(f"Expected {EXPECTED_MEDIA_TYPE} from the scanner, got {scanned_image.media_type}")
        request = job.request
        normalised_jpeg = self._jpeg_resolution_service.with_resolution(
            scanned_image.content, request.settings.dots_per_inch
        )
        thumbnail_jpeg = self._thumbnail_service.build_thumbnail(normalised_jpeg, THUMBNAIL_MAXIMUM_EDGE_PIXELS)
        return EncodedScan(
            content=self._build_final_content(normalised_jpeg, job),
            output_format=request.output_format,
            created_at=job.started_at,
            thumbnail_jpeg=thumbnail_jpeg,
        )

    def _build_final_content(self, normalised_jpeg: bytes, job: ScanJob) -> bytes:
        if job.request.output_format is not OutputFormat.PDF:
            return normalised_jpeg
        specification = PdfDocumentSpecification(
            dots_per_inch=job.request.settings.dots_per_inch,
            title=PDF_TITLE_TEMPLATE.format(started_at=job.started_at),
            created_at=job.started_at,
        )
        return self._pdf_assembly_service.build_pdf([normalised_jpeg], specification)
```

- [ ] **Passo 24: Rodar os testes da tarefa e ver passar**

Run: `.venv/bin/pytest tests/services/test_jpeg_resolution_service.py tests/services/test_pdf_assembly_service.py tests/services/test_thumbnail_service.py tests/services/test_scan_encoder.py -v`
Expected: `59 passed` (22 + 11 + 11 + 15), cada teste abaixo de 100 ms.

- [ ] **Passo 25: Commit**

```bash
git add src/digitalizadora/services/jpeg_resolution_service.py src/digitalizadora/services/pdf_assembly_service.py src/digitalizadora/services/thumbnail_service.py src/digitalizadora/services/scan_encoder.py tests/services/test_jpeg_resolution_service.py tests/services/test_pdf_assembly_service.py tests/services/test_thumbnail_service.py tests/services/test_scan_encoder.py
git commit -m "feat: add the encoding pipeline (JPEG resolution, PDF assembly, thumbnail, scan encoder)"
```

### Task 7: Repositórios (gravação atômica, pasta de saída e JSON)

**Objetivo:** Gravar arquivos de saída e ajustes sem nunca sobrescrever, deixar lixo ou perder dados numa interrupção, e traduzir qualquer falha da pasta de saída em `OutputFolderUnavailableError`.

**Files:**
- Create: `src/digitalizadora/repositories/atomic_file_writer.py`
- Create: `src/digitalizadora/repositories/file_system_scan_output_repository.py`
- Create: `src/digitalizadora/repositories/json_scanner_endpoint_repository.py`
- Create: `src/digitalizadora/repositories/json_application_settings_repository.py`
- Create: `tests/fakes/in_memory_settings_repository.py`
- Test: `tests/repositories/test_atomic_file_writer.py`
- Test: `tests/repositories/test_file_system_scan_output_repository.py`
- Test: `tests/repositories/test_json_scanner_endpoint_repository.py`
- Test: `tests/repositories/test_json_application_settings_repository.py`
- Test: `tests/repositories/test_in_memory_application_settings_repository.py`

**Interfaces:**
- Consumes (Task 2): `digitalizadora.domain.errors.OutputFolderUnavailableError`, `digitalizadora.domain.output_format.OutputFormat`, `digitalizadora.domain.scan_preset.ScanPreset`, `digitalizadora.domain.application_settings.ApplicationSettings(output_folder: Path, output_format: OutputFormat, scan_preset: ScanPreset)`, `digitalizadora.domain.scanner_endpoint.ScannerEndpoint(base_address, display_name, universally_unique_identifier=None)`, `digitalizadora.domain.encoded_scan.EncodedScan(content, output_format, created_at, thumbnail_jpeg)`, `digitalizadora.domain.scan_file_naming_policy.ScanFileNamingPolicy` (`build_file_name(scanned_at, sequence_number, output_format) -> str`, `extract_sequence_number(file_name, scanned_at) -> int | None`, esta devolvendo `None` para nomes de outra data, de outra extensão que não `pdf`/`jpg` e para o arquivo temporário `.AAAA-MM-DD_NNNNN.ext.part`), `digitalizadora.domain.ports.ApplicationSettingsRepository`.
- Produces:
  - `AtomicFileWriter.write_new_file(self, destination: Path, content: bytes) -> None` (levanta `FileExistsError` se o destino existir) e `AtomicFileWriter.replace_file(self, destination: Path, content: bytes) -> None`
  - `FileSystemScanOutputRepository(settings_repository, naming_policy, file_writer)` com `output_folder() -> Path` e `save(encoded_scan: EncodedScan) -> Path`; constante `MAXIMUM_NAME_ATTEMPTS = 1000` em `digitalizadora.repositories.file_system_scan_output_repository`
  - `JsonScannerEndpointRepository(storage_file: Path, file_writer: AtomicFileWriter)` com `load() -> ScannerEndpoint | None`, `save(endpoint) -> None`, `clear() -> None`
  - `JsonApplicationSettingsRepository(storage_file: Path, default_settings: ApplicationSettings, file_writer: AtomicFileWriter)` com `load() -> ApplicationSettings` e `save(settings) -> None`
  - `tests.fakes.in_memory_settings_repository.InMemoryApplicationSettingsRepository(settings: ApplicationSettings)` com `load()` e `save(settings)`

Notas de verificação (feitas antes de escrever o plano): `fcntl.F_FULLFSYNC` existe no Python do macOS (valor 51) e `fcntl.fcntl(descriptor, fcntl.F_FULLFSYNC)` é a chamada documentada pela Apple para esvaziar o cache do disco; `os.link(origem, destino)` levanta `FileExistsError` se o destino existir; `os.replace` é atômico no mesmo volume; `Path.unlink(missing_ok=True)` existe desde o Python 3.8. Este projeto só roda em macOS, então não há ramo para sistemas sem `F_FULLFSYNC`.

#### Ciclo 1: AtomicFileWriter, caminho feliz

- [ ] **Passo 1: Escrever o teste que falha**

Criar `tests/repositories/test_atomic_file_writer.py`:

```python
import errno
import fcntl
import os
import stat
from pathlib import Path

import pytest

from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter

TEMPORARY_FILE_NAME = ".report.pdf.part"


def list_file_names(folder: Path) -> list[str]:
    return sorted(entry.name for entry in folder.iterdir())


def test_write_new_file_creates_the_file_with_the_exact_bytes(tmp_path):
    destination = tmp_path / "report.pdf"

    AtomicFileWriter().write_new_file(destination, b"%PDF-1.4 content")

    assert destination.read_bytes() == b"%PDF-1.4 content"


def test_write_new_file_accepts_empty_content(tmp_path):
    destination = tmp_path / "report.pdf"

    AtomicFileWriter().write_new_file(destination, b"")

    assert destination.read_bytes() == b""


def test_write_new_file_refuses_to_overwrite_an_existing_file(tmp_path):
    destination = tmp_path / "report.pdf"
    destination.write_bytes(b"original")

    with pytest.raises(FileExistsError):
        AtomicFileWriter().write_new_file(destination, b"replacement")


def test_refused_write_leaves_the_original_untouched(tmp_path):
    destination = tmp_path / "report.pdf"
    destination.write_bytes(b"original")

    with pytest.raises(FileExistsError):
        AtomicFileWriter().write_new_file(destination, b"replacement")

    assert destination.read_bytes() == b"original"
    assert list_file_names(tmp_path) == ["report.pdf"]


def test_write_new_file_leaves_no_temporary_file_behind(tmp_path):
    AtomicFileWriter().write_new_file(tmp_path / "report.pdf", b"content")

    assert list_file_names(tmp_path) == ["report.pdf"]


def test_temporary_file_left_by_an_interrupted_write_does_not_block_a_new_write(tmp_path):
    (tmp_path / TEMPORARY_FILE_NAME).write_bytes(b"stale bytes from an interrupted write, longer than the content")
    destination = tmp_path / "report.pdf"

    AtomicFileWriter().write_new_file(destination, b"content")

    assert destination.read_bytes() == b"content"
    assert list_file_names(tmp_path) == ["report.pdf"]


def test_write_new_file_in_a_missing_folder_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        AtomicFileWriter().write_new_file(tmp_path / "missing" / "report.pdf", b"content")


def test_replace_file_creates_a_file_that_does_not_exist_yet(tmp_path):
    destination = tmp_path / "settings.json"

    AtomicFileWriter().replace_file(destination, b"{}")

    assert destination.read_bytes() == b"{}"


def test_replace_file_replaces_the_previous_content(tmp_path):
    destination = tmp_path / "settings.json"
    destination.write_bytes(b'{"old": true}')

    AtomicFileWriter().replace_file(destination, b"{}")

    assert destination.read_bytes() == b"{}"


def test_replace_file_leaves_no_temporary_file_behind(tmp_path):
    AtomicFileWriter().replace_file(tmp_path / "settings.json", b"{}")

    assert list_file_names(tmp_path) == ["settings.json"]
```

- [ ] **Passo 2: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/repositories/test_atomic_file_writer.py -v`
Expected: erro de coleta `ModuleNotFoundError: No module named 'digitalizadora.repositories.atomic_file_writer'`.

- [ ] **Passo 3: Implementar o mínimo**

Criar `src/digitalizadora/repositories/atomic_file_writer.py`:

```python
import logging
import os
from pathlib import Path

LOGGER = logging.getLogger(__name__)

TEMPORARY_FILE_PREFIX = "."
TEMPORARY_FILE_SUFFIX = ".part"
TEMPORARY_FILE_PERMISSIONS = 0o644


def temporary_path_for(destination: Path) -> Path:
    return destination.with_name(f"{TEMPORARY_FILE_PREFIX}{destination.name}{TEMPORARY_FILE_SUFFIX}")


def remove_temporary_file(temporary: Path) -> None:
    try:
        temporary.unlink(missing_ok=True)
    except OSError:
        LOGGER.warning("Could not remove the temporary file %s", temporary)


class AtomicFileWriter:
    def write_new_file(self, destination: Path, content: bytes) -> None:
        if destination.exists():
            raise FileExistsError(f"Refusing to overwrite {destination}")
        temporary = temporary_path_for(destination)
        try:
            self._write_temporary_file(temporary, content)
            os.link(temporary, destination)
        finally:
            remove_temporary_file(temporary)

    def replace_file(self, destination: Path, content: bytes) -> None:
        temporary = temporary_path_for(destination)
        try:
            self._write_temporary_file(temporary, content)
            os.replace(temporary, destination)
        finally:
            remove_temporary_file(temporary)

    def _write_temporary_file(self, temporary: Path, content: bytes) -> None:
        remove_temporary_file(temporary)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_TRUNC
        descriptor = os.open(temporary, flags, TEMPORARY_FILE_PERMISSIONS)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
```

- [ ] **Passo 4: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/repositories/test_atomic_file_writer.py -v`
Expected: `10 passed`

#### Ciclo 2: AtomicFileWriter, sincronização em disco e plano B para volumes sem hard link

- [ ] **Passo 5: Escrever os testes que falham**

Acrescentar ao final de `tests/repositories/test_atomic_file_writer.py`:

```python
def describe_descriptor(descriptor: int) -> str:
    return "directory" if stat.S_ISDIR(os.fstat(descriptor).st_mode) else "file"


class FullSyncRecorder:
    def __init__(self) -> None:
        self.synchronised_kinds: list[str] = []
        self._original_fcntl = fcntl.fcntl

    def __call__(self, descriptor: int, command: int) -> int:
        if command == fcntl.F_FULLFSYNC:
            self.synchronised_kinds.append(describe_descriptor(descriptor))
        return self._original_fcntl(descriptor, command)


def disable_full_sync(monkeypatch) -> list[str]:
    """Make F_FULLFSYNC fail and return the kinds of descriptors that fall back to fsync."""
    fallback_kinds: list[str] = []
    original_fsync = os.fsync

    def unsupported_full_sync(descriptor: int, command: int) -> int:
        raise OSError(errno.ENOTTY, "F_FULLFSYNC is not supported")

    def recording_fsync(descriptor: int) -> None:
        fallback_kinds.append(describe_descriptor(descriptor))
        original_fsync(descriptor)

    monkeypatch.setattr(fcntl, "fcntl", unsupported_full_sync)
    monkeypatch.setattr(os, "fsync", recording_fsync)
    return fallback_kinds


def fail_for_directories(original_function):
    def guarded_function(descriptor: int, *arguments):
        if stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise OSError(errno.EINVAL, "directories cannot be synchronised")
        return original_function(descriptor, *arguments)

    return guarded_function


def test_file_and_then_directory_are_flushed_with_full_fsync(tmp_path, monkeypatch):
    recorder = FullSyncRecorder()
    monkeypatch.setattr(fcntl, "fcntl", recorder)

    AtomicFileWriter().write_new_file(tmp_path / "report.pdf", b"content")

    assert recorder.synchronised_kinds == ["file", "directory"]


def test_replace_file_also_flushes_the_file_and_the_directory(tmp_path, monkeypatch):
    recorder = FullSyncRecorder()
    monkeypatch.setattr(fcntl, "fcntl", recorder)

    AtomicFileWriter().replace_file(tmp_path / "settings.json", b"{}")

    assert recorder.synchronised_kinds == ["file", "directory"]


def test_unsupported_full_fsync_still_writes_the_file(tmp_path, monkeypatch):
    disable_full_sync(monkeypatch)
    destination = tmp_path / "report.pdf"

    AtomicFileWriter().write_new_file(destination, b"content")

    assert destination.read_bytes() == b"content"


def test_unsupported_full_fsync_falls_back_to_fsync_for_the_file_and_the_directory(tmp_path, monkeypatch):
    fallback_kinds = disable_full_sync(monkeypatch)

    AtomicFileWriter().write_new_file(tmp_path / "report.pdf", b"content")

    assert fallback_kinds == ["file", "directory"]


def test_directory_synchronisation_failure_does_not_fail_the_write(tmp_path, monkeypatch):
    monkeypatch.setattr(fcntl, "fcntl", fail_for_directories(fcntl.fcntl))
    monkeypatch.setattr(os, "fsync", fail_for_directories(os.fsync))
    destination = tmp_path / "report.pdf"

    AtomicFileWriter().write_new_file(destination, b"content")

    assert destination.read_bytes() == b"content"


def test_publishes_with_rename_when_the_volume_has_no_hard_links(tmp_path, monkeypatch):
    def unsupported_link(source: Path, destination: Path) -> None:
        raise OSError(errno.ENOTSUP, "hard links are not supported")

    monkeypatch.setattr(os, "link", unsupported_link)
    destination = tmp_path / "report.pdf"

    AtomicFileWriter().write_new_file(destination, b"content")

    assert destination.read_bytes() == b"content"
    assert list_file_names(tmp_path) == ["report.pdf"]


def test_rename_fallback_refuses_a_destination_that_appeared_meanwhile(tmp_path, monkeypatch):
    destination = tmp_path / "report.pdf"

    def link_that_loses_a_race(source: Path, target: Path) -> None:
        destination.write_bytes(b"created by another process")
        raise OSError(errno.ENOTSUP, "hard links are not supported")

    monkeypatch.setattr(os, "link", link_that_loses_a_race)

    with pytest.raises(FileExistsError):
        AtomicFileWriter().write_new_file(destination, b"content")

    assert destination.read_bytes() == b"created by another process"
    assert list_file_names(tmp_path) == ["report.pdf"]


def test_losing_the_link_race_raises_file_exists_and_leaves_no_temporary_file(tmp_path, monkeypatch):
    def link_to_an_existing_destination(source: Path, destination: Path) -> None:
        raise FileExistsError(destination)

    monkeypatch.setattr(os, "link", link_to_an_existing_destination)

    with pytest.raises(FileExistsError):
        AtomicFileWriter().write_new_file(tmp_path / "report.pdf", b"content")

    assert list_file_names(tmp_path) == []


def test_failure_while_writing_the_content_leaves_no_temporary_file(tmp_path, monkeypatch):
    def full_disk(descriptor: int) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    disable_full_sync(monkeypatch)
    monkeypatch.setattr(os, "fsync", full_disk)

    with pytest.raises(OSError, match="No space left on device"):
        AtomicFileWriter().write_new_file(tmp_path / "report.pdf", b"content")

    assert list_file_names(tmp_path) == []


def test_failure_to_publish_leaves_no_temporary_file(tmp_path, monkeypatch):
    def unsupported_link(source: Path, destination: Path) -> None:
        raise OSError(errno.ENOTSUP, "hard links are not supported")

    def failing_rename(source: Path, destination: Path) -> None:
        raise OSError(errno.EIO, "input/output error")

    monkeypatch.setattr(os, "link", unsupported_link)
    monkeypatch.setattr(os, "rename", failing_rename)

    with pytest.raises(OSError, match="input/output error"):
        AtomicFileWriter().write_new_file(tmp_path / "report.pdf", b"content")

    assert list_file_names(tmp_path) == []
```

- [ ] **Passo 6: Rodar os testes e ver falhar**

Run: `.venv/bin/pytest tests/repositories/test_atomic_file_writer.py -v`
Expected: `14 passed, 6 failed`. Os dez testes do ciclo 1 e quatro do ciclo 2 passam. Falham: `test_file_and_then_directory_are_flushed_with_full_fsync` e `test_replace_file_also_flushes_the_file_and_the_directory` (`AssertionError: assert [] == ['file', 'directory']`), `test_unsupported_full_fsync_falls_back_to_fsync_for_the_file_and_the_directory` (`AssertionError: assert ['file'] == ['file', 'directory']`), `test_publishes_with_rename_when_the_volume_has_no_hard_links` e `test_rename_fallback_refuses_a_destination_that_appeared_meanwhile` (`OSError: [Errno 45] hard links are not supported`) e `test_failure_to_publish_leaves_no_temporary_file` (`AssertionError: Regex pattern did not match`, porque o erro que sobe ainda é o de `os.link`).

- [ ] **Passo 7: Implementar**

Substituir `src/digitalizadora/repositories/atomic_file_writer.py` (arquivo inteiro):

```python
import fcntl
import logging
import os
from pathlib import Path

LOGGER = logging.getLogger(__name__)

TEMPORARY_FILE_PREFIX = "."
TEMPORARY_FILE_SUFFIX = ".part"
TEMPORARY_FILE_PERMISSIONS = 0o644


def temporary_path_for(destination: Path) -> Path:
    return destination.with_name(f"{TEMPORARY_FILE_PREFIX}{destination.name}{TEMPORARY_FILE_SUFFIX}")


def remove_temporary_file(temporary: Path) -> None:
    try:
        temporary.unlink(missing_ok=True)
    except OSError:
        LOGGER.warning("Could not remove the temporary file %s", temporary)


def flush_to_disk(descriptor: int) -> None:
    """Ask the drive to empty its own cache; plain fsync on macOS only reaches the drive's buffer."""
    try:
        fcntl.fcntl(descriptor, fcntl.F_FULLFSYNC)
    except OSError:
        os.fsync(descriptor)


class AtomicFileWriter:
    def write_new_file(self, destination: Path, content: bytes) -> None:
        if destination.exists():
            raise FileExistsError(f"Refusing to overwrite {destination}")
        temporary = temporary_path_for(destination)
        try:
            self._write_temporary_file(temporary, content)
            self._publish_without_overwriting(temporary, destination)
        finally:
            remove_temporary_file(temporary)
        self._synchronise_directory(destination.parent)

    def replace_file(self, destination: Path, content: bytes) -> None:
        temporary = temporary_path_for(destination)
        try:
            self._write_temporary_file(temporary, content)
            os.replace(temporary, destination)
        finally:
            remove_temporary_file(temporary)
        self._synchronise_directory(destination.parent)

    def _write_temporary_file(self, temporary: Path, content: bytes) -> None:
        remove_temporary_file(temporary)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_TRUNC
        descriptor = os.open(temporary, flags, TEMPORARY_FILE_PERMISSIONS)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            flush_to_disk(stream.fileno())

    def _publish_without_overwriting(self, temporary: Path, destination: Path) -> None:
        try:
            os.link(temporary, destination)
        except FileExistsError:
            raise
        except OSError:
            # Volumes such as exFAT do not support hard links, so fall back to rename after checking again.
            if destination.exists():
                raise FileExistsError(f"Refusing to overwrite {destination}") from None
            os.rename(temporary, destination)

    def _synchronise_directory(self, directory: Path) -> None:
        try:
            descriptor = os.open(directory, os.O_RDONLY)
            try:
                flush_to_disk(descriptor)
            finally:
                os.close(descriptor)
        except OSError:
            LOGGER.warning("Could not synchronise the directory %s", directory)
```

- [ ] **Passo 8: Rodar os testes e ver passar**

Run: `.venv/bin/pytest tests/repositories/test_atomic_file_writer.py -v`
Expected: `20 passed`

#### Ciclo 3: dublê em memória e FileSystemScanOutputRepository, nomes sequenciais

- [ ] **Passo 9: Escrever os testes que falham**

Criar `tests/repositories/test_in_memory_application_settings_repository.py`:

```python
from pathlib import Path

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from tests.fakes.in_memory_settings_repository import InMemoryApplicationSettingsRepository

INITIAL_SETTINGS = ApplicationSettings(Path("/scans"), OutputFormat.PDF, ScanPreset.DOCUMENT)
CHANGED_SETTINGS = ApplicationSettings(Path("/photos"), OutputFormat.JPEG, ScanPreset.PHOTO)


def test_load_returns_the_settings_given_at_construction():
    assert InMemoryApplicationSettingsRepository(INITIAL_SETTINGS).load() == INITIAL_SETTINGS


def test_load_returns_the_last_saved_settings():
    repository = InMemoryApplicationSettingsRepository(INITIAL_SETTINGS)

    repository.save(CHANGED_SETTINGS)

    assert repository.load() == CHANGED_SETTINGS
```

Criar `tests/repositories/test_file_system_scan_output_repository.py`:

```python
import errno
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.encoded_scan import EncodedScan
from digitalizadora.domain.errors import OutputFolderUnavailableError
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_file_naming_policy import ScanFileNamingPolicy
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter
from digitalizadora.repositories.file_system_scan_output_repository import (
    MAXIMUM_NAME_ATTEMPTS,
    FileSystemScanOutputRepository,
)
from tests.fakes.in_memory_settings_repository import InMemoryApplicationSettingsRepository

TIME_ZONE = timezone(timedelta(hours=-3))
SCANNED_AT = datetime(2026, 10, 13, 15, 30, 12, tzinfo=TIME_ZONE)
NEXT_DAY = datetime(2026, 10, 14, 9, 0, 0, tzinfo=TIME_ZONE)
READ_ONLY_FOLDER_MODE = 0o500
WRITABLE_FOLDER_MODE = 0o700


def build_encoded_scan(
    output_format: OutputFormat = OutputFormat.PDF, created_at: datetime = SCANNED_AT
) -> EncodedScan:
    return EncodedScan(
        content=b"scan content",
        output_format=output_format,
        created_at=created_at,
        thumbnail_jpeg=b"thumbnail",
    )


def build_repository(output_folder: Path, file_writer) -> FileSystemScanOutputRepository:
    settings = ApplicationSettings(output_folder, OutputFormat.PDF, ScanPreset.DOCUMENT)
    return FileSystemScanOutputRepository(
        InMemoryApplicationSettingsRepository(settings), ScanFileNamingPolicy(), file_writer
    )


def build_real_repository(output_folder: Path) -> FileSystemScanOutputRepository:
    return build_repository(output_folder, AtomicFileWriter())


def test_output_folder_comes_from_the_settings(tmp_path):
    assert build_real_repository(tmp_path / "scans").output_folder() == tmp_path / "scans"


def test_first_file_of_the_day_ends_with_sequence_one(tmp_path):
    saved_path = build_real_repository(tmp_path).save(build_encoded_scan())

    assert saved_path == tmp_path / "2026-10-13_00001.pdf"


def test_saved_file_holds_the_encoded_content(tmp_path):
    saved_path = build_real_repository(tmp_path).save(build_encoded_scan())

    assert saved_path.read_bytes() == b"scan content"


def test_next_file_of_the_day_ends_with_sequence_two(tmp_path):
    repository = build_real_repository(tmp_path)
    repository.save(build_encoded_scan())

    second_path = repository.save(build_encoded_scan())

    assert second_path.name == "2026-10-13_00002.pdf"


def test_sequence_continues_after_the_highest_existing_number_when_there_are_gaps(tmp_path):
    (tmp_path / "2026-10-13_00003.pdf").write_bytes(b"x")
    (tmp_path / "2026-10-13_00007.jpg").write_bytes(b"x")

    saved_path = build_real_repository(tmp_path).save(build_encoded_scan())

    assert saved_path.name == "2026-10-13_00008.pdf"


def test_files_of_other_dates_do_not_interfere(tmp_path):
    (tmp_path / "2026-10-12_00009.pdf").write_bytes(b"x")

    saved_path = build_real_repository(tmp_path).save(build_encoded_scan())

    assert saved_path.name == "2026-10-13_00001.pdf"


def test_each_date_has_its_own_counter(tmp_path):
    repository = build_real_repository(tmp_path)
    repository.save(build_encoded_scan(created_at=SCANNED_AT))

    next_day_path = repository.save(build_encoded_scan(created_at=NEXT_DAY))

    assert next_day_path.name == "2026-10-14_00001.pdf"


def test_files_with_other_extensions_do_not_interfere(tmp_path):
    (tmp_path / "2026-10-13_00009.png").write_bytes(b"x")
    (tmp_path / "2026-10-13_00009.txt").write_bytes(b"x")

    saved_path = build_real_repository(tmp_path).save(build_encoded_scan())

    assert saved_path.name == "2026-10-13_00001.pdf"


def test_pdf_and_jpeg_of_the_same_date_share_the_counter(tmp_path):
    (tmp_path / "2026-10-13_00004.jpg").write_bytes(b"x")

    saved_path = build_real_repository(tmp_path).save(build_encoded_scan(OutputFormat.PDF))

    assert saved_path.name == "2026-10-13_00005.pdf"


def test_jpeg_uses_the_jpg_extension_and_the_shared_counter(tmp_path):
    (tmp_path / "2026-10-13_00004.pdf").write_bytes(b"x")

    saved_path = build_real_repository(tmp_path).save(build_encoded_scan(OutputFormat.JPEG))

    assert saved_path.name == "2026-10-13_00005.jpg"


def test_unrelated_files_and_leftover_temporary_files_are_ignored(tmp_path):
    for name in ("notes.txt", "2026-10-13_abc.pdf", ".2026-10-13_00009.pdf.part"):
        (tmp_path / name).write_bytes(b"x")

    saved_path = build_real_repository(tmp_path).save(build_encoded_scan())

    assert saved_path.name == "2026-10-13_00001.pdf"


def test_missing_output_folder_is_created(tmp_path):
    output_folder = tmp_path / "external disk" / "scans"

    saved_path = build_real_repository(output_folder).save(build_encoded_scan())

    assert saved_path.parent == output_folder
    assert saved_path.exists()
```

- [ ] **Passo 10: Rodar os testes e ver falhar**

Run: `.venv/bin/pytest tests/repositories/test_in_memory_application_settings_repository.py tests/repositories/test_file_system_scan_output_repository.py -v`
Expected: dois erros de coleta: `ModuleNotFoundError: No module named 'tests.fakes.in_memory_settings_repository'` e `ModuleNotFoundError: No module named 'digitalizadora.repositories.file_system_scan_output_repository'`.

- [ ] **Passo 11: Implementar o mínimo**

Criar `tests/fakes/in_memory_settings_repository.py`:

```python
from digitalizadora.domain.application_settings import ApplicationSettings


class InMemoryApplicationSettingsRepository:
    def __init__(self, settings: ApplicationSettings) -> None:
        self._settings = settings

    def load(self) -> ApplicationSettings:
        return self._settings

    def save(self, settings: ApplicationSettings) -> None:
        self._settings = settings
```

Criar `src/digitalizadora/repositories/file_system_scan_output_repository.py`:

```python
from datetime import datetime
from pathlib import Path

from digitalizadora.domain.encoded_scan import EncodedScan
from digitalizadora.domain.ports import ApplicationSettingsRepository
from digitalizadora.domain.scan_file_naming_policy import ScanFileNamingPolicy
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter

MAXIMUM_NAME_ATTEMPTS = 1000


class FileSystemScanOutputRepository:
    def __init__(
        self,
        settings_repository: ApplicationSettingsRepository,
        naming_policy: ScanFileNamingPolicy,
        file_writer: AtomicFileWriter,
    ) -> None:
        self._settings_repository = settings_repository
        self._naming_policy = naming_policy
        self._file_writer = file_writer

    def output_folder(self) -> Path:
        return self._settings_repository.load().output_folder

    def save(self, encoded_scan: EncodedScan) -> Path:
        folder = self.output_folder()
        folder.mkdir(parents=True, exist_ok=True)
        sequence_number = self._highest_sequence_number(folder, encoded_scan.created_at) + 1
        destination = folder / self._naming_policy.build_file_name(
            encoded_scan.created_at, sequence_number, encoded_scan.output_format
        )
        self._file_writer.write_new_file(destination, encoded_scan.content)
        return destination

    def _highest_sequence_number(self, folder: Path, scanned_at: datetime) -> int:
        sequence_numbers = (
            self._naming_policy.extract_sequence_number(entry.name, scanned_at) for entry in folder.iterdir()
        )
        return max((number for number in sequence_numbers if number is not None), default=0)
```

- [ ] **Passo 12: Rodar os testes e ver passar**

Run: `.venv/bin/pytest tests/repositories/test_in_memory_application_settings_repository.py tests/repositories/test_file_system_scan_output_repository.py -v`
Expected: `14 passed` (2 do dublê e 12 do repositório).

#### Ciclo 4: FileSystemScanOutputRepository, pasta indisponível, corrida de nomes e disco cheio

- [ ] **Passo 13: Escrever os testes que falham**

Acrescentar ao final de `tests/repositories/test_file_system_scan_output_repository.py`:

```python
class FileWriterThatSucceedsOnAttempt:
    def __init__(self, successful_attempt: int) -> None:
        self._successful_attempt = successful_attempt
        self.attempted_destinations: list[Path] = []

    def write_new_file(self, destination: Path, content: bytes) -> None:
        self.attempted_destinations.append(destination)
        if len(self.attempted_destinations) < self._successful_attempt:
            raise FileExistsError(destination)


class FullDiskFileWriter:
    def write_new_file(self, destination: Path, content: bytes) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")


class RacingFileWriter:
    """Lets another 'process' take the first chosen name right before the real write."""

    def __init__(self, real_writer: AtomicFileWriter) -> None:
        self._real_writer = real_writer
        self._race_already_happened = False

    def write_new_file(self, destination: Path, content: bytes) -> None:
        if not self._race_already_happened:
            self._race_already_happened = True
            self._real_writer.write_new_file(destination, b"written by another process")
        self._real_writer.write_new_file(destination, content)


def test_output_folder_that_is_a_file_raises_output_folder_unavailable(tmp_path):
    blocking_file = tmp_path / "scans"
    blocking_file.write_bytes(b"not a folder")

    with pytest.raises(OutputFolderUnavailableError):
        build_real_repository(blocking_file).save(build_encoded_scan())


def test_output_folder_below_a_file_raises_output_folder_unavailable(tmp_path):
    blocking_file = tmp_path / "scans"
    blocking_file.write_bytes(b"not a folder")

    with pytest.raises(OutputFolderUnavailableError):
        build_real_repository(blocking_file / "nested").save(build_encoded_scan())


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permission bits")
def test_read_only_output_folder_raises_output_folder_unavailable(tmp_path):
    output_folder = tmp_path / "scans"
    output_folder.mkdir()
    output_folder.chmod(READ_ONLY_FOLDER_MODE)
    try:
        with pytest.raises(OutputFolderUnavailableError):
            build_real_repository(output_folder).save(build_encoded_scan())
    finally:
        output_folder.chmod(WRITABLE_FOLDER_MODE)


def test_full_disk_raises_output_folder_unavailable(tmp_path):
    repository = build_repository(tmp_path, FullDiskFileWriter())

    with pytest.raises(OutputFolderUnavailableError):
        repository.save(build_encoded_scan())


def test_name_taken_by_another_process_moves_to_the_following_number(tmp_path):
    repository = build_repository(tmp_path, RacingFileWriter(AtomicFileWriter()))

    saved_path = repository.save(build_encoded_scan())

    assert saved_path.name == "2026-10-13_00002.pdf"
    assert (tmp_path / "2026-10-13_00001.pdf").read_bytes() == b"written by another process"


def test_last_allowed_attempt_still_saves_the_file(tmp_path):
    file_writer = FileWriterThatSucceedsOnAttempt(MAXIMUM_NAME_ATTEMPTS)

    saved_path = build_repository(tmp_path, file_writer).save(build_encoded_scan())

    assert saved_path.name == "2026-10-13_01000.pdf"
    assert len(file_writer.attempted_destinations) == MAXIMUM_NAME_ATTEMPTS


def test_one_attempt_beyond_the_limit_raises_output_folder_unavailable(tmp_path):
    file_writer = FileWriterThatSucceedsOnAttempt(MAXIMUM_NAME_ATTEMPTS + 1)

    with pytest.raises(OutputFolderUnavailableError):
        build_repository(tmp_path, file_writer).save(build_encoded_scan())

    assert len(file_writer.attempted_destinations) == MAXIMUM_NAME_ATTEMPTS
```

- [ ] **Passo 14: Rodar os testes e ver falhar**

Run: `.venv/bin/pytest tests/repositories/test_file_system_scan_output_repository.py -v`
Expected: `12 passed, 7 failed`. Os 12 testes do ciclo 3 passam. Falham: `test_output_folder_that_is_a_file_raises_output_folder_unavailable` (`FileExistsError`), `test_output_folder_below_a_file_raises_output_folder_unavailable` (`NotADirectoryError`), `test_read_only_output_folder_raises_output_folder_unavailable` (`PermissionError`), `test_full_disk_raises_output_folder_unavailable` (`OSError: [Errno 28] No space left on device`), `test_name_taken_by_another_process_moves_to_the_following_number`, `test_last_allowed_attempt_still_saves_the_file` e `test_one_attempt_beyond_the_limit_raises_output_folder_unavailable` (os três com `FileExistsError`).

- [ ] **Passo 15: Implementar**

Substituir `src/digitalizadora/repositories/file_system_scan_output_repository.py` (arquivo inteiro):

```python
from datetime import datetime
from pathlib import Path

from digitalizadora.domain.encoded_scan import EncodedScan
from digitalizadora.domain.errors import OutputFolderUnavailableError
from digitalizadora.domain.ports import ApplicationSettingsRepository
from digitalizadora.domain.scan_file_naming_policy import ScanFileNamingPolicy
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter

MAXIMUM_NAME_ATTEMPTS = 1000


class FileSystemScanOutputRepository:
    def __init__(
        self,
        settings_repository: ApplicationSettingsRepository,
        naming_policy: ScanFileNamingPolicy,
        file_writer: AtomicFileWriter,
    ) -> None:
        self._settings_repository = settings_repository
        self._naming_policy = naming_policy
        self._file_writer = file_writer

    def output_folder(self) -> Path:
        return self._settings_repository.load().output_folder

    def save(self, encoded_scan: EncodedScan) -> Path:
        folder = self.output_folder()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            first_sequence_number = self._highest_sequence_number(folder, encoded_scan.created_at) + 1
        except OSError as error:
            raise OutputFolderUnavailableError(f"Cannot use the output folder {folder}: {error}") from error
        return self._write_under_a_free_name(folder, encoded_scan, first_sequence_number)

    def _write_under_a_free_name(self, folder: Path, encoded_scan: EncodedScan, first_sequence_number: int) -> Path:
        for sequence_number in range(first_sequence_number, first_sequence_number + MAXIMUM_NAME_ATTEMPTS):
            destination = folder / self._naming_policy.build_file_name(
                encoded_scan.created_at, sequence_number, encoded_scan.output_format
            )
            try:
                self._file_writer.write_new_file(destination, encoded_scan.content)
            except FileExistsError:
                continue
            except OSError as error:
                raise OutputFolderUnavailableError(f"Cannot write {destination}: {error}") from error
            return destination
        raise OutputFolderUnavailableError(
            f"No free file name in {folder} after {MAXIMUM_NAME_ATTEMPTS} attempts"
        )

    def _highest_sequence_number(self, folder: Path, scanned_at: datetime) -> int:
        sequence_numbers = (
            self._naming_policy.extract_sequence_number(entry.name, scanned_at) for entry in folder.iterdir()
        )
        return max((number for number in sequence_numbers if number is not None), default=0)
```

- [ ] **Passo 16: Rodar os testes e ver passar**

Run: `.venv/bin/pytest tests/repositories/test_file_system_scan_output_repository.py -v`
Expected: `19 passed` (ou `18 passed, 1 skipped` se a suíte rodar como root)

#### Ciclo 5: JsonScannerEndpointRepository

- [ ] **Passo 17: Escrever o teste que falha**

Criar `tests/repositories/test_json_scanner_endpoint_repository.py`:

```python
import json
import logging
from pathlib import Path

import pytest

from digitalizadora.domain.scanner_endpoint import ScannerEndpoint
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter
from digitalizadora.repositories.json_scanner_endpoint_repository import JsonScannerEndpointRepository

ENDPOINT = ScannerEndpoint(
    base_address="http://192.168.0.40:8080/eSCL",
    display_name="HP DeskJet 2800 series",
    universally_unique_identifier="11111111-2222-3333-4444-555555555555",
)
ENDPOINT_WITHOUT_IDENTIFIER = ScannerEndpoint(base_address="http://192.168.0.41:8080/eSCL", display_name="Printer")


def build_repository(storage_file: Path) -> JsonScannerEndpointRepository:
    return JsonScannerEndpointRepository(storage_file, AtomicFileWriter())


def test_load_returns_none_when_the_file_is_missing(tmp_path):
    assert build_repository(tmp_path / "scanner-endpoint.json").load() is None


def test_saved_endpoint_is_loaded_back_equal(tmp_path):
    repository = build_repository(tmp_path / "scanner-endpoint.json")

    repository.save(ENDPOINT)

    assert repository.load() == ENDPOINT


def test_endpoint_without_identifier_is_loaded_back_equal(tmp_path):
    repository = build_repository(tmp_path / "scanner-endpoint.json")

    repository.save(ENDPOINT_WITHOUT_IDENTIFIER)

    assert repository.load() == ENDPOINT_WITHOUT_IDENTIFIER


def test_save_writes_the_documented_json_shape(tmp_path):
    storage_file = tmp_path / "scanner-endpoint.json"

    build_repository(storage_file).save(ENDPOINT)

    assert json.loads(storage_file.read_text(encoding="utf-8")) == {
        "base_address": "http://192.168.0.40:8080/eSCL",
        "display_name": "HP DeskJet 2800 series",
        "universally_unique_identifier": "11111111-2222-3333-4444-555555555555",
    }


def test_save_creates_the_missing_data_folder(tmp_path):
    storage_file = tmp_path / "Application Support" / "Digitalizadora" / "scanner-endpoint.json"

    build_repository(storage_file).save(ENDPOINT)

    assert storage_file.exists()


def test_save_replaces_the_previous_endpoint(tmp_path):
    repository = build_repository(tmp_path / "scanner-endpoint.json")
    repository.save(ENDPOINT)

    repository.save(ENDPOINT_WITHOUT_IDENTIFIER)

    assert repository.load() == ENDPOINT_WITHOUT_IDENTIFIER


UNUSABLE_DOCUMENTS = [
    "",
    "{not json",
    "[]",
    '"text"',
    "{}",
    '{"base_address": "http://192.168.0.40:8080/eSCL"}',
    '{"base_address": "", "display_name": "Printer"}',
    '{"base_address": 5, "display_name": "Printer"}',
    '{"base_address": "http://192.168.0.40:8080/eSCL", "display_name": "Printer", "universally_unique_identifier": 7}',
]


@pytest.mark.parametrize("unusable_document", UNUSABLE_DOCUMENTS)
def test_load_returns_none_for_a_corrupt_or_incomplete_file(tmp_path, unusable_document):
    storage_file = tmp_path / "scanner-endpoint.json"
    storage_file.write_text(unusable_document, encoding="utf-8")

    assert build_repository(storage_file).load() is None


def test_load_returns_none_for_a_file_that_is_not_text(tmp_path):
    storage_file = tmp_path / "scanner-endpoint.json"
    storage_file.write_bytes(b"\xff\xfe\x00\x80")

    assert build_repository(storage_file).load() is None


def test_corrupt_file_is_reported_with_a_warning(tmp_path, caplog):
    storage_file = tmp_path / "scanner-endpoint.json"
    storage_file.write_text("{not json", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        build_repository(storage_file).load()

    assert [record.levelno for record in caplog.records] == [logging.WARNING]


def test_missing_file_is_not_reported_as_a_problem(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        build_repository(tmp_path / "scanner-endpoint.json").load()

    assert caplog.records == []


def test_clear_removes_the_saved_endpoint(tmp_path):
    repository = build_repository(tmp_path / "scanner-endpoint.json")
    repository.save(ENDPOINT)

    repository.clear()

    assert repository.load() is None
    assert not (tmp_path / "scanner-endpoint.json").exists()


def test_clear_is_idempotent(tmp_path):
    repository = build_repository(tmp_path / "scanner-endpoint.json")

    repository.clear()
    repository.clear()

    assert repository.load() is None
```

- [ ] **Passo 18: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/repositories/test_json_scanner_endpoint_repository.py -v`
Expected: erro de coleta `ModuleNotFoundError: No module named 'digitalizadora.repositories.json_scanner_endpoint_repository'`.

- [ ] **Passo 19: Implementar**

Criar `src/digitalizadora/repositories/json_scanner_endpoint_repository.py`:

```python
import json
import logging
from pathlib import Path

from digitalizadora.domain.scanner_endpoint import ScannerEndpoint
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter

LOGGER = logging.getLogger(__name__)


def parse_scanner_endpoint(document: object) -> ScannerEndpoint:
    if not isinstance(document, dict):
        raise ValueError("The scanner endpoint document must be a JSON object")
    base_address = document.get("base_address")
    display_name = document.get("display_name")
    identifier = document.get("universally_unique_identifier")
    if not isinstance(base_address, str) or not base_address:
        raise ValueError("The scanner endpoint document has no base_address")
    if not isinstance(display_name, str):
        raise ValueError("The scanner endpoint document has no display_name")
    if identifier is not None and not isinstance(identifier, str):
        raise ValueError("The scanner endpoint identifier must be text")
    return ScannerEndpoint(base_address, display_name, identifier)


class JsonScannerEndpointRepository:
    def __init__(self, storage_file: Path, file_writer: AtomicFileWriter) -> None:
        self._storage_file = storage_file
        self._file_writer = file_writer

    def load(self) -> ScannerEndpoint | None:
        try:
            document = json.loads(self._storage_file.read_text(encoding="utf-8"))
            return parse_scanner_endpoint(document)
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as error:
            LOGGER.warning("Ignoring the unusable scanner endpoint file %s: %s", self._storage_file, error)
            return None

    def save(self, endpoint: ScannerEndpoint) -> None:
        document = {
            "base_address": endpoint.base_address,
            "display_name": endpoint.display_name,
            "universally_unique_identifier": endpoint.universally_unique_identifier,
        }
        self._storage_file.parent.mkdir(parents=True, exist_ok=True)
        self._file_writer.replace_file(self._storage_file, json.dumps(document, indent=2).encode("utf-8"))

    def clear(self) -> None:
        self._storage_file.unlink(missing_ok=True)
```

- [ ] **Passo 20: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/repositories/test_json_scanner_endpoint_repository.py -v`
Expected: `20 passed`

#### Ciclo 6: JsonApplicationSettingsRepository

- [ ] **Passo 21: Escrever o teste que falha**

Criar `tests/repositories/test_json_application_settings_repository.py`:

```python
import json
import logging
from pathlib import Path

import pytest

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter
from digitalizadora.repositories.json_application_settings_repository import JsonApplicationSettingsRepository

DEFAULT_SETTINGS = ApplicationSettings(
    Path("/Users/someone/Pictures/Digitalizadora"), OutputFormat.PDF, ScanPreset.DOCUMENT
)
CUSTOM_SETTINGS = ApplicationSettings(Path("/Volumes/Archive/Digitalização"), OutputFormat.JPEG, ScanPreset.PHOTO)


def build_repository(storage_file: Path) -> JsonApplicationSettingsRepository:
    return JsonApplicationSettingsRepository(storage_file, DEFAULT_SETTINGS, AtomicFileWriter())


def write_document(storage_file: Path, document: dict) -> None:
    storage_file.write_text(json.dumps(document), encoding="utf-8")


def test_load_returns_the_defaults_when_the_file_is_missing(tmp_path):
    assert build_repository(tmp_path / "settings.json").load() == DEFAULT_SETTINGS


def test_saved_settings_are_loaded_back_equal(tmp_path):
    repository = build_repository(tmp_path / "settings.json")

    repository.save(CUSTOM_SETTINGS)

    assert repository.load() == CUSTOM_SETTINGS


def test_save_writes_the_documented_json_shape(tmp_path):
    storage_file = tmp_path / "settings.json"

    build_repository(storage_file).save(CUSTOM_SETTINGS)

    assert json.loads(storage_file.read_text(encoding="utf-8")) == {
        "output_folder": "/Volumes/Archive/Digitalização",
        "output_format": "jpg",
        "scan_preset": "photo",
    }


def test_save_creates_the_missing_data_folder(tmp_path):
    storage_file = tmp_path / "Application Support" / "Digitalizadora" / "settings.json"

    build_repository(storage_file).save(CUSTOM_SETTINGS)

    assert storage_file.exists()


def test_save_replaces_the_previous_settings(tmp_path):
    repository = build_repository(tmp_path / "settings.json")
    repository.save(CUSTOM_SETTINGS)

    repository.save(DEFAULT_SETTINGS)

    assert repository.load() == DEFAULT_SETTINGS


VALID_DOCUMENT = {"output_folder": "/Volumes/Archive", "output_format": "jpg", "scan_preset": "photo"}
UNUSABLE_DOCUMENTS = [
    {**VALID_DOCUMENT, "output_format": "tiff"},
    {**VALID_DOCUMENT, "scan_preset": "poster"},
    {**VALID_DOCUMENT, "output_folder": "relative/folder"},
    {**VALID_DOCUMENT, "output_folder": "~/Pictures"},
    {**VALID_DOCUMENT, "output_folder": ""},
    {**VALID_DOCUMENT, "output_folder": 123},
    {"output_format": "jpg", "scan_preset": "photo"},
    {"output_folder": "/Volumes/Archive", "scan_preset": "photo"},
    {"output_folder": "/Volumes/Archive", "output_format": "jpg"},
]


@pytest.mark.parametrize("unusable_document", UNUSABLE_DOCUMENTS)
def test_load_returns_the_whole_default_when_one_field_is_unusable(tmp_path, unusable_document):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, unusable_document)

    assert build_repository(storage_file).load() == DEFAULT_SETTINGS


@pytest.mark.parametrize("unusable_text", ["", "{not json", "[]", "null", '"text"'])
def test_load_returns_the_defaults_for_a_corrupt_file(tmp_path, unusable_text):
    storage_file = tmp_path / "settings.json"
    storage_file.write_text(unusable_text, encoding="utf-8")

    assert build_repository(storage_file).load() == DEFAULT_SETTINGS


def test_load_returns_the_defaults_for_a_file_that_is_not_text(tmp_path):
    storage_file = tmp_path / "settings.json"
    storage_file.write_bytes(b"\xff\xfe\x00\x80")

    assert build_repository(storage_file).load() == DEFAULT_SETTINGS


def test_valid_document_is_loaded_as_written_by_hand(tmp_path):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, VALID_DOCUMENT)

    assert build_repository(storage_file).load() == ApplicationSettings(
        Path("/Volumes/Archive"), OutputFormat.JPEG, ScanPreset.PHOTO
    )


def test_unusable_file_is_reported_with_a_warning(tmp_path, caplog):
    storage_file = tmp_path / "settings.json"
    storage_file.write_text("{not json", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        build_repository(storage_file).load()

    assert [record.levelno for record in caplog.records] == [logging.WARNING]


def test_missing_file_is_not_reported_as_a_problem(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        build_repository(tmp_path / "settings.json").load()

    assert caplog.records == []
```

- [ ] **Passo 22: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/repositories/test_json_application_settings_repository.py -v`
Expected: erro de coleta `ModuleNotFoundError: No module named 'digitalizadora.repositories.json_application_settings_repository'`.

- [ ] **Passo 23: Implementar**

Criar `src/digitalizadora/repositories/json_application_settings_repository.py`:

```python
import json
import logging
from pathlib import Path

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter

LOGGER = logging.getLogger(__name__)


def parse_application_settings(document: object) -> ApplicationSettings:
    if not isinstance(document, dict):
        raise ValueError("The settings document must be a JSON object")
    output_folder_text = document["output_folder"]
    if not isinstance(output_folder_text, str):
        raise ValueError("The output folder must be text")
    output_folder = Path(output_folder_text)
    if not output_folder.is_absolute():
        raise ValueError("The output folder must be an absolute path")
    return ApplicationSettings(
        output_folder=output_folder,
        output_format=OutputFormat(document["output_format"]),
        scan_preset=ScanPreset(document["scan_preset"]),
    )


class JsonApplicationSettingsRepository:
    def __init__(
        self,
        storage_file: Path,
        default_settings: ApplicationSettings,
        file_writer: AtomicFileWriter,
    ) -> None:
        self._storage_file = storage_file
        self._default_settings = default_settings
        self._file_writer = file_writer

    def load(self) -> ApplicationSettings:
        try:
            document = json.loads(self._storage_file.read_text(encoding="utf-8"))
            return parse_application_settings(document)
        except FileNotFoundError:
            return self._default_settings
        except (OSError, ValueError, KeyError) as error:
            LOGGER.warning("Using the default settings because %s is unusable: %r", self._storage_file, error)
            return self._default_settings

    def save(self, settings: ApplicationSettings) -> None:
        document = {
            "output_folder": str(settings.output_folder),
            "output_format": settings.output_format.value,
            "scan_preset": settings.scan_preset.value,
        }
        self._storage_file.parent.mkdir(parents=True, exist_ok=True)
        encoded_document = json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8")
        self._file_writer.replace_file(self._storage_file, encoded_document)
```

- [ ] **Passo 24: Rodar os testes da tarefa e ver passar**

Run: `.venv/bin/pytest tests/repositories -v`
Expected: `84 passed` (20 do escritor atômico, 2 do dublê, 19 do repositório de saída, 20 do endpoint e 23 dos ajustes), cada teste abaixo de 100 ms. Como root o teste da pasta somente leitura é pulado (`83 passed, 1 skipped`).

- [ ] **Passo 25: Commit**

```bash
git add src/digitalizadora/repositories/atomic_file_writer.py src/digitalizadora/repositories/file_system_scan_output_repository.py src/digitalizadora/repositories/json_scanner_endpoint_repository.py src/digitalizadora/repositories/json_application_settings_repository.py tests/fakes/in_memory_settings_repository.py tests/repositories/test_atomic_file_writer.py tests/repositories/test_file_system_scan_output_repository.py tests/repositories/test_json_scanner_endpoint_repository.py tests/repositories/test_json_application_settings_repository.py tests/repositories/test_in_memory_application_settings_repository.py
git commit -m "feat: add atomic file writer and the file system and JSON repositories"
```

### Task 8: StorageGuardService e ScanOutputService

**Objetivo:** Recusar uma digitalização quando a pasta de saída não tem espaço para ela e, depois de digitalizar, codificar e gravar o resultado devolvendo o caminho, a miniatura e o tamanho.

**Files:**
- Create: `src/digitalizadora/services/storage_guard_service.py`
- Create: `src/digitalizadora/services/scan_output_service.py`
- Test: `tests/services/test_storage_guard_service.py`
- Test: `tests/services/test_scan_output_service.py`

**Interfaces:**
- Consumes: `digitalizadora.domain.scan_settings.ScanSettings(dots_per_inch, color_mode)`, `digitalizadora.domain.color_mode.ColorMode`, `digitalizadora.domain.errors.InsufficientStorageError`, `digitalizadora.domain.errors.OutputFolderUnavailableError`, `digitalizadora.domain.errors.ScanFailedError`, `digitalizadora.domain.scan_request.ScanRequest(settings, output_format)`, `digitalizadora.domain.scan_job.ScanJob(request, started_at)`, `digitalizadora.domain.scanned_image.ScannedImage`, `digitalizadora.domain.encoded_scan.EncodedScan(content, output_format, created_at, thumbnail_jpeg)`, `digitalizadora.domain.scan_result.ScanResult(output_path, output_format, scanned_at, size_in_bytes)`, `digitalizadora.domain.stored_scan.StoredScan(result, thumbnail_jpeg)`, `digitalizadora.domain.output_format.OutputFormat`, `digitalizadora.domain.ports.ScanOutputRepository`, `digitalizadora.services.scan_encoder.ScanEncoder` (Task 6).
- Produces:
  - `digitalizadora.services.storage_guard_service`: constantes `MINIMUM_FREE_SPACE_BYTES`, `PLATEN_WIDTH_INCHES = 8.5`, `PLATEN_HEIGHT_INCHES = 11.69`, `ESTIMATED_BYTES_PER_PIXEL_COLOR = 0.12`, `ESTIMATED_BYTES_PER_PIXEL_GRAYSCALE = 0.08`, `SAFETY_MARGIN_PAGES = 3`; funções `estimated_page_bytes(settings: ScanSettings) -> int` e `read_free_space_in_bytes(folder: Path) -> int`; classe `StorageGuardService(free_space_reader: Callable[[Path], int] = read_free_space_in_bytes)` com `ensure_space_for_scan(folder: Path, settings: ScanSettings) -> None`, `estimate_pages_remaining(folder: Path, settings: ScanSettings) -> int` e `free_space_in_bytes(folder: Path) -> int`
  - `ScanOutputService(scan_encoder, scan_output_repository, storage_guard_service)` com `ensure_capacity(request: ScanRequest) -> None` e `store(scanned_image: ScannedImage, job: ScanJob) -> StoredScan`

Notas de decisão: a estimativa de uma página usa o vidro inteiro (8,5 x 11,69 pol.) porque na v1 não há recorte; as arestas em pixels são arredondadas para inteiros antes de multiplicar (assim 600 dpi dá exatamente 4 vezes o tamanho de 300 dpi) e os bytes por pixel (0,12 cor, 0,08 cinza) são valores iniciais a recalibrar com as medições do Gate 0. `read_free_space_in_bytes` sobe até a pasta existente mais próxima porque a pasta de saída pode ainda não existir (disco externo, primeira execução).

#### Ciclo 1: ler o espaço livre de uma pasta que talvez não exista

- [ ] **Passo 1: Escrever o teste que falha**

Criar `tests/services/test_storage_guard_service.py`:

```python
from pathlib import Path

from digitalizadora.services.storage_guard_service import read_free_space_in_bytes

BYTES_PER_MEBIBYTE = 1024 * 1024
FREE_SPACE_TOLERANCE_BYTES = BYTES_PER_MEBIBYTE


def test_free_space_of_an_existing_folder_is_a_positive_integer(tmp_path):
    free_space = read_free_space_in_bytes(tmp_path)

    assert isinstance(free_space, int)
    assert free_space > 0


def test_missing_subfolder_reports_the_space_of_its_nearest_existing_parent(tmp_path):
    expected_free_space = read_free_space_in_bytes(tmp_path)

    free_space = read_free_space_in_bytes(tmp_path / "not-yet-created")

    assert abs(free_space - expected_free_space) <= FREE_SPACE_TOLERANCE_BYTES


def test_several_missing_levels_report_the_space_of_the_nearest_existing_parent(tmp_path):
    expected_free_space = read_free_space_in_bytes(tmp_path)

    free_space = read_free_space_in_bytes(tmp_path / "external disk" / "scans" / "2026")

    assert abs(free_space - expected_free_space) <= FREE_SPACE_TOLERANCE_BYTES


def test_relative_path_that_does_not_exist_reports_the_space_of_the_current_folder():
    assert read_free_space_in_bytes(Path("a-folder-that-does-not-exist")) > 0
```

- [ ] **Passo 2: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/services/test_storage_guard_service.py -v`
Expected: erro de coleta `ModuleNotFoundError: No module named 'digitalizadora.services.storage_guard_service'`.

- [ ] **Passo 3: Implementar o mínimo**

Criar `src/digitalizadora/services/storage_guard_service.py`:

```python
import shutil
from pathlib import Path


def read_free_space_in_bytes(folder: Path) -> int:
    nearest_existing_folder = folder
    while not nearest_existing_folder.exists():
        nearest_existing_folder = nearest_existing_folder.parent
    return shutil.disk_usage(nearest_existing_folder).free
```

- [ ] **Passo 4: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/services/test_storage_guard_service.py -v`
Expected: `4 passed`

#### Ciclo 2: estimativa de uma página e recusa por falta de espaço

- [ ] **Passo 5: Escrever os testes que falham**

Em `tests/services/test_storage_guard_service.py`, trocar:

```python
from pathlib import Path

from digitalizadora.services.storage_guard_service import read_free_space_in_bytes
```

por:

```python
from pathlib import Path

import pytest

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import InsufficientStorageError
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.services.storage_guard_service import (
    MINIMUM_FREE_SPACE_BYTES,
    SAFETY_MARGIN_PAGES,
    StorageGuardService,
    estimated_page_bytes,
    read_free_space_in_bytes,
)
```

Acrescentar ao final de `tests/services/test_storage_guard_service.py`:

```python
OUTPUT_FOLDER = Path("/Volumes/Archive/Scans")
COLOR_AT_300 = ScanSettings(300, ColorMode.COLOR)
GRAYSCALE_AT_300 = ScanSettings(300, ColorMode.GRAYSCALE)
GRAYSCALE_AT_200 = ScanSettings(200, ColorMode.GRAYSCALE)
COLOR_AT_600 = ScanSettings(600, ColorMode.COLOR)


class RecordingFreeSpaceReader:
    def __init__(self, free_space_in_bytes: int) -> None:
        self._free_space_in_bytes = free_space_in_bytes
        self.requested_folders: list[Path] = []

    def __call__(self, folder: Path) -> int:
        self.requested_folders.append(folder)
        return self._free_space_in_bytes


def build_guard(free_space_in_bytes: int) -> StorageGuardService:
    return StorageGuardService(RecordingFreeSpaceReader(free_space_in_bytes))


def required_free_space(settings: ScanSettings) -> int:
    return MINIMUM_FREE_SPACE_BYTES + SAFETY_MARGIN_PAGES * estimated_page_bytes(settings)


def test_color_page_at_300_dots_per_inch_is_estimated_at_the_documented_size():
    assert estimated_page_bytes(COLOR_AT_300) == 1_073_142


def test_grayscale_page_at_200_dots_per_inch_is_estimated_at_the_documented_size():
    assert estimated_page_bytes(GRAYSCALE_AT_200) == 317_968


def test_grayscale_page_is_smaller_than_a_color_page_of_the_same_resolution():
    assert estimated_page_bytes(GRAYSCALE_AT_300) < estimated_page_bytes(COLOR_AT_300)


def test_page_at_600_dots_per_inch_is_four_times_the_page_at_300():
    assert estimated_page_bytes(COLOR_AT_600) == 4 * estimated_page_bytes(COLOR_AT_300)


def test_free_space_exactly_at_the_required_amount_is_accepted():
    build_guard(required_free_space(COLOR_AT_300)).ensure_space_for_scan(OUTPUT_FOLDER, COLOR_AT_300)


def test_free_space_one_byte_above_the_required_amount_is_accepted():
    build_guard(required_free_space(COLOR_AT_300) + 1).ensure_space_for_scan(OUTPUT_FOLDER, COLOR_AT_300)


def test_free_space_one_byte_below_the_required_amount_is_refused():
    guard = build_guard(required_free_space(COLOR_AT_300) - 1)

    with pytest.raises(InsufficientStorageError):
        guard.ensure_space_for_scan(OUTPUT_FOLDER, COLOR_AT_300)


def test_empty_disk_is_refused():
    with pytest.raises(InsufficientStorageError):
        build_guard(0).ensure_space_for_scan(OUTPUT_FOLDER, COLOR_AT_300)


def test_space_that_fits_a_300_dots_per_inch_scan_may_not_fit_a_600_dots_per_inch_scan():
    guard = build_guard(required_free_space(COLOR_AT_300))

    guard.ensure_space_for_scan(OUTPUT_FOLDER, COLOR_AT_300)
    with pytest.raises(InsufficientStorageError):
        guard.ensure_space_for_scan(OUTPUT_FOLDER, COLOR_AT_600)


def test_refusal_asks_the_reader_about_the_given_folder():
    reader = RecordingFreeSpaceReader(required_free_space(COLOR_AT_300))

    StorageGuardService(reader).ensure_space_for_scan(OUTPUT_FOLDER, COLOR_AT_300)

    assert reader.requested_folders == [OUTPUT_FOLDER]
```

- [ ] **Passo 6: Rodar os testes e ver falhar**

Run: `.venv/bin/pytest tests/services/test_storage_guard_service.py -v`
Expected: erro de coleta `ImportError: cannot import name 'MINIMUM_FREE_SPACE_BYTES' from 'digitalizadora.services.storage_guard_service'`.

- [ ] **Passo 7: Implementar**

Substituir `src/digitalizadora/services/storage_guard_service.py` (arquivo inteiro):

```python
import shutil
from collections.abc import Callable
from pathlib import Path

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import InsufficientStorageError
from digitalizadora.domain.scan_settings import ScanSettings

BYTES_PER_KIBIBYTE = 1024
MINIMUM_FREE_SPACE_BYTES = BYTES_PER_KIBIBYTE**3
PLATEN_WIDTH_INCHES = 8.5
PLATEN_HEIGHT_INCHES = 11.69
ESTIMATED_BYTES_PER_PIXEL_COLOR = 0.12
ESTIMATED_BYTES_PER_PIXEL_GRAYSCALE = 0.08
SAFETY_MARGIN_PAGES = 3

ESTIMATED_BYTES_PER_PIXEL = {
    ColorMode.COLOR: ESTIMATED_BYTES_PER_PIXEL_COLOR,
    ColorMode.GRAYSCALE: ESTIMATED_BYTES_PER_PIXEL_GRAYSCALE,
}


def estimated_page_bytes(settings: ScanSettings) -> int:
    pixels_wide = round(PLATEN_WIDTH_INCHES * settings.dots_per_inch)
    pixels_high = round(PLATEN_HEIGHT_INCHES * settings.dots_per_inch)
    return round(pixels_wide * pixels_high * ESTIMATED_BYTES_PER_PIXEL[settings.color_mode])


def read_free_space_in_bytes(folder: Path) -> int:
    nearest_existing_folder = folder
    while not nearest_existing_folder.exists():
        nearest_existing_folder = nearest_existing_folder.parent
    return shutil.disk_usage(nearest_existing_folder).free


class StorageGuardService:
    def __init__(self, free_space_reader: Callable[[Path], int] = read_free_space_in_bytes) -> None:
        self._free_space_reader = free_space_reader

    def ensure_space_for_scan(self, folder: Path, settings: ScanSettings) -> None:
        free_space = self._free_space_reader(folder)
        required_space = MINIMUM_FREE_SPACE_BYTES + SAFETY_MARGIN_PAGES * estimated_page_bytes(settings)
        if free_space < required_space:
            raise InsufficientStorageError(
                f"Only {free_space} bytes are free in {folder}; {required_space} bytes are required"
            )
```

- [ ] **Passo 8: Rodar os testes e ver passar**

Run: `.venv/bin/pytest tests/services/test_storage_guard_service.py -v`
Expected: `14 passed`

#### Ciclo 3: páginas restantes e espaço livre para a interface

- [ ] **Passo 9: Escrever os testes que falham**

Acrescentar ao final de `tests/services/test_storage_guard_service.py`:

```python
def test_no_pages_remain_when_free_space_equals_the_minimum():
    assert build_guard(MINIMUM_FREE_SPACE_BYTES).estimate_pages_remaining(OUTPUT_FOLDER, COLOR_AT_300) == 0


@pytest.mark.parametrize("free_space_in_bytes", [0, MINIMUM_FREE_SPACE_BYTES - 1])
def test_no_pages_remain_when_free_space_is_below_the_minimum(free_space_in_bytes):
    guard = build_guard(free_space_in_bytes)

    assert guard.estimate_pages_remaining(OUTPUT_FOLDER, COLOR_AT_300) == 0


def test_one_page_remains_when_free_space_exceeds_the_minimum_by_exactly_one_page():
    free_space = MINIMUM_FREE_SPACE_BYTES + estimated_page_bytes(COLOR_AT_300)

    assert build_guard(free_space).estimate_pages_remaining(OUTPUT_FOLDER, COLOR_AT_300) == 1


def test_no_page_remains_when_free_space_is_one_byte_short_of_one_page():
    free_space = MINIMUM_FREE_SPACE_BYTES + estimated_page_bytes(COLOR_AT_300) - 1

    assert build_guard(free_space).estimate_pages_remaining(OUTPUT_FOLDER, COLOR_AT_300) == 0


def test_partial_pages_are_rounded_down():
    free_space = MINIMUM_FREE_SPACE_BYTES + 2 * estimated_page_bytes(COLOR_AT_300) + 1

    assert build_guard(free_space).estimate_pages_remaining(OUTPUT_FOLDER, COLOR_AT_300) == 2


def test_grayscale_fits_more_pages_than_color_in_the_same_space():
    guard = build_guard(MINIMUM_FREE_SPACE_BYTES + 100 * estimated_page_bytes(COLOR_AT_300))

    assert guard.estimate_pages_remaining(OUTPUT_FOLDER, GRAYSCALE_AT_300) > guard.estimate_pages_remaining(
        OUTPUT_FOLDER, COLOR_AT_300
    )


def test_free_space_in_bytes_reports_what_the_reader_returns():
    reader = RecordingFreeSpaceReader(123_456)

    assert StorageGuardService(reader).free_space_in_bytes(OUTPUT_FOLDER) == 123_456
    assert reader.requested_folders == [OUTPUT_FOLDER]


def test_default_reader_reads_the_real_disk(tmp_path):
    assert StorageGuardService().free_space_in_bytes(tmp_path / "not-yet-created") > 0
```

- [ ] **Passo 10: Rodar os testes e ver falhar**

Run: `.venv/bin/pytest tests/services/test_storage_guard_service.py -v`
Expected: `14 passed, 9 failed`. Os 14 testes anteriores passam; os 9 novos (contando os dois casos parametrizados) falham com `AttributeError: 'StorageGuardService' object has no attribute 'estimate_pages_remaining'` ou `... 'free_space_in_bytes'`.

- [ ] **Passo 11: Implementar**

Substituir `src/digitalizadora/services/storage_guard_service.py` (arquivo inteiro):

```python
import shutil
from collections.abc import Callable
from pathlib import Path

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import InsufficientStorageError
from digitalizadora.domain.scan_settings import ScanSettings

BYTES_PER_KIBIBYTE = 1024
MINIMUM_FREE_SPACE_BYTES = BYTES_PER_KIBIBYTE**3
PLATEN_WIDTH_INCHES = 8.5
PLATEN_HEIGHT_INCHES = 11.69
ESTIMATED_BYTES_PER_PIXEL_COLOR = 0.12
ESTIMATED_BYTES_PER_PIXEL_GRAYSCALE = 0.08
SAFETY_MARGIN_PAGES = 3

ESTIMATED_BYTES_PER_PIXEL = {
    ColorMode.COLOR: ESTIMATED_BYTES_PER_PIXEL_COLOR,
    ColorMode.GRAYSCALE: ESTIMATED_BYTES_PER_PIXEL_GRAYSCALE,
}


def estimated_page_bytes(settings: ScanSettings) -> int:
    pixels_wide = round(PLATEN_WIDTH_INCHES * settings.dots_per_inch)
    pixels_high = round(PLATEN_HEIGHT_INCHES * settings.dots_per_inch)
    return round(pixels_wide * pixels_high * ESTIMATED_BYTES_PER_PIXEL[settings.color_mode])


def read_free_space_in_bytes(folder: Path) -> int:
    nearest_existing_folder = folder
    while not nearest_existing_folder.exists():
        nearest_existing_folder = nearest_existing_folder.parent
    return shutil.disk_usage(nearest_existing_folder).free


class StorageGuardService:
    def __init__(self, free_space_reader: Callable[[Path], int] = read_free_space_in_bytes) -> None:
        self._free_space_reader = free_space_reader

    def ensure_space_for_scan(self, folder: Path, settings: ScanSettings) -> None:
        free_space = self._free_space_reader(folder)
        required_space = MINIMUM_FREE_SPACE_BYTES + SAFETY_MARGIN_PAGES * estimated_page_bytes(settings)
        if free_space < required_space:
            raise InsufficientStorageError(
                f"Only {free_space} bytes are free in {folder}; {required_space} bytes are required"
            )

    def estimate_pages_remaining(self, folder: Path, settings: ScanSettings) -> int:
        usable_space = self._free_space_reader(folder) - MINIMUM_FREE_SPACE_BYTES
        return max(0, usable_space // estimated_page_bytes(settings))

    def free_space_in_bytes(self, folder: Path) -> int:
        return self._free_space_reader(folder)
```

- [ ] **Passo 12: Rodar os testes e ver passar**

Run: `.venv/bin/pytest tests/services/test_storage_guard_service.py -v`
Expected: `23 passed`

#### Ciclo 4: ScanOutputService, verificação de capacidade

- [ ] **Passo 13: Escrever os testes que falham**

Criar `tests/services/test_scan_output_service.py`:

```python
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.encoded_scan import EncodedScan
from digitalizadora.domain.errors import InsufficientStorageError, OutputFolderUnavailableError, ScanFailedError
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_job import ScanJob
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.domain.stored_scan import StoredScan
from digitalizadora.services.scan_output_service import ScanOutputService
from digitalizadora.services.storage_guard_service import (
    MINIMUM_FREE_SPACE_BYTES,
    SAFETY_MARGIN_PAGES,
    StorageGuardService,
    estimated_page_bytes,
)

OUTPUT_FOLDER = Path("/Volumes/Archive/Scans")
SAVED_PATH = OUTPUT_FOLDER / "2026-10-13_00001.pdf"
STARTED_AT = datetime(2026, 10, 13, 15, 30, 12, tzinfo=timezone(timedelta(hours=-3)))
SETTINGS = ScanSettings(300, ColorMode.COLOR)
REQUEST = ScanRequest(SETTINGS, OutputFormat.PDF)
JOB = ScanJob(REQUEST, STARTED_AT)
SCANNED_IMAGE = ScannedImage(b"scanned jpeg", "image/jpeg")
ENCODED_SCAN = EncodedScan(
    content=b"final pdf content",
    output_format=OutputFormat.PDF,
    created_at=STARTED_AT,
    thumbnail_jpeg=b"thumbnail jpeg",
)
ENOUGH_FREE_SPACE = MINIMUM_FREE_SPACE_BYTES + SAFETY_MARGIN_PAGES * estimated_page_bytes(SETTINGS)


class RecordingFreeSpaceReader:
    def __init__(self, free_space_in_bytes: int) -> None:
        self._free_space_in_bytes = free_space_in_bytes
        self.requested_folders: list[Path] = []

    def __call__(self, folder: Path) -> int:
        self.requested_folders.append(folder)
        return self._free_space_in_bytes


class RecordingScanOutputRepository:
    def __init__(self) -> None:
        self.saved_scans: list[EncodedScan] = []

    def output_folder(self) -> Path:
        return OUTPUT_FOLDER

    def save(self, encoded_scan: EncodedScan) -> Path:
        self.saved_scans.append(encoded_scan)
        return SAVED_PATH


class FailingScanOutputRepository:
    def output_folder(self) -> Path:
        return OUTPUT_FOLDER

    def save(self, encoded_scan: EncodedScan) -> Path:
        raise OutputFolderUnavailableError("The external disk was disconnected")


class StubScanEncoder:
    def __init__(self) -> None:
        self.encoded_requests: list[tuple[ScannedImage, ScanJob]] = []

    def encode(self, scanned_image: ScannedImage, job: ScanJob) -> EncodedScan:
        self.encoded_requests.append((scanned_image, job))
        return ENCODED_SCAN


class FailingScanEncoder:
    def encode(self, scanned_image: ScannedImage, job: ScanJob) -> EncodedScan:
        raise ScanFailedError("The scanner returned an unexpected image")


def build_service(
    scan_encoder, scan_output_repository, free_space_reader: RecordingFreeSpaceReader
) -> ScanOutputService:
    return ScanOutputService(scan_encoder, scan_output_repository, StorageGuardService(free_space_reader))


def test_capacity_check_asks_about_the_folder_of_the_repository():
    reader = RecordingFreeSpaceReader(ENOUGH_FREE_SPACE)
    service = build_service(StubScanEncoder(), RecordingScanOutputRepository(), reader)

    service.ensure_capacity(REQUEST)

    assert reader.requested_folders == [OUTPUT_FOLDER]


def test_capacity_check_passes_with_exactly_the_required_space():
    reader = RecordingFreeSpaceReader(ENOUGH_FREE_SPACE)

    build_service(StubScanEncoder(), RecordingScanOutputRepository(), reader).ensure_capacity(REQUEST)


def test_capacity_check_refuses_one_byte_less_than_the_required_space():
    reader = RecordingFreeSpaceReader(ENOUGH_FREE_SPACE - 1)
    service = build_service(StubScanEncoder(), RecordingScanOutputRepository(), reader)

    with pytest.raises(InsufficientStorageError):
        service.ensure_capacity(REQUEST)
```

- [ ] **Passo 14: Rodar os testes e ver falhar**

Run: `.venv/bin/pytest tests/services/test_scan_output_service.py -v`
Expected: erro de coleta `ModuleNotFoundError: No module named 'digitalizadora.services.scan_output_service'`.

- [ ] **Passo 15: Implementar o mínimo**

Criar `src/digitalizadora/services/scan_output_service.py`:

```python
from digitalizadora.domain.ports import ScanOutputRepository
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.services.scan_encoder import ScanEncoder
from digitalizadora.services.storage_guard_service import StorageGuardService


class ScanOutputService:
    def __init__(
        self,
        scan_encoder: ScanEncoder,
        scan_output_repository: ScanOutputRepository,
        storage_guard_service: StorageGuardService,
    ) -> None:
        self._scan_encoder = scan_encoder
        self._scan_output_repository = scan_output_repository
        self._storage_guard_service = storage_guard_service

    def ensure_capacity(self, request: ScanRequest) -> None:
        self._storage_guard_service.ensure_space_for_scan(
            self._scan_output_repository.output_folder(), request.settings
        )
```

- [ ] **Passo 16: Rodar os testes e ver passar**

Run: `.venv/bin/pytest tests/services/test_scan_output_service.py -v`
Expected: `3 passed`

#### Ciclo 5: ScanOutputService, codificar e gravar

- [ ] **Passo 17: Escrever os testes que falham**

Acrescentar ao final de `tests/services/test_scan_output_service.py`:

```python
def test_store_gives_the_scanned_image_and_the_job_to_the_encoder():
    scan_encoder = StubScanEncoder()
    service = build_service(scan_encoder, RecordingScanOutputRepository(), RecordingFreeSpaceReader(0))

    service.store(SCANNED_IMAGE, JOB)

    assert scan_encoder.encoded_requests == [(SCANNED_IMAGE, JOB)]


def test_store_saves_the_encoded_scan_in_the_repository():
    repository = RecordingScanOutputRepository()
    service = build_service(StubScanEncoder(), repository, RecordingFreeSpaceReader(0))

    service.store(SCANNED_IMAGE, JOB)

    assert repository.saved_scans == [ENCODED_SCAN]


def test_store_describes_the_saved_file_in_the_result():
    service = build_service(StubScanEncoder(), RecordingScanOutputRepository(), RecordingFreeSpaceReader(0))

    stored_scan = service.store(SCANNED_IMAGE, JOB)

    assert stored_scan.result == ScanResult(
        output_path=SAVED_PATH,
        output_format=OutputFormat.PDF,
        scanned_at=STARTED_AT,
        size_in_bytes=len(b"final pdf content"),
    )


def test_store_returns_the_thumbnail_of_the_encoded_scan():
    service = build_service(StubScanEncoder(), RecordingScanOutputRepository(), RecordingFreeSpaceReader(0))

    stored_scan = service.store(SCANNED_IMAGE, JOB)

    assert isinstance(stored_scan, StoredScan)
    assert stored_scan.thumbnail_jpeg == b"thumbnail jpeg"


def test_encoder_error_propagates_and_nothing_is_saved():
    repository = RecordingScanOutputRepository()
    service = build_service(FailingScanEncoder(), repository, RecordingFreeSpaceReader(0))

    with pytest.raises(ScanFailedError):
        service.store(SCANNED_IMAGE, JOB)

    assert repository.saved_scans == []


def test_repository_error_propagates():
    service = build_service(StubScanEncoder(), FailingScanOutputRepository(), RecordingFreeSpaceReader(0))

    with pytest.raises(OutputFolderUnavailableError):
        service.store(SCANNED_IMAGE, JOB)
```

- [ ] **Passo 18: Rodar os testes e ver falhar**

Run: `.venv/bin/pytest tests/services/test_scan_output_service.py -v`
Expected: `3 passed, 6 failed`. Os 6 testes novos falham com `AttributeError: 'ScanOutputService' object has no attribute 'store'`.

- [ ] **Passo 19: Implementar**

Substituir `src/digitalizadora/services/scan_output_service.py` (arquivo inteiro):

```python
from digitalizadora.domain.ports import ScanOutputRepository
from digitalizadora.domain.scan_job import ScanJob
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.domain.stored_scan import StoredScan
from digitalizadora.services.scan_encoder import ScanEncoder
from digitalizadora.services.storage_guard_service import StorageGuardService


class ScanOutputService:
    def __init__(
        self,
        scan_encoder: ScanEncoder,
        scan_output_repository: ScanOutputRepository,
        storage_guard_service: StorageGuardService,
    ) -> None:
        self._scan_encoder = scan_encoder
        self._scan_output_repository = scan_output_repository
        self._storage_guard_service = storage_guard_service

    def ensure_capacity(self, request: ScanRequest) -> None:
        self._storage_guard_service.ensure_space_for_scan(
            self._scan_output_repository.output_folder(), request.settings
        )

    def store(self, scanned_image: ScannedImage, job: ScanJob) -> StoredScan:
        encoded_scan = self._scan_encoder.encode(scanned_image, job)
        output_path = self._scan_output_repository.save(encoded_scan)
        result = ScanResult(
            output_path=output_path,
            output_format=encoded_scan.output_format,
            scanned_at=encoded_scan.created_at,
            size_in_bytes=len(encoded_scan.content),
        )
        return StoredScan(result, encoded_scan.thumbnail_jpeg)
```

- [ ] **Passo 20: Rodar os testes da tarefa e ver passar**

Run: `.venv/bin/pytest tests/services/test_storage_guard_service.py tests/services/test_scan_output_service.py -v`
Expected: `32 passed` (23 da guarda de espaço e 9 do serviço de saída), cada teste abaixo de 100 ms.

- [ ] **Passo 21: Commit**

```bash
git add src/digitalizadora/services/storage_guard_service.py src/digitalizadora/services/scan_output_service.py tests/services/test_storage_guard_service.py tests/services/test_scan_output_service.py
git commit -m "feat: add the storage guard and the scan output service"
```

### Task 9: Descoberta Bonjour e PrinterConnectionService

**Objetivo:** Descobrir a impressora pela rede (Bonjour, `_uscan._tcp`) sem acoplar os serviços ao `zeroconf` e entregar, pelo `PrinterConnectionService`, um gateway já verificado, com endereço salvo, nova busca e endereço manual.

**Files:**
- Create: `src/digitalizadora/infrastructure/bonjour_scanner_discovery.py`
- Create: `src/digitalizadora/infrastructure/zeroconf_service_record_source.py`
- Create: `src/digitalizadora/services/printer_connection_service.py`
- Test: `tests/infrastructure/test_bonjour_scanner_discovery.py`
- Test: `tests/infrastructure/test_zeroconf_service_record_source.py`
- Test: `tests/services/test_printer_connection_service.py`

**Interfaces:**
- Consumes:
  - Task 1: pacotes `digitalizadora.infrastructure`, `digitalizadora.services`, `tests.infrastructure`, `tests.services` e a dependência `zeroconf>=0.151` instalada no `.venv`.
  - Task 2: `ScannerEndpoint(base_address, display_name, universally_unique_identifier=None)`, `ScannerState`, `ScannerStatus`, `ScannerUnreachableError`, `LocalNetworkBlockedError` e as portas `ScannerDiscovery`, `ScannerEndpointRepository`, `ScannerGateway` de `digitalizadora.domain.ports`.
- Produces:
  - `ServiceRecord(instance_name, address, port, properties)`, `ServiceRecordSource` (Protocol com `async collect_records(timeout_seconds: float) -> list[ServiceRecord]`), `build_scanner_endpoint(record) -> ScannerEndpoint` e `BonjourScannerDiscovery(record_source)` com `async discover(timeout_seconds) -> list[ScannerEndpoint]`, em `digitalizadora.infrastructure.bonjour_scanner_discovery`.
  - `ZeroconfServiceRecordSource()` (o parâmetro `sleep` é opcional e existe só para respeitar a regra de espera injetada) em `digitalizadora.infrastructure.zeroconf_service_record_source`, mais as funções puras `decode_txt_properties` e `extract_instance_name`.
  - `PrinterConnectionState(connected, display_name, scanner_state, error_code)`, `DISCOVERY_TIMEOUT_SECONDS = 5.0` e `PrinterConnectionService(discovery, endpoint_repository, gateway_factory)` com `acquire_gateway()`, `check_connection()`, `refresh()` e `use_manual_address(base_address)`, em `digitalizadora.services.printer_connection_service` (implementa `ScannerGatewayProvider`).

**Notas da tarefa**
- API do `python-zeroconf` verificada nos arquivos-fonte oficiais (`src/zeroconf/asyncio.py`, `_services/info.py`, `_services/browser.py`, `_services/__init__.py`, `_utils/net.py`) e no exemplo `examples/async_browser.py`: `AsyncZeroconf(ip_version=IPVersion.V4Only)`, `AsyncServiceBrowser(zeroconf, type_, handlers=None, listener=None)`, `AsyncServiceBrowser.async_cancel()`, `AsyncZeroconf.async_close()`, `AsyncServiceInfo(type_, name)`, `await AsyncServiceInfo.async_request(zc, timeout_em_milissegundos)`, `ServiceInfo.parsed_addresses(version)`, `ServiceInfo.properties` (`dict[bytes, bytes | None]`).
- `ZeroconfServiceRecordSource` abre sockets multicast reais e **não tem teste de unidade**: ficam testadas apenas as funções puras `decode_txt_properties` e `extract_instance_name` e a forma da assinatura de `collect_records`; o comportamento real é coberto pelo teste de hardware da Task 14.
- O coletor de nomes usa o parâmetro `listener` (métodos `add_service`, `update_service`, `remove_service`, cada um com 3 parâmetros) em vez de `handlers`, cujos callbacks recebem 4 argumentos por palavra-chave; assim a regra de no máximo 3 parâmetros continua valendo.
- O construtor de `ZeroconfServiceRecordSource` aceita `sleep` opcional (padrão `asyncio.sleep`) para obedecer à regra de espera injetada; `ZeroconfServiceRecordSource()` continua válido para o composition root.
- Review Focus: modo 1 (impressora dormindo, offline ou com IP novo): `test_unreachable_stored_endpoint_triggers_discovery`, `test_endpoint_with_the_stored_identifier_is_preferred_after_discovery`, `test_down_status_counts_as_unreachable` e `test_connected_gateway_that_stops_answering_is_replaced_after_discovery`; Rede Local bloqueada: `test_blocked_local_network_error_survives_an_empty_discovery` e `test_check_connection_reports_a_blocked_local_network`.

- [ ] **Passo 1: Escrever o teste que falha** (ciclo 1: Registro Bonjour vira endpoint)

`build_scanner_endpoint` é uma função pura: o endereço-base é `http://<endereço>:<porta>/<rs sem barras>` (padrão `eSCL`, regra 1 do protocolo), o nome de exibição vem da chave TXT `ty` (ou do nome da instância) e o identificador vem de `uuid`, valor vazio contando como ausente.

Crie `tests/infrastructure/test_bonjour_scanner_discovery.py` com o conteúdo:

```python
from collections.abc import Mapping

from digitalizadora.infrastructure.bonjour_scanner_discovery import (
    ServiceRecord,
    build_scanner_endpoint,
)


def build_record(
    instance_name: str = "HP DeskJet 2800 series [000001]",
    address: str = "192.168.0.40",
    properties: Mapping[str, str] | None = None,
) -> ServiceRecord:
    return ServiceRecord(instance_name, address, 8080, properties or {})


def test_endpoint_base_address_combines_address_port_and_resource_path() -> None:
    endpoint = build_scanner_endpoint(build_record(properties={"rs": "eSCL"}))
    assert endpoint.base_address == "http://192.168.0.40:8080/eSCL"


def test_endpoint_uses_the_default_resource_path_when_rs_is_missing() -> None:
    assert build_scanner_endpoint(build_record()).base_address == "http://192.168.0.40:8080/eSCL"


def test_endpoint_uses_the_default_resource_path_when_rs_is_empty() -> None:
    assert build_scanner_endpoint(build_record(properties={"rs": ""})).base_address.endswith("/eSCL")


def test_endpoint_strips_the_slashes_around_the_resource_path() -> None:
    endpoint = build_scanner_endpoint(build_record(properties={"rs": "/eSCL/"}))
    assert endpoint.base_address == "http://192.168.0.40:8080/eSCL"


def test_endpoint_keeps_a_custom_resource_path() -> None:
    endpoint = build_scanner_endpoint(build_record(properties={"rs": "/airscan/escl"}))
    assert endpoint.base_address == "http://192.168.0.40:8080/airscan/escl"


def test_endpoint_display_name_comes_from_the_ty_property() -> None:
    endpoint = build_scanner_endpoint(build_record(properties={"ty": "HP DeskJet 2800 series"}))
    assert endpoint.display_name == "HP DeskJet 2800 series"


def test_endpoint_display_name_falls_back_to_the_instance_name_without_ty() -> None:
    assert build_scanner_endpoint(build_record()).display_name == "HP DeskJet 2800 series [000001]"


def test_endpoint_display_name_falls_back_to_the_instance_name_with_an_empty_ty() -> None:
    endpoint = build_scanner_endpoint(build_record(properties={"ty": ""}))
    assert endpoint.display_name == "HP DeskJet 2800 series [000001]"


def test_endpoint_carries_the_advertised_identifier() -> None:
    endpoint = build_scanner_endpoint(build_record(properties={"uuid": "5f6c1c2e"}))
    assert endpoint.universally_unique_identifier == "5f6c1c2e"


def test_endpoint_has_no_identifier_when_none_is_advertised() -> None:
    assert build_scanner_endpoint(build_record()).universally_unique_identifier is None


def test_endpoint_has_no_identifier_when_the_advertised_one_is_empty() -> None:
    endpoint = build_scanner_endpoint(build_record(properties={"uuid": ""}))
    assert endpoint.universally_unique_identifier is None
```

- [ ] **Passo 2: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/infrastructure/test_bonjour_scanner_discovery.py -v`

Expected: o pytest aborta na coleta com `ModuleNotFoundError: No module named 'digitalizadora.infrastructure.bonjour_scanner_discovery'` (resumo: `1 error`).

- [ ] **Passo 3: Implementar o mínimo**

Crie o módulo com `ServiceRecord`, o Protocol `ServiceRecordSource` e `build_scanner_endpoint`.

Crie `src/digitalizadora/infrastructure/bonjour_scanner_discovery.py` com o conteúdo:

```python
"""Turns Bonjour service records into scanner endpoints; no network access in this module."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from digitalizadora.domain.scanner_endpoint import ScannerEndpoint

DEFAULT_RESOURCE_PATH = "eSCL"
RESOURCE_PATH_KEY = "rs"
DISPLAY_NAME_KEY = "ty"
UNIVERSALLY_UNIQUE_IDENTIFIER_KEY = "uuid"


@dataclass(frozen=True)
class ServiceRecord:
    instance_name: str
    address: str
    port: int
    properties: Mapping[str, str]


class ServiceRecordSource(Protocol):
    async def collect_records(self, timeout_seconds: float) -> list[ServiceRecord]: ...


def build_scanner_endpoint(record: ServiceRecord) -> ScannerEndpoint:
    resource_path = record.properties.get(RESOURCE_PATH_KEY, "").strip("/") or DEFAULT_RESOURCE_PATH
    return ScannerEndpoint(
        base_address=f"http://{record.address}:{record.port}/{resource_path}",
        display_name=record.properties.get(DISPLAY_NAME_KEY) or record.instance_name,
        universally_unique_identifier=record.properties.get(UNIVERSALLY_UNIQUE_IDENTIFIER_KEY) or None,
    )
```

- [ ] **Passo 4: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/infrastructure/test_bonjour_scanner_discovery.py -v`

Expected: `11 passed`.

- [ ] **Passo 5: Escrever o teste que falha** (ciclo 2: BonjourScannerDiscovery.discover)

`discover` pede os registros à fonte, ignora os que não têm endereço, junta duplicatas (pelo identificador, ou pelo endereço-base quando não há identificador) e ordena por nome de exibição sem diferenciar maiúsculas de minúsculas. Os dados chegam por um dublê de `ServiceRecordSource`, sem rede.

Substitua o bloco de importações de `tests/infrastructure/test_bonjour_scanner_discovery.py` (as linhas `import` e `from` do topo do arquivo) por:

```python
from collections.abc import Mapping, Sequence

from digitalizadora.infrastructure.bonjour_scanner_discovery import (
    BonjourScannerDiscovery,
    ServiceRecord,
    build_scanner_endpoint,
)
```

Em `tests/infrastructure/test_bonjour_scanner_discovery.py`, logo depois do bloco de importações, acrescente:

```python
DISCOVERY_TIMEOUT_SECONDS = 5.0
```

Em `tests/infrastructure/test_bonjour_scanner_discovery.py`, logo depois de `build_record`, acrescente:

```python
class StubRecordSource:
    def __init__(self, records: Sequence[ServiceRecord]) -> None:
        self._records = list(records)
        self.requested_timeouts: list[float] = []

    async def collect_records(self, timeout_seconds: float) -> list[ServiceRecord]:
        self.requested_timeouts.append(timeout_seconds)
        return list(self._records)
```

Acrescente ao final de `tests/infrastructure/test_bonjour_scanner_discovery.py`:

```python
async def test_discover_returns_nothing_when_no_record_was_collected() -> None:
    discovery = BonjourScannerDiscovery(StubRecordSource([]))
    assert await discovery.discover(DISCOVERY_TIMEOUT_SECONDS) == []


async def test_discover_converts_a_record_into_an_endpoint() -> None:
    discovery = BonjourScannerDiscovery(StubRecordSource([build_record(properties={"ty": "Scanner"})]))
    endpoints = await discovery.discover(DISCOVERY_TIMEOUT_SECONDS)
    assert [endpoint.display_name for endpoint in endpoints] == ["Scanner"]


async def test_discover_passes_the_timeout_to_the_record_source() -> None:
    record_source = StubRecordSource([])
    await BonjourScannerDiscovery(record_source).discover(DISCOVERY_TIMEOUT_SECONDS)
    assert record_source.requested_timeouts == [DISCOVERY_TIMEOUT_SECONDS]


async def test_discover_merges_records_with_the_same_identifier() -> None:
    records = [
        build_record(address="192.168.0.40", properties={"uuid": "same"}),
        build_record(address="192.168.0.41", properties={"uuid": "same"}),
    ]
    endpoints = await BonjourScannerDiscovery(StubRecordSource(records)).discover(DISCOVERY_TIMEOUT_SECONDS)
    assert [endpoint.base_address for endpoint in endpoints] == ["http://192.168.0.40:8080/eSCL"]


async def test_discover_merges_records_without_identifier_that_share_the_base_address() -> None:
    records = [build_record(), build_record(instance_name="Same printer again")]
    endpoints = await BonjourScannerDiscovery(StubRecordSource(records)).discover(DISCOVERY_TIMEOUT_SECONDS)
    assert len(endpoints) == 1


async def test_discover_keeps_records_with_different_identifiers() -> None:
    records = [
        build_record(address="192.168.0.40", properties={"uuid": "first"}),
        build_record(address="192.168.0.41", properties={"uuid": "second"}),
    ]
    endpoints = await BonjourScannerDiscovery(StubRecordSource(records)).discover(DISCOVERY_TIMEOUT_SECONDS)
    assert len(endpoints) == 2


async def test_discover_sorts_endpoints_by_display_name_ignoring_case() -> None:
    records = [
        build_record(address="192.168.0.42", properties={"ty": "beta"}),
        build_record(address="192.168.0.41", properties={"ty": "Alpha"}),
        build_record(address="192.168.0.43", properties={"ty": "Gamma"}),
    ]
    endpoints = await BonjourScannerDiscovery(StubRecordSource(records)).discover(DISCOVERY_TIMEOUT_SECONDS)
    assert [endpoint.display_name for endpoint in endpoints] == ["Alpha", "beta", "Gamma"]


async def test_discover_ignores_records_with_an_empty_address() -> None:
    records = [build_record(address=""), build_record(address="192.168.0.41", properties={"ty": "Kept"})]
    endpoints = await BonjourScannerDiscovery(StubRecordSource(records)).discover(DISCOVERY_TIMEOUT_SECONDS)
    assert [endpoint.display_name for endpoint in endpoints] == ["Kept"]
```

- [ ] **Passo 6: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/infrastructure/test_bonjour_scanner_discovery.py -v`

Expected: o pytest aborta na coleta com `ImportError: cannot import name 'BonjourScannerDiscovery' from 'digitalizadora.infrastructure.bonjour_scanner_discovery'` (resumo: `1 error`).

- [ ] **Passo 7: Implementar o mínimo**

Acrescente o `logger`, as duas chaves de ordenação e a classe `BonjourScannerDiscovery`.

Substitua o bloco de importações de `src/digitalizadora/infrastructure/bonjour_scanner_discovery.py` (as linhas `import` e `from` do topo do arquivo) por:

```python
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from digitalizadora.domain.scanner_endpoint import ScannerEndpoint
```

Em `src/digitalizadora/infrastructure/bonjour_scanner_discovery.py`, logo depois do bloco de importações, acrescente:

```python
logger = logging.getLogger(__name__)
```

Acrescente ao final de `src/digitalizadora/infrastructure/bonjour_scanner_discovery.py`:

```python
def _deduplication_key(endpoint: ScannerEndpoint) -> str:
    return endpoint.universally_unique_identifier or endpoint.base_address


def _sorting_key(endpoint: ScannerEndpoint) -> str:
    return endpoint.display_name.casefold()


class BonjourScannerDiscovery:
    def __init__(self, record_source: ServiceRecordSource) -> None:
        self._record_source = record_source

    async def discover(self, timeout_seconds: float) -> list[ScannerEndpoint]:
        records = await self._record_source.collect_records(timeout_seconds)
        unique_endpoints: dict[str, ScannerEndpoint] = {}
        for record in records:
            if not record.address:
                logger.debug("Ignoring %s: the service record has no address", record.instance_name)
                continue
            endpoint = build_scanner_endpoint(record)
            unique_endpoints.setdefault(_deduplication_key(endpoint), endpoint)
        return sorted(unique_endpoints.values(), key=_sorting_key)
```

- [ ] **Passo 8: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/infrastructure/test_bonjour_scanner_discovery.py -v`

Expected: `19 passed`.

- [ ] **Passo 9: Escrever o teste que falha** (ciclo 3: Funções puras da fonte zeroconf)

A fonte `zeroconf` usa rede multicast real e **não tem teste de unidade**; só é exercitada pelo teste de hardware da Task 14. Para deixar o mínimo possível sem cobertura, a lógica sem rede fica em duas funções puras testadas aqui: `decode_txt_properties` (chaves TXT em minúsculas, valores em UTF-8 com `errors="replace"`, valor ausente vira texto vazio) e `extract_instance_name` (tira o sufixo `._uscan._tcp.local.`).

Crie `tests/infrastructure/test_zeroconf_service_record_source.py` com o conteúdo:

```python
from digitalizadora.infrastructure.zeroconf_service_record_source import (
    decode_txt_properties,
    extract_instance_name,
)


def test_txt_keys_are_lowercased() -> None:
    assert decode_txt_properties({b"UUID": b"abc", b"rs": b"eSCL"}) == {"uuid": "abc", "rs": "eSCL"}


def test_txt_values_are_decoded_as_utf8() -> None:
    assert decode_txt_properties({b"note": "Sala de estar".encode("utf-8")}) == {"note": "Sala de estar"}


def test_txt_values_with_invalid_bytes_are_replaced_instead_of_failing() -> None:
    assert decode_txt_properties({b"note": b"\xff"}) == {"note": "\ufffd"}


def test_txt_flag_without_value_becomes_an_empty_string() -> None:
    assert decode_txt_properties({b"duplex": None}) == {"duplex": ""}


def test_no_txt_properties_become_an_empty_mapping() -> None:
    assert decode_txt_properties({}) == {}


def test_instance_name_loses_the_service_type_suffix() -> None:
    full_name = "HP DeskJet 2800 series [000001]._uscan._tcp.local."
    assert extract_instance_name(full_name) == "HP DeskJet 2800 series [000001]"


def test_instance_name_without_the_suffix_is_unchanged() -> None:
    assert extract_instance_name("HP DeskJet") == "HP DeskJet"
```

- [ ] **Passo 10: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/infrastructure/test_zeroconf_service_record_source.py -v`

Expected: o pytest aborta na coleta com `ModuleNotFoundError: No module named 'digitalizadora.infrastructure.zeroconf_service_record_source'` (resumo: `1 error`).

- [ ] **Passo 11: Implementar o mínimo**

Crie o módulo com a constante do tipo de serviço e as duas funções.

Crie `src/digitalizadora/infrastructure/zeroconf_service_record_source.py` com o conteúdo:

```python
"""Collects eSCL service records from the local network with python-zeroconf (real multicast)."""

from collections.abc import Mapping

SERVICE_TYPE = "_uscan._tcp.local."


def extract_instance_name(full_service_name: str) -> str:
    return full_service_name.removesuffix(f".{SERVICE_TYPE}")


def decode_txt_properties(raw_properties: Mapping[bytes, bytes | None]) -> dict[str, str]:
    return {
        key.decode("utf-8", errors="replace").lower(): (value or b"").decode("utf-8", errors="replace")
        for key, value in raw_properties.items()
    }
```

- [ ] **Passo 12: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/infrastructure/test_zeroconf_service_record_source.py -v`

Expected: `7 passed`.

- [ ] **Passo 13: Escrever o teste que falha** (ciclo 4: ZeroconfServiceRecordSource (sem rede no teste))

API do `python-zeroconf` conferida na fonte (`zeroconf.asyncio`): `AsyncZeroconf(ip_version=IPVersion.V4Only)`; `AsyncServiceBrowser(async_zeroconf.zeroconf, "_uscan._tcp.local.", listener=...)` (o `listener` precisa de `add_service`, `update_service` e `remove_service`, chamados com `(zeroconf, service_type, name)` no laço de eventos); `AsyncServiceInfo(service_type, name)` com `await async_request(zeroconf, 3000)` (milissegundos, devolve `bool`), `parsed_addresses(IPVersion.V4Only)`, `port` e `properties` (`dict[bytes, bytes | None]`); `await browser.async_cancel()` e `await async_zeroconf.async_close()` ao final. Como a classe abre sockets multicast, o teste só confere que `collect_records` tem a forma do Protocol `ServiceRecordSource` (mesmos parâmetros, corrotina) **sem abrir socket algum**; o comportamento real fica para o teste de hardware da Task 14.

Substitua o bloco de importações de `tests/infrastructure/test_zeroconf_service_record_source.py` (as linhas `import` e `from` do topo do arquivo) por:

```python
import inspect

from digitalizadora.infrastructure.bonjour_scanner_discovery import ServiceRecordSource
from digitalizadora.infrastructure.zeroconf_service_record_source import (
    ZeroconfServiceRecordSource,
    decode_txt_properties,
    extract_instance_name,
)
```

Acrescente ao final de `tests/infrastructure/test_zeroconf_service_record_source.py`:

```python
def test_collect_records_has_the_signature_of_the_service_record_source_protocol() -> None:
    implementation = inspect.signature(ZeroconfServiceRecordSource.collect_records)
    protocol = inspect.signature(ServiceRecordSource.collect_records)
    assert list(implementation.parameters) == list(protocol.parameters)


def test_collect_records_is_a_coroutine_function() -> None:
    assert inspect.iscoroutinefunction(ZeroconfServiceRecordSource.collect_records)
```

- [ ] **Passo 14: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/infrastructure/test_zeroconf_service_record_source.py -v`

Expected: o pytest aborta na coleta com `ImportError: cannot import name 'ZeroconfServiceRecordSource' from 'digitalizadora.infrastructure.zeroconf_service_record_source'` (resumo: `1 error`).

- [ ] **Passo 15: Implementar o mínimo**

Acrescente o `logger`, o tempo de resolução, o coletor de nomes e a classe `ZeroconfServiceRecordSource`.

Substitua o bloco de importações de `src/digitalizadora/infrastructure/zeroconf_service_record_source.py` (as linhas `import` e `from` do topo do arquivo) por:

```python
import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping

from zeroconf import IPVersion, Zeroconf
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo, AsyncZeroconf

from digitalizadora.infrastructure.bonjour_scanner_discovery import ServiceRecord
```

Em `src/digitalizadora/infrastructure/zeroconf_service_record_source.py`, logo depois do bloco de importações, acrescente:

```python
logger = logging.getLogger(__name__)
```

Em `src/digitalizadora/infrastructure/zeroconf_service_record_source.py`, logo depois de `SERVICE_TYPE`, acrescente:

```python
RESOLVE_TIMEOUT_MILLISECONDS = 3000
```

Acrescente ao final de `src/digitalizadora/infrastructure/zeroconf_service_record_source.py`:

```python
class _ServiceNameCollector:
    def __init__(self) -> None:
        self.names: set[str] = set()

    def add_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        self.names.add(name)

    def update_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        self.names.add(name)

    def remove_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        self.names.discard(name)


class ZeroconfServiceRecordSource:
    def __init__(self, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        self._sleep = sleep

    async def collect_records(self, timeout_seconds: float) -> list[ServiceRecord]:
        async_zeroconf = AsyncZeroconf(ip_version=IPVersion.V4Only)
        collector = _ServiceNameCollector()
        browser = AsyncServiceBrowser(async_zeroconf.zeroconf, SERVICE_TYPE, listener=collector)
        try:
            await self._sleep(timeout_seconds)
            resolved = await asyncio.gather(
                *(self._resolve_record(async_zeroconf.zeroconf, name) for name in sorted(collector.names))
            )
        finally:
            await browser.async_cancel()
            await async_zeroconf.async_close()
        return [record for record in resolved if record is not None]

    async def _resolve_record(self, zeroconf: Zeroconf, service_name: str) -> ServiceRecord | None:
        service_info = AsyncServiceInfo(SERVICE_TYPE, service_name)
        if not await service_info.async_request(zeroconf, RESOLVE_TIMEOUT_MILLISECONDS):
            logger.info("Could not resolve %s", service_name)
            return None
        addresses = service_info.parsed_addresses(IPVersion.V4Only)
        if not addresses or not service_info.port:
            logger.info("Ignoring %s: no IPv4 address or port", service_name)
            return None
        return ServiceRecord(
            instance_name=extract_instance_name(service_name),
            address=addresses[0],
            port=service_info.port,
            properties=decode_txt_properties(service_info.properties),
        )
```

- [ ] **Passo 16: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/infrastructure/test_zeroconf_service_record_source.py -v`

Expected: `9 passed`.

- [ ] **Passo 17: Escrever o teste que falha** (ciclo 5: PrinterConnectionService: endereço salvo, descoberta inicial e reaproveitamento)

Os dublês ficam no próprio módulo de teste: `StubScannerGateway` (só `read_status`, com respostas roteirizadas), `RecordingGatewayFactory`, `InMemoryEndpointRepository` e `FakeDiscovery`. Primeiros comportamentos: endereço salvo que responde (estado `IDLE` ou ocupado) devolve o gateway montado por ele e não chama a descoberta; sem endereço salvo a descoberta acontece (prazo `DISCOVERY_TIMEOUT_SECONDS = 5.0`) e o endpoint achado é salvo; o gateway conectado é reaproveitado na chamada seguinte, mas o estado dele é conferido de novo a cada `acquire_gateway`.

Crie `tests/services/test_printer_connection_service.py` com o conteúdo:

```python
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from digitalizadora.domain.scanner_endpoint import ScannerEndpoint
from digitalizadora.domain.scanner_status import ScannerState, ScannerStatus
from digitalizadora.services.printer_connection_service import (
    DISCOVERY_TIMEOUT_SECONDS,
    PrinterConnectionService,
)

STORED_ENDPOINT = ScannerEndpoint("http://192.168.0.40:8080/eSCL", "HP Stored", "uuid-stored")
MOVED_ENDPOINT = ScannerEndpoint("http://192.168.0.77:8080/eSCL", "HP Moved", "uuid-stored")
OTHER_ENDPOINT = ScannerEndpoint("http://192.168.0.90:8080/eSCL", "HP Other", "uuid-other")
IDLE_STATUS = ScannerStatus(ScannerState.IDLE)
PROCESSING_STATUS = ScannerStatus(ScannerState.PROCESSING)


class StubScannerGateway:
    def __init__(self, outcomes: Sequence[ScannerStatus | Exception]) -> None:
        self._outcomes = list(outcomes)
        self.status_reads = 0

    async def read_status(self) -> ScannerStatus:
        self.status_reads += 1
        outcome = self._outcomes.pop(0) if len(self._outcomes) > 1 else self._outcomes[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class RecordingGatewayFactory:
    def __init__(self, gateways_by_base_address: Mapping[str, StubScannerGateway]) -> None:
        self._gateways_by_base_address = gateways_by_base_address
        self.requested_base_addresses: list[str] = []

    def __call__(self, endpoint: ScannerEndpoint) -> StubScannerGateway:
        self.requested_base_addresses.append(endpoint.base_address)
        return self._gateways_by_base_address[endpoint.base_address]


class InMemoryEndpointRepository:
    def __init__(self, stored_endpoint: ScannerEndpoint | None = None) -> None:
        self.stored_endpoint = stored_endpoint
        self.saved_endpoints: list[ScannerEndpoint] = []
        self.clear_count = 0

    def load(self) -> ScannerEndpoint | None:
        return self.stored_endpoint

    def save(self, endpoint: ScannerEndpoint) -> None:
        self.stored_endpoint = endpoint
        self.saved_endpoints.append(endpoint)

    def clear(self) -> None:
        self.stored_endpoint = None
        self.clear_count += 1


class FakeDiscovery:
    def __init__(self, endpoints: Sequence[ScannerEndpoint]) -> None:
        self._endpoints = list(endpoints)
        self.requested_timeouts: list[float] = []

    async def discover(self, timeout_seconds: float) -> list[ScannerEndpoint]:
        self.requested_timeouts.append(timeout_seconds)
        return list(self._endpoints)


@dataclass(frozen=True)
class ServiceHarness:
    service: PrinterConnectionService
    repository: InMemoryEndpointRepository
    discovery: FakeDiscovery
    gateway_factory: RecordingGatewayFactory


def build_harness(
    stored_endpoint: ScannerEndpoint | None,
    discovered_endpoints: Sequence[ScannerEndpoint],
    gateways_by_base_address: Mapping[str, StubScannerGateway],
) -> ServiceHarness:
    repository = InMemoryEndpointRepository(stored_endpoint)
    discovery = FakeDiscovery(discovered_endpoints)
    gateway_factory = RecordingGatewayFactory(gateways_by_base_address)
    service = PrinterConnectionService(discovery, repository, gateway_factory)
    return ServiceHarness(service, repository, discovery, gateway_factory)


async def test_stored_endpoint_that_answers_gives_the_gateway_built_from_it() -> None:
    gateway = StubScannerGateway([IDLE_STATUS])
    harness = build_harness(STORED_ENDPOINT, [], {STORED_ENDPOINT.base_address: gateway})
    assert await harness.service.acquire_gateway() is gateway


async def test_stored_endpoint_that_answers_skips_discovery() -> None:
    harness = build_harness(STORED_ENDPOINT, [], {STORED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS])})
    await harness.service.acquire_gateway()
    assert harness.discovery.requested_timeouts == []


async def test_busy_scanner_still_counts_as_reachable() -> None:
    gateway = StubScannerGateway([PROCESSING_STATUS])
    harness = build_harness(STORED_ENDPOINT, [], {STORED_ENDPOINT.base_address: gateway})
    assert await harness.service.acquire_gateway() is gateway


async def test_connected_gateway_is_reused_while_it_keeps_answering() -> None:
    gateway = StubScannerGateway([IDLE_STATUS])
    harness = build_harness(STORED_ENDPOINT, [], {STORED_ENDPOINT.base_address: gateway})
    await harness.service.acquire_gateway()
    await harness.service.acquire_gateway()
    assert harness.gateway_factory.requested_base_addresses == [STORED_ENDPOINT.base_address]


async def test_reused_gateway_is_checked_again_on_every_acquire() -> None:
    gateway = StubScannerGateway([IDLE_STATUS])
    harness = build_harness(STORED_ENDPOINT, [], {STORED_ENDPOINT.base_address: gateway})
    await harness.service.acquire_gateway()
    await harness.service.acquire_gateway()
    assert gateway.status_reads == 2


async def test_without_a_stored_endpoint_the_discovered_one_is_used() -> None:
    gateway = StubScannerGateway([IDLE_STATUS])
    harness = build_harness(None, [MOVED_ENDPOINT], {MOVED_ENDPOINT.base_address: gateway})
    assert await harness.service.acquire_gateway() is gateway


async def test_without_a_stored_endpoint_the_discovered_one_is_saved() -> None:
    harness = build_harness(None, [MOVED_ENDPOINT], {MOVED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS])})
    await harness.service.acquire_gateway()
    assert harness.repository.saved_endpoints == [MOVED_ENDPOINT]


async def test_discovery_uses_the_five_second_timeout() -> None:
    harness = build_harness(None, [MOVED_ENDPOINT], {MOVED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS])})
    await harness.service.acquire_gateway()
    assert harness.discovery.requested_timeouts == [DISCOVERY_TIMEOUT_SECONDS]
```

- [ ] **Passo 18: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/services/test_printer_connection_service.py -v`

Expected: o pytest aborta na coleta com `ModuleNotFoundError: No module named 'digitalizadora.services.printer_connection_service'` (resumo: `1 error`).

- [ ] **Passo 19: Implementar o mínimo**

Crie o serviço com a conexão verificada e a primeira versão do caminho de conexão (as falhas e a preferência pelo identificador chegam no próximo ciclo).

Crie `src/digitalizadora/services/printer_connection_service.py` com o conteúdo:

```python
"""Finds the scanner on the network and hands out a verified gateway."""

import logging
from collections.abc import Callable
from dataclasses import dataclass

from digitalizadora.domain.ports import ScannerDiscovery, ScannerEndpointRepository, ScannerGateway
from digitalizadora.domain.scanner_endpoint import ScannerEndpoint
from digitalizadora.domain.scanner_status import ScannerStatus

logger = logging.getLogger(__name__)
DISCOVERY_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class _Connection:
    gateway: ScannerGateway
    endpoint: ScannerEndpoint
    status: ScannerStatus


class PrinterConnectionService:
    def __init__(
        self,
        discovery: ScannerDiscovery,
        endpoint_repository: ScannerEndpointRepository,
        gateway_factory: Callable[[ScannerEndpoint], ScannerGateway],
    ) -> None:
        self._discovery = discovery
        self._endpoint_repository = endpoint_repository
        self._gateway_factory = gateway_factory
        self._connection: _Connection | None = None

    async def acquire_gateway(self) -> ScannerGateway:
        return (await self._ensure_connection()).gateway

    async def _ensure_connection(self) -> _Connection:
        if self._connection is not None:
            return await self._verify(self._connection.gateway, self._connection.endpoint)
        stored_endpoint = self._endpoint_repository.load()
        if stored_endpoint is not None:
            return await self._connect(stored_endpoint)
        return await self._connect_to_discovered()

    async def _connect_to_discovered(self) -> _Connection:
        discovered_endpoints = await self._discovery.discover(DISCOVERY_TIMEOUT_SECONDS)
        connection = await self._connect(discovered_endpoints[0])
        self._endpoint_repository.save(discovered_endpoints[0])
        return connection

    async def _connect(self, endpoint: ScannerEndpoint) -> _Connection:
        connection = await self._verify(self._gateway_factory(endpoint), endpoint)
        self._connection = connection
        return connection

    async def _verify(self, gateway: ScannerGateway, endpoint: ScannerEndpoint) -> _Connection:
        return _Connection(gateway, endpoint, await gateway.read_status())
```

- [ ] **Passo 20: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/services/test_printer_connection_service.py -v`

Expected: `8 passed`.

- [ ] **Passo 21: Escrever o teste que falha** (ciclo 6: Falhas: endereço antigo, estado Down, nada encontrado)

Impressora dormindo, offline ou com IP novo (modo de falha 1 da seção 8 da spec): se o endereço salvo não responde (`ScannerUnreachableError` em `read_status`) ou o estado é `DOWN`, a descoberta é chamada; o endpoint com o mesmo identificador salvo tem preferência (a impressora mudou de IP) e o novo endereço substitui o salvo; sem nada encontrado, ou se nenhum candidato responder, levanta `ScannerUnreachableError`; um `LocalNetworkBlockedError` do endereço salvo não se perde quando a descoberta volta vazia; e um gateway já conectado que deixa de responder é trocado após nova descoberta.

Substitua o bloco de importações de `tests/services/test_printer_connection_service.py` (as linhas `import` e `from` do topo do arquivo) por:

```python
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import pytest

from digitalizadora.domain.errors import LocalNetworkBlockedError, ScannerUnreachableError
from digitalizadora.domain.scanner_endpoint import ScannerEndpoint
from digitalizadora.domain.scanner_status import ScannerState, ScannerStatus
from digitalizadora.services.printer_connection_service import (
    DISCOVERY_TIMEOUT_SECONDS,
    PrinterConnectionService,
)
```

Em `tests/services/test_printer_connection_service.py`, logo depois de `PROCESSING_STATUS`, acrescente:

```python
DOWN_STATUS = ScannerStatus(ScannerState.DOWN)
```

Em `tests/services/test_printer_connection_service.py`, logo depois de `build_harness`, acrescente:

```python
def unreachable_gateway() -> StubScannerGateway:
    return StubScannerGateway([ScannerUnreachableError("no route to the scanner")])
```

Acrescente ao final de `tests/services/test_printer_connection_service.py`:

```python
async def test_unreachable_stored_endpoint_triggers_discovery() -> None:
    gateways = {
        STORED_ENDPOINT.base_address: unreachable_gateway(),
        MOVED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS]),
    }
    harness = build_harness(STORED_ENDPOINT, [MOVED_ENDPOINT], gateways)
    await harness.service.acquire_gateway()
    assert harness.discovery.requested_timeouts == [DISCOVERY_TIMEOUT_SECONDS]


async def test_endpoint_with_the_stored_identifier_is_preferred_after_discovery() -> None:
    other_gateway = StubScannerGateway([IDLE_STATUS])
    moved_gateway = StubScannerGateway([IDLE_STATUS])
    gateways = {
        STORED_ENDPOINT.base_address: unreachable_gateway(),
        OTHER_ENDPOINT.base_address: other_gateway,
        MOVED_ENDPOINT.base_address: moved_gateway,
    }
    harness = build_harness(STORED_ENDPOINT, [OTHER_ENDPOINT, MOVED_ENDPOINT], gateways)
    assert await harness.service.acquire_gateway() is moved_gateway


async def test_new_endpoint_replaces_the_stored_one_after_discovery() -> None:
    gateways = {
        STORED_ENDPOINT.base_address: unreachable_gateway(),
        MOVED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS]),
    }
    harness = build_harness(STORED_ENDPOINT, [MOVED_ENDPOINT], gateways)
    await harness.service.acquire_gateway()
    assert harness.repository.saved_endpoints == [MOVED_ENDPOINT]


async def test_other_scanner_is_used_when_the_stored_identifier_is_not_found() -> None:
    other_gateway = StubScannerGateway([IDLE_STATUS])
    gateways = {STORED_ENDPOINT.base_address: unreachable_gateway(), OTHER_ENDPOINT.base_address: other_gateway}
    harness = build_harness(STORED_ENDPOINT, [OTHER_ENDPOINT], gateways)
    assert await harness.service.acquire_gateway() is other_gateway


async def test_down_status_counts_as_unreachable() -> None:
    gateways = {
        STORED_ENDPOINT.base_address: StubScannerGateway([DOWN_STATUS]),
        MOVED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS]),
    }
    harness = build_harness(STORED_ENDPOINT, [MOVED_ENDPOINT], gateways)
    await harness.service.acquire_gateway()
    assert harness.repository.saved_endpoints == [MOVED_ENDPOINT]


async def test_nothing_found_raises_scanner_unreachable() -> None:
    harness = build_harness(None, [], {})
    with pytest.raises(ScannerUnreachableError):
        await harness.service.acquire_gateway()


async def test_unreachable_discovered_endpoint_raises_scanner_unreachable() -> None:
    harness = build_harness(None, [MOVED_ENDPOINT], {MOVED_ENDPOINT.base_address: unreachable_gateway()})
    with pytest.raises(ScannerUnreachableError):
        await harness.service.acquire_gateway()


async def test_blocked_local_network_error_survives_an_empty_discovery() -> None:
    blocked_gateway = StubScannerGateway([LocalNetworkBlockedError("blocked by the operating system")])
    harness = build_harness(STORED_ENDPOINT, [], {STORED_ENDPOINT.base_address: blocked_gateway})
    with pytest.raises(LocalNetworkBlockedError):
        await harness.service.acquire_gateway()


async def test_connected_gateway_that_stops_answering_is_replaced_after_discovery() -> None:
    stored_gateway = StubScannerGateway([IDLE_STATUS, ScannerUnreachableError("went to sleep")])
    moved_gateway = StubScannerGateway([IDLE_STATUS])
    gateways = {STORED_ENDPOINT.base_address: stored_gateway, MOVED_ENDPOINT.base_address: moved_gateway}
    harness = build_harness(STORED_ENDPOINT, [MOVED_ENDPOINT], gateways)
    await harness.service.acquire_gateway()
    assert await harness.service.acquire_gateway() is moved_gateway
```

- [ ] **Passo 22: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/services/test_printer_connection_service.py -v`

Expected: resumo `7 failed, 10 passed`; falham `test_unreachable_stored_endpoint_triggers_discovery`, `test_endpoint_with_the_stored_identifier_is_preferred_after_discovery`, `test_new_endpoint_replaces_the_stored_one_after_discovery` e mais 4 (erros: `ScannerUnreachableError`, `AssertionError`, `IndexError`). Os demais já passam.

- [ ] **Passo 23: Implementar o mínimo**

Acrescente a função que prioriza o identificador salvo e substitua `_ensure_connection`, `_connect_to_discovered` e `_verify` pelas versões finais.

Substitua o bloco de importações de `src/digitalizadora/services/printer_connection_service.py` (as linhas `import` e `from` do topo do arquivo) por:

```python
import logging
from collections.abc import Callable
from dataclasses import dataclass

from digitalizadora.domain.errors import ScannerUnreachableError
from digitalizadora.domain.ports import ScannerDiscovery, ScannerEndpointRepository, ScannerGateway
from digitalizadora.domain.scanner_endpoint import ScannerEndpoint
from digitalizadora.domain.scanner_status import ScannerState, ScannerStatus
```

Em `src/digitalizadora/services/printer_connection_service.py`, logo depois de `_Connection`, acrescente:

```python
def _prefer_stored_identity(
    discovered_endpoints: list[ScannerEndpoint], stored_endpoint: ScannerEndpoint | None
) -> list[ScannerEndpoint]:
    if stored_endpoint is None or stored_endpoint.universally_unique_identifier is None:
        return list(discovered_endpoints)
    stored_identifier = stored_endpoint.universally_unique_identifier
    same_scanner = [
        endpoint for endpoint in discovered_endpoints if endpoint.universally_unique_identifier == stored_identifier
    ]
    other_scanners = [
        endpoint for endpoint in discovered_endpoints if endpoint.universally_unique_identifier != stored_identifier
    ]
    return same_scanner + other_scanners
```

Em `src/digitalizadora/services/printer_connection_service.py`, substitua por inteiro o método `_ensure_connection` da classe `PrinterConnectionService` por (as reticências `...` representam o resto da classe, que não muda):

```python
class PrinterConnectionService:
    ...

    async def _ensure_connection(self) -> _Connection:
        if self._connection is not None:
            try:
                return await self._verify(self._connection.gateway, self._connection.endpoint)
            except ScannerUnreachableError:
                logger.info("The connected scanner stopped answering; looking for it again")
                self._connection = None
        stored_endpoint = self._endpoint_repository.load()
        failure: ScannerUnreachableError | None = None
        if stored_endpoint is not None:
            try:
                return await self._connect(stored_endpoint)
            except ScannerUnreachableError as error:
                failure = error
        return await self._connect_to_discovered(stored_endpoint, failure)
```

Em `src/digitalizadora/services/printer_connection_service.py`, substitua por inteiro o método `_connect_to_discovered` da classe `PrinterConnectionService` por (as reticências `...` representam o resto da classe, que não muda):

```python
class PrinterConnectionService:
    ...

    async def _connect_to_discovered(
        self, stored_endpoint: ScannerEndpoint | None, failure: ScannerUnreachableError | None
    ) -> _Connection:
        discovered_endpoints = await self._discovery.discover(DISCOVERY_TIMEOUT_SECONDS)
        for endpoint in _prefer_stored_identity(discovered_endpoints, stored_endpoint):
            try:
                connection = await self._connect(endpoint)
            except ScannerUnreachableError as error:
                failure = error
                continue
            self._endpoint_repository.save(endpoint)
            return connection
        raise failure or ScannerUnreachableError("No scanner was found on the local network")
```

Em `src/digitalizadora/services/printer_connection_service.py`, substitua por inteiro o método `_verify` da classe `PrinterConnectionService` por (as reticências `...` representam o resto da classe, que não muda):

```python
class PrinterConnectionService:
    ...

    async def _verify(self, gateway: ScannerGateway, endpoint: ScannerEndpoint) -> _Connection:
        status = await gateway.read_status()
        if status.state is ScannerState.DOWN:
            raise ScannerUnreachableError(f"The scanner at {endpoint.base_address} reports being down")
        return _Connection(gateway, endpoint, status)
```

- [ ] **Passo 24: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/services/test_printer_connection_service.py -v`

Expected: `17 passed`.

- [ ] **Passo 25: Escrever o teste que falha** (ciclo 7: check_connection, refresh e endereço manual)

`check_connection` nunca levanta: devolve `connected=True` com o nome e o estado do scanner, ou `connected=False` com `error_code` (`scanner_unreachable` ou `local_network_blocked`). `refresh` esquece o gateway em memória, apaga o endpoint salvo e procura de novo. `use_manual_address` salva um endpoint chamado "Manual", sem identificador e sem barra final, e descarta o gateway em memória.

Acrescente ao final de `tests/services/test_printer_connection_service.py`:

```python
async def test_check_connection_reports_the_name_and_state_of_the_scanner() -> None:
    harness = build_harness(STORED_ENDPOINT, [], {STORED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS])})
    state = await harness.service.check_connection()
    assert (state.connected, state.display_name, state.scanner_state, state.error_code) == (
        True,
        "HP Stored",
        ScannerState.IDLE,
        None,
    )


async def test_check_connection_reports_a_busy_scanner() -> None:
    gateways = {STORED_ENDPOINT.base_address: StubScannerGateway([PROCESSING_STATUS])}
    harness = build_harness(STORED_ENDPOINT, [], gateways)
    state = await harness.service.check_connection()
    assert state.scanner_state is ScannerState.PROCESSING


async def test_check_connection_reports_an_unreachable_scanner_without_raising() -> None:
    harness = build_harness(None, [], {})
    state = await harness.service.check_connection()
    assert (state.connected, state.display_name, state.scanner_state, state.error_code) == (
        False,
        None,
        None,
        "scanner_unreachable",
    )


async def test_check_connection_reports_a_blocked_local_network() -> None:
    blocked_gateway = StubScannerGateway([LocalNetworkBlockedError("blocked by the operating system")])
    harness = build_harness(STORED_ENDPOINT, [], {STORED_ENDPOINT.base_address: blocked_gateway})
    state = await harness.service.check_connection()
    assert state.error_code == "local_network_blocked"


async def test_refresh_clears_the_stored_endpoint() -> None:
    gateways = {STORED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS])}
    harness = build_harness(STORED_ENDPOINT, [STORED_ENDPOINT], gateways)
    await harness.service.refresh()
    assert harness.repository.clear_count == 1


async def test_refresh_discovers_the_scanner_again() -> None:
    gateways = {STORED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS])}
    harness = build_harness(STORED_ENDPOINT, [STORED_ENDPOINT], gateways)
    await harness.service.refresh()
    assert harness.discovery.requested_timeouts == [DISCOVERY_TIMEOUT_SECONDS]


async def test_refresh_forgets_the_connected_gateway() -> None:
    gateways = {STORED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS])}
    harness = build_harness(STORED_ENDPOINT, [STORED_ENDPOINT], gateways)
    await harness.service.acquire_gateway()
    await harness.service.refresh()
    assert harness.gateway_factory.requested_base_addresses == [STORED_ENDPOINT.base_address] * 2


async def test_refresh_reports_the_rediscovered_scanner() -> None:
    gateways = {MOVED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS])}
    harness = build_harness(STORED_ENDPOINT, [MOVED_ENDPOINT], gateways)
    state = await harness.service.refresh()
    assert (state.connected, state.display_name) == (True, "HP Moved")


async def test_refresh_reports_when_nothing_is_found() -> None:
    harness = build_harness(STORED_ENDPOINT, [], {})
    state = await harness.service.refresh()
    assert (state.connected, state.error_code) == (False, "scanner_unreachable")


def test_manual_address_is_saved_with_the_manual_display_name_and_no_identifier() -> None:
    harness = build_harness(None, [], {})
    harness.service.use_manual_address("http://192.168.0.50:8080/eSCL")
    assert harness.repository.saved_endpoints == [ScannerEndpoint("http://192.168.0.50:8080/eSCL", "Manual", None)]


def test_manual_address_loses_its_trailing_slash() -> None:
    harness = build_harness(None, [], {})
    harness.service.use_manual_address("http://192.168.0.50:8080/eSCL/")
    assert harness.repository.saved_endpoints[0].base_address == "http://192.168.0.50:8080/eSCL"


async def test_manual_address_drops_the_connected_gateway() -> None:
    manual_endpoint = ScannerEndpoint("http://192.168.0.50:8080/eSCL", "Manual")
    gateways = {
        STORED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS]),
        manual_endpoint.base_address: StubScannerGateway([IDLE_STATUS]),
    }
    harness = build_harness(STORED_ENDPOINT, [], gateways)
    await harness.service.acquire_gateway()
    harness.service.use_manual_address(manual_endpoint.base_address)
    await harness.service.acquire_gateway()
    assert harness.gateway_factory.requested_base_addresses[-1] == manual_endpoint.base_address
```

- [ ] **Passo 26: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/services/test_printer_connection_service.py -v`

Expected: resumo `12 failed, 17 passed`; falham `test_check_connection_reports_the_name_and_state_of_the_scanner`, `test_check_connection_reports_a_busy_scanner`, `test_check_connection_reports_an_unreachable_scanner_without_raising` e mais 9 (erros: `AttributeError`). Os demais já passam.

- [ ] **Passo 27: Implementar o mínimo**

Acrescente o nome do endpoint manual, o estado de conexão e os três métodos públicos.

Em `src/digitalizadora/services/printer_connection_service.py`, logo depois de `DISCOVERY_TIMEOUT_SECONDS`, acrescente:

```python
MANUAL_DISPLAY_NAME = "Manual"
```

Em `src/digitalizadora/services/printer_connection_service.py`, logo depois de `MANUAL_DISPLAY_NAME`, acrescente:

```python
@dataclass(frozen=True)
class PrinterConnectionState:
    connected: bool
    display_name: str | None
    scanner_state: ScannerState | None
    error_code: str | None
```

Em `src/digitalizadora/services/printer_connection_service.py`, dentro da classe `PrinterConnectionService`, logo depois do método `acquire_gateway`, acrescente (as reticências `...` representam o resto da classe):

```python
class PrinterConnectionService:
    ...

    async def check_connection(self) -> PrinterConnectionState:
        try:
            connection = await self._ensure_connection()
        except ScannerUnreachableError as error:
            return PrinterConnectionState(
                connected=False, display_name=None, scanner_state=None, error_code=error.code
            )
        return PrinterConnectionState(
            connected=True,
            display_name=connection.endpoint.display_name,
            scanner_state=connection.status.state,
            error_code=None,
        )

    async def refresh(self) -> PrinterConnectionState:
        self._connection = None
        self._endpoint_repository.clear()
        return await self.check_connection()

    def use_manual_address(self, base_address: str) -> None:
        self._connection = None
        self._endpoint_repository.save(
            ScannerEndpoint(base_address=base_address.rstrip("/"), display_name=MANUAL_DISPLAY_NAME)
        )
```

- [ ] **Passo 28: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/services/test_printer_connection_service.py -v`

Expected: `29 passed`.

- [ ] **Passo 29: Rodar todos os testes da tarefa**

Run: `.venv/bin/pytest tests/infrastructure/test_bonjour_scanner_discovery.py tests/infrastructure/test_zeroconf_service_record_source.py tests/services/test_printer_connection_service.py -v`

Expected: `57 passed`.

- [ ] **Passo 30: Rodar a verificação estática e a lentidão dos testes**

Run: `make lint && .venv/bin/pytest tests/infrastructure/test_bonjour_scanner_discovery.py tests/infrastructure/test_zeroconf_service_record_source.py tests/services/test_printer_connection_service.py --durations=3`

Expected: o lint sem erros do ruff e `57 passed`, com os três testes mais lentos abaixo de 100 ms.

- [ ] **Passo 31: Commit**

```bash
git add src/digitalizadora/infrastructure/bonjour_scanner_discovery.py src/digitalizadora/infrastructure/zeroconf_service_record_source.py src/digitalizadora/services/printer_connection_service.py tests/infrastructure/test_bonjour_scanner_discovery.py tests/infrastructure/test_zeroconf_service_record_source.py tests/services/test_printer_connection_service.py
git commit -m "feat(discovery): add Bonjour discovery and the printer connection service"
```

### Task 10: Acompanhamento de progresso, ScanService e estado da aplicação

**Objetivo:** Implementar a máquina de fases `ScanProgressTracker`, a orquestração `ScanService`, o `ApplicationStateService` e os dublês `ScriptedScannerGateway` e `FixedGatewayProvider` que os testes usam.

**Files:**
- Create: `src/digitalizadora/services/scan_progress_tracker.py`
- Create: `src/digitalizadora/services/scan_service.py`
- Create: `src/digitalizadora/services/application_state_service.py`
- Create: `tests/fakes/scripted_scanner_gateway.py`
- Test: `tests/services/test_scan_progress_tracker.py`
- Test: `tests/fakes/test_scripted_scanner_gateway.py`
- Test: `tests/services/test_scan_service.py`
- Test: `tests/services/test_application_state_service.py`

**Interfaces:**
- Consumes (Task 2): `OutputFormat`, `ScanPreset` (`.settings`), `ScanSettings`, `ScanRequest`, `ScanJob`, `ScanResult`, `StoredScan`, `ScannedImage`, `ScannerCapabilities`, `ScannerStatus`, `ScannerState`, `ApplicationSettings` (`.to_scan_request()`), `ScanPhase`, `ScanProgressSnapshot`, os erros de `digitalizadora.domain.errors`, as portas `Clock`, `ScannerGateway`, `ScannerGatewayProvider`, `ApplicationSettingsRepository` de `digitalizadora.domain.ports`, e `tests.fakes.fixed_clock.FixedClock(moment)` com `now()` e `advance(seconds)`.
- Consumes (Task 7): `tests.fakes.in_memory_settings_repository.InMemoryApplicationSettingsRepository(settings)` com `load()` e `save(settings)`.
- Consumes (Task 8): `digitalizadora.services.scan_output_service.ScanOutputService` (`ensure_capacity(request)`, `store(scanned_image, job) -> StoredScan`) e `digitalizadora.services.storage_guard_service.StorageGuardService(free_space_reader)` com `free_space_in_bytes(folder)` e `estimate_pages_remaining(folder, settings)`.
- Produces: `ScanProgressTracker(clock)` com `begin_scan`, `mark_scanning`, `mark_saving`, `mark_completed`, `mark_failed`, `snapshot`, `last_thumbnail_jpeg` (contrato 6.4, sem desvios).
- Produces: `ScanService(gateway_provider, scan_output_service, progress_tracker)` com `is_scan_in_progress()` e `async scan_one_file(request) -> ScanResult`.
- Produces: `StorageState(free_space_in_bytes, estimated_pages_remaining)`, `ApplicationState(snapshot, settings, storage)` e `ApplicationStateService(progress_tracker, settings_repository, storage_guard_service).build_state()`.
- Produces: `tests.fakes.scripted_scanner_gateway.ScriptedScannerGateway(capabilities, scan_outcomes)` (atributo `scan_requests`), `FixedGatewayProvider(gateway)` e a função auxiliar `build_sample_capabilities() -> ScannerCapabilities` (capacidades de uma 2874 fictícia).

Cobertura do Review Focus: modo (1) o teste do provedor que levanta `ScannerUnreachableError` e o do gateway que falha; modo (2) segunda chamada durante um scan (tracker e serviço); modo (3) `InsufficientStorageError` sem contatar o gateway e falha de gravação (`OutputFolderUnavailableError`).

#### Ciclo 1: ScanProgressTracker

- [ ] **Passo 1: Escrever o teste que falha**

Crie `tests/services/test_scan_progress_tracker.py`:

```python
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from digitalizadora.domain.errors import ScanAlreadyRunningError
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_progress import ScanPhase
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.domain.stored_scan import StoredScan
from digitalizadora.services.scan_progress_tracker import ScanProgressTracker
from tests.fakes.fixed_clock import FixedClock

STARTED_AT = datetime(2026, 10, 13, 15, 30, 12, tzinfo=timezone(timedelta(hours=-3)))
SCAN_REQUEST = ScanRequest(settings=ScanPreset.DOCUMENT.settings, output_format=OutputFormat.PDF)
THUMBNAIL_JPEG = b"thumbnail-bytes"


def build_stored_scan(thumbnail_jpeg: bytes = THUMBNAIL_JPEG) -> StoredScan:
    result = ScanResult(
        output_path=Path("/Volumes/Scans/2026-10-13_00001.pdf"),
        output_format=OutputFormat.PDF,
        scanned_at=STARTED_AT,
        size_in_bytes=1234,
    )
    return StoredScan(result=result, thumbnail_jpeg=thumbnail_jpeg)


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(STARTED_AT)


@pytest.fixture
def tracker(clock: FixedClock) -> ScanProgressTracker:
    return ScanProgressTracker(clock)


def test_new_tracker_is_idle_without_history(tracker: ScanProgressTracker) -> None:
    snapshot = tracker.snapshot()

    assert snapshot.phase is ScanPhase.IDLE
    assert snapshot.scans_completed == 0
    assert snapshot.last_result is None
    assert snapshot.last_error_code is None


def test_new_tracker_has_no_thumbnail(tracker: ScanProgressTracker) -> None:
    assert tracker.last_thumbnail_jpeg() is None


def test_begin_scan_moves_to_preparing(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)

    assert tracker.snapshot().phase is ScanPhase.PREPARING


def test_begin_scan_returns_job_with_request_and_clock_time(
    tracker: ScanProgressTracker, clock: FixedClock
) -> None:
    clock.advance(90)

    job = tracker.begin_scan(SCAN_REQUEST)

    assert job.request == SCAN_REQUEST
    assert job.started_at == STARTED_AT + timedelta(seconds=90)


def test_begin_scan_clears_the_previous_error_code(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_failed("scanner_unreachable")

    tracker.begin_scan(SCAN_REQUEST)

    assert tracker.snapshot().last_error_code is None


def test_mark_scanning_moves_to_scanning(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)

    tracker.mark_scanning()

    assert tracker.snapshot().phase is ScanPhase.SCANNING


def test_mark_saving_moves_to_saving(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_scanning()

    tracker.mark_saving()

    assert tracker.snapshot().phase is ScanPhase.SAVING


def test_mark_completed_returns_to_idle(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)

    tracker.mark_completed(build_stored_scan())

    assert tracker.snapshot().phase is ScanPhase.IDLE


def test_mark_completed_increments_scans_completed(tracker: ScanProgressTracker) -> None:
    for _ in range(2):
        tracker.begin_scan(SCAN_REQUEST)
        tracker.mark_completed(build_stored_scan())

    assert tracker.snapshot().scans_completed == 2


def test_mark_completed_stores_last_result_and_thumbnail(tracker: ScanProgressTracker) -> None:
    stored_scan = build_stored_scan()
    tracker.begin_scan(SCAN_REQUEST)

    tracker.mark_completed(stored_scan)

    assert tracker.snapshot().last_result == stored_scan.result
    assert tracker.last_thumbnail_jpeg() == THUMBNAIL_JPEG


def test_mark_failed_stores_code_and_returns_to_idle(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_scanning()

    tracker.mark_failed("scan_failed")

    snapshot = tracker.snapshot()
    assert snapshot.phase is ScanPhase.IDLE
    assert snapshot.last_error_code == "scan_failed"


def test_mark_failed_does_not_count_a_completed_scan(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)

    tracker.mark_failed("scan_failed")

    assert tracker.snapshot().scans_completed == 0


def test_thumbnail_survives_a_later_failure(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_completed(build_stored_scan())
    tracker.begin_scan(SCAN_REQUEST)

    tracker.mark_failed("scan_failed")

    assert tracker.last_thumbnail_jpeg() == THUMBNAIL_JPEG


def test_last_result_survives_a_later_failure(tracker: ScanProgressTracker) -> None:
    stored_scan = build_stored_scan()
    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_completed(stored_scan)
    tracker.begin_scan(SCAN_REQUEST)

    tracker.mark_failed("scan_failed")

    assert tracker.snapshot().last_result == stored_scan.result


def test_a_new_thumbnail_replaces_the_previous_one(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_completed(build_stored_scan(b"first"))
    tracker.begin_scan(SCAN_REQUEST)

    tracker.mark_completed(build_stored_scan(b"second"))

    assert tracker.last_thumbnail_jpeg() == b"second"


def test_begin_scan_raises_while_preparing(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)

    with pytest.raises(ScanAlreadyRunningError):
        tracker.begin_scan(SCAN_REQUEST)


@pytest.mark.parametrize("transition_name", ["mark_scanning", "mark_saving"])
def test_begin_scan_raises_while_scanning_or_saving(
    tracker: ScanProgressTracker, transition_name: str
) -> None:
    tracker.begin_scan(SCAN_REQUEST)
    getattr(tracker, transition_name)()

    with pytest.raises(ScanAlreadyRunningError):
        tracker.begin_scan(SCAN_REQUEST)


def test_rejected_begin_scan_leaves_the_running_scan_untouched(
    tracker: ScanProgressTracker,
) -> None:
    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_scanning()
    snapshot_before = tracker.snapshot()

    with pytest.raises(ScanAlreadyRunningError):
        tracker.begin_scan(SCAN_REQUEST)

    assert tracker.snapshot() == snapshot_before


def test_begin_scan_is_accepted_again_after_completion(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_completed(build_stored_scan())

    tracker.begin_scan(SCAN_REQUEST)

    assert tracker.snapshot().phase is ScanPhase.PREPARING


def test_begin_scan_is_accepted_again_after_failure(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_failed("scan_failed")

    tracker.begin_scan(SCAN_REQUEST)

    assert tracker.snapshot().phase is ScanPhase.PREPARING


def test_snapshot_is_not_changed_by_later_transitions(tracker: ScanProgressTracker) -> None:
    snapshot_before = tracker.snapshot()

    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_completed(build_stored_scan())

    assert snapshot_before.phase is ScanPhase.IDLE
    assert snapshot_before.scans_completed == 0


def test_snapshot_rejects_attribute_assignment(tracker: ScanProgressTracker) -> None:
    snapshot = tracker.snapshot()

    with pytest.raises(FrozenInstanceError):
        snapshot.scans_completed = 99
```

- [ ] **Passo 2: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/services/test_scan_progress_tracker.py::test_new_tracker_is_idle_without_history -v`

Expected: erro de coleta, `1 error`, com a linha `ModuleNotFoundError: No module named 'digitalizadora.services.scan_progress_tracker'`.

- [ ] **Passo 3: Implementar o mínimo**

Crie `src/digitalizadora/services/scan_progress_tracker.py`:

```python
from digitalizadora.domain.errors import ScanAlreadyRunningError
from digitalizadora.domain.ports import Clock
from digitalizadora.domain.scan_job import ScanJob
from digitalizadora.domain.scan_progress import ScanPhase, ScanProgressSnapshot
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.domain.stored_scan import StoredScan


class ScanProgressTracker:
    """Holds the progress of the current scan and the outcome of the previous ones.

    Every method runs on the event loop thread, so no locking is needed.
    """

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._phase = ScanPhase.IDLE
        self._scans_completed = 0
        self._last_result: ScanResult | None = None
        self._last_error_code: str | None = None
        self._last_thumbnail_jpeg: bytes | None = None

    def begin_scan(self, request: ScanRequest) -> ScanJob:
        if self._phase is not ScanPhase.IDLE:
            raise ScanAlreadyRunningError("A scan is already in progress")
        self._phase = ScanPhase.PREPARING
        self._last_error_code = None
        return ScanJob(request=request, started_at=self._clock.now())

    def mark_scanning(self) -> None:
        self._phase = ScanPhase.SCANNING

    def mark_saving(self) -> None:
        self._phase = ScanPhase.SAVING

    def mark_completed(self, stored_scan: StoredScan) -> None:
        self._scans_completed += 1
        self._last_result = stored_scan.result
        self._last_thumbnail_jpeg = stored_scan.thumbnail_jpeg
        self._phase = ScanPhase.IDLE

    def mark_failed(self, error_code: str) -> None:
        self._last_error_code = error_code
        self._phase = ScanPhase.IDLE

    def snapshot(self) -> ScanProgressSnapshot:
        return ScanProgressSnapshot(
            phase=self._phase,
            scans_completed=self._scans_completed,
            last_result=self._last_result,
            last_error_code=self._last_error_code,
        )

    def last_thumbnail_jpeg(self) -> bytes | None:
        return self._last_thumbnail_jpeg
```

- [ ] **Passo 4: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/services/test_scan_progress_tracker.py -v`

Expected: `23 passed`.

#### Ciclo 2: dublês ScriptedScannerGateway e FixedGatewayProvider

- [ ] **Passo 5: Escrever o teste que falha**

Crie `tests/fakes/test_scripted_scanner_gateway.py`:

```python
import pytest

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import ScannerUnreachableError
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.domain.scanner_status import ScannerState
from tests.fakes.scripted_scanner_gateway import (
    FixedGatewayProvider,
    ScriptedScannerGateway,
    build_sample_capabilities,
)

SETTINGS = ScanSettings(dots_per_inch=300, color_mode=ColorMode.COLOR)
FIRST_IMAGE = ScannedImage(content=b"first", media_type="image/jpeg")
SECOND_IMAGE = ScannedImage(content=b"second", media_type="image/jpeg")


async def test_scan_page_returns_the_scripted_outcomes_in_order() -> None:
    gateway = ScriptedScannerGateway(build_sample_capabilities(), [FIRST_IMAGE, SECOND_IMAGE])

    first = await gateway.scan_page(SETTINGS)
    second = await gateway.scan_page(SETTINGS)

    assert (first, second) == (FIRST_IMAGE, SECOND_IMAGE)


async def test_scan_page_raises_an_exception_outcome() -> None:
    gateway = ScriptedScannerGateway(build_sample_capabilities(), [ScannerUnreachableError("off")])

    with pytest.raises(ScannerUnreachableError):
        await gateway.scan_page(SETTINGS)


async def test_scan_page_records_every_requested_setting() -> None:
    gateway = ScriptedScannerGateway(build_sample_capabilities(), [FIRST_IMAGE, SECOND_IMAGE])

    await gateway.scan_page(SETTINGS)
    await gateway.scan_page(SETTINGS)

    assert gateway.scan_requests == [SETTINGS, SETTINGS]


async def test_scan_page_without_a_scripted_outcome_fails_loudly() -> None:
    gateway = ScriptedScannerGateway(build_sample_capabilities(), [])

    with pytest.raises(AssertionError):
        await gateway.scan_page(SETTINGS)


async def test_read_capabilities_returns_the_given_capabilities() -> None:
    capabilities = build_sample_capabilities()
    gateway = ScriptedScannerGateway(capabilities, [])

    assert await gateway.read_capabilities() == capabilities


async def test_read_status_reports_an_idle_scanner() -> None:
    gateway = ScriptedScannerGateway(build_sample_capabilities(), [])

    status = await gateway.read_status()

    assert status.state is ScannerState.IDLE
    assert status.is_ready


async def test_fixed_gateway_provider_returns_the_same_gateway_every_time() -> None:
    gateway = ScriptedScannerGateway(build_sample_capabilities(), [])
    provider = FixedGatewayProvider(gateway)

    assert await provider.acquire_gateway() is gateway
    assert await provider.acquire_gateway() is gateway
```

- [ ] **Passo 6: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/fakes/test_scripted_scanner_gateway.py::test_scan_page_returns_the_scripted_outcomes_in_order -v`

Expected: erro de coleta, `1 error`, com `ModuleNotFoundError: No module named 'tests.fakes.scripted_scanner_gateway'`.

- [ ] **Passo 7: Implementar o mínimo**

Crie `tests/fakes/scripted_scanner_gateway.py`:

```python
from collections import deque
from collections.abc import Sequence

from digitalizadora.domain.ports import ScannerGateway
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.domain.scanner_capabilities import ScannerCapabilities
from digitalizadora.domain.scanner_status import ScannerState, ScannerStatus


def build_sample_capabilities() -> ScannerCapabilities:
    return ScannerCapabilities(
        make_and_model="HP DeskJet 2800 series",
        platen_maximum_width=2551,
        platen_maximum_height=3507,
        supported_resolutions=(75, 100, 150, 200, 300, 600),
        supported_color_modes=("RGB24", "Grayscale8"),
        supported_document_formats=("image/jpeg",),
    )


class ScriptedScannerGateway:
    """Scanner gateway whose scan_page returns scripted outcomes in order.

    An outcome that is an Exception instance is raised instead of returned.
    """

    def __init__(
        self,
        capabilities: ScannerCapabilities,
        scan_outcomes: Sequence[ScannedImage | Exception],
    ) -> None:
        self._capabilities = capabilities
        self._remaining_outcomes = deque(scan_outcomes)
        self.scan_requests: list[ScanSettings] = []

    async def read_capabilities(self) -> ScannerCapabilities:
        return self._capabilities

    async def read_status(self) -> ScannerStatus:
        return ScannerStatus(state=ScannerState.IDLE)

    async def scan_page(self, settings: ScanSettings) -> ScannedImage:
        self.scan_requests.append(settings)
        if not self._remaining_outcomes:
            raise AssertionError("ScriptedScannerGateway has no scripted outcome left")
        outcome = self._remaining_outcomes.popleft()
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FixedGatewayProvider:
    """Scanner gateway provider that always hands out the same gateway."""

    def __init__(self, gateway: ScannerGateway) -> None:
        self._gateway = gateway

    async def acquire_gateway(self) -> ScannerGateway:
        return self._gateway
```

- [ ] **Passo 8: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/fakes/test_scripted_scanner_gateway.py -v`

Expected: `7 passed`.

#### Ciclo 3: ScanService

O `ObservingScriptedScannerGateway` do teste herda de `ScriptedScannerGateway` (sem alterar o contrato do dublê) para segurar a digitalização em um `asyncio.Event` e registrar a fase em que o gateway foi chamado.

- [ ] **Passo 9: Escrever o teste que falha**

Crie `tests/services/test_scan_service.py`:

```python
import asyncio
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from digitalizadora.domain.errors import (
    DigitalizadoraError,
    InsufficientStorageError,
    OutputFolderUnavailableError,
    ScanAlreadyRunningError,
    ScanFailedError,
    ScannerBusyError,
    ScannerUnreachableError,
    ScanTimedOutError,
)
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.ports import ScannerGateway
from digitalizadora.domain.scan_job import ScanJob
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_progress import ScanPhase
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.domain.scanner_capabilities import ScannerCapabilities
from digitalizadora.domain.stored_scan import StoredScan
from digitalizadora.services.scan_progress_tracker import ScanProgressTracker
from digitalizadora.services.scan_service import ScanService
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.scripted_scanner_gateway import (
    FixedGatewayProvider,
    ScriptedScannerGateway,
    build_sample_capabilities,
)

STARTED_AT = datetime(2026, 10, 13, 15, 30, 12, tzinfo=timezone(timedelta(hours=-3)))
SCAN_REQUEST = ScanRequest(settings=ScanPreset.DOCUMENT.settings, output_format=OutputFormat.PDF)
SCANNED_IMAGE = ScannedImage(content=b"jpeg-bytes", media_type="image/jpeg")
STORED_PATH = Path("/Volumes/Scans/2026-10-13_00001.pdf")


class RecordingScanOutputService:
    """Duck-typed stand-in for ScanOutputService (same two methods)."""

    def __init__(self, progress_tracker: ScanProgressTracker) -> None:
        self._progress_tracker = progress_tracker
        self.capacity_failure: Exception | None = None
        self.store_failure: Exception | None = None
        self.capacity_requests: list[ScanRequest] = []
        self.stored_jobs: list[ScanJob] = []
        self.phase_during_capacity_check: ScanPhase | None = None
        self.phase_during_store: ScanPhase | None = None
        self.store_thread_identifier: int | None = None

    def ensure_capacity(self, request: ScanRequest) -> None:
        self.capacity_requests.append(request)
        self.phase_during_capacity_check = self._progress_tracker.snapshot().phase
        if self.capacity_failure is not None:
            raise self.capacity_failure

    def store(self, scanned_image: ScannedImage, job: ScanJob) -> StoredScan:
        self.stored_jobs.append(job)
        self.phase_during_store = self._progress_tracker.snapshot().phase
        self.store_thread_identifier = threading.get_ident()
        if self.store_failure is not None:
            raise self.store_failure
        result = ScanResult(
            output_path=STORED_PATH,
            output_format=job.request.output_format,
            scanned_at=job.started_at,
            size_in_bytes=len(scanned_image.content),
        )
        return StoredScan(result=result, thumbnail_jpeg=b"thumbnail")


class ObservingScriptedScannerGateway(ScriptedScannerGateway):
    """Scripted gateway that can hold a scan open and reports the phase it ran in."""

    def __init__(
        self,
        capabilities: ScannerCapabilities,
        scan_outcomes: list[ScannedImage | Exception],
        progress_tracker: ScanProgressTracker,
    ) -> None:
        super().__init__(capabilities, scan_outcomes)
        self._progress_tracker = progress_tracker
        self.scan_started = asyncio.Event()
        self.release_scan = asyncio.Event()
        self.release_scan.set()
        self.phase_during_scan: ScanPhase | None = None

    def hold_scans_open(self) -> None:
        self.release_scan.clear()

    async def scan_page(self, settings: ScanSettings) -> ScannedImage:
        self.phase_during_scan = self._progress_tracker.snapshot().phase
        self.scan_started.set()
        await self.release_scan.wait()
        return await super().scan_page(settings)


class FailingGatewayProvider:
    def __init__(self, failure: Exception) -> None:
        self._failure = failure

    async def acquire_gateway(self) -> ScannerGateway:
        raise self._failure


@pytest.fixture
def progress_tracker() -> ScanProgressTracker:
    return ScanProgressTracker(FixedClock(STARTED_AT))


@pytest.fixture
def output_service(progress_tracker: ScanProgressTracker) -> RecordingScanOutputService:
    return RecordingScanOutputService(progress_tracker)


@pytest.fixture
def gateway(progress_tracker: ScanProgressTracker) -> ObservingScriptedScannerGateway:
    return ObservingScriptedScannerGateway(
        build_sample_capabilities(), [SCANNED_IMAGE], progress_tracker
    )


@pytest.fixture
def scan_service(
    gateway: ObservingScriptedScannerGateway,
    output_service: RecordingScanOutputService,
    progress_tracker: ScanProgressTracker,
) -> ScanService:
    return ScanService(FixedGatewayProvider(gateway), output_service, progress_tracker)


def start_held_scan(
    scan_service: ScanService, gateway: ObservingScriptedScannerGateway
) -> "asyncio.Task[ScanResult]":
    gateway.hold_scans_open()
    return asyncio.create_task(scan_service.scan_one_file(SCAN_REQUEST))


async def test_scan_one_file_returns_the_stored_result(scan_service: ScanService) -> None:
    result = await scan_service.scan_one_file(SCAN_REQUEST)

    assert result.output_path == STORED_PATH
    assert result.size_in_bytes == len(SCANNED_IMAGE.content)


async def test_scan_one_file_ends_idle_with_one_completed_scan(
    scan_service: ScanService, progress_tracker: ScanProgressTracker
) -> None:
    result = await scan_service.scan_one_file(SCAN_REQUEST)

    snapshot = progress_tracker.snapshot()
    assert snapshot.phase is ScanPhase.IDLE
    assert snapshot.scans_completed == 1
    assert snapshot.last_result == result
    assert snapshot.last_error_code is None


async def test_gateway_receives_the_settings_of_the_request(
    scan_service: ScanService, gateway: ObservingScriptedScannerGateway
) -> None:
    await scan_service.scan_one_file(SCAN_REQUEST)

    assert gateway.scan_requests == [SCAN_REQUEST.settings]


async def test_capacity_is_checked_for_the_request(
    scan_service: ScanService, output_service: RecordingScanOutputService
) -> None:
    await scan_service.scan_one_file(SCAN_REQUEST)

    assert output_service.capacity_requests == [SCAN_REQUEST]


async def test_store_receives_the_job_started_by_the_tracker(
    scan_service: ScanService, output_service: RecordingScanOutputService
) -> None:
    await scan_service.scan_one_file(SCAN_REQUEST)

    stored_job = output_service.stored_jobs[0]
    assert stored_job.request == SCAN_REQUEST
    assert stored_job.started_at == STARTED_AT


async def test_phase_is_preparing_during_the_capacity_check(
    scan_service: ScanService, output_service: RecordingScanOutputService
) -> None:
    await scan_service.scan_one_file(SCAN_REQUEST)

    assert output_service.phase_during_capacity_check is ScanPhase.PREPARING


async def test_phase_is_scanning_while_the_gateway_is_awaited(
    scan_service: ScanService, gateway: ObservingScriptedScannerGateway
) -> None:
    await scan_service.scan_one_file(SCAN_REQUEST)

    assert gateway.phase_during_scan is ScanPhase.SCANNING


async def test_phase_is_saving_while_the_image_is_stored(
    scan_service: ScanService, output_service: RecordingScanOutputService
) -> None:
    await scan_service.scan_one_file(SCAN_REQUEST)

    assert output_service.phase_during_store is ScanPhase.SAVING


async def test_store_runs_outside_the_event_loop_thread(
    scan_service: ScanService, output_service: RecordingScanOutputService
) -> None:
    await scan_service.scan_one_file(SCAN_REQUEST)

    assert output_service.store_thread_identifier != threading.get_ident()


async def test_insufficient_storage_is_recorded_with_its_code(
    scan_service: ScanService,
    output_service: RecordingScanOutputService,
    progress_tracker: ScanProgressTracker,
) -> None:
    output_service.capacity_failure = InsufficientStorageError("disk almost full")

    with pytest.raises(InsufficientStorageError):
        await scan_service.scan_one_file(SCAN_REQUEST)

    snapshot = progress_tracker.snapshot()
    assert snapshot.last_error_code == "insufficient_storage"
    assert snapshot.phase is ScanPhase.IDLE


async def test_insufficient_storage_does_not_contact_the_gateway(
    scan_service: ScanService,
    gateway: ObservingScriptedScannerGateway,
    output_service: RecordingScanOutputService,
) -> None:
    output_service.capacity_failure = InsufficientStorageError("disk almost full")

    with pytest.raises(InsufficientStorageError):
        await scan_service.scan_one_file(SCAN_REQUEST)

    assert gateway.scan_requests == []


async def test_scanner_unreachable_from_the_gateway_is_recorded(
    progress_tracker: ScanProgressTracker, output_service: RecordingScanOutputService
) -> None:
    gateway = ObservingScriptedScannerGateway(
        build_sample_capabilities(), [ScannerUnreachableError("offline")], progress_tracker
    )
    scan_service = ScanService(FixedGatewayProvider(gateway), output_service, progress_tracker)

    with pytest.raises(ScannerUnreachableError):
        await scan_service.scan_one_file(SCAN_REQUEST)

    assert progress_tracker.snapshot().last_error_code == "scanner_unreachable"
    assert output_service.stored_jobs == []


@pytest.mark.parametrize("error_type", [ScannerBusyError, ScanFailedError, ScanTimedOutError])
async def test_every_gateway_error_records_its_own_code(
    progress_tracker: ScanProgressTracker,
    output_service: RecordingScanOutputService,
    error_type: type[DigitalizadoraError],
) -> None:
    gateway = ObservingScriptedScannerGateway(
        build_sample_capabilities(), [error_type("failure")], progress_tracker
    )
    scan_service = ScanService(FixedGatewayProvider(gateway), output_service, progress_tracker)

    with pytest.raises(error_type):
        await scan_service.scan_one_file(SCAN_REQUEST)

    assert progress_tracker.snapshot().last_error_code == error_type.code


async def test_provider_failure_is_recorded_like_a_gateway_failure(
    output_service: RecordingScanOutputService, progress_tracker: ScanProgressTracker
) -> None:
    provider = FailingGatewayProvider(ScannerUnreachableError("not found"))
    scan_service = ScanService(provider, output_service, progress_tracker)

    with pytest.raises(ScannerUnreachableError):
        await scan_service.scan_one_file(SCAN_REQUEST)

    snapshot = progress_tracker.snapshot()
    assert snapshot.last_error_code == "scanner_unreachable"
    assert snapshot.phase is ScanPhase.IDLE


async def test_store_failure_records_the_code_of_that_error(
    scan_service: ScanService,
    output_service: RecordingScanOutputService,
    progress_tracker: ScanProgressTracker,
) -> None:
    output_service.store_failure = OutputFolderUnavailableError("volume disconnected")

    with pytest.raises(OutputFolderUnavailableError):
        await scan_service.scan_one_file(SCAN_REQUEST)

    snapshot = progress_tracker.snapshot()
    assert snapshot.last_error_code == "output_folder_unavailable"
    assert snapshot.scans_completed == 0
    assert snapshot.phase is ScanPhase.IDLE


async def test_unexpected_exception_is_recorded_and_reraised(
    progress_tracker: ScanProgressTracker, output_service: RecordingScanOutputService
) -> None:
    gateway = ObservingScriptedScannerGateway(
        build_sample_capabilities(), [RuntimeError("boom")], progress_tracker
    )
    scan_service = ScanService(FixedGatewayProvider(gateway), output_service, progress_tracker)

    with pytest.raises(RuntimeError, match="boom"):
        await scan_service.scan_one_file(SCAN_REQUEST)

    snapshot = progress_tracker.snapshot()
    assert snapshot.last_error_code == "unexpected_error"
    assert snapshot.phase is ScanPhase.IDLE


async def test_a_new_scan_succeeds_after_a_failure(
    progress_tracker: ScanProgressTracker, output_service: RecordingScanOutputService
) -> None:
    gateway = ObservingScriptedScannerGateway(
        build_sample_capabilities(),
        [ScannerBusyError("busy"), SCANNED_IMAGE],
        progress_tracker,
    )
    scan_service = ScanService(FixedGatewayProvider(gateway), output_service, progress_tracker)
    with pytest.raises(ScannerBusyError):
        await scan_service.scan_one_file(SCAN_REQUEST)

    await scan_service.scan_one_file(SCAN_REQUEST)

    snapshot = progress_tracker.snapshot()
    assert snapshot.last_error_code is None
    assert snapshot.scans_completed == 1


async def test_second_call_during_a_scan_raises_scan_already_running(
    scan_service: ScanService, gateway: ObservingScriptedScannerGateway
) -> None:
    first_scan = start_held_scan(scan_service, gateway)
    await gateway.scan_started.wait()

    with pytest.raises(ScanAlreadyRunningError):
        await scan_service.scan_one_file(SCAN_REQUEST)

    gateway.release_scan.set()
    await first_scan


async def test_second_call_leaves_the_running_scan_untouched(
    scan_service: ScanService,
    gateway: ObservingScriptedScannerGateway,
    progress_tracker: ScanProgressTracker,
) -> None:
    first_scan = start_held_scan(scan_service, gateway)
    await gateway.scan_started.wait()

    with pytest.raises(ScanAlreadyRunningError):
        await scan_service.scan_one_file(SCAN_REQUEST)

    snapshot = progress_tracker.snapshot()
    assert snapshot.phase is ScanPhase.SCANNING
    assert snapshot.last_error_code is None
    gateway.release_scan.set()
    await first_scan


async def test_first_scan_completes_after_a_rejected_second_call(
    scan_service: ScanService,
    gateway: ObservingScriptedScannerGateway,
    progress_tracker: ScanProgressTracker,
) -> None:
    first_scan = start_held_scan(scan_service, gateway)
    await gateway.scan_started.wait()
    with pytest.raises(ScanAlreadyRunningError):
        await scan_service.scan_one_file(SCAN_REQUEST)

    gateway.release_scan.set()
    result = await first_scan

    snapshot = progress_tracker.snapshot()
    assert snapshot.scans_completed == 1
    assert snapshot.last_result == result
    assert gateway.scan_requests == [SCAN_REQUEST.settings]


async def test_is_scan_in_progress_is_false_when_idle(scan_service: ScanService) -> None:
    assert scan_service.is_scan_in_progress() is False


async def test_is_scan_in_progress_is_true_while_scanning(
    scan_service: ScanService, gateway: ObservingScriptedScannerGateway
) -> None:
    first_scan = start_held_scan(scan_service, gateway)
    await gateway.scan_started.wait()

    assert scan_service.is_scan_in_progress() is True

    gateway.release_scan.set()
    await first_scan


async def test_is_scan_in_progress_is_false_after_completion(scan_service: ScanService) -> None:
    await scan_service.scan_one_file(SCAN_REQUEST)

    assert scan_service.is_scan_in_progress() is False


async def test_is_scan_in_progress_is_false_after_a_failure(
    scan_service: ScanService, output_service: RecordingScanOutputService
) -> None:
    output_service.capacity_failure = InsufficientStorageError("disk almost full")
    with pytest.raises(InsufficientStorageError):
        await scan_service.scan_one_file(SCAN_REQUEST)

    assert scan_service.is_scan_in_progress() is False
```

- [ ] **Passo 10: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/services/test_scan_service.py::test_scan_one_file_returns_the_stored_result -v`

Expected: erro de coleta, `1 error`, com `ModuleNotFoundError: No module named 'digitalizadora.services.scan_service'`.

- [ ] **Passo 11: Implementar o mínimo**

Crie `src/digitalizadora/services/scan_service.py`. O `begin_scan` fica fora do `try` de propósito: um segundo gatilho recebe `ScanAlreadyRunningError` sem mexer no estado do scan em curso.

```python
import asyncio
import logging

from digitalizadora.domain.errors import DigitalizadoraError
from digitalizadora.domain.ports import ScannerGatewayProvider
from digitalizadora.domain.scan_job import ScanJob
from digitalizadora.domain.scan_progress import ScanPhase
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.services.scan_output_service import ScanOutputService
from digitalizadora.services.scan_progress_tracker import ScanProgressTracker

logger = logging.getLogger(__name__)


class ScanService:
    def __init__(
        self,
        gateway_provider: ScannerGatewayProvider,
        scan_output_service: ScanOutputService,
        progress_tracker: ScanProgressTracker,
    ) -> None:
        self._gateway_provider = gateway_provider
        self._scan_output_service = scan_output_service
        self._progress_tracker = progress_tracker

    def is_scan_in_progress(self) -> bool:
        return self._progress_tracker.snapshot().phase is not ScanPhase.IDLE

    async def scan_one_file(self, request: ScanRequest) -> ScanResult:
        # Outside the try: a rejected second scan must not touch the state of the running one.
        job = self._progress_tracker.begin_scan(request)
        try:
            return await self._scan_and_store(job)
        except DigitalizadoraError as error:
            self._progress_tracker.mark_failed(error.code)
            raise
        except Exception:
            logger.exception("Unexpected failure while scanning")
            self._progress_tracker.mark_failed(DigitalizadoraError.code)
            raise

    async def _scan_and_store(self, job: ScanJob) -> ScanResult:
        self._scan_output_service.ensure_capacity(job.request)
        gateway = await self._gateway_provider.acquire_gateway()
        self._progress_tracker.mark_scanning()
        scanned_image = await gateway.scan_page(job.request.settings)
        self._progress_tracker.mark_saving()
        stored_scan = await asyncio.to_thread(self._scan_output_service.store, scanned_image, job)
        self._progress_tracker.mark_completed(stored_scan)
        return stored_scan.result
```

- [ ] **Passo 12: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/services/test_scan_service.py -v`

Expected: `26 passed`.

#### Ciclo 4: ApplicationStateService

- [ ] **Passo 13: Escrever o teste que falha**

Crie `tests/services/test_application_state_service.py`:

```python
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_progress import ScanPhase
from digitalizadora.services.application_state_service import (
    ApplicationStateService,
    StorageState,
)
from digitalizadora.services.scan_progress_tracker import ScanProgressTracker
from digitalizadora.services.storage_guard_service import StorageGuardService
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.in_memory_settings_repository import InMemoryApplicationSettingsRepository

STARTED_AT = datetime(2026, 10, 13, 15, 30, 12, tzinfo=timezone(timedelta(hours=-3)))
OUTPUT_FOLDER = Path("/Volumes/External/scans")
FREE_SPACE_IN_BYTES = 50 * 1024**3
SETTINGS = ApplicationSettings(
    output_folder=OUTPUT_FOLDER,
    output_format=OutputFormat.PDF,
    scan_preset=ScanPreset.DOCUMENT,
)


class RecordingFreeSpaceReader:
    def __init__(self, free_space_in_bytes: int) -> None:
        self._free_space_in_bytes = free_space_in_bytes
        self.folders: list[Path] = []

    def __call__(self, folder: Path) -> int:
        self.folders.append(folder)
        return self._free_space_in_bytes


@pytest.fixture
def progress_tracker() -> ScanProgressTracker:
    return ScanProgressTracker(FixedClock(STARTED_AT))


@pytest.fixture
def settings_repository() -> InMemoryApplicationSettingsRepository:
    return InMemoryApplicationSettingsRepository(SETTINGS)


@pytest.fixture
def free_space_reader() -> RecordingFreeSpaceReader:
    return RecordingFreeSpaceReader(FREE_SPACE_IN_BYTES)


@pytest.fixture
def storage_guard_service(free_space_reader: RecordingFreeSpaceReader) -> StorageGuardService:
    return StorageGuardService(free_space_reader)


@pytest.fixture
def state_service(
    progress_tracker: ScanProgressTracker,
    settings_repository: InMemoryApplicationSettingsRepository,
    storage_guard_service: StorageGuardService,
) -> ApplicationStateService:
    return ApplicationStateService(progress_tracker, settings_repository, storage_guard_service)


def test_state_contains_the_tracker_snapshot(
    state_service: ApplicationStateService, progress_tracker: ScanProgressTracker
) -> None:
    progress_tracker.begin_scan(SETTINGS.to_scan_request())
    progress_tracker.mark_scanning()

    state = state_service.build_state()

    assert state.snapshot == progress_tracker.snapshot()
    assert state.snapshot.phase is ScanPhase.SCANNING


def test_state_contains_the_saved_settings(state_service: ApplicationStateService) -> None:
    assert state_service.build_state().settings == SETTINGS


def test_state_reflects_settings_saved_after_the_service_was_built(
    state_service: ApplicationStateService,
    settings_repository: InMemoryApplicationSettingsRepository,
) -> None:
    photo_settings = ApplicationSettings(
        output_folder=OUTPUT_FOLDER,
        output_format=OutputFormat.JPEG,
        scan_preset=ScanPreset.PHOTO,
    )
    settings_repository.save(photo_settings)

    assert state_service.build_state().settings == photo_settings


def test_state_reports_the_free_space_of_the_output_folder(
    state_service: ApplicationStateService, free_space_reader: RecordingFreeSpaceReader
) -> None:
    state = state_service.build_state()

    assert state.storage.free_space_in_bytes == FREE_SPACE_IN_BYTES
    assert set(free_space_reader.folders) == {OUTPUT_FOLDER}


def test_state_estimates_pages_for_the_selected_preset(
    state_service: ApplicationStateService, storage_guard_service: StorageGuardService
) -> None:
    expected_pages = storage_guard_service.estimate_pages_remaining(
        OUTPUT_FOLDER, ScanPreset.DOCUMENT.settings
    )

    state = state_service.build_state()

    assert state.storage == StorageState(
        free_space_in_bytes=FREE_SPACE_IN_BYTES, estimated_pages_remaining=expected_pages
    )


def test_a_heavier_preset_leaves_fewer_estimated_pages(
    state_service: ApplicationStateService,
    settings_repository: InMemoryApplicationSettingsRepository,
) -> None:
    settings_repository.save(
        ApplicationSettings(OUTPUT_FOLDER, OutputFormat.PDF, ScanPreset.DOCUMENT_ECONOMY)
    )
    economy_pages = state_service.build_state().storage.estimated_pages_remaining
    settings_repository.save(ApplicationSettings(OUTPUT_FOLDER, OutputFormat.PDF, ScanPreset.PHOTO))

    photo_pages = state_service.build_state().storage.estimated_pages_remaining

    assert photo_pages < economy_pages
```

- [ ] **Passo 14: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/services/test_application_state_service.py::test_state_contains_the_saved_settings -v`

Expected: erro de coleta, `1 error`, com `ModuleNotFoundError: No module named 'digitalizadora.services.application_state_service'`.

- [ ] **Passo 15: Implementar o mínimo**

Crie `src/digitalizadora/services/application_state_service.py`:

```python
from dataclasses import dataclass

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.ports import ApplicationSettingsRepository
from digitalizadora.domain.scan_progress import ScanProgressSnapshot
from digitalizadora.services.scan_progress_tracker import ScanProgressTracker
from digitalizadora.services.storage_guard_service import StorageGuardService


@dataclass(frozen=True)
class StorageState:
    free_space_in_bytes: int
    estimated_pages_remaining: int


@dataclass(frozen=True)
class ApplicationState:
    snapshot: ScanProgressSnapshot
    settings: ApplicationSettings
    storage: StorageState


class ApplicationStateService:
    def __init__(
        self,
        progress_tracker: ScanProgressTracker,
        settings_repository: ApplicationSettingsRepository,
        storage_guard_service: StorageGuardService,
    ) -> None:
        self._progress_tracker = progress_tracker
        self._settings_repository = settings_repository
        self._storage_guard_service = storage_guard_service

    def build_state(self) -> ApplicationState:
        settings = self._settings_repository.load()
        folder = settings.output_folder
        storage = StorageState(
            free_space_in_bytes=self._storage_guard_service.free_space_in_bytes(folder),
            estimated_pages_remaining=self._storage_guard_service.estimate_pages_remaining(
                folder, settings.scan_preset.settings
            ),
        )
        return ApplicationState(
            snapshot=self._progress_tracker.snapshot(),
            settings=settings,
            storage=storage,
        )
```

- [ ] **Passo 16: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/services/test_application_state_service.py -v`

Expected: `6 passed`.

- [ ] **Passo 17: Rodar tudo da tarefa e fazer o commit**

Run: `.venv/bin/pytest tests/services/test_scan_progress_tracker.py tests/fakes/test_scripted_scanner_gateway.py tests/services/test_scan_service.py tests/services/test_application_state_service.py -v`

Expected: `62 passed`, cada teste em menos de 100 ms.

Run:

```bash
git add src/digitalizadora/services/scan_progress_tracker.py src/digitalizadora/services/scan_service.py src/digitalizadora/services/application_state_service.py tests/fakes/scripted_scanner_gateway.py tests/fakes/test_scripted_scanner_gateway.py tests/services/test_scan_progress_tracker.py tests/services/test_scan_service.py tests/services/test_application_state_service.py
git commit -m "feat: add scan progress tracker, scan service and application state service"
```

### Task 11: Serviço de ajustes, catálogo de erros, guarda de requisições, controllers e fábrica da aplicação

**Objetivo:** Expor a API local (controllers finos, guarda contra DNS rebinding e CSRF, mensagens em português) e montar a aplicação FastAPI em `create_application`.

**Files:**
- Create: `src/digitalizadora/services/application_settings_service.py`
- Create: `src/digitalizadora/controllers/error_message_catalog.py`
- Create: `src/digitalizadora/controllers/local_request_guard.py`
- Create: `src/digitalizadora/controllers/settings_controller.py`
- Create: `src/digitalizadora/controllers/scan_controller.py`
- Create: `src/digitalizadora/controllers/state_controller.py`
- Create: `src/digitalizadora/controllers/printer_controller.py`
- Create: `src/digitalizadora/controllers/preview_controller.py`
- Create: `src/digitalizadora/application_factory.py`
- Create: `tests/controllers/controller_test_support.py`
- Test: `tests/services/test_application_settings_service.py`
- Test: `tests/controllers/test_error_message_catalog.py`
- Test: `tests/controllers/test_local_request_guard.py`
- Test: `tests/controllers/test_settings_controller.py`
- Test: `tests/controllers/test_scan_controller.py`
- Test: `tests/controllers/test_state_controller.py`
- Test: `tests/controllers/test_printer_controller.py`
- Test: `tests/controllers/test_preview_controller.py`
- Test: `tests/controllers/test_application_factory.py`

**Interfaces:**
- Consumes (Task 2): modelos, enums e erros do domínio (`ApplicationSettings`, `OutputFormat`, `ScanPreset`, `ScanRequest`, `ScanResult`, `StoredScan`, `ScanProgressSnapshot`, `ScanPhase`, `ScannerState`, `DigitalizadoraError` e subclasses), `ApplicationSettingsRepository`, `tests.fakes.fixed_clock.FixedClock`, `tests.fakes.sample_images.build_sample_jpeg()`.
- Consumes (Task 7): `tests.fakes.in_memory_settings_repository.InMemoryApplicationSettingsRepository(settings)`.
- Consumes (Task 8): `StorageGuardService(free_space_reader)` de `digitalizadora.services.storage_guard_service`.
- Consumes (Task 9): `PrinterConnectionService` (`check_connection()`, `refresh()`, `use_manual_address(base_address)`) e `PrinterConnectionState(connected, display_name, scanner_state, error_code)` de `digitalizadora.services.printer_connection_service`.
- Consumes (Task 10): `ScanService` (`is_scan_in_progress()`, `scan_one_file(request)`), `ScanProgressTracker`, `ApplicationStateService`, `ApplicationState`, `StorageState`.
- Produces (contrato 6.4): `SettingsUpdate(output_folder, output_format, scan_preset)`, `prepare_output_folder(folder)`, `ApplicationSettingsService(settings_repository, folder_preparer)` com `current()` e `update(update)`.
- Produces (contrato 6.5): `ErrorMessageCatalog().message_for(error_code)`; `REQUIRED_HEADER_NAME`, `REQUIRED_HEADER_VALUE`, `LocalRequestGuard(app, allowed_hosts)`; `ScanController`, `StateController`, `SettingsController`, `PrinterController`, `PreviewController`, todos com `build_router() -> APIRouter` e os construtores do contrato; `ApplicationControllers`, `WebInterfaceConfiguration`, `create_application(controllers, web_configuration) -> FastAPI`.
- Produces (adições compatíveis, sem alterar o contrato): em `error_message_catalog.py`, `ERROR_MESSAGES` (mapa somente leitura código para mensagem) e `build_error_body(error_message_catalog, error_code) -> dict[str, str]` (o formato `{"code", "message"}` de todas as respostas de erro); em `settings_controller.py`, `build_settings_body(settings) -> dict[str, str]`; em `local_request_guard.py`, `STATE_CHANGING_METHODS`; em `application_settings_service.py`, `WRITE_PROBE_FILE_NAME`.
- Produces (apoio de teste): `tests/controllers/controller_test_support.py` com `TEST_BASE_ADDRESS`, `STATE_CHANGING_HEADERS`, `SCANNED_AT`, `build_test_client(router) -> TestClient`, `StubScanService` e `StubPrinterConnectionService`. Não é um módulo de teste (o nome não começa com `test_`); só existe para evitar duplicar esses dublês entre os testes de controllers e da fábrica.

Cobertura do Review Focus: modo (2) 409 do `ScanController`, cabeçalho obrigatório no `LocalRequestGuard` e na fábrica; modo (3) `prepare_output_folder` (pasta inexistente criada, sem permissão, caminho sob um arquivo) e `OutputFolderUnavailableError` virando 422 no `SettingsController`.

#### Ciclo 1: ErrorMessageCatalog

- [ ] **Passo 1: Escrever o teste que falha**

Crie `tests/controllers/test_error_message_catalog.py` (os textos são os da seção 4.4 da especificação, copiados literalmente):

```python
import pytest

from digitalizadora.controllers.error_message_catalog import (
    ERROR_MESSAGES,
    ErrorMessageCatalog,
    build_error_body,
)
from digitalizadora.domain.errors import DigitalizadoraError

EXPECTED_MESSAGES = {
    "scanner_unreachable": (
        "Não encontrei a impressora. Confira se está ligada, com a luz do Wi-Fi acesa "
        "e na mesma rede do Mac (2,4 GHz)."
    ),
    "local_network_blocked": (
        "O macOS pode estar bloqueando o acesso à rede local. Abra o Digitalizadora pelo "
        "Terminal.app (duplo clique no arquivo .command) e confira Ajustes > Privacidade "
        "e Segurança > Rede Local."
    ),
    "scanner_busy": "A impressora está ocupada. Aguarde alguns segundos e tente de novo.",
    "scan_rejected": "A impressora recusou os ajustes desta digitalização.",
    "scan_failed": "A digitalização falhou. Confira se a tampa está fechada e tente de novo.",
    "scan_timed_out": "A impressora demorou demais para responder.",
    "scan_already_running": "Já existe uma digitalização em andamento.",
    "insufficient_storage": (
        "Pouco espaço livre na pasta de saída. Use um disco externo ou libere espaço."
    ),
    "output_folder_unavailable": (
        "Não consigo gravar na pasta de saída. Se for um disco externo, confira se está "
        "conectado."
    ),
    "invalid_settings": "Ajustes inválidos.",
    "unexpected_error": (
        "Algo inesperado aconteceu. Veja o registro em ~/Library/Logs/Digitalizadora."
    ),
}


def collect_error_classes(root: type[DigitalizadoraError]) -> list[type[DigitalizadoraError]]:
    collected = [root]
    for subclass in root.__subclasses__():
        collected.extend(collect_error_classes(subclass))
    return collected


@pytest.fixture
def catalog() -> ErrorMessageCatalog:
    return ErrorMessageCatalog()


def test_the_catalog_has_exactly_the_eleven_messages_of_the_specification() -> None:
    assert len(EXPECTED_MESSAGES) == 11
    assert dict(ERROR_MESSAGES) == EXPECTED_MESSAGES


@pytest.mark.parametrize("error_code", sorted(EXPECTED_MESSAGES))
def test_message_for_returns_the_verbatim_message(
    catalog: ErrorMessageCatalog, error_code: str
) -> None:
    assert catalog.message_for(error_code) == EXPECTED_MESSAGES[error_code]


def test_unknown_code_returns_the_unexpected_error_message(catalog: ErrorMessageCatalog) -> None:
    assert catalog.message_for("code_nobody_defined") == EXPECTED_MESSAGES["unexpected_error"]


def test_empty_code_returns_the_unexpected_error_message(catalog: ErrorMessageCatalog) -> None:
    assert catalog.message_for("") == EXPECTED_MESSAGES["unexpected_error"]


def test_every_error_class_has_a_message_in_the_catalog() -> None:
    error_classes = collect_error_classes(DigitalizadoraError)

    assert len(error_classes) == 11
    codes_without_message = [
        error_class.__name__
        for error_class in error_classes
        if error_class.code not in ERROR_MESSAGES
    ]
    assert codes_without_message == []


def test_build_error_body_contains_code_and_message(catalog: ErrorMessageCatalog) -> None:
    body = build_error_body(catalog, "insufficient_storage")

    assert body == {
        "code": "insufficient_storage",
        "message": EXPECTED_MESSAGES["insufficient_storage"],
    }


def test_build_error_body_keeps_an_unknown_code_with_the_generic_message(
    catalog: ErrorMessageCatalog,
) -> None:
    body = build_error_body(catalog, "code_nobody_defined")

    assert body["code"] == "code_nobody_defined"
    assert body["message"] == EXPECTED_MESSAGES["unexpected_error"]
```

- [ ] **Passo 2: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/controllers/test_error_message_catalog.py::test_unknown_code_returns_the_unexpected_error_message -v`

Expected: erro de coleta, `1 error`, com `ModuleNotFoundError: No module named 'digitalizadora.controllers.error_message_catalog'`.

- [ ] **Passo 3: Implementar o mínimo**

Crie `src/digitalizadora/controllers/error_message_catalog.py`:

```python
from collections.abc import Mapping
from types import MappingProxyType

UNEXPECTED_ERROR_CODE = "unexpected_error"

ERROR_MESSAGES: Mapping[str, str] = MappingProxyType(
    {
        "scanner_unreachable": (
            "Não encontrei a impressora. Confira se está ligada, com a luz do Wi-Fi acesa "
            "e na mesma rede do Mac (2,4 GHz)."
        ),
        "local_network_blocked": (
            "O macOS pode estar bloqueando o acesso à rede local. Abra o Digitalizadora pelo "
            "Terminal.app (duplo clique no arquivo .command) e confira Ajustes > Privacidade "
            "e Segurança > Rede Local."
        ),
        "scanner_busy": "A impressora está ocupada. Aguarde alguns segundos e tente de novo.",
        "scan_rejected": "A impressora recusou os ajustes desta digitalização.",
        "scan_failed": (
            "A digitalização falhou. Confira se a tampa está fechada e tente de novo."
        ),
        "scan_timed_out": "A impressora demorou demais para responder.",
        "scan_already_running": "Já existe uma digitalização em andamento.",
        "insufficient_storage": (
            "Pouco espaço livre na pasta de saída. Use um disco externo ou libere espaço."
        ),
        "output_folder_unavailable": (
            "Não consigo gravar na pasta de saída. Se for um disco externo, confira se está "
            "conectado."
        ),
        "invalid_settings": "Ajustes inválidos.",
        UNEXPECTED_ERROR_CODE: (
            "Algo inesperado aconteceu. Veja o registro em ~/Library/Logs/Digitalizadora."
        ),
    }
)


class ErrorMessageCatalog:
    def message_for(self, error_code: str) -> str:
        return ERROR_MESSAGES.get(error_code, ERROR_MESSAGES[UNEXPECTED_ERROR_CODE])


def build_error_body(error_message_catalog: ErrorMessageCatalog, error_code: str) -> dict[str, str]:
    return {"code": error_code, "message": error_message_catalog.message_for(error_code)}
```

- [ ] **Passo 4: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/controllers/test_error_message_catalog.py -v`

Expected: `17 passed`.

#### Ciclo 2: prepare_output_folder e ApplicationSettingsService

- [ ] **Passo 5: Escrever o teste que falha**

Crie `tests/services/test_application_settings_service.py`:

```python
from pathlib import Path

import pytest

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.errors import InvalidSettingsError, OutputFolderUnavailableError
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.services.application_settings_service import (
    WRITE_PROBE_FILE_NAME,
    ApplicationSettingsService,
    SettingsUpdate,
    prepare_output_folder,
)
from tests.fakes.in_memory_settings_repository import InMemoryApplicationSettingsRepository

INITIAL_SETTINGS = ApplicationSettings(
    output_folder=Path("/Volumes/Initial/scans"),
    output_format=OutputFormat.PDF,
    scan_preset=ScanPreset.DOCUMENT,
)


class RecordingFolderPreparer:
    def __init__(self) -> None:
        self.prepared_folders: list[Path] = []
        self.failure: Exception | None = None

    def __call__(self, folder: Path) -> None:
        self.prepared_folders.append(folder)
        if self.failure is not None:
            raise self.failure


def build_update(
    output_folder: str = "/Volumes/External/scans",
    output_format: str = "jpg",
    scan_preset: str = "photo",
) -> SettingsUpdate:
    return SettingsUpdate(
        output_folder=output_folder, output_format=output_format, scan_preset=scan_preset
    )


@pytest.fixture
def settings_repository() -> InMemoryApplicationSettingsRepository:
    return InMemoryApplicationSettingsRepository(INITIAL_SETTINGS)


@pytest.fixture
def folder_preparer() -> RecordingFolderPreparer:
    return RecordingFolderPreparer()


@pytest.fixture
def settings_service(
    settings_repository: InMemoryApplicationSettingsRepository,
    folder_preparer: RecordingFolderPreparer,
) -> ApplicationSettingsService:
    return ApplicationSettingsService(settings_repository, folder_preparer)


def test_prepare_output_folder_creates_missing_parent_folders(tmp_path: Path) -> None:
    folder = tmp_path / "external" / "scans"

    prepare_output_folder(folder)

    assert folder.is_dir()


def test_prepare_output_folder_accepts_an_existing_folder(tmp_path: Path) -> None:
    prepare_output_folder(tmp_path)

    assert tmp_path.is_dir()


def test_prepare_output_folder_leaves_no_probe_file_behind(tmp_path: Path) -> None:
    prepare_output_folder(tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_prepare_output_folder_keeps_existing_files(tmp_path: Path) -> None:
    existing_file = tmp_path / "2026-10-13_00001.pdf"
    existing_file.write_bytes(b"pdf")

    prepare_output_folder(tmp_path)

    assert existing_file.read_bytes() == b"pdf"


def test_prepare_output_folder_rejects_a_path_below_a_regular_file(tmp_path: Path) -> None:
    blocking_file = tmp_path / "not-a-folder"
    blocking_file.write_bytes(b"x")

    with pytest.raises(OutputFolderUnavailableError):
        prepare_output_folder(blocking_file / "scans")


def test_prepare_output_folder_turns_permission_error_into_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def deny_mkdir(self: Path, *arguments: object, **options: object) -> None:
        raise PermissionError("read-only volume")

    monkeypatch.setattr(Path, "mkdir", deny_mkdir)

    with pytest.raises(OutputFolderUnavailableError):
        prepare_output_folder(tmp_path / "scans")


def test_prepare_output_folder_rejects_a_folder_that_cannot_be_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def deny_write(self: Path, content: bytes) -> int:
        raise PermissionError("read-only volume")

    monkeypatch.setattr(Path, "write_bytes", deny_write)

    with pytest.raises(OutputFolderUnavailableError):
        prepare_output_folder(tmp_path)


def test_probe_file_name_is_hidden() -> None:
    assert WRITE_PROBE_FILE_NAME.startswith(".")


def test_current_returns_the_saved_settings(settings_service: ApplicationSettingsService) -> None:
    assert settings_service.current() == INITIAL_SETTINGS


def test_update_returns_the_new_settings(settings_service: ApplicationSettingsService) -> None:
    saved = settings_service.update(build_update())

    assert saved == ApplicationSettings(
        output_folder=Path("/Volumes/External/scans"),
        output_format=OutputFormat.JPEG,
        scan_preset=ScanPreset.PHOTO,
    )


def test_update_saves_the_new_settings(
    settings_service: ApplicationSettingsService,
    settings_repository: InMemoryApplicationSettingsRepository,
) -> None:
    saved = settings_service.update(build_update())

    assert settings_repository.load() == saved


def test_update_prepares_the_output_folder(
    settings_service: ApplicationSettingsService, folder_preparer: RecordingFolderPreparer
) -> None:
    settings_service.update(build_update(output_folder="/Volumes/External/scans"))

    assert folder_preparer.prepared_folders == [Path("/Volumes/External/scans")]


@pytest.fixture
def home_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_update_expands_the_home_folder_marker(
    settings_service: ApplicationSettingsService, home_folder: Path
) -> None:
    saved = settings_service.update(build_update(output_folder="~/Pictures/Digitalizadora"))

    assert saved.output_folder == home_folder / "Pictures" / "Digitalizadora"


def test_update_prepares_the_expanded_home_folder(
    settings_service: ApplicationSettingsService,
    folder_preparer: RecordingFolderPreparer,
    home_folder: Path,
) -> None:
    settings_service.update(build_update(output_folder="~/Pictures/Digitalizadora"))

    assert folder_preparer.prepared_folders == [home_folder / "Pictures" / "Digitalizadora"]


@pytest.mark.parametrize("relative_folder", ["scans", "./scans", "../scans", ""])
def test_update_rejects_a_relative_output_folder(
    settings_service: ApplicationSettingsService, relative_folder: str
) -> None:
    with pytest.raises(InvalidSettingsError):
        settings_service.update(build_update(output_folder=relative_folder))


def test_update_rejects_an_unknown_output_format(
    settings_service: ApplicationSettingsService,
) -> None:
    with pytest.raises(InvalidSettingsError):
        settings_service.update(build_update(output_format="tiff"))


def test_update_rejects_an_unknown_scan_preset(
    settings_service: ApplicationSettingsService,
) -> None:
    with pytest.raises(InvalidSettingsError):
        settings_service.update(build_update(scan_preset="poster"))


def test_update_accepts_every_known_format_and_preset(
    settings_service: ApplicationSettingsService,
) -> None:
    for output_format in OutputFormat:
        for scan_preset in ScanPreset:
            saved = settings_service.update(
                build_update(output_format=output_format.value, scan_preset=scan_preset.value)
            )
            assert (saved.output_format, saved.scan_preset) == (output_format, scan_preset)


INVALID_UPDATES = [
    build_update(output_format="tiff"),
    build_update(scan_preset="poster"),
    build_update(output_folder="relative/scans"),
]


@pytest.mark.parametrize("invalid_update", INVALID_UPDATES)
def test_invalid_update_saves_nothing(
    settings_service: ApplicationSettingsService,
    settings_repository: InMemoryApplicationSettingsRepository,
    invalid_update: SettingsUpdate,
) -> None:
    with pytest.raises(InvalidSettingsError):
        settings_service.update(invalid_update)

    assert settings_repository.load() == INITIAL_SETTINGS


@pytest.mark.parametrize("invalid_update", INVALID_UPDATES)
def test_invalid_update_prepares_no_folder(
    settings_service: ApplicationSettingsService,
    folder_preparer: RecordingFolderPreparer,
    invalid_update: SettingsUpdate,
) -> None:
    with pytest.raises(InvalidSettingsError):
        settings_service.update(invalid_update)

    assert folder_preparer.prepared_folders == []


def test_unavailable_folder_propagates_and_saves_nothing(
    settings_service: ApplicationSettingsService,
    settings_repository: InMemoryApplicationSettingsRepository,
    folder_preparer: RecordingFolderPreparer,
) -> None:
    folder_preparer.failure = OutputFolderUnavailableError("volume disconnected")

    with pytest.raises(OutputFolderUnavailableError):
        settings_service.update(build_update())

    assert settings_repository.load() == INITIAL_SETTINGS
```

- [ ] **Passo 6: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/services/test_application_settings_service.py::test_current_returns_the_saved_settings -v`

Expected: erro de coleta, `1 error`, com `ModuleNotFoundError: No module named 'digitalizadora.services.application_settings_service'`.

- [ ] **Passo 7: Implementar o mínimo**

Crie `src/digitalizadora/services/application_settings_service.py`. `PermissionError` é subclasse de `OSError`, então o `except OSError` cobre os dois casos do contrato. O formato e o preset são validados antes da pasta, e nada é salvo antes de tudo estar válido.

```python
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TypeVar

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.errors import InvalidSettingsError, OutputFolderUnavailableError
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.ports import ApplicationSettingsRepository
from digitalizadora.domain.scan_preset import ScanPreset

WRITE_PROBE_FILE_NAME = ".digitalizadora-write-probe"

EnumMember = TypeVar("EnumMember", bound=Enum)


@dataclass(frozen=True)
class SettingsUpdate:
    output_folder: str
    output_format: str
    scan_preset: str


def prepare_output_folder(folder: Path) -> None:
    probe_file = folder / WRITE_PROBE_FILE_NAME
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe_file.write_bytes(b"")
        probe_file.unlink()
    except OSError as error:
        raise OutputFolderUnavailableError(f"Cannot write to {folder}: {error}") from error


def parse_enum_member(
    enum_type: type[EnumMember], raw_value: str, field_label: str
) -> EnumMember:
    try:
        return enum_type(raw_value)
    except ValueError as error:
        raise InvalidSettingsError(f"Unsupported {field_label}: {raw_value!r}") from error


def parse_output_folder(raw_folder: str) -> Path:
    folder = Path(raw_folder).expanduser()
    if not folder.is_absolute():
        raise InvalidSettingsError(f"Output folder must be an absolute path: {raw_folder!r}")
    return folder


class ApplicationSettingsService:
    def __init__(
        self,
        settings_repository: ApplicationSettingsRepository,
        folder_preparer: Callable[[Path], None] = prepare_output_folder,
    ) -> None:
        self._settings_repository = settings_repository
        self._folder_preparer = folder_preparer

    def current(self) -> ApplicationSettings:
        return self._settings_repository.load()

    def update(self, update: SettingsUpdate) -> ApplicationSettings:
        output_format = parse_enum_member(OutputFormat, update.output_format, "output format")
        scan_preset = parse_enum_member(ScanPreset, update.scan_preset, "scan preset")
        output_folder = parse_output_folder(update.output_folder)
        self._folder_preparer(output_folder)
        settings = ApplicationSettings(
            output_folder=output_folder,
            output_format=output_format,
            scan_preset=scan_preset,
        )
        self._settings_repository.save(settings)
        return settings
```

- [ ] **Passo 8: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/services/test_application_settings_service.py -v`

Expected: `28 passed`.

#### Ciclo 3: LocalRequestGuard

- [ ] **Passo 9: Escrever o teste que falha**

Crie `tests/controllers/test_local_request_guard.py`:

```python
from http import HTTPStatus

import httpx
import pytest
from starlette.types import Receive, Scope, Send

from digitalizadora.controllers.local_request_guard import (
    REQUIRED_HEADER_NAME,
    REQUIRED_HEADER_VALUE,
    LocalRequestGuard,
)

ALLOWED_HOSTS = frozenset({"127.0.0.1:8765", "localhost:8765"})
INNER_BODY = b"inner application reached"


class RecordingApplication:
    def __init__(self) -> None:
        self.scope_types: list[str] = []

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.scope_types.append(scope["type"])
        if scope["type"] != "http":
            return
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": INNER_BODY})


class RecordingSend:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    async def __call__(self, message: dict[str, object]) -> None:
        self.messages.append(message)


async def no_message() -> dict[str, object]:
    return {}


@pytest.fixture
def inner_application() -> RecordingApplication:
    return RecordingApplication()


@pytest.fixture
def guard(inner_application: RecordingApplication) -> LocalRequestGuard:
    return LocalRequestGuard(inner_application, ALLOWED_HOSTS)


async def send_request(
    guard: LocalRequestGuard, method: str, headers: dict[str, str]
) -> httpx.Response:
    transport = httpx.ASGITransport(app=guard)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8765") as client:
        return await client.request(method, "/anything", headers=headers)


async def test_allowed_host_reaches_the_application(guard: LocalRequestGuard) -> None:
    response = await send_request(guard, "GET", {"host": "127.0.0.1:8765"})

    assert response.status_code == HTTPStatus.OK
    assert response.content == INNER_BODY


async def test_localhost_with_the_right_port_is_allowed(guard: LocalRequestGuard) -> None:
    response = await send_request(guard, "GET", {"host": "localhost:8765"})

    assert response.status_code == HTTPStatus.OK


async def test_upper_case_host_matching_ignoring_case_is_allowed(guard: LocalRequestGuard) -> None:
    response = await send_request(guard, "GET", {"host": "LOCALHOST:8765"})

    assert response.status_code == HTTPStatus.OK


async def test_foreign_host_is_rejected_with_forbidden_host(
    guard: LocalRequestGuard, inner_application: RecordingApplication
) -> None:
    response = await send_request(guard, "GET", {"host": "evil.example"})

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()["code"] == "forbidden_host"
    assert response.json()["message"]
    assert inner_application.scope_types == []


async def test_same_host_with_another_port_is_rejected(guard: LocalRequestGuard) -> None:
    response = await send_request(guard, "GET", {"host": "127.0.0.1:9999"})

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()["code"] == "forbidden_host"


async def test_host_without_port_is_rejected(guard: LocalRequestGuard) -> None:
    response = await send_request(guard, "GET", {"host": "127.0.0.1"})

    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
async def test_state_changing_method_without_the_header_is_rejected(
    guard: LocalRequestGuard, method: str
) -> None:
    response = await send_request(guard, method, {"host": "127.0.0.1:8765"})

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()["code"] == "missing_request_header"


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
async def test_state_changing_method_with_the_header_passes(
    guard: LocalRequestGuard, method: str
) -> None:
    headers = {"host": "127.0.0.1:8765", REQUIRED_HEADER_NAME: REQUIRED_HEADER_VALUE}

    response = await send_request(guard, method, headers)

    assert response.status_code == HTTPStatus.OK


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
async def test_safe_method_without_the_header_passes(
    guard: LocalRequestGuard, method: str
) -> None:
    response = await send_request(guard, method, {"host": "127.0.0.1:8765"})

    assert response.status_code == HTTPStatus.OK


async def test_wrong_header_value_is_rejected(guard: LocalRequestGuard) -> None:
    headers = {"host": "127.0.0.1:8765", REQUIRED_HEADER_NAME: "something-else"}

    response = await send_request(guard, "POST", headers)

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()["code"] == "missing_request_header"


async def test_the_host_check_runs_before_the_header_check(guard: LocalRequestGuard) -> None:
    response = await send_request(guard, "POST", {"host": "evil.example"})

    assert response.json()["code"] == "forbidden_host"


async def test_websocket_with_a_foreign_host_is_closed(
    guard: LocalRequestGuard, inner_application: RecordingApplication
) -> None:
    recorded_send = RecordingSend()
    scope = {"type": "websocket", "headers": [(b"host", b"evil.example")]}

    await guard(scope, no_message, recorded_send)

    assert [message["type"] for message in recorded_send.messages] == ["websocket.close"]
    assert inner_application.scope_types == []


async def test_websocket_with_an_allowed_host_reaches_the_application(
    guard: LocalRequestGuard, inner_application: RecordingApplication
) -> None:
    scope = {"type": "websocket", "headers": [(b"host", b"127.0.0.1:8765")]}

    await guard(scope, no_message, RecordingSend())

    assert inner_application.scope_types == ["websocket"]


async def test_lifespan_scope_passes_through_without_headers(
    guard: LocalRequestGuard, inner_application: RecordingApplication
) -> None:
    await guard({"type": "lifespan"}, no_message, RecordingSend())

    assert inner_application.scope_types == ["lifespan"]
```

- [ ] **Passo 10: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/controllers/test_local_request_guard.py::test_allowed_host_reaches_the_application -v`

Expected: erro de coleta, `1 error`, com `ModuleNotFoundError: No module named 'digitalizadora.controllers.local_request_guard'`.

- [ ] **Passo 11: Implementar o mínimo**

Crie `src/digitalizadora/controllers/local_request_guard.py`. A comparação do `Host` é feita em minúsculas e inclui a porta; o cabeçalho `X-Requested-With` só é exigido em `http` com método que altera estado; `lifespan` passa direto; `websocket` fora da lista é fechado com o código 1008.

```python
from dataclasses import dataclass
from http import HTTPStatus

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

REQUIRED_HEADER_NAME = "x-requested-with"
REQUIRED_HEADER_VALUE = "digitalizadora"
STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
WEBSOCKET_POLICY_VIOLATION_CLOSE_CODE = 1008


@dataclass(frozen=True)
class Rejection:
    code: str
    message: str


FORBIDDEN_HOST = Rejection(
    code="forbidden_host",
    message="Acesso recusado: o endereço usado não é o da própria máquina.",
)
MISSING_REQUEST_HEADER = Rejection(
    code="missing_request_header",
    message="Requisição recusada: falta o cabeçalho X-Requested-With.",
)


class LocalRequestGuard:
    def __init__(self, app: ASGIApp, allowed_hosts: frozenset[str]) -> None:
        self._app = app
        self._allowed_hosts = frozenset(host.lower() for host in allowed_hosts)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        rejection = self._find_rejection(scope)
        if rejection is None:
            await self._app(scope, receive, send)
        elif scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": WEBSOCKET_POLICY_VIOLATION_CLOSE_CODE})
        else:
            response = JSONResponse(
                status_code=HTTPStatus.FORBIDDEN,
                content={"code": rejection.code, "message": rejection.message},
            )
            await response(scope, receive, send)

    def _find_rejection(self, scope: Scope) -> Rejection | None:
        if scope["type"] == "lifespan":
            return None
        headers = dict(scope["headers"])
        host = headers.get(b"host", b"").decode("latin-1").lower()
        if host not in self._allowed_hosts:
            return FORBIDDEN_HOST
        if scope["type"] == "http" and scope["method"] in STATE_CHANGING_METHODS:
            header_value = headers.get(REQUIRED_HEADER_NAME.encode("latin-1"), b"")
            if header_value.decode("latin-1") != REQUIRED_HEADER_VALUE:
                return MISSING_REQUEST_HEADER
        return None
```

- [ ] **Passo 12: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/controllers/test_local_request_guard.py -v`

Expected: `22 passed`.

#### Ciclo 4: apoio de teste e SettingsController

- [ ] **Passo 13: Criar o apoio de teste compartilhado**

Crie `tests/controllers/controller_test_support.py` (apenas dublês e um construtor de `TestClient`; não contém testes):

```python
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.services.printer_connection_service import PrinterConnectionState

TEST_BASE_ADDRESS = "http://127.0.0.1:8765"
STATE_CHANGING_HEADERS = {"X-Requested-With": "digitalizadora"}
SCANNED_AT = datetime(2026, 10, 13, 15, 30, 12, tzinfo=timezone(timedelta(hours=-3)))


def build_test_client(router: APIRouter) -> TestClient:
    application = FastAPI()
    application.include_router(router)
    return TestClient(application, base_url=TEST_BASE_ADDRESS)


class StubScanService:
    """Duck-typed stand-in for ScanService that records the requests it receives."""

    def __init__(self) -> None:
        self.in_progress = False
        self.failure: Exception | None = None
        self.requests: list[ScanRequest] = []

    def is_scan_in_progress(self) -> bool:
        return self.in_progress

    async def scan_one_file(self, request: ScanRequest) -> ScanResult:
        self.requests.append(request)
        if self.failure is not None:
            raise self.failure
        return ScanResult(
            output_path=Path("/Volumes/Scans/2026-10-13_00001.pdf"),
            output_format=request.output_format,
            scanned_at=SCANNED_AT,
            size_in_bytes=1234,
        )


class StubPrinterConnectionService:
    """Duck-typed stand-in for PrinterConnectionService."""

    def __init__(self, connection_state: PrinterConnectionState) -> None:
        self.connection_state = connection_state
        self.check_count = 0
        self.refresh_count = 0
        self.manual_addresses: list[str] = []

    async def check_connection(self) -> PrinterConnectionState:
        self.check_count += 1
        return self.connection_state

    async def refresh(self) -> PrinterConnectionState:
        self.refresh_count += 1
        return self.connection_state

    def use_manual_address(self, base_address: str) -> None:
        self.manual_addresses.append(base_address)
```

- [ ] **Passo 14: Escrever o teste que falha**

Crie `tests/controllers/test_settings_controller.py`:

```python
from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog
from digitalizadora.controllers.settings_controller import SettingsController
from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.errors import OutputFolderUnavailableError
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.services.application_settings_service import ApplicationSettingsService
from tests.controllers.controller_test_support import build_test_client
from tests.fakes.in_memory_settings_repository import InMemoryApplicationSettingsRepository

CATALOG = ErrorMessageCatalog()
INITIAL_SETTINGS = ApplicationSettings(
    output_folder=Path("/Volumes/Initial/scans"),
    output_format=OutputFormat.PDF,
    scan_preset=ScanPreset.DOCUMENT,
)
VALID_BODY = {
    "output_folder": "/Volumes/External/scans",
    "output_format": "jpg",
    "scan_preset": "photo",
}


class StubFolderPreparer:
    def __init__(self) -> None:
        self.failure: Exception | None = None

    def __call__(self, folder: Path) -> None:
        if self.failure is not None:
            raise self.failure


@pytest.fixture
def settings_repository() -> InMemoryApplicationSettingsRepository:
    return InMemoryApplicationSettingsRepository(INITIAL_SETTINGS)


@pytest.fixture
def folder_preparer() -> StubFolderPreparer:
    return StubFolderPreparer()


@pytest.fixture
def client(
    settings_repository: InMemoryApplicationSettingsRepository,
    folder_preparer: StubFolderPreparer,
) -> TestClient:
    settings_service = ApplicationSettingsService(settings_repository, folder_preparer)
    controller = SettingsController(settings_service, CATALOG)
    return build_test_client(controller.build_router())


def test_get_settings_returns_the_saved_settings(client: TestClient) -> None:
    response = client.get("/api/settings")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "output_folder": "/Volumes/Initial/scans",
        "output_format": "pdf",
        "scan_preset": "document",
    }


def test_put_settings_returns_the_new_settings(client: TestClient) -> None:
    response = client.put("/api/settings", json=VALID_BODY)

    assert response.status_code == HTTPStatus.OK
    assert response.json() == VALID_BODY


def test_put_settings_saves_the_new_settings(
    client: TestClient, settings_repository: InMemoryApplicationSettingsRepository
) -> None:
    client.put("/api/settings", json=VALID_BODY)

    assert settings_repository.load() == ApplicationSettings(
        output_folder=Path("/Volumes/External/scans"),
        output_format=OutputFormat.JPEG,
        scan_preset=ScanPreset.PHOTO,
    )


def test_put_settings_with_an_unknown_format_answers_422(client: TestClient) -> None:
    response = client.put("/api/settings", json={**VALID_BODY, "output_format": "tiff"})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json() == {
        "code": "invalid_settings",
        "message": CATALOG.message_for("invalid_settings"),
    }


def test_put_settings_with_a_relative_folder_answers_422(client: TestClient) -> None:
    response = client.put("/api/settings", json={**VALID_BODY, "output_folder": "scans"})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json()["code"] == "invalid_settings"


def test_put_settings_with_an_unavailable_folder_answers_422(
    client: TestClient, folder_preparer: StubFolderPreparer
) -> None:
    folder_preparer.failure = OutputFolderUnavailableError("volume disconnected")

    response = client.put("/api/settings", json=VALID_BODY)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json() == {
        "code": "output_folder_unavailable",
        "message": CATALOG.message_for("output_folder_unavailable"),
    }


def test_a_rejected_put_leaves_the_saved_settings_untouched(
    client: TestClient,
    settings_repository: InMemoryApplicationSettingsRepository,
) -> None:
    client.put("/api/settings", json={**VALID_BODY, "scan_preset": "poster"})

    assert settings_repository.load() == INITIAL_SETTINGS
```

- [ ] **Passo 15: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/controllers/test_settings_controller.py::test_get_settings_returns_the_saved_settings -v`

Expected: erro de coleta, `1 error`, com `ModuleNotFoundError: No module named 'digitalizadora.controllers.settings_controller'`.

- [ ] **Passo 16: Implementar o mínimo**

Crie `src/digitalizadora/controllers/settings_controller.py`:

```python
from http import HTTPStatus
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog, build_error_body
from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.errors import DigitalizadoraError
from digitalizadora.services.application_settings_service import (
    ApplicationSettingsService,
    SettingsUpdate,
)


class SettingsRequestBody(BaseModel):
    output_folder: str
    output_format: str
    scan_preset: str


def build_settings_body(settings: ApplicationSettings) -> dict[str, str]:
    return {
        "output_folder": str(settings.output_folder),
        "output_format": settings.output_format.value,
        "scan_preset": settings.scan_preset.value,
    }


class SettingsController:
    def __init__(
        self,
        settings_service: ApplicationSettingsService,
        error_message_catalog: ErrorMessageCatalog,
    ) -> None:
        self._settings_service = settings_service
        self._error_message_catalog = error_message_catalog

    def build_router(self) -> APIRouter:
        router = APIRouter()
        router.add_api_route("/api/settings", self.read_settings, methods=["GET"])
        router.add_api_route("/api/settings", self.update_settings, methods=["PUT"])
        return router

    async def read_settings(self) -> dict[str, Any]:
        return build_settings_body(self._settings_service.current())

    async def update_settings(self, body: SettingsRequestBody) -> JSONResponse:
        update = SettingsUpdate(
            output_folder=body.output_folder,
            output_format=body.output_format,
            scan_preset=body.scan_preset,
        )
        try:
            saved_settings = self._settings_service.update(update)
        except DigitalizadoraError as error:
            return JSONResponse(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                content=build_error_body(self._error_message_catalog, error.code),
            )
        return JSONResponse(content=build_settings_body(saved_settings))
```

- [ ] **Passo 17: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/controllers/test_settings_controller.py -v`

Expected: `7 passed`.

#### Ciclo 5: ScanController, StateController, PrinterController e PreviewController

- [ ] **Passo 18: Escrever os testes que falham**

Crie `tests/controllers/test_scan_controller.py`:

```python
import logging
from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog
from digitalizadora.controllers.scan_controller import ScanController
from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.errors import ScannerUnreachableError
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.services.application_settings_service import ApplicationSettingsService
from tests.controllers.controller_test_support import StubScanService, build_test_client
from tests.fakes.in_memory_settings_repository import InMemoryApplicationSettingsRepository

SETTINGS = ApplicationSettings(
    output_folder=Path("/Volumes/External/scans"),
    output_format=OutputFormat.JPEG,
    scan_preset=ScanPreset.PHOTO,
)
CATALOG = ErrorMessageCatalog()


@pytest.fixture
def scan_service() -> StubScanService:
    return StubScanService()


@pytest.fixture
def client(scan_service: StubScanService) -> TestClient:
    settings_service = ApplicationSettingsService(InMemoryApplicationSettingsRepository(SETTINGS))
    controller = ScanController(scan_service, settings_service, CATALOG)
    return build_test_client(controller.build_router())


def test_post_scans_answers_202_accepted(client: TestClient) -> None:
    response = client.post("/api/scans")

    assert response.status_code == HTTPStatus.ACCEPTED
    assert response.json() == {"accepted": True}


def test_post_scans_runs_one_scan_with_the_request_built_from_the_settings(
    client: TestClient, scan_service: StubScanService
) -> None:
    client.post("/api/scans")

    assert scan_service.requests == [SETTINGS.to_scan_request()]


def test_post_scans_answers_409_while_a_scan_is_running(
    client: TestClient, scan_service: StubScanService
) -> None:
    scan_service.in_progress = True

    response = client.post("/api/scans")

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json() == {
        "code": "scan_already_running",
        "message": CATALOG.message_for("scan_already_running"),
    }


def test_post_scans_does_not_start_a_scan_while_one_is_running(
    client: TestClient, scan_service: StubScanService
) -> None:
    scan_service.in_progress = True

    client.post("/api/scans")

    assert scan_service.requests == []


def test_a_scan_error_in_the_background_does_not_change_the_answer(
    client: TestClient, scan_service: StubScanService
) -> None:
    scan_service.failure = ScannerUnreachableError("printer offline")

    response = client.post("/api/scans")

    assert response.status_code == HTTPStatus.ACCEPTED


def test_a_scan_error_in_the_background_is_logged_with_its_code(
    client: TestClient, scan_service: StubScanService, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING)
    scan_service.failure = ScannerUnreachableError("printer offline")

    client.post("/api/scans")

    assert "scanner_unreachable" in caplog.text
```

Crie `tests/controllers/test_state_controller.py`:

```python
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog
from digitalizadora.controllers.state_controller import StateController
from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_progress import ScanPhase, ScanProgressSnapshot
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.services.application_state_service import ApplicationState, StorageState
from tests.controllers.controller_test_support import build_test_client

SCANNED_AT = datetime(2026, 10, 13, 15, 30, 12, tzinfo=timezone(timedelta(hours=-3)))
CATALOG = ErrorMessageCatalog()
SETTINGS = ApplicationSettings(
    output_folder=Path("/Volumes/External/scans"),
    output_format=OutputFormat.PDF,
    scan_preset=ScanPreset.DOCUMENT_ECONOMY,
)
STORAGE = StorageState(free_space_in_bytes=5_000_000_000, estimated_pages_remaining=1200)
LAST_RESULT = ScanResult(
    output_path=Path("/Volumes/External/scans/2026-10-13_00007.pdf"),
    output_format=OutputFormat.PDF,
    scanned_at=SCANNED_AT,
    size_in_bytes=734003,
)
IDLE_SNAPSHOT = ScanProgressSnapshot(
    phase=ScanPhase.IDLE, scans_completed=0, last_result=None, last_error_code=None
)


class StubApplicationStateService:
    def __init__(self, snapshot: ScanProgressSnapshot) -> None:
        self.snapshot = snapshot

    def build_state(self) -> ApplicationState:
        return ApplicationState(snapshot=self.snapshot, settings=SETTINGS, storage=STORAGE)


@pytest.fixture
def state_service() -> StubApplicationStateService:
    return StubApplicationStateService(IDLE_SNAPSHOT)


@pytest.fixture
def client(state_service: StubApplicationStateService) -> TestClient:
    controller = StateController(state_service, CATALOG)
    return build_test_client(controller.build_router())


def test_health_answers_ok(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "ok"}


def test_state_of_a_fresh_application(client: TestClient) -> None:
    body = client.get("/api/state").json()

    assert body["scan_phase"] == "idle"
    assert body["scans_completed"] == 0
    assert body["last_result"] is None
    assert body["last_error"] is None


def test_state_reports_the_current_phase(
    client: TestClient, state_service: StubApplicationStateService
) -> None:
    state_service.snapshot = ScanProgressSnapshot(
        phase=ScanPhase.SCANNING, scans_completed=3, last_result=None, last_error_code=None
    )

    body = client.get("/api/state").json()

    assert body["scan_phase"] == "scanning"
    assert body["scans_completed"] == 3


def test_state_describes_the_last_result(
    client: TestClient, state_service: StubApplicationStateService
) -> None:
    state_service.snapshot = ScanProgressSnapshot(
        phase=ScanPhase.IDLE, scans_completed=7, last_result=LAST_RESULT, last_error_code=None
    )

    body = client.get("/api/state").json()

    assert body["last_result"] == {
        "file_name": "2026-10-13_00007.pdf",
        "output_folder": "/Volumes/External/scans",
        "output_format": "pdf",
        "size_in_bytes": 734003,
        "scanned_at": "2026-10-13T15:30:12-03:00",
    }


def test_state_describes_the_last_error_with_the_catalog_message(
    client: TestClient, state_service: StubApplicationStateService
) -> None:
    state_service.snapshot = ScanProgressSnapshot(
        phase=ScanPhase.IDLE,
        scans_completed=0,
        last_result=None,
        last_error_code="insufficient_storage",
    )

    body = client.get("/api/state").json()

    assert body["last_error"] == {
        "code": "insufficient_storage",
        "message": CATALOG.message_for("insufficient_storage"),
    }


def test_state_uses_the_generic_message_for_an_unknown_error_code(
    client: TestClient, state_service: StubApplicationStateService
) -> None:
    state_service.snapshot = ScanProgressSnapshot(
        phase=ScanPhase.IDLE,
        scans_completed=0,
        last_result=None,
        last_error_code="never_heard_of_it",
    )

    body = client.get("/api/state").json()

    assert body["last_error"]["message"] == CATALOG.message_for("unexpected_error")


def test_state_contains_the_settings(client: TestClient) -> None:
    body = client.get("/api/state").json()

    assert body["settings"] == {
        "output_folder": "/Volumes/External/scans",
        "output_format": "pdf",
        "scan_preset": "document_economy",
    }


def test_state_contains_the_storage_figures(client: TestClient) -> None:
    body = client.get("/api/state").json()

    assert body["storage"] == {
        "free_space_in_bytes": 5_000_000_000,
        "estimated_pages_remaining": 1200,
    }


def test_state_has_exactly_the_documented_keys(client: TestClient) -> None:
    body = client.get("/api/state").json()

    assert set(body) == {
        "scan_phase",
        "scans_completed",
        "last_result",
        "last_error",
        "settings",
        "storage",
    }
```

Crie `tests/controllers/test_printer_controller.py`:

```python
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog
from digitalizadora.controllers.printer_controller import PrinterController
from digitalizadora.domain.scanner_status import ScannerState
from digitalizadora.services.printer_connection_service import PrinterConnectionState
from tests.controllers.controller_test_support import (
    StubPrinterConnectionService,
    build_test_client,
)

CATALOG = ErrorMessageCatalog()
CONNECTED_STATE = PrinterConnectionState(
    connected=True,
    display_name="HP DeskJet 2800 series [000001]",
    scanner_state=ScannerState.IDLE,
    error_code=None,
)
DISCONNECTED_STATE = PrinterConnectionState(
    connected=False,
    display_name=None,
    scanner_state=None,
    error_code="scanner_unreachable",
)
MANUAL_ADDRESS = "http://192.168.0.40:8080/eSCL"


@pytest.fixture
def printer_service() -> StubPrinterConnectionService:
    return StubPrinterConnectionService(CONNECTED_STATE)


@pytest.fixture
def client(printer_service: StubPrinterConnectionService) -> TestClient:
    controller = PrinterController(printer_service, CATALOG)
    return build_test_client(controller.build_router())


def test_get_printer_describes_a_connected_printer(client: TestClient) -> None:
    response = client.get("/api/printer")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "connected": True,
        "display_name": "HP DeskJet 2800 series [000001]",
        "scanner_state": "idle",
        "error": None,
    }


def test_get_printer_describes_a_missing_printer_with_the_catalog_message(
    client: TestClient, printer_service: StubPrinterConnectionService
) -> None:
    printer_service.connection_state = DISCONNECTED_STATE

    body = client.get("/api/printer").json()

    assert body == {
        "connected": False,
        "display_name": None,
        "scanner_state": None,
        "error": {
            "code": "scanner_unreachable",
            "message": CATALOG.message_for("scanner_unreachable"),
        },
    }


def test_get_printer_checks_the_connection_once(
    client: TestClient, printer_service: StubPrinterConnectionService
) -> None:
    client.get("/api/printer")

    assert printer_service.check_count == 1
    assert printer_service.refresh_count == 0


def test_refresh_searches_the_printer_again(
    client: TestClient, printer_service: StubPrinterConnectionService
) -> None:
    response = client.post("/api/printer/refresh")

    assert response.status_code == HTTPStatus.OK
    assert response.json()["connected"] is True
    assert printer_service.refresh_count == 1


def test_put_address_uses_the_manual_address_and_reports_the_connection(
    client: TestClient, printer_service: StubPrinterConnectionService
) -> None:
    response = client.put("/api/printer/address", json={"base_address": MANUAL_ADDRESS})

    assert response.status_code == HTTPStatus.OK
    assert response.json()["display_name"] == "HP DeskJet 2800 series [000001]"
    assert printer_service.manual_addresses == [MANUAL_ADDRESS]
    assert printer_service.check_count == 1


def test_put_address_ignores_surrounding_whitespace(
    client: TestClient, printer_service: StubPrinterConnectionService
) -> None:
    client.put("/api/printer/address", json={"base_address": f"  {MANUAL_ADDRESS}\n"})

    assert printer_service.manual_addresses == [MANUAL_ADDRESS]


@pytest.mark.parametrize(
    "invalid_address",
    ["", "   ", "192.168.0.40:8080/eSCL", "https://192.168.0.40/eSCL", "ftp://printer.local"],
)
def test_put_address_rejects_an_empty_or_non_http_address(
    client: TestClient, printer_service: StubPrinterConnectionService, invalid_address: str
) -> None:
    response = client.put("/api/printer/address", json={"base_address": invalid_address})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json() == {
        "code": "invalid_settings",
        "message": CATALOG.message_for("invalid_settings"),
    }
    assert printer_service.manual_addresses == []
```

Crie `tests/controllers/test_preview_controller.py`:

```python
from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from digitalizadora.controllers.preview_controller import PreviewController
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.domain.stored_scan import StoredScan
from digitalizadora.services.scan_progress_tracker import ScanProgressTracker
from tests.controllers.controller_test_support import SCANNED_AT, build_test_client
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.sample_images import build_sample_jpeg

SCAN_REQUEST = ScanRequest(settings=ScanPreset.DOCUMENT.settings, output_format=OutputFormat.PDF)


def build_stored_scan(thumbnail_jpeg: bytes) -> StoredScan:
    result = ScanResult(
        output_path=Path("/Volumes/Scans/2026-10-13_00001.pdf"),
        output_format=OutputFormat.PDF,
        scanned_at=SCANNED_AT,
        size_in_bytes=1234,
    )
    return StoredScan(result=result, thumbnail_jpeg=thumbnail_jpeg)


@pytest.fixture
def progress_tracker() -> ScanProgressTracker:
    return ScanProgressTracker(FixedClock(SCANNED_AT))


@pytest.fixture
def client(progress_tracker: ScanProgressTracker) -> TestClient:
    return build_test_client(PreviewController(progress_tracker).build_router())


def test_thumbnail_is_404_before_the_first_scan(client: TestClient) -> None:
    response = client.get("/api/scans/last/thumbnail")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_thumbnail_is_served_as_jpeg_after_a_scan(
    client: TestClient, progress_tracker: ScanProgressTracker
) -> None:
    thumbnail_jpeg = build_sample_jpeg()
    progress_tracker.begin_scan(SCAN_REQUEST)
    progress_tracker.mark_completed(build_stored_scan(thumbnail_jpeg))

    response = client.get("/api/scans/last/thumbnail")

    assert response.status_code == HTTPStatus.OK
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content == thumbnail_jpeg


def test_thumbnail_is_never_cached_by_the_browser(
    client: TestClient, progress_tracker: ScanProgressTracker
) -> None:
    progress_tracker.begin_scan(SCAN_REQUEST)
    progress_tracker.mark_completed(build_stored_scan(build_sample_jpeg()))

    response = client.get("/api/scans/last/thumbnail")

    assert response.headers["cache-control"] == "no-store"


def test_thumbnail_stays_available_after_a_later_failure(
    client: TestClient, progress_tracker: ScanProgressTracker
) -> None:
    thumbnail_jpeg = build_sample_jpeg()
    progress_tracker.begin_scan(SCAN_REQUEST)
    progress_tracker.mark_completed(build_stored_scan(thumbnail_jpeg))
    progress_tracker.begin_scan(SCAN_REQUEST)
    progress_tracker.mark_failed("scan_failed")

    response = client.get("/api/scans/last/thumbnail")

    assert response.content == thumbnail_jpeg
```

- [ ] **Passo 19: Rodar os testes e ver falhar**

Run: `.venv/bin/pytest tests/controllers/test_scan_controller.py tests/controllers/test_state_controller.py tests/controllers/test_printer_controller.py tests/controllers/test_preview_controller.py -v`

Expected: `4 errors` de coleta, um por arquivo, com `ModuleNotFoundError: No module named 'digitalizadora.controllers.scan_controller'` (e os equivalentes para `state_controller`, `printer_controller` e `preview_controller`).

- [ ] **Passo 20: Implementar o mínimo**

Crie `src/digitalizadora/controllers/scan_controller.py`. O `POST` só valida e agenda; a digitalização roda em `BackgroundTasks`, e o erro de domínio é apenas registrado no log porque o tracker já guarda o código que a página vai mostrar.

```python
import logging
from http import HTTPStatus

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse

from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog, build_error_body
from digitalizadora.domain.errors import DigitalizadoraError, ScanAlreadyRunningError
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.services.application_settings_service import ApplicationSettingsService
from digitalizadora.services.scan_service import ScanService

logger = logging.getLogger(__name__)


class ScanController:
    def __init__(
        self,
        scan_service: ScanService,
        settings_service: ApplicationSettingsService,
        error_message_catalog: ErrorMessageCatalog,
    ) -> None:
        self._scan_service = scan_service
        self._settings_service = settings_service
        self._error_message_catalog = error_message_catalog

    def build_router(self) -> APIRouter:
        router = APIRouter()
        router.add_api_route("/api/scans", self.start_scan, methods=["POST"])
        return router

    async def start_scan(self, background_tasks: BackgroundTasks) -> JSONResponse:
        if self._scan_service.is_scan_in_progress():
            return JSONResponse(
                status_code=HTTPStatus.CONFLICT,
                content=build_error_body(
                    self._error_message_catalog, ScanAlreadyRunningError.code
                ),
            )
        scan_request = self._settings_service.current().to_scan_request()
        background_tasks.add_task(self._run_scan, scan_request)
        return JSONResponse(status_code=HTTPStatus.ACCEPTED, content={"accepted": True})

    async def _run_scan(self, scan_request: ScanRequest) -> None:
        try:
            await self._scan_service.scan_one_file(scan_request)
        except DigitalizadoraError as error:
            # The progress tracker already holds the error code that the page will show.
            logger.warning("Scan failed with code %s: %s", error.code, error)
```

Crie `src/digitalizadora/controllers/state_controller.py`:

```python
from typing import Any

from fastapi import APIRouter

from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog, build_error_body
from digitalizadora.controllers.settings_controller import build_settings_body
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.services.application_state_service import (
    ApplicationState,
    ApplicationStateService,
)


class StateController:
    def __init__(
        self,
        state_service: ApplicationStateService,
        error_message_catalog: ErrorMessageCatalog,
    ) -> None:
        self._state_service = state_service
        self._error_message_catalog = error_message_catalog

    def build_router(self) -> APIRouter:
        router = APIRouter()
        router.add_api_route("/api/health", self.read_health, methods=["GET"])
        router.add_api_route("/api/state", self.read_state, methods=["GET"])
        return router

    async def read_health(self) -> dict[str, str]:
        return {"status": "ok"}

    async def read_state(self) -> dict[str, Any]:
        state = self._state_service.build_state()
        return {
            "scan_phase": state.snapshot.phase.value,
            "scans_completed": state.snapshot.scans_completed,
            "last_result": self._describe_last_result(state.snapshot.last_result),
            "last_error": self._describe_last_error(state),
            "settings": build_settings_body(state.settings),
            "storage": {
                "free_space_in_bytes": state.storage.free_space_in_bytes,
                "estimated_pages_remaining": state.storage.estimated_pages_remaining,
            },
        }

    @staticmethod
    def _describe_last_result(last_result: ScanResult | None) -> dict[str, Any] | None:
        if last_result is None:
            return None
        return {
            "file_name": last_result.output_path.name,
            "output_folder": str(last_result.output_path.parent),
            "output_format": last_result.output_format.value,
            "size_in_bytes": last_result.size_in_bytes,
            "scanned_at": last_result.scanned_at.isoformat(),
        }

    def _describe_last_error(self, state: ApplicationState) -> dict[str, str] | None:
        error_code = state.snapshot.last_error_code
        if error_code is None:
            return None
        return build_error_body(self._error_message_catalog, error_code)
```

Crie `src/digitalizadora/controllers/printer_controller.py`:

```python
from http import HTTPStatus
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog, build_error_body
from digitalizadora.domain.errors import InvalidSettingsError
from digitalizadora.services.printer_connection_service import (
    PrinterConnectionService,
    PrinterConnectionState,
)

MANUAL_ADDRESS_REQUIRED_PREFIX = "http://"


class PrinterAddressRequestBody(BaseModel):
    base_address: str


class PrinterController:
    def __init__(
        self,
        printer_connection_service: PrinterConnectionService,
        error_message_catalog: ErrorMessageCatalog,
    ) -> None:
        self._printer_connection_service = printer_connection_service
        self._error_message_catalog = error_message_catalog

    def build_router(self) -> APIRouter:
        router = APIRouter()
        router.add_api_route("/api/printer", self.read_printer, methods=["GET"])
        router.add_api_route("/api/printer/refresh", self.refresh_printer, methods=["POST"])
        router.add_api_route("/api/printer/address", self.update_printer_address, methods=["PUT"])
        return router

    async def read_printer(self) -> dict[str, Any]:
        return self._describe(await self._printer_connection_service.check_connection())

    async def refresh_printer(self) -> dict[str, Any]:
        return self._describe(await self._printer_connection_service.refresh())

    async def update_printer_address(self, body: PrinterAddressRequestBody) -> JSONResponse:
        base_address = body.base_address.strip()
        if not base_address.startswith(MANUAL_ADDRESS_REQUIRED_PREFIX):
            return JSONResponse(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                content=build_error_body(self._error_message_catalog, InvalidSettingsError.code),
            )
        self._printer_connection_service.use_manual_address(base_address)
        connection_state = await self._printer_connection_service.check_connection()
        return JSONResponse(content=self._describe(connection_state))

    def _describe(self, connection_state: PrinterConnectionState) -> dict[str, Any]:
        scanner_state = connection_state.scanner_state
        error_code = connection_state.error_code
        return {
            "connected": connection_state.connected,
            "display_name": connection_state.display_name,
            "scanner_state": None if scanner_state is None else scanner_state.value,
            "error": (
                None
                if error_code is None
                else build_error_body(self._error_message_catalog, error_code)
            ),
        }
```

Crie `src/digitalizadora/controllers/preview_controller.py`:

```python
from http import HTTPStatus

from fastapi import APIRouter, Response

from digitalizadora.services.scan_progress_tracker import ScanProgressTracker

JPEG_MEDIA_TYPE = "image/jpeg"
NO_STORE_HEADERS = {"Cache-Control": "no-store"}


class PreviewController:
    def __init__(self, progress_tracker: ScanProgressTracker) -> None:
        self._progress_tracker = progress_tracker

    def build_router(self) -> APIRouter:
        router = APIRouter()
        router.add_api_route("/api/scans/last/thumbnail", self.read_last_thumbnail, methods=["GET"])
        return router

    async def read_last_thumbnail(self) -> Response:
        thumbnail_jpeg = self._progress_tracker.last_thumbnail_jpeg()
        if thumbnail_jpeg is None:
            return Response(status_code=HTTPStatus.NOT_FOUND, headers=NO_STORE_HEADERS)
        return Response(
            content=thumbnail_jpeg, media_type=JPEG_MEDIA_TYPE, headers=NO_STORE_HEADERS
        )
```

- [ ] **Passo 21: Rodar os testes e ver passar**

Run: `.venv/bin/pytest tests/controllers/test_scan_controller.py tests/controllers/test_state_controller.py tests/controllers/test_printer_controller.py tests/controllers/test_preview_controller.py -v`

Expected: `30 passed`.

#### Ciclo 6: application_factory

- [ ] **Passo 22: Escrever o teste que falha**

Crie `tests/controllers/test_application_factory.py`:

```python
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from digitalizadora.application_factory import (
    ApplicationControllers,
    WebInterfaceConfiguration,
    create_application,
)
from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog
from digitalizadora.controllers.preview_controller import PreviewController
from digitalizadora.controllers.printer_controller import PrinterController
from digitalizadora.controllers.scan_controller import ScanController
from digitalizadora.controllers.settings_controller import SettingsController
from digitalizadora.controllers.state_controller import StateController
from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.domain.scanner_status import ScannerState
from digitalizadora.domain.stored_scan import StoredScan
from digitalizadora.services.application_settings_service import ApplicationSettingsService
from digitalizadora.services.application_state_service import ApplicationStateService
from digitalizadora.services.printer_connection_service import PrinterConnectionState
from digitalizadora.services.scan_progress_tracker import ScanProgressTracker
from digitalizadora.services.storage_guard_service import StorageGuardService
from tests.controllers.controller_test_support import (
    SCANNED_AT,
    STATE_CHANGING_HEADERS,
    TEST_BASE_ADDRESS,
    StubPrinterConnectionService,
    StubScanService,
)
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.in_memory_settings_repository import InMemoryApplicationSettingsRepository
from tests.fakes.sample_images import build_sample_jpeg

ALLOWED_HOSTS = frozenset({"127.0.0.1:8765", "localhost:8765"})
INDEX_HTML = "<!doctype html><title>Digitalizadora</title>"
STYLESHEET = "body { margin: 0; }"
FREE_SPACE_IN_BYTES = 50 * 1024**3
SETTINGS = ApplicationSettings(
    output_folder=Path("/Volumes/External/scans"),
    output_format=OutputFormat.JPEG,
    scan_preset=ScanPreset.PHOTO,
)
SETTINGS_BODY = {
    "output_folder": "/Volumes/External/scans",
    "output_format": "jpg",
    "scan_preset": "photo",
}
CONNECTED_STATE = PrinterConnectionState(
    connected=True,
    display_name="HP DeskJet 2800 series",
    scanner_state=ScannerState.IDLE,
    error_code=None,
)


@dataclass(frozen=True)
class ApplicationParts:
    controllers: ApplicationControllers
    scan_service: StubScanService
    progress_tracker: ScanProgressTracker


def build_application_parts() -> ApplicationParts:
    catalog = ErrorMessageCatalog()
    progress_tracker = ScanProgressTracker(FixedClock(SCANNED_AT))
    settings_repository = InMemoryApplicationSettingsRepository(SETTINGS)
    settings_service = ApplicationSettingsService(settings_repository, lambda folder: None)
    scan_service = StubScanService()
    storage_guard_service = StorageGuardService(lambda folder: FREE_SPACE_IN_BYTES)
    controllers = ApplicationControllers(
        scan=ScanController(scan_service, settings_service, catalog),
        state=StateController(
            ApplicationStateService(progress_tracker, settings_repository, storage_guard_service),
            catalog,
        ),
        settings=SettingsController(settings_service, catalog),
        printer=PrinterController(StubPrinterConnectionService(CONNECTED_STATE), catalog),
        preview=PreviewController(progress_tracker),
    )
    return ApplicationParts(controllers, scan_service, progress_tracker)


def build_client(
    parts: ApplicationParts,
    static_directory: Path,
    shutdown_callbacks: tuple[Callable[[], Awaitable[None]], ...] = (),
) -> TestClient:
    web_configuration = WebInterfaceConfiguration(
        allowed_hosts=ALLOWED_HOSTS,
        static_directory=static_directory,
        shutdown_callbacks=shutdown_callbacks,
    )
    application = create_application(parts.controllers, web_configuration)
    return TestClient(application, base_url=TEST_BASE_ADDRESS)


@pytest.fixture
def static_directory(tmp_path: Path) -> Path:
    directory = tmp_path / "static"
    directory.mkdir()
    (directory / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (directory / "application.css").write_text(STYLESHEET, encoding="utf-8")
    return directory


@pytest.fixture
def parts() -> ApplicationParts:
    return build_application_parts()


@pytest.fixture
def client(parts: ApplicationParts, static_directory: Path) -> TestClient:
    return build_client(parts, static_directory)


def test_root_serves_the_index_page(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == HTTPStatus.OK
    assert response.text == INDEX_HTML
    assert response.headers["content-type"].startswith("text/html")


def test_static_files_are_served_below_static(client: TestClient) -> None:
    response = client.get("/static/application.css")

    assert response.status_code == HTTPStatus.OK
    assert response.text == STYLESHEET


def test_missing_static_file_answers_404(client: TestClient) -> None:
    assert client.get("/static/missing.js").status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_interactive_documentation_is_disabled(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == HTTPStatus.NOT_FOUND


def test_health_is_reachable_through_the_factory(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def test_state_is_reachable_through_the_factory(client: TestClient) -> None:
    body = client.get("/api/state").json()

    assert body["settings"] == SETTINGS_BODY
    assert body["storage"]["free_space_in_bytes"] == FREE_SPACE_IN_BYTES


def test_settings_are_reachable_through_the_factory(client: TestClient) -> None:
    assert client.get("/api/settings").json() == SETTINGS_BODY


def test_printer_is_reachable_through_the_factory(client: TestClient) -> None:
    assert client.get("/api/printer").json()["connected"] is True


def test_localhost_host_header_is_allowed(client: TestClient) -> None:
    response = client.get("/api/health", headers={"host": "localhost:8765"})

    assert response.status_code == HTTPStatus.OK


def test_foreign_host_header_is_rejected(client: TestClient) -> None:
    response = client.get("/api/health", headers={"host": "evil.example"})

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()["code"] == "forbidden_host"


def test_put_without_the_required_header_is_rejected(client: TestClient) -> None:
    response = client.put("/api/settings", json=SETTINGS_BODY)

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()["code"] == "missing_request_header"


def test_put_with_the_required_header_is_accepted(client: TestClient) -> None:
    response = client.put("/api/settings", json=SETTINGS_BODY, headers=STATE_CHANGING_HEADERS)

    assert response.status_code == HTTPStatus.OK


def test_put_with_an_incomplete_body_answers_422_in_the_error_shape(client: TestClient) -> None:
    response = client.put("/api/settings", json={}, headers=STATE_CHANGING_HEADERS)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert response.json() == {
        "code": "invalid_settings",
        "message": ErrorMessageCatalog().message_for("invalid_settings"),
    }


def test_post_scans_answers_202_and_scans_once_with_the_saved_settings(
    client: TestClient, parts: ApplicationParts
) -> None:
    response = client.post("/api/scans", headers=STATE_CHANGING_HEADERS)

    assert response.status_code == HTTPStatus.ACCEPTED
    assert parts.scan_service.requests == [SETTINGS.to_scan_request()]


def test_post_scans_answers_409_while_the_scan_service_is_busy(
    client: TestClient, parts: ApplicationParts
) -> None:
    parts.scan_service.in_progress = True

    response = client.post("/api/scans", headers=STATE_CHANGING_HEADERS)

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()["code"] == "scan_already_running"


def test_post_scans_without_the_required_header_does_not_scan(
    client: TestClient, parts: ApplicationParts
) -> None:
    response = client.post("/api/scans")

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert parts.scan_service.requests == []


def test_thumbnail_is_404_and_then_200_after_a_stored_scan(
    client: TestClient, parts: ApplicationParts
) -> None:
    assert client.get("/api/scans/last/thumbnail").status_code == HTTPStatus.NOT_FOUND
    thumbnail_jpeg = build_sample_jpeg()
    result = ScanResult(
        output_path=Path("/Volumes/External/scans/2026-10-13_00001.jpg"),
        output_format=OutputFormat.JPEG,
        scanned_at=SCANNED_AT,
        size_in_bytes=1234,
    )
    parts.progress_tracker.begin_scan(ScanRequest(ScanPreset.PHOTO.settings, OutputFormat.JPEG))
    parts.progress_tracker.mark_completed(StoredScan(result, thumbnail_jpeg))

    response = client.get("/api/scans/last/thumbnail")

    assert response.status_code == HTTPStatus.OK
    assert response.content == thumbnail_jpeg


class RecordingShutdownCallback:
    def __init__(self) -> None:
        self.call_count = 0

    async def __call__(self) -> None:
        self.call_count += 1


def test_shutdown_callbacks_do_not_run_while_the_application_is_up(
    parts: ApplicationParts, static_directory: Path
) -> None:
    callback = RecordingShutdownCallback()

    with build_client(parts, static_directory, (callback,)) as running_client:
        running_client.get("/api/health")
        assert callback.call_count == 0


def test_shutdown_callbacks_run_once_when_the_application_stops(
    parts: ApplicationParts, static_directory: Path
) -> None:
    first_callback = RecordingShutdownCallback()
    second_callback = RecordingShutdownCallback()

    with build_client(parts, static_directory, (first_callback, second_callback)):
        pass

    assert (first_callback.call_count, second_callback.call_count) == (1, 1)
```

- [ ] **Passo 23: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/controllers/test_application_factory.py::test_root_serves_the_index_page -v`

Expected: erro de coleta, `1 error`, com `ModuleNotFoundError: No module named 'digitalizadora.application_factory'`.

- [ ] **Passo 24: Implementar o mínimo**

Crie `src/digitalizadora/application_factory.py`. O corpo inválido (campo ausente, JSON malformado) vira `422` no mesmo formato `{"code", "message"}` das demais respostas de erro; o `LocalRequestGuard` é o último middleware adicionado, portanto o mais externo.

```python
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog, build_error_body
from digitalizadora.controllers.local_request_guard import LocalRequestGuard
from digitalizadora.controllers.preview_controller import PreviewController
from digitalizadora.controllers.printer_controller import PrinterController
from digitalizadora.controllers.scan_controller import ScanController
from digitalizadora.controllers.settings_controller import SettingsController
from digitalizadora.controllers.state_controller import StateController
from digitalizadora.domain.errors import InvalidSettingsError

INDEX_FILE_NAME = "index.html"
STATIC_ROUTE = "/static"


@dataclass(frozen=True)
class ApplicationControllers:
    scan: ScanController
    state: StateController
    settings: SettingsController
    printer: PrinterController
    preview: PreviewController


@dataclass(frozen=True)
class WebInterfaceConfiguration:
    allowed_hosts: frozenset[str]
    static_directory: Path
    shutdown_callbacks: tuple[Callable[[], Awaitable[None]], ...] = ()


def create_application(
    controllers: ApplicationControllers, web_configuration: WebInterfaceConfiguration
) -> FastAPI:
    @asynccontextmanager
    async def run_lifespan(application: FastAPI) -> AsyncIterator[None]:
        yield
        for shutdown_callback in web_configuration.shutdown_callbacks:
            await shutdown_callback()

    application = FastAPI(
        title="Digitalizadora",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=run_lifespan,
    )
    register_invalid_body_handler(application, ErrorMessageCatalog())
    for controller in (
        controllers.scan,
        controllers.state,
        controllers.settings,
        controllers.printer,
        controllers.preview,
    ):
        application.include_router(controller.build_router())

    index_file = web_configuration.static_directory / INDEX_FILE_NAME

    async def serve_index() -> FileResponse:
        return FileResponse(index_file)

    application.add_api_route("/", serve_index, methods=["GET"], include_in_schema=False)
    application.mount(
        STATIC_ROUTE, StaticFiles(directory=web_configuration.static_directory), name="static"
    )
    application.add_middleware(LocalRequestGuard, allowed_hosts=web_configuration.allowed_hosts)
    return application


def register_invalid_body_handler(
    application: FastAPI, error_message_catalog: ErrorMessageCatalog
) -> None:
    async def respond_to_invalid_body(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content=build_error_body(error_message_catalog, InvalidSettingsError.code),
        )

    application.add_exception_handler(RequestValidationError, respond_to_invalid_body)
```

- [ ] **Passo 25: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/controllers/test_application_factory.py -v`

Expected: `21 passed`.

- [ ] **Passo 26: Rodar tudo da tarefa e fazer o commit**

Run: `.venv/bin/pytest tests/services/test_application_settings_service.py tests/controllers -v`

Expected: `125 passed`, cada teste em menos de 100 ms.

Run:

```bash
git add src/digitalizadora/services/application_settings_service.py src/digitalizadora/controllers/error_message_catalog.py src/digitalizadora/controllers/local_request_guard.py src/digitalizadora/controllers/settings_controller.py src/digitalizadora/controllers/scan_controller.py src/digitalizadora/controllers/state_controller.py src/digitalizadora/controllers/printer_controller.py src/digitalizadora/controllers/preview_controller.py src/digitalizadora/application_factory.py tests/controllers/controller_test_support.py tests/services/test_application_settings_service.py tests/controllers/test_error_message_catalog.py tests/controllers/test_local_request_guard.py tests/controllers/test_settings_controller.py tests/controllers/test_scan_controller.py tests/controllers/test_state_controller.py tests/controllers/test_printer_controller.py tests/controllers/test_preview_controller.py tests/controllers/test_application_factory.py
git commit -m "feat: add settings service, error catalog, request guard, controllers and application factory"
```

### Task 12: Interface web (arquivos estáticos)

**Objetivo:** Criar a página única em português (HTML, CSS e JavaScript puros, sem build e sem pedidos externos) que dispara a digitalização com o botão ou a tecla Espaço e mostra impressora, progresso, último arquivo e erros.

**Files:**
- Create: `src/digitalizadora/web/static/index.html`
- Create: `src/digitalizadora/web/static/application.css`
- Create: `src/digitalizadora/web/static/application.js`
- Test: `tests/web/test_static_assets.py`

**Interfaces:**
- Consumes (HTTP, spec seção 6.5, servido pela Tarefa 11: `/` entrega `index.html` e `/static/*` entrega os demais arquivos): `GET /api/settings`, `PUT /api/settings`, `GET /api/state`, `GET /api/printer`, `POST /api/scans`, `GET /api/scans/last/thumbnail?version=<contador>`. Erros chegam como `{"code": "...", "message": "..."}`. Qualquer `POST` ou `PUT` exige o cabeçalho `X-Requested-With: digitalizadora`.
- Consumes (Python): nada. O teste só lê os três arquivos. `tests/web/__init__.py` já existe (Tarefa 1).
- Produces: os três arquivos estáticos. Funções e classes globais do script: `format_byte_count(size_in_bytes)` (texto como "1,2 MB"), `send_request(method, path, body)` (sempre envia `X-Requested-With: digitalizadora` fora do `GET`), classe `RequestError`, classe `ScanPage` com o método `start_scan()` (chamado pelo clique e pela tecla Espaço).

Decisões de comportamento (todas pedidas pelo spec, seção 7, ou necessárias para ele funcionar):
- A tecla Espaço usa `keydown`, ignora `event.repeat` e não dispara quando o foco está num campo de texto, num `select`, num botão que não seja o Digitalizar ou num botão de opção (nesses elementos o Espaço já tem função própria). Depois de trocar formato, modo ou pasta, o foco volta ao botão Digitalizar para o Espaço continuar valendo.
- O botão fica desabilitado enquanto `scan_phase` não for `idle` e enquanto o `POST` estiver em andamento (evita clique duplo e Espaço repetido); um 409 do servidor mostra a mensagem do catálogo na faixa de erro.
- Consultas: `/api/state` a cada 500 ms fora de `idle` e a cada 2000 ms em `idle`; `/api/printer` a cada 15000 ms e só em `idle`.
- Ícones são caracteres Unicode (sem SVG com `xmlns`, para a página não conter nenhum endereço `http://`).

- [ ] **Passo 1: Escrever o teste que falha**

Criar `tests/web/test_static_assets.py`:

```python
import re
from pathlib import Path

import pytest

STATIC_DIRECTORY = Path(__file__).resolve().parents[2] / "src" / "digitalizadora" / "web" / "static"
STATIC_FILE_NAMES = ["index.html", "application.css", "application.js"]
SCRIPT_IDENTIFIER_PATTERNS = (
    re.compile(r"""getElementById\(\s*["']([^"']+)["']\s*\)"""),
    re.compile(r"""querySelector\(\s*["']#([A-Za-z0-9_-]+)"""),
)
PAGE_IDENTIFIER_PATTERN = re.compile(r"""\bid\s*=\s*["']([^"']+)["']""")
EXTERNAL_ADDRESS_PATTERN = re.compile(r"""https?://|(?:src|href)\s*=\s*["']//""")


def read_static_file(file_name: str) -> str:
    return (STATIC_DIRECTORY / file_name).read_text(encoding="utf-8")


def find_identifiers_used_by_script(script: str) -> set[str]:
    used_identifiers: set[str] = set()
    for pattern in SCRIPT_IDENTIFIER_PATTERNS:
        used_identifiers.update(pattern.findall(script))
    return used_identifiers


@pytest.mark.parametrize("file_name", STATIC_FILE_NAMES)
def test_static_file_exists(file_name: str) -> None:
    assert (STATIC_DIRECTORY / file_name).is_file()


def test_script_uses_element_identifiers() -> None:
    assert find_identifiers_used_by_script(read_static_file("application.js"))


def test_every_element_identifier_used_by_script_exists_in_page() -> None:
    used_identifiers = find_identifiers_used_by_script(read_static_file("application.js"))
    declared_identifiers = set(PAGE_IDENTIFIER_PATTERN.findall(read_static_file("index.html")))
    assert used_identifiers - declared_identifiers == set()


@pytest.mark.parametrize("required_text", ["X-Requested-With", "digitalizadora"])
def test_script_sends_required_header(required_text: str) -> None:
    assert required_text in read_static_file("application.js")


def test_page_declares_brazilian_portuguese_language() -> None:
    assert re.search(r'<html[^>]*\blang="pt-BR"', read_static_file("index.html"))


@pytest.mark.parametrize("file_name", STATIC_FILE_NAMES)
def test_static_file_has_no_external_address(file_name: str) -> None:
    assert EXTERNAL_ADDRESS_PATTERN.search(read_static_file(file_name)) is None


def test_script_has_no_console_log() -> None:
    assert "console.log" not in read_static_file("application.js")


@pytest.mark.parametrize("served_path", ["/static/application.css", "/static/application.js"])
def test_page_references_files_served_by_static_route(served_path: str) -> None:
    assert served_path in read_static_file("index.html")


@pytest.mark.parametrize("api_path", ["/api/settings", "/api/state", "/api/printer", "/api/scans"])
def test_script_calls_api_path(api_path: str) -> None:
    assert api_path in read_static_file("application.js")


def test_script_defines_byte_count_formatter() -> None:
    assert "function format_byte_count(size_in_bytes)" in read_static_file("application.js")


@pytest.mark.parametrize("option_value", ["pdf", "jpg", "document", "document_economy", "photo"])
def test_page_offers_every_format_and_preset(option_value: str) -> None:
    assert f'value="{option_value}"' in read_static_file("index.html")


def test_script_ignores_repeated_key_presses() -> None:
    assert "event.repeat" in read_static_file("application.js")


@pytest.mark.parametrize("role", ["alert", "status"])
def test_page_declares_accessible_region(role: str) -> None:
    assert f'role="{role}"' in read_static_file("index.html")
```

- [ ] **Passo 2: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/web/test_static_assets.py -v`
Expected: `27 failed`. Os testes de existência falham com `AssertionError` e todos os outros com `FileNotFoundError: [Errno 2] No such file or directory: '.../src/digitalizadora/web/static/...'`.

- [ ] **Passo 3: Implementar a página e o estilo**

Criar `src/digitalizadora/web/static/index.html`:

```html
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <title>Digitalizadora</title>
  <link rel="icon" href="data:,">
  <link rel="stylesheet" href="/static/application.css">
  <script src="/static/application.js" defer></script>
</head>
<body>
  <header class="page-header">
    <h1 class="page-title">Digitalizadora</h1>
    <div id="printer-status-chip" class="printer-chip" data-printer-condition="searching">
      <span id="printer-status-icon" class="printer-chip-icon" aria-hidden="true">…</span>
      <span id="printer-status-text" role="status" aria-live="polite">Procurando…</span>
    </div>
  </header>

  <main class="page-content">
    <noscript>
      <p class="noscript-message">Esta página precisa de JavaScript para funcionar.</p>
    </noscript>

    <p id="printer-detail" class="printer-detail" hidden></p>

    <div id="error-banner" role="alert">
      <p id="error-banner-content" class="error-banner" hidden>
        <span class="error-banner-icon" aria-hidden="true">⚠</span>
        <span id="error-banner-text"></span>
      </p>
    </div>

    <section class="scan-section" aria-label="Digitalizar">
      <button id="scan-button" class="scan-button" type="button" autofocus>
        <span id="scan-button-label" class="scan-button-label">Digitalizar</span>
        <kbd class="scan-button-hint">Espaço</kbd>
      </button>
      <p id="status-line" class="status-line" role="status" aria-live="polite">Pronto para digitalizar. Coloque a folha no vidro e aperte Espaço.</p>
    </section>

    <section class="settings-section" aria-label="Ajustes">
      <fieldset class="format-group">
        <legend>Formato do arquivo</legend>
        <label class="choice-label" for="output-format-pdf">
          <input id="output-format-pdf" type="radio" name="output-format" value="pdf" checked>
          <span>PDF</span>
        </label>
        <label class="choice-label" for="output-format-jpg">
          <input id="output-format-jpg" type="radio" name="output-format" value="jpg">
          <span>JPG</span>
        </label>
      </fieldset>

      <div class="field">
        <label for="preset-select">Modo de digitalização</label>
        <select id="preset-select" name="scan-preset">
          <option value="document">Documento (300 dpi, cor)</option>
          <option value="document_economy">Documento econômico (200 dpi, cinza)</option>
          <option value="photo">Foto (600 dpi, cor)</option>
        </select>
      </div>

      <div class="field">
        <label for="output-folder-input">Pasta de saída</label>
        <div class="folder-row">
          <input id="output-folder-input" type="text" name="output-folder" autocomplete="off" spellcheck="false">
          <button id="output-folder-save-button" type="button">Salvar</button>
        </div>
        <p id="output-folder-message" class="field-message" hidden></p>
        <p id="storage-line" class="storage-line">Espaço livre: calculando…</p>
        <p id="storage-warning" class="storage-warning" hidden>
          <span aria-hidden="true">⚠</span>
          Recomendado: use um disco externo
        </p>
      </div>
    </section>

    <section id="last-scan-panel" class="last-scan-panel" aria-label="Última digitalização" hidden>
      <img id="last-scan-thumbnail" class="last-scan-thumbnail" alt="Miniatura da última digitalização">
      <dl class="last-scan-details">
        <dt>Arquivo</dt>
        <dd id="last-scan-file-name"></dd>
        <dt>Tamanho</dt>
        <dd id="last-scan-size"></dd>
        <dt>Hora</dt>
        <dd id="last-scan-time"></dd>
      </dl>
    </section>

    <p id="session-counter" class="session-counter">Digitalizações nesta sessão: 0</p>
  </main>
</body>
</html>
```

Criar `src/digitalizadora/web/static/application.css`:

```css
:root {
  color-scheme: light dark;
  --color-background: #f3f5f8;
  --color-surface: #ffffff;
  --color-text: #1b1f24;
  --color-text-muted: #4a5460;
  --color-border: #aab4c0;
  --color-accent: #0b5fff;
  --color-accent-text: #ffffff;
  --color-disabled-background: #d9dee5;
  --color-disabled-text: #3d4651;
  --color-focus: #1b1f24;
  --color-success-background: #e3f5e8;
  --color-success-text: #0f4d22;
  --color-warning-background: #fff4d6;
  --color-warning-text: #5c3d00;
  --color-error-background: #fde8e7;
  --color-error-border: #b3261e;
  --color-error-text: #5f1410;
  --size-touch-target: 3rem;
  --size-gutter: 1rem;
  --radius-control: 0.5rem;
}

@media (prefers-color-scheme: dark) {
  :root {
    --color-background: #12161b;
    --color-surface: #1c222a;
    --color-text: #eef1f5;
    --color-text-muted: #b4bdc8;
    --color-border: #5d6a78;
    --color-accent: #6ea0ff;
    --color-accent-text: #0a1020;
    --color-disabled-background: #333b45;
    --color-disabled-text: #c3cbd5;
    --color-focus: #ffd54a;
    --color-success-background: #153322;
    --color-success-text: #bfeccc;
    --color-warning-background: #3b2e0c;
    --color-warning-text: #ffe6a3;
    --color-error-background: #3d1715;
    --color-error-border: #ff8a80;
    --color-error-text: #ffd9d6;
  }
}

* {
  box-sizing: border-box;
}

[hidden] {
  display: none !important;
}

body {
  margin: 0;
  background: var(--color-background);
  color: var(--color-text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 1.0625rem;
  line-height: 1.5;
}

:focus-visible {
  outline: 3px solid var(--color-focus);
  outline-offset: 3px;
}

.page-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--size-gutter);
  max-width: 44rem;
  margin: 0 auto;
  padding: var(--size-gutter);
}

.page-title {
  margin: 0;
  font-size: 1.5rem;
}

.page-content {
  display: grid;
  gap: 1.25rem;
  max-width: 44rem;
  margin: 0 auto;
  padding: 0 var(--size-gutter) 2rem;
}

.printer-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  min-height: 2.5rem;
  padding: 0.25rem 0.875rem;
  border: 2px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface);
  font-weight: 600;
}

.printer-chip[data-printer-condition="ready"] {
  border-color: var(--color-success-text);
  background: var(--color-success-background);
  color: var(--color-success-text);
}

.printer-chip[data-printer-condition="busy"] {
  border-color: var(--color-warning-text);
  background: var(--color-warning-background);
  color: var(--color-warning-text);
}

.printer-chip[data-printer-condition="missing"] {
  border-color: var(--color-error-border);
  background: var(--color-error-background);
  color: var(--color-error-text);
}

.printer-detail {
  margin: 0;
  color: var(--color-text-muted);
}

.error-banner {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  margin: 0;
  padding: 0.875rem 1rem;
  border: 2px solid var(--color-error-border);
  border-radius: var(--radius-control);
  background: var(--color-error-background);
  color: var(--color-error-text);
  font-weight: 600;
}

.error-banner-icon {
  font-size: 1.5rem;
  line-height: 1.2;
}

.scan-section {
  display: grid;
  gap: 0.75rem;
}

button,
select,
input[type="text"] {
  min-height: var(--size-touch-target);
  border: 2px solid var(--color-border);
  border-radius: var(--radius-control);
  background: var(--color-surface);
  color: var(--color-text);
  font: inherit;
}

button,
select {
  cursor: pointer;
  padding: 0.5rem 1rem;
}

input[type="text"] {
  min-width: 0;
  padding: 0.5rem 0.75rem;
}

.scan-button {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.25rem;
  width: 100%;
  min-height: 7rem;
  border-color: var(--color-accent);
  background: var(--color-accent);
  color: var(--color-accent-text);
  font-size: 2rem;
  font-weight: 700;
}

.scan-button:disabled {
  border-color: var(--color-border);
  background: var(--color-disabled-background);
  color: var(--color-disabled-text);
  cursor: not-allowed;
}

.scan-button-hint {
  padding: 0.125rem 0.75rem;
  border: 2px solid currentColor;
  border-radius: 0.375rem;
  font-family: inherit;
  font-size: 1rem;
  font-weight: 600;
}

.status-line {
  min-height: 1.5rem;
  margin: 0;
  font-weight: 600;
  text-align: center;
}

.settings-section {
  display: grid;
  gap: 1rem;
  padding: var(--size-gutter);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
  background: var(--color-surface);
}

.format-group {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 1rem;
  margin: 0;
  padding: 0;
  border: 0;
}

.format-group legend {
  margin-bottom: 0.25rem;
  padding: 0;
  font-weight: 600;
}

.choice-label {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  min-height: var(--size-touch-target);
  padding: 0 1rem 0 0.75rem;
  border: 2px solid var(--color-border);
  border-radius: var(--radius-control);
  cursor: pointer;
}

.choice-label input {
  width: 1.5rem;
  height: 1.5rem;
  accent-color: var(--color-accent);
}

.field {
  display: grid;
  gap: 0.375rem;
}

.field > label {
  font-weight: 600;
}

.folder-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0.5rem;
}

.field-message {
  margin: 0;
  color: var(--color-error-text);
  font-weight: 600;
}

.storage-line,
.storage-warning {
  margin: 0;
}

.storage-line {
  color: var(--color-text-muted);
}

.storage-warning {
  padding: 0.5rem 0.75rem;
  border-radius: var(--radius-control);
  background: var(--color-warning-background);
  color: var(--color-warning-text);
  font-weight: 600;
}

.last-scan-panel {
  display: grid;
  grid-template-columns: 8rem 1fr;
  gap: var(--size-gutter);
  align-items: start;
  padding: var(--size-gutter);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-control);
  background: var(--color-surface);
}

.last-scan-thumbnail {
  width: 100%;
  height: auto;
  border: 1px solid var(--color-border);
  border-radius: 0.25rem;
}

.last-scan-details {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.25rem 0.75rem;
  margin: 0;
}

.last-scan-details dt {
  color: var(--color-text-muted);
}

.last-scan-details dd {
  margin: 0;
  font-weight: 600;
  overflow-wrap: anywhere;
}

.session-counter {
  margin: 0;
  color: var(--color-text-muted);
  text-align: center;
}

.noscript-message {
  margin: 0;
  font-weight: 600;
}

@media (max-width: 30rem) {
  .last-scan-panel {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Passo 4: Rodar o teste e ver o que falta**

Run: `.venv/bin/pytest tests/web/test_static_assets.py -v`
Expected: `14 passed, 13 failed`. Os 13 que falham são os que leem `application.js` (`FileNotFoundError`), por exemplo `test_script_has_no_console_log` e `test_every_element_identifier_used_by_script_exists_in_page`.

- [ ] **Passo 5: Implementar o comportamento no navegador**

Criar `src/digitalizadora/web/static/application.js`:

```javascript
"use strict";

const REQUIRED_HEADER_NAME = "X-Requested-With";
const REQUIRED_HEADER_VALUE = "digitalizadora";

const IDLE_PHASE = "idle";
const PREPARING_PHASE = "preparing";
const PHASE_MESSAGES = {
  preparing: "Preparando…",
  scanning: "Digitalizando… pode levar de 20 a 60 segundos",
  saving: "Salvando…",
};
const READY_MESSAGE = "Pronto para digitalizar. Coloque a folha no vidro e aperte Espaço.";
const LAST_SCAN_FAILED_MESSAGE = "A última digitalização falhou.";
const SERVER_UNREACHABLE_MESSAGE = "Não consegui falar com o Digitalizadora. Ele ainda está aberto no Terminal?";
const UNEXPECTED_ERROR_MESSAGE = "Algo inesperado aconteceu. Veja o registro em ~/Library/Logs/Digitalizadora.";
const SERVER_UNREACHABLE_CODE = "server_unreachable";
const UNEXPECTED_ERROR_CODE = "unexpected_error";

const SCAN_BUTTON_READY_LABEL = "Digitalizar";
const SCAN_BUTTON_BUSY_LABEL = "Digitalizando…";

const ACTIVE_POLL_INTERVAL_MILLISECONDS = 500;
const IDLE_POLL_INTERVAL_MILLISECONDS = 2000;
const PRINTER_POLL_INTERVAL_MILLISECONDS = 15000;
const IMMEDIATE_REFRESH_MILLISECONDS = 0;

const BYTES_PER_UNIT = 1000;
const BYTE_UNITS = ["B", "KB", "MB", "GB", "TB"];
const ROUNDING_SCALE = 10;
const EXTERNAL_DISK_WARNING_BYTES = 5 * BYTES_PER_UNIT ** 3;
const SINGLE_PAGE_COUNT = 1;

const PORTUGUESE_LOCALE = "pt-BR";
const ONE_DECIMAL_FORMAT = { minimumFractionDigits: 1, maximumFractionDigits: 1 };
const CLOCK_TIME_FORMAT = { hour: "2-digit", minute: "2-digit", second: "2-digit" };

const SPACE_KEY_CODE = "Space";
const ENTER_KEY_CODE = "Enter";
const KEYBOARD_RESERVED_TAG_NAMES = ["INPUT", "SELECT", "TEXTAREA"];

const PRINTER_PRESENTATIONS = {
  searching: { icon: "…", text: "Procurando…" },
  ready: { icon: "✔", text: "Impressora pronta" },
  busy: { icon: "⏳", text: "Impressora ocupada" },
  missing: { icon: "⚠", text: "Impressora não encontrada" },
};
const READY_SCANNER_STATE = "idle";

class RequestError extends Error {
  constructor(status_code, error_code, message) {
    super(message);
    this.status_code = status_code;
    this.error_code = error_code;
  }
}

function format_byte_count(size_in_bytes) {
  let scaled_value = size_in_bytes;
  let unit_index = 0;
  const last_unit_index = BYTE_UNITS.length - 1;
  while (
    unit_index < last_unit_index &&
    Math.round(scaled_value * ROUNDING_SCALE) / ROUNDING_SCALE >= BYTES_PER_UNIT
  ) {
    scaled_value /= BYTES_PER_UNIT;
    unit_index += 1;
  }
  if (unit_index === 0) {
    return `${scaled_value} ${BYTE_UNITS[0]}`;
  }
  return `${scaled_value.toLocaleString(PORTUGUESE_LOCALE, ONE_DECIMAL_FORMAT)} ${BYTE_UNITS[unit_index]}`;
}

function describe_pages_remaining(page_count) {
  if (page_count === SINGLE_PAGE_COUNT) {
    return `cabe ~${SINGLE_PAGE_COUNT} página`;
  }
  return `cabem ~${page_count.toLocaleString(PORTUGUESE_LOCALE)} páginas`;
}

function describe_storage(storage) {
  const free_space_text = format_byte_count(storage.free_space_in_bytes);
  return `Espaço livre: ${free_space_text} — ${describe_pages_remaining(storage.estimated_pages_remaining)}`;
}

function build_thumbnail_address(version) {
  return `/api/scans/last/thumbnail?version=${version}`;
}

function format_scan_time(scanned_at) {
  return new Date(scanned_at).toLocaleTimeString(PORTUGUESE_LOCALE, CLOCK_TIME_FORMAT);
}

function describe_scan_status(state) {
  if (state.scan_phase !== IDLE_PHASE) {
    return PHASE_MESSAGES[state.scan_phase] ?? "";
  }
  if (state.last_error !== null) {
    return LAST_SCAN_FAILED_MESSAGE;
  }
  if (state.last_result !== null) {
    return `Pronto! Salvo como ${state.last_result.file_name}`;
  }
  return READY_MESSAGE;
}

function classify_printer(printer) {
  if (!printer.connected) {
    return "missing";
  }
  return printer.scanner_state === READY_SCANNER_STATE ? "ready" : "busy";
}

async function build_request_error(response) {
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  const error_code = payload !== null && typeof payload.code === "string" ? payload.code : UNEXPECTED_ERROR_CODE;
  const message = payload !== null && typeof payload.message === "string" ? payload.message : UNEXPECTED_ERROR_MESSAGE;
  return new RequestError(response.status, error_code, message);
}

async function send_request(method, path, body) {
  const options = { method, headers: {}, cache: "no-store" };
  if (method !== "GET") {
    options.headers[REQUIRED_HEADER_NAME] = REQUIRED_HEADER_VALUE;
  }
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(path, options);
  } catch {
    throw new RequestError(0, SERVER_UNREACHABLE_CODE, SERVER_UNREACHABLE_MESSAGE);
  }
  if (!response.ok) {
    throw await build_request_error(response);
  }
  return response.json();
}

function collect_elements() {
  return {
    printer_status_chip: document.getElementById("printer-status-chip"),
    printer_status_icon: document.getElementById("printer-status-icon"),
    printer_status_text: document.getElementById("printer-status-text"),
    printer_detail: document.getElementById("printer-detail"),
    error_banner_content: document.getElementById("error-banner-content"),
    error_banner_text: document.getElementById("error-banner-text"),
    scan_button: document.getElementById("scan-button"),
    scan_button_label: document.getElementById("scan-button-label"),
    status_line: document.getElementById("status-line"),
    format_inputs: {
      pdf: document.getElementById("output-format-pdf"),
      jpg: document.getElementById("output-format-jpg"),
    },
    preset_select: document.getElementById("preset-select"),
    output_folder_input: document.getElementById("output-folder-input"),
    output_folder_save_button: document.getElementById("output-folder-save-button"),
    output_folder_message: document.getElementById("output-folder-message"),
    storage_line: document.getElementById("storage-line"),
    storage_warning: document.getElementById("storage-warning"),
    last_scan_panel: document.getElementById("last-scan-panel"),
    last_scan_thumbnail: document.getElementById("last-scan-thumbnail"),
    last_scan_file_name: document.getElementById("last-scan-file-name"),
    last_scan_size: document.getElementById("last-scan-size"),
    last_scan_time: document.getElementById("last-scan-time"),
    session_counter: document.getElementById("session-counter"),
  };
}

class ScanPage {
  constructor(elements) {
    this.elements = elements;
    this.scan_phase = IDLE_PHASE;
    this.is_start_request_pending = false;
    this.saved_settings = null;
    this.shown_thumbnail_version = null;
    this.connection_error_message = null;
    this.action_error_message = null;
    this.scan_error_message = null;
    this.state_timer = null;
    this.printer_timer = null;
  }

  start() {
    this.bind_events();
    this.render_printer(PRINTER_PRESENTATIONS.searching, "searching");
    this.load_settings();
    this.refresh_state();
    this.refresh_printer();
  }

  bind_events() {
    const { scan_button, preset_select, output_folder_input, output_folder_save_button, format_inputs } = this.elements;
    scan_button.addEventListener("click", () => this.start_scan());
    document.addEventListener("keydown", (event) => this.handle_key_down(event));
    document.addEventListener("keyup", (event) => this.handle_key_up(event));
    Object.values(format_inputs).forEach((input) => {
      input.addEventListener("change", (event) => this.change_setting({ output_format: event.target.value }));
    });
    preset_select.addEventListener("change", () => this.change_setting({ scan_preset: preset_select.value }));
    output_folder_save_button.addEventListener("click", () => this.save_output_folder());
    output_folder_input.addEventListener("keydown", (event) => {
      if (event.code === ENTER_KEY_CODE) {
        this.save_output_folder();
      }
    });
  }

  is_space_reserved_by(target) {
    if (KEYBOARD_RESERVED_TAG_NAMES.includes(target.tagName)) {
      return true;
    }
    // Space activates any other focused button natively; only the scan button hands it to the scan.
    return target.tagName === "BUTTON" && target !== this.elements.scan_button;
  }

  handle_key_down(event) {
    if (event.code !== SPACE_KEY_CODE || this.is_space_reserved_by(event.target)) {
      return;
    }
    event.preventDefault();
    if (event.repeat) {
      return;
    }
    this.start_scan();
  }

  handle_key_up(event) {
    // Firefox clicks a focused button on keyup; the keydown already started the scan.
    if (event.code === SPACE_KEY_CODE && !this.is_space_reserved_by(event.target)) {
      event.preventDefault();
    }
  }

  can_start_scan() {
    return this.scan_phase === IDLE_PHASE && !this.is_start_request_pending;
  }

  async start_scan() {
    if (!this.can_start_scan()) {
      return;
    }
    this.is_start_request_pending = true;
    this.action_error_message = null;
    this.render_scan_controls();
    this.render_error_banner();
    try {
      await send_request("POST", "/api/scans");
      this.scan_phase = PREPARING_PHASE;
    } catch (error) {
      this.action_error_message = error.message;
    } finally {
      this.is_start_request_pending = false;
    }
    this.render_scan_controls();
    this.render_error_banner();
    this.schedule_state_refresh(IMMEDIATE_REFRESH_MILLISECONDS);
  }

  schedule_state_refresh(delay_milliseconds) {
    window.clearTimeout(this.state_timer);
    this.state_timer = window.setTimeout(() => this.refresh_state(), delay_milliseconds);
  }

  next_state_interval() {
    return this.scan_phase === IDLE_PHASE ? IDLE_POLL_INTERVAL_MILLISECONDS : ACTIVE_POLL_INTERVAL_MILLISECONDS;
  }

  async refresh_state() {
    try {
      this.apply_state(await send_request("GET", "/api/state"));
    } catch (error) {
      this.connection_error_message = error.message;
      this.render_error_banner();
    } finally {
      this.schedule_state_refresh(this.next_state_interval());
    }
  }

  apply_state(state) {
    const previous_phase = this.scan_phase;
    this.scan_phase = state.scan_phase;
    this.connection_error_message = null;
    this.scan_error_message = state.last_error === null ? null : state.last_error.message;
    if (previous_phase !== IDLE_PHASE && state.scan_phase === IDLE_PHASE) {
      this.action_error_message = null;
      // A finished or failed scan may have changed what the printer reports.
      this.refresh_printer();
    }
    this.render_scan_controls();
    this.render_status_line(state);
    this.render_storage(state.storage);
    this.render_last_scan(state);
    this.elements.session_counter.textContent = `Digitalizações nesta sessão: ${state.scans_completed}`;
    this.render_error_banner();
  }

  schedule_printer_refresh() {
    window.clearTimeout(this.printer_timer);
    this.printer_timer = window.setTimeout(() => this.run_scheduled_printer_refresh(), PRINTER_POLL_INTERVAL_MILLISECONDS);
  }

  async run_scheduled_printer_refresh() {
    if (this.scan_phase !== IDLE_PHASE) {
      this.schedule_printer_refresh();
      return;
    }
    await this.refresh_printer();
  }

  async refresh_printer() {
    try {
      this.apply_printer(await send_request("GET", "/api/printer"));
    } catch (error) {
      this.apply_printer({ connected: false, display_name: null, scanner_state: null, error: { message: error.message } });
    } finally {
      this.schedule_printer_refresh();
    }
  }

  apply_printer(printer) {
    const condition = classify_printer(printer);
    this.render_printer(PRINTER_PRESENTATIONS[condition], condition);
    this.elements.printer_status_chip.title = printer.display_name ?? "";
    const detail = printer.error === null ? "" : printer.error.message;
    this.elements.printer_detail.textContent = detail;
    this.elements.printer_detail.hidden = detail === "";
  }

  render_printer(presentation, condition) {
    this.elements.printer_status_chip.dataset.printerCondition = condition;
    this.elements.printer_status_icon.textContent = presentation.icon;
    this.elements.printer_status_text.textContent = presentation.text;
  }

  render_scan_controls() {
    const { scan_button, scan_button_label } = this.elements;
    const can_scan = this.can_start_scan();
    const was_disabled = scan_button.disabled;
    scan_button.disabled = !can_scan;
    scan_button.setAttribute("aria-busy", String(!can_scan));
    scan_button_label.textContent = can_scan ? SCAN_BUTTON_READY_LABEL : SCAN_BUTTON_BUSY_LABEL;
    if (was_disabled && can_scan && document.activeElement === document.body) {
      scan_button.focus();
    }
  }

  render_status_line(state) {
    this.elements.status_line.textContent = describe_scan_status(state);
  }

  render_storage(storage) {
    this.elements.storage_line.textContent = describe_storage(storage);
    this.elements.storage_warning.hidden = storage.free_space_in_bytes >= EXTERNAL_DISK_WARNING_BYTES;
  }

  render_last_scan(state) {
    const result = state.last_result;
    this.elements.last_scan_panel.hidden = result === null;
    if (result === null) {
      return;
    }
    if (this.shown_thumbnail_version !== state.scans_completed) {
      this.elements.last_scan_thumbnail.src = build_thumbnail_address(state.scans_completed);
      this.shown_thumbnail_version = state.scans_completed;
    }
    this.elements.last_scan_file_name.textContent = result.file_name;
    this.elements.last_scan_size.textContent = format_byte_count(result.size_in_bytes);
    this.elements.last_scan_time.textContent = format_scan_time(result.scanned_at);
  }

  choose_error_message() {
    return this.connection_error_message ?? this.action_error_message ?? this.scan_error_message;
  }

  render_error_banner() {
    const message = this.choose_error_message();
    this.elements.error_banner_content.hidden = message === null;
    this.elements.error_banner_text.textContent = message ?? "";
  }

  async load_settings() {
    try {
      this.apply_saved_settings(await send_request("GET", "/api/settings"));
    } catch (error) {
      this.action_error_message = error.message;
      this.render_error_banner();
    }
  }

  apply_saved_settings(settings) {
    this.saved_settings = settings;
    this.elements.format_inputs[settings.output_format].checked = true;
    this.elements.preset_select.value = settings.scan_preset;
    this.elements.output_folder_input.value = settings.output_folder;
  }

  async send_settings(settings) {
    this.apply_saved_settings(await send_request("PUT", "/api/settings", settings));
    this.schedule_state_refresh(IMMEDIATE_REFRESH_MILLISECONDS);
  }

  async change_setting(changes) {
    try {
      await this.send_settings({ ...this.saved_settings, ...changes });
      this.action_error_message = null;
    } catch (error) {
      this.action_error_message = error.message;
      this.apply_saved_settings(this.saved_settings);
    }
    this.render_error_banner();
    this.elements.scan_button.focus();
  }

  async save_output_folder() {
    const { output_folder_input, output_folder_message, scan_button } = this.elements;
    output_folder_message.hidden = true;
    try {
      await this.send_settings({ ...this.saved_settings, output_folder: output_folder_input.value.trim() });
    } catch (error) {
      output_folder_message.textContent = error.message;
      output_folder_message.hidden = false;
      return;
    }
    scan_button.focus();
  }
}

document.addEventListener("DOMContentLoaded", () => {
  new ScanPage(collect_elements()).start();
});
```

- [ ] **Passo 6: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/web/test_static_assets.py -v`
Expected: `27 passed`.

- [ ] **Passo 7: Conferir a sintaxe e a função de formatação (opcional, só se o Node estiver instalado)**

Run:
```
node --check src/digitalizadora/web/static/application.js && node -e 'const fs=require("fs"),vm=require("vm");const ctx={document:{addEventListener(){}},window:{}};vm.createContext(ctx);vm.runInContext(fs.readFileSync("src/digitalizadora/web/static/application.js","utf8")+";globalThis.format=format_byte_count;",ctx);console.log([0,999,1000,1234567,5e9].map(ctx.format).join(" | "))'
```
Expected: uma única linha `0 B | 999 B | 1,0 KB | 1,2 MB | 5,0 GB` (sem erro de sintaxe antes dela).

- [ ] **Passo 8: Commit**

```
git add src/digitalizadora/web/static/index.html src/digitalizadora/web/static/application.css src/digitalizadora/web/static/application.js tests/web/test_static_assets.py
git commit -m "feat(web): add the single-page scanning interface"
```

- [ ] **Passo 9: Verificação manual com o simulador (executar depois da Tarefa 13, que cria `make simulator` e `make run-simulated`)**

Preparação: no Terminal.app, janela 1: `make simulator`. Janela 2: `DIGITALIZADORA_OUTPUT_FOLDER="$HOME/Digitalizadora-teste" make run-simulated`. Abrir `http://127.0.0.1:8765` no Chrome ou Safari, com as Ferramentas do Desenvolvedor abertas na aba Rede (Network).

| O que fazer | O que deve acontecer |
|---|---|
| Carregar a página | Aparecem pedidos `GET /api/settings`, `/api/state` e `/api/printer`; o selo vai de "Procurando…" para "Impressora pronta" com o ícone ✔; o botão Digitalizar já está com o foco; a linha mostra "Espaço livre: X GB — cabem ~N páginas"; o aviso "Recomendado: use um disco externo" só aparece se houver menos de 5 GB livres |
| Apertar Espaço | O botão fica desabilitado e passa a dizer "Digitalizando…"; o status mostra "Preparando…", depois "Digitalizando… pode levar de 20 a 60 segundos" e "Salvando…", e termina com "Pronto! Salvo como AAAA-MM-DD_00001.pdf"; aparecem a miniatura, o nome, o tamanho (por exemplo "1,2 MB") e a hora; o contador mostra "Digitalizações nesta sessão: 1"; o arquivo existe em `~/Digitalizadora-teste` |
| Na aba Rede, olhar o `POST /api/scans` | Resposta 202 e o cabeçalho de requisição `X-Requested-With: digitalizadora` |
| Durante o scan, olhar os pedidos `/api/state` | Um a cada 0,5 s; depois que o status volta a "Pronto", um a cada 2 s; nenhum `/api/printer` enquanto o scan roda |
| Segurar o Espaço por 3 s | Só um `POST /api/scans` |
| Apertar Espaço, e logo em seguida clicar no botão duas vezes | Só um `POST /api/scans` (o botão já está desabilitado) |
| Clicar no campo da pasta, digitar um espaço e apertar Espaço | O espaço entra no texto e nenhum `POST /api/scans` sai |
| Escolher JPG | `PUT /api/settings` imediato com `"output_format": "jpg"` e o cabeçalho obrigatório; o foco volta ao botão Digitalizar |
| Trocar o modo para "Foto (600 dpi, cor)" | `PUT /api/settings` imediato com `"scan_preset": "photo"`; recarregar a página mantém JPG e Foto |
| Digitar `pasta/relativa` no campo e clicar em Salvar | A resposta é 422 e a mensagem "Ajustes inválidos." aparece logo abaixo do campo |
| Digitar um caminho absoluto válido e clicar em Salvar | A pasta é aceita, a mensagem some e a linha de espaço livre é recalculada |
| Parar o simulador (Control-C na janela 1) e esperar até 15 s | O selo vira "Impressora não encontrada" com o ícone ⚠ e a explicação aparece abaixo do cabeçalho |
| Com o simulador parado, apertar Espaço | Depois de alguns segundos surge a faixa vermelha (role `alert`) com o ícone ⚠ e o texto "Não encontrei a impressora..."; o botão volta a ficar habilitado |
| No Console do navegador, rodar `format_byte_count(1234567)` | Retorna `"1,2 MB"` |
| Mudar a aparência do macOS para Escuro e recarregar | Cores escuras, texto legível; apertar Tab mostra um contorno de foco visível em todos os controles |

Se algo não acontecer como descrito, corrigir o arquivo estático e fazer um novo commit `fix(web): ...` com os mesmos três arquivos.

---

### Task 13: Configuração, raiz de composição, pontos de entrada, launcher, Makefile e README

**Objetivo:** Ligar todas as peças (configuração por ambiente, `build_container`, `python -m digitalizadora`, simulador, launcher de duplo clique, Makefile e README completos) para o app rodar de ponta a ponta.

**Files:**
- Create: `src/digitalizadora/configuration.py`
- Create: `src/digitalizadora/composition_root.py`
- Create: `src/digitalizadora/__main__.py`
- Create: `src/digitalizadora/simulator/__main__.py`
- Create: `iniciar-digitalizadora.command`
- Create: `tests/fakes/configuration_builder.py`
- Modify: `Makefile` (substituir pelo conteúdo completo abaixo)
- Modify: `README.md` (substituir pelo conteúdo completo abaixo)
- Test: `tests/test_configuration.py`
- Test: `tests/test_composition_root.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes (spec seção 6, nomes exatos): `ApplicationControllers`, `WebInterfaceConfiguration`, `create_application` (`digitalizadora.application_factory`); `ScanController`, `StateController`, `SettingsController`, `PrinterController`, `PreviewController`, `ErrorMessageCatalog` (módulos `scan_controller`, `state_controller`, `settings_controller`, `printer_controller`, `preview_controller`, `error_message_catalog` em `digitalizadora.controllers`); `ApplicationSettings`, `OutputFormat`, `ScanPreset`, `ScannerEndpoint`, `ScanFileNamingPolicy`, `ScannerGateway` (`digitalizadora.domain.*`); `AtomicFileWriter`, `FileSystemScanOutputRepository`, `JsonApplicationSettingsRepository`, `JsonScannerEndpointRepository` (`digitalizadora.repositories.*`); `JpegResolutionService`, `PdfAssemblyService`, `ThumbnailService`, `ScanEncoder`, `StorageGuardService`, `read_free_space_in_bytes`, `ScanOutputService`, `ScanProgressTracker`, `ScanService`, `PrinterConnectionService`, `ApplicationSettingsService`, `ApplicationStateService` (`digitalizadora.services.*`); `EsclGatewayTiming`, `EsclScannerGateway`, `BonjourScannerDiscovery`, `ServiceRecord`, `ZeroconfServiceRecordSource`, `SystemClock`; `FakeScannerBehavior`, `create_fake_escl_scanner_app`; os arquivos estáticos da Tarefa 12; `scripts/probe-printer.sh` (Tarefa 0, recebe o endereço da impressora como primeiro argumento) e `docs/spike-0/README.md`.
- Produces: `ApplicationConfiguration` com `from_environment(environment, home_directory)` (constantes `DEFAULT_PORT`, `LOCAL_HOST`, `PORT_VARIABLE_NAME`, `SCANNER_ADDRESS_VARIABLE_NAME`, `OUTPUT_FOLDER_VARIABLE_NAME`); `ApplicationContainer`, `build_container(configuration, scanner_transport=None)` e `build_scanner_http_client(scanner_transport)` em `digitalizadora.composition_root` (o `build_scanner_http_client` é público para o teste de hardware da Tarefa 14 usar o mesmo cliente HTTP de produção); em `digitalizadora.__main__`: `configure_logging(log_directory)`, `ensure_port_is_available(host, port)`, `run_application(environment, home_directory) -> int`, `main()`; `tests/fakes/configuration_builder.py` com `TEST_HOST`, `TEST_PORT` e `build_application_configuration(tmp_path, scanner_address_override)` (usado também pela Tarefa 14).
- Pontos de teste que a Tarefa 14 usa de `composition_root`: os nomes `EsclGatewayTiming`, `ZeroconfServiceRecordSource` e `read_free_space_in_bytes` ficam importados no módulo e são procurados em tempo de chamada, para `monkeypatch.setattr` poder trocá-los.

**Cycle 1: configuração por variáveis de ambiente**

- [ ] **Passo 1: Escrever o teste que falha**

Criar `tests/test_configuration.py`:

```python
from pathlib import Path

import pytest

from digitalizadora.configuration import ApplicationConfiguration

HOME_DIRECTORY = Path("/Users/example")


def build_configuration(environment: dict[str, str]) -> ApplicationConfiguration:
    return ApplicationConfiguration.from_environment(environment, HOME_DIRECTORY)


def test_data_directory_defaults_to_application_support() -> None:
    expected_directory = HOME_DIRECTORY / "Library" / "Application Support" / "Digitalizadora"
    assert build_configuration({}).data_directory == expected_directory


def test_log_directory_defaults_to_library_logs() -> None:
    expected_directory = HOME_DIRECTORY / "Library" / "Logs" / "Digitalizadora"
    assert build_configuration({}).log_directory == expected_directory


def test_default_output_folder_is_inside_pictures() -> None:
    expected_folder = HOME_DIRECTORY / "Pictures" / "Digitalizadora"
    assert build_configuration({}).default_output_folder == expected_folder


def test_port_defaults_to_8765() -> None:
    assert build_configuration({}).port == 8765


def test_host_defaults_to_loopback() -> None:
    assert build_configuration({}).host == "127.0.0.1"


def test_host_cannot_be_changed_by_the_environment() -> None:
    assert build_configuration({"DIGITALIZADORA_HOST": "0.0.0.0"}).host == "127.0.0.1"


def test_scanner_address_override_is_absent_by_default() -> None:
    assert build_configuration({}).scanner_address_override is None


def test_output_folder_can_be_overridden() -> None:
    environment = {"DIGITALIZADORA_OUTPUT_FOLDER": "/Volumes/Disco/Scans"}
    assert build_configuration(environment).default_output_folder == Path("/Volumes/Disco/Scans")


def test_blank_output_folder_falls_back_to_default() -> None:
    expected_folder = HOME_DIRECTORY / "Pictures" / "Digitalizadora"
    assert build_configuration({"DIGITALIZADORA_OUTPUT_FOLDER": "  "}).default_output_folder == expected_folder


@pytest.mark.parametrize(
    "raw_port, expected_port",
    [("1", 1), ("8765", 8765), ("65535", 65535), (" 9000 ", 9000)],
)
def test_valid_port_is_accepted(raw_port: str, expected_port: int) -> None:
    assert build_configuration({"DIGITALIZADORA_PORT": raw_port}).port == expected_port


@pytest.mark.parametrize("raw_port", ["0", "65536", "-1", "abc", "80.5", "", "   "])
def test_invalid_port_raises_value_error(raw_port: str) -> None:
    with pytest.raises(ValueError, match="DIGITALIZADORA_PORT"):
        build_configuration({"DIGITALIZADORA_PORT": raw_port})


def test_scanner_address_override_is_stripped() -> None:
    environment = {"DIGITALIZADORA_SCANNER_ADDRESS": "  http://127.0.0.1:8080/eSCL \n"}
    assert build_configuration(environment).scanner_address_override == "http://127.0.0.1:8080/eSCL"


@pytest.mark.parametrize("raw_address", ["", "   ", "\t\n"])
def test_blank_scanner_address_becomes_none(raw_address: str) -> None:
    environment = {"DIGITALIZADORA_SCANNER_ADDRESS": raw_address}
    assert build_configuration(environment).scanner_address_override is None
```

- [ ] **Passo 2: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/test_configuration.py -v`
Expected: erro de coleta `ModuleNotFoundError: No module named 'digitalizadora.configuration'` (`1 error`).

- [ ] **Passo 3: Implementar o mínimo**

Criar `src/digitalizadora/configuration.py`:

```python
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

APPLICATION_NAME = "Digitalizadora"
LOCAL_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
MINIMUM_PORT = 1
MAXIMUM_PORT = 65535
PORT_VARIABLE_NAME = "DIGITALIZADORA_PORT"
SCANNER_ADDRESS_VARIABLE_NAME = "DIGITALIZADORA_SCANNER_ADDRESS"
OUTPUT_FOLDER_VARIABLE_NAME = "DIGITALIZADORA_OUTPUT_FOLDER"


@dataclass(frozen=True)
class ApplicationConfiguration:
    host: str
    port: int
    data_directory: Path
    log_directory: Path
    default_output_folder: Path
    scanner_address_override: str | None

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str], home_directory: Path
    ) -> "ApplicationConfiguration":
        return cls(
            host=LOCAL_HOST,
            port=_read_port(environment),
            data_directory=home_directory / "Library" / "Application Support" / APPLICATION_NAME,
            log_directory=home_directory / "Library" / "Logs" / APPLICATION_NAME,
            default_output_folder=_read_output_folder(environment, home_directory),
            scanner_address_override=_read_optional_text(environment, SCANNER_ADDRESS_VARIABLE_NAME),
        )


def _read_optional_text(environment: Mapping[str, str], variable_name: str) -> str | None:
    raw_text = environment.get(variable_name)
    if raw_text is None:
        return None
    return raw_text.strip() or None


def _read_output_folder(environment: Mapping[str, str], home_directory: Path) -> Path:
    configured_folder = _read_optional_text(environment, OUTPUT_FOLDER_VARIABLE_NAME)
    if configured_folder is None:
        return home_directory / "Pictures" / APPLICATION_NAME
    return Path(configured_folder)


def _read_port(environment: Mapping[str, str]) -> int:
    raw_port = environment.get(PORT_VARIABLE_NAME)
    if raw_port is None:
        return DEFAULT_PORT
    invalid_port_message = (
        f"{PORT_VARIABLE_NAME} precisa ser um número inteiro entre "
        f"{MINIMUM_PORT} e {MAXIMUM_PORT}, mas veio {raw_port!r}."
    )
    try:
        port = int(raw_port)
    except ValueError:
        raise ValueError(invalid_port_message) from None
    if not MINIMUM_PORT <= port <= MAXIMUM_PORT:
        raise ValueError(invalid_port_message)
    return port
```

- [ ] **Passo 4: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/test_configuration.py -v`
Expected: `24 passed`.

**Cycle 2: raiz de composição**

- [ ] **Passo 5: Escrever o teste que falha**

Criar `tests/fakes/configuration_builder.py` (apoio dos testes; a Tarefa 14 também o usa):

```python
from pathlib import Path

from digitalizadora.configuration import ApplicationConfiguration

TEST_HOST = "127.0.0.1"
TEST_PORT = 8765


def build_application_configuration(
    tmp_path: Path, scanner_address_override: str | None
) -> ApplicationConfiguration:
    return ApplicationConfiguration(
        host=TEST_HOST,
        port=TEST_PORT,
        data_directory=tmp_path / "data",
        log_directory=tmp_path / "logs",
        default_output_folder=tmp_path / "scans",
        scanner_address_override=scanner_address_override,
    )
```

Criar `tests/test_composition_root.py`:

```python
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from digitalizadora import composition_root
from digitalizadora.application_factory import create_application
from digitalizadora.composition_root import ApplicationContainer, build_container
from digitalizadora.infrastructure.bonjour_scanner_discovery import ServiceRecord
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter
from digitalizadora.repositories.json_scanner_endpoint_repository import JsonScannerEndpointRepository
from tests.fakes.configuration_builder import TEST_PORT, build_application_configuration

SCANNER_ADDRESS = "http://scanner.test/eSCL"
LOOPBACK_BASE_ADDRESS = f"http://127.0.0.1:{TEST_PORT}"
LOCALHOST_BASE_ADDRESS = f"http://localhost:{TEST_PORT}"
OTHER_PORT_BASE_ADDRESS = f"http://127.0.0.1:{TEST_PORT + 1}"


class RecordingScannerTransport(httpx.AsyncBaseTransport):
    def __init__(self) -> None:
        self.request_count = 0
        self.is_closed = False

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.request_count += 1
        raise AssertionError("The scanner must not be contacted by this test")

    async def aclose(self) -> None:
        self.is_closed = True


class RecordingServiceRecordSource:
    def __init__(self) -> None:
        self.collect_count = 0

    async def collect_records(self, timeout_seconds: float) -> list[ServiceRecord]:
        self.collect_count += 1
        return []


@pytest.fixture
def scanner_transport() -> RecordingScannerTransport:
    return RecordingScannerTransport()


@pytest.fixture
def record_source(monkeypatch: pytest.MonkeyPatch) -> RecordingServiceRecordSource:
    source = RecordingServiceRecordSource()
    monkeypatch.setattr(composition_root, "ZeroconfServiceRecordSource", lambda: source)
    return source


def build_client(container: ApplicationContainer, base_address: str) -> TestClient:
    application = create_application(container.controllers, container.web_configuration)
    return TestClient(application, base_url=base_address)


def test_health_endpoint_answers_ok(
    tmp_path: Path, scanner_transport: RecordingScannerTransport, record_source: RecordingServiceRecordSource
) -> None:
    container = build_container(build_application_configuration(tmp_path, None), scanner_transport)
    with build_client(container, LOOPBACK_BASE_ADDRESS) as client:
        response = client.get("/api/health")
    assert (response.status_code, response.json()) == (200, {"status": "ok"})


def test_state_endpoint_reports_default_settings(
    tmp_path: Path, scanner_transport: RecordingScannerTransport, record_source: RecordingServiceRecordSource
) -> None:
    configuration = build_application_configuration(tmp_path, None)
    container = build_container(configuration, scanner_transport)
    with build_client(container, LOOPBACK_BASE_ADDRESS) as client:
        response = client.get("/api/state")
    expected_settings = {
        "output_folder": str(configuration.default_output_folder),
        "output_format": "pdf",
        "scan_preset": "document",
    }
    assert (response.status_code, response.json()["settings"]) == (200, expected_settings)


def test_state_endpoint_reports_an_idle_scanner_without_history(
    tmp_path: Path, scanner_transport: RecordingScannerTransport, record_source: RecordingServiceRecordSource
) -> None:
    container = build_container(build_application_configuration(tmp_path, None), scanner_transport)
    with build_client(container, LOOPBACK_BASE_ADDRESS) as client:
        state = client.get("/api/state").json()
    assert (state["scan_phase"], state["scans_completed"], state["last_result"], state["last_error"]) == (
        "idle",
        0,
        None,
        None,
    )


def test_localhost_host_header_is_accepted(
    tmp_path: Path, scanner_transport: RecordingScannerTransport, record_source: RecordingServiceRecordSource
) -> None:
    container = build_container(build_application_configuration(tmp_path, None), scanner_transport)
    with build_client(container, LOCALHOST_BASE_ADDRESS) as client:
        assert client.get("/api/health").status_code == 200


def test_host_header_with_another_port_is_rejected(
    tmp_path: Path, scanner_transport: RecordingScannerTransport, record_source: RecordingServiceRecordSource
) -> None:
    container = build_container(build_application_configuration(tmp_path, None), scanner_transport)
    with build_client(container, OTHER_PORT_BASE_ADDRESS) as client:
        assert client.get("/api/health").status_code != 200


def test_scanner_address_override_is_persisted_in_the_data_directory(
    tmp_path: Path, scanner_transport: RecordingScannerTransport, record_source: RecordingServiceRecordSource
) -> None:
    configuration = build_application_configuration(tmp_path, SCANNER_ADDRESS)
    build_container(configuration, scanner_transport)
    repository = JsonScannerEndpointRepository(
        configuration.data_directory / "scanner-endpoint.json", AtomicFileWriter()
    )
    saved_endpoint = repository.load()
    assert saved_endpoint is not None and saved_endpoint.base_address == SCANNER_ADDRESS


def test_no_endpoint_file_is_written_without_override(
    tmp_path: Path, scanner_transport: RecordingScannerTransport, record_source: RecordingServiceRecordSource
) -> None:
    configuration = build_application_configuration(tmp_path, None)
    build_container(configuration, scanner_transport)
    assert not (configuration.data_directory / "scanner-endpoint.json").exists()


def test_web_configuration_points_to_the_packaged_interface(
    tmp_path: Path, scanner_transport: RecordingScannerTransport, record_source: RecordingServiceRecordSource
) -> None:
    container = build_container(build_application_configuration(tmp_path, None), scanner_transport)
    assert (container.web_configuration.static_directory / "index.html").is_file()


def test_allowed_hosts_cover_loopback_and_localhost(
    tmp_path: Path, scanner_transport: RecordingScannerTransport, record_source: RecordingServiceRecordSource
) -> None:
    container = build_container(build_application_configuration(tmp_path, None), scanner_transport)
    assert container.web_configuration.allowed_hosts == frozenset(
        {f"127.0.0.1:{TEST_PORT}", f"localhost:{TEST_PORT}"}
    )


async def test_shutdown_callback_closes_the_scanner_http_client(
    tmp_path: Path, scanner_transport: RecordingScannerTransport, record_source: RecordingServiceRecordSource
) -> None:
    container = build_container(build_application_configuration(tmp_path, None), scanner_transport)
    (shutdown_callback,) = container.web_configuration.shutdown_callbacks
    await shutdown_callback()
    assert scanner_transport.is_closed


def test_serving_state_never_contacts_the_scanner_or_discovery(
    tmp_path: Path, scanner_transport: RecordingScannerTransport, record_source: RecordingServiceRecordSource
) -> None:
    container = build_container(build_application_configuration(tmp_path, SCANNER_ADDRESS), scanner_transport)
    with build_client(container, LOOPBACK_BASE_ADDRESS) as client:
        client.get("/api/health")
        client.get("/api/state")
    assert (scanner_transport.request_count, record_source.collect_count) == (0, 0)
```

- [ ] **Passo 6: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/test_composition_root.py -v`
Expected: erro de coleta `ImportError: cannot import name 'composition_root' from 'digitalizadora'` (`1 error`).

- [ ] **Passo 7: Implementar o mínimo**

Criar `src/digitalizadora/composition_root.py` (único lugar que instancia classes concretas; cada função de montagem tem no máximo 3 parâmetros):

```python
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

from digitalizadora.application_factory import ApplicationControllers, WebInterfaceConfiguration
from digitalizadora.configuration import ApplicationConfiguration
from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog
from digitalizadora.controllers.preview_controller import PreviewController
from digitalizadora.controllers.printer_controller import PrinterController
from digitalizadora.controllers.scan_controller import ScanController
from digitalizadora.controllers.settings_controller import SettingsController
from digitalizadora.controllers.state_controller import StateController
from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.ports import ScannerGateway
from digitalizadora.domain.scan_file_naming_policy import ScanFileNamingPolicy
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scanner_endpoint import ScannerEndpoint
from digitalizadora.infrastructure.bonjour_scanner_discovery import BonjourScannerDiscovery
from digitalizadora.infrastructure.escl.escl_scanner_gateway import EsclGatewayTiming, EsclScannerGateway
from digitalizadora.infrastructure.system_clock import SystemClock
from digitalizadora.infrastructure.zeroconf_service_record_source import ZeroconfServiceRecordSource
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter
from digitalizadora.repositories.file_system_scan_output_repository import FileSystemScanOutputRepository
from digitalizadora.repositories.json_application_settings_repository import JsonApplicationSettingsRepository
from digitalizadora.repositories.json_scanner_endpoint_repository import JsonScannerEndpointRepository
from digitalizadora.services.application_settings_service import ApplicationSettingsService
from digitalizadora.services.application_state_service import ApplicationStateService
from digitalizadora.services.jpeg_resolution_service import JpegResolutionService
from digitalizadora.services.pdf_assembly_service import PdfAssemblyService
from digitalizadora.services.printer_connection_service import PrinterConnectionService
from digitalizadora.services.scan_encoder import ScanEncoder
from digitalizadora.services.scan_output_service import ScanOutputService
from digitalizadora.services.scan_progress_tracker import ScanProgressTracker
from digitalizadora.services.scan_service import ScanService
from digitalizadora.services.storage_guard_service import StorageGuardService, read_free_space_in_bytes
from digitalizadora.services.thumbnail_service import ThumbnailService

SETTINGS_FILE_NAME = "settings.json"
SCANNER_ENDPOINT_FILE_NAME = "scanner-endpoint.json"
STATIC_DIRECTORY = Path(__file__).parent / "web" / "static"

SCANNER_CONNECT_TIMEOUT_SECONDS = 5.0
SCANNER_WRITE_TIMEOUT_SECONDS = 10.0
SCANNER_POOL_TIMEOUT_SECONDS = 5.0
# NextDocument may block while the carriage moves; 600 dpi in colour takes about a minute and a half.
SCANNER_READ_TIMEOUT_SECONDS = 180.0
NO_IDLE_CONNECTIONS = 0


@dataclass(frozen=True)
class ApplicationContainer:
    controllers: ApplicationControllers
    web_configuration: WebInterfaceConfiguration


@dataclass(frozen=True)
class _Repositories:
    settings: JsonApplicationSettingsRepository
    scanner_endpoint: JsonScannerEndpointRepository
    scan_output: FileSystemScanOutputRepository


@dataclass(frozen=True)
class _Services:
    scan: ScanService
    settings: ApplicationSettingsService
    state: ApplicationStateService
    printer_connection: PrinterConnectionService
    progress_tracker: ScanProgressTracker


def build_scanner_http_client(scanner_transport: httpx.AsyncBaseTransport | None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=scanner_transport,
        follow_redirects=False,
        timeout=httpx.Timeout(
            connect=SCANNER_CONNECT_TIMEOUT_SECONDS,
            read=SCANNER_READ_TIMEOUT_SECONDS,
            write=SCANNER_WRITE_TIMEOUT_SECONDS,
            pool=SCANNER_POOL_TIMEOUT_SECONDS,
        ),
        limits=httpx.Limits(max_keepalive_connections=NO_IDLE_CONNECTIONS),
    )


def build_container(
    configuration: ApplicationConfiguration,
    scanner_transport: httpx.AsyncBaseTransport | None = None,
) -> ApplicationContainer:
    configuration.data_directory.mkdir(parents=True, exist_ok=True)
    http_client = build_scanner_http_client(scanner_transport)
    services = _build_services(_build_repositories(configuration), http_client)
    _apply_scanner_address_override(configuration, services.printer_connection)
    return ApplicationContainer(
        controllers=_build_controllers(services),
        web_configuration=_build_web_configuration(configuration, http_client),
    )


def _build_repositories(configuration: ApplicationConfiguration) -> _Repositories:
    file_writer = AtomicFileWriter()
    default_settings = ApplicationSettings(
        output_folder=configuration.default_output_folder,
        output_format=OutputFormat.PDF,
        scan_preset=ScanPreset.DOCUMENT,
    )
    settings_repository = JsonApplicationSettingsRepository(
        configuration.data_directory / SETTINGS_FILE_NAME, default_settings, file_writer
    )
    return _Repositories(
        settings=settings_repository,
        scanner_endpoint=JsonScannerEndpointRepository(
            configuration.data_directory / SCANNER_ENDPOINT_FILE_NAME, file_writer
        ),
        scan_output=FileSystemScanOutputRepository(settings_repository, ScanFileNamingPolicy(), file_writer),
    )


def _build_gateway_factory(http_client: httpx.AsyncClient) -> Callable[[ScannerEndpoint], ScannerGateway]:
    def build_gateway(endpoint: ScannerEndpoint) -> ScannerGateway:
        return EsclScannerGateway(http_client, endpoint.base_address, EsclGatewayTiming())

    return build_gateway


def _build_scan_output_service(
    repositories: _Repositories, storage_guard_service: StorageGuardService
) -> ScanOutputService:
    scan_encoder = ScanEncoder(JpegResolutionService(), PdfAssemblyService(), ThumbnailService())
    return ScanOutputService(scan_encoder, repositories.scan_output, storage_guard_service)


def _build_services(repositories: _Repositories, http_client: httpx.AsyncClient) -> _Services:
    progress_tracker = ScanProgressTracker(SystemClock())
    storage_guard_service = StorageGuardService(read_free_space_in_bytes)
    printer_connection_service = PrinterConnectionService(
        BonjourScannerDiscovery(ZeroconfServiceRecordSource()),
        repositories.scanner_endpoint,
        _build_gateway_factory(http_client),
    )
    return _Services(
        scan=ScanService(
            printer_connection_service,
            _build_scan_output_service(repositories, storage_guard_service),
            progress_tracker,
        ),
        settings=ApplicationSettingsService(repositories.settings),
        state=ApplicationStateService(progress_tracker, repositories.settings, storage_guard_service),
        printer_connection=printer_connection_service,
        progress_tracker=progress_tracker,
    )


def _build_controllers(services: _Services) -> ApplicationControllers:
    error_message_catalog = ErrorMessageCatalog()
    return ApplicationControllers(
        scan=ScanController(services.scan, services.settings, error_message_catalog),
        state=StateController(services.state, error_message_catalog),
        settings=SettingsController(services.settings, error_message_catalog),
        printer=PrinterController(services.printer_connection, error_message_catalog),
        preview=PreviewController(services.progress_tracker),
    )


def _build_web_configuration(
    configuration: ApplicationConfiguration, http_client: httpx.AsyncClient
) -> WebInterfaceConfiguration:
    return WebInterfaceConfiguration(
        allowed_hosts=frozenset({f"{configuration.host}:{configuration.port}", f"localhost:{configuration.port}"}),
        static_directory=STATIC_DIRECTORY,
        shutdown_callbacks=(http_client.aclose,),
    )


def _apply_scanner_address_override(
    configuration: ApplicationConfiguration, printer_connection_service: PrinterConnectionService
) -> None:
    if configuration.scanner_address_override is not None:
        printer_connection_service.use_manual_address(configuration.scanner_address_override)
```

- [ ] **Passo 8: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/test_composition_root.py -v`
Expected: `11 passed`.

**Cycle 3: ponto de entrada `python -m digitalizadora`**

- [ ] **Passo 9: Escrever o teste que falha**

Criar `tests/test_main.py`:

```python
import logging
import socket
from collections.abc import Iterator
from pathlib import Path

import pytest
import uvicorn

from digitalizadora.__main__ import configure_logging, ensure_port_is_available, run_application

LOOPBACK_HOST = "127.0.0.1"


class RecordingUvicornRun:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def __call__(self, application: object, **options: object) -> None:
        self.calls.append(options)


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((LOOPBACK_HOST, 0))
        return probe.getsockname()[1]


@pytest.fixture(autouse=True)
def restore_root_logger() -> Iterator[None]:
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    original_level = root_logger.level
    yield
    for handler in list(root_logger.handlers):
        if handler not in original_handlers:
            root_logger.removeHandler(handler)
            handler.close()
    root_logger.setLevel(original_level)


def test_free_port_is_available() -> None:
    ensure_port_is_available(LOOPBACK_HOST, find_free_port())


def test_port_in_use_is_rejected() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind((LOOPBACK_HOST, 0))
        listener.listen()
        with pytest.raises(OSError):
            ensure_port_is_available(LOOPBACK_HOST, listener.getsockname()[1])


def test_configure_logging_writes_to_the_log_directory(tmp_path: Path) -> None:
    configure_logging(tmp_path / "logs")
    logging.getLogger("digitalizadora.test").info("log line for the test")
    for handler in logging.getLogger().handlers:
        handler.flush()
    log_text = (tmp_path / "logs" / "digitalizadora.log").read_text(encoding="utf-8")
    assert "log line for the test" in log_text


def test_invalid_port_is_explained_and_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = run_application({"DIGITALIZADORA_PORT": "abc"}, tmp_path)
    assert exit_code == 1
    assert "Configuração inválida" in capsys.readouterr().out


def test_port_in_use_is_explained_in_portuguese_and_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind((LOOPBACK_HOST, 0))
        listener.listen()
        port = listener.getsockname()[1]
        exit_code = run_application({"DIGITALIZADORA_PORT": str(port)}, tmp_path)
    assert exit_code == 1
    assert f"A porta {port} já está em uso" in capsys.readouterr().out


def test_run_application_serves_on_the_configured_loopback_port(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = RecordingUvicornRun()
    monkeypatch.setattr(uvicorn, "run", recorder)
    port = find_free_port()
    exit_code = run_application({"DIGITALIZADORA_PORT": str(port)}, tmp_path)
    assert exit_code == 0
    assert recorder.calls == [{"host": LOOPBACK_HOST, "port": port, "log_level": "info"}]


def test_run_application_tells_how_to_open_the_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(uvicorn, "run", RecordingUvicornRun())
    port = find_free_port()
    run_application({"DIGITALIZADORA_PORT": str(port)}, tmp_path)
    output = capsys.readouterr().out
    assert f"http://{LOOPBACK_HOST}:{port}" in output
    assert "Terminal aberta" in output
```

- [ ] **Passo 10: Rodar o teste e ver falhar**

Run: `.venv/bin/pytest tests/test_main.py -v`
Expected: erro de coleta `ModuleNotFoundError: No module named 'digitalizadora.__main__'` (`1 error`).

- [ ] **Passo 11: Implementar o mínimo**

Criar `src/digitalizadora/__main__.py`. O `uvicorn` transforma uma porta ocupada em `SystemExit(1)` (verificado no código do `Server.startup`, que faz `logger.error(exc)` e `sys.exit(1)`), então o aviso em português vem de uma checagem prévia com um `socket`. O `print` só existe aqui, no ponto de entrada, porque a mensagem é para quem abriu o Terminal.

```python
import logging
import os
import socket
from collections.abc import Mapping
from logging.handlers import RotatingFileHandler
from pathlib import Path

import uvicorn

from digitalizadora.application_factory import create_application
from digitalizadora.composition_root import build_container
from digitalizadora.configuration import ApplicationConfiguration

LOG_FILE_NAME = "digitalizadora.log"
LOG_MAXIMUM_BYTES = 1024 * 1024
LOG_BACKUP_COUNT = 3
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
EXIT_CODE_SUCCESS = 0
EXIT_CODE_FAILURE = 1

PAGE_ADDRESS_MESSAGE = "Digitalizadora pronto. Abra esta página no navegador: {page_address}"
KEEP_TERMINAL_OPEN_MESSAGE = (
    "Mantenha esta janela do Terminal aberta enquanto estiver digitalizando. "
    "Para encerrar, aperte Control-C ou feche a janela."
)
INVALID_CONFIGURATION_MESSAGE = "Configuração inválida: {reason}"
PORT_IN_USE_MESSAGE = (
    "A porta {port} já está em uso. Provavelmente o Digitalizadora já está aberto em outra janela do Terminal. "
    "Feche a outra janela ou escolha outra porta, por exemplo: DIGITALIZADORA_PORT=8766 make run"
)


def configure_logging(log_directory: Path) -> None:
    log_directory.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_directory / LOG_FILE_NAME,
        maxBytes=LOG_MAXIMUM_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    for handler in (file_handler, logging.StreamHandler()):
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        root_logger.addHandler(handler)


def ensure_port_is_available(host: str, port: int) -> None:
    # uvicorn turns a bind failure into SystemExit, so the port is probed first to explain it in Portuguese.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind((host, port))


def print_startup_instructions(configuration: ApplicationConfiguration) -> None:
    page_address = f"http://{configuration.host}:{configuration.port}"
    print(PAGE_ADDRESS_MESSAGE.format(page_address=page_address))
    print(KEEP_TERMINAL_OPEN_MESSAGE)


def run_application(environment: Mapping[str, str], home_directory: Path) -> int:
    try:
        configuration = ApplicationConfiguration.from_environment(environment, home_directory)
    except ValueError as error:
        print(INVALID_CONFIGURATION_MESSAGE.format(reason=error))
        return EXIT_CODE_FAILURE
    configure_logging(configuration.log_directory)
    try:
        ensure_port_is_available(configuration.host, configuration.port)
    except OSError:
        print(PORT_IN_USE_MESSAGE.format(port=configuration.port))
        return EXIT_CODE_FAILURE
    container = build_container(configuration)
    application = create_application(container.controllers, container.web_configuration)
    print_startup_instructions(configuration)
    uvicorn.run(application, host=configuration.host, port=configuration.port, log_level="info")
    return EXIT_CODE_SUCCESS


def main() -> None:
    raise SystemExit(run_application(os.environ, Path.home()))


if __name__ == "__main__":
    main()
```

- [ ] **Passo 12: Rodar o teste e ver passar**

Run: `.venv/bin/pytest tests/test_main.py -v`
Expected: `7 passed`.

**Cycle 4: ponto de entrada do simulador**

- [ ] **Passo 13: Implementar o simulador executável**

Não há teste unitário (o que roda é o `uvicorn` real); a verificação é uma fumaça manual no Passo 14.

Criar `src/digitalizadora/simulator/__main__.py`:

```python
import uvicorn

from digitalizadora.simulator.fake_escl_scanner_app import FakeScannerBehavior, create_fake_escl_scanner_app

SIMULATOR_HOST = "127.0.0.1"
SIMULATOR_PORT = 8080
SIMULATOR_SCANNER_ADDRESS = f"http://{SIMULATOR_HOST}:{SIMULATOR_PORT}/eSCL"
SIMULATOR_MESSAGE = (
    "Impressora de mentira ligada em {address}. "
    "Em outro Terminal, rode: make run-simulated (ou use este endereço como endereço manual da impressora)."
)


def main() -> None:
    print(SIMULATOR_MESSAGE.format(address=SIMULATOR_SCANNER_ADDRESS))
    application = create_fake_escl_scanner_app(FakeScannerBehavior())
    uvicorn.run(application, host=SIMULATOR_HOST, port=SIMULATOR_PORT, log_level="info")


if __name__ == "__main__":
    main()
```

- [ ] **Passo 14: Verificar o simulador**

Run:
```
.venv/bin/python -u -m digitalizadora.simulator & SIMULATOR_PROCESS=$!; sleep 3; curl --silent http://127.0.0.1:8080/eSCL/ScannerStatus; echo; kill $SIMULATOR_PROCESS
```
Expected: primeiro a linha `Impressora de mentira ligada em http://127.0.0.1:8080/eSCL. ...`, depois o XML de `ScannerStatus` contendo a palavra `Idle`.

**Cycle 5: launcher de duplo clique**

- [ ] **Passo 15: Criar o launcher e torná-lo executável**

Criar `iniciar-digitalizadora.command`. A espera pelo `/api/health` desiste na hora se o servidor morrer, e o `trap` no `EXIT` (acionado também por `INT` e `TERM`) encerra o servidor.

```zsh
#!/bin/zsh
# Inicia o Digitalizadora. Precisa rodar pelo Terminal.app (duplo clique neste arquivo)
# porque só o Terminal.app tem acesso à rede local da impressora no macOS.

cd "$(dirname "$0")" || exit 1

PORT="${DIGITALIZADORA_PORT:-8765}"
PAGE_ADDRESS="http://127.0.0.1:${PORT}"
HEALTH_ADDRESS="${PAGE_ADDRESS}/api/health"
MAXIMUM_WAIT_SECONDS=30
LOG_FILE="$HOME/Library/Logs/Digitalizadora/digitalizadora.log"

if [[ ! -x .venv/bin/python ]]; then
  echo "Primeira execução: preparando o ambiente (pode levar alguns minutos)..."
  if ! make setup; then
    echo "Não consegui preparar o ambiente. Confira sua conexão com a internet e tente de novo."
    exit 1
  fi
fi

echo "Iniciando o Digitalizadora..."
.venv/bin/python -m digitalizadora &
server_process=$!

stop_server() {
  kill "$server_process" 2>/dev/null
}
trap stop_server EXIT
trap 'exit 1' INT TERM

waited_seconds=0
until curl --silent --fail "$HEALTH_ADDRESS" > /dev/null 2>&1; do
  if ! kill -0 "$server_process" 2>/dev/null; then
    echo "O Digitalizadora fechou logo depois de abrir. Veja a mensagem acima ou o registro em $LOG_FILE"
    exit 1
  fi
  if (( waited_seconds >= MAXIMUM_WAIT_SECONDS )); then
    echo "O Digitalizadora não respondeu em ${MAXIMUM_WAIT_SECONDS} segundos. Veja o registro em $LOG_FILE"
    exit 1
  fi
  sleep 1
  waited_seconds=$(( waited_seconds + 1 ))
done

open "$PAGE_ADDRESS"
echo "Digitalizadora aberto em $PAGE_ADDRESS"
echo "Mantenha esta janela aberta enquanto estiver digitalizando. Para encerrar, feche a janela ou aperte Control-C."
wait "$server_process"
```

Run: `chmod +x iniciar-digitalizadora.command`

- [ ] **Passo 16: Verificar permissão e sintaxe**

Run: `ls -l iniciar-digitalizadora.command && zsh -n iniciar-digitalizadora.command && echo "sintaxe ok"`
Expected: a linha do `ls` começa com `-rwxr-xr-x` e termina com o nome do arquivo, seguida de `sintaxe ok` (o `zsh -n` não imprime nada quando a sintaxe está certa).

**Cycle 6: Makefile e README completos**

- [ ] **Passo 17: Substituir o Makefile**

Antes, conferir o nome do grupo de dependências de desenvolvimento escolhido pela Tarefa 1: `grep -n -A6 "optional-dependencies" pyproject.toml`. O Makefile abaixo instala `".[development]"`; se o grupo tiver outro nome, usar o nome real na linha do `pip install`. Substituir o conteúdo de `Makefile` (as linhas de receita começam com um caractere TAB, não com espaços):

```makefile
PYTHON ?= python3
VIRTUAL_ENVIRONMENT := .venv
VIRTUAL_PYTHON := $(VIRTUAL_ENVIRONMENT)/bin/python
VIRTUAL_PYTEST := $(VIRTUAL_ENVIRONMENT)/bin/pytest
VIRTUAL_RUFF := $(VIRTUAL_ENVIRONMENT)/bin/ruff
SIMULATOR_SCANNER_ADDRESS := http://127.0.0.1:8080/eSCL

.PHONY: setup run simulator run-simulated test test-hardware lint probe

setup:
	$(PYTHON) -m venv $(VIRTUAL_ENVIRONMENT)
	$(VIRTUAL_PYTHON) -m pip install --upgrade pip
	$(VIRTUAL_PYTHON) -m pip install -e ".[development]"

run:
	$(VIRTUAL_PYTHON) -m digitalizadora

simulator:
	$(VIRTUAL_PYTHON) -m digitalizadora.simulator

run-simulated:
	DIGITALIZADORA_SCANNER_ADDRESS=$(SIMULATOR_SCANNER_ADDRESS) $(VIRTUAL_PYTHON) -m digitalizadora

test:
	$(VIRTUAL_PYTEST)

test-hardware:
	DIGITALIZADORA_HARDWARE_TESTS=1 $(VIRTUAL_PYTEST) -m hardware -v

lint:
	$(VIRTUAL_RUFF) check src tests

probe:
	@test -n "$(HOST)" || { echo "Uso: make probe HOST=192.168.0.40"; exit 1; }
	scripts/probe-printer.sh $(HOST)
```

Run: `make -n setup run simulator run-simulated test test-hardware lint probe HOST=192.168.0.40`
Expected: onze linhas impressas, sem executar nada, nesta ordem: `python3 -m venv .venv`; `.venv/bin/python -m pip install --upgrade pip`; `.venv/bin/python -m pip install -e ".[development]"`; `.venv/bin/python -m digitalizadora`; `.venv/bin/python -m digitalizadora.simulator`; `DIGITALIZADORA_SCANNER_ADDRESS=http://127.0.0.1:8080/eSCL .venv/bin/python -m digitalizadora`; `.venv/bin/pytest`; `DIGITALIZADORA_HARDWARE_TESTS=1 .venv/bin/pytest -m hardware -v`; `.venv/bin/ruff check src tests`; e as duas linhas do `probe` (`test -n "192.168.0.40" || ...` e `scripts/probe-printer.sh 192.168.0.40`).

- [ ] **Passo 18: Substituir o README**

Substituir o conteúdo de `README.md`:

````markdown
# Digitalizadora

App pessoal para o MacBook: aperte um botão (ou a tecla **Espaço**) numa página local do navegador e a **HP DeskJet Ink Advantage 2874** digitaliza **uma página do vidro** e grava um **PDF** ou um **JPG** com nome automático. Não usa driver nem software da HP: fala direto com a impressora pelo protocolo **eSCL (AirScan)**.

## O que você precisa

- Mac com macOS 15 e **Python 3.12 ou mais novo** (`python3 --version`).
- A impressora **ligada**, com a luz do Wi-Fi fixa, na **mesma rede Wi-Fi do Mac** (a 2874 só usa 2,4 GHz). Desligue a VPN.
- O **Terminal.app** (o da Apple, em Aplicativos > Utilitários).
- De preferência um **disco externo** para guardar os arquivos: o disco interno tem pouco espaço livre.
- Antes do primeiro uso, confirme que a sua impressora responde em eSCL: veja [docs/spike-0/README.md](docs/spike-0/README.md) (Gate 0).

## Primeira execução

### Jeito fácil: duplo clique

1. No Finder, dê duplo clique em `iniciar-digitalizadora.command`. Se o macOS reclamar de desenvolvedor não identificado, clique com o botão direito no arquivo, escolha **Abrir** e confirme.
2. Na primeira vez ele prepara o ambiente sozinho (`make setup`), o que leva alguns minutos e precisa de internet.
3. O navegador abre em `http://127.0.0.1:8765`. **Deixe a janela do Terminal aberta**; fechar a janela encerra o app.

### Jeito manual

Abra o **Terminal.app** (não o terminal do VS Code) e rode:

```
cd ~/Code/digitalizadora
make setup
make run
```

Depois abra `http://127.0.0.1:8765` no navegador.

### Por que precisa ser pelo Terminal.app

A partir do macOS 15 o sistema bloqueia o acesso à rede local (a impressora) para programas que não são de confiança. Só os programas iniciados pelo **Terminal.app** da Apple ficam isentos. O terminal do **VS Code**, o do **Cursor**, o shell do **Claude Code** e apps empacotados **não** são isentos: lá a impressora aparece como "não encontrada" ou o erro `No route to host` surge. Se isso acontecer, feche e abra o app pelo Terminal.app. Também confira em Ajustes do Sistema > Privacidade e Segurança > Rede Local.

## Como usar

1. Coloque a folha (ou a foto) no vidro, com a face para baixo, e feche a tampa.
2. Aperte **Espaço** (ou clique em **Digitalizar**). Espere de 20 a 60 segundos: o status mostra Preparando, Digitalizando, Salvando e por fim "Pronto! Salvo como AAAA-MM-DD_NNNNN.pdf".
3. Levante a tampa, troque a folha e aperte Espaço de novo. Não precisa tocar no mouse.

Ajustes (salvos na hora):

- **Formato:** PDF ou JPG.
- **Modo:** Documento (300 dpi, cor), Documento econômico (200 dpi, cinza) ou Foto (600 dpi, cor).
- **Pasta de saída:** digite o caminho completo (por exemplo `/Volumes/MeuDisco/Scans`) e clique em **Salvar**. O padrão é `~/Pictures/Digitalizadora`. A página mostra o espaço livre e quantas páginas ainda cabem.

Os arquivos se chamam `AAAA-MM-DD_NNNNN.pdf` ou `.jpg`, com um contador de 5 dígitos por dia, e nunca sobrescrevem outro arquivo.

## Testar sem a impressora (simulador)

O simulador é uma impressora de mentira que fala eSCL. Use dois Terminais:

```
make simulator
make run-simulated
```

O primeiro liga a impressora falsa em `http://127.0.0.1:8080/eSCL`; o segundo abre o app apontando para ela. Para não encher a pasta de Imagens, use uma pasta de teste:

```
DIGITALIZADORA_OUTPUT_FOLDER="$HOME/Digitalizadora-teste" make run-simulated
```

## Variáveis de ambiente

| Variável | Para que serve | Padrão |
|---|---|---|
| `DIGITALIZADORA_PORT` | Porta da página local (1 a 65535) | `8765` |
| `DIGITALIZADORA_OUTPUT_FOLDER` | Pasta de saída inicial | `~/Pictures/Digitalizadora` |
| `DIGITALIZADORA_SCANNER_ADDRESS` | Endereço fixo da impressora, por exemplo `http://192.168.0.40:8080/eSCL`; dispensa a busca automática | vazio |

O servidor só escuta em `127.0.0.1`; isso não é configurável.

## Comandos

| Comando | O que faz |
|---|---|
| `make setup` | Cria o `.venv` e instala as dependências |
| `make run` | Roda o app |
| `make simulator` | Liga a impressora falsa na porta 8080 |
| `make run-simulated` | Roda o app apontando para o simulador |
| `make test` | Roda os testes (sem rede e sem impressora) |
| `make test-hardware` | Roda os testes com a impressora real (Terminal.app, impressora ligada, folha no vidro) |
| `make lint` | Confere o estilo do código com ruff |
| `make probe HOST=192.168.0.40` | Sonda a impressora pelo endereço (Gate 0) |

## Quando algo dá errado

A faixa vermelha da página mostra a mensagem. O registro fica em `~/Library/Logs/Digitalizadora/digitalizadora.log`.

| Código | Mensagem na página | O que fazer |
|---|---|---|
| `scanner_unreachable` | Não encontrei a impressora... | Ligue a impressora, espere a luz do Wi-Fi fixar, confira a rede 2,4 GHz e desligue a VPN; depois tente de novo. Se o IP mudou, o app procura de novo sozinho. |
| `local_network_blocked` | O macOS pode estar bloqueando o acesso à rede local... | Abra o app pelo Terminal.app (duplo clique no `.command`) e confira Ajustes > Privacidade e Segurança > Rede Local. |
| `scanner_busy` | A impressora está ocupada... | Outro programa (Captura de Imagem, app HP) pode estar usando o scanner. Feche-o e espere alguns segundos. |
| `scan_rejected` | A impressora recusou os ajustes... | Troque o modo (por exemplo, de Foto para Documento) e tente de novo; avise se repetir. |
| `scan_failed` | A digitalização falhou... | Feche a tampa e tente de novo. Se repetir, desligue e ligue a impressora. |
| `scan_timed_out` | A impressora demorou demais... | Use um modo de resolução menor, confira o Wi-Fi e tente de novo. |
| `scan_already_running` | Já existe uma digitalização em andamento. | Espere o status voltar a "Pronto". |
| `insufficient_storage` | Pouco espaço livre na pasta de saída... | Use um disco externo ou libere espaço; o app exige pelo menos 1 GiB livre. |
| `output_folder_unavailable` | Não consigo gravar na pasta de saída... | Se for disco externo, confira se está conectado; ou escolha outra pasta e clique em Salvar. |
| `invalid_settings` | Ajustes inválidos. | A pasta precisa ser um caminho completo, começando por `/`. |
| `unexpected_error` | Algo inesperado aconteceu... | Veja o registro em `~/Library/Logs/Digitalizadora` e avise. |

Outros sintomas:

- **"A porta 8765 já está em uso"**: o app já está aberto em outra janela do Terminal. Feche-a ou rode `DIGITALIZADORA_PORT=8766 make run`.
- **O navegador não abre a página**: confira se a janela do Terminal ainda está aberta e se o endereço é `http://127.0.0.1:8765`.

## Convenções do código

- Arquivos e pastas em **kebab-case**; classes em **PascalCase**; funções e variáveis em **snake_case**; constantes em **UPPER_SNAKE_CASE**; tabelas em snake_case. Sem abreviações (`identifier`, não `id`; `base_address`, não `url`; `dots_per_inch`, não `dpi`) e com nomes descritivos. Siglas que são nome de formato ou protocolo (PDF, JPEG, HTTP, XML, eSCL) são permitidas.
- **Exceção D6:** os módulos Python importáveis (inclusive os testes) usam `snake_case` (`scan_service.py`), porque `import scan-service` é erro de sintaxe. O resto continua em kebab-case.
- Módulos pequenos e pouco acoplados, injeção de dependência por construtor montada só em `composition_root.py`, e separação em controllers, services e repositories.
- Clean Code: no máximo 3 parâmetros por função, sem parâmetros booleanos de modo, sem números mágicos, `Enum` no lugar de textos soltos, type hints, comentários só para explicar o porquê.
- Testes: `pytest` com `asyncio_mode = "auto"`, cada teste rápido e com um único conceito; relógio e `sleep` injetados; sem rede real.

## Estrutura do projeto

```
digitalizadora/
├── Makefile  pyproject.toml  README.md
├── iniciar-digitalizadora.command     duplo clique para iniciar
├── scripts/probe-printer.sh           sonda da impressora (Gate 0)
├── docs/                              spec, plano, Gate 0, checklist de aceitação
├── src/digitalizadora/
│   ├── __main__.py  configuration.py  composition_root.py  application_factory.py
│   ├── domain/            modelos, erros e portas (Protocols)
│   ├── services/          regras: digitalizar, codificar, guardar, conectar
│   ├── repositories/      arquivos e JSON
│   ├── infrastructure/    eSCL (httpx), Bonjour (zeroconf), relógio
│   ├── controllers/       HTTP em português
│   ├── simulator/         impressora falsa
│   └── web/static/        index.html, application.css, application.js
└── tests/                 espelha o src; fakes/, fixtures/, integration/, hardware/
```

## Documentos

- Design: [docs/superpowers/specs/2026-10-13-digitalizadora-design.md](docs/superpowers/specs/2026-10-13-digitalizadora-design.md)
- Plano de implementação: [docs/superpowers/plans/2026-10-13-digitalizadora-gate-0-e-mvp.md](docs/superpowers/plans/2026-10-13-digitalizadora-gate-0-e-mvp.md)
- Gate 0 (validar a impressora): [docs/spike-0/README.md](docs/spike-0/README.md)
- Checklist de aceitação: [docs/acceptance-checklist.md](docs/acceptance-checklist.md)
- Pesquisa: [docs/pesquisa/digest-da-pesquisa-2026-10-13.md](docs/pesquisa/digest-da-pesquisa-2026-10-13.md)
````

Run: `for code in scanner_unreachable local_network_blocked scanner_busy scan_rejected scan_failed scan_timed_out scan_already_running insufficient_storage output_folder_unavailable invalid_settings unexpected_error; do grep -q "$code" README.md || echo "faltando: $code"; done`
Expected: nenhuma saída (os onze códigos da seção 4.4 do spec estão na tabela).

- [ ] **Passo 19: Rodar a suíte inteira e o lint**

Run: `.venv/bin/pytest -q && make lint`
Expected: a última linha do pytest é `N passed` (sem `failed` nem `error`; os testes de hardware ficam de fora) e o lint termina com `All checks passed!`.

- [ ] **Passo 20: Commit**

```
git add src/digitalizadora/configuration.py src/digitalizadora/composition_root.py src/digitalizadora/__main__.py src/digitalizadora/simulator/__main__.py iniciar-digitalizadora.command Makefile README.md tests/fakes/configuration_builder.py tests/test_configuration.py tests/test_composition_root.py tests/test_main.py
git commit -m "feat: add configuration, composition root, entry points, launcher, Makefile and README"
```

---

### Task 14: Teste de integração, teste de hardware e checklist de aceitação

**Objetivo:** Provar o fluxo completo (clique até arquivo válido) com a impressora falsa, deixar pronto o teste opcional com a impressora real e entregar o checklist de aceitação para você preencher.

**Files:**
- Create: `tests/integration/test_scan_flow.py`
- Create: `tests/hardware/test_real_printer.py`
- Create: `docs/acceptance-checklist.md`
- Test: `tests/integration/test_scan_flow.py`
- Test: `tests/hardware/test_real_printer.py`

**Interfaces:**
- Consumes: `build_container`, `build_scanner_http_client` (`digitalizadora.composition_root`); `create_application`; `ApplicationConfiguration`; `EsclGatewayTiming`, `EsclScannerGateway`; `BonjourScannerDiscovery`; `ZeroconfServiceRecordSource`; `FakeScannerBehavior`, `create_fake_escl_scanner_app`; `ScanSettings`, `ColorMode`, `ScannerEndpoint`; `TEST_PORT`, `build_application_configuration(tmp_path, scanner_address_override)` de `tests/fakes/configuration_builder.py` (Tarefa 13); o marcador `hardware` e o conftest da Tarefa 1; `pikepdf` e `Pillow` (instalados pelo `make setup`).
- Produces: nada que outra tarefa use (é a última). Os dublês `InstrumentedScannerApp` e `AdjustableFreeSpaceReader` ficam dentro do próprio teste de integração.

Notas de projeto do teste de integração:
- O app roda inteiro (controllers, serviços, repositórios e o `EsclScannerGateway` de verdade); só o transporte do scanner é trocado por `httpx.ASGITransport` apontando para a impressora falsa, e a impressora falsa responde `503` uma vez antes do documento (`busy_polls_before_document=1`).
- O `EsclGatewayTiming()` padrão espera 1,5 s entre consultas. Para o teste ficar rápido, o fixture troca o nome `EsclGatewayTiming` dentro de `composition_root` por uma função que devolve um `EsclGatewayTiming(sleep=...)` que não espera. Do mesmo modo troca `read_free_space_in_bytes` por um leitor ajustável (assim o teste não depende do espaço real do disco do Mac, que é pequeno).
- O preset usado é `document_economy` (200 dpi, cinza, cerca de 3 megapixels) para as imagens serem pequenas.
- O `TestClient` do Starlette só devolve a resposta do `POST /api/scans` depois que a tarefa em segundo plano termina, e por isso `GET /api/state` já mostra o resultado; mesmo assim os testes esperam o estado com um laço limitado (`wait_for_state`), o que também funciona se a Tarefa 11 agendar a digitalização de outro modo. As falhas da digitalização aparecem em `/api/state`, por isso o cliente usa `raise_server_exceptions=False`.
- O caso do `409` precisa de uma digitalização que realmente fique em andamento: um `asyncio.Event` (`document_gate`) segura o `NextDocument` da impressora falsa, e o teste usa `httpx.AsyncClient` com `ASGITransport` no mesmo laço de eventos (o `TestClient` bloquearia no primeiro `POST`).

Cobertura do Review Focus (spec seção 8): (3) pasta ausente ou disco cheio: `test_unavailable_output_folder_*` e `test_full_disk_*`; (2) Espaço repetido ou clique duplo: os três testes `409`.

- [ ] **Passo 1: Escrever o teste de integração**

Criar `tests/integration/test_scan_flow.py`:

```python
import asyncio
import re
import shutil
import time
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import httpx
import pikepdf
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from starlette.types import ASGIApp, Receive, Scope, Send

from digitalizadora import composition_root
from digitalizadora.application_factory import create_application
from digitalizadora.composition_root import build_container
from digitalizadora.configuration import ApplicationConfiguration
from digitalizadora.infrastructure.escl.escl_scanner_gateway import EsclGatewayTiming
from digitalizadora.simulator.fake_escl_scanner_app import FakeScannerBehavior, create_fake_escl_scanner_app
from tests.fakes.configuration_builder import TEST_PORT, build_application_configuration

BASE_ADDRESS = f"http://127.0.0.1:{TEST_PORT}"
SCANNER_ADDRESS = "http://scanner.test/eSCL"
STATE_CHANGING_HEADERS = {"X-Requested-With": "digitalizadora"}
DOCUMENT_PATH_SUFFIX = "/NextDocument"
SCAN_JOBS_PATH_SUFFIX = "/ScanJobs"
ABUNDANT_FREE_SPACE_BYTES = 100 * 1024**3
JPEG_MARKER = b"\xff\xd8"
ECONOMY_PRESET_DOTS_PER_INCH = 200
MAXIMUM_STATE_POLLS = 500
STATE_POLL_INTERVAL_SECONDS = 0.01
FIRST_PDF_NAME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}_00001\.pdf$")
SECOND_JPG_NAME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}_00002\.jpg$")
OUTPUT_FOLDER_UNAVAILABLE_MESSAGE = (
    "Não consigo gravar na pasta de saída. Se for um disco externo, confira se está conectado."
)
INSUFFICIENT_STORAGE_MESSAGE = "Pouco espaço livre na pasta de saída. Use um disco externo ou libere espaço."
SCAN_ALREADY_RUNNING_MESSAGE = "Já existe uma digitalização em andamento."


class InstrumentedScannerApp:
    def __init__(self, inner_application: ASGIApp) -> None:
        self.inner_application = inner_application
        self.received_paths: list[str] = []
        self.document_gate = asyncio.Event()
        self.document_gate.set()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            self.received_paths.append(scope["path"])
            if scope["path"].endswith(DOCUMENT_PATH_SUFFIX):
                await self.document_gate.wait()
        await self.inner_application(scope, receive, send)


class AdjustableFreeSpaceReader:
    def __init__(self, free_space_in_bytes: int) -> None:
        self.free_space_in_bytes = free_space_in_bytes

    def __call__(self, folder: Path) -> int:
        return self.free_space_in_bytes


@dataclass(frozen=True)
class ScanEnvironment:
    configuration: ApplicationConfiguration
    scanner_app: InstrumentedScannerApp
    free_space_reader: AdjustableFreeSpaceReader


async def yield_without_waiting(seconds: float) -> None:
    await asyncio.sleep(0)


def build_fast_timing() -> EsclGatewayTiming:
    return EsclGatewayTiming(sleep=yield_without_waiting)


def build_application(scan_environment: ScanEnvironment) -> FastAPI:
    scanner_transport = httpx.ASGITransport(app=scan_environment.scanner_app)
    container = build_container(scan_environment.configuration, scanner_transport)
    return create_application(container.controllers, container.web_configuration)


def build_settings(output_folder: Path, output_format: str) -> dict[str, str]:
    return {
        "output_folder": str(output_folder),
        "output_format": output_format,
        "scan_preset": "document_economy",
    }


def has_completed_scans(expected_count: int) -> Callable[[dict], bool]:
    return lambda state: state["scan_phase"] == "idle" and state["scans_completed"] == expected_count


def has_failed(state: dict) -> bool:
    return state["scan_phase"] == "idle" and state["last_error"] is not None


def is_scan_running(state: dict) -> bool:
    return state["scan_phase"] != "idle"


def wait_for_state(client: TestClient, condition: Callable[[dict], bool]) -> dict:
    state: dict = {}
    for _ in range(MAXIMUM_STATE_POLLS):
        state = client.get("/api/state").json()
        if condition(state):
            return state
        time.sleep(STATE_POLL_INTERVAL_SECONDS)
    raise AssertionError(f"The expected state never arrived; last state: {state}")


async def wait_for_state_asynchronously(client: httpx.AsyncClient, condition: Callable[[dict], bool]) -> dict:
    state: dict = {}
    for _ in range(MAXIMUM_STATE_POLLS):
        state = (await client.get("/api/state")).json()
        if condition(state):
            return state
        await asyncio.sleep(STATE_POLL_INTERVAL_SECONDS)
    raise AssertionError(f"The expected state never arrived; last state: {state}")


def scan_once(client: TestClient, output_folder: Path, output_format: str) -> dict:
    settings_response = client.put(
        "/api/settings", json=build_settings(output_folder, output_format), headers=STATE_CHANGING_HEADERS
    )
    assert settings_response.status_code == 200
    scan_count_before = client.get("/api/state").json()["scans_completed"]
    scan_response = client.post("/api/scans", headers=STATE_CHANGING_HEADERS)
    assert scan_response.status_code == 202
    return wait_for_state(client, has_completed_scans(scan_count_before + 1))


def saved_file_path(state: dict) -> Path:
    last_result = state["last_result"]
    return Path(last_result["output_folder"]) / last_result["file_name"]


@pytest.fixture
def output_folder(tmp_path: Path) -> Path:
    return tmp_path / "out"


@pytest.fixture
def scan_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ScanEnvironment:
    free_space_reader = AdjustableFreeSpaceReader(ABUNDANT_FREE_SPACE_BYTES)
    monkeypatch.setattr(composition_root, "EsclGatewayTiming", build_fast_timing)
    monkeypatch.setattr(composition_root, "read_free_space_in_bytes", free_space_reader)
    fake_scanner = create_fake_escl_scanner_app(FakeScannerBehavior(busy_polls_before_document=1))
    return ScanEnvironment(
        configuration=build_application_configuration(tmp_path, SCANNER_ADDRESS),
        scanner_app=InstrumentedScannerApp(fake_scanner),
        free_space_reader=free_space_reader,
    )


@pytest.fixture
def client(scan_environment: ScanEnvironment) -> Iterator[TestClient]:
    application = build_application(scan_environment)
    # A failed scan is reported through /api/state, so the POST itself must not re-raise it.
    with TestClient(application, base_url=BASE_ADDRESS, raise_server_exceptions=False) as test_client:
        yield test_client


def test_scan_request_is_accepted(client: TestClient, output_folder: Path) -> None:
    client.put("/api/settings", json=build_settings(output_folder, "pdf"), headers=STATE_CHANGING_HEADERS)
    response = client.post("/api/scans", headers=STATE_CHANGING_HEADERS)
    assert (response.status_code, response.json()) == (202, {"accepted": True})


def test_state_reports_the_completed_pdf_scan(client: TestClient, output_folder: Path) -> None:
    state = scan_once(client, output_folder, "pdf")
    assert FIRST_PDF_NAME_PATTERN.match(state["last_result"]["file_name"])


def test_completed_scan_leaves_the_application_idle_with_one_scan(client: TestClient, output_folder: Path) -> None:
    state = scan_once(client, output_folder, "pdf")
    assert (state["scan_phase"], state["scans_completed"]) == ("idle", 1)


def test_saved_pdf_has_exactly_one_page(client: TestClient, output_folder: Path) -> None:
    state = scan_once(client, output_folder, "pdf")
    with pikepdf.open(saved_file_path(state)) as document:
        assert len(document.pages) == 1


def test_second_scan_as_jpg_continues_the_day_sequence(client: TestClient, output_folder: Path) -> None:
    scan_once(client, output_folder, "pdf")
    state = scan_once(client, output_folder, "jpg")
    assert SECOND_JPG_NAME_PATTERN.match(state["last_result"]["file_name"])


def test_saved_jpg_starts_with_the_jpeg_marker(client: TestClient, output_folder: Path) -> None:
    state = scan_once(client, output_folder, "jpg")
    assert saved_file_path(state).read_bytes()[:2] == JPEG_MARKER


def test_saved_jpg_reports_the_requested_resolution(client: TestClient, output_folder: Path) -> None:
    state = scan_once(client, output_folder, "jpg")
    with Image.open(saved_file_path(state)) as image:
        assert image.info["dpi"] == (ECONOMY_PRESET_DOTS_PER_INCH, ECONOMY_PRESET_DOTS_PER_INCH)


def test_last_thumbnail_is_served_as_jpeg(client: TestClient, output_folder: Path) -> None:
    scan_once(client, output_folder, "pdf")
    response = client.get("/api/scans/last/thumbnail")
    assert (response.status_code, response.headers["content-type"]) == (200, "image/jpeg")
    assert response.content[:2] == JPEG_MARKER


def test_thumbnail_is_not_found_before_the_first_scan(client: TestClient) -> None:
    assert client.get("/api/scans/last/thumbnail").status_code == 404


def make_output_folder_unavailable(client: TestClient, output_folder: Path) -> None:
    client.put("/api/settings", json=build_settings(output_folder, "pdf"), headers=STATE_CHANGING_HEADERS)
    shutil.rmtree(output_folder)
    output_folder.write_text("a file where the folder used to be")


def test_unavailable_output_folder_is_reported_with_its_message(client: TestClient, output_folder: Path) -> None:
    make_output_folder_unavailable(client, output_folder)
    client.post("/api/scans", headers=STATE_CHANGING_HEADERS)
    state = wait_for_state(client, has_failed)
    assert state["last_error"] == {
        "code": "output_folder_unavailable",
        "message": OUTPUT_FOLDER_UNAVAILABLE_MESSAGE,
    }


def test_unavailable_output_folder_is_detected_before_contacting_the_scanner(
    client: TestClient, scan_environment: ScanEnvironment, output_folder: Path
) -> None:
    make_output_folder_unavailable(client, output_folder)
    client.post("/api/scans", headers=STATE_CHANGING_HEADERS)
    wait_for_state(client, has_failed)
    assert scan_environment.scanner_app.received_paths == []


def test_full_disk_is_reported_with_its_message(
    client: TestClient, scan_environment: ScanEnvironment, output_folder: Path
) -> None:
    client.put("/api/settings", json=build_settings(output_folder, "pdf"), headers=STATE_CHANGING_HEADERS)
    scan_environment.free_space_reader.free_space_in_bytes = 0
    client.post("/api/scans", headers=STATE_CHANGING_HEADERS)
    state = wait_for_state(client, has_failed)
    assert state["last_error"] == {"code": "insufficient_storage", "message": INSUFFICIENT_STORAGE_MESSAGE}


def test_full_disk_is_detected_before_contacting_the_scanner(
    client: TestClient, scan_environment: ScanEnvironment, output_folder: Path
) -> None:
    client.put("/api/settings", json=build_settings(output_folder, "pdf"), headers=STATE_CHANGING_HEADERS)
    scan_environment.free_space_reader.free_space_in_bytes = 0
    client.post("/api/scans", headers=STATE_CHANGING_HEADERS)
    wait_for_state(client, has_failed)
    assert scan_environment.scanner_app.received_paths == []


@dataclass(frozen=True)
class RunningScan:
    client: httpx.AsyncClient
    first_request: "asyncio.Task[httpx.Response]"


@pytest.fixture
async def running_scan(scan_environment: ScanEnvironment, output_folder: Path) -> AsyncIterator[RunningScan]:
    scan_environment.scanner_app.document_gate.clear()
    transport = httpx.ASGITransport(app=build_application(scan_environment))
    async with httpx.AsyncClient(transport=transport, base_url=BASE_ADDRESS) as client:
        await client.put("/api/settings", json=build_settings(output_folder, "pdf"), headers=STATE_CHANGING_HEADERS)
        first_request = asyncio.create_task(client.post("/api/scans", headers=STATE_CHANGING_HEADERS))
        await wait_for_state_asynchronously(client, is_scan_running)
        yield RunningScan(client=client, first_request=first_request)
        scan_environment.scanner_app.document_gate.set()
        await first_request
        await wait_for_state_asynchronously(client, has_completed_scans(1))


async def test_second_scan_request_during_a_scan_is_rejected_with_conflict(running_scan: RunningScan) -> None:
    response = await running_scan.client.post("/api/scans", headers=STATE_CHANGING_HEADERS)
    assert (response.status_code, response.json()) == (
        409,
        {"code": "scan_already_running", "message": SCAN_ALREADY_RUNNING_MESSAGE},
    )


async def test_rejected_second_request_does_not_start_another_job(
    running_scan: RunningScan, scan_environment: ScanEnvironment
) -> None:
    await running_scan.client.post("/api/scans", headers=STATE_CHANGING_HEADERS)
    job_requests = [path for path in scan_environment.scanner_app.received_paths if path.endswith(SCAN_JOBS_PATH_SUFFIX)]
    assert len(job_requests) == 1


async def test_running_scan_stays_in_progress_after_a_rejected_request(running_scan: RunningScan) -> None:
    await running_scan.client.post("/api/scans", headers=STATE_CHANGING_HEADERS)
    state = (await running_scan.client.get("/api/state")).json()
    assert state["scan_phase"] != "idle"
```

- [ ] **Passo 2: Rodar o teste e ver o resultado**

Este é um teste de aceitação escrito depois das unidades, então o esperado é verde; qualquer vermelho aponta um defeito de integração e deve ser corrigido na tarefa dona do comportamento.

Run: `.venv/bin/pytest tests/integration/test_scan_flow.py -v`
Expected: `16 passed`.

Se algum teste falhar, usar esta tabela:

| Teste que falha | Defeito provável | Onde corrigir |
|---|---|---|
| `test_unavailable_output_folder_is_detected_before_contacting_the_scanner` (a lista `received_paths` não está vazia) | A pasta só é verificada depois da digitalização, então uma folha seria escaneada e perdida com o disco externo desconectado | `ScanOutputService.ensure_capacity` (Tarefa 8): antes de qualquer outra coisa deve criar a pasta se faltar e confirmar que dá para gravar, levantando `OutputFolderUnavailableError`; ver `contract_change_requests` deste plano |
| `test_full_disk_*` | A guarda de espaço não roda antes do scanner | `ScanService.scan_one_file` e `ScanOutputService.ensure_capacity` (Tarefas 8 e 10) |
| `test_saved_jpg_reports_the_requested_resolution` | O JFIF não foi normalizado | `JpegResolutionService` e `ScanEncoder` (Tarefa 6) |
| `test_*_rejected_*` ou `409` ausente | O controller não consulta `is_scan_in_progress()` | `ScanController` (Tarefa 11) |

- [ ] **Passo 3: Escrever o teste de hardware (opcional, só com a impressora)**

O marcador `hardware` faz o conftest da Tarefa 1 pular estes testes, a menos que `DIGITALIZADORA_HARDWARE_TESTS=1`. Cada teste descobre a impressora de novo (até 10 s).

Criar `tests/hardware/test_real_printer.py`:

```python
import io
import time
from collections.abc import AsyncIterator, Callable

import pytest
from PIL import Image

from digitalizadora.composition_root import build_scanner_http_client
from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanner_endpoint import ScannerEndpoint
from digitalizadora.infrastructure.bonjour_scanner_discovery import BonjourScannerDiscovery
from digitalizadora.infrastructure.escl.escl_scanner_gateway import EsclGatewayTiming, EsclScannerGateway
from digitalizadora.infrastructure.zeroconf_service_record_source import ZeroconfServiceRecordSource

pytestmark = pytest.mark.hardware

DISCOVERY_TIMEOUT_SECONDS = 10.0
ACCEPTED_RESOLUTIONS = (150, 200, 300)
JPEG_MEDIA_TYPE = "image/jpeg"
JPEG_MARKER = b"\xff\xd8"
SCAN_DOTS_PER_INCH = 150
GLASS_SHORT_SIDE_INCHES = 8.5
MINIMUM_PAGE_EDGE_PIXELS = int(SCAN_DOTS_PER_INCH * GLASS_SHORT_SIDE_INCHES / 2)


@pytest.fixture
async def scanner_endpoint() -> ScannerEndpoint:
    discovery = BonjourScannerDiscovery(ZeroconfServiceRecordSource())
    endpoints = await discovery.discover(DISCOVERY_TIMEOUT_SECONDS)
    assert endpoints, "No _uscan._tcp scanner found: printer on, same Wi-Fi, run from Terminal.app?"
    return endpoints[0]


@pytest.fixture
async def scanner_gateway(scanner_endpoint: ScannerEndpoint) -> AsyncIterator[EsclScannerGateway]:
    http_client = build_scanner_http_client(None)
    try:
        yield EsclScannerGateway(http_client, scanner_endpoint.base_address, EsclGatewayTiming())
    finally:
        await http_client.aclose()


async def test_discovery_finds_the_printer(scanner_endpoint: ScannerEndpoint) -> None:
    assert scanner_endpoint.base_address.startswith("http://")


async def test_capabilities_offer_a_common_resolution(scanner_gateway: EsclScannerGateway) -> None:
    capabilities = await scanner_gateway.read_capabilities()
    assert set(ACCEPTED_RESOLUTIONS) & set(capabilities.supported_resolutions)


async def test_capabilities_offer_jpeg(scanner_gateway: EsclScannerGateway) -> None:
    capabilities = await scanner_gateway.read_capabilities()
    assert JPEG_MEDIA_TYPE in capabilities.supported_document_formats


async def test_scan_one_page_returns_a_decodable_jpeg(
    scanner_gateway: EsclScannerGateway, record_property: Callable[[str, object], None]
) -> None:
    settings = ScanSettings(dots_per_inch=SCAN_DOTS_PER_INCH, color_mode=ColorMode.GRAYSCALE)
    started_at = time.monotonic()
    scanned_image = await scanner_gateway.scan_page(settings)
    record_property("scan_elapsed_seconds", round(time.monotonic() - started_at, 1))
    with Image.open(io.BytesIO(scanned_image.content)) as image:
        image.load()
        width_pixels, height_pixels = image.size
    assert scanned_image.content[:2] == JPEG_MARKER
    assert min(width_pixels, height_pixels) >= MINIMUM_PAGE_EDGE_PIXELS
```

- [ ] **Passo 4: Conferir que o teste de hardware fica de fora da suíte normal**

Run: `.venv/bin/pytest tests/hardware -v`
Expected: nenhum teste passa nem falha; a saída termina com `4 skipped` (ou `4 deselected`, se o `pyproject.toml` da Tarefa 1 excluir o marcador com `-m "not hardware"`).

Para rodar de verdade: `make test-hardware`. **Lembrete:** rode pelo **Terminal.app** (não pelo terminal do VS Code), com a impressora ligada, na mesma rede, VPN desligada e **uma folha no vidro**. Expected: `4 passed` em cerca de 30 a 90 s; o tempo da digitalização aparece em `scan_elapsed_seconds` (rode `DIGITALIZADORA_HARDWARE_TESTS=1 .venv/bin/pytest -m hardware -v --junitxml=$TMPDIR/hardware-report.xml` e procure `scan_elapsed_seconds` no XML gerado).

- [ ] **Passo 5: Escrever o checklist de aceitação**

Criar `docs/acceptance-checklist.md`:

````markdown
# Checklist de aceitação do Digitalizadora

Preencha a coluna **Resultado** com OK, FALHOU (e o que viu) ou N/A. Faça primeiro a parte do simulador (sem impressora) e só depois a da impressora real.

Anote ao começar:

- Data: ____________  macOS (`sw_vers -productVersion` e `sw_vers -buildVersion`): ____________
- Versão do código (`git rev-parse --short HEAD`): ____________

## Parte A: simulador (sem impressora)

Use dois Terminais (Terminal.app). Pasta de teste: `~/Digitalizadora-teste`.

| # | O que fazer | Resultado esperado | Resultado |
|---|---|---|---|
| A1 | Terminal 1: `make simulator` | Aparece "Impressora de mentira ligada em http://127.0.0.1:8080/eSCL" |  |
| A2 | Terminal 2: `DIGITALIZADORA_OUTPUT_FOLDER="$HOME/Digitalizadora-teste" make run-simulated` | Aparece o endereço `http://127.0.0.1:8765` e o aviso para manter a janela aberta |  |
| A3 | Abrir `http://127.0.0.1:8765` no navegador | Página em português; selo "Impressora pronta" em até 15 s; botão Digitalizar com o foco; linha "Espaço livre: ... cabem ~N páginas" |  |
| A4 | Apertar **Espaço** | O botão desabilita; o status passa por Preparando…, Digitalizando… e Salvando…; termina com "Pronto! Salvo como AAAA-MM-DD_00001.pdf" |  |
| A5 | Abrir o arquivo da pasta de teste no Preview | O PDF abre com 1 página |  |
| A6 | Olhar o painel da última digitalização | Miniatura, nome do arquivo, tamanho (por exemplo "1,2 MB") e hora; "Digitalizações nesta sessão: 1" |  |
| A7 | Escolher **JPG** e apertar Espaço | Surge `AAAA-MM-DD_00002.jpg` na pasta, abre no Preview |  |
| A8 | Trocar o modo para Foto e recarregar a página (Cmd+R) | Formato JPG e modo Foto continuam selecionados; a pasta continua a mesma |  |
| A9 | Segurar a tecla Espaço por 3 segundos | Só um arquivo novo é criado |  |
| A10 | Apertar Espaço duas vezes seguidas, bem rápido (ou clicar duas vezes) | Só um arquivo novo; se aparecer faixa vermelha, é "Já existe uma digitalização em andamento." |  |
| A11 | Clicar no campo da pasta, digitar um espaço e apertar Espaço | O espaço entra no texto; nenhuma digitalização começa |  |
| A12 | Digitar `pasta/relativa` no campo e clicar em **Salvar** | Mensagem "Ajustes inválidos." logo abaixo do campo; a pasta anterior continua valendo |  |
| A13 | Digitar `/Digitalizadora-sem-permissao` e clicar em **Salvar** | Mensagem "Não consigo gravar na pasta de saída. Se for um disco externo, confira se está conectado." abaixo do campo |  |
| A14 | Digitar o caminho completo `/Users/<seu-usuário>/Digitalizadora-teste/outra` e clicar em **Salvar**; depois apertar Espaço | A pasta é criada e o novo arquivo cai nela |  |
| A15 | Procurar arquivos `.part` nas pastas de teste (`find ~/Digitalizadora-teste -name "*.part"`) | Nenhum resultado |  |
| A16 | No Terminal 1, Control-C (parar o simulador); esperar até 15 s | O selo muda para "Impressora não encontrada" e aparece a explicação abaixo do cabeçalho |  |
| A17 | Com o simulador parado, apertar Espaço | Faixa vermelha com ícone e texto: "Não encontrei a impressora. Confira se está ligada..." |  |
| A18 | Religar o simulador (`make simulator`) e apertar Espaço | A digitalização funciona sem reiniciar o app |  |
| A19 | Abrir um terceiro Terminal e rodar `make run` | Mensagem "A porta 8765 já está em uso..." e o comando termina |  |
| A20 | Control-C no Terminal 2 e rodar `make run-simulated` de novo | O app encerra sem erro e sobe de novo |  |
| A21 | Ajustes do Sistema > Aparência > Escuro, recarregar a página; navegar com a tecla Tab | Texto legível no modo escuro; o foco aparece com contorno visível em todos os controles |  |

## Parte B: impressora real

Antes de começar:

- [ ] Gate 0 concluído e decisão "seguir" registrada em `docs/spike-0/README.md`.
- [ ] Impressora ligada, luz do Wi-Fi fixa, mesma rede do Mac, VPN desligada.
- [ ] Tudo rodando pelo **Terminal.app** (nunca pelo terminal do VS Code).
- [ ] Disco externo conectado e pasta de saída escolhida nele.
- [ ] Uma folha de texto no vidro.

| # | O que fazer | Resultado esperado | Resultado |
|---|---|---|---|
| B1 | Duplo clique em `iniciar-digitalizadora.command` | O navegador abre em `http://127.0.0.1:8765`; selo "Impressora pronta" |  |
| B2 | Escolher PDF, modo Documento, apertar Espaço | Em 20 a 60 s aparece "Pronto! Salvo como AAAA-MM-DD_00001.pdf"; anote o tempo: ______ s |  |
| B3 | Abrir o PDF no Preview e ver Ferramentas > Mostrar Inspetor | 1 página de cerca de 216 × 297 mm (A4), com o texto legível |  |
| B4 | Escolher JPG, modo Documento, digitalizar; abrir no Preview > Ferramentas > Mostrar Inspetor > aba Mais Informações | Arquivo `.jpg` abre; resolução de 300 dpi |  |
| B5 | Modo Documento econômico, digitalizar em JPG | Resolução de 200 dpi; imagem em tons de cinza; anote o tempo: ______ s |  |
| B6 | Uma foto no vidro, modo Foto, JPG | Resolução de 600 dpi, cores corretas; anote o tempo: ______ s e se a impressora aguentou |  |
| B7 | Dez digitalizações seguidas, só com Espaço, sem tocar no mouse | Dez arquivos com números em sequência, sem buracos e sem repetição |  |
| B8 | Deixar a impressora parada por 10 minutos e apertar Espaço | A digitalização funciona (o primeiro pedido pode demorar mais); anote o atraso: ______ s |  |
| B9 | Desligar o Wi-Fi do Mac, apertar Espaço, ligar o Wi-Fi e apertar Espaço de novo | Primeiro a faixa "Não encontrei a impressora..."; depois funciona sem reiniciar o app |  |
| B10 | Com o app aberto, desconectar o disco externo e apertar Espaço | Faixa "Não consigo gravar na pasta de saída..." logo, sem esperar a impressora digitalizar |  |
| B11 | Reconectar o disco e apertar Espaço | A digitalização funciona e o arquivo cai no disco externo |  |
| B12 | Procurar arquivos `.part` na pasta de saída | Nenhum arquivo `.part` sobrou |  |
| B13 | Apertar Espaço três vezes enquanto a impressora digitaliza | Só um arquivo novo; a faixa pode mostrar "Já existe uma digitalização em andamento." |  |
| B14 | Abrir a tampa durante uma digitalização (de propósito) | O app mostra uma mensagem em português (por exemplo "A digitalização falhou...") e volta a aceitar Espaço |  |
| B15 | Fechar a janela do Terminal e tentar abrir a página | A página não responde; ao dar duplo clique no `.command` de novo, tudo volta a funcionar |  |
| B16 | (Opcional) Rodar `make run` pelo terminal do VS Code | A impressora aparece como não encontrada ou "O macOS pode estar bloqueando o acesso à rede local..."; confirma a regra do Terminal.app |  |

Resumo (preencha no fim):

- Páginas por hora no uso real: ____________
- Problemas encontrados: ____________
- Decisão: aceitar a v1 / corrigir antes: ____________
````

- [ ] **Passo 6: Rodar a suíte inteira e o lint**

Run: `.venv/bin/pytest -q && make lint`
Expected: a última linha do pytest é `N passed` (com `4 skipped` ou `4 deselected` dos testes de hardware e sem `failed`) e o lint termina com `All checks passed!`.

- [ ] **Passo 7: Commit**

```
git add tests/integration/test_scan_flow.py tests/hardware/test_real_printer.py docs/acceptance-checklist.md
git commit -m "test: add scan flow integration test, hardware test and acceptance checklist"
```


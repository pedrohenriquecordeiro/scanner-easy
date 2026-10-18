# Digitalizadora — design (spec)

**Data:** 2026-10-13 · **Atualizado em:** 2026-10-17 · **Status:** direção aprovada por você; **Gate 0 concluído em 2026-10-17** ([resultado](../../gate-0-resultado-2026-10-17.md)) · **Modo Documento (várias páginas num PDF) incluído nesta versão em 2026-10-17** ([design](2026-10-17-documento-de-varias-paginas.md)) · **Nada foi implementado ainda**

**Entrada:** [md.md](../../../../md.md) · **Pesquisa:** [digest da pesquisa](../../pesquisa/digest-da-pesquisa-2026-10-13.md) (em inglês, com fontes) · **Gate 0:** [resultado](../../gate-0-resultado-2026-10-17.md) e [capturas reais](../../gate-0-capturas/) · **Mudanças de contrato:** [ACC-1 a ACC-13](../plans/2026-10-13-mudancas-de-contrato-pendentes.md) e [G0C-1 a G0C-16](../plans/2026-10-17-mudancas-de-contrato-do-gate-0.md) (já aplicadas abaixo; G0C-14 a G0C-16 prevalecem sobre G0C-3 e G0C-4 onde houver conflito) · **Plano:** [Gate 0 + MVP](../plans/2026-10-17-digitalizadora-plano-final.md)

---

## 0. Resumo

- **O que construir:** um app local, aberto com duplo clique no launcher `iniciar-digitalizadora.command` (que abre o Terminal.app), que mostra uma página em `http://127.0.0.1:8765` com um botão grande **Digitalizar** (e a tecla **Espaço**), um seletor **PDF | JPG** e um seletor de qualidade (**Texto**, **Texto econômico**, **Foto**; até 2026-10-17 chamado "modo" Documento, Documento econômico e Foto, renomeado para não confundir com o modo Documento). Cada clique digitaliza uma página da mesa da impressora e grava um arquivo com nome automático. Um seletor **Rápido | Documento** escolhe entre esse modo rápido e o **modo Documento**, em que cada clique acrescenta uma página a um documento em andamento e **Finalizar PDF** grava um único PDF com todas as páginas ([design do documento de várias páginas](2026-10-17-documento-de-varias-paginas.md)).
- **Como fala com a impressora:** direto pelo protocolo **eSCL (AirScan)** usando `httpx`, sem driver nem software HP. É o mesmo protocolo que o Captura de Imagem, o Preview e o NAPS2 usam no Mac. A impressora é encontrada pela **API nativa de DNS-SD do macOS** (via `ctypes`), que enxerga as duas rotas; o app prefere o **cabo USB** e cai para o **Wi-Fi**.
- **Gate 0 concluído (2026-10-17):** a impressora respondeu em eSCL pelas **duas rotas**, com o **mesmo UUID**: pelo **USB** (ponte IPP-over-USB do macOS, em `localhost`, porta dinâmica) e pelo **Wi-Fi** (porta 8080). Capacidades, digitalização, tempos e tamanhos medidos estão na seção 9 e em [docs/gate-0-resultado-2026-10-17.md](../../gate-0-resultado-2026-10-17.md).
- **Limites reais:** a 2874 só tem **vidro** (sem alimentador), então cada página é levantar a tampa. Ciclo medido da máquina: **~10 s** (cinza, 300 dpi), **~19 s** (cor, 300 dpi) e **~77 s** (cor, 600 dpi), mais o tempo de trocar a folha; só o ciclo da máquina soma de 2,8 a 5,3 horas por 1.000 páginas a 300 dpi. O disco interno tem **12 GB livres** (2026-10-17): a pasta padrão `~/Pictures/Digitalizadora` serve, a guarda de espaço continua obrigatória e um disco externo é recomendado só para volumes muito grandes.
- **Exceção à sua regra de nomes aprovada** (seção 3, D6, 2026-10-17): módulos Python importáveis em `snake_case`, porque `import scan-service` é erro de sintaxe; os demais arquivos ficam em kebab-case.
- **Escopo deste plano:** Gate 0 (concluído) + MVP com dois modos: **Rápido** (um clique = um arquivo, Tarefas 1 a 14) e **Documento** (várias páginas num PDF, com miniaturas, nome, reordenar, excluir, descartar a última, cancelar e retomada depois de uma queda, Tarefas 15 a 22), pedido por você em 2026-10-17 para esta versão. Os contratos do modo Documento estão no [design próprio](2026-10-17-documento-de-varias-paginas.md), que complementa este spec. Lote, qualidade de imagem, OCR e app empacotado ficam como roadmap (seção 10), cada um com seu plano depois que o MVP rodar com a impressora real.

---

## 1. O que entendi (corrija o que estiver errado)

**Você pediu** (md.md): software para o MacBook, local, para digitalizar com a HP DeskJet Ink Advantage 2874 uma **quantidade gigante** de documentos e fotos; um **botão** que digitaliza e cria **PDF ou JPG**; uma **opção** no software para escolher PDF ou JPG. **Acrescentado em 2026-10-17:** além do modo rápido, uma opção para criar um **PDF de várias páginas**, adicionando página por página com um botão e clicando em **Finalizar** para gerar um PDF com todas as páginas da sessão (decisões e contratos no [design do documento de várias páginas](2026-10-17-documento-de-varias-paginas.md)).

**Premissas que assumi (confirme ou corrija):**

1. Uso pessoal, só neste MacBook, sem contas nem nuvem.
2. A impressora fica ligada ao Mac pelo cabo USB e também na mesma rede Wi-Fi; o app prefere o USB e usa o Wi-Fi quando o cabo não estiver conectado (as duas rotas funcionaram no Gate 0).
3. "Um botão" pode ser um botão numa página local do navegador mais a tecla Espaço. Ícone no Dock e janela própria ficam para depois.
4. Na v1: uma folha ou uma foto por digitalização, colocada no vidro.
5. Interface em português do Brasil.
6. Os arquivos vão para uma pasta que você escolhe; o padrão é `~/Pictures/Digitalizadora`, no disco interno. Um disco externo é recomendado só para volumes muito grandes.

**Sucesso da v1:** dar duplo clique no launcher, ver "Impressora pronta (USB)" ou "Impressora pronta (Wi-Fi)", apertar Espaço, e cerca de 15 s depois (na qualidade Foto, cerca de 75 s) o arquivo (PDF ou JPG) aparecer na pasta com nome automático e sem nenhum diálogo; repetir sem tocar no mouse; erros explicados em português. No modo Documento: apertar Espaço a cada folha, ver as miniaturas na ordem e apertar Enter para gravar um único PDF; se o app ou o Mac cair no meio, o documento volta ao abrir o app.

**Fora do escopo agora:** vários documentos em andamento ao mesmo tempo, lote, OCR, recorte e rotação automáticos, divisão de várias fotos por varredura, alimentador de folhas, app com ícone, outros scanners.

---

## 2. Fatos que moldam o projeto

Status: **medido** (feito neste Mac; "Gate 0" = medido em 2026-10-17, ver [resultado](../../gate-0-resultado-2026-10-17.md)), **confirmado** (fonte primária), **não verificado** (sem evidência direta).

| Fato | Status | Consequência |
|---|---|---|
| HP DeskJet Ink Advantage 2874 (SKU 6W7G2A): scanner de **mesa** (CIS), sem alimentador nem duplex, 1200 dpi ópticos, vidro 216×297 mm, Wi-Fi **só 2,4 GHz**, **sem botão de scan** | confirmado (HP) e medido (Gate 0: só `Platen`, `duplex=F`) | Cada página é manual; a digitalização só começa por software |
| **eSCL confirmado** nesta unidade (firmware TIP1CN2446AR) por **duas rotas com o mesmo UUID**: **USB**, pela ponte IPP-over-USB do macOS (anunciada pelo mDNSResponder só na interface local `0xFFFFFFFF`, host `localhost.`, porta dinâmica: 57805 no dia; a mesma instância também é resolvida para `localhost.:57805` na interface do Wi-Fi, a 11), e **Wi-Fi** (`<host-da-impressora>.local.`, porta 8080; `_uscans._tcp` na 443, não usado). O XML de capacidades é idêntico byte a byte nas duas rotas | medido (Gate 0) | Seguir com o MVP; preferir o USB e cair para o Wi-Fi (D8); o plano B (HP LEDM) sai do caminho crítico |
| Capacidades reais: modelo "DeskJet Ink Advantage 2800 All-in-One Printer series"; vidro de 2550 × 3508 (em 1/300 pol.); resoluções discretas 75, 100, 150, 200, 300, 400, 600 e 1200; cores `RGB24`, `Grayscale8`, `BlackAndWhite1`; formatos `image/jpeg`, `application/pdf`, `application/octet-stream` | medido (Gate 0) | Presets confirmados; XML real vira fixture de teste (seção 8) |
| Ciclo por página (vidro vazio, A4 inteiro, JPEG): cinza 300 dpi, imagem em 6,7 s e `Idle` em ~10 s (119 KB); cor 300 dpi, imagem em 14,4 s e `Idle` em ~19 s (154 KB, igual no USB e no Wi-Fi); cor 600 dpi, imagem em 71,9 s e `Idle` em ~77 s (663 KB). Páginas com conteúdo ainda não foram medidas | medido (Gate 0) | Textos da interface: "cerca de 15 s; no modo Foto, cerca de 75 s"; tempo limite de leitura de 180 s (seção 6.5) |
| Protocolo nesta impressora: `POST ScanJobs` → 201 com `Location` **absoluto** (`http://localhost:57805/eSCL/ScanJobs/<uuid>`); `GET .../NextDocument` **bloqueia até a imagem ficar pronta** e responde 200 na primeira tentativa (nenhum 503), depois 404; `DELETE` depois desse 404 → **404** (o trabalho já sumiu); depois da entrega, `Processing` por 4–5 s e então `Idle`; o JPEG já vem com a densidade JFIF certa (300 ou 600) | medido (Gate 0) | Regras 3 a 6 da seção 6.2; a impressora falsa imita isso (seção 6.6) |
| `python-zeroconf` 0.151.5 **não enxerga a rota USB** (só devolveu o registro do Wi-Fi; `parsed_addresses()` devolveu IPv6 mesmo com `IPVersion.V4Only`); a API nativa `dns_sd` da libSystem, via `ctypes`, enxerga as duas rotas (sonda de referência em `docs/gate-0-capturas/dns-service-discovery-probe.py`) | medido (Gate 0) | Descoberta pela API nativa (D2, D8); `zeroconf` sai das dependências (seção 6.7) |
| A impressora está **ligada e conectada** pelo cabo USB e pelo Wi-Fi (em 13/10 estava offline) | medido (Gate 0) | Testes de hardware e receitas da seção 12 já podem ser feitos |
| macOS 15.7.3; o único driver de scanner é o **AirScan da Apple** (eSCL); não há driver HP | medido | A impressora anuncia eSCL, então Captura de Imagem, Preview e NAPS2 devem enxergá-la; se o Captura de Imagem a lista ainda não foi testado |
| Privacidade de **Rede Local** (macOS 15) vale para endereços da rede local: a rota USB (`localhost`) **não depende dessa permissão**. A Apple documenta que processos iniciados pelo Terminal.app são isentos e que apps empacotados precisam de permissão; no Gate 0 a rota Wi-Fi respondeu também a partir do shell do Claude Code dentro do VS Code | confirmado (Apple TN3179) e medido (Gate 0) | Pelo USB o app funciona iniciado de qualquer lugar; pelo Wi-Fi, o app que inicia o servidor precisa da permissão de Rede Local (o launcher, que abre o Terminal.app, é o caminho recomendado) |
| Disco interno: 245 GB, **12 GB livres** em 2026-10-17; sem disco externo conectado | medido | Pasta padrão `~/Pictures/Digitalizadora` no disco interno; guarda de espaço livre obrigatória; disco externo recomendado para volumes muito grandes |
| Python 3.12.3 com FastAPI, uvicorn, httpx e Pillow 10.4 já instalados; faltam img2pdf, pikepdf, pytest | medido | Ambiente virtual `.venv` do projeto |
| Sem Xcode.app (só Command Line Tools); Swift 6.2 funciona | medido | Caminho nativo em Swift/SwiftUI descartado para a v1 |
| Nomes de arquivo em kebab-case não podem ser importados em Python | verificado | Exceção aprovada por você em 2026-10-17 (D6) |
| Image Capture, app HP (já instalado) e NAPS2 8.x já digitalizam | confirmado | Você pode escanear hoje (seção 12); construímos só o que falta. O Gate 0 não precisou do app HP |
| macOS 27 saiu em 2026-09-14; a HP só suporta até macOS 13; seu Mac está no 15.7.3 (o 15.8.1 existe) | confirmado | Não atualizar o macOS antes de validar o MVP com a impressora; registrar a build (D10) |

O que o Gate 0 ainda **não** testou está na seção 9.3.

---

## 3. Decisões

**D1 — Escopo em fases.** MVP = Gate 0 + "um clique, um arquivo". Valida o hardware cedo e entrega valor rápido. O Gate 0 foi concluído em 2026-10-17 (seção 9). *Descartado:* construir tudo de uma vez.

**D2 — Motor de digitalização: cliente eSCL direto em Python (`httpx`)** atrás de uma porta `ScannerGateway`. Controla JPEG, região e limpeza do trabalho, não precisa de driver HP e dispensa o loop de eventos do Cocoa. Fluxo verificado em três clientes de referência e medido nesta impressora no Gate 0: descobrir `_uscan._tcp`, `GET ScannerCapabilities`, `GET ScannerStatus`, `POST ScanJobs` (201 + `Location`, absoluto nesta impressora), `GET .../NextDocument` (nesta impressora bloqueia até a imagem e responde 200; em outros firmwares 503 = ainda não pronto; 404 = fim), `DELETE` do trabalho (404 = o trabalho já terminou, também é sucesso). **Descoberta pela API nativa de DNS-SD do macOS** (`dns_sd` da libSystem, chamada por `ctypes`, só biblioteca padrão), porque o `python-zeroconf` não enxerga a rota USB (testado no Gate 0). *Plano B:* não foi necessário (o eSCL funcionou); a seção 9 guarda a tabela de decisão como histórico. *Descartados:* SANE (o Homebrew não tem o backend eSCL), ImageCaptureCore em Swift (sem Xcode, e depende do mesmo eSCL), `python-zeroconf` (não vê a rota USB e devolve IPv6 mesmo pedindo só IPv4).

**D3 — Interface: servidor FastAPI em `127.0.0.1` + página web**, iniciado com duplo clique em `iniciar-digitalizadora.command` (que abre o Terminal.app). Pela rota USB (`localhost`) a privacidade de Rede Local não se aplica, então o app funciona iniciado de qualquer lugar; pela rota Wi-Fi, o app que inicia o servidor precisa da permissão de Rede Local, e o Terminal.app (pelo launcher) é o caminho recomendado. Dispensa assinatura e empacotamento, e usa o que você já tem instalado. Aceita por você para a v1 (seção 13, pergunta 3). *Depois (Fase 5):* app empacotado. *Descartados:* SwiftUI, PySide/Tk, Electron/Tauri.

**D4 — Saída.** O JPEG que vem do scanner é o **mestre**. **JPG** = o mestre com a densidade (dpi) normalizada, sem recomprimir. **PDF** = `img2pdf` coloca os bytes do JPEG dentro do PDF sem recomprimir, com o tamanho de página calculado pelos dpi. A opção PDF/JPG é só o codificador local. *Descartados:* pedir PDF ao scanner (comportamento varia por modelo), Pillow para PDF (recomprime cada página).

**D5 — Armazenamento.** Pasta configurável, padrão `~/Pictures/Digitalizadora` (no disco interno, que tem 12 GB livres em 2026-10-17); disco externo recomendado, não obrigatório, para volumes muito grandes; recusa digitalizar com pouco espaço livre; gravação atômica com `F_FULLFSYNC`; nome `AAAA-MM-DD_NNNNN.ext` sem nunca sobrescrever.

**D6 — Exceção à regra de nomes (aprovada por você em 2026-10-17).** Seguimos todas as suas regras literalmente, exceto: **módulos Python importáveis usam `snake_case`** (`scan_service.py`), inclusive os módulos de teste, porque `import scan-service` é `SyntaxError` (verificado) e `importlib` quebra tipagem, navegação do editor e a descoberta do pytest. **Kebab-case continua valendo** para tudo que não é importado: documentos, scripts, launcher, configuração, arquivos da interface web, fixtures.

**D7 — Segurança da interface local.** Servidor só em `127.0.0.1`; a requisição é recusada se o cabeçalho `Host` não for `127.0.0.1:PORTA` ou `localhost:PORTA` (defesa contra DNS rebinding); métodos que alteram estado (`POST`, `PUT`, `DELETE`) exigem o cabeçalho `X-Requested-With: digitalizadora` (defesa contra CSRF); nenhum CORS. O protocolo eSCL não tem autenticação, então a barreira é o próprio servidor local.

**D8 — Descoberta e conexão.** A API nativa de DNS-SD do macOS procura `_uscan._tcp` no domínio `local.` e resolve cada instância na interface em que ela foi achada. A impressora aparece por **duas rotas com o mesmo UUID**: **USB** (a ponte IPP-over-USB do macOS, anunciada só na interface local `0xFFFFFFFF`, host `localhost`, **porta dinâmica**) e **Wi-Fi** (`<host-da-impressora>.local`, porta 8080). **A rota é classificada pelo host, não só pela interface** (G0C-14): o mDNSResponder também resolve a instância USB para `localhost.:57805` na interface do Wi-Fi (11), então um registro é **USB** quando foi achado na interface `0xFFFFFFFF` **ou** quando o host é um nome de loopback (`localhost`, `127.0.0.1`, `::1`, sem diferenciar maiúsculas); qualquer outro registro é **rede**. A descoberta devolve **primeiro as rotas USB, depois as de rede**, sem endereços-base repetidos (fica a primeira ocorrência). **Uma busca nova por processo** (G0C-15): a primeira conexão de cada execução do app (o primeiro `acquire_gateway` ou `check_connection`) e cada "Procurar de novo" descobrem e escolhem por esta preferência, usando o UUID do endereço salvo: mesmo UUID pelo USB, mesmo UUID pela rede, qualquer USB, qualquer rede. O endereço salvo é só a alternativa final: é usado direto quando a busca não devolve nada (e tentado por último quando nenhum achado responde). Assim, ligar o cabo USB vale na próxima abertura do app ou no "Procurar de novo", e um endereço Wi-Fi salvo nunca prende o app ao Wi-Fi entre reinícios. Depois da escolha, o gateway em memória é reaproveitado; se a checagem de status dele falhar, o app procura de novo (mesma preferência) antes de dizer que não achou a impressora. O endereço escolhido é salvo com o UUID e a rota depois de cada escolha bem-sucedida, e o endereço salvo nunca é apagado antes de uma busca. Há também endereço manual (`http://HOST:PORTA/eSCL`): com host de loopback ele é gravado com rota USB, senão rede (G0C-16); ele vale direto no processo em que foi definido (pela interface ou por `DIGITALIZADORA_SCANNER_ADDRESS`, sem a busca nova) e, num processo seguinte, volta a ser só a alternativa final. Os nomes de host são usados como vêm (`localhost`, `HP….local`); quem resolve `.local` é o sistema. HTTP por padrão (o HTTPS `_uscans`, porta 443, usa certificado autoassinado e não é usado). Para a rota Wi-Fi, reservar o IP da impressora no roteador (MAC termina em `00:00:01`) continua opcional e útil.

**D9 — Testes.** `pytest` + uma impressora falsa (aplicativo ASGI que fala eSCL como a impressora real se comportou no Gate 0, com injeção de falhas) + fixtures XML reais capturadas no Gate 0 (mais fixtures sintéticas para casos de fronteira); relógio e `sleep` injetados para os testes serem rápidos; testes de hardware só rodam com `DIGITALIZADORA_HARDWARE_TESTS=1`.

**D10 — Sistema operacional.** Não atualizar o macOS antes de validar o MVP com a impressora; registrar a build (`sw_vers`) em cada validação; depois de qualquer atualização, repetir a descoberta e uma digitalização real (teste de hardware, seção 8).

---

## 4. Arquitetura

### 4.1 Camadas (regra de dependência: controllers → services → domain ← repositories/infrastructure)

```
Navegador  (index.html + application.js)
   │  HTTP + JSON, somente 127.0.0.1
┌──▼──────────────────────────────────────────────────────────────┐
│ controllers      traduzem HTTP ⇄ serviços; mensagens em pt-BR    │
├─────────────────────────────────────────────────────────────────┤
│ services         regras: ScanService, ScanOutputService,         │
│                  PrinterConnectionService, StorageGuardService…  │
├─────────────────────────────────────────────────────────────────┤
│ domain           modelos, erros e ports (Protocols); não importa  │
│                  nada de fora                                    │
├────────────────────────────┬────────────────────────────────────┤
│ repositories               │ infrastructure                      │
│ arquivos, JSON             │ eSCL (httpx), DNS-SD, relógio       │
└────────────────────────────┴────────────────────────────────────┘
composition_root.py monta tudo (injeção por construtor); nada de estado global
```

### 4.2 Mapa de arquivos (e a tarefa do plano que cria cada um)

```
digitalizadora/
├── .gitignore  Makefile  pyproject.toml  README.md                  T1, T13
├── iniciar-digitalizadora.command                                   T13
├── docs/gate-0-resultado-2026-10-17.md, docs/gate-0-capturas/        T0 (Gate 0 concluído; nada a criar)
├── src/digitalizadora/
│   ├── __init__.py  __main__.py  configuration.py                   T1, T13
│   ├── composition_root.py  application_factory.py                  T13, T11
│   ├── domain/        modelos (inclusive scanner_route.py), errors.py, ports.py, naming policy   T2
│   ├── services/      encode/store/scan/connection/state/guard      T6, T8, T9, T10, T11
│   ├── repositories/  atomic writer, output folder preparer, output, JSON ×2   T7
│   ├── infrastructure/escl/  protocol + gateway                     T3, T5
│   ├── infrastructure/bonjour_scanner_discovery.py, dns_service_discovery_record_source.py   T9
│   ├── infrastructure/system_clock.py                               T2
│   ├── controllers/   guard, catálogo de mensagens, 5 controllers   T11
│   ├── simulator/     impressora falsa (ASGI) + __main__            T4
│   └── web/static/    index.html, application.css, application.js   T12
└── tests/  (espelha src; fakes/, fixtures/)                         em cada tarefa
    └── integration/, hardware/                                      T14
```

### 4.3 Uma digitalização (sequência)

```
Navegador      ScanController   ScanService        Tracker   PrinterConnection   EsclGateway     OutputService
  │ POST /api/scans  │              │                 │            │                  │               │
  │─────────────────▶│ 202          │                 │            │                  │               │
  │                  │─background──▶│ begin_scan ────▶│ (409 se ocupado)             │               │
  │                  │              │ ensure_capacity ──────────────────────────────────────────────▶│ espaço livre
  │                  │              │ acquire_gateway ────────────▶│ 1ª vez no processo: DNS-SD (USB 1º); depois, gateway em memória
  │                  │              │ mark_scanning ─▶│            │                  │               │
  │                  │              │ scan_page ───────────────────────────────────▶│ status → POST → NextDocument → DELETE
  │                  │              │ mark_saving ───▶│            │                  │               │
  │                  │              │ store ────────────────────────────────────────────────────────▶│ JPEG/PDF + thumbnail + arquivo
  │                  │              │ mark_completed ▶│            │                  │               │
  │ GET /api/state (a cada 0,5 s durante o scan; 2 s parado)       │                  │               │
```

### 4.4 Erros e mensagens

O código de erro viaja pelo sistema; o texto em português só existe no `ErrorMessageCatalog` (camada de controllers).

| Código | Quando | Mensagem ao usuário |
|---|---|---|
| `scanner_unreachable` | não achou ou não conectou | "Não encontrei a impressora. Confira se está ligada e com o cabo USB conectado ao Mac. Sem o cabo, confira se a luz do Wi-Fi está acesa e se ela está na mesma rede do Mac (2,4 GHz)." |
| `local_network_blocked` | `errno 65` (EHOSTUNREACH) ao falar com a rede local (só na rota Wi-Fi) | "O macOS pode estar bloqueando o acesso à rede local. Conecte a impressora pelo cabo USB, que não depende dessa permissão, ou abra o Digitalizadora pelo arquivo iniciar-digitalizadora.command (ele abre o Terminal.app) e confira Ajustes > Privacidade e Segurança > Rede Local." |
| `scanner_busy` | estado diferente de Idle depois de esperar | "A impressora está ocupada. Aguarde alguns segundos e tente de novo." |
| `scan_rejected` | 400/409 no `POST ScanJobs`, ou ajuste não suportado | "A impressora recusou os ajustes desta digitalização." |
| `scan_failed` | 500, imagem inválida, formato inesperado | "A digitalização falhou. Confira se a tampa está fechada e tente de novo." |
| `scan_timed_out` | passou do tempo máximo | "A impressora demorou demais para responder." |
| `scan_already_running` | segundo gatilho durante um scan | "Já existe uma digitalização em andamento." |
| `insufficient_storage` | pouco espaço livre | "Pouco espaço livre na pasta de saída. Use um disco externo ou libere espaço." |
| `output_folder_unavailable` | pasta inexistente ou sem permissão | "Não consigo gravar na pasta de saída. Se for um disco externo, confira se está conectado." |
| `invalid_settings` | ajustes inválidos na API | "Ajustes inválidos." |
| `unexpected_error` | qualquer outra falha | "Algo inesperado aconteceu. Veja o registro em ~/Library/Logs/Digitalizadora." |

A privacidade de Rede Local do macOS só afeta a rota Wi-Fi: pela rota USB (`localhost`) o app funciona iniciado de qualquer lugar. Por isso as duas primeiras mensagens sugerem o cabo USB, inclusive na primeira execução, quando a busca não acha nada (uma busca vazia pela rede, sem `errno 65`, aparece como `scanner_unreachable`). Nenhum texto diz que o app "só funciona" pelo Terminal.app.

### 4.5 Persistência e arquivos

- Ajustes: `~/Library/Application Support/Digitalizadora/settings.json` e `scanner-endpoint.json` (escritos de forma atômica). O `scanner-endpoint.json` guarda endereço-base, nome, UUID e rota (`usb` ou `network`; arquivo antigo sem a chave é lido como `network`).
- Registro (log): `~/Library/Logs/Digitalizadora/digitalizadora.log` (rotativo).
- Saída: `<pasta de saída>/AAAA-MM-DD_NNNNN.pdf|jpg`, com contador de 5 dígitos por dia. O contador é calculado pelo maior número já existente na pasta para a data, e a criação usa exclusão mútua (nunca sobrescreve).
- Gravação: arquivo temporário `.part` na mesma pasta → `F_FULLFSYNC` (com fallback para `fsync`) → `os.link` para o nome final (falha se existir) ou, se o volume não suportar *hard link* (por exemplo exFAT), `os.rename` depois de checar que não existe → apaga o `.part` → `fsync` da pasta.

---

## 5. Convenções de código (valem para o plano inteiro)

**Suas regras (`~/.claude/rules`):** módulos pequenos e com baixo acoplamento; injeção de dependência (por construtor, composta em `composition_root.py`); separação em Controllers, Services e Repositories. Nomes: arquivos em kebab-case, classes em PascalCase, funções e variáveis em snake_case, constantes em UPPER_SNAKE_CASE, tabelas de banco em snake_case; **sem abreviações** (`id`, `url`…); nomes descritivos.

**Interpretação adotada** (diga se discorda): siglas que são o *nome* de um formato ou protocolo ficam (`PDF`, `JPEG`, `HTTP`, `XML`, `eSCL`, `JSON`, `OCR`); abreviações de palavras comuns são proibidas. Padronização: `identifier` (não `id`), `universally_unique_identifier` (não `uuid`), `base_address` (não `url`), `dots_per_inch` (não `dpi`), `configuration`, `repository`, `message`, `directory`/`folder`, `maximum`/`minimum`, `image`, `temporary`. Diretórios `src` e `tests` e os nomes definidos por ferramentas (`pyproject.toml`, `Makefile`, `.venv`) seguem a convenção das ferramentas. Em JavaScript valem as mesmas regras (funções e variáveis em snake_case, classes em PascalCase).

**Clean Code (suas skills `python-clean-code`):**

- No máximo **3 argumentos** por função ou método (contando o construtor, sem contar `self`); mais que isso vira dataclass.
- Sem argumentos "flag" (booleanos que mudam o comportamento); sem argumentos de saída.
- Constantes nomeadas no lugar de números mágicos; `Enum` no lugar de strings soltas; type hints em toda interface pública.
- Comentário só quando explica o *porquê* ou uma unidade; nunca código comentado.
- Um conceito por teste; testes rápidos (menos de 100 ms cada); casos de fronteira (vazio, limite exato, um acima, um abaixo).

**Estrutura dos testes:** `tests/<camada>/test_<módulo>.py` (snake_case por exigência do pytest e do import), com `__init__.py` em cada pasta; `asyncio_mode = "auto"`; marcador `hardware` ignorado por padrão.

---

## 6. Contratos (autoridade para o plano)

Assinaturas, não implementações (as implementações estão no plano). Os caminhos são relativos a `src/digitalizadora/`. **Qualquer mudança de nome ou assinatura precisa ser feita aqui primeiro.**

### 6.1 `domain/`

```python
# output_format.py
class OutputFormat(str, Enum):
    PDF = "pdf"
    JPEG = "jpg"
    @property
    def file_extension(self) -> str: ...            # "pdf" | "jpg"

# color_mode.py
class ColorMode(str, Enum):
    COLOR = "color"
    GRAYSCALE = "grayscale"

# scan_settings.py
@dataclass(frozen=True)
class ScanSettings:
    dots_per_inch: int
    color_mode: ColorMode

# scan_preset.py
class ScanPreset(str, Enum):
    DOCUMENT = "document"                  # 300 dots per inch, color
    DOCUMENT_ECONOMY = "document_economy"  # 200 dots per inch, grayscale
    PHOTO = "photo"                        # 600 dots per inch, color
    @property
    def settings(self) -> ScanSettings: ...

# scan_request.py
@dataclass(frozen=True)
class ScanRequest:
    settings: ScanSettings
    output_format: OutputFormat

# scan_job.py
@dataclass(frozen=True)
class ScanJob:
    request: ScanRequest
    started_at: datetime                   # timezone-aware, from Clock

# scanner_route.py
LOOPBACK_HOST_NAMES = frozenset({"localhost", "127.0.0.1", "::1"})
class ScannerRoute(str, Enum):
    USB = "usb"                            # ponte IPP-over-USB: interface 0xFFFFFFFF ou host de loopback (G0C-14)
    NETWORK = "network"                    # qualquer outro registro (Wi-Fi)
def route_for_host_name(host_name: str) -> ScannerRoute: ...   # função pura (G0C-16), testada na Tarefa 2
    # USB quando host_name, sem diferenciar maiúsculas, está em LOOPBACK_HOST_NAMES; senão NETWORK.
    # Recebe o nome já normalizado: sem ponto final e, para IPv6, sem colchetes ("::1", não "[::1]").
    # Regra única de loopback: usada por classify_route (seção 6.2) e por use_manual_address (seção 6.4).

# scanner_endpoint.py
@dataclass(frozen=True)
class ScannerEndpoint:
    base_address: str                      # "http://localhost:57805/eSCL" (USB) ou
                                           # "http://HP000000000001.local:8080/eSCL" (Wi-Fi); sem barra no fim
    display_name: str
    universally_unique_identifier: str | None = None
    route: ScannerRoute = ScannerRoute.NETWORK   # último campo, com padrão: construções antigas continuam válidas

# scanner_capabilities.py
@dataclass(frozen=True)
class ScannerCapabilities:
    make_and_model: str
    platen_maximum_width: int              # unidades eSCL: 1/300 de polegada
    platen_maximum_height: int
    supported_resolutions: tuple[int, ...] # dots per inch, ordem crescente
    supported_color_modes: tuple[str, ...] # nomes eSCL: "RGB24", "Grayscale8", "BlackAndWhite1"
    supported_document_formats: tuple[str, ...]  # tipos de mídia: "image/jpeg", "application/pdf"
    def closest_supported_resolution(self, requested_dots_per_inch: int) -> int: ...
        # menor suportada >= pedida; se nenhuma, a maior; se a lista for vazia, a pedida
    def supports_color_mode(self, escl_color_mode: str) -> bool: ...

# scanner_status.py
class ScannerState(str, Enum):
    IDLE = "idle"; PROCESSING = "processing"; TESTING = "testing"
    STOPPED = "stopped"; DOWN = "down"; UNKNOWN = "unknown"

@dataclass(frozen=True)
class ScannerStatus:
    state: ScannerState
    @property
    def is_ready(self) -> bool: ...        # state is IDLE

# scanned_image.py
@dataclass(frozen=True)
class ScannedImage:
    content: bytes
    media_type: str                        # esperado: "image/jpeg"

# encoded_scan.py
@dataclass(frozen=True)
class EncodedScan:
    content: bytes                         # arquivo final (PDF ou JPEG)
    output_format: OutputFormat
    created_at: datetime
    thumbnail_jpeg: bytes

# scan_result.py
@dataclass(frozen=True)
class ScanResult:
    output_path: Path
    output_format: OutputFormat
    scanned_at: datetime
    size_in_bytes: int

# stored_scan.py
@dataclass(frozen=True)
class StoredScan:
    result: ScanResult
    thumbnail_jpeg: bytes

# application_settings.py
@dataclass(frozen=True)
class ApplicationSettings:
    output_folder: Path
    output_format: OutputFormat
    scan_preset: ScanPreset
    def to_scan_request(self) -> ScanRequest: ...

# scan_progress.py
class ScanPhase(str, Enum):
    IDLE = "idle"; PREPARING = "preparing"; SCANNING = "scanning"; SAVING = "saving"

@dataclass(frozen=True)
class ScanProgressSnapshot:
    phase: ScanPhase
    scans_completed: int
    last_result: ScanResult | None
    last_error_code: str | None

# errors.py  (mensagens internas em inglês; o texto em português fica nos controllers)
class DigitalizadoraError(Exception):          code = "unexpected_error"
class ScannerUnreachableError(DigitalizadoraError):    code = "scanner_unreachable"
class LocalNetworkBlockedError(ScannerUnreachableError): code = "local_network_blocked"
class ScannerBusyError(DigitalizadoraError):           code = "scanner_busy"
class ScanRejectedError(DigitalizadoraError):          code = "scan_rejected"
class ScanFailedError(DigitalizadoraError):            code = "scan_failed"
class ScanTimedOutError(DigitalizadoraError):          code = "scan_timed_out"
class ScanAlreadyRunningError(DigitalizadoraError):    code = "scan_already_running"
class InsufficientStorageError(DigitalizadoraError):   code = "insufficient_storage"
class OutputFolderUnavailableError(DigitalizadoraError): code = "output_folder_unavailable"
class InvalidSettingsError(DigitalizadoraError):       code = "invalid_settings"

# scan_file_naming_policy.py   (regra pura; sem I/O)
class ScanFileNamingPolicy:
    def build_file_name(self, scanned_at: datetime, sequence_number: int,
                        output_format: OutputFormat) -> str: ...   # "2026-10-13_00007.pdf"
    def extract_sequence_number(self, file_name: str, scanned_at: datetime) -> int | None: ...
    # Só nomes exatamente "AAAA-MM-DD_NNNNN.pdf" ou ".jpg" (minúsculas, 5 ou mais dígitos, sequência >= 1)
    # da MESMA data devolvem o número; qualquer outro nome (outra data, outra extensão, lixo, arquivo ".part") devolve None.

# ports.py
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
    def ensure_output_folder_ready(self) -> None: ...   # cria a pasta e confirma que dá para gravar; OutputFolderUnavailableError
    def save(self, encoded_scan: EncodedScan) -> Path: ...
```

Presets: `DOCUMENT` = 300 dpi cor; `DOCUMENT_ECONOMY` = 200 dpi cinza; `PHOTO` = 600 dpi cor. Confirmados no Gate 0: a impressora oferece 200, 300 e 600 dpi, e 600 dpi em cor funcionou (71,9 s até a imagem, 663 KB numa página em branco).

### 6.2 `infrastructure/`

```python
# escl/escl_protocol.py   (funções puras)
ESCL_UNITS_PER_INCH = 300
def build_scan_settings_xml(settings: ScanSettings, capabilities: ScannerCapabilities) -> bytes: ...
def parse_scanner_capabilities(document: bytes) -> ScannerCapabilities: ...
def parse_scanner_status(document: bytes) -> ScannerStatus: ...
# As duas funções de parse levantam ScanFailedError (mensagem em inglês) para XML malformado, fora do formato
# eSCL ou com "<!ENTITY"; nenhum ParseError/ValueError escapa delas.
def extract_job_path(location_header: str) -> str: ...   # só o caminho; ignora o host do cabeçalho
# (esta impressora manda URL absoluta: "http://localhost:57805/eSCL/ScanJobs/<uuid>" → "/eSCL/ScanJobs/<uuid>")

# escl/escl_scanner_gateway.py
@dataclass(frozen=True)
class EsclGatewayTiming:
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    monotonic_clock: Callable[[], float] = time.monotonic
    document_poll_interval_seconds: float = 1.5
    busy_wait_seconds: float = 30.0
    scan_timeout_seconds: float = 300.0
    cleanup_timeout_seconds: float = 10.0
# Nenhum tempo limite por requisição dentro do gateway pode deixar a leitura do NextDocument abaixo de 180 s
# (nesta impressora o GET bloqueia até ~75 s a 600 dpi; ver build_scanner_http_client na seção 6.5).

class EsclScannerGateway:                      # implementa ScannerGateway
    def __init__(self, http_client: httpx.AsyncClient, base_address: str,
                 timing: EsclGatewayTiming) -> None: ...
    async def read_capabilities(self) -> ScannerCapabilities: ...   # em cache por instância
    async def read_status(self) -> ScannerStatus: ...
    async def scan_page(self, settings: ScanSettings) -> ScannedImage: ...

# bonjour_scanner_discovery.py          (sem rede; 100% testável em unidade)
@dataclass(frozen=True)
class ServiceRecord:
    instance_name: str
    host_name: str                             # "localhost" ou "HP000000000001.local" (sem ponto no fim)
    port: int
    properties: Mapping[str, str]              # chaves em minúsculas ("rs", "uuid", "ty", "note"…)
    route: ScannerRoute                        # classify_route(interface, host_name): USB na interface 0xFFFFFFFF
                                               # ou com host de loopback; senão NETWORK (G0C-14)
class ServiceRecordSource(Protocol):
    async def collect_records(self, timeout_seconds: float) -> list[ServiceRecord]: ...
def build_scanner_endpoint(record: ServiceRecord) -> ScannerEndpoint: ...   # função pura
    # base_address = "http://<host_name>:<port>/<rs sem barras, padrão eSCL>"; copia route e o UUID.
    # O nome de host é usado como veio (nada de resolver IPv4 no nosso código; o sistema resolve ".local").
class BonjourScannerDiscovery:                 # implementa ScannerDiscovery
    def __init__(self, record_source: ServiceRecordSource) -> None: ...
    async def discover(self, timeout_seconds: float) -> list[ScannerEndpoint]: ...
    # Devolve primeiro os endpoints de rota USB e depois os de rede, mantendo a ordem dentro de cada grupo;
    # depois dessa ordenação, remove duplicatas por base_address: fica a primeira ocorrência (G0C-14). Assim a
    # instância USB resolvida também na interface do Wi-Fi ("http://localhost:57805/eSCL" duas vezes) vira um
    # endpoint só, e as duas rotas da mesma impressora (mesmo UUID, endereços diferentes) continuam na lista.

# dns_service_discovery_record_source.py   (rede real; coberta só pelo teste de hardware)
def parse_text_record(raw_text_record: bytes) -> dict[str, str]: ...   # função pura, testada sem rede
    # Entradas TXT com prefixo de tamanho; chaves em minúsculas; valor = tudo depois do primeiro "=";
    # entrada sem "=" vira chave com valor "".
def normalize_host_name(host_target: str) -> str: ...                 # função pura: tira o ponto final
LOCAL_ONLY_INTERFACE_INDEX = 0xFFFFFFFF        # kDNSServiceInterfaceIndexLocalOnly (uint32_t, sem sinal)
def classify_route(interface_index: int, host_name: str) -> ScannerRoute: ...   # função pura, testada sem rede
    # G0C-14: USB quando interface_index == LOCAL_ONLY_INTERFACE_INDEX OU route_for_host_name(host_name) é USB
    # (host_name já passou por normalize_host_name); senão NETWORK. Ex.: (0xFFFFFFFF, "localhost") → USB;
    # (11, "localhost") → USB; (11, "HP000000000001.local") → NETWORK.
class DnsServiceDiscoveryRecordSource:         # implementa ServiceRecordSource
    def __init__(self) -> None: ...
    async def collect_records(self, timeout_seconds: float) -> list[ServiceRecord]: ...
    # API nativa dns_sd do macOS: ctypes.CDLL("/usr/lib/libSystem.B.dylib"). Dentro de asyncio.to_thread,
    # um laço bloqueante com select: DNSServiceBrowse de "_uscan._tcp" em "local." durante timeout_seconds,
    # depois DNSServiceResolve de cada instância na interface em que foi achada; a rota de cada registro
    # resolvido vem de classify_route(interface da resposta, nome de host normalizado). Os callbacks ficam
    # referenciados enquanto estão em uso; cada DNSServiceRef é desalocado (DNSServiceRefDeallocate) num finally.
    # Referência que funcionou no Gate 0: docs/gate-0-capturas/dns-service-discovery-probe.py.
    # (O python-zeroconf não serve: não enxerga a rota USB, que só é anunciada na interface local 0xFFFFFFFF.)

# system_clock.py
class SystemClock:                             # implementa Clock
    def now(self) -> datetime: ...             # horário local com fuso
```

**Regras do protocolo eSCL que o código precisa seguir** (de `sane-airscan`, NAPS2 e `escl-scanner-cli`, ver digest §3; conferidas com a impressora real no Gate 0):

1. Endereço-base = `http://HOST:PORTA/<valor de rs sem barras, padrão eSCL>`, com o nome de host do anúncio como veio (`localhost` na rota USB); nunca fixar porta nem caminho (a porta USB muda).
2. XML do `ScanSettings` em **uma linha só**, começando pela declaração `<?xml version="1.0" encoding="UTF-8"?>` colada ao elemento raiz `scan:ScanSettings` (que declara `xmlns:pwg` e depois `xmlns:scan`, nessa ordem, como o `sane-airscan`); prefixo `pwg` em `Version`, `ScanRegions`, `ScanRegion`, `ContentRegionUnits`, `XOffset`, `YOffset`, `Width`, `Height`, `InputSource` e `DocumentFormat`; prefixo `scan` em `ColorMode`, `XResolution` e `YResolution`; filhos de `ScanRegion` na ordem `ContentRegionUnits`, `XOffset`, `YOffset`, `Width`, `Height`. Namespaces `pwg=http://www.pwg.org/schemas/2010/12/sm` e `scan=http://schemas.hp.com/imaging/escl/2011/05/03`, `pwg:Version` 2.0, região com o texto literal `escl:ThreeHundredthsOfInches` (prefixo não declarado), `Width`/`Height` = `platen_maximum_width`/`platen_maximum_height` (sempre o vidro inteiro: na v1 **não há recorte**, a página tem o tamanho do vidro, 216 × 297 mm; o recorte no Mac é a Fase 3), `InputSource` = `Platen`, sem `Duplex`, `DocumentFormat` = `image/jpeg`, `ColorMode` = `RGB24` ou `Grayscale8`, `XResolution` e `YResolution` = resolução suportada mais próxima. Ordem canônica: `Version`, `ScanRegions`, `InputSource`, `ColorMode`, `DocumentFormat`, `XResolution`, `YResolution`.
3. `GET ScannerStatus` antes do `POST`: se não estiver `Idle`, esperar até `busy_wait_seconds`, consultando a cada 2 s, e então `ScannerBusyError`. Nesta impressora o estado fica `Processing` por 4–5 s depois de cada entrega, então a digitalização seguinte normalmente espera um pouco aqui.
4. `POST ScanJobs` com `Content-Type: text/xml`: 201 + `Location` (usar só o caminho; nesta impressora o `Location` é absoluto e o identificador do trabalho é um UUID); 503 → `ScannerBusyError`; 400/409 → `ScanRejectedError`; outros → `ScanFailedError`.
5. `GET <caminho do trabalho>/NextDocument`: 200 = imagem; 503 = ainda não está pronta (esperar `document_poll_interval_seconds` e repetir); 404 antes da primeira página = repetir algumas vezes; 500 → `ScanFailedError`; passou de `scan_timeout_seconds` → `ScanTimedOutError`. **Nesta impressora o caminho normal é um único GET que bloqueia até a imagem ficar pronta (71,9 s a 600 dpi em cor) e responde 200**, sem nenhum 503; o laço de 503 fica porque outros firmwares o usam. Os testes cobrem: 200 na primeira requisição sem nenhuma chamada a `sleep`; 503 N vezes e depois 200; 404 antes da primeira página repetido; e o tempo de leitura esgotado só vira `ScanTimedOutError` depois de `scan_timeout_seconds`.
6. Sempre `DELETE <caminho do trabalho>` ao final (sucesso ou erro). 2xx **e 404** são sucesso (nesta impressora o trabalho some sozinho depois do 404 do `NextDocument`, e o `DELETE` responde 404). Qualquer outro status ou erro de transporte vira um aviso no registro (nível warning) e nunca é levantado, tanto no caminho de sucesso quanto no de erro; o erro original, se houver, sempre prevalece.
7. Requisições **sequenciais**, sem seguir redirecionamentos, sem reaproveitar conexão entre trabalhos; o parser XML ignora namespaces e normaliza `<!doctype` em minúsculas.
8. `httpx.ConnectError`, tempos de conexão esgotados e erros de rede viram `ScannerUnreachableError`; quando a causa for `OSError` com `errno 65` vira `LocalNetworkBlockedError` (só acontece na rota Wi-Fi; a rota USB é `localhost` e não passa pela privacidade de Rede Local).
9. Validar a resposta: tipo `image/jpeg` e bytes iniciais `FF D8`; senão `ScanFailedError`. (Esta impressora já manda o JPEG com a densidade JFIF certa; a normalização de dpi da seção 6.4 continua, por robustez.)

### 6.3 `repositories/`

```python
# atomic_file_writer.py
class AtomicFileWriter:
    def write_new_file(self, destination: Path, content: bytes) -> None: ...  # FileExistsError se já existir
    def replace_file(self, destination: Path, content: bytes) -> None: ...    # troca atômica (JSON)

# file_system_scan_output_repository.py          implementa ScanOutputRepository
class FileSystemScanOutputRepository:
    def __init__(self, settings_repository: ApplicationSettingsRepository,
                 naming_policy: ScanFileNamingPolicy, file_writer: AtomicFileWriter) -> None: ...
    def output_folder(self) -> Path: ...
    def ensure_output_folder_ready(self) -> None: ...         # chama prepare_output_folder(self.output_folder())
    def save(self, encoded_scan: EncodedScan) -> Path: ...
    # OutputFolderUnavailableError se não puder gravar; OSError com errno ENOSPC ou EDQUOT (disco cheio no meio
    # da gravação) vira InsufficientStorageError, não OutputFolderUnavailableError.

# output_folder_preparer.py                      (função de sistema de arquivos; sem estado)
def prepare_output_folder(folder: Path) -> None: ...   # mkdir(parents=True, exist_ok=True) + prova de escrita
                                                       # (cria e apaga um arquivo temporário); OutputFolderUnavailableError

# json_scanner_endpoint_repository.py            implementa ScannerEndpointRepository
class JsonScannerEndpointRepository:
    def __init__(self, storage_file: Path, file_writer: AtomicFileWriter) -> None: ...
    # Guarda e lê base_address, display_name, universally_unique_identifier e route ("usb" | "network");
    # arquivo sem a chave "route" é lido como ScannerRoute.NETWORK.

# json_application_settings_repository.py        implementa ApplicationSettingsRepository
class JsonApplicationSettingsRepository:
    def __init__(self, storage_file: Path, default_settings: ApplicationSettings,
                 file_writer: AtomicFileWriter) -> None: ...
```

### 6.4 `services/`

```python
# jpeg_resolution_service.py
class JpegResolutionService:
    def with_resolution(self, jpeg_content: bytes, dots_per_inch: int) -> bytes: ...
    # Reescreve ou insere o segmento JFIF APP0 (unidade = pontos por polegada, densidade X = Y = dots_per_inch)
    # SEM recodificar a imagem. Se não for JPEG (não começa com FF D8): ScanFailedError.

# pdf_assembly_service.py
@dataclass(frozen=True)
class PdfDocumentSpecification:
    dots_per_inch: int
    title: str
    created_at: datetime
class PdfAssemblyService:
    def build_pdf(self, jpeg_pages: Sequence[bytes], specification: PdfDocumentSpecification) -> bytes: ...
    # img2pdf com layout de dpi fixo; os bytes JPEG entram no PDF sem recompressão.

# thumbnail_service.py
class ThumbnailService:
    def build_thumbnail(self, jpeg_content: bytes, maximum_edge_pixels: int) -> bytes: ...  # JPEG

# scan_encoder.py
class ScanEncoder:
    def __init__(self, jpeg_resolution_service: JpegResolutionService,
                 pdf_assembly_service: PdfAssemblyService, thumbnail_service: ThumbnailService) -> None: ...
    def encode(self, scanned_image: ScannedImage, job: ScanJob) -> EncodedScan: ...
    # Valida image/jpeg; normaliza dpi; PDF se pedido; thumbnail de 480 px; created_at = job.started_at.

# storage_guard_service.py
def read_free_space_in_bytes(folder: Path) -> int: ...      # OutputFolderUnavailableError se a pasta não existir (sem subir para o pai)
class StorageGuardService:
    def __init__(self, free_space_reader: Callable[[Path], int] = read_free_space_in_bytes) -> None: ...
    def ensure_space_for_scan(self, folder: Path, settings: ScanSettings) -> None: ...  # InsufficientStorageError
    def estimate_pages_remaining(self, folder: Path, settings: ScanSettings) -> int: ...
    def free_space_in_bytes(self, folder: Path) -> int: ...
    # Regra: livre >= MINIMUM_FREE_SPACE_BYTES (1 GiB) + 3 x tamanho estimado de uma página.
    # Estimativa: vidro 8,5 x 11,69 pol.; bytes por pixel 0,12 (cor) e 0,08 (cinza). Valor conservador: no Gate 0
    # páginas em branco mediram bem menos (154 KB a 300 dpi em cor); páginas com conteúdo ainda não foram medidas.

# scan_output_service.py
class ScanOutputService:
    def __init__(self, scan_encoder: ScanEncoder, scan_output_repository: ScanOutputRepository,
                 storage_guard_service: StorageGuardService) -> None: ...
    def ensure_capacity(self, request: ScanRequest) -> None: ...
    # 1º repository.ensure_output_folder_ready() (OutputFolderUnavailableError ANTES de pedir a página à
    # impressora, senão a página de 15 a 75 s se perderia); 2º storage_guard.ensure_space_for_scan(...).
    def store(self, scanned_image: ScannedImage, job: ScanJob) -> StoredScan: ...

# scan_progress_tracker.py
class ScanProgressTracker:
    def __init__(self, clock: Clock) -> None: ...
    def begin_scan(self, request: ScanRequest) -> ScanJob: ...
    # phase IDLE → PREPARING e limpa last_error_code. Se phase != IDLE: ScanAlreadyRunningError,
    # SEM alterar o estado (o scan em curso continua intacto).
    def mark_scanning(self) -> None: ...
    def mark_saving(self) -> None: ...
    def mark_completed(self, stored_scan: StoredScan) -> None: ...
    def mark_failed(self, error_code: str) -> None: ...
    def snapshot(self) -> ScanProgressSnapshot: ...
    def last_thumbnail_jpeg(self) -> bytes | None: ...

# scan_service.py
class ScanService:
    def __init__(self, gateway_provider: ScannerGatewayProvider,
                 scan_output_service: ScanOutputService, progress_tracker: ScanProgressTracker) -> None: ...
    def is_scan_in_progress(self) -> bool: ...                # usado pelo controller para responder 409
    async def scan_one_file(self, request: ScanRequest) -> ScanResult: ...
    # begin_scan (FORA do try: ScanAlreadyRunningError sobe sem mexer no estado) → ensure_capacity →
    # acquire_gateway → mark_scanning → scan_page → mark_saving → store (em thread, via
    # asyncio.to_thread) → mark_completed. Dentro do try, em qualquer DigitalizadoraError:
    # mark_failed(error.code) e relança; em outra exceção: mark_failed("unexpected_error") e relança.

# printer_connection_service.py
@dataclass(frozen=True)
class PrinterConnectionState:
    connected: bool
    display_name: str | None
    scanner_state: ScannerState | None
    error_code: str | None
    route: ScannerRoute | None = None          # rota do endpoint em uso; None quando não há conexão
    # Ordem dos campos = ordem das chaves de GET /api/printer (seção 6.5), com error_code virando "error".
class PrinterConnectionService:                 # implementa ScannerGatewayProvider
    def __init__(self, discovery: ScannerDiscovery, endpoint_repository: ScannerEndpointRepository,
                 gateway_factory: Callable[[ScannerEndpoint], ScannerGateway]) -> None: ...
    async def acquire_gateway(self) -> ScannerGateway: ...
    # G0C-15 (prevalece sobre G0C-4). Busca nova uma vez por processo:
    # 1. Sem gateway em memória (o primeiro acquire_gateway ou o primeiro check_connection do processo, o que vier
    #    antes, ou depois de uma tentativa em que nada respondeu; a exceção é logo depois de use_manual_address,
    #    abaixo): descobre e ordena pela preferência abaixo, usando o UUID do endpoint
    #    salvo como referência; usa o primeiro candidato cujo read_status responde (estado DOWN, resposta
    #    inutilizável ou erro de transporte contam como "não respondeu"). O endpoint salvo é só a alternativa
    #    final: usado direto quando a descoberta não devolve nada, e tentado por último quando nenhum candidato
    #    descoberto responde (se o endereço dele não estava entre os descobertos). Nada respondeu →
    #    ScannerUnreachableError (LocalNetworkBlockedError tem prioridade se algum candidato o levantou).
    # 2. Depois da escolha, o gateway em memória é reaproveitado: cada acquire_gateway / check_connection confere
    #    o read_status dele; se falhar, esquece o gateway e descobre de novo (mesma preferência, mesmo UUID de
    #    referência) antes de levantar ScannerUnreachableError.
    # Preferência entre os descobertos: mesmo UUID do salvo e rota USB; mesmo UUID na rede; qualquer USB;
    # qualquer rede (o serviço não depende da ordem que a descoberta devolve).
    # Depois de cada escolha bem-sucedida grava o endpoint escolhido (com UUID e rota), mesmo que seja igual ao
    # salvo. O endpoint salvo nunca é apagado (F-06). Consequência: ligar o cabo USB vale na próxima abertura do
    # app ou no refresh ("Procurar de novo"); um endpoint Wi-Fi salvo nunca prende o app ao Wi-Fi entre reinícios.
    async def check_connection(self) -> PrinterConnectionState: ...   # mesmas regras de acquire_gateway; nunca levanta
    async def refresh(self) -> PrinterConnectionState: ...   # esquece o gateway em memória e procura de novo
    # Sempre faz a busca nova do passo 1 (mesma preferência, mesmo UUID de referência, salvo como alternativa
    # final), inclusive depois de use_manual_address. NÃO apaga o endpoint salvo antes de procurar. Nunca levanta.
    def use_manual_address(self, base_address: str) -> None: ...
    # Só grava o endereço (display_name "Manual", sem UUID, sem barra no fim) e esquece o gateway em memória;
    # NÃO conecta. Rota (G0C-16): route_for_host_name(urlsplit(base_address).hostname or "") — USB quando o host é
    # de loopback ("http://localhost:57805/eSCL", "http://127.0.0.1:8080/eSCL", "http://[::1]:8080/eSCL"),
    # senão NETWORK. Conta como a escolha deste processo: o próximo acquire_gateway / check_connection usa esse
    # endereço direto, com a checagem de status do passo 2 (sem a busca nova do passo 1); se a checagem falhar,
    # descobre de novo antes de levantar. Por isso DIGITALIZADORA_SCANNER_ADDRESS (aplicado na partida, seção 6.5)
    # fixa o endereço do processo e a impressora falsa dos testes nunca dispara a descoberta real enquanto
    # responde. Num processo seguinte sem a variável, o endereço manual salvo volta a ser só a alternativa final.
    # Quem quiser o estado chama check_connection() depois.

# application_settings_service.py
@dataclass(frozen=True)
class SettingsUpdate:
    output_folder: str
    output_format: str
    scan_preset: str
class ApplicationSettingsService:
    def __init__(self, settings_repository: ApplicationSettingsRepository,
                 folder_preparer: Callable[[Path], None]) -> None: ...   # a raiz de composição injeta prepare_output_folder
    def current(self) -> ApplicationSettings: ...
    def update(self, update: SettingsUpdate) -> ApplicationSettings: ...
    # Pasta precisa ser caminho absoluto; formato e preset precisam existir nos enums:
    # InvalidSettingsError / OutputFolderUnavailableError. Só salva depois de validar tudo.

# application_state_service.py
@dataclass(frozen=True)
class StorageState:
    free_space_in_bytes: int
    estimated_pages_remaining: int
    output_folder_available: bool = True      # False (e 0, 0) quando a pasta não existe ou o disco externo saiu
@dataclass(frozen=True)
class ApplicationState:
    snapshot: ScanProgressSnapshot
    settings: ApplicationSettings
    storage: StorageState
class ApplicationStateService:
    def __init__(self, progress_tracker: ScanProgressTracker,
                 settings_repository: ApplicationSettingsRepository,
                 storage_guard_service: StorageGuardService) -> None: ...
    def build_state(self) -> ApplicationState: ...
    # Captura OutputFolderUnavailableError do guarda de espaço e devolve StorageState(0, 0, False).
```

### 6.5 `controllers/` e raiz

```python
# controllers/error_message_catalog.py
class ErrorMessageCatalog:
    def message_for(self, error_code: str) -> str: ...     # textos da seção 4.4; código desconhecido → unexpected_error

# controllers/local_request_guard.py                (middleware ASGI puro)
REQUIRED_HEADER_NAME = "x-requested-with"
REQUIRED_HEADER_VALUE = "digitalizadora"
class LocalRequestGuard:
    def __init__(self, app: ASGIApp, allowed_hosts: frozenset[str]) -> None: ...
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None: ...

# controllers/<nome da classe em snake_case>.py: scan_controller.py, state_controller.py, settings_controller.py,
# printer_controller.py, preview_controller.py (mais error_message_catalog.py e local_request_guard.py acima).
# Cada controller expõe build_router() -> APIRouter
class ScanController:     # POST /api/scans (409 se is_scan_in_progress(); senão agenda a digitalização em segundo plano)
    def __init__(self, scan_service: ScanService, settings_service: ApplicationSettingsService,
                 error_message_catalog: ErrorMessageCatalog) -> None: ...
class StateController:    # GET /api/health, GET /api/state
    def __init__(self, state_service: ApplicationStateService,
                 error_message_catalog: ErrorMessageCatalog) -> None: ...
class SettingsController: # GET /api/settings, PUT /api/settings
    def __init__(self, settings_service: ApplicationSettingsService,
                 error_message_catalog: ErrorMessageCatalog) -> None: ...
class PrinterController:  # GET /api/printer, POST /api/printer/refresh, PUT /api/printer/address
    def __init__(self, printer_connection_service: PrinterConnectionService,
                 error_message_catalog: ErrorMessageCatalog) -> None: ...
class PreviewController:  # GET /api/scans/last/thumbnail
    def __init__(self, progress_tracker: ScanProgressTracker) -> None: ...

# application_factory.py
@dataclass(frozen=True)
class ApplicationControllers:
    scan: ScanController; state: StateController; settings: SettingsController
    printer: PrinterController; preview: PreviewController
@dataclass(frozen=True)
class WebInterfaceConfiguration:
    allowed_hosts: frozenset[str]
    static_directory: Path
    error_message_catalog: ErrorMessageCatalog
    shutdown_callbacks: tuple[Callable[[], Awaitable[None]], ...] = ()
def create_application(controllers: ApplicationControllers,
                       web_configuration: WebInterfaceConfiguration) -> FastAPI: ...
# "/" serve index.html; "/static/*" serve os arquivos; LocalRequestGuard envolve tudo.
# Corpo inválido (RequestValidationError do FastAPI) responde 422 {"code": "invalid_settings", "message": ...}
# usando web_configuration.error_message_catalog, nunca o {"detail": [...]} padrão do FastAPI.

# configuration.py
@dataclass(frozen=True)
class ApplicationConfiguration:
    host: str
    port: int
    data_directory: Path
    log_directory: Path
    default_output_folder: Path
    scanner_address_override: str | None
    @classmethod
    def from_environment(cls, environment: Mapping[str, str], home_directory: Path) -> "ApplicationConfiguration": ...
# Variáveis: DIGITALIZADORA_PORT (8765), DIGITALIZADORA_SCANNER_ADDRESS, DIGITALIZADORA_OUTPUT_FOLDER.

# composition_root.py
@dataclass(frozen=True)
class ApplicationContainer:
    controllers: ApplicationControllers
    web_configuration: WebInterfaceConfiguration
@dataclass(frozen=True)
class ContainerOverrides:                       # pontos de injeção para testes; em produção tudo fica None
    scanner_transport: httpx.AsyncBaseTransport | None = None   # httpx.ASGITransport da impressora falsa
    gateway_timing: EsclGatewayTiming | None = None             # tempos sem espera real
    free_space_reader: Callable[[Path], int] | None = None      # espaço livre fixo
def build_scanner_http_client(scanner_transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient: ...
# Cliente de produção: follow_redirects=False, httpx.Timeout(30.0, connect=5.0, read=180.0), sem conexões
# reaproveitadas. Leitura de 180 s porque o NextDocument desta impressora bloqueia até ~75 s a 600 dpi (Gate 0);
# o scan_timeout_seconds do gateway continua 300 s.
# Público porque o teste de hardware (Tarefa 14) usa o mesmo cliente.
def build_container(configuration: ApplicationConfiguration,
                    overrides: ContainerOverrides | None = None) -> ApplicationContainer: ...
# Se configuration.scanner_address_override existir, chama PrinterConnectionService.use_manual_address
# (na montagem, antes de qualquer acquire_gateway: o endereço fica fixo para o processo, seção 6.4).
# Na partida tenta prepare_output_folder(configuration.default_output_folder) e só registra um aviso se falhar.
# É o ÚNICO lugar que instancia classes concretas (inclusive ErrorMessageCatalog, DnsServiceDiscoveryRecordSource
# e prepare_output_folder injetados).
```

**JSON da API** (todas as respostas de erro: `{"code": "...", "message": "..."}`):

- `GET /api/state` → `{"scan_phase", "scans_completed", "last_result": {"file_name","output_folder","output_format","size_in_bytes","scanned_at"} | null, "last_error": {"code","message"} | null, "settings": {"output_folder","output_format","scan_preset"}, "storage": {"free_space_in_bytes","estimated_pages_remaining","output_folder_available"}}`
- `POST /api/scans` → `202 {"accepted": true}`; `409` se já houver scan; o resultado chega por `/api/state`.
- `GET /api/printer` e `POST /api/printer/refresh` → `{"connected", "display_name", "scanner_state", "route": "usb" | "network" | null, "error": {"code","message"} | null}`, com as chaves nesta ordem.
- `PUT /api/printer/address` com `{"base_address": "http://IP:PORTA/eSCL"}` → mesmo formato.
- `GET/PUT /api/settings` → `{"output_folder","output_format","scan_preset"}`; `422` com `invalid_settings` ou `output_folder_unavailable`.
- `GET /api/scans/last/thumbnail` → `image/jpeg` ou `404`.
- `GET /api/health` → `{"status": "ok"}`.

### 6.6 Impressora falsa e dublês de teste

```python
# simulator/fake_escl_scanner_app.py   (imita o comportamento medido da impressora real no Gate 0)
@dataclass
class FakeScannerBehavior:
    busy_polls_before_document: int = 0       # respostas 503 antes de entregar a imagem (a real nunca deu 503)
    initial_state: str = "Idle"                # nome eSCL do estado
    post_status_code: int = 201
    document_status_code: int = 200
    processing_polls_after_document: int = 0  # leituras de ScannerStatus que respondem "Processing" logo depois
                                              # da entrega (cobre "esperar Idle antes do próximo POST")
def create_fake_escl_scanner_app(behavior: FakeScannerBehavior) -> FastAPI: ...
# O módulo também exporta (usados pelas Tarefas 5 e 14): build_capabilities_document(color_modes: Sequence[str]) -> bytes,
# build_status_document(state_name: str) -> bytes e as constantes PLATEN_MAXIMUM_WIDTH, PLATEN_MAXIMUM_HEIGHT,
# SUPPORTED_COLOR_MODES. O rótulo da página sintética é ASCII ("Pagina <n>"): a fonte embutida do Pillow não tem "á".
# Rotas: /eSCL/ScannerCapabilities, /eSCL/ScannerStatus, POST /eSCL/ScanJobs (201 + Location ABSOLUTO com
# identificador UUID: "http://<host da requisição>/eSCL/ScanJobs/<uuid4>"),
# GET /eSCL/ScanJobs/<uuid>/NextDocument (503 busy_polls_before_document vezes, 200 com JPEG de página A4
# sintética, depois 404), DELETE /eSCL/ScanJobs/<uuid> (404 se a imagem já foi entregue e o NextDocument já
# respondeu 404, como a impressora real; 200 para um trabalho ainda vivo). Depois da entrega, ScannerStatus
# responde "Processing" processing_polls_after_document vezes e então volta ao estado inicial.
# Usada pelos testes (httpx.ASGITransport) e por `make simulator` (uvicorn, porta 8080).

# tests/fakes/ (dublês compartilhados; quem cria cada um está no plano)
class FixedClock:                 # T2
    def __init__(self, moment: datetime) -> None: ...
    def now(self) -> datetime: ...
    def advance(self, seconds: float) -> None: ...
def build_sample_jpeg(width_pixels: int = 64, height_pixels: int = 48,
                      dots_per_inch: int | None = None) -> bytes: ...          # T2 (Pillow)
def read_escl_fixture(file_name: str) -> bytes: ...   # T3 (lê tests/fixtures/escl/<file_name>)
class RecordingFreeSpaceReader:   # T8, em tests/fakes/recording_free_space_reader.py (usado também pela T10)
    def __init__(self, free_space_in_bytes: int) -> None: ...   # substitui read_free_space_in_bytes nos testes
    failure: Exception | None     # se o teste atribuir uma exceção, as chamadas seguintes a levantam
    requested_folders: list[Path] # cada pasta pedida, em ordem
    def __call__(self, folder: Path) -> int: ...
class RecordingSleep:             # T5
    delays: list[float]
    async def __call__(self, seconds: float) -> None: ...
class ScriptedScannerGateway:     # T10 (implementa ScannerGateway)
    def __init__(self, capabilities: ScannerCapabilities,
                 scan_outcomes: Sequence[ScannedImage | Exception]) -> None: ...
    scan_requests: list[ScanSettings]
class FixedGatewayProvider:       # T10 (implementa ScannerGatewayProvider)
    def __init__(self, gateway: ScannerGateway) -> None: ...
class InMemoryApplicationSettingsRepository:   # T7
    def __init__(self, settings: ApplicationSettings) -> None: ...
```

### 6.7 Dependências (`pyproject.toml`)

`requires-python = ">=3.12"`. Execução: `fastapi>=0.115`, `uvicorn>=0.30`, `httpx>=0.27`, `pillow>=12`, `img2pdf>=0.6.3`, `pikepdf>=10.9` (os testes usam `Page.get_images()`). Desenvolvimento, no grupo opcional chamado **`development`** (o nome `dev` é abreviação; instalar com `pip install -e ".[development]"`): `pytest>=8`, `pytest-asyncio>=0.24`, `ruff`. Ruff: `line-length = 120`. (Versões verificadas no PyPI em 2026-10-12: img2pdf 0.6.3, pikepdf 10.17.0; `pip` resolve as mais novas.) **Sem `zeroconf`:** a descoberta usa só a biblioteca padrão (`ctypes`, `select`, `asyncio`) e a libSystem do macOS (G0C-1). `pytest`: `asyncio_mode = "auto"`, `pythonpath = ["."]`, marcador `hardware` excluído por padrão.

---

## 7. Interface (UX)

Uma tela só, em português, teclado primeiro:

- **Cabeçalho:** "Digitalizadora" + indicador da impressora ("Procurando…", "Impressora pronta (USB)" ou "Impressora pronta (Wi-Fi)" conforme o campo `route` de `GET /api/printer`, "Impressora ocupada", "Impressora não encontrada").
- **Botão grande "Digitalizar"** (dica "Espaço"). Foco automático; a tecla Espaço dispara; `event.repeat` é ignorado; durante um scan o botão fica desabilitado.
- **Seletor `PDF | JPG`** e **seletor de qualidade** `Texto (300 dpi, cor)`, `Texto econômico (200 dpi, cinza)`, `Foto (600 dpi, cor)` (rótulos renomeados em 2026-10-17 para não confundir com o modo Documento; os valores da API não mudam). As mudanças são salvas na hora. O seletor **Rápido | Documento** e a interface do modo Documento estão na seção 3 e em 6.7 do [design do documento de várias páginas](2026-10-17-documento-de-varias-paginas.md).
- **Pasta de saída** (campo de texto + Salvar) com o **espaço livre** e "cabem ~N páginas"; aviso se houver menos de 5 GB: "Recomendado: use um disco externo" (com 12 GB livres hoje, o aviso não aparece na pasta padrão). Se `storage.output_folder_available` for falso (por exemplo o disco externo foi desconectado), mostra "Pasta de saída indisponível. Se for um disco externo, confira se está conectado." no lugar do espaço livre.
- **Estado:** "Preparando…", "Digitalizando… (cerca de 15 s)", ou "(cerca de 75 s)" na qualidade Foto (tempos medidos no Gate 0; o texto mostra só o tempo da qualidade escolhida desde a Tarefa 21), "Salvando…", "Pronto! Salvo como AAAA-MM-DD_NNNNN.pdf".
- **Último arquivo:** miniatura, nome, tamanho e hora; **contador** "Digitalizações nesta sessão: N".
- **Erros:** faixa vermelha com a mensagem em português da seção 4.4, mais ícone e texto (nunca só cor).
- **Acessibilidade:** alvos de toque grandes, `role="status"` na área de estado, contraste suficiente.
- **Consultas:** `GET /api/state` a cada 0,5 s durante o scan e a cada 2 s parado; `GET /api/printer` a cada 15 s parado e nunca durante um scan.

---

## 8. Estratégia de testes

| Camada | Como | Exemplos de casos de fronteira |
|---|---|---|
| Domínio | testes unitários puros | resolução pedida entre dois valores suportados, acima do máximo, lista vazia; `route_for_host_name` com `localhost`, `LOCALHOST`, `127.0.0.1`, `::1` (USB) e `HP000000000001.local`, `localhost.example` (rede) |
| Protocolo eSCL | XML **real** da impressora, capturado no Gate 0 e copiado sem mudanças de `docs/gate-0-capturas/` para `tests/fixtures/escl/hp-deskjet-2800-scanner-capabilities.xml` e `tests/fixtures/escl/hp-deskjet-2800-scanner-status-idle.xml`; as fixtures sintéticas ficam para os casos de fronteira | XML real: modelo "DeskJet Ink Advantage 2800 All-in-One Printer series", vidro 2550 × 3508, resoluções (75, 100, 150, 200, 300, 400, 600, 1200), cores com `RGB24`/`Grayscale8`/`BlackAndWhite1`, formatos com `image/jpeg` e `application/pdf`, estado `Idle`; sintéticas: `<!doctype` em minúsculas, `rs` com ou sem barra, `Location` com host estranho ou absoluto (`http://localhost:57805/...`) |
| Gateway | impressora falsa via `httpx.ASGITransport` + `httpx.MockTransport` para erros de rede | `NextDocument` 200 na primeira requisição sem `sleep` (o caso real), 503 repetido, 404 antes da página, 409, `errno 65`, estouro do tempo máximo, `DELETE` sempre enviado e 404 no `DELETE` aceito no caminho de sucesso, `Processing` depois da entrega |
| Descoberta | `ServiceRecordSource` falso; funções puras `parse_text_record`, `normalize_host_name` e `classify_route` | USB antes da rede; o mesmo `base_address` duas vezes (USB em `0xFFFFFFFF` e `localhost` na interface 11) vira um endpoint só, o primeiro; as duas rotas com o mesmo UUID continuam; `classify_route` com `0xFFFFFFFF`, com `localhost` na interface 11 e com host `.local` na interface 11; entrada TXT sem "=", chave em maiúsculas (`UUID`), host com ponto final, `rs` ausente |
| Serviços | dublês (`FixedClock`, `ScriptedScannerGateway`, `RecordingFreeSpaceReader`, descoberta e repositório falsos) | espaço livre exatamente no limite e 1 byte abaixo; segundo `begin_scan`; JPEG sem JFIF; conexão: a primeira conexão do processo descobre mesmo com um endpoint Wi-Fi salvo que responde e escolhe o USB do mesmo UUID; endpoint salvo usado só com descoberta vazia (ou nenhum achado respondendo); gateway em memória reaproveitado sem nova descoberta; status do gateway em memória falhando → nova descoberta; endpoint escolhido gravado a cada escolha; endereço manual em `localhost`/`127.0.0.1`/`[::1]` gravado como USB e usado sem descoberta |
| Repositórios | pasta temporária (`tmp_path`) | nome já existente, buracos na sequência, pasta inexistente |
| Controllers | `TestClient` (Starlette) com `base_url="http://127.0.0.1:8765"` | `Host` inválido, falta do cabeçalho, 409 com scan em andamento |
| Integração | aplicação completa + impressora falsa | clique → arquivo PDF e JPG válidos na pasta |
| Hardware (opcional) | `DIGITALIZADORA_HARDWARE_TESTS=1 .venv/bin/pytest -m hardware` | descoberta real pela API nativa de DNS-SD e uma digitalização real a 300 dpi |

Metas: cada teste abaixo de 100 ms (sem rede real, `sleep` falso); um conceito por teste.

**Os cinco modos de falha com mais chance de acontecer** (viram a seção "Review Focus" do plano, cada um com teste): (1) impressora dormindo, desligada, com IP novo ou com porta USB nova ao apertar Digitalizar; (2) Espaço repetido ou clique duplo durante um scan; (3) pasta de saída ausente (disco externo desconectado) ou cheia; (4) imagem inesperada do scanner (não-JPEG, corrompida, sem densidade JFIF); (5) processo interrompido no meio da gravação e colisão de nomes. Além deles: Rede Local bloqueada, só na rota Wi-Fi (mensagem própria, que sugere o cabo USB).

---

## 9. Gate 0 — resultado (concluído em 2026-10-17)

**Veredito: aprovado.** A impressora digitaliza por eSCL pelo cabo USB e pelo Wi-Fi, com o mesmo UUID. Registro completo em [docs/gate-0-resultado-2026-10-17.md](../../gate-0-resultado-2026-10-17.md); capturas reais (com número de série, UUID e host trocados por marcadores) em [docs/gate-0-capturas/](../../gate-0-capturas/). O Gate 0 não tem mais passos a executar e não existe script de sondagem para criar.

### 9.1 Como foi feito

Pelo shell do Claude Code dentro do VS Code (não pelo Terminal.app), com a impressora ligada e conectada ao Mac pelo cabo USB e pelo Wi-Fi. O app HP não foi necessário.

### 9.2 Passos e resultado

| Passo | O que estava previsto | Resultado |
|---|---|---|
| 0.1 | Apertar o botão **Informação** da impressora (IP, nome e firmware) | Não foi preciso: o nome do host (`HP….local`) veio do Bonjour e o firmware (TIP1CN2446AR, de 13/11/2024) veio das capacidades e do cabeçalho `Server` |
| 0.2 | `dns-sd -B` / `dns-sd -L` de `_uscan._tcp`, `_uscans._tcp`, `_ipp._tcp` | `_uscan._tcp` aparece **duas vezes, com o mesmo UUID**: USB em `localhost.:57805` (interface -1, a ponte IPP-over-USB do macOS; TXT com `usb_SN`, `usb_VID=1008`, `usb_PID=795`) e Wi-Fi em `<host-da-impressora>.local.:8080`. `_uscans._tcp` na porta 443 (não testado). `_ipp._tcp` e `_http._tcp` presentes. TXT comum: `rs=eSCL`, `vers=2.63`, `is=platen`, `duplex=F`, `cs=binary,color,grayscale`, `pdl=application/octet-stream,application/pdf,image/jpeg`, `mopria-certified-scan=1.3`. O `python-zeroconf` 0.151.5 só viu o Wi-Fi; a API nativa `dns_sd` via `ctypes` viu as duas rotas (`dns-service-discovery-probe.py`) |
| 0.3 | `GET /eSCL/ScannerCapabilities` e `/eSCL/ScannerStatus` | XML idêntico byte a byte nas duas rotas (5.439 bytes); cópias em `docs/gate-0-capturas/`. Só `Platen`, área 2550 × 3508 (1/300 pol.), resoluções 75 a 1200 (discretas, inclusive 600 e 1200), cores `BlackAndWhite1`/`Grayscale8`/`RGB24`, formatos `image/jpeg`/`application/pdf`/`application/octet-stream` |
| 0.4 | `POST ScanJobs` a 300 dpi JPEG, `NextDocument`, `DELETE` | `201 Created` com `Location` absoluto (`http://localhost:57805/eSCL/ScanJobs/<uuid>`); `NextDocument` bloqueou e respondeu 200 na primeira tentativa, depois 404; `DELETE` → 404; 14,4 s até a imagem; 154 KB (página em branco); 2550 × 3508 pixels; JFIF 300 dpi |
| 0.5 | Captura de Imagem: a impressora aparece e digitaliza? | **Não testado** |
| 0.6 | Matriz de tempo e tamanho | Parcial: cor 300 dpi (USB 14,4 s até a imagem e ~19 s até `Idle`; Wi-Fi 14,3 s e 18,8 s; 154 KB), cinza 300 dpi (6,7 s e 10,4 s; 119 KB), cor 600 dpi (71,9 s e 76,9 s; 663 KB; 5100 × 7016). 150 e 200 dpi não foram medidos; todos os tamanhos são de página em branco |
| 0.7 | Sono: 10 minutos parada, depois descoberta, capacidades e um scan | **Não testado** |
| 0.8 | Rede Local: repetir 0.3 fora do Terminal.app | A rota Wi-Fi respondeu também a partir do shell do VS Code (sem `No route to host`); a rota USB é `localhost` e não depende da permissão de Rede Local |

### 9.3 Ainda não testado

- Uma página com conteúdo de verdade (tamanho real do arquivo).
- `application/pdf` gerado pela própria impressora.
- Impressora dormindo (o modo de espera começa depois de ~5 min) e quanto tempo ela leva para acordar (passo 0.7).
- HTTPS (`_uscans`, porta 443) com o OpenSSL do Python.
- Se o Captura de Imagem lista a impressora (passo 0.5).
- Intent `Photo` contra `Document` na qualidade da imagem.

### 9.4 Decisão (registro histórico)

| Resultado | O que fazer | Situação |
|---|---|---|
| `_uscan._tcp` aparece, capacidades e scan funcionam | Seguir com o MVP; adicionar o XML real como fixture (as sintéticas ficam para casos de fronteira) | **Tomada em 2026-10-17** |
| Não aparece, mas a página da impressora (EWS) tem opção de eSCL/AirPrint/Webscan | Ativar, repetir 0.2 | Não se aplica |
| Não há eSCL | O app HP e o VueScan falam outros protocolos (LEDM/REST). Reavaliar: (a) um adaptador HP LEDM atrás de `ScannerGateway` (o resto do projeto não muda), ou (b) desistir de software próprio e usar app HP/NAPS2/VueScan | Não se aplica |
| eSCL funciona, mas 600 dpi em cor falha ou fica lento | Limitar o preset `PHOTO` a 400 dpi | Não se aplica: 600 dpi em cor funcionou (71,9 s até a imagem); o preset `PHOTO` fica em 600 dpi |

---

## 10. Roadmap depois do MVP

Cada fase vira um plano próprio, escrito depois de validar a anterior com a impressora real.

| Fase | Conteúdo | Condição para começar |
|---|---|---|
| **2 — Lote e conforto** (prioridade) | O PDF de várias páginas (Finalizar com Enter, Descartar última com Backspace, retomada depois de queda, nome do documento) saiu daqui e entrou no MVP como modo Documento ([design](2026-10-17-documento-de-varias-paginas.md)), com rascunho em pasta + `manifest.json` em vez de SQLite. Fica para esta fase: lote (`Sessão > Documento > Página`, nome do lote, vários documentos em andamento); "Redigitalizar" (R) uma página; `caffeinate` durante a sessão; sons; normalização de EXIF (resolução e data) e data de criação do arquivo; PDF dividido a cada ~500 páginas | MVP rodando com a impressora |
| **3 — Qualidade de imagem** | Aviso de página em branco; orientação (Tesseract OSD ou Vision); recorte de folha única (Vision); divisão de várias fotos **só se** o Captura de Imagem ("Detectar imagens separadas"), o preset "Vários itens" do app HP e o Auto-Crop do NAPS2 não bastarem | Comparação com fotos reais (S0-13 do digest) |
| **4 — OCR em segundo plano** | Tesseract com dados `por` (precisa baixar) ou Vision; camada de texto por renderizador testado (Tesseract ou `ocrmypdf`), nunca escrita à mão; fila `ocr_jobs` idempotente | Fase 2 pronta |
| **5 — App empacotado** | PyInstaller/py2app + `pywebview`, `NSLocalNetworkUsageDescription`, `NSBonjourServices`, identidade de assinatura estável; ou o ajuste do sistema `AllowedWiFiLocalNetworkAddresses` | Teste de permissão de Rede Local persistindo entre reconstruções (só a rota Wi-Fi precisa dela; a rota USB é `localhost`) |
| **6 — Outros scanners** | A mesma porta `ScannerGateway` aceita um scanner eSCL com alimentador (`InputSource=Feeder`) | Se você comprar um scanner com alimentador |

---

## 11. Riscos

| Risco | Prob./impacto | Mitigação |
|---|---|---|
| eSCL ausente nesta unidade | **resolvido** | Gate 0 de 2026-10-17: eSCL confirmado pelo USB e pelo Wi-Fi (seção 9); o plano B ficou só como registro |
| Mesa de vidro versus volume (ciclo medido de ~10 s em cinza e ~19 s em cor a 300 dpi, ~77 s a 600 dpi, mais a troca da folha) | alta / alto | Expectativa clara; Fase 2 para reduzir o esforço por página; considerar um scanner com alimentador para documentos |
| Disco cheio (12 GB livres no disco interno em 2026-10-17) | média / alto | Guarda de espaço obrigatória, aviso na interface; disco externo recomendado para volumes muito grandes |
| Rede Local bloqueada (`No route to host`) | baixa / médio | Preferir a rota USB (`localhost`, que não depende da permissão); para o Wi-Fi, iniciar pelo launcher (Terminal.app); mensagem própria que sugere o cabo USB |
| Impressora dorme, muda de IP ou muda de porta USB | alta / médio | Busca nova a cada abertura do app e a cada "Procurar de novo" (USB preferido, UUID salvo como referência, endereço salvo só como alternativa final); checagem de status do gateway em memória + nova busca se falhar; espera e nova tentativa; o comportamento dormindo ainda não foi testado (seção 9.3) |
| Peculiaridades do firmware HP (XML, 409 versus 503, doctype, `Location` absoluto, `NextDocument` bloqueante, `DELETE` → 404) | média / médio | XML numa linha, parser tolerante, `DELETE` sempre com 404 aceito, tempo de leitura de 180 s, fixtures reais e impressora falsa que imita o que foi medido |
| Descoberta nativa por `ctypes` (assinaturas C, callbacks, desalocação) | baixa / médio | Sonda de referência que funcionou no Gate 0 (`docs/gate-0-capturas/dns-service-discovery-probe.py`); funções puras testadas sem rede; callbacks referenciados e `DNSServiceRefDeallocate` em `finally`; teste de hardware |
| 600 dpi em cor contra 64 MB de RAM da impressora | baixa / médio | Medido no Gate 0: funcionou (71,9 s, 663 KB numa página em branco); página com conteúdo ainda não medida |
| Exposição da interface local (CSRF, DNS rebinding) | baixa / médio | `127.0.0.1`, checagem de `Host`, cabeçalho obrigatório |
| Atualização do macOS (27) | baixa / alto | Não atualizar antes de validar; registrar a build; repetir a descoberta e uma digitalização real (D10) |
| Dependência LGPL (`img2pdf`) | baixa / baixo | Uso pessoal; sem redistribuição |

---

## 12. Escanear hoje, enquanto isso

*A impressora está ligada e respondendo em eSCL desde 2026-10-17, mas estas receitas ainda não foram testadas com ela. Nomes de menus em português podem variar um pouco.*

**A. Captura de Imagem (já está no Mac).** Com a impressora ligada (pelo cabo USB ou pelo Wi-Fi, com a luz do Wi-Fi fixa), abra o **Captura de Imagem**; se a impressora não aparecer em "Dispositivos" ou "Compartilhados", remova e adicione a impressora em Ajustes do Sistema > Impressoras e Scanners e reinicie a impressora. Clique em **Mostrar Detalhes**. *Documentos:* modo **Mesa** (Flatbed), tipo Preto e Branco (ou Texto), 300 dpi, tamanho A4, formato PDF, "Combinar em um único documento" (não confirmado para scanner de mesa), pasta de destino à sua escolha. *Fotos:* tipo Cor, 600 dpi, tamanho "Detectar imagens separadas" (deixe cerca de 1 cm entre as fotos), formato JPEG.

**B. App HP (já instalado; o Digitalizadora não precisa dele).** Tem presets Foto, Documento, Vários itens, Livro e Lote, "Adicionar digitalização" para várias páginas e PDF pesquisável. Pede conta HP e internet.

**C. NAPS2 8.x (grátis; `brew install --cask naps2`).** No Mac não existe a barra de perfis; use os atalhos F2–F12 por perfil. Crie os perfis "Documento PDF" (Vidro, A4, 300 dpi, cinza) e "Foto JPG" (Vidro, 600 dpi, cor, qualidade JPEG 90, Auto-Crop). Em "Salvar automaticamente", use **caminho absoluto** (`/Users/usuario/Scans/doc-$(nnn).pdf`; o `~` não funciona). Para várias páginas num PDF: Digitalizar > Lote > "Várias digitalizações, perguntar entre elas" e "Salvar num único arquivo".

Até o modo Documento estar implementado, para juntar PDFs de uma página, abra-os no Preview e arraste as miniaturas.

---

## 13. Perguntas para você

1. **Nomes:** aceita a exceção da D6 (módulos Python em `snake_case`, o resto em kebab-case)? **Resposta (2026-10-17): sim.** D6 aprovada.
2. **Onde guardar:** **Resposta (2026-10-17):** em `~/Pictures/Digitalizadora`, no disco interno, que agora tem 12 GB livres. Disco externo é opcional, recomendado só para volumes muito grandes; a guarda de espaço continua obrigatória.
3. **Interface:** uma página local aberta no navegador, iniciada por duplo clique, serve para a v1? **Resposta (2026-10-17): sim, como recomendado;** app empacotado só na Fase 5.
4. **Volume:** **Resposta (Gate 0, 2026-10-17):** os tempos medidos substituem a estimativa antiga: ciclo de ~10 s (cinza, 300 dpi), ~19 s (cor, 300 dpi) e ~77 s (cor, 600 dpi) por página, mais o tempo de trocar a folha. Para milhares de folhas de documentos, um scanner com alimentador continua sendo uma opção (o app já nasce preparado para ele).
5. **Próxima fase:** PDF de várias páginas primeiro (recomendo) ou fotos primeiro? **Resposta (2026-10-17): PDF de várias páginas, e já nesta versão, junto com o modo rápido** (pedido acrescentado ao md.md). Nas suas respostas: os controles são adicionar página, finalizar, descartar a última página, cancelar o documento, miniaturas das páginas, nome do documento, visão geral de cima (grade com todas as páginas), reordenar as páginas arrastando e soltando e excluir qualquer página; se o app ou o Mac cair, o documento deve **retomar de onde parou**. As decisões tomadas a partir disso (M1 a M11) e os refinamentos (R1 a R20) estão no [design do documento de várias páginas](2026-10-17-documento-de-varias-paginas.md); o plano ganhou as Tarefas 15 a 22.
6. **Gate 0:** **Resposta: concluído em 2026-10-17** (seção 9); o app HP não foi necessário.

---

## 14. Transparência da pesquisa

- 14 agentes (7 pesquisadores e 7 céticos independentes) trabalharam em paralelo; a primeira execução parou no limite de uso da sessão e foi retomada, aproveitando o que já estava pronto.
- **Limites:** a cota de buscas na web acabou nas sete frentes, então parte da checagem foi por leitura direta de fontes; `support.hp.com` e a Comunidade HP ficaram inacessíveis; as especificações da Mopria (eSCL) e da Apple (AirPrint) não foram lidas; durante a pesquisa (13/10) **nada foi medido na impressora**, que estava desligada. As medições vieram depois, no Gate 0 de 2026-10-17 (seção 9).
- **O que os agentes fizeram no seu Mac:** leitura de arquivos (cache do app HP, que revelou o modelo 6W7G2A e o MAC da impressora; PPD; Captura de Imagem; cabeçalhos do SDK; uso de disco) e download de fontes de referência para uma pasta temporária (cerca de 1,1 GB). Um agente executou por engano `HP.app --version` e abriu brevemente um app SwiftUI de teste invisível (removido). Durante a pesquisa, nenhum agente falou com a impressora nem sondou a rede local; eu fiz apenas a busca Bonjour passiva. A primeira conversa com a impressora foi o Gate 0 (seção 9).
- O MAC e o nome de host da impressora foram trocados por marcadores na cópia do digest guardada no projeto.

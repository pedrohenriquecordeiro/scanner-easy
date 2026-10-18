# Gate 0: resultado

**Data:** 2026-10-17 · **Veredito:** **aprovado**: a impressora digitaliza por eSCL, pelo USB e pelo Wi-Fi.

Relacionados: [relatório do levantamento](relatorio-do-levantamento-2026-10-13.md) · [spec](superpowers/specs/2026-10-13-digitalizadora-design.md) · [plano (rascunho)](superpowers/plans/2026-10-17-digitalizadora-plano-final.md)

Executado pelo shell do Claude Code dentro do VS Code (não pelo Terminal.app), com a impressora ligada e conectada por USB e Wi-Fi.

## 1. Descoberta (Bonjour)

| Serviço | Endereço | Observação |
|---|---|---|
| `_uscan._tcp` (eSCL, USB) | `localhost:57805`, interface -1 | Ponte IPP-over-USB do macOS. TXT traz `usb_SN`, `usb_VID=1008`, `usb_PID=795`. Por ser `localhost`, **não depende da permissão de Rede Local**. A porta deve ser tratada como dinâmica. |
| `_uscan._tcp` (eSCL, Wi-Fi) | `<host-da-impressora>.local:8080` | Funcionou também a partir do shell do VS Code. |
| `_uscans._tcp` (eSCL HTTPS) | `<host-da-impressora>.local:443` | Não testado. |
| `_ipp._tcp`, `_http._tcp` | — | Presentes. |

TXT comum: `rs=eSCL`, `vers=2.63`, `is=platen`, `duplex=F`, `cs=binary,color,grayscale`, `pdl=application/octet-stream,application/pdf,image/jpeg`, `mopria-certified-scan=1.3`, `UUID=00000000-0000-4000-8000-000000000001` (o mesmo nas duas rotas).

## 2. Capacidades (`GET /eSCL/ScannerCapabilities`)

O XML é idêntico, byte a byte, nas duas rotas (5.439 bytes; cópia na pasta temporária da sessão).

- Modelo: "DeskJet Ink Advantage 2800 All-in-One Printer series"; firmware TIP1CN2446AR (13/11/2024).
- Só **Platen** (vidro). Área de 8 a 2550 × 8 a 3508 (em 1/300 pol., ou seja A4: 216 × 297 mm). `MaxScanRegions=1`.
- Cores: `BlackAndWhite1`, `Grayscale8`, `RGB24`.
- Formatos: `image/jpeg`, `application/pdf`, `application/octet-stream`.
- Resoluções discretas: 75, 100, 150, 200, 300, 400, 600, 1200.
- Intents: `Document`, `Photo`, `Preview`, `TextAndGraphic`. ContentTypes: `Photo`, `Text`, `TextAndPhoto`.
- Brilho e contraste de 0 a 2000 (normal 1000); limiar de 0 a 255 (normal 128).
- Margens "arriscadas": esquerda e direita 34, topo 42, base 45 (1/300 pol.).

## 3. Digitalizações de teste (vidro vazio, A4 inteiro, JPEG)

| Rota | Modo | dpi | Até a imagem chegar | Até voltar a `Idle` | Tamanho | Imagem |
|---|---|---|---|---|---|---|
| USB | RGB24 | 300 | 14,4 s | ~19 s | 154 KB | 2550 × 3508, JFIF 300 dpi |
| Wi-Fi | RGB24 | 300 | 14,3 s | 18,8 s | 154 KB | igual |
| USB | Grayscale8 | 300 | 6,7 s | 10,4 s | 119 KB | 1 componente, JFIF 300 dpi |
| USB | RGB24 | 600 | 71,9 s | 76,9 s | 663 KB | 5100 × 7016, JFIF 600 dpi |

Os tamanhos são de uma página **em branco**; uma página com conteúdo será maior (o spec estima 0,65 a 1,4 MB para A4 colorido a 300 dpi).

## 4. Comportamentos do protocolo que o código precisa respeitar

1. `POST /eSCL/ScanJobs` → `201 Created`, e o `Location` vem com URL **absoluta** (`http://localhost:57805/eSCL/ScanJobs/<uuid>`): usar só o caminho.
2. `GET <job>/NextDocument` **bloqueia até a imagem ficar pronta** e responde 200 na primeira tentativa (não houve 503). O tempo limite de leitura precisa passar de **90 s** (600 dpi em cor levou 72 s).
3. Depois da última página, `NextDocument` → **404** (fim).
4. `DELETE <job>` depois do fim → **404**: o trabalho já some sozinho. **404 no DELETE é sucesso**, não erro.
5. Depois de entregar a imagem, o estado fica `Processing` por 4 a 5 s (o cabeçote voltando). A próxima digitalização deve esperar `Idle`, ou tratar 503/409 com nova tentativa.
6. O JPEG já vem com a densidade JFIF certa (300 ou 600). A normalização prevista continua inofensiva, mas não é obrigatória para este modelo.
7. O cabeçalho `Server` identifica o modelo, o número de série e o firmware.

## 5. O que muda no plano

| Tema | Antes (spec de 13/10) | Agora |
|---|---|---|
| eSCL nesta unidade | Não verificado; plano B (HP LEDM) | **Confirmado**; o plano B sai do caminho crítico |
| Rede Local do macOS | Iniciar obrigatoriamente pelo Terminal.app | Pela rota **USB (`localhost`)** a permissão não se aplica; o Wi-Fi também respondeu a partir do VS Code. Preferir USB quando o anúncio local existir; manter a dica do Terminal.app só para o Wi-Fi. |
| Descoberta | Endereço de rede + UUID | Duas rotas com o **mesmo UUID**: preferir a de interface local (`localhost`), cair para a de rede. A porta USB é dinâmica: sempre redescobrir. |
| Espera da imagem | Laço de 503 | `NextDocument` bloqueia; tempo limite de leitura ≥ 120 s. Manter o laço de 503 por robustez. |
| `DELETE` | Sempre, para liberar | Sempre, **aceitando 404** |
| Entre digitalizações | — | Esperar `Idle` (~5 s) antes do próximo `POST` |
| Velocidade | Estimativa de 20 a 50 s por página | **Medido:** ~10 s (cinza 300), ~19 s (cor 300), ~77 s (cor 600) por ciclo |
| Disco | 2 a 3 GB livres | **12 GB livres** em 17/10; a guarda de espaço continua necessária |

## 6. Não testado ainda

- Uma página com conteúdo de verdade (tamanho real do arquivo).
- `application/pdf` gerado pela própria impressora.
- Comportamento com a impressora dormindo (Sleep após ~5 min) e quanto tempo leva para acordar.
- HTTPS (`_uscans`, porta 443) com o OpenSSL do Python.
- Se o Captura de Imagem lista a impressora.
- Escolha do Intent `Photo` contra `Document` na qualidade da imagem.

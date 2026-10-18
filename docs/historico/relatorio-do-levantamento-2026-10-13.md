# Digitalizadora: relatório do levantamento

**Data:** 2026-10-13 · **Pedido:** [md.md](../../md.md) · **Situação:** levantamento e design concluídos, plano em rascunho, **nada implementado**

Documentos relacionados: [spec (design)](superpowers/specs/2026-10-13-digitalizadora-design.md) · [plano Gate 0 + MVP (rascunho)](superpowers/plans/2026-10-17-digitalizadora-plano-final.md) · [achados da revisão](superpowers/plans/2026-10-13-achados-da-revisao.md) · [mudanças de contrato pendentes](superpowers/plans/2026-10-13-mudancas-de-contrato-pendentes.md) · [digest da pesquisa, em inglês](pesquisa/digest-da-pesquisa-2026-10-13.md)

---

## 1. Resumo

O levantamento terminou e **nenhum código do software foi escrito**. O resultado é um design (spec), um rascunho de plano com 15 tarefas e a lista do que ainda precisa ser corrigido nele. Tudo o que eu tinha rodando já havia terminado; nada segue em execução.

- **O que você pediu:** um software local para o MacBook que digitaliza documentos e fotos com a HP DeskJet Ink Advantage 2874 num clique, em PDF ou JPG.
- **O que recomendo construir:** uma página web local (servidor FastAPI em `127.0.0.1`, aberto pelo Terminal.app) que fala direto com a impressora pelo protocolo **eSCL** e grava um arquivo por clique ou por tecla Espaço.
- **O que ainda não se sabe:** se a **sua unidade** responde em eSCL. Ela esteve offline durante todo o trabalho, então o primeiro passo é o **Gate 0**, com a impressora ligada.
- **O que limita o projeto:** a impressora só tem vidro (sem alimentador), cada página leva de 20 a 50 s, e o Mac tem apenas 2–3 GB livres.
- **Onde parou:** a revisão adversarial do plano achou **2 defeitos bloqueantes e 13 graves distintos**. Eles, junto com 13 mudanças de contrato já aceitas, **ainda não foram aplicados** ao plano.

---

## 2. O que foi levantado sobre a impressora e o seu Mac

Status: **medido** (feito neste Mac), **confirmado** (fonte primária), **inferência** (raciocínio), **não verificado** (sem evidência direta).

| # | Fato | Status | Consequência |
|---|---|---|---|
| 1 | HP DeskJet Ink Advantage 2874 (SKU 6W7G2A, HP Brasil), da família "DeskJet Ink Advantage 2800". O macOS a mostra como "HP DeskJet 2800 series [000001]" (os últimos 3 bytes do MAC). | confirmado | Identificação da unidade. |
| 2 | Scanner de **mesa** (CIS): vidro de 216 × 297 mm, 1200 dpi ópticos, sem alimentador e sem duplex, 64 MB de RAM. | confirmado (HP) | Cada página é levantar a tampa. |
| 3 | **Sem botão de digitalizar** (7 botões: Power, Cancel, Resume, Wi-Fi, Information e cópia colorida e preta). | confirmado (HP) | A digitalização só começa por software. |
| 4 | Wi-Fi **só 2,4 GHz**; USB 2.0 (cabo não incluso). | confirmado (HP) | A rede precisa ter 2,4 GHz, na mesma sub-rede, sem isolamento de clientes. |
| 5 | Velocidade não publicada. Modelos irmãos levam cerca de 20 s por página A4 a 300 dpi em preto e branco; em cor pode dobrar. | inferência | Planejar **20–50 s por página**: de 7 a 17 horas por 1.000 páginas. |
| 6 | eSCL é provável na família: Mopria certificou "Scan" em 2023-05-15; o banco do HPLIP lista "Ink Advantage 2800" como eSCL; um dump Linux de 2024 de uma "2800 series" anuncia `_uscan._tcp` na porta 8080. | confirmado para a família | Boa chance, mas não prova nada sobre a sua unidade. |
| 7 | **Nada foi observado na sua unidade** (firmware TIP1CN2446AR, sem XML de capacidades). O PPD da sua fila não tem as chaves `APScanner*`, que o macOS só grava quando lê as capacidades eSCL ao criar a fila (2025-11-15). | não verificado / inferência | Sinal fraco contra eSCL, ou uma corrida na instalação. "Scanning support: No" não é teste de saúde. |
| 8 | A impressora esteve **offline** em todo o trabalho: o macOS diz "Offline" e a busca Bonjour por `_uscan._tcp` e `_ipp._tcp` não achou nada, com o mDNS funcionando no Mac (teste de controle positivo). | medido | Ligue-a para o Gate 0. A causa é desconhecida (desligada, Wi-Fi, isolamento de rede). |
| 9 | Folhas da HP de outros modelos dizem: Sleep após 5 min, e Auto-Off de 2 h desligado enquanto o Wi-Fi está ativo. Se uma impressora dormindo responde a mDNS, e quanto demora para acordar, é desconhecido. | não verificado | O cliente precisa repetir tentativas e reencontrar a impressora pelo UUID. |
| 10 | O app HP ("HP: Print and Support" 26.3.1) já está instalado: presets Foto, Documento, Vários itens, Livro e Lote, e PDF pesquisável; exige conta HP. O cache dele indica o modelo 6W7G2A e sugere que você já digitalizou com ele. | medido / inferência | Alternativa imediata para digitalizar. Pergunta aberta para você (seção 9). |
| 11 | macOS 15.7.3 em Apple Silicon. O **único driver de scanner é o AirScan da Apple** (eSCL); não há driver HP. A HP só suporta até macOS 13/14. | medido | Captura de Imagem, Preview e NAPS2 só enxergam a impressora se ela anunciar eSCL. |
| 12 | Privacidade de **Rede Local** (macOS 15): só o que é iniciado pelo **Terminal.app** é isento. Terminal do VS Code, shell do Claude Code, apps empacotados e LaunchAgents não são. | confirmado (Apple TN3179) | O app deve ser iniciado pelo Terminal.app. Um app empacotado precisa de permissão. |
| 13 | Disco interno de 245 GB com **só 2–3 GB livres**; nenhum disco externo conectado. | medido | Pasta de saída em disco externo e guarda de espaço livre. |
| 14 | Sem Xcode.app (só Command Line Tools). Python 3.12.3 já tem FastAPI, uvicorn, httpx e Pillow 10.4. Tesseract instalado, sem o idioma `por`. | medido | Caminho nativo em Swift descartado; ambiente virtual próprio do projeto. |
| 15 | Uma VPN e um software de contêineres instalados. | medido | Uma VPN pode bloquear a rede local à parte da permissão de Rede Local. Testar com a VPN desligada. |
| 16 | O macOS 27 saiu em 2026-09-14; seu Mac está no 15.7.3 (o 15.8.1 existe). | confirmado | Não atualizar o macOS antes de validar; registrar a build em cada teste. |

---

## 3. Como o software fala com a impressora: protocolo e ferramentas que já existem

### 3.1 O protocolo eSCL (AirScan)

O mesmo fluxo aparece em três clientes de referência (`sane-airscan`, NAPS2 e `escl-scanner-cli`):

1. Descobrir `_uscan._tcp` por Bonjour; o endereço-base é `http://HOST:PORTA/<valor de rs>` (nunca fixar porta nem caminho).
2. `GET ScannerCapabilities` e `GET ScannerStatus` (precisa estar `Idle`).
3. `POST ScanJobs` (XML numa linha só, região em 1/300 de polegada, `Platen`, JPEG) → 201 com `Location` (usar só o caminho).
4. `GET <Location>/NextDocument`: 503 = ainda não está pronto, 200 = imagem, 404 = fim.
5. `DELETE` do trabalho, sempre, para liberar a impressora.

Cuidados que o código precisa ter, vindos de relatos em outros modelos HP: XML numa linha só; `rs` pode vir como `eSCL` ou `/eSCL`; `<!doctype` em minúsculas; digitalizar o vidro inteiro e recortar depois; HTTP por padrão (o HTTPS usa certificado autoassinado). Cada trabalho no vidro devolve **uma única imagem**, então PDFs de várias páginas precisam ser montados no Mac.

### 3.2 O que já existe, e por que ainda vale construir

| Ferramenta | O que faz | Limites para o seu caso |
|---|---|---|
| **Captura de Imagem** (macOS) | Mesa, PDF ou JPEG, "Detectar imagens separadas" (grátis; separa e endireita fotos) | Sem atalho nem linha de comando; juntar páginas de mesa num PDF não está confirmado |
| **App HP** (já instalado) | Presets Foto, Documento, Vários itens, Livro e Lote; PDF pesquisável | Exige conta HP e internet |
| **NAPS2 8.x** (grátis) | Perfis, salvamento automático, lote, console com `--waitscan` | No Mac não há barra de perfis (use os atalhos F2–F12); o caminho do salvamento automático precisa ser absoluto; o console não recorta sozinho; o lote não salva aos poucos |
| **VueScan** (pago) | Recorte múltiplo, lote | Suporte a macOS 15/26/27 não declarado |
| **scanline** (linha de comando, MIT) | Usa o mesmo AirScan | Dormente desde 2025-11 |
| **SANE** | Padrão no Linux | O Homebrew não tem o backend eSCL (exige Avahi): descartado |

**Veredito:** nenhuma ferramenta entrega "um clique, PDF ou JPG, milhares de páginas de mesa". As lacunas reais do software próprio são: sessão e documento com diário à prova de queda e finalização antecipada, alternância PDF/JPG com presets, nomes sem colisão, pós-processamento em segundo plano e refazer/descartar a última. Dividir várias fotos sozinho **não** é lacuna (o Captura de Imagem já faz).

### 3.3 Imagem e PDF

- O JPEG do scanner é o **mestre**; o PDF é montado com `img2pdf`, que coloca os bytes JPEG no PDF **sem recomprimir**. O Pillow recomprimiria cada página.
- Armadilha: sem densidade (dpi) no JPEG, o PDF sai com 96 dpi e o tamanho de página errado; a densidade JFIF precisa ser normalizada sem recodificar a imagem.
- Tamanho: uma página A4 colorida a 300 dpi tem cerca de 0,65–1,4 MB; 1.000 páginas ocupam 0,65–1,4 GB e 20.000 páginas, 13–28 GB.
- Diretrizes de digitalização (Library of Congress, FADGI, NARA): documentos a 300 dpi, fotos a 600 dpi (mínimo 400). JPEG é formato de acesso, não de preservação.
- OCR fica para depois: Apple Vision (pt-BR funciona, 0,3–0,8 s por página) ou Tesseract (os dados `por` não estão instalados). A camada de texto nunca deve ser escrita à mão.

---

## 4. Decisões tomadas e alternativas descartadas

| # | Decisão | Alternativas descartadas |
|---|---|---|
| D1 | **Escopo em fases:** MVP = Gate 0 + um clique, um arquivo | Construir tudo de uma vez |
| D2 | **Cliente eSCL direto em Python (`httpx`)** atrás de uma porta `ScannerGateway`; plano B se o Gate 0 falhar: outro adaptador atrás da mesma porta | SANE; ImageCaptureCore em Swift (sem Xcode, e depende do mesmo eSCL) |
| D3 | **Servidor FastAPI em `127.0.0.1` + página web**, iniciado pelo Terminal.app com duplo clique | SwiftUI, PySide/Tk, Electron/Tauri |
| D4 | **JPEG do scanner como mestre**; PDF por `img2pdf`; PDF/JPG é só o codificador local | Pedir PDF ao scanner; Pillow para PDF |
| D5 | Pasta configurável (padrão `~/Pictures/Digitalizadora`), guarda de espaço livre, gravação atômica, nome `AAAA-MM-DD_NNNNN.ext` sem nunca sobrescrever | Nome por data e hora sem contador |
| D6 | **Exceção à sua regra de nomes (precisa da sua aprovação):** módulos Python em `snake_case`, todo o resto em kebab-case, porque `import scan-service` é erro de sintaxe (verificado) | Carregar cada módulo com `importlib` |
| D7 | Segurança local: só `127.0.0.1`, `Host` validado (DNS rebinding), cabeçalho `X-Requested-With: digitalizadora` nos métodos que alteram estado (CSRF), sem CORS | Servidor sem proteção |
| D8 | Descoberta: `python-zeroconf` (IPv4), endereço salvo com UUID, endereço manual; HTTP por padrão; recomendo reservar o IP no roteador | Só `dns-sd`; HTTPS por padrão |
| D9 | Testes: `pytest` + impressora falsa ASGI com injeção de falhas + fixtures reais do Gate 0; testes de hardware opcionais | Testar só contra a impressora real |
| D10 | Não atualizar o macOS antes do Gate 0 e do MVP; registrar a build | Atualizar para o macOS 26/27 |

---

## 5. Arquitetura e escopo

### 5.1 Camadas

```
Navegador  (index.html + application.js)          HTTP + JSON, somente 127.0.0.1
   │
┌──▼───────────────────────────────────────────────────────────────┐
│ controllers      HTTP ⇄ serviços; mensagens em português          │
├──────────────────────────────────────────────────────────────────┤
│ services         ScanService, ScanOutputService,                   │
│                  PrinterConnectionService, StorageGuardService…    │
├──────────────────────────────────────────────────────────────────┤
│ domain           modelos, erros e portas (Protocols)               │
├─────────────────────────────┬────────────────────────────────────┤
│ repositories                │ infrastructure                      │
│ arquivos, JSON              │ eSCL (httpx), zeroconf, relógio     │
└─────────────────────────────┴────────────────────────────────────┘
composition_root.py monta tudo por injeção de construtor; nada de estado global
```

Dependência: controllers → services → domain ← repositories e infrastructure. Cada função tem no máximo 3 parâmetros (regra Clean Code das suas skills); os contratos exatos estão na seção 6 do spec.

### 5.2 Fases

| Fase | Conteúdo | Condição para começar |
|---|---|---|
| **0 — Gate 0** | Com a impressora ligada, no Terminal.app: achar `_uscan._tcp`, ler as capacidades, digitalizar por `curl`, medir tempo e tamanho, testar o sono da impressora | Impressora ligada |
| **1 — MVP** (este plano, 15 tarefas) | Um clique ou Espaço → um arquivo PDF ou JPG, nome automático, pasta escolhida, guarda de espaço | Gate 0 positivo |
| **2 — Várias páginas e lote** (prioridade seguinte) | Sessão > Documento > Página, diário atômico + SQLite, "Finalizar documento", descartar a última, continuar depois de queda, `caffeinate`, sons | MVP rodando com a impressora real |
| **3 — Qualidade** | Página em branco, orientação, recorte de folha única; divisão de fotos só se as ferramentas existentes não bastarem | Comparação com fotos reais |
| **4 — OCR em segundo plano** | Tesseract (`por`) ou Vision, camada de texto por renderizador testado | Fase 2 pronta |
| **5 — App empacotado** | PyInstaller ou py2app + `pywebview`, permissão de Rede Local persistente | Teste de permissão entre reconstruções |
| **6 — Outros scanners** | A mesma porta aceita um scanner eSCL com alimentador | Se você comprar um |

---

## 6. Resultado da revisão do plano

Seis revisores independentes (cinco por faixa de tarefas e um global) leram o plano com quatro lentes: correção técnica e APIs, conformidade com o spec, regras suas e qualidade dos testes, modos de falha e segurança.

### 6.1 Números

- **65 achados:** 2 bloqueantes, 15 graves e 48 menores. Os graves têm 2 repetições entre revisores, então são **13 distintos**.
- **60 usos de bibliotecas conferidos:** 47 corretos, 5 errados e 8 não verificáveis.
- Os revisores **reconstruíram o código das tarefas numa pasta temporária e rodaram os testes**, e as contagens do plano batem: por exemplo 155 testes em T0–T3, 274 em T6–T8 (nenhum acima de uns 50 ms) e 187 em T10–T11. O XML do script de teste da impressora ficou idêntico, byte a byte, ao do código de T3. As falhas encontradas estão abaixo.

### 6.2 Os 15 itens críticos

| # | Gravidade | Tarefa | Problema | Efeito se ficar assim |
|---|---|---|---|---|
| 1 | Bloqueante | T3 | O teste usa `Callable` sem importar | O arquivo de teste não carrega (`NameError`) |
| 2 | Bloqueante | T5 | A detecção de "Rede Local bloqueada" olha só `__cause__`, mas o httpx liga o `OSError` por `__context__` | A mensagem específica nunca aparece em produção; os testes escondem o defeito |
| 3 | Grave | T3 | O parser só captura `ParseError`; um encoding desconhecido (`LookupError`) escapa | Vira `unexpected_error` em vez de `scan_failed` |
| 4 | Grave | T5 | O resultado esperado do Passo 6 está errado (2 falham e 9 passam), e dois testes de cor não podem falhar na fase vermelha | Quem executa se confunde; testes que não discriminam |
| 5 | Grave | T9 | `check_connection` "nunca levanta" mas só captura `ScannerUnreachableError`; erros do zeroconf (`RuntimeError`, `OSError`) escapam | Impressora offline pode virar erro 500 em vez de mensagem clara |
| 6 | Grave | T9 | `refresh` apaga o endereço salvo antes de procurar | Perde a preferência por UUID e esquece a impressora se ela estiver dormindo |
| 7 | Grave | T9 | A Rede Local só é detectada quando há endereço salvo; no primeiro uso, uma busca vazia vira `scanner_unreachable` sem a dica do Terminal.app | O usuário não recebe a orientação certa |
| 8 | Grave | T8 | O leitor de espaço livre só trata pasta inexistente; `PermissionError` e `OSError` (permissão do macOS, disco ejetado) escapam | Erro cru na interface |
| 9 | Grave | T11 | Erros do framework e inesperados saem fora do formato `{code, message}`; `expanduser` e o caractere NUL não são tratados | Resposta 500 em texto puro |
| 10 | Grave | T11 | A mudança de contrato ACC-8 quebra o fixture de `test_scan_controller` (`TypeError`) e deixa textos e contagens defasados | Seis testes quebram na preparação |
| 11 | Grave | T0 | Os comandos `dns-sd` do roteiro do Gate 0 não terminam sozinhos | Colar o bloco trava; o Ctrl-C descarta o resto |
| 12 | Grave | T12 | Nenhum teste de comportamento para o Espaço e a repetição de tecla (só busca de texto) | O modo de falha 2 fica sem prova |
| 13 | Grave | T13 | O launcher considera pronto um `.venv` instalado pela metade | Uma primeira execução sem internet deixa o app quebrado para sempre |
| 14 | Grave | T13 | O teste de composição precisa de uma costura de descoberta que o ACC-12 não oferece | Os testes não podem ser escritos como planejado |
| 15 | Grave | T14 | O fixture do teste de 409 pode competir com o pedido à impressora | Teste intermitente |

### 6.3 Achados por revisor

| Revisor | Faixa | Bloqueantes | Graves | Menores |
|---|---|---|---|---|
| a | T0–T3 | 1 | 1 | 8 |
| b | T4, T5, T9 | 1 | 3 | 2 |
| c | T6–T8 | 0 | 1 | 7 |
| d | T10–T11 | 0 | 2 | 7 |
| e | T12–T14 | 0 | 4 | 11 |
| f (global) | plano inteiro | 0 | 4 | 13 |

Os 48 achados menores (estilo, mensagens, contagens esperadas, pequenas lacunas de teste) estão no arquivo de achados, com evidência e correção sugerida.

### 6.4 O que ficou pendente

1. Aplicar as **13 mudanças de contrato aceitas** (ACC-1 a ACC-13) às tarefas. Já estão no spec, não no plano.
2. Aplicar os **65 achados** (ao menos os 15 críticos).
3. Rodar de novo o verificador estático e revisar só o que mudou.

---

## 7. Riscos e incertezas

| Risco | Prob. / impacto | Mitigação |
|---|---|---|
| eSCL ausente nesta unidade | média / alto | Gate 0 antes de codar; plano B: adaptador HP LEDM atrás da mesma porta, ou usar app HP, NAPS2 e VueScan |
| Mesa de vidro contra volume (20–50 s por página) | alta / alto | Expectativa clara; Fase 2 reduz o esforço por página; considerar um scanner com alimentador para documentos |
| Disco cheio (2–3 GB livres) | alta / alto | Pasta em disco externo, guarda de espaço, aviso na interface |
| Rede Local bloqueada (`No route to host`) | média / alto | Rodar pelo Terminal.app, mensagem própria, teste no Gate 0 |
| Impressora dorme ou muda de IP | alta / médio | UUID, endereço salvo e nova busca, repetição com espera, IP reservado |
| Peculiaridades do firmware HP (XML, 409 contra 503) | média / médio | XML numa linha, parser tolerante, `DELETE` sempre, fixtures reais |
| 600 dpi em cor contra 64 MB de RAM da impressora | média / médio | Medir no Gate 0; limitar o preset de foto a 400 dpi se preciso |
| Exposição da interface local (CSRF, DNS rebinding) | baixa / médio | `127.0.0.1`, checagem de `Host`, cabeçalho obrigatório |
| Atualização do macOS | baixa / alto | Não atualizar antes de validar; repetir o Gate 0 depois de qualquer atualização |
| Plano com defeitos conhecidos | certa / alto | Não executar antes de aplicar a seção 6.4 |

**Só o Gate 0 responde:** se `_uscan._tcp` aparece e em qual porta; as capacidades reais (resoluções, formatos); o tempo e o tamanho por página em cada resolução; se a impressora responde dormindo e quanto demora a acordar; se o HTTPS funciona com o OpenSSL do Python; se o Captura de Imagem lista a impressora.

---

## 8. Estado dos arquivos e do que estava rodando

### 8.1 O que estava rodando

**Nada.** A pesquisa e suas retomadas, a redação do plano e a revisão já haviam terminado quando você pediu para parar; o `TaskStop` confirmou que a última (a revisão) não estava mais ativa. Uma retomada da pesquisa que eu mesmo havia interrompido antes (ela repetia agentes já prontos) também está encerrada, e `ListAgents` não mostrou nenhum agente desta sessão em andamento.

### 8.2 No projeto (`<projeto>`)

| Arquivo | O que é | Estado |
|---|---|---|
| `md.md` | Seu pedido original | Intacto |
| `docs/superpowers/specs/2026-10-13-digitalizadora-design.md` | Design: fatos, decisões, arquitetura, **contratos exatos**, UX, testes, Gate 0, roadmap, riscos, perguntas | Atualizado com as 13 mudanças de contrato; **aguarda a sua revisão** |
| `docs/superpowers/plans/2026-10-17-digitalizadora-plano-final.md` | Plano com 15 tarefas (15,7 mil linhas, 235 blocos de código) | **Rascunho não revisado**, com um aviso no topo |
| `docs/superpowers/plans/2026-10-13-achados-da-revisao.md` | Os 65 achados da revisão, com evidência e correção sugerida | Completo |
| `docs/superpowers/plans/2026-10-13-mudancas-de-contrato-pendentes.md` | As 13 mudanças aceitas e as tarefas que elas afetam | Completo |
| `docs/superpowers/plans/ferramentas/check-plan-code.py` | Verificador estático do plano (sintaxe, máximo de 3 parâmetros, abreviações proibidas, marcadores de pendência) | Pronto para reuso |
| `docs/pesquisa/digest-da-pesquisa-2026-10-13.md` | Resultado consolidado da pesquisa, em inglês, com fontes; MAC e hostname da impressora foram trocados por marcadores | Completo |
| `docs/relatorio-do-levantamento-2026-10-13.md` | Este relatório | — |

Não existe código do produto, ambiente virtual nem repositório Git: o projeto só tem a pasta `docs/` e o `md.md`.

### 8.3 Fora do projeto

- **Memória do assistente** (`~/.claude/projects/-<usuario>-<projeto>/memory/`): duas anotações e o índice, sobre o estado do projeto e sobre como retomar execuções de workflow sem repetir trabalho.
- **Registros dos agentes** (`~/.claude/projects/-<usuario>-<projeto>/subagents/workflows/`): o texto bruto de cada pesquisador, cético, redator e revisor.
- **Pasta temporária da sessão** (cerca de 136 MB): partes do plano, ferramentas e as pastas de teste dos revisores. É descartável.
- **Documento online "Digitalizadora: relatório do levantamento"**, que comecei a criar antes do seu pedido de Markdown: ficou só com a estrutura (seções vazias). Este arquivo `.md` é o relatório de verdade; o documento online pode ser apagado, ou eu o preencho se você quiser.

---

## 9. O que preciso de você e próximos passos

### 9.1 Decisões

1. **Nomes:** aceita a exceção D6 (módulos Python em `snake_case`, o resto em kebab-case)? Recomendo sim.
2. **Onde guardar:** você tem um HD ou SSD externo? O disco interno tem só 2–3 GB livres. Há dados de contêineres (cerca de 39 GB e 11 GB) que você poderia reaproveitar; não mexi em nada.
3. **Interface:** uma página local no navegador, aberta por duplo clique, serve para a v1? Recomendo sim; app empacotado só na Fase 5.
4. **Volume:** 20–50 s por página é aceitável? Para milhares de folhas de documentos, vale pensar num scanner com alimentador; o app já nasce preparado para ele.
5. **Próxima fase:** PDF de várias páginas primeiro (recomendo) ou fotos primeiro?
6. **App HP:** você já digitalizou com ele neste Mac? Se sim, aumenta a chance de o eSCL funcionar.

### 9.2 Próximos passos, em ordem

1. **Ligar a impressora e fazer o Gate 0**, pelo Terminal.app, com a VPN desligada. O roteiro completo está na seção 9 do spec; o essencial:
   - `dns-sd -B _uscan._tcp local.` (Ctrl-C depois de uns 5 s) para ver se ela anuncia eSCL e em que porta;
   - `curl -s http://<endereço>:<porta>/eSCL/ScannerCapabilities` para ver as capacidades;
   - o Captura de Imagem lista a impressora? Uma digitalização de mesa a 300 dpi funciona?
2. **Digitalizar hoje com o que existe** (Captura de Imagem, app HP ou NAPS2), usando as receitas da seção 12 do spec. Elas não foram testadas, porque a impressora estava offline.
3. **Ler o spec** e responder às perguntas acima.
4. **Retomar o plano:** aplicar as 13 mudanças e os 65 achados (cinco corretores em paralelo, um por parte), rodar o verificador estático e revisar só o que mudou.
5. **Escolher como executar** (um agente por tarefa com revisão, ou tudo nesta sessão) e só então implementar.

---

## 10. Como o trabalho foi feito e transparência

- **Processo:** classifiquei o pedido como arquitetural (projeto novo) e segui `brainstorming` e `writing-plans`. Você pediu o plano direto, então escrevi spec e plano juntos e **não houve implementação**, que fica condicionada à sua aprovação.
- **Agentes:** 15 na pesquisa (7 pesquisadores, 7 céticos independentes e 1 consolidador), 5 na redação do plano e 6 na revisão: 26 no total, **cerca de 8,8 milhões de tokens** de subagentes (pesquisa 6,0 M, redação 1,4 M, revisão 1,4 M).
- **Limite de uso:** a primeira execução da pesquisa bateu no limite de uso da sessão e 3 agentes falharam; foi retomada. Na retomada, o cache reaproveita por **ordem de chamada**, e a ordem diferente repetiu 6 céticos já prontos; interrompi, corrigi a ordem e retomei de novo, gastando só o que faltava.
- **Limites das evidências:** a cota de buscas na web acabou em todas as frentes de pesquisa (a checagem passou a ser por leitura direta de fontes); `support.hp.com` e a Comunidade HP ficaram inacessíveis; as especificações da Mopria (eSCL) e da Apple (AirPrint) não foram lidas; **nada foi medido na impressora**.
- **O que os agentes fizeram no seu Mac:**
  - leram arquivos sem alterar nada (cache do app HP, que revelou o modelo e o MAC da impressora; PPD; Captura de Imagem; cabeçalhos do SDK; uso de disco);
  - baixaram fontes de referência para a pasta temporária (cerca de 1,1 GB; **apaguei cerca de 1 GB** de pastas grandes da pesquisa ao ver o disco em 99%);
  - um agente executou por engano `HP.app --version` e abriu brevemente um app SwiftUI de teste invisível (removido);
  - redatores e revisores rodaram o código do plano **em pastas temporárias** (pacotes como pytest, img2pdf e pikepdf só ali, e um ambiente virtual numa pasta temporária); nada foi instalado no seu Python (continua sem pytest, img2pdf, pikepdf nem zeroconf; o `uvicorn` já estava lá) nem no projeto.
- **Rede:** nenhum agente falou com a impressora nem sondou a rede local; eu fiz apenas uma busca Bonjour passiva.
- **Privacidade:** o MAC e o nome de host da impressora foram trocados por marcadores na cópia do digest guardada no projeto.
- **Suas regras:** seguidas literalmente, exceto a D6 (a aprovar). Interpretei "sem abreviações" como: siglas que nomeiam um formato ou protocolo (PDF, JPEG, HTTP, XML, eSCL) ficam; abreviações de palavras comuns (`id`, `url`, `dpi`) são proibidas.

---

## Fontes principais

- HP Brasil, página do produto 2874: https://www.hp.com/br-pt/shop/impressora-multifuncional-hp-deskjet-ink-advantage-2874-6w7g2a.html
- Mopria, certificação da série 2800: https://mopria.org/certifiedproducts/certified-products-en.php?type=product&productid=8230&lang=english
- HPLIP, banco de modelos: https://raw.githubusercontent.com/zdohnal/hplip/master/data/models/models.dat
- Dump de uma "2800 series" anunciando eSCL: https://forums.linuxmint.com/viewtopic.php?t=426948
- Apple TN3179, privacidade de Rede Local: https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy
- `sane-airscan`, implementação de referência do eSCL: https://raw.githubusercontent.com/alexpevzner/sane-airscan/master/airscan-escl.c
- NAPS2, cliente eSCL: https://raw.githubusercontent.com/cyanfish/naps2/master/NAPS2.Escl/Client/EsclClient.cs
- NAPS2, documentação do console e do lote: https://www.naps2.com/doc/command-line
- Library of Congress, guia de digitalização: https://www.digitalpreservation.gov/personalarchiving/documents/PA_scanning.pdf
- Apple, guia do Captura de Imagem: https://support.apple.com/guide/image-capture/welcome/mac

A lista completa, com mais de 100 fontes, está no [digest da pesquisa](pesquisa/digest-da-pesquisa-2026-10-13.md).

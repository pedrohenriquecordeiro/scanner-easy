# Moldura de corte por página, ampliação e giro só na página: design

**Data:** 2026-10-18 · **Status:** decisões tomadas e contratos fechados (seções 5 e 6), tarefas T32 a T50 na seção 9, prontas para virar plano · **Substitui** as partes de corte e giro de [Ajustes: girar, resoluções, corte](2026-10-17-ajustes-rotacao-resolucoes-corte.md) (decisões A1, A3, A4, A6 e A14, a lista "Girar" e a lista "Predefinição" da seção 3, o item 4.4 e o algoritmo 6.4 daquele documento). As demais decisões de lá (A2 para o JPEG recodificado a 95, A7, A8 a A13) continuam valendo. **Complementa** [Documento de várias páginas](2026-10-17-documento-de-varias-paginas.md) (as referências "R12", "6.6.1" etc. são desse documento) · **Baseline:** 2530 testes passando (5 de hardware pulados), `ruff` limpo, 10 commits locais.

## 1. O que você pediu (md.md, linhas 30 a 36, e a captura do modo Documento)

1. O corte deve aparecer **em cada página como uma moldura** e a moldura deve poder ser **ajustada**.
2. Cada página deve poder ser **ampliada** para conferir a moldura e, se estiver errada, ajustá-la ali.
3. **Tirar "Predefinição"**: ficam só **Resolução** e **Cor**.
4. **Tirar "Girar" dos ajustes**: girar existe **só no ícone da página**, nos modos Rápido e Documento. Na captura, o botão "Girar ↻" fica ao lado de "Mover para…" ("manter aqui").
5. Testar tudo na impressora real com o livro no vidro.

O que o código e as digitalizações reais do livro mostram, e que mudam o desenho:

- **Hoje o corte é destrutivo e sem volta.** `ImageAdjustmentService` corta o JPEG no momento da digitalização e grava o JPEG cortado como a página. Uma moldura ajustável exige o contrário: a página guardada continua sendo o JPEG do scanner, e a moldura é só um dado ao lado dela (decisão D1).
- **Hoje girar uma página do rascunho reescreve o arquivo** (`DocumentPageRotator` + `DocumentDraftStore.replace_page`, com identificador novo). É pesado (decodifica e recodifica até 143 megapixels), perde um pouco de qualidade a cada giro e é a parte mais complicada da segurança contra queda. Com a moldura em frações da página exibida, girar vira trocar dois números no manifesto (D2).
- **O detector atual não acha o livro.** Em `scratchpad/real-scans/NOTES.md` (4 digitalizações reais: 100 dpi em cor, 100 dpi em cinza, 300 dpi, 150 dpi) a tampa estava aberta e a borda da imagem não é um fundo uniforme: à esquerda é branco estourado (o livro some no fundo), à direita há uma sombra escura e em cima e embaixo um cinza claro em degradê. `detect_paper_region` devolve `None` nas quatro (a regra "a borda é um fundo" falha), então o corte automático nunca dispara nesse cenário. Medi um detector por lado (6.3) nas mesmas quatro imagens e ele acerta em cima, à direita e embaixo; a esquerda é invisível por natureza (branco sobre branco) e fica na borda do vidro, para você ajustar na moldura. É exatamente o caso em que ter a moldura ajustável vale mais do que um detector perfeito.
- **O modo Rápido não tem lugar para uma moldura**: o arquivo já foi entregue na sua pasta e a página mostra só a última miniatura. Ali o corte continua sendo aplicado direto (D9) e o giro vira "girar o último arquivo salvo" (D8).
- Ao girar sem trocar de identificador, a miniatura (servida com `Cache-Control: immutable` por identificador) ficaria velha. Por isso as miniaturas e a visão ampliada passam a levar a rotação na própria URL (`?rotation_degrees=90`): a resposta é uma função pura de (página, rotação) e pode mesmo ser guardada para sempre (D6).

## 2. Decisões (tomadas pelo assistente; corrija se quiser)

| # | Decisão | Por quê | Alternativa descartada |
|---|---|---|---|
| D1 | **Não destrutivo.** O JPEG da página no disco (`page-<identificador>.jpg`) continua sendo o JPEG do scanner, com a densidade gravada e mais nada. Cortar e girar nunca o reescrevem. Cada página ganha no manifesto `rotation_degrees` (0, 90, 180 ou 270, sentido horário) e `crop` (`null` = página inteira, ou quatro frações `left`, `top`, `right`, `bottom` entre 0 e 1 **da página como é exibida, depois do giro**). | Ajustar a moldura quantas vezes quiser sem perder pixel; giro instantâneo e sem perda; a mesma moldura vale a 100 ou a 1200 dpi (frações). | Cortar de verdade ao digitalizar e guardar o original ao lado (o dobro do disco, e o PDF teria de escolher qual usar) |
| D2 | **Girar a página do rascunho = só metadado.** `POST /api/document/pages/{page_identifier}/rotation` troca `rotation_degrees` por +90° e **gira também o retângulo da moldura** (fórmula em 6.1, com vetores de teste compartilhados entre Python e JavaScript). O identificador da página **não muda**. `DocumentPageRotator`, `DocumentDraftStore.replace_page`, `ensure_capacity_for_replacement` e `DocumentDraft.with_page_replaced` **saem**. | Edição só do manifesto: o `replace_file` atômico já existente (ou o manifesto antigo, ou o novo, nunca um meio-termo). Some a janela de queda de "arquivo novo, manifesto velho" e a regra de espaço em dobro. | Manter a regravação do arquivo |
| D3 | **A moldura nasce na digitalização, mas não é aplicada.** Com "Cortar automaticamente e remover o fundo" ligado, cada página nova do modo Documento passa pela detecção sobre uma prévia reduzida e o resultado vira o `crop` da página. Se nada confiável for achado, `crop` fica `null`. Com a caixa desligada, `crop` nasce `null` (página inteira) e você pode desenhar uma moldura à mão. Detecção que falha **nunca** impede a página de entrar no rascunho (vira `null` e vai para o log). | A moldura é uma sugestão que você confere; errar custa um arrasto, não uma página perdida. | Falhar a digitalização quando a detecção falha |
| D4 | **Nas páginas do modo Documento a detecção é mais tolerante do que no modo Rápido** (6.3). No modo Documento vale `detect_crop_to_suggest`: primeiro o detector estrito de hoje (`detect_paper_region`, que só aceita bordas uniformes) e, se ele não achar nada, um detector por lado (`detect_paper_edges`) que aceita no mínimo dois lados com borda clara e deixa os outros na borda do vidro. No modo Rápido vale `detect_crop_to_apply`, só o estrito. | No modo Documento a moldura é visível e editável, então um palpite parcial é útil; no modo Rápido o corte é destrutivo, e o estrito foi o que as três revisões validaram contra perder conteúdo. | Um só detector tolerante nos dois modos (risco de cortar conteúdo sem como desfazer) |
| D5 | **Renderização só ao salvar, página por página.** Ao "Salvar", cada página com `rotation_degrees` 0 e `crop` nulo entra no PDF **com os bytes do scanner intactos** (img2pdf embute o JPEG sem recomprimir, como hoje). Cada página com giro ou moldura é renderizada na hora em que o img2pdf a pede: abre o mestre, corta na orientação do mestre, gira, grava um JPEG qualidade 95 com a mesma densidade JFIF, entrega os bytes e solta os pixels. Nunca há duas páginas decodificadas ao mesmo tempo. | A 1200 dpi uma A4 tem 143 MP e cerca de 430 MB decodificados; medi 0,4 s e pico de 950 MB para cortar e girar uma dessas. | Renderizar todas antes de montar o PDF (picos somados) |
| D6 | **Miniatura e visão ampliada vêm do mestre girado, sem corte**, para a moldura se alinhar por porcentagem. A miniatura em disco (`thumbnail-<identificador>.jpg`) continua a do mestre sem giro, e o servidor a gira (imagem pequena, de 480 px) conforme `?rotation_degrees=`. A visão ampliada é uma prévia de 1600 px no lado maior, decodificada reduzida (`Image.draft`) do mestre e girada, em `GET /api/document/pages/{page_identifier}/preview?rotation_degrees=`. **Sem cache no servidor**: a resposta é `immutable` por URL, o navegador a guarda, e medi 0,11 s e 88 MB de pico para gerá-la a 1200 dpi. | Mantém o disco com um arquivo por página e uma miniatura, e nenhuma queda deixa miniatura girada com manifesto não girado. | Gravar uma miniatura por rotação (arquivos a mais e regras de recuperação); cache em memória no servidor (código e testes por 0,1 s) |
| D7 | **Configurações: saem a lista Predefinição e a lista Girar.** `GET`/`PUT /api/settings` e o objeto `settings` de `/api/state` deixam de ter `scan_preset` e `rotation_degrees`. O `PUT` ignora chaves desconhecidas (comportamento padrão do Pydantic), então um cliente antigo que mande `scan_preset` ou `rotation_degrees` é aceito e **ignorado** (um `scan_preset` sozinho, sem resolução nem cor, deixa a qualidade salva como está). `settings.json` antigo carrega: `rotation_degrees` é ignorado e `scan_preset` só vale como reserva quando o par resolução/cor falta ou é inválido (como já é hoje). `ScanPreset` **fica no domínio** como tabela da qualidade padrão e dos nomes que um arquivo antigo pode guardar, sem `matching`. | Atende o pedido sem uma limpeza de 30 arquivos de teste que só usam `ScanPreset.DOCUMENT.settings` como valor de exemplo. | Apagar `ScanPreset` (churn grande, sem ganho de comportamento; pode ser um passo futuro) |
| D8 | **Modo Rápido: girar o último arquivo salvo, no próprio arquivo.** O painel "Última digitalização" ganha **Girar ↻**. `POST /api/scans/last/rotation`: JPG = `Image.transpose` + recodificação qualidade 95 mantendo densidade, subamostragem e perfil; PDF = atualização sem perda de `/Rotate` com pikepdf. O arquivo é trocado de forma atômica (`AtomicFileWriter.replace_file`, mesmo nome), a miniatura da última digitalização é girada e a página a recarrega. Só vale para a última digitalização desta execução (a "última" é memória do servidor). | O arquivo é do tracker de progresso, que já sabe qual é; o usuário pediu giro "no ícone da página" também no modo rápido. O PDF não perde nada; o JPG recodifica uma vez por giro (invisível a 95). | Girar qualquer arquivo da pasta (mexer em arquivo que o app não acabou de criar) |
| D9 | **Modo Rápido não tem editor de moldura.** Com a caixa ligada, o corte é aplicado direto no arquivo no momento da digitalização, como hoje (`detect_crop_to_apply`). A dica da caixa diz isso (seção 3). | O arquivo já está na sua pasta; um editor ali seria um segundo aplicativo. Se precisar ajustar, use o modo Documento. | Moldura também no Rápido (exigiria guardar o original) |
| D10 | **A rotação e a moldura são edições do rascunho** como excluir e reordenar: mesmo bloqueio (`DocumentDraftService._run_edit`), mesmas regras de 409, aumentam `revision` quando mudam algo, e **tiram as marcas de finalização** (um PDF gravado antes da mudança não confere mais). Mudar a moldura para o mesmo valor, ou rodar a detecção sem achar nada, não muda nada e não aumenta `revision` (como `rename` e `reorder` iguais). | Uma só regra de segurança para todas as edições. | Edições fora do bloqueio |
| D11 | **Dois erros de validação novos**: `invalid_crop` (422) e `invalid_page_rotation` (422). Três para o modo Rápido: `no_last_scan` (404), `last_scan_file_missing` (409) e `saved_scan_unreadable` (409). | Cada situação tem texto próprio em português e a interface decide o que fazer pelo código. | Reaproveitar `invalid_settings` |
| D12 | **Interface da moldura:** em cada miniatura, uma `div` posicionada em porcentagem com borda de duas cores e fora escurecido; botão **Ampliar** abre um `<dialog>` com a visão ampliada, moldura arrastável e redimensionável por 8 alças (eventos de ponteiro) e a alternativa de teclado nas mesmas alças (setas, Shift anda mais). Botões: **Detectar automaticamente**, **Sem corte**, **Girar ↻**, **Cancelar** (Esc) e **Aplicar**. A geometria (limitar, redimensionar por alça, empurrar, girar o retângulo, de e para frações) fica num módulo JavaScript puro, `page-frame-geometry.js`, testado no Node. | Pedido 1 e 2, com acessibilidade por teclado e anúncios em português. | Campos numéricos (quatro campos a mais para a mesma coisa que as setas fazem) |
| D13 | **Capacidade e estimativa.** Páginas do modo Documento não são recodificadas na digitalização, então a checagem de espaço e a estimativa do disco do rascunho deixam de contar o "fator de ajuste" (que fica só no modo Rápido). Ao salvar, a estimativa do PDF conta o fator de recodificação (2) apenas nas páginas com giro ou moldura. | A conta reflete o que realmente vai a disco em cada etapa. | Manter o fator em tudo |

**Desvios dos padrões que a tarefa pedia, com a justificativa:**

- **Sem arquivo JPEG temporário no salvar.** O padrão pedia gravar cada página renderizada num JPEG temporário. Medi no código instalado (img2pdf 0.6.3) que `convert` percorre as entradas em sequência e, para cada uma, chama `read()` (se existir) ou lê o arquivo inteiro para a memória antes de passar à seguinte. Basta então entregar objetos com `read()` que renderizam na hora: o mesmo efeito de "uma página por vez" sem arquivo temporário, sem faxina de sobras e sem espaço extra em disco. Os bytes JPEG de todas as páginas já ficavam na memória (o PDF é montado em memória pelo pikepdf, como hoje); só os pixels decodificados são soltos a cada página.
- **Sem cache da visão ampliada no servidor** (D6): o navegador faz o cache por URL.
- **`ScanPreset` continua existindo** (D7).

## 3. Interface

**Caixa Ajustes**, de cima para baixo (comum aos dois modos, exceto o formato):

1. **Formato do arquivo** (PDF, JPG), como hoje; escondido no modo Documento.
2. Grupo **Qualidade** só com **Resolução** (as oito: 75, 100, 150, 200, 300, 400, 600 e 1200 dpi) e **Cor** (Colorido, Tons de cinza), mais o aviso de 600 e 1200 dpi. **Sem Predefinição.**
3. ~~Girar~~ (removido, com a dica dele).
4. Caixa **Cortar automaticamente e remover o fundo** (desligada por padrão), com a dica nova: "Use para fotos e folhas menores que o vidro. No modo Documento, o corte aparece como uma moldura em cada página e você pode ajustá-la em Ampliar; no modo Rápido, ele é aplicado direto no arquivo. Se não achar uma borda confiável, a imagem fica inteira."
5. **Pasta de saída** com **Salvar pasta**.

**Miniatura no modo Documento.** A miniatura fica dentro de um invólucro (`page-thumbnail-frame`, posição relativa, `overflow: hidden`) cuja proporção é a da própria imagem (lida de `naturalWidth` e `naturalHeight` quando a miniatura carrega), para a moldura em porcentagem cair exatamente sobre a página mesmo quando ela é deitada. Sobre ela, quando `crop` não é `null`, a moldura (`page-crop-overlay`, `aria-hidden`): borda de 2 px clara com contorno de 1 px escuro (legível em página clara e escura) e `box-shadow: 0 0 0 9999px` translúcido para escurecer fora. Clicar na miniatura também abre a visão ampliada (conveniência do mouse; o teclado usa o botão). As ações da página, nesta ordem de Tab:

| Linha | Botões |
|---|---|
| 1 | ◀ · ▶ · × (como hoje) |
| 2 | **Girar ↻** · **Mover para…** (mantidos lado a lado, como você pediu) |
| 3 | **Ampliar** (largura inteira, `aria-label="Ampliar a página N e ajustar a moldura de corte"`) |

O `aria-label` do item vira "Página N de M" ou "Página N de M, com moldura de corte".

**Visão ampliada** (`<dialog id="page-frame-dialog" class="page-dialog frame-dialog">`):

- Título: "Página N de M: moldura de corte". Texto de ajuda: "Arraste as bordas ou os cantos da moldura. Com o teclado, escolha uma alça (Tab) e use as setas; Shift anda mais."
- O palco (`frame-stage`, `display: inline-block`, sem espaço sobrando) contém a `<img>` ampliada (até 70 vh de altura) e a moldura (`frame-box`) em porcentagem, com um botão central **Mover a moldura** e oito botões de alça (`aria-label`: "Borda esquerda", "Borda direita", "Borda de cima", "Borda de baixo", "Canto superior esquerdo", "Canto superior direito", "Canto inferior esquerdo", "Canto inferior direito"). Alças são `<button type="button">`, não `div`: o Espaço num botão nunca inicia uma digitalização (`is_space_reserved_by`) e o foco visível sai do navegador. A área de toque de cada alça tem pelo menos 44 px (preenchimento invisível) e `touch-action: none`.
- Abaixo do palco, um parágrafo `role="status" aria-live="polite"` com o texto atual da moldura ("Moldura: esquerda 13%, topo 12%, direita 91%, base 91%." ou "Sem corte: a página inteira será usada.") e os anúncios do dialog.
- Botões: **Detectar automaticamente** · **Sem corte** · **Girar ↻** · **Cancelar** · **Aplicar**. **Esc** é Cancelar. O foco inicial vai para **Mover a moldura** (as setas já funcionam). **Enter não aplica** (evita aplicar sem querer); Aplicar é um clique ou Tab + Enter/Espaço no botão.
- Semântica: arrastar e empurrar mudam só uma **moldura de rascunho local**; **Aplicar** envia `PUT .../crop` (desabilitado enquanto igual à salva); **Sem corte** zera o rascunho (Aplicar então envia `null`); **Cancelar** descarta o rascunho; **Detectar automaticamente** e **Girar ↻** são **ações imediatas** no servidor (salvam na hora); depois de uma detecção que achou, o rascunho passa a ser a moldura detectada, e depois de Girar o rascunho local também gira (mesma fórmula do servidor), então um ajuste ainda não aplicado sobrevive ao giro.
- Textos de status (todos em português): ao arrastar, só ao soltar ("Moldura: ..."); ao empurrar com seta: "Borda esquerda em 13%." (alça de canto: "Canto superior esquerdo: esquerda 13%, topo 12%."); detecção que achou: "Moldura detectada e salva. Moldura: ..."; que não achou: "Não achei uma borda confiável nesta página. A moldura não mudou."; aplicada: "Moldura aplicada à página 2." ou "Corte removido da página 2."; giro: "Página 2 girada 90° para a direita. A moldura acompanhou o giro."; cancelar com mudanças: "Alterações da moldura descartadas."; falha da imagem: "Não consegui carregar a imagem ampliada desta página."; página sumiu (outra aba): "Essa página não está mais no documento." e o dialog fecha.
- Durante uma digitalização ou outra edição, os botões que editam ficam desabilitados (mesma regra `can_edit_document`); olhar continua possível. Ao fechar, o foco volta ao botão **Ampliar** da página.
- Teclas globais: o painel considera o dialog como "diálogo aberto" (`is_confirmation_open()` passa a incluir `page-frame-dialog`), então Backspace, Enter e Esc do modo Documento ficam inertes enquanto ele está aberto. No dialog um filtro em fase de captura impede que Espaço e Backspace cheguem ao tratador da página.

**Modo Rápido, painel "Última digitalização":** um botão **Girar ↻** (`last-scan-rotate-button`, `aria-label="Girar a última digitalização 90 graus para a direita"`) ao lado dos detalhes. Fica desabilitado durante uma digitalização e enquanto o giro roda. Ao terminar, a linha de status (`role="status"`) diz "Última digitalização girada 90° para a direita." e a miniatura recarrega (a versão da miniatura passa a ser `last_result_revision`, 4.5). Dica curta abaixo: "Girar regrava o arquivo salvo."

**Mensagens novas do catálogo de erros** (`error_message_catalog.py`):

| Código | Texto |
|---|---|
| `invalid_crop` | "A moldura de corte é inválida. Ajuste e tente de novo." |
| `invalid_page_rotation` | "Rotação inválida." |
| `no_last_scan` | "Ainda não há uma digitalização para girar." |
| `last_scan_file_missing` | "O arquivo da última digitalização não está mais na pasta de saída." |
| `saved_scan_unreadable` | "Não consegui ler o arquivo da última digitalização para girá-lo. Veja o registro em ~/Library/Logs/Digitalizadora." |

O texto de `image_adjustment_failed` passa a "Não consegui cortar a imagem com a memória livre do Mac. Escolha uma resolução menor, desligue o corte automático e tente de novo." (o giro de página deixou de usar memória).

## 4. API (todas com o guarda de `Host`; as que escrevem, com o cabeçalho `X-Requested-With`)

### 4.1 Configurações

`GET /api/settings` e o objeto `settings` de `GET /api/state` passam a ser:

```json
{ "output_folder": "/Users/pedro/Pictures/Digitalizadora", "output_format": "pdf", "dots_per_inch": 300,
  "color_mode": "color", "capture_mode": "single", "auto_crop": false }
```

`PUT /api/settings`: obrigatórios `output_folder` e `output_format`; opcionais (ausente ou `null` mantém o salvo) `capture_mode`, `dots_per_inch`, `color_mode`, `auto_crop`. Qualquer outra chave (inclusive `scan_preset` e `rotation_degrees` de um cliente antigo) é ignorada sem erro. Os demais erros ficam como hoje.

### 4.2 Corpo do documento

`GET /api/document` e toda edição devolvem o corpo de 6.5 do outro spec com **dois campos novos em cada página**:

```json
{ "page_identifier": "…", "scanned_at": "…", "dots_per_inch": 300, "color_mode": "color", "size_in_bytes": 682312,
  "rotation_degrees": 90, "crop": { "left": 0.13, "top": 0.115, "right": 0.924, "bottom": 0.925 } }
```

`rotation_degrees` ∈ {0, 90, 180, 270}; `crop` é `null` ou quatro números entre 0 e 1 **na orientação exibida** (já girada). O resto do corpo não muda.

### 4.3 Rotas do documento

| Rota | Corpo | Resposta | Observação |
|---|---|---|---|
| `POST /api/document/pages/{page_identifier}/rotation` | nenhum | `200` corpo do documento | gira 90° à direita (mantida); metadado apenas; a moldura gira junto |
| `PUT /api/document/pages/{page_identifier}/crop` | `{"crop": null}` ou `{"crop": {"left","top","right","bottom"}}` | `200` corpo do documento | valida `0 ≤ left < right ≤ 1` e `0 ≤ top < bottom ≤ 1` com tamanho mínimo de 2% em cada eixo (`invalid_crop`, 422); arredonda a 6 casas; uma moldura igual à página inteira vira `null` |
| `POST /api/document/pages/{page_identifier}/crop/detect` | nenhum | `200` corpo do documento **mais** `"crop_detected": true` ou `false` | roda `detect_crop_to_suggest` no mestre e guarda o resultado (já na orientação exibida); se não achar nada, a moldura **não muda** e a revisão não sobe |
| `GET /api/document/pages/{page_identifier}/thumbnail?rotation_degrees=N` | | JPEG | `N` opcional (padrão 0); sem giro devolve os bytes guardados, com giro gira a miniatura pequena; `Cache-Control: private, max-age=31536000, immutable` |
| `GET /api/document/pages/{page_identifier}/preview?rotation_degrees=N` | | JPEG de até 1600 px no lado maior | mesmo cabeçalho de cache; decodificação reduzida do mestre |

Erros (formato `{code, message}`; os de arquivo com `page_identifier` no corpo, como em R18):

| Situação | Código | Status |
|---|---|---|
| Digitalização em andamento (edições) | `scan_already_running` | 409 |
| Outra edição em andamento | `document_busy` | 409 |
| Sem rascunho | `no_open_document` | 404 |
| Identificador fora do rascunho ou mal formado | `page_not_found` | 404 |
| Moldura inválida (valores, ordem, tamanho, tipo ou formato do corpo) | `invalid_crop` | 422 |
| `rotation_degrees` fora de {0, 90, 180, 270} ou que não é número | `invalid_page_rotation` | 422 |
| Mestre ausente, de tamanho diferente do manifesto ou ilegível (detecção, ampliação) | `damaged_document_page` | 409 |
| Disco do rascunho indisponível | `draft_storage_unavailable` | 503 |

O guarda de corpo mal formado (`ErrorResponses.respond_to_invalid_body`) hoje olha o caminho exato; passa a olhar uma lista de padrões (`VALIDATION_ERROR_CODE_PATTERNS`, 7), para que `…/{identificador}/crop` responda `invalid_crop` e `…/{identificador}/(thumbnail|preview)` responda `invalid_page_rotation`.

### 4.4 Último arquivo do modo Rápido

`POST /api/scans/last/rotation`, sem corpo. Gira o último arquivo salvo 90° à direita, no próprio arquivo, e responde `200`:

```json
{ "last_result": { "file_name": "2026-10-18_00001.pdf", "output_folder": "…", "output_format": "pdf",
                   "size_in_bytes": 95412, "scanned_at": "…" } }
```

| Situação | Código | Status |
|---|---|---|
| Ainda não houve digitalização nesta execução | `no_last_scan` | 404 |
| Digitalização em andamento | `scan_already_running` | 409 |
| Arquivo apagado ou movido | `last_scan_file_missing` | 409 |
| Arquivo que não abre como JPEG ou PDF | `saved_scan_unreadable` | 409 |
| Pouco espaço ou pasta indisponível | `insufficient_storage` (507) · `output_folder_unavailable` (503) | |
| Sem memória para decodificar (JPG de 1200 dpi) | `image_adjustment_failed` | 500 |

### 4.5 Estado

`GET /api/state` ganha `last_result_revision` (inteiro, sobe a cada digitalização rápida concluída e a cada giro do último arquivo; a página usa-o como versão da miniatura, caindo para `scans_completed` quando um servidor antigo não o envia). Nada mais muda no estado; `document.draft_storage` passa a ser estimado só com a qualidade (D13).

## 5. Contratos

Todas as assinaturas respeitam: no máximo 3 parâmetros por método e construtor (sem `self`), nenhum parâmetro booleano, sem abreviações, injeção por construtor (só `composition_root.py` instancia concretos), camadas `controllers → services → domain ← repositories/infrastructure`.

### 5.1 `domain/`

```python
# page_crop.py   (NOVO)
MINIMUM_CROP_SIDE_SHARE = 0.02
CROP_PRECISION_DIGITS = 6
CROP_SIDE_TOLERANCE = 1e-9

@dataclass(frozen=True)
class PageCrop:
    """A rectangle in fractions (0..1) of the page as it is displayed, after the page rotation."""
    left: float
    top: float
    right: float
    bottom: float

    def __post_init__(self) -> None: ...        # InvalidCropError: not finite, outside 0..1, side below the minimum
    @classmethod
    def rounded(cls, edges: tuple[float, float, float, float]) -> "PageCrop": ...   # rounds to 6 digits, then validates
    @property
    def covers_whole_page(self) -> bool: ...
    def turned_clockwise(self) -> "PageCrop": ...          # 6.1: (l, t, r, b) -> (1 - b, l, 1 - t, r)
    def turned_counterclockwise(self) -> "PageCrop": ...   # 6.1: (l, t, r, b) -> (t, 1 - r, b, 1 - l)
    def to_pixel_region(self, image_size: tuple[int, int]) -> PixelRegion: ...        # floor of the origin, ceil of the far edges
    @classmethod
    def from_pixel_region(cls, region: PixelRegion, image_size: tuple[int, int]) -> "PageCrop": ...

WHOLE_PAGE = PageCrop(0.0, 0.0, 1.0, 1.0)

# page_framing.py   (NOVO)
@dataclass(frozen=True)
class PageFraming:
    """How a stored page is shown and saved: the rotation and the crop; the stored JPEG never changes."""
    rotation: PageRotation = PageRotation.NONE
    crop: PageCrop | None = None

    @property
    def needs_rendering(self) -> bool: ...                 # rotation is not NONE or crop is not None
    def turned_clockwise(self) -> "PageFraming": ...       # rotation +90 and the crop turned with it
    def with_crop(self, crop: PageCrop | None) -> "PageFraming": ...   # a crop that covers the whole page becomes None
    def crop_on_master(self) -> PageCrop | None: ...       # the crop turned back to the orientation of the stored JPEG
    def crop_from_master(self, master_crop: PageCrop) -> PageCrop: ...  # a crop found on the stored JPEG, in the displayed orientation

UNFRAMED = PageFraming()

# document_draft.py   (MUDA)
@dataclass(frozen=True)
class DocumentPage:
    page_identifier: str
    scanned_at: datetime
    dots_per_inch: int
    color_mode: ColorMode
    size_in_bytes: int
    framing: PageFraming = UNFRAMED          # last field with a default: every five-argument construction keeps working

# DocumentDraft: NOVO with_page_framing(self, page_identifier: str, framing: PageFraming) -> DocumentDraft
#   (position kept, PageNotFoundError for an unknown page, no finalization marks, as every content change)
# DocumentDraft: NOVO estimated_document_size_in_bytes -> int   (size x RENDERED_PAGE_SIZE_FACTOR (2) for pages that need rendering)
# DocumentDraft: SAI with_page_replaced

# errors.py   (ACRÉSCIMO)
# InvalidCropError(DigitalizadoraError)        code = "invalid_crop"
# InvalidPageRotationError(DigitalizadoraError) code = "invalid_page_rotation"
# NoLastScanError(DigitalizadoraError)          code = "no_last_scan"
# LastScanFileMissingError(DigitalizadoraError) code = "last_scan_file_missing"
# SavedScanUnreadableError(DigitalizadoraError) code = "saved_scan_unreadable"

# image_adjustment.py   (MUDA: perde o giro)
@dataclass(frozen=True)
class ImageAdjustment:
    auto_crop: bool = False
    @property
    def is_active(self) -> bool: ...        # auto_crop

# scan_progress.py   (MUDA)  ScanProgressSnapshot ganha, no fim, last_result_revision: int = 0

# scan_preset.py   (MUDA: perde matching(); o resto fica, ver D7)

# ports.py   (ACRÉSCIMO em ScanOutputRepository)
#   def read_saved_scan(self, scan_path: Path) -> bytes | None: ...
#   def replace_saved_scan(self, scan_path: Path, content: bytes) -> None: ...
```

`PageRotation` não muda. A moldura **não** é um parâmetro booleano nem um parâmetro de função: `PageFraming` agrupa giro e moldura, o que mantém as assinaturas em até três parâmetros.

### 5.2 `repositories/`

```python
# document_manifest_codec.py   (MUDA; format_version continua 1)
ROTATION_DEGREES_KEY = "rotation_degrees"
CROP_KEY = "crop"
# encode: cada página ganha "rotation_degrees" e "crop" (null ou {"left","top","right","bottom"}).
# decode: chave ausente = 0 e null (manifesto antigo). Valor presente e inválido (rotação fora das quatro,
#         moldura que não valida) = o padrão da chave + um aviso no log; NÃO torna o manifesto ilegível
#         (justificativa em 7: um manifesto ilegível põe o rascunho inteiro de lado; perder só uma moldura é barato).

# file_system_scan_output_repository.py   (MUDA; implementa o port)
#   read_saved_scan(scan_path) -> bytes | None            # None se o arquivo não existe
#   replace_saved_scan(scan_path, content) -> None        # file_writer.replace_file; OSError -> translate_storage_error

# json_application_settings_repository.py   (MUDA)
#   a chave "rotation_degrees" deixa de ser lida e de ser gravada (arquivo antigo: ignorada em silêncio);
#   o resto da leitura tolerante (par resolução/cor, scan_preset de reserva, capture_mode, auto_crop) fica igual.
```

`file_system_document_draft_repository.py` **não muda** (a moldura é só manifesto, e `save_manifest` já usa `replace_file`).

### 5.3 `services/`

```python
# jpeg_reencoding.py   (NOVO; o que hoje é privado em image_adjustment_service.py, compartilhado)
ADJUSTED_JPEG_QUALITY = 95
TRANSPOSE_BY_ROTATION = {...}                                        # como hoje
def read_encoding_options(source: Image.Image) -> dict[str, Any]: ...  # qualidade 95, subamostragem, densidade e perfil
def replace_with(image: Image.Image, transformation: Callable[[Image.Image], Image.Image]) -> Image.Image: ...

# paper_edge_detection.py   (NOVO; funções puras sobre a prévia, sem I/O)
@dataclass(frozen=True)
class PaperEdges:
    left: float | None       # fração 0..1 da prévia; None = lado sem borda confiável
    top: float | None
    right: float | None
    bottom: float | None
def detect_paper_edges(preview: Image.Image) -> PaperEdges | None: ...   # 6.3

# page_crop_detection_service.py   (NOVO; síncrono)
class PageCropDetectionService:
    def detect_crop_to_apply(self, jpeg_content: bytes) -> PageCrop | None: ...    # só o estrito; usado pelo modo Rápido
    def detect_crop_to_suggest(self, jpeg_content: bytes) -> PageCrop | None: ...  # estrito, depois por lado; usado pelo Documento
# Ambos: decodificam uma prévia de no máximo 400 px (Image.draft + BOX), devolvem frações da imagem inteira com a
# margem de 1% (CROP_MARGIN_RATIO) já aplicada e None quando o resultado cobre a página toda. MemoryError ->
# ImageAdjustmentFailedError; imagem ilegível -> ScanFailedError (como hoje).

# image_adjustment_service.py   (MUDA)
class ImageAdjustmentService:
    def __init__(self, crop_detection_service: PageCropDetectionService) -> None: ...
    def adjust(self, jpeg_content: bytes, adjustment: ImageAdjustment) -> bytes: ...
# Só corta (destrutivo, modo Rápido): crop = detect_crop_to_apply(...); None -> os mesmos bytes; senão
# crop.to_pixel_region(tamanho), recorta e recodifica com read_encoding_options. Não gira mais.

# page_image_view_service.py   (NOVO)
class PageImageViewService:
    def build_view(self, jpeg_content: bytes, rotation: PageRotation, maximum_edge_pixels: int) -> bytes: ...
# Image.draft + thumbnail(maximum_edge_pixels) + transpose(rotation) + JPEG qualidade 85. Serve a miniatura girada
# (480), a visão ampliada (1600) e a miniatura do último arquivo do modo Rápido.
ENLARGED_VIEW_MAXIMUM_EDGE_PIXELS = 1600     # a prévia de 400 px da detecção é outra coisa (PREVIEW_MAXIMUM_EDGE_PIXELS)
VIEW_JPEG_QUALITY = 85

# document_page_view_service.py   (NOVO)
class DocumentPageViewService:
    def __init__(self, draft_store: DocumentDraftStore, image_view_service: PageImageViewService) -> None: ...
    def read_thumbnail(self, page_identifier: str, rotation: PageRotation) -> bytes | None: ...  # None se a página não existe
    def read_preview(self, page_identifier: str, rotation: PageRotation) -> bytes: ...           # usa DocumentDraftStore.read_page_content

# document_page_renderer.py   (NOVO; síncrono, só Pillow)
class DocumentPageRenderer:
    def render_jpeg(self, page_file: Path, framing: PageFraming) -> bytes: ...
# framing.needs_rendering falso -> page_file.read_bytes() (bytes do scanner intactos). Senão: abre, lê as opções,
# recorta na orientação do mestre (framing.crop_on_master().to_pixel_region(size)), gira, grava qualidade 95 com a
# mesma densidade. OSError, DecompressionBombError e ValueError -> ScanFailedError; MemoryError sobe (vira DocumentTooLargeError).

# rendered_page_source.py   (NOVO)
class RenderedPageSource:
    """O objeto com read() que o img2pdf chama quando chega à página: renderiza só então."""
    def __init__(self, page_renderer: DocumentPageRenderer, page_file: Path, framing: PageFraming) -> None: ...
    def read(self) -> bytes: ...            # OSError -> ScanFailedError (para nunca virar "pasta de saída indisponível")

# pdf_assembly_service.py   (MUDA)
class PageImageSource(Protocol):
    def read(self) -> bytes: ...
# write_pdf_at_embedded_resolutions(page_files, metadata, output_stream) é SUBSTITUÍDO por
def write_pdf_from_sources(self, page_sources: Sequence[PageImageSource], metadata: PdfDocumentMetadata,
                           output_stream: BinaryIO) -> None: ...    # mesmas opções, as fontes em vez de caminhos

# document_pdf_assembler.py   (NOVO)
class DocumentPdfAssembler:
    def __init__(self, page_renderer: DocumentPageRenderer, pdf_assembly_service: PdfAssemblyService) -> None: ...
    def write_pdf(self, assembly_input: DocumentAssemblyInput, metadata: PdfDocumentMetadata,
                  output_stream: BinaryIO) -> None: ...       # monta uma RenderedPageSource por página, na ordem do rascunho

# document_finalizer.py   (MUDA)
class DocumentFinalizer:
    def __init__(self, document_pdf_assembler: DocumentPdfAssembler, scan_output_repository: ScanOutputRepository,
                 storage_guard_service: StorageGuardService) -> None: ...
# ensure_capacity usa draft.estimated_document_size_in_bytes (D13). write_document passa o assembler no lugar do serviço.

# document_draft_store.py   (MUDA)
@dataclass(frozen=True)
class CapturedPage:
    jpeg_content: bytes; thumbnail_jpeg: bytes; scanned_at: datetime; settings: ScanSettings
    framing: PageFraming = UNFRAMED
# NOVO  turn_page_clockwise(self, page_identifier: str) -> DocumentDraft       # só manifesto
# NOVO  set_page_crop(self, page_identifier: str, crop: PageCrop | None) -> DocumentDraft   # igual -> sem salvar e sem revisão
# SAEM  replace_page, ensure_capacity_for_replacement, REPLACEMENT_SPACE_FACTOR
# ensure_capacity_for_page(settings) e describe_storage(settings) perdem o parâmetro adjustment (D13)

# document_page_capture.py   (MUDA)
class DocumentPageCapture:
    def __init__(self, scan_encoder: ScanEncoder, draft_store: DocumentDraftStore,
                 crop_detection_service: PageCropDetectionService) -> None: ...
# store(): codifica o mestre SEM ajuste (o request sem adjustment, via dataclasses.replace), e, se
# job.request.adjustment.auto_crop, framing = PageFraming(crop=detect_crop_to_suggest(mestre)); uma falha da detecção
# (DigitalizadoraError) vira aviso no log e framing sem moldura. ensure_capacity(request) não conta o ajuste.

# document_page_crop_detector.py   (NOVO; roda dentro de um _run_edit)
@dataclass(frozen=True)
class CropDetectionResult:
    draft: DocumentDraft
    crop_detected: bool
class DocumentPageCropDetector:
    def __init__(self, draft_store: DocumentDraftStore, crop_detection_service: PageCropDetectionService) -> None: ...
    def detect_for_page(self, page_identifier: str) -> CropDetectionResult: ...

# document_draft_service.py   (MUDA)
@dataclass(frozen=True)
class DocumentDraftCollaborators:
    draft_store: DocumentDraftStore
    page_scanner: Callable[[ScanRequest], Awaitable[DocumentPage]]
    finalizer: DocumentFinalizer
    page_cropper: DocumentPageCropDetector      # no lugar de page_rotator
    page_views: DocumentPageViewService
# rotate_page(page_identifier) -> DocumentDraft                       # _run_edit(store.turn_page_clockwise)
# set_page_crop(self, page_identifier: str, crop: PageCrop | None) -> DocumentDraft
# detect_page_crop(page_identifier) -> CropDetectionResult            # _run_edit(page_cropper.detect_for_page)
# read_thumbnail(self, page_identifier: str, rotation: PageRotation) -> bytes | None     # sem bloqueio
# read_preview(self, page_identifier: str, rotation: PageRotation) -> bytes              # sem bloqueio
# describe_draft_storage(settings) perde o parâmetro adjustment

# scan_content_rotator.py   (NOVO)
class ScanContentRotator:
    def rotate_clockwise(self, content: bytes, output_format: OutputFormat) -> bytes: ...
# JPEG: Pillow transpose ROTATE_270 + read_encoding_options (densidade mantida), replace_with para segurar duas imagens no máximo.
# PDF: pikepdf abre dos bytes, soma 90 ao /Rotate de cada página, salva em memória (os fluxos de imagem não são tocados).
# Erro de decodificação -> SavedScanUnreadableError; MemoryError -> ImageAdjustmentFailedError.

# scan_progress_tracker.py   (MUDA)
#   mark_completed passa a somar 1 a last_result_revision.
#   NOVO replace_last_scan(self, expected_result: ScanResult, replacement: StoredScan) -> None
#     só age se last_result for exatamente expected_result (uma digitalização nova no meio do giro vence); soma 1 a last_result_revision.

# last_scan_rotation_service.py   (NOVO)
@dataclass(frozen=True)
class LastScanRotators:
    content_rotator: ScanContentRotator
    image_view_service: PageImageViewService
class LastScanRotationService:
    def __init__(self, progress_tracker: ScanProgressTracker, scan_output_repository: ScanOutputRepository,
                 rotators: LastScanRotators) -> None: ...
    async def rotate_clockwise(self) -> ScanResult: ...
# 409 se há digitalização; NoLastScanError se não há; um asyncio.Lock serializa giros; o trabalho de disco roda em
# asyncio.to_thread; a troca do estado do tracker volta ao laço de eventos. 6.7.

# application_settings_service.py   (MUDA)
#   SettingsUpdate perde scan_preset e rotation_degrees; _resolve_scan_settings deixa de olhar predefinição;
#   _resolve_adjustment só trata auto_crop; saem _resolve_rotation e o import de PageRotation.

# storage_guard_service.py   (NÃO MUDA: o fator 2 por ajuste ativo continua valendo no modo Rápido)
```

### 5.4 `controllers/`

```python
# settings_controller.py: SettingsRequestBody perde scan_preset e rotation_degrees (Pydantic ignora as chaves extras).
# settings_body.py: build_settings_body sem scan_preset e sem rotation_degrees.

# scan_result_body.py   (NOVO)  def describe_scan_result(result: ScanResult) -> dict[str, Any]: ...   # tirado do StateController
# state_controller.py: usa describe_scan_result; ganha last_result_revision; _describe_document sem o ajuste.

# last_scan_controller.py   (NOVO)
class LastScanController:
    def __init__(self, last_scan_rotation_service: LastScanRotationService, error_message_catalog: ErrorMessageCatalog) -> None: ...
    def build_router(self) -> APIRouter: ...      # POST /api/scans/last/rotation
    async def rotate_last_scan(self) -> JSONResponse: ...
LAST_SCAN_ERROR_STATUSES = {"no_last_scan": 404, "scan_already_running": 409, "last_scan_file_missing": 409,
                            "saved_scan_unreadable": 409, "insufficient_storage": 507, "output_folder_unavailable": 503}

# document_body.py: _describe_page ganha "rotation_degrees" e "crop" (None ou as quatro chaves).

# document_controller.py   (MUDA; o construtor continua com 3 parâmetros)
class PageCropEdgesRequestBody(BaseModel):    left: StrictInt | StrictFloat; top: ...; right: ...; bottom: ...
class PageCropRequestBody(BaseModel):         crop: PageCropEdgesRequestBody | None
# rotas novas: PUT .../crop (set_page_crop), POST .../crop/detect (detect_page_crop), GET .../preview (read_preview);
# GET .../thumbnail ganha o parâmetro de consulta rotation_degrees (inteiro; padrão 0);
# DOCUMENT_ERROR_STATUSES ganha invalid_crop e invalid_page_rotation (422).

# application_factory.py: ApplicationControllers ganha last_scan; VALIDATION_ERROR_CODES_BY_PATH vira
# VALIDATION_ERROR_CODE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] (4.3).
```

### 5.5 Raiz de composição (`composition_root.py`)

`_SharedServices` ganha `crop_detection: PageCropDetectionService` e `image_view: PageImageViewService`; `ImageAdjustmentService(shared.crop_detection)`; `DocumentPageCapture(scan_encoder, draft_store, shared.crop_detection)`; `DocumentPageCropDetector`, `DocumentPageViewService`, `DocumentPdfAssembler(DocumentPageRenderer(), PdfAssemblyService())` e o `DocumentFinalizer` novo; `LastScanRotationService(progress_tracker, scan_output_repository, LastScanRotators(ScanContentRotator(), image_view))` e `LastScanController`. `DocumentPageRotator` sai. Nenhum outro módulo instancia concretos.

### 5.6 Simulador

Sem mudança obrigatória: `DIGITALIZADORA_SIMULATOR_LID_BACKGROUND` (tampa escura) já cobre o detector estrito. O cenário do livro (borda não uniforme) é coberto por duas digitalizações reais pequenas guardadas como fixtures (6.3, seção 8), sem acrescentar um modo ao simulador.

### 5.7 Interface (`web/static`)

```
index.html          MUDA  sai preset-select/preset-custom-option, rotation-select, rotation-document-hint; dica nova da caixa de corte;
                          entram <dialog id="page-frame-dialog"> (e seus controles), last-scan-rotate-button, last-scan-hint;
                          dois scripts novos antes de document-panel.js: page-frame-geometry.js e page-frame-editor.js
page-frame-geometry.js  NOVO  funções puras (6.9), sem DOM
page-frame-editor.js    NOVO  class PageFrameEditor: o dialog (ponteiro, teclado, status); decide nada, usa page-frame-geometry.js
scan-quality-policy.js  MUDA  saem CUSTOM_PRESET_VALUE, ROTATION_DEGREES, NO_ROTATION_DEGREES, choose_preset_option,
                              build_preset_changes, parse_rotation_degrees
scan-trigger-policy.js  MUDA  novo can_rotate_last_scan(scan_activity, rotation_activity)
document-page-policy.js MUDA  textos e regras novas (6.9); o comentário de decide_focus_after_action deixa de falar de "identificador novo"
document-panel.js       MUDA  tile com invólucro + moldura + Ampliar; miniatura por URL com rotation_degrees; liga o PageFrameEditor
application.js          MUDA  sem preset e giro; botão Girar ↻ do último arquivo; versão da miniatura = last_result_revision
application.css         MUDA  .page-thumbnail-frame, .page-crop-overlay, .frame-dialog, .frame-stage, .frame-box, .frame-handle
```

Constantes de módulo novas no JavaScript (nenhum número solto): `MINIMUM_FRAME_SIDE = 0.02`, `FINE_NUDGE_STEP = 0.005`, `COARSE_NUDGE_STEP = 0.05`, `FRAME_COMPARISON_TOLERANCE = 0.0005`, `FRAME_PRECISION_DIGITS = 4`.

## 6. Algoritmos

### 6.1 Giro do retângulo e a conversão para o mestre

Coordenadas da página exibida: `x` para a direita, `y` para baixo, ambos em 0..1. Girar a página 90° no sentido horário leva o ponto `(x, y)` para `(1 − y, x)` (confere: o canto superior esquerdo `(0, 0)` vai ao superior direito `(1, 0)`; o superior direito `(1, 0)` vai ao inferior direito `(1, 1)`). Um retângulo `(left, top, right, bottom)` vira:

```
turned_clockwise:         (left, top, right, bottom) -> (1 - bottom, left, 1 - top, right)
turned_counterclockwise:  (left, top, right, bottom) -> (top, 1 - right, bottom, 1 - left)      # a inversa
```

Os resultados passam por `PageCrop.rounded` (6 casas), para quatro giros voltarem exatamente ao início (`1 − (1 − 0.1)` dá `0.09999999999999998` em ponto flutuante). Vetores (também guardados em `tests/fixtures/page-crop-rotation-vectors.json`, lido pelos testes de Python **e** do Node, para as duas pontas concordarem):

| Retângulo | Girado 90° à direita |
|---|---|
| `(0.1, 0.2, 0.5, 0.9)` | `(0.1, 0.1, 0.8, 0.5)` |
| `(0, 0, 0.5, 1)` (metade esquerda) | `(0, 0, 1, 0.5)` (metade de cima) |
| `(0.2, 0.3, 0.7, 0.6)` | `(0.4, 0.2, 0.7, 0.7)` |
| `(0, 0, 1, 1)` | `(0, 0, 1, 1)` |

Quatro giros devolvem o retângulo original; `turned_counterclockwise` desfaz `turned_clockwise`.

**Conversão para o mestre.** A moldura está na orientação exibida; o mestre, na do scanner. Com `rotation = R` (quartos de volta `R / 90`), `crop_on_master()` aplica `turned_counterclockwise` `R / 90` vezes. `crop_from_master(master_crop)` faz o contrário (usado quando a detecção roda no mestre e o resultado é guardado na orientação exibida). Na hora de cortar, `to_pixel_region((largura, altura))` usa `floor(round(fração × tamanho, 6))` para esquerda e topo e `ceil(round(fração × tamanho, 6))` para direita e base (o `round` evita que `0.07 × 100 = 7.000000000000001` vire 8), limitados ao tamanho e com pelo menos 1 px.

**Recortar antes de girar.** O render corta o mestre na sua orientação (menor imagem primeiro) e só então gira a parte cortada; o resultado é o mesmo de girar e cortar, com menos pixels em memória.

### 6.2 Uma digitalização nova

Modo Rápido (inalterado): scanner → `ScanEncoder.encode` → `MasterJpegService` → `ImageAdjustmentService` (corte destrutivo só com `auto_crop`, por `detect_crop_to_apply`) → JPEG/PDF → pasta de saída. Não há giro na digitalização.

Modo Documento: scanner → `ScanEncoder.encode` com o pedido **sem ajuste** (o mestre é só o JPEG do scanner com a densidade, mais a miniatura) → se `auto_crop`, `detect_crop_to_suggest(mestre)` → `CapturedPage(framing=PageFraming(crop=…))` → `DocumentDraftStore.append_page`: arquivos primeiro e manifesto por último, como hoje (6.6.1 do outro spec). `rotation` nasce `NONE`. A página entra mesmo que a detecção falhe.

### 6.3 Detecção (calibrada nas digitalizações reais)

**Estrito** (`detect_paper_region`, inalterado): aceita só uma borda de vidro quase uniforme. Nas quatro digitalizações reais devolve `None` (NOTES.md).

**Por lado** (`detect_paper_edges`, novo; roda só no modo Documento, depois do estrito). Sobre a prévia em tons de cinza (no máximo 400 px):

1. **Perfil mediano por eixo.** Para as colunas, a mediana de cada coluna sobre as linhas de 25% a 75% da altura; para as linhas, a mediana de cada linha sobre as colunas de 25% a 75% da largura. A mediana (e não a média) ignora o texto, que ocupa uma minoria de cada coluna ou linha, e mostra a cor do papel ou do fundo. (Com a média, o topo do livro dava 0,212 em vez de 0,125, porque o título pesa na média.)
2. **Primeira borda a partir de fora, em cada lado.** Pula os 2% mais externos (a faixa escura do próprio vidro: o perfil de cima começa em 132 e sobe para 210 no primeiro pixel). Do lado de fora para dentro, em cada posição `i` até 35% do lado, compara a média de 3 pixels de dentro com a de 3 pixels de fora; a primeira posição cuja diferença absoluta chega a 12 níveis é a borda, refinada para a posição de maior diferença nos 6 pixels seguintes. "A primeira a partir de fora", e não "a mais forte", é o que evita confundir o texto do livro com a borda. Se nenhuma posição chega a 12 níveis, o lado fica sem borda (`None`).
3. **Aceitar só com pelo menos 2 lados** com borda; os lados sem borda ficam na borda do vidro (0 ou 1). Rejeitar (`None`) se a moldura ocupar menos de 20% da página, se algum lado ficar com menos de 2% (a moldura mínima) ou se cobrir a página toda. A margem de 1% do lado maior cresce a moldura para fora, como no estrito.

Constantes (nomeadas, em `paper_edge_detection.py`): `PROFILE_BAND_START_SHARE = 0.25`, `PROFILE_BAND_END_SHARE = 0.75`, `SKIPPED_BORDER_SHARE = 0.02`, `EDGE_SEARCH_REACH_SHARE = 0.35`, `EDGE_COMPARISON_WINDOW_PIXELS = 3`, `EDGE_STEP_LEVELS = 12`, `EDGE_REFINEMENT_PIXELS = 6`, `MINIMUM_DETECTED_SIDES = 2`, `MINIMUM_FRAME_AREA_SHARE = 0.20`.

**Resultado nas 4 digitalizações reais** (protótipo em `scratchpad/designer/proto3.py`; frações da imagem; verdade estimada no NOTES.md: esquerda 0,13, topo 0,125, direita 0,91, base 0,914):

| Imagem | Esquerda | Topo | Direita | Base |
|---|---|---|---|---|
| 1-color-100.jpg (850 × 1169) | sem borda | 0,125 | 0,914 | 0,915 |
| 2-gray-100.jpg | sem borda | 0,125 | 0,914 | 0,917 |
| 3-color-300.jpg (2550 × 3508) | sem borda | 0,125 | 0,907 | 0,915 |
| 4-color-150-photo.jpg | sem borda | 0,125 | 0,911 | 0,915 |

Com a margem de 1% a moldura sugerida fica perto de `(0, 0,115, 0,924, 0,925)`: três lados certos e a esquerda na borda do vidro, a 13% do livro, para você puxar. A esquerda é invisível por natureza: o livro é branco sobre um fundo estourado em branco. Duas dessas imagens (a de 100 dpi em cor e a em cinza, 95 KB e 87 KB) viram fixtures de teste (`tests/fixtures/real-scans/`) com tolerância de ±0,02 em cada lado e a esquerda em 0; uma página toda branca, uma página de texto com margens e uma página com tampa escura têm testes próprios (nada sai, nada sai, o estrito responde).

**Risco conhecido do detector por lado:** ele pode propor uma moldura que corta para dentro do conteúdo quando um fundo escuro e uma capa escura têm quase o mesmo nível (o caso da capa azul-marinho que o detector estrito recusa por segurança). Como no modo Documento a moldura é visível, escurece o que ficaria de fora e se ajusta, isso é aceitável ali; por isso o detector por lado **não** roda no modo Rápido (D4).

### 6.4 Salvar (finalizar) com moldura

`DocumentDraftService._write_document` não muda de forma: `ensure_capacity`, `verify_page_files`, marca de intenção, escrita, limpeza. O que muda é o que o `DocumentFinalizer` passa para o PDF: `DocumentPdfAssembler.write_pdf` monta, para cada página do rascunho, uma `RenderedPageSource(page_renderer, arquivo, page.framing)` e chama `PdfAssemblyService.write_pdf_from_sources`. O img2pdf percorre as fontes em ordem; para cada uma chama `read()`, que devolve o JPEG (bytes do scanner se não há giro nem moldura; senão o JPEG renderizado). Pico de memória por página renderizada: o mestre decodificado mais a parte cortada (medido: 950 MB a 1200 dpi para cortar e girar uma A4 inteira; 4 MB de saída). O PDF continua com uma página por foto, cada uma com a densidade do próprio JFIF (`default_layout_fun`): uma página cortada tem o tamanho físico da região cortada.

Erros: página ilegível ou sem memória no `read()` chegam como hoje (`ScanFailedError` → `DocumentAssemblyFailedError`; `MemoryError` → `DocumentTooLargeError`); o rascunho fica intacto e a marca de intenção sai.

### 6.5 Atomicidade das edições (giro e moldura)

Girar, mudar a moldura e detectar são **uma só gravação**: `DocumentDraftStore._save_and_replace` → `save_manifest` → `AtomicFileWriter.replace_file` (arquivo temporário no mesmo diretório, `fsync`, `os.replace`, `fsync` do diretório) e, depois, a troca do `DraftSnapshot` inteiro com `revision + 1`. Casos de queda: antes do `os.replace`, vale o manifesto anterior (e o `.part` é lixo que a recuperação apaga); depois, vale o novo. Não há arquivo de página, de miniatura nem identificador novos, então **nenhum caso de queda deixa página sem dono, miniatura incoerente ou tamanho divergente**; `reconcile_draft` não precisa mudar. A falha ao gravar o manifesto (`DigitalizadoraError`) mantém o snapshot anterior e é devolvida ao cliente (503 ou 507). O bloqueio (`_run_edit`) é o de sempre: 409 durante uma digitalização, espera as outras edições, uma de cada vez.

Gravar `rotation_degrees`/`crop` não mexe em `size_in_bytes`, então a conferência de tamanho da recuperação (`reconcile_draft`) e `verify_page_files` valem como antes.

### 6.6 Miniatura e visão ampliada

`DocumentPageViewService.read_thumbnail(page_identifier, rotation)`: `DocumentDraftStore.read_thumbnail` (membership + arquivo; `None` se não existe); `rotation` `NONE` devolve os bytes guardados; senão `PageImageViewService.build_view(miniatura, rotation, 480)`. `read_preview(page_identifier, rotation)`: `read_page_content` (membership, tamanho do manifesto, `DamagedDocumentPageError`), `build_view(mestre, rotation, 1600)`. Um mestre que sumiu entre a checagem e a leitura vira `PageNotFoundError`; um que não decodifica vira `DamagedDocumentPageError`. Nenhum bloqueio é tomado (o mestre nunca muda depois de gravado; a exclusão da página tira o arquivo, e a leitura em andamento termina com o arquivo já aberto ou erra como acima). Medições (JPEG sintético de 10200 × 14032, 143 MP): visão ampliada 0,11 s e 88 MB de pico.

### 6.7 Girar o último arquivo do modo Rápido

`LastScanRotationService.rotate_clockwise()`:

1. Se `ScanProgressTracker.snapshot().phase` não é `IDLE` → `ScanAlreadyRunningError` (409).
2. `last_result` é `None` → `NoLastScanError` (404).
3. Sob `asyncio.Lock` e em `asyncio.to_thread`: `read_saved_scan(caminho)` (`None` → `LastScanFileMissingError`); `ScanContentRotator.rotate_clockwise(conteúdo, formato)`; `replace_saved_scan(caminho, novo)` (atômico, mesmo nome; um disco cheio deixa o original intacto, porque o temporário é um arquivo à parte); a miniatura da última digitalização é girada por `build_view(miniatura, CLOCKWISE_90, 480)` (a miniatura do PDF é a mesma imagem pequena do mestre, então não é preciso rasterizar PDF).
4. De volta ao laço de eventos: `tracker.replace_last_scan(resultado_antigo, StoredScan(novo ScanResult com o tamanho novo, miniatura girada))`. Se uma digitalização nova terminou no meio, `replace_last_scan` não faz nada (o arquivo girado continua certo; só o painel não troca).

Cada giro de JPG recodifica uma vez (qualidade 95, subamostragem, densidade e perfil mantidos); o PDF só muda o `/Rotate` (os fluxos JPEG ficam como estão, sem perda). A 1200 dpi o JPG decodifica cerca de 430 MB e `replace_with` segura no máximo duas imagens (pico próximo de 1 GB, como o corte).

### 6.8 1200 dpi continua seguro

Limite de pixels (`MAXIMUM_SCANNER_IMAGE_PIXELS`) e esperas do scanner por resolução: inalterados. Decodificação reduzida (`Image.draft`) em miniatura, detecção e visão ampliada: inalterada ou nova pelo mesmo padrão. Salvar: no máximo uma página decodificada de cada vez (6.4); o giro do último arquivo JPG é a única operação que decodifica a página inteira fora do salvar, e segura duas imagens. Estimativa de espaço: o disco do rascunho conta só a página do scanner (D13); o salvar conta 2× nas páginas que precisam de renderização.

### 6.9 O módulo de geometria da moldura (`page-frame-geometry.js`)

Uma moldura é `{left, top, right, bottom}` em frações de 0 a 1 da página exibida. Todas as funções são puras e devolvem objetos novos:

```
clamp_fraction(value) -> number                       # limita a 0..1
build_frame(edges) -> frame                           # arredonda a FRAME_PRECISION_DIGITS
is_whole_page_frame(frame) -> boolean
frames_are_equal(first_frame, second_frame) -> boolean       # tolerância FRAME_COMPARISON_TOLERANCE
move_frame(frame, shift) -> frame                     # shift {delta_x, delta_y}; mantém o tamanho e fica dentro da página
resize_frame(frame, resize) -> frame                  # resize {handle, delta_x, delta_y}; só os eixos da alça;
                                                      #  cada borda limitada a 0..1 e a MINIMUM_FRAME_SIDE da borda oposta
nudge_handle(frame, nudge) -> frame                   # nudge {handle, direction, step}; direction: left|right|up|down
read_nudge_step(key_event) -> number                  # Shift: COARSE_NUDGE_STEP; senão FINE_NUDGE_STEP
turn_frame_clockwise(frame) -> frame                  # a fórmula de 6.1 (testada com os vetores compartilhados)
convert_pointer_shift(pointer_shift, box_size) -> {delta_x, delta_y}     # pixels do ponteiro / tamanho do palco
describe_frame_style(frame) -> {left_percent, top_percent, width_percent, height_percent}
describe_frame(frame) -> string                       # "Moldura: esquerda 13%, topo 12%, direita 91%, base 91%." ou "Sem corte: …"
read_frame_from_crop(crop) -> frame                   # null -> a página inteira
build_crop_request_body(frame) -> {crop: null | {left, top, right, bottom}}     # página inteira -> null
```

As alças: `north`, `north_east`, `east`, `south_east`, `south`, `south_west`, `west`, `north_west` (constantes `FRAME_HANDLES`). Alças de canto mexem nos dois eixos; as de borda, em um.

**Ponteiro:** `pointerdown` numa alça (ou no botão de mover) guarda a moldura inicial e a posição do ponteiro, chama `setPointerCapture`; `pointermove` calcula o deslocamento **acumulado desde o início** (nunca incremental, para não acumular erro de arredondamento) com `convert_pointer_shift` e redesenha a moldura de rascunho; `pointerup` e `pointercancel` soltam a captura e anunciam o estado. **Teclado:** `keydown` numa alça com seta chama `nudge_handle`; no botão de mover, `move_frame`; passo `read_nudge_step`; `preventDefault` para a página não rolar. **Foco visível:** `:focus-visible` com contorno de 3 px.

## 7. Compatibilidade

- **Manifesto antigo** (sem `rotation_degrees` nem `crop`) carrega como `0` e `null`; o `format_version` continua 1 e um programa antigo que leia um manifesto novo ignora as chaves novas (perde só a rotação e a moldura). Uma página girada pela versão anterior já é um arquivo girado: continua assim, com `rotation_degrees` 0.
- **Valor inválido** de `rotation_degrees` ou `crop` num manifesto **não** o torna ilegível (o resto do manifesto é lido com rigor, como antes): cai para o padrão da chave e deixa um aviso no log. Escolha deliberada: um manifesto ilegível põe o rascunho inteiro de lado; perder uma moldura custa um arrasto.
- **`settings.json` antigo** com `rotation_degrees` e/ou `scan_preset` carrega; a rotação é ignorada em silêncio; o `scan_preset` vale só como reserva do par resolução/cor, como hoje. O arquivo regravado não tem nenhuma das duas chaves.
- **Cliente antigo** (uma aba aberta de antes) que mande `scan_preset` ou `rotation_degrees` no `PUT /api/settings`: aceito e ignorado. Que peça `/thumbnail` sem parâmetro: recebe a miniatura sem giro (a página antiga não girava por metadado).
- **Rascunho em andamento no momento da atualização:** continua válido; as páginas ficam sem moldura.
- **Simulador, `make`, README:** sem mudança de uso.

## 8. Testes: o que muda e o que entra

**Existentes que precisam mudar** (lista exata, por arquivo; todos os outros continuam como estão):

- `tests/domain/test_image_adjustment.py`: apagar `test_a_rotation_alone_is_active` e `test_a_rotation_with_a_crop_is_active`; editar `test_the_default_adjustment_changes_nothing`, `test_an_automatic_crop_alone_is_active` e `test_the_adjustment_is_immutable` para a classe sem `rotation`.
- `tests/domain/test_application_settings.py`: `test_to_scan_request_carries_the_adjustment` (sem rotação).
- `tests/domain/test_scan_preset.py`: apagar `test_matching_finds_the_preset_of_its_own_settings`, `test_matching_is_none_for_a_resolution_no_preset_uses` e `test_matching_is_none_for_a_known_resolution_with_another_colour_mode`; os outros dois ficam.
- `tests/domain/test_document_draft.py`: apagar os cinco `test_with_page_replaced_*` (`keeps_the_position`, `swaps_the_page_details`, `of_an_unknown_page_raises`, `clears_both_finalization_markers`, `keeps_the_name_and_creation_moment`); os equivalentes passam a ser os de `with_page_framing`.
- `tests/domain/test_immutable_models.py`: acrescentar `PageCrop`, `PageFraming`; ajustar a construção de `ImageAdjustment`.
- `tests/repositories/test_document_manifest_codec.py`: `test_unknown_keys_are_ignored` e os testes de ida e volta (acrescentar os dois campos); os de manifesto estrito ficam.
- `tests/repositories/test_json_application_settings_repository.py`: `test_save_writes_the_documented_json_shape` (sem `rotation_degrees`), `test_adjusted_settings_are_loaded_back_equal`, `test_old_document_gets_no_adjustment`; apagar `test_an_invalid_rotation_is_read_as_no_rotation_keeping_the_other_fields`, `test_a_changed_invalid_rotation_is_reported_again` e `test_a_missing_rotation_and_auto_crop_are_not_reported_as_problems` (reescrito só para o `auto_crop`); entra "uma chave `rotation_degrees` antiga é ignorada sem aviso".
- `tests/repositories/test_file_system_scan_output_repository.py`: sem apagar nada; entram os testes de `read_saved_scan` e `replace_saved_scan`.
- `tests/services/test_image_adjustment_service.py`: apagar `test_the_rotation_turns_the_page_clockwise`, `test_a_quarter_turn_swaps_the_dimensions`, `test_four_clockwise_quarter_turns_bring_the_page_back`, `test_a_page_without_a_sheet_is_still_rotated_when_the_crop_finds_nothing`, `test_the_crop_happens_before_the_rotation`; o construtor passa a receber o serviço de detecção em todos os outros.
- `tests/services/test_master_jpeg_service.py`: `test_the_requested_density_is_written_after_a_rotation` vira "…after a crop"; `test_the_adjustment_of_the_request_is_applied` (só corte).
- `tests/services/test_scan_encoder.py`: apagar `test_the_rotation_reaches_the_jpeg_output`, `test_the_rotation_reaches_the_thumbnail`, `test_the_rotation_reaches_the_pdf`; `test_the_density_is_written_after_the_rotation` vira "after the crop".
- `tests/services/test_storage_guard_service.py`: `test_an_active_rotation_doubles_the_estimated_page_size` apagado (o corte ativo continua dobrando: `test_an_active_crop_doubles_the_estimated_page_size`); `test_fewer_pages_remain_when_an_adjustment_is_active` com `ImageAdjustment(auto_crop=True)`.
- `tests/services/test_application_settings_service.py`: apagar `test_update_rejects_an_unknown_scan_preset`, `test_a_preset_alone_sets_both_quality_values`, `test_the_pair_wins_over_the_old_preset_the_page_sent_back`, `test_a_resolution_wins_over_the_preset_and_keeps_the_saved_colour_not_the_preset_colour`, `test_an_unknown_preset_is_refused_even_with_a_valid_resolution`, `test_a_rotation_is_saved_and_the_crop_is_kept`, `test_a_rotation_of_zero_degrees_turns_the_rotation_off`, `test_a_rotation_outside_the_four_quarters_is_refused`; editar `test_update_accepts_every_known_format_and_preset` (só formatos), `test_update_without_adjustment_fields_keeps_the_saved_adjustment`, `test_a_crop_choice_is_saved_and_the_rotation_is_kept` (vira "…is saved"), `test_a_refused_quality_or_adjustment_saves_nothing`.
- `tests/services/test_application_state_service.py`: `test_state_estimates_pages_for_the_selected_preset` e `test_a_heavier_preset_leaves_fewer_estimated_pages` só trocam o nome (sem predefinição); a conta do modo Rápido não muda.
- `tests/services/test_document_draft_store.py`: apagar os cinco `test_capacity_for_a_replacement_*`, os catorze `test_replace_page_*` (de `test_replace_page_puts_a_new_identifier_at_the_same_position` a `test_replace_page_without_a_draft_raises_no_open_document`), `test_capacity_check_counts_the_adjustment_of_the_page`, `test_capacity_check_without_adjustment_accepts_exactly_enough_space` (vira "…accepts exactly enough space"), `test_describe_storage_estimates_fewer_pages_when_the_pages_are_adjusted`; entram os de `turn_page_clockwise` e `set_page_crop` (mesmos oito cenários de falha e de snapshot dos de `rename`).
- `tests/services/test_document_page_replacement_recovery.py`: **apagado**; vira `tests/services/test_document_page_framing_recovery.py` (queda antes e depois do `os.replace` do manifesto na rotação e na moldura).
- `tests/services/test_document_draft_recovery.py`: `test_failed_recovery_blocks_replacements_with_draft_storage_unavailable` vira "…blocks new pages" (só `ensure_capacity_for_page`).
- `tests/services/test_document_draft_service.py`: `test_rotate_page_gives_the_page_a_new_identifier_at_the_same_position` (agora: mantém o identificador e a posição), `test_rotate_page_replaces_the_snapshot` (a revisão sobe), `test_rotate_page_swaps_the_dimensions_of_the_stored_page` (agora: o arquivo da página fica idêntico), `test_a_rotated_page_goes_into_the_saved_pdf_with_its_new_orientation` (continua verdadeiro, pelo render), `test_describe_draft_storage_counts_the_adjustment` apagado, `test_add_page_passes_the_adjustment_to_the_page_scanner` e `test_add_page_without_adjustment_asks_for_no_adjustment` ficam; `test_read_thumbnail_returns_the_thumbnail_of_the_page` com o giro.
- `tests/services/test_document_page_capture.py`: `test_ensure_capacity_counts_the_adjustment_of_the_request` (agora: não conta); construtor com o terceiro colaborador; entram os de moldura detectada.
- `tests/services/test_document_page_rotator.py`: **apagado** (8 testes).
- `tests/services/test_document_finalizer.py`: o primeiro colaborador passa a ser o `DocumentPdfAssembler`; `test_pdf_keeps_the_order_of_the_page_files`, `test_unreadable_page_raises_document_assembly_failed`, `test_unreadable_page_leaves_no_file_in_the_output_folder`, `test_memory_error_while_assembling_raises_document_too_large`, `test_ensure_capacity_accepts_the_minimum_plus_the_draft_size_in_the_output_folder` e `…one_byte_short…` (agora com `estimated_document_size_in_bytes`).
- `tests/services/test_pdf_assembly_service.py`: os sete `test_streamed_*` e `test_page_file_that_is_not_an_image_raises_scan_failed` trocam `write_pdf_at_embedded_resolutions(paths…)` por `write_pdf_from_sources(fontes…)`.
- `tests/services/test_scan_progress_tracker.py`: acrescentar `last_result_revision` e `replace_last_scan`; `test_a_new_thumbnail_replaces_the_previous_one` fica.
- `tests/fakes/document_service_parts.py`, `tests/fakes/stub_document_draft_service.py`, `tests/fakes/document_drafts.py`, `tests/fakes/stored_scans.py`: construção sem `DocumentPageRotator`, com os colaboradores novos e métodos novos no stub.
- `tests/controllers/test_settings_controller.py`: `test_get_settings_returns_the_saved_settings`, `test_put_settings_returns_the_new_settings`, `test_put_settings_without_a_preset_or_quality_keeps_the_saved_quality`, `test_put_settings_saves_the_new_settings`, `test_a_rejected_put_leaves_the_saved_settings_untouched` (sem `scan_preset`/`rotation_degrees`); apagar `test_put_settings_reports_no_preset_for_a_custom_combination`, `test_put_settings_reports_the_preset_a_combination_matches`, `test_the_page_may_send_a_preset_with_null_quality_fields`; `test_put_settings_saves_the_rotation_and_the_crop` vira só corte; `test_put_settings_with_an_invalid_quality_or_rotation_answers_422` só qualidade; entra "um cliente antigo que manda `scan_preset` e `rotation_degrees` é aceito e eles são ignorados".
- `tests/controllers/test_state_controller.py`: `test_state_contains_the_settings`, `test_state_estimates_the_draft_storage_with_the_saved_quality_and_adjustment` (só qualidade); entra `last_result_revision`.
- `tests/controllers/test_document_controller.py`: os quatro `test_rotate_page_*` ficam com o novo retorno; `test_rotation_failing_for_lack_of_memory_says_to_choose_a_lower_resolution` apagado (a rotação não usa mais memória); `test_rotation_is_a_post_only_route` fica; `test_thumbnail_is_served_as_jpeg`, `test_thumbnail_may_be_cached_forever`, `test_missing_thumbnail_answers_404_without_a_body` com o parâmetro de giro; `test_post_pages_adds_a_page_with_the_saved_quality_and_adjustment` fica.
- `tests/controllers/test_document_body.py`: `test_document_describes_the_draft_and_its_pages_in_order` e `test_document_keys_come_in_the_documented_order` com os dois campos.
- `tests/controllers/test_application_factory.py`: `ApplicationControllers` com o campo novo; entram os padrões de validação.
- `tests/controllers/test_error_message_catalog.py`: o catálogo ganha cinco códigos e o texto de `image_adjustment_failed` muda (os testes que listam os códigos).
- `tests/test_composition_root.py`: `test_state_endpoint_reports_default_settings` (sem os dois campos); `test_an_old_settings_file_with_only_a_preset_is_served_with_the_quality_of_the_preset` (sem `scan_preset` na resposta).
- `tests/integration/test_adjustments_flow.py`: **reescrito** (nome novo `test_frame_and_rotation_flow.py`): saem `test_quick_scan_with_a_quarter_turn_swaps_the_dimensions`, `test_quick_scan_with_a_half_turn_keeps_the_dimensions`, `test_document_page_with_a_quarter_turn_swaps_the_dimensions`, `test_rotating_a_page_of_the_draft_answers_it_under_a_new_identifier`, `test_rotating_a_page_of_the_draft_swaps_its_dimensions`, `test_a_page_rotated_in_the_draft_is_saved_turned_in_the_pdf` (agora: pelo render), `test_the_saved_adjustments_are_served_back_after_a_scan` (sem rotação) e `test_document_page_against_the_dark_lid_is_cropped` (agora: vira moldura, mestre intacto); ficam os do modo Rápido sem giro.
- `tests/integration/test_document_flow.py`: `test_page_scanned_by_the_fake_printer_appears_in_the_document` (campos novos).
- `tests/hardware/test_real_printer.py`: `test_capabilities_offer_every_preset_resolution` só troca "preset" no nome.
- `tests/web/` (Node): `document-panel-harness.js`, `scan-page-harness.js`, `fake-browser.js` (lista de scripts e ids), `test_static_assets.py` (`SCRIPT_FILE_NAMES`, `SETTINGS_ELEMENT_IDENTIFIERS`, `DOCUMENT_ELEMENT_IDENTIFIERS`; apagar `test_rotation_list_offers_the_four_turns`, `test_preset_list_ends_with_the_custom_option_that_cannot_be_chosen`, `test_preset_options_of_the_page_match_the_presets_of_the_server`; `test_page_offers_every_format_preset_and_mode` sem preset; `test_auto_crop_label_names_the_background_removal` e a dica nova), `test_scan_quality_policy.py` (apagar `test_preset_choice_rules` e `test_rotation_choice_rules`), `test_scan_page_behaviour.py` (apagar `test_a_rotation_value_that_is_not_an_angle_is_sent_as_no_rotation`, `test_a_named_preset_hides_the_custom_option`, `test_a_custom_combination_selects_the_custom_option`, `test_a_server_without_the_new_settings_leaves_rotation_and_crop_off` e `test_rotation_hint_for_the_document_mode_is_hidden_in_quick_mode`; `test_saved_settings_fill_the_rotation_and_crop_controls` e `test_saved_rotation_and_crop_fill_their_controls` só o corte), `test_document_panel_behaviour.py` (apagar `test_rotation_hint_is_shown_in_document_mode`; `test_tile_has_a_rotate_button_with_its_own_style_class` fica), `test_document_panel_keyboard.py` (apagar `test_enter_on_the_rotation_select_opens_no_confirmation`), `test_document_panel_edits.py` (`test_rotated_page_keeps_its_position_with_the_new_identifier` → "keeps its tile"; `test_rotated_page_shows_the_new_thumbnail` → "uses the rotation in the thumbnail address"; `test_rotate_without_enough_memory_*` apagados; os demais `test_rotate_*` ficam), `test_document_page_policy.py` (o texto de `describe_page_rotation` e `decide_focus_after_action` para `rotate` sem "identificador novo").

**Testes novos** (um conceito por teste, cada um abaixo de 100 ms, escritos antes do código):

- `PageCrop`: validação (fora de 0..1, `right <= left`, lado menor que 2%, `NaN`); arredondamento; os quatro vetores de 6.1 nos dois sentidos; quatro giros voltam ao início; `to_pixel_region` com os casos de `floor`/`ceil` (`0.07 × 100`); `from_pixel_region` ida e volta.
- `PageFraming`: giro soma 90 e gira a moldura; moldura da página inteira vira `None`; `crop_on_master` e `crop_from_master` são inversas para as quatro rotações; `needs_rendering`.
- `DocumentDraft.with_page_framing` (posição, página desconhecida, marcas de finalização) e `estimated_document_size_in_bytes`.
- Manifesto: ida e volta com e sem moldura; manifesto antigo; valor inválido cai no padrão com aviso.
- Detecção por lado: as duas digitalizações reais (cores e cinza); nada em página branca; nada em página de texto com margens; o estrito vence quando a tampa é escura; falha de uma só borda recusada (menos de 2 lados); área mínima; `detect_crop_to_apply` não usa o detector por lado.
- `DocumentPageRenderer`: sem giro nem moldura devolve os bytes do arquivo; só giro troca as dimensões e mantém a densidade; só moldura tem o tamanho da região; giro e moldura juntos cortam na orientação do mestre; o JPEG renderizado conserva a densidade; `MemoryError` sobe; imagem ilegível vira `ScanFailedError`.
- PDF: uma página com moldura tem o tamanho físico da região (pontos = pixels / densidade × 72); uma página sem ajuste é embutida sem recompressão (o teste que já existe, agora pela fonte); só uma página fica decodificada de cada vez (fonte que registra a ordem de `read()` e a de liberação).
- Capture: com `auto_crop` o `CapturedPage` leva a moldura e o mestre sai com os bytes do scanner (densidade à parte); falha da detecção não impede a página; sem `auto_crop` não chama a detecção.
- `DocumentPageCropDetector`: acha e guarda (já na orientação exibida, com a página girada); não acha e não muda; página danificada.
- `DocumentDraftService`: `set_page_crop` e `rotate_page` seguem as regras de 409 e de revisão; moldura igual não sobe a revisão.
- Controladores: as rotas novas, os códigos de 4.3, o corpo malformado (`invalid_crop`, `invalid_page_rotation`), os cabeçalhos de cache, o `crop_detected`.
- Último arquivo do Rápido: JPG gira e muda as dimensões e mantém a densidade; PDF só muda `/Rotate` e o fluxo da imagem fica idêntico; 404, 409 e arquivo ausente; a substituição é atômica (falha ao escrever deixa o original); a miniatura gira; `replace_last_scan` ignora quando já há outra digitalização; dois giros seguidos somam 180°.
- Integração com o simulador (HOME temporário e outra porta): modo Documento com tampa escura e `auto_crop` → moldura na página, mestre inalterado byte a byte, salvar → PDF com a página do tamanho da região; giro por metadado; queda simulada (matar o servidor depois da edição) → o rascunho volta com a moldura e a rotação; modo Rápido: digitalizar, girar JPG e PDF.
- JavaScript (Node): geometria completa (limites, tamanho mínimo, cada alça, empurrar com e sem Shift, giro com os vetores compartilhados, porcentagens, de e para frações, descrições em português); tile (invólucro, moldura aparece e some, miniatura recarrega com `rotation_degrees`, `Ampliar` presente e na ordem do Tab); dialog (abrir, arrastar, empurrar, Aplicar envia `PUT`, Sem corte envia `null`, Detectar, Girar mantém o rascunho, Cancelar descarta, Esc, foco de volta, página sumida fecha, teclas globais inertes, Espaço nunca digitaliza); botão Girar do último arquivo.

## 9. Tarefas

Cada tarefa é feita por TDD (teste vermelho, código, teste verde), termina com `ruff check src tests` limpo e **um commit local** (nunca `git push`; nunca `md.md`). A ordem é a das dependências: servidor primeiro, depois a interface.

### T32: A moldura em frações (`PageCrop`)
**Arquivos:** `src/digitalizadora/domain/page_crop.py` (novo), `domain/errors.py` (+`InvalidCropError`, `InvalidPageRotationError`), `tests/domain/test_page_crop.py` (novo), `tests/fixtures/page-crop-rotation-vectors.json` (novo).
**Interfaces:** `PageCrop` (5.1), `PageCrop.rounded`, `WHOLE_PAGE`, `turned_clockwise`, `turned_counterclockwise`, `to_pixel_region`, `from_pixel_region`. Sem dependência de outras tarefas.

### T33: O enquadramento da página no rascunho
**Arquivos:** `domain/page_framing.py` (novo), `domain/document_draft.py`, `tests/domain/test_page_framing.py` (novo), `tests/domain/test_document_draft.py`, `tests/domain/test_immutable_models.py`, `tests/fakes/document_drafts.py`.
**Interfaces:** `PageFraming`, `UNFRAMED`, `DocumentPage.framing`, `DocumentDraft.with_page_framing`, `estimated_document_size_in_bytes`; sai `with_page_replaced`. Depende de T32.

### T34: Manifesto e corpo do documento com giro e moldura
**Arquivos:** `repositories/document_manifest_codec.py`, `controllers/document_body.py`, `tests/repositories/test_document_manifest_codec.py`, `tests/controllers/test_document_body.py`.
**Interfaces:** chaves `rotation_degrees` e `crop` (5.2 e 4.2); leitura tolerante dos dois campos. Depende de T33.

### T35: Girar e enquadrar são edições só do manifesto (sai a regravação)
**Arquivos:** `services/document_draft_store.py` (`turn_page_clockwise`, `set_page_crop`; saem `replace_page`, `ensure_capacity_for_replacement`, `REPLACEMENT_SPACE_FACTOR`), `services/document_draft_service.py` (`rotate_page` e `set_page_crop` pelo store), **apagar** `services/document_page_rotator.py` e `tests/services/test_document_page_rotator.py` e `tests/services/test_document_page_replacement_recovery.py`, `composition_root.py`, `tests/fakes/document_service_parts.py`, `tests/fakes/stub_document_draft_service.py`, `tests/services/test_document_draft_store.py`, `tests/services/test_document_draft_service.py`, `tests/services/test_document_draft_recovery.py`, `tests/services/test_document_page_framing_recovery.py` (novo).
**Interfaces:** `DocumentDraftStore.turn_page_clockwise(page_identifier)`, `set_page_crop(page_identifier, crop)`; `DocumentDraftCollaborators` sem `page_rotator` (os campos novos entram nas tarefas seguintes). Até T40 o PDF ainda sai com os mestres sem giro: esta tarefa e T39 são commitadas em sequência e T39 vem logo depois. Depende de T33 e T34.

### T36: Tirar o giro e a predefinição das configurações e do pipeline de digitalização
**Arquivos:** `domain/image_adjustment.py` (sem `rotation`), `domain/scan_preset.py` (sem `matching`), `services/application_settings_service.py`, `services/image_adjustment_service.py` (só corta, ainda com a detecção estrita atual), `repositories/json_application_settings_repository.py`, `controllers/settings_controller.py`, `controllers/settings_body.py`, `controllers/error_message_catalog.py` (texto de `image_adjustment_failed`), e os testes de 8 (domain, repositórios, services de ajuste, encoder, master, storage guard, controllers de configurações e estado, `test_composition_root.py`).
**Interfaces:** `ImageAdjustment(auto_crop)`, `SettingsUpdate` sem `scan_preset` e `rotation_degrees`, corpo de configurações de 4.1. Depende de T35 (nada mais usa `ImageAdjustment.rotation` depois dela).

### T37: Detecção por lado e serviço de detecção de moldura
**Arquivos:** `services/paper_edge_detection.py` (novo), `services/page_crop_detection_service.py` (novo), `services/jpeg_reencoding.py` (novo, extraído de `image_adjustment_service.py`), `services/image_adjustment_service.py` (recebe o serviço de detecção por construtor), `composition_root.py`, `tests/services/test_paper_edge_detection.py` (novo), `tests/services/test_page_crop_detection_service.py` (novo), `tests/fixtures/real-scans/book-on-glass-100-dpi-color.jpg` e `…-gray.jpg` (cópias de `1-color-100.jpg` e `2-gray-100.jpg`), `tests/services/test_image_adjustment_service.py`, `tests/services/test_paper_region_detection.py` (sem mudança de comportamento).
**Interfaces:** `PaperEdges`, `detect_paper_edges`, `PageCropDetectionService.detect_crop_to_apply` e `detect_crop_to_suggest`, constantes de 6.3. Depende de T32 e T36.

### T38: Miniatura girada e visão ampliada (servidor)
**Arquivos:** `services/page_image_view_service.py` (novo), `services/document_page_view_service.py` (novo), `services/document_draft_service.py` (`read_thumbnail(page_identifier, rotation)`, `read_preview(page_identifier, rotation)`, `page_views` nos colaboradores), `composition_root.py`, testes novos de cada serviço e do `DocumentDraftService`, `tests/fakes/stub_document_draft_service.py`.
**Interfaces:** `PageImageViewService.build_view`, `DocumentPageViewService`, constante `ENLARGED_VIEW_MAXIMUM_EDGE_PIXELS = 1600`. Depende de T35.

### T39: Renderizar com giro e moldura ao salvar
**Arquivos:** `services/document_page_renderer.py` (novo), `services/rendered_page_source.py` (novo), `services/document_pdf_assembler.py` (novo), `services/pdf_assembly_service.py` (`write_pdf_from_sources`; sai `write_pdf_at_embedded_resolutions`), `services/document_finalizer.py`, `composition_root.py`, `tests/fakes/document_service_parts.py` e os testes de 8 (finalizer, PDF, renderer, assembler, serviço do rascunho).
**Interfaces:** 5.3. Depende de T33, T35 e T37 (reutiliza `jpeg_reencoding`).

### T40: A moldura nasce na digitalização e a detecção pode ser repetida
**Arquivos:** `services/document_page_capture.py` (terceiro colaborador, mestre sem ajuste), `services/document_page_crop_detector.py` (novo), `services/document_draft_store.py` (`CapturedPage.framing`; `ensure_capacity_for_page(settings)` e `describe_storage(settings)` sem ajuste), `services/document_draft_service.py` (`detect_page_crop`, `page_cropper`, `describe_draft_storage(settings)`), `controllers/state_controller.py` (sem o ajuste no estado do rascunho), `composition_root.py`, testes de 8.
**Interfaces:** `CropDetectionResult`, `DocumentPageCropDetector.detect_for_page`. Depende de T35, T37 e T39.

### T41: Rotas do documento: moldura, detecção, ampliação e miniatura girada
**Arquivos:** `controllers/document_controller.py`, `application_factory.py` (`VALIDATION_ERROR_CODE_PATTERNS`), `controllers/error_message_catalog.py` (`invalid_crop`, `invalid_page_rotation`), `tests/controllers/test_document_controller.py`, `tests/controllers/test_application_factory.py`, `tests/controllers/test_error_message_catalog.py`.
**Interfaces:** 4.3. Depende de T38 e T40.

### T42: Girar o último arquivo do modo Rápido (servidor)
**Arquivos:** `domain/scan_progress.py` (`last_result_revision`), `services/scan_progress_tracker.py` (`replace_last_scan`), `domain/ports.py` e `repositories/file_system_scan_output_repository.py` (`read_saved_scan`, `replace_saved_scan`), `services/scan_content_rotator.py` (novo), `services/last_scan_rotation_service.py` (novo), `controllers/scan_result_body.py` (novo), `controllers/last_scan_controller.py` (novo), `controllers/state_controller.py`, `application_factory.py` (campo `last_scan`), `controllers/error_message_catalog.py`, `composition_root.py`, testes novos de cada peça.
**Interfaces:** 4.4, 5.3 e 5.4. Depende de T38 (`PageImageViewService`).

### T43: Integração com o simulador
**Arquivos:** `tests/integration/test_frame_and_rotation_flow.py` (substitui `test_adjustments_flow.py`), `tests/integration/test_document_flow.py`, `tests/integration/test_scan_flow.py` (acréscimo do giro do último arquivo).
**Cenários:** os de 8 ("Integração com o simulador"). Depende de T41 e T42.

### T44: Geometria da moldura (JavaScript puro)
**Arquivos:** `web/static/page-frame-geometry.js` (novo), `tests/web/document-page-policy-harness.js` (carrega o módulo novo), `tests/web/test_page_frame_geometry.py` (novo), `tests/web/test_static_assets.py` e `tests/web/fake-browser.js` (a lista de scripts).
**Interfaces:** 6.9; os vetores compartilhados de `tests/fixtures/page-crop-rotation-vectors.json`. Independente do servidor (pode ser feita em paralelo a T35 em diante).

### T45: Ajustes sem Predefinição e sem Girar
**Arquivos:** `web/static/index.html`, `web/static/application.js`, `web/static/scan-quality-policy.js`, `tests/web/scan-page-harness.js`, `tests/web/test_scan_page_behaviour.py`, `tests/web/test_scan_quality_policy.py`, `tests/web/test_static_assets.py`.
**Interfaces:** a caixa Ajustes de 3, a dica nova do corte. Depende de T36.

### T46: A moldura na miniatura, "Ampliar" e a miniatura girada
**Arquivos:** `web/static/document-panel.js`, `web/static/document-page-policy.js`, `web/static/application.css`, `tests/web/document-panel-harness.js`, `tests/web/test_document_panel_behaviour.py`, `tests/web/test_document_panel_edits.py`, `tests/web/test_document_page_policy.py`.
**Interfaces:** tile com `page-thumbnail-frame`, `page-crop-overlay` (`describe_frame_style`), botão **Ampliar** (linha 3), URL da miniatura com `rotation_degrees`, foco de rotação por posição. Depende de T41 e T44.

### T47: O editor da moldura (dialog de ampliação)
**Arquivos:** `web/static/page-frame-editor.js` (novo), `web/static/index.html` (`page-frame-dialog`), `web/static/document-panel.js` (liga o editor; `is_confirmation_open()` inclui o dialog), `web/static/document-page-policy.js` (textos), `web/static/application.css`, `tests/web/document-panel-harness.js`, `tests/web/fake-browser.js` (eventos de ponteiro e `setPointerCapture`), `tests/web/test_page_frame_editor_behaviour.py` (novo).
**Interfaces:** 3 (visão ampliada) e 6.9 (ponteiro e teclado). Depende de T46.

### T48: Girar o último arquivo no modo Rápido (interface)
**Arquivos:** `web/static/index.html`, `web/static/application.js`, `web/static/scan-trigger-policy.js`, `web/static/application.css`, `tests/web/scan-page-harness.js`, `tests/web/test_scan_page_behaviour.py`.
**Interfaces:** `last-scan-rotate-button`, `can_rotate_last_scan`, versão da miniatura por `last_result_revision`. Depende de T42 e T45.

### T49: Documentação
**Arquivos:** `README.md` (moldura, Ampliar, giro só na página, modo Rápido x Documento), `docs/acceptance-checklist.md` (partes novas: moldura e giro no simulador e na impressora), este documento (status "implementado"). Depende de T47 e T48.

### T50: Aceitação na impressora real, com o livro no vidro (só o agente a quem isso foi pedido; uma digitalização por vez)
Aplicativo novo numa porta livre, `HOME` temporário, a impressora real. Roteiro, anotando tempo e resultado de cada passo (a mesma folha de capa do livro, tampa aberta):

1. **Rápido, 300 dpi cor, PDF, sem corte:** uma digitalização; girar ↻ uma vez no painel; conferir que o PDF tem `/Rotate` 90 e que a imagem embutida é a mesma; girar de novo (180°); mesmo teste em JPG (dimensões trocadas, densidade 300 mantida, nome igual).
2. **Rápido com corte ligado:** a capa do livro tem borda não uniforme; esperado: o estrito não acha e a imagem fica inteira (anotar). Repetir com uma folha menor sobre fundo escuro, se houver.
3. **Documento, 300 dpi cor, corte ligado:** página 1 (o livro): esperado moldura perto de `(0, 0,115, 0,924, 0,925)`; conferir a sobreposição na miniatura, abrir **Ampliar**, puxar a borda esquerda para cerca de 0,13 por arrasto e por teclado, **Aplicar**; **Girar ↻** na miniatura (a moldura acompanha) e no dialog; **Detectar automaticamente**; **Sem corte**; **Cancelar** descarta.
4. **Documento, corte desligado:** página 2: sem moldura; desenhar uma à mão e aplicar; reordenar, mover para, excluir e descartar a última; nome do documento.
5. **Salvar (Enter):** o PDF tem as páginas na ordem; a 1 do tamanho físico da região (pontos = pixels ÷ 300 × 72 ± 1); a 2 conforme a moldura desenhada; a girada na orientação certa; o arquivo do mestre no rascunho continua com o tamanho do manifesto (comparar o hash antes e depois das edições).
6. **Resoluções:** o mesmo livro a 100 e a 300 dpi: as molduras detectadas coincidem em ±0,01 (frações); 75, 150, 200, 400 e 600 dpi pelo menos uma página cada (600 leva cerca de 75 s); 1200 dpi só se for pedido (vários minutos): conferir tempo, pico de memória e que a visão ampliada abre rápido.
7. **Segurança contra queda:** depois de uma moldura e uma rotação, `kill -9` no servidor, abrir de novo: o rascunho volta com as duas; um `.part` fica? (não deve).
8. **409:** durante uma digitalização, giro, moldura, detecção e girar o último arquivo respondem 409; a visão ampliada continua abrindo.
9. **Salvar pasta**, **Cancelar documento** e cada rota nova com o cabeçalho ausente (recusada).
Anotar tudo (tempo por passo, frações detectadas, tamanhos) para ajustar as constantes de 6.3 se a moldura sugerida estiver ruim.

## 10. Riscos e pontos em aberto

- **A esquerda do livro.** Branco sobre branco não tem borda a achar; a moldura sugerida deixa essa borda no vidro e o texto do dialog e a dica explicam. Se quiser uma heurística (por exemplo, simetria com a margem direita), ela entra depois de a aceitação mostrar que vale a pena.
- **Constantes do detector por lado** vieram de quatro digitalizações do mesmo livro. T50 as confirma ou ajusta com outra capa e com uma folha comum.
- **Páginas giradas ou cortadas são recodificadas uma vez no PDF** (qualidade 95); só as páginas sem ajuste são embutidas byte a byte. Uma página só girada poderia entrar sem recodificar (marca EXIF de orientação injetada no JPEG, que o img2pdf converte em `/Rotate`): otimização possível, fora deste escopo, para não misturar bytes de cabeçalho com a renderização.
- **Visão ampliada e miniatura são recalculadas por URL** a cada recarga da página (o servidor não guarda cache); medido em 0,11 s a 1200 dpi.
- **Girar o último arquivo JPG recodifica** (qualidade 95) a cada giro; o PDF não. O arquivo é seu: a mudança é na hora e sem desfazer além de girar três vezes.
- **Edição de moldura em duas abas** ao mesmo tempo: a última gravação vale; a revisão sobe e a outra aba relê o documento (R19).

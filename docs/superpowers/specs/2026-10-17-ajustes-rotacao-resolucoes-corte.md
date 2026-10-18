# Ajustes: girar, todas as resoluções, corte automático e botão Salvar: design

**Data:** 2026-10-17 · **Status:** decisões tomadas e contratos fechados (seções 5 e 6), tarefas T23 a T31 na seção 8, prontos para virar plano · **Complementa:** [spec principal](2026-10-13-digitalizadora-design.md) e [Documento de várias páginas](2026-10-17-documento-de-varias-paginas.md) (as referências "R12", "6.6.1" etc. são desse segundo documento) · **Baseline:** 2073 testes passando, `make lint` limpo.

## 1. O que você pediu (md.md, linhas 16 a 24, "ajustes")

1. Adicionar a opção de **girar a página** no modo Rápido e no modo Documento (uma digitalização real da capa de um livro saiu de cabeça para baixo).
2. No modo Documento, o botão "Finalizar PDF (Enter)" **pode ser removido** e o botão **Salvar** faz o papel dele.
3. Adicionar **todas as qualidades disponíveis**; "acho que tem 1200 dpi disponível".
4. Adicionar **corte automático, removendo o fundo**, como **caixa de seleção** (o usuário decide se quer ou não).

Fatos que o código e a captura da impressora mostram e que mudam ou precisam de cuidado em relação ao enunciado:

- **Hoje não existe botão "Salvar" no painel do Documento.** O único "Salvar" da página é o do campo "Pasta de saída" (`output-folder-save-button`). O pedido 2 só faz sentido se o botão do documento passar a se chamar "Salvar"; por isso o botão do documento vira **Salvar** e o da pasta vira **Salvar pasta** (decisão A8). Se você queria dizer outra coisa (por exemplo, que o "Salvar" da pasta também grave o PDF), diga e eu ajusto.
- A impressora anuncia exatamente 75, 100, 150, 200, 300, 400, 600 e 1200 dpi (`docs/gate-0-capturas/hp-deskjet-2800-scanner-capabilities.xml`), e os modos RGB24, Grayscale8 e BlackAndWhite1. O simulador já oferece as mesmas oito resoluções.
- **Pillow 13.0.0 não levanta `DecompressionBombError` para uma página inteira a 1200 dpi.** O vidro tem 2550 × 3508 (em 1/300 de polegada), ou seja 10200 × 14032 = 143.126.400 pixels a 1200 dpi. O limite padrão é 89.478.485: acima dele Pillow só emite `DecompressionBombWarning`; o erro vem acima do dobro (178.956.970). Medi isso abrindo um JPEG sintético desse tamanho. O aviso aparece a cada página e esconderia avisos de verdade, e o limite de erro continua longe de qualquer digitalização real, então o design sobe o limite com uma constante nomeada (6.6) em vez de tratar uma exceção que não ocorre.
- O `ScanEncoder` já recebe três serviços; um quarto estouraria o limite de três parâmetros. Por isso a etapa "ajustar e gravar a densidade" ganha um serviço próprio, o `MasterJpegService` (A10).
- Os identificadores de página nunca são reutilizados e a miniatura é servida com `Cache-Control: immutable` por identificador. Reescrever uma página já digitalizada com o **mesmo** identificador deixaria o navegador com a miniatura velha e abriria uma janela de queda em que o tamanho do arquivo não bate com o manifesto (a retomada descartaria a página). Por isso girar uma página gera um **identificador novo** (A6).

## 2. Decisões (tomadas pelo assistente; corrija se quiser)

| # | Decisão | Por quê | Alternativa descartada |
|---|---|---|---|
| A1 | **Girar é um ajuste salvo** `rotation_degrees` ∈ {0, 90, 180, 270}, no sentido horário, aplicado a **toda digitalização nova** (modo Rápido e cada página nova do modo Documento). Na interface é uma lista "Girar" com quatro opções ("Sem girar", "90° à direita", "180°", "90° à esquerda"), que mostra o valor atual por si só. | Resolve o seu caso (capa de cabeça para baixo: escolher 180° e digitalizar de novo), vale nos dois modos e não precisa de estado novo no servidor. Uma lista é acessível, cabe numa linha e não exige a conta de "mais 90" no JavaScript. | Dois botões ↺ ↻ com o ângulo ao lado (mais código e mais testes para o mesmo efeito) |
| A2 | **Rotação sobre os pixels com `Image.transpose`** (geometria sem perda) e **recodificação em JPEG qualidade 95**, mantendo subamostragem, densidade e perfil de cor da página. Com 0° e sem corte, **os bytes do scanner não são tocados** (nem decodificados). Não se usa a marca EXIF de orientação. | Com pixels girados, miniatura, Preview, PDF e qualquer leitor concordam; a marca EXIF dependeria de cada programa respeitá-la. A recodificação a 95 é invisível na prática; a rotação em si não perde nada. | Marca EXIF; giro sem perda via `jpegtran` (dependência nova e imagem com bordas que não são múltiplas do bloco) |
| A3 | No **modo Documento**, cada miniatura ganha um botão **Girar ↻** (90° à direita) que reescreve uma página já digitalizada: `POST /api/document/pages/{page_identifier}/rotation`. Passa pelo mesmo lock, pelas mesmas regras de 409 e pela mesma segurança contra queda das demais edições. No modo Rápido não há giro depois do fato: o arquivo já foi entregue na sua pasta e o app não reescreve arquivos seus; o remédio é o ajuste A1 e uma nova digitalização. | É o que "girar a página no modo documento" pede, com o custo de uma edição a mais, igual a excluir ou reordenar. Para girar à esquerda basta clicar três vezes (cada clique recodifica a 95; o dano é invisível). | Girar o último arquivo do modo Rápido (mexer em arquivo já entregue e no PDF dele); dois botões por miniatura (a grade já tem quatro) |
| A4 | **Ordem do pipeline:** scanner → **corte automático (se ligado)** → **giro** → codificação (JPEG mestre, miniatura, PDF). Quem manda é um serviço novo, `ImageAdjustmentService`, chamado pelo `MasterJpegService`, que o `ScanEncoder` usa. O modo Rápido (`ScanOutputService`) e o modo Documento (`DocumentPageCapture`) já passam pelo `ScanEncoder.encode`, então nada é duplicado. | Cortar antes de girar processa menos pixels e a detecção não depende da orientação. O `ScanEncoder` é o único ponto comum aos dois modos. | Ajustar em cada destino (`ScanDestination`), o que duplicaria a regra |
| A5 | **Resolução e cor viram ajustes próprios:** `dots_per_inch` (as oito resoluções) e `color_mode` (Colorido ou Tons de cinza). Os três nomes antigos continuam como atalho numa lista **Predefinição** que preenche as duas; ela mostra "Personalizada" quando a combinação não é nenhuma das três. O servidor devolve `scan_preset` já calculado (nome ou `null`) e aceita `scan_preset` como entrada antiga. | Dá todas as qualidades sem perder os atalhos que você já usa e sem tabela duplicada no JavaScript (a combinação é decidida no Python). | Trocar a lista por oito linhas fixas (sem a cor); manter só o preset e acrescentar uma lista de dpi que o contradiz |
| A6 | **Girar uma página do rascunho cria um identificador novo.** Arquivos novos (`page-<novo>.jpg`, `thumbnail-<novo>.jpg`) são gravados antes; o manifesto troca, na mesma posição, a entrada antiga pela nova (atômico); só então os arquivos antigos saem. | Mesmo padrão de 6.6.1 do outro spec: nenhuma queda deixa o manifesto apontando para arquivo errado, a retomada limpa os arquivos sem dono (`reconcile_draft` já faz), e o cache `immutable` da miniatura continua válido. | Trocar o arquivo no lugar com o mesmo identificador (janela de queda com tamanho divergente; miniatura velha no cache) |
| A7 | **Corte automático é a caixa "Cortar automaticamente e remover o fundo"**, ajuste `auto_crop`, padrão desligado. Usa só Pillow, sobre uma cópia em tons de cinza de no máximo 400 px (6.5). Se não achar uma região confiável, **mantém a imagem inteira** e registra no log. | Sem dependência nova (numpy não é dependência). Falhar para "não cortar" nunca perde conteúdo. | OpenCV/numpy (dependência nova); cortar sempre que algo for detectado |
| A8 | **Documento: sai "Finalizar PDF (Enter)"; entra "Salvar (Enter)".** O botão tem texto visível `Salvar`, `aria-label="Salvar documento"` e id `save-document-button`; o do campo da pasta passa a `Salvar pasta` (`aria-label="Salvar pasta de saída"`, id inalterado). O atalho Enter continua e **mantém exatamente as regras já projetadas**, inclusive a confirmação ("Salvar o PDF com N páginas?", botão "Salvar"). Os nomes internos `finalize` (rota `/api/document/finalize`, `request_finalize`, `DocumentFinalizer`) **não mudam**: finalização é o conceito do rascunho; "Salvar" é só o rótulo. | A confirmação protege de um Enter sem querer, já está testada (diálogo armado só depois do keyup, repetição ignorada, foco no botão de aceitar) e não há regra mais simples que seja igualmente segura. Renomear só o texto evita mexer em rota, serviço e centenas de testes. | Salvar sem confirmar (um Enter perdido encerra o documento); renomear tudo para "save" |
| A9 | **A lista de resoluções é uma constante** (`SUPPORTED_DOTS_PER_INCH`), validada no servidor; o scanner continua a escolher a resolução aceita mais próxima pela regra que já existe (`closest_supported_resolution`). Não consulto as capacidades da impressora para montar a lista. | A captura é estável para este modelo; ler as capacidades exigiria impressora conectada só para desenhar a tela e traria um estado "sem lista" a tratar. Para esta impressora as oito são exatas, então a densidade gravada no JPEG (`dots_per_inch` pedido) é a real. | Lista dinâmica por `GET /api/printer` |
| A10 | **`MasterJpegService`** (novo) = ajustar + gravar a densidade JFIF; é o primeiro parâmetro do `ScanEncoder` no lugar do `JpegResolutionService`. O mesmo serviço é usado para girar uma página do rascunho, então a densidade e a recodificação são idênticas nos dois caminhos. | Mantém o `ScanEncoder` em três parâmetros e evita duas rotinas de "recodificar mantendo a densidade". | Quarto parâmetro no `ScanEncoder`; ajustar dentro do `JpegResolutionService` (mistura bytes de cabeçalho com pixels) |
| A11 | **1200 dpi é seguro por construção** (6.6): limite de pixels subido num único lugar com constante nomeada; miniatura e detecção usam decodificação reduzida (`Image.draft`); giro e corte seguram no máximo duas imagens por vez; tempos de espera do scanner crescem com a área; a estimativa de espaço entende o JPEG recodificado. Aviso na tela ao escolher 600 ou 1200 dpi. | A 1200 dpi em cor uma página decodificada tem cerca de 430 MB. | Proibir ajustes acima de 600 dpi |
| A12 | **Cor: só Colorido e Tons de cinza.** `BlackAndWhite1` (1 bit) não é oferecido. | O pipeline todo é JPEG; um JPEG não tem 1 bit, e esse modo nunca foi capturado no Gate 0 (a impressora pode recusar ou entregar outra coisa). Se você quiser, é um próximo passo com Gate 0 próprio. | Oferecer sem testar na impressora |
| A13 | **Compatibilidade:** `settings.json` antigo (só `scan_preset`) carrega e vira o par `dots_per_inch`/`color_mode`; o manifesto do rascunho **não muda** (continua `format_version` 1: a página já guarda `dots_per_inch`, `color_mode` e `size_in_bytes`, e uma página girada ou cortada é só outro JPEG). `PUT /api/settings` sem nenhum campo novo continua válido. | Nada do que já está no disco precisa de migração. | Subir o formato do manifesto |
| A14 | **Rotação e corte valem no momento da digitalização**, como a qualidade: mudar o ajuste no meio de um documento afeta só as páginas seguintes, e cada página guarda a densidade que teve. O PDF do documento já aceita páginas de tamanhos diferentes (6.3, `write_pdf_at_embedded_resolutions`). | Mesma regra de qualidade por página do README. | Reaplicar o ajuste a todo o documento ao finalizar |

## 3. Interface

Caixa **Ajustes** (comum aos dois modos), de cima para baixo:

1. **Formato do arquivo** (PDF, JPG), como hoje; escondido no modo Documento.
2. Grupo **Qualidade**:
   - lista **Predefinição**: "Texto (300 dpi, cor)", "Texto econômico (200 dpi, cinza)", "Foto (600 dpi, cor)" e "Personalizada" (esta aparece sozinha quando a combinação atual não é nenhuma das três; não dá para escolhê-la);
   - lista **Resolução**: 75, 100, 150, 200, 300, 400, 600 e 1200 dpi;
   - lista **Cor**: "Colorido", "Tons de cinza";
   - aviso (`resolution-warning`, mesma aparência de `storage-warning`) quando a resolução é 600 ou mais: 600 dpi: "600 dpi leva cerca de 75 s por página e gera arquivos grandes."; 1200 dpi: "1200 dpi pode levar vários minutos e gerar arquivos muito grandes." As duas frases terminam em ponto.
3. Lista **Girar**: "Sem girar", "90° à direita", "180°", "90° à esquerda". Embaixo, só no modo Documento: "Vale para as próximas digitalizações. Para girar uma página que já está no documento, use Girar na miniatura."
4. Caixa de seleção **Cortar automaticamente e remover o fundo** (desligada por padrão), com a dica "Use para fotos e folhas menores que o vidro. Se a folha e a tampa forem brancas, a imagem fica inteira."
5. **Pasta de saída** com o botão **Salvar pasta**.

Painel do **Documento**: a barra de ações fica "Descartar última (Backspace)", "Cancelar documento" e **"Salvar (Enter)"** (estilo de botão principal, o que era "Finalizar PDF"). Cada miniatura: ◀ ▶ × na primeira linha, depois **Girar ↻** e "Mover para…". Textos que mudam de "finalizar" para "salvar":

| Onde | Hoje | Novo |
|---|---|---|
| Pergunta do diálogo | `Finalizar o PDF com 3 páginas?` | `Salvar o PDF com 3 páginas?` |
| Botão de aceitar do diálogo | `Finalizar` | `Salvar` |
| Botão grande durante a gravação | `Finalizando…` | `Salvando…` |
| Linha de status durante a gravação | `Finalizando o PDF (3 páginas)…` | `Salvando o PDF (3 páginas)…` |
| Linha de status após cada página | `…; Enter finaliza.` | `…; Enter salva.` |
| Aviso de documento grande | `finalizar pode levar alguns segundos…` | `salvar pode levar alguns segundos e usar bastante memória.` |
| Aviso de possível gravação anterior | `Confira antes de finalizar de novo.` / `…antes de finalizar de novo.` | `Confira antes de salvar de novo.` / `…antes de salvar de novo.` |
| Erro `empty_document` | `…antes de finalizar.` | `…antes de salvar.` |
| Erro `document_busy` | `O documento está sendo finalizado ou alterado…` | `O documento está sendo salvo ou alterado…` |

Textos de duração durante a digitalização (hoje por predefinição, passam a ser por resolução): até 300 dpi "cerca de 15 s" (medido: 14,4 s em cor, 6,7 s em cinza); 400 dpi "cerca de 30 s" (**estimativa** por área, não medida); 600 dpi "cerca de 75 s" (medido: 71,9 s); 1200 dpi "vários minutos" (estimativa de cerca de 5 minutos; não medida, a mesma conta por área dá 4 × 72 s).

## 4. API (acréscimos às seções 6.5 de cada spec; todas com o guarda de `Host` e o cabeçalho `X-Requested-With`)

### 4.1 `GET /api/settings` e o objeto `settings` de `GET /api/state`

```json
{
  "output_folder": "/Users/pedro/Pictures/Digitalizadora",
  "output_format": "pdf",
  "dots_per_inch": 300,
  "color_mode": "color",
  "scan_preset": "document",
  "capture_mode": "single",
  "rotation_degrees": 0,
  "auto_crop": false
}
```

`scan_preset` é **calculado**: o nome da predefinição cuja combinação é exatamente `dots_per_inch` + `color_mode`, ou `null` ("Personalizada"). Os outros campos são os ajustes salvos.

### 4.2 `PUT /api/settings`

Obrigatórios: `output_folder`, `output_format`. Todos os demais são opcionais, e **ausente ou `null` mantém o valor salvo** (como `capture_mode` hoje): `scan_preset`, `dots_per_inch` (inteiro), `color_mode` (`"color"` ou `"grayscale"`), `capture_mode`, `rotation_degrees` (inteiro), `auto_crop` (booleano). Regras de resolução da qualidade:

1. `scan_preset` presente mas desconhecido → `422 invalid_settings` (inalterado: `"poster"` continua recusado).
2. Se **nenhum** dos dois, `dots_per_inch` e `color_mode`, veio e `scan_preset` veio: vale o par da predefinição. É o cliente antigo, que só mandava `scan_preset`; e é como a lista Predefinição escolhe: a página manda `{scan_preset: "photo", dots_per_inch: null, color_mode: null}`.
3. Se `dots_per_inch` e/ou `color_mode` vieram, cada um vale sozinho e o resto vem do salvo; `scan_preset` é ignorado. Assim a página pode reenviar o objeto que leu (com o `scan_preset` velho) sem desfazer a mudança.
4. `dots_per_inch` fora das oito → `422 invalid_settings`; `rotation_degrees` fora de {0, 90, 180, 270} → `422 invalid_settings`. Tipos errados (texto onde deve haver número) continuam recebendo o `422` padrão do FastAPI, como qualquer corpo mal formado hoje.

A resposta é o objeto de 4.1. Nada é gravado quando qualquer campo é recusado (inalterado).

### 4.3 Adicionar página (modo Documento)

`POST /api/document/pages` continua sem corpo e `202`; o servidor lê `dots_per_inch`, `color_mode`, `rotation_degrees` e `auto_crop` dos ajustes salvos **no momento do pedido** e os junta ao pedido de digitalização. `POST /api/scans` (modo Rápido) idem.

### 4.4 Girar uma página do rascunho

`POST /api/document/pages/{page_identifier}/rotation`, sem corpo. Gira a página 90° no sentido horário. Responde `200` com o corpo do documento de 6.5 (o mesmo de toda edição); **o identificador da página muda** (a posição não), então a interface relê as páginas do corpo e vê a miniatura nova. Erros, todos no formato `{code, message}` já usado:

| Situação | Código | Status |
|---|---|---|
| Digitalização em andamento | `scan_already_running` | 409 |
| Outra edição em andamento | `document_busy` | 409 |
| Sem rascunho | `no_open_document` | 404 |
| Identificador fora do rascunho ou mal formado | `page_not_found` | 404 |
| Arquivo da página ausente, de tamanho diferente do manifesto ou que não decodifica como imagem (com `page_identifier` no corpo, como em R18) | `damaged_document_page` | 409 |
| Pouco espaço no disco do Mac para o arquivo novo | `insufficient_draft_storage` | 507 |
| Disco do rascunho indisponível | `draft_storage_unavailable` | 503 |
| Memória insuficiente para girar | **`image_adjustment_failed` (novo)** | 500 |

### 4.5 Outros erros

- Um erro **novo**, `image_adjustment_failed`: "Não consegui girar ou cortar a imagem com a memória livre do Mac. Escolha uma resolução menor, desligue o corte automático e tente de novo." Aparece como `last_error` quando acontece numa digitalização (a página continua perdida, como em qualquer falha do `ScanService`), e como corpo `500` na rotação de página.
- Uma imagem do scanner que não decodifica durante giro ou corte vira `ScanFailedError` (`scan_failed`), igual à miniatura de hoje.
- Nenhum outro código novo. `GET /api/state` não ganha campos além do objeto `settings` de 4.1.

## 5. Contratos

### 5.1 Visão geral das mudanças por camada

```
domain/            scan_quality.py (NOVO)        page_rotation.py (NOVO)       image_adjustment.py (NOVO)
                   pixel_region.py (NOVO)        scan_preset.py (MUDA)         application_settings.py (MUDA)
                   scan_request.py (MUDA)        document_draft.py (MUDA)      errors.py (MUDA)   ports.py (MUDA)
repositories/      json_application_settings_repository.py (MUDA)   file_system_document_draft_repository.py (MUDA)
services/          image_pixel_limit.py (NOVO)   paper_region_detection.py (NOVO)   image_adjustment_service.py (NOVO)
                   master_jpeg_service.py (NOVO) document_page_rotator.py (NOVO)
                   scan_encoder.py, thumbnail_service.py, storage_guard_service.py, application_settings_service.py,
                   application_state_service.py, document_page_capture.py, scan_output_service.py,
                   document_draft_store.py, document_draft_service.py (MUDAM)
infrastructure/    escl/escl_scanner_gateway.py (MUDA: espera por resolução)
controllers/       settings_body.py, settings_controller.py, state_controller.py, document_controller.py,
                   error_message_catalog.py (MUDAM)
raiz               composition_root.py (MUDA)    simulator/fake_escl_scanner_app.py (MUDA: tampa escura)
web/static/        scan-quality-policy.js (NOVO) index.html, application.css, application.js, document-page-policy.js,
                   document-panel.js (MUDAM)
```

Camadas inalteradas: controladores → serviços → domínio ← repositórios/infraestrutura. Só a raiz de composição instancia classes concretas. Máximo de três parâmetros por função/método/construtor (sem contar `self`; campos de dataclass não contam), nenhum parâmetro booleano, nenhuma abreviação, tudo injetado no construtor.

### 5.2 `domain/`

```python
# scan_quality.py   (NOVO; regras puras)
SUPPORTED_DOTS_PER_INCH: tuple[int, ...] = (75, 100, 150, 200, 300, 400, 600, 1200)
REFERENCE_DOTS_PER_INCH = 600            # Gate 0: 71,9 s por página A4 em cor
SLOW_SCAN_DOTS_PER_INCH = 600            # a partir daqui a interface avisa (a constante vale para o texto do JavaScript também)
HIGHEST_DOTS_PER_INCH = 1200
PLATEN_WIDTH_INCHES = 8.5                # movidos de storage_guard_service.py; o módulo antigo os importa daqui
PLATEN_HEIGHT_INCHES = 11.69

def is_supported_dots_per_inch(dots_per_inch: int) -> bool: ...
def pixels_per_page(dots_per_inch: int) -> int: ...          # round(8.5 * dpi) * round(11.69 * dpi)
def scan_timeout_multiplier(dots_per_inch: int) -> float: ...  # max(1.0, (dots_per_inch / 600) ** 2)

# page_rotation.py   (NOVO)
class PageRotation(int, Enum):
    NONE = 0
    CLOCKWISE_90 = 90
    HALF_TURN = 180
    COUNTERCLOCKWISE_90 = 270
    def turned_clockwise(self) -> "PageRotation": ...          # PageRotation((self.value + 90) % 360)

# image_adjustment.py   (NOVO)
@dataclass(frozen=True)
class ImageAdjustment:
    rotation: PageRotation = PageRotation.NONE
    auto_crop: bool = False
    @property
    def is_active(self) -> bool: ...                           # rotation is not NONE or auto_crop
NO_ADJUSTMENT = ImageAdjustment()

# pixel_region.py   (NOVO; coordenadas como as do Pillow: right e bottom exclusivos)
@dataclass(frozen=True)
class PixelRegion:
    left: int
    top: int
    right: int
    bottom: int
    @property
    def width(self) -> int: ...
    @property
    def height(self) -> int: ...
    @property
    def area(self) -> int: ...
    def as_box(self) -> tuple[int, int, int, int]: ...
    def scaled(self, from_size: tuple[int, int], to_size: tuple[int, int]) -> "PixelRegion": ...   # left/top para baixo, right/bottom para cima
    def grown_within(self, margin: int, limits: tuple[int, int]) -> "PixelRegion": ...             # soma a margem e limita a [0, limits]

# scan_preset.py   (MUDA: um método novo; o resto fica)
class ScanPreset(str, Enum):
    @classmethod
    def matching(cls, scan_settings: ScanSettings) -> "ScanPreset | None": ...

# scan_request.py   (MUDA: campo novo no fim, com padrão; toda construção de hoje continua valendo)
@dataclass(frozen=True)
class ScanRequest:
    settings: ScanSettings
    output_format: OutputFormat
    adjustment: ImageAdjustment = NO_ADJUSTMENT

# application_settings.py   (MUDA: scan_preset sai, scan_settings entra no mesmo lugar; um campo novo no fim)
@dataclass(frozen=True)
class ApplicationSettings:
    output_folder: Path
    output_format: OutputFormat
    scan_settings: ScanSettings
    capture_mode: CaptureMode = CaptureMode.SINGLE
    adjustment: ImageAdjustment = NO_ADJUSTMENT
    def to_scan_request(self) -> ScanRequest: ...   # ScanRequest(self.scan_settings, self.output_format, self.adjustment)

# document_draft.py   (MUDA: um método novo em DocumentDraft)
def with_page_replaced(self, page_identifier: str, replacement: DocumentPage) -> "DocumentDraft": ...
#   mesma posição; PageNotFoundError se o identificador não está no rascunho; sem as marcas de finalização (R15),
#   como toda mudança de conteúdo (usa _with_content).

# errors.py   (ACRÉSCIMO)
class ImageAdjustmentFailedError(DigitalizadoraError):
    code = "image_adjustment_failed"

# ports.py   (ACRÉSCIMO em DocumentDraftRepository)
def read_page_file(self, page_identifier: str) -> bytes | None: ...   # None se o arquivo não existe
```

`ScanPreset.matching` devolve a predefinição cujo `settings` é igual ao argumento, ou `None`. O `ScanPreset` continua existindo para a leitura de `settings.json` antigo, para o campo `scan_preset` de 4.1 e como entrada antiga de 4.2.

### 5.3 `repositories/`

```python
# json_application_settings_repository.py   (MUDA)
```

Leitura (`parse_application_settings`), por chave, nesta ordem:

1. `output_folder` e `output_format`: como hoje (ausente, ilegível ou inválido torna o arquivo inteiro inutilizável → ajustes padrão, com aviso no log).
2. **Qualidade:** se `dots_per_inch` está em `SUPPORTED_DOTS_PER_INCH` (inteiro, não booleano) **e** `color_mode` é um `ColorMode` conhecido, vale o par. Senão, se `scan_preset` é um `ScanPreset` válido, vale `scan_preset.settings` (e um par presente mas inválido gera um aviso no log, uma vez por valor). Senão o arquivo é inutilizável (como hoje com `"poster"`).
3. `capture_mode`: como hoje (ausente ou desconhecido → modo Rápido, aviso uma vez só para o desconhecido).
4. `rotation_degrees`: ausente → 0; fora do enum (texto, 45, `null`, booleano) → 0 com aviso uma vez por valor, **sem descartar o resto**.
5. `auto_crop`: ausente → `False`; não booleano → `False` com aviso uma vez por valor.

O "aviso uma vez por valor" passa a valer para as três chaves tolerantes (`capture_mode`, `rotation_degrees`, `auto_crop`) com um dicionário `chave → texto já avisado`, porque `GET /api/state` lê os ajustes a cada 0,5 s.

Gravação (`save`): `output_folder`, `output_format`, `dots_per_inch`, `color_mode`, `capture_mode`, `rotation_degrees`, `auto_crop`. A chave `scan_preset` **não é mais gravada** (a combinação é a fonte; o nome é calculado). Um `settings.json` gravado por esta versão não é lido por versões anteriores ao design; isso é aceito (não há volta).

```python
# file_system_document_draft_repository.py   (MUDA: um método novo; implementa o port)
def read_page_file(self, page_identifier: str) -> bytes | None:
    """O arquivo inteiro da página, ou None se não existe; outro OSError vira DraftStorageUnavailableError."""
```

`document_manifest_codec.py` **não muda** (A13).

### 5.4 `services/`

```python
# image_pixel_limit.py   (NOVO)
MAXIMUM_SCAN_DOTS_PER_INCH = HIGHEST_DOTS_PER_INCH                      # 1200
PIXEL_LIMIT_MARGIN = 1.05
MAXIMUM_SCANNER_IMAGE_PIXELS = ceil(pixels_per_page(1200) * 1.05)       # 150.239.880 (a estimativa da página inteira a 1200 dpi é 143.085.600; a imagem real do vidro tem 143.126.400)
def raise_decompression_limit_to_scanner_size() -> None:
    Image.MAX_IMAGE_PIXELS = MAXIMUM_SCANNER_IMAGE_PIXELS
# Pillow avisa acima do limite e só recusa acima do dobro (300 milhões): uma digitalização de verdade nunca avisa,
# e uma imagem enorme forjada continua recusada. Chamada UMA vez, no começo de build_container.
```

```python
# paper_region_detection.py   (NOVO; funções puras sobre uma imagem Pillow pequena, sem I/O)
def detect_paper_region(preview: Image.Image) -> PixelRegion | None:
    """preview: modo "L", lado maior de até 400 px. Devolve a região do papel em pixels do preview, ou None."""
```

Algoritmo e constantes em 6.5.

```python
# image_adjustment_service.py   (NOVO; síncrono, roda no thread do store/do edit)
class ImageAdjustmentService:
    def adjust(self, jpeg_content: bytes, adjustment: ImageAdjustment) -> bytes: ...
```

- `adjustment.is_active` falso → devolve **o mesmo objeto `bytes`**, sem decodificar.
- `auto_crop` ligado: decodifica um preview reduzido (`Image.draft("L", (400, 400))` + `thumbnail` com `Resampling.BOX`), roda `detect_paper_region`, mapeia a região para a imagem inteira com `PixelRegion.scaled` e `grown_within(CROP_MARGIN, tamanho)`. Sem região **e** sem giro → devolve os bytes originais (nada é recodificado).
- Com região ou giro: decodifica a imagem inteira **uma vez**, corta (se houver região) e libera o original, gira (se houver giro) e libera o cortado, e codifica.
- Mapa de giro (o Pillow gira no sentido anti-horário): `CLOCKWISE_90 → Transpose.ROTATE_270`, `HALF_TURN → ROTATE_180`, `COUNTERCLOCKWISE_90 → ROTATE_90`. Um teste com imagem assimétrica trava isso.
- Codificação: `quality=95` (`ADJUSTED_JPEG_QUALITY`), `subsampling` lida **antes** da transformação com `JpegImagePlugin.get_sampling(source)` e passada como número (depois de `transpose` a imagem perde o `format` e `subsampling="keep"` levanta `ValueError`; medido); omitida se a imagem é "L" (valor `-1`); `dpi` e `icc_profile` repassados se a origem os tem. O resultado sempre tem JFIF; a densidade final é regravada por `JpegResolutionService` (A10).
- Erros: `MemoryError` → `ImageAdjustmentFailedError`; `OSError`, `Image.DecompressionBombError` ou `ValueError` ao decodificar → `ScanFailedError("The scanned image could not be decoded for the adjustment")`.

```python
# master_jpeg_service.py   (NOVO)
class MasterJpegService:
    def __init__(self, image_adjustment_service: ImageAdjustmentService,
                 jpeg_resolution_service: JpegResolutionService) -> None: ...
    def build_master_jpeg(self, scanned_jpeg: bytes, request: ScanRequest) -> bytes:
        """adjust(scanned_jpeg, request.adjustment) e depois with_resolution(..., request.settings.dots_per_inch)."""

# scan_encoder.py   (MUDA: o primeiro parâmetro troca de tipo; a ordem e a quantidade ficam)
def __init__(self, master_jpeg_service: MasterJpegService, pdf_assembly_service: PdfAssemblyService,
             thumbnail_service: ThumbnailService) -> None: ...
# encode(): normalised_jpeg = master_jpeg_service.build_master_jpeg(scanned_image.content, job.request)
# O resto de encode (miniatura a partir do mestre, PDF com build_pdf) fica igual. THUMBNAIL_MAXIMUM_EDGE_PIXELS
# passa para thumbnail_service.py (o ScanEncoder e o DocumentPageRotator o importam de lá).
```

```python
# storage_guard_service.py   (MUDA: terceiro parâmetro opcional; chamadas de hoje continuam valendo)
ADJUSTED_PAGE_SIZE_FACTOR = 2       # estimativa conservadora: recodificar a 95 devolve um JPEG maior que o do scanner
def estimated_page_bytes(settings: ScanSettings, adjustment: ImageAdjustment = NO_ADJUSTMENT) -> int: ...
def ensure_space_for_scan(self, folder: Path, settings: ScanSettings, adjustment: ImageAdjustment = NO_ADJUSTMENT) -> None: ...
def estimate_pages_remaining(self, folder: Path, settings: ScanSettings, adjustment: ImageAdjustment = NO_ADJUSTMENT) -> int: ...
# Com adjustment.is_active a estimativa de uma página é multiplicada por ADJUSTED_PAGE_SIZE_FACTOR.
# A conta por pixel não muda (0,12 e 0,08 bytes por pixel). 1200 dpi em cor: 143 MP x 0,12 = cerca de 17 MB por página
# (cerca de 34 MB com ajuste); as 3 páginas de margem e o 1 GiB mínimo continuam.
```

```python
# document_page_capture.py   (MUDA: só repassa)
def ensure_capacity(self, request: ScanRequest) -> None:   # draft_store.ensure_capacity_for_page(request.settings, request.adjustment)
# scan_output_service.py (MUDA: só repassa)
# ensure_capacity: storage_guard_service.ensure_space_for_scan(folder, request.settings, request.adjustment)

# application_state_service.py   (MUDA)
# estimate_pages_remaining(folder, settings.scan_settings, settings.adjustment)

# application_settings_service.py   (MUDA)
@dataclass(frozen=True)
class SettingsUpdate:
    output_folder: str
    output_format: str
    scan_preset: str | None = None
    capture_mode: str | None = None
    dots_per_inch: int | None = None
    color_mode: str | None = None
    rotation_degrees: int | None = None
    auto_crop: bool | None = None
# update(update): lê os ajustes salvos uma vez, resolve cada campo (None mantém o salvo), valida
# (InvalidSettingsError), prepara a pasta e grava. Regras de qualidade: 4.2. Funções auxiliares privadas:
# _resolve_scan_settings(update, saved), _resolve_adjustment(update, saved).
```

```python
# document_draft_store.py   (MUDA)
def ensure_capacity_for_page(self, settings: ScanSettings, adjustment: ImageAdjustment = NO_ADJUSTMENT) -> None: ...
def describe_storage(self, settings: ScanSettings, adjustment: ImageAdjustment = NO_ADJUSTMENT) -> DraftStorageState: ...
def read_page_content(self, page_identifier: str) -> StoredPage: ...
def ensure_capacity_for_replacement(self, page_identifier: str) -> None: ...
def replace_page(self, page_identifier: str, replacement: CapturedPage) -> DocumentDraft: ...

@dataclass(frozen=True)
class StoredPage:
    page: DocumentPage
    position: int
    jpeg_content: bytes
```

- `read_page_content`: `NoOpenDocumentError` sem rascunho; `PageNotFoundError` se o identificador não está nele; arquivo ausente ou de tamanho diferente de `page.size_in_bytes` → `DamagedDocumentPageError(page_identifier, position)` (R18).
- `ensure_capacity_for_replacement`: `storage_guard.ensure_space_for_file(drafts_folder, 2 * page.size_in_bytes)` (o arquivo novo coexiste com o antigo por um instante; a recodificação pode crescer), com os erros passados por `as_draft_storage_error` e o mesmo bloqueio de `_recovery_failed` de `ensure_capacity_for_page`.
- `replace_page` é 6.4; devolve o rascunho novo.

```python
# document_page_rotator.py   (NOVO; síncrono, roda dentro do _run_edit)
class DocumentPageRotator:
    def __init__(self, draft_store: DocumentDraftStore, master_jpeg_service: MasterJpegService,
                 thumbnail_service: ThumbnailService) -> None: ...
    def rotate_clockwise(self, page_identifier: str) -> DocumentDraft: ...
```

Passos: `ensure_capacity_for_replacement` → `read_page_content` → monta `ScanRequest(ScanSettings(page.dots_per_inch, page.color_mode), OutputFormat.JPEG, ImageAdjustment(rotation=PageRotation.CLOCKWISE_90))` → `master_jpeg_service.build_master_jpeg(jpeg, request)` (o `ScanFailedError` de uma página que não decodifica vira `DamagedDocumentPageError(page_identifier, position)`) → `thumbnail_service.build_thumbnail(rotado, THUMBNAIL_MAXIMUM_EDGE_PIXELS)` → `draft_store.replace_page(page_identifier, CapturedPage(rotado, miniatura, page.scanned_at, request.settings))`.

```python
# document_draft_service.py   (MUDA)
@dataclass(frozen=True)
class DocumentDraftCollaborators:
    draft_store: DocumentDraftStore
    page_scanner: Callable[[ScanRequest], Awaitable[DocumentPage]]
    finalizer: DocumentFinalizer
    page_rotator: DocumentPageRotator           # NOVO (campo de dataclass: o construtor do serviço continua com três parâmetros)

async def add_page(self, settings: ScanSettings, adjustment: ImageAdjustment = NO_ADJUSTMENT) -> DocumentPage: ...
# ScanRequest(settings=settings, output_format=OutputFormat.JPEG, adjustment=adjustment)
async def rotate_page(self, page_identifier: str) -> DocumentDraft:
    return await self._run_edit(functools.partial(self._page_rotator.rotate_clockwise, page_identifier))
def describe_draft_storage(self, settings: ScanSettings, adjustment: ImageAdjustment = NO_ADJUSTMENT) -> DraftStorageState: ...
```

`_run_edit` já garante: 409 `scan_already_running` se há digitalização, espera pelo lock, thread de trabalho, `_waiting_edit_count`. Nada novo no lock.

### 5.5 `infrastructure/`

```python
# escl/escl_scanner_gateway.py   (MUDA: a espera pela página cresce com a resolução)
# EsclGatewayTiming ganha um método e nenhum campo novo:
def scan_timeout_for(self, dots_per_inch: int) -> float:
    return self.scan_timeout_seconds * scan_timeout_multiplier(dots_per_inch)
# scan_page(settings): scan_timeout = timing.scan_timeout_for(settings.dots_per_inch)
# _download_page(job_path, scan_timeout_seconds) e _request_next_document(job_path, scan_timeout_seconds):
#   o limite total e a leitura de NextDocument usam esse valor (a leitura é max(180, scan_timeout), como hoje).
```

Base medida e margem: o limite atual de 300 s cobre os 71,9 s de 600 dpi em cor com margem de 4,2 vezes. O multiplicador é 1 até 600 dpi e cresce com a **área** (300 dpi → 600 dpi levou 14,4 s → 71,9 s, cerca de 5 vezes para 4 vezes a área): a 1200 dpi o multiplicador é 4, o limite é 1200 s (20 minutos) e a espera esperada é de 290 a 360 s, margem de 3,3 a 4,2 vezes. Resoluções menores mantêm 300 s, então uma impressora travada continua sendo detectada no mesmo tempo de hoje. O tempo de leitura padrão do cliente HTTP (180 s em `composition_root.py`) **não é mais o limite do `NextDocument`** (o gateway já o substitui por pedido); o comentário da constante deve dizer isso.

### 5.6 `controllers/`

```python
# settings_body.py   (MUDA)
def build_settings_body(settings: ApplicationSettings) -> dict[str, str | int | bool | None]:
    # 4.1: output_folder, output_format, dots_per_inch, color_mode, scan_preset (calculado: ScanPreset.matching(...)),
    #      capture_mode, rotation_degrees, auto_crop

# settings_controller.py   (MUDA)
class SettingsRequestBody(BaseModel):
    output_folder: str
    output_format: str
    scan_preset: str | None = None
    capture_mode: str | None = None
    dots_per_inch: StrictInt | None = None
    color_mode: str | None = None
    rotation_degrees: StrictInt | None = None
    auto_crop: StrictBool | None = None
# read_settings devolve dict[str, str | int | bool | None]; update_settings monta SettingsUpdate com todos os campos.

# state_controller.py   (MUDA)
# _describe_document: describe_draft_storage(state.settings.scan_settings, state.settings.adjustment)

# document_controller.py   (MUDA)
router.add_api_route("/api/document/pages/{page_identifier}/rotation", self.rotate_page, methods=["POST"])
async def rotate_page(self, page_identifier: str) -> JSONResponse:
    return await self._respond_to_edit(self._document_draft_service.rotate_page(page_identifier))
# add_page: settings = self._settings_service.current(); background_tasks.add_task(self._run_add_page, settings)
#           _run_add_page(settings: ApplicationSettings) -> document_draft_service.add_page(settings.scan_settings, settings.adjustment)
# DOCUMENT_ERROR_STATUSES não ganha entrada: image_adjustment_failed cai no padrão 500.
```

`error_message_catalog.py`: acrescenta `image_adjustment_failed` (4.5) e muda `empty_document` e `document_busy` (seção 3). A rota nova entra antes de `/pages/{page_identifier}` apenas por consistência; ela é distinta (`POST` com sufixo `/rotation`).

### 5.7 Raiz de composição (`composition_root.py`)

- `build_container` chama `raise_decompression_limit_to_scanner_size()` **uma vez**, na primeira linha.
- Ajustes padrão: `ApplicationSettings(output_folder=..., output_format=PDF, scan_settings=ScanPreset.DOCUMENT.settings)` (rotação 0, corte desligado).
- `_SharedServices` ganha `master_jpeg_service: MasterJpegService` (campo de dataclass). `master_jpeg_service = MasterJpegService(ImageAdjustmentService(), JpegResolutionService())`; `scan_encoder = ScanEncoder(master_jpeg_service, PdfAssemblyService(), ThumbnailService())`.
- `DocumentPageRotator(draft_store, shared_services.master_jpeg_service, ThumbnailService())` entra em `DocumentDraftCollaborators(draft_store, page_scanner, finalizer, page_rotator)`.
- Nenhuma outra classe concreta é instanciada fora daqui.

### 5.8 Simulador (`simulator/fake_escl_scanner_app.py`)

```python
class LidBackground(str, Enum):
    WHITE = "white"      # a página branca ocupa o vidro (o simulador de hoje)
    DARK = "dark"        # tampa aberta: fundo escuro e uma folha clara menor, fora do centro

@dataclass
class FakeScannerBehavior:                       # campo novo no fim, com padrão
    lid_background: LidBackground = LidBackground.WHITE

def build_synthetic_page(requested_scan: RequestedScan, page_number: int, lid_background: LidBackground) -> bytes: ...
```

Com `DARK`, o fundo é `(30, 30, 30)` e a folha branca com moldura e rótulo ocupa de 15% a 80% da largura e de 10% a 85% da altura. Serve ao teste de ponta a ponta do corte e do giro (o rótulo "Pagina N" fica no canto superior esquerdo da folha, assimétrico de propósito). O padrão `WHITE` não muda nenhum teste de hoje. `simulator/__main__.py` lê a variável de ambiente `DIGITALIZADORA_SIMULATOR_LID_BACKGROUND` (`white` ou `dark`; ausente ou desconhecida = `white`) e a passa para `FakeScannerBehavior(lid_background=...)`; assim `make simulator` com `DIGITALIZADORA_SIMULATOR_LID_BACKGROUND=dark` serve à verificação manual.

### 5.9 Interface (`web/static`)

**`scan-quality-policy.js` (NOVO; regras puras, sem DOM; carregado logo depois de `scan-trigger-policy.js`):**

```js
const SLOW_SCAN_DOTS_PER_INCH = 600;
const VERY_SLOW_SCAN_DOTS_PER_INCH = 1200;
const CUSTOM_PRESET_VALUE = "custom";
const ROTATION_DEGREES = Object.freeze([0, 90, 180, 270]);
function describe_expected_scan_duration(dots_per_inch)        // 4 faixas de 3: até 300 / 400 / 600 / 1200 ou mais
function describe_resolution_warning(dots_per_inch)            // null abaixo de 600; texto de 600; texto de 1200
function choose_preset_option(settings)                        // settings.scan_preset ?? CUSTOM_PRESET_VALUE
function build_preset_changes(preset_value)                    // { scan_preset: preset_value, dots_per_inch: null, color_mode: null }
function parse_rotation_degrees(select_value)                  // Number(select_value), só se estiver em ROTATION_DEGREES; senão 0
```

`describe_expected_scan_duration` sai de `document-page-policy.js` (a tabela por predefinição `EXPECTED_SCAN_DURATION_TEXTS`, `DEFAULT_SCAN_PRESET` e a função antiga somem); `describe_document_status` passa a receber `dots_per_inch` no lugar de `scan_preset` no objeto de progresso, e `PHASE_MESSAGES.scanning` de `application.js` idem. A ordem de carga das scripts passa a ser: `scan-trigger-policy.js`, `scan-quality-policy.js`, `error-banner.js`, `document-page-policy.js`, `document-panel.js`, `application.js`.

**`index.html`:** ids novos `resolution-select`, `color-mode-select`, `resolution-warning`, `rotation-select`, `rotation-document-hint`, `auto-crop-checkbox`, `save-document-button` (substitui `finalize-document-button`); `preset-select` ganha a opção `custom` desabilitada. O botão da pasta continua `output-folder-save-button`.

**`application.js`:** `collect_elements` ganha as chaves `resolution_select`, `color_mode_select`, `resolution_warning`, `rotation_select`, `rotation_document_hint`, `auto_crop_checkbox`, `save_document_button` (e perde `finalize_document_button`). `apply_saved_settings(settings)` preenche as cinco listas e a caixa (`preset_select.value = choose_preset_option(settings)`, `rotation_select.value = String(settings.rotation_degrees ?? 0)`, `auto_crop_checkbox.checked = settings.auto_crop === true`, e `settings.dots_per_inch`/`settings.color_mode` nas duas outras; ausentes num servidor antigo deixam o controle como está). Eventos: `preset_select` → `change_setting(build_preset_changes(value))`; `resolution_select` → `{dots_per_inch: Number(value)}`; `color_mode_select` → `{color_mode: value}`; `rotation_select` → `{rotation_degrees: parse_rotation_degrees(value)}`; `auto_crop_checkbox` → `{auto_crop: checked}`. `render_resolution_warning` mostra/esconde `resolution_warning` com `describe_resolution_warning(settings.dots_per_inch)`. `render_capture_mode` mostra `rotation_document_hint` só no modo Documento. `choose_scan_button_label`: "Finalizando…" → "Salvando…" (constante `SCAN_BUTTON_SAVING_LABEL`).

**`document-page-policy.js`:** `NEXT_SHEET_TEXT` = "Coloque a próxima folha e aperte Espaço; Enter salva."; `describe_document_status`: "Salvando o PDF (N páginas)…"; `describe_possible_previous_save`: "…antes de salvar de novo."; `DOCUMENT_ACTIONS.ROTATE = "rotate"`; `FOCUS_TARGETS.ROTATE_BUTTON = "rotate_button"`; `decide_focus_after_action`: ação `ROTATE` iniciada pelo teclado → botão Girar da miniatura que agora está na mesma posição; iniciada pelo mouse → botão grande (a regra geral de hoje). `describe_page_rotation(position)` → `Página ${position} girada 90° para a direita.` As ações e nomes de evento `FINALIZED`, `REQUEST_FINALIZE` etc. **não mudam** (A8).

**`document-panel.js`:** `save_document_button` no lugar de `finalize_document_button` (mesmos ouvintes: clique → `request_finalize`); `FINALIZE_ACCEPT_LABEL` → `SAVE_ACCEPT_LABEL = "Salvar"`; pergunta `Salvar o PDF com ${describe_page_count(n)}?`; `build_page_rotation_path(page_identifier)` = `/api/document/pages/${page_identifier}/rotation`; `build_tile` cria `rotate_button` ("Girar ↻", classe `page-rotate`, `aria-label` "Girar a página N 90 graus para a direita") entre `delete_button` e `move_to_button`; `render_controls` o desabilita fora de `can_edit`; `rotate_page(page_identifier, action_origin)` faz `run_edit({method: "POST", path})`, anuncia `describe_page_rotation(position)` e chama `apply_focus({action: ROTATE, acted_position, ...})`; `DEFAULT_DOTS_PER_INCH = 300` no lugar de `DEFAULT_SCAN_PRESET`; `apply_summary` recebe `dots_per_inch`.

**`application.css`:** estilos de `.quality-group`, `.rotation-field`, `.page-rotate` (a grade `.page-actions` passa a ter ◀ ▶ × na primeira linha e Girar + Mover na segunda).

## 6. Algoritmos

### 6.1 Ordem de uma digitalização nova (os dois modos)

1. `POST /api/scans` ou `POST /api/document/pages`: o controlador lê os ajustes salvos e monta `ScanRequest(settings, output_format, adjustment)` (no modo Documento o formato é sempre JPEG).
2. `ensure_capacity(request)` (thread): a pasta primeiro, depois o espaço, **com a estimativa de 5.4** (inclui o fator de ajuste).
3. `gateway.scan_page(request.settings)` com o limite de espera de 5.5.
4. `store` (thread): `ScanEncoder.encode(scanned_image, job)`:
   1. confere `image/jpeg`;
   2. `MasterJpegService.build_master_jpeg`: `ImageAdjustmentService.adjust` (corte se ligado, depois giro; sem ajuste, os bytes do scanner intactos) e, em seguida, `JpegResolutionService.with_resolution` (densidade JFIF = `dots_per_inch` pedido);
   3. miniatura (480 px) **do mestre já ajustado**, por decodificação reduzida;
   4. PDF (`build_pdf`) só no modo Rápido com PDF; o mestre é o conteúdo no modo Documento e no modo Rápido com JPG.
5. Modo Rápido: o repositório grava o arquivo. Modo Documento: `append_page` (6.6.1 do outro spec) com `CapturedPage(jpeg_content = mestre ajustado, ..., settings)`.

**Efeito nos registros de página:** `DocumentPage.dots_per_inch` e `color_mode` são os da digitalização (o corte e o giro não mudam a densidade); `size_in_bytes` é o tamanho do **JPEG ajustado**, que é o que `verify_page_files` e a retomada comparam. As dimensões em pixels não são guardadas (nunca foram): uma página cortada ou girada tem dimensões diferentes e o PDF a monta com o tamanho físico `pixels / dots_per_inch` do próprio JFIF, como já faz para páginas de resoluções misturadas. No modo Rápido com PDF, `build_pdf` usa o mesmo `dots_per_inch` fixo; a página sai com o tamanho físico da região cortada.

### 6.2 Resolução e cor

`ScanSettings(dots_per_inch, color_mode)` vai ao scanner como hoje (`build_scan_settings_xml` escolhe `RGB24` ou `Grayscale8` e a resolução aceita mais próxima, nunca menor que a pedida enquanto existir uma maior). Nenhuma mudança no protocolo eSCL: o XML já passa `XResolution` e `YResolution`. A região é a do vidro inteiro, como hoje.

### 6.3 Giro nas digitalizações novas

`rotation_degrees` vem dos ajustes salvos no momento do pedido (A14). Com `0` e corte desligado, `adjust` devolve o mesmo `bytes`: o caminho de hoje fica idêntico, byte a byte.

### 6.4 Girar uma página do rascunho (atômico, no padrão de 6.6.1 e 6.6.4 do outro spec)

Tudo dentro de `DocumentDraftService._run_edit` (lock, 409 durante digitalização, thread de trabalho):

1. `draft = snapshot().draft` ou `NoOpenDocumentError`; `PageNotFoundError` se `is_page_identifier(...)` é falso ou o identificador não está no rascunho.
2. `ensure_capacity_for_replacement` (recusa antes de decodificar qualquer coisa).
3. `read_page_content`: arquivo existente e com o tamanho do manifesto, senão `DamagedDocumentPageError` (R18).
4. Gira, recodifica e gera a miniatura (`DocumentPageRotator`); falha de decodificação → `DamagedDocumentPageError`; `MemoryError` → `ImageAdjustmentFailedError`. Nada foi gravado até aqui.
5. `new_identifier = identity_source.page_identifier_factory()`; `repository.write_page_files(DocumentPageFiles(new_identifier, rotado, miniatura))` (a página e depois a miniatura, cada uma atômica, como em 6.6.1 do outro spec).
6. `new_page = DocumentPage(new_identifier, page.scanned_at, page.dots_per_inch, page.color_mode, len(rotado))`; `new_draft = draft.with_page_replaced(page_identifier, new_page)` (mesma posição; sem as marcas de finalização).
7. `repository.save_manifest(new_draft)`. Se falhar: `repository.delete_page_files(new_identifier)` (melhor esforço) e relança; o snapshot não muda e a página antiga continua inteira.
8. Troca o snapshot (`revision + 1`, `recovery_report = None`, `last_finished_document = None`).
9. `repository.delete_page_files(page_identifier)` (melhor esforço; falhar só deixa arquivos sem dono).
10. Devolve `new_draft`; o controlador responde com o corpo do documento.

Quedas: antes do passo 7 terminar, os arquivos novos estão fora do manifesto e `reconcile_draft` os apaga na retomada (`unlisted_page_files` e `discarded_thumbnails`); o manifesto antigo vale e a página antiga está intacta. Depois do passo 7 e antes do 9, os arquivos antigos é que estão fora do manifesto e saem do mesmo jeito. `os.replace` do manifesto é atômico, então vale o antigo ou o novo, nunca um pedaço. Não existe estado com tamanho divergente.

### 6.5 Corte automático (`detect_paper_region` e o mapeamento)

Entrada: o preview em tons de cinza, lado maior de até `PREVIEW_MAXIMUM_EDGE_PIXELS = 400` (decodificação reduzida com `draft`, portanto barata mesmo a 1200 dpi: 21 ms medidos para 10200 × 14032 → 1275 × 1754 → 291 × 400). Constantes, todas nomeadas:

| Constante | Valor | Para quê |
|---|---|---|
| `BORDER_WIDTH_RATIO` / `MINIMUM_BORDER_WIDTH_PIXELS` | 0,015 do lado maior / 2 px | faixa da borda usada como amostra do fundo |
| `BACKGROUND_TOLERANCE_LEVELS` | 20 | pixel da borda a até ±20 níveis da mediana conta como fundo |
| `MINIMUM_BACKGROUND_BORDER_SHARE` | 0,6 | fração mínima da borda que precisa parecer fundo |
| `FOREGROUND_DIFFERENCE_LEVELS` | 40 | diferença para o fundo a partir da qual o pixel é "papel" |
| `NOISE_FILTER_SIZE` | 7 | `MedianFilter` sobre a máscara (apaga pontos e traços finos) |
| `MINIMUM_LINE_COVERAGE` | 0,05 | fração de uma linha ou coluna da máscara para ela fazer parte do papel |
| `MINIMUM_REGION_SHARE` | 0,10 | região menor que isso do vidro: sem corte |
| `MAXIMUM_REGION_SHARE` | 0,95 | região maior que isso do vidro: é a imagem inteira, sem corte |
| `CROP_MARGIN_RATIO` | 0,01 do lado maior da imagem inteira (cerca de 3 mm) | folga em volta da região, para não cortar a borda da folha |

Passos:

1. **Fundo:** concatena os histogramas das quatro faixas da borda (cima, baixo, e as laterais sem os cantos já contados) e toma a **mediana** como `background_level`.
2. **Borda confiável:** a fração de pixels da borda em `[background_level - 20, background_level + 20]` precisa ser pelo menos 0,6. Senão devolve `None` (a folha encosta em boa parte da borda, ou há degradê forte: não dá para saber o que é fundo).
3. **Máscara:** `preview.point(tabela)` com `tabela[nível] = 255 se abs(nível - background_level) > 40, senão 0` (uma tabela de 256 posições, sem laço por pixel).
4. **Limpeza:** `mask.filter(ImageFilter.MedianFilter(7))`.
5. **Perfis:** `mask.reduce((1, altura))` dá a cobertura de cada coluna (imagem largura × 1) e `mask.reduce((largura, 1))` a de cada linha (1 × altura); `point` com limiar `0,05 * 255` e `getbbox()` de cada um dão primeira e última coluna e linha com cobertura. Isso aproxima "a maior área" sem componentes conexos (que o Pillow não tem) e ignora riscos soltos.
6. **Região:** `PixelRegion(left, top, right, bottom)`. Se a máscara não tem nenhuma linha ou coluna acima do limiar: `None`.
7. **Plausibilidade:** `area / (largura * altura)` abaixo de 0,10 ou acima de 0,95: `None`.

Mapeamento para a imagem inteira (no `ImageAdjustmentService`): `region.scaled(preview_size, full_size).grown_within(margin, full_size)` com `margin = round(0.01 * max(full_size))` (140 px a 1200 dpi, 35 px a 300 dpi).

Os dois casos reais:

- **(a) Tampa aberta ou fundo escuro com folha mais clara** (o seu print da capa do livro com moldura escura): a borda é escura e homogênea, a capa difere mais de 40 níveis, a máscara vira um bloco sólido e o corte vai até a capa mais a folga. Partes da capa quase tão escuras quanto o fundo ficam dentro do bloco porque o perfil usa a primeira e a última linha e coluna, não o contorno.
- **(b) Tampa branca com folha branca:** a diferença fica abaixo de 40 níveis, a máscara sai vazia e o resultado é `None`: a imagem fica inteira (os bytes do scanner, se não houver giro). O mesmo vale para uma folha A4 de texto que cobre o vidro: a borda é branca e homogênea, mas os blocos de texto, reduzidos a 400 px, ficam cinza-claros e os traços finos somem no filtro mediano.

**Limitações conhecidas** (por isso é opcional e desligado por padrão): uma imagem que preenche o vidro e tem um bloco grande e escuro dentro pode ser cortada para esse bloco; o contraste só é medido em luminosidade (papel amarelo claro sobre fundo cinza claro não é detectado, o que mantém a imagem inteira); não há correção de inclinação (deskew). A região cortada continua sendo um retângulo alinhado aos eixos, então uma folha inclinada leva um pouco de fundo junto.

### 6.6 O pipeline a 1200 dpi

Números medidos com um JPEG sintético 10200 × 14032 em cor (Pillow 13.0.0, esta máquina): decodificar por inteiro 0,14 s; `transpose` 0,25 s; recodificar a 95 cerca de 0,1 s; decodificação reduzida para o preview 0,02 s; uma imagem decodificada ocupa cerca de 430 MB (3 bytes por pixel) e, com a original e a girada vivas ao mesmo tempo, o pico do processo passa de 1 GB. Páginas reais, com ruído, demoram mais para decodificar; a ordem de grandeza continua em segundos, enquanto o scanner leva minutos.

Regras, uma por serviço que decodifica imagem:

1. **Limite de pixels:** `MAXIMUM_SCANNER_IMAGE_PIXELS` (5.4), em um único lugar, chamado no início de `build_container`. Vale para Pillow, `img2pdf`, miniatura, giro e corte.
2. **Miniatura (`ThumbnailService`):** já usa `Image.draft`, então a 1200 dpi decodifica a 1/8 do tamanho. Sem mudança além da constante do lado maior mudar de módulo.
3. **Detecção do corte:** preview reduzido (6.5); nunca decodifica a imagem inteira só para analisar.
4. **Giro e corte:** no máximo duas imagens inteiras vivas ao mesmo tempo (original + cortada, depois cortada + girada), com `close()` explícito de cada etapa antes da seguinte. Pico estimado: cerca de 0,9 GB em cor e 0,3 GB em tons de cinza a 1200 dpi. `MemoryError` vira `ImageAdjustmentFailedError` com a mensagem de 4.5; nada fica pela metade (o que se perde é a página da digitalização, nunca o documento).
5. **Tempo de espera do scanner:** 5.5.
6. **Estimativa de espaço:** 5.4. O aviso de documento grande da interface (mais de 300 páginas ou mais de 1 GiB) continua valendo e a montagem do PDF continua em fluxo (R18); só o consumo por página sobe.
7. **Servidor e navegador:** a digitalização já roda em segundo plano (`202`) e a interface consulta o estado a cada 0,5 s; o trabalho de Pillow roda em `asyncio.to_thread`, que libera o GIL nas partes pesadas, então o servidor continua respondendo durante os minutos de um scan a 1200 dpi.

Não há teste automático a 1200 dpi (cada teste leva menos de 100 ms e uma página dessas tem 430 MB). A verificação é manual com o simulador (T31).

## 7. Compatibilidade

- **`settings.json` antigo** (`output_folder`, `output_format`, `scan_preset`, e opcionalmente `capture_mode`): carrega; `dots_per_inch`/`color_mode` vêm da predefinição, `rotation_degrees` 0, `auto_crop` `false`. O arquivo é regravado no formato novo na primeira mudança de ajuste. `test_composition_root.save_settings_with_output_folder` continua sendo um bom teste dessa leitura (ele não muda).
- **Manifesto de rascunho antigo:** o `format_version` 1 não muda e nada nele é novo; um rascunho de antes do design retoma exatamente como hoje.
- **API:** `PUT /api/settings` de um cliente antigo (só `scan_preset`) funciona (regra 2 de 4.2). `GET /api/settings` ganha campos e mantém `scan_preset`. `POST /api/scans` e `POST /api/document/pages` não mudam de forma. A rota de rotação é nova.
- **Página no navegador:** a página nova é servida pelo mesmo servidor; uma aba aberta de antes do deploy precisa ser recarregada (os campos que ela lê continuam existindo, então nada quebra antes disso).

## 8. Tarefas

Todas em TDD: o teste que falha primeiro, o código depois, `make test` e `make lint` verdes ao fim de cada tarefa. Backend antes da interface; cada tarefa deixa o programa funcionando.

### T23: Domínio dos ajustes

**Arquivos:** `src/digitalizadora/domain/{scan_quality,page_rotation,image_adjustment,pixel_region}.py` (novos); `scan_preset.py`, `scan_request.py`, `application_settings.py`, `document_draft.py`, `errors.py`, `ports.py`; `services/storage_guard_service.py` (só passa a importar `PLATEN_*` de `scan_quality`).
**Interfaces:** 5.2 inteira.
**Testes novos:** `tests/domain/test_scan_quality.py` (as oito resoluções; `is_supported_dots_per_inch`; `pixels_per_page(1200) == 143_085_600`; multiplicador 1 até 600 e 4 a 1200), `test_page_rotation.py` (`turned_clockwise` percorre 0, 90, 180, 270, 0), `test_image_adjustment.py` (`is_active` nos quatro casos), `test_pixel_region.py` (largura, altura, área, `scaled` com arredondamento, `grown_within` limitado), `test_scan_preset.py` (+`matching`: as três predefinições e `None` para 400 dpi), `test_document_draft.py` (+`with_page_replaced`: mesma posição, `PageNotFoundError`, marcas limpas).
**Testes que mudam:** `tests/domain/test_application_settings.py`, `tests/domain/test_immutable_models.py` (construções com `scan_settings`; `to_scan_request` carrega o ajuste; os novos modelos são imutáveis).

### T24: Ajustes salvos e API de ajustes

**Arquivos:** `repositories/json_application_settings_repository.py`, `services/application_settings_service.py`, `services/application_state_service.py`, `controllers/{settings_body,settings_controller,state_controller,document_controller}.py`, `composition_root.py` (ajustes padrão), `services/document_draft_service.py` + `services/document_draft_store.py` (assinaturas com `adjustment` opcional, 5.4), `services/document_page_capture.py`, `services/scan_output_service.py`, `services/storage_guard_service.py` (terceiro parâmetro e fator).
**Interfaces:** 4.1, 4.2, 5.3 (JSON), 5.4 (`SettingsUpdate`, guarda de espaço), 5.6 (corpo, controlador).
**Testes novos:** leitura de `settings.json` antigo; par válido; par inválido com `scan_preset` válido; par inválido sem `scan_preset` (arquivo inutilizável → padrão); rotação e corte inválidos mantêm o resto; aviso no log uma vez por valor; gravação sem `scan_preset`; regras 1 a 4 de 4.2; ida e volta (o corpo do `GET` serve de corpo do `PUT`); `add_page` do controlador passa `settings.scan_settings` e `settings.adjustment`; estimativa com e sem ajuste.
**Testes que mudam:** seção 9 (itens de ajustes).

### T25: Detecção do papel, serviço de ajuste e limite de pixels

**Arquivos:** `services/{paper_region_detection,image_adjustment_service,image_pixel_limit}.py` (novos).
**Interfaces:** 5.4 (`detect_paper_region`, `ImageAdjustmentService.adjust`, `raise_decompression_limit_to_scanner_size`).
**Testes novos (imagens pequenas, cada um abaixo de 100 ms):** `tests/services/test_paper_region_detection.py` (fundo escuro com folha no meio; folha no canto; folha clara sobre tampa escura e foto escura sobre tampa branca; fundo branco com folha branca → `None`; imagem uniforme → `None`; região menor que 10% → `None`; região de 95% ou mais → `None`; borda não homogênea → `None`; traços finos de texto sobre fundo branco → `None`; ruído de ±5 níveis ainda acha a folha), `tests/services/test_image_adjustment_service.py` (sem ajuste devolve o mesmo objeto; os quatro giros com uma imagem assimétrica, dimensões trocadas em 90 e 270; corte reduz as dimensões; corte sem região devolve os bytes originais; corte antes de giro; subamostragem e `dpi` mantidos; `MemoryError` → `ImageAdjustmentFailedError`; bytes corrompidos → `ScanFailedError`), `tests/services/test_image_pixel_limit.py` (restaura `Image.MAX_IMAGE_PIXELS` com `monkeypatch`; o valor é 150.239.880; 143.126.400 (a imagem real do vidro a 1200 dpi) fica abaixo).

### T26: Pipeline de codificação com ajuste

**Arquivos:** `services/master_jpeg_service.py` (novo), `services/scan_encoder.py`, `services/thumbnail_service.py` (a constante do lado maior), `composition_root.py` (`MasterJpegService`, `raise_decompression_limit_to_scanner_size()` no início de `build_container`, `_SharedServices`).
**Interfaces:** 5.4 (`MasterJpegService`, `ScanEncoder`), 5.7.
**Testes novos:** `tests/services/test_master_jpeg_service.py` (densidade correta depois do giro; ajuste aplicado antes da densidade; sem ajuste igual ao caminho de hoje), em `test_scan_encoder.py` (giro e corte chegam ao JPEG, à miniatura e ao PDF; PDF com tamanho físico da região cortada), em `test_scan_output_service.py` e `test_document_page_capture.py` (o ajuste do pedido chega ao codificador; `size_in_bytes` da página é o do JPEG ajustado), `tests/integration/test_adjustments_flow.py` (simulador a 75 dpi, para ficar rápido: modo Rápido com giro de 90° e dimensões trocadas; modo Documento com corte contra a tampa escura; documento com duas páginas e ajustes diferentes finaliza num PDF).
**Testes que mudam:** `tests/services/test_scan_encoder.py` (construtor e importação da constante), `tests/services/test_document_page_capture.py` (construtor), `tests/fakes/document_service_parts.py` (construtores).

### T27: Espera do scanner por resolução e simulador de tampa escura

**Arquivos:** `infrastructure/escl/escl_scanner_gateway.py`, `composition_root.py` (só o comentário de `SCANNER_READ_TIMEOUT_SECONDS`), `simulator/fake_escl_scanner_app.py`, `simulator/__main__.py`.
**Interfaces:** 5.5, 5.8.
**Testes novos:** em `tests/infrastructure/test_escl_scanner_gateway.py`: 1200 dpi espera quatro vezes o limite base antes de `ScanTimedOutError`; 600 dpi e 300 dpi mantêm o limite base; a leitura de `NextDocument` a 1200 dpi é `max(180, 4 * base)`; em `tests/simulator/test_fake_escl_scanner_app.py`: a página `DARK` tem fundo escuro nas bordas e folha clara dentro, e a página `WHITE` é a de hoje.
**Testes que mudam:** nenhum (os de tempo de hoje usam 300 dpi, multiplicador 1).

### T28: Girar uma página do rascunho (servidor)

**Arquivos:** `repositories/file_system_document_draft_repository.py` (`read_page_file`), `services/document_draft_store.py` (`StoredPage`, `read_page_content`, `ensure_capacity_for_replacement`, `replace_page`), `services/document_page_rotator.py` (novo), `services/document_draft_service.py` (`page_rotator`, `rotate_page`), `controllers/document_controller.py` (rota), `controllers/error_message_catalog.py` (`image_adjustment_failed`), `composition_root.py` (rotator).
**Interfaces:** 4.4, 5.3, 5.4, 5.6, 6.4.
**Testes novos:** repositório (`read_page_file` existente, ausente, erro de disco); store (`replace_page`: mesma posição, identificador novo, tamanho do manifesto igual ao do arquivo novo, arquivos antigos apagados, snapshot com `revision + 1`, falha em `save_manifest` apaga só os arquivos novos e deixa o rascunho; `read_page_content` danificado; capacidade); rotator (giro de 90° horário, miniatura nova, página que não decodifica → `DamagedDocumentPageError`); serviço (`rotate_page` durante digitalização → `ScanAlreadyRunningError`; espera pelo lock; queda simulada entre o passo 5 e o 7 e entre o 7 e o 9 → a retomada limpa os arquivos sem dono e o rascunho fica como estava, em `test_document_draft_recovery.py`); controlador (`POST .../rotation` → `200` com o corpo do documento; `404` e `409` do quadro de 4.4; `damaged_document_page` leva `page_identifier`); catálogo.
**Testes que mudam:** `tests/fakes/stub_document_draft_service.py` (`add_page(settings, adjustment)`, `rotate_page`, `describe_draft_storage`), `tests/fakes/document_service_parts.py` (coletivo com `page_rotator`), `test_error_message_catalog.py` (as duas mensagens da seção 3 e a nova).

### T29: Interface, parte 1: qualidade, giro e corte nos ajustes

**Arquivos:** `web/static/scan-quality-policy.js` (novo), `index.html`, `application.css`, `application.js`, `document-page-policy.js` (sai a duração por predefinição, entra `dots_per_inch`), `document-panel.js` (só `dots_per_inch`).
**Interfaces:** 5.9 (política, ids, eventos), 3 (textos, avisos).
**Testes novos:** `tests/web/test_scan_quality_policy.py` com seu harness (`describe_expected_scan_duration` nas quatro faixas; `describe_resolution_warning`: `null` a 300, texto de 600, texto de 1200; `choose_preset_option` com e sem `scan_preset`; `build_preset_changes`; `parse_rotation_degrees` com valores válidos e inválidos); cenários da página em `test_scan_page_behaviour.py` (as oito resoluções na lista; mudar a resolução envia `{dots_per_inch}` e mostra o aviso; escolher uma predefinição envia o pacote com `null`s; "Personalizada" aparece quando `scan_preset` vem `null`; a lista Girar e a caixa de corte enviam seus campos; Espaço na lista Girar e na caixa não digitaliza).
**Testes que mudam:** seção 9 (itens da interface).

### T30: Interface, parte 2: Salvar no lugar de Finalizar e Girar na miniatura

**Arquivos:** `index.html`, `application.css`, `document-page-policy.js`, `document-panel.js`, `application.js` (rótulos).
**Interfaces:** 3 (tabela de textos), 5.9 (`save_document_button`, `rotate_button`, `ROTATE`, `describe_page_rotation`).
**Testes novos:** em `test_document_page_policy.py` (foco depois de `ROTATE` iniciado por teclado e por mouse; `describe_page_rotation`), em `test_document_panel_edits.py` (clicar em Girar envia `POST .../rotation`, anuncia o giro, a miniatura nova usa o identificador novo e o foco volta ao Girar da mesma posição; Girar desabilitado enquanto há digitalização ou edição; erro `damaged_document_page` marca a página), em `test_document_panel_keyboard.py` (Enter ainda abre a confirmação do botão Salvar; Enter com o foco no botão Salvar o aciona sem duplicar).
**Testes que mudam:** seção 9 (itens da interface).

### T31: Documentação e verificação final

**Arquivos:** `README.md` (seções de qualidade, de giro e corte, de "Salvar"), `docs/acceptance-checklist.md` (itens novos, abaixo), este spec marcado como implementado.
**Verificação com o simulador (não toca na impressora; porta e `HOME` próprios):** num terminal `make simulator` (porta 8080 já é a do Makefile; use `python -m digitalizadora.simulator` com outra porta se a 8080 estiver ocupada); em outro, `HOME="$(mktemp -d)" DIGITALIZADORA_PORT=8791 DIGITALIZADORA_SCANNER_ADDRESS=http://127.0.0.1:8080/eSCL .venv/bin/python -m digitalizadora`. Conferir: as oito resoluções; 1200 dpi mostra o aviso; uma digitalização a 1200 dpi pelo simulador (a imagem de 143 MP e o corte e giro nela, sem aviso `DecompressionBombWarning` no log e sem erro de memória; anotar o pico de memória e o tempo); giro de 180° no modo Rápido; corte com a tampa escura (exige o simulador em modo `DARK`; rodar `DIGITALIZADORA_SIMULATOR_LID_BACKGROUND=dark make simulator`); Girar na miniatura; Salvar e Enter.
**Itens novos do checklist:** A (simulador): resoluções, avisos, giro, corte, Girar na miniatura, Salvar/Enter, "Salvar pasta". B (impressora real; **só você roda**): medir o tempo de 400 dpi e de 1200 dpi (hoje são estimativas), conferir se 1200 dpi chega sem estourar o limite de espera, comparar o tamanho do arquivo com e sem giro (para calibrar `ADJUSTED_PAGE_SIZE_FACTOR`) e repetir o caso da capa do livro com 180°.

## 9. Testes existentes que precisam mudar (lista exata)

**Construção de `ApplicationSettings` (o terceiro argumento passa de `ScanPreset.X` para `ScanPreset.X.settings`, e o campo se chama `scan_settings`):**
`tests/domain/test_application_settings.py`, `tests/domain/test_immutable_models.py` (linha 44), `tests/repositories/test_json_application_settings_repository.py` (linhas 14 a 17, 111, 133 a 136), `tests/repositories/test_file_system_scan_output_repository.py` (linha 44), `tests/fakes/test_in_memory_settings_repository.py` (linhas 8 e 9), `tests/fakes/document_service_parts.py` (linha 149), `tests/controllers/test_application_factory.py` (linha 60), `tests/controllers/test_settings_controller.py` (linhas 19 e 84), `tests/controllers/test_scan_controller.py` (linha 22), `tests/controllers/test_state_controller.py` (linha 24), `tests/controllers/test_document_controller.py` (linha 45), `tests/services/test_application_settings_service.py` (linhas 18, 82), `tests/services/test_application_state_service.py` (linhas 25, 97, 146, 149, 159), `tests/services/test_document_finalizer.py` (linhas 80 e 225).

**Quem lê `.scan_preset` do objeto de ajustes:** `tests/services/test_application_settings_service.py` linha 188 (`saved.scan_preset` → `saved.scan_settings`); `tests/controllers/test_state_controller.py` linha 214 (o stub registra `describe_draft_storage(settings, adjustment)`) e `tests/controllers/test_document_controller.py` linha 151 (`add_page` recebe o par `(settings, adjustment)`).

**Formato do JSON que os testes travam:**
`tests/repositories/test_json_application_settings_repository.py::test_save_writes_the_documented_json_shape` (sem `scan_preset`; com `dots_per_inch`, `color_mode`, `rotation_degrees`, `auto_crop`); `tests/controllers/test_settings_controller.py` (linhas 28, 64 e `test_put_settings_returns_the_new_settings`: corpo de `GET` e de `PUT` com os campos novos; `VALID_BODY` continua válido, pois só tem `scan_preset`); `tests/controllers/test_state_controller.py` (linha 150: o objeto `settings`); `tests/test_composition_root.py` (linha 107: `test_state_endpoint_reports_default_settings`, que ganha os campos novos); `tests/integration/test_scan_flow.py` (linha 126: o `settings` do estado depois do `PUT` com `scan_preset`, que continua sendo aceito).

**Construtores trocados:** `tests/services/test_scan_encoder.py` (linha 31 e a importação de `THUMBNAIL_MAXIMUM_EDGE_PIXELS`, que passa a vir de `thumbnail_service`), `tests/services/test_document_page_capture.py` (linha 58), `tests/fakes/document_service_parts.py` (linhas 180 e 185: `ScanEncoder(MasterJpegService(...), ...)` e `DocumentDraftCollaborators(..., page_rotator)`).

**Fakes:** `tests/fakes/stub_document_draft_service.py` (`add_page`, `describe_draft_storage`, `rotate_page`).

**Textos (finalizar → salvar):** `tests/controllers/test_error_message_catalog.py` (linhas 50 e 53), `tests/web/test_document_page_policy.py` (linhas 11, 314 a 317, 405 a 410, e o bloco 298 a 311 de `describe_expected_scan_duration`, que sai e vai para o novo teste da política de qualidade), `tests/web/test_document_panel_behaviour.py` (linhas 8, 112 a 118; as linhas 133 e 191 trocam `scan_preset: "document"` por `dots_per_inch: 300` no resumo), `tests/web/test_document_panel_keyboard.py` (linha 108: `Salvar o PDF com 3 páginas?`), `tests/web/test_document_panel_edits.py` (linha 10: `…salvo ou alterado…`).

**Página, ids e scripts:** `tests/web/test_static_assets.py` (`SCRIPT_FILE_NAMES` com seis arquivos na ordem de 5.9; `test_page_loads_the_five_scripts_in_dependency_order` passa a ser "six"; `DOCUMENT_ELEMENT_IDENTIFIERS`: `finalize-document-button` → `save-document-button`; a lista de rotas do painel ganha `/rotation`; `test_page_offers_every_format_preset_and_mode` e `test_quality_options_use_the_new_names` continuam e ganham as opções de resolução e cor; um teste novo confirma que as três predefinições do HTML têm os mesmos pares que `ScanPreset`, lendo `index.html`), `tests/web/fake-browser.js` (linhas 15 a 19: a lista de scripts), `tests/web/document-page-policy-harness.js` (linha 11 e o `scan_preset` da linha 49), `tests/web/document-panel-harness.js` (linha 33 e o id `finalize-document-button` nas linhas 220, 380 e 387), `tests/web/scan-page-harness.js` (linha 17: o objeto de ajustes com os campos novos).

**Não mudam** (por desenho): `tests/hardware/test_real_printer.py` (usa só `ScanPreset.X.settings`), `tests/repositories/test_document_manifest_codec.py` e `tests/repositories/test_file_system_document_draft_repository.py` (além de acrescentar `read_page_file`), `tests/infrastructure/test_escl_protocol.py`, todos os testes de tempo do gateway a 300 dpi, `tests/test_composition_root.py::save_settings_with_output_folder` (é o teste da leitura do arquivo antigo), e a rota `/api/document/finalize` em qualquer teste.

## 10. Riscos e pontos em aberto

- **O significado de "Salvar"** (seção 1): tratado como renomear o botão do documento. Se não for isso, é só T30.
- **Limiares do corte** (6.5) vieram de imagens sintéticas e do seu relato do caso (a); não tive o print da capa. Antes de dar a T25 por fechada, rodar o detector sobre ao menos duas digitalizações reais suas (uma com tampa aberta, uma com tampa fechada) e ajustar `FOREGROUND_DIFFERENCE_LEVELS` e `MINIMUM_BACKGROUND_BORDER_SHARE` se preciso; as constantes existem para isso.
- **Tempos a 400 e 1200 dpi são estimativas** (não toquei na impressora). O limite de espera de 20 minutos a 1200 dpi é folgado de propósito. Se a impressora levar mais que isso, o app mostra `scan_timed_out` e a digitalização é perdida.
- **A impressora fica em `Processing` depois de entregar a página** por 4 a 5 s (Gate 0, a 300 e 600 dpi). A 1200 dpi pode ser mais; `busy_wait_seconds` (30 s) é o limite de hoje para a próxima digitalização e pode precisar de um valor por resolução se isso aparecer.
- **Recodificar a 95 pode engordar o arquivo** em relação ao JPEG do scanner (a qualidade do scanner não é conhecida); o fator 2 de `ADJUSTED_PAGE_SIZE_FACTOR` é um palpite conservador a calibrar no item B do checklist.
- **Memória a 1200 dpi** (cerca de 0,9 GB em cor durante giro ou corte) é segura em um Mac com 8 GB ou mais, mas não foi medida com uma página real e com outros programas abertos; o plano B é a mensagem `image_adjustment_failed`.
- **Documentos de muitas páginas a 1200 dpi** ficam enormes (cerca de 17 MB por página em cor): 100 páginas passam de 1,7 GB de PDF e de memória na hora de salvar. O aviso de "documento grande" (mais de 1 GiB) já avisa; a montagem em fluxo e o erro `document_too_large` já existem.
- **`BlackAndWhite1` e girar à esquerda numa página do documento com um só clique** ficam como próximos passos possíveis (A12 e A3).

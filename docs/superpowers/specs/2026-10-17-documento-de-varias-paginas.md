# Documento de várias páginas: design

**Data:** 2026-10-17 · **Status:** decisões tomadas; contratos na seção 6 (refinamentos R1 a R20 em 6.0, os de R12 em diante vindos da segunda revisão cética), tarefas T15 a T22 (com a T18 dividida em 18a, 18b e 18c) na seção 7 e testes na seção 8, prontos para virar plano · **Complementa:** [spec principal](2026-10-13-digitalizadora-design.md)

## 1. O que você pediu (md.md, acrescentado em 2026-10-17)

> além da opção scanner único e rápido eu quero uma opção para criar documento pdf com várias páginas onde eu vá indo escaneando (clicando em um botão no software e adicionando o pdf no mesmo documento) e ao final, clicar no botão finalizar e isso gerar um documento pdf com todos os documentos escaneados da sessão

Respostas suas em 2026-10-17:

- **Quando:** já nesta versão, junto com o modo rápido.
- **Controles:** adicionar página, finalizar, **descartar a última página**, **cancelar o documento**, **miniaturas das páginas**, **nome do documento**, **visão geral de cima (grade com todas as páginas)**, **reordenar as páginas arrastando e soltando** e **excluir qualquer página**.
- **Queda do app ou do Mac:** **retomar de onde parou**.

## 2. Decisões (tomadas pelo assistente; corrija se quiser)

| # | Decisão | Por quê | Alternativa descartada |
|---|---|---|---|
| M1 | Dois modos na mesma tela: **Rápido** (o MVP atual: 1 clique = 1 arquivo PDF ou JPG) e **Documento** (várias páginas → 1 PDF). O modo escolhido fica salvo nos ajustes. | Uma tela só, como no spec; o modo rápido continua igual. | Duas páginas separadas |
| M2 | **Um único documento em andamento por vez.** Começa sozinho na primeira "Adicionar página"; o nome é opcional e pode ser trocado até finalizar. | Simples de entender e de retomar. | Vários rascunhos abertos |
| M3 | O documento é sempre **PDF**. Cada página é o JPEG do scanner (mestre), com a resolução do preset da hora em que foi digitalizada; o PDF é montado com `img2pdf` **sem recomprimir**, na ordem atual. | Mesmo pipeline do MVP (D4). | PDF da impressora; Pillow |
| M4 | **Rascunho em disco, à prova de queda:** pasta `<data_directory>/drafts/current/` com um JPEG por página (`page-<identificador>.jpg`), uma miniatura por página (`thumbnail-<identificador>.jpg`) e `manifest.json` (nome, preset, criado em, ordem das páginas). Cada página é gravada de forma atômica **antes** de o manifesto ser trocado de forma atômica (`AtomicFileWriter.replace_file`). Ao abrir, páginas listadas sem arquivo são ignoradas com aviso no log, e arquivos fora do manifesto também. | Retomar de onde parou sem banco de dados; uma pasta, um manifesto. | SQLite (roadmap antigo da Fase 2): desnecessário para um único rascunho |
| M5 | O rascunho fica no **disco interno** (`data_directory`, normalmente `~/Library/Application Support/Digitalizadora`), não na pasta de saída: assim não some se o disco externo sair. A guarda de espaço confere o disco do rascunho antes de cada página e a pasta de saída antes de finalizar (soma dos JPEGs + margem). | O rascunho sobrevive à troca de pasta de saída e ao disco externo desconectado. | Rascunho na pasta de saída |
| M6 | **Finalizar:** monta o PDF, grava na pasta de saída sem sobrescrever e só então apaga o rascunho. Para não gerar PDF duplicado se cair entre gravar e apagar, o manifesto registra o nome do PDF gravado antes de apagar; ao abrir, um rascunho já finalizado cujo PDF existe é apagado sem perguntar. | Nunca perder páginas e nunca duplicar. | Apagar antes de confirmar a gravação |
| M7 | **Nome do arquivo:** sem nome → o automático `AAAA-MM-DD_NNNNN.pdf` (mesma sequência do modo rápido); com nome → `<nome>.pdf`, com o nome limpo (sem `/`, `:`, caracteres de controle, ponto inicial; espaços nas pontas removidos; até 120 caracteres; letras acentuadas permitidas) e, se já existir, `<nome> (2).pdf`, `(3)`… Nunca sobrescreve. O título do PDF é o nome (ou "Digitalização <data e hora>"). | O usuário reconhece o documento pelo nome. | Exigir nome |
| M8 | **Reordenar:** a interface manda a ordem completa (lista de identificadores); o servidor só aceita uma permutação exata das páginas atuais (senão `422 invalid_page_order`). Arrastar e soltar (HTML5) **e** botões "mover para a esquerda/direita" para teclado e acessibilidade. | Arrastar não é acessível sozinho; a ordem completa evita corrida entre pedidos. | Mover uma posição por pedido |
| M9 | **Concorrência:** "Adicionar página" usa o mesmo controle de digitalização em curso do modo rápido (`409 scan_already_running`); editar o rascunho (excluir, reordenar, renomear, cancelar, finalizar) durante uma digitalização responde `409 scan_already_running`; todas as mudanças no rascunho passam por um único lock assíncrono. | Nunca corromper o manifesto. | Permitir edição durante a digitalização |
| M10 | **Teclado:** Espaço = adicionar página (modo Documento) ou digitalizar (modo Rápido); Backspace = descartar a última (com o foco fora de campos de texto); Enter = finalizar (pede confirmação); Esc fecha confirmações. Cancelar o documento sempre pede confirmação. | Volume grande, mãos livres. | — |
| M11 | Sem limite rígido de páginas; aviso na interface acima de 300 páginas ("documento grande: finalizar pode levar alguns segundos"). A montagem do PDF roda em thread (`asyncio.to_thread`). | img2pdf é linear e não recomprime. | Dividir PDF automaticamente (fica para depois) |


## 3. Interface (acréscimos à seção 7 do spec)

- Seletor de modo no topo: **Rápido | Documento**.
- No modo Documento:
  - campo "Nome do documento (opcional)";
  - botão grande **Adicionar página** (Espaço);
  - **grade** de miniaturas na ordem, cada uma com o número da página, botão excluir (×), botões ◀ ▶ e "Mover para…" (posição digitada); arrastar e soltar para reordenar;
  - barra com "N páginas · ~X MB", **Descartar última** (Backspace), **Cancelar documento** e **Finalizar PDF** (Enter);
  - linha de espaço do **disco do Mac**, onde as páginas ficam guardadas (não a da pasta de saída);
  - depois de finalizar: "Pronto! Salvo como <arquivo>.pdf (N páginas)".
- Ao abrir o app com um rascunho pendente, o modo Documento aparece com as páginas e um aviso que diz o que a retomada fez (páginas recuperadas, páginas perdidas, pasta posta de lado, PDF talvez já salvo); detalhes em 6.7.
- No modo Rápido com um documento em andamento: uma linha "Documento em andamento: N páginas" com o botão "Voltar ao modo Documento".
- PDF/JPG e o painel "Último arquivo" só aparecem no modo Rápido.

## 4. API (acréscimos à seção 6.5; todas com o mesmo guarda de `Host` e cabeçalho)

| Método e caminho | Faz | Respostas |
|---|---|---|
| `GET /api/document` | Rascunho atual, aviso de retomada e último PDF finalizado | `200` corpo do documento (6.5) |
| `POST /api/document/pages` | Digitaliza e acrescenta uma página (em segundo plano, como `POST /api/scans`) | `202`; `409 scan_already_running`; `409 document_busy`; resultado por `/api/state` e `/api/document` |
| `DELETE /api/document/pages/last` | Descarta a última | `200` corpo do documento; `404 no_open_document`; `409` |
| `DELETE /api/document/pages/{page_identifier}` | Exclui a página | idem, mais `404 page_not_found` |
| `PUT /api/document/page-order` | `{"page_identifiers": [...]}` | `200`; `422 invalid_page_order`; `409` |
| `PUT /api/document/name` | `{"name": "..."}` (vazio = automático) | `200`; `422 invalid_document_name` |
| `POST /api/document/finalize` | Monta e grava o PDF | `200 {"file_name", "output_folder", "page_count", "size_in_bytes"}`; `404 no_open_document`; `422 empty_document`; `409`; `409 damaged_document_page`; erros de pasta/espaço como no modo rápido |
| `DELETE /api/document` | Cancela (apaga o rascunho) | `200` corpo do documento; `409` |
| `GET /api/document/pages/{page_identifier}/thumbnail` | Miniatura | `image/jpeg` ou `404` |

`/api/state` ganha o modo nos ajustes (`settings.capture_mode`: `"single"` ou `"document"`) e o resumo `document` (sessão, revisão, contagem, tamanho e espaço do disco do rascunho).

Os formatos exatos, os status de erro e a ordem em que são conferidos estão na seção 6.5, que prevalece sobre esta tabela (R1, R8, R10, R11, R17, R18 e R20).

## 5. Erros novos (seção 4.4)

`no_open_document`, `page_not_found`, `invalid_page_order`, `invalid_document_name`, `empty_document`, cada um com mensagem em português no catálogo. Mais três pelo refinamento R7: `draft_storage_unavailable`, `insufficient_draft_storage` e `document_assembly_failed`; e quatro pelos refinamentos R12, R17 e R18: `draft_folder_in_use`, `document_busy`, `damaged_document_page` e `document_too_large` (textos na seção 6.5).

## 6. Contratos (autoridade para as Tarefas 15 a 22)

Mesmo formato da seção 6 do spec principal: assinaturas, não implementações; caminhos relativos a `src/digitalizadora/`. Valem as convenções da seção 5 do spec principal: no máximo 3 parâmetros por função, método ou construtor (sem contar `self`; campos de dataclass não contam), nada de parâmetro booleano, nada de abreviação, injeção por construtor, só `composition_root.py` instancia classes concretas, `Clock` injetado, camadas controllers → services → domain ← repositories/infrastructure, mensagens ao usuário em português e código em inglês. **Qualquer mudança de nome ou assinatura é feita aqui primeiro.** Onde esta seção refina uma decisão M1 a M11, o refinamento está em 6.0 e prevalece sobre as seções 2 a 5.

Injeção por construtor, um caso a registrar: `ScanService.scan_document_page(request, page_capture)` recebe o destino por parâmetro (é o mesmo método genérico do modo rápido com outro destino), mas ninguém o chama assim fora da raiz: `composition_root.py` liga o destino uma vez com `functools.partial` e o `DocumentDraftService` recebe a função pronta (`page_scanner`) pelo construtor. Assim o serviço do documento não depende de `DocumentPageCapture`.

### 6.0 Refinamentos das decisões (feitos ao escrever os contratos e na revisão)

| # | Refinamento | Por quê |
|---|---|---|
| R1 | O rascunho **não tem preset próprio**: cada página guarda `dots_per_inch` e `color_mode` da hora em que foi digitalizada (M3). O manifesto e o `GET /api/document` não têm `scan_preset` no nível do documento. | Com presets misturados, um preset do documento seria enganoso. |
| R2 | O PDF do documento usa a **densidade JFIF de cada página** (`img2pdf.default_layout_fun`), não um dpi único: páginas de 300 e 600 dpi saem com o mesmo tamanho físico. O `build_pdf` do modo rápido não muda. | `get_fixed_dpi_layout_fun` aplica um dpi a todas as páginas e deixaria a página de 600 dpi com o dobro do tamanho. |
| R3 | Um rascunho guardado **sempre tem pelo menos 1 página**. Excluir ou descartar a única página que resta apaga o rascunho (a resposta tem `"document": null`); o nome digitado continua no campo da interface e é reenviado quando a próxima primeira página chegar. **Só nesse caso:** finalizar ou cancelar limpa o campo (6.7). | Elimina "documento recuperado: 0 páginas" e o estado "nome sem páginas", sem levar o nome de um documento para o seguinte. |
| R4 | A limpeza do nome (M7) troca por `-` também `\ * ? " < > \|` (além de `/` e `:`), tira pontos e espaços do fim e um `.pdf` final digitado, normaliza para NFC e limita a 200 bytes UTF-8 além dos 120 caracteres. Nome comprido demais é **recusado** (`422 invalid_document_name`), nunca cortado em silêncio. | A pasta de saída recomendada é um disco externo, quase sempre exFAT, que recusa esses caracteres; o APFS limita o nome a 255 bytes. |
| R5 | *(Substituído por R14.)* | — |
| R6 | *(Substituído por R15.)* | — |
| R7 | Três códigos de erro além dos cinco da seção 5: `draft_storage_unavailable` e `insufficient_draft_storage` (o rascunho fica no disco interno, e as mensagens do modo rápido mandariam o usuário olhar a pasta de saída) e `document_assembly_failed` (uma página guardada não pôde ser lida como imagem ao montar o PDF). | Mensagem certa para cada lugar. |
| R8 | "O resultado da última página acrescentada" em `/api/state` é o resumo `document` (sempre um objeto: `draft_session`, `revision`, `page_count`, `estimated_size_in_bytes`, `draft_storage`); quando a sessão ou a `revision` muda, a interface relê `GET /api/document`. Falhas ao acrescentar continuam em `last_error`, como no modo rápido. Páginas acrescentadas contam em `scans_completed`, mas não mudam `last_result` nem a miniatura do modo rápido. | Um só mecanismo para qualquer mudança no rascunho, inclusive feita em outra aba. |
| R9 | *(Refinado por R17.)* `POST /api/document/pages` responde 409 também quando outra mudança no rascunho está em curso (por exemplo, finalizar 300 páginas). As edições esperam o lock (são curtas) e só respondem 409 se houver digitalização. | Evita aceitar (202) uma página que só começaria depois de uma finalização. |
| R10 | Finalizar é síncrono (a resposta traz o resultado), então os erros de pasta e de espaço viram status HTTP: `503` para `output_folder_unavailable` e `draft_storage_unavailable`, `507` para `insufficient_storage` e `insufficient_draft_storage`, com o corpo `{"code","message"}` de sempre. | No modo rápido esses erros chegam por `/api/state`; aqui chegam na própria resposta. |
| R11 | Corpo malformado nas rotas novas responde com o código da rota (`invalid_page_order` em `PUT /api/document/page-order`, `invalid_document_name` em `PUT /api/document/name`), não com `invalid_settings`. | "Ajustes inválidos." não explica um nome ou uma ordem recusada. |
| R12 | **Um único processo escreve em `drafts/`.** Na partida, antes da retomada, o repositório pega um `fcntl.flock(LOCK_EX \| LOCK_NB)` em `<data_directory>/drafts/.owner-lock` e mantém o arquivo aberto até o processo terminar. Se outro processo já o tem: `DraftFolderInUseError` e o app sai com "O Digitalizadora já está aberto em outra janela do Terminal…" (código de saída 1). A mensagem de porta em uso deixa de sugerir uma segunda cópia. | Duas cópias (por exemplo em portas diferentes) com a mesma pasta de dados perderiam páginas confirmadas: cada uma tem o seu lock e o seu snapshot em memória, e a retomada de uma apagaria como órfãos os arquivos da outra. |
| R13 | **Só um manifesto ilegível põe a pasta de lado.** Qualquer outra falha na retomada deixa `current/` como estava, sem rascunho nesta execução, e bloqueia novas páginas com `draft_storage_unavailable` até a próxima abertura (que tenta de novo). Falha ao regravar o manifesto na retomada não é fatal: o rascunho fica em memória e o manifesto no disco continua um superconjunto. O que a retomada fez vai para a interface (`recovery`, R20). | Um erro de disco passageiro ou um disco cheio não pode tirar do app um rascunho válido, e páginas sumidas não podem sumir em silêncio. |
| R14 | **O app só apaga o que sabe ser descartável:** temporários e arquivos de página/miniatura que nunca foram confirmados (fora de um manifesto legível, ou sem manifesto). Página confirmada com tamanho diferente do manifesto vai para uma pasta `set-aside-…`, não para o lixo. Arquivos de nome desconhecido (por exemplo `.DS_Store` do Finder) nunca são apagados nem movidos, nem por `delete_draft`. A retomada e a primeira página de um rascunho novo classificam uma sobra pela mesma regra (6.6.8). | M6 ("nunca perder páginas"); e sobras de um cancelamento não viram cópias permanentes de documentos que o usuário descartou. |
| R15 | **A marca de finalizado (M6) nunca é retirada pela retomada.** Se o PDF marcado não puder ser confirmado (disco externo ausente, pasta bloqueada), o rascunho volta com a marca e a interface diz "Este documento talvez já tenha sido salvo como X". Finalizar de novo confere a marca primeiro: se o arquivo existe agora, fecha o rascunho sem gravar outro PDF. Qualquer mudança de conteúdo (página nova, exclusão, ordem, nome) retira as marcas, porque o PDF antigo deixou de corresponder. | Retirar a marca garantia um `<nome> (2).pdf` quando o disco voltasse. |
| R16 | **Marca de intenção:** antes de gravar o PDF, o manifesto recebe `finalization_started_at` (melhor esforço). Se a retomada encontra a intenção sem a marca de finalizado, o rascunho volta e a interface diz que uma finalização foi interrompida e pede para conferir a pasta de saída. Se depois do PDF a marca e a limpeza falharem, o rascunho fica em memória marcado como finalizado (não some), e finalizar de novo só fecha. | A janela entre o `os.link` do PDF e a marca inclui o `fsync` da pasta do disco externo (segundos num HD USB); uma duplicata possível nunca fica silenciosa. |
| R17 | **"Adicionar página" nunca espera o lock:** `ensure_can_add_page()` e o `async with lock` acontecem sem `await` entre eles (atômico no laço de eventos). Digitalização em curso → `409 scan_already_running`; lock ocupado por outra mudança, ou alguma edição esperando por ele → `409 document_busy`, com mensagem própria. | Esperar o lock fazia um segundo pedido aceito digitalizar de novo a folha que estava no vidro. |
| R18 | **Montagem do PDF em fluxo:** o PDF é escrito direto no temporário da pasta de saída (`img2pdf.convert(*caminhos, outputstream=...)`), lendo as páginas pelos caminhos, sem juntar os bytes na memória (medido: cerca de 1 × a soma dos JPEGs, contra 2,5 × antes). Antes de montar, cada página é conferida (existe e tem o `size_in_bytes` do manifesto): falha → `409 damaged_document_page` com o `page_identifier`, e a interface marca a miniatura. `MemoryError` → `document_too_large`. | Um documento grande a 600 dpi ficava impossível de finalizar num Mac de 8 GB, e uma página sumida fazia toda finalização falhar sem dizer qual. |
| R19 | **Sessão do rascunho:** cada processo gera uma `draft_session` aleatória; o corpo do documento e o resumo levam `draft_session` e `revision`, e a interface só aceita um corpo de outra sessão ou de revisão maior ou igual à mostrada. | A `revision` recomeça em 0 a cada abertura; sem a sessão, uma aba aberta durante um reinício podia mostrar uma grade velha, e uma resposta atrasada podia desfazer na tela uma edição mais nova. |
| R20 | O corpo do documento ganha `recovery` (o que a retomada fez; some na primeira mudança aceita) e `last_finished_document` (o último PDF finalizado neste processo; some na mudança aceita seguinte). O resumo de `/api/state` ganha `draft_storage` (espaço livre e páginas que cabem no disco do rascunho). | Uma aba recarregada ou outra aba precisa saber onde o PDF foi parar e o que a retomada perdeu; no modo Documento o espaço que importa é o do disco interno. |

### 6.1 Visão geral

```
composition_root: draft_repository.claim_exclusive_access() (R12) → document_draft_service.recover_draft() → servidor atende

DocumentController ──▶ DocumentDraftService (asyncio.Lock único das mudanças no rascunho)
                         │
                         ├─ add_page ──▶ page_scanner = partial(ScanService.scan_document_page, page_capture=DocumentPageCapture)
                         │                 └─ a MESMA sequência do modo rápido (_capture_and_store) e o MESMO
                         │                    ScanProgressTracker (409 único); ScanService.scan_one_file usa ScanOutputService
                         │
                         ├─ edições ────▶ DocumentDraftStore ──▶ DocumentDraftRepository (FileSystemDocumentDraftRepository)
                         └─ finalize ───▶ DocumentFinalizer ──▶ StorageGuardService.ensure_space_for_file,
                                                                PdfAssemblyService.write_pdf_at_embedded_resolutions (em fluxo),
                                                                ScanOutputRepository.save_document
StateController ──▶ ApplicationStateService (inalterado) + DocumentDraftService.snapshot() e describe_draft_storage() → chave "document"
```

Acrescentar uma página (compare com a seção 4.3 do spec principal):

```
Navegador     DocumentController   DocumentDraftService   ScanService      Tracker   DocumentPageCapture   DocumentDraftStore → disco
 │ POST /api/document/pages │              │                  │               │            │                      │
 │─────────────────────────▶│ ensure_can_add_page(): 409 scan_already_running | document_busy                       │
 │◀──── 202 ────────────────│─background──▶│ ensure_can_add_page(); async with lock (sem await entre os dois)       │
 │                          │              │─page_scanner────▶│ begin_scan ──▶│ (síncrono, antes do primeiro await)  │
 │                          │              │                  │ ensure_capacity (thread) ───▶│─ensure_capacity_for_page▶ pasta + espaço do rascunho
 │                          │              │                  │ acquire_gateway; mark_scanning; scan_page; mark_saving   │
 │                          │              │                  │ store (thread) ─────────────▶│ encode (JPEG) ─append_page▶ page → thumbnail → manifesto
 │                          │              │                  │ mark_page_added ▶│            │                      │ snapshot (revision + 1)
 │ GET /api/state (0,5 s): document.revision mudou → GET /api/document → grade redesenhada                        │
```

### 6.2 `domain/`

```python
# capture_mode.py   (NOVO)
class CaptureMode(str, Enum):
    SINGLE = "single"                       # modo Rápido: 1 clique = 1 arquivo (o MVP)
    DOCUMENT = "document"                   # modo Documento: várias páginas → 1 PDF

# application_settings.py   (MUDA: campo novo no fim, com padrão)
@dataclass(frozen=True)
class ApplicationSettings:
    output_folder: Path
    output_format: OutputFormat
    scan_preset: ScanPreset
    capture_mode: CaptureMode = CaptureMode.SINGLE   # construções de 3 argumentos continuam válidas
    def to_scan_request(self) -> ScanRequest: ...    # inalterado

# document_draft.py   (NOVO; regras puras, sem I/O)
PAGE_IDENTIFIER_PATTERN = re.compile(r"[0-9a-f]{16}")   # sempre com fullmatch
PAGE_IDENTIFIER_SIZE_IN_BYTES = 8
DRAFT_SESSION_SIZE_IN_BYTES = 8
def generate_page_identifier() -> str: ...      # secrets.token_hex(PAGE_IDENTIFIER_SIZE_IN_BYTES); a raiz injeta como fábrica
def generate_draft_session() -> str: ...        # secrets.token_hex(DRAFT_SESSION_SIZE_IN_BYTES); a raiz chama uma vez por processo (R19)
def is_page_identifier(text: str) -> bool: ...  # fullmatch; recusa "last", "../x", maiúsculas, tamanho errado

@dataclass(frozen=True)
class DocumentPage:
    page_identifier: str
    scanned_at: datetime                    # job.started_at da digitalização (com fuso)
    dots_per_inch: int                      # do pedido; é também a densidade JFIF gravada no JPEG
    color_mode: ColorMode
    size_in_bytes: int                      # tamanho exato de page-<identificador>.jpg

@dataclass(frozen=True)
class DocumentPageFiles:
    page_identifier: str
    jpeg_content: bytes                     # JPEG mestre já normalizado pelo ScanEncoder (sem recompressão)
    thumbnail_jpeg: bytes                   # 480 px na maior aresta

@dataclass(frozen=True)
class DocumentDraft:
    name: str                               # já limpo por clean_document_name; "" = nome automático
    created_at: datetime                    # scanned_at da primeira página
    pages: tuple[DocumentPage, ...]         # ordem atual = ordem do PDF
    finalization_started_at: datetime | None = None   # marca de intenção (R16): a gravação do PDF começou
    finished_document: ScanResult | None = None       # marca M6 (R15): PDF gravado (caminho, tamanho, momento)
    @classmethod
    def start(cls, first_page: DocumentPage) -> "DocumentDraft": ...   # name "", created_at = first_page.scanned_at
    @property
    def page_count(self) -> int: ...
    @property
    def page_identifiers(self) -> tuple[str, ...]: ...
    @property
    def estimated_size_in_bytes(self) -> int: ...       # soma de size_in_bytes (o PDF fica poucos KB acima)
    def position_of(self, page_identifier: str) -> int: ...                 # 1 = primeira; PageNotFoundError
    # Mudanças de conteúdo: devolvem o rascunho novo SEM as duas marcas (R15).
    def with_page_appended(self, page: DocumentPage) -> "DocumentDraft": ...
    def without_page(self, page_identifier: str) -> "DocumentDraft": ...    # PageNotFoundError
    def without_last_page(self) -> "DocumentDraft": ...                     # EmptyDocumentError sem páginas
    def reordered(self, page_identifiers: Sequence[str]) -> "DocumentDraft": ...   # InvalidPageOrderError (6.6.6)
    def renamed(self, document_name: str) -> "DocumentDraft": ...           # recebe o nome já limpo
    # Marcas:
    def with_finalization_started(self, started_at: datetime) -> "DocumentDraft": ...
    def without_finalization_marker(self) -> "DocumentDraft": ...           # só a marca de intenção
    def marked_finished(self, finished_document: ScanResult) -> "DocumentDraft": ...   # mantém a marca de intenção

@dataclass(frozen=True)
class DocumentFinalizationResult:          # o que finalizar devolve e o que o snapshot lembra (R20)
    result: ScanResult                      # caminho, PDF, momento da finalização, tamanho
    page_count: int

class RecoveryOutcome(str, Enum):
    RESUMED = "resumed"                     # o rascunho voltou (talvez sem algumas páginas)
    PAGES_LOST = "pages_lost"               # manifesto legível, mas nenhuma página tinha arquivo certo: rascunho apagado
    SET_ASIDE = "set_aside"                 # manifesto ilegível: a pasta inteira foi posta de lado
    FAILED = "failed"                       # erro inesperado: nada foi apagado; páginas novas bloqueadas até reabrir (R13)

@dataclass(frozen=True)
class DraftRecoveryReport:
    outcome: RecoveryOutcome
    kept_page_count: int
    dropped_page_positions: tuple[int, ...]   # posições no manifesto (1 = primeira), em ordem crescente
    set_aside_folder: Path | None             # pasta set-aside-… criada nesta retomada, se houve

@dataclass(frozen=True)
class DraftSnapshot:                        # trocado inteiro numa atribuição, como o ScanProgressSnapshot
    draft_session: str                      # fixa no processo (R19)
    revision: int                           # 0 na partida; +1 a cada mudança aceita (nunca volta dentro da sessão)
    draft: DocumentDraft | None
    recovery_report: DraftRecoveryReport | None = None                 # some na primeira mudança aceita
    last_finished_document: DocumentFinalizationResult | None = None   # posto por finalizar; some na mudança aceita seguinte

# document_draft_reconciliation.py   (NOVO; regra pura da retomada, 6.6.2, e nomes dos arquivos do rascunho)
MANIFEST_FILE_NAME = "manifest.json"
PAGE_FILE_PREFIX = "page-"
THUMBNAIL_FILE_PREFIX = "thumbnail-"
JPEG_FILE_SUFFIX = ".jpg"
def page_file_name(page_identifier: str) -> str: ...        # "page-<identificador>.jpg"
def thumbnail_file_name(page_identifier: str) -> str: ...   # "thumbnail-<identificador>.jpg"
@dataclass(frozen=True)
class DraftFileInventory:
    page_file_sizes: Mapping[str, int]      # identificador → tamanho de cada "page-<identificador>.jpg" com identificador válido
    thumbnail_identifiers: frozenset[str]   # cada "thumbnail-<identificador>.jpg" com identificador válido
    temporary_file_names: frozenset[str]    # ".<nome>.<pid>-<token>.part" e ".digitalizadora-write-probe-*"
    unknown_file_names: frozenset[str]      # qualquer outro nome, exceto manifest.json: nunca apagados nem movidos (R14)
    @property
    def known_file_names(self) -> tuple[str, ...]: ...   # páginas, miniaturas e temporários, em ordem alfabética
@dataclass(frozen=True)
class DraftReconciliation:
    draft: DocumentDraft                    # só as páginas cujo arquivo existe com o size_in_bytes do manifesto
    dropped_page_positions: tuple[int, ...] # posições no manifesto das páginas sem arquivo ou com tamanho diferente
    files_to_set_aside: tuple[str, ...]     # page-<identificador>.jpg de página confirmada com tamanho diferente (R14)
    files_to_delete: tuple[str, ...]        # temporários; página e miniatura fora do manifesto; miniatura de página descartada
def reconcile_draft(draft: DocumentDraft, inventory: DraftFileInventory) -> DraftReconciliation: ...
    # As listas de arquivos vêm em ordem alfabética. A ordem das páginas mantidas é a do manifesto; o nome e as duas
    # marcas passam sem mudança.

# document_name_policy.py   (NOVO; regra pura, 6.6.5)
MAXIMUM_DOCUMENT_NAME_CHARACTERS = 120
MAXIMUM_DOCUMENT_NAME_BYTES = 200           # UTF-8; " (1000).pdf" ainda cabe nos 255 bytes do APFS
FORBIDDEN_FILE_NAME_CHARACTERS = frozenset('/\\:*?"<>|')
FORBIDDEN_CHARACTER_REPLACEMENT = "-"
REMOVED_UNICODE_CATEGORIES = frozenset({"Cc", "Cf", "Cs"})   # controle, formatação (bidi, largura zero), surrogates
PDF_FILE_SUFFIX = ".pdf"
def clean_document_name(raw_name: str) -> str: ...            # "" = nome automático; InvalidDocumentNameError
def build_document_file_name(document_name: str, attempt_number: int) -> str: ...
    # attempt_number 1 → "<nome>.pdf"; n >= 2 → "<nome> (n).pdf". Recebe o nome já limpo e não vazio.

# document_pdf_to_save.py   (NOVO)
@dataclass(frozen=True)
class DocumentPdfToSave:
    write_content: Callable[[BinaryIO], None]   # escreve o PDF inteiro no fluxo recebido (montagem em fluxo, R18)
    created_at: datetime                    # momento da finalização: dá a data do nome automático
    document_name: str                      # já limpo; "" = nome automático "AAAA-MM-DD_NNNNN.pdf"

# errors.py   (ACRÉSCIMOS; mensagens internas em inglês)
class NoOpenDocumentError(DigitalizadoraError):           code = "no_open_document"
class PageNotFoundError(DigitalizadoraError):             code = "page_not_found"
class InvalidPageOrderError(DigitalizadoraError):         code = "invalid_page_order"
class InvalidDocumentNameError(DigitalizadoraError):      code = "invalid_document_name"
class EmptyDocumentError(DigitalizadoraError):            code = "empty_document"
class DocumentBusyError(DigitalizadoraError):             code = "document_busy"           # R17
class DraftFolderInUseError(DigitalizadoraError):         code = "draft_folder_in_use"     # R12; só na partida
class DraftStorageUnavailableError(DigitalizadoraError):  code = "draft_storage_unavailable"
class UnreadableDraftError(DraftStorageUnavailableError): ...   # herda o código; manifesto ilegível, tratado na retomada
class InsufficientDraftStorageError(InsufficientStorageError): code = "insufficient_draft_storage"
class DocumentAssemblyFailedError(DigitalizadoraError):   code = "document_assembly_failed"
class DamagedDocumentPageError(DocumentAssemblyFailedError):     code = "damaged_document_page"   # R18
    def __init__(self, page_identifier: str, page_position: int) -> None: ...   # guarda os dois; mensagem interna com ambos
class DocumentTooLargeError(DocumentAssemblyFailedError):        code = "document_too_large"      # R18 (MemoryError)
def as_draft_storage_error(error: DigitalizadoraError) -> DigitalizadoraError: ...
    # Única tradução para o lugar do rascunho: InsufficientStorageError que ainda não é InsufficientDraftStorageError →
    # InsufficientDraftStorageError(str(error)); OutputFolderUnavailableError → DraftStorageUnavailableError(str(error));
    # qualquer outro → o próprio erro. Quem chama faz "raise as_draft_storage_error(error) from error".

# ports.py   (ACRÉSCIMOS)
class ScanOutputRepository(Protocol):       # MUDA: um método novo; os três de hoje ficam iguais
    def output_folder(self) -> Path: ...
    def ensure_output_folder_ready(self) -> None: ...
    def save(self, encoded_scan: EncodedScan) -> Path: ...
    def save_document(self, document_pdf: DocumentPdfToSave) -> ScanResult: ...   # nunca sobrescreve (6.3)
class DocumentDraftRepository(Protocol):    # NOVO
    def storage_folder(self) -> Path: ...                   # <data_directory>/drafts: o espaço livre é medido aqui
    def claim_exclusive_access(self) -> None: ...           # R12: cria drafts/ e pega o flock; DraftFolderInUseError
    def ensure_storage_folder_ready(self) -> None: ...      # cria e prova escrita; DraftStorageUnavailableError | InsufficientDraftStorageError
    def load_manifest(self) -> DocumentDraft | None: ...    # None sem manifest.json; UnreadableDraftError se inutilizável
    def save_manifest(self, draft: DocumentDraft) -> None: ...   # troca atômica (AtomicFileWriter.replace_file)
    def ensure_draft_folder_exists(self) -> None: ...       # mkdir de current/ se faltar (a sobra é tratada antes, 6.6.8)
    def write_page_files(self, page_files: DocumentPageFiles) -> None: ...   # página, depois miniatura (write_new_file)
    def page_file_path(self, page_identifier: str) -> Path: ...              # caminho de page-<identificador>.jpg (sem I/O)
    def page_file_size(self, page_identifier: str) -> int | None: ...        # None se não existe; outro OSError → DraftStorageUnavailableError
    def read_thumbnail(self, page_identifier: str) -> bytes | None: ...
    def delete_page_files(self, page_identifier: str) -> None: ...   # melhor esforço; nunca levanta
    def take_inventory(self) -> DraftFileInventory: ...     # pasta inexistente → inventário vazio
    def delete_files(self, file_names: Sequence[str]) -> None: ...   # melhor esforço; só nomes simples dentro de current/
    def set_aside_files(self, file_names: Sequence[str]) -> Path: ...   # move para uma pasta set-aside-… nova; DraftStorageUnavailableError
    def set_aside_draft_folder(self) -> Path | None: ...    # renomeia current/; None se ela não existir
    def delete_draft(self) -> None: ...                     # manifesto primeiro (levanta), depois só os arquivos conhecidos (6.6.4)
    def finished_document_exists(self, finished_document_path: Path) -> bool: ...   # True só se is_file() confirmar; OSError → False (R15)
```

### 6.3 `repositories/`

**Pasta do rascunho** (M4, M5; sempre no disco interno):

```
<data_directory>/drafts/                          storage_folder(): espaço livre e prova de escrita
├── .owner-lock                                   flock do processo dono (R12); nunca apagado; fora de current/
├── current/                                      o único rascunho (M2)
│   ├── manifest.json
│   ├── page-3f9c0a1b2c3d4e5f.jpg                 JPEG mestre normalizado (M3)
│   ├── thumbnail-3f9c0a1b2c3d4e5f.jpg            miniatura de 480 px
│   └── .page-3f9c0a1b2c3d4e5f.jpg.<pid>-<token>.part   temporário do AtomicFileWriter (só durante uma gravação)
└── set-aside-20261017-101500-a1b2c3d4/           rascunho ilegível, sobra com manifesto válido ou página danificada (o app nunca apaga)
```

**`manifest.json`** (UTF-8, `ensure_ascii=False`, `indent=2`, chaves nesta ordem):

```json
{
  "format_version": 1,
  "name": "Contrato do apartamento",
  "created_at": "2026-10-17T10:00:00-03:00",
  "pages": [
    {
      "page_identifier": "3f9c0a1b2c3d4e5f",
      "scanned_at": "2026-10-17T10:00:00-03:00",
      "dots_per_inch": 300,
      "color_mode": "color",
      "size_in_bytes": 806123
    }
  ],
  "finalization_started_at": null,
  "finished_document": null
}
```

`finished_document`, quando presente: `{"path": "/Volumes/Arquivo/Contrato do apartamento.pdf", "size_in_bytes": 1612800, "finalized_at": "2026-10-17T10:05:00-03:00"}` (o formato é sempre PDF).

Regras de leitura (qualquer violação → `UnreadableDraftError` com o motivo em inglês): JSON objeto; `format_version` inteiro (não booleano) igual a `1` (versão maior ou ausente também é ilegível: um app mais velho nunca reinterpreta um manifesto mais novo); `name` texto; `created_at`, `scanned_at`, `finalization_started_at` e `finalized_at` em ISO 8601 **com fuso**; `pages` lista (pode vir vazia: a retomada apaga o rascunho); `page_identifier` válido por `is_page_identifier` e sem repetição; `dots_per_inch` inteiro de 1 a 65535; `color_mode` de `ColorMode`; `size_in_bytes` inteiro ≥ 1; `finalization_started_at` nulo ou data; `finished_document` nulo ou objeto com `path` absoluto em texto, `size_in_bytes` inteiro ≥ 1 e `finalized_at`. Chaves desconhecidas são ignoradas (acréscimos futuros compatíveis na versão 1); chaves novas desta seção ausentes valem `null`.

```python
# document_manifest_codec.py   (NOVO; funções puras, sem I/O)
MANIFEST_FORMAT_VERSION = 1
def encode_manifest(draft: DocumentDraft) -> bytes: ...
def decode_manifest(content: bytes) -> DocumentDraft: ...      # UnreadableDraftError
    # decode_manifest(encode_manifest(draft)) == draft para qualquer rascunho válido.

# atomic_file_writer.py   (MUDA: um método novo; os dois de hoje mantêm o comportamento)
class AtomicFileWriter:
    def write_new_file(self, destination: Path, content: bytes) -> None: ...   # passa a delegar para write_new_file_from
    def write_new_file_from(self, destination: Path, write_content: Callable[[BinaryIO], None]) -> int: ...
    # Mesma sequência do write_new_file (temporário exclusivo, F_FULLFSYNC, os.link sem sobrescrever ou rename no exFAT,
    # fsync da pasta), mas o conteúdo vem do callback escrevendo no fluxo do temporário. Devolve o tamanho gravado
    # (stream.tell() depois do callback). Exceção do callback: o temporário é removido e a exceção sobe sem tradução.

# file_system_document_draft_repository.py   (NOVO; implementa DocumentDraftRepository)
CURRENT_DRAFT_FOLDER_NAME = "current"
OWNER_LOCK_FILE_NAME = ".owner-lock"
SET_ASIDE_FOLDER_PREFIX = "set-aside-"
SET_ASIDE_MOMENT_FORMAT = "%Y%m%d-%H%M%S"
def translate_draft_storage_error(error: OSError, description: str) -> DigitalizadoraError: ...
    # = as_draft_storage_error(translate_storage_error(error, description)): ENOSPC/EDQUOT → InsufficientDraftStorageError,
    #   qualquer outro → DraftStorageUnavailableError. Nenhuma tabela de errno própria.
class FileSystemDocumentDraftRepository:
    def __init__(self, drafts_folder: Path, file_writer: AtomicFileWriter, clock: Clock) -> None: ...
    # storage_folder() = drafts_folder; a pasta do rascunho é drafts_folder / "current".
    # claim_exclusive_access: drafts_folder.mkdir(parents=True, exist_ok=True); abre .owner-lock com open(..., "a+b") e
    #   guarda o objeto de arquivo num atributo (fica aberto enquanto o repositório existir; o processo encerrado solta o
    #   lock); fcntl.flock(LOCK_EX | LOCK_NB); BlockingIOError → DraftFolderInUseError; outro OSError passa por
    #   translate_draft_storage_error (ENOSPC → InsufficientDraftStorageError, o resto → DraftStorageUnavailableError).
    #   Segunda chamada no mesmo objeto não faz nada.
    # ensure_storage_folder_ready: chama prepare_output_folder(drafts_folder); erros por as_draft_storage_error.
    # write_page_files: write_new_file(página) e depois write_new_file(miniatura); se a miniatura falhar, apaga a página
    #   (melhor esforço) e levanta o erro traduzido. Todo OSError sai por translate_draft_storage_error.
    # read_thumbnail: identificador inválido ou arquivo ausente → None; qualquer outro OSError → None com aviso no log.
    # set_aside_draft_folder: os.rename(current, drafts/set-aside-<clock.now() em SET_ASIDE_MOMENT_FORMAT>-<token_hex(4)>).
    # set_aside_files: cria uma pasta set-aside-… com o mesmo nome e move (os.rename) cada arquivo para dentro dela.
    # delete_draft: (1) apaga manifest.json e faz fsync de current/ (falha ao apagar → DraftStorageUnavailableError, nada
    #   mais mudou; falha no fsync depois de apagar → só aviso, porque o manifesto já saiu e o rascunho deixou de existir);
    #   (2) delete_files(inventário.known_file_names); (3) rmdir de current/ se ficou vazia (falha só gera aviso).
    #   Nomes desconhecidos ficam (R14). Pasta current/ ausente: nada a fazer.
    # take_inventory: current/ ausente (falha ao abri-la) → inventário vazio; um arquivo de página que some entre a listagem
    #   e o stat é ignorado (fica ausente do inventário e a retomada o conta como página faltando); outro OSError →
    #   DraftStorageUnavailableError. Só arquivos comuns são classificados (sem seguir links simbólicos).
    # delete_files recusa (com aviso) qualquer nome com separador de caminho, "." ou "..".
    # Nenhum método decide o que fazer com uma sobra: isso é do DocumentDraftStore (6.6.8).

# file_system_scan_output_repository.py   (MUDA: um método novo; construtor e save inalterados)
class FileSystemScanOutputRepository:
    def save_document(self, document_pdf: DocumentPdfToSave) -> ScanResult: ...
    # document_name "" → mesma regra do save: "AAAA-MM-DD_NNNNN.pdf" com a data de created_at, a partir do maior número
    #   já existente na pasta para essa data (a sequência do modo rápido).
    # nome escolhido → build_document_file_name(nome, n) para n = 1, 2, … até MAXIMUM_NAME_ATTEMPTS (1000).
    # Cada tentativa é write_new_file_from(candidato, document_pdf.write_content): o nome já existente é pulado antes de
    # escrever; só uma corrida real (outro processo criou o nome durante a escrita) refaz a montagem no próximo nome.
    # No APFS, insensível a maiúsculas e à normalização Unicode, "contrato.pdf" colide com "Contrato.pdf" e vira
    # "contrato (2).pdf": nunca sobrescreve. Cria a pasta se faltar; erros como no save (translate_storage_error;
    # tentativas esgotadas → OutputFolderUnavailableError); exceções do callback (ScanFailedError, MemoryError) sobem iguais.
    # Devolve ScanResult(caminho gravado, OutputFormat.PDF, scanned_at=created_at, size_in_bytes=tamanho devolvido).
    # O laço de tentativas do save passa a ser um auxiliar privado único que recebe os nomes candidatos e a gravação.

# json_application_settings_repository.py   (MUDA)
# Leitura: capture_mode é lido chave a chave: ausente, não texto ou fora de CaptureMode → CaptureMode.SINGLE, mantendo
# output_folder, output_format e scan_preset (um valor de versão mais nova não devolve os scans ao disco interno). Só o valor
# não texto ou desconhecido (inclusive null) gera aviso no log, uma vez por valor e por instância do repositório; a chave
# ausente é o caso normal de quem atualiza o app e não gera aviso, porque o ApplicationStateService lê os ajustes a cada
# GET /api/state (a página consulta a cada 0,5 s) e um aviso por leitura encheria o log. parse_capture_mode é uma função pura
# (sem log); o repositório decide quando avisar. As três chaves de hoje continuam com a regra de hoje.
# Gravação: acrescenta "capture_mode" como quarta chave.
```

### 6.4 `services/`

```python
# scan_destination.py   (NOVO; protocolo de serviço, não porta de infraestrutura)
class ScanDestination[StoredOutcome](Protocol):
    def ensure_capacity(self, request: ScanRequest) -> None: ...                       # roda em thread
    def store(self, scanned_image: ScannedImage, job: ScanJob) -> StoredOutcome: ...   # roda em thread
# ScanOutputService já satisfaz ScanDestination[StoredScan] sem nenhuma mudança;
# DocumentPageCapture satisfaz ScanDestination[DocumentPage].

# scan_progress_tracker.py   (MUDA: um método novo)
class ScanProgressTracker:
    def mark_page_added(self) -> None: ...
    # phase → IDLE e scans_completed + 1, numa única atribuição do snapshot. last_result, last_error_code (já limpo
    # pelo begin_scan) e last_thumbnail_jpeg NÃO mudam: o painel do modo rápido continua mostrando o último arquivo.

# scan_service.py   (MUDA: um método público novo; construtor e scan_one_file mantêm o comportamento)
class ScanService:
    async def scan_one_file(self, request: ScanRequest) -> ScanResult: ...
    async def scan_document_page(self, request: ScanRequest,
                                 page_capture: ScanDestination[DocumentPage]) -> DocumentPage: ...
    # Ligado uma vez pela raiz (functools.partial); ver o parágrafo antes de 6.0.
    # Os dois fazem: job = begin_scan(request) FORA do try e antes do primeiro await (ScanAlreadyRunningError sobe sem
    # mexer no estado); with self._recording_failures(): outcome = await self._capture_and_store(job, destino); depois a
    # marca de conclusão (mark_completed(stored_scan) no modo rápido, mark_page_added() no Documento) e o retorno.
    # _capture_and_store[StoredOutcome](self, job, destination) é a sequência ÚNICA de hoje: ensure_capacity (thread) →
    # acquire_gateway → mark_scanning → scan_page(job.request.settings) → mark_saving → store (thread).
    # _recording_failures() é um contextmanager com o tratamento de hoje: DigitalizadoraError → mark_failed(code);
    # outra exceção → logger.exception + mark_failed("unexpected_error"); sempre relança.

# storage_guard_service.py   (MUDA: um método novo)
class StorageGuardService:
    def ensure_space_for_file(self, folder: Path, file_size_in_bytes: int) -> None: ...
    # livre >= MINIMUM_FREE_SPACE_BYTES (1 GiB) + file_size_in_bytes, senão InsufficientStorageError.
    # (O .part e o nome final são o mesmo arquivo, por hard link: não precisa do dobro.)

# pdf_assembly_service.py   (MUDA: constante, dataclass e método novos; build_pdf com o mesmo comportamento)
DEFAULT_PDF_TITLE_TEMPLATE = "Digitalização {moment:%Y-%m-%d %H:%M:%S}"   # único; o ScanEncoder passa a usá-lo
@dataclass(frozen=True)
class PdfDocumentMetadata:
    title: str
    created_at: datetime
class PdfAssemblyService:
    def build_pdf(self, jpeg_pages: Sequence[bytes], specification: PdfDocumentSpecification) -> bytes: ...   # inalterado por fora
    def write_pdf_at_embedded_resolutions(self, page_files: Sequence[Path], metadata: PdfDocumentMetadata,
                                          output_stream: BinaryIO) -> None: ...
    # img2pdf.convert(*[os.fsencode(caminho) ...], outputstream=output_stream, **opções) com layout_fun=img2pdf.default_layout_fun
    # (os caminhos vão como bytes: o img2pdf 0.6.3 trata um str que não consegue abrir como se fosse o conteúdo da imagem e
    # levanta TypeError; com bytes levanta ImageOpenError, que vira ScanFailedError e, na Tarefa 19, document_assembly_failed):
    # cada página usa a densidade JFIF do próprio JPEG (o ScanEncoder já a normalizou para o dots_per_inch da página),
    # sem recompressão e sem juntar as páginas na memória (R18).
    # Os dois métodos montam as opções num único auxiliar _conversion_options(metadata, layout_function) -> dict, com
    # layout_function OBRIGATÓRIO (nunca None: o img2pdf chama layout_fun sem conferir). build_pdf passa
    # get_fixed_dpi_layout_fun(...) e deriva PdfDocumentMetadata(specification.title, specification.created_at).
    # Mesmo creator, engine, rotação e erros: lista vazia ou imagem ilegível → ScanFailedError; MemoryError sobe igual.

# scan_encoder.py   (MUDA: uma linha) PDF_TITLE_TEMPLATE sai; usa DEFAULT_PDF_TITLE_TEMPLATE.format(moment=job.started_at).
# O texto gerado é o mesmo, então os testes do ScanEncoder não mudam.

# document_draft_store.py   (NOVO; síncrono: estado do rascunho + persistência)
@dataclass(frozen=True)
class CapturedPage:
    jpeg_content: bytes                     # JPEG normalizado (EncodedScan.content de um pedido JPEG)
    thumbnail_jpeg: bytes
    scanned_at: datetime                    # job.started_at
    settings: ScanSettings                  # job.request.settings (dá dots_per_inch e color_mode)
@dataclass(frozen=True)
class DraftIdentitySource:
    draft_session: str                      # generate_draft_session(), uma vez por processo
    page_identifier_factory: Callable[[], str]
@dataclass(frozen=True)
class DraftStorageState:                    # espaço do disco do rascunho, para a interface (R20)
    free_space_in_bytes: int
    estimated_pages_remaining: int
    available: bool
UNAVAILABLE_DRAFT_STORAGE_STATE = DraftStorageState(0, 0, False)
class DocumentDraftStore:
    def __init__(self, draft_repository: DocumentDraftRepository, storage_guard_service: StorageGuardService,
                 identity_source: DraftIdentitySource) -> None: ...
    def snapshot(self) -> DraftSnapshot: ...                       # qualquer thread; nunca toca no disco
    def recover(self) -> None: ...                                 # 6.6.2; só na partida; nunca levanta
    def describe_storage(self, settings: ScanSettings) -> DraftStorageState: ...   # free_space_in_bytes e estimate_pages_remaining
                                                                   # do storage_folder(); OutputFolderUnavailableError → UNAVAILABLE
    def ensure_capacity_for_page(self, settings: ScanSettings) -> None: ...   # 6.6.1, passo 3
    def append_page(self, captured_page: CapturedPage) -> DocumentPage: ...   # 6.6.1, passos 6 a 11
    def rename(self, raw_name: str) -> DocumentDraft: ...          # NoOpenDocumentError, InvalidDocumentNameError
    def reorder(self, page_identifiers: Sequence[str]) -> DocumentDraft: ...  # NoOpenDocumentError, InvalidPageOrderError
    def delete_page(self, page_identifier: str) -> DocumentDraft | None: ...  # NoOpenDocumentError, PageNotFoundError; None = rascunho apagado (R3)
    def discard_last_page(self) -> DocumentDraft | None: ...       # NoOpenDocumentError; None = rascunho apagado (R3)
    def discard(self) -> None: ...                                 # cancelar; sem rascunho não faz nada; falha → levanta sem mudar o estado
    def read_thumbnail(self, page_identifier: str) -> bytes | None: ...   # None: identificador inválido, fora do rascunho ou sem arquivo
    def is_finished_document_present(self, draft: DocumentDraft) -> bool: ...   # marca M6 presente e finished_document_exists
    def verify_page_files(self, draft: DocumentDraft) -> list[Path]: ...  # 6.6.3, passo 4; DamagedDocumentPageError
    def mark_finalization_started(self, started_at: datetime) -> None: ...   # grava a intenção só no disco; melhor esforço
    def clear_finalization_marker(self) -> None: ...               # regrava o manifesto do snapshot; melhor esforço
    def close_finished_draft(self, finalization: DocumentFinalizationResult) -> None: ...   # 6.6.3, passo 8; nunca levanta
    # Contrato de threads: os métodos que mudam o estado só rodam (a) em thread aberta pelo DocumentDraftService
    # enquanto ele segura o lock, ou (b) em recover(), antes de o servidor atender. Cada mudança aceita termina trocando
    # o DraftSnapshot inteiro numa atribuição (revision + 1, recovery_report None; last_finished_document None, exceto
    # em close_finished_draft, que o define), então snapshot() lido de outra thread é sempre coerente.
    # Mudança sem efeito (mesmo nome limpo, mesma ordem) não grava nada e não muda o snapshot.
    # Estado privado além do snapshot: _recovery_failed (R13), que faz ensure_capacity_for_page levantar.

# document_page_capture.py   (NOVO; implementa ScanDestination[DocumentPage])
class DocumentPageCapture:
    def __init__(self, scan_encoder: ScanEncoder, draft_store: DocumentDraftStore) -> None: ...
    def ensure_capacity(self, request: ScanRequest) -> None: ...   # draft_store.ensure_capacity_for_page(request.settings)
    def store(self, scanned_image: ScannedImage, job: ScanJob) -> DocumentPage: ...
    # encoded = scan_encoder.encode(scanned_image, job). O pedido do job é sempre JPEG (DocumentDraftService.add_page),
    # então encoded.content é o JPEG normalizado e encoded.thumbnail_jpeg a miniatura de 480 px; o ScanEncoder não muda.
    # Depois: draft_store.append_page(CapturedPage(encoded.content, encoded.thumbnail_jpeg, job.started_at, job.request.settings)).

# document_finalizer.py   (NOVO; síncrono, roda em thread)
@dataclass(frozen=True)
class DocumentAssemblyInput:
    draft: DocumentDraft
    page_files: Sequence[Path]              # na ordem do rascunho, já conferidos por verify_page_files
    finalized_at: datetime                  # do Clock
class DocumentFinalizer:
    def __init__(self, pdf_assembly_service: PdfAssemblyService, scan_output_repository: ScanOutputRepository,
                 storage_guard_service: StorageGuardService) -> None: ...
    def ensure_capacity(self, draft: DocumentDraft) -> None: ...
    # 1º ensure_output_folder_ready() (OutputFolderUnavailableError antes de conferir 300 páginas);
    # 2º ensure_space_for_file(output_folder(), draft.estimated_size_in_bytes) (InsufficientStorageError).
    def write_document(self, assembly_input: DocumentAssemblyInput) -> ScanResult: ...
    # título = draft.name, ou DEFAULT_PDF_TITLE_TEMPLATE.format(moment=draft.created_at) quando o nome é "";
    # write_content = functools.partial(pdf_assembly_service.write_pdf_at_embedded_resolutions, page_files,
    #                                   PdfDocumentMetadata(título, finalized_at));
    # devolve save_document(DocumentPdfToSave(write_content, finalized_at, draft.name)).
    # ScanFailedError → DocumentAssemblyFailedError; MemoryError → DocumentTooLargeError; erros de pasta e espaço sobem iguais.

# document_draft_service.py   (NOVO; assíncrono; dono do lock)
@dataclass(frozen=True)
class DocumentDraftCollaborators:
    draft_store: DocumentDraftStore
    page_scanner: Callable[[ScanRequest], Awaitable[DocumentPage]]   # partial(scan_service.scan_document_page, page_capture=...)
    finalizer: DocumentFinalizer
class DocumentDraftService:
    def __init__(self, scan_service: ScanService, collaborators: DocumentDraftCollaborators, clock: Clock) -> None: ...
    def recover_draft(self) -> None: ...                 # a raiz de composição chama uma vez; delega a draft_store.recover()
    def snapshot(self) -> DraftSnapshot: ...
    def describe_draft_storage(self, settings: ScanSettings) -> DraftStorageState: ...   # delega; usado pelo StateController
    def ensure_can_add_page(self) -> None: ...
    # scan_service.is_scan_in_progress() → ScanAlreadyRunningError; lock.locked() ou edição esperando o lock → DocumentBusyError
    # (R17). "Esperando" é o contador _waiting_edit_count de _run_edit: logo depois de Lock.release(), locked() já é False
    # enquanto a edição acordada ainda não rodou, e um acquire() de página nessa janela entraria na fila atrás dela.
    def read_thumbnail(self, page_identifier: str) -> bytes | None: ...   # sem lock (leitura de arquivo imutável)
    async def add_page(self, settings: ScanSettings) -> DocumentPage: ...
    # self.ensure_can_add_page(); async with self._lock: return await page_scanner(ScanRequest(settings, OutputFormat.JPEG))
    # Nenhum await entre a conferência e a tomada do lock livre (sem dono e sem edição esperando): nunca espera o lock (R17).
    async def rename(self, raw_name: str) -> DocumentDraft: ...
    async def reorder(self, page_identifiers: Sequence[str]) -> DocumentDraft: ...
    async def delete_page(self, page_identifier: str) -> DocumentDraft | None: ...
    async def discard_last_page(self) -> DocumentDraft | None: ...
    async def cancel(self) -> None: ...
    async def finalize(self) -> DocumentFinalizationResult: ...   # 6.6.3
    # As seis edições passam por um único auxiliar privado _run_edit(edit: Callable[[], T]) -> T (6.6.7).
```

### 6.5 `controllers/`, raiz e `__main__`

```python
# controllers/error_message_catalog.py   (MUDA: doze mensagens novas; UnreadableDraftError usa a de draft_storage_unavailable)
"no_open_document": "Não há documento em andamento. Adicione uma página para começar.",
"page_not_found": "Essa página não está mais no documento. A lista foi atualizada.",
"invalid_page_order": "A nova ordem das páginas não confere com o documento. A lista foi atualizada; tente de novo.",
"invalid_document_name": ("Nome de documento inválido: comprido demais ou só com pontos e caracteres invisíveis. "
                          "Use um nome mais curto, com letras ou números."),
"empty_document": "O documento não tem páginas. Adicione pelo menos uma página antes de finalizar.",
"document_busy": "O documento está sendo finalizado ou alterado. Aguarde um instante e tente de novo.",
"draft_folder_in_use": ("O Digitalizadora já está aberto em outra janela do Terminal. "
                        "Use aquela janela, ou feche-a antes de abrir de novo."),
"draft_storage_unavailable": ("Não consigo guardar as páginas do documento no disco do Mac. "
                              "Veja o registro em ~/Library/Logs/Digitalizadora."),
"insufficient_draft_storage": "Pouco espaço livre no disco do Mac para guardar as páginas do documento. Libere espaço e tente de novo.",
"document_assembly_failed": ("Não consegui montar o PDF porque uma página guardada não pôde ser lida como imagem. "
                             "Veja o registro em ~/Library/Logs/Digitalizadora."),
"damaged_document_page": ("Uma página guardada do documento está danificada ou sumiu do disco do Mac. "
                          "Ela está marcada na grade: exclua-a e digitalize-a de novo."),
"document_too_large": ("O documento é grande demais para montar com a memória livre do Mac. "
                       "Feche outros programas e tente de novo."),

# controllers/settings_body.py   (MUDA) build_settings_body ganha "capture_mode" como quarta chave.
# controllers/settings_controller.py   (MUDA)
class SettingsRequestBody(BaseModel):
    output_folder: str
    output_format: str
    scan_preset: str
    capture_mode: str | None = None         # ausente = mantém o modo atual (cliente antigo continua funcionando)
# services/application_settings_service.py   (MUDA)
@dataclass(frozen=True)
class SettingsUpdate:
    output_folder: str
    output_format: str
    scan_preset: str
    capture_mode: str | None = None         # None = mantém current().capture_mode; senão parse_enum_member(CaptureMode, ...)

# controllers/document_body.py   (NOVO; como settings_body.py, compartilhado por DocumentController e StateController)
def build_document_body(draft_snapshot: DraftSnapshot) -> dict[str, Any]: ...       # corpo do documento (abaixo)
def build_document_summary_body(draft_snapshot: DraftSnapshot,
                                draft_storage: DraftStorageState) -> dict[str, Any]: ...   # chave "document" de /api/state

# controllers/document_controller.py   (NOVO)
class PageOrderRequestBody(BaseModel):
    page_identifiers: list[str]
class DocumentNameRequestBody(BaseModel):
    name: str
DOCUMENT_ERROR_STATUSES: Mapping[str, HTTPStatus] = MappingProxyType({
    "scan_already_running": HTTPStatus.CONFLICT, "document_busy": HTTPStatus.CONFLICT,
    "damaged_document_page": HTTPStatus.CONFLICT,
    "no_open_document": HTTPStatus.NOT_FOUND, "page_not_found": HTTPStatus.NOT_FOUND,
    "invalid_page_order": HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_document_name": HTTPStatus.UNPROCESSABLE_ENTITY,
    "empty_document": HTTPStatus.UNPROCESSABLE_ENTITY,
    "output_folder_unavailable": HTTPStatus.SERVICE_UNAVAILABLE, "draft_storage_unavailable": HTTPStatus.SERVICE_UNAVAILABLE,
    "insufficient_storage": HTTPStatus.INSUFFICIENT_STORAGE, "insufficient_draft_storage": HTTPStatus.INSUFFICIENT_STORAGE,
})                                          # qualquer outro DigitalizadoraError → 500 com o próprio código
THUMBNAIL_CACHE_HEADERS = {"Cache-Control": "private, max-age=31536000, immutable"}   # o identificador nunca é reaproveitado
class DocumentController:
    def __init__(self, document_draft_service: DocumentDraftService, settings_service: ApplicationSettingsService,
                 error_message_catalog: ErrorMessageCatalog) -> None: ...
    def build_router(self) -> APIRouter: ...
    # Rotas, registradas nesta ordem (/pages/last antes de /pages/{page_identifier}):
    # GET    /api/document                                     read_document       (síncrono: só lê o snapshot)
    # POST   /api/document/pages                               add_page            (ensure_can_add_page() → 409; senão 202 e tarefa em segundo plano)
    # DELETE /api/document/pages/last                          discard_last_page
    # DELETE /api/document/pages/{page_identifier}             delete_page
    # GET    /api/document/pages/{page_identifier}/thumbnail   read_thumbnail      (síncrono; image/jpeg ou 404 sem corpo)
    # PUT    /api/document/page-order                          reorder_pages
    # PUT    /api/document/name                                rename_document
    # POST   /api/document/finalize                            finalize_document
    # DELETE /api/document                                     cancel_document
    # add_page lê settings_service.current().scan_preset.settings na hora do pedido (como o ScanController) e a tarefa
    # em segundo plano registra no log o DigitalizadoraError ou a falha inesperada, sem relançar (o tracker já tem o código;
    # um ScanAlreadyRunningError ou DocumentBusyError da segunda conferência só vai para o log: nenhuma folha é lida duas vezes).
    # Toda edição responde com build_document_body(document_draft_service.snapshot()) depois de concluída.
    # DamagedDocumentPageError: corpo {"code", "message", "page_identifier"} (único erro com chave a mais).

# controllers/state_controller.py   (MUDA: terceiro parâmetro antes do catálogo; chave nova "document")
class StateController:
    def __init__(self, state_service: ApplicationStateService, document_draft_service: DocumentDraftService,
                 error_message_catalog: ErrorMessageCatalog) -> None: ...
    # "document": build_document_summary_body(snapshot(), describe_draft_storage(state.settings.scan_preset.settings))

# application_factory.py   (MUDA)
@dataclass(frozen=True)
class ApplicationControllers:
    scan: ScanController; state: StateController; settings: SettingsController
    printer: PrinterController; preview: PreviewController; document: DocumentController   # NOVO, incluído no laço de routers
VALIDATION_ERROR_CODES_BY_PATH: Mapping[str, str] = MappingProxyType({
    "/api/document/page-order": InvalidPageOrderError.code,
    "/api/document/name": InvalidDocumentNameError.code,
})   # ErrorResponses.respond_to_invalid_body usa request.url.path; qualquer outro caminho continua invalid_settings

# composition_root.py   (MUDA)
DRAFTS_FOLDER_NAME = "drafts"
# Um único SystemClock e um único ScanEncoder para todo o container (hoje são criados em linha).
# repositories: FileSystemDocumentDraftRepository(configuration.data_directory / DRAFTS_FOLDER_NAME, file_writer, clock)
# services: DocumentDraftStore(draft_repository, storage_guard_service,
#                              DraftIdentitySource(generate_draft_session(), generate_page_identifier));
#           DocumentPageCapture(scan_encoder, draft_store);
#           DocumentFinalizer(PdfAssemblyService(), repositories.scan_output, storage_guard_service);
#           DocumentDraftService(scan_service, DocumentDraftCollaborators(
#               draft_store, functools.partial(scan_service.scan_document_page, page_capture=page_capture), finalizer), clock)
# controllers: DocumentController(document_draft_service, settings_service, catalog);
#              StateController(state_service, document_draft_service, catalog)
# Na montagem, antes de o servidor atender:
#   draft_repository.claim_exclusive_access()   (logo depois de criar os repositórios, antes de preparar a pasta de saída e de
#                                                 criar o httpx.AsyncClient: uma segunda cópia para antes de tocar em qualquer arquivo;
#                                                 DraftFolderInUseError sobe para quem chamou build_container)
#   document_draft_service.recover_draft()      (depois de criar os serviços)
# ContainerOverrides não muda.

# __main__.py   (MUDA)
PORT_IN_USE_MESSAGE = (
    "A porta {port} já está em uso. Provavelmente o Digitalizadora já está aberto em outra janela do Terminal: "
    "use aquela janela. Se a porta é de outro programa, escolha outra, por exemplo: DIGITALIZADORA_PORT=8766 make run"
)
# run_application: build_container dentro de try; DraftFolderInUseError → print(ERROR_MESSAGES[DraftFolderInUseError.code])
# e EXIT_CODE_FAILURE. Uma segunda cópia em outra porta para nesse ponto (R12).
```

**JSON da API** (erros sempre `{"code", "message"}`, mais `page_identifier` em `damaged_document_page`; todas as rotas novas passam pelo `LocalRequestGuard`, e `POST`, `PUT` e `DELETE` exigem `X-Requested-With: digitalizadora`):

- Corpo do documento, usado por `GET /api/document` e por todas as edições (chaves nesta ordem):

  ```json
  {"draft_session": "5c0f9a2e7b1d4c38",
   "revision": 4,
   "document": {
     "name": "Contrato do apartamento",
     "created_at": "2026-10-17T10:00:00-03:00",
     "page_count": 2,
     "estimated_size_in_bytes": 1612246,
     "finalization_started_at": null,
     "finished_document_path": null,
     "pages": [
       {"page_identifier": "3f9c0a1b2c3d4e5f", "scanned_at": "2026-10-17T10:00:00-03:00",
        "dots_per_inch": 300, "color_mode": "color", "size_in_bytes": 806123},
       {"page_identifier": "a07e5c9d11f04b2e", "scanned_at": "2026-10-17T10:00:41-03:00",
        "dots_per_inch": 300, "color_mode": "color", "size_in_bytes": 806123}
     ]},
   "recovery": {"outcome": "resumed", "kept_page_count": 2, "dropped_page_positions": [3], "set_aside_folder": null},
   "last_finished_document": null}
  ```

  `document`, `recovery` e `last_finished_document` podem ser `null` cada um. `last_finished_document`, quando presente: `{"file_name", "output_folder", "page_count", "size_in_bytes", "finalized_at"}`. `recovery` pode vir com `document: null` (`set_aside`, `pages_lost`, `failed`).
- `GET /api/state` → as chaves de hoje + `"document": {"draft_session", "revision", "page_count", "estimated_size_in_bytes", "draft_storage": {"free_space_in_bytes", "estimated_pages_remaining", "available"}}` (sempre um objeto; `page_count` e `estimated_size_in_bytes` 0 sem rascunho); `settings` ganha `"capture_mode": "single" | "document"`.
- `GET/PUT /api/settings` → `{"output_folder", "output_format", "scan_preset", "capture_mode"}`; o `PUT` aceita o corpo antigo, de três chaves, e então mantém o modo.

| Rota | Sucesso | Erros, na ordem em que são conferidos |
|---|---|---|
| `GET /api/document` | `200` corpo do documento | — |
| `POST /api/document/pages` | `202 {"accepted": true}` | `409 scan_already_running` (digitalização em curso); `409 document_busy` (outra mudança no rascunho em curso, R17); falhas da digitalização chegam por `/api/state` (`last_error`) |
| `DELETE /api/document/pages/last` | `200` corpo do documento (`document: null` se era a única página) | `409`; `404 no_open_document`; `503`/`507` dos erros do rascunho |
| `DELETE /api/document/pages/{page_identifier}` | `200` idem | `409`; `404 no_open_document`; `404 page_not_found` (inclusive identificador malformado); `503`/`507` |
| `PUT /api/document/page-order` `{"page_identifiers": [...]}` | `200` corpo do documento | `409`; `404 no_open_document`; `422 invalid_page_order` (corpo malformado também, R11); `503`/`507` |
| `PUT /api/document/name` `{"name": "..."}` | `200` corpo do documento (com o nome limpo) | `409`; `422 invalid_document_name` (corpo malformado também); `404 no_open_document`; `503`/`507` |
| `POST /api/document/finalize` | `200 {"file_name", "output_folder", "page_count", "size_in_bytes"}` | `409`; `404 no_open_document`; `422 empty_document`; `503 output_folder_unavailable`; `507 insufficient_storage`; `409 damaged_document_page`; `503 draft_storage_unavailable` (página ilegível por erro de disco); `500 document_assembly_failed`; `500 document_too_large` |
| `DELETE /api/document` | `200` corpo do documento (`document: null`; também sem rascunho: idempotente) | `409`; `503 draft_storage_unavailable` se nem o manifesto puder ser apagado |
| `GET /api/document/pages/{page_identifier}/thumbnail` | `200 image/jpeg` com `THUMBNAIL_CACHE_HEADERS` | `404` sem corpo |

### 6.6 Algoritmos

Nos passos abaixo, "trocar o snapshot" é sempre uma única atribuição de um `DraftSnapshot` novo com `revision + 1`, `recovery_report = None` e `last_finished_document = None` (exceto onde dito).

#### 6.6.1 Acrescentar página (atômico: arquivos da página primeiro, manifesto depois)

1. `DocumentController.add_page`: `ensure_can_add_page()` → `409 scan_already_running` ou `409 document_busy`. Senão lê `scan_preset.settings` dos ajustes, agenda `add_page(settings)` em segundo plano e responde `202`.
2. `DocumentDraftService.add_page`: `ensure_can_add_page()` de novo e, sem `await` entre os dois, `async with lock` (um lock livre é tomado sem ceder o laço, então conferir e tomar é atômico). Se a conferência falhar aqui (outro pedido aceito passou na frente), só o log registra: o tracker não muda e a folha não é lida duas vezes. Com o lock: `page_scanner(ScanRequest(settings, JPEG))` → `scan_document_page` → `begin_scan` (síncrono, antes do primeiro `await`).
3. `ensure_capacity` (thread) → `draft_store.ensure_capacity_for_page(settings)`: `_recovery_failed` → `DraftStorageUnavailableError` (R13); `repository.ensure_storage_folder_ready()`; `storage_guard.ensure_space_for_scan(repository.storage_folder(), settings)`, com qualquer erro passado por `as_draft_storage_error`. Tudo **antes** de pedir a página à impressora (15 a 75 s).
4. `acquire_gateway` → `mark_scanning` → `scan_page` → `mark_saving` (sequência única do `ScanService`).
5. `store` (thread) → `DocumentPageCapture.store`: `ScanEncoder.encode` (valida `image/jpeg`, normaliza a densidade, miniatura de 480 px) → `draft_store.append_page(captured_page)`:
6. `page_identifier = identity_source.page_identifier_factory()`.
7. Sem rascunho em memória: `_clear_leftovers()` (6.6.8) e `repository.ensure_draft_folder_exists()`.
8. `repository.write_page_files(DocumentPageFiles(...))`: `page-<identificador>.jpg` com `write_new_file` (temporário, `F_FULLFSYNC`, `os.link`, `fsync` da pasta) e depois `thumbnail-<identificador>.jpg` do mesmo jeito.
9. `page = DocumentPage(page_identifier, scanned_at, settings.dots_per_inch, settings.color_mode, len(jpeg_content))`; `new_draft = DocumentDraft.start(page)` ou `current.with_page_appended(page)` (sem marcas, R15).
10. `repository.save_manifest(new_draft)` (`replace_file`: temporário, `F_FULLFSYNC`, `os.replace`, `fsync` da pasta). Se falhar: `repository.delete_page_files(page_identifier)` (melhor esforço) e relança; o snapshot não muda.
11. Troca o snapshot para `new_draft`; devolve `page`. De volta no `ScanService`: `mark_page_added()`. Qualquer erro dos passos 3 a 10 vira `mark_failed(code)`, como no modo rápido.

Queda depois do passo 8 e antes do 10: a página e a miniatura ficam fora do manifesto e a retomada as apaga (a página nunca foi mostrada ao usuário). Queda durante o passo 10: `os.replace` é atômico, então vale o manifesto antigo ou o novo, nunca um pela metade.

#### 6.6.2 Retomada na abertura (`DocumentDraftStore.recover`, chamada uma vez pela raiz depois de `claim_exclusive_access`)

O snapshot começa como `DraftSnapshot(draft_session, 0, None)`. Ao fim, `revision` continua 0 e só `draft` e `recovery_report` são definidos.

1. `inventory = repository.take_inventory()`; `manifest = repository.load_manifest()`.
2. `UnreadableDraftError`: `repository.set_aside_draft_folder()`, aviso no log com o motivo e o caminho novo; relatório `SET_ASIDE` com a pasta; fim (nada é apagado).
3. `manifest is None`: `repository.delete_files(inventory.known_file_names)` (páginas, miniaturas e temporários nunca confirmados; um aviso com a contagem); nomes desconhecidos ficam (um aviso, R14); sem relatório; fim.
4. `manifest.finished_document` preenchido e `repository.finished_document_exists(caminho)`: `repository.delete_draft()`, registro informativo, sem relatório, fim (não duplica). Marca presente mas PDF **não confirmado** (ausente, disco desconectado, pasta bloqueada): segue com a marca intacta (R15).
5. `reconciliation = reconcile_draft(manifest, inventory)`; aviso no log para cada posição descartada.
6. `reconciliation.files_to_set_aside` não vazio: `set_aside_folder = repository.set_aside_files(...)` (a página confirmada de tamanho errado nunca é apagada, R14).
7. `reconciliation.draft.page_count == 0`: `repository.delete_draft()`; relatório `PAGES_LOST` com as posições descartadas e a pasta do passo 6 (sem relatório se o manifesto já tinha `pages: []`); fim.
8. Se houve posições descartadas: `repository.save_manifest(reconciliation.draft)`. Falha (por exemplo ENOSPC): aviso no log e segue (R13): o manifesto no disco ainda lista as páginas descartadas, e a próxima abertura reconcilia do mesmo jeito. As marcas nunca são retiradas aqui; sem páginas descartadas, o manifesto não é regravado.
9. `repository.delete_files(reconciliation.files_to_delete)` (melhor esforço, aviso por arquivo); nomes desconhecidos ficam e geram um aviso só.
10. Snapshot com `reconciliation.draft` e relatório `RESUMED(kept_page_count, dropped_page_positions, set_aside_folder)`. Uma falha no passo 7 depois de `set_aside_files` já ter criado uma pasta set-aside dá o relatório `FAILED` sem `set_aside_folder` (`FAILED` significa "nada foi apagado"). Miniatura ausente não descarta a página: `read_thumbnail` devolve `None` e a interface mostra um quadro com o número da página.

Qualquer outra exceção nos passos 1 a 7, e não só `DigitalizadoraError` (por exemplo `OSError` passageiro no inventário, falha ao pôr de lado no passo 2 ou 6) é registrada com o traceback, `_recovery_failed = True`, snapshot sem rascunho e relatório `FAILED`; `current/` fica como estava (os passos anteriores ao 7 não apagam nada). `recover` nunca levanta, o servidor sempre sobe, e as páginas novas respondem `draft_storage_unavailable` até a próxima abertura, que tenta de novo. Isso impede que a primeira página nova ponha de lado um rascunho válido que só não pôde ser lido agora.

#### 6.6.3 Finalizar (`DocumentDraftService.finalize`, dentro de `_run_edit`, tudo numa única thread)

1. `draft = snapshot().draft` ou `NoOpenDocumentError`; `draft.page_count == 0` → `EmptyDocumentError` (invariante; não acontece pela API).
2. `draft_store.is_finished_document_present(draft)` (marca M6 de antes e o arquivo existe agora): `finalization = DocumentFinalizationResult(draft.finished_document, draft.page_count)`, vai direto ao passo 8 sem gravar outro PDF (R15).
3. `finalizer.ensure_capacity(draft)`: pasta de saída pronta (`OutputFolderUnavailableError`) e espaço livre ≥ 1 GiB + `estimated_size_in_bytes` (`InsufficientStorageError`), antes de conferir qualquer página.
4. `page_files = draft_store.verify_page_files(draft)`: para cada página, na ordem, `repository.page_file_size` deve ser igual a `size_in_bytes`; arquivo ausente ou de outro tamanho → `DamagedDocumentPageError(page_identifier, posição)` (R18); outro erro de disco → `DraftStorageUnavailableError`. Devolve `repository.page_file_path` de cada página.
5. `finalized_at = clock.now()`; `draft_store.mark_finalization_started(finalized_at)`: grava no disco o manifesto com `with_finalization_started` (o snapshot não muda; falha → aviso e segue: a marca de intenção é uma rede, não uma condição).
6. `result = finalizer.write_document(DocumentAssemblyInput(draft, page_files, finalized_at))`: o PDF é escrito em fluxo no temporário da pasta de saída e publicado sem sobrescrever (6.3).
7. Falha em 3 a 6: se o passo 5 gravou a intenção, `draft_store.clear_finalization_marker()` (melhor esforço); o rascunho fica intacto e o erro vira a resposta (R10).
8. `finalization = DocumentFinalizationResult(result, draft.page_count)`; `draft_store.close_finished_draft(finalization)`:
   - `save_manifest(draft.marked_finished(finalization.result))` (falha → aviso; no disco fica a intenção do passo 5);
   - `repository.delete_draft()`: sucesso → snapshot sem rascunho; falha ao apagar o manifesto → aviso e o snapshot **mantém** `draft.marked_finished(...)` em memória (R16): a interface mostra "já salvo como X", e finalizar de novo cai no passo 2 e tenta apagar outra vez;
   - snapshot trocado com `last_finished_document = finalization`.
9. Devolve `finalization`.

Memória (R18): a montagem em fluxo segura cerca de 1 × a soma dos JPEGs (medido com img2pdf 0.6.3 e pikepdf 10.17: 0,97 ×), sem a lista de páginas em memória; 500 páginas a 600 dpi em cor (~4,3 MB cada) ≈ 2,2 GB. `MemoryError` → `document_too_large`, com o rascunho intacto. Dividir o PDF continua para depois (M11).

Janela restante: queda entre o `os.link` do PDF (passo 6, incluído o `fsync` da pasta do disco externo) e o fim da primeira gravação do passo 8 deixa o PDF gravado e o rascunho com a marca de intenção. Ao reabrir, o documento volta e a interface diz "Uma finalização deste documento foi interrompida às HH:MM. Confira na pasta de saída se o PDF já existe antes de finalizar de novo." Só se o passo 5 também falhou (disco interno cheio) uma duplicata `<nome> (2).pdf` pode acontecer sem aviso.

#### 6.6.4 Excluir, descartar a última, renomear, cancelar

- `delete_page(page_identifier)`: `NoOpenDocumentError` sem rascunho; `PageNotFoundError` se `is_page_identifier(page_identifier)` for falso ou o identificador não estiver no rascunho. Se era a única página: `repository.delete_draft()` (falha → levanta, nada muda) e snapshot sem rascunho (R3). Senão: `save_manifest(draft.without_page(page_identifier))` → troca o snapshot → `delete_page_files(page_identifier)` (melhor esforço; sobra fica fora do manifesto e sai na próxima retomada ou na próxima primeira página). Manifesto primeiro: uma queda nunca deixa o manifesto apontando para arquivo apagado.
- `discard_last_page()`: igual, com o identificador da última página.
- `rename(raw_name)`: `clean_document_name(raw_name)` (pode levantar), `NoOpenDocumentError` sem rascunho; mesmo nome limpo → devolve sem gravar; senão `save_manifest(draft.renamed(nome))` e troca o snapshot.
- `discard()` (cancelar): sem rascunho não faz nada. Senão `repository.delete_draft()`: (1) apaga `manifest.json` e faz `fsync` da pasta (se apagar falhar, levanta `DraftStorageUnavailableError` e o rascunho continua inteiro; uma falha no `fsync` depois de apagar só gera aviso: o manifesto já saiu); (2) apaga os arquivos conhecidos do inventário (falha só gera aviso: o que sobrar não tem manifesto e `_clear_leftovers` o apaga na próxima primeira página, ou a retomada na próxima abertura); nomes desconhecidos ficam. Depois troca o snapshot sem rascunho.
- Todas as mudanças de conteúdo retiram as marcas de intenção e de finalizado (R15).

#### 6.6.5 Nome do documento e do arquivo (M7 com R4)

`clean_document_name(raw_name)`, nesta ordem:

1. Normaliza para NFC (`unicodedata.normalize("NFC", ...)`).
2. Para cada caractere: espaço em branco de qualquer tipo (`str.isspace`: tabulação, quebra de linha, espaço não separável, U+2028) vira um espaço; caractere de `FORBIDDEN_FILE_NAME_CHARACTERS` vira `-`; caractere de categoria Unicode `Cc`, `Cf` ou `Cs` é removido (controle, marcas bidirecionais como U+202E, largura zero, hífen suave).
3. Sequências de espaços viram um espaço só.
4. Tira espaços das pontas; depois, se terminar em `.pdf` sem diferenciar maiúsculas, tira esse sufixo uma vez; depois tira pontos e espaços do início (`lstrip(". ")`) e do fim (`rstrip(". ")`). O sufixo sai **antes** do `lstrip`: na ordem inversa, `.pdf` e `..pdf` virariam `pdf` em vez de serem recusados com `invalid_document_name`.
5. Resultado vazio: se `raw_name.strip()` for vazio, devolve `""` (nome automático); senão `InvalidDocumentNameError` (só pontos, só caracteres invisíveis).
6. Mais de `MAXIMUM_DOCUMENT_NAME_CHARACTERS` (120) caracteres, ou mais de `MAXIMUM_DOCUMENT_NAME_BYTES` (200) bytes em UTF-8 → `InvalidDocumentNameError`. Nunca corta.

| Digitado | Nome limpo | Arquivo gravado |
|---|---|---|
| `Contrato do apartamento` | `Contrato do apartamento` | `Contrato do apartamento.pdf` |
| `  Notas fiscais 2026/10  ` | `Notas fiscais 2026-10` | `Notas fiscais 2026-10.pdf` |
| `Recibo: março` | `Recibo- março` | `Recibo- março.pdf` |
| `Linha 1⏎Linha   2` | `Linha 1 Linha 2` | `Linha 1 Linha 2.pdf` |
| `.oculto` | `oculto` | `oculto.pdf` |
| `Relatório.PDF` | `Relatório` | `Relatório.pdf` |
| `Pergunta?` | `Pergunta-` | `Pergunta-.pdf` |
| `abc` + U+202E + `fdp.exe` | `abcfdp.exe` | `abcfdp.exe.pdf` |
| `Ação` escrito em NFD (A + ◌̧ …) | `Ação` em NFC | `Ação.pdf` |
| `` ou `   ` | `` (automático) | `2026-10-17_00008.pdf` (sequência do modo rápido, data da finalização) |
| `...` ou `.pdf` | erro `invalid_document_name` | — |
| 121 letras, ou 60 emojis (240 bytes) | erro `invalid_document_name` | — |
| `Contrato do apartamento` com `Contrato do apartamento.pdf` já na pasta | `Contrato do apartamento` | `Contrato do apartamento (2).pdf`, depois `(3)`… |
| `contrato do apartamento` com `Contrato do apartamento.pdf` já na pasta (APFS) | `contrato do apartamento` | `contrato do apartamento (2).pdf` |

O título do PDF é o nome limpo; sem nome, `DEFAULT_PDF_TITLE_TEMPLATE` (`Digitalização AAAA-MM-DD HH:MM:SS`) com o `created_at` do rascunho.

#### 6.6.6 Reordenar (M8)

`DocumentDraft.reordered(page_identifiers)` aceita só uma permutação exata das páginas atuais: mesmo tamanho que `page_count`, sem repetição e com o mesmo conjunto de identificadores; qualquer outra lista (vazia, com um a mais, com um a menos, repetida, com identificador desconhecido, com identificador que não é texto) → `InvalidPageOrderError` (`422`). A ordem nova é exatamente a lista recebida. A mesma ordem de hoje responde `200` sem gravar e sem mudar a `revision`. Como a interface manda a lista inteira que estava vendo, uma lista velha (por exemplo, enviada depois que outra aba excluiu uma página) é recusada em vez de produzir uma ordem que ninguém viu; a interface então relê o documento.

#### 6.6.7 Concorrência (M9 com R9, R12 e R17)

- **Um único processo:** o `flock` de `drafts/.owner-lock` (R12). Tudo abaixo vale dentro desse processo.
- **Um único "digitalização em curso":** o `ScanProgressTracker` de hoje. O modo rápido e "Adicionar página" passam pelo mesmo `begin_scan`, então nunca há duas digitalizações e o `409 scan_already_running` é o mesmo nos dois modos.
- **Um único lock das mudanças no rascunho:** `asyncio.Lock` do `DocumentDraftService`. `add_page` segura o lock durante toda a digitalização da página (a gravação no passo 10 de 6.6.1 acontece com ele seguro) e **nunca espera** por ele: confere `ensure_can_add_page()` e toma o lock sem `await` no meio (R17); o lock só conta como livre se não tem dono **e** nenhuma edição espera por ele (contador `_waiting_edit_count`, porque logo depois de `release()` o `locked()` já é falso enquanto a edição acordada ainda não rodou). Toda edição passa por `_run_edit(edit)`:
  1. `scan_service.is_scan_in_progress()` → `ScanAlreadyRunningError` (`409`);
  2. conta-se como esperando e `lock.acquire()` (edições esperam: renomear, reordenar e excluir levam milissegundos; finalizar, alguns segundos);
  3. confere de novo o passo 1 (uma digitalização rápida pode ter começado durante a espera) → `409`;
  4. `return await asyncio.to_thread(edit)` (todo acesso a disco fora da thread do laço de eventos).
- `POST /api/document/pages` responde `409 scan_already_running` com digitalização em curso e `409 document_busy` com o lock ocupado ou uma edição esperando por ele.
- O modo rápido (`POST /api/scans`) não usa o lock: pode digitalizar enquanto um documento é finalizado, porque não toca no rascunho. As duas gravações na pasta de saída nunca colidem (`write_new_file` com nova tentativa).
- Leituras (`GET /api/document`, `/api/state`, miniaturas) não usam o lock: leem o `DraftSnapshot` imutável ou arquivos que nunca mudam depois de gravados.
- Corrida residual, aceita: dois pedidos de página aceitos (`202`) antes de qualquer tarefa começar. A segunda tarefa encontra a primeira com o lock (ou com `begin_scan` feito) e só registra no log: nenhuma página duplicada, nenhuma edição perdida. A interface já impede o segundo pedido na mesma aba (`is_start_request_pending`).

#### 6.6.8 Sobra em `current/` sem rascunho em memória (`DocumentDraftStore._clear_leftovers`, R14)

Chamada no passo 7 de 6.6.1, antes da primeira página de um rascunho novo. A retomada (6.6.2) segue a mesma classificação nos passos 2 a 4, com uma diferença: lá um manifesto válido sem marca confirmada é retomado; aqui ele é posto de lado.

1. `manifest = repository.load_manifest()`; `UnreadableDraftError` → `repository.set_aside_draft_folder()`, fim.
2. `manifest is None` → `repository.delete_files(take_inventory().known_file_names)` (sobra de um cancelamento ou de uma limpeza que falhou; nunca confirmada ou já descartada pelo usuário). Desconhecidos ficam.
3. `manifest.finished_document` e `finished_document_exists` → `repository.delete_draft()` (o PDF existe; sobra de uma finalização).
4. Qualquer outro manifesto válido → `repository.set_aside_draft_folder()` (só acontece se uma limpeza falhou de um jeito que deixou um rascunho legível para trás; pôr de lado é o que preserva as páginas).

Erros de disco aqui sobem traduzidos por `as_draft_storage_error` e a página falha com o código (o tracker registra), sem perder nada.

### 6.7 Interface (`web/static/`)

Scripts clássicos, sem build, carregados nesta ordem pelo `index.html`: `scan-trigger-policy.js`, `error-banner.js` (NOVO), `document-page-policy.js` (NOVO), `document-panel.js` (NOVO), `application.js`. Toda regra que decide algo fica em funções puras de `document-page-policy.js` (sem DOM), testadas pelo mesmo esquema da Tarefa 12: um harness Node (`vm`) imprime JSON e o pytest confere um conceito por teste (`node` ausente → testes pulados).

```js
// error-banner.js   (NOVO; o estado do banner sai do ScanPage para quebrar a dependência circular)
class ErrorBanner {
  constructor(elements) {}            // error_banner_content, error_banner_text
  report_action_error(message) {}     // null limpa
  set_scan_error(message) {}
  set_connection_error(message) {}
  render() {}                         // connection ?? action ?? scan: a regra de hoje (choose_error_message), movida
}
```

```js
// document-page-policy.js   (NOVO; funções puras)
const CAPTURE_MODES = Object.freeze({ SINGLE: "single", DOCUMENT: "document" });
const LARGE_DOCUMENT_PAGE_COUNT = 300;
const LARGE_DOCUMENT_SIZE_IN_BYTES = 1024 ** 3;
const DRAFT_STORAGE_WARNING_PAGES = 3;          // a guarda exige 1 GiB + 3 páginas (SAFETY_MARGIN_PAGES)
const PAGE_PLACEMENTS = Object.freeze({ BEFORE: "before", AFTER: "after" });
const DOCUMENT_KEY_ACTIONS = Object.freeze({
  IGNORE: "ignore", SUPPRESS: "suppress", DISCARD_LAST_PAGE: "discard_last_page", REQUEST_FINALIZE: "request_finalize",
  FOCUS_SCAN_BUTTON: "focus_scan_button",
});
const CONFIRMATION_KEY_ACTIONS = Object.freeze({ IGNORE: "ignore", SUPPRESS: "suppress" });
const DOCUMENT_EVENTS = Object.freeze({ NONE: "none", PAGE_ADDED: "page_added", PAGE_FAILED: "page_failed", EDITED: "edited" });
const DOCUMENT_ACTIONS = Object.freeze({
  MOVE: "move", DELETE: "delete", DISCARD_LAST: "discard_last", DROP: "drop", NAME_SAVED: "name_saved",
  DIALOG_CLOSED: "dialog_closed", FINALIZED: "finalized", CANCELLED: "cancelled",
});
const FOCUS_TARGETS = Object.freeze({ SCAN_BUTTON: "scan_button", SAME_BUTTON: "same_button", DELETE_BUTTON: "delete_button" });
const DRAFT_ENDINGS = Object.freeze({
  FINALIZED: "finalized", CANCELLED: "cancelled", LAST_PAGE_REMOVED_HERE: "last_page_removed_here", ENDED_ELSEWHERE: "ended_elsewhere",
});
const EXPECTED_SCAN_DURATION_TEXTS = Object.freeze({ document: "cerca de 15 s", document_economy: "cerca de 15 s", photo: "cerca de 75 s" });

function move_page_by_offset(page_identifiers, page_identifier, offset) {}  // cópia nova; fora dos limites → cópia igual
function move_page_to_position(page_identifiers, page_identifier, position) {}   // posição 1..M, limitada às pontas
function move_page_next_to(page_identifiers, page_drop) {}                  // page_drop = {dragged_identifier, target_identifier, placement}
function choose_drop_placement(pointer_horizontal_position, tile_box) {}     // tile_box = {left, width}; metade esquerda → BEFORE
function is_same_order(first_identifiers, second_identifiers) {}
function should_render_document_body(rendered_version, body_version) {}
  // versão = {draft_session, revision}: renderiza se nada foi renderizado, se a sessão é outra ou se a revision do corpo
  // é maior ou igual à mostrada (R19). Uma resposta atrasada de revision menor é ignorada.
function can_edit_document(document_activity) {}  // {scan_phase, is_start_request_pending, is_edit_request_pending}: idle e nada pendente
function can_start_document_page(document_activity) {}   // can_start_scan(...) e nenhum pedido de edição pendente (finalizar incluído)
function decide_document_key_action(key_event, document_activity) {}
  // document_activity = {capture_mode, page_count, can_edit, is_confirmation_open, scan_button}. Regras, nesta ordem:
  // 1. modo diferente de "document" ou confirmação aberta → IGNORE (a confirmação tem a própria regra)
  // 2. Escape → FOCUS_SCAN_BUTTON (de qualquer alvo; o blur do campo de nome salva o nome)
  // 3. tecla que não é Backspace, Enter ou NumpadEnter → IGNORE (o Espaço continua com decide_space_key_action)
  // 4. alvo INPUT, SELECT, TEXTAREA ou isContentEditable → IGNORE (Backspace apaga texto; Enter salva o nome)
  // 5. Enter num BUTTON que não é o scan_button → IGNORE (ativa aquele botão: ×, ◀, ▶, Cancelar…)
  // 6. key_event.repeat → SUPPRESS (segurar Backspace nunca descarta várias páginas)
  // 7. page_count 0 ou !can_edit → SUPPRESS (Enter no botão grande nunca vira "Adicionar página" no modo Documento)
  // 8. Backspace → DISCARD_LAST_PAGE; Enter → REQUEST_FINALIZE (que abre a confirmação)
function decide_confirmation_key_action(key_event, confirmation_state) {}
  // confirmation_state = {is_armed}. Vale em keydown e keyup dentro do <dialog>. Regras, nesta ordem:
  // 1. Escape → IGNORE (o evento cancel nativo fecha)
  // 2. key_event.repeat → SUPPRESS (segurar Enter abre a confirmação, mas nunca a confirma)
  // 3. Espaço → SUPPRESS (o reflexo de "adicionar página" nunca confirma; o botão nativo ativa no keyup do Espaço)
  // 4. !is_armed → SUPPRESS
  // 5. → IGNORE (Enter ou clique ativam o botão com foco)
  // Aberta pelo teclado, a confirmação se arma no keyup da tecla que a abriu; aberta pelo ponteiro, já nasce armada.
function decide_focus_after_action(action_context) {}
  // action_context = {action, is_keyboard_initiated, page_identifiers_after, acted_page_identifier, acted_position}
  // → {target, page_identifier}. Regras, nesta ordem:
  // 1. DISCARD_LAST, NAME_SAVED, DIALOG_CLOSED, FINALIZED, CANCELLED ou DROP → SCAN_BUTTON
  // 2. !is_keyboard_initiated (event.detail !== 0: clique) → SCAN_BUTTON
  // 3. MOVE pelo teclado → SAME_BUTTON na página movida (se esse botão ficou desabilitado na ponta, o do outro lado)
  // 4. DELETE pelo teclado → DELETE_BUTTON da página que ficou na mesma posição, senão da anterior, senão SCAN_BUTTON
function next_document_event(previous_observation, observation, previous_event) {}
  // observação = {draft_session, revision, page_count, scans_completed, last_error_code, capture_mode}. Regras, nesta ordem:
  // 1. sem observação anterior ou sessão diferente → NONE
  // 2. capture_mode mudou → EDITED
  // 3. page_count e scans_completed subiram juntos → PAGE_ADDED
  // 4. last_error_code passou de null para um código → PAGE_FAILED
  // 5. revision mudou → EDITED
  // 6. senão → previous_event
function decide_name_field_after_draft_end(draft_ending) {}   // "keep" só para LAST_PAGE_REMOVED_HERE (R3); "clear" nos outros
function decide_name_to_send(name_field) {}   // {typed_name, saved_name, document_exists} → nome aparado ou null
function should_switch_to_document_mode(switch_check) {}   // {document_body, capture_mode, switched_draft_session}: recovery.outcome "resumed", modo "single" e draft_session ainda não trocada
function should_warn_about_large_document(document_size) {}   // {page_count, estimated_size_in_bytes}: > 300 páginas ou > 1 GiB
function should_warn_about_draft_storage(draft_storage) {}    // !available ou estimated_pages_remaining < 3
function describe_expected_scan_duration(scan_preset) {}      // EXPECTED_SCAN_DURATION_TEXTS; preset desconhecido → o de "document"
function describe_page_count(page_count) {}                // "1 página" | "N páginas"
function describe_document_status(scan_phase, document_progress) {}
  // document_progress = {page_count, last_event, scan_preset, is_finalizing}. N = page_count + 1 nas fases ativas:
  // "Preparando a página N…", "Digitalizando a página N… (cerca de 75 s)", "Guardando a página N…",
  // "Finalizando o PDF (N páginas)…",
  // PAGE_FAILED: "A última página não foi adicionada. Coloque a folha de novo e aperte Espaço.",
  // PAGE_ADDED: "Página N adicionada. Coloque a próxima folha e aperte Espaço; Enter finaliza.",
  // outro evento com páginas: "N páginas no documento. Coloque a próxima folha e aperte Espaço; Enter finaliza.",
  // sem páginas: "Modo Documento: coloque a primeira folha no vidro e aperte Espaço."
function describe_page_removal(page_removal) {}
  // {action: DISCARD_LAST | DELETE, position, remaining_page_count}: "Página 12 descartada. O documento tem 11 páginas." |
  // "Página 5 excluída. O documento tem 11 páginas." | com 0 restantes: "Página 1 excluída. O documento foi encerrado."
function describe_page_move(position_before, position_after) {}   // "Página 3 movida para a posição 2"
function describe_recovery(recovery) {}
  // resumed sem perdas: "Documento em andamento recuperado: 41 páginas."
  // resumed com perdas: "Documento em andamento recuperado: 41 páginas. A página 37 não pôde ser recuperada; digitalize-a de
  //   novo." (plural: "As páginas 5 e 37 não puderam ser recuperadas; digitalize-as de novo.")
  // pages_lost: "Não consegui recuperar nenhuma página do documento em andamento."
  // set_aside: "Não consegui ler o documento em andamento. As páginas foram guardadas em <pasta>."
  // failed: "Não consegui abrir o documento em andamento. Nada foi apagado: feche o Digitalizadora e abra de novo.
  //   Detalhes em ~/Library/Logs/Digitalizadora."
  // Com set_aside_folder em resumed ou pages_lost, acrescenta: "Os arquivos danificados foram guardados em <pasta>."
function describe_possible_previous_save(document) {}
  // finished_document_path: "Este documento talvez já tenha sido salvo como <caminho>. Confira antes de finalizar de novo."
  // finalization_started_at: "Uma finalização deste documento foi interrompida às HH:MM. Confira na pasta de saída se o PDF
  //   já existe antes de finalizar de novo."   ·   nenhum dos dois → null
function describe_pending_document(page_count) {}          // "Documento em andamento: N páginas" (no modo Rápido)
function describe_finished_document(last_finished_document) {}   // "Pronto! Salvo como <arquivo> (N páginas)"
```

```js
// document-panel.js   (NOVO; liga o DOM às regras; sem regra própria)
class DocumentPanel {
  constructor(elements, page_services) {}
  // page_services = {send_request, format_byte_count, error_banner, focus_scan_button} (montados por build_scan_page)
  show() {} hide() {}
  apply_summary(document_summary, scan_observation) {}   // de /api/state; scan_observation = {scan_phase, scans_completed,
                                                          // last_error_code, capture_mode}; sessão ou revision diferente → refresh_document();
                                                          // calcula next_document_event; summary de >0 para 0 páginas sem
                                                          // pedido desta aba → ENDED_ELSEWHERE
  async refresh_document() {}            // GET /api/document → render_document(body) se should_render_document_body; devolve o corpo
  render_document(body) {}               // grade reaproveita um <li> por identificador (miniatura não recarrega ao reordenar)
  describe_status(scan_phase) {}         // describe_document_status com o estado do painel (o ScanPage escreve na status-line)
  is_edit_request_pending() {}
  has_pages() {}
  async discard_last_page(action_origin) {}              // DELETE /api/document/pages/last
  async delete_page(page_identifier, action_origin) {}   // DELETE /api/document/pages/<identificador>
  async move_page(page_move, action_origin) {}           // page_move = {page_identifier, offset} → move_page_by_offset → PUT
  async move_page_to(page_identifier, action_origin) {}  // move-page-dialog → move_page_to_position → PUT
  async drop_page(page_drop) {}                          // move_page_next_to → PUT (nada se is_same_order)
  async save_name() {}                   // decide_name_to_send → PUT /api/document/name; resposta substitui o campo
  async request_finalize() {}            // confirmação → save_name pendente (422: para, foco no campo, mensagem no banner)
                                         // → POST /api/document/finalize
  async request_cancel() {}              // confirmação (foco inicial em "Voltar") → DELETE /api/document
  confirm_action(confirmation) {}        // Promise<boolean>; confirmation = {question, accept_label, initial_focus, opened_by_keyboard}
}
// action_origin = {is_keyboard_initiated} (event.detail === 0); depois de cada ação o painel aplica decide_focus_after_action.
// 422 invalid_page_order, 404 page_not_found ou 404 no_open_document → mensagem no banner e refresh_document().
// 409 damaged_document_page → mensagem no banner, classe is-damaged no <li> do page_identifier do corpo e foco no × dele.
```

```js
// application.js   (MUDA)
function build_scan_page(elements) {}
  // const error_banner = new ErrorBanner(elements);
  // const document_panel = new DocumentPanel(elements, {send_request, format_byte_count, error_banner,
  //                                                     focus_scan_button: () => elements.scan_button.focus()});
  // return new ScanPage(elements, {document_panel, error_banner});
  // A página e o scan-page-harness.js usam esta função; ScanPage nunca cria colaboradores.
class ScanPage { constructor(elements, page_parts) {} }   // page_parts = {document_panel, error_banner}
function describe_draft_storage(draft_storage) {}          // "Espaço no Mac para as páginas: X — cabem ~N páginas"
```

**`index.html`** ganha: seletor de modo `capture-mode-single` / `capture-mode-document` (rádios `name="capture-mode"`, legenda "Modo", rótulos "Rápido" e "Documento"); `id="output-format-group"` no grupo PDF/JPG existente (escondido no modo Documento); o rótulo do preset passa de "Modo de digitalização" para "Qualidade", e as opções passam a "Texto (300 dpi, cor)", "Texto econômico (200 dpi, cinza)" e "Foto (600 dpi, cor)" (valores da API iguais); `document-pending-notice` com `document-pending-text` e `return-to-document-button` ("Voltar ao modo Documento"), visível só no modo Rápido com rascunho; a seção `document-section` com `document-name-input` (sem `maxlength`; rótulo "Nome do documento (opcional)"), `document-recovery-notice`, `document-previous-save-notice`, `document-large-warning`, `document-empty-message`, `document-page-grid` (`<ol>`), `document-summary`, `draft-storage-line`, `draft-storage-warning`, `discard-last-page-button` ("Descartar última", dica Backspace), `cancel-document-button`, `finalize-document-button` ("Finalizar PDF", dica Enter), `document-finished-message` e `document-announcement` (`role="status"`, visualmente oculto); `confirmation-dialog` (`<dialog>`) com `confirmation-text`, `confirmation-accept-button` e `confirmation-reject-button`; e `move-page-dialog` (`<dialog>`) com `move-page-position-input` (`type="number"`, rótulo "Nova posição"), `move-page-accept-button` ("Mover") e `move-page-reject-button` ("Voltar").

Comportamento:

- O botão grande é o mesmo `scan-button`: "Digitalizar" no modo Rápido, "Adicionar página" no Documento. `ScanPage.start_scan()` (mesmo nome, para o harness da Tarefa 12) manda `POST /api/scans` ou `POST /api/document/pages` conforme `capture_mode`; ajuste sem `capture_mode` (servidor antigo) vale "single". No modo Documento o botão segue `can_start_document_page` e mostra "Finalizando…" durante a finalização.
- O texto "Digitalizando…" dos dois modos passa a usar `describe_expected_scan_duration` com o preset salvo: "Digitalizando… (cerca de 75 s)" na qualidade Foto (some o "no modo Foto", que confundia com o seletor novo).
- Cada página da grade: `<li draggable="true" aria-label="Página N de M">` com `<img alt="Miniatura da página N" loading="lazy" decoding="async">` (ou o quadro "Página N" se a miniatura der 404), número, botões ◀ e ▶ (`aria-label="Mover a página N para a esquerda/direita"`, desabilitados nas pontas), × (`aria-label="Excluir a página N"`) e "Mover para…" (`aria-label="Mover a página N para outra posição"`, abre `move-page-dialog` com a posição atual preenchida e selecionada, de 1 a M, para o que se digita substituí-la). Os botões ficam no DOM nessa ordem, que é a ordem visual e, portanto, a ordem do Tab. Arrastar: `dragstart` grava o identificador em `dataTransfer` (`text/plain`); `dragover` chama `choose_drop_placement` e marca o lado com as classes `is-drop-before`/`is-drop-after`; `drop` chama `drop_page`.
- Anúncios em `document-announcement`: `describe_page_move` depois de mover; `describe_page_removal` depois de descartar ou excluir.
- **Foco** (sempre por `decide_focus_after_action`): depois de "Descartar última" (botão ou Backspace), de fechar qualquer `<dialog>`, de salvar o nome com Enter, de soltar um arrasto e de qualquer ação da grade feita com o ponteiro, o foco vai para o `scan-button`, para que o próximo Espaço adicione uma página e nunca repita a ação. Só ações da grade feitas pelo teclado mantêm o foco na grade. Esc fora de diálogos leva o foco ao `scan-button`.
- Teclado (M10): Espaço continua com `decide_space_key_action`; Backspace, Enter e Esc com `decide_document_key_action`; dentro de um `<dialog>`, um ouvinte em fase de captura aplica `decide_confirmation_key_action` em keydown e keyup. A confirmação de finalizar abre com o foco em "Finalizar" (aberta pelo teclado, arma no keyup da tecla que a abriu se ela ainda está apertada, como o Enter, que clica no keydown; já nasce armada se não está, como o Espaço, que clica só no keyup) e a de cancelar com o foco em "Voltar"; Esc fecha pelo evento `cancel` nativo.
- Edição desabilitada (botões, arrastar, Backspace, Enter) enquanto `scan_phase` não for `idle` ou houver pedido pendente; o seletor de modo e o botão "Voltar ao modo Documento" também. Salvar o nome não conta como pedido pendente (o `blur` do campo acontece no `mousedown` do botão grande e bloquear engoliria o clique).
- Status: `describe_document_status`, com `last_event` de `next_document_event`; uma edição aceita nesta aba troca o último evento para `EDITED` (para não repetir "Página N adicionada" de uma página que a própria aba acabou de remover); a mensagem de falha some na primeira edição aceita ou troca de modo.
- Retomada e avisos: se o corpo do documento trouxer `recovery`, `document-recovery-notice` mostra `describe_recovery`, e só então (`should_switch_to_document_mode`) o modo salvo "single" troca para "document" com `PUT /api/settings`, uma vez por `draft_session` (lembrada no `localStorage` do navegador; o servidor mantém o `recovery` até a próxima mudança aceita do rascunho, e trocar o modo ou digitalizar no modo Rápido não é mudança do rascunho). Uma recarga comum da página, ou um rascunho deixado de propósito enquanto se usa o modo Rápido (inclusive depois de voltar a Rápido após uma retomada), não troca o modo; uma nova queda e uma nova retomada geram outra `draft_session` e trocam de novo. `document-previous-save-notice` mostra `describe_possible_previous_save` enquanto o rascunho tiver uma das marcas.
- Modo Rápido com rascunho: `document-pending-notice` com `describe_pending_document` e o botão que volta ao modo Documento.
- Barra: `describe_page_count` + " · ~" + `format_byte_count(estimated_size_in_bytes)`; com `should_warn_about_large_document`, "Documento grande: finalizar pode levar alguns segundos e usar bastante memória."
- Espaço: no modo Documento a `storage-line` do modo rápido fica escondida e `draft-storage-line` mostra `describe_draft_storage`; com `should_warn_about_draft_storage`, `draft-storage-warning` diz "Pouco espaço no disco do Mac para as páginas do documento. Libere espaço antes de continuar."
- Fim do documento: `document-finished-message` mostra `describe_finished_document(body.last_finished_document)` sempre que o corpo o trouxer e não houver rascunho, inclusive numa aba recarregada ou em outra aba. O painel `last-scan-panel` ("Último arquivo") fica escondido no modo Documento.
- Nome: salvo no `blur` e no Enter do campo (o Enter faz o `blur()` do campo e só então pede o foco do botão grande), se houver rascunho; durante uma digitalização o servidor recusa edições (`409 scan_already_running`), então o nome fica no campo marcado como por enviar e sai quando os controles voltam a ficar habilitados; sem rascunho fica no campo e vai com `decide_name_to_send` quando o resumo mostrar o documento pela primeira vez e antes de finalizar. Quando o rascunho termina, `decide_name_field_after_draft_end` decide: finalizar, cancelar ou o fim visto vindo de outra aba limpam o campo e o `saved_name`; só a exclusão da única página feita nesta aba o mantém (R3).

### 6.8 Dublês de teste novos (`tests/fakes/`)

```python
class SequentialPageIdentifiers:      # T18b: "0000000000000001", "0000000000000002"… (identificadores válidos)
    def __call__(self) -> str: ...
class ScriptedFileWriter(AtomicFileWriter):   # T17, T18b, T18c: grava de verdade, mas falha uma vez por nome configurado
    def __init__(self, failures_by_file_name: Mapping[str, OSError]) -> None: ...
    written_file_names: list[str]             # vale para write_new_file, write_new_file_from e replace_file
class BlockingFreeSpaceReader:        # T19: Callable[[Path], int] que segura a primeira leitura até release()
    def __init__(self, free_space_in_bytes: int) -> None: ...
    entered: threading.Event                  # posto quando uma leitura começa
    def release(self) -> None: ...
    def __call__(self, folder: Path) -> int: ...
    # Injetado no StorageGuardService do DocumentFinalizer: ensure_space_for_file é a primeira coisa que finalizar faz com o
    # lock seguro (6.6.3, passo 3). O teste espera `await asyncio.to_thread(reader.entered.wait)`, faz os pedidos
    # concorrentes e chama release().
class StubDocumentDraftService:       # T20: dublê por duck typing para os controllers (registra chamadas, falha sob demanda)
    add_page_refusal: Exception | None
    failure: Exception | None
    draft_snapshot: DraftSnapshot
    draft_storage: DraftStorageState
    calls: list[str]
def build_document_page(page_identifier: str, size_in_bytes: int = 3) -> DocumentPage: ...   # T15
def build_document_draft(page_count: int) -> DocumentDraft: ...                               # T15
def write_draft_folder(drafts_folder: Path, draft: DocumentDraft) -> None: ...                # T17: manifesto + páginas com o tamanho certo
def seed_draft_folder(drafts_folder: Path, page_contents: Sequence[bytes]) -> DocumentDraft: ...   # T17: páginas JPEG reais
# write_draft_folder e seed_draft_folder escrevem com Path.write_bytes, sem fsync, para os testes ficarem abaixo de 100 ms.
```

Movidos de `tests/services/test_scan_service.py` para `tests/fakes/` na T18a, sem mudança de comportamento (o teste de hoje só troca os imports):

```python
# tests/fakes/observing_scanner_gateway.py
class ObservingScriptedScannerGateway(ScriptedScannerGateway): ...   # scan_started, release_scan, hold_scans_open(), phase_during_scan
# tests/fakes/recording_scan_destinations.py
class RecordingScanOutputService: ...                 # o de hoje: fases, threads, falhas injetáveis, devolve StoredScan
class RecordingDocumentPageDestination(RecordingScanOutputService):   # NOVO: mesmo registro, store devolve um DocumentPage
    def __init__(self, progress_tracker: ScanProgressTracker, stored_page: DocumentPage) -> None: ...
```

### 6.9 Mudanças em arquivos existentes

| Arquivo | Classe ou função | Mudança | Testes existentes que mudam |
|---|---|---|---|
| `__main__.py` | `PORT_IN_USE_MESSAGE`, `run_application` | mensagem nova; `DraftFolderInUseError` explicado e código 1 | `tests/test_main.py`: acrescentar o caso da segunda cópia (o de porta em uso confere só o começo da frase, que não muda) |
| `domain/application_settings.py` | `ApplicationSettings` | campo `capture_mode: CaptureMode = CaptureMode.SINGLE` no fim | nenhum (o padrão mantém as construções de 3 argumentos) |
| `domain/errors.py` | — | 13 classes novas e `as_draft_storage_error` (6.2) | `tests/domain/test_errors.py`: acrescentar as linhas novas na tabela (os testes de hoje continuam passando) |
| `domain/ports.py` | `ScanOutputRepository`, `DocumentDraftRepository` | `save_document` novo; porta nova | `tests/domain/test_ports.py`: `EXPECTED_PORT_NAMES` e `EXPECTED_METHOD_NAMES_BY_PORT` |
| `repositories/atomic_file_writer.py` | `AtomicFileWriter` | `write_new_file_from`; `write_new_file` delega | nenhum |
| `repositories/json_application_settings_repository.py` | `parse_application_settings`, `save` | lê `capture_mode` chave a chave com padrão `"single"`; grava a quarta chave | `test_save_writes_the_documented_json_shape` |
| `repositories/file_system_scan_output_repository.py` | `FileSystemScanOutputRepository` | `save_document` em fluxo; laço de nomes vira auxiliar privado | nenhum |
| `services/application_settings_service.py` | `SettingsUpdate`, `update` | `capture_mode: str \| None = None` (None mantém o atual) | nenhum (o `saved == ApplicationSettings(3 argumentos)` continua igual) |
| `services/scan_progress_tracker.py` | `ScanProgressTracker` | `mark_page_added()` | nenhum |
| `services/scan_service.py` | `ScanService` | `scan_document_page`; sequência extraída para `_capture_and_store` e tratamento para `_recording_failures` | `tests/services/test_scan_service.py`: só os imports dos dois dublês movidos para `tests/fakes/` |
| `services/storage_guard_service.py` | `StorageGuardService` | `ensure_space_for_file` | nenhum |
| `services/pdf_assembly_service.py` | `PdfAssemblyService` | `DEFAULT_PDF_TITLE_TEMPLATE`, `PdfDocumentMetadata`, `write_pdf_at_embedded_resolutions`, `_conversion_options` comum | nenhum |
| `services/scan_encoder.py` | `ScanEncoder` | usa `DEFAULT_PDF_TITLE_TEMPLATE` (uma linha; mesmo texto) | nenhum |
| `controllers/error_message_catalog.py` | `ERROR_MESSAGES` | 12 mensagens novas | `tests/controllers/test_error_message_catalog.py`: `EXPECTED_MESSAGES` e `DOMAIN_ERROR_CLASS_COUNT` (11 → 24) |
| `controllers/settings_body.py` | `build_settings_body` | chave `capture_mode` | `test_settings_controller.py` (`test_get_settings_returns_the_saved_settings`, `test_put_settings_returns_the_new_settings`); `test_state_controller.py` (`test_state_contains_the_settings`); `test_application_factory.py` (`SETTINGS_BODY`); `tests/test_composition_root.py` (`test_state_endpoint_reports_default_settings`) |
| `controllers/settings_controller.py` | `SettingsRequestBody` | `capture_mode: str \| None = None` repassado ao `SettingsUpdate` | nenhum além dos acima |
| `controllers/state_controller.py` | `StateController` | parâmetro `document_draft_service`; chave `document` | `test_state_controller.py` (fixture `client` e `test_state_has_exactly_the_documented_keys`); `test_application_factory.py` (construção) |
| `application_factory.py` | `ApplicationControllers`, `ErrorResponses` | campo `document`; `VALIDATION_ERROR_CODES_BY_PATH` | `test_application_factory.py` (construção de `ApplicationControllers`) |
| `composition_root.py` | `build_container` e auxiliares | relógio e encoder únicos; peças novas; `claim_exclusive_access()` e `recover_draft()` | só o já citado `test_state_endpoint_reports_default_settings` |
| `web/static/index.html`, `application.js`, `application.css` | `ScanPage`, `collect_elements`, `build_scan_page` | modo, seção Documento, teclado, os dois `<dialog>`, textos das opções de qualidade, banner movido para `ErrorBanner`, `ScanPage(elements, page_parts)` | `tests/web/test_static_assets.py` (`STATIC_FILE_NAMES` com os três scripts novos, conferência de identificadores também em `document-panel.js`, ordem dos scripts); `tests/web/scan-page-harness.js` (`SCRIPT_FILE_NAMES` com os scripts novos, `build_scan_page(collect_elements())` no lugar de `new ScanPage(...)`, `SETTINGS` com `capture_mode: "single"`, falso DOM movido para `tests/web/fake-browser.js`); `tests/web/test_scan_page_behaviour.py` (`SCANNING_MESSAGE` passa a "Digitalizando… (cerca de 15 s)") |
| `docs/acceptance-checklist.md`, `README.md` | — | Parte C (modo Documento), seção curta no README e os nomes novos das opções de qualidade | — |

Ficam iguais: `ScanOutputService`, `ThumbnailService`, `JpegResolutionService`, `ApplicationStateService`, `ScanController`, `PreviewController`, `PrinterController`, `LocalRequestGuard`, `configuration.py`, o simulador e `tests/integration/test_scan_flow.py`.

## 7. Tarefas novas do plano (T15 a T22, depois da Tarefa 14)

Cada tarefa parte do código integrado das anteriores, segue TDD (teste que falha → implementação → todos os testes verdes → `make lint`) e só muda os arquivos listados. A antiga Tarefa 18 foi dividida em 18a, 18b e 18c; os outros números não mudam.

### Task 15: Domínio do documento, erros e portas

**Files:**
- Create: `src/digitalizadora/domain/document_draft.py`, `domain/document_draft_reconciliation.py`, `domain/document_name_policy.py`, `domain/document_pdf_to_save.py`, `tests/fakes/document_drafts.py`
- Modify: `domain/errors.py`, `domain/ports.py`, `controllers/error_message_catalog.py`
- Test: `tests/domain/test_document_draft.py`, `test_document_draft_reconciliation.py`, `test_document_name_policy.py`, `tests/fakes/test_document_drafts.py`; Modify: `tests/domain/test_errors.py`, `tests/domain/test_ports.py`, `tests/controllers/test_error_message_catalog.py`

**Interfaces:**
- Consumes: `ColorMode`, `ScanResult`, `DigitalizadoraError`, `InsufficientStorageError`, `OutputFolderUnavailableError`, `EncodedScan` (Tarefa 2).
- Produces: `DocumentPage`, `DocumentPageFiles`, `DocumentDraft`, `DocumentFinalizationResult`, `RecoveryOutcome`, `DraftRecoveryReport`, `DraftSnapshot`, `PAGE_IDENTIFIER_PATTERN`, `generate_page_identifier`, `generate_draft_session`, `is_page_identifier`, `page_file_name`, `thumbnail_file_name`, `DraftFileInventory`, `DraftReconciliation`, `reconcile_draft`, `clean_document_name`, `build_document_file_name`, `DocumentPdfToSave`, as 13 classes de erro, `as_draft_storage_error`, `ScanOutputRepository.save_document`, `DocumentDraftRepository`, as 12 mensagens do catálogo, `build_document_page`, `build_document_draft`.

Só regras puras: o rascunho imutável e as suas transformações (acrescentar, excluir, descartar a última, reordenar com a validação da M8, renomear, as duas marcas e a retirada delas em toda mudança de conteúdo), a reconciliação da retomada (quais páginas ficam, quais arquivos vão para o lixo e quais são postos de lado), a limpeza do nome com todos os exemplos de 6.6.5, o nome numerado e a tradução única para os erros do rascunho. Acrescenta os erros com o texto do catálogo e as portas (só os Protocols; ninguém as implementa ainda). Nada toca em disco.

### Task 16: Modo de captura nos ajustes

**Files:**
- Create: `src/digitalizadora/domain/capture_mode.py`
- Modify: `domain/application_settings.py`, `repositories/json_application_settings_repository.py`, `services/application_settings_service.py`, `controllers/settings_body.py`, `controllers/settings_controller.py`
- Test: `tests/domain/test_capture_mode.py`; Modify: `tests/domain/test_application_settings.py`, `tests/repositories/test_json_application_settings_repository.py`, `tests/services/test_application_settings_service.py`, `tests/controllers/test_settings_controller.py`, `tests/controllers/test_state_controller.py`, `tests/controllers/test_application_factory.py`, `tests/test_composition_root.py`

**Interfaces:**
- Consumes: `ApplicationSettings`, `JsonApplicationSettingsRepository`, `ApplicationSettingsService`, `SettingsController` (Tarefas 2, 7, 11).
- Produces: `CaptureMode`; `ApplicationSettings.capture_mode`; `settings.json` e `GET/PUT /api/settings` e `/api/state` com `capture_mode`.

Acrescenta o modo salvo (M1) de ponta a ponta sem quebrar quem não o conhece: arquivo antigo sem a chave vale `"single"`, valor desconhecido no arquivo vale `"single"` sem perder a pasta de saída, corpo `PUT` antigo de três chaves mantém o modo atual, valor desconhecido no `PUT` responde `422 invalid_settings`. Atualiza os testes que conferem o formato exato dos ajustes (lista em 6.9).

### Task 17: Persistência do rascunho, gravação em fluxo e PDF com resoluções misturadas

**Files:**
- Create: `src/digitalizadora/repositories/document_manifest_codec.py`, `repositories/file_system_document_draft_repository.py`, `tests/fakes/scripted_file_writer.py`
- Modify: `repositories/atomic_file_writer.py`, `repositories/file_system_scan_output_repository.py`, `services/storage_guard_service.py`, `services/pdf_assembly_service.py`, `services/scan_encoder.py`, `tests/fakes/document_drafts.py` (`write_draft_folder`, `seed_draft_folder`)
- Test: `tests/repositories/test_document_manifest_codec.py`, `test_file_system_document_draft_repository.py`, `tests/fakes/test_scripted_file_writer.py`; Modify: `tests/repositories/test_atomic_file_writer.py`, `tests/repositories/test_file_system_scan_output_repository.py`, `tests/services/test_storage_guard_service.py`, `tests/services/test_pdf_assembly_service.py`

**Interfaces:**
- Consumes: as peças da Tarefa 15; `AtomicFileWriter`, `prepare_output_folder`, `translate_storage_error` (Tarefa 7); `Clock`.
- Produces: `encode_manifest`, `decode_manifest`, `MANIFEST_FORMAT_VERSION`, `AtomicFileWriter.write_new_file_from`, `FileSystemDocumentDraftRepository` (com `claim_exclusive_access`), `translate_draft_storage_error`, `FileSystemScanOutputRepository.save_document`, `StorageGuardService.ensure_space_for_file`, `DEFAULT_PDF_TITLE_TEMPLATE`, `PdfDocumentMetadata`, `PdfAssemblyService.write_pdf_at_embedded_resolutions`, `ScriptedFileWriter`, `write_draft_folder`, `seed_draft_folder`.

Implementa a pasta e o manifesto da seção 6.3 (versão 1, leitura estrita, chaves desconhecidas ignoradas), o lock de processo único (R12), as operações de arquivo do repositório do rascunho (gravação atômica da página e da miniatura, inventário, apagar o rascunho com o manifesto primeiro e só os arquivos conhecidos, pôr de lado a pasta ou arquivos soltos), a gravação em fluxo sem sobrescrever, o PDF com nome escolhido e a montagem que respeita a densidade de cada página (R2) sem juntar as páginas na memória (R18). Sem regra de negócio além da tradução de erros.

### Task 18a: Sequência única de digitalização para a página do documento

**Files:**
- Create: `src/digitalizadora/services/scan_destination.py`, `tests/fakes/observing_scanner_gateway.py`, `tests/fakes/recording_scan_destinations.py`
- Modify: `services/scan_progress_tracker.py`, `services/scan_service.py`
- Test: `tests/services/test_scan_service_document_page.py`; Modify: `tests/services/test_scan_progress_tracker.py` (só acréscimos), `tests/services/test_scan_service.py` (só imports)

**Interfaces:**
- Consumes: `ScanService`, `ScanProgressTracker` (Tarefas 8 e 10); `ScriptedScannerGateway`, `FixedGatewayProvider`, `FixedClock`, `build_document_page`.
- Produces: `ScanDestination`, `ScanProgressTracker.mark_page_added`, `ScanService.scan_document_page`, `ObservingScriptedScannerGateway` e `RecordingScanOutputService` em `tests/fakes/`, `RecordingDocumentPageDestination`.

Refatora o `ScanService` para que o modo rápido e a página do documento usem a mesma sequência (`_capture_and_store`) e o mesmo tracker, sem mudar nenhum teste do modo rápido. Os testes novos cobrem só o que difere do modo rápido (a ordem das fases e as threads já estão cobertas por `test_scan_service.py`).

### Task 18b: Estado do rascunho, edições e captura da página

**Files:**
- Create: `src/digitalizadora/services/document_draft_store.py`, `services/document_page_capture.py`, `tests/fakes/sequential_page_identifiers.py`
- Test: `tests/services/test_document_draft_store.py`, `tests/services/test_document_draft_leftovers.py`, `tests/services/test_document_page_capture.py`

**Interfaces:**
- Consumes: Tarefas 15, 17 e 18a; `ScanEncoder` (Tarefa 6), `StorageGuardService` (Tarefa 8); `FixedClock`, `RecordingFreeSpaceReader`, `build_sample_jpeg`, `ScriptedFileWriter`.
- Produces: `CapturedPage`, `DraftIdentitySource`, `DraftStorageState`, `DocumentDraftStore` (todos os métodos de 6.4 menos `recover`), `DocumentPageCapture`, `SequentialPageIdentifiers`.

Implementa o estado do rascunho com a gravação atômica (6.6.1), as edições (6.6.4), a sobra sem rascunho (6.6.8), a conferência das páginas antes de finalizar e as marcas de intenção e de finalizado, testados contra o repositório real numa pasta temporária.

### Task 18c: Retomada na abertura

**Files:**
- Modify: `src/digitalizadora/services/document_draft_store.py` (`recover`)
- Test: `tests/services/test_document_draft_recovery.py`

**Interfaces:**
- Consumes: Tarefa 18b; `write_draft_folder`, `ScriptedFileWriter`.
- Produces: `DocumentDraftStore.recover` e o `DraftRecoveryReport` de cada caso.

A retomada completa de 6.6.2, com os estados de queda montados direto no disco (lista em 8).

### Task 19: Serviço do documento: lock, edições e finalização segura

**Files:**
- Create: `src/digitalizadora/services/document_finalizer.py`, `services/document_draft_service.py`, `tests/fakes/blocking_free_space_reader.py`
- Test: `tests/services/test_document_finalizer.py`, `tests/services/test_document_draft_service.py`, `tests/services/test_document_draft_concurrency.py`

**Interfaces:**
- Consumes: Tarefas 15, 17, 18a e 18b; `ScanService`, `PdfAssemblyService`, `ScanOutputRepository`, `StorageGuardService`, `Clock`; `InMemoryApplicationSettingsRepository`, `ObservingScriptedScannerGateway`, `BlockingFreeSpaceReader`, `seed_draft_folder`.
- Produces: `DocumentAssemblyInput`, `DocumentFinalizer`, `DocumentDraftCollaborators`, `DocumentDraftService` (com `ensure_can_add_page`, `snapshot`, `describe_draft_storage`, `recover_draft`, `read_thumbnail` e as sete operações assíncronas), `BlockingFreeSpaceReader`.

Junta as peças: o lock único e as regras de 409 (6.6.7, R17), as edições passando por `_run_edit` em thread, e a finalização (6.6.3) com a conferência de pasta, espaço e páginas antes de montar, a marca de intenção, a montagem em fluxo em thread, o nome sem colisão, a marca M6, o atalho de um PDF já gravado e a limpeza do rascunho, inclusive quando a marca ou a limpeza falham depois de o PDF existir.

### Task 20: API do documento, estado, composição e partida

**Files:**
- Create: `src/digitalizadora/controllers/document_body.py`, `controllers/document_controller.py`, `tests/fakes/stub_document_draft_service.py`
- Modify: `controllers/state_controller.py`, `application_factory.py`, `composition_root.py`, `__main__.py`
- Test: `tests/controllers/test_document_controller.py`, `tests/controllers/test_document_body.py`, `tests/integration/test_document_flow.py`; Modify: `tests/controllers/test_state_controller.py`, `tests/controllers/test_application_factory.py`, `tests/test_composition_root.py`, `tests/test_main.py`

**Interfaces:**
- Consumes: Tarefas 16 e 19; `ErrorMessageCatalog`, `ERROR_MESSAGES`, `build_error_body`, `ApplicationSettingsService`, `ErrorResponses`, `build_container`, `create_application`; a impressora falsa (`create_fake_escl_scanner_app`), `build_application_configuration` e `seed_draft_folder`.
- Produces: as nove rotas de 6.5, a chave `document` de `/api/state`, `ApplicationControllers.document`, `VALIDATION_ERROR_CODES_BY_PATH`, a montagem completa com `claim_exclusive_access()` e `recover_draft()` na partida, a mensagem da segunda cópia em `__main__`.

Traduz o serviço para HTTP com os status de 6.5 e os corpos exatos, mapeia corpo malformado para o código da rota (R11) e monta tudo na raiz de composição. Os testes de integração são um por conceito, abaixo de 100 ms cada: uma página acrescentada pela impressora falsa aparece em `GET /api/document`; um rascunho de três páginas semeado com `seed_draft_folder` finalizado gera o PDF com as páginas na ordem; a retomada pela raiz (rascunho semeado com órfão e com marca M6); um segundo container na mesma pasta de dados recusa a partida. Reordenar, excluir e renomear ficam nos testes do controller e do serviço.

### Task 21: Interface do modo Documento

**Files:**
- Create: `src/digitalizadora/web/static/error-banner.js`, `web/static/document-page-policy.js`, `web/static/document-panel.js`, `tests/web/fake-browser.js`, `tests/web/document-page-policy-harness.js`, `tests/web/document-panel-harness.js`
- Modify: `web/static/index.html`, `web/static/application.js`, `web/static/application.css`, `tests/web/scan-page-harness.js`
- Test: `tests/web/test_document_page_policy.py`, `tests/web/test_document_panel_behaviour.py`; Modify: `tests/web/test_static_assets.py`, `tests/web/test_scan_page_behaviour.py` (`SCANNING_MESSAGE`)

**Interfaces:**
- Consumes (HTTP): as rotas de 6.5, `GET/PUT /api/settings` com `capture_mode`, `GET /api/state` com `document`.
- Consumes (JS): `decide_space_key_action`, `can_start_scan` (Tarefa 12), `send_request`, `format_byte_count`.
- Produces: `ErrorBanner`, as funções de `document-page-policy.js`, a classe `DocumentPanel`, `build_scan_page`, `ScanPage(elements, page_parts)`, o `index.html` com os identificadores de 6.7.

Seletor Rápido | Documento, grade com miniaturas preguiçosas, arrastar e soltar, botões ◀ ▶ "Mover para…" ×, nome com envio adiado e limpo ao fim do documento, barra com contagem e tamanho, avisos de documento grande, de espaço do rascunho, de retomada e de PDF talvez já salvo, confirmações com `<dialog>` à prova de tecla segurada, teclado da M10 com a regra de foco, anúncios para leitor de tela e o resultado da finalização visível em qualquer aba. Toda decisão fica nas funções puras; o painel só liga o DOM. O falso DOM do harness da Tarefa 12 vai para `fake-browser.js` (com `createElement`, `replaceChildren`, `classList`, `focus` e `<dialog>` falsos) sem mudar nenhum cenário existente.

### Task 22: Checklist de aceitação e README

**Files:**
- Modify: `docs/acceptance-checklist.md`, `README.md`

**Interfaces:**
- Consumes: o app completo (Tarefas 15 a 21), `make simulator`, `make run-simulated`.
- Produces: Parte C do checklist (simulador e impressora real) e a seção "Documento de várias páginas" do README.

Escreve os passos manuais que os testes não alcançam: o arrastar e soltar real no navegador, o foco e o leitor de tela (Espaço depois de clicar em "Descartar última" adiciona uma página), Enter segurado não confirma a finalização, a queda de verdade (`kill -9` no processo durante "Digitalizando a página" e depois de duas páginas) com a retomada, uma segunda cópia do app recusada, o disco externo desconectado ao finalizar e ao reabrir com a marca M6, páginas em presets misturados abertas no Preview (mesmo tamanho físico), nomes com `/`, `:` e acentos, e três páginas reais na HP. Inclui onde fica o rascunho (`~/Library/Application Support/Digitalizadora/drafts/current`, e `~/Digitalizadora-simulador/...` no simulador), que não se deve mexer nos arquivos de `current/`, e o que fazer com uma pasta `set-aside-…`.

## 8. Testes

Mesmas metas do spec principal: cada teste abaixo de 100 ms (imagens de 64 × 48 de `build_sample_jpeg`, pastas em `tmp_path`, rascunhos semeados sem `fsync`, `sleep` e relógio falsos, nenhuma rede real), um conceito por teste e casos de fronteira.

| Tarefa | Arquivo de teste | O que cobre |
|---|---|---|
| T15 | `test_document_draft.py` | `start` usa a hora da primeira página e nome vazio; acrescentar mantém a ordem; excluir a do meio, a primeira e a última; identificador desconhecido → `PageNotFoundError`; descartar a última; descartar sem páginas → `EmptyDocumentError`; reordenar: permutação aceita, mesma ordem aceita, lista vazia, um a mais, um a menos, repetida, identificador desconhecido → `InvalidPageOrderError`; tamanho estimado = soma; `position_of`; intenção e finalizado colocados; cada mudança de conteúdo retira as duas marcas; `without_finalization_marker` mantém a de finalizado; imutabilidade; `is_page_identifier` com 16 hex, 15, 17, maiúsculas, `last`, `../x`; `generate_draft_session` com 16 hex |
| T15 | `test_document_draft_reconciliation.py` | tudo presente → nada muda; página sem arquivo → descartada com a posição certa; tamanho diferente → descartada e o arquivo em `files_to_set_aside` (não em `files_to_delete`); página e miniatura fora do manifesto → a apagar; temporário → a apagar; miniatura de página descartada → a apagar; miniatura faltando não descarta; desconhecido fica fora das duas listas; ordem do manifesto mantida; nome e marcas passam iguais; `known_file_names` em ordem alfabética |
| T15 | `test_document_name_policy.py` | cada linha da tabela de 6.6.5; exatamente 120 caracteres aceito e 121 recusado; exatamente 200 bytes aceito e 201 recusado; NFD vira NFC; `build_document_file_name` com 1, 2 e 1000 |
| T15 | `test_errors.py`, `test_ports.py`, `test_error_message_catalog.py` | códigos novos; `DamagedDocumentPageError` guarda identificador e posição; `as_draft_storage_error` com cada um dos três casos e sem mexer num erro já do rascunho; portas novas; mensagens exatas; toda classe de erro tem mensagem |
| T16 | testes de ajustes | padrão `single`; arquivo sem a chave lido como `single`; arquivo com `capture_mode` desconhecido lido como `single` mantendo a pasta de saída; aviso no log só para o valor desconhecido e uma vez por valor (a chave ausente não avisa); quarta chave gravada; `PUT` de três chaves mantém o modo; `PUT` com `document` grava; valor desconhecido no `PUT` → `422 invalid_settings` sem gravar; `/api/state` e `/api/settings` com a chave |
| T17 | `test_document_manifest_codec.py` | ida e volta (com e sem cada marca); formato exato (chaves e ordem); acentos sem escape; cada regra de leitura estrita de 6.3 (versão 2, versão ausente, `true` como versão, data sem fuso, identificador inválido, repetido, `dots_per_inch` 0 e 65536, `size_in_bytes` 0, caminho relativo na marca, `finished_document` sem `finalized_at`, JSON quebrado, não objeto) → `UnreadableDraftError`; chave desconhecida ignorada; manifesto sem as chaves de marca lido com `null` |
| T17 | `test_file_system_document_draft_repository.py` | `claim_exclusive_access` cria `drafts/` e o lock; segunda instância na mesma pasta → `DraftFolderInUseError`; segunda chamada na mesma instância não falha; página antes da miniatura; miniatura falhando apaga a página; ENOSPC → `InsufficientDraftStorageError`; outro erro → `DraftStorageUnavailableError`; inventário de `current/` classifica cada tipo de nome; pasta ausente → inventário vazio; página que some durante a listagem fica ausente do inventário sem esvaziá-lo; `delete_draft` apaga o manifesto antes do resto, falha ao apagar o manifesto preserva tudo, falha no `fsync` depois de apagá-lo só avisa e o rascunho é apagado, e arquivo desconhecido sobrevive; `set_aside_draft_folder` e `set_aside_files` com o nome do relógio; `page_file_size` ausente → `None`; `delete_files` recusa `../x`; `read_thumbnail` com identificador inválido → `None` sem tocar no disco |
| T17 | gravação, saída, guarda e PDF | `write_new_file_from` grava o que o callback escreve e devolve o tamanho; callback que levanta não deixa temporário nem destino; `save_document`: nome livre, `(2)`, `(3)`, colisão só de maiúsculas, nome vazio segue a sequência do dia, ENOSPC, tentativas esgotadas, `ScanResult` com o tamanho; `ensure_space_for_file` no limite exato e 1 byte abaixo; PDF em fluxo com páginas de 300 e 600 dpi tem o mesmo tamanho em pontos; ordem das páginas preservada (larguras diferentes); título e data; lista vazia → `ScanFailedError`; `build_pdf` continua com o dpi fixo; título do `ScanEncoder` igual ao de antes |
| T18a | `test_scan_service_document_page.py` | devolve o `DocumentPage` do destino; `mark_page_added` não muda `last_result` nem a miniatura; `scans_completed` sobe 1; segunda chamada durante um scan → 409 sem mexer no estado; uma falha do destino grava um código; modo rápido bloqueado durante uma página e vice-versa |
| T18b | `test_document_draft_store.py` | primeira página cria rascunho e pasta; páginas seguintes acrescentam; falha do manifesto apaga página e miniatura e não muda o snapshot; `revision` sobe uma vez por mudança e não sobe em mudança sem efeito; a sessão vem do `DraftIdentitySource`; mudança aceita limpa `recovery_report` e `last_finished_document`; excluir grava o manifesto antes de apagar os arquivos; excluir a única página apaga o rascunho; cancelar; falha ao apagar o manifesto no cancelamento preserva o rascunho; espaço do rascunho insuficiente → `InsufficientDraftStorageError` antes de qualquer gravação; `verify_page_files` com página sumida e com tamanho diferente → `DamagedDocumentPageError` com a posição; `mark_finalization_started` grava no disco sem mudar o snapshot; `close_finished_draft` com sucesso deixa `last_finished_document`; `close_finished_draft` com marca e limpeza falhando mantém o rascunho marcado em memória; `describe_storage` com pasta ausente → indisponível |
| T18b | `test_document_draft_leftovers.py` | primeira página com sobra sem manifesto → arquivos conhecidos apagados e desconhecido mantido; sobra com marca M6 e PDF existente → apagada; sobra com manifesto válido sem marca → posta de lado; sobra com manifesto ilegível → posta de lado |
| T18b | `test_document_page_capture.py` | capacidade delega ao store; store codifica e acrescenta com a hora e os ajustes do job |
| T18c | `test_document_draft_recovery.py` | os casos de queda abaixo |
| T19 | `test_document_finalizer.py` | pasta indisponível e espaço insuficiente antes de montar; título com nome e sem nome; `ScanFailedError` → `DocumentAssemblyFailedError`; `MemoryError` → `DocumentTooLargeError`; resultado com caminho e tamanho |
| T19 | `test_document_draft_service.py` | finalizar grava o PDF com as páginas na ordem, apaga o rascunho e devolve a contagem; nome escolhido e `(2)`; sem rascunho → 404; falha de pasta deixa o rascunho intacto e sem marca de intenção; página danificada → `DamagedDocumentPageError` e rascunho intacto; marca de intenção gravada antes do PDF; falha da marca de finalizado depois do PDF ainda apaga o rascunho e responde sucesso; falha da marca e da limpeza mantém o rascunho marcado e responde sucesso; finalizar de novo com a marca e o PDF existente fecha sem gravar outro PDF; marca com PDF ausente grava um PDF novo; `last_finished_document` no snapshot; página com preset novo usa a densidade nova |
| T19 | `test_document_draft_concurrency.py` | com a página segura aberta (`ObservingScriptedScannerGateway`): cada edição e finalizar → 409; segundo `add_page` → `ScanAlreadyRunningError` e a impressora chamada uma vez; digitalização rápida → 409; dois `add_page` criados antes de qualquer um rodar → o segundo levanta e a impressora é chamada uma vez; com finalizar seguro (`BlockingFreeSpaceReader`): `add_page` → `DocumentBusyError` sem esperar; `ensure_can_add_page` → `DocumentBusyError`; logo depois de o lock ser liberado, com uma edição ainda esperando, `ensure_can_add_page` → `DocumentBusyError`; renomear e reordenar enfileirados executam em ordem depois de `release()`; edição que esperou o lock e encontrou um scan rápido começado → 409 |
| T20 | `test_document_controller.py`, `test_document_body.py` | cada rota com cada status de 6.5; `409 document_busy` e `409 scan_already_running` no `POST /pages`; `damaged_document_page` com `page_identifier` no corpo; corpo malformado → código da rota; `/pages/last` não cai em `/pages/{page_identifier}`; cabeçalho obrigatório nos `DELETE`; miniatura com cache imutável e 404 sem corpo; chaves exatas do corpo do documento (com e sem rascunho, `recovery`, `last_finished_document`) e do resumo (com `draft_storage`) |
| T20 | `test_document_flow.py`, `test_composition_root.py`, `test_main.py` | uma página pela impressora falsa aparece no documento; rascunho semeado de três páginas finalizado gera o PDF na ordem; retomada pela raiz com órfão apagado; retomada pela raiz com marca M6 e PDF existente; dois containers na mesma pasta de dados → `DraftFolderInUseError`; containers em processos ou pastas diferentes têm sessões diferentes; `run_application` com a pasta de dados em uso explica em português e sai com 1 |
| T21 | `test_document_page_policy.py` | mover nas pontas e no meio; mover para a posição 1, M, 0 e M+1 (limitado); soltar antes, depois e sobre si mesma; metade exata da miniatura; `should_render_document_body` (outra sessão, revision menor ignorada, igual aceita); cada regra do teclado (Backspace num campo, Enter no botão ×, Enter no botão grande, repetição, confirmação aberta, modo Rápido, Esc); cada regra da confirmação (repetição, Espaço, antes de armar, Esc); cada regra do foco; cada regra de `next_document_event`; nome a enviar; nome depois de cada fim de documento; troca de modo só com `recovery` "resumed" e só uma vez por `draft_session`; aviso em 300 e 301 páginas e em 1 GiB; aviso de espaço do rascunho em 2 e 3 páginas; cada texto de status, de remoção, de retomada e de PDF talvez salvo, no singular e no plural; duração por preset |
| T21 | `test_document_panel_behaviour.py`, `test_static_assets.py` | Espaço no modo Documento manda uma página e não manda `/api/scans`; Espaço depois de clicar em "Descartar última" manda `POST /api/document/pages`, não um segundo `DELETE`; Espaço depois de clicar em ◀ manda uma página, não um `PUT`; ◀ pelo teclado mantém o foco no botão da página movida; × pelo teclado leva o foco ao × da página seguinte; Backspace descarta uma vez; Enter abre a confirmação sem mandar página; Enter segurado (repetição) abre a confirmação e não finaliza; Espaço na confirmação não finaliza; depois de finalizar, o campo de nome fica vazio e a próxima primeira página não manda `PUT /api/document/name` (e o mesmo depois de cancelar); nome recusado na finalização para, foca o campo e não manda `POST /finalize`; durante a finalização o botão grande fica desabilitado com "Finalizando…"; corpo de revision menor chegando depois de um maior é ignorado; 409 vai para o banner; 422 relê o documento; `damaged_document_page` marca a miniatura; corpo com `recovery` troca o modo e mostra o aviso; recarga sem `recovery` não troca o modo, nem a recarga de um rascunho já trocado nesta sessão; nome deixado no campo durante uma digitalização sai quando os controles voltam; Enter no campo de nome durante a digitalização não perde o foco; botão "Voltar ao modo Documento" desabilitado durante uma digitalização rápida; uma edição troca o último evento do status para `EDITED`; Espaço que abriu a confirmação não consome o primeiro Enter; a ordem do Tab nos botões da miniatura segue a ordem visual; modo Rápido com rascunho mostra a linha de documento em andamento; `last-scan-panel` escondido no modo Documento; `last_finished_document` mostrado numa aba que não finalizou; identificadores novos presentes; ordem dos cinco scripts |

**Casos de queda** (`test_document_draft_recovery.py`, cada um montado direto no disco com `write_draft_folder` e verificado com um `DocumentDraftStore` novo, como se o processo tivesse reaberto):

1. Sem pasta `drafts/` → sem rascunho, sem relatório e nada criado.
2. `current/` sem manifesto com `page-…`, `thumbnail-…` e `.part` (queda antes do primeiro manifesto) → os três apagados, sem rascunho, sem relatório.
3. Manifesto e arquivos íntegros → rascunho igual, `revision` 0, manifesto não regravado (`ScriptedFileWriter.written_file_names` vazio), relatório `resumed` sem perdas.
4. Página e miniatura gravadas fora do manifesto (queda entre os passos 8 e 10 de 6.6.1) → as duas apagadas; as páginas confirmadas ficam.
5. Página listada sem arquivo → descartada, manifesto regravado sem ela, relatório com a posição dela.
6. Página com tamanho diferente do manifesto → descartada e o arquivo movido para uma pasta `set-aside-…` (não apagado), relatório com a posição e a pasta.
7. `.part` de uma gravação interrompida → apagado.
8. Arquivo desconhecido → mantido, um aviso; também quando não há manifesto (por exemplo `.DS_Store`).
9. Miniatura faltando → página mantida; `read_thumbnail` → `None`.
10. Nenhuma página com arquivo → rascunho apagado, relatório `pages_lost` com todas as posições.
11. Manifesto ilegível (JSON cortado, arquivo vazio, versão 2, identificador repetido) → pasta posta de lado com todos os arquivos dentro, sem rascunho, nada apagado, relatório `set_aside` com a pasta.
12. Marca M6 com o PDF existente → rascunho apagado, sem duplicar, sem relatório.
13. Marca M6 com o PDF não confirmado (arquivo ausente; pasta sem permissão) → rascunho mantido com a marca, manifesto não regravado, relatório `resumed`.
14. Queda depois do `delete_draft` apagar o manifesto e antes de apagar os arquivos → tratado como o caso 2.
15. `OSError` inesperado no inventário ou na leitura do manifesto → `recover` não levanta, `current/` intacta, relatório `failed`, e `ensure_capacity_for_page` levanta `DraftStorageUnavailableError`.
16. ENOSPC ao regravar o manifesto no passo 8 → rascunho mantido em memória sem a página descartada, manifesto no disco igual ao de antes, relatório `resumed`.
17. Marca de intenção sem marca de finalizado (queda durante a finalização) → rascunho mantido com `finalization_started_at`, relatório `resumed`.
18. Falha ao pôr de lado o arquivo de tamanho errado → relatório `failed`, nada apagado.

**Os seis modos de falha com mais chance de acontecer** (viram o "Review Focus" das Tarefas 15 a 22, cada um com teste):

1. **Queda no meio de "Adicionar página" ou de uma edição** (app fechado, Mac sem bateria): o que foi confirmado nunca se perde, nada órfão fica, o manifesto sempre lê, e o que se perdeu aparece na interface. Testes: casos de queda 2 a 8, 14 a 16 e 18; falha do manifesto apaga a página (T18b); textos de retomada (T21).
2. **Queda entre gravar o PDF e apagar o rascunho, ou abertura com o disco externo ausente**: nunca páginas perdidas e nunca PDF duplicado sem aviso. Testes: casos 12, 13 e 17; marca de intenção, atalho de PDF já gravado e falhas da marca e da limpeza depois do PDF (T19); retomada pela raiz (T20).
3. **Pedidos concorrentes**: Espaço segurado ou clique duplo em "Adicionar página", duas abas, duas cópias do app, excluir, reordenar, finalizar ou cancelar durante a digitalização, lista de ordem velha, resposta atrasada. Testes: `test_document_draft_concurrency.py`, lock de processo (T17, T20), 409 e 422 do controller, regras de teclado, foco e confirmação, `should_render_document_body` e cenários do painel.
4. **Nome de arquivo hostil ou repetido** (`/`, `:`, ponto inicial, controle e bidi, NFD, maiúsculas, nome comprido, disco exFAT): nunca sobrescreve e nunca falha por causa do nome. Testes: tabela de 6.6.5, `save_document` com `(2)`/`(3)` e colisão de maiúsculas.
5. **Falta de espaço ou pasta ausente**: disco interno cheio ao acrescentar (mensagem própria, antes de gastar 15 a 75 s da impressora, e aviso antes disso na linha de espaço do rascunho) e pasta de saída cheia ou desconectada ao finalizar (rascunho intacto). Testes: `ensure_capacity_for_page`, `DocumentFinalizer.ensure_capacity`, 503/507 do controller, `should_warn_about_draft_storage`.
6. **Páginas em presets diferentes e documento grande**: tamanho físico certo em cada página, montagem em fluxo fora do laço de eventos (o `/api/state` continua respondendo durante a finalização) e página danificada apontada pelo número. Testes: PDF de 300 e 600 dpi em fluxo (T17); finalização em thread, `DamagedDocumentPageError` e `DocumentTooLargeError` (T19).

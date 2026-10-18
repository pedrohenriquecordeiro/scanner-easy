# Arquitetura

Como o Digitalizadora é construído hoje. Para mudar algo, veja as receitas em [desenvolvimento.md](desenvolvimento.md). O que foi planejado e descartado está em [historico/](historico/README.md).

## Camadas e regra de dependência

```
            web/static (HTML + JS, sem build)
                       |  HTTP /api/...
                       v
 controllers  ---->  services  ---->  domain  <----  repositories
   (FastAPI)       (regras, casos      (modelos,      (disco: JSON,
                    de uso)             erros,         arquivos)
                                        portas)  <---- infrastructure
                                                       (eSCL, Bonjour, relógio)

 composition_root: o único lugar que instancia classes concretas e liga tudo
```

- `domain` não importa nada de fora do `domain`. As **portas** (Protocols) ficam em `domain/ports.py`: `ScannerGateway`, `ScannerGatewayProvider`, `ScannerDiscovery`, `ScannerEndpointRepository`, `ApplicationSettingsRepository`, `ScanOutputRepository`, `QuickScanSlotRepository`, `DocumentDraftRepository` e `Clock`.
- `services` importam `domain` e outros `services`. `repositories` importam `domain` e `repositories`. `infrastructure` importa `domain` e `infrastructure`. `controllers` importam `domain`, `services` e `controllers`.
- Services dependem das portas, nunca de repositories ou da infraestrutura. Dependências entram pelo construtor.
- Só `composition_root.py` (e `__main__.py`) instancia as classes concretas. `application_factory.py` monta o FastAPI com os controllers; `configuration.py` lê o ambiente e não importa nada do projeto.
- `tests/architecture/` impõe isso a cada `make test` (veja [desenvolvimento.md](desenvolvimento.md)).

## Mapa dos pacotes

Tudo em `src/digitalizadora/`. Cada camada tem subpacotes por funcionalidade com o mesmo nome.

| Pacote | Função |
|---|---|
| `__main__.py` | Ponto de entrada: log, checagem da porta, uvicorn, mensagens de partida. |
| `configuration.py` | `ApplicationConfiguration`: porta, pastas de dados e de log, pasta de saída inicial, endereço manual da impressora. |
| `composition_root.py` | `build_container`: cria repositórios, services e controllers e os liga. |
| `application_factory.py` | `create_application`: FastAPI, roteadores, tratamento de erros, `LocalRequestGuard`, arquivos estáticos. |
| `domain/scanning` | `ScanRequest`, `ScanSettings`, `ScanJob`, `ScannedImage`, `ColorMode`. |
| `domain/settings` | `ApplicationSettings`, `CaptureMode`, `ScanPreset`, resoluções suportadas (`scan_quality.py`). |
| `domain/scanner` | `ScannerEndpoint`, `ScannerRoute` (USB ou rede), `ScannerCapabilities`, `ScannerStatus`. |
| `domain/imaging` | `PageCrop` (quadrilátero em frações), `PageFraming` (giro + molduras), `PageRotation`, `ImageAdjustment`, `PixelRegion`. |
| `domain/output` | `OutputFormat`, `EncodedScan`, `ScanFileNamingPolicy` (nomes de arquivo). |
| `domain/quick_scan` | `LastScan`, `QuickScanSlot`, `StoredScan`, `ScanProgressSnapshot`. |
| `domain/documents` | `DocumentDraft`, `DocumentPage`, política de nome do documento, reconciliação do rascunho com o disco. |
| `domain/errors.py` | Hierarquia de `DigitalizadoraError`; cada erro tem um `code` estável. |
| `services/scanner` | `ScanService` (a sequência única de digitalização), `PrinterConnectionService` (acha a impressora, USB primeiro), `ScanDestination`. |
| `services/quick_scan` | `ScanOutputService`, `LastScanEditService`, `LastScanViewService`, `ScanProgressTracker`, `QuickScanOutputRenderer`. |
| `services/documents` | `DocumentDraftService` (casos de uso), `DocumentDraftStore` (estado e recuperação), `DocumentPageCapture`, `DocumentFinalizer`, `DocumentPdfAssembler`, `DocumentPageCropDetector`, `DocumentPageViewService`, `RenderedPageSource`. |
| `services/imaging` | `PageCropDetectionService` (usa `paper_edge_detection`, `photo_region_detection`, `edge_refinement`), `PageFramingRenderer`, `PageImageViewService`, `ThumbnailService`, `jpeg_reencoding`, `image_pixel_limit`. |
| `services/output` | `ScanEncoder`, `PdfAssemblyService`, `JpegResolutionService`. |
| `services/application` | `ApplicationSettingsService`, `ApplicationStateService`, `StorageGuardService` (espaço livre). |
| `repositories/settings` | `JsonApplicationSettingsRepository`, `JsonScannerEndpointRepository`. |
| `repositories/storage` | `AtomicFileWriter`, `FileSystemScanOutputRepository`, `output_folder_preparer`, `crop_codec`. |
| `repositories/quick_scan` | `FileSystemQuickScanSlotRepository` e o codec do manifesto. |
| `repositories/documents` | `FileSystemDocumentDraftRepository` e o codec do manifesto. |
| `infrastructure` | `escl/EsclScannerGateway` (httpx), `BonjourScannerDiscovery` e `DnsServiceDiscoveryRecordSource` (DNS-SD do macOS via ctypes), `SystemClock`. |
| `controllers/<grupo>` | Um roteador por controller: `application` (estado, ajustes, impressora), `quick_scan` (digitalizar, última digitalização, prévias), `documents`, `shared` (catálogo de mensagens de erro em português, `LocalRequestGuard`, estáticos). |
| `simulator` | Impressora eSCL de mentira (`python -m digitalizadora.simulator`). Só desenvolvimento. |
| `web/static` | Página única: `index.html`, `application.css` e scripts sem build. Regras puras (`*-policy.js`, `page-frame-geometry.js`) separadas dos que mexem no DOM (`*-panel.js`, `page-frame-editor.js`, `application.js`). A ordem dos `<script>` em `index.html` importa. |

## Fluxos principais

**Digitalização no modo Rápido**
1. `POST /api/scans` chega em `ScanController.start_scan`, que confere `ScanService.ensure_scan_can_start` (409 se já há digitalização ou ajuste em curso) e agenda a digitalização com os ajustes salvos.
2. `ScanService.scan_one_file` chama `ScanProgressTracker.begin_scan` (fase "preparando") e, numa thread, `ScanOutputService.ensure_capacity` (pasta de saída pronta e espaço livre).
3. `PrinterConnectionService.acquire_gateway` entrega o `EsclScannerGateway`; `scan_page` devolve o JPEG do scanner (`ScannedImage`).
4. `ScanOutputService.store`: `ScanEncoder.encode_master`, detecção de molduras se o corte automático está ligado, gravação do original no slot, `QuickScanOutputRenderer.render_outputs`, `FileSystemScanOutputRepository.save_scans` e, por fim, o commit do slot (`FileSystemQuickScanSlotRepository`).
5. `ScanProgressTracker.mark_completed`; a página, que consulta `GET /api/state`, vê `last_result_revision` mudar e busca a miniatura.

**Página do modo Documento**
1. `POST /api/document/pages` chega em `DocumentController.add_page` e `DocumentDraftService.add_page`, que passa por `ScanService.scan_document_page` (o mesmo `ScanProgressTracker`: uma digitalização por vez).
2. `DocumentPageCapture.store` guarda o JPEG do scanner sem alterá-lo e sugere molduras (corte automático) como `PageFraming`.
3. `DocumentDraftStore.append_page` grava página e miniatura e, por último, o manifesto (`FileSystemDocumentDraftRepository`).

**Finalizar o documento**
1. `POST /api/document/finalize` roda `DocumentDraftService.finalize` sob a trava de edição, numa thread.
2. Confere capacidade (`DocumentFinalizer.ensure_capacity`) e o tamanho de cada página guardada (`verify_page_files`).
3. `mark_finalization_started` (só no disco) e `DocumentFinalizer.write_document`: `DocumentPdfAssembler.write_pdf` renderiza cada página no momento de gravar (`RenderedPageSource`, `PageFramingRenderer`) e `PdfAssemblyService` escreve o PDF em fluxo; `FileSystemScanOutputRepository.save_document` publica sob o primeiro nome livre.
4. `close_finished_draft` marca o manifesto como finalizado e apaga o rascunho.

**Detecção de molduras e renderização**
1. A detecção (`PageCropDetectionService.detect_crops`) recebe o JPEG do scanner, acha até 2 fotos ou a folha em uma prévia reduzida e refina as bordas no tamanho maior. Devolve `PageCrop`s em frações, em ordem de leitura.
2. As molduras viram parte do `PageFraming`, guardado no manifesto (documento) ou no slot (rápido). O JPEG do scanner nunca muda.
3. `PageFramingRenderer.render_jpeg` aplica giro e uma moldura ao JPEG do scanner e escreve um JPEG novo (qualidade 100). Rápido: `QuickScanOutputRenderer` + `ScanEncoder.wrap_output` fazem o arquivo final. Documento: o `DocumentPdfAssembler` faz isso a cada página, só ao finalizar.

**Ajuste da última digitalização (girar, aplicar molduras, detectar)**
1. `POST /api/scans/last/rotation`, `PUT /api/scans/last/crops` ou `POST /api/scans/last/crops/detect` chegam em `LastScanController` e `LastScanEditService`.
2. Sob a trava de edição, `_apply_edit` carrega o slot, planeja o novo `PageFraming`, grava o manifesto com `render_pending`, renderiza arquivos novos a partir do original com nomes novos (`save_scans_in_folder`) e confirma o manifesto. Se falhar, o manifesto volta ao enquadramento anterior.
3. `ScanProgressTracker.replace_last_scan` troca a última digitalização; os arquivos antigos ficam na pasta.

## Dados em disco

| O quê | Onde |
|---|---|
| Ajustes | `~/Library/Application Support/Digitalizadora/settings.json` |
| Última impressora achada | `.../Digitalizadora/scanner-endpoint.json` |
| Última digitalização do modo Rápido (slot) | `.../Digitalizadora/quick-scan/`: `manifest.json`, `master-<id>.jpg`, `thumbnail-<id>.jpg` |
| Documento em andamento | `.../Digitalizadora/drafts/current/`: `manifest.json`, `page-<id>.jpg`, `thumbnail-<id>.jpg`; `drafts/.owner-lock` (uma cópia do app por vez) |
| Arquivos que o app não conseguiu usar | `set-aside-<data>-<sufixo>/` ao lado do slot ou de `current/`; nunca são apagados |
| Arquivos digitalizados | Pasta de saída dos ajustes (padrão `~/Pictures/Digitalizadora`) |
| Registro | `~/Library/Logs/Digitalizadora/digitalizadora.log` (rotativo) |

Com `make run-simulated`, o `HOME` do app é `~/Digitalizadora-simulador`, e todos esses caminhos ficam dentro dele.

## API HTTP

Todas as respostas de erro têm o formato `{"code", "message"}`; os códigos vêm de `domain/errors.py` e as mensagens de `controllers/shared/error_message_catalog.py`.

| Método | Caminho | Para quê |
|---|---|---|
| GET | `/` , `/static/*` | Página e scripts (sempre revalidados). |
| GET | `/api/health` | Saúde (usada pelo launcher). |
| GET | `/api/state` | Fase da digitalização, última digitalização, ajustes, espaço, documento. A página consulta periodicamente. |
| GET, PUT | `/api/settings` | Lê e grava os ajustes. |
| GET | `/api/printer` | Estado da conexão com a impressora. |
| POST | `/api/printer/refresh` | Procura a impressora de novo. |
| PUT | `/api/printer/address` | Define um endereço manual. |
| POST | `/api/scans` | Digitaliza no modo Rápido (202; 409 se ocupado). |
| GET | `/api/scans/last/thumbnail`, `/api/scans/last/preview` | Miniatura e visão ampliada da última digitalização. |
| POST | `/api/scans/last/rotation` | Gira a última digitalização. |
| PUT | `/api/scans/last/crops` | Grava as molduras da última digitalização. |
| POST | `/api/scans/last/crops/detect` | Detecta as molduras da última digitalização. |
| GET | `/api/document` | Documento em andamento. |
| POST | `/api/document/pages` | Digitaliza e acrescenta uma página. |
| DELETE | `/api/document/pages/last`, `/api/document/pages/{page_identifier}` | Descarta a última página / exclui uma página. |
| GET | `/api/document/pages/{page_identifier}/thumbnail`, `.../preview` | Miniatura e visão ampliada. |
| POST | `/api/document/pages/{page_identifier}/rotation` | Gira a página. |
| PUT | `/api/document/pages/{page_identifier}/crops` | Grava as molduras da página. |
| POST | `/api/document/pages/{page_identifier}/crops/detect` | Detecta as molduras da página. |
| PUT | `/api/document/page-order` | Reordena as páginas. |
| PUT | `/api/document/name` | Define o nome do documento. |
| POST | `/api/document/finalize` | Grava o PDF e encerra o documento. |
| DELETE | `/api/document` | Cancela o documento. |

## Invariantes (não quebre)

- **Originais intactos.** O JPEG do scanner (`master-<id>.jpg` no slot, `page-<id>.jpg` no rascunho) nunca é alterado. Giro e molduras ficam no manifesto como `PageFraming` e os arquivos finais são sempre renderizados a partir do original. Sem corte e sem giro, a saída mantém os bytes do scanner.
- **Nunca sobrescrever nem apagar a saída.** Arquivos novos entram por `AtomicFileWriter.write_new_file_from` (arquivo temporário oculto, publicado sem sobrescrever; um nome ocupado vira o próximo). Ajustar a última digitalização grava arquivos novos e mantém os antigos.
- **Uma digitalização por vez.** `ScanProgressTracker.begin_scan` recusa uma segunda (`scan_already_running`, 409) e também uma durante o ajuste da última digitalização (`last_scan_busy`). A impressora só atende um job, e `EsclScannerGateway` apaga o job ao terminar. Edições do documento rodam sob um `asyncio.Lock` no `DocumentDraftService` e do slot no `LastScanEditService`; acrescentar uma página enquanto outra edição está em curso devolve `document_busy` (409), e editar durante uma digitalização devolve `scan_already_running`.
- **Ordem de gravação à prova de queda.** Primeiro os arquivos, o manifesto por último (ele é o ponto de confirmação), e só então se apaga o que ficou obsoleto. Página: `page-<id>.jpg` e miniatura, depois `manifest.json`. Ajuste da última digitalização: manifesto com `render_pending`, arquivos novos, manifesto final; na partida `LastScanEditService.restore_after_start` termina um ajuste interrompido. Finalização: marca de intenção só no disco, PDF, marca de finalizado, e só então apaga o rascunho. Na recuperação, o que não bate com o manifesto vai para `set-aside-*`, nunca é apagado.
- **Memória a 1200 dpi.** Uma página inteira tem cerca de 143 milhões de pixels. `image_pixel_limit.raise_decompression_limit_to_scanner_size` sobe o limite do Pillow só até esse tamanho. Prévias são decodificadas reduzidas, `jpeg_reencoding.replace_with` mantém no máximo duas imagens inteiras na memória, o PDF é escrito em fluxo e `MemoryError` vira `ImageAdjustmentFailedError` ou `DocumentTooLargeError`. Não carregue páginas inteiras de uma vez.
- **Só local.** O servidor escuta em `127.0.0.1`. `LocalRequestGuard` recusa um `Host` que não seja `127.0.0.1:<porta>` ou `localhost:<porta>` (403 `forbidden_host`) e exige `X-Requested-With: digitalizadora` em POST, PUT, PATCH e DELETE (403 `missing_request_header`). O app não configura CORS.
- **Uma cópia do app por vez.** `FileSystemDocumentDraftRepository.claim_exclusive_access` toma o `.owner-lock`; uma segunda cópia (mesmo em outra porta) recusa partir.
- **Disco e imagem fora do laço de eventos.** Trabalho de disco e de imagem roda em `asyncio.to_thread`; o `ScanProgressTracker` troca o estado por um instantâneo imutável, sem travas.

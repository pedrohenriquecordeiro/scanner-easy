# Desenvolvimento

Guia para quem vai mudar o código. Antes de tudo, leia [arquitetura.md](arquitetura.md).

## Ambiente e comandos

Python 3.12 ou mais novo. `make setup` cria o `.venv` do zero e instala o projeto em modo editável com as dependências de desenvolvimento (pytest, pytest-asyncio, ruff). Os testes da interface precisam do Node.js (`node`); sem ele, esses testes são pulados.

| Comando | O que faz |
|---|---|
| `make setup` | Recria o `.venv` e instala tudo (`PYTHON=python3.12` escolhe o Python). |
| `make run` | Roda o app em `http://127.0.0.1:8765`. |
| `make test` | `pytest` (sem rede e sem impressora). |
| `make lint` | `ruff check src tests`. |
| `make check` | `lint` e depois `test`. Rode antes de commitar. |
| `make simulator` | Impressora eSCL falsa em `http://127.0.0.1:8080/eSCL`. |
| `make run-simulated` | App apontando para o simulador, com `HOME` em `~/Digitalizadora-simulador`. |
| `make test-hardware` | Testes com a impressora real (`DIGITALIZADORA_HARDWARE_TESTS=1`). |

Teste um arquivo ou um nome: `.venv/bin/python -m pytest tests/services/imaging -q` ou `-k nome`.

Variáveis do simulador: `DIGITALIZADORA_SIMULATOR_PORT` (padrão 8080), `DIGITALIZADORA_SIMULATOR_SCENE` (`sheet`, `photos_one` ou `photos_two`) e `DIGITALIZADORA_SIMULATOR_LID_BACKGROUND`. As cenas desenham só formas sintéticas, nunca pessoas.

## Convenções

- **Nomes**: pastas e arquivos em kebab-case (`iniciar-digitalizadora.command`, `scan-trigger-policy.js`); **módulos Python importáveis em snake_case** (`scan_service.py`), porque `import scan-service` não existe; classes em PascalCase; funções e variáveis em snake_case; constantes em UPPER_SNAKE_CASE; tabelas em snake_case.
- Sem abreviações (`identifier`, não `id`; `base_address`, não `url`; `dots_per_inch`, não `dpi`). Siglas de formato ou protocolo (PDF, JPEG, HTTP, eSCL) são permitidas. Nomes descritivos.
- Código em inglês; interface, mensagens e documentação em português.
- No máximo 3 parâmetros por função (agrupe em um `dataclass`, como `ScanOutputParts`), sem parâmetros booleanos de modo, sem números mágicos (constantes nomeadas), `Enum` no lugar de textos soltos, type hints, comentários só para explicar o porquê.
- Camadas: controllers -> services -> domain <- repositories/infrastructure. Injeção por construtor; só `composition_root.py` instancia concretos. Detalhes em [arquitetura.md](arquitetura.md).

## Testes

- `tests/` espelha `src/`: `tests/<camada>/<grupo>/test_<módulo>.py`.
- TDD: escreva o teste que falha, depois o código. Cada teste leva menos de 100 ms e verifica **um conceito**. Relógio, espera (`sleep`) e leitura de espaço livre são injetados; nenhum teste usa rede real nem a impressora.
- **Fakes** ficam em `tests/fakes/` (`ScriptedScannerGateway`, `FixedClock`, `InMemoryApplicationSettingsRepository`, geradores de imagens sintéticas, entre outros). Prefira um fake a um mock.
- **Integração** (`tests/integration/`): a aplicação inteira sobre o scanner falso, a 75 dpi (`flow_support.py`).
- **Simulador**: `tests/simulator/` cobre o servidor eSCL falso. Uma cena nova do simulador é testada ali.
- **Interface**: os scripts de `web/static/` rodam no Node com um navegador falso (`tests/web/fake-browser.js` e os `*-harness.js`). Cada `test_*.py` chama o harness e confere o JSON que ele imprime. `test_static_assets.py` confere a ordem dos `<script>` do `index.html` e se todo `id` usado pelos scripts existe na página.
- **Impressora real**: `tests/hardware/` está marcado com `hardware` e só roda com `DIGITALIZADORA_HARDWARE_TESTS=1` (`make test-hardware`, impressora no USB, folha no vidro). Alguns testes de detecção de molduras só rodam se você apontar para arquivos seus: `DIGITALIZADORA_REAL_SCANS_FOLDER`, `DIGITALIZADORA_USER_MASTER_SCAN` e `DIGITALIZADORA_CARD_IMAGE`. Nunca ponha essas imagens no repositório.
- Fixtures de teste ficam em `tests/fixtures/` (respostas eSCL em `escl/`). Não commite imagens de pessoas nem identificadores da sua impressora (MAC, número de série, nome Bonjour).

### Teste de arquitetura

`tests/architecture/` roda junto com os demais:

- `test_layer_dependencies.py` lê os `import` de cada módulo com `ast` (inclusive os dentro de funções e de `TYPE_CHECKING`) e recusa imports que violem a regra de dependência, imports relativos e qualquer import de `composition_root` fora do ponto de entrada.
- `test_module_naming.py` exige snake_case nos módulos e nas pastas de pacotes.

Se um teste falhar com "must not import ...", não adapte o teste: mova a regra para a camada certa. Costuma ser uma destas saídas: declarar uma porta (Protocol) em `domain/ports.py` e injetar a implementação pelo construtor; mover o tipo compartilhado para `domain`; ou montar o objeto no `composition_root.py`. Um pacote ou módulo novo na raiz de `src/digitalizadora/` precisa de uma linha em `ALLOWED_LAYERS`.

## Receitas

Sempre rode `make check` no fim. Os caminhos abaixo são relativos a `src/digitalizadora/` e `tests/`.

### Adicionar um ajuste (do modelo à tela)

Exemplo guia: `crop_margin`, o último ajuste que entrou.

1. **Domínio**: o campo no modelo, com valor padrão (`domain/imaging/image_adjustment.py` para ajustes de imagem; `domain/settings/application_settings.py` para os demais).
2. **Repositório**: `repositories/settings/json_application_settings_repository.py`: constante da chave, leitura tolerante (arquivo antigo sem a chave volta ao padrão, valor inválido é registrado no log e também volta ao padrão) e gravação em `save`.
3. **Service**: `services/application/application_settings_service.py`: campo em `SettingsUpdate` e a regra em `update` (`None` mantém o valor salvo).
4. **Controller**: `controllers/application/settings_controller.py` (`SettingsRequestBody` e o `SettingsUpdate`) e `controllers/application/settings_body.py` (o que `GET /api/settings` e `GET /api/state` devolvem).
5. **Composition root**: só se outro objeto precisa ler o valor. `crop_margin` chega ao `PageCropDetectionService` por uma função que lê o repositório (`composition_root.py`, `_build_shared_services`).
6. **Interface**: o controle em `web/static/index.html`, o `id` registrado e os eventos em `web/static/application.js` (coleta dos elementos, envio por `change_adjustment`, preenchimento a partir de `/api/settings`).
7. **Testes que fixam o formato dos ajustes** (atualize todos): `tests/repositories/settings/test_json_application_settings_repository.py`, `tests/services/application/test_application_settings_service.py`, `tests/controllers/application/test_settings_controller.py`, `tests/controllers/application/test_state_controller.py`, `tests/controllers/test_application_factory.py`, `tests/test_composition_root.py`, `tests/domain/settings/test_application_settings.py` e, na interface, `tests/web/scan-page-harness.js` com `tests/web/test_scan_page_behaviour.py` e `tests/web/test_static_assets.py`.
8. Documente o ajuste na tabela do [README](../README.md).

### Adicionar um endpoint HTTP

1. Se há um erro novo: uma classe com `code` em `domain/errors.py` e a mensagem em português em `controllers/shared/error_message_catalog.py` (`tests/controllers/shared/test_error_message_catalog.py` confere os dois). Mapeie o código ao status HTTP no controller (o padrão para "ocupado" é 409).
2. Regra de negócio num service em `services/<grupo>/`; o controller só traduz HTTP.
3. Controller em `controllers/<grupo>/` com `build_router()` e o corpo da requisição validado por Pydantic (use tipos estritos: `StrictInt`, `StrictBool`).
4. Registre o controller: campo em `ApplicationControllers` e no laço de `include_router` (`application_factory.py`) e a construção em `_build_controllers` (`composition_root.py`). Se o corpo inválido deve responder um código próprio, acrescente o caminho em `VALIDATION_ERROR_CODE_PATTERNS`.
5. POST, PUT, PATCH e DELETE já exigem `X-Requested-With: digitalizadora` pelo `LocalRequestGuard`; a interface envia esse cabeçalho.
6. Testes: `tests/controllers/<grupo>/test_<controller>.py` com `build_test_client` e os stubs de `tests/controllers/controller_test_support.py`; um fluxo completo em `tests/integration/` se atravessa vários services. Acrescente a rota à tabela de [arquitetura.md](arquitetura.md).

### Adicionar um controle ou diálogo na interface

1. Marcação em `web/static/index.html` (diálogos são `<dialog id="...">`) e estilo em `application.css`, com tema escuro e largura de celular.
2. Regras puras (quando pode, textos, cálculos) num arquivo `*-policy.js` sem DOM; o que mexe no DOM em `application.js` ou num painel (`document-panel.js`, `last-scan-panel.js`, `page-frame-editor.js`).
3. Arquivo `.js` novo: acrescente o `<script src="/static/..." defer>` em `index.html` **depois** dos arquivos de que ele depende, e o nome na lista de ordem em `tests/web/test_static_assets.py`. O `pyproject.toml` já empacota `web/static/*`.
4. Testes: um teste de política com `tests/web/policy_expression_runner.py` ou o harness do painel (`tests/web/*-harness.js`), mais `test_static_assets.py` (todo `id` usado precisa existir na página). O texto novo vai em português; confira a tela com `make run-simulated`.
5. Se o controle muda o fluxo, acrescente uma linha ao [checklist manual](acceptance-checklist.md).

### Adicionar um formato de saída

1. Membro novo em `domain/output/output_format.py` (o valor é a extensão do arquivo, via `file_extension`).
2. Como o arquivo é produzido a partir do JPEG renderizado: `ScanEncoder.wrap_output` em `services/output/scan_encoder.py` (hoje JPG segue como está e PDF envolve o JPEG em `PdfAssemblyService`). Um formato novo ganha um service em `services/output/`, injetado em `ScanEncoder` pelo `composition_root.py`.
3. Nomes: `ScanFileNamingPolicy` já usa `file_extension`. O repositório de saída não escolhe formato.
4. Ajustes: `ApplicationSettingsService` valida com `parse_enum_member`; o repositório JSON lê `OutputFormat(...)`; atualize a interface (`index.html`, `application.js`) e os testes da receita do ajuste.
5. O modo Documento sempre grava PDF (`DocumentPdfAssembler`); mexa ali só se o novo formato valer para documentos.

### Adicionar uma cena ao simulador

1. Membro novo em `PhotoScene` e a lista de `PhotoPlacement` em `PHOTO_PLACEMENTS_BY_SCENE` (`simulator/photo_scene_page.py`). `parse_photo_scene` já aceita o novo valor como texto de `DIGITALIZADORA_SIMULATOR_SCENE`.
2. Testes em `tests/simulator/` e, se a cena serve a testes de detecção, um construtor em `tests/fakes/photo_scenes.py`.
3. Use só formas sintéticas. Anote a cena no [checklist](acceptance-checklist.md) se ela entra numa verificação manual.

### Adicionar um ajuste ou passo ao pipeline de imagem

O pipeline de saída é: JPEG do scanner (original) -> `PageFramingRenderer.render_jpeg` (giro e moldura) -> `ScanEncoder.wrap_output` (JPG ou PDF).

1. Se o passo depende de dados por página (como as molduras), o dado entra em `PageFraming` ou noutro modelo de `domain/imaging/` e precisa de gravação e leitura nos codecs dos manifestos (`repositories/storage/crop_codec.py`, `repositories/documents/document_manifest_codec.py`, `repositories/quick_scan/quick_scan_manifest_codec.py`). Manifestos antigos têm que continuar legíveis.
2. O passo em si vai em `services/imaging/`, síncrono e só com Pillow, chamado por `PageFramingRenderer._render_framed`. Mantenha o original intacto, não segure mais de duas imagens inteiras na memória (`jpeg_reencoding.replace_with`) e conserve a qualidade fixa `REENCODING_JPEG_QUALITY`.
3. Quem chama o renderizador passa o pedido por `FrameRenderRequest`: `QuickScanOutputRenderer` (modo Rápido) e `DocumentPdfAssembler` (modo Documento). Atualize os dois.
4. Teste com imagens sintéticas pequenas (`tests/fakes/synthetic_scans.py`, `sample_images.py`). Um passo caro precisa de um teste de memória ou de tamanho a 1200 dpi.

### Suportar outro backend de scanner

1. Implemente a porta `ScannerGateway` (`read_capabilities`, `read_status`, `scan_page`) numa classe nova em `infrastructure/`. `scan_page` devolve um `ScannedImage` JPEG: o resto do app (`ScanEncoder.encode_master`) recusa outro tipo de mídia. Traduza as falhas do backend para os erros de `domain/errors.py`.
2. Descoberta: implemente `ScannerDiscovery` (devolve `ScannerEndpoint`s). `PrinterConnectionService` recebe a descoberta, o `ScannerEndpointRepository` e uma fábrica `ScannerEndpoint -> ScannerGateway`, e prefere a rota USB.
3. Ligue tudo em `composition_root.py` (`_build_gateway_factory`, `_build_scanner_access` e a construção de `PrinterConnectionService`). Nenhum service ou controller muda.
4. Teste o gateway novo contra um servidor falso (como `tests/infrastructure/test_escl_scanner_gateway.py` faz com o transporte do `httpx`) e acrescente testes com a marca `hardware` para o aparelho real.

## Antes de enviar (push)

1. `make check` verde (lint e testes).
2. Se mexeu em fluxo de digitalização, molduras, documento ou interface: rode o que couber do [checklist de aceitação](acceptance-checklist.md) no simulador (parte A, C.1 e D); com a impressora real, partes B e C.2.
3. Confira `git status`: nenhum arquivo pessoal (`md.md` é a lista de pedidos do dono do projeto), imagem de pessoa ou identificador da impressora.
4. Atualize [README](../README.md) e [arquitetura.md](arquitetura.md) se a mudança alterou ajustes, rotas, pastas ou invariantes.

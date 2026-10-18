# Digitalizadora

App pessoal para o MacBook: aperte um botão (ou a tecla **Espaço**) numa página local do navegador e a **HP DeskJet Ink Advantage 2874** digitaliza **uma página do vidro** e grava um **PDF** ou um **JPG** com nome automático. Não usa driver nem software da HP: fala direto com a impressora pelo protocolo **eSCL (AirScan)**, pelo **cabo USB** (preferido) ou pelo **Wi-Fi**.

## O que você precisa

- Mac com macOS 15 e **Python 3.12 ou mais novo** (`python3 --version`). Se o `python3` for mais velho, instale o Python 3.12 e prepare o ambiente com `make setup PYTHON=python3.12`.
- As ferramentas de linha de comando da Apple (Command Line Tools), que trazem o `make`.
- A impressora **ligada** e conectada ao Mac pelo **cabo USB**, o jeito recomendado (não depende de nenhuma permissão do macOS). Sem o cabo, ela precisa estar na **mesma rede Wi-Fi do Mac** (a 2874 só usa 2,4 GHz), com a luz do Wi-Fi fixa e a VPN desligada.
- Espaço livre na pasta de saída: o app recusa digitalizar com menos de 1 GiB livre. A pasta padrão, `~/Pictures/Digitalizadora`, fica no disco interno; para volumes muito grandes, um disco externo é recomendado. Na primeira gravação num disco externo, o macOS pede permissão para o programa que abriu o app (normalmente o Terminal) acessar Volumes Removíveis: clique em **Permitir**.

A impressora já foi validada (Gate 0, aprovado em 2026-10-17, pelo USB e pelo Wi-Fi): veja [docs/gate-0-resultado-2026-10-17.md](docs/gate-0-resultado-2026-10-17.md).

## Primeira execução

### Jeito fácil: duplo clique

1. No Finder, dê duplo clique em `iniciar-digitalizadora.command`. Ele abre o **Terminal.app**. Se o macOS reclamar de desenvolvedor não identificado, clique com o botão direito no arquivo, escolha **Abrir** e confirme.
2. Na primeira vez ele prepara o ambiente sozinho (`make setup`), o que leva alguns minutos e precisa de internet. Se a preparação falhar no meio, o próximo duplo clique recomeça do zero.
3. O navegador abre em `http://127.0.0.1:8765`. **Deixe a janela do Terminal aberta**; fechar a janela encerra o app. Se o app já estiver aberto em outra janela, o duplo clique só abre a página.

### Jeito manual

No Terminal, dentro da pasta do projeto:

```
make setup
make run
```

Depois abra `http://127.0.0.1:8765` no navegador.

### USB, Wi-Fi e a permissão de Rede Local do macOS

O app procura a impressora pelas duas rotas e prefere o cabo USB. O cabeçalho da página mostra "Impressora pronta (USB)" ou "Impressora pronta (Wi-Fi)".

- **Pelo cabo USB** a impressora aparece no próprio Mac (`localhost`), e a privacidade de Rede Local do macOS não se aplica: o app funciona aberto de qualquer lugar, inclusive pelo terminal do VS Code.
- **Pelo Wi-Fi**, o macOS 15 só deixa o app falar com a impressora se o programa que o abriu tiver a permissão de **Rede Local**. O jeito recomendado é o duplo clique no `iniciar-digitalizadora.command`, que abre o Terminal.app. Se a página mostrar o erro `local_network_blocked`, conecte o cabo USB ou abra o app pelo launcher e confira Ajustes do Sistema > Privacidade e Segurança > Rede Local.

## Como usar

1. Coloque a folha (ou a foto) no vidro, com a face para baixo, e feche a tampa.
2. Aperte **Espaço** (ou clique em **Digitalizar**). Espere cerca de 15 s (no modo Foto, cerca de 75 s): o status mostra Preparando, Digitalizando, Salvando e por fim "Pronto! Salvo como AAAA-MM-DD_NNNNN.pdf".
3. Levante a tampa, troque a folha e aperte Espaço de novo. Não precisa tocar no mouse.

Ajustes (salvos na hora):

- **Formato:** PDF ou JPG.
- **Modo:** Documento (300 dpi, cor), Documento econômico (200 dpi, cinza) ou Foto (600 dpi, cor).
- **Pasta de saída:** digite o caminho completo (por exemplo `/Volumes/MeuDisco/Scans`) e clique em **Salvar**. O padrão é `~/Pictures/Digitalizadora`. A página mostra o espaço livre e quantas páginas ainda cabem; se a pasta sumir (por exemplo, um disco externo desconectado), mostra "Pasta de saída indisponível" no lugar do espaço livre.

Os arquivos se chamam `AAAA-MM-DD_NNNNN.pdf` ou `.jpg`, com um contador de 5 dígitos por dia, e nunca sobrescrevem outro arquivo.

## Testar sem a impressora (simulador)

O simulador é uma impressora de mentira que fala eSCL como a impressora real. Use dois Terminais:

```
make simulator
make run-simulated
```

O primeiro liga a impressora falsa em `http://127.0.0.1:8080/eSCL`; o segundo abre o app apontando para ela. O `make run-simulated` usa uma pasta pessoal separada, `~/Digitalizadora-simulador`: os ajustes, o endereço da impressora, o registro e os arquivos de teste (em `~/Digitalizadora-simulador/Pictures/Digitalizadora`) ficam lá, e o uso real não é afetado. Para usar outra pasta: `make run-simulated SIMULATED_HOME="$HOME/outra-pasta"`. Essa pasta pode ser apagada quando você quiser.

## Variáveis de ambiente

| Variável | Para que serve | Padrão |
|---|---|---|
| `DIGITALIZADORA_PORT` | Porta da página local (1 a 65535) | `8765` |
| `DIGITALIZADORA_OUTPUT_FOLDER` | Pasta de saída inicial, usada enquanto você não salvar outra na página; caminho completo, começando por `/` ou `~/` | `~/Pictures/Digitalizadora` |
| `DIGITALIZADORA_SCANNER_ADDRESS` | Endereço da impressora tentado antes da busca automática, por exemplo `http://HP000000000001.local:8080/eSCL` (Wi-Fi). Não use para o USB: a porta da rota USB muda a cada conexão | vazio |

O servidor só escuta em `127.0.0.1`; isso não é configurável.

## Comandos

| Comando | O que faz |
|---|---|
| `make setup` | Cria (do zero) o `.venv` e instala as dependências; `make setup PYTHON=python3.12` escolhe outro Python |
| `make run` | Roda o app |
| `make simulator` | Liga a impressora falsa na porta 8080 |
| `make run-simulated` | Roda o app apontando para o simulador, com a pasta pessoal separada `~/Digitalizadora-simulador` |
| `make test` | Roda os testes (sem rede e sem impressora) |
| `make test-hardware` | Roda os testes com a impressora real (impressora ligada pelo cabo USB, folha no vidro) |
| `make lint` | Confere o estilo do código com ruff |

## Quando algo dá errado

A faixa vermelha da página mostra a mensagem. O registro fica em `~/Library/Logs/Digitalizadora/digitalizadora.log`.

| Código | Mensagem na página | O que fazer |
|---|---|---|
| `scanner_unreachable` | Não encontrei a impressora... | Ligue a impressora e confira o cabo USB. Sem o cabo, espere a luz do Wi-Fi fixar, confira a rede 2,4 GHz e desligue a VPN; depois tente de novo. Se o endereço mudou, o app procura de novo sozinho. |
| `local_network_blocked` | O macOS pode estar bloqueando o acesso à rede local... | Só acontece pelo Wi-Fi. Conecte o cabo USB, ou abra o app pelo `iniciar-digitalizadora.command` e confira Ajustes > Privacidade e Segurança > Rede Local. |
| `scanner_busy` | A impressora está ocupada... | Outro programa (Captura de Imagem, app HP) pode estar usando o scanner. Feche-o e espere alguns segundos. |
| `scan_rejected` | A impressora recusou os ajustes... | Troque o modo (por exemplo, de Foto para Documento) e tente de novo; avise se repetir. |
| `scan_failed` | A digitalização falhou... | Feche a tampa e tente de novo. Se repetir, desligue e ligue a impressora. |
| `scan_timed_out` | A impressora demorou demais... | Use um modo de resolução menor, confira o cabo ou o Wi-Fi e tente de novo. |
| `scan_already_running` | Já existe uma digitalização em andamento. | Espere o status voltar a "Pronto". |
| `insufficient_storage` | Pouco espaço livre na pasta de saída... | Libere espaço ou escolha uma pasta num disco externo; o app exige pelo menos 1 GiB livre. |
| `output_folder_unavailable` | Não consigo gravar na pasta de saída... | Se for disco externo, confira se está conectado. Se está conectado, confira Ajustes do Sistema > Privacidade e Segurança > Arquivos e Pastas > Terminal (ou o programa que abriu o app) > Volumes Removíveis, que o macOS pede na primeira gravação num disco externo. Ou escolha outra pasta e clique em Salvar. |
| `invalid_settings` | Ajustes inválidos. | A pasta precisa ser um caminho completo, começando por `/`. |
| `unexpected_error` | Algo inesperado aconteceu... | Veja o registro em `~/Library/Logs/Digitalizadora` e avise. |
| `forbidden_host` | Acesso recusado... | Abra a página pelo endereço `http://127.0.0.1:8765` (ou `http://localhost:8765`), não por outro nome ou porta. |
| `missing_request_header` | Requisição recusada... | Use a página do app; chamadas feitas à mão precisam do cabeçalho `X-Requested-With: digitalizadora`. |

Outros sintomas:

- **"A porta 8765 já está em uso"**: o app já está aberto em outra janela do Terminal. Feche-a ou rode `DIGITALIZADORA_PORT=8766 make run`.
- **"precisa do Python 3.12 ou mais novo"**: instale o Python 3.12 e rode uma vez `make setup PYTHON=python3.12`.
- **O navegador não abre a página**: confira se a janela do Terminal ainda está aberta e se o endereço é `http://127.0.0.1:8765`.

## Depois de atualizar o macOS ou o firmware da impressora

O Gate 0 foi feito no macOS 15.7.3 com o firmware TIP1CN2446AR da impressora. Não atualize o macOS antes de validar o app com a impressora real; depois de qualquer atualização do macOS ou do firmware:

1. Anote a nova versão com `sw_vers` (e, para o firmware, a página de informações da impressora).
2. Com a impressora ligada pelo cabo USB e uma folha no vidro, rode `make test-hardware` (descoberta real e uma digitalização real).
3. Se falhar, tente também pelo Wi-Fi (sem o cabo, pelo `iniciar-digitalizadora.command`) e compare com o [resultado do Gate 0](docs/gate-0-resultado-2026-10-17.md) e as [capturas](docs/gate-0-capturas/). Enquanto isso, o Captura de Imagem ou o app HP continuam servindo para digitalizar.

## Convenções do código

- Arquivos e pastas em **kebab-case**; classes em **PascalCase**; funções e variáveis em **snake_case**; constantes em **UPPER_SNAKE_CASE**; tabelas em snake_case. Sem abreviações (`identifier`, não `id`; `base_address`, não `url`; `dots_per_inch`, não `dpi`) e com nomes descritivos. Siglas que são nome de formato ou protocolo (PDF, JPEG, HTTP, XML, eSCL) são permitidas.
- **Exceção D6 (aprovada em 2026-10-17):** os módulos Python importáveis (inclusive os testes) usam `snake_case` (`scan_service.py`), porque `import scan-service` é erro de sintaxe. O resto continua em kebab-case.
- Módulos pequenos e pouco acoplados, injeção de dependência por construtor montada só em `composition_root.py`, e separação em controllers, services e repositories.
- Clean Code: no máximo 3 parâmetros por função, sem parâmetros booleanos de modo, sem números mágicos, `Enum` no lugar de textos soltos, type hints, comentários só para explicar o porquê.
- Testes: `pytest` com `asyncio_mode = "auto"`, cada teste rápido e com um único conceito; relógio e `sleep` injetados; sem rede real.

## Estrutura do projeto

```
digitalizadora/
├── Makefile  pyproject.toml  README.md
├── iniciar-digitalizadora.command     duplo clique para iniciar
├── docs/                              spec, plano, resultado e capturas do Gate 0, checklist de aceitação
├── src/digitalizadora/
│   ├── __main__.py  configuration.py  composition_root.py  application_factory.py
│   ├── domain/            modelos, erros e portas (Protocols)
│   ├── services/          regras: digitalizar, codificar, guardar, conectar
│   ├── repositories/      arquivos e JSON
│   ├── infrastructure/    eSCL (httpx), DNS-SD nativo do macOS (ctypes), relógio
│   ├── controllers/       HTTP em português
│   ├── simulator/         impressora falsa
│   └── web/static/        index.html, application.css, application.js
└── tests/                 espelha o src; fakes/, fixtures/, integration/, hardware/
```

## Documentos

- Design: [docs/superpowers/specs/2026-10-13-digitalizadora-design.md](docs/superpowers/specs/2026-10-13-digitalizadora-design.md)
- Plano de implementação: [docs/superpowers/plans/2026-10-17-digitalizadora-plano-final.md](docs/superpowers/plans/2026-10-17-digitalizadora-plano-final.md)
- Gate 0 (validação da impressora): [docs/gate-0-resultado-2026-10-17.md](docs/gate-0-resultado-2026-10-17.md) e [docs/gate-0-capturas/](docs/gate-0-capturas/)
- Checklist de aceitação: [docs/acceptance-checklist.md](docs/acceptance-checklist.md)
- Pesquisa: [docs/pesquisa/digest-da-pesquisa-2026-10-13.md](docs/pesquisa/digest-da-pesquisa-2026-10-13.md)

# Digitalizadora

App pessoal para o MacBook: aperte um botão (ou a tecla **Espaço**) numa página local do navegador e a **HP DeskJet Ink Advantage 2874** digitaliza **uma página do vidro** e grava um **PDF** ou um **JPG** com nome automático. No modo **Documento**, as páginas digitalizadas uma a uma vão para um único PDF, gravado quando você clica em **Finalizar PDF**. Não usa driver nem software da HP: fala direto com a impressora pelo protocolo **eSCL (AirScan)**, pelo **cabo USB** (preferido) ou pelo **Wi-Fi**.

## O que você precisa

- Mac com macOS 15 e **Python 3.12 ou mais novo** (`python3 --version`). Se o `python3` for mais velho, instale o Python 3.12 e prepare o ambiente com `make setup PYTHON=python3.12`.
- As ferramentas de linha de comando da Apple (Command Line Tools), que trazem o `make`.
- A impressora **ligada** e conectada ao Mac pelo **cabo USB**, o jeito recomendado (não depende de nenhuma permissão do macOS). Sem o cabo, ela precisa estar na **mesma rede Wi-Fi do Mac** (a 2874 só usa 2,4 GHz), com a luz do Wi-Fi fixa e a VPN desligada.
- Espaço livre na pasta de saída: o app recusa digitalizar com menos de 1 GiB livre. A pasta padrão, `~/Pictures/Digitalizadora`, fica no disco interno; para volumes muito grandes, um disco externo é recomendado. Na primeira gravação num disco externo, o macOS pede permissão para o programa que abriu o app (normalmente o Terminal) acessar Volumes Removíveis: clique em **Permitir**.
- Espaço livre no disco interno do Mac para o modo Documento: as páginas de um documento em andamento ficam guardadas no Mac até você finalizar, e o app recusa uma página nova com menos de 1 GiB livre ali (mais o espaço de 3 páginas).

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

O seletor **Modo** no topo da página tem duas opções:

- **Rápido** (o padrão): cada Espaço digitaliza uma folha e grava um arquivo PDF ou JPG.
- **Documento**: cada Espaço acrescenta uma página a um documento, e no fim um clique em **Finalizar PDF** grava um único PDF com todas as páginas. Veja a seção [Documento de várias páginas](#documento-de-várias-páginas).

No modo Rápido:

1. Coloque a folha (ou a foto) no vidro, com a face para baixo, e feche a tampa.
2. Aperte **Espaço** (ou clique em **Digitalizar**). Espere cerca de 15 s (na qualidade Foto, cerca de 75 s): o status mostra Preparando, Digitalizando, Salvando e por fim "Pronto! Salvo como AAAA_MM_DD__HH_MM_SS_NNNNNNNNN.pdf".
3. Levante a tampa, troque a folha e aperte Espaço de novo. Não precisa tocar no mouse.

Ajustes (salvos na hora):

- **Modo:** Rápido ou Documento.
- **Formato:** PDF ou JPG (só no modo Rápido; o modo Documento sempre grava PDF).
- **Resolução** (75 a 1200 dpi) e **Cor** (colorido ou tons de cinza).
- **Cortar automaticamente e remover o fundo:** acha até 2 fotos (ou uma folha menor que o vidro), inclusive tortas, e dá uma moldura a cada uma. Veja [Molduras de corte](#molduras-de-corte-até-2-fotos-e-qualidade-do-jpeg).
- **Pasta de saída:** digite o caminho completo (por exemplo `/Volumes/MeuDisco/Scans`) e clique em **Salvar**. O padrão é `~/Pictures/Digitalizadora`. A página mostra o espaço livre e quantas páginas ainda cabem; se a pasta sumir (por exemplo, um disco externo desconectado), mostra "Pasta de saída indisponível" no lugar do espaço livre.

Os arquivos se chamam `AAAA_MM_DD__HH_MM_SS_NNNNNNNNN.pdf` ou `.jpg`: a data e a hora locais da digitalização e 9 dígitos de nanossegundos (por exemplo `2026_10_18__16_14_03_123456789.jpg`). Quando uma gravação cria mais de um arquivo (duas fotos no modo Rápido, ou **Aplicar**, **Girar** e **Detectar** com duas molduras), todos os arquivos dela repartem a mesma data, hora e nanossegundos e ganham um contador no fim, na ordem de leitura: `2026_10_18__16_14_03_123456789__1.jpg` e `2026_10_18__16_14_03_123456789__2.jpg`. Uma gravação de um arquivo só não tem contador. O app nunca sobrescreve nem apaga outro arquivo. O nome tem os segundos, então a ordem alfabética é a ordem do tempo, e a mesma imagem pode ser salva mais de uma vez (cada gravação ganha um nome novo; num choque improvável, o app tenta o nanossegundo seguinte para todos os arquivos da gravação, mantendo os contadores). Arquivos antigos com nomes de padrões anteriores continuam intocados.

## Molduras de corte, até 2 fotos e qualidade do JPEG

Uma **moldura** é um quadrilátero com quatro cantos livres: serve para uma foto reta e para uma foto torta, deitada em qualquer ângulo no vidro. O corte **endireita** a região da moldura (e o "lado de cima" da moldura é o lado de cima da foto recortada). Cada digitalização aceita **até 2 molduras**, para digitalizar duas fotos de uma vez.

- **Modo Rápido.** Com **Cortar automaticamente** ligado, cada foto achada vira um arquivo (cada um com o seu nome de data e hora, mesmo formato). O painel **Última digitalização** mostra a miniatura com as molduras (a 1 em azul e linha contínua, a 2 em laranja e tracejada, com o número ao lado), a lista de arquivos, **Girar ↻** e **Ampliar**. O original do scanner fica guardado em `~/Library/Application Support/Digitalizadora/quick-scan/` até a próxima digitalização; por isso cada ajuste (**Aplicar**, **Girar ↻**, **Detectar**) grava arquivos novos a partir dele, sem perder qualidade, com nomes novos; os arquivos gravados antes ficam como estavam (nada é substituído nem apagado, nem quando uma moldura é removida) e o painel passa a listar os arquivos mais novos (a tela diz "N arquivos novos salvos: …" e que os anteriores foram mantidos). Se o app fechar no meio de um ajuste, ao abrir ele termina o ajuste em arquivos novos; nenhum arquivo incompleto aparece sob um nome final. Sem o original guardado, os dois botões ficam desabilitados e o painel explica.
- **Modo Documento.** Cada página guarda as suas molduras (miniaturas com as mesmas cores e números e, com duas, o texto "2 molduras"). Uma página com 2 molduras vira **2 páginas no PDF**, na ordem de leitura (da esquerda para a direita, depois de cima para baixo).
- **Ampliar** (os dois modos, o mesmo editor). Arraste um **canto** (só ele se move), um **lado** (anda na perpendicular dele), o **interior** (move a moldura toda) ou a **alça redonda de cima** (gira a moldura). Botões: **Adicionar moldura** (no máximo 2), **Remover moldura**, **Girar moldura ↻** (muda o lado de cima da foto recortada), **Detectar automaticamente**, **Sem corte**, **Girar ↻** (gira a página), **Cancelar** (Esc) e **Aplicar**. Com o teclado: Tab percorre as alças da moldura selecionada, depois **Selecionar moldura N**; as setas movem a alça (Shift anda 10 vezes mais; nas laterais só valem as setas que apontam na perpendicular; na alça de girar, esquerda e direita giram 0,5°, com Shift 5°). Um movimento que deixaria a moldura torta demais (côncava, achatada ou com lado menor que 2%) é ignorado, e a tela diz.
- **Qualidade do JPEG.** O scanner entrega JPEG de qualidade 50; cada regravação por corte, endireitamento ou giro usa sempre qualidade 90 (não há ajuste na tela). Uma imagem sem corte e sem giro mantém os bytes do scanner. Um `settings.json` antigo com `jpeg_quality` continua valendo: o valor é ignorado.

## Documento de várias páginas

Para juntar várias folhas num único PDF (um contrato, um caderno, uma pilha de notas fiscais):

1. No seletor **Modo**, escolha **Documento**. O botão grande passa a se chamar **Adicionar página**, e o seletor PDF/JPG e o painel da última digitalização (miniatura, nome e tamanho do arquivo) somem (o documento é sempre PDF).
2. Se quiser, digite um nome em **Nome do documento (opcional)**. Dá para trocar o nome até finalizar.
3. Coloque a primeira folha no vidro e aperte **Espaço**. O status mostra "Preparando a página 1…", "Digitalizando a página 1… (cerca de 15 s)" e "Guardando a página 1…", e a miniatura aparece na grade.
4. Troque a folha e aperte Espaço de novo, quantas vezes quiser. A barra abaixo da grade mostra quantas páginas o documento tem e o tamanho aproximado, por exemplo "3 páginas · ~2,4 MB".
5. Aperte **Enter** (ou clique em **Finalizar PDF**) e confirme em **Finalizar**. O app grava o PDF na pasta de saída e mostra, por exemplo, "Pronto! Salvo como Contrato do apartamento.pdf (3 páginas)". O campo do nome fica vazio para o próximo documento.

Na grade, cada miniatura tem o número da página e os seus botões:

- **Reordenar:** arraste a miniatura e solte antes ou depois de outra. Pelo teclado, use os botões ◀ e ▶ da página, ou **Mover para…**, que pergunta a nova posição.
- **Excluir uma página:** botão × da página.
- **Descartar a última:** botão **Descartar última** (ou Backspace).
- **Cancelar documento:** apaga as páginas guardadas sem gravar PDF. Sempre pede confirmação, com o foco começando em **Voltar**.

As edições ficam desabilitadas enquanto uma página está sendo digitalizada.

Teclado no modo Documento (com o foco fora do campo do nome):

| Tecla | O que faz |
|---|---|
| Espaço | Adiciona uma página |
| Backspace | Descarta a última página; segurar a tecla descarta só uma |
| Enter | Abre a confirmação de finalizar; segurar a tecla abre a confirmação, mas nunca confirma |
| Esc | Fecha a confirmação; fora dela, leva o foco de volta ao botão **Adicionar página** |

Depois de "Descartar última", de fechar uma confirmação, de salvar o nome com Enter, de soltar uma miniatura arrastada ou de qualquer clique na grade, o foco volta ao botão **Adicionar página**: o próximo Espaço sempre adiciona uma página e nunca repete a ação. No campo do nome, Backspace apaga texto e Enter salva o nome. Os anúncios para o leitor de tela (VoiceOver) dizem o que mudou, por exemplo "Página 3 movida para a posição 2" ou "Página 12 descartada. O documento tem 11 páginas."

**Nome do arquivo.** Sem nome, o PDF recebe o nome automático `AAAA_MM_DD__HH_MM_SS_NNNNNNNNN.pdf`, no mesmo formato do modo Rápido. Com nome, vira `<nome>.pdf`, e o título do PDF é o nome. O app limpa o nome para ele servir em qualquer disco, inclusive os discos externos em exFAT: `/ \ : * ? " < > |` viram `-`, caracteres invisíveis saem, espaços repetidos viram um só, e saem os pontos do começo e do fim e um `.pdf` digitado no final (`Recibo: março` grava `Recibo- março.pdf`; `Relatório.PDF` grava `Relatório.pdf`). Acentos ficam. Um nome com mais de 120 caracteres (ou mais de 200 bytes) é recusado, nunca cortado. Se o arquivo já existir, o novo vira `<nome> (2).pdf`, depois `(3)`, e assim por diante: nunca sobrescreve, nem quando a diferença é só de maiúsculas.

**Qualidade por página.** Cada página guarda a qualidade da hora em que foi digitalizada, então dá para trocar a qualidade no meio do documento (por exemplo, uma foto a 600 dpi entre páginas de texto). Todas saem no PDF com o tamanho real da folha.

**Documento grande.** Não há limite de páginas. Acima de 300 páginas (ou de 1 GiB) a página avisa "Documento grande: finalizar pode levar alguns segundos e usar bastante memória."

**Modo Rápido com um documento em andamento.** O documento continua guardado: a página mostra "Documento em andamento: N páginas" e o botão **Voltar ao modo Documento**. Digitalizar no modo Rápido não mexe no documento.

### Onde ficam as páginas

Até você finalizar, as páginas ficam no disco interno do Mac, não na pasta de saída: assim o documento não se perde se o disco externo sair.

- Uso normal: `~/Library/Application Support/Digitalizadora/drafts/current`
- Simulador (`make run-simulated`): `~/Digitalizadora-simulador/Library/Application Support/Digitalizadora/drafts/current`

A pasta `current` tem o `manifest.json` (nome, ordem das páginas e marcas da finalização), um `page-<identificador>.jpg` por página (o JPEG que veio da impressora) e um `thumbnail-<identificador>.jpg` por página (a miniatura). **Não mexa nos arquivos de `current/`** nem no `.owner-lock` ao lado dela: o app confere cada página pelo tamanho registrado e põe de lado o que não bate. A linha "Espaço no Mac para as páginas" mostra o espaço livre desse disco; perto do limite aparece "Pouco espaço no disco do Mac para as páginas do documento. Libere espaço antes de continuar."

### Se o app ou o Mac caírem

O documento em andamento volta sozinho na próxima abertura, com todas as páginas que já estavam guardadas, e a página diz o que a retomada fez, por exemplo "Documento em andamento recuperado: 41 páginas." ou "Documento em andamento recuperado: 41 páginas. A página 37 não pôde ser recuperada; digitalize-a de novo." Se o modo salvo era Rápido, a página troca para Documento nesse momento (só na retomada). A folha que estava sendo digitalizada na hora da queda não entra: digitalize-a de novo.

Dois avisos pedem para conferir a pasta de saída antes de finalizar de novo:

- "Uma finalização deste documento foi interrompida às HH:MM. Confira na pasta de saída se o PDF já existe antes de finalizar de novo." A queda foi durante a gravação do PDF. Se o PDF está na pasta e abre com todas as páginas, clique em **Cancelar documento**; se não está, finalize de novo.
- "Este documento talvez já tenha sido salvo como <caminho>. Confira antes de finalizar de novo." O PDF foi gravado, mas o app não conseguiu confirmar que ele existe (por exemplo, o disco externo estava desconectado na abertura). Reconecte o disco e clique em **Finalizar PDF**: se o arquivo existir, o app só encerra o documento, sem gravar uma cópia.

### Pasta `set-aside-…`

Quando o app encontra na pasta do documento algo que não consegue usar com segurança (um `manifest.json` ilegível, uma página com tamanho diferente do registrado, ou as páginas de um documento antigo que ficaram para trás), ele não apaga nada: move os arquivos para uma pasta como `set-aside-20261017-101500-a1b2c3d4`, ao lado de `current` dentro de `drafts/`, e a página diz onde ela ficou ("Não consegui ler o documento em andamento. As páginas foram guardadas em <pasta>." ou "Os arquivos danificados foram guardados em <pasta>."). O app nunca apaga essas pastas. Para aproveitar o que está dentro, abra os `page-<identificador>.jpg` no Preview; a lista `pages` do `manifest.json` (quando ele é legível) dá a ordem em que as páginas estavam. Digitalize de novo o que faltar e, depois de conferir, apague a pasta pelo Finder.

### Uma cópia do app por vez

Só um Digitalizadora pode usar a pasta do documento. Uma segunda cópia, mesmo em outra porta (`DIGITALIZADORA_PORT=8766 make run`), para na partida com "O Digitalizadora já está aberto em outra janela do Terminal. Use aquela janela, ou feche-a antes de abrir de novo." Duas abas do navegador abertas na mesma cópia funcionam: o que muda numa aparece na outra em instantes.

## Testar sem a impressora (simulador)

O simulador é uma impressora de mentira que fala eSCL como a impressora real. Use dois Terminais:

```
make simulator
make run-simulated
```

O primeiro liga a impressora falsa em `http://127.0.0.1:8080/eSCL`; o segundo abre o app apontando para ela. O `make run-simulated` usa uma pasta pessoal separada, `~/Digitalizadora-simulador`: os ajustes, o endereço da impressora, o registro e os arquivos de teste (em `~/Digitalizadora-simulador/Pictures/Digitalizadora`) ficam lá, e o uso real não é afetado. Para usar outra pasta: `make run-simulated SIMULATED_HOME="$HOME/outra-pasta"`. Essa pasta pode ser apagada quando você quiser.

Para testar as molduras com fotos (formas sintéticas, nunca pessoas), ligue o simulador com uma cena: `DIGITALIZADORA_SIMULATOR_SCENE=photos_two make simulator` (duas fotos giradas sobre a tampa branca; `photos_one` põe uma só; o padrão, `sheet`, é uma folha). Cada foto tem um quadradinho magenta no canto de cima à esquerda e um verde no de cima à direita, para conferir que o recorte sai em pé.

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
| `no_open_document` | Não há documento em andamento... | Adicione uma página para começar. Outra aba pode ter finalizado ou cancelado o documento. |
| `page_not_found` | Essa página não está mais no documento... | A grade já foi atualizada (outra aba pode ter excluído a página); repita a ação se ainda quiser. |
| `invalid_page_order` | A nova ordem das páginas não confere com o documento... | A grade já foi atualizada com a ordem atual; arraste ou mova a página de novo. |
| `invalid_document_name` | Nome de documento inválido... | Use até 120 caracteres, com letras ou números. Deixe o campo vazio para o nome automático. |
| `empty_document` | O documento não tem páginas... | Adicione pelo menos uma página antes de finalizar. |
| `document_busy` | O documento está sendo finalizado ou alterado... | Espere a finalização (ou a outra mudança) terminar e aperte Espaço de novo; a folha no vidro não foi digitalizada. |
| `draft_folder_in_use` | O Digitalizadora já está aberto em outra janela do Terminal... | Aparece no Terminal, na partida. Use a janela que já está aberta, ou feche-a antes de abrir de novo (também vale para uma cópia em outra porta). |
| `draft_storage_unavailable` | Não consigo guardar as páginas do documento no disco do Mac... | Veja o registro em `~/Library/Logs/Digitalizadora`. Se o aviso apareceu ao abrir o app, nada foi apagado: feche o Digitalizadora e abra de novo. |
| `insufficient_draft_storage` | Pouco espaço livre no disco do Mac para guardar as páginas do documento... | Libere espaço no disco interno (as páginas ficam no Mac, não na pasta de saída); o app exige 1 GiB livre mais o espaço de 3 páginas. |
| `document_assembly_failed` | Não consegui montar o PDF porque uma página guardada não pôde ser lida como imagem... | Veja o registro em `~/Library/Logs/Digitalizadora`; o documento continua guardado. |
| `damaged_document_page` | Uma página guardada do documento está danificada ou sumiu do disco do Mac... | A página fica marcada na grade: exclua-a (×), digitalize a folha de novo, mova a página nova para o lugar e finalize. |
| `document_too_large` | O documento é grande demais para montar com a memória livre do Mac... | Feche outros programas e finalize de novo; o documento continua guardado. |

Outros sintomas:

- **"A porta 8765 já está em uso"**: provavelmente o app já está aberto em outra janela do Terminal; use aquela janela. Se a porta é de outro programa, rode `DIGITALIZADORA_PORT=8766 make run`.
- **"O Digitalizadora já está aberto em outra janela do Terminal"** (na partida): outra cópia já usa a pasta do documento, mesmo que em outra porta. Use a janela dela, ou feche-a e abra de novo.
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
│   ├── services/          regras: digitalizar, codificar, guardar, conectar, documento de várias páginas
│   ├── repositories/      arquivos, JSON e o rascunho do documento
│   ├── infrastructure/    eSCL (httpx), DNS-SD nativo do macOS (ctypes), relógio
│   ├── controllers/       HTTP em português
│   ├── simulator/         impressora falsa
│   └── web/static/        index.html, application.css e os scripts scan-trigger-policy.js, error-banner.js,
│                          document-page-policy.js, document-panel.js e application.js
└── tests/                 espelha o src; fakes/, fixtures/, integration/, hardware/
```

## Documentos

- Design: [docs/superpowers/specs/2026-10-13-digitalizadora-design.md](docs/superpowers/specs/2026-10-13-digitalizadora-design.md)
- Design do documento de várias páginas: [docs/superpowers/specs/2026-10-17-documento-de-varias-paginas.md](docs/superpowers/specs/2026-10-17-documento-de-varias-paginas.md)
- Plano de implementação: [docs/superpowers/plans/2026-10-17-digitalizadora-plano-final.md](docs/superpowers/plans/2026-10-17-digitalizadora-plano-final.md)
- Gate 0 (validação da impressora): [docs/gate-0-resultado-2026-10-17.md](docs/gate-0-resultado-2026-10-17.md) e [docs/gate-0-capturas/](docs/gate-0-capturas/)
- Checklist de aceitação: [docs/acceptance-checklist.md](docs/acceptance-checklist.md)
- Pesquisa: [docs/pesquisa/digest-da-pesquisa-2026-10-13.md](docs/pesquisa/digest-da-pesquisa-2026-10-13.md)

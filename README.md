# Digitalizadora

App local para macOS: numa página do navegador, uma tecla (**Espaço**) digitaliza uma folha do vidro da impressora **HP DeskJet 2800 series** e grava um PDF ou JPG com nome automático. O modo **Documento** junta várias folhas num único PDF. Não usa driver nem software da HP: fala com a impressora pelo protocolo eSCL (AirScan), pelo cabo USB ou pelo Wi-Fi. O servidor só escuta em `127.0.0.1`.

## Requisitos

- macOS com **Python 3.12 ou mais novo** (`python3 --version`) e as Command Line Tools da Apple (trazem o `make`).
- Impressora ligada, no **cabo USB** (recomendado) ou na mesma rede **Wi-Fi 2,4 GHz** do Mac, com a VPN desligada.
- Pelo USB não é preciso nenhuma permissão. Pelo Wi-Fi, o macOS exige a permissão de **Rede Local** para o programa que abriu o app; o Terminal.app é o recomendado.

## Instalar e rodar

```
make setup     # cria o .venv e instala as dependências (uma vez)
make run       # sobe o app em http://127.0.0.1:8765
```

Ou dê duplo clique em `iniciar-digitalizadora.command`: ele prepara o ambiente na primeira vez, sobe o app e abre o navegador. Deixe a janela do Terminal aberta enquanto digitaliza. Se o `python3` for mais velho, use `make setup PYTHON=python3.12`.

## Como usar

- **Rápido** (padrão): Espaço digitaliza e grava um arquivo. **Documento**: Espaço acrescenta uma página; **Enter** (ou **Finalizar PDF**) grava um PDF com todas. Na grade dá para reordenar (arrastar, ◀ ▶ ou **Mover para…**), excluir, **Descartar última** (Backspace) e **Cancelar documento**. Um documento em andamento sobrevive a quedas.
- **Cortar automaticamente**: acha até 2 fotos (ou uma folha menor que o vidro, inclusive tortas) e dá uma **moldura** a cada uma. **Ampliar** abre o editor: arraste cantos, lados, o interior ou a alça de giro; **Girar ↻** gira a página; **Detectar automaticamente** refaz as molduras; **Aplicar** grava.
- O original do scanner fica guardado sem alterações. Cada **Aplicar**, **Girar** ou **Detectar** gera arquivos novos a partir dele, em qualidade JPEG 100, e mantém os anteriores. Uma imagem sem corte e sem giro mantém os bytes do scanner.
- **Onde ficam os arquivos**: na pasta de saída (padrão `~/Pictures/Digitalizadora`). Nome: `AAAA_MM_DD__HH_MM_SS_NNNNNNNNN.pdf` ou `.jpg` (data e hora locais e nanossegundos). Uma gravação com vários arquivos (duas fotos) repete o nome e acrescenta `__1`, `__2`, na ordem de leitura. No modo Documento com nome, o PDF vira `<nome>.pdf`, e um nome repetido vira `<nome> (2).pdf`. O app nunca sobrescreve nem apaga arquivos da pasta de saída.
- O app recusa digitalizar com menos de 1 GiB livre na pasta de saída (e, no modo Documento, no disco interno).

## Ajustes

Salvos na hora, em `~/Library/Application Support/Digitalizadora/settings.json`.

| Ajuste | Opções | Padrão |
|---|---|---|
| Modo | Rápido, Documento | Rápido |
| Formato (só no Rápido) | PDF, JPG | PDF |
| Resolução | 75, 100, 150, 200, 300, 400, 600, 1200 dpi (1200 dpi é lento e usa muita memória) | 300 |
| Cor | Colorido, tons de cinza | Colorido |
| Cortar automaticamente | ligado, desligado | desligado |
| Margem de segurança no corte | ligada, desligada | ligada |
| Pasta de saída | caminho completo (`/...` ou `~/...`) | `~/Pictures/Digitalizadora` |

Variáveis de ambiente: `DIGITALIZADORA_PORT` (porta, padrão 8765), `DIGITALIZADORA_OUTPUT_FOLDER` (pasta de saída inicial) e `DIGITALIZADORA_SCANNER_ADDRESS` (endereço da impressora no Wi-Fi, por exemplo `http://HP000000000001.local:8080/eSCL`).

## Problemas comuns

O registro fica em `~/Library/Logs/Digitalizadora/digitalizadora.log`.

- "Não encontrei a impressora": ligue-a, confira o cabo USB ou o Wi-Fi 2,4 GHz e tente de novo.
- `local_network_blocked` (só no Wi-Fi): use o USB, ou abra pelo launcher e confira Ajustes do Sistema > Privacidade e Segurança > Rede Local.
- "A porta 8765 já está em uso" ou "já está aberto em outra janela": use a janela que já está aberta; só uma cópia do app pode usar o rascunho do documento.
- "Já existe uma digitalização em andamento": espere o status voltar a "Pronto".
- Página não abre: confira se o Terminal continua aberto e o endereço é `http://127.0.0.1:8765`.

## Desenvolvimento

```
make test            # testes, sem rede e sem impressora
make lint            # ruff
make check           # lint + testes
make simulator       # impressora de mentira em http://127.0.0.1:8080/eSCL
make run-simulated   # app apontando para o simulador, com dados em ~/Digitalizadora-simulador
make test-hardware   # testes com a impressora real (cabo USB, folha no vidro)
```

- [docs/arquitetura.md](docs/arquitetura.md): camadas, pacotes, fluxos, dados em disco, API e regras que não podem quebrar.
- [docs/desenvolvimento.md](docs/desenvolvimento.md): ambiente, convenções, testes e receitas para mudanças comuns.
- [docs/acceptance-checklist.md](docs/acceptance-checklist.md): checklist manual de aceitação.
- [docs/historico/](docs/historico/README.md): planejamento, pesquisa, Gate 0 e specs antigos.

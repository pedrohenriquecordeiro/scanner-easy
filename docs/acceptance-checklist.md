# Checklist de aceitação do Digitalizadora

Preencha a coluna **Resultado** com OK, FALHOU (e o que viu) ou N/A. Faça primeiro a parte do simulador (sem impressora) e só depois a da impressora real. O Gate 0 já foi concluído em 2026-10-17 ([resultado](gate-0-resultado-2026-10-17.md)); este checklist não repete nenhum passo dele.

Anote ao começar:

- Data: ____________  macOS (`sw_vers -productVersion` e `sw_vers -buildVersion`): ____________
- Versão do código (`git rev-parse --short HEAD`): ____________

## Parte A: simulador (sem impressora)

Deixe a impressora de verdade **desligada** durante toda a parte A: com ela ligada, quando o simulador parar (A16 a A18) o app procura de novo e acha a impressora real pelo USB ou pelo Wi-Fi. Use duas janelas de terminal (o Terminal.app é o recomendado). Pasta de teste: `~/Digitalizadora-teste`. O `make run-simulated` guarda os ajustes em `~/Digitalizadora-simulador`, e a variável `DIGITALIZADORA_OUTPUT_FOLDER` só vale quando ainda não há ajustes salvos; por isso o passo A0 apaga essa pasta antes de começar.

| # | O que fazer | Resultado esperado | Resultado |
|---|---|---|---|
| A0 | Num terminal, apagar os ajustes e os arquivos de execuções anteriores do simulador (inclusive da verificação manual da Tarefa 12): `rm -rf ~/Digitalizadora-simulador ~/Digitalizadora-teste` | O comando termina sem mensagem; as duas pastas deixam de existir (`ls ~/Digitalizadora-simulador ~/Digitalizadora-teste` responde "No such file or directory") |  |
| A1 | Terminal 1: `make simulator` | Aparece "Impressora de mentira ligada em http://127.0.0.1:8080/eSCL" |  |
| A2 | Terminal 2: `DIGITALIZADORA_OUTPUT_FOLDER="$HOME/Digitalizadora-teste" make run-simulated` | Aparece o endereço `http://127.0.0.1:8765` e o aviso para manter a janela aberta |  |
| A3 | Abrir `http://127.0.0.1:8765` no navegador | Página em português; selo "Impressora pronta (USB)" em até 15 s (o simulador entra como endereço manual em 127.0.0.1, e um endereço de loopback conta como rota USB pela G0C-16); botão Digitalizar com o foco; linha "Espaço livre: ... cabem ~N páginas" |  |
| A4 | Apertar **Espaço** | O botão desabilita; o status passa por "Preparando…", "Digitalizando… (cerca de 15 s; no modo Foto, cerca de 75 s)" e "Salvando…"; termina com "Pronto! Salvo como AAAA-MM-DD_00001.pdf" |  |
| A5 | Abrir o arquivo da pasta de teste no Preview | O PDF abre com 1 página |  |
| A6 | Olhar o painel da última digitalização | Miniatura, nome do arquivo, tamanho (por exemplo "1,2 MB") e hora; "Digitalizações nesta sessão: 1" |  |
| A7 | Escolher **JPG** e apertar Espaço | Surge `AAAA-MM-DD_00002.jpg` na pasta, abre no Preview |  |
| A8 | Trocar o modo para Foto e recarregar a página (Cmd+R) | Formato JPG e modo Foto continuam selecionados; a pasta continua a mesma |  |
| A9 | Segurar a tecla Espaço por 3 segundos | Só um arquivo novo é criado |  |
| A10 | Apertar Espaço duas vezes seguidas, bem rápido (ou clicar duas vezes) | Só um arquivo novo; se aparecer faixa vermelha, é "Já existe uma digitalização em andamento." |  |
| A11 | Clicar no campo da pasta, digitar um espaço e apertar Espaço | O espaço entra no texto; nenhuma digitalização começa |  |
| A12 | Digitar `pasta/relativa` no campo e clicar em **Salvar** | Mensagem "Ajustes inválidos." logo abaixo do campo; a pasta anterior continua valendo |  |
| A13 | Digitar `/Digitalizadora-sem-permissao` e clicar em **Salvar** | Mensagem "Não consigo gravar na pasta de saída. Se for um disco externo, confira se está conectado." abaixo do campo |  |
| A14 | Digitar o caminho completo `/Users/<seu-usuário>/Digitalizadora-teste/outra` e clicar em **Salvar**; depois apertar Espaço | A pasta é criada e o novo arquivo cai nela |  |
| A15 | Apagar a pasta `~/Digitalizadora-teste/outra` (Finder ou `rm -r ~/Digitalizadora-teste/outra`) e esperar 2 s | A linha de espaço livre vira "Pasta de saída indisponível. Se for um disco externo, confira se está conectado."; o aviso "Recomendado: use um disco externo" não aparece |  |
| A16 | Com a pasta apagada, apertar Espaço | A pasta é criada de novo, o arquivo cai nela e a linha volta a mostrar o espaço livre |  |
| A17 | Procurar arquivos `.part` nas pastas de teste (`find ~/Digitalizadora-teste -name "*.part"`) | Nenhum resultado |  |
| A18 | No Terminal 1, Control-C (parar o simulador); esperar até 25 s (a próxima consulta pode levar 15 s, e ela ainda faz uma busca de 5 s antes de desistir) | O selo muda para "Impressora não encontrada" e aparece a explicação abaixo do cabeçalho, que sugere conferir o cabo USB |  |
| A19 | Com o simulador parado, apertar Espaço | Faixa vermelha com ícone e texto: "Não encontrei a impressora. Confira se está ligada e com o cabo USB conectado ao Mac. Sem o cabo, confira se a luz do Wi-Fi está acesa e se ela está na mesma rede do Mac (2,4 GHz)." |  |
| A20 | Religar o simulador (`make simulator`) e apertar Espaço | A digitalização funciona sem reiniciar o app |  |
| A21 | Abrir um terceiro terminal e rodar `make run` | Mensagem "A porta 8765 já está em uso..." e o comando termina |  |
| A22 | Control-C no Terminal 2 e rodar `make run-simulated` de novo | O app encerra sem erro e sobe de novo |  |
| A23 | Ajustes do Sistema > Aparência > Escuro, recarregar a página; navegar com a tecla Tab | Texto legível no modo escuro; o foco aparece com contorno visível em todos os controles |  |

## Parte B: impressora real

A rota preferida é o **cabo USB**: o macOS a anuncia em `localhost` e ela não depende da permissão de Rede Local. O Wi-Fi é o plano de reserva e só é testado em B9 e B10.

Antes de começar:

- [ ] Parar o simulador e o `make run-simulated` da parte A (Control-C nas duas janelas).
- [ ] Impressora ligada e **conectada ao Mac pelo cabo USB**; para B9 e B10, ela também precisa estar no mesmo Wi-Fi do Mac (luz do Wi-Fi acesa, rede de 2,4 GHz), com a VPN desligada.
- [ ] Abrir pelo launcher `iniciar-digitalizadora.command` (ele abre o Terminal.app, que também tem a permissão de Rede Local para a rota Wi-Fi).
- [ ] Pasta de saída: a padrão, `~/Pictures/Digitalizadora` (disco interno, 12 GB livres em 2026-10-17), ou uma pasta num disco externo, se você tiver um; um disco externo só é recomendado para volumes muito grandes.
- [ ] Uma folha de texto no vidro.

| # | O que fazer | Resultado esperado | Resultado |
|---|---|---|---|
| B1 | Duplo clique em `iniciar-digitalizadora.command`; se for usar um disco externo, digitar a pasta dele no campo Pasta de saída e clicar em **Salvar** (a parte A usou uma pasta pessoal separada, `~/Digitalizadora-simulador`, então a pasta padrão `~/Pictures/Digitalizadora` continua valendo) | O navegador abre em `http://127.0.0.1:8765`; selo "Impressora pronta (USB)" (a cada início o app procura a impressora e prefere o cabo USB; pode levar alguns segundos); a pasta mostrada é a padrão ou a do disco externo |  |
| B2 | Escolher PDF, modo Documento, apertar Espaço | Em cerca de 15 a 25 s aparece "Pronto! Salvo como AAAA-MM-DD_00001.pdf"; anote o tempo: ______ s |  |
| B3 | Abrir o PDF no Preview e ver Ferramentas > Mostrar Inspetor | 1 página de cerca de 216 × 297 mm (o vidro inteiro; não é exatamente A4, que tem 210 × 297 mm), com o texto legível |  |
| B4 | Escolher JPG, modo Documento, digitalizar; abrir no Preview > Ferramentas > Mostrar Inspetor > aba Mais Informações | Arquivo `.jpg` abre; resolução de 300 dpi |  |
| B5 | Modo Documento econômico, digitalizar em JPG | Resolução de 200 dpi; imagem em tons de cinza; anote o tempo: ______ s (no Gate 0, cinza a 300 dpi levou cerca de 10 s) |  |
| B6 | Uma foto no vidro, modo Foto, JPG | Resolução de 600 dpi, cores corretas; cerca de 75 s; anote o tempo: ______ s |  |
| B7 | Dez digitalizações seguidas, só com Espaço, sem tocar no mouse | Dez arquivos com números em sequência, sem buracos e sem repetição (depois de cada página a impressora fica ocupada por 4 a 5 s; o app espera sozinho) |  |
| B8 | Deixar a impressora parada por 10 minutos e apertar Espaço | A digitalização funciona (o primeiro pedido pode demorar mais, porque ela dorme depois de cerca de 5 minutos); anote o atraso: ______ s |  |
| B9 | Desconectar o cabo USB, esperar até 15 s e apertar Espaço | O selo passa a "Impressora pronta (Wi-Fi)" (ou muda na própria digitalização) e o arquivo é salvo pelo Wi-Fi, sem reiniciar o app |  |
| B10 | Com o cabo ainda desconectado, desligar o Wi-Fi do Mac e apertar Espaço | Faixa "Não encontrei a impressora. Confira se está ligada e com o cabo USB conectado ao Mac. Sem o cabo, confira se a luz do Wi-Fi está acesa e se ela está na mesma rede do Mac (2,4 GHz)." (se aparecer a mensagem sobre a Rede Local, anote) |  |
| B11 | Religar o Wi-Fi do Mac, reconectar o cabo USB e apertar Espaço | A digitalização funciona sem reiniciar o app; o selo pode continuar em "(Wi-Fi)", porque o app só troca de rota quando a rota em uso deixa de responder |  |
| B12 | Tirar a permissão de gravação da pasta de saída (`chmod a-w ~/Pictures/Digitalizadora`; com disco externo, desconecte o disco) e apertar Espaço | Faixa "Não consigo gravar na pasta de saída..." logo, sem esperar a impressora digitalizar |  |
| B13 | Devolver a permissão (`chmod u+w ~/Pictures/Digitalizadora`; ou reconectar o disco) e apertar Espaço | A digitalização funciona e o arquivo cai na pasta de saída |  |
| B14 | Procurar arquivos `.part` na pasta de saída | Nenhum arquivo `.part` sobrou |  |
| B15 | Apertar Espaço três vezes enquanto a impressora digitaliza | Só um arquivo novo; a faixa pode mostrar "Já existe uma digitalização em andamento." |  |
| B16 | Abrir a tampa durante uma digitalização (de propósito) | O app mostra uma mensagem em português (por exemplo "A digitalização falhou...") e volta a aceitar Espaço |  |
| B17 | Fechar a janela do Terminal e tentar abrir a página | A página não responde; ao dar duplo clique no `.command` de novo, tudo volta a funcionar |  |
| B18 | (Opcional) Fechar o app, rodar `make run` pelo terminal do VS Code com o cabo USB conectado e apertar Espaço | Selo "Impressora pronta (USB)" e a digitalização funciona: a cada início o app procura de novo e prefere o USB mesmo que B9 tenha deixado o Wi-Fi salvo (G0C-15), e a rota USB não depende da permissão de Rede Local |  |

Resumo (preencha no fim):

- Páginas por hora no uso real: ____________
- Problemas encontrados: ____________
- Decisão: aceitar a v1 / corrigir antes: ____________

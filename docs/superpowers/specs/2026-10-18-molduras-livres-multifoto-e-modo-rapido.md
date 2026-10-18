# Molduras livres, até 2 fotos por digitalização e o modo Rápido com moldura: design

**Data:** 2026-10-18 · **Status:** servidor implementado (T51 a T60, seção 13) e interface implementada (T61 a T65, seção 14; aceitação no simulador, T67, na 14.4); falta só a limpeza do servidor da 14.5 e a aceitação na impressora real (T68). Decisões tomadas e medidas feitas (seções 2 e 3), contratos fechados (seções 4 a 8), tarefas T51 a T68 na seção 11 · **Substitui** do [Moldura de corte por página](2026-10-18-moldura-de-corte-por-pagina.md): D1 (a moldura é um retângulo, uma por página), D4 e D9 (o modo Rápido corta de forma destrutiva e só com o detector estrito), D8 (girar o arquivo salvo no próprio arquivo), D12 (oito alças de retângulo), a seção 6.1 (giro de um retângulo), 6.3 (os dois detectores e onde cada um roda) e 6.9 (módulo de geometria). **Complementa** [Documento de várias páginas](2026-10-17-documento-de-varias-paginas.md) e [Ajustes: girar, resoluções, corte](2026-10-17-ajustes-rotacao-resolucoes-corte.md) (a decisão A2, "recodificar a 95", é substituída pela qualidade configurável, D23) · **Baseline:** 3263 testes passando (17 pulados), `ruff` limpo, 28 commits locais (nada enviado ao GitHub).

## 1. O que você pediu (md.md, linhas 39 a 56) e o que as medições mudaram

Suas respostas e observações, uma a uma:

1. **Detector mais amplo também no modo Rápido, com ajuste possível.** "O modo rápido é semelhante ao modo documento, mas é uma página apenas." Hoje o modo Rápido corta direto no arquivo e só com o detector estrito; nem a moldura nem o **Ampliar** existem ali.
2. **Moldura mais flexível**, para fotos na diagonal (o cartão a uns 30° que você mandou): "hoje está fixo retangular".
3. **Até 2 fotos de uma vez**: digitalizar, recortar e emoldurar até 2 fotos numa digitalização, para ir mais rápido.
4. **Qualidade final configurável**: o recorte regrava o JPEG a 95 e o arquivo fica de 2 a 4 vezes maior.
5. **Tirar a dica** "Use para fotos e folhas menores que o vidro…" da caixa Ajustes (a caixa **Cortar automaticamente e remover o fundo** fica).
6. Mantidos: moldura 1 a 2% larga ("excelente decisão"), mestres intactos, giro só no ícone da página (tile do documento e painel do modo Rápido), **Resolução** e **Cor** sem predefinição, Salvar (Enter), regras de 409, rascunho à prova de queda, 1200 dpi seguro, as oito resoluções.

O que o código e as medições mostram, e que moldaram o desenho:

- **Hoje a moldura é um retângulo alinhado aos eixos** (`PageCrop(left, top, right, bottom)`), no manifesto, na API, no render (`Image.crop`) e no JavaScript (oito alças). Uma foto torta só cabe num retângulo grande demais, com fundo branco nos cantos. A moldura precisa virar um quadrilátero (D14) e o render precisa "endireitar" a região (D17).
- **Você já escaneou a cena de aceitação de verdade.** Em `scratchpad/real-scans/` há agora três digitalizações com duas fotos sobre a tampa branca fechada (`photos-1-color-100.jpg`, `photos-2-color-300.jpg`, `photos-3-gray-150.jpg`; ver NOTES.md): a foto A, no alto, girada uns 30° e **de cabeça para baixo**; a foto B, embaixo, quase reta (−2,2°). O detector novo as acha (seção 3.2). A foto A mostra por que a moldura precisa ter o próprio "lado de cima" (D16): girar a página inteira para endireitar A viraria B de cabeça para baixo.
- **O JPEG do scanner é qualidade 50.** A primeira linha da tabela de quantização dos quatro JPEG reais é `16, 11, 10, 16`, a da qualidade 50. Regravar a 95 não recupera nada (o que o scanner jogou fora já foi), só engorda: 2,1 vezes. Medi o tamanho por qualidade (seção 3.4); a 90 o arquivo sai 1,7 vez maior, a 75 sai 1,3 vez e a 60 sai igual ao do scanner.
- **A detecção já custa 15 ms** (seção 3.2); rodar o detector amplo no modo Rápido não pesa. O que pesava era o risco: cortar errado de forma destrutiva. Com o mestre guardado (D19) o risco some, porque o corte passa a ser uma moldura que você ajusta.
- **O Pillow já endireita regiões**: `Image.transform(QUAD)` mapeia um quadrilátero para um retângulo em uma passada, e medi que pode ler direto da imagem inteira (seção 3.1). Nenhuma dependência nova (nada de numpy).

## 2. Decisões (tomadas pelo assistente; corrija se quiser)

As decisões D1 a D13 do outro documento continuam valendo, exceto onde a lista acima as substitui. Aqui a numeração segue em D14.

| # | Decisão | Por quê | Alternativa descartada |
|---|---|---|---|
| D14 | **A moldura é um quadrilátero convexo** (`PageCrop`): quatro cantos em frações (0 a 1) da página **como é exibida, depois do giro**, na ordem dos papéis `top_left`, `top_right`, `bottom_right`, `bottom_left`, no sentido horário da tela. Um retângulo alinhado aos eixos é o caso especial com `top_left` em cima à esquerda. Validação: finito, dentro da página, sentido horário, convexo, cada lado com pelo menos 2% (em frações), nenhum canto "achatado" (o triângulo do canto com menos de 5% da área). Todas as regras usam só frações (o lado mínimo também), então o domínio não precisa saber o tamanho da imagem em pixels. | Atende "foto na diagonal" sem inventar outro tipo de moldura; o retângulo de hoje é um caso dela. | Ângulo + centro + largura + altura (só retângulos girados; não permite o ajuste de um canto) |
| D15 | **Até 2 molduras por página (`MAXIMUM_CROPS_PER_PAGE = 2`)**, sempre guardadas em **ordem de leitura**: se os intervalos verticais das duas ocupam a mesma faixa (sobreposição maior que 50% da menor altura), a da esquerda vem primeiro; senão, a de cima. Sem moldura, a página vale como uma só página inteira (`output_count = max(1, quantidade de molduras)`). Uma moldura que cobre a página inteira, sem giro de papéis, vira "sem moldura". | A ordem estável faz o "1" e o "2" da tela serem sempre os mesmos e dá a ordem das páginas do PDF e dos arquivos do modo Rápido. Na cena real, A (no alto) é 1 e B é 2. | Deixar o usuário ordenar (mais um controle para o mesmo resultado) |
| D16 | **O giro da página gira os cantos e desloca os papéis em um; "Girar moldura" desloca só os papéis.** A página girada 90° à direita leva o ponto `(x, y)` a `(1 − y, x)` e o papel de cada canto avança: o novo `top_left` é o antigo `bottom_left` (o antigo lado esquerdo passa a ser o de cima). "Girar moldura ↻" (por moldura, no editor) faz só o deslocamento dos papéis: a foto recortada sai girada 90° à direita, sem mexer na posição da moldura. Os vetores são compartilhados entre Python e JavaScript (6.1). Não há regra de "lado mais próximo da horizontal" no domínio (ela dependeria da proporção da página): só o detector, que conhece os pixels, a usa para dar os papéis na primeira vez. | O mesmo cartão a 31° saiu de lado quando o lado "de cima" foi o mais horizontal; a foto A da cena real sai de cabeça para baixo. Com a moldura carregando o próprio "lado de cima", cada foto é endireitada sozinha. O giro da página continua girando a saída, como hoje. | Escolher o lado de cima pelo ângulo no domínio (erra de 35° a 45° em página não quadrada) |
| D17 | **Renderização por moldura com `Image.transform(QUAD)` lendo a imagem inteira do mestre**, sem recortar uma sub-imagem antes. O tamanho da saída é a média dos lados opostos em pixels do mestre; a densidade do JFIF continua a do mestre; a qualidade vem da configuração (D23). Moldura **retangular** (lados paralelos aos da página, com qualquer papel de canto) usa o caminho de hoje (`crop` da caixa e `transpose`), com os mesmos bytes de hoje. Cada moldura é renderizada sozinha (o mestre é decodificado uma vez por moldura): no máximo uma imagem decodificada de cada vez. Nas molduras não retangulares o giro da página entra no mesmo `transform` (os cantos voltam à orientação do mestre sem mudar de papel), sem `transpose` separado. | Medido: ler direto da imagem inteira dá o mesmo tempo e **menos** memória do que recortar a caixa antes (734 contra 844 MB em cor; 3.1). Um passo só para giro, moldura e endireitamento. | Recortar a caixa envolvente antes (mais memória e mais código); `PERSPECTIVE` com solução de sistema 8×8 (QUAD é exato para retângulos girados e paralelogramos, e num scanner plano a distorção de perspectiva não existe) |
| D18 | **Detecção em duas camadas, nos dois modos.** (1) Detector de regiões (novo, `photo_region_detection.py`): se a borda da prévia é um fundo uniforme, acha até 2 regiões como retângulos girados de área mínima. (2) Se não achar nenhuma (ou se a borda não é uniforme, como o livro com a tampa aberta), roda o detector por lado de hoje (`paper_edge_detection.py`, inalterado), que dá uma moldura retangular. O detector estrito `detect_paper_region` sai: o de regiões o contém (mesmas regras de segurança, 20 cenas antigas com o mesmo resultado, 3.2). `detect_crop_to_apply` e `detect_crop_to_suggest` viram um só método, `detect_crops`. | Uma regra só nos dois modos, porque o corte deixou de ser destrutivo (D19); o livro continua enquadrado. | Dois detectores por modo (a diferença só existia por causa do corte sem volta) |
| D19 | **O modo Rápido guarda o mestre e a moldura da última digitalização** (um espaço, "o espaço da última digitalização", substituído pela digitalização seguinte). A digitalização grava logo os arquivos de saída: com **Cortar automaticamente** ligado, cada moldura detectada vira um arquivo; desligado, a imagem inteira. O painel ganha a miniatura com as molduras sobrepostas, **Girar ↻** e **Ampliar** (o mesmo editor do modo Documento). **Aplicar** regrava os arquivos a partir do mestre. O giro do último arquivo passa a ser metadado mais regravação (PDF e JPG), e `ScanContentRotator` sai. | É o pedido 1. Mantém "mestre não destrutivo" nos dois modos e uma só regra de qualidade. | Editar o arquivo de saída (sem o mestre, cada ajuste degrada) |
| D20 | **Espaço da última digitalização:** `<pasta de dados>/quick-scan/` com `manifest.json`, `master-<scan_identifier>.jpg` e `thumbnail-<scan_identifier>.jpg` (`scan_identifier` = 16 hexadecimais da digitalização). Gravação atômica de cada arquivo (`AtomicFileWriter.write_new_file` e `replace_file`); o manifesto é o ponto de confirmação. Ordem: mestre e miniatura → arquivos de saída → manifesto → apagar os arquivos do espaço anterior. Na partida, a recuperação carrega o manifesto, apaga o que ele não cita (inclusive `.part`), **restaura o painel da última digitalização** (se ao menos um arquivo de saída ainda existe) e, se o manifesto diz `render_pending`, regrava as saídas a partir do mestre. Se o disco do Mac não aceitar o mestre, a digitalização **não falha**: os arquivos saem normalmente e o painel mostra a miniatura sem **Ampliar** (`is_editable: false`). | Segurança contra queda também aqui, sem nenhum caso de "arquivo de saída com bytes pela metade". Restaurar o painel é a consequência natural de o espaço sobreviver à reinicialização. | Manter só em memória (some numa queda, exatamente quando se quer ajustar); falhar a digitalização por causa do mestre |
| D21 | **Aplicar no modo Rápido:** o servidor grava o manifesto novo com `render_pending`, regrava cada arquivo de saída existente no mesmo nome (`replace_file`), **cria** arquivos novos para molduras a mais (próximos números livres da sequência do dia, formato do arquivo da digitalização) e **apaga** os arquivos de molduras a menos, mas só se o arquivo ainda está como o aplicativo o gravou (mesmo tamanho e mesma data de modificação, guardados no manifesto); senão o mantém e avisa. Só apaga arquivos desta digitalização. A resposta lista os nomes apagados e os mantidos, e a tela diz. Arquivo de saída ausente: `last_scan_file_missing` (409), nada muda. | O pedido diz que removida a moldura só se apagam arquivos que a própria digitalização criou. A guarda de tamanho e data evita apagar o que você editou depois. | Apagar sem conferir; ou nunca apagar (sobra arquivo que ninguém pediu) |
| D22 | **API do último arquivo e do documento:** `crops` (lista de 0 a 2 quadriláteros) substitui `crop`; rotas `PUT …/crops`, `POST …/crops/detect`, mais as do último arquivo (seção 5.4). `GET /api/state` ganha o objeto `last_result` novo (vários arquivos, giro, molduras, `scan_identifier`, `is_editable`). A visão ampliada do último arquivo é `GET /api/scans/last/preview?scan_identifier=…&rotation_degrees=…` (imutável por endereço). `last_result_revision` sobe a cada digitalização e a cada edição que muda algo. | Mesmo vocabulário nos dois modos; o editor troca só os endereços (D25). | Rotas de `crop` no singular com lista dentro (o nome mentiria) |
| D23 | **Qualidade do JPEG configurável:** `jpeg_quality`, inteiro de 50 a 100, padrão **90**, em `ImageAdjustment` (junto de `auto_crop`), nas configurações (`PUT /api/settings`, 422 `invalid_settings` fora da faixa ou se não é inteiro), gravado em `settings.json` (arquivo antigo carrega com 90; valor inválido vira 90 com aviso). Vale para **toda** regravação (corte, endireitamento e giro, nos dois modos); o mestre sem corte e sem giro mantém os bytes do scanner. Miniaturas (480 e 1600 px) não mudam. O servidor lê a configuração **salva** na hora de cada regravação (Salvar, Aplicar, Girar, Detectar), em vez de receber o valor no corpo: uma só fonte, nada de aba desatualizada. O controle da página grava a configuração ao mudar, como os outros. A estimativa de espaço usa um fator por qualidade (2 até 90, 3 até 97, 4 acima) no lugar do "2" fixo. | Pedido 4. O fator vem da tabela da seção 3.4. | Mandar o valor em cada pedido de regravação (duas fontes para o mesmo número) |
| D24 | **A dica da caixa de corte sai**; ficam o rótulo "Cortar automaticamente e remover o fundo" e a caixa. O novo controle de qualidade tem **uma** linha de dica ("Vale quando a imagem é cortada ou girada."). | Pedido 5. | Dica nova longa |
| D25 | **Um só editor para os dois modos.** `PageFrameEditor` e o módulo de geometria servem aos dois; quem abre passa um **alvo de edição** (`editor_target`) com o título, o endereço da visão ampliada, o corpo atual e as três requisições (girar, aplicar molduras, detectar). O `DocumentPanel` e o `ScanPage` constroem cada um o seu. Nada de cópia do editor. | "Reutilize o código do editor e da geometria; não faça um fork." | Um editor para cada modo |
| D26 | **O editor passa a ter** quatro alças de canto livres (movem só o canto), quatro alças de lado (movem o lado ao longo da normal dele: num retângulo girado, é exatamente redimensionar), mover a moldura inteira, uma alça de **girar a moldura** (gira em torno do centro; a moldura encolhe o mínimo para continuar dentro da página), **Adicionar moldura** (no máximo 2), **Remover moldura**, **Girar moldura ↻** (D16), **Detectar automaticamente** (da página inteira), **Sem corte** (remove todas), **Girar ↻** da página, **Cancelar** e **Aplicar**. Duas molduras: a ativa tem alças; a outra é um contorno com um botão "Selecionar moldura N". Cores e rótulos diferentes (D28). Teclado: Tab entre alças, setas e Shift+setas. | Pedido 2 e 3. | Só os quatro cantos (fazer um retângulo girado exigiria mexer nos quatro) |
| D27 | **Modo Documento com 2 molduras:** a página gera **2 páginas no PDF** (ordem de leitura), cada uma com a densidade do mestre. `DocumentFinalizationResult.page_count` passa a ser o número de páginas do PDF (`DocumentDraft.output_page_count`). A reordenação continua por páginas inteiras. | Pedido 3. | Uma página de PDF com as duas fotos (não é o que se quer ao dividir o lote) |
| D28 | **Cores e rótulos:** moldura 1 em azul, linha contínua; moldura 2 em laranja, tracejada; um selo "1" ou "2" no primeiro canto; o tile diz "2 molduras" em texto. As cores são variáveis do tema (claro e escuro). | Nunca só a cor: o formato da linha e o número também diferenciam. | Duas cores sem outro sinal |
| D29 | **Simulador:** `DIGITALIZADORA_SIMULATOR_SCENE` (`photos_one` e `photos_two`) compõe 1 ou 2 fotos **sintéticas** giradas sobre a tampa branca, com um marcador no canto de cima da foto para conferir a orientação do recorte. A cena do livro continua coberta por fixtures. | Testes de integração e a conferência no Chrome sem a impressora. | Usar a imagem de pessoas (nunca vai para o repositório) |
| D30 | **Compatibilidade.** `settings.json` antigo carrega (sem `jpeg_quality`: 90). Manifesto de rascunho antigo (`crop` com quatro frações) carrega: o retângulo vira um `PageCrop` e a lista de uma moldura; o `format_version` continua 1; o programa grava só `crops`. Clientes antigos (aba aberta) que não conhecem `crops` não veem molduras até recarregar a página; nada quebra. | Nenhum dado do usuário se perde. | Subir o `format_version` (um programa antigo passaria a recusar o rascunho inteiro) |

**Desvios do que a tarefa sugeria, com a justificativa:**

- **Sem recortar a caixa envolvente antes do `transform`** (D17): medi os dois e ler da imagem inteira usa menos memória (3.1).
- **"Detectar automaticamente" e "Sem corte" são da página, não de cada moldura** (D26). Uma detecção acha as duas fotos de uma vez; dizer qual achado vai para qual moldura exigiria um casamento por sobreposição que só atrapalha. "Remover moldura" e "Adicionar moldura" fazem o trabalho por moldura.
- **`QUAD` do Pillow, não perspectiva** (D17): mapeamento bilinear, exato para retângulos girados e paralelogramos; num scanner plano não há distorção de perspectiva, e um quadrilátero qualquer vira um retângulo plausível.
- **Sem "regra do lado mais horizontal" no domínio** (D16): os papéis dos cantos fazem parte do dado; só o detector os atribui.
- **O painel do modo Rápido é restaurado depois de reiniciar** (D20), o que muda a frase "só vale para a última digitalização desta execução" do outro documento.
- **A qualidade não viaja no corpo** (D23), pelo motivo na tabela.

## 3. Medições (protótipos descartáveis em `scratchpad/designer2/`)

Máquina: Mac arm64, 8 núcleos, 16 GB, Python 3.12, Pillow 13.0.0. Scripts: `p1_transform.py`, `p1_worst.py` (render), `p2_detect.py` a `p8_gap.py` (detecção), `p9_quad_domain.py` e `p10_vectors.py` (vetores), `p3_unwarp_card.py` e `p7_unwarp_real.py` (conferência visual). Nenhum vai para o repositório.

### 3.1 `Image.transform(QUAD)` em 10200 × 14032 (143 MP, JPEG de 37 MB, ruído de propósito)

| Caso | Saída | Tempo | Pico de memória |
|---|---|---|---|
| Só decodificar, cor | n/a | 0,41 s | 592 MB |
| Retângulo girado 25°, cor, **direto da imagem inteira** | 5610 × 6314 (35 MP) | 1,50 s (transform 1,41 s, JPEG 0,10 s) | **734 MB** |
| O mesmo, **recortando a caixa envolvente antes** | 35 MP | 1,58 s | 844 MB |
| O mesmo, cinza, direto / com caixa | 35 MP | 0,80 s / 0,80 s | **206 MB** / 236 MB |
| Pior caso: moldura de 90% da página a 4°, cor, BICUBIC | 9180 × 12629 (116 MP) | 3,67 s + 0,29 s de JPEG | 1054 MB |
| O mesmo com BILINEAR | 116 MP | 1,91 s + 0,26 s | 1054 MB |
| O mesmo, cinza, BICUBIC | 116 MP | 1,65 s + 0,23 s | 302 MB |
| Referência de hoje: `crop` + `transpose` de 90 MP, cor / cinza | 90 MP | 0,76 s / 0,54 s | 949 MB / 276 MB |

Conclusões: direto da imagem inteira vale; o pior caso (1,05 GB) é o do giro de hoje (0,95 GB); BICUBIC fica (3,7 s numa moldura gigante a 1200 dpi, que é o caso raro). Duas molduras são renderizadas em sequência, sem somar o pico. Conferido: uma moldura do tamanho da página reproduz a imagem sem diferença (máximo 0), e uma moldura que encosta na borda do vidro não deixa pixel preto de amostragem fora da imagem (0 em 54000).

### 3.2 Detecção de regiões em Python puro (prévia de 400 px)

Etapas medidas numa prévia de 291 × 400 (filtro de mediana 7): máscara de primeiro plano e filtros 12 ms, **rotulagem por corridas de linha com união-busca 0,9 ms**, casco convexo e retângulo de área mínima por aresta do casco 0,9 ms, guardas 0,5 ms: **14 a 15 ms no total**; com o filtro 5 (o escolhido) **10 a 11 ms**, com o filtro 3 cerca de 7 ms. A prévia reduzida da imagem custa 2 ms (150 dpi), 12 ms (100 dpi), 7 ms (300 dpi) e **286 ms a 1200 dpi com 71 MB de pico**.

Cena real de aceitação (a que você escaneou, mesma resposta nos três arquivos, frações da imagem; ordem de leitura):

| Região | Ângulo do lado de cima | Cantos `top_left`, `top_right`, `bottom_right`, `bottom_left` (photos-2-color-300.jpg) | Preenchimento do retângulo |
|---|---|---|---|
| 1 (foto A, no alto) | −30,4° | (0,039, 0,280) (0,650, 0,019) (0,894, 0,321) (0,282, 0,582) | 0,98 |
| 2 (foto B, embaixo) | −2,2° | (0,171, 0,604) (0,878, 0,584) (0,896, 0,931) (0,189, 0,951) | 0,98 |

Conferido contra a imagem (A vai de 0,04 a 0,90 de largura, B de 0,17 a 0,90) e **endireitado** com `transform(QUAD)`: as duas saem retas (1878 × 1297 e 1875 × 1289 px a 300 dpi, 73 a 82 ms cada), com uma borda de uns 35 px (a margem de 1%). A foto A sai de cabeça para baixo, porque assim estava no vidro (D16).

Cartão a 31° (3.png): mesma detecção na imagem sozinha (`ângulo 31,1°`, saída endireitada de 345 × 507 px, retrato) e numa cena composta de 1275 × 1754 com a verdade conhecida: erro máximo de canto **3,5 px** de 1275 (2 fotos, 31° e −12°: 3,5 e 7,3 px).

Cenas sintéticas de 1275 × 1754 (todas a 13 a 16 ms; "gap" é o vão entre as fotos; o erro é o maior desvio de canto):

| Cena | Resultado |
|---|---|
| 1 foto reta / 1 cartão a 31° | 1 região, erro 3,2 / 3,5 px |
| 2 fotos a 31° e −12°; lado a lado retas; empilhadas a ±5° | 2 regiões, 3,5 a 7,3 px |
| 3 fotos | as 2 maiores (a terceira é ignorada e contada) |
| Tampa em branco; página branca com linha impressa fina; polaroide (borda branca sobre tampa branca) | nenhuma região; a polaroide só de branco **não** é achada, e a com foto dentro acha só a foto (perde a borda branca, até 140 px por canto; esperado, é branco sobre branco) |
| Foto de 2% da página; foto de 1,5% (etiqueta) ao lado de uma foto grande | a pequena é ignorada (mínimo de 3%) |
| Tampa escura com folha branca reta e a 7°; capa escura de nível parecido | acha a folha; a capa quase igual à tampa (diferença menor que 20) não vira região |
| Foto encostada na borda do vidro | achada (toca 2 lados no máximo) |

**Vão mínimo entre duas fotos** (150 dpi, duas fotos retas de 420 × 560 px) conforme o filtro de mediana: filtro 7 separa a partir de **3,4 mm**, filtro 5 a partir de **2,7 mm**, filtro 3 a partir de 2,0 mm; abaixo de 1,4 mm as duas viram uma só (a moldura envolve as duas e você pode ajustar). As 20 cenas do detector estrito que os testes de hoje usam dão o **mesmo resultado** com os filtros 3, 5 e 7; as digitalizações reais dão o mesmo com 3 e 5. Escolhi **5** (10 a 11 ms).

O livro (tampa aberta, 4 digitalizações) **não** passa no teste de "borda é fundo uniforme": o detector de regiões fica de fora e o por lado dá `(0,137, 0,125, 0,914, 0,915)`, `(0,12, 0,125, 0,914, 0,917)`, `(0,134, 0,125, 0,907, 0,915)` e `(0,107, 0,125, 0,911, 0,915)`, como hoje.

### 3.3 Combinação com o detector por lado

**Revisado (15):** o detector por lado só roda quando o detector de regiões **não tem voto**, isto é, quando a borda não é uma tampa uniforme (o livro com a tampa aberta). Numa tampa uniforme a resposta do detector de regiões é final, mesmo vazia: então tampa em branco, página com linha fina, polaroide completa e um grupo de fotos que as guardas recusam dão **nenhuma moldura** e a imagem fica inteira. (A primeira versão deste parágrafo dizia que o detector por lado também não achava nada nessas cenas; isso era falso para uma foto que toca 3 lados e para duas fotos sobrepostas, onde ele devolvia um retângulo que cortava a foto.) As cenas de duas fotos, resolvidas pelo detector de regiões, nunca chegam ao por lado.

### 3.4 Tamanho do JPEG regravado em função da qualidade

Razão entre o tamanho do arquivo regravado (imagem inteira, mesma subamostragem) e o do scanner, nos JPEG reais:

| Arquivo | do scanner | 100 | 95 | **90** | 85 | 75 | 60 |
|---|---|---|---|---|---|---|---|
| 3-color-300.jpg | 666 KB | 3,21 | 2,13 | **1,69** | 1,42 | 1,25 | 1,03 |
| photos-2-color-300.jpg | 509 KB | 3,33 | 2,10 | **1,70** | 1,42 | 1,29 | 1,03 |
| photos-3-gray-150.jpg | 159 KB | 3,03 | 2,16 | **1,75** | 1,44 | 1,30 | 1,02 |
| 2-gray-100.jpg | 85 KB | 3,21 | 2,23 | **1,75** | 1,45 | 1,27 | 1,01 |

Daí o fator de espaço por qualidade (D23) e a dica de que 60 a 75 é o que o scanner tem de verdade. O padrão fica em 90, como foi sugerido.

## 4. Contratos

Todas as assinaturas respeitam: no máximo 3 parâmetros por método e construtor (sem `self`; campos de dataclass não contam), nenhum parâmetro booleano, nomes sem abreviações, injeção por construtor (só `composition_root.py` instancia concretos), camadas `controllers → services → domain ← repositories/infrastructure`, módulos Python em snake_case e arquivos que não são Python em kebab-case.

### 4.1 `domain/`

```python
# pixel_region.py   (ACRÉSCIMO)
@dataclass(frozen=True)
class PixelCorner:
    x: float
    y: float

# page_crop.py   (MUDA: o retângulo vira quadrilátero; o nome PageCrop fica)
MINIMUM_CROP_EDGE_SHARE = 0.02
MINIMUM_CORNER_TRIANGLE_SHARE = 0.05
CROP_PRECISION_DIGITS = 6
CROP_TOLERANCE = 1e-9

@dataclass(frozen=True)
class CropCorner:
    x: float
    y: float
    def turned_clockwise(self) -> "CropCorner": ...          # (x, y) -> (1 - y, x)
    def turned_counterclockwise(self) -> "CropCorner": ...   # (x, y) -> (y, 1 - x)

@dataclass(frozen=True)
class RectangleEdges:        # o antigo PageCrop: left, top, right, bottom (frações)
    left: float
    top: float
    right: float
    bottom: float

@dataclass(frozen=True)
class PageCrop:
    """Four corners in fractions (0..1) of the page as displayed (after the rotation), clockwise on the screen.

    The role of a corner (top_left ...) says where that corner goes in the cropped image: the edge from top_left to
    top_right is its top, so the roles also fix how the cropped photo is turned."""
    top_left: CropCorner
    top_right: CropCorner
    bottom_right: CropCorner
    bottom_left: CropCorner

    def __post_init__(self) -> None: ...   # InvalidCropError: not finite, outside 0..1, not clockwise or empty,
                                           # not convex, an edge under 2%, a corner triangle under 5% of the area
    @classmethod
    def from_rectangle(cls, edges: RectangleEdges) -> "PageCrop": ...
    @classmethod
    def rounded(cls, corners: Sequence[CropCorner]) -> "PageCrop": ...   # exactly 4, in role order; rounds to 6 digits, then validates
    @property
    def corners(self) -> tuple[CropCorner, CropCorner, CropCorner, CropCorner]: ...
    @property
    def is_rectangle(self) -> bool: ...           # the four edges are parallel to the page edges (any roles)
    @property
    def rotation_to_upright(self) -> PageRotation: ...   # rectangle only: how to turn the cut-out so that top_left is at its upper left
    @property
    def covers_whole_page(self) -> bool: ...      # a rectangle, 0, 0, 1, 1, with rotation_to_upright NONE
    @property
    def bounding_edges(self) -> RectangleEdges: ...
    def turned_clockwise(self) -> "PageCrop": ...              # the page turns: points (x, y) -> (1 - y, x), roles advance (6.1)
    def turned_counterclockwise(self) -> "PageCrop": ...       # the inverse
    def with_output_turned_clockwise(self) -> "PageCrop": ...  # roles only: top_left <- bottom_left, ... (6.1)
    def seen_on_master(self, quarter_turns: int) -> "PageCrop": ...   # points turned back by the page rotation, roles kept
    def to_pixel_region(self, image_size: tuple[int, int]) -> PixelRegion: ...        # of bounding_edges, floor and ceil as before
    def to_pixel_corners(self, image_size: tuple[int, int]) -> tuple[PixelCorner, PixelCorner, PixelCorner, PixelCorner]: ...
    def output_size_in_pixels(self, image_size: tuple[int, int]) -> tuple[int, int]: ...  # mean of opposite edges, at least 1

# page_framing.py   (MUDA)
MAXIMUM_CROPS_PER_PAGE = 2

@dataclass(frozen=True)
class PageFraming:
    rotation: PageRotation = PageRotation.NONE
    crops: tuple[PageCrop, ...] = ()           # 0 to 2, in reading order (D15); InvalidCropError for more than 2

    @property
    def needs_rendering(self) -> bool: ...      # rotation is not NONE or there is a crop
    @property
    def output_count(self) -> int: ...          # max(1, len(crops)): PDF pages (document) or files (quick) it produces
    def turned_clockwise(self) -> "PageFraming": ...                      # rotation +90 and every crop turned with the page
    def with_crops(self, crops: Sequence[PageCrop]) -> "PageFraming": ... # drops the crops that cover the whole page, orders by reading order, keeps at most 2
    def crops_on_master(self) -> tuple[PageCrop, ...]: ...                # crop.seen_on_master(quarter turns of the rotation)
    def crops_from_master(self, master_crops: Sequence[PageCrop]) -> tuple[PageCrop, ...]: ...  # found on the stored JPEG, shown turned
def put_in_reading_order(crops: Sequence[PageCrop]) -> tuple[PageCrop, ...]: ...   # D15

# image_adjustment.py   (MUDA)
MINIMUM_JPEG_QUALITY = 50
MAXIMUM_JPEG_QUALITY = 100
DEFAULT_JPEG_QUALITY = 90

@dataclass(frozen=True)
class ImageAdjustment:
    auto_crop: bool = False
    jpeg_quality: int = DEFAULT_JPEG_QUALITY   # InvalidSettingsError when not an int (a bool is not) from 50 to 100
    @property
    def is_active(self) -> bool: ...           # auto_crop only: the quality alone changes nothing

def rendered_size_factor(jpeg_quality: int) -> int: ...   # 2 up to 90, 3 up to 97, 4 above (3.4)

# document_draft.py   (MUDA)
#   DocumentDraft: NOVO output_page_count -> int (sum of framing.output_count)
#   DocumentDraft: estimated_document_size_in_bytes (propriedade) vira estimate_document_size_in_bytes(self, jpeg_quality: int) -> int
#   (size x rendered_size_factor(jpeg_quality) for the pages that need rendering); sai RENDERED_PAGE_SIZE_FACTOR
#   DocumentFinalizationResult.page_count passa a ser output_page_count (D27)

# last_scan.py   (NOVO)
@dataclass(frozen=True)
class SavedScanFile:
    file_name: str                    # simple name inside output_folder
    size_in_bytes: int
    modified_at_nanoseconds: int      # what the application saw right after writing (the guard of D21)

@dataclass(frozen=True)
class LastScan:
    """The last quick scan: its files in the output folder and the framing the files were made with."""
    scan_identifier: str              # 16 hexadecimal digits, new with every scan
    scanned_at: datetime
    output_folder: Path
    output_format: OutputFormat
    saved_files: tuple[SavedScanFile, ...]     # one per output, in frame order
    framing: PageFraming = UNFRAMED
    is_editable: bool = True                   # False when the master could not be kept (D20)
    @property
    def total_size_in_bytes(self) -> int: ...
    def saved_file_path(self, saved_file: SavedScanFile) -> Path: ...
    def with_framing(self, framing: PageFraming) -> "LastScan": ...
    def with_saved_files(self, saved_files: Sequence[SavedScanFile]) -> "LastScan": ...

@dataclass(frozen=True)
class QuickScanSlot:
    last_scan: LastScan
    dots_per_inch: int
    color_mode: ColorMode
    render_pending: bool = False               # a re-render started and has not been confirmed (D20, D21)

@dataclass(frozen=True)
class QuickScanMasterFiles:
    scan_identifier: str
    master_jpeg: bytes
    thumbnail_jpeg: bytes

# stored_scan.py   (MUDA): StoredScan(last_scan: LastScan, thumbnail_jpeg: bytes)
# scan_progress.py (MUDA): ScanProgressSnapshot.last_result: ScanResult | None  ->  last_scan: LastScan | None
#                          last_result_revision continua (sobe a cada digitalização e a cada edição que muda algo)
# encoded_scan.py  (MUDA): EncodedScan(content, output_format, created_at); perde thumbnail_jpeg
# scan_request.py  (sem mudança; ImageAdjustment carrega a qualidade)

# errors.py   (ACRÉSCIMO)
# LastScanNotEditableError(DigitalizadoraError)  code = "last_scan_not_editable"   (409)
# LastScanBusyError(DigitalizadoraError)         code = "last_scan_busy"           (409)
# InvalidCropError ganha o caso "mais de 2 molduras"; InvalidSettingsError cobre jpeg_quality

# ports.py   (MUDA)
class ScanOutputRepository(Protocol):
    ...   # output_folder, ensure_output_folder_ready, save, save_document, replace_saved_scan: como estão
    def describe_saved_scan(self, scan_path: Path) -> SavedScanFile | None: ...   # size and modification time; None when gone
    def delete_saved_scan(self, scan_path: Path) -> None: ...                      # a file that is gone is not an error
    # SAI read_saved_scan: o mestre substitui a releitura do arquivo salvo

class QuickScanSlotRepository(Protocol):
    def storage_folder(self) -> Path: ...
    def ensure_storage_folder_ready(self) -> None: ...
    def write_master_files(self, master_files: QuickScanMasterFiles) -> None: ...   # master, then thumbnail; each atomic
    def master_file_path(self, scan_identifier: str) -> Path: ...
    def read_thumbnail(self, scan_identifier: str) -> bytes | None: ...
    def load(self) -> QuickScanSlot | None: ...     # None: no slot, an unreadable manifest (logged and set aside) or a missing master
    def commit(self, slot: QuickScanSlot) -> None: ...     # the manifest (replace_file), then the files of every other scan are deleted
    def delete_leftovers(self, kept_scan_identifier: str | None) -> None: ...   # files the manifest does not cite, and .part files
    def discard(self) -> None: ...
```

### 4.2 `repositories/`

```python
# document_manifest_codec.py   (MUDA; format_version continua 1)
CROPS_KEY = "crops"
LEGACY_CROP_KEY = "crop"
CROP_CORNER_KEYS = ("top_left", "top_right", "bottom_right", "bottom_left")
# encode: cada página ganha "rotation_degrees" e "crops" (lista de 0 a 2 objetos com os quatro cantos {"x", "y"}); sai "crop".
# decode: "crops" presente e lista -> cada item é lido; um item inválido é descartado com aviso (o resto fica),
#         mais de 2 itens: os 2 primeiros com aviso; "crops" ausente e "crop" presente (manifesto antigo) ->
#         PageCrop.from_rectangle(RectangleEdges(...)) numa lista de um item; nenhuma das chaves: sem moldura.
#         Nada disso torna o manifesto ilegível (mesma regra de 7 do outro documento).

# file_system_quick_scan_slot_repository.py   (NOVO; implementa QuickScanSlotRepository)
class FileSystemQuickScanSlotRepository:
    def __init__(self, slot_folder: Path, file_writer: AtomicFileWriter, clock: Clock) -> None: ...
# manifest.json (7.1); master-<scan_identifier>.jpg e thumbnail-<scan_identifier>.jpg; commit: replace_file do manifesto, depois apaga os
# arquivos de outras digitalizações; load: lê o manifesto, confere que o mestre existe e tem o tamanho dele;
# delete_leftovers: apaga o que o manifesto não cita e os .part (padrão de nome do AtomicFileWriter).

# quick_scan_manifest_codec.py   (NOVO; funções puras, como document_manifest_codec.py)
def encode_quick_scan_manifest(slot: QuickScanSlot) -> bytes: ...
def decode_quick_scan_manifest(content: bytes) -> QuickScanSlot: ...      # estrito; UnreadableQuickScanError

# file_system_scan_output_repository.py   (MUDA)
#   NOVO describe_saved_scan(scan_path) e delete_saved_scan(scan_path); SAI read_saved_scan; replace_saved_scan fica
# json_application_settings_repository.py   (MUDA)
#   chave "jpeg_quality": lida com tolerância (ausente = 90; inválida = 90 com aviso, sem derrubar o resto) e gravada
```

### 4.3 `services/`

```python
# photo_region_detection.py   (NOVO; substitui paper_region_detection.py; só Pillow, funções puras sobre a prévia)
MINIMUM_PHOTO_AREA_SHARE = 0.03
MAXIMUM_PHOTOS = 2
REGION_NOISE_FILTER_SIZE = 5
MINIMUM_REGION_FILL_SHARE = 0.75
MAXIMUM_TOUCHED_SIDES = 2
MAXIMUM_RING_FOREGROUND_SHARE = 0.25
AXIS_SNAP_DEGREES = 1.5

@dataclass(frozen=True)
class PhotoRegion:
    corners: tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]
    # pixels of the preview, roles by the nearest-to-horizontal rule (6.3 step 8)
@dataclass(frozen=True)
class PhotoRegions:
    regions: tuple[PhotoRegion, ...]        # 0 to 2, reading order
    ignored_count: int                      # regions that passed every guard but were not among the 2 largest
def detect_photo_regions(preview: Image.Image) -> PhotoRegions | None: ...
#   None = the border is not a uniform background (the by-side detector takes over); PhotoRegions((), 0) = uniform and nothing found

# paper_edge_detection.py   (SEM MUDANÇA)

# page_crop_detection_service.py   (MUDA)
@dataclass(frozen=True)
class DetectedCrops:
    crops: tuple[PageCrop, ...]             # 0 to 2, reading order, in the orientation of the JPEG given
    ignored_region_count: int
class PageCropDetectionService:
    def detect_crops(self, jpeg_content: bytes) -> DetectedCrops: ...
# Prévia de no máximo 400 px (Image.draft + BOX), regiões e depois por lado (D18); frações da imagem inteira, margem de 1%
# (CROP_MARGIN_RATIO) já aplicada (6.3 passo 9); () quando nada é confiável. MemoryError -> ImageAdjustmentFailedError;
# imagem ilegível -> ScanFailedError (como hoje). SAEM detect_crop_to_apply e detect_crop_to_suggest.

# image_adjustment_service.py e master_jpeg_service.py   (SAEM: o corte deixou de ser destrutivo)

# jpeg_reencoding.py   (MUDA)
def read_encoding_options(source: Image.Image, jpeg_quality: int) -> dict[str, Any]: ...   # sai ADJUSTED_JPEG_QUALITY

# page_framing_renderer.py   (NOVO; é o DocumentPageRenderer, renomeado e generalizado; síncrono, só Pillow)
@dataclass(frozen=True)
class FrameRenderRequest:
    framing: PageFraming
    frame_index: int           # which crop; 0 when the page has none or one
    jpeg_quality: int
class PageFramingRenderer:
    def render_jpeg(self, master: BinaryIO, request: FrameRenderRequest) -> bytes: ...
# Sem giro e sem moldura: master.read() (os bytes do scanner). Só giro: transpose, como hoje. Moldura retangular (qualquer
# papel de canto): recorta a caixa na orientação do mestre e gira por rotation_to_upright, como hoje. Moldura não retangular:
# transform(QUAD) com os cantos na orientação do mestre (6.2). OSError, DecompressionBombError e ValueError -> ScanFailedError; MemoryError sobe.

# rendered_page_source.py   (MUDA): RenderedPageSource(page_renderer: PageFramingRenderer, page_file: Path, request: FrameRenderRequest)
#   read() abre o arquivo da página e chama render_jpeg; OSError -> ScanFailedError.

# document_pdf_assembler.py   (MUDA)
@dataclass(frozen=True)
class DocumentAssemblyInput:
    draft: DocumentDraft
    page_files: Sequence[Path]
    finalized_at: datetime
    jpeg_quality: int
# write_pdf monta uma RenderedPageSource por (página, índice de moldura) na ordem do rascunho: o PDF tem draft.output_page_count páginas.

# document_finalizer.py   (MUDA): ensure_capacity(draft, jpeg_quality) usa draft.estimate_document_size_in_bytes(jpeg_quality)

# document_draft_store.py   (MUDA)
#   set_page_crop(page_identifier, crop) -> set_page_crops(self, page_identifier: str, crops: Sequence[PageCrop]) -> DocumentDraft
#   (framing.with_crops; igual ao que há -> sem gravar e sem revisão)
#   CapturedPage.framing e o resto: como estão; describe_storage e ensure_capacity_for_page: sem mudança

# document_page_capture.py   (MUDA): com auto_crop, framing = PageFraming().with_crops(detect_crops(mestre).crops); falha da
#   detecção (DigitalizadoraError) = aviso no log e sem molduras. Usa ScanEncoder.encode_master (sem o artifício do NO_ADJUSTMENT).

# document_page_crop_detector.py   (MUDA)
@dataclass(frozen=True)
class CropDetectionResult:
    draft: DocumentDraft
    crops_detected: bool
    ignored_region_count: int
class DocumentPageCropDetector:
    def detect_for_page(self, page_identifier: str) -> CropDetectionResult: ...
# nada achado: as molduras NÃO mudam e a revisão não sobe; achado: substitui as molduras da página (já na orientação exibida).

# document_draft_service.py   (MUDA)
#   set_page_crop -> set_page_crops(self, page_identifier: str, crops: Sequence[PageCrop]) -> DocumentDraft
#   detect_page_crop -> detect_page_crops(self, page_identifier: str) -> CropDetectionResult
#   finalize(self, jpeg_quality: int) -> DocumentFinalizationResult          # o controlador passa settings.adjustment.jpeg_quality
#   describe_draft_storage(settings), read_thumbnail e read_preview: como estão

# scan_encoder.py   (MUDA)
@dataclass(frozen=True)
class EncodedMaster:
    jpeg_content: bytes          # the scanner JPEG with the density of the request, untouched otherwise
    thumbnail_jpeg: bytes        # 480 px, of the unturned master
@dataclass(frozen=True)
class OutputIdentity:
    created_at: datetime
    dots_per_inch: int
    output_format: OutputFormat
class ScanEncoder:
    def __init__(self, jpeg_resolution_service: JpegResolutionService, pdf_assembly_service: PdfAssemblyService,
                 thumbnail_service: ThumbnailService) -> None: ...
    def encode_master(self, scanned_image: ScannedImage, job: ScanJob) -> EncodedMaster: ...
    def wrap_output(self, output_jpeg: bytes, identity: OutputIdentity) -> EncodedScan: ...   # JPG as is; PDF with the fixed density layout

# quick_scan_output_renderer.py   (NOVO)
@dataclass(frozen=True)
class OutputsRequest:
    framing: PageFraming
    jpeg_quality: int
    identity: OutputIdentity
class QuickScanOutputRenderer:
    def __init__(self, page_framing_renderer: PageFramingRenderer, scan_encoder: ScanEncoder) -> None: ...
    def render_outputs(self, master: BinaryIO, request: OutputsRequest) -> tuple[EncodedScan, ...]: ...
# uma saída por moldura (ou uma, sem moldura), cada uma renderizada e embrulhada em sequência; master.seek(0) entre elas.

# scan_output_service.py   (MUDA; é o ScanDestination[StoredScan] do modo Rápido)
@dataclass(frozen=True)
class ScanOutputParts:
    scan_encoder: ScanEncoder
    output_renderer: QuickScanOutputRenderer
    crop_detection_service: PageCropDetectionService
    storage_guard_service: StorageGuardService
class ScanOutputService:
    def __init__(self, parts: ScanOutputParts, scan_output_repository: ScanOutputRepository,
                 slot_repository: QuickScanSlotRepository) -> None: ...
    def ensure_capacity(self, request: ScanRequest) -> None: ...     # pasta pronta, depois o espaço (fator por qualidade)
    def store(self, scanned_image: ScannedImage, job: ScanJob) -> StoredScan: ...    # 7.2

# last_scan_edit_service.py   (NOVO; substitui last_scan_rotation_service.py)
@dataclass(frozen=True)
class LastScanEditResult:
    last_scan: LastScan
    crops_detected: bool = False
    ignored_region_count: int = 0
    deleted_file_names: tuple[str, ...] = ()
    kept_file_names: tuple[str, ...] = ()
@dataclass(frozen=True)
class LastScanEditParts:
    slot_repository: QuickScanSlotRepository
    scan_output_repository: ScanOutputRepository
    output_renderer: QuickScanOutputRenderer
    crop_detection_service: PageCropDetectionService
class LastScanEditService:
    def __init__(self, progress_tracker: ScanProgressTracker, parts: LastScanEditParts) -> None: ...
    async def rotate_clockwise(self, jpeg_quality: int) -> LastScanEditResult: ...
    async def set_crops(self, crops: Sequence[PageCrop], jpeg_quality: int) -> LastScanEditResult: ...
    async def detect_crops(self, jpeg_quality: int) -> LastScanEditResult: ...
    def restore_after_start(self, jpeg_quality: int) -> None: ...      # 7.4; síncrono, antes de o servidor responder
# 7.3 e 7.5

# last_scan_view_service.py   (NOVO)
class LastScanViewService:
    def __init__(self, progress_tracker: ScanProgressTracker, slot_repository: QuickScanSlotRepository,
                 image_view_service: PageImageViewService) -> None: ...
    def read_thumbnail(self) -> bytes | None: ...                       # a miniatura sem giro, girada pelo giro da digitalização; 480 px
    def read_preview(self, scan_identifier: str, rotation: PageRotation) -> bytes: ...   # 1600 px do mestre, girado
# NoLastScanError quando não há digitalização ou o identificador não é o da atual; LastScanNotEditableError sem mestre.

# scan_progress_tracker.py   (MUDA)
#   last_thumbnail_jpeg() fica (a miniatura SEM giro); mark_completed(stored_scan) guarda last_scan;
#   replace_last_scan(self, expected_scan_identifier: str, replacement: StoredScan) -> None   (nova digitalização no meio vence)
#   NOVO restore_last_scan(self, stored_scan: StoredScan) -> None            (só na partida)
#   NOVO mark_last_scan_edit_started(self) / mark_last_scan_edit_ended(self)  (a trava de 7.5)
#   begin_scan levanta LastScanBusyError enquanto uma edição do último arquivo roda

# scan_service.py   (MUDA): is_scan_in_progress() é substituído por ensure_scan_can_start() (ScanAlreadyRunningError ou
#   LastScanBusyError); o ScanController usa ensure_scan_can_start() antes de aceitar o pedido.

# storage_guard_service.py   (MUDA): estimated_page_bytes(settings, adjustment) multiplica por rendered_size_factor(adjustment.jpeg_quality)
#   quando adjustment.is_active (o corte automático pode regravar a imagem).

# application_settings_service.py   (MUDA): SettingsUpdate.jpeg_quality: int | None = None (None mantém o salvo);
#   _resolve_adjustment cria ImageAdjustment(auto_crop, jpeg_quality); fora da faixa -> InvalidSettingsError.
# scan_content_rotator.py, last_scan_rotation_service.py   (SAEM)
```

### 4.4 `controllers/`

```python
# document_body.py: _describe_page ganha "crops" (lista de 0 a 2 de {"top_left": {"x","y"}, "top_right", "bottom_right", "bottom_left"})
#   no lugar de "crop"; build_document_summary_body: estimated_size_in_bytes continua o do scanner.
# document_controller.py   (MUDA; o construtor continua com 3 parâmetros)
class CropCornerRequestBody(BaseModel):     x: StrictInt | StrictFloat; y: StrictInt | StrictFloat
class PageCropRequestBody(BaseModel):       top_left: CropCornerRequestBody; top_right: ...; bottom_right: ...; bottom_left: ...
class PageCropsRequestBody(BaseModel):      crops: list[PageCropRequestBody] = Field(max_length=2)
# rotas: PUT .../crops (set_page_crops), POST .../crops/detect (detect_page_crops); saem PUT .../crop e POST .../crop/detect;
# DOCUMENT_ERROR_STATUSES ganha last_scan_busy (409); POST /api/document/finalize passa settings.adjustment.jpeg_quality. VALIDATION_ERROR_CODE_PATTERNS: o padrão de crop vira .../crops(/detect)?
# scan_result_body.py: describe_scan_result(result) -> describe_last_scan(last_scan: LastScan) (5.2)
# settings_body.py: ganha "jpeg_quality"; settings_controller.py: SettingsRequestBody.jpeg_quality: StrictInt | None = None
# last_scan_controller.py   (MUDA)
class LastScanController:
    def __init__(self, last_scan_edit_service: LastScanEditService, settings_service: ApplicationSettingsService,
                 error_message_catalog: ErrorMessageCatalog) -> None: ...
    def build_router(self) -> APIRouter: ...   # POST /api/scans/last/rotation, PUT .../crops, POST .../crops/detect
LAST_SCAN_ERROR_STATUSES: no_last_scan 404; scan_already_running, last_scan_busy, last_scan_file_missing, saved_scan_unreadable,
                          last_scan_not_editable 409; invalid_crop 422; insufficient_storage 507; output_folder_unavailable 503;
                          image_adjustment_failed 500
# preview_controller.py   (MUDA): PreviewController(last_scan_view_service: LastScanViewService): GET /api/scans/last/thumbnail
#   (no-store, como hoje, agora girada) e GET /api/scans/last/preview?scan_identifier=&rotation_degrees= (imutável)
# error_message_catalog.py: textos novos e mudados em 8.5
# state_controller.py: last_result vira describe_last_scan(...) ; application_factory.py: padrões de validação de /api/scans/last/...
```

### 4.5 Raiz de composição

`_SharedServices` ganha `page_framing_renderer`, `output_renderer`; sai `master_jpeg_service`; `ScanEncoder(JpegResolutionService(), PdfAssemblyService(), ThumbnailService())`. `ScanOutputService(ScanOutputParts(...), repositories.scan_output, repositories.quick_scan_slot)`; `DocumentPdfAssembler(PageFramingRenderer(), PdfAssemblyService())`; `LastScanEditService(progress_tracker, LastScanEditParts(...))`; `LastScanViewService`; `FileSystemQuickScanSlotRepository(data_directory / "quick-scan", file_writer, clock)` em `_Repositories`. Depois de `document_draft.recover_draft()`, `last_scan_edit.restore_after_start(settings.adjustment.jpeg_quality)` (nunca levanta: um espaço ilegível é guardado de lado e o servidor sobe). Nenhum outro módulo instancia concretos.

## 5. Manifesto, corpo e API

Todas as rotas têm o guarda de `Host`; as que escrevem, o cabeçalho `X-Requested-With`.

### 5.1 Manifesto do rascunho e migração

Cada página do `manifest.json` passa a ter, no lugar de `crop`:

```json
{ "page_identifier": "…", "scanned_at": "…", "dots_per_inch": 300, "color_mode": "color", "size_in_bytes": 682312,
  "rotation_degrees": 0,
  "crops": [
    { "top_left": {"x": 0.039, "y": 0.28}, "top_right": {"x": 0.65, "y": 0.019},
      "bottom_right": {"x": 0.894, "y": 0.321}, "bottom_left": {"x": 0.282, "y": 0.582} },
    { "top_left": {"x": 0.171, "y": 0.604}, "top_right": {"x": 0.878, "y": 0.584},
      "bottom_right": {"x": 0.896, "y": 0.931}, "bottom_left": {"x": 0.189, "y": 0.951} } ] }
```

Migração (leitura, `format_version` continua 1): `crops` presente = lista (item inválido descartado com aviso; mais de 2 = os 2 primeiros com aviso); `crops` ausente e `crop` com `left`, `top`, `right`, `bottom` válidos (manifesto antigo) = `[PageCrop.from_rectangle(RectangleEdges(left, top, right, bottom))]`, e a moldura da página inteira some, como hoje; nenhuma das chaves = `[]`. A escrita nunca grava `crop`. Um programa antigo lendo um manifesto novo ignora `crops` (perde só as molduras).

### 5.2 Corpos

`GET /api/document` e toda edição: cada página leva `"rotation_degrees"` e `"crops"` (lista de 0 a 2 com os quatro cantos, como acima, em frações da página já girada, 6 casas); o resto do corpo não muda, mas `last_finished_document.page_count` e a resposta de `POST /api/document/finalize` passam a contar as **páginas do PDF** (D27).

`GET /api/state`: o objeto `last_result` (ou `null`) passa a ser

```json
{ "scan_identifier": "9f3c…", "file_names": ["2026-10-18_00007.pdf", "2026-10-18_00008.pdf"],
  "output_folder": "/Users/pedro/Pictures/Digitalizadora", "output_format": "pdf",
  "total_size_in_bytes": 412345, "scanned_at": "2026-10-18T12:41:03-03:00",
  "rotation_degrees": 0, "crops": [ { "top_left": {"x": 0.04, "y": 0.28}, … } ], "is_editable": true }
```

mais `last_result_revision` (como já é). `GET /api/settings`, `settings` do estado: ganha `"jpeg_quality": 90`.

### 5.3 Rotas do documento

| Rota | Corpo | Resposta | Observação |
|---|---|---|---|
| `PUT /api/document/pages/{page_identifier}/crops` | `{"crops": []}` a `{"crops": [c1, c2]}` | `200` corpo do documento | valida cada moldura (`invalid_crop`, 422), no máximo 2 (422), guarda em ordem de leitura; igual ao que há = nada muda e a revisão não sobe; cada moldura que cobre a página inteira some |
| `POST /api/document/pages/{page_identifier}/crops/detect` | nenhum | `200` corpo do documento mais `"crops_detected": bool` e `"ignored_region_count": n` | roda `detect_crops` no mestre; achou = **substitui** as molduras da página (já na orientação exibida); não achou = nada muda |
| `POST /api/document/pages/{page_identifier}/rotation` | nenhum | `200` | como hoje; todas as molduras giram com a página (6.1) |
| `GET …/thumbnail?rotation_degrees=`, `GET …/preview?rotation_degrees=` | | JPEG | como hoje |
| `POST /api/document/finalize` | nenhum | `200` | usa `jpeg_quality` salvo; `page_count` = páginas do PDF |

Erros e status: os de 4.3 do outro documento, com `invalid_crop` (422) cobrindo valores, ordem dos cantos, convexidade, tamanho e "mais de 2". Desaparecem `PUT …/crop` e `POST …/crop/detect` (404).

### 5.4 Rotas do último arquivo (modo Rápido)

| Rota | Corpo | Resposta | Observação |
|---|---|---|---|
| `POST /api/scans/last/rotation` | nenhum | `200` `{"last_result": …, "deleted_file_names": [], "kept_file_names": []}` | `rotation_degrees` +90, as molduras giram junto, **todas** as saídas são regravadas a partir do mestre |
| `PUT /api/scans/last/crops` | `{"crops": [...]}` | `200`, mesmo formato | D21: regrava, cria e apaga; `crops` igual ao que há = nada muda (sem escrita, sem revisão) |
| `POST /api/scans/last/crops/detect` | nenhum | `200`, mesmo formato mais `"crops_detected"` e `"ignored_region_count"` | `detect_crops` no mestre; achou = como `PUT` com o achado |
| `GET /api/scans/last/preview?scan_identifier=…&rotation_degrees=…` | | JPEG de até 1600 px | do mestre, girado; `Cache-Control: private, max-age=31536000, immutable` (o endereço leva o identificador da digitalização) |
| `GET /api/scans/last/thumbnail?version=…` | | JPEG de 480 px | `no-store`, como hoje, agora girada pelo giro da digitalização |

| Situação | Código | Status |
|---|---|---|
| Nenhuma digitalização, ou `scan_identifier` que não é o da atual | `no_last_scan` | 404 |
| Digitalização em andamento (edições) | `scan_already_running` | 409 |
| Outra edição do último arquivo roda (ao iniciar uma digitalização) | `last_scan_busy` | 409 |
| Arquivo de saída apagado ou movido | `last_scan_file_missing` | 409 |
| O mestre sumiu ou não abre | `saved_scan_unreadable` | 409 |
| O mestre não foi guardado (D20) | `last_scan_not_editable` | 409 |
| Moldura inválida | `invalid_crop` | 422 |
| Pouco espaço ou pasta indisponível | `insufficient_storage` (507) · `output_folder_unavailable` (503) | |
| Sem memória para decodificar | `image_adjustment_failed` | 500 |

### 5.5 Revisão, cache e a regra de 409

- `last_result_revision` sobe a cada digitalização concluída e a cada edição que **muda algo**; a página usa-a como versão da miniatura (`?version=`). A visão ampliada é imutável por `scan_identifier` + `rotation_degrees`: o mestre não muda enquanto o identificador vale.
- Documento: sem mudança (`revision` do rascunho sobe a cada edição que muda algo).
- 409: edições do último arquivo respondem 409 durante uma digitalização (`scan_already_running`); uma digitalização (rápida ou página de documento) enquanto uma edição do último arquivo roda responde `last_scan_busy`; ver a visão ampliada e a miniatura continua possível durante tudo.

## 6. Algoritmos

### 6.1 Giro, papéis dos cantos e validação (vetores compartilhados)

Coordenadas da página exibida: `x` para a direita, `y` para baixo, de 0 a 1. A ordem dos cantos é horária **na tela**; com `y` para baixo, isso é área com sinal positiva pela fórmula do cadarço.

```
girar a página 90° à direita:   ponto (x, y) -> (1 - y, x);  papéis: (tl, tr, br, bl)' = (g(bl), g(tl), g(tr), g(br))   [g = o giro do ponto]
girar a página 90° à esquerda:  a inversa:  ponto (x, y) -> (y, 1 - x);  papéis: (tl, tr, br, bl)' = (g(tr), g(br), g(bl), g(tl))
girar a moldura (saída 90° à direita): (tl, tr, br, bl)' = (bl, tl, tr, br)        # só os papéis: o antigo lado esquerdo vira o de cima
visto no mestre (página girada por k quartos de volta): cada ponto volta k vezes por (x, y) -> (y, 1 - x); papéis ficam
```

Os pontos arredondam a 6 casas a cada giro, para quatro giros voltarem exatamente ao início. Para um retângulo `(left, top, right, bottom)` o resultado é o do outro documento: `(1 − bottom, left, 1 − top, right)`.

**Validação (`PageCrop`)**, na ordem: todo número finito (um inteiro grande demais para `float` também é recusado); todo ponto em `[0, 1]` (tolerância `1e-9`); área com sinal `> 0` (sentido horário e não vazio); cada um dos quatro lados com comprimento `≥ 0,02` (em frações); cada canto convexo (produto vetorial `> 0`); cada triângulo de canto com pelo menos 5% da área do quadrilátero (impede o "canto achatado"). Todas usam só frações, sem o tamanho da imagem em pixels, então valem iguais no domínio (Python) e no navegador. O motivo do triângulo: um retângulo tem 50% em cada canto; um canto quase reto (180°) tem 0%.

**Vetores** em `tests/fixtures/page-crop-vectors.json` (substitui `page-crop-rotation-vectors.json`; lido pelos testes Python **e** Node). Cantos em ordem `top_left, top_right, bottom_right, bottom_left`:

| Caso | Moldura | Página girada 90° à direita | Moldura girada (só os papéis) |
|---|---|---|---|
| Retângulo | (0,1 0,2) (0,5 0,2) (0,5 0,9) (0,1 0,9) | (0,1 0,1) (0,8 0,1) (0,8 0,5) (0,1 0,5) | (0,1 0,9) (0,1 0,2) (0,5 0,2) (0,5 0,9) |
| Metade esquerda | (0 0) (0,5 0) (0,5 1) (0 1) | (0 0) (1 0) (1 0,5) (0 0,5) | (0 1) (0 0) (0,5 0) (0,5 1) |
| Página inteira | (0 0) (1 0) (1 1) (0 1) | igual | (0 1) (0 0) (1 0) (1 1) |
| Cartão diagonal | (0,486 0,119) (0,983 0,347) (0,542 0,904) (0,045 0,676) | (0,324 0,045) (0,881 0,486) (0,653 0,983) (0,096 0,542) | (0,045 0,676) (0,486 0,119) (0,983 0,347) (0,542 0,904) |
| Foto torta | (0,40 0,55) (0,93 0,44) (0,97 0,80) (0,44 0,91) | (0,09 0,44) (0,45 0,40) (0,56 0,93) (0,20 0,97) | (0,44 0,91) (0,40 0,55) (0,93 0,44) (0,97 0,80) |
| Quadrilátero qualquer | (0,10 0,10) (0,80 0,20) (0,90 0,85) (0,20 0,70) | (0,30 0,20) (0,90 0,10) (0,80 0,80) (0,15 0,90) | (0,20 0,70) (0,10 0,10) (0,80 0,20) (0,90 0,85) |

Quatro giros da página devolvem a moldura; girar à esquerda desfaz girar à direita; a página inteira girada continua cobrindo a página (mas **girar a moldura** na página inteira a faz deixar de ser "a página inteira": a saída fica girada). Casos de validade (mesmo arquivo): recusados `(0,1 0,1) (0,8 0,8) (0,8 0,1) (0,1 0,8)` (gravata, sentido não horário ou vazio), o mesmo retângulo no sentido anti-horário, `(0,1 0,1) (0,9 0,1) (0,9 0,1005) (0,1 0,1005)` (lado de 0,0005), `(0,1 0,1) (0,9 0,1) (0,9 0,9) (0,5 0,3)` (canto reflexo), `(−0,1 0) …` (fora da página), `(0,1 0,1) (0,5 0,1) (0,9 0,1002) (0,5 0,9)` (canto achatado), retângulo com um lado de 0,01; aceitos: retângulo com um lado de exatamente 0,02 e o quadrado girado `(0,5 0) (1 0,5) (0,5 1) (0 0,5)`.

**Ordem de leitura (D15)**, `put_in_reading_order`: com duas molduras `a` e `b`, seja a faixa vertical de cada uma o intervalo `[menor y, maior y]` dos quatro cantos. Se a sobreposição das faixas é maior que 50% da menor delas, vem primeiro a de menor centro em `x` (centro = média dos quatro cantos); senão, a de menor centro em `y`. Empate: a ordem em que chegaram. Na cena real, as faixas de A (0,02 a 0,58) e B (0,58 a 0,95) mal se tocam, então A vem primeiro. O mesmo algoritmo existe em JavaScript (mesmos vetores).

### 6.2 Render de uma moldura (`PageFramingRenderer.render_jpeg`)

1. Abre o mestre (`Image.open` sobre o fluxo recebido) e lê as opções do JPEG (`read_encoding_options(imagem, qualidade)`: qualidade da configuração, subamostragem, densidade e perfil do mestre) **antes** de qualquer transformação (uma imagem transformada perde o formato JPEG).
2. Sem moldura: só giro → `transpose` (como hoje); nem giro → os bytes do mestre, sem recodificar.
3. Com a moldura `c = framing.crops_on_master()[frame_index]`:
   - **`c.is_rectangle`** (caminho de hoje, mesmos bytes de hoje): `região = c.to_pixel_region(tamanho)` (piso na origem, teto nas bordas), `crop`, solta a imagem inteira, `transpose(c.rotation_to_upright)`.
   - **Senão** (quadrilátero livre): `cantos = c.to_pixel_corners(tamanho)` (em pixels do mestre, papéis da orientação exibida), `tamanho_da_saída = c.output_size_in_pixels(tamanho)` e
     `imagem.transform(tamanho_da_saída, QUAD, (*top_left, *bottom_left, *bottom_right, *top_right), BICUBIC)`, direto da imagem inteira (D17). A saída já sai em pé na orientação exibida: o giro da página está nos cantos.
   `rotation_to_upright` de um retângulo, pela posição do canto `top_left` no mestre: em cima à esquerda, nada; embaixo à esquerda, 90° à direita (`ROTATE_270` do Pillow); embaixo à direita, 180°; em cima à direita, 90° à esquerda (`ROTATE_90`). **Conferido** em `scratchpad/designer2/p11_render_semantics.py`: numa imagem de quadrantes coloridos, para a página girada 0°, 90°, 180° e 270° com um retângulo, o caminho do retângulo e o de `QUAD` dão **exatamente** a mesma imagem que recortar a página já girada; girar só os papéis equivale a girar o recorte 90° à direita; e a moldura que acompanha o giro da página mostra o mesmo conteúdo.
4. `save(JPEG, **opções)` com a densidade do mestre: a saída tem o tamanho físico da região (pontos = pixels ÷ densidade × 72).

`replace_with` segura no máximo duas imagens em memória (o mestre e a saída). Pico medido (3.1): 0,73 GB para uma moldura de 35 MP e 1,05 GB para uma de 116 MP em cor a 1200 dpi (0,2 e 0,3 GB em cinza). Duas molduras: dois `render_jpeg` em sequência, sem somar. Erros: `OSError`, `Image.DecompressionBombError` e `ValueError` viram `ScanFailedError` (um `DecompressionBombError` não pode acontecer a 1200 dpi: o limite do aplicativo é o do scanner); `MemoryError` sobe.

### 6.3 Detecção (calibrada nas digitalizações reais e nas cenas sintéticas)

**`detect_photo_regions(prévia)`** (só Pillow; prévia de no máximo 400 px):

1. **Fundo.** Histograma de cada canal na borda da prévia (faixa de 1,5% da maior aresta, no mínimo 2 px) e a mediana de cada canal. A borda é fundo se ao menos 60% dela fica a ±20 níveis da mediana em **todos** os canais (a regra de hoje). Senão: `None`, e a detecção por lado assume (o livro com a tampa aberta cai aqui).
2. **Primeiro plano.** Um pixel é primeiro plano se algum canal difere do fundo por mais de 20 níveis (uma capa escura colorida não se perde); filtro de mediana de 5 (`REGION_NOISE_FILTER_SIZE`). Uma segunda máscara, mais frouxa (10 níveis, mesmo filtro), serve ao anel da etapa 7.
3. **Componentes conexos** em Python puro, por **corridas de linha** (`re.finditer(b"\xff+", linha)`) e união-busca: uma corrida liga-se às da linha anterior com que se sobrepõe. Cada componente guarda a área e, por corrida, os quatro cantos de pixel `(início, y)`, `(fim, y)`, `(início, y + 1)`, `(fim, y + 1)`.
4. **Área mínima:** descarta componentes com menos de **1%** da prévia (`MINIMUM_PHOTO_AREA_SHARE`; poeira, etiquetas). Eram 3%, o que deixava de fora a foto 3x4 cm (cerca de 1,9% de um vidro A4) e a 3,5x4,5 cm (2,5%); com 1% o filtro de mediana de 5, o preenchimento e o anel seguem recusando poeira, fios de cabelo e um disco de 0,8% (revisão, 15).
5. **Casco convexo** (cadeia monótona) e **retângulo de área mínima**: o ótimo tem um lado sobre uma aresta do casco, então se testa cada aresta (projeta o casco no eixo da aresta e no perpendicular, pega a caixa e a área); fica a menor.
6. **Guardas**, da maior área para a menor, até 2 aceitos: preenchimento (pixels do componente ÷ área do retângulo) `≥ 0,75`; o retângulo toca no máximo 2 lados da prévia (faixa de 1,5%): uma região em 3 ou 4 lados é o fundo em volta de uma folha grande; o **anel** em volta (a faixa de 1,5%, rasterizada com `ImageDraw.polygon`, menos o interior e menos o anel já aceito de outra foto) tem no máximo 25% de primeiro plano da máscara frouxa (uma metade escura da página, quase igual à tampa, faria a moldura cortar o conteúdo). Os componentes que passam além dos 2 maiores contam em `ignored_count`.
7. **Papéis:** o lado de cima é a aresta mais próxima da horizontal **em pixels da prévia** (empate: a de ângulo maior, no sentido horário). Depois, a ordem de leitura (6.1).

**Conversão para `PageCrop` (`PageCropDetectionService`):**

8. **Ajuste ao eixo:** se o ângulo do lado de cima está a 1,5° (`AXIS_SNAP_DEGREES`) de 0° ou de 90°, a região vira a caixa envolvente, com `top_left` em cima à esquerda. (A foto B da cena real, a −2,2°, **não** é ajustada ao eixo: ela está mesmo torta.)
9. **Margem de 1% da maior aresta da imagem inteira**, em pixels da imagem inteira: a caixa alinhada cresce e é cortada pela imagem (como hoje, `grown_within`); a girada cresce em cada lado para fora e, se um canto sairia da página, a margem cai pela metade até caber (até 10 vezes; senão, sem margem). Divide por largura e altura, arredonda a 6 casas, `PageCrop.rounded`; uma moldura que cobre a página inteira, ou fina demais, é descartada com um aviso no log.

**Combinação (D18):**

```
regiões = detect_photo_regions(prévia)
se regiões não é None:   molduras = as regiões convertidas ou ()     # até 2; tampa uniforme: a resposta é final
senão:                   bordas = detect_paper_edges(prévia)         # o livro, tampa aberta: uma moldura retangular
                         molduras = [bordas convertidas] ou ()
```

A regra de segurança de hoje é toda mantida: borda que não é fundo uniforme = não há região; capa quase igual à tampa = não há região (o anel recusa quando a parte escura não vira primeiro plano); folha que enche o vidro = nada; branco sobre branco = nada (e as molduras do usuário valem mais que o palpite). As 20 cenas do detector estrito dão os mesmos retângulos (±3 px); a mudança de comportamento é só o piso de área, de 10% para 3% por região.

**Limites conhecidos (vão para a tela como dica, 8.5):** duas fotos a menos de uns 2,7 mm uma da outra viram uma região só (a moldura envolve as duas; use **Adicionar moldura**); mais de 2 fotos: as 2 maiores (a tela avisa); foto com borda branca sobre tampa branca: acha só a parte colorida.

**Constantes (nomeadas, em `photo_region_detection.py` e `page_crop_detection_service.py`):** `MINIMUM_PHOTO_AREA_SHARE = 0.01`, `MAXIMUM_PHOTOS = 2`, `REGION_NOISE_FILTER_SIZE = 5`, `MINIMUM_REGION_FILL_SHARE = 0.75`, `MAXIMUM_TOUCHED_SIDES = 2`, `MAXIMUM_RING_FOREGROUND_SHARE = 0.25`, `AXIS_SNAP_DEGREES = 1.5`, `CROP_MARGIN_RATIO = 0.01`, `MAXIMUM_MARGIN_HALVINGS = 10`; as de fundo e de primeiro plano (`BORDER_WIDTH_RATIO`, `BACKGROUND_TOLERANCE_LEVELS = 20`, `MINIMUM_BACKGROUND_BORDER_SHARE = 0.6`, `FOREGROUND_DIFFERENCE_LEVELS = 20`, `SURROUNDING_DIFFERENCE_LEVELS = 10`) saem de `paper_region_detection.py` para o módulo novo sem mudar de valor.

**Testes** (todos abaixo de 100 ms, escritos antes do código): cenas sintéticas feitas por `tests/fakes/photo_scenes.py` direto em prévia de 400 px (retângulos girados com `ImageDraw.polygon`, conteúdo de gradiente e círculos, tampa com degradê leve e ruído), com a verdade conhecida: 1 foto reta, 1 foto a 31°, 2 fotos a −30° e −2° (a cena real, em formas sintéticas), 2 fotos lado a lado, empilhadas e a 30 px de vão (acha 2) e a 8 px (acha 1), 3 fotos (2 achadas, 1 ignorada), tampa em branco, página com linha fina, polaroide, foto de 2%, foto encostada no vidro, tampa escura com folha reta e a 7°, as 20 cenas portadas do detector estrito; o livro (quatro digitalizações reais, quando `DIGITALIZADORA_REAL_SCANS_FOLDER` aponta para elas, e a imagem sintética `tests/fakes/book_on_glass.py`) segue enquadrado por lado e o de regiões fica de fora; as três `photos-*.jpg` reais, **também só com a variável**, dão 2 regiões com cantos a ±0,02 e ângulos −30° e −2° (±2°). Nenhuma imagem com pessoas entra no repositório.

### 6.4 Salvar (modo Documento) com 2 molduras

`DocumentDraftService._write_document` não muda de forma (`ensure_capacity`, `verify_page_files`, marca de intenção, escrita, limpeza). O que muda: `ensure_capacity(draft, jpeg_quality)` estima o PDF por `estimate_document_size_in_bytes(jpeg_quality)` (D23); `DocumentPdfAssembler.write_pdf` monta uma `RenderedPageSource` por `(página, índice de moldura)` na ordem do rascunho e das molduras, e o img2pdf as lê uma a uma. O PDF tem `output_page_count` páginas, cada uma com o tamanho físico da própria região. Uma página sem giro e sem moldura continua entrando com os bytes do scanner (sem recomprimir). O mestre é decodificado uma vez **por moldura** (a 1200 dpi, cerca de 0,4 s a mais por moldura, medido), nunca duas imagens ao mesmo tempo. Erros: como hoje (`ScanFailedError` vira `DocumentAssemblyFailedError`; `MemoryError`, `DocumentTooLargeError`; o rascunho fica intacto e a marca sai).

## 7. Modo Rápido não destrutivo

### 7.1 O espaço da última digitalização

`<pasta de dados>/quick-scan/` (irmã de `drafts/`), com um espaço só:

```
manifest.json                    o ponto de confirmação
master-<scan_identifier>.jpg     o JPEG do scanner com a densidade, byte a byte o que o ScanEncoder.encode_master devolveu
thumbnail-<scan_identifier>.jpg  480 px, do mestre sem giro
```

```json
{ "format_version": 1, "scan_identifier": "9f3c1a2b4d5e6f70", "scanned_at": "2026-10-18T12:41:03-03:00",
  "dots_per_inch": 300, "color_mode": "color",
  "output_folder": "/Users/pedro/Pictures/Digitalizadora", "output_format": "pdf",
  "rotation_degrees": 0, "crops": [ { "top_left": {"x": 0.039, "y": 0.28}, … } ],
  "saved_files": [ { "file_name": "2026-10-18_00007.pdf", "size_in_bytes": 211873, "modified_at_nanoseconds": 1760802063123456789 } ],
  "render_pending": false }
```

O manifesto só existe quando o mestre foi guardado (`is_editable` é então sempre verdadeiro; o caso "sem mestre" vive só na memória, 7.2). Leitura estrita (versão 1, qualquer coisa fora do formato é manifesto ilegível); o `load()` ainda confere que o mestre existe e que o identificador do nome do arquivo é o do manifesto. Um manifesto ilegível ou sem mestre é guardado de lado (`quick-scan/set-aside-<momento>-<token>/`, mesma convenção do rascunho) e o painel começa vazio.

### 7.2 Uma digitalização rápida (`ScanOutputService.store`, no thread do `ScanService`)

1. `encode_master(imagem, job)`: o JPEG do scanner com a densidade e a miniatura. Sem ajuste, sem corte.
2. `scan_identifier = secrets.token_hex(8)`.
3. Com `auto_crop` ligado: `detect_crops(mestre)`; uma falha da detecção (`DigitalizadoraError`) vira aviso no log e nenhuma moldura (o arquivo sai inteiro, como a página do documento). Desligado: nenhuma moldura. `framing = PageFraming().with_crops(achadas)`.
4. `slot_repository.write_master_files(...)` (mestre e miniatura, cada um atômico). Se falhar: aviso no log, `is_editable = False`, e o resto segue.
5. `render_outputs(BytesIO(mestre), OutputsRequest(framing, jpeg_quality, identidade))`: de 1 a 2 saídas (`EncodedScan`), JPG como está ou PDF de uma página com a densidade do mestre. Sem moldura, os bytes do scanner.
6. Para cada saída, em ordem: `scan_output_repository.save_scans(...)` (todos os arquivos juntos, com a mesma data-base e os contadores `__1`, `__2`; ver a seção 16, `ScanFileNamingPolicy`; cada `save` recalcula o próximo número livre) e `describe_saved_scan(...)` para o tamanho e a data.
7. Com o mestre guardado: `slot_repository.commit(QuickScanSlot(last_scan, dpi, cor))` grava o manifesto e só depois apaga os arquivos da digitalização anterior. Sem o mestre guardado: `slot_repository.discard()` (o espaço velho não pode sobreviver a uma digitalização nova).
8. Devolve `StoredScan(last_scan, miniatura)`; o `ScanService` o entrega ao tracker (`mark_completed`).

Falha no passo 5 ou 6 (`ScanFailedError`, pouco espaço): o erro sobe como hoje, nada é confirmado, o espaço anterior continua valendo e os arquivos do mestre novo ficam órfãos (apagados por `delete_leftovers` na próxima gravação ou partida). Se a moldura 1 já foi salva e a 2 falhou, o arquivo 1 fica na pasta; a tela mostra o erro, e a digitalização seguinte começa do zero. Memória a 1200 dpi: como a de hoje (o mestre em memória e uma imagem decodificada por vez, 6.2).

### 7.3 Editar a última digitalização (`LastScanEditService`)

Giro, `crops` e detecção compartilham um caminho. No laço de eventos:

1. `ScanAlreadyRunningError` se `phase` não é `IDLE`; `NoLastScanError` sem digitalização; `LastScanNotEditableError` se não há mestre.
2. Sob um `asyncio.Lock` (as edições esperam umas pelas outras, uma de cada vez), chama `tracker.mark_last_scan_edit_started()` **sem nenhum `await` entre a checagem da fase e essa chamada**, e roda o trabalho de disco em `asyncio.to_thread`. No fim (sempre), `mark_last_scan_edit_ended()`.
3. De volta ao laço, `tracker.replace_last_scan(identificador_esperado, StoredScan(nova, miniatura))`, que sobe `last_result_revision`.

O trabalho de disco (`_apply_edit`), com o enquadramento novo já calculado (giro: `framing.turned_clockwise()`; `set_crops`: `framing.with_crops(crops)`; detecção: `detect_crops(mestre)` lido do espaço, as molduras achadas levadas à orientação exibida por `crops_from_master`, e **nada achado = nada muda**):

1. Enquadramento igual ao atual: devolve o resultado atual sem escrever nada (sem revisão).
2. Confere que cada arquivo salvo que será regravado ainda existe (`describe_saved_scan`); senão `LastScanFileMissingError` **antes** de qualquer escrita.
3. `slot_repository.commit(slot com o enquadramento novo e render_pending = True)`.
4. `_render_outputs(slot, jpeg_quality)` (compartilhado com a recuperação):
   1. abre o mestre (`master_file_path`) e chama `render_outputs` (todas as saídas em memória, uma imagem decodificada de cada vez);
   2. para `i < min(antigas, novas)`: `replace_saved_scan(caminho_i, conteúdo_i)` (atômico, mesmo nome);
   3. para `i ≥ antigas`: a gravação do grupo (`save_scans_in_folder`, data-base nova) e `describe_saved_scan`;
   4. para `i ≥ novas`: `describe_saved_scan`; **se o tamanho e a data são os do manifesto, `delete_saved_scan`**; se mudaram, o arquivo fica e o nome vai em `kept_file_names`; se já não existe, nada (D21);
   5. `commit(slot com saved_files novos e render_pending = False)`.
5. Falha no meio (disco cheio, por exemplo): o erro sobe; em melhor esforço, o manifesto volta ao enquadramento anterior e a `render_pending = False`. Se o que cai é o processo, a recuperação (7.4) termina o trabalho.

`rotation_degrees` e as molduras de uma digitalização nova começam do que o passo 3 do 7.2 achou; o giro nunca é aplicado numa digitalização nova.

### 7.4 Recuperação na partida (`restore_after_start`, nunca levanta)

1. `slot = slot_repository.load()`. `None`: `delete_leftovers(None)`, painel vazio.
2. Nenhum dos `saved_files` existe mais (você os apagou): `discard()`, painel vazio. Senão o espaço vale.
3. `render_pending`: `_render_outputs(slot, jpeg_quality)` (o mesmo código, com o enquadramento gravado). Um arquivo novo criado antes da queda e ainda não registrado fica como um arquivo a mais na pasta (aviso no log): é o preço de não registrar nomes antes de criá-los.
4. `delete_leftovers(slot.scan_identifier)` e `tracker.restore_last_scan(StoredScan(slot.last_scan, miniatura))` (miniatura do disco; se faltar, refeita do mestre).

Nenhuma falha impede o servidor de subir: um erro vira aviso no log e o painel começa vazio.

### 7.5 Interação com a digitalização e com o documento

- Uma digitalização rápida ou uma página de documento não começa enquanto uma edição do último arquivo roda (`ScanService.ensure_scan_can_start()` levanta `LastScanBusyError`; o `ScanController` e o `DocumentDraftService.ensure_can_add_page` o usam antes de aceitar o pedido, e `begin_scan` o repete, dentro do laço de eventos, para a janela entre os dois).
- Uma edição do último arquivo não começa durante uma digitalização (`scan_already_running`).
- O modo Documento (rascunho, edições, Salvar) não depende do espaço da última digitalização; as duas coisas podem ter molduras abertas ao mesmo tempo, mas o editor é modal e só mostra uma.
- A miniatura e a visão ampliada **não** tomam trava: o mestre só muda quando a digitalização seguinte confirma o manifesto; uma leitura em andamento nessa janela termina com o arquivo já aberto ou responde 404 (`no_last_scan`).

### 7.6 Nomes, criação, troca e remoção de arquivos

- Nomes: a política de hoje (`AAAA_MM_DD__HH_MM_SS_NNNNNNNNN.pdf` ou `.jpg`; seção 16), com o formato de **quando a digitalização foi feita** (um espaço restaurado conserva o formato dele, mesmo que a configuração mude depois).
- Duas molduras na digitalização: dois arquivos que repartem a data-base e terminam em `__1` e `__2` (seção 16). Sem moldura: um, com nome simples.
- Aplicar com mais molduras: arquivos novos nos próximos números livres; com menos: os de índice maior são apagados (se estão como foram gravados) e a tela diz quais. O arquivo `i` é sempre a moldura `i` (ordem de leitura): remover a moldura 1 de 2 faz o arquivo 1 receber a foto que era a 2 e apaga o arquivo 2.
- Nunca se mexe em arquivo que a digitalização atual não criou. A pasta de saída é a da digitalização (gravada no manifesto), não a configurada agora.

## 8. Configurações e interface

### 8.1 Qualidade do JPEG e a dica removida

- `GET`/`PUT /api/settings` e `settings` do estado ganham `jpeg_quality` (inteiro, 50 a 100). `PUT`: opcional, ausente ou `null` mantém o salvo; não inteiro (inclusive `true`) ou fora da faixa = 422 `invalid_settings`, sem salvar nada.
- `settings.json`: chave `jpeg_quality`; ausente = 90; inválida = 90 com um aviso no log, as outras chaves lidas normalmente.
- Página: abaixo da caixa de corte, um campo **Qualidade do JPEG** com `<input id="jpeg-quality-input" type="range" min="50" max="100" step="1">` e o valor ao lado (`<output id="jpeg-quality-value">`, atualizado a cada movimento, para o leitor de tela ler "90"); a configuração é gravada ao soltar (`change`), como as outras. Uma linha de dica (`#jpeg-quality-hint`, ligada por `aria-describedby`): **"Vale quando a imagem é cortada ou girada."** Sem tabela de tamanhos na tela.
- A caixa **Cortar automaticamente e remover o fundo** fica, sem o parágrafo `#auto-crop-hint` e sem o `aria-describedby` dele.
- Funções puras novas em `scan-quality-policy.js`: `MINIMUM_JPEG_QUALITY`, `MAXIMUM_JPEG_QUALITY`, `DEFAULT_JPEG_QUALITY`, `parse_jpeg_quality(text)` (um valor fora da faixa ou que não é número volta ao padrão).

### 8.2 O tile do modo Documento

O invólucro da miniatura (`page-thumbnail-frame`, proporção da imagem) leva agora um `<svg class="page-crop-overlay" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">` no lugar da `div`: um caminho `fill-rule: evenodd` (a página inteira menos cada moldura) escurece o lado de fora e um `<polygon>` por moldura desenha o contorno (`vector-effect: non-scaling-stroke`; moldura 1 azul contínua, moldura 2 laranja tracejada, 2 px com um contorno escuro de 1 px para valer em página clara e escura). O selo "1" ou "2" é um `<span>` posicionado no primeiro canto (`aria-hidden`). Texto no tile, para quem não vê cor: uma linha "2 molduras" (`page-crop-count`) quando há mais de uma. O `aria-label` do item vira "Página N de M", "Página N de M, com moldura de corte" ou "Página N de M, com 2 molduras de corte (2 páginas no PDF)". A ordem do Tab e os botões não mudam (◀ ▶ × / Girar ↻ Mover para… / Ampliar).

### 8.3 O editor (`<dialog id="page-frame-dialog">`)

Reaproveita `PageFrameEditor`, `page-frame-geometry.js` e os textos de `document-page-policy.js` (D25). O que muda:

**Alvo de edição.** `PageFrameEditor.open(opening)` recebe `opening.editor_target`:

```js
editor_target = {
  title_text,                     // "Página 2 de 3: moldura de corte" | "Última digitalização: moldura de corte"
  describe_label,                 // "da página 2" | "da última digitalização" (nos anúncios)
  rotation_degrees, crops,        // o estado salvo
  build_preview_address(rotation_degrees),
  requests: { rotate_page, set_crops(crops), detect_crops },     // cada uma devolve a requisição para attempt_edit
  max_crops: 2,
}
```

e `editor_services` (os que já existem: `attempt_edit`, `report_failure`, `can_edit`, `announce`, `restore_focus`) mais `find_target(identifier)` no lugar de `find_page`. O `DocumentPanel` e o `ScanPage` constroem cada um o seu alvo; as respostas do servidor entram por `handle_target_change()`, como `handle_document_change()` hoje.

**Estado do editor:** `saved_frames` (do servidor), `draft_frames` (0 a 2, do rascunho local), `active_index`, `rotation_degrees`, `surface` (largura e altura em pixels da imagem ampliada, lidas de `naturalWidth` e `naturalHeight` ao carregar). Arrastar e empurrar só mudam o rascunho; **Aplicar** manda `PUT …/crops` com o rascunho; **Cancelar** (Esc) o descarta; **Detectar automaticamente** e **Girar ↻** são edições imediatas do servidor; depois de cada resposta o rascunho acompanha (o rascunho sem mudança vira o salvo; um rascunho com mudança gira junto com a página, `turn_frames_by_quarter_turns`).

**Palco.** `<img>` ampliada; `<svg class="frame-overlay">` com o escurecimento (evenodd) e os contornos (1 azul contínua, 2 laranja tracejada; a ativa mais grossa); sobre ele, **botões** de alça posicionados em porcentagem (`left`/`top` com `translate(-50%, -50%)`): 4 de canto (`Canto superior esquerdo`, `Canto superior direito`, `Canto inferior direito`, `Canto inferior esquerdo`), 4 de lado, no meio de cada lado (`Borda de cima`, `Borda direita`, `Borda de baixo`, `Borda esquerda`), **Mover a moldura** no centro e **Girar a moldura** (uma alça fora do lado de cima, a uns 6% da altura da moldura, para fora). Só a moldura ativa tem alças; a outra tem o botão **Selecionar moldura N** no centro (o mesmo clique no polígono, para o mouse). Alças são `<button type="button">` (Espaço num botão nunca digitaliza), com área de toque de pelo menos 44 px e `touch-action: none`; só o botão primário inicia um arraste e o menu de contexto do palco é suprimido (como hoje).

**Geometria (`page-frame-geometry.js`), tudo em frações da página, com `surface` para converter em pixels quando o ângulo importa:**

```
FRAME_CORNER_HANDLES = ["top_left", "top_right", "bottom_right", "bottom_left"];  FRAME_EDGE_HANDLES = ["top", "right", "bottom", "left"]
build_frame(corners) / read_frame_from_crop(crop) / read_frames_from_crops(crops) / build_crops_request_body(frames)
is_rectangle_frame(frame), is_whole_page_frame(frame), frames_are_equal(first_frame, second_frame)     // tolerância 0,0005
validate_frame(frame) -> { is_valid, problem }          // as mesmas regras e os mesmos vetores do Python (6.1)
move_frame(frame, shift)                                // shift {delta_x, delta_y}; limita para os cantos ficarem em 0..1
move_corner(frame, move)                                // move {corner, delta_x, delta_y}; resultado inválido = a moldura de antes
move_edge(frame, move)                                  // move {edge, delta_x, delta_y, surface}: o deslocamento projetado na normal do lado
rotate_frame(frame, rotation)                           // rotation {degrees, surface}: em torno do centro, em pixels; encolhe só o necessário para caber
turn_frame_clockwise(frame)                             // o giro da página (6.1)        turn_frame_output_clockwise(frame): só os papéis
turn_frames_by_quarter_turns(frames, quarter_turns)
put_frames_in_reading_order(frames)                     // 6.1
suggest_new_frame(frames)                               // sem molduras: retângulo (0,2 0,2) a (0,8 0,8); com uma: retângulo de 40% x 40% na metade livre, de (0,55 0,30) a (0,95 0,70) se o centro da existente fica à esquerda, de (0,05 0,30) a (0,45 0,70) se fica à direita
nudge_corner / nudge_edge / nudge_whole_frame / nudge_rotation       // setas; Shift passa de 0,005 para 0,05 (e de 0,5° para 5°)
describe_frame_outline(frame) -> polígono em porcentagem para o svg;  describe_handle_style(point) -> {left_percent, top_percent}
describe_frame(frame, label) / describe_corner_position / describe_edge_position                         // textos em português (8.5)
```

Lado de um retângulo girado: as alças de lado movem o lado ao longo da normal (num retângulo, é redimensionar sem entortar). Alça de canto: livre. Girar a moldura: ângulo do ponteiro em relação ao centro, medido **desde o início do arraste** (nunca incremental), ou setas esquerda e direita na alça (0,5°, Shift 5°). Qualquer resultado inválido (côncavo, achatado, lado curto) é ignorado e, ao soltar, o status diz "Esse movimento deixaria a moldura torta demais. Ela ficou como estava.".

**Botões:** linha 1 (moldura): **Adicionar moldura** (desabilitado com 2 molduras), **Remover moldura** (a ativa; desabilitado sem moldura), **Girar moldura ↻** (a ativa; `aria-label` "Girar a moldura 1 em 90 graus para a direita: muda o lado de cima da foto recortada"); linha 2 (página): **Detectar automaticamente**, **Sem corte** (remove todas), **Girar ↻**; linha 3: **Cancelar**, **Aplicar** (desabilitado enquanto o rascunho é igual ao salvo). O foco inicial vai para **Mover a moldura** da ativa (ou para **Adicionar moldura** se não há moldura). Enter não aplica; Esc cancela; no celular as linhas quebram e os botões ocupam a largura.

**Teclado:** Tab percorre as alças da moldura ativa (canto superior esquerdo, os outros cantos no sentido horário, depois os lados, **Mover**, **Girar a moldura**), depois **Selecionar moldura N**, depois os botões. Setas movem a alça (um canto, pelo eixo da seta; um lado, só pelas setas que apontam mais na direção da normal do lado do que na da tangente: num lado de cima levemente torto, "para cima" e "para baixo" andam e "esquerda" e "direita" não); Shift anda 10 vezes mais. As teclas globais do documento ficam inertes (o diálogo conta como aberto) e Espaço e Backspace não chegam ao tratador da página.

### 8.4 O painel "Última digitalização" (modo Rápido)

No lugar da `<img>` solta, o mesmo invólucro de miniatura do tile (`last-scan-thumbnail-frame` com `<img id="last-scan-thumbnail">` e o `<svg>` das molduras). Os detalhes: **Arquivos** (um nome por linha), **Tamanho** (total), **Hora**. Botões, nesta ordem: **Girar ↻** (como hoje, agora regrava os arquivos a partir do mestre) e **Ampliar** (abre o mesmo editor com o alvo do último arquivo). A linha `role="status"` diz o resultado de cada ação ("Última digitalização girada 90° para a direita.", "Moldura aplicada: 2 arquivos.", "O arquivo 2026-10-18_00008.pdf foi apagado porque agora há só 1 arquivo.", "Mantive 2026-10-18_00008.pdf porque ele foi alterado depois de gravado."). Sem mestre (`is_editable: false`): os dois botões desabilitados, com a dica "O original desta digitalização não foi guardado; os arquivos foram salvos normalmente." A dica de hoje ("Girar regrava o arquivo salvo.") vira "Ajustes regravam os arquivos salvos." Os dois botões ficam desabilitados durante uma digitalização e enquanto uma edição roda. A miniatura é `GET /api/scans/last/thumbnail?version=<last_result_revision>`; o editor abre `…/preview?scan_identifier=…&rotation_degrees=…`.

### 8.5 Textos novos (todos em português)

Catálogo de erros (`error_message_catalog.py`):

| Código | Texto |
|---|---|
| `invalid_crop` (muda) | "A moldura de corte é inválida: ela precisa ser um quadrilátero sem pontas viradas, dentro da página, e são no máximo 2 molduras. Ajuste e tente de novo." |
| `no_last_scan` (muda) | "Ainda não há uma digitalização para ajustar." |
| `last_scan_busy` | "A última digitalização está sendo ajustada. Aguarde um instante e tente de novo." |
| `last_scan_not_editable` | "O original desta digitalização não foi guardado, então ela não pode ser ajustada." |
| `saved_scan_unreadable` (muda) | "Não consegui ler o original da última digitalização para ajustá-la. Veja o registro em ~/Library/Logs/Digitalizadora." |
| `image_adjustment_failed` (muda) | "Não consegui processar a imagem com a memória livre do Mac. Escolha uma resolução menor e tente de novo." |

Editor: "Moldura 1 de 2 selecionada." · "Moldura 2 adicionada." · "Só dá para ter 2 molduras." · "Moldura 2 removida." · "Moldura 1 girada: o lado de cima da foto mudou." · durante uma regravação do modo Rápido: "Regravando…" · detecção: "Achei 2 molduras e salvei.", "Achei 1 moldura e salvei.", "Achei mais de 2 fotos; usei as 2 maiores." (somada ao anterior) e, sem achado, "Não achei uma borda confiável nesta página. As molduras não mudaram." · aplicação: "Molduras aplicadas à página 2." · "Corte removido da página 2." · descrição de uma moldura reta: "Moldura 1: esquerda 13%, topo 12%, direita 91%, base 91%." e de uma torta: "Moldura 1: inclinada 30° para a esquerda. Cantos: superior esquerdo (4%, 28%), superior direito (65%, 2%), inferior direito (89%, 32%), inferior esquerdo (28%, 58%)." (esquerda = sentido anti-horário na tela) · "Sem corte: a página inteira será usada." · dica do diálogo: "Arraste os cantos, os lados ou a moldura toda. A alça de cima gira a moldura. Com o teclado, escolha uma alça (Tab) e use as setas; Shift anda mais." · dicas das limitações: "Duas fotos muito juntas podem virar uma só moldura: use Adicionar moldura. Uma foto com uma faixa quase branca pode virar duas: confira as molduras, remova uma e ajuste a outra." fica só no `aria-describedby` do diálogo, em texto pequeno (não na caixa Ajustes).

## 9. Simulador

`DIGITALIZADORA_SIMULATOR_SCENE` (`sheet`, o padrão, que mantém `DIGITALIZADORA_SIMULATOR_LID_BACKGROUND`; `photos_one`; `photos_two`) e `DIGITALIZADORA_SIMULATOR_PORT` já existe. Em `fake_escl_scanner_app.py`: `PhotoScene` (enum), `parse_photo_scene(text)` (ausente ou desconhecido = `sheet`, como `parse_lid_background`), `PhotoPlacement` (centro e tamanho em frações da **largura** do vidro, ângulo) e `build_photo_scene_page(requested_scan, scene)`: tampa `#fcfcfc` com um degradê vertical leve (14 níveis, como as cenas medidas), mais uma foto **sintética** por posição (gradiente e círculos de semente fixa, borda escura de 1%) girada com `Image.rotate(expand=True)` e colada com máscara. Cada foto tem um marcador magenta no canto de cima à esquerda e um verde no de cima à direita, para os testes conferirem que o recorte sai em pé.

| Cena | Fotos (centro x, y da largura; tamanho largura × altura da largura; ângulo) |
|---|---|
| `photos_one` | A: (0,50, 0,45), 0,62 × 0,42, −30° |
| `photos_two` | A: (0,465, 0,30), 0,71 × 0,48, −30° · B: (0,535, 0,77), 0,71 × 0,48, −2° (as duas copiam a cena real: dois 10 × 15 cm) |

A cena nunca desenha pessoas nem usa a imagem do usuário. `FakeScannerBehavior.scene: PhotoScene = PhotoScene.SHEET`; `__main__` lê a variável.

## 10. Testes: o que muda e o que entra

A lista abaixo vem de uma varredura por AST dos testes que usam os símbolos que mudam (`PageCrop`, `PageFraming.crop`, `set_page_crop`, `detect_crop_to_apply/suggest`, `detect_paper_region`, `ImageAdjustmentService`, `MasterJpegService`, `DocumentPageRenderer`, `ScanContentRotator`, `LastScanRotationService`, `last_result`, `StoredScan`, `read_saved_scan`, `SettingsUpdate`, `ApplicationSettings(`), feita no commit `5b634cb`; o que não aparece aqui continua como está. Os nomes são os de hoje, sem o prefixo `test_`. Para não repetir a mesma troca mecânica em dezenas de testes, entra o ajudante `tests/fakes/page_crops.py` (`rectangle(left, top, right, bottom) -> PageCrop`, `framing_with(*crops) -> PageFraming`) e toda construção `PageCrop(l, t, r, b)` dos testes passa a `rectangle(l, t, r, b)`.

### 10.1 Arquivos de teste apagados ou trocados

- **Apagados** (o código sai): `tests/services/test_image_adjustment_service.py` (17 testes sobre corte destrutivo: a densidade, a subamostragem, o perfil, o cinza, a memória e a imagem ilegível passam a ser testes do `PageFramingRenderer`; os de detecção passam ao serviço de detecção), `tests/services/test_master_jpeg_service.py` (3: `without_adjustment_the_result_is_the_scanner_image_with_the_requested_density` vira teste de `encode_master`), `tests/services/test_scan_content_rotator.py`, `tests/services/test_last_scan_rotation_service.py` (6 testes do giro no arquivo).
- **Renomeados e reescritos:** `test_paper_region_detection.py` → `test_photo_region_detection.py`; `test_document_page_renderer.py` → `test_page_framing_renderer.py`; `tests/fakes/stub_last_scan_rotation_service.py` → `stub_last_scan_edit_service.py`; `tests/integration/test_frame_and_rotation_flow.py` → `test_frames_flow.py` (documento) e `test_quick_scan_slot_flow.py` (modo Rápido).

### 10.2 Testes existentes que precisam mudar (por arquivo)

**Domínio**

- `tests/domain/test_page_crop.py` (26, todos): `a_crop_with_a_far_edge_before_the_near_one_is_refused` → `a_counterclockwise_quadrilateral_is_refused`; `a_side_below_the_minimum_share_is_refused` e `a_side_of_exactly_the_minimum_share_is_accepted` → "um lado de 0,01 é recusado" e "um lado de 0,02 é aceito"; `an_edge_outside_the_page_is_refused` → "um canto fora da página"; `an_edge_that_is_not_finite…`, `…not_a_number…`, `an_integer_too_large_for_a_float…` (3) e `rounded_*` (3) trocam "borda" por "canto"; `the_whole_page_is_a_valid_crop`, `the_whole_page_covers_the_whole_page`, `edges_one_float_step_away_from_the_page_still_cover_it` usam `from_rectangle`; `turning_clockwise_follows_the_shared_vectors`, `turning_counterclockwise_undoes_the_shared_vectors` leem `page-crop-vectors.json`; `four_clockwise_turns_*` (2) ficam com quadriláteros; `the_corner_of_a_half_page_goes_where_the_page_corner_goes` fica (o canto `top_left` vai ao `top_right` e o papel avança); `to_pixel_region_*` (6) e `from_pixel_region_*` (2) ficam sobre `bounding_edges`.
- `tests/domain/test_page_framing.py` (13): `turning_without_a_crop_keeps_it_empty` → "sem molduras"; `turning_clockwise_turns_the_crop_with_the_page` → "todas as molduras"; `with_crop_replaces_the_crop`, `with_crop_keeps_the_rotation`, `a_crop_that_covers_the_whole_page_becomes_no_crop`, `with_no_crop_removes_the_crop` → `with_crops_*`; os seis `*_on_the_master*`/`*_from_the_master*` e `without_a_crop_the_master_has_no_crop_either` → `crops_on_master`/`crops_from_master` (listas).
- `tests/domain/test_image_adjustment.py`: `an_automatic_crop_alone_is_active`, `the_adjustment_is_immutable` (com a qualidade); entram os da faixa de `jpeg_quality`.
- `tests/domain/test_application_settings.py` (7): `to_scan_request_carries_the_adjustment` (leva a qualidade) e os que constroem `ApplicationSettings` não mudam de comportamento.
- `tests/domain/test_document_draft.py`: `the_estimated_document_size_counts_a_page_without_framing_once` e `the_estimated_document_size_doubles_a_page_that_needs_rendering` viram `estimate_document_size_in_bytes(jpeg_quality)` (×2 a 90, ×4 a 100); entra `output_page_count`.
- `tests/domain/test_immutable_models.py`: acrescentar `CropCorner`, `RectangleEdges`, `LastScan`, `SavedScanFile`, `QuickScanSlot`.

**Repositórios**

- `tests/repositories/test_document_manifest_codec.py` (6): `the_rotation_and_the_crop_are_encoded_on_the_page` (agora `crops`), `a_manifest_from_before_the_framing_reads_pages_without_rotation_or_crop`, `an_invalid_crop_is_read_as_no_crop` (descarta só o item), `an_invalid_crop_does_not_make_the_manifest_unreadable`, `an_invalid_rotation_keeps_the_crop_of_the_page` (as molduras), `a_crop_of_the_whole_page_is_read_as_no_crop`; entram o manifesto com `crop` antigo (uma moldura retangular), os dois itens e o terceiro descartado.
- `tests/repositories/test_json_application_settings_repository.py`: `save_writes_the_documented_json_shape` (com `jpeg_quality`), `an_invalid_quality_pair_without_a_preset_keeps_the_other_fields` e os de `auto_crop` (5) só ganham a chave nova no documento; entram `jpeg_quality` ausente, inválido e gravado.
- `tests/repositories/test_file_system_scan_output_repository.py` (7): **apagar** os três `read_saved_scan_*` (o método sai); os quatro `replace_saved_scan_*` ficam; entram `describe_saved_scan_*` e `delete_saved_scan_*`.

**Serviços**

- `tests/services/test_paper_region_detection.py` → `test_photo_region_detection.py` (21): cada teste chama `detect_photo_regions` e compara a **caixa envolvente** com a mesma tolerância de 3 px (as 20 cenas portadas); `a_sheet_below_a_tenth_of_the_glass_is_ignored` → `a_sheet_below_three_percent_of_the_glass_is_ignored` (continua 0,8% da prévia); `a_sheet_just_above_a_tenth_of_the_glass_is_found` fica (11%); `a_gradient_background_has_no_reliable_border` passa a esperar `None`, "borda não é fundo".
- `tests/services/test_paper_edge_detection.py` (23): **sem mudança** (o detector por lado não muda); os dois testes de digitalizações reais passam também pelo serviço.
- `tests/services/test_page_crop_detection_service.py` (19): **apagar** `the_crop_to_apply_frames_a_sheet_on_a_dark_lid`, `the_crop_to_apply_grows_the_sheet_by_a_margin_of_a_hundredth_of_the_longest_side`, `the_crop_to_apply_of_a_white_page_is_none`, `the_crop_to_apply_ignores_the_detection_by_side`, `a_crop_to_apply_that_finds_no_sheet_says_so_in_the_log`, `a_crop_to_apply_that_finds_a_sheet_logs_nothing`, `the_strict_detection_still_sees_no_sheet_in_the_real_scans`; os outros 12 viram `detect_crops` (os `…_to_suggest_…` perdem o sufixo): `…frames_a_sheet_on_a_dark_lid…`, `…frames_a_book_the_strict_detection_cannot_see`, `…keeps_the_whole_book`, `…leaves_a_side_without_an_edge_at_the_glass`, `a_dark_cover_around_a_bright_picture…` (um só), `…of_a_white_page_is_none`, `the_crop_of_a_large_scan_maps_the_sheet_from_the_reduced_preview`, `…says_so_in_the_log`, `running_out_of_memory…`, `a_sheet_so_thin_that_its_crop_is_invalid_is_not_cropped`, `the_real_scans_of_the_book_get_a_frame_that_holds_the_whole_book`.
- `tests/services/test_scan_encoder.py` (2): `the_crop_reaches_the_jpeg_output` apagado; `the_density_is_written_after_the_crop` → `the_master_carries_the_requested_density`; o resto passa a `encode_master` e `wrap_output`.
- `tests/services/test_jpeg_reencoding.py` (5): `the_options_ask_for_the_adjusted_quality` → `the_options_ask_for_the_quality_given`; os outros quatro passam o segundo argumento.
- `tests/services/test_page_framing_renderer.py` (era `test_document_page_renderer.py`): `a_crop_away_from_the_marker_leaves_the_marker_out`, `the_displayed_crop_that_misses_the_turned_marker_misses_it_in_the_result` e os demais usam `FrameRenderRequest`; entram os de `QUAD`.
- `tests/services/test_rendered_page_source.py` (5): constroem com `FrameRenderRequest`.
- `tests/services/test_document_pdf_assembler.py`: `a_cropped_page_has_the_physical_size_of_the_region` e `a_cropped_and_rotated_page_has_the_size_of_the_turned_region` (±1 px: a moldura retangular segue o caminho de hoje, tamanho igual); entram os de duas molduras.
- `tests/services/test_document_finalizer.py`: o primeiro colaborador e `ensure_capacity(draft, jpeg_quality)`; `memory_error_while_assembling_raises_document_too_large`, os dois de `ensure_capacity_accepts_the_minimum_plus_the_draft_size…` e `…one_byte_short…` (com o fator por qualidade).
- `tests/services/test_document_page_capture.py`: `a_page_with_the_automatic_crop_gets_the_frame_of_the_sheet` → "as molduras"; entram "duas fotos viram duas molduras" e "uma falha da detecção não impede a página"; `ensure_capacity_does_not_count_the_adjustment_of_the_request` fica.
- `tests/services/test_document_page_crop_detector.py` (9): `a_result_is_a_draft_and_a_boolean` → "um rascunho, um booleano e uma contagem"; os outros trocam crop por crops; entra "achou duas".
- `tests/services/test_document_draft_store.py` (14, todos de `set_page_crop` e `turning_a_page_turns_its_crop_with_it`) e `tests/services/test_document_draft_service.py` (12) e `tests/services/test_document_page_framing_recovery.py` (3): `set_page_crop` → `set_page_crops`, `detect_page_crop` → `detect_page_crops`, "a crop" → "the crops"; `a_cropped_page_goes_into_the_saved_pdf_with_the_size_of_its_frame` fica; `add_page_passes_the_adjustment_to_the_page_scanner` (leva a qualidade); entra o `finalize(jpeg_quality)`.
- `tests/services/test_scan_progress_tracker.py` (20): todos trocam `last_result`/`ScanResult` por `last_scan`/`LastScan`; os cinco `replace_last_scan_*` passam a identificar pelo `scan_identifier`; entram `restore_last_scan`, `mark_last_scan_edit_started/ended` e "`begin_scan` levanta `LastScanBusyError`".
- `tests/services/test_scan_service.py` (3) e `tests/services/test_scan_service_document_page.py` (4): `last_result` → `last_scan`; entra `ensure_scan_can_start`.
- `tests/services/test_scan_output_service.py`: **reescrito** (7.2): `store_returns_the_thumbnail_of_the_encoded_scan` e o resto viram os cenários do pipeline novo.
- `tests/services/test_storage_guard_service.py`: `an_active_crop_doubles_the_estimated_page_size` → "multiplica pelo fator da qualidade" (90: ×2; 100: ×4).
- `tests/services/test_application_settings_service.py` (6): `update_returns_the_new_settings`, `invalid_update_saves_nothing`, `invalid_update_prepares_no_folder`, `update_without_adjustment_fields_keeps_the_saved_adjustment`, `a_crop_choice_is_saved`, `a_refused_quality_or_adjustment_saves_nothing` (agora também a `jpeg_quality` fora da faixa); entram `a_jpeg_quality_is_saved` e `a_boolean_is_not_a_jpeg_quality`.
- `tests/services/test_application_state_service.py` (3): constroem as configurações com a qualidade (o resultado não muda).

**Controladores**

- `tests/controllers/test_document_controller.py` (16): os nove `set_page_crop_*` → `set_page_crops_*` (corpo com `crops`, 0 a 2 itens; `…accepts_whole_numbers_as_edges` → `…as_coordinates`; `…with_an_invalid_rectangle_answers_422` → `…quadrilateral…`; entra "mais de 2 molduras = 422"); os sete `detect_page_crop_*` → `detect_page_crops_*` (a resposta leva `crops_detected` e `ignored_region_count`); `…is_a_put_only_route`/`…post_only_route` ficam; entra o `finalize` com a qualidade.
- `tests/controllers/test_document_body.py`: `document_describes_the_draft_and_its_pages_in_order`, `a_framed_page_reports_its_rotation_and_crop` (`crops`, os quatro cantos).
- `tests/controllers/test_application_factory.py`: `a_malformed_crop_does_not_reach_the_document_service` (rota `…/crops`); entram os padrões do último arquivo; `thumbnail_is_served_after_a_stored_scan` (a miniatura vem do `LastScanViewService`).
- `tests/controllers/test_last_scan_controller.py` (4): **reescrito** para as três rotas (5.4).
- `tests/controllers/test_settings_controller.py` (5): `get_settings_returns_the_saved_settings`, `put_settings_returns_the_new_settings`, `put_settings_saves_the_new_settings`, `put_settings_saves_the_crop`, `a_mistyped_field_saves_nothing` (com `jpeg_quality`); entram os 422 de `jpeg_quality`.
- `tests/controllers/test_state_controller.py` (7): `state_contains_the_settings`, `state_describes_the_last_result` (formato novo, 5.2), `state_has_exactly_the_documented_keys`, `state_of_a_fresh_application`, `state_reports_the_current_phase_and_counter`, e os dois da revisão.
- `tests/controllers/test_error_message_catalog.py`: os testes que listam os códigos (seis mudanças de 8.5).

**Integração e raiz**

- `tests/integration/test_frame_and_rotation_flow.py` (40 testes; 28 deles mudam) → `test_frames_flow.py` e `test_quick_scan_slot_flow.py`: os nove do giro do último arquivo (`a_quick_jpg_is_turned_in_its_own_file`, `a_quick_jpg_keeps_its_density_when_turned`, `a_quick_pdf_only_gets_a_quarter_turn_on_its_page` — **agora o PDF é regravado, não só `/Rotate`**: o teste passa a conferir a orientação e a densidade —, `two_quick_turns_in_a_row_add_up_to_a_half_turn`, `turning_the_last_scan_raises_the_revision_and_turns_the_thumbnail`, `the_state_reports_the_new_size_of_the_turned_file`, `turning_the_last_scan_before_any_scan_answers_no_last_scan`, `a_document_page_is_not_a_last_scan_to_turn`, `turning_a_last_scan_that_was_deleted_answers_last_scan_file_missing`); os onze de moldura do documento (rota `crops`); os oito de ajustes (`quick_scan_with_the_crop_against_the_dark_lid_keeps_only_the_sheet` **muda de sentido**: o arquivo sai cortado e o mestre fica no espaço; `quick_scan_with_the_crop_on_a_white_page_keeps_the_whole_glass`; `the_frame_and_the_rotation_survive_a_restart`; `a_restart_leaves_no_temporary_file_of_the_manifest`).
- `tests/integration/test_scan_flow.py`: `state_reports_the_completed_pdf_scan`, `second_scan_as_jpg_continues_the_day_sequence` (formato novo de `last_result`); `tests/integration/test_document_flow.py`: `page_scanned_by_the_fake_printer_appears_in_the_document` (campo `crops`).
- `tests/test_composition_root.py`: `state_endpoint_reports_default_settings` (com `jpeg_quality`) e `state_endpoint_reports_an_idle_scanner_without_history`; entra "a raiz restaura a última digitalização".
- `tests/fakes/`: `stored_scans.py`, `document_drafts.py`, `document_service_parts.py`, `stub_document_draft_service.py`, `synthetic_previews.py` (ajudante de polígono girado), `book_on_glass.py` (sem mudança).

**Web (Node, rodados por testes Python)**

- `tests/web/test_page_frame_geometry.py` (409 linhas): **reescrito** para o módulo novo (retângulos viram `read_frame_from_crop`/quadriláteros; entram `validate_frame` com os vetores de validade, `move_corner`, `move_edge`, `rotate_frame`, `turn_frame_*`, `put_frames_in_reading_order`, `suggest_new_frame`); `a_built_frame_is_rounded` fica com cantos. Os vetores vêm de `page-crop-vectors.json`.
- `tests/web/page-frame-editor-harness.js`, `test_page_frame_editor_behaviour.py`, `test_page_frame_editor_edits.py`: o harness ganha o alvo de edição, SVG e botões de alça novos; `a_page_without_a_crop_opens_with_the_whole_page_as_the_frame` e `no_crop_makes_the_whole_page_the_frame` → "sem moldura o editor abre sem molduras" e "Sem corte remove todas"; `apply_sends_the_dragged_frame_as_the_crop`, `apply_with_no_crop_sends_null` (agora `{"crops": []}`), `rotating_a_page_without_a_frame_does_not_talk_about_a_frame`; os demais arrastos de oito alças viram os de quatro cantos e quatro lados.
- `tests/web/document-panel-harness.js`, `test_document_panel_behaviour.py`, `test_document_panel_edits.py`, `test_document_page_policy.py`, `test_page_frame_policy.py`: tile com `<svg>` e o selo, `describe_tile_label` com duas molduras, textos novos.
- `tests/web/scan-page-harness.js`, `test_scan_page_behaviour.py` (15 de giro do último arquivo: o texto de status e a miniatura não mudam, a requisição é a mesma; os de `saved_settings_fill_the_crop_control`, `saved_crop_and_colour_fill_their_controls`, `a_server_without_the_new_settings_leaves_the_crop_off` e `the_scan_button_gets_the_focus_after_toggling_the_auto_crop` ganham a qualidade), `test_scan_quality_policy.py`, `fake-browser.js` (SVG e `setPointerCapture` já existem).
- `tests/web/test_static_assets.py` (3): **`auto_crop_hint_explains_the_frame_of_the_document_mode_and_the_direct_crop_of_the_quick_mode` apagado** e trocado por `the_crop_checkbox_has_no_hint_text` (nenhum `#auto-crop-hint`, nenhuma menção a "Use para fotos e folhas menores que o vidro"); `auto_crop_checkbox_is_off_by_default_and_has_its_label` e `auto_crop_label_names_the_background_removal` ficam; entram os do campo de qualidade; as listas de ids (`SETTINGS_ELEMENT_IDENTIFIERS`, `DOCUMENT_ELEMENT_IDENTIFIERS`) ganham os ids novos.

### 10.3 Testes novos (um conceito por teste, cada um abaixo de 100 ms, escritos antes do código)

- **`PageCrop`:** cada regra de validade do arquivo de vetores (recusados e aceitos); `from_rectangle`; `is_rectangle` e `rotation_to_upright` nas quatro posições do `top_left`; os seis vetores de giro da página e da moldura nos dois sentidos; quatro giros voltam; `seen_on_master` para 0 a 3 quartos; `to_pixel_corners`; `output_size_in_pixels` (média dos lados opostos, mínimo 1).
- **`PageFraming`:** no máximo 2 molduras; `with_crops` descarta a página inteira, ordena (os casos de 6.1: lado a lado, empilhadas, sobrepostas pela metade, empate) e arredonda; `output_count`; `needs_rendering`.
- **Manifesto:** ida e volta com 0, 1 e 2; antigo com `crop`; `crops` com um item inválido; mais de 2; ilegível continua ilegível só pelas regras de antes.
- **Detecção:** as cenas e as regras de 6.3; `detect_crops` combina regiões e por lado (cena de duas fotos nunca chama o por lado; o livro nunca chama o de regiões além do teste de borda); `ignored_region_count`; margem de 1% em retângulo, em retângulo girado e a halving encostado no vidro; ajuste ao eixo a 1,4° e não a 2,2°.
- **Renderer:** sem giro e sem moldura, bytes do scanner; só giro; retângulo (tamanho da região, com e sem giro da página, com os papéis girados); quadrilátero girado 31° (o tamanho da saída, o marcador no canto de cima à esquerda, a densidade); a qualidade chega ao JPEG (tamanho menor a 60 que a 95, mesma imagem); duas molduras, duas saídas na ordem; o mestre de 1200 dpi sintético de poucos pixels não estoura; `MemoryError` sobe; imagem ilegível vira `ScanFailedError`.
- **PDF do documento:** uma página com 2 molduras dá 2 páginas, cada uma com o tamanho físico da região; a ordem das páginas é a das molduras; `page_count` conta as páginas do PDF.
- **Espaço da última digitalização:** gravar (mestre e miniatura antes do manifesto), confirmar, apagar o anterior só depois, `.part` limpo, manifesto ilegível guardado de lado, mestre ausente, nome do arquivo com identificador trocado; queda simulada entre cada passo com `ScriptedFileWriter` (nenhum caso deixa o manifesto citando arquivo inexistente).
- **Pipeline rápido:** sem `auto_crop`, os bytes do scanner (JPG) e um PDF de uma página; com duas fotos, dois arquivos com a mesma data-base e os sufixos `__1` e `__2`, e duas molduras no espaço; a detecção falha e o arquivo sai inteiro; o disco do espaço falha e a digitalização conclui com `is_editable = False` e sem manifesto; a falha na segunda saída deixa a primeira e o espaço anterior.
- **Edição do último arquivo:** girar (molduras acompanham, todos os arquivos regravados, `last_result_revision` sobe); `set_crops` igual = nada escreve; 1 → 2 cria um arquivo; 2 → 1 apaga o segundo só se tamanho e data conferem, senão o mantém e diz; 2 → 0 mantém o 1 inteiro; arquivo ausente = 409 sem escrever; digitalização em andamento = 409; uma digitalização que começa durante a edição responde `last_scan_busy`; falha no meio restaura o manifesto; **a recuperação com `render_pending`** regrava tudo e termina; espaço restaurado alimenta o tracker; sem arquivos de saída, o espaço é descartado.
- **Controladores:** as rotas e códigos de 5.3 e 5.4, o corpo malformado (`invalid_crop`, `invalid_page_rotation`), os cabeçalhos de cache, a visão ampliada com identificador errado = 404.
- **JavaScript (Node):** a geometria completa (6.1 e 8.3), o tile (SVG, selo, rótulo), o editor (abrir com 0, 1 e 2 molduras; arrastar canto, lado, mover, girar; Adicionar, Remover, Girar moldura, Selecionar; Aplicar envia `PUT` com a lista, Sem corte envia `[]`; Detectar com achado, sem achado e com "mais de 2"; Girar mantém o rascunho; Cancelar descarta; Esc; foco de volta; alvo que some fecha; teclas globais inertes; Espaço nunca digitaliza; movimento inválido ignorado com o texto), o painel do modo Rápido (miniatura com molduras, Ampliar abre o editor com o alvo certo, Girar, os textos de apagado e mantido, desabilitado sem mestre e durante a digitalização), o campo de qualidade (valor visível, grava ao soltar, 422 volta ao salvo).
- **Integração com o simulador** (HOME temporário e outra porta; `DIGITALIZADORA_SIMULATOR_SCENE`): modo Documento, `photos_two` com corte ligado: duas molduras na página (cantos a ±0,02 da verdade e −30° e −2° a ±2°), mestre inalterado byte a byte, Salvar gera um PDF de 2 páginas em pé (os marcadores nos cantos certos) com o tamanho físico das fotos; `photos_one` no modo Rápido: um arquivo cortado, um mestre no espaço; Aplicar duas molduras cria o segundo arquivo; remover apaga; girar regrava; reiniciar o servidor restaura o painel; `kill -9` depois de uma edição com `render_pending` termina na partida; qualidade 60 dá um arquivo menor que 90 na mesma foto; 1200 dpi continua seguro (com 1 foto, memória e tempo anotados).

## 11. Tarefas

Cada tarefa é feita por TDD (teste vermelho, código, teste verde), termina com `.venv/bin/python -m pytest -q` verde e `.venv/bin/ruff check src tests` limpo e **um commit local** com a mensagem terminando em `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` (nunca `git push`; nunca `md.md`; nenhuma imagem de `scratchpad` ou de `images/` entra no repositório). A ordem é a das dependências: servidor primeiro, depois a interface. Para a suíte continuar verde a cada commit, o corpo do documento leva **provisoriamente** `crop` (derivado) além de `crops`, a rota `PUT …/crop` continua como apelido e `last_result` continua com `file_name` e `size_in_bytes`; T64 e T65 os removem (com seus testes). O `crop` provisório do corpo é a caixa (`left`, `top`, `right`, `bottom`) da primeira moldura quando há **exatamente uma** e ela é retangular com os papéis normais; senão, `null`. Nenhuma tarefa usa a impressora real.

### T51: O quadrilátero de corte (`PageCrop`), só no domínio
**Arquivos:** `domain/page_crop.py` (o retângulo de hoje passa a se chamar `RectangleCrop` e continua servindo ao resto até T52; entra o `PageCrop` novo, `CropCorner` e `RectangleEdges`), `domain/pixel_region.py` (`PixelCorner`), `tests/domain/test_page_crop.py` (os testes de hoje passam a `RectangleCrop`; o arquivo novo `tests/domain/test_page_crop_quadrilateral.py` cobre o `PageCrop`), `tests/fixtures/page-crop-vectors.json` (novo; o antigo fica até T61), `tests/fakes/page_crops.py` (novo), `tests/domain/test_immutable_models.py`.
**Interfaces:** 4.1 (`PageCrop`, `CropCorner`, `RectangleEdges`, `is_rectangle`, `rotation_to_upright`, `turned_clockwise`, `turned_counterclockwise`, `with_output_turned_clockwise`, `seen_on_master`, `to_pixel_region`, `to_pixel_corners`, `output_size_in_pixels`) e 6.1 (os vetores). Sem dependências.

### T52: Até 2 molduras por página, ponta a ponta (migração do retângulo para a lista de quadriláteros)
**Arquivos:** `domain/page_framing.py` (`crops`, `MAXIMUM_CROPS_PER_PAGE`, `put_in_reading_order`, `with_crops`, `crops_on_master`, `crops_from_master`), `domain/document_draft.py` (`output_page_count`), `repositories/document_manifest_codec.py` (`crops` e o `crop` antigo), `controllers/document_body.py` (`crops` e o `crop` provisório), `services/document_draft_store.py` (`set_page_crops`), `services/document_draft_service.py` (`set_page_crops`, `detect_page_crops`), `services/document_page_crop_detector.py` (`CropDetectionResult` com a lista, ainda com uma só moldura vinda do detector atual), `services/document_page_capture.py`, `services/document_page_renderer.py` (só o caminho retangular, com `rotation_to_upright`), `controllers/document_controller.py` (`PUT …/crops`; `PUT …/crop` como apelido), `application_factory.py`, **apagar** `RectangleCrop`, e os testes de 10.2 que citam esses símbolos (`tests/domain/test_page_framing.py`, `tests/repositories/test_document_manifest_codec.py`, `tests/controllers/test_document_*`, `tests/services/test_document_*`, `tests/integration/test_frame_and_rotation_flow.py`).
**Interfaces:** 4.1 (`PageFraming`), 4.2 (manifesto), 4.3 (`set_page_crops`, `detect_page_crops`), 5.1, 5.3. É a maior tarefa de refatoração: nada muda para quem usa a tela (continua uma moldura retangular). Depende de T51.

### T53: Qualidade do JPEG configurável
**Arquivos:** `domain/image_adjustment.py` (`jpeg_quality`, `rendered_size_factor`), `services/jpeg_reencoding.py` (`read_encoding_options(source, jpeg_quality)`), `services/document_page_renderer.py` e `services/rendered_page_source.py` (a qualidade vem do pedido), `services/document_pdf_assembler.py` (`DocumentAssemblyInput.jpeg_quality`), `services/document_finalizer.py` (`ensure_capacity(draft, jpeg_quality)`), `services/document_draft_service.py` (`finalize(jpeg_quality)`), `domain/document_draft.py` (`estimate_document_size_in_bytes`), `services/storage_guard_service.py`, `services/application_settings_service.py`, `repositories/json_application_settings_repository.py`, `controllers/settings_controller.py`, `controllers/settings_body.py`, `controllers/document_controller.py` (o `finalize` passa a qualidade salva), `services/image_adjustment_service.py` (a qualidade do corte destrutivo, até T58), testes de 10.2.
**Interfaces:** D23 e 8.1 (servidor). Depende de T52.

### T54: Detecção de regiões girada e `detect_crops`
**Arquivos:** `services/photo_region_detection.py` (novo; leva o que serve de `paper_region_detection.py`, que é **apagado**), `services/page_crop_detection_service.py` (`DetectedCrops`, `detect_crops`; saem `detect_crop_to_apply` e `detect_crop_to_suggest`), `services/image_adjustment_service.py` (usa a primeira moldura de `detect_crops` até T58), `services/document_page_capture.py` e `services/document_page_crop_detector.py` (passam a guardar as duas molduras e a contagem de ignoradas), `tests/fakes/photo_scenes.py` (novo), `tests/fakes/synthetic_previews.py` (polígono girado), `tests/services/test_photo_region_detection.py` (novo, no lugar de `test_paper_region_detection.py`), `tests/services/test_page_crop_detection_service.py`, `tests/services/test_document_page_capture.py`, `tests/services/test_document_page_crop_detector.py`.
**Interfaces:** 4.3 (`PhotoRegions`, `detect_photo_regions`, `DetectedCrops`, `PageCropDetectionService.detect_crops`) e 6.3 (passos, constantes, combinação, testes). Depende de T52.

### T55: Render de quadriláteros e PDF com várias páginas por foto
**Arquivos:** `services/page_framing_renderer.py` (novo; é `document_page_renderer.py` renomeado: `FrameRenderRequest`, caminho do retângulo, caminho de `transform(QUAD)`), `services/rendered_page_source.py` (por moldura), `services/document_pdf_assembler.py` (uma fonte por `(página, moldura)`), `services/document_finalizer.py` e `domain/document_draft.py` (`DocumentFinalizationResult.page_count` = páginas do PDF), `tests/services/test_page_framing_renderer.py`, `tests/services/test_rendered_page_source.py`, `tests/services/test_document_pdf_assembler.py`, `tests/services/test_document_finalizer.py`.
**Interfaces:** 4.3 (`PageFramingRenderer`, `FrameRenderRequest`), 6.2 e 6.4. Depende de T52 e T53.

### T56: O modo Documento com duas molduras
**Arquivos:** `controllers/document_controller.py` (`POST …/crops/detect` com `crops_detected` e `ignored_region_count`; o corpo de `PUT …/crops` com no máximo 2), `application_factory.py` (padrão de validação `…/crops(/detect)?`), `controllers/error_message_catalog.py` (`invalid_crop`), `tests/controllers/*`, `tests/integration/test_frames_flow.py` (cenas com duas fotos pelo `ScriptedScannerGateway`).
**Interfaces:** 5.3. Depende de T54 e T55.

### T57: O espaço da última digitalização (domínio, portas, repositório)
**Arquivos:** `domain/last_scan.py` (novo), `domain/stored_scan.py`, `domain/ports.py` (`QuickScanSlotRepository`, `describe_saved_scan`, `delete_saved_scan`), `domain/errors.py` (`LastScanNotEditableError`, `LastScanBusyError`, `UnreadableQuickScanError`), `repositories/quick_scan_manifest_codec.py` e `repositories/file_system_quick_scan_slot_repository.py` (novos), `repositories/file_system_scan_output_repository.py`, testes de 10.2 (`tests/repositories/*`, `tests/domain/test_immutable_models.py`) e as quedas simuladas de 10.3.
**Interfaces:** 4.1 (`LastScan`, `SavedScanFile`, `QuickScanSlot`, `QuickScanMasterFiles`), 4.2, 7.1. Depende de T52.

### T58: O pipeline do modo Rápido não destrutivo
**Arquivos:** `services/scan_encoder.py` (`encode_master`, `wrap_output`, `EncodedMaster`, `OutputIdentity`), `domain/encoded_scan.py`, `services/quick_scan_output_renderer.py` (novo), `services/scan_output_service.py` (7.2; `ScanOutputParts`), `services/scan_progress_tracker.py` e `domain/scan_progress.py` (`last_scan`, `restore_last_scan`, marcas de edição, `LastScanBusyError` no `begin_scan`), `services/scan_service.py` (`ensure_scan_can_start`), `controllers/scan_controller.py`, `controllers/document_controller.py` (`add_page` usa `ensure_scan_can_start`), `controllers/scan_result_body.py` (`describe_last_scan`, com `file_name` e `size_in_bytes` provisórios), `controllers/state_controller.py`, `services/document_page_capture.py` (usa `encode_master`), **apagar** `services/image_adjustment_service.py` e `services/master_jpeg_service.py` com seus testes, `composition_root.py`, testes de 10.2.
**Interfaces:** 4.1, 4.3 (`ScanEncoder`, `QuickScanOutputRenderer`, `ScanOutputService`), 5.2, 7.2. Depende de T55 e T57.

### T59: Editar a última digitalização (servidor)
**Arquivos:** `services/last_scan_edit_service.py` e `services/last_scan_view_service.py` (novos), `controllers/last_scan_controller.py` (rotação, `crops`, `crops/detect`), `controllers/preview_controller.py` (miniatura girada e visão ampliada), `controllers/error_message_catalog.py`, `application_factory.py` (padrões `/api/scans/last/crops`), `composition_root.py` (`restore_after_start` depois do rascunho), **apagar** `services/scan_content_rotator.py`, `services/last_scan_rotation_service.py`, `read_saved_scan` e os testes deles, `tests/services/test_last_scan_edit_service.py`, `tests/fakes/stub_last_scan_edit_service.py`, `tests/controllers/test_last_scan_controller.py`.
**Interfaces:** 4.3 (`LastScanEditService`, `LastScanEditResult`, `LastScanViewService`), 5.4, 5.5, 7.3 a 7.6. Depende de T58.

### T60: Simulador com fotos sintéticas e integração
**Arquivos:** `simulator/fake_escl_scanner_app.py` e `simulator/__main__.py` (9), `tests/simulator/test_fake_escl_scanner_app.py` (as cenas), `tests/integration/test_frames_flow.py`, `tests/integration/test_quick_scan_slot_flow.py`, `tests/integration/test_scan_flow.py`, `tests/integration/test_document_flow.py`.
**Interfaces:** D29 e os cenários de 10.3 (integração). Depende de T56 e T59.

### T61: Geometria do quadrilátero (JavaScript puro)
**Arquivos:** `web/static/page-frame-geometry.js` (reescrito, 8.3), `tests/web/document-page-policy-harness.js`, `tests/web/test_page_frame_geometry.py` (reescrito), apagar `tests/fixtures/page-crop-rotation-vectors.json`.
**Interfaces:** a lista de funções de 8.3 e os vetores de `page-crop-vectors.json`. Depende de T51 (independente do resto do servidor; pode andar em paralelo a T52 em diante).

### T62: A caixa Ajustes: qualidade do JPEG e sem a dica
**Arquivos:** `web/static/index.html` (campo de qualidade, sem `#auto-crop-hint`), `web/static/application.js`, `web/static/scan-quality-policy.js`, `web/static/application.css`, `tests/web/scan-page-harness.js`, `tests/web/test_scan_page_behaviour.py`, `tests/web/test_scan_quality_policy.py`, `tests/web/test_static_assets.py`.
**Interfaces:** 8.1. Depende de T53.

### T63: Molduras no tile do modo Documento
**Arquivos:** `web/static/document-panel.js` (`<svg>`, selo, "N molduras", lê `crops`), `web/static/document-page-policy.js` (`describe_tile_label`), `web/static/application.css`, `tests/web/document-panel-harness.js`, `tests/web/test_document_panel_behaviour.py`, `tests/web/test_document_page_policy.py`.
**Interfaces:** 8.2. Depende de T52 e T61.

### T64: O editor de molduras (quatro cantos, lados, duas molduras) e o fim do compat do documento
**Arquivos:** `web/static/page-frame-editor.js` (alvo de edição, alças, adicionar, remover, girar moldura, selecionar, detectar), `web/static/index.html` (diálogo), `web/static/document-panel.js` (monta o alvo do documento), `web/static/document-page-policy.js` (textos), `web/static/application.css`, `tests/web/page-frame-editor-harness.js`, `tests/web/test_page_frame_editor_behaviour.py`, `tests/web/test_page_frame_editor_edits.py`; no servidor, **sai** o `crop` provisório do corpo e o apelido `PUT …/crop` (e os testes dele).
**Interfaces:** 8.3 e 8.5. Depende de T56, T61 e T63.

### T65: O painel do modo Rápido com moldura, Ampliar e Girar
**Arquivos:** `web/static/index.html` (invólucro da miniatura, **Ampliar**, lista de arquivos), `web/static/application.js` (alvo do último arquivo, estado novo, textos de apagado e mantido), `web/static/scan-trigger-policy.js`, `web/static/application.css`, `tests/web/scan-page-harness.js`, `tests/web/test_scan_page_behaviour.py`; no servidor, **saem** `file_name` e `size_in_bytes` de `last_result`.
**Interfaces:** 8.4 e D25. Depende de T59 e T64.

### T66: Documentação
**Arquivos:** `README.md` (molduras livres, até 2 fotos, Ampliar nos dois modos, qualidade, mestre guardado), `docs/acceptance-checklist.md` (partes novas), este documento (status "implementado" e as notas do que saiu diferente).
Depende de T65.

### T67: Aceitação no simulador, com o Chrome sem janela (sem a impressora)
Aplicativo numa porta livre e `HOME` temporário, o simulador em outra porta com `DIGITALIZADORA_SIMULATOR_SCENE=photos_two` e depois `photos_one` e `sheet`; o Chrome sem janela do `~/.cache/puppeteer` dirigido pelo cliente CDP de `scratchpad/real-browser/cdp.js` (a mesma ferramenta da rodada anterior; os scripts ficam fora do repositório). Roteiro, anotando tempo e resultado: (1) **Documento, corte ligado, 150 dpi, `photos_two`:** duas molduras, uma azul contínua e uma laranja tracejada, nos dois tiles; **Ampliar**: arrastar um canto, um lado, mover, girar a moldura pela alça e por teclado; **Adicionar moldura** (a terceira é recusada), **Remover moldura**, **Girar moldura ↻**, **Detectar automaticamente**, **Sem corte**, **Cancelar**; **Aplicar**; **Salvar (Enter)**: PDF de 2 páginas em pé, com o tamanho das fotos. (2) **Rápido, corte ligado, `photos_two`:** dois arquivos; **Ampliar** no painel; mover uma moldura e **Aplicar**; **Adicionar** e **Remover** (o arquivo a mais é apagado e a tela diz); **Girar ↻**; trocar a qualidade para 60 e conferir o tamanho; reiniciar o servidor e ver o painel de volta; `kill -9` com `render_pending`. (3) **Rápido, corte desligado:** a imagem inteira; desenhar uma moldura à mão e aplicar. (4) **Tampa branca sem foto:** nenhuma moldura. (5) **409** durante uma digitalização (edições respondem 409; a visão ampliada continua abrindo). (6) 600 e 1200 dpi com `photos_one`: tempo e pico de memória do **Aplicar** (esperado, pela seção 3.1, de 1 a 4 s e menos de 1,1 GB). (7) Celular (390 px) e tema escuro. Anotar tudo.

### T68: Aceitação na impressora real (só o agente a quem isso foi pedido; uma digitalização por vez)
Com as duas fotos da cena de aceitação no vidro e depois o livro, num aplicativo novo numa porta livre e `HOME` temporário: modo Documento e modo Rápido, 100 e 300 dpi, corte ligado. Esperado: duas molduras com os cantos da tabela de 3.2 a ±0,02; A (30°) sai reta e de cabeça para baixo até o **Girar moldura ↻**; B (−2°) sai reta; o livro continua enquadrado pelo detector por lado; os arquivos do modo Rápido batem com as molduras e o mestre do espaço tem os bytes do scanner. Anotar as frações detectadas para ajustar as constantes de 6.3 se for preciso.

## 12. Riscos e pontos em aberto

- **Fotos coladas.** Com menos de uns 2,7 mm entre elas, viram uma moldura só. O editor resolve com **Adicionar moldura**; uma segunda passada com erosão adaptativa fica fora do escopo (o mesmo vale para três fotos: a terceira é ignorada e a tela avisa).
- **Foto com borda branca sobre a tampa branca** (polaroide, foto de página branca): o detector acha só a parte colorida. É o mesmo "branco sobre branco" do livro; a moldura é ajustável.
- **`QUAD` é bilinear.** Para um quadrilátero muito diferente de um paralelogramo, a imagem endireitada tem uma pequena distorção. Num scanner plano isso só aparece se você arrasta os cantos de propósito.
- **O mestre do modo Rápido dura até a digitalização seguinte.** Quem quer ajustar duas digitalizações seguidas deve ajustar a primeira antes da segunda (ou usar o modo Documento, que guarda tudo). É a consequência de "um espaço, substituído pela seguinte".
- **Apagar o arquivo de uma moldura removida.** Só se o arquivo continua como foi gravado (tamanho e data); mesmo assim é apagar um arquivo seu, sem lixeira (a lixeira do macOS exigiria uma dependência ou um `osascript`). A tela diz o nome do arquivo apagado e do mantido.
- **Painel restaurado depois de reiniciar** pode mostrar uma digitalização de ontem; a hora fica visível. Se ao menos um arquivo existe, o painel volta.
- **Uma queda no meio de "Aplicar" com 2 molduras novas** pode deixar um arquivo a mais na pasta (7.4, passo 3). É raro, aparece no log e custa apagar um arquivo.
- **Qualidade padrão.** O scanner entrega JPEG de qualidade 50; regravar acima de uns 85 só engorda (3.4). Fica 90, como foi sugerido, mas 75 daria arquivos 25% menores sem diferença visível; é uma troca de uma linha em `DEFAULT_JPEG_QUALITY` se você preferir.
- **Aplicar a 1200 dpi pode levar alguns segundos** (pior caso medido: 3,7 s de `transform` mais a codificação); a tela já desabilita os botões durante qualquer edição e mostra "Regravando…".
- **Edição em duas abas do mesmo aparelho** ao mesmo tempo: a última gravação vale e a outra aba relê o estado (revisão).
- **O editor fica mais complexo** (dez alças, duas molduras, SVG). A cobertura vem dos testes de geometria no Node (puros) e da conferência no Chrome sem janela (T67); o risco restante é de ergonomia no toque, onde a alça de girar a moldura pode ficar apertada em telas pequenas (a área de toque tem 44 px).

## 13. Notas da implementação do servidor (T51 a T60)

O servidor está feito e testado com o simulador; a interface (T61 a T66) não foi tocada. Baseline anterior: 3263 testes; agora **3736 passam** (17 pulados) e `ruff` está limpo. Nada foi enviado ao GitHub e a impressora real não foi usada.

### 13.1 O que saiu como o desenho dizia

Quadrilátero (`PageCrop`, `CropCorner`, `RectangleEdges`, `find_quadrilateral_problem` com os mesmos nomes de problema dos vetores), `PageFraming.crops` em ordem de leitura, manifesto com `crops` e leitura do `crop` antigo (uma moldura retangular), `PageFramingRenderer` com `transform(QUAD)` lendo direto do mestre, um PDF por moldura, `jpeg_quality` de ponta a ponta (422 `invalid_settings`, arquivo antigo carrega com 90), detector de regiões em Pillow puro (`photo_region_detection.py`) com o por lado de reserva, espaço da última digitalização (`quick-scan/`, manifesto como ponto de confirmação), `LastScanEditService` (girar, `crops`, detectar, recuperação na partida), `LastScanViewService`, rotas novas, textos novos, simulador com `photos_one` e `photos_two`. Os vetores compartilhados estão em `tests/fixtures/page-crop-vectors.json` (o JavaScript os lê na T61; o arquivo antigo de retângulos fica até lá).

### 13.2 Desvios e escolhas pequenas (todos dentro dos contratos)

- **`PageFraming.with_crops` recusa mais de 2 molduras** (`InvalidCropError`) em vez de "manter as 2 primeiras": quem recebe uma lista longa (API, 422) ou a corta com aviso (manifesto) sabe o que está fazendo; o domínio não adivinha. Molduras que cobrem a página inteira são descartadas **antes** da conta.
- **`detect_photo_regions` devolve as regiões da maior para a menor**, e quem põe em ordem de leitura é o `PageCropDetectionService`, com `put_in_reading_order` do domínio (uma só implementação da regra D15, a mesma que o `PageFraming` usa). O `PhotoRegions.ignored_count` conta **todas** as regiões plausíveis além das 2 primeiras (o protótipo parava ao achar 2).
- **`FrameRenderRequest` e `PageFramingRenderer` entraram junto com a qualidade (T53)**, não na T55: sem o pedido único o `RenderedPageSource` passaria de 3 parâmetros. A T55 ficou só com o `QUAD` e o PDF de várias páginas, no mesmo commit.
- **`ScanOutputParts.scan_identifier_factory`** (injeção do gerador do identificador) e **`LastScanEditParts.thumbnail_service`** (refazer a miniatura do mestre quando ela falta na recuperação) são campos a mais nos agrupamentos de dependências; os construtores continuam com 3 parâmetros ou menos.
- **`UnreadableQuickScanError` herda de `SavedScanUnreadableError`** e por isso usa o código `saved_scan_unreadable` (um espaço ilegível é guardado de lado e nunca chega à API como erro próprio).
- **`describe_last_scan` (módulo `last_scan_body.py`) leva `file_name` e `size_in_bytes` provisórios**, como a seção 11 previa, até a T65; o corpo do documento leva `crop` provisório e a rota `PUT …/crop` segue como apelido até a T64.
- **A resposta de `POST /api/scans/last/rotation`, `PUT …/crops` e `POST …/crops/detect` não leva a revisão**; a página a lê do estado (`last_result_revision`), como no desenho.
- **`ScanService.is_scan_in_progress()` ficou** ao lado de `ensure_scan_can_start()`: as edições do documento continuam só proibidas durante uma digitalização (`scan_already_running`) e não por uma edição do último arquivo.
- **Mensagens de aviso da detecção** (mais de 2 fotos, sem achado) continuam por conta da tela: o servidor devolve `crops_detected` e `ignored_region_count`.

### 13.3 O que mudou de comportamento sem estar no desenho

- **O piso de área de 10% para 3% faz uma folha branca sobre a tampa branca com um bloco colorido grande (um logotipo de 3% ou mais da página) ser enquadrada pelo bloco.** O desenho aceita o caso da polaroide (branco sobre branco acha só a parte colorida); com o modo Rápido agora aplicando o palpite, vale a atenção: a moldura aparece no painel e **Ampliar** a corrige, e o mestre está guardado, mas quem digitaliza folha de texto com logotipo grande deve deixar **Cortar automaticamente** desligado. Os testes que usavam uma página branca com um bloco vermelho de 4% para "sem folha" passaram a usar uma página branca lisa.
- **Uma capa azul-marinho com uma figura clara sobre tampa escura** (cena de teste antiga) antes não era achada porque o anel em volta dava 25,3% de primeiro plano (limite 25%) por causa do halo do JPEG; no detector novo o anel é um polígono sem o contorno e a capa **inteira** é enquadrada. É o comportamento desejado ("não cortar até a figura"), e o teste agora confere isso.
- **O corte do modo Rápido deixou de ser destrutivo e de depender de um detector cauteloso:** com **Cortar automaticamente** ligado, cada moldura achada é um arquivo; desligado, o arquivo é a imagem inteira, e o mestre fica sempre no espaço.

### 13.4 Números medidos (servidor real em `HOME` temporário, simulador em outra porta, sem a impressora)

Detecção, tempo por digitalização (o mesmo detector roda no Documento e no Rápido): as três `photos-*.jpg` reais dão **duas regiões em 14 a 21 ms**, com os cantos da tabela 3.2 mais a margem de 1%; os quatro livros ficam com a moldura retangular do detector por lado em **6 a 12 ms**; o cartão de 3.png (a uns 31°) dá uma região em 12 ms. Os testes marcados com `DIGITALIZADORA_REAL_SCANS_FOLDER` e `DIGITALIZADORA_CARD_IMAGE` (a imagem de pessoas nunca entra no repositório; sem a variável os testes pulam) passam com essas imagens.

1200 dpi, cor, mestre de 10200 × 14032 (143 MP, 2,5 MB), **pico de memória do processo inteiro** (linha de base do servidor: 72 MB):

| Ação (Aplicar, mesma rota do modo Rápido) | Saída | Tempo | Pico |
|---|---|---|---|
| Quadrilátero de 90% da página, a 4° | 9237 × 12607 (116 MP) | **3,44 s** | **1071 MB** |
| Quadrilátero de 60% a 25° | 7398 × 7859 (58 MP) | 1,97 s | 857 MB |
| Girar a página (com moldura de 60%) | 7859 × 7398 | 2,06 s | 848 MB |
| Detectar automaticamente (um arquivo) | | 1,36 s | 738 MB |
| Duas molduras (40% a 10° e 30% a −7°) | dois arquivos | 0,66 s | 645 MB |

Em cinza: 1,63 s e **318 MB** (90% a 4°), 0,81 s e 332 MB (60% a 25°), 0,92 s ao girar, 0,53 s ao detectar, 0,26 s para as duas molduras. Uma digitalização com uma foto a 1200 dpi (simulador, cena `photos_one`): 1,0 a 2,2 s de ponta a ponta, 741 MB de pico; Salvar de um documento de uma página com uma moldura torta: 1,19 s e 762 MB. Tudo bate com a seção 3.1 (734 MB e 3,7 s no pior caso).

Qualidade (75 dpi, duas fotos, mesma cena): a 60 os dois arquivos saem com 9737 a 11782 bytes e a 95 com 29948 a 38176; a 1200 dpi, uma foto: 648 KB a 60 e 1,64 MB a 95. Regravar um arquivo (Aplicar, Girar) lê a qualidade **salva** na hora, como D23.

### 13.5 Como rodar os testes que dependem de arquivos de fora

```
DIGITALIZADORA_REAL_SCANS_FOLDER=<pasta com 1-color-100.jpg … photos-3-gray-150.jpg> \
DIGITALIZADORA_CARD_IMAGE=<caminho do cartão a uns 30°> \
.venv/bin/python -m pytest -q tests/services/test_page_crop_detection_service.py
```

### 13.6 Pontos que seguem abertos para a interface

A rota provisória e o `crop` do corpo saem na T64; `file_name` e `size_in_bytes` de `last_result` saem na T65; a leitura do arquivo `page-crop-rotation-vectors.json` pelos testes do Node vira a de `page-crop-vectors.json` na T61.

## 14. Notas da implementação da interface (T61 a T65) e aceitação no simulador (T67)

A interface está feita e testada. Baseline anterior: 3736 testes; agora **4039 passam** (17 pulados) e `ruff` está limpo. Os testes novos da interface rodam no Node (cada teste abaixo de 100 ms; o processo do Node de cada módulo é o único custo, como antes). Nada foi enviado ao GitHub, a impressora real não foi usada e a porta 8765 não foi tocada.

### 14.1 O que saiu como o desenho dizia

Moldura como quadrilátero (`page-frame-geometry.js` reescrito, os vetores de `page-crop-vectors.json` lidos pelo Node: giro da página, giro só da saída, quatro giros voltam ao início e todos os casos de validade com os mesmos nomes de problema do Python); sobreposição em SVG com o escurecimento `evenodd`, um polígono por moldura (1 azul contínua, 2 laranja tracejada), selo com o número, "2 molduras" em texto no tile; o editor com quatro cantos livres, quatro lados (andam na perpendicular), mover, alça de girar a moldura, **Adicionar**, **Remover**, **Girar moldura ↻**, **Detectar automaticamente**, **Sem corte**, **Girar ↻**, **Cancelar** e **Aplicar**; o teclado (Tab, setas, Shift) e os anúncios; o painel do modo Rápido com miniatura, molduras, lista de arquivos, **Girar ↻** e **Ampliar** (o mesmo editor, sem cópia); o campo de **Qualidade do JPEG** e a dica removida.

### 14.2 Desvios e escolhas pequenas (todos dentro dos contratos)

- **O editor recebe o dono em cada abertura, não um `editor_services` fixo (D25).** `PageFrameEditor.open({owner, target_identifier, action_origin})`; o dono é o `DocumentPanel` ou o `LastScanPanel` e dá `find_target`, `attempt_edit`, `report_failure`, `can_edit`, `announce` e `restore_focus`. As respostas entram por `handle_target_change(owner)`, que ignora quem não é o dono da sessão. O alvo leva também `progress_text` ("Regravando…" no modo Rápido, nada no Documento) e `describe_application(frame_count)` (o painel do modo Rápido já escreveu o que fez nos arquivos e devolve `null`).
- **`move_corner`, `move_edge` e `rotate_frame` devolvem `null` quando o resultado é inválido**, em vez de "a moldura de antes". Assim o arraste fica no último lugar bom em vez de saltar para o início, e só ao soltar a tela diz "Esse movimento deixaria a moldura torta demais. Ela ficou como estava." As setas usam o mesmo `null`.
- **`describe_frame(frame, {label, surface})`** leva o tamanho da imagem ampliada: o ângulo "inclinada N° para a esquerda/direita" só é certo em pixels. Um quadrilátero cujo lado de cima aponta mais para um lado do que para cima diz também "Lado de cima da foto à direita/à esquerda/embaixo".
- **As duas molduras ficam em ordem de leitura no rascunho do editor**, como o servidor as guarda: a ordem muda ao soltar o arraste ou depois de uma seta, e a moldura selecionada continua a mesma (a numeração 1 e 2 acompanha).
- **"Mover a moldura" e "Selecionar moldura N" são botões do tamanho do palco recortados pelo polígono da moldura (`clip-path`)**: o ponteiro só os alcança dentro dela, e as duas molduras podem se sobrepor sem problema. A ordem do Tab é cantos, lados, mover, girar, selecionar, botões (com duas molduras **Adicionar moldura** está desabilitado e o Tab o pula).
- **Arquivos novos:** `frame-overlay.js` (as molduras sobre uma imagem, usado pelo tile, pelo painel e pelo editor), `frame-dialog-policy.js` (textos e regras do editor), `last-scan-policy.js` (endereços e textos do último arquivo) e `last-scan-panel.js` (`LastScanPanel`, o painel do modo Rápido). O `ScanPage` só os liga. O texto da dica de limites (duas fotos muito juntas) fica no diálogo, em letra pequena e no `aria-describedby`.
- **Uma digitalização espera qualquer ajuste em curso** (`can_start_capture`), no modo Documento e no Rápido, para a resposta nunca ser `last_scan_busy` (409) por culpa da tela. O seletor de modo também fica desabilitado durante um ajuste do último arquivo.
- **Estado antigo nunca desfaz um ajuste.** Cada ajuste que termina sobe um contador (`edit_serial`); um `GET /api/state` pedido antes do fim do ajuste, ou que chega durante um, é ignorado. A miniatura recarrega logo depois de um ajuste feito aqui (versão `revisão-serial`) e o estado novo é pedido na hora.
- **A caixa de qualidade grava ao soltar** (`change`) e mostra o número enquanto mexe (`input`); uma recusa do servidor devolve o controle ao valor salvo. Os outros ajustes levam a qualidade salva no corpo, como já levavam o resto das configurações.
- **O texto de abertura e a alça de girar são calculados de novo quando a imagem carrega**, porque só então se conhece o tamanho em pixels (o ângulo "inclinada N°" e a distância da alça dependem dele); um texto que o usuário já provocou não é trocado. Um segundo dedo em outra alça não toma o arraste do primeiro.
- **O selo do número fica logo dentro do primeiro canto** (4 px para dentro), para não ficar debaixo da alça do canto.
- **Não foi feita a limpeza do servidor da T64 e da T65** (o `crop` provisório do corpo do documento, o apelido `PUT …/crop` e `file_name`/`size_in_bytes` de `last_result`): a tela não os usa mais, e tirá-los mexe em testes de integração do servidor, fora de `web/static` e `tests/web`. Ver 14.5.

### 14.3 Textos que ficaram errados e foram trocados

Saiu a dica da caixa de corte (e o `aria-describedby`). A dica do painel virou "Ajustes regravam os arquivos salvos."; "Arquivo" virou "Arquivos" (um nome por linha); o status do painel passou a se chamar `last-scan-status` e diz "Regravando…", "Moldura aplicada: 2 arquivos.", "Corte removido: 1 arquivo.", "Molduras detectadas: 2 arquivos.", "Novo arquivo: …", "O arquivo … foi apagado porque agora há só 1 arquivo." e "Mantive … porque ele foi alterado depois de gravado." A linha de status da página diz "Pronto! 2 arquivos salvos: A e B". `README.md` e `docs/acceptance-checklist.md` (parte D) ganharam as partes novas.

### 14.4 Aceitação no simulador (T67), com o Chrome sem janela

Aplicativo numa porta livre (18952) com `HOME` temporário, simulador em outra (18951) com `DIGITALIZADORA_SIMULATOR_SCENE=photos_two`; o Chrome sem janela do `~/.cache/puppeteer` dirigido pelo cliente CDP de antes (os scripts ficam no scratchpad, fora do repositório). Tudo passou, sem erro no console e sem exceção:

- **Modo Rápido, 150 dpi, corte ligado:** painel com 2 molduras (a 2 tracejada, o polígono casa com o contorno desenhado a ±0,01 e o quadro da miniatura tem a proporção da imagem), dois arquivos; o arquivo 1 saiu endireitado, com o quadradinho magenta em cima à esquerda e o verde em cima à direita.
- **Ampliar:** as alças ficam sobre os cantos (±0,01 do que o servidor guarda); arrastar um canto com o mouse muda o polígono; **Aplicar** regravou só o arquivo da moldura mudada (64924 para 56384 bytes) e o painel disse "Moldura aplicada: 2 arquivos."; toque (eventos de toque do CDP) moveu um canto; o lado, o interior e a alça redonda de girar também arrastam; **Girar moldura ↻**, **Detectar automaticamente** ("Achei 2 molduras e salvei.") e **Cancelar** respondem; teclado: Enter abre com o foco em **Mover a moldura**, Tab segue a ordem do desenho, setas e Shift+setas movem um canto e a tela diz a posição, Esc fecha e devolve o foco a **Ampliar**.
- **Remover e Adicionar:** clicar dentro da moldura 2 a seleciona; remover e aplicar apagou o arquivo 2 e o painel disse por quê; adicionar e aplicar criou de novo o arquivo 2 ("Novo arquivo: …"); com duas molduras **Adicionar** fica desabilitado.
- **Girar ↻** no painel: rotação 90, miniatura rotacionada, arquivos regravados; quatro giros voltam a 0. **Qualidade 60** (30 vezes seta para a esquerda no controle, salva em `/api/settings`): os arquivos regravados caíram de 64924 e 54668 bytes para 31187 e 28508.
- **Corte desligado:** a digitalização é a imagem inteira, sem molduras; **Ampliar** abre com o foco em **Adicionar moldura**; uma moldura desenhada à mão e aplicada vira 1 moldura.
- **Modo Documento, corte ligado:** o tile mostra as 2 molduras, "2 molduras" e o rótulo "…com 2 molduras de corte (2 páginas no PDF)"; **Salvar** (Enter, confirmar) gravou um PDF de **2 páginas**; o painel do modo Rápido some.
- **Celular (390 px, tema escuro):** sem rolagem horizontal; o diálogo rola por dentro.

Não foi repetido aqui o que o servidor já mediu (13.4): 600 e 1200 dpi, memória, kill -9 com `render_pending`.

### 14.5 Pontos que seguem abertos

- ~~**Limpeza do servidor (T64 e T65)**~~ feita na revisão (15.2).
- **Aceitação na impressora real (T68)**, com as duas fotos e depois o livro.
- **Ergonomia no toque:** resolvida na revisão (15.4): a alça de girar fica a pelo menos 52 px do lado de cima e, sem espaço fora da página, passa para dentro da moldura.
- **Duas molduras que se sobrepõem** têm o botão de selecionar da outra por baixo do da selecionada: clicar na parte comum move a selecionada, e a outra se seleciona pela parte só dela ou pelo teclado.


## 15. Revisão das molduras livres (achados verificados e aplicados)

Baseline antes da revisão: 4039 testes; depois, **4081 passam** (17 pulados; com as variáveis de fora ligadas, 4093 passam e 5 pulam) e `ruff` está limpo. Nada foi enviado ao GitHub, a impressora real não foi usada e a porta 8765 não foi tocada. O que mudou de contrato:

### 15.1 Detecção

- **Detector por lado só sem voto das regiões** (3.3, 6.3): `PageCropDetectionService.detect_crops` roda `detect_photo_regions` uma vez; `None` (borda não uniforme, o livro) vai ao detector por lado; qualquer outra resposta, mesmo sem regiões, é final.
- **Área mínima de 1%** (`MINIMUM_PHOTO_AREA_SHARE`), com os testes de poeira, fio e etiqueta mantidos.
- **Tampa com sombra de cima para baixo** (`photo_region_detection.py`): com a borda não uniforme, ou com menos de 2 regiões em tampa uniforme, o fundo também é tentado como um **plano** (nível e inclinação saem das medianas dos quatro lados da borda, montado só com Pillow: `Image.linear_gradient` e `ImageChops.add`). Esse caminho **só responde quando acha 2 regiões** (o que um nível único e o detector por lado não separam); um objeto só (o livro, uma foto) continua indo ao detector por lado. Cenas de 2 cartões com sombra de 34, 45, 70 e 100 níveis passam a dar 2 molduras (antes 0 ou um retângulo que cobria 77% de uma foto); as 4 digitalizações reais do livro e as 3 de 2 fotos dão o mesmo de antes. Custo: cerca de 15 ms a mais, só quando a primeira passada não achou 2.
- **Faixa quase branca atravessando uma foto (dividida em duas molduras): não foi tratada no código.** A heurística proposta (juntar duas regiões cujo retângulo conjunto é quase cheio) juntaria também duas fotos lado a lado e coladas, que é justamente o caso de uso de 2 fotos; ela é inerente ao branco sobre branco e o usuário corrige em **Ampliar**. Mitigação: a dica do diálogo ganhou "Uma foto com uma faixa quase branca pode virar duas: confira as molduras, remova uma e ajuste a outra."

### 15.2 Servidor

- **`ScanOutputRepository.save_in_folder(output_folder, encoded_scan)`** (porta e repositório; `save` chama com a pasta dos ajustes): `LastScanEditService` cria os arquivos novos na **pasta da digitalização**, não na dos ajustes de agora. Antes, trocar a pasta de saída e depois adicionar uma moldura gravava o arquivo na pasta nova, repetia o nome no manifesto e mandava o mestre para `set-aside-*`.
- Reforços: dois arquivos de mesmo nome no mesmo render viram `OutputFolderUnavailableError`; uma edição que acha o espaço sumido marca a digitalização como **não editável** no tracker (o painel deixa de oferecer Ampliar e Girar).
- **Partida com o disco externo desligado:** `restore_after_start` não descarta mais o espaço quando a pasta de saída não existe (aviso no log, painel sem última digitalização); só descarta quando a pasta existe e nenhum arquivo dela existe. O mestre fica.
- **Erros das rotas do último arquivo:** `LAST_SCAN_ERROR_STATUSES` ganhou `invalid_page_rotation` (422); os erros do espaço (`insufficient_draft_storage`, `draft_storage_unavailable`) viram os códigos `insufficient_last_scan_storage` (507) e `last_scan_storage_unavailable` (503), com texto do modo Rápido (`respond_to_last_scan_error`, usado também pela rota de pré-visualização).
- **API provisória removida:** `PUT …/crop`, `POST …/crop/detect`, `ProvisionalCropRequestBody`, a chave `crop` das páginas, `crop_detected` e `file_name`/`size_in_bytes` de `last_result`.
- **`output_page_count`** no corpo do documento (`document.output_page_count`) e no resumo de `/api/state` (`document.output_page_count`): páginas do PDF (uma página com 2 molduras conta 2).
- **Cabeçalho `Cache-Control: no-cache`** em `/` e em `/static/*` (`RevalidatedStaticFiles`; o ETag faz a revalidação virar um 304): o Chrome deixava de pegar JS e CSS novos depois de uma atualização.

### 15.3 Interface

- **Diálogo da moldura:** coluna flex com altura máxima da tela (`100dvh`); só a área da imagem rola e as linhas de botões ficam sempre à vista (as duas primeiras linhas viraram uma); no celular (≤ 30 rem) o diálogo todo rola e só a linha de **Cancelar** e **Aplicar** fica grudada embaixo. Medido no Chrome sem janela em 1280×720, 1440×800, 1440×900, 1920×950 e 390×844: **Aplicar** e **Cancelar** ficam a vista em todos.
- **Contagem de páginas do PDF:** o resumo diz "2 páginas (4 no PDF)", o aviso do documento pendente também, e a pergunta de Salvar usa as páginas do PDF.
- **Aplicar em andamento:** Adicionar, Remover, Sem corte, Girar moldura, Detectar, Girar página e **Cancelar** ficam desabilitados, as alças e as setas não mexem na moldura e o Esc não fecha o diálogo; assim "Alterações da moldura descartadas." nunca é dito de algo que o servidor aplicou.
- **Foco visível** em **Mover a moldura** e na seleção: listras (preto e branco a 35%) em vez do véu branco a 22%.
- **Qualidade do JPEG:** o salvamento espera 300 ms depois da última mudança (uma tecla segurada não dispara mais um PUT por passo) e uma resposta sobre um valor antigo não devolve o controle a ele (de 20 setas a 80 ms de latência, de 90 acabava em 82; agora acaba em 70).
- **Alça de girar a moldura:** no mínimo 52 px do meio do lado de cima (antes cobria a alça desse lado em 390 px) e, sem espaço fora da página, vai para dentro da moldura.
- **Aviso de arquivo apagado:** "O arquivo X foi apagado porque agora há só N arquivo(s)." (não nomeia mais uma moldura, porque os arquivos acompanham as posições).

### 15.4 Testes e histórico

- Os ajudantes de teste sem parâmetro booleano (`build_job(output_format, adjustment)`, `job_with`) e com no máximo 3 parâmetros (`rectangle((esquerda, topo, direita, base))`, `render_request`, ajudantes `turn_last_scan`, `put_last_crops` e `detect_last_crops`); o teste de 409 durante a digitalização, de 0,8 s, virou cinco testes sem espera (a digitalização fica presa por um portão). Os testes de integração do aplicativo inteiro seguem em 0,1 a 0,2 s cada (subir o aplicativo e escanear no simulador): aberto.
- O commit `493241f` deixa a suíte vermelha (falta uma linha de teste, que o commit seguinte, de mesmo assunto, traz). O histórico reescrito, com os dois juntos e a mesma árvore final, ficou pronto no branch local `tmp-bisect-fix`; o `main` não foi reescrito (a ferramenta recusou mover o branch). Para adotar antes do envio: `git branch -f main tmp-bisect-fix`.

## 16. Revisão: salvar sem nunca substituir ou apagar (substitui as regras de regravação das seções anteriores)

- **Nome:** `AAAA_MM_DD__HH_MM_SS_NNNNNNNNN.pdf|jpg` (hora local, dois sublinhados entre a data e a hora, segundos incluídos para que a ordem alfabética seja a ordem do tempo, 9 dígitos de nanossegundos dentro do segundo; exemplo `2026_10_18__16_42_01_783249000.jpg`). Vale para o modo Rápido e para o PDF do modo Documento sem nome digitado; o nome digitado continua `Nome.pdf` / `Nome (2).pdf`. Arquivos com padrões antigos na pasta nunca são tocados.
- **Várias fotos numa gravação:** quando uma gravação (uma digitalização, ou um **Aplicar**/**Girar**/**Detectar**) cria mais de um arquivo, todos repartem a mesma leitura do relógio (um instante só por gravação) e ganham o contador `__<n>` (inteiro simples, começando em 1, na ordem de leitura): `AAAA_MM_DD__HH_MM_SS_NNNNNNNNN__1.jpg`, `…__2.jpg`. Uma gravação com um arquivo só mantém o nome simples, sem contador. Cada nova gravação tem uma data-base nova; os arquivos anteriores ficam como estão. A política devolve grupos de nomes (`name_groups(output_format, file_count)`) e o repositório grava o grupo com `save_scans` / `save_scans_in_folder` (um grupo por tentativa).
- **Estratégia:** cada gravação pega uma data-base nova (criação exclusiva de cada arquivo; num choque, os arquivos já criados nessa tentativa são recolhidos e o grupo inteiro tenta o nanossegundo seguinte, com os mesmos contadores). Nada é substituído nem apagado. A mesma imagem pode ser salva quantas vezes se quiser.
- **Ajustes do painel Rápido** (**Aplicar**, **Girar ↻**, **Detectar**): gravam arquivos novos a partir do original guardado e deixam os anteriores como estão, inclusive quando uma moldura é removida. O painel e o manifesto apontam para os arquivos da gravação mais nova; o histórico de nomes antigos não entra no manifesto. A tela diz "N arquivos novos salvos: …" e que os anteriores foram mantidos. Saíram `replace_saved_scan`, `delete_saved_scan`, `kept_file_names`/`deleted_file_names`, o erro `last_scan_file_missing` (409) e as mensagens de criado/substituído/apagado.
- **Queda no meio de um ajuste:** a marca `render_pending` continua. Ao abrir, o app refaz o ajuste a partir do original em arquivos novos; arquivos completos da tentativa interrompida (se houver) ficam na pasta como qualquer outro; um arquivo incompleto só existe com nome temporário oculto, nunca sob um nome final.
- **Qualidade do JPEG:** o controle e a configuração `jpeg_quality` saíram; toda regravação usa a constante `REENCODING_JPEG_QUALITY = 90`. `settings.json` antigo e clientes que ainda enviam `jpeg_quality` continuam funcionando (o valor é ignorado) e `GET /api/settings` não o devolve mais.
- **Margem de segurança no corte:** a caixa continua; a linha de dica abaixo dela saiu (e o `aria-describedby`).

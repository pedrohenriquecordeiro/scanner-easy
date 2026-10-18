# Digitalizadora

App local para macOS (FastAPI em `127.0.0.1` + página em JS puro) que digitaliza com uma HP DeskJet 2800 series pelo protocolo eSCL. Modo Rápido (um clique, arquivos) e modo Documento (PDF de várias páginas), molduras de corte editáveis (até 2 por digitalização), giro, 8 resoluções, originais preservados. Python 3.12, FastAPI, httpx, Pillow, img2pdf, pikepdf. UI e documentação em português; código em inglês.

## Comandos

- Tabela completa dos alvos do `make` (setup, run, simulator, run-simulated, test, lint, check, test-hardware): `docs/desenvolvimento.md`. `make check` deve terminar verde antes de commitar.
- `make test-hardware` usa a impressora real; só o usuário pede isso.

## Arquitetura

Camadas: `controllers -> services -> domain <- repositories / infrastructure`. Injeção por construtor; só `composition_root.py` instancia classes concretas. Portas (Protocols) em `domain/ports.py`. `tests/architecture/` falha se a regra for violada. Cada camada tem subpacotes por funcionalidade (`documents`, `quick_scan`, `imaging`, `scanner`, ...). Mapa, fluxos, API e invariantes: `docs/arquitetura.md`. Receitas de mudança (novo ajuste, endpoint, controle, formato, cena do simulador, backend): `docs/desenvolvimento.md`.

## Convenções

- Pastas e arquivos em kebab-case; **módulos Python em snake_case**; classes PascalCase; funções e variáveis snake_case; constantes UPPER_SNAKE_CASE.
- Sem abreviações (`identifier`, `base_address`, `dots_per_inch`) e nomes descritivos.
- No máximo 3 parâmetros por função, sem flags booleanas de modo, sem números mágicos, `Enum` em vez de textos soltos, type hints, comentários só para o porquê.

## Testes

- TDD. Cada teste: menos de 100 ms, um conceito, sem rede e sem impressora. Relógio, `sleep` e espaço livre são injetados.
- Fakes em `tests/fakes/`; interface testada no Node (`tests/web/`); testes de hardware só com `DIGITALIZADORA_HARDWARE_TESTS=1`.
- `make check` (pytest e ruff) deve terminar verde; não deixe a contagem de testes cair sem motivo.

## Cuidados

- **Nunca use a impressora real** em testes ou verificações; use o simulador. Ela faz um job por vez.
- O app em `127.0.0.1:8765` pode ser a instância real do usuário: não a derrube nem mexa nela. Para testar, use outra porta (`DIGITALIZADORA_PORT`) e `make run-simulated`, que usa `HOME=~/Digitalizadora-simulador`.
- Os originais do scanner nunca mudam; arquivos de saída nunca são sobrescritos nem apagados; o manifesto é gravado por último. Veja os invariantes em `docs/arquitetura.md`.
- 1200 dpi tem cerca de 143 milhões de pixels: não carregue páginas inteiras à toa (`replace_with`, prévias reduzidas, PDF em fluxo).
- Não commite imagens de pessoas nem identificadores da impressora (MAC, série, nome Bonjour). Cenas do simulador são formas sintéticas.
- `md.md` na raiz é a lista pessoal de pedidos do usuário: nunca edite, mova, renomeie nem commite.
- Nunca faça `git push` sem o usuário pedir. Commits ficam locais; a mensagem termina com a linha `Co-Authored-By` indicada pelo ambiente.
- Mudou um ajuste, rota, pasta ou invariante? Atualize `README.md` e `docs/arquitetura.md`.

## Documentos

`README.md` (uso), `docs/arquitetura.md`, `docs/desenvolvimento.md`, `docs/acceptance-checklist.md` (checklist manual) e `docs/historico/` (planos e specs antigos, obsoletos: não os siga).

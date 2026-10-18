# Histórico do projeto

Registros de como o Digitalizadora foi pensado e validado: levantamento, pesquisa, resultado do Gate 0 (a validação da impressora), specs de cada funcionalidade e planos. **Nada aqui descreve o código de hoje com exatidão.** Para mudar o código, leia [../arquitetura.md](../arquitetura.md) e [../desenvolvimento.md](../desenvolvimento.md). Estes arquivos servem para entender por que uma decisão foi tomada.

O arquivo `md.md`, na raiz do repositório, é o pedido original e a lista pessoal de pedidos do dono do projeto; vários documentos daqui o citam.

## Levantamento, pesquisa e Gate 0

| Arquivo | O que é |
|---|---|
| [relatorio-do-levantamento-2026-10-13.md](relatorio-do-levantamento-2026-10-13.md) | Relatório do levantamento inicial, antes de existir código. |
| [pesquisa/digest-da-pesquisa-2026-10-13.md](pesquisa/digest-da-pesquisa-2026-10-13.md) | Resumo da pesquisa sobre software de digitalização para a impressora (em inglês, com fontes). |
| [gate-0-resultado-2026-10-17.md](gate-0-resultado-2026-10-17.md) | Resultado do Gate 0: a impressora digitaliza por eSCL, pelo USB e pelo Wi-Fi. Continua válido como registro das respostas reais da impressora. |
| [gate-0-capturas/](gate-0-capturas/) | Respostas reais capturadas no Gate 0 (descoberta Bonjour, capacidades, estado, cabeçalhos). |

## Specs das funcionalidades

Em ordem cronológica. "Parcialmente vigente" quer dizer que a ideia central ainda vale, mas partes foram trocadas por um spec mais novo ou pelo código.

| Spec | Assunto | Situação |
|---|---|---|
| [2026-10-13-digitalizadora-design.md](superpowers/specs/2026-10-13-digitalizadora-design.md) | Desenho original: uma página por clique, eSCL, camadas, contratos. | Parcialmente vigente: as camadas e o eSCL seguem; a interface, o corte e a qualidade foram superados. |
| [2026-10-17-documento-de-varias-paginas.md](superpowers/specs/2026-10-17-documento-de-varias-paginas.md) | Modo Documento: rascunho em disco, manifesto, finalização, recuperação após queda. | Parcialmente vigente: rascunho, manifesto e recuperação seguem; o corte por página foi substituído pelas molduras. |
| [2026-10-17-ajustes-rotacao-resolucoes-corte.md](superpowers/specs/2026-10-17-ajustes-rotacao-resolucoes-corte.md) | Girar, 8 resoluções, corte automático, botão Salvar. | Parcialmente vigente: as resoluções seguem; giro e corte foram substituídos pelos dois specs abaixo. |
| [2026-10-18-moldura-de-corte-por-pagina.md](superpowers/specs/2026-10-18-moldura-de-corte-por-pagina.md) | Uma moldura retangular por página, ampliação, giro só na página. | Superado em grande parte pelo spec seguinte (moldura retangular virou quadrilátero, uma virou até duas). |
| [2026-10-18-molduras-livres-multifoto-e-modo-rapido.md](superpowers/specs/2026-10-18-molduras-livres-multifoto-e-modo-rapido.md) | Molduras livres (quadriláteros), até 2 fotos por digitalização, modo Rápido com moldura, mestre guardado. | Vigente para as molduras; a qualidade do JPEG configurável (D23) virou fixa em 100. |

## Planos

| Arquivo | O que é |
|---|---|
| [superpowers/plans/2026-10-17-digitalizadora-plano-final.md](superpowers/plans/2026-10-17-digitalizadora-plano-final.md) | Plano de implementação inicial, com cerca de 38 mil linhas. **Obsoleto:** o código evoluiu muito depois dele (nomes, pastas, funcionalidades). Não o siga. |
| [superpowers/plans/2026-10-13-achados-da-revisao.md](superpowers/plans/2026-10-13-achados-da-revisao.md) | Achados da revisão adversarial do primeiro rascunho do plano. |
| [superpowers/plans/2026-10-13-mudancas-de-contrato-pendentes.md](superpowers/plans/2026-10-13-mudancas-de-contrato-pendentes.md) | Mudanças de contrato ACC-1 a ACC-13. |
| [superpowers/plans/2026-10-17-mudancas-de-contrato-do-gate-0.md](superpowers/plans/2026-10-17-mudancas-de-contrato-do-gate-0.md) | Mudanças de contrato decididas depois do Gate 0 (G0C). |
| [superpowers/plans/arquivo-rascunho-2026-10-13/](superpowers/plans/arquivo-rascunho-2026-10-13/) | Primeiro rascunho do plano, não revisado. |
| [superpowers/plans/ferramentas/check-plan-code.py](superpowers/plans/ferramentas/check-plan-code.py) | Script que conferia o código dos planos. |

Os caminhos citados dentro destes documentos (`docs/superpowers/...`, `src/digitalizadora/services/...`) são os de quando foram escritos e podem não existir mais.

# Digitalizadora

App local para o MacBook: abre uma página em `http://127.0.0.1:8765` com um botão **Digitalizar** (ou a tecla Espaço), digitaliza uma página do vidro da HP DeskJet Ink Advantage 2874 pelo protocolo eSCL e grava um PDF ou um JPG com nome automático.

Estado: em construção (MVP). O desenho está em `docs/superpowers/specs/2026-10-13-digitalizadora-design.md`. A validação da impressora (Gate 0, aprovada em 2026-10-17) está em `docs/gate-0-resultado-2026-10-17.md`, com as capturas em `docs/gate-0-capturas/`.

## Desenvolvimento

```bash
make setup   # cria o .venv e instala o projeto com as ferramentas de desenvolvimento (grupo development)
make test    # roda os testes
make lint    # confere o estilo com o ruff
```

Os testes que usam a impressora real ficam marcados com `hardware` e só rodam com `DIGITALIZADORA_HARDWARE_TESTS=1`.

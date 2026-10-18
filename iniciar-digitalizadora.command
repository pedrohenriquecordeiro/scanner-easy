#!/bin/zsh
# Inicia o Digitalizadora com duplo clique (o Finder abre este arquivo no Terminal.app).
# Pelo cabo USB o app funciona aberto de qualquer lugar. Pelo Wi-Fi, o macOS só deixa o app falar com a
# impressora se o programa que o abriu tiver a permissão de Rede Local; o Terminal.app é o caminho recomendado.

cd "$(dirname "$0")" || exit 1

PORT="${DIGITALIZADORA_PORT:-8765}"
PAGE_ADDRESS="http://127.0.0.1:${PORT}"
HEALTH_ADDRESS="${PAGE_ADDRESS}/api/health"
MAXIMUM_WAIT_SECONDS=30
LOG_FILE="$HOME/Library/Logs/Digitalizadora/digitalizadora.log"
SETUP_MARKER=".venv/digitalizadora-setup-complete"
PYTHON_COMMAND="${PYTHON:-python3}"
MINIMUM_PYTHON_CHECK='import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)'
DEPENDENCY_CHECK='import digitalizadora, fastapi, uvicorn, httpx, PIL, img2pdf, pikepdf'

# O make setup só cria o marcador depois de instalar tudo; sem ele (ou com o ambiente quebrado), prepara de novo.
environment_is_ready() {
  [[ -f "$SETUP_MARKER" ]] && .venv/bin/python -c "$DEPENDENCY_CHECK" > /dev/null 2>&1
}

if ! environment_is_ready; then
  if ! "$PYTHON_COMMAND" -c "$MINIMUM_PYTHON_CHECK" > /dev/null 2>&1; then
    echo "O Digitalizadora precisa do Python 3.12 ou mais novo, e o comando $PYTHON_COMMAND não serve."
    echo "Instale o Python 3.12 (python.org) e rode uma vez no Terminal, dentro desta pasta: make setup PYTHON=python3.12"
    exit 1
  fi
  echo "Preparando o ambiente (na primeira vez leva alguns minutos e precisa de internet)..."
  if ! make setup PYTHON="$PYTHON_COMMAND"; then
    echo "Não consegui preparar o ambiente. Confira a conexão com a internet e dê duplo clique de novo."
    echo "A mensagem acima diz o que falhou; a preparação recomeça do zero na próxima vez."
    exit 1
  fi
fi

if curl --silent --fail "$HEALTH_ADDRESS" > /dev/null 2>&1; then
  open "$PAGE_ADDRESS"
  echo "O Digitalizadora já está aberto em outra janela do Terminal. Abri a página dele: $PAGE_ADDRESS"
  exit 0
fi

echo "Iniciando o Digitalizadora..."
.venv/bin/python -m digitalizadora &
server_process=$!

stop_server() {
  kill "$server_process" 2>/dev/null
}
trap stop_server EXIT
trap 'exit 1' INT TERM HUP

waited_seconds=0
until curl --silent --fail "$HEALTH_ADDRESS" > /dev/null 2>&1; do
  if ! kill -0 "$server_process" 2>/dev/null; then
    echo "O Digitalizadora fechou logo depois de abrir. Veja a mensagem acima ou o registro em $LOG_FILE"
    exit 1
  fi
  if (( waited_seconds >= MAXIMUM_WAIT_SECONDS )); then
    echo "O Digitalizadora não respondeu em ${MAXIMUM_WAIT_SECONDS} segundos. Veja o registro em $LOG_FILE"
    exit 1
  fi
  sleep 1
  waited_seconds=$(( waited_seconds + 1 ))
done

open "$PAGE_ADDRESS"
echo "Digitalizadora aberto em $PAGE_ADDRESS"
echo "Mantenha esta janela aberta enquanto estiver digitalizando. Para encerrar, feche a janela ou aperte Control-C."
wait "$server_process"

import logging
import os
import socket
from collections.abc import Mapping
from logging.handlers import RotatingFileHandler
from pathlib import Path

import uvicorn

from digitalizadora.application_factory import create_application
from digitalizadora.composition_root import build_container
from digitalizadora.configuration import ApplicationConfiguration
from digitalizadora.controllers.shared.error_message_catalog import ERROR_MESSAGES
from digitalizadora.domain.errors import DraftFolderInUseError

LOG_FILE_NAME = "digitalizadora.log"
LOG_MAXIMUM_BYTES = 1024 * 1024
LOG_BACKUP_COUNT = 3
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
UVICORN_LOG_LEVEL = "info"
HTTP_CLIENT_LOGGER_NAME = "httpx"
EXIT_CODE_SUCCESS = 0
EXIT_CODE_FAILURE = 1

PAGE_ADDRESS_MESSAGE = "Digitalizadora pronto. Abra esta página no navegador: {page_address}"
KEEP_TERMINAL_OPEN_MESSAGE = (
    "Mantenha esta janela do Terminal aberta enquanto estiver digitalizando. "
    "Para encerrar, aperte Control-C ou feche a janela."
)
INVALID_CONFIGURATION_MESSAGE = "Configuração inválida: {reason}"
# R12: a second copy on another port is refused anyway, so the message no longer suggests one.
PORT_IN_USE_MESSAGE = (
    "A porta {port} já está em uso. Provavelmente o Digitalizadora já está aberto em outra janela do Terminal: "
    "use aquela janela. Se a porta é de outro programa, escolha outra, por exemplo: DIGITALIZADORA_PORT=8766 make run"
)


def configure_logging(log_directory: Path) -> None:
    log_directory.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_directory / LOG_FILE_NAME,
        maxBytes=LOG_MAXIMUM_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    for handler in (file_handler, logging.StreamHandler()):
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        root_logger.addHandler(handler)
    # httpx logs every scanner request at INFO; the printer check every 15 s would bury the instructions.
    logging.getLogger(HTTP_CLIENT_LOGGER_NAME).setLevel(logging.WARNING)


def ensure_port_is_available(host: str, port: int) -> None:
    # uvicorn turns a bind failure into SystemExit, so the port is probed first to explain it in Portuguese.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind((host, port))


def print_startup_instructions(configuration: ApplicationConfiguration) -> None:
    page_address = f"http://{configuration.host}:{configuration.port}"
    print(PAGE_ADDRESS_MESSAGE.format(page_address=page_address))
    print(KEEP_TERMINAL_OPEN_MESSAGE)


def run_application(environment: Mapping[str, str], home_directory: Path) -> int:
    try:
        configuration = ApplicationConfiguration.from_environment(environment, home_directory)
    except ValueError as error:
        print(INVALID_CONFIGURATION_MESSAGE.format(reason=error))
        return EXIT_CODE_FAILURE
    configure_logging(configuration.log_directory)
    try:
        ensure_port_is_available(configuration.host, configuration.port)
    except OSError:
        print(PORT_IN_USE_MESSAGE.format(port=configuration.port))
        return EXIT_CODE_FAILURE
    try:
        container = build_container(configuration)
    except DraftFolderInUseError:
        # Another copy owns the drafts folder (R12): two copies would lose confirmed pages.
        print(ERROR_MESSAGES[DraftFolderInUseError.code])
        return EXIT_CODE_FAILURE
    application = create_application(container.controllers, container.web_configuration)
    print_startup_instructions(configuration)
    # log_config=None keeps uvicorn's records flowing to the root handlers (the log file included);
    # access_log=False keeps the /api/state polling from burying the instructions printed above.
    uvicorn.run(
        application,
        host=configuration.host,
        port=configuration.port,
        log_level=UVICORN_LOG_LEVEL,
        log_config=None,
        access_log=False,
    )
    return EXIT_CODE_SUCCESS


def main() -> None:
    raise SystemExit(run_application(os.environ, Path.home()))


if __name__ == "__main__":
    main()

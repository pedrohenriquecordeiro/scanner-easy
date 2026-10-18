from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

APPLICATION_NAME = "Digitalizadora"
LOCAL_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
MINIMUM_PORT = 1
MAXIMUM_PORT = 65535
PORT_VARIABLE_NAME = "DIGITALIZADORA_PORT"
SCANNER_ADDRESS_VARIABLE_NAME = "DIGITALIZADORA_SCANNER_ADDRESS"
OUTPUT_FOLDER_VARIABLE_NAME = "DIGITALIZADORA_OUTPUT_FOLDER"
HOME_SHORTCUT = "~"
HOME_SHORTCUT_PREFIX = "~/"


@dataclass(frozen=True)
class ApplicationConfiguration:
    host: str
    port: int
    data_directory: Path
    log_directory: Path
    default_output_folder: Path
    scanner_address_override: str | None

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str], home_directory: Path
    ) -> "ApplicationConfiguration":
        return cls(
            host=LOCAL_HOST,
            port=_read_port(environment),
            data_directory=home_directory / "Library" / "Application Support" / APPLICATION_NAME,
            log_directory=home_directory / "Library" / "Logs" / APPLICATION_NAME,
            default_output_folder=_read_output_folder(environment, home_directory),
            scanner_address_override=_read_optional_text(environment, SCANNER_ADDRESS_VARIABLE_NAME),
        )


def _read_optional_text(environment: Mapping[str, str], variable_name: str) -> str | None:
    raw_text = environment.get(variable_name)
    if raw_text is None:
        return None
    return raw_text.strip() or None


def _expand_home_shortcut(folder_text: str, home_directory: Path) -> Path:
    if folder_text == HOME_SHORTCUT:
        return home_directory
    if folder_text.startswith(HOME_SHORTCUT_PREFIX):
        return home_directory / folder_text.removeprefix(HOME_SHORTCUT_PREFIX)
    return Path(folder_text)


def _read_output_folder(environment: Mapping[str, str], home_directory: Path) -> Path:
    configured_folder = _read_optional_text(environment, OUTPUT_FOLDER_VARIABLE_NAME)
    if configured_folder is None:
        return home_directory / "Pictures" / APPLICATION_NAME
    output_folder = _expand_home_shortcut(configured_folder, home_directory)
    if not output_folder.is_absolute():
        raise ValueError(
            f"{OUTPUT_FOLDER_VARIABLE_NAME} precisa ser um caminho completo, começando por / ou ~/, "
            f"mas veio {configured_folder!r}."
        )
    return output_folder


def _read_port(environment: Mapping[str, str]) -> int:
    raw_port = environment.get(PORT_VARIABLE_NAME)
    if raw_port is None:
        return DEFAULT_PORT
    invalid_port_message = (
        f"{PORT_VARIABLE_NAME} precisa ser um número inteiro entre "
        f"{MINIMUM_PORT} e {MAXIMUM_PORT}, mas veio {raw_port!r}."
    )
    try:
        port = int(raw_port)
    except ValueError:
        raise ValueError(invalid_port_message) from None
    if not MINIMUM_PORT <= port <= MAXIMUM_PORT:
        raise ValueError(invalid_port_message)
    return port

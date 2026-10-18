from collections.abc import Mapping
from types import MappingProxyType

UNEXPECTED_ERROR_CODE = "unexpected_error"
FORBIDDEN_HOST_CODE = "forbidden_host"
MISSING_REQUEST_HEADER_CODE = "missing_request_header"

ERROR_MESSAGES: Mapping[str, str] = MappingProxyType(
    {
        "scanner_unreachable": (
            "Não encontrei a impressora. Confira se está ligada e com o cabo USB conectado ao Mac. "
            "Sem o cabo, confira se a luz do Wi-Fi está acesa e se ela está na mesma rede do Mac "
            "(2,4 GHz)."
        ),
        "local_network_blocked": (
            "O macOS pode estar bloqueando o acesso à rede local. Conecte a impressora pelo cabo USB, "
            "que não depende dessa permissão, ou abra o Digitalizadora pelo arquivo "
            "iniciar-digitalizadora.command (ele abre o Terminal.app) e confira Ajustes > "
            "Privacidade e Segurança > Rede Local."
        ),
        "scanner_busy": "A impressora está ocupada. Aguarde alguns segundos e tente de novo.",
        "scan_rejected": "A impressora recusou os ajustes desta digitalização.",
        "scan_failed": "A digitalização falhou. Confira se a tampa está fechada e tente de novo.",
        "scan_timed_out": "A impressora demorou demais para responder.",
        "scan_already_running": "Já existe uma digitalização em andamento.",
        "insufficient_storage": (
            "Pouco espaço livre na pasta de saída. Use um disco externo ou libere espaço."
        ),
        "output_folder_unavailable": (
            "Não consigo gravar na pasta de saída. Se for um disco externo, confira se está "
            "conectado."
        ),
        "invalid_settings": "Ajustes inválidos.",
        UNEXPECTED_ERROR_CODE: (
            "Algo inesperado aconteceu. Veja o registro em ~/Library/Logs/Digitalizadora."
        ),
        FORBIDDEN_HOST_CODE: "Acesso recusado: o endereço usado não é o da própria máquina.",
        MISSING_REQUEST_HEADER_CODE: "Requisição recusada: falta o cabeçalho X-Requested-With.",
    }
)


class ErrorMessageCatalog:
    def message_for(self, error_code: str) -> str:
        return ERROR_MESSAGES.get(error_code, ERROR_MESSAGES[UNEXPECTED_ERROR_CODE])


def build_error_body(error_message_catalog: ErrorMessageCatalog, error_code: str) -> dict[str, str]:
    return {"code": error_code, "message": error_message_catalog.message_for(error_code)}

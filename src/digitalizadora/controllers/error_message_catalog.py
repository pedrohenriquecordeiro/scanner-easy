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
        "no_open_document": "Não há documento em andamento. Adicione uma página para começar.",
        "page_not_found": "Essa página não está mais no documento. A lista foi atualizada.",
        "invalid_page_order": (
            "A nova ordem das páginas não confere com o documento. A lista foi atualizada; tente de novo."
        ),
        "invalid_document_name": (
            "Nome de documento inválido: comprido demais ou só com pontos e caracteres invisíveis. "
            "Use um nome mais curto, com letras ou números."
        ),
        "empty_document": (
            "O documento não tem páginas. Adicione pelo menos uma página antes de salvar."
        ),
        "document_busy": (
            "O documento está sendo salvo ou alterado. Aguarde um instante e tente de novo."
        ),
        "draft_folder_in_use": (
            "O Digitalizadora já está aberto em outra janela do Terminal. "
            "Use aquela janela, ou feche-a antes de abrir de novo."
        ),
        "draft_storage_unavailable": (
            "Não consigo guardar as páginas do documento no disco do Mac. "
            "Veja o registro em ~/Library/Logs/Digitalizadora."
        ),
        "insufficient_draft_storage": (
            "Pouco espaço livre no disco do Mac para guardar as páginas do documento. "
            "Libere espaço e tente de novo."
        ),
        "document_assembly_failed": (
            "Não consegui montar o PDF porque uma página guardada não pôde ser lida como imagem. "
            "Veja o registro em ~/Library/Logs/Digitalizadora."
        ),
        "damaged_document_page": (
            "Uma página guardada do documento está danificada ou sumiu do disco do Mac. "
            "Ela está marcada na grade: exclua-a e digitalize-a de novo."
        ),
        "document_too_large": (
            "O documento é grande demais para montar com a memória livre do Mac. "
            "Feche outros programas e tente de novo."
        ),
        "image_adjustment_failed": (
            "Não consegui processar a imagem com a memória livre do Mac. "
            "Escolha uma resolução menor e tente de novo."
        ),
        "invalid_crop": (
            "A moldura de corte é inválida: ela precisa ser um quadrilátero sem pontas viradas, dentro da "
            "página, e são no máximo 2 molduras. Ajuste e tente de novo."
        ),
        "invalid_page_rotation": "Rotação inválida.",
        "no_last_scan": "Ainda não há uma digitalização para ajustar.",
        "last_scan_file_missing": "O arquivo da última digitalização não está mais na pasta de saída.",
        "saved_scan_unreadable": (
            "Não consegui ler o original da última digitalização para ajustá-la. "
            "Veja o registro em ~/Library/Logs/Digitalizadora."
        ),
        "last_scan_busy": (
            "A última digitalização está sendo ajustada. Aguarde um instante e tente de novo."
        ),
        "last_scan_not_editable": (
            "O original desta digitalização não foi guardado, então ela não pode ser ajustada."
        ),
        "insufficient_last_scan_storage": (
            "Pouco espaço livre no disco do Mac para ajustar a última digitalização. "
            "Libere espaço e tente de novo."
        ),
        "last_scan_storage_unavailable": (
            "Não consigo guardar o original da última digitalização no disco do Mac. "
            "Veja o registro em ~/Library/Logs/Digitalizadora."
        ),
    }
)


class ErrorMessageCatalog:
    def message_for(self, error_code: str) -> str:
        return ERROR_MESSAGES.get(error_code, ERROR_MESSAGES[UNEXPECTED_ERROR_CODE])


def build_error_body(error_message_catalog: ErrorMessageCatalog, error_code: str) -> dict[str, str]:
    return {"code": error_code, "message": error_message_catalog.message_for(error_code)}

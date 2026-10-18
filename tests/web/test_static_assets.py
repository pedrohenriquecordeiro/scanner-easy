import re
from pathlib import Path

import pytest

from digitalizadora.domain.scan_quality import SUPPORTED_DOTS_PER_INCH

STATIC_DIRECTORY = Path(__file__).resolve().parents[2] / "src" / "digitalizadora" / "web" / "static"
SCRIPT_FILE_NAMES = [
    "scan-trigger-policy.js",
    "scan-quality-policy.js",
    "error-banner.js",
    "document-page-policy.js",
    "page-frame-geometry.js",
    "frame-dialog-policy.js",
    "last-scan-policy.js",
    "frame-overlay.js",
    "page-frame-editor.js",
    "document-panel.js",
    "last-scan-panel.js",
    "application.js",
]
STATIC_FILE_NAMES = ["index.html", "application.css", *SCRIPT_FILE_NAMES]
SCRIPT_IDENTIFIER_PATTERNS = (
    re.compile(r"""getElementById\(\s*["']([^"']+)["']\s*\)"""),
    re.compile(r"""querySelector\(\s*["']#([A-Za-z0-9_-]+)"""),
)
PAGE_IDENTIFIER_PATTERN = re.compile(r"""\bid\s*=\s*["']([^"']+)["']""")
EXTERNAL_ADDRESS_PATTERN = re.compile(r"""https?://|(?:src|href)\s*=\s*["']//""")
# The name of the SVG space of names, which every drawing in a page carries; the browser never fetches it.
SVG_NAMESPACE_NAME = "http://www.w3.org/2000/svg"
SCRIPT_SOURCE_PATTERN = re.compile(r"""<script\s+src="/static/([^"]+)\"""")
COLLECTED_ELEMENT_PATTERN = re.compile(r"""^\s+([a-z_]+): (?:document\.getElementById\(|\{)""", re.MULTILINE)
PANEL_ELEMENT_PATTERN = re.compile(r"""\belements\.([a-z_]+)""")
PANEL_DESTRUCTURED_ELEMENTS_PATTERN = re.compile(r"""\{([^{}]+)\}\s*=\s*this\.elements""")
POLICY_SCRIPT_PATH = "/static/scan-trigger-policy.js"
APPLICATION_SCRIPT_PATH = "/static/application.js"
DOCUMENT_ELEMENT_IDENTIFIERS = [
    "capture-mode-single",
    "capture-mode-document",
    "output-format-group",
    "document-pending-notice",
    "document-pending-text",
    "return-to-document-button",
    "document-section",
    "document-name-input",
    "document-recovery-notice",
    "document-previous-save-notice",
    "document-large-warning",
    "document-empty-message",
    "document-page-grid",
    "document-summary",
    "draft-storage-line",
    "draft-storage-warning",
    "discard-last-page-button",
    "cancel-document-button",
    "save-document-button",
    "document-finished-message",
    "document-announcement",
    "confirmation-dialog",
    "confirmation-text",
    "confirmation-accept-button",
    "confirmation-reject-button",
    "move-page-dialog",
    "move-page-position-input",
    "move-page-accept-button",
    "move-page-reject-button",
]
FRAME_DIALOG_ELEMENT_IDENTIFIERS = [
    "page-frame-dialog",
    "page-frame-title",
    "page-frame-help",
    "page-frame-limits",
    "frame-stage",
    "frame-image",
    "frame-overlay-host",
    "frame-move-button",
    "frame-corner-top-left",
    "frame-corner-top-right",
    "frame-corner-bottom-right",
    "frame-corner-bottom-left",
    "frame-edge-top",
    "frame-edge-right",
    "frame-edge-bottom",
    "frame-edge-left",
    "frame-rotate-handle",
    "frame-select-button",
    "frame-status",
    "frame-add-button",
    "frame-remove-button",
    "frame-turn-button",
    "frame-detect-button",
    "frame-clear-button",
    "frame-rotate-button",
    "frame-cancel-button",
    "frame-apply-button",
]
LAST_SCAN_ELEMENT_IDENTIFIERS = [
    "last-scan-panel",
    "last-scan-thumbnail-frame",
    "last-scan-thumbnail",
    "last-scan-file-names",
    "last-scan-size",
    "last-scan-time",
    "last-scan-rotate-button",
    "last-scan-enlarge-button",
    "last-scan-hint",
    "last-scan-status",
]
SETTINGS_ELEMENT_IDENTIFIERS = [
    "resolution-select",
    "color-mode-select",
    "resolution-warning",
    "resolution-warning-text",
    "auto-crop-checkbox",
    "jpeg-quality-input",
    "jpeg-quality-value",
    "jpeg-quality-hint",
    "output-folder-save-button",
]
REMOVED_ELEMENT_IDENTIFIERS = [
    "auto-crop-hint",
    "last-scan-rotation-status",
    "last-scan-file-name",
    "frame-box",
    "frame-cutout",
    "frame-handle-north",
    "frame-handle-north-west",
    "preset-select",
    "preset-custom-option",
    "rotation-select",
    "rotation-document-hint",
]
SUPPORTED_DOTS_PER_INCH_VALUES = ("75", "100", "150", "200", "300", "400", "600", "1200")
COLOR_OPTIONS = (("color", "Colorido"), ("grayscale", "Tons de cinza"))
SELECT_OPTION_PATTERN = re.compile(r"""<option value="([^"]+)"[^>]*>([^<]+)</option>""")
SAVE_DOCUMENT_BUTTON_PATTERN = (
    r'<button id="save-document-button"[^>]*aria-label="Salvar documento"[^>]*>\s*Salvar <kbd>Enter</kbd>'
)
SAVE_FOLDER_BUTTON_PATTERN = (
    r'<button id="output-folder-save-button"[^>]*aria-label="Salvar pasta de saída"[^>]*>Salvar pasta</button>'
)
SELECT_PATTERN = re.compile(r"""<select id="([^"]+)"[^>]*>(.*?)</select>""", re.DOTALL)


def read_static_file(file_name: str) -> str:
    return (STATIC_DIRECTORY / file_name).read_text(encoding="utf-8")


def find_identifiers_used_by_script(script: str) -> set[str]:
    used_identifiers: set[str] = set()
    for pattern in SCRIPT_IDENTIFIER_PATTERNS:
        used_identifiers.update(pattern.findall(script))
    return used_identifiers


def find_elements_used_by_the_document_panel() -> set[str]:
    used_elements: set[str] = set()
    for file_name in ("document-panel.js", "page-frame-editor.js", "last-scan-panel.js"):
        script = read_static_file(file_name)
        used_elements.update(PANEL_ELEMENT_PATTERN.findall(script))
        for destructured_names in PANEL_DESTRUCTURED_ELEMENTS_PATTERN.findall(script):
            used_elements.update(name.strip() for name in destructured_names.split(",") if name.strip())
    return used_elements


@pytest.mark.parametrize("file_name", STATIC_FILE_NAMES)
def test_static_file_exists(file_name: str) -> None:
    assert (STATIC_DIRECTORY / file_name).is_file()


def test_script_uses_element_identifiers() -> None:
    assert find_identifiers_used_by_script(read_static_file("application.js"))


def test_every_element_identifier_used_by_script_exists_in_page() -> None:
    used_identifiers = find_identifiers_used_by_script(read_static_file("application.js"))
    declared_identifiers = set(PAGE_IDENTIFIER_PATTERN.findall(read_static_file("index.html")))
    assert used_identifiers - declared_identifiers == set()


def test_document_panel_uses_page_elements() -> None:
    assert find_elements_used_by_the_document_panel()


def test_every_element_used_by_the_document_panel_is_collected_by_the_page() -> None:
    collected_elements = set(COLLECTED_ELEMENT_PATTERN.findall(read_static_file("application.js")))
    assert find_elements_used_by_the_document_panel() - collected_elements == set()


@pytest.mark.parametrize("element_identifier", DOCUMENT_ELEMENT_IDENTIFIERS)
def test_page_declares_document_mode_element(element_identifier: str) -> None:
    assert element_identifier in PAGE_IDENTIFIER_PATTERN.findall(read_static_file("index.html"))


@pytest.mark.parametrize("element_identifier", FRAME_DIALOG_ELEMENT_IDENTIFIERS)
def test_page_declares_the_frame_dialog_element(element_identifier: str) -> None:
    assert element_identifier in PAGE_IDENTIFIER_PATTERN.findall(read_static_file("index.html"))


@pytest.mark.parametrize("element_identifier", LAST_SCAN_ELEMENT_IDENTIFIERS)
def test_page_declares_the_last_scan_element(element_identifier: str) -> None:
    assert element_identifier in PAGE_IDENTIFIER_PATTERN.findall(read_static_file("index.html"))


@pytest.mark.parametrize("element_identifier", REMOVED_ELEMENT_IDENTIFIERS)
def test_page_no_longer_declares_the_removed_setting(element_identifier: str) -> None:
    assert element_identifier not in PAGE_IDENTIFIER_PATTERN.findall(read_static_file("index.html"))


def test_every_identifier_of_the_page_is_unique() -> None:
    identifiers = PAGE_IDENTIFIER_PATTERN.findall(read_static_file("index.html"))
    assert len(identifiers) == len(set(identifiers))


@pytest.mark.parametrize("required_text", ["X-Requested-With", "digitalizadora"])
def test_script_sends_required_header(required_text: str) -> None:
    assert required_text in read_static_file("application.js")


def test_page_declares_brazilian_portuguese_language() -> None:
    assert re.search(r'<html[^>]*\blang="pt-BR"', read_static_file("index.html"))


@pytest.mark.parametrize("file_name", STATIC_FILE_NAMES)
def test_static_file_has_no_external_address(file_name: str) -> None:
    assert EXTERNAL_ADDRESS_PATTERN.search(read_static_file(file_name).replace(SVG_NAMESPACE_NAME, "")) is None


@pytest.mark.parametrize("file_name", SCRIPT_FILE_NAMES)
def test_script_has_no_console_log(file_name: str) -> None:
    assert "console.log" not in read_static_file(file_name)


@pytest.mark.parametrize(
    "served_path", ["/static/application.css", *(f"/static/{file_name}" for file_name in SCRIPT_FILE_NAMES)]
)
def test_page_references_files_served_by_static_route(served_path: str) -> None:
    assert served_path in read_static_file("index.html")


def test_page_loads_the_trigger_policy_before_the_application_script() -> None:
    page = read_static_file("index.html")
    assert page.index(POLICY_SCRIPT_PATH) < page.index(APPLICATION_SCRIPT_PATH)


def test_page_loads_the_scripts_in_dependency_order() -> None:
    assert SCRIPT_SOURCE_PATTERN.findall(read_static_file("index.html")) == SCRIPT_FILE_NAMES


@pytest.mark.parametrize(
    "api_path",
    ["/api/settings", "/api/state", "/api/printer", "/api/scans", "/api/document/pages"],
)
def test_script_calls_api_path(api_path: str) -> None:
    assert api_path in read_static_file("application.js")


@pytest.mark.parametrize("api_path", ["/api/scans/last", "/rotation", "/crops", "/detect", "/thumbnail", "/preview"])
def test_last_scan_policy_builds_the_routes_of_the_last_scan(api_path: str) -> None:
    assert api_path in read_static_file("last-scan-policy.js")


@pytest.mark.parametrize("path_text", ["/last", "/page-order", "/name", "/finalize"])
def test_document_panel_calls_document_route(path_text: str) -> None:
    assert path_text in read_static_file("document-panel.js")


@pytest.mark.parametrize(
    "path_text", ['"/api/document"', "/pages", "/thumbnail", "/preview", "/rotation", "/crops", "/detect"]
)
def test_document_page_policy_builds_the_page_routes(path_text: str) -> None:
    assert path_text in read_static_file("document-page-policy.js")


@pytest.mark.parametrize("path_builder", ["build_page_crops_path", "build_page_crops_detection_path"])
def test_document_panel_edits_the_frames_through_the_crops_routes(path_builder: str) -> None:
    assert path_builder in read_static_file("document-panel.js")


@pytest.mark.parametrize("path_constant", ["LAST_SCAN_CROPS_PATH", "LAST_SCAN_CROPS_DETECTION_PATH"])
def test_last_scan_panel_edits_the_frames_through_the_crops_routes(path_constant: str) -> None:
    assert path_constant in read_static_file("last-scan-panel.js")


def test_script_defines_byte_count_formatter() -> None:
    assert "function format_byte_count(size_in_bytes)" in read_static_file("application.js")


@pytest.mark.parametrize("option_value", ["pdf", "jpg", "single", "document"])
def test_page_offers_every_format_and_mode(option_value: str) -> None:
    assert f'value="{option_value}"' in read_static_file("index.html")


def test_page_offers_no_preset_names() -> None:
    page = read_static_file("index.html")
    assert not any(preset_name in page for preset_name in ("document_economy", "Texto econômico", "Foto (600"))


@pytest.mark.parametrize("printer_changing_path", ["/api/printer/refresh", "/api/printer/address"])
def test_script_never_changes_the_printer_connection(printer_changing_path: str) -> None:
    # The page has no refresh or address control, so nothing can swap the printer in the middle of a scan.
    assert printer_changing_path not in read_static_file("application.js")


@pytest.mark.parametrize("role", ["alert", "status"])
def test_page_declares_accessible_region(role: str) -> None:
    assert f'role="{role}"' in read_static_file("index.html")


def test_document_name_field_has_no_length_limit() -> None:
    # The server refuses a name that is too long with a clear message (R4); a maxlength would cut it silently.
    assert re.search(r'<input id="document-name-input"[^>]*\bmaxlength', read_static_file("index.html")) is None


@pytest.mark.parametrize("element_identifier", SETTINGS_ELEMENT_IDENTIFIERS)
def test_page_declares_settings_element(element_identifier: str) -> None:
    assert element_identifier in PAGE_IDENTIFIER_PATTERN.findall(read_static_file("index.html"))


def test_page_no_longer_declares_the_finalize_document_button() -> None:
    assert "finalize-document-button" not in read_static_file("index.html")


def read_select_options(select_identifier: str) -> list[tuple[str, str]]:
    selects = dict(SELECT_PATTERN.findall(read_static_file("index.html")))
    return SELECT_OPTION_PATTERN.findall(selects[select_identifier])


def test_resolution_list_offers_every_resolution_of_the_printer() -> None:
    offered_values = tuple(value for value, _ in read_select_options("resolution-select"))
    assert offered_values == SUPPORTED_DOTS_PER_INCH_VALUES


def test_resolution_values_match_the_supported_resolutions_of_the_server() -> None:
    offered_values = tuple(int(value) for value, _ in read_select_options("resolution-select"))
    assert offered_values == SUPPORTED_DOTS_PER_INCH


def test_resolution_options_say_dpi() -> None:
    assert [text for _, text in read_select_options("resolution-select")] == [
        f"{value} dpi" for value in SUPPORTED_DOTS_PER_INCH_VALUES
    ]


def test_colour_list_offers_colour_and_grayscale_only() -> None:
    assert tuple(read_select_options("color-mode-select")) == COLOR_OPTIONS


def test_the_settings_offer_only_resolution_and_colour_as_lists() -> None:
    settings = read_static_file("index.html").split('aria-label="Ajustes"')[1].split("</section>")[0]
    offered_lists = [identifier for identifier, _ in SELECT_PATTERN.findall(settings)]
    assert offered_lists == ["resolution-select", "color-mode-select"]


def test_auto_crop_checkbox_is_off_by_default_and_has_its_label() -> None:
    page = read_static_file("index.html")
    assert re.search(r'<input id="auto-crop-checkbox" type="checkbox"(?![^>]*\bchecked)[^>]*>', page)


def test_auto_crop_label_names_the_background_removal() -> None:
    assert "Cortar automaticamente e remover o fundo" in read_static_file("index.html")


def test_the_settings_box_no_longer_explains_the_crop() -> None:
    page = " ".join(read_static_file("index.html").split())
    assert "Use para fotos e folhas menores que o vidro" not in page


def test_the_crop_checkbox_is_not_described_by_a_hint() -> None:
    page = read_static_file("index.html")
    checkbox = re.search(r'<input id="auto-crop-checkbox"[^>]*>', page)
    assert checkbox is not None and "aria-describedby" not in checkbox.group(0)


def test_jpeg_quality_is_a_slider_from_50_to_100() -> None:
    page = read_static_file("index.html")
    assert re.search(r'<input id="jpeg-quality-input" type="range"[^>]*min="50"[^>]*max="100"[^>]*step="1"', page)


def test_jpeg_quality_starts_at_90_in_the_page() -> None:
    assert re.search(r'<input id="jpeg-quality-input"[^>]*\svalue="90"', read_static_file("index.html"))


def test_jpeg_quality_has_a_label_and_shows_its_number() -> None:
    page = read_static_file("index.html")
    assert (
        '<label for="jpeg-quality-input">Qualidade do JPEG</label>' in page
        and re.search(r'<output id="jpeg-quality-value"[^>]*for="jpeg-quality-input"[^>]*>90</output>', page)
    )


def test_jpeg_quality_has_a_single_short_hint_tied_to_the_slider() -> None:
    page = read_static_file("index.html")
    assert re.search(r'aria-describedby="jpeg-quality-hint"', page) and re.search(
        r'<p id="jpeg-quality-hint"[^>]*>Vale quando a imagem é cortada ou girada\.</p>', page
    )


def test_last_scan_rotate_button_names_its_action() -> None:
    page = read_static_file("index.html")
    assert re.search(
        r'<button id="last-scan-rotate-button"[^>]*aria-label="Girar a última digitalização 90 graus para a direita"',
        page,
    )


def test_last_scan_enlarge_button_names_its_action() -> None:
    page = read_static_file("index.html")
    assert re.search(
        r'<button id="last-scan-enlarge-button"[^>]*'
        r'aria-label="Ampliar a última digitalização e ajustar a moldura de corte"',
        page,
    )


def test_last_scan_buttons_come_in_the_documented_order() -> None:
    page = read_static_file("index.html")
    labels = re.findall(r'<button id="last-scan-(?:rotate|enlarge)-button"[^>]*>([^<]+)</button>', page)
    assert labels == ["Girar ↻", "Ampliar"]


def test_last_scan_hint_says_the_adjustments_rewrite_the_files() -> None:
    assert "Ajustes regravam os arquivos salvos." in read_static_file("index.html")


def test_last_scan_status_is_a_polite_live_region() -> None:
    page = read_static_file("index.html")
    assert re.search(r'<p id="last-scan-status"[^>]*role="status"[^>]*aria-live="polite"', page)


def test_last_scan_lists_its_files_under_a_plural_heading() -> None:
    assert "<dt>Arquivos</dt>" in read_static_file("index.html")


def test_frame_dialog_is_a_labelled_modal_dialog() -> None:
    page = read_static_file("index.html")
    assert re.search(r'<dialog id="page-frame-dialog"[^>]*aria-labelledby="page-frame-title"', page)


def test_frame_dialog_is_described_by_its_help_and_its_limits() -> None:
    page = read_static_file("index.html")
    assert re.search(r'<dialog id="page-frame-dialog"[^>]*aria-describedby="page-frame-help page-frame-limits"', page)


def test_frame_dialog_status_is_a_polite_live_region() -> None:
    assert re.search(r'<p id="frame-status"[^>]*role="status"[^>]*aria-live="polite"', read_static_file("index.html"))


def test_frame_handles_are_buttons_so_that_space_never_scans() -> None:
    handles = re.findall(
        r'<(\w+) id="frame-(?:corner-[a-z-]+|edge-[a-z]+|move-button|rotate-handle|select-button)"',
        read_static_file("index.html"),
    )
    assert handles == ["button"] * 11


def test_frame_dialog_explains_the_keyboard_and_the_rotate_handle() -> None:
    page = " ".join(read_static_file("index.html").split())
    assert (
        "Arraste os cantos, os lados ou a moldura toda. A alça de cima gira a moldura. "
        "Com o teclado, escolha uma alça (Tab) e use as setas; Shift anda mais."
    ) in page


def test_frame_dialog_warns_about_photos_that_are_too_close() -> None:
    page = " ".join(read_static_file("index.html").split())
    assert "Duas fotos muito juntas podem virar uma só moldura: use Adicionar moldura." in page


def test_frame_dialog_buttons_come_in_the_documented_order() -> None:
    page = read_static_file("index.html")
    labels = re.findall(
        r'<button id="frame-(?:add|remove|turn|detect|clear|rotate|cancel|apply)-button"[^>]*>([^<]+)</button>', page
    )
    assert labels == [
        "Adicionar moldura",
        "Remover moldura",
        "Girar moldura ↻",
        "Detectar automaticamente",
        "Sem corte",
        "Girar ↻",
        "Cancelar",
        "Aplicar",
    ]


def test_frame_dialog_handles_come_in_the_documented_tab_order() -> None:
    page = read_static_file("index.html")
    identifiers = re.findall(
        r'<button id="(frame-(?:corner-[a-z-]+|edge-[a-z]+|move-button|rotate-handle|select-button))"', page
    )
    assert identifiers == [
        "frame-corner-top-left",
        "frame-corner-top-right",
        "frame-corner-bottom-right",
        "frame-corner-bottom-left",
        "frame-edge-top",
        "frame-edge-right",
        "frame-edge-bottom",
        "frame-edge-left",
        "frame-move-button",
        "frame-rotate-handle",
        "frame-select-button",
    ]


def test_save_document_button_has_the_accessible_name_and_the_enter_hint() -> None:
    page = read_static_file("index.html")
    assert re.search(SAVE_DOCUMENT_BUTTON_PATTERN, page)


def test_folder_button_is_renamed_to_save_folder() -> None:
    page = read_static_file("index.html")
    assert re.search(SAVE_FOLDER_BUTTON_PATTERN, page)


def test_page_has_no_finalize_wording_left_for_the_user() -> None:
    assert "Finalizar" not in read_static_file("index.html")

import re
from pathlib import Path

import pytest

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_quality import SUPPORTED_DOTS_PER_INCH

STATIC_DIRECTORY = Path(__file__).resolve().parents[2] / "src" / "digitalizadora" / "web" / "static"
SCRIPT_FILE_NAMES = [
    "scan-trigger-policy.js",
    "scan-quality-policy.js",
    "error-banner.js",
    "document-page-policy.js",
    "document-panel.js",
    "application.js",
]
STATIC_FILE_NAMES = ["index.html", "application.css", *SCRIPT_FILE_NAMES]
SCRIPT_IDENTIFIER_PATTERNS = (
    re.compile(r"""getElementById\(\s*["']([^"']+)["']\s*\)"""),
    re.compile(r"""querySelector\(\s*["']#([A-Za-z0-9_-]+)"""),
)
PAGE_IDENTIFIER_PATTERN = re.compile(r"""\bid\s*=\s*["']([^"']+)["']""")
EXTERNAL_ADDRESS_PATTERN = re.compile(r"""https?://|(?:src|href)\s*=\s*["']//""")
SCRIPT_SOURCE_PATTERN = re.compile(r"""<script\s+src="/static/([^"]+)\"""")
COLLECTED_ELEMENT_PATTERN = re.compile(r"""^\s+([a-z_]+): document\.getElementById\(""", re.MULTILINE)
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
SETTINGS_ELEMENT_IDENTIFIERS = [
    "preset-select",
    "preset-custom-option",
    "resolution-select",
    "color-mode-select",
    "resolution-warning",
    "resolution-warning-text",
    "rotation-select",
    "rotation-document-hint",
    "auto-crop-checkbox",
    "auto-crop-hint",
    "output-folder-save-button",
]
SUPPORTED_DOTS_PER_INCH_VALUES = ("75", "100", "150", "200", "300", "400", "600", "1200")
ROTATION_OPTIONS = (("0", "Sem girar"), ("90", "90° à direita"), ("180", "180°"), ("270", "90° à esquerda"))
COLOR_OPTIONS = (("color", "Colorido"), ("grayscale", "Tons de cinza"))
PRESET_OPTION_PATTERN = re.compile(r"""<option value="([a-z_]+)">[^<(]*\((\d+) dpi, (cor|cinza)\)</option>""")
COLOR_MODES_BY_PRESET_TEXT = {"cor": ColorMode.COLOR, "cinza": ColorMode.GRAYSCALE}
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
    script = read_static_file("document-panel.js")
    used_elements = set(PANEL_ELEMENT_PATTERN.findall(script))
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


@pytest.mark.parametrize("required_text", ["X-Requested-With", "digitalizadora"])
def test_script_sends_required_header(required_text: str) -> None:
    assert required_text in read_static_file("application.js")


def test_page_declares_brazilian_portuguese_language() -> None:
    assert re.search(r'<html[^>]*\blang="pt-BR"', read_static_file("index.html"))


@pytest.mark.parametrize("file_name", STATIC_FILE_NAMES)
def test_static_file_has_no_external_address(file_name: str) -> None:
    assert EXTERNAL_ADDRESS_PATTERN.search(read_static_file(file_name)) is None


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


def test_page_loads_the_six_scripts_in_dependency_order() -> None:
    assert SCRIPT_SOURCE_PATTERN.findall(read_static_file("index.html")) == SCRIPT_FILE_NAMES


@pytest.mark.parametrize(
    "api_path", ["/api/settings", "/api/state", "/api/printer", "/api/scans", "/api/document/pages"]
)
def test_script_calls_api_path(api_path: str) -> None:
    assert api_path in read_static_file("application.js")


@pytest.mark.parametrize(
    "path_text", ['"/api/document"', "/pages", "/last", "/page-order", "/name", "/finalize", "/thumbnail", "/rotation"]
)
def test_document_panel_calls_document_route(path_text: str) -> None:
    assert path_text in read_static_file("document-panel.js")


def test_script_defines_byte_count_formatter() -> None:
    assert "function format_byte_count(size_in_bytes)" in read_static_file("application.js")


@pytest.mark.parametrize("option_value", ["pdf", "jpg", "document", "document_economy", "photo", "single"])
def test_page_offers_every_format_preset_and_mode(option_value: str) -> None:
    assert f'value="{option_value}"' in read_static_file("index.html")


@pytest.mark.parametrize(
    "option_text", ["Texto (300 dpi, cor)", "Texto econômico (200 dpi, cinza)", "Foto (600 dpi, cor)"]
)
def test_quality_options_use_the_new_names(option_text: str) -> None:
    assert f">{option_text}</option>" in read_static_file("index.html")


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


def test_rotation_list_offers_the_four_turns() -> None:
    assert tuple(read_select_options("rotation-select")) == ROTATION_OPTIONS


def test_preset_list_ends_with_the_custom_option_that_cannot_be_chosen() -> None:
    page = read_static_file("index.html")
    assert re.search(r'<option id="preset-custom-option" value="custom" disabled', page)


def test_preset_options_of_the_page_match_the_presets_of_the_server() -> None:
    page_presets = {
        value: (int(dots_per_inch), COLOR_MODES_BY_PRESET_TEXT[color_text])
        for value, dots_per_inch, color_text in PRESET_OPTION_PATTERN.findall(read_static_file("index.html"))
    }
    server_presets = {
        preset.value: (preset.settings.dots_per_inch, preset.settings.color_mode) for preset in ScanPreset
    }
    assert page_presets == server_presets


def test_auto_crop_checkbox_is_off_by_default_and_has_its_label() -> None:
    page = read_static_file("index.html")
    assert re.search(r'<input id="auto-crop-checkbox" type="checkbox"(?![^>]*\bchecked)[^>]*>', page)


def test_auto_crop_label_names_the_background_removal() -> None:
    assert "Cortar automaticamente e remover o fundo" in read_static_file("index.html")


def test_save_document_button_has_the_accessible_name_and_the_enter_hint() -> None:
    page = read_static_file("index.html")
    assert re.search(SAVE_DOCUMENT_BUTTON_PATTERN, page)


def test_folder_button_is_renamed_to_save_folder() -> None:
    page = read_static_file("index.html")
    assert re.search(SAVE_FOLDER_BUTTON_PATTERN, page)


def test_page_has_no_finalize_wording_left_for_the_user() -> None:
    assert "Finalizar" not in read_static_file("index.html")

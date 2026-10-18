import re
from pathlib import Path

import pytest

STATIC_DIRECTORY = Path(__file__).resolve().parents[2] / "src" / "digitalizadora" / "web" / "static"
SCRIPT_FILE_NAMES = [
    "scan-trigger-policy.js",
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
    "finalize-document-button",
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


def test_page_loads_the_five_scripts_in_dependency_order() -> None:
    assert SCRIPT_SOURCE_PATTERN.findall(read_static_file("index.html")) == SCRIPT_FILE_NAMES


@pytest.mark.parametrize(
    "api_path", ["/api/settings", "/api/state", "/api/printer", "/api/scans", "/api/document/pages"]
)
def test_script_calls_api_path(api_path: str) -> None:
    assert api_path in read_static_file("application.js")


@pytest.mark.parametrize(
    "path_text", ['"/api/document"', "/pages", "/last", "/page-order", "/name", "/finalize", "/thumbnail"]
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

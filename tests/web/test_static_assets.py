import re
from pathlib import Path

import pytest

STATIC_DIRECTORY = Path(__file__).resolve().parents[2] / "src" / "digitalizadora" / "web" / "static"
STATIC_FILE_NAMES = ["index.html", "application.css", "scan-trigger-policy.js", "application.js"]
SCRIPT_IDENTIFIER_PATTERNS = (
    re.compile(r"""getElementById\(\s*["']([^"']+)["']\s*\)"""),
    re.compile(r"""querySelector\(\s*["']#([A-Za-z0-9_-]+)"""),
)
PAGE_IDENTIFIER_PATTERN = re.compile(r"""\bid\s*=\s*["']([^"']+)["']""")
EXTERNAL_ADDRESS_PATTERN = re.compile(r"""https?://|(?:src|href)\s*=\s*["']//""")
POLICY_SCRIPT_PATH = "/static/scan-trigger-policy.js"
APPLICATION_SCRIPT_PATH = "/static/application.js"


def read_static_file(file_name: str) -> str:
    return (STATIC_DIRECTORY / file_name).read_text(encoding="utf-8")


def find_identifiers_used_by_script(script: str) -> set[str]:
    used_identifiers: set[str] = set()
    for pattern in SCRIPT_IDENTIFIER_PATTERNS:
        used_identifiers.update(pattern.findall(script))
    return used_identifiers


@pytest.mark.parametrize("file_name", STATIC_FILE_NAMES)
def test_static_file_exists(file_name: str) -> None:
    assert (STATIC_DIRECTORY / file_name).is_file()


def test_script_uses_element_identifiers() -> None:
    assert find_identifiers_used_by_script(read_static_file("application.js"))


def test_every_element_identifier_used_by_script_exists_in_page() -> None:
    used_identifiers = find_identifiers_used_by_script(read_static_file("application.js"))
    declared_identifiers = set(PAGE_IDENTIFIER_PATTERN.findall(read_static_file("index.html")))
    assert used_identifiers - declared_identifiers == set()


@pytest.mark.parametrize("required_text", ["X-Requested-With", "digitalizadora"])
def test_script_sends_required_header(required_text: str) -> None:
    assert required_text in read_static_file("application.js")


def test_page_declares_brazilian_portuguese_language() -> None:
    assert re.search(r'<html[^>]*\blang="pt-BR"', read_static_file("index.html"))


@pytest.mark.parametrize("file_name", STATIC_FILE_NAMES)
def test_static_file_has_no_external_address(file_name: str) -> None:
    assert EXTERNAL_ADDRESS_PATTERN.search(read_static_file(file_name)) is None


def test_script_has_no_console_log() -> None:
    assert "console.log" not in read_static_file("application.js")


@pytest.mark.parametrize("served_path", ["/static/application.css", POLICY_SCRIPT_PATH, APPLICATION_SCRIPT_PATH])
def test_page_references_files_served_by_static_route(served_path: str) -> None:
    assert served_path in read_static_file("index.html")


def test_page_loads_the_trigger_policy_before_the_application_script() -> None:
    page = read_static_file("index.html")
    assert page.index(POLICY_SCRIPT_PATH) < page.index(APPLICATION_SCRIPT_PATH)


@pytest.mark.parametrize("api_path", ["/api/settings", "/api/state", "/api/printer", "/api/scans"])
def test_script_calls_api_path(api_path: str) -> None:
    assert api_path in read_static_file("application.js")


def test_script_defines_byte_count_formatter() -> None:
    assert "function format_byte_count(size_in_bytes)" in read_static_file("application.js")


@pytest.mark.parametrize("option_value", ["pdf", "jpg", "document", "document_economy", "photo"])
def test_page_offers_every_format_and_preset(option_value: str) -> None:
    assert f'value="{option_value}"' in read_static_file("index.html")


@pytest.mark.parametrize("printer_changing_path", ["/api/printer/refresh", "/api/printer/address"])
def test_script_never_changes_the_printer_connection(printer_changing_path: str) -> None:
    # The page has no refresh or address control, so nothing can swap the printer in the middle of a scan.
    assert printer_changing_path not in read_static_file("application.js")


@pytest.mark.parametrize("role", ["alert", "status"])
def test_page_declares_accessible_region(role: str) -> None:
    assert f'role="{role}"' in read_static_file("index.html")

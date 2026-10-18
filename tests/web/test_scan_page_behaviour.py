import json
import shutil
import subprocess
from pathlib import Path

import pytest

NODE_EXECUTABLE = shutil.which("node")
HARNESS_PATH = Path(__file__).resolve().parent / "scan-page-harness.js"
HARNESS_TIMEOUT_SECONDS = 30
SCAN_ALREADY_RUNNING_MESSAGE = "Já existe uma digitalização em andamento."
SCANNING_MESSAGE = "Digitalizando… (cerca de 15 s; no modo Foto, cerca de 75 s)"
OUTPUT_FOLDER_UNAVAILABLE_TEXT = "Pasta de saída indisponível. Se for um disco externo, confira se está conectado."

pytestmark = pytest.mark.skipif(
    NODE_EXECUTABLE is None, reason="Node.js is not installed, so application.js cannot be exercised"
)


@pytest.fixture(scope="module")
def scenario_results() -> dict:
    completed = subprocess.run(
        [NODE_EXECUTABLE, str(HARNESS_PATH)],
        capture_output=True,
        text=True,
        timeout=HARNESS_TIMEOUT_SECONDS,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_space_on_the_page_starts_one_scan(scenario_results: dict) -> None:
    assert scenario_results["space_on_the_page_body"]["scan_requests"] == 1


def test_space_on_the_page_does_not_scroll_it(scenario_results: dict) -> None:
    assert scenario_results["space_on_the_page_body"]["default_prevented"] is True


def test_space_on_the_focused_scan_button_starts_one_scan(scenario_results: dict) -> None:
    assert scenario_results["space_on_the_scan_button"]["scan_requests"] == 1


@pytest.mark.parametrize(
    "scenario_name",
    [
        "space_in_the_folder_field",
        "space_on_the_preset_select",
        "space_on_a_format_option",
        "space_on_the_folder_save_button",
    ],
)
def test_space_keeps_its_own_meaning_in_other_controls(scenario_results: dict, scenario_name: str) -> None:
    assert scenario_results[scenario_name] == {"scan_requests": 0, "default_prevented": False}


def test_repeated_keydown_never_starts_a_scan(scenario_results: dict) -> None:
    assert scenario_results["repeated_space_only"]["scan_requests"] == 0


def test_repeated_keydown_is_swallowed(scenario_results: dict) -> None:
    assert scenario_results["repeated_space_only"]["default_prevented"] is True


def test_held_space_starts_one_scan(scenario_results: dict) -> None:
    assert scenario_results["held_space"]["scan_requests"] == 1


def test_double_click_sends_one_scan_request(scenario_results: dict) -> None:
    assert scenario_results["double_click_while_the_request_is_pending"]["scan_requests"] == 1


def test_scan_button_is_disabled_while_the_request_is_pending(scenario_results: dict) -> None:
    assert scenario_results["double_click_while_the_request_is_pending"]["button_disabled"] is True


def test_start_scan_ignores_a_second_call_while_the_request_is_pending(scenario_results: dict) -> None:
    assert scenario_results["start_scan_called_twice_while_pending"]["scan_requests"] == 1


def test_space_during_a_scan_sends_no_request(scenario_results: dict) -> None:
    assert scenario_results["space_during_a_scan"]["scan_requests"] == 0


def test_scan_button_is_disabled_during_a_scan(scenario_results: dict) -> None:
    assert scenario_results["space_during_a_scan"]["button_disabled"] is True


def test_scan_button_is_enabled_when_idle(scenario_results: dict) -> None:
    assert scenario_results["idle_page"]["button_disabled"] is False


def test_scanning_status_shows_the_measured_durations(scenario_results: dict) -> None:
    assert scenario_results["scanning_page"]["status_text"] == SCANNING_MESSAGE


def test_printer_is_not_polled_during_a_scan(scenario_results: dict) -> None:
    assert scenario_results["printer_poll_during_a_scan"]["extra_printer_requests"] == 0


def test_printer_is_not_asked_while_it_settles_after_a_scan(scenario_results: dict) -> None:
    assert scenario_results["printer_after_a_scan"]["immediate_printer_requests"] == 0


def test_header_stays_ready_right_after_a_scan(scenario_results: dict) -> None:
    assert scenario_results["printer_after_a_scan"]["chip_text_right_after"] == "Impressora pronta (USB)"


def test_printer_is_asked_once_it_has_settled_after_a_scan(scenario_results: dict) -> None:
    result = scenario_results["printer_after_a_scan"]
    assert (result["delayed_printer_requests"], result["chip_text_after_the_delay"]) == (1, "Impressora pronta (USB)")


def test_scan_request_carries_the_required_header(scenario_results: dict) -> None:
    assert scenario_results["scan_request_headers"]["headers"] == {"X-Requested-With": "digitalizadora"}


def test_conflict_answer_shows_the_catalog_message_in_the_banner(scenario_results: dict) -> None:
    assert scenario_results["conflict_answer"] == {"banner_hidden": False, "banner_text": SCAN_ALREADY_RUNNING_MESSAGE}


def test_unavailable_output_folder_replaces_the_free_space_line(scenario_results: dict) -> None:
    assert scenario_results["unavailable_output_folder"]["storage_text"] == OUTPUT_FOLDER_UNAVAILABLE_TEXT


def test_unavailable_output_folder_hides_the_external_disk_warning(scenario_results: dict) -> None:
    assert scenario_results["unavailable_output_folder"]["warning_hidden"] is True


def test_low_free_space_shows_the_external_disk_warning(scenario_results: dict) -> None:
    assert scenario_results["low_free_space"]["warning_hidden"] is False


@pytest.mark.parametrize(
    ("scenario_name", "expected_text"),
    [("printer_on_usb", "Impressora pronta (USB)"), ("printer_on_wifi", "Impressora pronta (Wi-Fi)")],
)
def test_ready_printer_shows_its_route(scenario_results: dict, scenario_name: str, expected_text: str) -> None:
    assert scenario_results[scenario_name]["chip_text"] == expected_text


@pytest.mark.parametrize(
    ("size_in_bytes", "expected_text"),
    [
        ("0", "0 B"),
        ("999", "999 B"),
        ("1000", "1,0 KB"),
        ("999949", "999,9 KB"),
        ("999950", "1,0 MB"),
        ("1234567", "1,2 MB"),
        ("5000000000", "5,0 GB"),
    ],
)
def test_byte_count_is_formatted_in_portuguese(scenario_results: dict, size_in_bytes: str, expected_text: str) -> None:
    assert scenario_results["byte_counts"][size_in_bytes] == expected_text


@pytest.mark.parametrize(
    ("page_count", "expected_text"),
    [("0", "cabem ~0 páginas"), ("1", "cabe ~1 página"), ("1234", "cabem ~1.234 páginas")],
)
def test_pages_remaining_are_described_in_portuguese(
    scenario_results: dict, page_count: str, expected_text: str
) -> None:
    assert scenario_results["page_counts"][page_count] == expected_text

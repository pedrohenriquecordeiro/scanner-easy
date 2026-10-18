import json
import shutil
import subprocess
from pathlib import Path

import pytest

NODE_EXECUTABLE = shutil.which("node")
HARNESS_PATH = Path(__file__).resolve().parent / "scan-page-harness.js"
HARNESS_TIMEOUT_SECONDS = 30
SCAN_ALREADY_RUNNING_MESSAGE = "Já existe uma digitalização em andamento."
SCANNING_MESSAGE = "Digitalizando… (cerca de 15 s)"
SLOW_RESOLUTION_WARNING = "1200 dpi pode levar vários minutos e gerar arquivos muito grandes."
SETTINGS_BODY = {
    "output_folder": "/Users/teste/Digitalizadora",
    "output_format": "pdf",
    "dots_per_inch": 300,
    "color_mode": "color",
    "capture_mode": "single",
    "auto_crop": False,
    "crop_margin": True,
    "jpeg_quality": 90,
}
FOLDER_REFUSED_MESSAGE = "Não consigo usar essa pasta de saída."
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
        "space_on_a_format_option",
        "space_on_the_folder_save_button",
        "space_on_the_resolution_select",
        "space_on_the_color_mode_select",
        "space_on_the_auto_crop_checkbox",
        "space_on_the_quality_slider",
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


@pytest.mark.parametrize(
    ("scenario_name", "changes"),
    [
        ("change_the_resolution", {"dots_per_inch": 600}),
        ("change_the_color_mode", {"color_mode": "grayscale"}),
        ("turn_auto_crop_on", {"auto_crop": True}),
        ("turn_crop_margin_off", {"crop_margin": False}),
    ],
)
def test_changing_a_setting_sends_all_the_saved_settings_with_the_change(
    scenario_results: dict, scenario_name: str, changes: dict
) -> None:
    assert scenario_results[scenario_name]["settings_request_body"] == {**SETTINGS_BODY, **changes}


SELECT_SCENARIOS = ["change_the_resolution", "change_the_color_mode"]


@pytest.mark.parametrize("scenario_name", SELECT_SCENARIOS)
def test_a_select_keeps_the_focus_after_its_change_so_the_arrows_can_go_on(
    scenario_results: dict, scenario_name: str
) -> None:
    assert scenario_results[scenario_name]["control_focused"] is True


def test_a_refused_select_change_keeps_the_focus_on_the_select(scenario_results: dict) -> None:
    assert scenario_results["refused_resolution_focus"]["control_focused"] is True


def test_the_scan_button_gets_the_focus_after_toggling_the_auto_crop(scenario_results: dict) -> None:
    assert scenario_results["turn_auto_crop_on"]["scan_button_focused"] is True


def test_the_crop_margin_is_on_and_disabled_while_the_auto_crop_is_off(scenario_results: dict) -> None:
    controls = scenario_results["default_settings_controls"]
    assert (controls["crop_margin"], controls["crop_margin_disabled"]) == (True, True)


def test_the_saved_crop_margin_choice_shows_and_is_enabled_with_the_auto_crop_on(scenario_results: dict) -> None:
    controls = scenario_results["crop_margin_with_the_auto_crop_on"]
    assert (controls["crop_margin"], controls["crop_margin_disabled"]) == (False, False)


def test_saved_settings_fill_the_quality_controls(scenario_results: dict) -> None:
    controls = scenario_results["default_settings_controls"]
    assert (controls["resolution"], controls["color_mode"]) == ("300", "color")


def test_saved_settings_fill_the_crop_control(scenario_results: dict) -> None:
    assert scenario_results["default_settings_controls"]["auto_crop"] is False


def test_the_page_has_no_preset_list(scenario_results: dict) -> None:
    assert scenario_results["settings_without_preset_and_rotation"]["has_preset_select"] is False


def test_the_page_has_no_rotation_list_in_the_settings(scenario_results: dict) -> None:
    assert scenario_results["settings_without_preset_and_rotation"]["has_rotation_select"] is False


def test_the_page_has_no_rotation_hint_in_the_settings(scenario_results: dict) -> None:
    assert scenario_results["settings_without_preset_and_rotation"]["has_rotation_hint"] is False


def test_the_resolution_warning_is_hidden_at_300_dpi(scenario_results: dict) -> None:
    controls = scenario_results["default_settings_controls"]
    assert (controls["warning_hidden"], controls["warning_text"]) == (True, "")


def test_the_resolution_warning_is_shown_at_1200_dpi(scenario_results: dict) -> None:
    controls = scenario_results["slow_and_cropping_controls"]
    assert (controls["warning_hidden"], controls["warning_text"]) == (False, SLOW_RESOLUTION_WARNING)


def test_saved_crop_and_colour_fill_their_controls(scenario_results: dict) -> None:
    controls = scenario_results["slow_and_cropping_controls"]
    assert (controls["auto_crop"], controls["color_mode"]) == (True, "grayscale")


def test_a_server_without_the_new_settings_leaves_the_crop_off(scenario_results: dict) -> None:
    assert scenario_results["old_server_controls"]["auto_crop"] is False


def test_a_server_without_the_new_settings_shows_no_resolution_warning(scenario_results: dict) -> None:
    assert scenario_results["old_server_controls"]["warning_hidden"] is True


def test_a_refused_setting_shows_the_server_message(scenario_results: dict) -> None:
    assert scenario_results["refused_resolution"]["banner_text"] == "A resolução escolhida não é aceita."


def test_a_refused_setting_puts_the_controls_back_to_the_saved_values(scenario_results: dict) -> None:
    assert scenario_results["refused_resolution"]["controls"]["resolution"] == "300"


def test_scanning_status_follows_the_resolution(scenario_results: dict) -> None:
    assert scenario_results["scanning_at_a_high_resolution"]["status_text"] == "Digitalizando… (vários minutos)"


def test_the_quality_slider_starts_at_the_default(scenario_results: dict) -> None:
    controls = scenario_results["default_settings_controls"]
    assert (controls["jpeg_quality"], controls["jpeg_quality_text"]) == ("90", "90")


def test_the_saved_quality_fills_the_slider_and_its_number(scenario_results: dict) -> None:
    controls = scenario_results["quality_filled_from_the_saved_settings"]
    assert (controls["jpeg_quality"], controls["jpeg_quality_text"]) == ("60", "60")


def test_a_server_without_the_quality_setting_leaves_the_default(scenario_results: dict) -> None:
    controls = scenario_results["old_server_controls"]
    assert (controls["jpeg_quality"], controls["jpeg_quality_text"]) == ("90", "90")


def test_the_number_follows_the_slider_while_it_moves(scenario_results: dict) -> None:
    assert scenario_results["move_the_quality_slider"]["controls"]["jpeg_quality_text"] == "75"


def test_moving_the_slider_saves_nothing_until_it_is_let_go(scenario_results: dict) -> None:
    assert scenario_results["move_the_quality_slider"]["settings_requests"] == 0


def test_a_value_the_slider_cannot_hold_shows_the_default(scenario_results: dict) -> None:
    assert scenario_results["move_the_quality_slider_to_nonsense"]["jpeg_quality_text"] == "90"


def test_letting_the_slider_go_saves_the_quality_with_the_other_settings(scenario_results: dict) -> None:
    body = scenario_results["release_the_quality_slider"]["settings_request_body"]
    assert body == {**SETTINGS_BODY, "jpeg_quality": 75}


def test_letting_the_slider_go_keeps_the_focus_on_it(scenario_results: dict) -> None:
    result = scenario_results["release_the_quality_slider"]
    assert (result["slider_focused"], result["scan_button_focused"]) == (True, False)


def test_a_key_held_on_the_slider_saves_only_the_last_quality_once(scenario_results: dict) -> None:
    result = scenario_results["hold_a_key_on_the_quality_slider"]
    assert (result["requests_while_holding"], result["requests_after"], result["saved_quality"]) == (0, 1, 70)


def test_an_answer_about_an_older_quality_does_not_take_the_slider_back(scenario_results: dict) -> None:
    controls = scenario_results["answer_about_an_older_quality_while_the_slider_moved_on"]
    assert (controls["jpeg_quality"], controls["jpeg_quality_text"]) == ("60", "60")


def test_another_setting_goes_with_the_saved_quality(scenario_results: dict) -> None:
    body = scenario_results["quality_kept_while_another_setting_changes"]["settings_request_body"]
    assert (body["jpeg_quality"], body["dots_per_inch"]) == (60, 600)


def test_a_refused_quality_shows_the_server_message_and_puts_the_slider_back(scenario_results: dict) -> None:
    result = scenario_results["refused_quality"]
    assert (result["banner_text"], result["controls"]["jpeg_quality"], result["controls"]["jpeg_quality_text"]) == (
        "A resolução escolhida não é aceita.",
        "90",
        "90",
    )


def test_the_crop_checkbox_has_no_hint_any_more(scenario_results: dict) -> None:
    assert scenario_results["settings_without_the_crop_hint"] == {"has_hint": False, "checkbox_description": None}


def test_folder_button_is_busy_and_disabled_while_the_server_has_not_answered(scenario_results: dict) -> None:
    result = scenario_results["folder_save_before_the_answer"]
    assert (result["button_label"], result["button_disabled"], result["button_busy"]) == ("Salvando…", True, "true")


def test_folder_save_shows_no_confirmation_before_the_answer(scenario_results: dict) -> None:
    assert scenario_results["folder_save_before_the_answer"]["confirmation_text"] == ""


def test_folder_button_returns_to_normal_after_the_answer(scenario_results: dict) -> None:
    result = scenario_results["folder_save_answered"]
    assert (result["button_label"], result["button_disabled"], result["button_busy"]) == ("Salvar", False, "false")


def test_folder_save_confirms_with_the_saved_folder_message(scenario_results: dict) -> None:
    result = scenario_results["folder_save_answered"]
    assert (result["confirmation_text"], result["confirmation_hidden"]) == ("✔ Pasta salva", False)


def test_folder_save_sends_the_typed_folder(scenario_results: dict) -> None:
    assert scenario_results["folder_save_answered"]["settings_request_body"]["output_folder"] == "/Volumes/Arquivo"


def test_folder_save_hands_the_focus_to_the_scan_button(scenario_results: dict) -> None:
    assert scenario_results["folder_save_answered"]["scan_button_focused"] is True


def test_folder_confirmation_waits_for_its_timer_to_end(scenario_results: dict) -> None:
    assert scenario_results["folder_save_answered"]["pending_confirmation_timers"] == 1


def test_folder_confirmation_disappears_when_its_timer_ends(scenario_results: dict) -> None:
    result = scenario_results["folder_confirmation_after_it_ends"]
    assert (result["confirmation_text"], result["confirmation_hidden"]) == ("", True)


def test_folder_confirmation_leaves_no_timer_behind(scenario_results: dict) -> None:
    assert scenario_results["folder_confirmation_after_it_ends"]["pending_confirmation_timers"] == 0


def test_refused_folder_shows_the_message_of_the_server(scenario_results: dict) -> None:
    result = scenario_results["folder_save_refused"]
    assert (result["error_text"], result["error_hidden"]) == (FOLDER_REFUSED_MESSAGE, False)


def test_refused_folder_shows_no_confirmation(scenario_results: dict) -> None:
    assert scenario_results["folder_save_refused"]["confirmation_text"] == ""


def test_refused_folder_returns_the_button_to_normal(scenario_results: dict) -> None:
    result = scenario_results["folder_save_refused"]
    assert (result["button_label"], result["button_disabled"], result["button_busy"]) == ("Salvar", False, "false")


def test_refused_folder_keeps_the_focus_in_the_folder_field(scenario_results: dict) -> None:
    assert scenario_results["folder_save_refused"]["input_focused"] is True


def test_a_save_after_a_refusal_clears_the_error(scenario_results: dict) -> None:
    result = scenario_results["folder_save_succeeds_after_a_refusal"]
    assert (result["error_text"], result["error_hidden"], result["confirmation_text"]) == ("", True, "✔ Pasta salva")


def test_a_refusal_after_a_success_replaces_the_confirmation(scenario_results: dict) -> None:
    result = scenario_results["folder_save_refused_after_a_success"]
    assert (result["confirmation_hidden"], result["error_text"]) == (True, FOLDER_REFUSED_MESSAGE)


def test_a_refusal_after_a_success_leaves_no_timer_behind(scenario_results: dict) -> None:
    assert scenario_results["folder_save_refused_after_a_success"]["pending_confirmation_timers"] == 0


def test_saving_the_folder_twice_keeps_a_single_confirmation_timer(scenario_results: dict) -> None:
    assert scenario_results["folder_saved_twice"]["pending_confirmation_timers"] == 1


def test_enter_in_the_folder_field_while_saving_sends_one_request(scenario_results: dict) -> None:
    assert scenario_results["enter_twice_in_the_folder_field_while_saving"]["settings_requests"] == 1


@pytest.mark.parametrize("scenario_name", ["adjustment_saved", "format_saved", "crop_boxes_saved", "quality_saved"])
def test_an_adjustment_confirms_with_the_saved_adjustment_message(scenario_results: dict, scenario_name: str) -> None:
    result = scenario_results[scenario_name]
    assert (result["confirmation_text"], result["confirmation_hidden"]) == ("✔ Ajuste salvo", False)


def test_an_adjustment_does_not_touch_the_folder_button(scenario_results: dict) -> None:
    result = scenario_results["adjustment_saved"]
    assert (result["button_busy"], result["button_disabled"]) == (None, False)


def test_an_adjustment_confirmation_disappears_when_its_timer_ends(scenario_results: dict) -> None:
    result = scenario_results["adjustment_confirmation_after_it_ends"]
    assert (result["confirmation_hidden"], result["pending_confirmation_timers"]) == (True, 0)


def test_a_refused_adjustment_shows_no_confirmation(scenario_results: dict) -> None:
    assert scenario_results["adjustment_refused"]["confirmation_text"] == ""


def test_a_refused_adjustment_leaves_no_timer_behind(scenario_results: dict) -> None:
    assert scenario_results["adjustment_refused"]["pending_confirmation_timers"] == 0


def test_changing_the_capture_mode_shows_no_adjustment_confirmation(scenario_results: dict) -> None:
    assert scenario_results["capture_mode_saved"]["confirmation_text"] == ""


def test_two_adjustments_in_a_row_keep_a_single_confirmation_timer(scenario_results: dict) -> None:
    assert scenario_results["two_adjustments_in_a_row"]["pending_confirmation_timers"] == 1


def test_scan_button_shows_the_state_while_a_scan_runs(scenario_results: dict) -> None:
    assert scenario_results["scan_button_while_scanning"]["button_label"] == "Digitalizando…"

import pytest

from tests.web.panel_scenario_runner import NODE_EXECUTABLE, run_frame_editor_scenarios

SECOND_PAGE = "0000000000000002"
SECOND_PAGE_ENLARGE_LABEL = "Ampliar a página 2 e ajustar a moldura de corte"
SECOND_PAGE_FRAME = {"left": "13%", "top": "11.5%", "width": "78.4%", "height": "80%"}
WHOLE_PAGE_FRAME = {"left": "0%", "top": "0%", "width": "100%", "height": "100%"}
WEST_DRAGGED_FRAME = {"left": "23%", "top": "11.5%", "width": "68.4%", "height": "80%"}
TURNED_SECOND_PAGE_FRAME = {"left": "8.5%", "top": "13%", "width": "80%", "height": "78.4%"}
TURNED_DRAFT_FRAME = {"left": "8.5%", "top": "23%", "width": "80%", "height": "68.4%"}
DETECTED_FRAME = {"left": "12%", "top": "11%", "width": "80%", "height": "82%"}
DISCARDED_TEXT = "Alterações da moldura descartadas."
PAGE_GONE_TEXT = "Essa página não está mais no documento."
INVALID_CROP_MESSAGE = "A moldura de corte é inválida. Ajuste e tente de novo."
SCAN_ALREADY_RUNNING_MESSAGE = "Já existe uma digitalização em andamento."
DAMAGED_PAGE_MESSAGE = (
    "Uma página guardada do documento está danificada ou sumiu do disco do Mac. "
    "Ela está marcada na grade: exclua-a e digitalize-a de novo."
)
HEADERS = {"X-Requested-With": "digitalizadora"}

SCENARIO_NAMES = (
    "apply_a_dragged_frame",
    "apply_after_opening_by_keyboard",
    "apply_without_a_crop",
    "apply_with_nothing_changed",
    "apply_enabled_after_a_change",
    "apply_refused",
    "apply_while_a_page_scans",
    "apply_conflict",
    "apply_with_space_on_the_button",
    "detect_that_finds_a_frame",
    "detect_that_finds_nothing",
    "detect_on_a_damaged_page",
    "detect_while_a_page_scans",
    "detect_on_a_page_without_a_frame",
    "rotate_in_the_dialog",
    "rotate_with_a_draft_in_the_dialog",
    "rotate_a_page_without_a_frame_in_the_dialog",
    "rotate_while_the_request_is_pending",
    "cancel_after_a_drag",
    "cancel_without_changes",
    "cancel_after_opening_by_keyboard",
    "escape_after_a_drag",
    "reopen_after_a_discarded_drag",
    "open_twice",
    "page_deleted_elsewhere",
    "document_finished_elsewhere",
    "page_added_while_open",
    "page_inserted_before_while_open",
    "crop_changed_elsewhere",
    "crop_changed_elsewhere_with_a_draft",
    "rotated_elsewhere_with_a_draft",
    "space_on_a_handle",
    "space_on_the_dialog_itself",
    "backspace_in_the_dialog",
    "enter_in_the_dialog",
    "arrows_do_not_reach_the_page_shortcuts",
)

pytestmark = pytest.mark.skipif(
    NODE_EXECUTABLE is None, reason="Node.js is not installed, so page-frame-editor.js cannot be exercised"
)


@pytest.fixture(scope="module")
def scenario_results() -> dict:
    return run_frame_editor_scenarios(SCENARIO_NAMES)


def test_apply_sends_the_dragged_frame_as_the_crop(scenario_results: dict) -> None:
    result = scenario_results["apply_a_dragged_frame"]
    assert (result["requests"], result["body"]) == (
        1,
        {"crop": {"left": 0.23, "top": 0.115, "right": 0.914, "bottom": 0.915}},
    )


def test_apply_sends_the_required_header(scenario_results: dict) -> None:
    assert scenario_results["apply_a_dragged_frame"]["headers"] == {**HEADERS, "Content-Type": "application/json"}


def test_apply_closes_the_dialog_and_announces_it(scenario_results: dict) -> None:
    result = scenario_results["apply_a_dragged_frame"]
    assert (result["open"], result["announcement"]) == (False, "Moldura aplicada à página 2.")


def test_apply_by_pointer_focuses_the_scan_button(scenario_results: dict) -> None:
    assert scenario_results["apply_a_dragged_frame"]["scan_button_focused"] is True


def test_the_frame_of_the_tile_follows_the_applied_crop(scenario_results: dict) -> None:
    assert scenario_results["apply_a_dragged_frame"]["tile_overlay"] == WEST_DRAGGED_FRAME


def test_apply_after_opening_by_keyboard_returns_the_focus_to_the_enlarge_button(scenario_results: dict) -> None:
    assert scenario_results["apply_after_opening_by_keyboard"]["focus"] == {
        "label": SECOND_PAGE_ENLARGE_LABEL,
        "page_identifier": SECOND_PAGE,
    }


def test_apply_with_no_crop_sends_null(scenario_results: dict) -> None:
    assert scenario_results["apply_without_a_crop"]["body"] == {"crop": None}


def test_apply_with_no_crop_announces_the_removal(scenario_results: dict) -> None:
    assert scenario_results["apply_without_a_crop"]["announcement"] == "Corte removido da página 2."


def test_apply_with_no_crop_takes_the_frame_off_the_tile(scenario_results: dict) -> None:
    assert scenario_results["apply_without_a_crop"]["overlay_hidden"] is True


def test_apply_is_disabled_while_nothing_changed(scenario_results: dict) -> None:
    result = scenario_results["apply_with_nothing_changed"]
    assert (result["apply_disabled"], result["requests"], result["open"]) == (True, 0, True)


def test_apply_is_enabled_by_a_change(scenario_results: dict) -> None:
    assert scenario_results["apply_enabled_after_a_change"]["apply_disabled"] is False


def test_a_refused_crop_keeps_the_dialog_open_and_says_why(scenario_results: dict) -> None:
    result = scenario_results["apply_refused"]
    assert (result["dialog"]["open"], result["dialog"]["status"]) == (True, INVALID_CROP_MESSAGE)


def test_a_refused_crop_also_goes_to_the_banner(scenario_results: dict) -> None:
    assert scenario_results["apply_refused"]["banner"] == {"hidden": False, "text": INVALID_CROP_MESSAGE}


def test_a_refused_crop_keeps_the_draft_and_the_focus_on_apply(scenario_results: dict) -> None:
    result = scenario_results["apply_refused"]
    assert (result["dialog"]["frame_box"], result["apply_focused"], result["dialog"]["apply_disabled"]) == (
        WEST_DRAGGED_FRAME,
        True,
        False,
    )


def test_apply_is_disabled_while_a_page_scans(scenario_results: dict) -> None:
    assert scenario_results["apply_while_a_page_scans"] == {"disabled_while_scanning": True, "requests": 0}


def test_apply_refused_by_a_conflict_keeps_the_dialog_open(scenario_results: dict) -> None:
    result = scenario_results["apply_conflict"]
    assert (result["open"], result["status"]) == (True, SCAN_ALREADY_RUNNING_MESSAGE)


def test_space_on_the_apply_button_applies_and_never_scans(scenario_results: dict) -> None:
    assert scenario_results["apply_with_space_on_the_button"] == {"crop_requests": 1, "page_requests": 0, "open": False}


def test_detection_that_finds_a_frame_replaces_the_draft_with_it(scenario_results: dict) -> None:
    dialog = scenario_results["detect_that_finds_a_frame"]["dialog"]
    assert (dialog["frame_box"], dialog["apply_disabled"]) == (DETECTED_FRAME, True)


def test_detection_that_finds_a_frame_says_so(scenario_results: dict) -> None:
    status = scenario_results["detect_that_finds_a_frame"]["dialog"]["status"]
    assert status == "Moldura detectada e salva. Moldura: esquerda 12%, topo 11%, direita 92%, base 93%."


def test_detection_is_saved_at_once_so_the_tile_shows_it(scenario_results: dict) -> None:
    assert scenario_results["detect_that_finds_a_frame"]["tile_overlay"] == DETECTED_FRAME


def test_detection_sends_the_required_header(scenario_results: dict) -> None:
    assert scenario_results["detect_that_finds_a_frame"]["headers"] == HEADERS


def test_detection_keeps_the_focus_on_its_button(scenario_results: dict) -> None:
    assert scenario_results["detect_that_finds_a_frame"]["detect_focused"] is True


def test_detection_that_finds_nothing_says_so_and_keeps_the_draft(scenario_results: dict) -> None:
    dialog = scenario_results["detect_that_finds_nothing"]
    assert (dialog["status"], dialog["frame_box"], dialog["apply_disabled"]) == (
        "Não achei uma borda confiável nesta página. A moldura não mudou.",
        WEST_DRAGGED_FRAME,
        False,
    )


def test_detection_on_a_damaged_page_says_why_in_the_dialog_and_in_the_banner(scenario_results: dict) -> None:
    result = scenario_results["detect_on_a_damaged_page"]
    assert (result["dialog"]["status"], result["banner"]["text"]) == (DAMAGED_PAGE_MESSAGE, DAMAGED_PAGE_MESSAGE)


def test_detection_is_disabled_while_a_page_scans(scenario_results: dict) -> None:
    assert scenario_results["detect_while_a_page_scans"] == {"disabled_while_scanning": True, "requests": 0}


def test_detection_gives_a_page_without_a_frame_the_detected_one(scenario_results: dict) -> None:
    result = scenario_results["detect_on_a_page_without_a_frame"]
    assert (result["dialog"]["frame_box"], result["tile_overlay"]) == (DETECTED_FRAME, DETECTED_FRAME)


def test_rotating_in_the_dialog_asks_for_the_turned_view(scenario_results: dict) -> None:
    right_after = scenario_results["rotate_in_the_dialog"]["right_after"]
    assert right_after["image_source"] == f"/api/document/pages/{SECOND_PAGE}/preview?rotation_degrees=90"


def test_rotating_in_the_dialog_turns_the_frame_with_the_page(scenario_results: dict) -> None:
    assert scenario_results["rotate_in_the_dialog"]["right_after"]["frame_box"] == TURNED_SECOND_PAGE_FRAME


def test_rotating_in_the_dialog_waits_for_the_new_image(scenario_results: dict) -> None:
    result = scenario_results["rotate_in_the_dialog"]
    assert (result["right_after"]["stage_loading"], result["after_loading"]["stage_loading"]) == (True, False)


def test_rotating_in_the_dialog_says_the_frame_followed(scenario_results: dict) -> None:
    status = scenario_results["rotate_in_the_dialog"]["right_after"]["status"]
    assert status == "Página 2 girada 90° para a direita. A moldura acompanhou o giro."


def test_rotating_in_the_dialog_sends_the_required_header(scenario_results: dict) -> None:
    assert scenario_results["rotate_in_the_dialog"]["headers"] == HEADERS


def test_rotating_in_the_dialog_keeps_the_focus_on_its_button(scenario_results: dict) -> None:
    assert scenario_results["rotate_in_the_dialog"]["rotate_focused"] is True


def test_rotating_in_the_dialog_turns_the_tile_thumbnail_too(scenario_results: dict) -> None:
    thumbnail_source = scenario_results["rotate_in_the_dialog"]["tile_thumbnail"]
    assert thumbnail_source == f"/api/document/pages/{SECOND_PAGE}/thumbnail?rotation_degrees=90"


def test_a_draft_turns_with_the_page_and_can_still_be_applied(scenario_results: dict) -> None:
    dialog = scenario_results["rotate_with_a_draft_in_the_dialog"]
    assert (dialog["frame_box"], dialog["apply_disabled"]) == (TURNED_DRAFT_FRAME, False)


def test_rotating_a_page_without_a_frame_does_not_talk_about_a_frame(scenario_results: dict) -> None:
    dialog = scenario_results["rotate_a_page_without_a_frame_in_the_dialog"]
    assert (dialog["status"], dialog["frame_box"]) == ("Página 1 girada 90° para a direita.", WHOLE_PAGE_FRAME)


def test_the_edit_buttons_are_disabled_while_a_rotation_runs(scenario_results: dict) -> None:
    during = scenario_results["rotate_while_the_request_is_pending"]["during"]
    assert (during["rotate_disabled"], during["detect_disabled"], during["apply_disabled"]) == (True, True, True)


def test_the_edit_buttons_are_enabled_again_after_the_rotation(scenario_results: dict) -> None:
    after = scenario_results["rotate_while_the_request_is_pending"]["after"]
    assert (after["rotate_disabled"], after["detect_disabled"]) == (False, False)


def test_cancel_closes_the_dialog_without_sending_anything(scenario_results: dict) -> None:
    result = scenario_results["cancel_after_a_drag"]
    assert (result["open"], result["crop_requests"]) == (False, 0)


def test_cancel_after_a_drag_announces_the_discarded_changes(scenario_results: dict) -> None:
    assert scenario_results["cancel_after_a_drag"]["announcement"] == DISCARDED_TEXT


def test_cancel_by_pointer_focuses_the_scan_button(scenario_results: dict) -> None:
    assert scenario_results["cancel_after_a_drag"]["scan_button_focused"] is True


def test_cancel_without_changes_announces_nothing(scenario_results: dict) -> None:
    assert scenario_results["cancel_without_changes"] == {"open": False, "announcement": ""}


def test_cancel_after_opening_by_keyboard_returns_the_focus_to_the_enlarge_button(scenario_results: dict) -> None:
    assert scenario_results["cancel_after_opening_by_keyboard"]["focus"] == {
        "label": SECOND_PAGE_ENLARGE_LABEL,
        "page_identifier": SECOND_PAGE,
    }


def test_escape_cancels_and_discards_the_draft(scenario_results: dict) -> None:
    result = scenario_results["escape_after_a_drag"]
    assert (result["open"], result["announcement"]) == (False, DISCARDED_TEXT)


def test_escape_by_pointer_opening_focuses_the_scan_button(scenario_results: dict) -> None:
    assert scenario_results["escape_after_a_drag"]["scan_button_focused"] is True


def test_reopening_after_a_discarded_drag_starts_from_the_saved_frame(scenario_results: dict) -> None:
    assert scenario_results["reopen_after_a_discarded_drag"]["frame_box"] == SECOND_PAGE_FRAME


def test_opening_while_open_does_not_open_a_second_time(scenario_results: dict) -> None:
    assert scenario_results["open_twice"]["show_count"] == 1


def test_a_page_deleted_elsewhere_closes_the_dialog_and_says_so(scenario_results: dict) -> None:
    result = scenario_results["page_deleted_elsewhere"]
    assert (result["open"], result["announcement"]) == (False, PAGE_GONE_TEXT)


def test_a_page_deleted_elsewhere_gives_the_focus_to_the_scan_button(scenario_results: dict) -> None:
    assert scenario_results["page_deleted_elsewhere"]["scan_button_focused"] is True


def test_a_document_finished_elsewhere_closes_the_dialog(scenario_results: dict) -> None:
    result = scenario_results["document_finished_elsewhere"]
    assert (result["open"], result["announcement"]) == (False, PAGE_GONE_TEXT)


def test_a_page_added_while_open_updates_the_title(scenario_results: dict) -> None:
    assert scenario_results["page_added_while_open"]["title"] == "Página 2 de 4: moldura de corte"


def test_a_page_inserted_before_updates_the_position_in_the_title(scenario_results: dict) -> None:
    assert scenario_results["page_inserted_before_while_open"]["title"] == "Página 3 de 4: moldura de corte"


def test_a_crop_changed_elsewhere_replaces_a_draft_that_was_not_touched(scenario_results: dict) -> None:
    dialog = scenario_results["crop_changed_elsewhere"]
    assert (dialog["frame_box"], dialog["apply_disabled"]) == (DETECTED_FRAME, True)


def test_a_crop_changed_elsewhere_leaves_a_draft_that_was_touched(scenario_results: dict) -> None:
    dialog = scenario_results["crop_changed_elsewhere_with_a_draft"]
    assert (dialog["frame_box"], dialog["apply_disabled"]) == (WEST_DRAGGED_FRAME, False)


def test_a_page_rotated_elsewhere_turns_the_view_and_the_draft(scenario_results: dict) -> None:
    dialog = scenario_results["rotated_elsewhere_with_a_draft"]
    assert (dialog["image_source"], dialog["frame_box"]) == (
        f"/api/document/pages/{SECOND_PAGE}/preview?rotation_degrees=90",
        TURNED_DRAFT_FRAME,
    )


def test_space_on_a_handle_never_scans(scenario_results: dict) -> None:
    assert scenario_results["space_on_a_handle"] == {"page_requests": 0, "scan_requests": 0}


def test_space_on_the_dialog_itself_never_reaches_the_page(scenario_results: dict) -> None:
    result = scenario_results["space_on_the_dialog_itself"]
    assert result == {"page_requests": 0, "key_down_default_prevented": False, "key_up_default_prevented": False}


def test_backspace_in_the_dialog_never_discards_a_page(scenario_results: dict) -> None:
    assert scenario_results["backspace_in_the_dialog"]["discard_requests"] == 0


def test_enter_in_the_dialog_never_asks_to_save(scenario_results: dict) -> None:
    assert scenario_results["enter_in_the_dialog"] == {"confirmation_shown": 0, "finalize_requests": 0}


def test_arrows_in_the_dialog_send_nothing(scenario_results: dict) -> None:
    assert scenario_results["arrows_do_not_reach_the_page_shortcuts"]["requests"] == 0

import pytest

from tests.web.panel_scenario_runner import NODE_EXECUTABLE, run_frame_editor_scenarios

SECOND_PAGE = "0000000000000002"
SECOND_PAGE_ENLARGE_LABEL = "Ampliar a página 2 e ajustar a moldura de corte"
SECOND_PAGE_OUTLINE = "13,11.5 91.4,11.5 91.4,91.5 13,91.5"
WEST_DRAGGED_OUTLINE = "23,11.5 91.4,11.5 91.4,91.5 23,91.5"
TURNED_DRAFT_OUTLINE = "8.5,23 88.5,23 88.5,91.4 8.5,91.4"
UPPER_OUTLINE = "5,2 90,2 90,55 5,55"
LOWER_OUTLINE = "5,60 90,60 90,95 5,95"
DISCARDED_TEXT = "Alterações da moldura descartadas."
PAGE_GONE_TEXT = "Essa página não está mais no documento."

SCENARIO_NAMES = (
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
    "frames_changed_elsewhere",
    "frames_changed_elsewhere_with_a_draft",
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


def outline_points(dialog: dict) -> list[str | None]:
    return [outline["points"] for outline in dialog["overlay"]["outlines"]]


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
    assert outline_points(scenario_results["reopen_after_a_discarded_drag"])[0] == SECOND_PAGE_OUTLINE


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


def test_frames_changed_elsewhere_replace_a_draft_that_was_not_touched(scenario_results: dict) -> None:
    dialog = scenario_results["frames_changed_elsewhere"]
    assert (outline_points(dialog), dialog["disabled"]["apply"]) == ([UPPER_OUTLINE, LOWER_OUTLINE], True)


def test_frames_changed_elsewhere_leave_a_draft_that_was_touched(scenario_results: dict) -> None:
    dialog = scenario_results["frames_changed_elsewhere_with_a_draft"]
    assert (outline_points(dialog)[0], dialog["disabled"]["apply"]) == (WEST_DRAGGED_OUTLINE, False)


def test_a_page_rotated_elsewhere_turns_the_view_and_the_draft(scenario_results: dict) -> None:
    dialog = scenario_results["rotated_elsewhere_with_a_draft"]
    assert (dialog["image_source"], outline_points(dialog)[0]) == (
        f"/api/document/pages/{SECOND_PAGE}/preview?rotation_degrees=90",
        TURNED_DRAFT_OUTLINE,
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
    assert scenario_results["arrows_do_not_reach_the_page_shortcuts"]["edits"] == 0

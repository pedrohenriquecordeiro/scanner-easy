import pytest

from tests.web.panel_scenario_runner import NODE_EXECUTABLE, run_frame_editor_scenarios

SECOND_PAGE = "0000000000000002"
SECOND_PAGE_ENLARGE_LABEL = "Ampliar a página 2 e ajustar a moldura de corte"
SECOND_PAGE_OUTLINE = "13,11.5 91.4,11.5 91.4,91.5 13,91.5"
WEST_DRAGGED_OUTLINE = "23,11.5 91.4,11.5 91.4,91.5 23,91.5"
TURNED_SECOND_PAGE_OUTLINE = "8.5,13 88.5,13 88.5,91.4 8.5,91.4"
TURNED_DRAFT_OUTLINE = "8.5,23 88.5,23 88.5,91.4 8.5,91.4"
DETECTED_OUTLINE = "12,11 92,11 92,93 12,93"
UPPER_OUTLINE = "5,2 90,2 90,55 5,55"
LOWER_OUTLINE = "5,60 90,60 90,95 5,95"
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
    "apply_two_frames",
    "apply_the_frames_in_reading_order",
    "apply_after_opening_by_keyboard",
    "apply_without_a_frame",
    "apply_a_frame_that_covers_the_whole_page",
    "apply_with_nothing_changed",
    "apply_enabled_after_a_change",
    "apply_refused",
    "apply_while_a_page_scans",
    "apply_conflict",
    "apply_with_space_on_the_button",
    "detect_that_finds_two_frames",
    "detect_that_finds_one_frame",
    "detect_that_finds_more_than_two_photos",
    "detect_that_finds_nothing",
    "detect_on_a_damaged_page",
    "detect_while_a_page_scans",
    "detect_on_a_page_without_a_frame",
    "rotate_in_the_dialog",
    "rotate_with_a_draft_in_the_dialog",
    "rotate_a_page_with_two_frames_in_the_dialog",
    "rotate_a_page_without_a_frame_in_the_dialog",
    "rotate_while_the_request_is_pending",
    "apply_while_the_request_is_pending",
)

pytestmark = pytest.mark.skipif(
    NODE_EXECUTABLE is None, reason="Node.js is not installed, so page-frame-editor.js cannot be exercised"
)


@pytest.fixture(scope="module")
def scenario_results() -> dict:
    return run_frame_editor_scenarios(SCENARIO_NAMES)


def outline_points(dialog: dict) -> list[str | None]:
    return [outline["points"] for outline in dialog["overlay"]["outlines"]]


def visible_outline_points(overlay: dict) -> list[str | None]:
    return [outline["points"] for outline in overlay["outlines"] if outline["visible"]]


def test_apply_sends_the_dragged_frame_as_a_list_of_crops(scenario_results: dict) -> None:
    result = scenario_results["apply_a_dragged_frame"]
    assert (result["requests"], result["body"]) == (
        1,
        {
            "crops": [
                {
                    "top_left": {"x": 0.23, "y": 0.115},
                    "top_right": {"x": 0.914, "y": 0.115},
                    "bottom_right": {"x": 0.914, "y": 0.915},
                    "bottom_left": {"x": 0.23, "y": 0.915},
                }
            ]
        },
    )


def test_apply_sends_the_required_header(scenario_results: dict) -> None:
    assert scenario_results["apply_a_dragged_frame"]["headers"] == {**HEADERS, "Content-Type": "application/json"}


def test_apply_closes_the_dialog_and_announces_it(scenario_results: dict) -> None:
    result = scenario_results["apply_a_dragged_frame"]
    assert (result["open"], result["announcement"]) == (False, "Moldura aplicada à página 2.")


def test_apply_by_pointer_focuses_the_scan_button(scenario_results: dict) -> None:
    assert scenario_results["apply_a_dragged_frame"]["scan_button_focused"] is True


def test_the_frame_of_the_tile_follows_the_applied_crop(scenario_results: dict) -> None:
    overlay = scenario_results["apply_a_dragged_frame"]["tile_overlay"]
    assert visible_outline_points(overlay) == [WEST_DRAGGED_OUTLINE]


def test_apply_sends_both_frames(scenario_results: dict) -> None:
    body = scenario_results["apply_two_frames"]["body"]
    assert [crop["top_left"] for crop in body["crops"]] == [{"x": 0.05, "y": 0.3}, {"x": 0.13, "y": 0.115}]


def test_apply_with_two_frames_announces_the_pages_of_the_pdf(scenario_results: dict) -> None:
    assert scenario_results["apply_two_frames"]["announcement"] == "Molduras aplicadas à página 2 (2 páginas no PDF)."


def test_the_tile_of_a_page_with_two_frames_says_so_after_applying(scenario_results: dict) -> None:
    label = scenario_results["apply_two_frames"]["tile_label"]
    assert label == "Página 2 de 3, com 2 molduras de corte (2 páginas no PDF)"


def test_apply_sends_the_frames_in_reading_order(scenario_results: dict) -> None:
    body = scenario_results["apply_the_frames_in_reading_order"]["body"]
    assert [crop["top_left"]["x"] for crop in body["crops"]] == [0.04, 0.1]


def test_apply_after_opening_by_keyboard_returns_the_focus_to_the_enlarge_button(scenario_results: dict) -> None:
    assert scenario_results["apply_after_opening_by_keyboard"]["focus"] == {
        "label": SECOND_PAGE_ENLARGE_LABEL,
        "page_identifier": SECOND_PAGE,
    }


def test_apply_with_no_frame_sends_an_empty_list(scenario_results: dict) -> None:
    assert scenario_results["apply_without_a_frame"]["body"] == {"crops": []}


def test_apply_with_no_frame_announces_the_removal(scenario_results: dict) -> None:
    assert scenario_results["apply_without_a_frame"]["announcement"] == "Corte removido da página 2."


def test_apply_with_no_frame_takes_the_frame_off_the_tile(scenario_results: dict) -> None:
    assert scenario_results["apply_without_a_frame"]["overlay_hidden"] is True


def test_a_frame_dragged_over_the_whole_page_is_not_sent(scenario_results: dict) -> None:
    result = scenario_results["apply_a_frame_that_covers_the_whole_page"]
    assert (result["body"], result["announcement"]) == ({"crops": []}, "Corte removido da página 2.")


def test_apply_is_disabled_while_nothing_changed(scenario_results: dict) -> None:
    result = scenario_results["apply_with_nothing_changed"]
    assert (result["apply_disabled"], result["requests"], result["open"]) == (True, 0, True)


def test_apply_is_enabled_by_a_change(scenario_results: dict) -> None:
    assert scenario_results["apply_enabled_after_a_change"]["apply_disabled"] is False


def test_a_refused_crop_keeps_the_dialog_open_and_says_why(scenario_results: dict) -> None:
    dialog = scenario_results["apply_refused"]["dialog"]
    assert (dialog["open"], dialog["status"]) == (True, INVALID_CROP_MESSAGE)


def test_a_refused_crop_also_goes_to_the_banner(scenario_results: dict) -> None:
    assert scenario_results["apply_refused"]["banner"] == {"hidden": False, "text": INVALID_CROP_MESSAGE}


def test_a_refused_crop_keeps_the_draft_and_the_focus_on_apply(scenario_results: dict) -> None:
    result = scenario_results["apply_refused"]
    assert (outline_points(result["dialog"])[0], result["apply_focused"], result["dialog"]["disabled"]["apply"]) == (
        WEST_DRAGGED_OUTLINE,
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


def test_detection_that_finds_two_frames_replaces_the_draft_with_them(scenario_results: dict) -> None:
    dialog = scenario_results["detect_that_finds_two_frames"]["dialog"]
    assert (outline_points(dialog), dialog["disabled"]["apply"]) == ([UPPER_OUTLINE, LOWER_OUTLINE], True)


def test_detection_that_finds_two_frames_says_so(scenario_results: dict) -> None:
    assert scenario_results["detect_that_finds_two_frames"]["dialog"]["status"] == "Achei 2 molduras e salvei."


def test_detection_is_saved_at_once_so_the_tile_shows_it(scenario_results: dict) -> None:
    overlay = scenario_results["detect_that_finds_two_frames"]["tile_overlay"]
    assert visible_outline_points(overlay) == [UPPER_OUTLINE, LOWER_OUTLINE]


def test_detection_sends_the_required_header(scenario_results: dict) -> None:
    assert scenario_results["detect_that_finds_two_frames"]["headers"] == HEADERS


def test_detection_keeps_the_focus_on_its_button(scenario_results: dict) -> None:
    assert scenario_results["detect_that_finds_two_frames"]["detect_focused"] is True


def test_detection_that_finds_one_frame_says_so(scenario_results: dict) -> None:
    dialog = scenario_results["detect_that_finds_one_frame"]
    assert (dialog["status"], outline_points(dialog)[0]) == ("Achei 1 moldura e salvei.", DETECTED_OUTLINE)


def test_detection_that_finds_more_than_two_photos_says_which_it_used(scenario_results: dict) -> None:
    status = scenario_results["detect_that_finds_more_than_two_photos"]["status"]
    assert status == "Achei 2 molduras e salvei. Achei mais de 2 fotos; usei as 2 maiores."


def test_detection_that_finds_nothing_says_so_and_keeps_the_draft(scenario_results: dict) -> None:
    dialog = scenario_results["detect_that_finds_nothing"]
    assert (dialog["status"], outline_points(dialog)[0], dialog["disabled"]["apply"]) == (
        "Não achei uma borda confiável nesta página. As molduras não mudaram.",
        WEST_DRAGGED_OUTLINE,
        False,
    )


def test_detection_on_a_damaged_page_says_why_in_the_dialog_and_in_the_banner(scenario_results: dict) -> None:
    result = scenario_results["detect_on_a_damaged_page"]
    assert (result["dialog"]["status"], result["banner"]["text"]) == (DAMAGED_PAGE_MESSAGE, DAMAGED_PAGE_MESSAGE)


def test_detection_is_disabled_while_a_page_scans(scenario_results: dict) -> None:
    assert scenario_results["detect_while_a_page_scans"] == {"disabled_while_scanning": True, "requests": 0}


def test_detection_gives_a_page_without_a_frame_the_detected_one(scenario_results: dict) -> None:
    result = scenario_results["detect_on_a_page_without_a_frame"]
    assert (outline_points(result["dialog"])[0], visible_outline_points(result["tile_overlay"])) == (
        DETECTED_OUTLINE,
        [DETECTED_OUTLINE],
    )


def test_rotating_in_the_dialog_asks_for_the_turned_view(scenario_results: dict) -> None:
    right_after = scenario_results["rotate_in_the_dialog"]["right_after"]
    assert right_after["image_source"] == f"/api/document/pages/{SECOND_PAGE}/preview?rotation_degrees=90"


def test_rotating_in_the_dialog_turns_the_frame_with_the_page(scenario_results: dict) -> None:
    assert outline_points(scenario_results["rotate_in_the_dialog"]["right_after"])[0] == TURNED_SECOND_PAGE_OUTLINE


def test_rotating_in_the_dialog_waits_for_the_new_image(scenario_results: dict) -> None:
    result = scenario_results["rotate_in_the_dialog"]
    assert (result["right_after"]["stage_loading"], result["after_loading"]["stage_loading"]) == (True, False)


def test_rotating_in_the_dialog_says_the_frame_followed(scenario_results: dict) -> None:
    status = scenario_results["rotate_in_the_dialog"]["right_after"]["status"]
    assert status == "Página 2 girada 90° para a direita (total: 90°). A moldura acompanhou o giro."


def test_rotating_in_the_dialog_sends_the_required_header(scenario_results: dict) -> None:
    assert scenario_results["rotate_in_the_dialog"]["headers"] == HEADERS


def test_rotating_in_the_dialog_keeps_the_focus_on_its_button(scenario_results: dict) -> None:
    assert scenario_results["rotate_in_the_dialog"]["rotate_focused"] is True


def test_rotating_in_the_dialog_turns_the_tile_thumbnail_too(scenario_results: dict) -> None:
    thumbnail_source = scenario_results["rotate_in_the_dialog"]["tile_thumbnail"]
    assert thumbnail_source == f"/api/document/pages/{SECOND_PAGE}/thumbnail?rotation_degrees=90"


def test_a_draft_turns_with_the_page_and_can_still_be_applied(scenario_results: dict) -> None:
    dialog = scenario_results["rotate_with_a_draft_in_the_dialog"]
    assert (outline_points(dialog)[0], dialog["disabled"]["apply"]) == (TURNED_DRAFT_OUTLINE, False)


def test_rotating_a_page_with_two_frames_says_both_followed(scenario_results: dict) -> None:
    status = scenario_results["rotate_a_page_with_two_frames_in_the_dialog"]["status"]
    assert status == "Página 2 girada 90° para a direita (total: 90°). As molduras acompanharam o giro."


def test_rotating_a_page_with_two_frames_shows_both_turned(scenario_results: dict) -> None:
    dialog = scenario_results["rotate_a_page_with_two_frames_in_the_dialog"]
    assert outline_points(dialog) == ["45,5 98,5 98,90 45,90", "2,5 40,5 40,90 2,90"]


def test_rotating_a_page_without_a_frame_does_not_talk_about_a_frame(scenario_results: dict) -> None:
    dialog = scenario_results["rotate_a_page_without_a_frame_in_the_dialog"]
    assert (dialog["status"], dialog["overlay"]["hidden"]) == ("Página 1 girada 90° para a direita (total: 90°).", True)


def test_the_edit_buttons_are_disabled_while_a_rotation_runs(scenario_results: dict) -> None:
    disabled = scenario_results["rotate_while_the_request_is_pending"]["during"]["disabled"]
    assert (disabled["rotate"], disabled["detect"], disabled["apply"]) == (True, True, True)


def test_the_edit_buttons_are_enabled_again_after_the_rotation(scenario_results: dict) -> None:
    disabled = scenario_results["rotate_while_the_request_is_pending"]["after"]["disabled"]
    assert (disabled["rotate"], disabled["detect"]) == (False, False)


def test_every_editing_button_is_disabled_while_the_frames_are_being_applied(scenario_results: dict) -> None:
    disabled = scenario_results["apply_while_the_request_is_pending"]["during"]["disabled"]
    assert disabled == {
        "add": True,
        "remove": True,
        "turn": True,
        "detect": True,
        "clear": True,
        "rotate": True,
        "apply": True,
        "cancel": True,
    }


def test_cancel_does_not_close_the_dialog_while_the_frames_are_being_applied(scenario_results: dict) -> None:
    assert scenario_results["apply_while_the_request_is_pending"]["open_after_cancel"] is True


def test_the_frames_applied_after_a_cancel_click_are_never_announced_as_discarded(scenario_results: dict) -> None:
    announcement = scenario_results["apply_while_the_request_is_pending"]["announcement"]
    assert "descartadas" not in announcement

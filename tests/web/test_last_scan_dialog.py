import pytest

from tests.web.panel_scenario_runner import NODE_EXECUTABLE, run_last_scan_scenarios

SCAN_IDENTIFIER = "9f3c1d2e4b5a6978"
FIRST_FILE = "2026-10-18_00007.pdf"
SECOND_FILE = "2026-10-18_00008.pdf"
UPPER_OUTLINE = "5,2 90,2 90,55 5,55"
LOWER_OUTLINE = "5,60 90,60 90,95 5,95"
WHOLE_OUTLINE = "10,10 80,10 80,90 10,90"
TURNED_OUTLINE = "10,20 90,20 90,80 10,80"
DRAGGED_OUTLINE = "15,15 80,10 80,90 10,90"
DETECTED_OUTLINE = "12,11 92,11 92,93 12,93"
INVALID_CROP_MESSAGE = "A moldura de corte é inválida. Ajuste e tente de novo."
FILE_MISSING_MESSAGE = "Um dos arquivos da última digitalização foi apagado ou movido. Digitalize de novo."
REWRITING_TEXT = "Regravando…"
HEADERS = {"X-Requested-With": "digitalizadora"}

SCENARIO_NAMES = (
    "enlarge_by_the_button",
    "enlarge_by_the_thumbnail",
    "enlarge_a_scan_without_frames",
    "enlarge_while_scanning",
    "enlarge_a_scan_whose_original_was_not_kept",
    "apply_a_dragged_frame_of_one_file",
    "apply_after_opening_by_keyboard",
    "apply_a_second_frame_that_creates_a_file",
    "apply_a_removed_frame_that_deletes_a_file",
    "apply_a_removed_frame_whose_file_was_edited",
    "apply_without_frames",
    "apply_while_the_answer_is_pending",
    "apply_refused",
    "apply_when_a_file_is_missing",
    "detect_that_finds_two_photos",
    "detect_that_finds_nothing",
    "rotate_in_the_dialog",
    "cancel_after_a_drag",
    "cancel_after_opening_by_keyboard",
    "scan_replaced_while_the_dialog_is_open",
    "frames_changed_elsewhere_while_the_dialog_is_open",
    "rotated_elsewhere_while_the_dialog_is_open",
    "dialog_buttons_while_scanning_elsewhere",
    "space_in_the_dialog_never_scans",
)

pytestmark = pytest.mark.skipif(
    NODE_EXECUTABLE is None, reason="Node.js is not installed, so last-scan-panel.js cannot be exercised"
)


@pytest.fixture(scope="module")
def scenario_results() -> dict:
    return run_last_scan_scenarios(SCENARIO_NAMES)


def visible_outlines(overlay_holder: dict) -> list[str]:
    return [outline["points"] for outline in overlay_holder["overlay"]["outlines"] if outline["visible"]]


def test_the_enlarge_button_opens_the_same_dialog_as_the_documento_mode(scenario_results: dict) -> None:
    dialog = scenario_results["enlarge_by_the_button"]["dialog"]
    assert (dialog["open"], dialog["title"]) == (True, "Última digitalização: moldura de corte")


def test_the_dialog_shows_the_enlarged_view_of_the_scan(scenario_results: dict) -> None:
    dialog = scenario_results["enlarge_by_the_button"]["dialog"]
    assert (dialog["image_source"], dialog["image_alt"]) == (
        f"/api/scans/last/preview?scan_identifier={SCAN_IDENTIFIER}&rotation_degrees=0",
        "Última digitalização ampliada",
    )


def test_the_dialog_draws_both_frames_of_the_scan(scenario_results: dict) -> None:
    dialog = scenario_results["enlarge_by_the_button"]["dialog"]
    assert visible_outlines(dialog) == [UPPER_OUTLINE, LOWER_OUTLINE]


def test_the_dialog_opens_on_the_move_button_of_the_first_frame(scenario_results: dict) -> None:
    result = scenario_results["enlarge_by_the_button"]
    assert (result["focused_move_button"], result["dialog"]["move"]["label"]) == (True, "Mover a moldura 1")


def test_a_click_on_the_thumbnail_opens_the_dialog_too(scenario_results: dict) -> None:
    assert scenario_results["enlarge_by_the_thumbnail"] == {
        "open": True,
        "title": "Última digitalização: moldura de corte",
    }


def test_a_scan_without_frames_opens_the_dialog_on_the_add_button(scenario_results: dict) -> None:
    result = scenario_results["enlarge_a_scan_without_frames"]
    assert (result["focused_add_button"], result["dialog"]["status"]) == (
        True,
        "Sem corte: a página inteira será usada.",
    )


def test_the_dialog_does_not_open_while_a_scan_runs(scenario_results: dict) -> None:
    assert scenario_results["enlarge_while_scanning"] == {"open": False}


def test_the_dialog_does_not_open_when_the_original_was_not_kept(scenario_results: dict) -> None:
    assert scenario_results["enlarge_a_scan_whose_original_was_not_kept"] == {"open": False}


def test_applying_sends_the_dragged_frame_to_the_crops_of_the_last_scan(scenario_results: dict) -> None:
    result = scenario_results["apply_a_dragged_frame_of_one_file"]
    assert (result["body"]["crops"][0]["top_left"], result["headers"]) == (
        {"x": 0.15, "y": 0.15},
        {**HEADERS, "Content-Type": "application/json"},
    )


def test_applying_closes_the_dialog_and_the_panel_says_what_it_did(scenario_results: dict) -> None:
    result = scenario_results["apply_a_dragged_frame_of_one_file"]
    assert (result["open"], result["panel"]["status"]) == (False, "Moldura aplicada: 1 arquivo.")


def test_applying_redraws_the_frame_of_the_panel(scenario_results: dict) -> None:
    panel = scenario_results["apply_a_dragged_frame_of_one_file"]["panel"]
    assert visible_outlines(panel) == ["15,12 80,12 80,90 15,90"]


def test_applying_by_pointer_focuses_the_scan_button(scenario_results: dict) -> None:
    assert scenario_results["apply_a_dragged_frame_of_one_file"]["scan_button_focused"] is True


def test_applying_after_opening_by_keyboard_returns_to_the_enlarge_button(scenario_results: dict) -> None:
    assert scenario_results["apply_after_opening_by_keyboard"]["enlarge_button_focused"] is True


def test_a_second_frame_creates_a_second_file_and_the_panel_names_it(scenario_results: dict) -> None:
    panel = scenario_results["apply_a_second_frame_that_creates_a_file"]["panel"]
    assert (panel["status"], panel["file_names"]) == (
        f"Moldura aplicada: 2 arquivos. Novo arquivo: {SECOND_FILE}.",
        f"{FIRST_FILE}\n{SECOND_FILE}",
    )


def test_a_second_frame_is_sent_with_the_first(scenario_results: dict) -> None:
    body = scenario_results["apply_a_second_frame_that_creates_a_file"]["body"]
    assert [crop["top_left"] for crop in body["crops"]] == [{"x": 0.1, "y": 0.1}, {"x": 0.55, "y": 0.3}]


def test_a_removed_frame_says_which_file_was_deleted_and_why(scenario_results: dict) -> None:
    panel = scenario_results["apply_a_removed_frame_that_deletes_a_file"]["panel"]
    assert panel["status"] == (
        f"Moldura aplicada: 1 arquivo. O arquivo {SECOND_FILE} foi apagado porque a moldura 2 foi removida."
    )


def test_a_removed_frame_leaves_one_file_in_the_panel(scenario_results: dict) -> None:
    panel = scenario_results["apply_a_removed_frame_that_deletes_a_file"]["panel"]
    assert (panel["file_names"], visible_outlines(panel)) == (FIRST_FILE, [UPPER_OUTLINE])


def test_a_file_edited_after_it_was_written_is_kept_and_the_panel_says_so(scenario_results: dict) -> None:
    status = scenario_results["apply_a_removed_frame_whose_file_was_edited"]["status"]
    assert status == f"Moldura aplicada: 2 arquivos. Mantive {SECOND_FILE} porque ele foi alterado depois de gravado."


def test_applying_without_frames_sends_an_empty_list_and_says_the_crop_is_gone(scenario_results: dict) -> None:
    result = scenario_results["apply_without_frames"]
    assert (result["body"], result["panel"]["status"], visible_outlines(result["panel"])) == (
        {"crops": []},
        "Corte removido: 1 arquivo.",
        [],
    )


def test_while_the_files_are_rewritten_the_dialog_and_the_panel_say_so(scenario_results: dict) -> None:
    result = scenario_results["apply_while_the_answer_is_pending"]
    assert (result["dialog"]["status"], result["panel"]["status"]) == (REWRITING_TEXT, REWRITING_TEXT)


def test_while_the_files_are_rewritten_the_edits_of_the_server_are_disabled(scenario_results: dict) -> None:
    disabled = scenario_results["apply_while_the_answer_is_pending"]["dialog"]["disabled"]
    assert (disabled["detect"], disabled["rotate"], disabled["apply"]) == (True, True, True)


def test_a_refused_application_keeps_the_dialog_the_draft_and_says_why(scenario_results: dict) -> None:
    result = scenario_results["apply_refused"]
    assert (
        result["dialog"]["open"],
        result["dialog"]["status"],
        visible_outlines(result["dialog"]),
        result["banner_text"],
        result["panel"]["status"],
    ) == (True, INVALID_CROP_MESSAGE, [DRAGGED_OUTLINE], INVALID_CROP_MESSAGE, "")


def test_a_missing_file_says_so_and_reads_the_state_again(scenario_results: dict) -> None:
    result = scenario_results["apply_when_a_file_is_missing"]
    assert (result["open"], result["banner_text"], result["extra_state_requests"]) == (True, FILE_MISSING_MESSAGE, 1)


def test_detection_in_the_dialog_gives_the_two_photos_their_frames(scenario_results: dict) -> None:
    result = scenario_results["detect_that_finds_two_photos"]
    assert (visible_outlines(result["dialog"]), result["dialog"]["status"], result["headers"]) == (
        [UPPER_OUTLINE, LOWER_OUTLINE],
        "Achei 2 molduras e salvei.",
        HEADERS,
    )


def test_detection_tells_the_panel_about_the_new_file(scenario_results: dict) -> None:
    panel = scenario_results["detect_that_finds_two_photos"]["panel"]
    assert panel["status"] == f"Molduras detectadas: 2 arquivos. Novo arquivo: {SECOND_FILE}."


def test_detection_that_finds_nothing_says_so_and_keeps_the_draft(scenario_results: dict) -> None:
    result = scenario_results["detect_that_finds_nothing"]
    assert (result["dialog"]["status"], visible_outlines(result["dialog"]), result["dialog"]["disabled"]["apply"]) == (
        "Não achei uma borda confiável nesta digitalização. As molduras não mudaram.",
        [DRAGGED_OUTLINE],
        False,
    )


def test_rotating_in_the_dialog_asks_for_the_turned_view_and_turns_the_frame(scenario_results: dict) -> None:
    dialog = scenario_results["rotate_in_the_dialog"]["dialog"]
    assert (dialog["image_source"], visible_outlines(dialog)) == (
        f"/api/scans/last/preview?scan_identifier={SCAN_IDENTIFIER}&rotation_degrees=90",
        [TURNED_OUTLINE],
    )


def test_rotating_in_the_dialog_says_the_frame_followed(scenario_results: dict) -> None:
    status = scenario_results["rotate_in_the_dialog"]["dialog"]["status"]
    assert status == "Última digitalização girada 90° para a direita (total: 90°). A moldura acompanhou o giro."


def test_rotating_in_the_dialog_also_turns_the_frames_of_the_panel(scenario_results: dict) -> None:
    assert visible_outlines(scenario_results["rotate_in_the_dialog"]["panel"]) == [TURNED_OUTLINE]


def test_cancelling_sends_nothing_and_the_panel_announces_the_discarded_changes(scenario_results: dict) -> None:
    result = scenario_results["cancel_after_a_drag"]
    assert (result["open"], result["edits"], result["panel"]["status"]) == (
        False,
        0,
        "Alterações da moldura descartadas.",
    )


def test_cancelling_by_pointer_focuses_the_scan_button(scenario_results: dict) -> None:
    assert scenario_results["cancel_after_a_drag"]["scan_button_focused"] is True


def test_cancelling_after_opening_by_keyboard_returns_to_the_enlarge_button(scenario_results: dict) -> None:
    assert scenario_results["cancel_after_opening_by_keyboard"]["enlarge_button_focused"] is True


def test_a_scan_that_replaces_the_open_one_closes_the_dialog_and_says_so(scenario_results: dict) -> None:
    result = scenario_results["scan_replaced_while_the_dialog_is_open"]
    assert (result["open"], result["panel"]["status"]) == (False, "Essa digitalização foi substituída por outra.")


def test_frames_changed_elsewhere_replace_a_draft_that_was_not_touched(scenario_results: dict) -> None:
    dialog = scenario_results["frames_changed_elsewhere_while_the_dialog_is_open"]
    assert (visible_outlines(dialog), dialog["disabled"]["apply"]) == ([DETECTED_OUTLINE, LOWER_OUTLINE], True)


def test_a_scan_rotated_elsewhere_turns_the_view_of_the_dialog(scenario_results: dict) -> None:
    dialog = scenario_results["rotated_elsewhere_while_the_dialog_is_open"]
    assert (dialog["image_source"], visible_outlines(dialog)) == (
        f"/api/scans/last/preview?scan_identifier={SCAN_IDENTIFIER}&rotation_degrees=90",
        [TURNED_OUTLINE],
    )


def test_a_scan_that_starts_elsewhere_disables_the_edits_of_the_server_in_the_dialog(scenario_results: dict) -> None:
    disabled = scenario_results["dialog_buttons_while_scanning_elsewhere"]
    assert (disabled["detect"], disabled["rotate"], disabled["apply"]) == (True, True, True)


def test_a_scan_that_starts_elsewhere_leaves_the_local_edits_of_the_dialog(scenario_results: dict) -> None:
    disabled = scenario_results["dialog_buttons_while_scanning_elsewhere"]
    assert (disabled["add"], disabled["remove"], disabled["clear"]) == (False, False, False)


def test_space_in_the_dialog_never_scans_and_never_edits(scenario_results: dict) -> None:
    assert scenario_results["space_in_the_dialog_never_scans"] == {"scan_requests": 0, "edits": 0}

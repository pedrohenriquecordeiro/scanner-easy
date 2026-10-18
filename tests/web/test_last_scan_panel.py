import pytest

from tests.web.panel_scenario_runner import NODE_EXECUTABLE, run_last_scan_scenarios

FIRST_FILE = "2026-10-18_16-14-03-000000006.pdf"
SECOND_FILE = "2026-10-18_16-14-03-000000007.pdf"
UPPER_OUTLINE = "5,2 90,2 90,55 5,55"
LOWER_OUTLINE = "5,60 90,60 90,95 5,95"
WHOLE_OUTLINE = "10,10 80,10 80,90 10,90"
TURNED_OUTLINE = "10,20 90,20 90,80 10,80"
ROTATED_TEXT = "Última digitalização girada 90° para a direita."
NO_LAST_SCAN_MESSAGE = "Ainda não há uma digitalização para ajustar."
NOT_EDITABLE_HINT = "O original desta digitalização não foi guardado; os arquivos foram salvos normalmente."
REWRITING_TEXT = "Regravando…"

SCENARIO_NAMES = (
    "panel_after_two_photos",
    "panel_after_one_file",
    "panel_after_one_photo_with_a_frame",
    "panel_before_any_scan",
    "panel_of_a_scan_whose_original_was_not_kept",
    "panel_of_a_server_without_revisions",
    "panel_in_the_document_mode",
    "panel_proportion_follows_the_loaded_thumbnail",
    "panel_follows_a_new_scan",
    "panel_while_scanning",
    "rotate_by_pointer",
    "rotate_asks_for_the_state_at_once",
    "rotate_while_the_answer_is_pending",
    "rotate_by_keyboard",
    "space_after_clicking_rotate",
    "rotate_again_empties_the_status_until_the_answer",
    "rotate_refused",
    "rotate_refused_for_another_reason",
    "rotate_while_scanning",
    "scan_button_while_an_adjustment_runs",
    "rotation_message_goes_away_with_the_next_scan",
    "older_state_arriving_after_an_adjustment",
    "state_arriving_while_an_adjustment_runs",
)

pytestmark = pytest.mark.skipif(
    NODE_EXECUTABLE is None, reason="Node.js is not installed, so last-scan-panel.js cannot be exercised"
)


@pytest.fixture(scope="module")
def scenario_results() -> dict:
    return run_last_scan_scenarios(SCENARIO_NAMES)


def visible_outlines(panel: dict) -> list[str]:
    return [outline["points"] for outline in panel["overlay"]["outlines"] if outline["visible"]]


def test_the_panel_is_hidden_before_any_scan(scenario_results: dict) -> None:
    assert scenario_results["panel_before_any_scan"]["hidden"] is True


def test_the_panel_lists_one_file_per_line(scenario_results: dict) -> None:
    assert scenario_results["panel_after_two_photos"]["file_names"] == f"{FIRST_FILE}\n{SECOND_FILE}"


def test_the_panel_shows_the_total_size_of_the_files(scenario_results: dict) -> None:
    assert scenario_results["panel_after_two_photos"]["size"] == "412,3 KB"


def test_the_panel_draws_both_frames_over_the_thumbnail(scenario_results: dict) -> None:
    assert visible_outlines(scenario_results["panel_after_two_photos"]) == [UPPER_OUTLINE, LOWER_OUTLINE]


def test_the_frames_of_the_panel_are_hidden_from_screen_readers(scenario_results: dict) -> None:
    assert scenario_results["panel_after_two_photos"]["overlay"]["aria_hidden"] == "true"


def test_the_second_frame_of_the_panel_has_its_own_colour_and_number(scenario_results: dict) -> None:
    overlay = scenario_results["panel_after_two_photos"]["overlay"]
    colours = [outline["is_second_colour"] for outline in overlay["outlines"]]
    numbers = [badge["text"] for badge in overlay["badges"]]
    assert (colours, numbers) == ([False, True], ["1", "2"])


def test_a_scan_without_frames_draws_none(scenario_results: dict) -> None:
    panel = scenario_results["panel_after_one_file"]
    assert (panel["overlay"]["hidden"], visible_outlines(panel)) == (True, [])


def test_a_scan_with_one_frame_draws_one(scenario_results: dict) -> None:
    assert visible_outlines(scenario_results["panel_after_one_photo_with_a_frame"]) == [WHOLE_OUTLINE]


def test_the_thumbnail_follows_the_revision_of_the_files(scenario_results: dict) -> None:
    assert scenario_results["panel_after_two_photos"]["thumbnail_source"] == "/api/scans/last/thumbnail?version=3"


def test_a_server_without_revisions_versions_the_thumbnail_by_the_scan_count(scenario_results: dict) -> None:
    assert scenario_results["panel_of_a_server_without_revisions"]["thumbnail_source"] == (
        "/api/scans/last/thumbnail?version=7"
    )


def test_the_thumbnail_of_two_photos_says_how_many_there_are(scenario_results: dict) -> None:
    alt = scenario_results["panel_after_two_photos"]["thumbnail_alt"]
    assert alt == "Miniatura da última digitalização (2 fotos)"


def test_the_thumbnail_of_one_file_has_the_plain_text_alternative(scenario_results: dict) -> None:
    assert scenario_results["panel_after_one_file"]["thumbnail_alt"] == "Miniatura da última digitalização"


def test_the_thumbnail_frame_takes_the_proportion_of_the_loaded_picture(scenario_results: dict) -> None:
    result = scenario_results["panel_proportion_follows_the_loaded_thumbnail"]
    assert (result["before_loading"], result["after_loading"], result["after_an_empty_load"]) == (
        None,
        "480 / 320",
        "480 / 320",
    )


def test_the_status_line_names_the_only_file(scenario_results: dict) -> None:
    assert scenario_results["panel_after_one_file"]["status_line"] == f"Pronto! Salvo como {FIRST_FILE}"


def test_the_status_line_names_both_files(scenario_results: dict) -> None:
    assert scenario_results["panel_after_two_photos"]["status_line"] == (
        f"Pronto! 2 arquivos salvos: {FIRST_FILE} e {SECOND_FILE}"
    )


def test_the_hint_says_that_adjustments_rewrite_the_files(scenario_results: dict) -> None:
    assert scenario_results["panel_after_two_photos"]["hint"] == "Ajustes regravam os arquivos salvos."


def test_the_panel_offers_both_buttons_once_idle(scenario_results: dict) -> None:
    panel = scenario_results["panel_after_two_photos"]
    assert (panel["rotate_disabled"], panel["enlarge_disabled"]) == (False, False)


def test_a_scan_whose_original_was_not_kept_cannot_be_adjusted_and_says_why(scenario_results: dict) -> None:
    panel = scenario_results["panel_of_a_scan_whose_original_was_not_kept"]
    assert (panel["rotate_disabled"], panel["enlarge_disabled"], panel["hint"]) == (True, True, NOT_EDITABLE_HINT)


def test_a_scan_whose_original_was_not_kept_still_shows_its_frames(scenario_results: dict) -> None:
    panel = scenario_results["panel_of_a_scan_whose_original_was_not_kept"]
    assert visible_outlines(panel) == [WHOLE_OUTLINE]


def test_the_panel_is_hidden_in_the_document_mode(scenario_results: dict) -> None:
    assert scenario_results["panel_in_the_document_mode"]["hidden"] is True


def test_a_new_scan_replaces_the_files_the_frames_and_the_thumbnail(scenario_results: dict) -> None:
    panel = scenario_results["panel_follows_a_new_scan"]
    assert (panel["file_names"], visible_outlines(panel), panel["thumbnail_source"]) == (
        f"{SECOND_FILE}\n2026-10-18_16-14-03-000000008.pdf",
        [UPPER_OUTLINE, LOWER_OUTLINE],
        "/api/scans/last/thumbnail?version=4",
    )


def test_the_buttons_are_disabled_while_a_scan_runs(scenario_results: dict) -> None:
    panel = scenario_results["panel_while_scanning"]
    assert (panel["rotate_disabled"], panel["enlarge_disabled"]) == (True, True)


def test_rotating_sends_one_post_with_the_required_header(scenario_results: dict) -> None:
    result = scenario_results["rotate_by_pointer"]
    assert (result["rotation_requests"], result["request_headers"]) == (1, {"X-Requested-With": "digitalizadora"})


def test_rotating_says_so(scenario_results: dict) -> None:
    assert scenario_results["rotate_by_pointer"]["right_after"]["status"] == ROTATED_TEXT


def test_rotating_turns_the_frames_at_once(scenario_results: dict) -> None:
    assert visible_outlines(scenario_results["rotate_by_pointer"]["right_after"]) == [TURNED_OUTLINE]


def test_rotating_reloads_the_thumbnail_and_keeps_doing_so_with_the_next_revision(scenario_results: dict) -> None:
    assert scenario_results["rotate_by_pointer"]["thumbnail_after_the_next_state"] == (
        "/api/scans/last/thumbnail?version=4-1"
    )


def test_rotating_asks_for_the_state_at_once(scenario_results: dict) -> None:
    assert scenario_results["rotate_asks_for_the_state_at_once"]["extra_state_requests"] == 1


def test_rotating_by_pointer_focuses_the_scan_button(scenario_results: dict) -> None:
    assert scenario_results["rotate_by_pointer"]["scan_button_focused"] is True


def test_rotating_by_keyboard_keeps_the_focus_on_the_button(scenario_results: dict) -> None:
    assert scenario_results["rotate_by_keyboard"] == {"rotation_requests": 1, "rotate_button_focused": True}


def test_space_after_clicking_the_rotation_scans_instead_of_rotating_again(scenario_results: dict) -> None:
    assert scenario_results["space_after_clicking_rotate"] == {"rotation_requests": 1, "scan_requests": 1}


def test_while_the_files_are_rewritten_the_panel_says_so(scenario_results: dict) -> None:
    assert scenario_results["rotate_while_the_answer_is_pending"]["during"]["status"] == REWRITING_TEXT


def test_while_the_files_are_rewritten_both_buttons_are_disabled_and_only_one_request_goes(
    scenario_results: dict,
) -> None:
    result = scenario_results["rotate_while_the_answer_is_pending"]
    assert (result["during"]["rotate_disabled"], result["during"]["enlarge_disabled"], result["rotation_requests"]) == (
        True,
        True,
        1,
    )


def test_the_buttons_are_enabled_again_after_the_rewrite(scenario_results: dict) -> None:
    after = scenario_results["rotate_while_the_answer_is_pending"]["after"]
    assert (after["rotate_disabled"], after["enlarge_disabled"]) == (False, False)


def test_the_scan_button_waits_for_the_rewrite(scenario_results: dict) -> None:
    result = scenario_results["scan_button_while_an_adjustment_runs"]
    assert (result["disabled_during"], result["scan_requests_during"], result["disabled_after"]) == (True, 0, False)


def test_rotating_again_empties_the_status_until_the_answer(scenario_results: dict) -> None:
    result = scenario_results["rotate_again_empties_the_status_until_the_answer"]
    assert (
        result["status_after_the_first"],
        result["status_while_the_second_is_pending"],
        result["status_after_the_second"],
    ) == (ROTATED_TEXT, REWRITING_TEXT, ROTATED_TEXT)


def test_a_refused_rotation_shows_the_catalog_message_and_says_nothing_in_the_panel(scenario_results: dict) -> None:
    result = scenario_results["rotate_refused"]
    assert (result["banner_text"], result["panel"]["status"]) == (NO_LAST_SCAN_MESSAGE, "")


def test_a_refused_rotation_leaves_the_buttons_enabled(scenario_results: dict) -> None:
    panel = scenario_results["rotate_refused"]["panel"]
    assert (panel["rotate_disabled"], panel["enlarge_disabled"]) == (False, False)


def test_an_answer_that_says_the_scan_is_gone_reads_the_state_again(scenario_results: dict) -> None:
    assert scenario_results["rotate_refused"]["extra_state_requests"] == 1


def test_another_refusal_does_not_read_the_state_again(scenario_results: dict) -> None:
    assert scenario_results["rotate_refused_for_another_reason"]["extra_state_requests"] == 0


def test_rotating_is_refused_by_the_page_while_a_scan_runs(scenario_results: dict) -> None:
    result = scenario_results["rotate_while_scanning"]
    assert (result["panel"]["rotate_disabled"], result["edits"]) == (True, 0)


def test_the_rotation_message_goes_away_when_the_next_scan_starts(scenario_results: dict) -> None:
    assert scenario_results["rotation_message_goes_away_with_the_next_scan"]["status"] == ""


def test_a_state_asked_for_before_an_adjustment_ended_does_not_undo_it(scenario_results: dict) -> None:
    panel = scenario_results["older_state_arriving_after_an_adjustment"]
    assert (visible_outlines(panel), panel["status"]) == ([TURNED_OUTLINE], ROTATED_TEXT)


def test_a_state_that_arrives_while_an_adjustment_runs_is_not_applied(scenario_results: dict) -> None:
    panel = scenario_results["state_arriving_while_an_adjustment_runs"]
    assert (panel["thumbnail_source"], panel["status"]) == ("/api/scans/last/thumbnail?version=3", REWRITING_TEXT)

import pytest

from tests.web.panel_scenario_runner import NODE_EXECUTABLE, run_panel_scenarios

FIRST_PAGE = "0000000000000001"
SECOND_PAGE = "0000000000000002"
THIRD_PAGE = "0000000000000003"

SCENARIO_NAMES = (
    "space_in_document_mode",
    "space_after_clicking_discard_last",
    "space_after_clicking_move_left",
    "keyboard_move_left",
    "keyboard_move_left_to_the_first_position",
    "keyboard_delete",
    "held_backspace",
    "enter_on_the_scan_button",
    "held_enter",
    "second_enter_confirms",
    "space_in_the_confirmation",
    "space_opened_confirmation_takes_the_first_enter",
    "escape_in_the_confirmation",
    "move_to_dialog",
    "enter_on_the_save_button",
)

pytestmark = pytest.mark.skipif(
    NODE_EXECUTABLE is None, reason="Node.js is not installed, so document-panel.js cannot be exercised"
)


@pytest.fixture(scope="module")
def scenario_results() -> dict:
    return run_panel_scenarios(SCENARIO_NAMES)


def test_space_in_document_mode_adds_a_page_instead_of_a_quick_scan(scenario_results: dict) -> None:
    assert scenario_results["space_in_document_mode"] == {"page_requests": 1, "scan_requests": 0}


def test_space_after_clicking_discard_last_adds_a_page(scenario_results: dict) -> None:
    assert scenario_results["space_after_clicking_discard_last"] == {"discard_requests": 1, "page_requests": 1}


def test_space_after_clicking_an_arrow_adds_a_page(scenario_results: dict) -> None:
    assert scenario_results["space_after_clicking_move_left"] == {"order_requests": 1, "page_requests": 1}


def test_left_arrow_sends_the_whole_new_order(scenario_results: dict) -> None:
    assert scenario_results["keyboard_move_left"]["order_body"] == {
        "page_identifiers": [FIRST_PAGE, THIRD_PAGE, SECOND_PAGE]
    }


def test_left_arrow_by_keyboard_keeps_the_focus_on_the_moved_page(scenario_results: dict) -> None:
    assert scenario_results["keyboard_move_left"]["focus"] == {
        "label": "Mover a página 2 para a esquerda",
        "page_identifier": THIRD_PAGE,
    }


def test_move_is_announced(scenario_results: dict) -> None:
    assert scenario_results["keyboard_move_left"]["announcement"] == "Página 3 movida para a posição 2"


def test_left_arrow_reaching_the_first_position_focuses_the_right_arrow(scenario_results: dict) -> None:
    assert scenario_results["keyboard_move_left_to_the_first_position"]["focus"] == {
        "label": "Mover a página 1 para a direita",
        "page_identifier": SECOND_PAGE,
    }


def test_delete_by_keyboard_sends_one_delete(scenario_results: dict) -> None:
    assert scenario_results["keyboard_delete"]["delete_requests"] == 1


def test_delete_by_keyboard_focuses_the_delete_button_of_the_next_page(scenario_results: dict) -> None:
    assert scenario_results["keyboard_delete"]["focus"] == {
        "label": "Excluir a página 2",
        "page_identifier": THIRD_PAGE,
    }


def test_delete_is_announced(scenario_results: dict) -> None:
    assert scenario_results["keyboard_delete"]["announcement"] == "Página 2 excluída. O documento tem 2 páginas."


def test_held_backspace_discards_one_page(scenario_results: dict) -> None:
    assert scenario_results["held_backspace"]["discard_requests"] == 1


def test_enter_opens_the_finalize_confirmation(scenario_results: dict) -> None:
    assert scenario_results["enter_on_the_scan_button"]["dialog_open"] is True


def test_enter_on_the_scan_button_adds_no_page(scenario_results: dict) -> None:
    assert scenario_results["enter_on_the_scan_button"]["page_requests"] == 0


def test_enter_alone_does_not_finalize(scenario_results: dict) -> None:
    assert scenario_results["enter_on_the_scan_button"]["finalize_requests"] == 0


def test_finalize_confirmation_opens_on_its_accept_button(scenario_results: dict) -> None:
    assert scenario_results["enter_on_the_scan_button"]["accept_button_focused"] is True


def test_finalize_confirmation_asks_with_the_page_count(scenario_results: dict) -> None:
    assert scenario_results["enter_on_the_scan_button"]["question"] == "Salvar o PDF com 3 páginas?"


def test_held_enter_opens_the_confirmation_without_finalizing(scenario_results: dict) -> None:
    assert scenario_results["held_enter"] == {"dialog_open": True, "finalize_requests": 0}


def test_second_enter_press_confirms_the_finalization(scenario_results: dict) -> None:
    assert scenario_results["second_enter_confirms"]["finalize_requests"] == 1


def test_space_in_the_confirmation_neither_finalizes_nor_adds_a_page(scenario_results: dict) -> None:
    assert scenario_results["space_in_the_confirmation"] == {
        "dialog_open": True,
        "finalize_requests": 0,
        "page_requests": 0,
    }


def test_first_enter_confirms_a_finalization_opened_with_space(scenario_results: dict) -> None:
    assert scenario_results["space_opened_confirmation_takes_the_first_enter"]["finalize_requests"] == 1


def test_escape_closes_the_confirmation_without_finalizing(scenario_results: dict) -> None:
    result = scenario_results["escape_in_the_confirmation"]
    assert (result["dialog_open"], result["finalize_requests"]) == (False, 0)


def test_closing_the_confirmation_focuses_the_scan_button(scenario_results: dict) -> None:
    assert scenario_results["escape_in_the_confirmation"]["scan_button_focused"] is True


def test_move_dialog_opens_with_the_current_position(scenario_results: dict) -> None:
    assert scenario_results["move_to_dialog"]["position_value"] == "3"


def test_move_dialog_selects_the_position_so_typing_replaces_it(scenario_results: dict) -> None:
    assert scenario_results["move_to_dialog"]["is_position_selected"] is True


def test_enter_on_the_save_button_opens_the_confirmation_once(scenario_results: dict) -> None:
    assert scenario_results["enter_on_the_save_button"]["dialog_shown_times"] == 1


def test_enter_on_the_save_button_does_not_save_by_itself(scenario_results: dict) -> None:
    assert scenario_results["enter_on_the_save_button"]["finalize_requests"] == 0


def test_confirmation_accept_button_says_save(scenario_results: dict) -> None:
    assert scenario_results["enter_on_the_save_button"]["accept_label"] == "Salvar"

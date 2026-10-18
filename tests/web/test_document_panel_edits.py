import pytest

from tests.web.panel_scenario_runner import NODE_EXECUTABLE, run_panel_scenarios

FIRST_PAGE = "0000000000000001"
SECOND_PAGE = "0000000000000002"
THIRD_PAGE = "0000000000000003"
FINISHED_TEXT = "Pronto! Salvo como Contrato.pdf (3 páginas)"
SCAN_ALREADY_RUNNING_MESSAGE = "Já existe uma digitalização em andamento."
DOCUMENT_BUSY_MESSAGE = "O documento está sendo salvo ou alterado. Aguarde um instante e tente de novo."
INVALID_PAGE_ORDER_MESSAGE = (
    "A nova ordem das páginas não confere com o documento. A lista foi atualizada; tente de novo."
)
INVALID_DOCUMENT_NAME_MESSAGE = (
    "Nome de documento inválido: comprido demais ou só com pontos e caracteres invisíveis. "
    "Use um nome mais curto, com letras ou números."
)
DAMAGED_PAGE_MESSAGE = (
    "Uma página guardada do documento está danificada ou sumiu do disco do Mac. "
    "Ela está marcada na grade: exclua-a e digitalize-a de novo."
)

SCENARIO_NAMES = (
    "name_after_finalizing",
    "name_after_cancelling",
    "name_after_removing_the_only_page_here",
    "refused_name_on_finalize",
    "name_left_while_a_page_scans",
    "enter_in_the_name_field_during_a_scan",
    "conflict_on_discard",
    "busy_document_on_add_page",
    "stale_page_order",
    "damaged_page_on_finalize",
    "drag_and_drop",
    "escape_in_the_name_field",
    "keyboard_rotate",
    "pointer_rotate",
    "space_after_clicking_rotate",
    "rotate_while_a_page_scans",
    "rotate_while_the_request_is_pending",
    "rotate_refused_by_a_conflict",
    "rotate_a_damaged_page",
)

pytestmark = pytest.mark.skipif(
    NODE_EXECUTABLE is None, reason="Node.js is not installed, so document-panel.js cannot be exercised"
)


@pytest.fixture(scope="module")
def scenario_results() -> dict:
    return run_panel_scenarios(SCENARIO_NAMES)


def test_name_field_is_cleared_after_finalizing(scenario_results: dict) -> None:
    assert scenario_results["name_after_finalizing"]["name_field"] == ""


def test_finalized_document_is_shown_with_its_file_name(scenario_results: dict) -> None:
    assert scenario_results["name_after_finalizing"]["finished_text"] == FINISHED_TEXT


def test_scan_button_has_the_focus_after_finalizing(scenario_results: dict) -> None:
    assert scenario_results["name_after_finalizing"]["scan_button_focused"] is True


def test_first_page_after_finalizing_sends_no_name(scenario_results: dict) -> None:
    assert scenario_results["name_after_finalizing"]["name_requests_for_the_next_first_page"] == 0


def test_cancel_confirmation_opens_on_its_reject_button(scenario_results: dict) -> None:
    assert scenario_results["name_after_cancelling"]["reject_button_focused"] is True


def test_cancel_confirmation_asks_with_the_page_count(scenario_results: dict) -> None:
    assert scenario_results["name_after_cancelling"]["question"] == "Cancelar o documento e apagar 3 páginas?"


def test_accepted_cancel_sends_one_delete(scenario_results: dict) -> None:
    assert scenario_results["name_after_cancelling"]["cancel_requests"] == 1


def test_name_field_is_cleared_after_cancelling(scenario_results: dict) -> None:
    assert scenario_results["name_after_cancelling"]["name_field"] == ""


def test_first_page_after_cancelling_sends_no_name(scenario_results: dict) -> None:
    assert scenario_results["name_after_cancelling"]["name_requests_for_the_next_first_page"] == 0


def test_name_is_kept_after_removing_the_only_page_here(scenario_results: dict) -> None:
    assert scenario_results["name_after_removing_the_only_page_here"]["name_field"] == "Contrato"


def test_kept_name_goes_with_the_next_first_page(scenario_results: dict) -> None:
    assert scenario_results["name_after_removing_the_only_page_here"]["name_request_body"] == {"name": "Contrato"}


def test_refused_name_stops_the_finalization(scenario_results: dict) -> None:
    assert scenario_results["refused_name_on_finalize"]["finalize_requests"] == 0


def test_refused_name_puts_the_focus_on_the_name_field(scenario_results: dict) -> None:
    assert scenario_results["refused_name_on_finalize"]["name_field_focused"] is True


def test_refused_name_shows_the_catalog_message(scenario_results: dict) -> None:
    assert scenario_results["refused_name_on_finalize"]["banner"] == {
        "hidden": False,
        "text": INVALID_DOCUMENT_NAME_MESSAGE,
    }


def test_name_left_while_a_page_scans_is_not_sent_during_the_scan(scenario_results: dict) -> None:
    assert scenario_results["name_left_while_a_page_scans"]["name_requests_during_the_scan"] == 0


def test_name_left_while_a_page_scans_is_sent_when_the_page_lands(scenario_results: dict) -> None:
    assert scenario_results["name_left_while_a_page_scans"]["name_bodies_after_the_page_lands"] == [
        {"name": "Contrato"}
    ]


def test_name_left_while_a_page_scans_stays_in_the_field(scenario_results: dict) -> None:
    assert scenario_results["name_left_while_a_page_scans"]["name_field"] == "Contrato"


def test_enter_in_the_name_field_during_a_scan_saves_the_name_when_the_page_lands(
    scenario_results: dict,
) -> None:
    assert scenario_results["enter_in_the_name_field_during_a_scan"]["name_requests"] == 1


def test_space_after_enter_in_the_name_field_during_a_scan_adds_a_page(scenario_results: dict) -> None:
    assert scenario_results["enter_in_the_name_field_during_a_scan"]["new_page_requests"] == 1


def test_conflict_on_an_edit_goes_to_the_banner(scenario_results: dict) -> None:
    assert scenario_results["conflict_on_discard"]["banner"] == {"hidden": False, "text": SCAN_ALREADY_RUNNING_MESSAGE}


def test_conflict_on_an_edit_keeps_the_grid(scenario_results: dict) -> None:
    assert scenario_results["conflict_on_discard"]["page_identifiers"] == [FIRST_PAGE, SECOND_PAGE, THIRD_PAGE]


def test_busy_document_on_add_page_goes_to_the_banner(scenario_results: dict) -> None:
    assert scenario_results["busy_document_on_add_page"]["banner"] == {"hidden": False, "text": DOCUMENT_BUSY_MESSAGE}


def test_stale_page_order_shows_the_catalog_message(scenario_results: dict) -> None:
    assert scenario_results["stale_page_order"]["banner"] == {"hidden": False, "text": INVALID_PAGE_ORDER_MESSAGE}


def test_stale_page_order_reloads_the_document(scenario_results: dict) -> None:
    assert scenario_results["stale_page_order"]["extra_document_requests"] == 1


def test_damaged_page_is_marked_in_the_grid(scenario_results: dict) -> None:
    assert scenario_results["damaged_page_on_finalize"]["damaged_identifiers"] == [SECOND_PAGE]


def test_damaged_page_delete_button_takes_the_focus(scenario_results: dict) -> None:
    assert scenario_results["damaged_page_on_finalize"]["focus"] == {
        "label": "Excluir a página 2",
        "page_identifier": SECOND_PAGE,
    }


def test_damaged_page_shows_the_catalog_message(scenario_results: dict) -> None:
    assert scenario_results["damaged_page_on_finalize"]["banner"] == {"hidden": False, "text": DAMAGED_PAGE_MESSAGE}


def test_drop_after_the_last_page_sends_the_new_order(scenario_results: dict) -> None:
    assert scenario_results["drag_and_drop"]["order_body"] == {
        "page_identifiers": [SECOND_PAGE, THIRD_PAGE, FIRST_PAGE]
    }


def test_reordered_grid_reuses_the_tile_of_each_page(scenario_results: dict) -> None:
    assert scenario_results["drag_and_drop"]["same_tile_kept"] is True


def test_drop_focuses_the_scan_button(scenario_results: dict) -> None:
    assert scenario_results["drag_and_drop"]["scan_button_focused"] is True


def test_escape_in_the_name_field_focuses_the_scan_button(scenario_results: dict) -> None:
    assert scenario_results["escape_in_the_name_field"]["scan_button_focused"] is True


def test_leaving_the_name_field_saves_the_typed_name(scenario_results: dict) -> None:
    assert scenario_results["escape_in_the_name_field"]["name_request_body"] == {"name": "Contrato"}


def test_rotate_sends_one_post_to_the_page_rotation_route(scenario_results: dict) -> None:
    assert scenario_results["keyboard_rotate"]["rotation_requests"] == 1


def test_rotate_sends_the_required_header(scenario_results: dict) -> None:
    assert scenario_results["keyboard_rotate"]["request_headers"] == {"X-Requested-With": "digitalizadora"}


def test_rotated_page_keeps_its_identifier_and_its_position(scenario_results: dict) -> None:
    assert scenario_results["keyboard_rotate"]["page_identifiers"] == [FIRST_PAGE, SECOND_PAGE, THIRD_PAGE]


def test_rotated_page_asks_for_its_thumbnail_turned(scenario_results: dict) -> None:
    thumbnail_source = scenario_results["keyboard_rotate"]["thumbnail_source"]
    assert thumbnail_source == f"/api/document/pages/{SECOND_PAGE}/thumbnail?rotation_degrees=90"


def test_the_other_pages_keep_their_thumbnail_address(scenario_results: dict) -> None:
    thumbnail_source = scenario_results["keyboard_rotate"]["first_thumbnail_source"]
    assert thumbnail_source == f"/api/document/pages/{FIRST_PAGE}/thumbnail?rotation_degrees=0"


def test_rotate_by_keyboard_keeps_the_focus_on_the_rotate_button_of_the_position(scenario_results: dict) -> None:
    assert scenario_results["keyboard_rotate"]["focus"] == {
        "label": "Girar a página 2 90 graus para a direita",
        "page_identifier": SECOND_PAGE,
    }


def test_rotate_is_announced(scenario_results: dict) -> None:
    assert scenario_results["keyboard_rotate"]["announcement"] == "Página 2 girada 90° para a direita."


def test_rotate_by_pointer_focuses_the_scan_button(scenario_results: dict) -> None:
    assert scenario_results["pointer_rotate"]["scan_button_focused"] is True


def test_space_after_clicking_rotate_adds_a_page(scenario_results: dict) -> None:
    assert scenario_results["space_after_clicking_rotate"] == {"rotation_requests": 1, "page_requests": 1}


def test_rotate_is_disabled_while_a_page_scans(scenario_results: dict) -> None:
    assert scenario_results["rotate_while_a_page_scans"] == {"rotate_disabled": True, "rotation_requests": 0}


def test_rotate_buttons_are_disabled_while_the_rotation_is_pending(scenario_results: dict) -> None:
    assert scenario_results["rotate_while_the_request_is_pending"]["disabled_during"] == [True, True, True]


def test_rotate_buttons_are_enabled_again_after_the_rotation(scenario_results: dict) -> None:
    assert scenario_results["rotate_while_the_request_is_pending"]["disabled_after"] is False


def test_rotate_conflict_goes_to_the_banner(scenario_results: dict) -> None:
    assert scenario_results["rotate_refused_by_a_conflict"]["banner"] == {
        "hidden": False,
        "text": SCAN_ALREADY_RUNNING_MESSAGE,
    }


def test_rotate_conflict_leaves_the_grid_alone(scenario_results: dict) -> None:
    assert scenario_results["rotate_refused_by_a_conflict"]["page_identifiers"] == [
        FIRST_PAGE,
        SECOND_PAGE,
        THIRD_PAGE,
    ]


def test_rotate_conflict_keeps_the_focus_on_the_rotate_button(scenario_results: dict) -> None:
    assert scenario_results["rotate_refused_by_a_conflict"]["focus"] == {
        "label": "Girar a página 2 90 graus para a direita",
        "page_identifier": SECOND_PAGE,
    }


def test_rotating_a_damaged_page_marks_it(scenario_results: dict) -> None:
    assert scenario_results["rotate_a_damaged_page"]["damaged_identifiers"] == [SECOND_PAGE]


def test_rotating_a_damaged_page_focuses_its_delete_button(scenario_results: dict) -> None:
    assert scenario_results["rotate_a_damaged_page"]["focus"] == {
        "label": "Excluir a página 2",
        "page_identifier": SECOND_PAGE,
    }


def test_rotating_a_damaged_page_shows_the_catalog_message(scenario_results: dict) -> None:
    assert scenario_results["rotate_a_damaged_page"]["banner"] == {"hidden": False, "text": DAMAGED_PAGE_MESSAGE}

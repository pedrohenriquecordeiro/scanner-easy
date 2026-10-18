import pytest

from tests.web.panel_scenario_runner import NODE_EXECUTABLE, run_panel_scenarios

FIRST_PAGE = "0000000000000001"
SECOND_PAGE = "0000000000000002"
THIRD_PAGE = "0000000000000003"
FINISHED_TEXT = "Pronto! Salvo como Contrato.pdf (3 páginas)"
SCAN_ALREADY_RUNNING_MESSAGE = "Já existe uma digitalização em andamento."
DOCUMENT_BUSY_MESSAGE = "O documento está sendo finalizado ou alterado. Aguarde um instante e tente de novo."
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

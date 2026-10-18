import pytest

from tests.web.panel_scenario_runner import NODE_EXECUTABLE, run_panel_scenarios

FIRST_PAGE = "0000000000000001"
SECOND_PAGE = "0000000000000002"
THIRD_PAGE = "0000000000000003"
NEXT_SHEET_TEXT = "Coloque a próxima folha e aperte Espaço; Enter salva."
FINISHED_TEXT = "Pronto! Salvo como Contrato.pdf (3 páginas)"
SAVED_SETTINGS = {
    "output_folder": "/Users/teste/Digitalizadora",
    "output_format": "pdf",
    "dots_per_inch": 300,
    "color_mode": "color",
    "scan_preset": "document",
    "capture_mode": "single",
    "rotation_degrees": 0,
    "auto_crop": False,
}

SCENARIO_NAMES = (
    "idle_document_page",
    "grid_tiles",
    "during_finalization",
    "older_answer_after_a_newer_one",
    "recovered_draft_in_quick_mode",
    "recovered_draft_already_switched_in_quick_mode",
    "recovered_draft_with_blocked_storage",
    "reload_with_a_draft_in_quick_mode",
    "return_to_document_mode",
    "return_button_during_a_quick_scan",
    "mode_selector",
    "last_scan_panel_in_document_mode",
    "finished_document_seen_from_another_tab",
    "page_added",
    "status_after_discarding_an_added_page",
)

pytestmark = pytest.mark.skipif(
    NODE_EXECUTABLE is None, reason="Node.js is not installed, so document-panel.js cannot be exercised"
)


@pytest.fixture(scope="module")
def scenario_results() -> dict:
    return run_panel_scenarios(SCENARIO_NAMES)


def test_big_button_says_add_page_in_document_mode(scenario_results: dict) -> None:
    assert scenario_results["idle_document_page"]["button_label"] == "Adicionar página"


def test_status_line_counts_the_pages_in_document_mode(scenario_results: dict) -> None:
    assert scenario_results["idle_document_page"]["status_text"] == f"3 páginas no documento. {NEXT_SHEET_TEXT}"


def test_document_section_is_shown_in_document_mode(scenario_results: dict) -> None:
    assert scenario_results["idle_document_page"]["section_hidden"] is False


def test_output_format_choice_is_hidden_in_document_mode(scenario_results: dict) -> None:
    assert scenario_results["idle_document_page"]["output_format_hidden"] is True


def test_document_bar_shows_the_page_count_and_size(scenario_results: dict) -> None:
    assert scenario_results["idle_document_page"]["summary_text"] == "3 páginas · ~2,4 MB"


def test_output_folder_space_line_is_hidden_in_document_mode(scenario_results: dict) -> None:
    assert scenario_results["idle_document_page"]["storage_line_hidden"] is True


def test_draft_space_line_describes_the_mac_disk(scenario_results: dict) -> None:
    assert (
        scenario_results["idle_document_page"]["draft_storage_text"]
        == "Espaço no Mac para as páginas: 12,0 GB — cabem ~4.000 páginas"
    )


def test_grid_shows_the_pages_in_order(scenario_results: dict) -> None:
    assert scenario_results["grid_tiles"]["page_identifiers"] == [FIRST_PAGE, SECOND_PAGE, THIRD_PAGE]


def test_tile_is_labelled_with_its_position(scenario_results: dict) -> None:
    assert scenario_results["grid_tiles"]["first_tile_label"] == "Página 1 de 3"


def test_tile_thumbnail_comes_from_the_document_route(scenario_results: dict) -> None:
    assert scenario_results["grid_tiles"]["thumbnail_source"] == f"/api/document/pages/{FIRST_PAGE}/thumbnail"


def test_tile_thumbnail_loads_lazily(scenario_results: dict) -> None:
    assert scenario_results["grid_tiles"]["thumbnail_loading"] == "lazy"


def test_tile_thumbnail_has_a_text_alternative(scenario_results: dict) -> None:
    assert scenario_results["grid_tiles"]["thumbnail_text"] == "Miniatura da página 1"


@pytest.mark.parametrize("button_state", ["first_left_disabled", "last_right_disabled"])
def test_arrow_at_the_end_of_the_grid_is_disabled(scenario_results: dict, button_state: str) -> None:
    assert scenario_results["grid_tiles"][button_state] is True


def test_delete_button_names_its_page(scenario_results: dict) -> None:
    assert scenario_results["grid_tiles"]["delete_label"] == "Excluir a página 2"


def test_tile_can_be_dragged_when_idle(scenario_results: dict) -> None:
    assert scenario_results["grid_tiles"]["draggable"] is True


def test_tile_buttons_follow_the_visual_order_for_the_tab_key(scenario_results: dict) -> None:
    assert scenario_results["grid_tiles"]["first_tile_action_labels"] == [
        "Mover a página 1 para a esquerda",
        "Mover a página 1 para a direita",
        "Excluir a página 1",
        "Girar a página 1 90 graus para a direita",
        "Mover a página 1 para outra posição",
    ]


def test_big_button_is_disabled_while_saving(scenario_results: dict) -> None:
    result = scenario_results["during_finalization"]
    assert (result["button_disabled"], result["button_label"]) == (True, "Salvando…")


def test_status_line_reports_the_saving(scenario_results: dict) -> None:
    assert scenario_results["during_finalization"]["status_text"] == "Salvando o PDF (3 páginas)…"


def test_space_while_finalizing_adds_no_page(scenario_results: dict) -> None:
    assert scenario_results["during_finalization"]["page_requests"] == 0


def test_older_document_answer_after_a_newer_one_is_ignored(scenario_results: dict) -> None:
    assert scenario_results["older_answer_after_a_newer_one"]["page_identifiers"] == [THIRD_PAGE]


def test_recovered_draft_switches_the_saved_mode_to_document(scenario_results: dict) -> None:
    assert scenario_results["recovered_draft_in_quick_mode"]["settings_request_body"] == {
        **SAVED_SETTINGS,
        "capture_mode": "document",
    }


def test_recovered_draft_shows_the_document_section(scenario_results: dict) -> None:
    assert scenario_results["recovered_draft_in_quick_mode"]["section_hidden"] is False


def test_recovered_draft_shows_what_the_recovery_did(scenario_results: dict) -> None:
    result = scenario_results["recovered_draft_in_quick_mode"]
    assert (result["notice_hidden"], result["notice_text"]) == (False, "Documento em andamento recuperado: 3 páginas.")


def test_recovered_draft_remembers_the_draft_session_it_switched_for(scenario_results: dict) -> None:
    assert scenario_results["recovered_draft_in_quick_mode"]["remembered_draft_session"] == "5c0f9a2e7b1d4c38"


def test_session_already_switched_leaves_the_quick_mode_alone(scenario_results: dict) -> None:
    result = scenario_results["recovered_draft_already_switched_in_quick_mode"]
    assert (result["settings_requests"], result["section_hidden"]) == (0, True)


def test_blocked_browser_storage_still_switches_a_recovered_draft(scenario_results: dict) -> None:
    assert scenario_results["recovered_draft_with_blocked_storage"]["settings_requests"] == 1


def test_reload_without_recovery_keeps_the_quick_mode(scenario_results: dict) -> None:
    result = scenario_results["reload_with_a_draft_in_quick_mode"]
    assert (result["settings_requests"], result["section_hidden"], result["button_label"]) == (0, True, "Digitalizar")


def test_quick_mode_with_a_draft_shows_the_pending_document_line(scenario_results: dict) -> None:
    result = scenario_results["reload_with_a_draft_in_quick_mode"]
    assert (result["pending_notice_hidden"], result["pending_text"]) == (False, "Documento em andamento: 3 páginas")


def test_return_button_saves_the_document_mode(scenario_results: dict) -> None:
    assert scenario_results["return_to_document_mode"]["settings_request_body"]["capture_mode"] == "document"


def test_return_button_shows_the_document_section_and_hides_the_line(scenario_results: dict) -> None:
    result = scenario_results["return_to_document_mode"]
    assert (result["section_hidden"], result["pending_notice_hidden"]) == (False, True)


def test_return_button_is_disabled_during_a_quick_scan(scenario_results: dict) -> None:
    assert scenario_results["return_button_during_a_quick_scan"]["is_disabled_while_scanning"] is True


def test_return_button_sends_no_settings_during_a_quick_scan(scenario_results: dict) -> None:
    assert scenario_results["return_button_during_a_quick_scan"]["settings_requests"] == 0


def test_mode_selector_saves_all_the_settings(scenario_results: dict) -> None:
    assert scenario_results["mode_selector"]["settings_request_body"] == {**SAVED_SETTINGS, "capture_mode": "single"}


def test_quick_mode_hides_the_document_section(scenario_results: dict) -> None:
    result = scenario_results["mode_selector"]
    assert (result["section_hidden"], result["button_label"]) == (True, "Digitalizar")


def test_last_file_panel_is_hidden_in_document_mode(scenario_results: dict) -> None:
    assert scenario_results["last_scan_panel_in_document_mode"]["last_scan_panel_hidden"] is True


def test_document_finished_in_another_tab_is_shown(scenario_results: dict) -> None:
    assert scenario_results["finished_document_seen_from_another_tab"] == {
        "finished_hidden": False,
        "finished_text": FINISHED_TEXT,
    }


def test_added_page_redraws_the_grid(scenario_results: dict) -> None:
    assert scenario_results["page_added"]["page_count"] == 4


def test_added_page_is_reported_in_the_status_line(scenario_results: dict) -> None:
    assert scenario_results["page_added"]["status_text"] == f"Página 4 adicionada. {NEXT_SHEET_TEXT}"


def test_status_line_drops_the_added_page_event_after_an_edit(scenario_results: dict) -> None:
    assert scenario_results["status_after_discarding_an_added_page"]["status_text"] == (
        f"3 páginas no documento. {NEXT_SHEET_TEXT}"
    )


def test_rotation_hint_is_shown_in_document_mode(scenario_results: dict) -> None:
    assert scenario_results["idle_document_page"]["rotation_hint_hidden"] is False


def test_tile_has_a_rotate_button_with_its_own_style_class(scenario_results: dict) -> None:
    result = scenario_results["grid_tiles"]
    assert (result["rotate_text"], result["rotate_class"]) == ("Girar ↻", "page-rotate")

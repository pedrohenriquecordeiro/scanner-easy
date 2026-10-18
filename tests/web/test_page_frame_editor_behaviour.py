import pytest

from tests.web.panel_scenario_runner import NODE_EXECUTABLE, run_frame_editor_scenarios

SECOND_PAGE = "0000000000000002"
SECOND_PAGE_FRAME = {"left": "13%", "top": "11.5%", "width": "78.4%", "height": "80%"}
WHOLE_PAGE_FRAME = {"left": "0%", "top": "0%", "width": "100%", "height": "100%"}
WEST_DRAGGED_FRAME = {"left": "23%", "top": "11.5%", "width": "68.4%", "height": "80%"}
SECOND_PAGE_STATUS = "Moldura: esquerda 13%, topo 12%, direita 91%, base 92%."
NO_CROP_STATUS = "Sem corte: a página inteira será usada."

SCENARIO_NAMES = (
    "open_by_the_enlarge_button",
    "open_by_the_thumbnail",
    "open_a_page_without_a_crop",
    "open_a_turned_page",
    "stage_while_the_image_loads",
    "image_that_fails_to_load",
    "open_while_a_page_scans",
    "tab_order_of_the_dialog",
    "drag_the_west_handle",
    "drag_a_corner",
    "drag_the_whole_frame",
    "drag_is_measured_from_where_it_began",
    "drag_past_the_page",
    "cancelled_drag",
    "move_without_pressing",
    "arrow_on_the_left_edge",
    "shift_arrow_on_the_left_edge",
    "arrow_on_a_corner",
    "arrow_on_the_move_button",
    "other_key_on_a_handle",
    "no_crop_button",
    "no_crop_button_on_a_page_without_a_crop",
)

pytestmark = pytest.mark.skipif(
    NODE_EXECUTABLE is None, reason="Node.js is not installed, so page-frame-editor.js cannot be exercised"
)


@pytest.fixture(scope="module")
def scenario_results() -> dict:
    return run_frame_editor_scenarios(SCENARIO_NAMES)


def test_the_enlarge_button_opens_the_dialog(scenario_results: dict) -> None:
    assert scenario_results["open_by_the_enlarge_button"]["dialog"]["open"] is True


def test_the_dialog_is_titled_with_the_position_of_the_page(scenario_results: dict) -> None:
    assert scenario_results["open_by_the_enlarge_button"]["dialog"]["title"] == "Página 2 de 3: moldura de corte"


def test_the_dialog_shows_the_enlarged_view_of_the_page(scenario_results: dict) -> None:
    dialog = scenario_results["open_by_the_enlarge_button"]["dialog"]
    assert dialog["image_source"] == f"/api/document/pages/{SECOND_PAGE}/preview?rotation_degrees=0"


def test_the_enlarged_view_has_a_text_alternative(scenario_results: dict) -> None:
    assert scenario_results["open_by_the_enlarge_button"]["dialog"]["image_alt"] == "Página 2 ampliada"


def test_the_dialog_starts_from_the_saved_frame(scenario_results: dict) -> None:
    dialog = scenario_results["open_by_the_enlarge_button"]["dialog"]
    assert (dialog["frame_box"], dialog["cutout"]) == (SECOND_PAGE_FRAME, SECOND_PAGE_FRAME)


def test_the_dialog_says_where_the_frame_is(scenario_results: dict) -> None:
    assert scenario_results["open_by_the_enlarge_button"]["dialog"]["status"] == SECOND_PAGE_STATUS


def test_the_dialog_opens_with_nothing_to_apply_and_every_edit_available(scenario_results: dict) -> None:
    dialog = scenario_results["open_by_the_enlarge_button"]["dialog"]
    assert (
        dialog["apply_disabled"],
        dialog["detect_disabled"],
        dialog["rotate_disabled"],
        dialog["clear_disabled"],
    ) == (
        True,
        False,
        False,
        False,
    )


def test_the_dialog_opens_on_the_move_button(scenario_results: dict) -> None:
    assert scenario_results["open_by_the_enlarge_button"]["focused_move_button"] is True


def test_the_handles_are_named_in_portuguese(scenario_results: dict) -> None:
    assert scenario_results["open_by_the_enlarge_button"]["handle_labels"] == [
        "Borda de cima",
        "Canto superior direito",
        "Borda direita",
        "Canto inferior direito",
        "Borda de baixo",
        "Canto inferior esquerdo",
        "Borda esquerda",
        "Canto superior esquerdo",
    ]


def test_a_click_on_the_thumbnail_opens_the_dialog_too(scenario_results: dict) -> None:
    assert scenario_results["open_by_the_thumbnail"] == {
        "open": True,
        "title": "Página 2 de 3: moldura de corte",
    }


def test_a_page_without_a_crop_opens_with_the_whole_page_as_the_frame(scenario_results: dict) -> None:
    dialog = scenario_results["open_a_page_without_a_crop"]
    assert (dialog["frame_box"], dialog["status"]) == (WHOLE_PAGE_FRAME, NO_CROP_STATUS)


def test_a_turned_page_asks_for_its_enlarged_view_turned(scenario_results: dict) -> None:
    image_source = scenario_results["open_a_turned_page"]["image_source"]
    assert image_source == f"/api/document/pages/{SECOND_PAGE}/preview?rotation_degrees=270"


def test_the_stage_is_marked_as_loading_until_the_image_arrives(scenario_results: dict) -> None:
    assert scenario_results["stage_while_the_image_loads"] == {"while_loading": True, "after_loading": False}


def test_an_image_that_fails_to_load_is_said_in_the_status(scenario_results: dict) -> None:
    result = scenario_results["image_that_fails_to_load"]
    assert (result["status"], result["open"]) == ("Não consegui carregar a imagem ampliada desta página.", True)


def test_looking_is_possible_while_a_page_scans_but_editing_is_not(scenario_results: dict) -> None:
    dialog = scenario_results["open_while_a_page_scans"]
    assert (dialog["open"], dialog["detect_disabled"], dialog["rotate_disabled"], dialog["apply_disabled"]) == (
        True,
        True,
        True,
        True,
    )


def test_the_tab_order_goes_from_the_move_button_around_the_handles_to_the_actions(scenario_results: dict) -> None:
    assert scenario_results["tab_order_of_the_dialog"]["identifiers"] == [
        "frame-move-button",
        "frame-handle-north",
        "frame-handle-north-east",
        "frame-handle-east",
        "frame-handle-south-east",
        "frame-handle-south",
        "frame-handle-south-west",
        "frame-handle-west",
        "frame-handle-north-west",
        "frame-detect-button",
        "frame-clear-button",
        "frame-rotate-button",
        "frame-cancel-button",
        "frame-apply-button",
    ]


def test_pressing_a_handle_captures_the_pointer(scenario_results: dict) -> None:
    assert scenario_results["drag_the_west_handle"]["captured_while_dragging"] is True


def test_dragging_a_handle_moves_the_frame_and_the_shade_with_it(scenario_results: dict) -> None:
    during = scenario_results["drag_the_west_handle"]["during"]
    assert (during["frame_box"], during["cutout"]) == (WEST_DRAGGED_FRAME, WEST_DRAGGED_FRAME)


def test_the_status_is_not_repeated_while_dragging(scenario_results: dict) -> None:
    assert scenario_results["drag_the_west_handle"]["during"]["status"] == SECOND_PAGE_STATUS


def test_the_status_says_the_frame_when_the_pointer_is_released(scenario_results: dict) -> None:
    after = scenario_results["drag_the_west_handle"]["after"]
    assert after["status"] == "Moldura: esquerda 23%, topo 12%, direita 91%, base 92%."


def test_releasing_the_pointer_lets_go_of_the_capture(scenario_results: dict) -> None:
    assert scenario_results["drag_the_west_handle"]["released_after"] is True


def test_a_dragged_frame_can_be_applied(scenario_results: dict) -> None:
    assert scenario_results["drag_the_west_handle"]["after"]["apply_disabled"] is False


def test_dragging_a_corner_moves_two_edges(scenario_results: dict) -> None:
    dialog = scenario_results["drag_a_corner"]
    assert dialog["frame_box"] == {"left": "23%", "top": "21.5%", "width": "68.4%", "height": "70%"}


def test_a_corner_drag_says_the_frame_when_released(scenario_results: dict) -> None:
    status = scenario_results["drag_a_corner"]["status"]
    assert status == "Moldura: esquerda 23%, topo 22%, direita 91%, base 92%."


def test_dragging_the_frame_keeps_its_size(scenario_results: dict) -> None:
    dialog = scenario_results["drag_the_whole_frame"]
    assert dialog["frame_box"] == {"left": "18%", "top": "16.5%", "width": "78.4%", "height": "80%"}


def test_a_moved_frame_says_where_it_is(scenario_results: dict) -> None:
    status = scenario_results["drag_the_whole_frame"]["status"]
    assert status == "Moldura: esquerda 18%, topo 17%, direita 96%, base 97%."


def test_a_drag_is_measured_from_where_it_began(scenario_results: dict) -> None:
    assert scenario_results["drag_is_measured_from_where_it_began"]["frame_box"] == WEST_DRAGGED_FRAME


def test_an_edge_dragged_past_the_page_stops_at_the_minimum_size(scenario_results: dict) -> None:
    dialog = scenario_results["drag_past_the_page"]
    assert (dialog["frame_box"]["left"], dialog["frame_box"]["width"]) == ("89.4%", "2%")


def test_a_cancelled_pointer_ends_the_drag_and_lets_go(scenario_results: dict) -> None:
    result = scenario_results["cancelled_drag"]
    assert (result["released"], result["dialog"]["frame_box"]) == (True, WEST_DRAGGED_FRAME)


def test_the_status_follows_a_cancelled_drag_too(scenario_results: dict) -> None:
    status = scenario_results["cancelled_drag"]["dialog"]["status"]
    assert status == "Moldura: esquerda 23%, topo 12%, direita 91%, base 92%."


def test_a_pointer_that_never_pressed_a_handle_moves_nothing(scenario_results: dict) -> None:
    assert scenario_results["move_without_pressing"]["frame_box"] == SECOND_PAGE_FRAME


def test_an_arrow_pushes_the_edge_by_a_fine_step(scenario_results: dict) -> None:
    dialog = scenario_results["arrow_on_the_left_edge"]["dialog"]
    assert dialog["frame_box"] == {"left": "13.5%", "top": "11.5%", "width": "77.9%", "height": "80%"}


def test_an_arrow_on_an_edge_says_where_the_edge_is(scenario_results: dict) -> None:
    assert scenario_results["arrow_on_the_left_edge"]["dialog"]["status"] == "Borda esquerda em 14%."


def test_an_arrow_does_not_scroll_the_page(scenario_results: dict) -> None:
    assert scenario_results["arrow_on_the_left_edge"]["default_prevented"] is True


def test_shift_with_an_arrow_pushes_by_a_coarse_step(scenario_results: dict) -> None:
    dialog = scenario_results["shift_arrow_on_the_left_edge"]
    assert (dialog["frame_box"]["left"], dialog["status"]) == ("8%", "Borda esquerda em 8%.")


def test_arrows_on_a_corner_push_both_edges_and_say_both(scenario_results: dict) -> None:
    dialog = scenario_results["arrow_on_a_corner"]
    assert (dialog["frame_box"], dialog["status"]) == (
        {"left": "13%", "top": "11.5%", "width": "73.4%", "height": "75%"},
        "Canto inferior direito: direita 86%, base 87%.",
    )


def test_arrows_on_the_move_button_move_the_whole_frame(scenario_results: dict) -> None:
    dialog = scenario_results["arrow_on_the_move_button"]
    assert (dialog["frame_box"]["left"], dialog["frame_box"]["width"]) == ("8%", "78.4%")


def test_arrows_on_the_move_button_say_the_frame(scenario_results: dict) -> None:
    status = scenario_results["arrow_on_the_move_button"]["status"]
    assert status == "Moldura: esquerda 8%, topo 12%, direita 86%, base 92%."


def test_another_key_on_a_handle_changes_nothing(scenario_results: dict) -> None:
    result = scenario_results["other_key_on_a_handle"]
    assert (result["default_prevented"], result["dialog"]["frame_box"]) == (False, SECOND_PAGE_FRAME)


def test_no_crop_makes_the_whole_page_the_frame(scenario_results: dict) -> None:
    dialog = scenario_results["no_crop_button"]
    assert (dialog["frame_box"], dialog["status"]) == (WHOLE_PAGE_FRAME, NO_CROP_STATUS)


def test_no_crop_on_a_page_with_a_crop_can_be_applied(scenario_results: dict) -> None:
    assert scenario_results["no_crop_button"]["apply_disabled"] is False


def test_no_crop_on_a_page_without_a_crop_changes_nothing_to_apply(scenario_results: dict) -> None:
    assert scenario_results["no_crop_button_on_a_page_without_a_crop"]["apply_disabled"] is True

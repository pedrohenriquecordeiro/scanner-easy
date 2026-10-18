import pytest

from tests.web.panel_scenario_runner import NODE_EXECUTABLE, run_frame_editor_scenarios

SECOND_PAGE = "0000000000000002"
SECOND_PAGE_OUTLINE = "13,11.5 91.4,11.5 91.4,91.5 13,91.5"
SECOND_PAGE_CLIP = "polygon(13% 11.5%, 91.4% 11.5%, 91.4% 91.5%, 13% 91.5%)"
SECOND_PAGE_STATUS = "Moldura 1: esquerda 13%, topo 12%, direita 91%, base 92%."
UPPER_OUTLINE = "5,2 90,2 90,55 5,55"
LOWER_OUTLINE = "5,60 90,60 90,95 5,95"
WEST_DRAGGED_OUTLINE = "23,11.5 91.4,11.5 91.4,91.5 23,91.5"
NO_CROP_STATUS = "Sem corte: a página inteira será usada."
INVALID_MOVE_STATUS = "Esse movimento deixaria a moldura torta demais. Ela ficou como estava."
HANDLE_LABELS = {
    "corners": [
        "Canto superior esquerdo",
        "Canto superior direito",
        "Canto inferior direito",
        "Canto inferior esquerdo",
    ],
    "edges": ["Borda de cima", "Borda direita", "Borda de baixo", "Borda esquerda"],
}

SCENARIO_NAMES = (
    "open_by_the_enlarge_button",
    "open_by_the_thumbnail",
    "open_a_page_without_a_frame",
    "open_a_page_with_two_frames",
    "open_a_tilted_frame",
    "open_a_turned_page",
    "stage_while_the_image_loads",
    "image_that_fails_to_load",
    "open_while_a_page_scans",
    "tab_order_with_one_frame",
    "tab_order_with_two_frames",
    "tab_order_without_a_frame",
    "drag_the_left_edge",
    "drag_a_corner",
    "drag_a_corner_of_a_tilted_frame",
    "drag_the_whole_frame",
    "drag_the_whole_frame_past_the_page",
    "drag_the_rotate_handle",
    "drag_is_measured_from_where_it_began",
    "drag_a_corner_past_the_opposite_corner",
    "drag_a_corner_back_to_a_good_place_after_a_refusal",
    "second_finger_does_not_take_the_drag",
    "open_before_the_size_of_the_picture_is_known",
    "status_the_user_already_changed_is_kept_when_the_picture_loads",
    "cancelled_drag",
    "drag_with_the_secondary_button",
    "drag_with_the_middle_button_on_the_move_area",
    "context_menu_on_the_stage",
    "move_without_pressing",
    "drag_the_second_frame_before_the_first",
)

pytestmark = pytest.mark.skipif(
    NODE_EXECUTABLE is None, reason="Node.js is not installed, so page-frame-editor.js cannot be exercised"
)


@pytest.fixture(scope="module")
def scenario_results() -> dict:
    return run_frame_editor_scenarios(SCENARIO_NAMES)


def outline_points(dialog: dict) -> list[str | None]:
    return [outline["points"] for outline in dialog["overlay"]["outlines"]]


def test_the_enlarge_button_opens_the_dialog(scenario_results: dict) -> None:
    assert scenario_results["open_by_the_enlarge_button"]["dialog"]["open"] is True


def test_the_dialog_is_titled_with_the_position_of_the_page(scenario_results: dict) -> None:
    assert scenario_results["open_by_the_enlarge_button"]["dialog"]["title"] == "Página 2 de 3: moldura de corte"


def test_the_dialog_shows_the_enlarged_view_of_the_page(scenario_results: dict) -> None:
    dialog = scenario_results["open_by_the_enlarge_button"]["dialog"]
    assert dialog["image_source"] == f"/api/document/pages/{SECOND_PAGE}/preview?rotation_degrees=0"


def test_the_enlarged_view_has_a_text_alternative(scenario_results: dict) -> None:
    assert scenario_results["open_by_the_enlarge_button"]["dialog"]["image_alt"] == "Página 2 ampliada"


def test_the_dialog_draws_the_saved_frame_and_shades_the_outside(scenario_results: dict) -> None:
    overlay = scenario_results["open_by_the_enlarge_button"]["dialog"]["overlay"]
    assert (overlay["hidden"], overlay["outlines"][0]["points"], overlay["shade_path"]) == (
        False,
        SECOND_PAGE_OUTLINE,
        "M0 0H100V100H0ZM13 11.5L91.4 11.5L91.4 91.5L13 91.5Z",
    )


def test_the_dialog_marks_the_frame_it_edits_as_the_active_one(scenario_results: dict) -> None:
    outlines = scenario_results["open_by_the_enlarge_button"]["dialog"]["overlay"]["outlines"]
    assert [outline["is_active"] for outline in outlines] == [True, False]


def test_the_dialog_says_where_the_frame_is(scenario_results: dict) -> None:
    assert scenario_results["open_by_the_enlarge_button"]["dialog"]["status"] == SECOND_PAGE_STATUS


def test_the_dialog_opens_with_nothing_to_apply_and_every_edit_available(scenario_results: dict) -> None:
    disabled = scenario_results["open_by_the_enlarge_button"]["dialog"]["disabled"]
    assert disabled == {
        "add": False,
        "remove": False,
        "turn": False,
        "detect": False,
        "clear": False,
        "rotate": False,
        "apply": True,
    }


def test_the_dialog_opens_on_the_move_button(scenario_results: dict) -> None:
    assert scenario_results["open_by_the_enlarge_button"]["focused_move_button"] is True


def test_the_move_button_takes_the_pointer_only_inside_the_frame(scenario_results: dict) -> None:
    move = scenario_results["open_by_the_enlarge_button"]["dialog"]["move"]
    assert (move["hidden"], move["clip_path"]) == (False, SECOND_PAGE_CLIP)


def test_the_corner_handles_sit_on_the_corners_of_the_frame(scenario_results: dict) -> None:
    corners = scenario_results["open_by_the_enlarge_button"]["dialog"]["corners"]
    assert [(corner["left"], corner["top"]) for corner in corners.values()] == [
        ("13%", "11.5%"),
        ("91.4%", "11.5%"),
        ("91.4%", "91.5%"),
        ("13%", "91.5%"),
    ]


def test_the_edge_handles_sit_in_the_middle_of_the_edges(scenario_results: dict) -> None:
    edges = scenario_results["open_by_the_enlarge_button"]["dialog"]["edges"]
    assert [(edge["left"], edge["top"]) for edge in edges.values()] == [
        ("52.2%", "11.5%"),
        ("91.4%", "51.5%"),
        ("52.2%", "91.5%"),
        ("13%", "51.5%"),
    ]


def test_the_rotate_handle_sits_above_the_top_edge(scenario_results: dict) -> None:
    handle = scenario_results["open_by_the_enlarge_button"]["dialog"]["rotate_handle"]
    assert (handle["left"], handle["top"]) == ("52.2%", "2%")


def test_the_handles_are_named_in_portuguese(scenario_results: dict) -> None:
    dialog = scenario_results["open_by_the_enlarge_button"]["dialog"]
    assert (
        [corner["label"] for corner in dialog["corners"].values()],
        [edge["label"] for edge in dialog["edges"].values()],
        dialog["rotate_handle"]["label"],
        dialog["move"]["label"],
    ) == (HANDLE_LABELS["corners"], HANDLE_LABELS["edges"], "Girar a moldura", "Mover a moldura")


def test_the_turn_button_names_the_frame_it_turns(scenario_results: dict) -> None:
    turn_label = scenario_results["open_by_the_enlarge_button"]["dialog"]["turn_label"]
    assert turn_label == "Girar a moldura 1 em 90 graus para a direita: muda o lado de cima da foto recortada"


def test_a_click_on_the_thumbnail_opens_the_dialog_too(scenario_results: dict) -> None:
    assert scenario_results["open_by_the_thumbnail"] == {"open": True, "title": "Página 2 de 3: moldura de corte"}


def test_a_page_without_a_frame_opens_with_no_frame_drawn(scenario_results: dict) -> None:
    dialog = scenario_results["open_a_page_without_a_frame"]["dialog"]
    assert (dialog["overlay"]["hidden"], dialog["status"]) == (True, NO_CROP_STATUS)


def test_a_page_without_a_frame_hides_every_handle(scenario_results: dict) -> None:
    dialog = scenario_results["open_a_page_without_a_frame"]["dialog"]
    hidden = [handle["hidden"] for handle in [*dialog["corners"].values(), *dialog["edges"].values()]]
    assert (all(hidden), dialog["rotate_handle"]["hidden"], dialog["move"]["hidden"]) == (True, True, True)


def test_a_page_without_a_frame_can_only_add_one(scenario_results: dict) -> None:
    disabled = scenario_results["open_a_page_without_a_frame"]["dialog"]["disabled"]
    assert (disabled["add"], disabled["remove"], disabled["turn"]) == (False, True, True)


def test_a_page_without_a_frame_opens_on_the_add_button(scenario_results: dict) -> None:
    assert scenario_results["open_a_page_without_a_frame"]["focused_add_button"] is True


def test_a_page_with_two_frames_draws_both(scenario_results: dict) -> None:
    dialog = scenario_results["open_a_page_with_two_frames"]["dialog"]
    assert outline_points(dialog) == [UPPER_OUTLINE, LOWER_OUTLINE]


def test_a_page_with_two_frames_opens_on_the_first_and_says_so(scenario_results: dict) -> None:
    status = scenario_results["open_a_page_with_two_frames"]["dialog"]["status"]
    assert status == "Moldura 1 de 2 selecionada. Moldura 1: esquerda 5%, topo 2%, direita 90%, base 55%."


def test_a_page_with_two_frames_gives_the_handles_to_the_first(scenario_results: dict) -> None:
    dialog = scenario_results["open_a_page_with_two_frames"]["dialog"]
    assert (dialog["corners"]["top_left"]["label"], dialog["move"]["label"], dialog["rotate_handle"]["label"]) == (
        "Canto superior esquerdo da moldura 1",
        "Mover a moldura 1",
        "Girar a moldura 1",
    )


def test_a_page_with_two_frames_offers_to_select_the_other(scenario_results: dict) -> None:
    select = scenario_results["open_a_page_with_two_frames"]["dialog"]["select"]
    assert (select["hidden"], select["label"], select["clip_path"]) == (
        False,
        "Selecionar moldura 2",
        "polygon(5% 60%, 90% 60%, 90% 95%, 5% 95%)",
    )


def test_a_page_with_two_frames_cannot_add_a_third(scenario_results: dict) -> None:
    assert scenario_results["open_a_page_with_two_frames"]["dialog"]["disabled"]["add"] is True


def test_a_page_with_one_frame_offers_no_other_frame_to_select(scenario_results: dict) -> None:
    assert scenario_results["open_by_the_enlarge_button"]["dialog"]["select"]["hidden"] is True


def test_a_tilted_frame_is_drawn_with_its_corners_where_they_are(scenario_results: dict) -> None:
    dialog = scenario_results["open_a_tilted_frame"]
    assert dialog["overlay"]["outlines"][0]["points"] == "40,55 93,44 97,80 44,91"


def test_the_handles_of_a_tilted_frame_follow_its_corners(scenario_results: dict) -> None:
    corners = scenario_results["open_a_tilted_frame"]["corners"]
    assert [(corner["left"], corner["top"]) for corner in corners.values()] == [
        ("40%", "55%"),
        ("93%", "44%"),
        ("97%", "80%"),
        ("44%", "91%"),
    ]


def test_a_tilted_frame_is_described_by_its_tilt_and_corners(scenario_results: dict) -> None:
    assert scenario_results["open_a_tilted_frame"]["status"] == (
        "Moldura 1: inclinada 9° para a esquerda. "
        "Cantos: superior esquerdo (40%, 55%), superior direito (93%, 44%), "
        "inferior direito (97%, 80%), inferior esquerdo (44%, 91%)."
    )


def test_a_turned_page_asks_for_its_enlarged_view_turned(scenario_results: dict) -> None:
    image_source = scenario_results["open_a_turned_page"]["image_source"]
    assert image_source == f"/api/document/pages/{SECOND_PAGE}/preview?rotation_degrees=270"


def test_the_stage_is_marked_as_loading_until_the_image_arrives(scenario_results: dict) -> None:
    assert scenario_results["stage_while_the_image_loads"] == {"while_loading": True, "after_loading": False}


def test_an_image_that_fails_to_load_is_said_in_the_status(scenario_results: dict) -> None:
    result = scenario_results["image_that_fails_to_load"]
    assert (result["status"], result["open"]) == ("Não consegui carregar a imagem ampliada nesta página.", True)


def test_looking_is_possible_while_a_page_scans_but_editing_is_not(scenario_results: dict) -> None:
    dialog = scenario_results["open_while_a_page_scans"]
    disabled = dialog["disabled"]
    assert (dialog["open"], disabled["detect"], disabled["rotate"], disabled["apply"]) == (True, True, True, True)


def test_the_tab_order_goes_around_the_handles_then_to_the_actions(scenario_results: dict) -> None:
    assert scenario_results["tab_order_with_one_frame"]["identifiers"] == [
        "frame-corner-top-left",
        "frame-corner-top-right",
        "frame-corner-bottom-right",
        "frame-corner-bottom-left",
        "frame-edge-top",
        "frame-edge-right",
        "frame-edge-bottom",
        "frame-edge-left",
        "frame-move-button",
        "frame-rotate-handle",
        "frame-add-button",
        "frame-remove-button",
        "frame-turn-button",
        "frame-detect-button",
        "frame-clear-button",
        "frame-rotate-button",
        "frame-cancel-button",
        "frame-apply-button",
    ]


def test_with_two_frames_the_select_button_comes_after_the_handles(scenario_results: dict) -> None:
    identifiers = scenario_results["tab_order_with_two_frames"]["identifiers"]
    assert identifiers[9:12] == ["frame-rotate-handle", "frame-select-button", "frame-add-button"]


def test_without_a_frame_the_tab_order_has_only_the_actions(scenario_results: dict) -> None:
    assert scenario_results["tab_order_without_a_frame"]["identifiers"] == [
        "frame-add-button",
        "frame-remove-button",
        "frame-turn-button",
        "frame-detect-button",
        "frame-clear-button",
        "frame-rotate-button",
        "frame-cancel-button",
        "frame-apply-button",
    ]


def test_pressing_a_handle_captures_the_pointer(scenario_results: dict) -> None:
    assert scenario_results["drag_the_left_edge"]["captured_while_dragging"] is True


def test_dragging_an_edge_moves_the_frame_and_the_shade_with_it(scenario_results: dict) -> None:
    during = scenario_results["drag_the_left_edge"]["during"]["overlay"]
    assert (during["outlines"][0]["points"], during["shade_path"]) == (
        WEST_DRAGGED_OUTLINE,
        "M0 0H100V100H0ZM23 11.5L91.4 11.5L91.4 91.5L23 91.5Z",
    )


def test_the_handles_follow_the_frame_while_dragging(scenario_results: dict) -> None:
    during = scenario_results["drag_the_left_edge"]["during"]
    assert (during["corners"]["top_left"]["left"], during["edges"]["left"]["left"]) == ("23%", "23%")


def test_the_move_area_follows_the_frame_while_dragging(scenario_results: dict) -> None:
    clip_path = scenario_results["drag_the_left_edge"]["during"]["move"]["clip_path"]
    assert clip_path == "polygon(23% 11.5%, 91.4% 11.5%, 91.4% 91.5%, 23% 91.5%)"


def test_the_status_is_not_repeated_while_dragging(scenario_results: dict) -> None:
    assert scenario_results["drag_the_left_edge"]["during"]["status"] == SECOND_PAGE_STATUS


def test_the_status_says_the_frame_when_the_pointer_is_released(scenario_results: dict) -> None:
    after = scenario_results["drag_the_left_edge"]["after"]
    assert after["status"] == "Moldura 1: esquerda 23%, topo 12%, direita 91%, base 92%."


def test_releasing_the_pointer_lets_go_of_the_capture(scenario_results: dict) -> None:
    assert scenario_results["drag_the_left_edge"]["released_after"] is True


def test_a_dragged_frame_can_be_applied(scenario_results: dict) -> None:
    assert scenario_results["drag_the_left_edge"]["after"]["disabled"]["apply"] is False


def test_dragging_a_corner_moves_only_that_corner(scenario_results: dict) -> None:
    dialog = scenario_results["drag_a_corner"]
    assert dialog["overlay"]["outlines"][0]["points"] == "23,21.5 91.4,11.5 91.4,91.5 13,91.5"


def test_a_frame_with_one_corner_moved_is_described_by_its_tilt(scenario_results: dict) -> None:
    assert scenario_results["drag_a_corner"]["status"] == (
        "Moldura 1: inclinada 7° para a esquerda. "
        "Cantos: superior esquerdo (23%, 22%), superior direito (91%, 12%), "
        "inferior direito (91%, 92%), inferior esquerdo (13%, 92%)."
    )


def test_dragging_a_corner_of_a_tilted_frame_keeps_the_other_three(scenario_results: dict) -> None:
    dialog = scenario_results["drag_a_corner_of_a_tilted_frame"]
    assert dialog["overlay"]["outlines"][0]["points"] == "40,55 83,54 97,80 44,91"


def test_dragging_the_frame_keeps_its_shape_and_size(scenario_results: dict) -> None:
    dialog = scenario_results["drag_the_whole_frame"]
    assert dialog["overlay"]["outlines"][0]["points"] == "18,16.5 96.4,16.5 96.4,96.5 18,96.5"


def test_a_moved_frame_says_where_it_is(scenario_results: dict) -> None:
    status = scenario_results["drag_the_whole_frame"]["status"]
    assert status == "Moldura 1: esquerda 18%, topo 17%, direita 96%, base 97%."


def test_a_frame_dragged_past_the_page_stops_at_the_edge_of_the_page(scenario_results: dict) -> None:
    dialog = scenario_results["drag_the_whole_frame_past_the_page"]
    assert dialog["overlay"]["outlines"][0]["points"] == "21.6,20 100,20 100,100 21.6,100"


def test_dragging_the_rotate_handle_turns_the_frame_around_its_centre(scenario_results: dict) -> None:
    dialog = scenario_results["drag_the_rotate_handle"]
    assert dialog["overlay"]["outlines"][0]["points"] == "83.87,3 83.87,100 20.53,100 20.53,3"


def test_a_frame_turned_a_quarter_says_where_its_top_side_went(scenario_results: dict) -> None:
    assert scenario_results["drag_the_rotate_handle"]["status"].endswith("Lado de cima da foto à direita.")


def test_the_rotate_handle_follows_the_turned_frame(scenario_results: dict) -> None:
    handle = scenario_results["drag_the_rotate_handle"]["rotate_handle"]
    assert (handle["left"], handle["top"]) == ("92.47%", "51.5%")


def test_a_drag_is_measured_from_where_it_began(scenario_results: dict) -> None:
    dialog = scenario_results["drag_is_measured_from_where_it_began"]
    assert dialog["overlay"]["outlines"][0]["points"] == WEST_DRAGGED_OUTLINE


def test_a_corner_dragged_where_the_frame_would_bend_keeps_the_last_good_place(scenario_results: dict) -> None:
    result = scenario_results["drag_a_corner_past_the_opposite_corner"]
    assert outline_points(result["during_the_refusal"]) == outline_points(result["valid_place"])


def test_a_refused_drag_says_so_when_it_ends(scenario_results: dict) -> None:
    after = scenario_results["drag_a_corner_past_the_opposite_corner"]["after"]
    assert after["status"] == INVALID_MOVE_STATUS


def test_a_drag_that_comes_back_to_a_good_place_is_not_refused(scenario_results: dict) -> None:
    dialog = scenario_results["drag_a_corner_back_to_a_good_place_after_a_refusal"]
    assert dialog["overlay"]["outlines"][0]["points"] == "23,21.5 91.4,11.5 91.4,91.5 13,91.5"


def test_a_cancelled_pointer_ends_the_drag_and_lets_go(scenario_results: dict) -> None:
    result = scenario_results["cancelled_drag"]
    assert (result["released"], outline_points(result["dialog"])[0]) == (True, WEST_DRAGGED_OUTLINE)


def test_the_secondary_button_does_not_start_a_drag(scenario_results: dict) -> None:
    result = scenario_results["drag_with_the_secondary_button"]
    assert (result["captured"], outline_points(result["dialog"])[0]) == (False, SECOND_PAGE_OUTLINE)


def test_the_middle_button_does_not_move_the_frame(scenario_results: dict) -> None:
    dialog = scenario_results["drag_with_the_middle_button_on_the_move_area"]
    assert outline_points(dialog)[0] == SECOND_PAGE_OUTLINE


def test_the_context_menu_of_the_stage_is_suppressed(scenario_results: dict) -> None:
    assert scenario_results["context_menu_on_the_stage"]["prevented"] is True


def test_a_pointer_that_never_pressed_a_handle_moves_nothing(scenario_results: dict) -> None:
    assert outline_points(scenario_results["move_without_pressing"])[0] == SECOND_PAGE_OUTLINE


def test_a_frame_dragged_before_the_other_becomes_the_first(scenario_results: dict) -> None:
    dialog = scenario_results["drag_the_second_frame_before_the_first"]
    assert outline_points(dialog) == ["4,10 44,10 44,90 4,90", "10,10 40,10 40,90 10,90"]


def test_the_frame_being_dragged_stays_the_selected_one_after_the_order_changes(scenario_results: dict) -> None:
    dialog = scenario_results["drag_the_second_frame_before_the_first"]
    assert [outline["is_active"] for outline in dialog["overlay"]["outlines"]] == [True, False]


def test_a_second_finger_on_another_handle_does_not_take_the_drag(scenario_results: dict) -> None:
    result = scenario_results["second_finger_does_not_take_the_drag"]
    assert (result["second_captured"], outline_points(result["dialog"])[0]) == (False, WEST_DRAGGED_OUTLINE)


def test_the_opening_text_is_written_again_when_the_size_of_the_picture_is_known(scenario_results: dict) -> None:
    result = scenario_results["open_before_the_size_of_the_picture_is_known"]
    assert (result["before_loading"]["status"][:30], result["after_loading"]["status"][:30]) == (
        "Moldura 1: inclinada 12° para ",
        "Moldura 1: inclinada 9° para a",
    )


def test_the_handles_are_placed_again_when_the_size_of_the_picture_is_known(scenario_results: dict) -> None:
    result = scenario_results["open_before_the_size_of_the_picture_is_known"]
    assert result["before_loading"]["rotate_handle"] != result["after_loading"]["rotate_handle"]


def test_a_text_the_user_caused_is_not_replaced_when_the_picture_loads(scenario_results: dict) -> None:
    result = scenario_results["status_the_user_already_changed_is_kept_when_the_picture_loads"]
    assert result["after_loading"] == result["after_the_drag"]
    assert result["after_loading"] == "Moldura 1: esquerda 23%, topo 12%, direita 91%, base 92%."

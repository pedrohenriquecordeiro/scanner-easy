import pytest

from tests.web.panel_scenario_runner import NODE_EXECUTABLE, run_frame_editor_scenarios

SECOND_PAGE_OUTLINE = "13,11.5 91.4,11.5 91.4,91.5 13,91.5"
SECOND_PAGE_STATUS = "Moldura 1: esquerda 13%, topo 12%, direita 91%, base 92%."
UPPER_OUTLINE = "5,2 90,2 90,55 5,55"
LOWER_OUTLINE = "5,60 90,60 90,95 5,95"
NO_CROP_STATUS = "Sem corte: a página inteira será usada."
INVALID_MOVE_STATUS = "Esse movimento deixaria a moldura torta demais. Ela ficou como estava."

SCENARIO_NAMES = (
    "arrow_on_the_left_edge",
    "shift_arrow_on_the_left_edge",
    "tangent_arrow_on_the_left_edge",
    "arrows_on_a_corner",
    "arrow_on_the_move_button",
    "arrows_on_the_rotate_handle",
    "vertical_arrow_on_the_rotate_handle",
    "arrow_that_would_bend_the_frame",
    "other_key_on_a_handle",
    "arrow_on_a_page_without_a_frame",
    "add_a_frame_to_a_page_without_a_frame",
    "add_a_second_frame_next_to_the_first",
    "add_a_second_frame_to_the_right_of_a_frame_on_the_left",
    "remove_one_of_two_frames",
    "remove_the_only_frame",
    "turn_the_frame_output",
    "select_the_other_frame_with_the_pointer",
    "select_the_other_frame_with_the_keyboard",
    "select_the_other_frame_twice",
    "no_crop_button",
    "no_crop_button_with_two_frames",
    "no_crop_button_on_a_page_without_a_frame",
)

pytestmark = pytest.mark.skipif(
    NODE_EXECUTABLE is None, reason="Node.js is not installed, so page-frame-editor.js cannot be exercised"
)


@pytest.fixture(scope="module")
def scenario_results() -> dict:
    return run_frame_editor_scenarios(SCENARIO_NAMES)


def outline_points(dialog: dict) -> list[str | None]:
    return [outline["points"] for outline in dialog["overlay"]["outlines"]]


def test_an_arrow_pushes_an_edge_by_a_fine_step(scenario_results: dict) -> None:
    dialog = scenario_results["arrow_on_the_left_edge"]["dialog"]
    assert outline_points(dialog)[0] == "13.5,11.5 91.4,11.5 91.4,91.5 13.5,91.5"


def test_an_arrow_on_an_edge_says_where_the_edge_is(scenario_results: dict) -> None:
    status = scenario_results["arrow_on_the_left_edge"]["dialog"]["status"]
    assert status == "Borda esquerda: de (14%, 92%) a (14%, 12%)."


def test_an_arrow_does_not_scroll_the_page(scenario_results: dict) -> None:
    assert scenario_results["arrow_on_the_left_edge"]["default_prevented"] is True


def test_shift_with_an_arrow_pushes_by_a_coarse_step(scenario_results: dict) -> None:
    dialog = scenario_results["shift_arrow_on_the_left_edge"]
    assert (outline_points(dialog)[0], dialog["status"]) == (
        "8,11.5 91.4,11.5 91.4,91.5 8,91.5",
        "Borda esquerda: de (8%, 92%) a (8%, 12%).",
    )


def test_an_arrow_along_an_edge_does_not_move_it(scenario_results: dict) -> None:
    dialog = scenario_results["tangent_arrow_on_the_left_edge"]["dialog"]
    assert (outline_points(dialog)[0], dialog["disabled"]["apply"]) == (SECOND_PAGE_OUTLINE, True)


def test_arrows_on_a_corner_push_only_that_corner(scenario_results: dict) -> None:
    dialog = scenario_results["arrows_on_a_corner"]
    assert outline_points(dialog)[0] == "13,11.5 91.4,11.5 86.4,86.5 13,91.5"


def test_arrows_on_a_corner_say_where_the_corner_is(scenario_results: dict) -> None:
    assert scenario_results["arrows_on_a_corner"]["status"] == "Canto inferior direito em (86%, 87%)."


def test_arrows_on_the_move_button_move_the_whole_frame(scenario_results: dict) -> None:
    dialog = scenario_results["arrow_on_the_move_button"]
    assert (outline_points(dialog)[0], dialog["status"]) == (
        "8,11.5 86.4,11.5 86.4,91.5 8,91.5",
        "Moldura 1: esquerda 8%, topo 12%, direita 86%, base 92%.",
    )


def test_left_and_right_on_the_rotate_handle_turn_the_frame(scenario_results: dict) -> None:
    dialog = scenario_results["arrows_on_the_rotate_handle"]
    assert dialog["status"].startswith("Moldura 1: inclinada 5° para a direita.")


def test_up_and_down_on_the_rotate_handle_do_nothing(scenario_results: dict) -> None:
    dialog = scenario_results["vertical_arrow_on_the_rotate_handle"]
    assert (outline_points(dialog)[0], dialog["disabled"]["apply"]) == (SECOND_PAGE_OUTLINE, True)


def test_an_arrow_that_would_bend_the_frame_leaves_it_as_it_was(scenario_results: dict) -> None:
    dialog = scenario_results["arrow_that_would_bend_the_frame"]
    assert (outline_points(dialog)[0], dialog["status"]) == (
        "83,11.5 91.4,11.5 91.4,91.5 13,91.5",
        INVALID_MOVE_STATUS,
    )


def test_another_key_on_a_handle_changes_nothing(scenario_results: dict) -> None:
    result = scenario_results["other_key_on_a_handle"]
    assert (result["default_prevented"], outline_points(result["dialog"])[0]) == (False, SECOND_PAGE_OUTLINE)


def test_an_arrow_with_no_frame_is_left_to_the_browser(scenario_results: dict) -> None:
    assert scenario_results["arrow_on_a_page_without_a_frame"]["default_prevented"] is False


def test_adding_a_frame_to_a_page_without_one_puts_it_in_the_middle(scenario_results: dict) -> None:
    result = scenario_results["add_a_frame_to_a_page_without_a_frame"]
    assert (outline_points(result["dialog"])[0], result["dialog"]["status"]) == (
        "20,20 80,20 80,80 20,80",
        "Moldura 1 adicionada. Moldura 1: esquerda 20%, topo 20%, direita 80%, base 80%.",
    )


def test_a_frame_that_was_added_can_be_applied(scenario_results: dict) -> None:
    dialog = scenario_results["add_a_frame_to_a_page_without_a_frame"]["dialog"]
    assert dialog["disabled"]["apply"] is False


def test_adding_a_frame_gives_the_focus_to_its_move_button(scenario_results: dict) -> None:
    assert scenario_results["add_a_frame_to_a_page_without_a_frame"]["focused_move_button"] is True


def test_the_second_frame_goes_to_the_free_side_of_the_page(scenario_results: dict) -> None:
    dialog = scenario_results["add_a_second_frame_next_to_the_first"]["dialog"]
    assert outline_points(dialog) == ["5,30 45,30 45,70 5,70", SECOND_PAGE_OUTLINE]


def test_the_new_frame_becomes_the_selected_one(scenario_results: dict) -> None:
    dialog = scenario_results["add_a_second_frame_next_to_the_first"]["dialog"]
    assert [outline["is_active"] for outline in dialog["overlay"]["outlines"]] == [True, False]


def test_with_two_frames_the_add_button_is_disabled(scenario_results: dict) -> None:
    assert scenario_results["add_a_second_frame_next_to_the_first"]["dialog"]["disabled"]["add"] is True


def test_the_second_frame_goes_to_the_right_when_the_first_is_on_the_left(scenario_results: dict) -> None:
    dialog = scenario_results["add_a_second_frame_to_the_right_of_a_frame_on_the_left"]
    assert (outline_points(dialog)[1], dialog["status"]) == (
        "55,30 95,30 95,70 55,70",
        "Moldura 2 adicionada. Moldura 2: esquerda 55%, topo 30%, direita 95%, base 70%.",
    )


def test_removing_a_frame_leaves_the_other_selected(scenario_results: dict) -> None:
    result = scenario_results["remove_one_of_two_frames"]
    dialog = result["dialog"]
    assert (outline_points(dialog)[0], dialog["status"], result["focused_move_button"]) == (
        LOWER_OUTLINE,
        "Moldura 1 removida.",
        True,
    )


def test_removing_a_frame_hides_the_other_outline_and_the_select_button(scenario_results: dict) -> None:
    dialog = scenario_results["remove_one_of_two_frames"]["dialog"]
    assert (dialog["overlay"]["outlines"][1]["visible"], dialog["select"]["hidden"]) == (False, True)


def test_removing_the_only_frame_hides_the_frame_and_its_handles(scenario_results: dict) -> None:
    dialog = scenario_results["remove_the_only_frame"]["dialog"]
    assert (dialog["overlay"]["hidden"], dialog["corners"]["top_left"]["hidden"], dialog["move"]["hidden"]) == (
        True,
        True,
        True,
    )


def test_removing_the_only_frame_moves_the_focus_to_the_add_button(scenario_results: dict) -> None:
    result = scenario_results["remove_the_only_frame"]
    assert (result["focused_add_button"], result["dialog"]["status"]) == (True, "Moldura 1 removida.")


def test_with_no_frame_left_remove_and_turn_are_disabled(scenario_results: dict) -> None:
    disabled = scenario_results["remove_the_only_frame"]["dialog"]["disabled"]
    assert (disabled["remove"], disabled["turn"], disabled["apply"]) == (True, True, False)


def test_turning_the_frame_only_advances_the_roles_of_its_corners(scenario_results: dict) -> None:
    dialog = scenario_results["turn_the_frame_output"]
    assert (outline_points(dialog)[0], dialog["corners"]["top_left"]["top"]) == (
        "13,91.5 13,11.5 91.4,11.5 91.4,91.5",
        "91.5%",
    )


def test_turning_the_frame_says_the_top_side_of_the_photo_changed(scenario_results: dict) -> None:
    status = scenario_results["turn_the_frame_output"]["status"]
    assert status == "Moldura 1 girada: o lado de cima da foto mudou."


def test_a_frame_with_turned_roles_can_be_applied(scenario_results: dict) -> None:
    assert scenario_results["turn_the_frame_output"]["disabled"]["apply"] is False


def test_selecting_the_other_frame_gives_it_the_handles(scenario_results: dict) -> None:
    result = scenario_results["select_the_other_frame_with_the_pointer"]
    dialog = result["dialog"]
    assert (
        [outline["is_active"] for outline in dialog["overlay"]["outlines"]],
        dialog["corners"]["top_left"]["label"],
        result["focused_move_button"],
    ) == ([False, True], "Canto superior esquerdo da moldura 2", True)


def test_selecting_the_other_frame_says_which_one_it_is(scenario_results: dict) -> None:
    status = scenario_results["select_the_other_frame_with_the_pointer"]["dialog"]["status"]
    assert status == "Moldura 2 de 2 selecionada. Moldura 2: esquerda 5%, topo 60%, direita 90%, base 95%."


def test_after_selecting_the_other_frame_the_first_can_be_selected(scenario_results: dict) -> None:
    select = scenario_results["select_the_other_frame_with_the_pointer"]["dialog"]["select"]
    assert (select["label"], select["clip_path"]) == (
        "Selecionar moldura 1",
        "polygon(5% 2%, 90% 2%, 90% 55%, 5% 55%)",
    )


def test_the_select_button_works_with_the_keyboard(scenario_results: dict) -> None:
    dialog = scenario_results["select_the_other_frame_with_the_keyboard"]
    assert [outline["is_active"] for outline in dialog["overlay"]["outlines"]] == [False, True]


def test_selecting_twice_comes_back_to_the_first_frame(scenario_results: dict) -> None:
    dialog = scenario_results["select_the_other_frame_twice"]
    assert (outline_points(dialog), dialog["status"]) == (
        [UPPER_OUTLINE, LOWER_OUTLINE],
        "Moldura 1 de 2 selecionada. Moldura 1: esquerda 5%, topo 2%, direita 90%, base 55%.",
    )


def test_selecting_a_frame_changes_nothing_to_apply(scenario_results: dict) -> None:
    assert scenario_results["select_the_other_frame_twice"]["disabled"]["apply"] is True


def test_no_crop_removes_every_frame(scenario_results: dict) -> None:
    dialog = scenario_results["no_crop_button"]
    assert (dialog["overlay"]["hidden"], dialog["status"]) == (True, NO_CROP_STATUS)


def test_no_crop_on_a_page_with_a_frame_can_be_applied(scenario_results: dict) -> None:
    assert scenario_results["no_crop_button"]["disabled"]["apply"] is False


def test_no_crop_removes_both_frames(scenario_results: dict) -> None:
    dialog = scenario_results["no_crop_button_with_two_frames"]
    assert (dialog["overlay"]["hidden"], dialog["select"]["hidden"], dialog["disabled"]["apply"]) == (True, True, False)


def test_no_crop_on_a_page_without_a_frame_changes_nothing_to_apply(scenario_results: dict) -> None:
    assert scenario_results["no_crop_button_on_a_page_without_a_frame"]["disabled"]["apply"] is True

import json
from pathlib import Path

import pytest

from tests.web.policy_expression_runner import NODE_EXECUTABLE, evaluate_policy_expressions

VECTORS_FILE = Path(__file__).resolve().parents[1] / "fixtures" / "page-crop-rotation-vectors.json"
ROTATION_VECTORS = json.loads(VECTORS_FILE.read_text(encoding="utf-8"))["vectors"]
EDGE_NAMES = ("left", "top", "right", "bottom")
MIDDLE_FRAME = "{left: 0.2, top: 0.3, right: 0.6, bottom: 0.8}"
WHOLE_PAGE = {"left": 0, "top": 0, "right": 1, "bottom": 1}

pytestmark = pytest.mark.skipif(
    NODE_EXECUTABLE is None, reason="Node.js is not installed, so page-frame-geometry.js cannot be exercised"
)


def frame_expression(edges: list[float]) -> str:
    return "{" + ", ".join(f"{name}: {value}" for name, value in zip(EDGE_NAMES, edges, strict=True)) + "}"


def frame_result(edges: list[float]) -> dict:
    return dict(zip(EDGE_NAMES, edges, strict=True))


CLAMP_CASES = [
    pytest.param("clamp_fraction(-0.2)", 0, id="below-zero"),
    pytest.param("clamp_fraction(1.4)", 1, id="above-one"),
    pytest.param("clamp_fraction(0.37)", 0.37, id="inside-the-page"),
]

BUILD_CASES = [
    pytest.param(
        "build_frame({left: 0.123456, top: 0.2, right: 0.987654, bottom: 1})",
        {"left": 0.1235, "top": 0.2, "right": 0.9877, "bottom": 1},
        id="rounds-to-four-digits",
    ),
    pytest.param(
        "build_frame({left: 1 - 0.9, top: 0, right: 1, bottom: 1})",
        {"left": 0.1, "top": 0, "right": 1, "bottom": 1},
        id="floating-point-noise-disappears",
    ),
]

WHOLE_PAGE_CASES = [
    pytest.param("is_whole_page_frame({left: 0, top: 0, right: 1, bottom: 1})", True, id="whole-page"),
    pytest.param("is_whole_page_frame({left: 0.0004, top: 0, right: 0.9996, bottom: 1})", True, id="within-tolerance"),
    pytest.param("is_whole_page_frame({left: 0.001, top: 0, right: 1, bottom: 1})", False, id="smaller-by-a-tenth"),
    pytest.param("is_whole_page_frame({left: 0, top: 0, right: 1, bottom: 0.9})", False, id="shorter"),
    pytest.param("WHOLE_PAGE_FRAME", WHOLE_PAGE, id="constant"),
]

EQUALITY_CASES = [
    pytest.param(f"frames_are_equal({MIDDLE_FRAME}, {MIDDLE_FRAME})", True, id="same-frame"),
    pytest.param(
        f"frames_are_equal({MIDDLE_FRAME}, {{left: 0.2004, top: 0.3, right: 0.6, bottom: 0.8}})",
        True,
        id="within-tolerance",
    ),
    pytest.param(
        f"frames_are_equal({MIDDLE_FRAME}, {{left: 0.2, top: 0.3, right: 0.6, bottom: 0.801}})",
        False,
        id="one-edge-moved",
    ),
]

MOVE_CASES = [
    pytest.param(
        f"move_frame({MIDDLE_FRAME}, {{delta_x: 0.1, delta_y: -0.1}})",
        {"left": 0.3, "top": 0.2, "right": 0.7, "bottom": 0.7},
        id="shifts-both-axes",
    ),
    pytest.param(
        f"move_frame({MIDDLE_FRAME}, {{delta_x: 0.1, delta_y: 0.05}})",
        {"left": 0.3, "top": 0.35, "right": 0.7, "bottom": 0.85},
        id="keeps-the-size",
    ),
    pytest.param(
        f"move_frame({MIDDLE_FRAME}, {{delta_x: -0.5, delta_y: 0}})",
        {"left": 0, "top": 0.3, "right": 0.4, "bottom": 0.8},
        id="stops-at-the-left-of-the-page",
    ),
    pytest.param(
        f"move_frame({MIDDLE_FRAME}, {{delta_x: 0.9, delta_y: 0.9}})",
        {"left": 0.6, "top": 0.5, "right": 1, "bottom": 1},
        id="stops-at-the-bottom-right-of-the-page",
    ),
    pytest.param(
        f"move_frame({MIDDLE_FRAME}, {{delta_x: 0, delta_y: -0.9}})",
        {"left": 0.2, "top": 0, "right": 0.6, "bottom": 0.5},
        id="stops-at-the-top-of-the-page",
    ),
    pytest.param(
        f"move_frame({MIDDLE_FRAME}, {{delta_x: 0, delta_y: 0}})", frame_result([0.2, 0.3, 0.6, 0.8]), id="no-shift"
    ),
    pytest.param(
        f"nudge_whole_frame({MIDDLE_FRAME}, {{direction: 'right', step: 0.05}})",
        {"left": 0.25, "top": 0.3, "right": 0.65, "bottom": 0.8},
        id="arrow-moves-the-whole-frame-sideways",
    ),
    pytest.param(
        f"nudge_whole_frame({MIDDLE_FRAME}, {{direction: 'up', step: 0.005}})",
        {"left": 0.2, "top": 0.295, "right": 0.6, "bottom": 0.795},
        id="arrow-moves-the-whole-frame-up",
    ),
]

RESIZE_CASES = [
    pytest.param("west", 0.1, 0.1, [0.3, 0.3, 0.6, 0.8], id="west-moves-only-the-left-edge"),
    pytest.param("east", 0.1, 0.1, [0.2, 0.3, 0.7, 0.8], id="east-moves-only-the-right-edge"),
    pytest.param("north", 0.1, 0.1, [0.2, 0.4, 0.6, 0.8], id="north-moves-only-the-top-edge"),
    pytest.param("south", 0.1, 0.1, [0.2, 0.3, 0.6, 0.9], id="south-moves-only-the-bottom-edge"),
    pytest.param("north_west", 0.1, 0.1, [0.3, 0.4, 0.6, 0.8], id="north-west-moves-left-and-top"),
    pytest.param("north_east", 0.1, 0.1, [0.2, 0.4, 0.7, 0.8], id="north-east-moves-right-and-top"),
    pytest.param("south_west", 0.1, 0.1, [0.3, 0.3, 0.6, 0.9], id="south-west-moves-left-and-bottom"),
    pytest.param("south_east", 0.1, 0.1, [0.2, 0.3, 0.7, 0.9], id="south-east-moves-right-and-bottom"),
    pytest.param("west", -0.5, 0, [0, 0.3, 0.6, 0.8], id="left-edge-stops-at-the-page"),
    pytest.param("east", 0.9, 0, [0.2, 0.3, 1, 0.8], id="right-edge-stops-at-the-page"),
    pytest.param("north", 0, -0.9, [0.2, 0, 0.6, 0.8], id="top-edge-stops-at-the-page"),
    pytest.param("south", 0, 0.9, [0.2, 0.3, 0.6, 1], id="bottom-edge-stops-at-the-page"),
    pytest.param("west", 0.9, 0, [0.58, 0.3, 0.6, 0.8], id="left-edge-keeps-the-minimum-width"),
    pytest.param("east", -0.9, 0, [0.2, 0.3, 0.22, 0.8], id="right-edge-keeps-the-minimum-width"),
    pytest.param("north", 0, 0.9, [0.2, 0.78, 0.6, 0.8], id="top-edge-keeps-the-minimum-height"),
    pytest.param("south", 0, -0.9, [0.2, 0.3, 0.6, 0.32], id="bottom-edge-keeps-the-minimum-height"),
]

NUDGE_CASES = [
    pytest.param("west", "left", 0.005, [0.195, 0.3, 0.6, 0.8], id="left-edge-left"),
    pytest.param("west", "right", 0.005, [0.205, 0.3, 0.6, 0.8], id="left-edge-right"),
    pytest.param("east", "right", 0.05, [0.2, 0.3, 0.65, 0.8], id="right-edge-right-with-a-coarse-step"),
    pytest.param("north", "up", 0.005, [0.2, 0.295, 0.6, 0.8], id="top-edge-up"),
    pytest.param("south", "down", 0.005, [0.2, 0.3, 0.6, 0.805], id="bottom-edge-down"),
    pytest.param("west", "up", 0.05, [0.2, 0.3, 0.6, 0.8], id="vertical-key-on-a-vertical-edge-does-nothing"),
    pytest.param("north", "left", 0.05, [0.2, 0.3, 0.6, 0.8], id="horizontal-key-on-a-horizontal-edge-does-nothing"),
    pytest.param("north_west", "right", 0.05, [0.25, 0.3, 0.6, 0.8], id="corner-follows-the-horizontal-key"),
    pytest.param("north_west", "down", 0.05, [0.2, 0.35, 0.6, 0.8], id="corner-follows-the-vertical-key"),
    pytest.param("south_east", "left", 0.005, [0.2, 0.3, 0.595, 0.8], id="south-east-corner-left"),
]

TURN_CASES = [
    pytest.param(
        f"turn_frame_clockwise({frame_expression(vector['crop'])})",
        frame_result(vector["turned_clockwise"]),
        id=f"shared-vector-{index}",
    )
    for index, vector in enumerate(ROTATION_VECTORS)
]

QUARTER_TURN_CASES = [
    pytest.param(
        f"turn_frame_by_quarter_turns({frame_expression([0.1, 0.2, 0.5, 0.9])}, 4)",
        frame_result([0.1, 0.2, 0.5, 0.9]),
        id="four-turns-come-back",
    ),
    pytest.param(
        f"turn_frame_by_quarter_turns({frame_expression([0.1, 0.2, 0.5, 0.9])}, 0)",
        frame_result([0.1, 0.2, 0.5, 0.9]),
        id="no-turns-change-nothing",
    ),
    pytest.param(
        f"turn_frame_by_quarter_turns({frame_expression([0.1, 0.2, 0.5, 0.9])}, 2)",
        frame_result([0.5, 0.1, 0.9, 0.8]),
        id="two-turns-turn-it-upside-down",
    ),
    pytest.param("count_quarter_turns(0, 90)", 1, id="one-turn"),
    pytest.param("count_quarter_turns(270, 0)", 1, id="turn-past-a-full-circle"),
    pytest.param("count_quarter_turns(90, 0)", 3, id="three-turns-for-a-turn-back"),
    pytest.param("count_quarter_turns(180, 180)", 0, id="same-rotation"),
]

POINTER_CASES = [
    pytest.param(
        "convert_pointer_shift({horizontal_pixels: 50, vertical_pixels: -100}, {width: 500, height: 400})",
        {"delta_x": 0.1, "delta_y": -0.25},
        id="pixels-over-the-box-size",
    ),
    pytest.param(
        "convert_pointer_shift({horizontal_pixels: 50, vertical_pixels: 50}, {width: 0, height: 0})",
        {"delta_x": 0, "delta_y": 0},
        id="a-box-without-size-gives-no-shift",
    ),
]

STEP_CASES = [
    pytest.param("read_nudge_step({shiftKey: true})", 0.05, id="shift-takes-the-coarse-step"),
    pytest.param("read_nudge_step({shiftKey: false})", 0.005, id="no-shift-takes-the-fine-step"),
    pytest.param("read_nudge_direction('ArrowLeft')", "left", id="arrow-left"),
    pytest.param("read_nudge_direction('ArrowRight')", "right", id="arrow-right"),
    pytest.param("read_nudge_direction('ArrowUp')", "up", id="arrow-up"),
    pytest.param("read_nudge_direction('ArrowDown')", "down", id="arrow-down"),
    pytest.param("read_nudge_direction('KeyA')", None, id="another-key"),
]

STYLE_CASES = [
    pytest.param(
        "describe_frame_style({left: 0.13, top: 0.115, right: 0.924, bottom: 0.925})",
        {"left_percent": 13, "top_percent": 11.5, "width_percent": 79.4, "height_percent": 81},
        id="percentages-of-the-page",
    ),
    pytest.param(
        "describe_frame_style({left: 0, top: 0, right: 1, bottom: 1})",
        {"left_percent": 0, "top_percent": 0, "width_percent": 100, "height_percent": 100},
        id="whole-page",
    ),
]

DESCRIPTION_CASES = [
    pytest.param(
        "describe_frame({left: 0.13, top: 0.115, right: 0.914, bottom: 0.915})",
        "Moldura: esquerda 13%, topo 12%, direita 91%, base 92%.",
        id="frame",
    ),
    pytest.param(
        "describe_frame({left: 0, top: 0, right: 1, bottom: 1})",
        "Sem corte: a página inteira será usada.",
        id="no-crop",
    ),
    pytest.param(
        "describe_handle_position({left: 0.13, top: 0.12, right: 0.91, bottom: 0.91}, 'west')",
        "Borda esquerda em 13%.",
        id="left-edge",
    ),
    pytest.param(
        "describe_handle_position({left: 0.13, top: 0.12, right: 0.91, bottom: 0.91}, 'east')",
        "Borda direita em 91%.",
        id="right-edge",
    ),
    pytest.param(
        "describe_handle_position({left: 0.13, top: 0.12, right: 0.91, bottom: 0.91}, 'north')",
        "Borda de cima em 12%.",
        id="top-edge",
    ),
    pytest.param(
        "describe_handle_position({left: 0.13, top: 0.12, right: 0.91, bottom: 0.91}, 'south')",
        "Borda de baixo em 91%.",
        id="bottom-edge",
    ),
    pytest.param(
        "describe_handle_position({left: 0.13, top: 0.12, right: 0.91, bottom: 0.92}, 'north_west')",
        "Canto superior esquerdo: esquerda 13%, topo 12%.",
        id="north-west-corner",
    ),
    pytest.param(
        "describe_handle_position({left: 0.13, top: 0.12, right: 0.91, bottom: 0.92}, 'south_east')",
        "Canto inferior direito: direita 91%, base 92%.",
        id="south-east-corner",
    ),
    pytest.param(
        "describe_handle_position({left: 0.13, top: 0.12, right: 0.91, bottom: 0.92}, 'north_east')",
        "Canto superior direito: direita 91%, topo 12%.",
        id="north-east-corner",
    ),
    pytest.param(
        "describe_handle_position({left: 0.13, top: 0.12, right: 0.91, bottom: 0.92}, 'south_west')",
        "Canto inferior esquerdo: esquerda 13%, base 92%.",
        id="south-west-corner",
    ),
]

CROP_CASES = [
    pytest.param("read_frame_from_crop(null)", WHOLE_PAGE, id="no-crop-is-the-whole-page"),
    pytest.param(
        "read_frame_from_crop({left: 0.123456, top: 0.1, right: 0.9, bottom: 0.95})",
        {"left": 0.1235, "top": 0.1, "right": 0.9, "bottom": 0.95},
        id="crop-becomes-a-rounded-frame",
    ),
    pytest.param(
        "build_crop_request_body({left: 0, top: 0, right: 1, bottom: 1})",
        {"crop": None},
        id="whole-page-removes-the-crop",
    ),
    pytest.param(
        "build_crop_request_body({left: 0.1, top: 0.2, right: 0.8, bottom: 0.9})",
        {"crop": {"left": 0.1, "top": 0.2, "right": 0.8, "bottom": 0.9}},
        id="frame-becomes-a-crop",
    ),
]

HANDLE_CASES = [
    pytest.param("read_handle_label('west')", "Borda esquerda", id="west"),
    pytest.param("read_handle_label('east')", "Borda direita", id="east"),
    pytest.param("read_handle_label('north')", "Borda de cima", id="north"),
    pytest.param("read_handle_label('south')", "Borda de baixo", id="south"),
    pytest.param("read_handle_label('north_west')", "Canto superior esquerdo", id="north-west"),
    pytest.param("read_handle_label('north_east')", "Canto superior direito", id="north-east"),
    pytest.param("read_handle_label('south_west')", "Canto inferior esquerdo", id="south-west"),
    pytest.param("read_handle_label('south_east')", "Canto inferior direito", id="south-east"),
    pytest.param("Object.values(FRAME_HANDLES).length", 8, id="eight-handles"),
]


def resize_expression(handle: str, delta_x: float, delta_y: float) -> str:
    return f"resize_frame({MIDDLE_FRAME}, {{handle: '{handle}', delta_x: {delta_x}, delta_y: {delta_y}}})"


def nudge_expression(handle: str, direction: str, step: float) -> str:
    return f"nudge_handle({MIDDLE_FRAME}, {{handle: '{handle}', direction: '{direction}', step: {step}}})"


RESIZE_EXPRESSIONS = [resize_expression(*case.values[:3]) for case in RESIZE_CASES]
NUDGE_EXPRESSIONS = [nudge_expression(*case.values[:3]) for case in NUDGE_CASES]

SIMPLE_CASES = (
    CLAMP_CASES
    + BUILD_CASES
    + WHOLE_PAGE_CASES
    + EQUALITY_CASES
    + MOVE_CASES
    + TURN_CASES
    + QUARTER_TURN_CASES
    + POINTER_CASES
    + STEP_CASES
    + STYLE_CASES
    + DESCRIPTION_CASES
    + CROP_CASES
    + HANDLE_CASES
)


@pytest.fixture(scope="module")
def geometry_results() -> dict:
    expressions = [case.values[0] for case in SIMPLE_CASES] + RESIZE_EXPRESSIONS + NUDGE_EXPRESSIONS
    return evaluate_policy_expressions(expressions)


@pytest.mark.parametrize(("expression", "expected"), CLAMP_CASES)
def test_a_fraction_is_limited_to_the_page(geometry_results: dict, expression: str, expected: object) -> None:
    assert geometry_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), BUILD_CASES)
def test_a_built_frame_is_rounded(geometry_results: dict, expression: str, expected: object) -> None:
    assert geometry_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), WHOLE_PAGE_CASES)
def test_the_whole_page_frame_is_recognized(geometry_results: dict, expression: str, expected: object) -> None:
    assert geometry_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), EQUALITY_CASES)
def test_frames_are_compared_with_a_tolerance(geometry_results: dict, expression: str, expected: object) -> None:
    assert geometry_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), MOVE_CASES)
def test_moving_a_frame(geometry_results: dict, expression: str, expected: object) -> None:
    assert geometry_results[expression] == expected


@pytest.mark.parametrize(("handle", "delta_x", "delta_y", "expected_edges"), [case.values for case in RESIZE_CASES])
def test_resizing_a_frame_by_a_handle(
    geometry_results: dict, handle: str, delta_x: float, delta_y: float, expected_edges: list[float]
) -> None:
    assert geometry_results[resize_expression(handle, delta_x, delta_y)] == frame_result(expected_edges)


@pytest.mark.parametrize(("handle", "direction", "step", "expected_edges"), [case.values for case in NUDGE_CASES])
def test_nudging_a_handle_with_an_arrow(
    geometry_results: dict, handle: str, direction: str, step: float, expected_edges: list[float]
) -> None:
    assert geometry_results[nudge_expression(handle, direction, step)] == frame_result(expected_edges)


@pytest.mark.parametrize(("expression", "expected"), TURN_CASES)
def test_turning_a_frame_matches_the_vectors_shared_with_the_server(
    geometry_results: dict, expression: str, expected: object
) -> None:
    assert geometry_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), QUARTER_TURN_CASES)
def test_turning_a_frame_by_quarter_turns(geometry_results: dict, expression: str, expected: object) -> None:
    assert geometry_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), POINTER_CASES)
def test_a_pointer_shift_becomes_a_fraction_of_the_box(
    geometry_results: dict, expression: str, expected: object
) -> None:
    assert geometry_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), STEP_CASES)
def test_arrow_keys_choose_a_direction_and_a_step(geometry_results: dict, expression: str, expected: object) -> None:
    assert geometry_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), STYLE_CASES)
def test_a_frame_is_drawn_in_percentages_of_the_page(geometry_results: dict, expression: str, expected: object) -> None:
    assert geometry_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), DESCRIPTION_CASES)
def test_a_frame_is_described_in_portuguese(geometry_results: dict, expression: str, expected: object) -> None:
    assert geometry_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), CROP_CASES)
def test_a_frame_goes_to_and_comes_from_the_crop_of_the_server(
    geometry_results: dict, expression: str, expected: object
) -> None:
    assert geometry_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), HANDLE_CASES)
def test_handles_have_names_in_portuguese(geometry_results: dict, expression: str, expected: object) -> None:
    assert geometry_results[expression] == expected

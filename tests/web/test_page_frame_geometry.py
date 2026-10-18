import json
from pathlib import Path

import pytest

from tests.web.policy_expression_runner import NODE_EXECUTABLE, evaluate_policy_expressions

VECTORS_FILE = Path(__file__).resolve().parents[1] / "fixtures" / "page-crop-vectors.json"
SHARED_VECTORS = json.loads(VECTORS_FILE.read_text(encoding="utf-8"))
TURN_VECTORS = SHARED_VECTORS["vectors"]
VALIDITY_VECTORS = SHARED_VECTORS["validity"]
POINT_TOLERANCE = 1e-6
SQUARE_SURFACE = "{width: 400, height: 400}"
WIDE_SURFACE = "{width: 800, height: 400}"
MIDDLE = [[0.2, 0.3], [0.6, 0.3], [0.6, 0.8], [0.2, 0.8]]
TILTED = [[0.4, 0.55], [0.93, 0.44], [0.97, 0.8], [0.44, 0.91]]

pytestmark = pytest.mark.skipif(
    NODE_EXECUTABLE is None, reason="Node.js is not installed, so page-frame-geometry.js cannot be exercised"
)


def frame(points: list[list[float]]) -> str:
    return f"frame_from_points({json.dumps(points)})"


def points_of(expression: str) -> str:
    return f"points_of({expression})"


def move_corner(corner: str, delta_x: float, delta_y: float, points: list[list[float]] = MIDDLE) -> str:
    return points_of(f"move_corner({frame(points)}, {{corner: '{corner}', delta_x: {delta_x}, delta_y: {delta_y}}})")


def move_edge(edge: str, delta_x: float, delta_y: float, points: list[list[float]] = MIDDLE) -> str:
    move = f"{{edge: '{edge}', delta_x: {delta_x}, delta_y: {delta_y}, surface: {SQUARE_SURFACE}}}"
    return points_of(f"move_edge({frame(points)}, {move})")


def rotate(degrees: float, points: list[list[float]] = MIDDLE, surface: str = SQUARE_SURFACE) -> str:
    return points_of(f"rotate_frame({frame(points)}, {{degrees: {degrees}, surface: {surface}}})")


def nudge_edge(edge: str, direction: str, points: list[list[float]] = MIDDLE) -> str:
    nudge = f"{{edge: '{edge}', direction: '{direction}', step: 0.05, surface: {SQUARE_SURFACE}}}"
    return points_of(f"nudge_edge({frame(points)}, {nudge})")


def describe(points: list[list[float]], surface: str = SQUARE_SURFACE) -> str:
    return f"describe_frame({frame(points)}, {{label: 'Moldura 1', surface: {surface}}})"


TURN_EXPRESSIONS = {
    vector["name"]: (
        points_of(f"turn_frame_clockwise({frame(vector['quad'])})"),
        points_of(f"turn_frame_output_clockwise({frame(vector['quad'])})"),
        points_of(f"turn_frames_by_quarter_turns([{frame(vector['quad'])}], 4)[0]"),
    )
    for vector in TURN_VECTORS
}
VALIDITY_EXPRESSIONS = {vector["name"]: f"validate_frame({frame(vector['quad'])})" for vector in VALIDITY_VECTORS}

MOVE_FRAME_CASES = [
    pytest.param(
        points_of(f"move_frame({frame(MIDDLE)}, {{delta_x: 0.1, delta_y: -0.1}})"),
        [[0.3, 0.2], [0.7, 0.2], [0.7, 0.7], [0.3, 0.7]],
        id="shifts-every-corner",
    ),
    pytest.param(
        points_of(f"move_frame({frame(MIDDLE)}, {{delta_x: -0.5, delta_y: 0}})"),
        [[0, 0.3], [0.4, 0.3], [0.4, 0.8], [0, 0.8]],
        id="stops-at-the-left-of-the-page",
    ),
    pytest.param(
        points_of(f"move_frame({frame(MIDDLE)}, {{delta_x: 0.9, delta_y: 0.9}})"),
        [[0.6, 0.5], [1, 0.5], [1, 1], [0.6, 1]],
        id="stops-at-the-bottom-right-of-the-page",
    ),
    pytest.param(
        points_of(f"move_frame({frame(TILTED)}, {{delta_x: 0, delta_y: -0.9}})"),
        [[0.4, 0.11], [0.93, 0], [0.97, 0.36], [0.44, 0.47]],
        id="a-tilted-frame-stops-at-its-highest-corner",
    ),
]
MOVE_CORNER_CASES = [
    pytest.param(
        move_corner("top_left", 0.1, 0.05),
        [[0.3, 0.35], [0.6, 0.3], [0.6, 0.8], [0.2, 0.8]],
        id="a-corner-moves-alone",
    ),
    pytest.param(
        move_corner("bottom_right", 0.9, 0.9),
        [[0.2, 0.3], [0.6, 0.3], [1, 1], [0.2, 0.8]],
        id="a-corner-stops-at-the-page",
    ),
    pytest.param(
        move_corner("top_left", 0.5, 0.0),
        None,
        id="a-corner-past-its-neighbour-is-refused",
    ),
    pytest.param(
        move_corner("top_left", 0.0, 0.49),
        None,
        id="a-corner-that-would-flatten-the-frame-is-refused",
    ),
    pytest.param(
        move_corner("top_left", 0.0, 0.0),
        MIDDLE,
        id="no-shift-keeps-the-frame",
    ),
]
MOVE_EDGE_CASES = [
    pytest.param(
        move_edge("top", 0.3, -0.1),
        [[0.2, 0.2], [0.6, 0.2], [0.6, 0.8], [0.2, 0.8]],
        id="the-top-edge-follows-only-the-vertical-part",
    ),
    pytest.param(
        move_edge("left", -0.1, 0.4),
        [[0.1, 0.3], [0.6, 0.3], [0.6, 0.8], [0.1, 0.8]],
        id="the-left-edge-follows-only-the-horizontal-part",
    ),
    pytest.param(
        move_edge("bottom", 0, 0.9),
        [[0.2, 0.3], [0.6, 0.3], [0.6, 1], [0.2, 1]],
        id="an-edge-stops-at-the-page",
    ),
    pytest.param(
        move_edge("right", -0.9, 0),
        None,
        id="an-edge-past-the-opposite-one-is-refused",
    ),
    pytest.param(
        points_of(f"move_edge({frame(MIDDLE)}, {{edge: 'top', delta_x: 0, delta_y: 0.1, surface: {WIDE_SURFACE}}})"),
        [[0.2, 0.4], [0.6, 0.4], [0.6, 0.8], [0.2, 0.8]],
        id="a-wide-page-gives-the-same-fraction-for-the-same-fraction",
    ),
]
ROTATE_CASES = [
    pytest.param(
        rotate(90, [[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6]]),
        [[0.6, 0.4], [0.6, 0.6], [0.4, 0.6], [0.4, 0.4]],
        id="a-square-turned-a-quarter-lands-on-itself-with-moved-corners",
    ),
    pytest.param(
        rotate(0),
        MIDDLE,
        id="no-turn-keeps-the-frame",
    ),
    pytest.param(
        rotate(90, [[0.4, 0.4], [0.7, 0.4], [0.7, 0.6], [0.4, 0.6]]),
        [[0.65, 0.35], [0.65, 0.65], [0.45, 0.65], [0.45, 0.35]],
        id="a-rectangle-turned-a-quarter-swaps-its-sides-around-the-centre",
    ),
    pytest.param(
        rotate(45, [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]),
        [[0.5, 0.0], [1.0, 0.5], [0.5, 1.0], [0.0, 0.5]],
        id="a-frame-that-no-longer-fits-shrinks-until-it-does",
    ),
]
READING_ORDER_CASES = [
    pytest.param(
        "[[[0.05, 0.02], [0.9, 0.02], [0.9, 0.55], [0.05, 0.55]],"
        " [[0.05, 0.6], [0.9, 0.6], [0.9, 0.95], [0.05, 0.95]]]",
        [0, 1],
        id="top-to-bottom-when-they-do-not-share-a-row",
    ),
    pytest.param(
        "[[[0.05, 0.6], [0.9, 0.6], [0.9, 0.95], [0.05, 0.95]],"
        " [[0.05, 0.02], [0.9, 0.02], [0.9, 0.55], [0.05, 0.55]]]",
        [1, 0],
        id="the-higher-one-comes-first",
    ),
    pytest.param(
        "[[[0.55, 0.1], [0.95, 0.1], [0.95, 0.9], [0.55, 0.9]], [[0.05, 0.1], [0.45, 0.1], [0.45, 0.9], [0.05, 0.9]]]",
        [1, 0],
        id="left-to-right-when-they-share-a-row",
    ),
]


def frame_pair(points_text: str) -> str:
    return f"{points_text}.map((points) => frame_from_points(points))"


RECTANGLE_CASES = [
    pytest.param(f"is_rectangle_frame({frame(MIDDLE)})", True, id="axis-rectangle"),
    pytest.param(f"is_rectangle_frame({frame(TILTED)})", False, id="tilted-photo"),
    pytest.param(
        f"is_rectangle_frame({frame([[0.2, 0.8], [0.2, 0.3], [0.6, 0.3], [0.6, 0.8]])})",
        True,
        id="a-rectangle-with-turned-roles",
    ),
    pytest.param("is_whole_page_frame(WHOLE_PAGE_FRAME)", True, id="whole-page"),
    pytest.param(f"is_whole_page_frame({frame(MIDDLE)})", False, id="not-the-whole-page"),
    pytest.param(
        f"frames_are_equal({frame(MIDDLE)}, {frame([[0.2004, 0.3], [0.6, 0.3], [0.6, 0.8], [0.2, 0.8]])})",
        True,
        id="equal-within-the-tolerance",
    ),
    pytest.param(
        f"frames_are_equal({frame(MIDDLE)}, {frame([[0.201, 0.3], [0.6, 0.3], [0.6, 0.8], [0.2, 0.8]])})",
        False,
        id="different-beyond-the-tolerance",
    ),
    pytest.param(
        f"frame_lists_are_equal([{frame(MIDDLE)}], [{frame(MIDDLE)}, {frame(TILTED)}])",
        False,
        id="lists-of-different-lengths-differ",
    ),
    pytest.param("frame_lists_are_equal([], [])", True, id="two-empty-lists-are-equal"),
]
CROP_CASES = [
    pytest.param("read_frames_from_crops(null)", [], id="no-crops-is-no-frames"),
    pytest.param("read_frames_from_crops([]).length", 0, id="an-empty-list-is-no-frames"),
    pytest.param(
        points_of(
            "read_frames_from_crops([{top_left: {x: 0.1234567, y: 0.2}, top_right: {x: 0.5, y: 0.2},"
            " bottom_right: {x: 0.5, y: 0.9}, bottom_left: {x: 0.1, y: 0.9}}])[0]"
        ),
        [[0.123457, 0.2], [0.5, 0.2], [0.5, 0.9], [0.1, 0.9]],
        id="a-crop-becomes-a-rounded-frame",
    ),
    pytest.param(
        f"read_frames_from_crops([{frame(MIDDLE)}, {frame(TILTED)}, {frame(MIDDLE)}]).length",
        2,
        id="at-most-two-frames-are-read",
    ),
    pytest.param(
        f"build_crops_request_body([WHOLE_PAGE_FRAME, {frame(MIDDLE)}]).crops.length",
        1,
        id="a-whole-page-frame-is-not-sent",
    ),
    pytest.param("build_crops_request_body([])", {"crops": []}, id="no-frames-removes-the-crops"),
    pytest.param(
        f"build_crops_request_body([{frame(MIDDLE)}]).crops[0].top_left",
        {"x": 0.2, "y": 0.3},
        id="a-frame-becomes-a-crop",
    ),
]
SUGGESTION_CASES = [
    pytest.param(
        points_of("suggest_new_frame([])"), [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]], id="first-frame"
    ),
    pytest.param(
        points_of(f"suggest_new_frame([{frame([[0.05, 0.1], [0.45, 0.1], [0.45, 0.9], [0.05, 0.9]])}])"),
        [[0.55, 0.3], [0.95, 0.3], [0.95, 0.7], [0.55, 0.7]],
        id="second-frame-on-the-free-right-half",
    ),
    pytest.param(
        points_of(f"suggest_new_frame([{frame([[0.55, 0.1], [0.95, 0.1], [0.95, 0.9], [0.55, 0.9]])}])"),
        [[0.05, 0.3], [0.45, 0.3], [0.45, 0.7], [0.05, 0.7]],
        id="second-frame-on-the-free-left-half",
    ),
    pytest.param(f"suggest_new_frame([{frame(MIDDLE)}, {frame(TILTED)}])", None, id="no-third-frame"),
]
NUDGE_CASES = [
    pytest.param(
        points_of(f"nudge_whole_frame({frame(MIDDLE)}, {{direction: 'right', step: 0.05}})"),
        [[0.25, 0.3], [0.65, 0.3], [0.65, 0.8], [0.25, 0.8]],
        id="an-arrow-moves-the-whole-frame",
    ),
    pytest.param(
        points_of(f"nudge_corner({frame(MIDDLE)}, {{corner: 'top_left', direction: 'down', step: 0.05}})"),
        [[0.2, 0.35], [0.6, 0.3], [0.6, 0.8], [0.2, 0.8]],
        id="an-arrow-moves-a-corner-on-its-axis",
    ),
    pytest.param(nudge_edge("top", "up"), [[0.2, 0.25], [0.6, 0.25], [0.6, 0.8], [0.2, 0.8]], id="up-on-the-top-edge"),
    pytest.param(nudge_edge("top", "left"), MIDDLE, id="left-on-the-top-edge-does-nothing"),
    pytest.param(nudge_edge("left", "up"), MIDDLE, id="up-on-the-left-edge-does-nothing"),
    pytest.param(
        nudge_edge("left", "right"), [[0.25, 0.3], [0.6, 0.3], [0.6, 0.8], [0.25, 0.8]], id="right-on-the-left-edge"
    ),
    pytest.param(
        nudge_edge("top", "up", [[0.3, 0.4], [0.7, 0.38], [0.7, 0.8], [0.3, 0.8]]),
        [[0.297506, 0.350125], [0.697506, 0.330125], [0.7, 0.8], [0.3, 0.8]],
        id="a-slightly-tilted-top-edge-still-moves-with-up",
    ),
    pytest.param(
        nudge_edge("top", "left", [[0.3, 0.4], [0.7, 0.38], [0.7, 0.8], [0.3, 0.8]]),
        [[0.3, 0.4], [0.7, 0.38], [0.7, 0.8], [0.3, 0.8]],
        id="a-slightly-tilted-top-edge-ignores-left",
    ),
    pytest.param(
        points_of(f"nudge_rotation({frame(MIDDLE)}, {{direction: 'up', degrees: 5, surface: {SQUARE_SURFACE}}})"),
        MIDDLE,
        id="up-on-the-rotate-handle-does-nothing",
    ),
]
KEY_CASES = [
    pytest.param("read_nudge_step({shiftKey: true})", 0.05, id="shift-takes-the-coarse-step"),
    pytest.param("read_nudge_step({shiftKey: false})", 0.005, id="no-shift-takes-the-fine-step"),
    pytest.param("read_rotation_nudge_degrees({shiftKey: true})", 5, id="shift-turns-five-degrees"),
    pytest.param("read_rotation_nudge_degrees({shiftKey: false})", 0.5, id="no-shift-turns-half-a-degree"),
    pytest.param("read_nudge_direction('ArrowLeft')", "left", id="arrow-left"),
    pytest.param("read_nudge_direction('ArrowRight')", "right", id="arrow-right"),
    pytest.param("read_nudge_direction('ArrowUp')", "up", id="arrow-up"),
    pytest.param("read_nudge_direction('ArrowDown')", "down", id="arrow-down"),
    pytest.param("read_nudge_direction('KeyA')", None, id="another-key"),
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
    pytest.param(
        "measure_pointer_turn({centre: {x: 0, y: 0}, start_point: {x: 10, y: 0}, current_point: {x: 0, y: 10}})",
        90,
        id="a-pointer-moving-down-from-the-right-turns-clockwise",
    ),
    pytest.param(
        "measure_pointer_turn({centre: {x: 0, y: 0}, start_point: {x: 10, y: 0}, current_point: {x: 0, y: -10}})",
        -90,
        id="a-pointer-moving-up-from-the-right-turns-counterclockwise",
    ),
    pytest.param(
        "measure_pointer_turn({centre: {x: 0, y: 0}, start_point: {x: -10, y: 1}, current_point: {x: -10, y: -1}}) > 0",
        True,
        id="the-turn-goes-the-short-way-across-the-half-turn",
    ),
]
COUNT_CASES = [
    pytest.param("count_quarter_turns(0, 90)", 1, id="one-turn"),
    pytest.param("count_quarter_turns(270, 0)", 1, id="turn-past-a-full-circle"),
    pytest.param("count_quarter_turns(90, 0)", 3, id="three-turns-for-a-turn-back"),
    pytest.param("count_quarter_turns(180, 180)", 0, id="same-rotation"),
]
DRAWING_CASES = [
    pytest.param(
        f"describe_frame_outline({frame([[0.486, 0.119], [0.983, 0.347], [0.542, 0.904], [0.045, 0.676]])})",
        "48.6,11.9 98.3,34.7 54.2,90.4 4.5,67.6",
        id="outline-in-percent",
    ),
    pytest.param(
        f"describe_shade_path([{frame(MIDDLE)}])",
        "M0 0H100V100H0ZM20 30L60 30L60 80L20 80Z",
        id="shade-is-the-page-minus-the-frame",
    ),
    pytest.param("describe_shade_path([])", "M0 0H100V100H0Z", id="no-frame-shades-the-whole-page"),
    pytest.param(
        f"describe_clip_path({frame(MIDDLE)})",
        "polygon(20% 30%, 60% 30%, 60% 80%, 20% 80%)",
        id="clip-path-of-the-frame",
    ),
    pytest.param(
        "describe_handle_style({x: 0.4567, y: 0.1})",
        {"left_percent": 45.67, "top_percent": 10},
        id="handle-in-percent",
    ),
    pytest.param(
        points_of("copy_frame(WHOLE_PAGE_FRAME)"),
        [[0, 0], [1, 0], [1, 1], [0, 1]],
        id="a-copy-of-the-whole-page",
    ),
]
DESCRIPTION_CASES = [
    pytest.param(
        describe([[0.13, 0.115], [0.914, 0.115], [0.914, 0.915], [0.13, 0.915]]),
        "Moldura 1: esquerda 13%, topo 12%, direita 91%, base 92%.",
        id="rectangle",
    ),
    pytest.param(
        describe([[0, 0], [1, 0], [1, 1], [0, 1]]),
        "Sem corte: a página inteira será usada.",
        id="whole-page",
    ),
    pytest.param(
        describe([[0.2, 0.4], [0.54641, 0.6], [0.44641, 0.773205], [0.1, 0.573205]]),
        "Moldura 1: inclinada 30° para a direita. "
        "Cantos: superior esquerdo (20%, 40%), superior direito (55%, 60%), "
        "inferior direito (45%, 77%), inferior esquerdo (10%, 57%).",
        id="a-photo-turned-thirty-degrees-clockwise",
    ),
    pytest.param(
        describe([[0.2, 0.6], [0.5, 0.2], [0.8, 0.4], [0.5, 0.8]]),
        "Moldura 1: inclinada 37° para a direita. Lado de cima da foto à esquerda. "
        "Cantos: superior esquerdo (20%, 60%), superior direito (50%, 20%), "
        "inferior direito (80%, 40%), inferior esquerdo (50%, 80%).",
        id="a-frame-whose-top-edge-points-mostly-up",
    ),
    pytest.param(
        describe([[0.2, 0.8], [0.2, 0.3], [0.6, 0.3], [0.6, 0.8]]),
        "Moldura 1: esquerda 20%, topo 30%, direita 60%, base 80%. Lado de cima da foto à esquerda.",
        id="a-rectangle-whose-top-side-is-on-the-left",
    ),
    pytest.param(
        describe([[0.6, 0.8], [0.2, 0.8], [0.2, 0.3], [0.6, 0.3]]),
        "Moldura 1: esquerda 20%, topo 30%, direita 60%, base 80%. Lado de cima da foto embaixo.",
        id="an-upside-down-rectangle",
    ),
    pytest.param(
        f"describe_corner_position({frame(MIDDLE)}, 'bottom_right')",
        "Canto inferior direito em (60%, 80%).",
        id="a-corner",
    ),
    pytest.param(
        f"describe_edge_position({frame(MIDDLE)}, 'top')",
        "Borda de cima: de (20%, 30%) a (60%, 30%).",
        id="an-edge",
    ),
    pytest.param("read_corner_label('top_left')", "Canto superior esquerdo", id="label-of-top-left"),
    pytest.param("read_corner_label('top_right')", "Canto superior direito", id="label-of-top-right"),
    pytest.param("read_corner_label('bottom_right')", "Canto inferior direito", id="label-of-bottom-right"),
    pytest.param("read_corner_label('bottom_left')", "Canto inferior esquerdo", id="label-of-bottom-left"),
    pytest.param("read_edge_label('top')", "Borda de cima", id="label-of-top"),
    pytest.param("read_edge_label('right')", "Borda direita", id="label-of-right"),
    pytest.param("read_edge_label('bottom')", "Borda de baixo", id="label-of-bottom"),
    pytest.param("read_edge_label('left')", "Borda esquerda", id="label-of-left"),
]
HANDLE_POINT_CASES = [
    pytest.param(
        f"[find_rotate_handle_point({frame(MIDDLE)}, {SQUARE_SURFACE})].map((point) => [point.x, point.y])",
        [[0.4, 0.17]],
        id="the-rotate-handle-sits-above-the-middle-of-the-top-edge",
    ),
    pytest.param(
        (
            f"[find_rotate_handle_point({frame([[0.2, 0.0], [0.6, 0.0], [0.6, 0.5], [0.2, 0.5]])}, {SQUARE_SURFACE})]"
            ".map((point) => [point.x, point.y])"
        ),
        [[0.4, 0.13]],
        id="the-rotate-handle-goes-inside-the-frame-when-there-is-no-room-above-it",
    ),
    pytest.param(
        (
            f"[find_rotate_handle_point({frame([[0.2, 0.3], [0.6, 0.3], [0.6, 0.8], [0.2, 0.8]])}, "
            "{width: 200, height: 200})].map((point) => [point.x, point.y])"
        ),
        [[0.4, 0.3 - 52 / 200]],
        id="the-rotate-handle-keeps-52-pixels-from-the-top-edge-on-a-small-screen",
    ),
    pytest.param(
        (
            f"[find_rotate_handle_point({frame([[0.2, 0.0], [0.6, 0.0], [0.6, 0.1], [0.2, 0.1]])}, {SQUARE_SURFACE})]"
            ".map((point) => [point.x, point.y])"
        ),
        [[0.4, 0.05]],
        id="the-rotate-handle-of-a-low-frame-stays-inside-it",
    ),
]

SIMPLE_CASES = (
    RECTANGLE_CASES
    + CROP_CASES
    + SUGGESTION_CASES
    + KEY_CASES
    + POINTER_CASES
    + COUNT_CASES
    + DRAWING_CASES
    + DESCRIPTION_CASES
)
POINT_CASES = MOVE_FRAME_CASES + MOVE_CORNER_CASES + MOVE_EDGE_CASES + ROTATE_CASES + NUDGE_CASES + HANDLE_POINT_CASES
ORDER_EXPRESSIONS = {
    case.values[0]: f"put_frames_in_reading_order({frame_pair(case.values[0])}).map((ordered) => "
    f"{frame_pair(case.values[0])}.findIndex((original) => frames_are_equal(original, ordered)))"
    for case in READING_ORDER_CASES
}


@pytest.fixture(scope="module")
def geometry_results() -> dict:
    expressions = [case.values[0] for case in SIMPLE_CASES + POINT_CASES]
    for expression_tuple in TURN_EXPRESSIONS.values():
        expressions.extend(expression_tuple)
    expressions.extend(VALIDITY_EXPRESSIONS.values())
    expressions.extend(ORDER_EXPRESSIONS.values())
    return evaluate_policy_expressions(expressions)


def is_close(actual: object, expected: object) -> bool:
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(
                is_close(actual_item, expected_item)
                for actual_item, expected_item in zip(actual, expected, strict=True)
            )
        )
    if isinstance(expected, dict):
        return (
            isinstance(actual, dict)
            and actual.keys() == expected.keys()
            and all(is_close(actual[key], expected[key]) for key in expected)
        )
    if isinstance(expected, int | float) and not isinstance(expected, bool):
        return isinstance(actual, int | float) and abs(actual - expected) <= POINT_TOLERANCE
    return actual == expected


def assert_points_are_close(actual: object, expected: object) -> None:
    assert is_close(actual, expected), (actual, expected)


def assert_values_are_close(actual: object, expected: object) -> None:
    assert_points_are_close(actual, expected)


@pytest.mark.parametrize("vector", TURN_VECTORS, ids=lambda vector: vector["name"])
def test_turning_the_page_matches_the_vectors_shared_with_the_server(geometry_results: dict, vector: dict) -> None:
    turned_points = geometry_results[TURN_EXPRESSIONS[vector["name"]][0]]
    assert_points_are_close(turned_points, vector["page_turned_clockwise"])


@pytest.mark.parametrize("vector", TURN_VECTORS, ids=lambda vector: vector["name"])
def test_turning_the_output_matches_the_vectors_shared_with_the_server(geometry_results: dict, vector: dict) -> None:
    turned_points = geometry_results[TURN_EXPRESSIONS[vector["name"]][1]]
    assert_points_are_close(turned_points, vector["output_turned_clockwise"])


@pytest.mark.parametrize("vector", TURN_VECTORS, ids=lambda vector: vector["name"])
def test_four_turns_of_the_page_come_back_to_the_start(geometry_results: dict, vector: dict) -> None:
    assert_points_are_close(geometry_results[TURN_EXPRESSIONS[vector["name"]][2]], vector["quad"])


@pytest.mark.parametrize("vector", VALIDITY_VECTORS, ids=lambda vector: vector["name"])
def test_validity_names_the_same_problem_as_the_server(geometry_results: dict, vector: dict) -> None:
    verdict = geometry_results[VALIDITY_EXPRESSIONS[vector["name"]]]
    assert (verdict["is_valid"], verdict["problem"]) == (vector["problem"] is None, vector["problem"])


@pytest.mark.parametrize(("expression", "expected"), MOVE_FRAME_CASES)
def test_moving_the_whole_frame(geometry_results: dict, expression: str, expected: object) -> None:
    assert_points_are_close(geometry_results[expression], expected)


@pytest.mark.parametrize(("expression", "expected"), MOVE_CORNER_CASES)
def test_moving_a_corner(geometry_results: dict, expression: str, expected: object) -> None:
    assert_points_are_close(geometry_results[expression], expected)


@pytest.mark.parametrize(("expression", "expected"), MOVE_EDGE_CASES)
def test_moving_an_edge_along_its_normal(geometry_results: dict, expression: str, expected: object) -> None:
    assert_points_are_close(geometry_results[expression], expected)


@pytest.mark.parametrize(("expression", "expected"), ROTATE_CASES)
def test_turning_the_frame_around_its_centre(geometry_results: dict, expression: str, expected: object) -> None:
    assert_points_are_close(geometry_results[expression], expected)


@pytest.mark.parametrize(("expression", "expected"), NUDGE_CASES)
def test_nudging_with_the_arrows(geometry_results: dict, expression: str, expected: object) -> None:
    assert_points_are_close(geometry_results[expression], expected)


@pytest.mark.parametrize(("expression", "expected"), HANDLE_POINT_CASES)
def test_the_rotate_handle_is_placed_outside_the_top_edge(
    geometry_results: dict, expression: str, expected: object
) -> None:
    assert_points_are_close(geometry_results[expression], expected)


@pytest.mark.parametrize(("expression", "expected"), SUGGESTION_CASES)
def test_a_new_frame_is_suggested_in_the_free_part_of_the_page(
    geometry_results: dict, expression: str, expected: object
) -> None:
    assert_points_are_close(geometry_results[expression], expected)


@pytest.mark.parametrize(("expression", "expected"), READING_ORDER_CASES)
def test_frames_are_put_in_reading_order(geometry_results: dict, expression: str, expected: list[int]) -> None:
    assert geometry_results[ORDER_EXPRESSIONS[expression]] == expected


@pytest.mark.parametrize(("expression", "expected"), RECTANGLE_CASES)
def test_frames_are_recognized_and_compared(geometry_results: dict, expression: str, expected: object) -> None:
    assert geometry_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), CROP_CASES)
def test_frames_go_to_and_come_from_the_crops_of_the_server(
    geometry_results: dict, expression: str, expected: object
) -> None:
    assert_points_are_close(geometry_results[expression], expected)


@pytest.mark.parametrize(("expression", "expected"), KEY_CASES)
def test_arrow_keys_choose_a_direction_and_a_step(geometry_results: dict, expression: str, expected: object) -> None:
    assert geometry_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), POINTER_CASES)
def test_a_pointer_movement_becomes_a_shift_or_a_turn(
    geometry_results: dict, expression: str, expected: object
) -> None:
    assert_values_are_close(geometry_results[expression], expected)


@pytest.mark.parametrize(("expression", "expected"), COUNT_CASES)
def test_quarter_turns_are_counted_between_two_rotations(
    geometry_results: dict, expression: str, expected: object
) -> None:
    assert geometry_results[expression] == expected


@pytest.mark.parametrize(("expression", "expected"), DRAWING_CASES)
def test_a_frame_is_drawn_in_percentages_of_the_page(geometry_results: dict, expression: str, expected: object) -> None:
    assert_points_are_close(geometry_results[expression], expected)


@pytest.mark.parametrize(("expression", "expected"), DESCRIPTION_CASES)
def test_a_frame_is_described_in_portuguese(geometry_results: dict, expression: str, expected: object) -> None:
    assert geometry_results[expression] == expected

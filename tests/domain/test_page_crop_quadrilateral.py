import json
import math
from pathlib import Path

import pytest

from digitalizadora.domain.errors import InvalidCropError
from digitalizadora.domain.page_crop import (
    CropCorner,
    PageCrop,
    RectangleEdges,
    find_quadrilateral_problem,
)
from digitalizadora.domain.page_rotation import PageRotation
from digitalizadora.domain.pixel_region import PixelCorner, PixelRegion
from tests.fakes.page_crops import quadrilateral, rectangle

VECTORS_FILE = Path(__file__).parent.parent / "fixtures" / "page-crop-vectors.json"
VECTOR_DOCUMENT = json.loads(VECTORS_FILE.read_text(encoding="utf-8"))
TURN_VECTORS = VECTOR_DOCUMENT["vectors"]
VALIDITY_CASES = VECTOR_DOCUMENT["validity"]
DIAGONAL_CARD = quadrilateral((0.486, 0.119), (0.983, 0.347), (0.542, 0.904), (0.045, 0.676))


def crop_from_points(points) -> PageCrop:
    return quadrilateral(*(tuple(point) for point in points))


def points_of(crop: PageCrop) -> list[list[float]]:
    return [[corner.x, corner.y] for corner in crop.corners]


@pytest.mark.parametrize("case", VALIDITY_CASES, ids=[case["name"] for case in VALIDITY_CASES])
def test_the_problem_of_a_quadrilateral_follows_the_shared_vectors(case) -> None:
    corners = [CropCorner(x, y) for x, y in case["quad"]]

    assert find_quadrilateral_problem(corners) == case["problem"]


@pytest.mark.parametrize(
    "case", [case for case in VALIDITY_CASES if case["problem"] is not None], ids=lambda case: case["name"]
)
def test_a_quadrilateral_with_a_problem_is_refused(case) -> None:
    with pytest.raises(InvalidCropError):
        crop_from_points(case["quad"])


@pytest.mark.parametrize(
    "case", [case for case in VALIDITY_CASES if case["problem"] is None], ids=lambda case: case["name"]
)
def test_a_quadrilateral_without_a_problem_is_accepted(case) -> None:
    assert points_of(crop_from_points(case["quad"])) == case["quad"]


@pytest.mark.parametrize("not_a_number", [math.nan, math.inf, -math.inf, "0.5", None, True])
def test_a_coordinate_that_is_not_a_finite_number_is_refused(not_a_number) -> None:
    with pytest.raises(InvalidCropError):
        quadrilateral((0.1, 0.1), (not_a_number, 0.1), (0.9, 0.9), (0.1, 0.9))


@pytest.mark.parametrize("huge_integer", [10**400, -(10**400)])
def test_an_integer_too_large_for_a_float_is_refused(huge_integer) -> None:
    with pytest.raises(InvalidCropError):
        quadrilateral((0.1, 0.1), (huge_integer, 0.1), (0.9, 0.9), (0.1, 0.9))


def test_rounded_keeps_six_digits() -> None:
    crop = PageCrop.rounded(
        [CropCorner(0.1234567891, 0.2), CropCorner(0.5, 0.2), CropCorner(0.5, 0.9), CropCorner(0.1, 0.9)]
    )

    assert crop.top_left.x == 0.123457


def test_rounded_refuses_an_integer_too_large_for_a_float() -> None:
    with pytest.raises(InvalidCropError):
        PageCrop.rounded([CropCorner(0, 0), CropCorner(10**400, 0), CropCorner(1, 1), CropCorner(0, 1)])


def test_rounded_validates_the_rounded_corners() -> None:
    with pytest.raises(InvalidCropError):
        PageCrop.rounded([CropCorner(0, 0), CropCorner(0.0100001, 0), CropCorner(0.0100001, 1), CropCorner(0, 1)])


@pytest.mark.parametrize("corner_count", [0, 3, 5])
def test_rounded_wants_exactly_four_corners(corner_count) -> None:
    with pytest.raises(InvalidCropError):
        PageCrop.rounded([CropCorner(0.1, 0.1)] * corner_count)


def test_a_rectangle_is_built_from_its_edges() -> None:
    crop = PageCrop.from_rectangle(RectangleEdges(0.1, 0.2, 0.5, 0.9))

    assert points_of(crop) == [[0.1, 0.2], [0.5, 0.2], [0.5, 0.9], [0.1, 0.9]]


def test_the_corners_come_in_the_clockwise_role_order() -> None:
    crop = rectangle(0.1, 0.2, 0.5, 0.9)

    assert crop.corners == (crop.top_left, crop.top_right, crop.bottom_right, crop.bottom_left)


@pytest.mark.parametrize("vector", TURN_VECTORS, ids=lambda vector: vector["name"])
def test_turning_the_page_follows_the_shared_vectors(vector) -> None:
    turned = crop_from_points(vector["quad"]).turned_clockwise()

    assert points_of(turned) == vector["page_turned_clockwise"]


@pytest.mark.parametrize("vector", TURN_VECTORS, ids=lambda vector: vector["name"])
def test_turning_the_page_back_undoes_the_shared_vectors(vector) -> None:
    turned_back = crop_from_points(vector["page_turned_clockwise"]).turned_counterclockwise()

    assert points_of(turned_back) == vector["quad"]


@pytest.mark.parametrize("vector", TURN_VECTORS, ids=lambda vector: vector["name"])
def test_four_page_turns_bring_the_crop_back_exactly(vector) -> None:
    crop = crop_from_points(vector["quad"])

    turned = crop.turned_clockwise().turned_clockwise().turned_clockwise().turned_clockwise()

    assert turned == crop


@pytest.mark.parametrize("vector", TURN_VECTORS, ids=lambda vector: vector["name"])
def test_turning_the_output_follows_the_shared_vectors(vector) -> None:
    turned = crop_from_points(vector["quad"]).with_output_turned_clockwise()

    assert points_of(turned) == vector["output_turned_clockwise"]


def test_four_output_turns_bring_the_crop_back_exactly() -> None:
    turned = DIAGONAL_CARD
    for _ in range(4):
        turned = turned.with_output_turned_clockwise()

    assert turned == DIAGONAL_CARD


def test_turning_the_output_leaves_the_points_where_they_are() -> None:
    turned = DIAGONAL_CARD.with_output_turned_clockwise()

    assert set(turned.corners) == set(DIAGONAL_CARD.corners)


def test_the_corner_of_a_half_page_goes_where_the_page_corner_goes() -> None:
    left_half = rectangle(0.0, 0.0, 0.5, 1.0)

    assert left_half.turned_clockwise().top_right == CropCorner(1.0, 0.0)


@pytest.mark.parametrize("quarter_turns", [0, 1, 2, 3, 4])
def test_seen_on_the_master_undoes_the_page_turns_but_keeps_the_roles(quarter_turns) -> None:
    displayed = DIAGONAL_CARD
    for _ in range(quarter_turns):
        displayed = displayed.turned_clockwise()

    on_master = displayed.seen_on_master(quarter_turns)

    assert set(on_master.corners) == set(DIAGONAL_CARD.corners)


def test_seen_on_the_master_keeps_the_roles_of_the_displayed_crop() -> None:
    displayed = rectangle(0.1, 0.2, 0.5, 0.9)

    on_master = displayed.seen_on_master(1)

    assert on_master.top_left == CropCorner(0.2, 0.9)


def test_a_rectangle_is_recognised() -> None:
    assert rectangle(0.1, 0.2, 0.5, 0.9).is_rectangle is True


def test_a_rectangle_with_turned_roles_is_still_a_rectangle() -> None:
    assert rectangle(0.1, 0.2, 0.5, 0.9).with_output_turned_clockwise().is_rectangle is True


def test_a_tilted_quadrilateral_is_not_a_rectangle() -> None:
    assert DIAGONAL_CARD.is_rectangle is False


def test_a_slightly_tilted_quadrilateral_is_not_a_rectangle() -> None:
    assert quadrilateral((0.1, 0.1), (0.9, 0.11), (0.9, 0.9), (0.1, 0.9)).is_rectangle is False


@pytest.mark.parametrize(
    ("top_left_role", "expected_rotation"),
    [
        (0, PageRotation.NONE),
        (1, PageRotation.CLOCKWISE_90),
        (2, PageRotation.HALF_TURN),
        (3, PageRotation.COUNTERCLOCKWISE_90),
    ],
)
def test_the_rotation_to_upright_follows_where_the_top_left_role_sits(top_left_role, expected_rotation) -> None:
    crop = rectangle(0.1, 0.2, 0.5, 0.9)
    for _ in range(top_left_role):
        crop = crop.with_output_turned_clockwise()

    assert crop.rotation_to_upright is expected_rotation


def test_the_rotation_to_upright_of_a_tilted_quadrilateral_is_not_defined() -> None:
    with pytest.raises(ValueError):
        DIAGONAL_CARD.rotation_to_upright  # noqa: B018


def test_the_whole_page_covers_the_whole_page() -> None:
    assert rectangle(0.0, 0.0, 1.0, 1.0).covers_whole_page is True


def test_the_whole_page_with_the_roles_turned_does_not_cover_it() -> None:
    assert rectangle(0.0, 0.0, 1.0, 1.0).with_output_turned_clockwise().covers_whole_page is False


def test_a_smaller_rectangle_does_not_cover_the_whole_page() -> None:
    assert rectangle(0.1, 0.2, 0.5, 0.9).covers_whole_page is False


def test_a_rotated_square_does_not_cover_the_whole_page() -> None:
    assert quadrilateral((0.5, 0), (1, 0.5), (0.5, 1), (0, 0.5)).covers_whole_page is False


def test_corners_one_float_step_away_from_the_page_still_cover_it() -> None:
    assert rectangle(1e-12, 0.0, 1.0 - 1e-12, 1.0).covers_whole_page is True


def test_the_bounding_edges_hold_the_four_corners() -> None:
    edges = DIAGONAL_CARD.bounding_edges

    assert (edges.left, edges.top, edges.right, edges.bottom) == (0.045, 0.119, 0.983, 0.904)


def test_to_pixel_region_scales_the_bounding_edges() -> None:
    region = rectangle(0.1, 0.2, 0.5, 0.9).to_pixel_region((100, 200))

    assert region == PixelRegion(left=10, top=40, right=50, bottom=180)


def test_to_pixel_region_does_not_round_a_float_error_up() -> None:
    assert rectangle(0.07, 0.0, 0.5, 1.0).to_pixel_region((100, 10)).left == 7


def test_to_pixel_region_rounds_the_origin_down() -> None:
    assert rectangle(0.105, 0.0, 0.5, 1.0).to_pixel_region((100, 10)).left == 10


def test_to_pixel_region_rounds_the_far_edges_up() -> None:
    assert rectangle(0.0, 0.0, 0.505, 1.0).to_pixel_region((100, 10)).right == 51


def test_to_pixel_region_of_the_whole_page_is_the_whole_image() -> None:
    assert rectangle(0.0, 0.0, 1.0, 1.0).to_pixel_region((640, 480)) == PixelRegion(0, 0, 640, 480)


def test_to_pixel_region_keeps_at_least_one_pixel_on_a_tiny_image() -> None:
    region = rectangle(0.0, 0.0, 0.02, 0.02).to_pixel_region((10, 10))

    assert (region.width, region.height) == (1, 1)


def test_to_pixel_corners_scale_each_corner() -> None:
    corners = rectangle(0.1, 0.2, 0.5, 0.9).to_pixel_corners((100, 200))

    assert corners == (PixelCorner(10, 40), PixelCorner(50, 40), PixelCorner(50, 180), PixelCorner(10, 180))


def test_the_output_size_of_a_rectangle_is_its_size_in_pixels() -> None:
    assert rectangle(0.1, 0.2, 0.5, 0.9).output_size_in_pixels((100, 200)) == (40, 140)


def test_the_output_size_is_the_mean_of_the_opposite_edges() -> None:
    crop = quadrilateral((0.0, 0.0), (1.0, 0.0), (0.8, 0.5), (0.2, 0.5))

    assert crop.output_size_in_pixels((100, 100)) == (80, 54)


def test_the_output_size_of_a_turned_rectangle_swaps_width_and_height() -> None:
    crop = rectangle(0.1, 0.2, 0.5, 0.9).with_output_turned_clockwise()

    assert crop.output_size_in_pixels((100, 200)) == (140, 40)


def test_the_output_size_has_at_least_one_pixel() -> None:
    assert rectangle(0.0, 0.0, 0.02, 0.02).output_size_in_pixels((10, 10)) == (1, 1)


def test_the_diagonal_card_keeps_its_proportion_in_the_output() -> None:
    width, height = DIAGONAL_CARD.output_size_in_pixels((1000, 1000))

    assert (width, height) == (round(math.hypot(497, 228)), round(math.hypot(441, 557)))

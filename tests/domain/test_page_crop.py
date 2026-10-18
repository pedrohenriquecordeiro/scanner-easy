import json
import math
from pathlib import Path

import pytest

from digitalizadora.domain.errors import InvalidCropError
from digitalizadora.domain.page_crop import WHOLE_PAGE, RectangleCrop
from digitalizadora.domain.pixel_region import PixelRegion

VECTORS_FILE = Path(__file__).parent.parent / "fixtures" / "page-crop-rotation-vectors.json"
ROTATION_VECTORS = json.loads(VECTORS_FILE.read_text(encoding="utf-8"))["vectors"]
SAMPLE_CROP = RectangleCrop(0.1, 0.2, 0.5, 0.9)


def test_a_valid_crop_keeps_its_edges() -> None:
    assert (SAMPLE_CROP.left, SAMPLE_CROP.top, SAMPLE_CROP.right, SAMPLE_CROP.bottom) == (0.1, 0.2, 0.5, 0.9)


def test_the_whole_page_is_a_valid_crop() -> None:
    assert (WHOLE_PAGE.left, WHOLE_PAGE.top, WHOLE_PAGE.right, WHOLE_PAGE.bottom) == (0.0, 0.0, 1.0, 1.0)


@pytest.mark.parametrize(
    "edges",
    [
        (-0.1, 0.0, 0.5, 0.5),
        (0.0, -0.1, 0.5, 0.5),
        (0.0, 0.0, 1.1, 0.5),
        (0.0, 0.0, 0.5, 1.1),
    ],
)
def test_an_edge_outside_the_page_is_refused(edges) -> None:
    with pytest.raises(InvalidCropError):
        RectangleCrop(*edges)


@pytest.mark.parametrize(
    "edges", [(0.5, 0.0, 0.5, 1.0), (0.6, 0.0, 0.4, 1.0), (0.0, 0.5, 1.0, 0.5), (0.0, 0.6, 1.0, 0.4)]
)
def test_a_crop_with_a_far_edge_before_the_near_one_is_refused(edges) -> None:
    with pytest.raises(InvalidCropError):
        RectangleCrop(*edges)


@pytest.mark.parametrize("edges", [(0.0, 0.0, 0.019, 1.0), (0.0, 0.0, 1.0, 0.019)])
def test_a_side_below_the_minimum_share_is_refused(edges) -> None:
    with pytest.raises(InvalidCropError):
        RectangleCrop(*edges)


@pytest.mark.parametrize("edges", [(0.0, 0.0, 0.02, 1.0), (0.0, 0.0, 1.0, 0.02)])
def test_a_side_of_exactly_the_minimum_share_is_accepted(edges) -> None:
    assert RectangleCrop(*edges).covers_whole_page is False


@pytest.mark.parametrize("not_a_number", [math.nan, math.inf, -math.inf])
def test_an_edge_that_is_not_finite_is_refused(not_a_number) -> None:
    with pytest.raises(InvalidCropError):
        RectangleCrop(0.0, 0.0, not_a_number, 1.0)


@pytest.mark.parametrize("not_a_number", ["0.5", None, True])
def test_an_edge_that_is_not_a_number_is_refused(not_a_number) -> None:
    with pytest.raises(InvalidCropError):
        RectangleCrop(0.0, 0.0, not_a_number, 1.0)


@pytest.mark.parametrize("huge_integer", [10**400, -(10**400)])
def test_an_integer_too_large_for_a_float_is_refused(huge_integer) -> None:
    with pytest.raises(InvalidCropError):
        RectangleCrop(0.0, 0.0, huge_integer, 1.0)


def test_rounded_refuses_an_integer_too_large_for_a_float() -> None:
    with pytest.raises(InvalidCropError):
        RectangleCrop.rounded((0.0, 0.0, 10**400, 1.0))


def test_rounded_keeps_six_digits() -> None:
    assert RectangleCrop.rounded((0.1234567891, 0.2, 0.5, 0.9)).left == 0.123457


def test_rounded_validates_the_rounded_edges() -> None:
    with pytest.raises(InvalidCropError):
        RectangleCrop.rounded((0.0, 0.0, 0.0100001, 1.0))


def test_the_whole_page_covers_the_whole_page() -> None:
    assert WHOLE_PAGE.covers_whole_page is True


def test_a_smaller_crop_does_not_cover_the_whole_page() -> None:
    assert SAMPLE_CROP.covers_whole_page is False


def test_edges_one_float_step_away_from_the_page_still_cover_it() -> None:
    assert RectangleCrop(1e-12, 0.0, 1.0 - 1e-12, 1.0).covers_whole_page is True


@pytest.mark.parametrize("vector", ROTATION_VECTORS)
def test_turning_clockwise_follows_the_shared_vectors(vector) -> None:
    turned = RectangleCrop(*vector["crop"]).turned_clockwise()

    assert (turned.left, turned.top, turned.right, turned.bottom) == tuple(vector["turned_clockwise"])


@pytest.mark.parametrize("vector", ROTATION_VECTORS)
def test_turning_counterclockwise_undoes_the_shared_vectors(vector) -> None:
    turned_back = RectangleCrop(*vector["turned_clockwise"]).turned_counterclockwise()

    assert turned_back == RectangleCrop(*vector["crop"])


@pytest.mark.parametrize("vector", ROTATION_VECTORS)
def test_four_clockwise_turns_bring_the_crop_back_exactly(vector) -> None:
    crop = RectangleCrop(*vector["crop"])

    turned = crop.turned_clockwise().turned_clockwise().turned_clockwise().turned_clockwise()

    assert turned == crop


def test_four_clockwise_turns_of_an_awkward_fraction_bring_it_back_exactly() -> None:
    crop = RectangleCrop(0.1, 0.123456, 0.7, 0.9)

    turned = crop.turned_clockwise().turned_clockwise().turned_clockwise().turned_clockwise()

    assert turned == crop


def test_the_corner_of_a_half_page_goes_where_the_page_corner_goes() -> None:
    left_half = RectangleCrop(0.0, 0.0, 0.5, 1.0)

    assert left_half.turned_clockwise() == RectangleCrop(0.0, 0.0, 1.0, 0.5)


def test_to_pixel_region_scales_to_the_image_size() -> None:
    assert SAMPLE_CROP.to_pixel_region((100, 200)) == PixelRegion(left=10, top=40, right=50, bottom=180)


def test_to_pixel_region_does_not_round_a_float_error_up() -> None:
    crop = RectangleCrop(0.07, 0.0, 0.5, 1.0)

    assert crop.to_pixel_region((100, 10)).left == 7


def test_to_pixel_region_rounds_the_origin_down() -> None:
    crop = RectangleCrop(0.105, 0.0, 0.5, 1.0)

    assert crop.to_pixel_region((100, 10)).left == 10


def test_to_pixel_region_rounds_the_far_edges_up() -> None:
    crop = RectangleCrop(0.0, 0.0, 0.505, 1.0)

    assert crop.to_pixel_region((100, 10)).right == 51


def test_to_pixel_region_of_the_whole_page_is_the_whole_image() -> None:
    assert WHOLE_PAGE.to_pixel_region((640, 480)) == PixelRegion(0, 0, 640, 480)


def test_to_pixel_region_keeps_at_least_one_pixel_on_a_tiny_image() -> None:
    region = RectangleCrop(0.0, 0.0, 0.02, 0.02).to_pixel_region((10, 10))

    assert (region.width, region.height) == (1, 1)


def test_from_pixel_region_divides_by_the_image_size() -> None:
    assert RectangleCrop.from_pixel_region(PixelRegion(10, 40, 50, 180), (100, 200)) == SAMPLE_CROP


def test_from_pixel_region_round_trips_through_to_pixel_region() -> None:
    region = PixelRegion(13, 41, 52, 177)

    crop = RectangleCrop.from_pixel_region(region, (100, 200))

    assert crop.to_pixel_region((100, 200)) == region

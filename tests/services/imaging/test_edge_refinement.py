import math

import pytest
from PIL import Image, ImageDraw

from digitalizadora.services.imaging.edge_refinement import refine_corners
from tests.fakes.photo_scenes import rotated_rectangle_corners

PAGE_SIZE = (600, 800)
LID_LEVEL = 254
PHOTO_LEVEL = 100
COARSE_SWELL_PIXELS = 7
TOLERANCE_PIXELS = 1.0
INCLUSIVE_FILL_PIXELS = 0.5
PHOTO_SIZE = (300, 200)
PHOTO_CENTRE = (300.0, 400.0)


def page_with_photo(corners, photo_level: int = PHOTO_LEVEL) -> Image.Image:
    page = Image.new("L", PAGE_SIZE, LID_LEVEL)
    ImageDraw.Draw(page).polygon(swollen(corners, -INCLUSIVE_FILL_PIXELS), fill=photo_level)
    return page


def swollen(corners, pixels: float):
    centre_x = sum(x for x, _ in corners) / 4
    centre_y = sum(y for _, y in corners) / 4
    result = []
    for x, y in corners:
        length = math.hypot(x - centre_x, y - centre_y)
        result.append((x + (x - centre_x) / length * pixels, y + (y - centre_y) / length * pixels))
    return tuple(result)


def largest_corner_error(refined, truth) -> float:
    return max(math.dist(found, expected) for found, expected in zip(refined, truth, strict=True))


@pytest.mark.parametrize("angle_degrees", [0.0, 20.0, -35.0])
def test_a_swollen_frame_lands_on_the_corners_of_the_photo(angle_degrees):
    truth = rotated_rectangle_corners(PHOTO_CENTRE, PHOTO_SIZE, angle_degrees)
    coarse = swollen(truth, COARSE_SWELL_PIXELS)

    refined = refine_corners(page_with_photo(truth), coarse)

    assert largest_corner_error(refined, truth) <= TOLERANCE_PIXELS * math.sqrt(2) + 0.5


def test_an_axis_aligned_photo_is_met_within_a_pixel_on_every_side():
    truth = ((150.0, 300.0), (450.0, 300.0), (450.0, 500.0), (150.0, 500.0))
    coarse = swollen(truth, COARSE_SWELL_PIXELS)

    refined = refine_corners(page_with_photo(truth), coarse)

    assert largest_corner_error(refined, truth) <= TOLERANCE_PIXELS * math.sqrt(2)


def test_a_frame_already_on_the_photo_stays():
    truth = ((150.0, 300.0), (450.0, 300.0), (450.0, 500.0), (150.0, 500.0))

    refined = refine_corners(page_with_photo(truth), truth)

    assert largest_corner_error(refined, truth) <= TOLERANCE_PIXELS


def test_a_light_photo_with_a_low_contrast_edge_keeps_the_coarse_frame():
    truth = ((150.0, 300.0), (450.0, 300.0), (450.0, 500.0), (150.0, 500.0))
    coarse = swollen(truth, COARSE_SWELL_PIXELS)

    refined = refine_corners(page_with_photo(truth, photo_level=LID_LEVEL - 10), coarse)

    assert refined == coarse


def test_a_side_on_the_boundary_of_the_page_keeps_its_place_while_the_others_move():
    truth = ((0.0, 300.0), (450.0, 300.0), (450.0, 500.0), (0.0, 500.0))
    coarse = ((0.0, 293.0), (457.0, 293.0), (457.0, 507.0), (0.0, 507.0))

    refined = refine_corners(page_with_photo(truth), coarse)

    assert [corner[0] for corner in refined] == pytest.approx([0, 450, 450, 0], abs=TOLERANCE_PIXELS)


def test_a_gradual_edge_is_placed_where_it_has_left_the_lid():
    page = Image.new("L", PAGE_SIZE, LID_LEVEL)
    for column in range(150, 600):
        ramp = min(1.0, max(0.0, (column - 150) / 6))
        ImageDraw.Draw(page).line([(column, 300), (column, 500)], fill=round(LID_LEVEL - ramp * 114))
    coarse = ((142.0, 293.0), (457.0, 293.0), (457.0, 507.0), (142.0, 507.0))

    refined = refine_corners(page, coarse)

    assert 150.0 <= refined[0][0] <= 154.0


def test_a_frame_whose_sides_would_collapse_is_kept():
    page = Image.new("L", PAGE_SIZE, LID_LEVEL)
    ImageDraw.Draw(page).rectangle((300, 300, 303, 500), fill=PHOTO_LEVEL)
    coarse = ((292.0, 292.0), (312.0, 292.0), (312.0, 508.0), (292.0, 508.0))

    assert refine_corners(page, coarse) == coarse

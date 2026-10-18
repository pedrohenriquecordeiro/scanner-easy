import pytest
from PIL import ImageDraw

from digitalizadora.domain.pixel_region import PixelRegion
from digitalizadora.services.paper_region_detection import detect_paper_region
from tests.fakes.synthetic_previews import (
    PAPER_LEVEL,
    PREVIEW_SIZE,
    WHITE_LEVEL,
    ColoredRectangle,
    FilledRectangle,
    add_noise,
    build_color_preview,
    build_horizontal_gradient,
    build_preview,
)

CENTRAL_PAPER = FilledRectangle((40, 60, 159, 219), PAPER_LEVEL)
CENTRAL_PAPER_REGION = PixelRegion(40, 60, 160, 220)
CORNER_PAPER = FilledRectangle((30, 30, 119, 159), PAPER_LEVEL)
CORNER_PAPER_REGION = PixelRegion(30, 30, 120, 160)
POSITION_TOLERANCE_PIXELS = 3


def assert_region_close_to(region: PixelRegion | None, expected: PixelRegion) -> None:
    assert region is not None
    deviations = [abs(found - wanted) for found, wanted in zip(region.as_box(), expected.as_box(), strict=True)]
    assert max(deviations) <= POSITION_TOLERANCE_PIXELS


def test_a_sheet_in_the_middle_of_a_dark_lid_is_found():
    assert_region_close_to(detect_paper_region(build_preview(rectangles=[CENTRAL_PAPER])), CENTRAL_PAPER_REGION)


def test_a_sheet_near_a_corner_of_a_dark_lid_is_found():
    assert_region_close_to(detect_paper_region(build_preview(rectangles=[CORNER_PAPER])), CORNER_PAPER_REGION)


def test_a_dark_photo_on_a_white_lid_is_found():
    photo = FilledRectangle((40, 60, 159, 219), 60)

    region = detect_paper_region(build_preview(background_level=WHITE_LEVEL, rectangles=[photo]))

    assert_region_close_to(region, CENTRAL_PAPER_REGION)


def test_a_sheet_with_a_dark_frame_inside_is_found_as_a_whole():
    frame = FilledRectangle((60, 80, 139, 199), 90)
    paper = FilledRectangle((40, 60, 159, 219), PAPER_LEVEL)

    region = detect_paper_region(build_preview(rectangles=[paper, frame]))

    assert_region_close_to(region, CENTRAL_PAPER_REGION)


def test_a_white_sheet_on_a_white_lid_is_not_found():
    paper = FilledRectangle((40, 60, 159, 219), 245)

    assert detect_paper_region(build_preview(background_level=WHITE_LEVEL, rectangles=[paper])) is None


def test_a_uniform_image_has_no_sheet():
    assert detect_paper_region(build_preview(background_level=128)) is None


def test_a_sheet_below_a_tenth_of_the_glass_is_ignored():
    small_paper = FilledRectangle((90, 130, 110, 150), PAPER_LEVEL)

    assert detect_paper_region(build_preview(rectangles=[small_paper])) is None


def test_a_sheet_just_above_a_tenth_of_the_glass_is_found():
    paper = FilledRectangle((60, 80, 139, 159), PAPER_LEVEL)

    assert detect_paper_region(build_preview(rectangles=[paper])) is not None


def test_a_sheet_that_fills_the_glass_is_not_cropped():
    size = (400, 283)
    nearly_everything = FilledRectangle((4, 4, 395, 278), PAPER_LEVEL)

    assert detect_paper_region(build_preview(size, rectangles=[nearly_everything])) is None


def test_a_gradient_background_has_no_reliable_border():
    gradient = build_horizontal_gradient(PREVIEW_SIZE)
    ImageDraw.Draw(gradient).rectangle(CENTRAL_PAPER.box, fill=PAPER_LEVEL)

    assert detect_paper_region(gradient) is None


def test_the_lid_left_around_a_big_sheet_is_not_taken_for_the_sheet():
    big_paper = FilledRectangle((0, 0, 199, 200), PAPER_LEVEL)

    assert detect_paper_region(build_preview(rectangles=[big_paper])) is None


def test_a_sheet_flush_with_a_corner_of_the_glass_is_found():
    flush_paper = FilledRectangle((0, 0, 99, 139), PAPER_LEVEL)

    assert_region_close_to(detect_paper_region(build_preview(rectangles=[flush_paper])), PixelRegion(0, 0, 100, 140))


def test_a_sheet_flush_with_one_side_of_the_glass_is_found():
    flush_paper = FilledRectangle((0, 70, 99, 209), PAPER_LEVEL)

    assert_region_close_to(detect_paper_region(build_preview(rectangles=[flush_paper])), PixelRegion(0, 70, 100, 210))


def test_thin_text_lines_on_a_white_lid_are_not_a_sheet():
    preview = build_preview(background_level=WHITE_LEVEL)
    drawing = ImageDraw.Draw(preview)
    for row in range(40, 240, 5):
        drawing.line((30, row, 170, row), fill=0)

    assert detect_paper_region(preview) is None


def test_scattered_dust_on_a_dark_lid_is_not_a_sheet():
    preview = build_preview()
    drawing = ImageDraw.Draw(preview)
    for position in range(20, 180, 40):
        drawing.point((position, 2 * position), fill=WHITE_LEVEL)

    assert detect_paper_region(preview) is None


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_noise_of_five_levels_still_finds_the_sheet(seed):
    noisy = add_noise(build_preview(rectangles=[CENTRAL_PAPER]), amplitude=5, seed=seed)

    assert_region_close_to(detect_paper_region(noisy), CENTRAL_PAPER_REGION)


def test_text_blocks_that_look_light_grey_on_a_white_lid_are_not_a_sheet():
    blocks = [FilledRectangle((30, top, 170, top + 6), 225) for top in range(40, 240, 12)]

    assert detect_paper_region(build_preview(background_level=WHITE_LEVEL, rectangles=blocks)) is None


DARK_LID_COLOR = (40, 40, 40)
WHITE_COLOR = (255, 255, 255)
NAVY_COLOR = (25, 30, 70)
BLACK_COLOR = (5, 5, 5)
BRIGHT_PICTURE_COLOR = (220, 200, 120)
NEAR_LID_COLOR = (55, 55, 55)
PAGE_BOX = (30, 30, 169, 249)
PAGE_REGION = PixelRegion(30, 30, 170, 250)


def test_a_navy_cover_with_a_bright_picture_is_found_as_a_whole():
    cover = ColoredRectangle(PAGE_BOX, NAVY_COLOR)
    picture = ColoredRectangle((60, 90, 139, 189), BRIGHT_PICTURE_COLOR)

    region = detect_paper_region(build_color_preview(DARK_LID_COLOR, [cover, picture]))

    assert_region_close_to(region, PAGE_REGION)


def test_a_page_with_a_black_half_is_found_as_a_whole():
    page = ColoredRectangle(PAGE_BOX, WHITE_COLOR)
    black_half = ColoredRectangle((30, 140, 169, 249), BLACK_COLOR)

    region = detect_paper_region(build_color_preview(DARK_LID_COLOR, [page, black_half]))

    assert_region_close_to(region, PAGE_REGION)


def test_a_region_whose_surroundings_are_not_the_background_is_rejected():
    page = ColoredRectangle(PAGE_BOX, WHITE_COLOR)
    dark_half_close_to_the_lid = ColoredRectangle((30, 140, 169, 249), NEAR_LID_COLOR)

    preview = build_color_preview(DARK_LID_COLOR, [page, dark_half_close_to_the_lid])

    assert detect_paper_region(preview) is None


def test_a_colour_preview_of_a_white_sheet_on_a_dark_lid_is_found():
    page = ColoredRectangle(PAGE_BOX, WHITE_COLOR)

    assert_region_close_to(detect_paper_region(build_color_preview(DARK_LID_COLOR, [page])), PAGE_REGION)

import io
import math
import time

import pytest
from PIL import Image, ImageDraw

from digitalizadora.domain.imaging.pixel_region import PixelRegion
from digitalizadora.services.imaging.photo_region_detection import PhotoRegion, detect_photo_regions
from tests.fakes.book_on_glass import BookOnGlass, build_book_on_glass_jpeg
from tests.fakes.photo_scenes import (
    PlacedPhoto,
    build_flat_lid,
    build_lid,
    build_photo_scene,
    build_shaded_lid,
    paste_flat_sheet,
    photo_corners,
)
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


def detect_paper_region(preview) -> PixelRegion | None:
    """The bounding box of the only region found, in pixels of the preview; None when there is none."""
    detection = detect_photo_regions(preview)
    if detection is None or not detection.regions:
        return None
    assert len(detection.regions) == 1
    corners = detection.regions[0].corners
    horizontal_positions = [corner[0] for corner in corners]
    vertical_positions = [corner[1] for corner in corners]
    return PixelRegion(
        round(min(horizontal_positions)),
        round(min(vertical_positions)),
        round(max(horizontal_positions)),
        round(max(vertical_positions)),
    )


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


def test_a_sheet_below_one_percent_of_the_glass_is_ignored():
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
    blocks = [FilledRectangle((30, top, 170, top + 3), 225) for top in range(40, 240, 12)]

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


SCENE_SIZE = (291, 400)
CORNER_TOLERANCE_PIXELS = 2.5
UPRIGHT_PHOTO = PlacedPhoto(center=(145.0, 200.0), size=(150, 200), angle_degrees=0.0)
CARD_AT_31_DEGREES = PlacedPhoto(center=(145.0, 200.0), size=(110, 160), angle_degrees=31.0)
UPPER_PHOTO = PlacedPhoto(center=(135.0, 118.0), size=(205, 138), angle_degrees=-30.0)
LOWER_PHOTO = PlacedPhoto(center=(155.0, 305.0), size=(205, 138), angle_degrees=-2.0, seed=2)
LEFT_PHOTO = PlacedPhoto(center=(75.0, 200.0), size=(120, 160), angle_degrees=0.0)
RIGHT_PHOTO = PlacedPhoto(center=(215.0, 200.0), size=(120, 160), angle_degrees=0.0, seed=2)


def detect_in(photos: list[PlacedPhoto], lid=None):
    return detect_photo_regions(build_photo_scene(SCENE_SIZE, photos, lid))


def worst_corner_error(region: PhotoRegion, photo: PlacedPhoto) -> float:
    return max(math.dist(found, wanted) for found, wanted in zip(region.corners, photo_corners(photo), strict=True))


def test_an_upright_photo_on_a_white_lid_is_one_region_with_the_corners_of_the_photo():
    detection = detect_in([UPRIGHT_PHOTO])

    assert len(detection.regions) == 1
    assert worst_corner_error(detection.regions[0], UPRIGHT_PHOTO) <= CORNER_TOLERANCE_PIXELS


def test_a_card_lying_at_31_degrees_is_framed_as_a_rotated_rectangle():
    detection = detect_in([CARD_AT_31_DEGREES])

    assert len(detection.regions) == 1
    assert worst_corner_error(detection.regions[0], CARD_AT_31_DEGREES) <= CORNER_TOLERANCE_PIXELS


def test_the_angle_of_the_top_edge_of_a_tilted_card_is_the_angle_it_lies_at():
    detection = detect_in([CARD_AT_31_DEGREES])

    assert detection.regions[0].top_edge_angle_degrees == pytest.approx(31.0, abs=1.5)


def test_two_photos_at_minus_30_and_minus_2_degrees_are_two_regions():
    detection = detect_in([UPPER_PHOTO, LOWER_PHOTO])

    assert len(detection.regions) == 2


def test_the_two_photos_of_the_acceptance_scene_are_found_with_their_corners():
    detection = detect_in([UPPER_PHOTO, LOWER_PHOTO])

    errors = {
        round(worst_corner_error(region, photo), 1) <= CORNER_TOLERANCE_PIXELS
        for region in detection.regions
        for photo in (UPPER_PHOTO, LOWER_PHOTO)
        if math.dist(region.corners[0], photo_corners(photo)[0]) < 20
    }
    assert errors == {True}


def test_the_angles_of_the_two_photos_of_the_acceptance_scene_are_found():
    detection = detect_in([UPPER_PHOTO, LOWER_PHOTO])

    angles = sorted(region.top_edge_angle_degrees for region in detection.regions)
    assert angles == pytest.approx([-30.0, -2.0], abs=2.0)


def test_two_photos_side_by_side_are_two_regions():
    assert len(detect_in([LEFT_PHOTO, RIGHT_PHOTO]).regions) == 2


def test_two_photos_stacked_at_five_degrees_are_two_regions():
    upper = PlacedPhoto(center=(145.0, 105.0), size=(190, 130), angle_degrees=5.0)
    lower = PlacedPhoto(center=(145.0, 295.0), size=(190, 130), angle_degrees=-5.0, seed=2)

    assert len(detect_in([upper, lower]).regions) == 2


def test_two_photos_twelve_pixels_apart_are_two_regions():
    left = PlacedPhoto(center=(78.0, 200.0), size=(130, 160), angle_degrees=0.0)
    right = PlacedPhoto(center=(78.0 + 130 + 12, 200.0), size=(130, 160), angle_degrees=0.0, seed=2)

    assert len(detect_in([left, right]).regions) == 2


def test_two_photos_one_pixel_apart_are_one_region_around_both():
    left = PlacedPhoto(center=(78.0, 200.0), size=(130, 160), angle_degrees=0.0)
    right = PlacedPhoto(center=(78.0 + 130 + 1, 200.0), size=(130, 160), angle_degrees=0.0, seed=2)

    assert len(detect_in([left, right]).regions) == 1


def test_a_third_photo_is_ignored_and_counted():
    third = PlacedPhoto(center=(145.0, 345.0), size=(80, 70), angle_degrees=0.0, seed=3)
    upper_left = PlacedPhoto(center=(75.0, 110.0), size=(110, 140), angle_degrees=0.0)
    upper_right = PlacedPhoto(center=(215.0, 110.0), size=(110, 140), angle_degrees=8.0, seed=2)

    detection = detect_in([upper_left, upper_right, third])

    assert (len(detection.regions), detection.ignored_count) == (2, 1)


def test_the_two_regions_are_the_largest_ones():
    third = PlacedPhoto(center=(145.0, 345.0), size=(80, 70), angle_degrees=0.0, seed=3)
    upper_left = PlacedPhoto(center=(75.0, 110.0), size=(110, 140), angle_degrees=0.0)
    upper_right = PlacedPhoto(center=(215.0, 110.0), size=(110, 140), angle_degrees=8.0, seed=2)

    detection = detect_in([upper_left, upper_right, third])

    assert all(region.corners[0][1] < 200 for region in detection.regions)


def test_an_empty_white_lid_has_no_region():
    detection = detect_in([])

    assert detection.regions == ()


def test_a_page_with_a_thin_printed_frame_has_no_region():
    lid = build_flat_lid(SCENE_SIZE, color=(250, 250, 250))
    ImageDraw.Draw(lid).rectangle((0, 0, SCENE_SIZE[0] - 1, SCENE_SIZE[1] - 1), outline=(230, 230, 230))

    assert detect_in([], lid).regions == ()


def test_a_photo_of_two_percent_of_the_page_like_a_passport_photo_is_found():
    passport_photo = PlacedPhoto(center=(145.0, 200.0), size=(45, 50), angle_degrees=20.0)

    assert len(detect_in([passport_photo]).regions) == 1


def test_a_photo_of_half_a_percent_of_the_page_is_ignored():
    tiny = PlacedPhoto(center=(145.0, 200.0), size=(25, 25), angle_degrees=20.0)

    detection = detect_in([tiny])

    assert (detection.regions, detection.ignored_count) == ((), 0)


def test_a_small_label_next_to_a_big_photo_is_ignored():
    label = PlacedPhoto(center=(250.0, 370.0), size=(30, 30), angle_degrees=0.0, seed=4)
    photo = PlacedPhoto(center=(120.0, 190.0), size=(150, 200), angle_degrees=15.0)

    assert len(detect_in([photo, label]).regions) == 1


def test_a_photo_flush_with_the_edge_of_the_glass_is_found():
    flush = PlacedPhoto(center=(90.0, 100.0), size=(180, 200), angle_degrees=0.0)

    assert len(detect_in([flush]).regions) == 1


def test_a_white_sheet_on_a_dark_lid_at_seven_degrees_is_found():
    sheet = PlacedPhoto(center=(145.0, 200.0), size=(160, 220), angle_degrees=7.0)
    lid = build_flat_lid(SCENE_SIZE, color=(30, 30, 30))
    paste_flat_sheet(lid, sheet, (250, 250, 245))

    detection = detect_in([], lid)

    assert detection.regions[0].top_edge_angle_degrees == pytest.approx(7.0, abs=1.5)


def test_a_photo_almost_the_colour_of_the_lid_is_not_a_region():
    photo = PlacedPhoto(center=(145.0, 200.0), size=(160, 220), angle_degrees=0.0)
    lid = build_flat_lid(SCENE_SIZE, color=(30, 30, 30))
    paste_flat_sheet(lid, photo, (45, 45, 45))

    assert detect_in([], lid).regions == ()


def test_a_polaroid_with_a_white_border_on_a_white_lid_is_found_without_its_border():
    polaroid = PlacedPhoto(center=(145.0, 200.0), size=(150, 180), angle_degrees=10.0)
    lid = build_lid(SCENE_SIZE)
    paste_flat_sheet(lid, polaroid, (253, 253, 250))
    inner_photo = PlacedPhoto(center=(145.0, 190.0), size=(120, 120), angle_degrees=10.0, seed=3)

    detection = detect_in([inner_photo], lid)

    assert len(detection.regions) == 1
    assert worst_corner_error(detection.regions[0], inner_photo) <= CORNER_TOLERANCE_PIXELS


def test_a_white_polaroid_without_a_photo_inside_has_no_region():
    polaroid = PlacedPhoto(center=(145.0, 200.0), size=(150, 180), angle_degrees=10.0)
    lid = build_lid(SCENE_SIZE)
    paste_flat_sheet(lid, polaroid, (253, 253, 250))

    assert detect_in([], lid).regions == ()


def test_a_lid_with_a_gradient_border_gives_no_answer():
    gradient = build_horizontal_gradient(SCENE_SIZE).convert("RGB")

    assert detect_photo_regions(gradient) is None


def test_an_open_lid_with_a_shadow_gives_no_answer():
    book_preview = Image.open(io.BytesIO(build_book_on_glass_jpeg(BookOnGlass()))).convert("RGB")

    assert detect_photo_regions(book_preview) is None


@pytest.mark.parametrize("shading_levels", [45, 70, 100])
def test_two_photos_on_a_lid_shaded_from_top_to_bottom_are_two_regions(shading_levels):
    lid = build_shaded_lid(SCENE_SIZE, shading_levels)

    assert len(detect_in([UPPER_PHOTO, LOWER_PHOTO], lid).regions) == 2


def test_the_photos_on_a_shaded_lid_are_found_with_their_corners():
    lid = build_shaded_lid(SCENE_SIZE, 70)

    regions = detect_in([UPPER_PHOTO, LOWER_PHOTO], lid).regions

    assert worst_corner_error(regions[0], UPPER_PHOTO) < CORNER_TOLERANCE_PIXELS


def test_one_photo_on_a_shaded_lid_is_left_to_the_detection_by_side():
    lid = build_shaded_lid(SCENE_SIZE, 70)

    assert detect_in([UPRIGHT_PHOTO], lid) is None


def test_a_preview_too_small_for_a_border_gives_no_answer():
    assert detect_photo_regions(Image.new("RGB", (4, 4), (255, 255, 255))) is None


def test_detecting_two_photos_takes_a_small_part_of_a_second():
    scene = build_photo_scene(SCENE_SIZE, [UPPER_PHOTO, LOWER_PHOTO])

    started = time.perf_counter()
    detect_photo_regions(scene)

    assert time.perf_counter() - started < 0.1

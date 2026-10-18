import os
from pathlib import Path

import pytest
from PIL import Image

from digitalizadora.services.paper_edge_detection import PaperEdges, detect_paper_edges
from tests.fakes.book_on_glass import BookOnGlass, build_book_on_glass_preview
from tests.fakes.synthetic_previews import (
    PAPER_LEVEL,
    PREVIEW_SIZE,
    WHITE_LEVEL,
    FilledRectangle,
    add_noise,
    build_horizontal_gradient,
    build_preview,
)

EDGE_TOLERANCE = 0.02
LEFT_EDGE_TOLERANCE = 0.03
PREVIEW_WIDTH, PREVIEW_HEIGHT = PREVIEW_SIZE
CENTRAL_PAPER = FilledRectangle((40, 60, 159, 219), PAPER_LEVEL)
CENTRAL_PAPER_EDGES = (40 / PREVIEW_WIDTH, 60 / PREVIEW_HEIGHT, 160 / PREVIEW_WIDTH, 220 / PREVIEW_HEIGHT)
REAL_SCANS_VARIABLE = "DIGITALIZADORA_REAL_SCANS_FOLDER"


def assert_edges_close_to(edges: PaperEdges | None, expected: tuple[float | None, ...], tolerance: float) -> None:
    assert edges is not None
    found = (edges.left, edges.top, edges.right, edges.bottom)
    for found_edge, wanted_edge in zip(found, expected, strict=True):
        if wanted_edge is None:
            assert found_edge is None
        else:
            assert found_edge is not None
            assert abs(found_edge - wanted_edge) <= tolerance


def test_a_sheet_on_a_dark_lid_has_its_four_edges_found():
    edges = detect_paper_edges(build_preview(rectangles=[CENTRAL_PAPER]))

    assert_edges_close_to(edges, CENTRAL_PAPER_EDGES, EDGE_TOLERANCE)


def test_a_dark_photo_on_a_white_lid_has_its_four_edges_found():
    photo = FilledRectangle((40, 60, 159, 219), 60)

    edges = detect_paper_edges(build_preview(background_level=WHITE_LEVEL, rectangles=[photo]))

    assert_edges_close_to(edges, CENTRAL_PAPER_EDGES, EDGE_TOLERANCE)


def test_the_edges_survive_the_noise_of_a_scanner():
    preview = add_noise(build_preview(rectangles=[CENTRAL_PAPER]), amplitude=4, seed=7)

    assert_edges_close_to(detect_paper_edges(preview), CENTRAL_PAPER_EDGES, EDGE_TOLERANCE)


def test_a_colour_preview_is_read_as_grey():
    preview = build_preview(rectangles=[CENTRAL_PAPER]).convert("RGB")

    assert_edges_close_to(detect_paper_edges(preview), CENTRAL_PAPER_EDGES, EDGE_TOLERANCE)


def test_a_sheet_flush_with_the_top_left_corner_leaves_those_sides_at_the_glass():
    paper = FilledRectangle((0, 0, 139, 199), PAPER_LEVEL)

    edges = detect_paper_edges(build_preview(rectangles=[paper]))

    assert_edges_close_to(edges, (None, None, 140 / PREVIEW_WIDTH, 200 / PREVIEW_HEIGHT), EDGE_TOLERANCE)


def test_a_single_edge_is_not_enough():
    half_glass = FilledRectangle((0, 0, 119, 279), PAPER_LEVEL)

    assert detect_paper_edges(build_preview(rectangles=[half_glass])) is None


def test_edges_on_one_axis_only_are_not_a_sheet():
    full_width_strip = FilledRectangle((0, 60, 199, 219), PAPER_LEVEL)

    assert detect_paper_edges(build_preview(rectangles=[full_width_strip])) is None


def test_a_uniform_image_has_no_edges():
    assert detect_paper_edges(build_preview(background_level=128)) is None


def test_a_white_page_on_a_white_lid_has_no_edges():
    paper = FilledRectangle((40, 60, 159, 219), 250)

    assert detect_paper_edges(build_preview(background_level=WHITE_LEVEL, rectangles=[paper])) is None


def test_a_gradient_that_never_steps_has_no_edges():
    assert detect_paper_edges(build_horizontal_gradient((200, 280))) is None


def test_a_frame_below_a_fifth_of_the_glass_is_refused():
    small_paper = FilledRectangle((70, 100, 119, 159), PAPER_LEVEL)

    assert detect_paper_edges(build_preview(rectangles=[small_paper])) is None


def build_page_of_text(dash_period: int) -> Image.Image:
    page = build_preview(background_level=WHITE_LEVEL)
    for top in range(30, 250, 8):
        for left in range(24, 176, dash_period):
            page.paste(60, (left, top, left + 3, top + 2))
    return page


def test_a_page_of_text_with_margins_has_no_edges():
    assert detect_paper_edges(build_page_of_text(dash_period=8)) is None


def test_a_page_of_solid_lines_of_text_has_no_edges():
    assert detect_paper_edges(build_page_of_text(dash_period=3)) is None


def test_the_edge_of_the_sheet_wins_over_the_text_inside_it():
    paper = FilledRectangle((40, 60, 159, 219), 250)
    preview = build_preview(background_level=120, rectangles=[paper])
    for top in range(70, 210, 8):
        preview.paste(40, (60, top, 140, top + 1))

    assert_edges_close_to(detect_paper_edges(preview), CENTRAL_PAPER_EDGES, EDGE_TOLERANCE)


def test_a_preview_too_small_to_search_has_no_edges():
    assert detect_paper_edges(Image.new("L", (6, 6), 128)) is None


BOOK = BookOnGlass()


def test_a_book_with_an_invisible_left_edge_has_the_other_three_edges_found():
    edges = detect_paper_edges(build_book_on_glass_preview(BOOK))

    assert_edges_close_to(
        edges, (edges.left if edges else None, BOOK.top, BOOK.right, BOOK.bottom), EDGE_TOLERANCE
    )


def test_the_invisible_left_edge_of_a_book_is_read_from_the_glass_above_and_below_it():
    edges = detect_paper_edges(build_book_on_glass_preview(BOOK))

    assert edges is not None
    assert edges.left == pytest.approx(BOOK.left, abs=LEFT_EDGE_TOLERANCE)


def test_the_left_edge_of_a_book_is_never_inside_the_book():
    edges = detect_paper_edges(build_book_on_glass_preview(BOOK))

    assert edges is not None
    assert edges.left <= BOOK.left + EDGE_TOLERANCE / 2


def test_a_book_on_a_wider_preview_is_found_the_same_way():
    large_book = BookOnGlass(left=0.2, top=0.1, right=0.85, bottom=0.8, size=(400, 283))

    edges = detect_paper_edges(build_book_on_glass_preview(large_book))

    assert_edges_close_to(
        edges, (large_book.left, large_book.top, large_book.right, large_book.bottom), LEFT_EDGE_TOLERANCE
    )


def test_a_book_without_a_visible_top_edge_is_found_from_the_glass_beside_it():
    book = build_book_on_glass_preview(BOOK).transpose(Image.Transpose.TRANSPOSE)

    edges = detect_paper_edges(book)

    assert edges is not None
    assert edges.top == pytest.approx(BOOK.left, abs=LEFT_EDGE_TOLERANCE)


REAL_SCANS_FOLDER = os.environ.get(REAL_SCANS_VARIABLE)
REAL_SCAN_NAMES = ["1-color-100.jpg", "2-gray-100.jpg", "3-color-300.jpg", "4-color-150-photo.jpg"]
REAL_BOOK_EDGES = (0.13, 0.125, 0.91, 0.914)
PREVIEW_EDGE_PIXELS = 400


def read_real_preview(scan_path: Path) -> Image.Image:
    with Image.open(scan_path) as scan:
        scan.draft("L", (PREVIEW_EDGE_PIXELS, PREVIEW_EDGE_PIXELS))
        scan.thumbnail((PREVIEW_EDGE_PIXELS, PREVIEW_EDGE_PIXELS), Image.Resampling.BOX)
        return scan.convert("L")


@pytest.mark.skipif(REAL_SCANS_FOLDER is None, reason=f"set {REAL_SCANS_VARIABLE} to the folder of the real scans")
@pytest.mark.parametrize("scan_name", REAL_SCAN_NAMES)
def test_the_real_scans_of_the_book_are_framed_to_the_book(scan_name):
    edges = detect_paper_edges(read_real_preview(Path(REAL_SCANS_FOLDER) / scan_name))

    assert_edges_close_to(edges, REAL_BOOK_EDGES, LEFT_EDGE_TOLERANCE)

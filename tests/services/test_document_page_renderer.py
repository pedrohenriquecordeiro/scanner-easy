import io
from pathlib import Path

import pytest
from PIL import Image

from digitalizadora.domain.errors import ScanFailedError
from digitalizadora.domain.page_framing import UNFRAMED, PageFraming
from digitalizadora.domain.page_rotation import PageRotation
from digitalizadora.services import document_page_renderer
from digitalizadora.services.document_page_renderer import DocumentPageRenderer
from tests.fakes.page_crops import rectangle
from tests.fakes.synthetic_scans import build_marked_scan_jpeg, find_marker_corner, read_jpeg_size

PAGE_SIZE = (100, 200)
DOTS_PER_INCH = 300
TOP_RIGHT_QUADRANT = rectangle(0.5, 0.0, 1.0, 0.5)
TOP_LEFT_QUADRANT = rectangle(0.0, 0.0, 0.5, 0.5)
MARKER_REDNESS_THRESHOLD = 30
QUARTER_TURN = PageFraming(rotation=PageRotation.CLOCKWISE_90)


@pytest.fixture
def page_file(tmp_path: Path) -> Path:
    page_path = tmp_path / "page.jpg"
    page_path.write_bytes(build_marked_scan_jpeg(PAGE_SIZE, dpi=(DOTS_PER_INCH, DOTS_PER_INCH)))
    return page_path


def render(page_file: Path, framing: PageFraming) -> bytes:
    return DocumentPageRenderer().render_jpeg(page_file, framing)


def read_redness(jpeg_content: bytes, position: tuple[int, int]) -> int:
    with Image.open(io.BytesIO(jpeg_content)) as image:
        red, green, _ = image.convert("RGB").getpixel(position)
    return red - green


def rendered_width(jpeg_content: bytes) -> int:
    return read_jpeg_size(jpeg_content)[0]


def read_density(jpeg_content: bytes) -> tuple[float, float]:
    with Image.open(io.BytesIO(jpeg_content)) as image:
        return image.info["dpi"]


def test_a_page_without_rotation_or_crop_comes_out_with_the_bytes_of_the_scanner(page_file):
    assert render(page_file, UNFRAMED) == page_file.read_bytes()


def test_a_rotation_alone_swaps_the_dimensions(page_file):
    assert read_jpeg_size(render(page_file, QUARTER_TURN)) == PAGE_SIZE[::-1]


def test_a_half_turn_keeps_the_dimensions(page_file):
    assert read_jpeg_size(render(page_file, PageFraming(rotation=PageRotation.HALF_TURN))) == PAGE_SIZE


@pytest.mark.parametrize(
    ("rotation", "expected_corner"),
    [
        (PageRotation.CLOCKWISE_90, "top-right"),
        (PageRotation.HALF_TURN, "bottom-right"),
        (PageRotation.COUNTERCLOCKWISE_90, "bottom-left"),
    ],
)
def test_the_rotation_turns_the_page_clockwise(page_file, rotation, expected_corner):
    assert find_marker_corner(render(page_file, PageFraming(rotation=rotation))) == expected_corner


def test_a_crop_alone_has_the_size_of_the_region(page_file):
    assert read_jpeg_size(render(page_file, PageFraming(crops=(TOP_LEFT_QUADRANT,)))) == (50, 100)


def test_a_crop_alone_keeps_what_is_inside_the_frame(page_file):
    assert find_marker_corner(render(page_file, PageFraming(crops=(TOP_LEFT_QUADRANT,)))) == "top-left"


def test_a_crop_away_from_the_marker_leaves_the_marker_out(page_file):
    cropped = render(page_file, PageFraming(crops=(rectangle(0.5, 0.5, 1.0, 1.0),)))

    assert read_redness(cropped, (8, 8)) < MARKER_REDNESS_THRESHOLD


def test_a_rotation_and_a_crop_together_crop_in_the_displayed_orientation(page_file):
    framing = PageFraming(PageRotation.CLOCKWISE_90, (TOP_RIGHT_QUADRANT,))

    rendered = render(page_file, framing)

    assert (read_jpeg_size(rendered), find_marker_corner(rendered)) == ((100, 50), "top-right")


def test_the_displayed_crop_that_misses_the_turned_marker_misses_it_in_the_result(page_file):
    # The marker is at the top-left of the stored page, so at the top-right once the page is turned.
    framing = PageFraming(PageRotation.CLOCKWISE_90, (rectangle(0.0, 0.5, 0.5, 1.0),))

    rendered = render(page_file, framing)

    assert read_redness(rendered, (rendered_width(rendered) - 8, 8)) < MARKER_REDNESS_THRESHOLD


def test_the_rendered_page_keeps_the_density_of_the_scanner(page_file):
    assert read_density(render(page_file, PageFraming(PageRotation.CLOCKWISE_90, (TOP_LEFT_QUADRANT,)))) == (
        pytest.approx(DOTS_PER_INCH, abs=1),
        pytest.approx(DOTS_PER_INCH, abs=1),
    )


def test_the_rendered_page_is_a_jpeg(page_file):
    with Image.open(io.BytesIO(render(page_file, QUARTER_TURN))) as image:
        assert image.format == "JPEG"


def test_the_stored_page_is_not_touched(page_file):
    bytes_before = page_file.read_bytes()

    render(page_file, PageFraming(PageRotation.CLOCKWISE_90, (TOP_LEFT_QUADRANT,)))

    assert page_file.read_bytes() == bytes_before


def test_an_image_that_cannot_be_decoded_raises_scan_failed(tmp_path):
    broken_page = tmp_path / "broken.jpg"
    broken_page.write_bytes(b"not a jpeg")

    with pytest.raises(ScanFailedError):
        render(broken_page, QUARTER_TURN)


def test_a_page_file_that_vanished_raises_scan_failed(tmp_path):
    with pytest.raises(ScanFailedError):
        render(tmp_path / "gone.jpg", UNFRAMED)


def test_a_page_file_that_vanished_raises_scan_failed_when_it_needs_rendering(tmp_path):
    with pytest.raises(ScanFailedError):
        render(tmp_path / "gone.jpg", QUARTER_TURN)


def test_a_memory_error_is_not_hidden(page_file, monkeypatch):
    def exhaust_memory(*arguments: object) -> object:
        raise MemoryError

    monkeypatch.setattr(document_page_renderer, "replace_with", exhaust_memory)

    with pytest.raises(MemoryError):
        render(page_file, QUARTER_TURN)

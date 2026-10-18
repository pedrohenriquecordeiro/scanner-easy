import io

import pytest
from PIL import Image, JpegImagePlugin

from digitalizadora.domain.errors import ScanFailedError
from digitalizadora.domain.page_rotation import PageRotation
from digitalizadora.services.page_image_view_service import (
    ENLARGED_VIEW_MAXIMUM_EDGE_PIXELS,
    VIEW_JPEG_QUALITY,
    PageImageViewService,
)
from tests.fakes.synthetic_scans import build_marked_scan_jpeg, find_marker_corner, read_jpeg_size

PAGE_SIZE = (100, 200)
MAXIMUM_EDGE_PIXELS = 480


@pytest.fixture
def service() -> PageImageViewService:
    return PageImageViewService()


@pytest.fixture
def marked_page() -> bytes:
    return build_marked_scan_jpeg(PAGE_SIZE)


def test_the_enlarged_view_is_limited_to_sixteen_hundred_pixels():
    assert ENLARGED_VIEW_MAXIMUM_EDGE_PIXELS == 1600


def test_a_page_smaller_than_the_limit_keeps_its_size(service, marked_page):
    view = service.build_view(marked_page, PageRotation.NONE, MAXIMUM_EDGE_PIXELS)

    assert read_jpeg_size(view) == PAGE_SIZE


def test_a_page_larger_than_the_limit_is_reduced_to_it(service):
    large_page = build_marked_scan_jpeg((1200, 1600))

    view = service.build_view(large_page, PageRotation.NONE, MAXIMUM_EDGE_PIXELS)

    assert max(read_jpeg_size(view)) == MAXIMUM_EDGE_PIXELS


def test_the_reduction_keeps_the_proportions(service):
    large_page = build_marked_scan_jpeg((1200, 1600))

    width, height = read_jpeg_size(service.build_view(large_page, PageRotation.NONE, MAXIMUM_EDGE_PIXELS))

    assert width / height == pytest.approx(0.75, abs=0.01)


def test_a_quarter_turn_swaps_the_dimensions(service, marked_page):
    view = service.build_view(marked_page, PageRotation.CLOCKWISE_90, MAXIMUM_EDGE_PIXELS)

    assert read_jpeg_size(view) == PAGE_SIZE[::-1]


@pytest.mark.parametrize(
    ("rotation", "expected_corner"),
    [
        (PageRotation.NONE, "top-left"),
        (PageRotation.CLOCKWISE_90, "top-right"),
        (PageRotation.HALF_TURN, "bottom-right"),
        (PageRotation.COUNTERCLOCKWISE_90, "bottom-left"),
    ],
)
def test_the_view_is_turned_clockwise(service, marked_page, rotation, expected_corner):
    view = service.build_view(marked_page, rotation, MAXIMUM_EDGE_PIXELS)

    assert find_marker_corner(view) == expected_corner


def test_a_large_page_is_reduced_and_turned(service):
    large_page = build_marked_scan_jpeg((1200, 1600))

    view = service.build_view(large_page, PageRotation.CLOCKWISE_90, MAXIMUM_EDGE_PIXELS)

    assert (read_jpeg_size(view), find_marker_corner(view)) == ((MAXIMUM_EDGE_PIXELS, 360), "top-right")


def test_the_view_is_a_jpeg(service, marked_page):
    assert service.build_view(marked_page, PageRotation.NONE, MAXIMUM_EDGE_PIXELS).startswith(b"\xff\xd8")


def test_the_view_is_encoded_at_the_view_quality(service, marked_page):
    view = service.build_view(marked_page, PageRotation.NONE, MAXIMUM_EDGE_PIXELS)

    with Image.open(io.BytesIO(view)) as image:
        reference = io.BytesIO()
        Image.new("RGB", (8, 8)).save(reference, format="JPEG", quality=VIEW_JPEG_QUALITY)
        assert image.quantization[0][0] == Image.open(io.BytesIO(reference.getvalue())).quantization[0][0]


def test_a_grayscale_page_stays_grayscale(service):
    buffer = io.BytesIO()
    Image.new("L", PAGE_SIZE, 128).save(buffer, format="JPEG")

    view = service.build_view(buffer.getvalue(), PageRotation.NONE, MAXIMUM_EDGE_PIXELS)

    with Image.open(io.BytesIO(view)) as image:
        assert image.mode == "L"


def test_bytes_that_are_not_an_image_raise_scan_failed(service):
    with pytest.raises(ScanFailedError):
        service.build_view(b"not a jpeg", PageRotation.NONE, MAXIMUM_EDGE_PIXELS)


def test_a_truncated_jpeg_raises_scan_failed(service, marked_page):
    with pytest.raises(ScanFailedError):
        service.build_view(marked_page[: len(marked_page) // 2], PageRotation.NONE, MAXIMUM_EDGE_PIXELS)


def test_a_decompression_bomb_raises_scan_failed(service, marked_page, monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1)

    with pytest.raises(ScanFailedError):
        service.build_view(marked_page, PageRotation.NONE, MAXIMUM_EDGE_PIXELS)


def test_the_jpeg_is_decoded_reduced_not_in_full(service, monkeypatch):
    requested_sizes = []
    original_draft = JpegImagePlugin.JpegImageFile.draft

    def recording_draft(image, mode, size):
        requested_sizes.append(size)
        return original_draft(image, mode, size)

    monkeypatch.setattr(JpegImagePlugin.JpegImageFile, "draft", recording_draft)

    service.build_view(build_marked_scan_jpeg((800, 1000)), PageRotation.NONE, MAXIMUM_EDGE_PIXELS)

    assert requested_sizes[0] == (MAXIMUM_EDGE_PIXELS, MAXIMUM_EDGE_PIXELS)

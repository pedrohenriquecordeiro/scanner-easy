import io

import pytest
from PIL import Image, JpegImagePlugin

from digitalizadora.domain.errors import ImageAdjustmentFailedError, ScanFailedError
from digitalizadora.domain.image_adjustment import ImageAdjustment
from digitalizadora.domain.page_rotation import PageRotation
from digitalizadora.services.image_adjustment_service import ImageAdjustmentService
from tests.fakes.synthetic_scans import (
    build_marked_scan_jpeg,
    build_scan_jpeg,
    find_marker_corner,
    read_jpeg_size,
)

PAGE_SIZE = (80, 120)
DARK_LID = (30, 30, 30)
PAPER = (240, 240, 240)
PAPER_BOX = (40, 60, 159, 219)
LID_SIZE = (200, 280)
CROP_MARGIN_RATIO = 0.01
SIZE_TOLERANCE_PIXELS = 8
ROTATE = ImageAdjustment(rotation=PageRotation.CLOCKWISE_90)
CROP = ImageAdjustment(auto_crop=True)


@pytest.fixture
def service() -> ImageAdjustmentService:
    return ImageAdjustmentService()


@pytest.fixture
def marked_page() -> bytes:
    return build_marked_scan_jpeg(PAGE_SIZE)


@pytest.fixture
def sheet_on_dark_lid() -> bytes:
    return build_scan_jpeg(LID_SIZE, [(PAPER_BOX, PAPER)], background=DARK_LID)


def test_an_inactive_adjustment_returns_the_same_bytes(service, marked_page):
    assert service.adjust(marked_page, ImageAdjustment()) is marked_page


@pytest.mark.parametrize(
    ("rotation", "expected_corner"),
    [
        (PageRotation.CLOCKWISE_90, "top-right"),
        (PageRotation.HALF_TURN, "bottom-right"),
        (PageRotation.COUNTERCLOCKWISE_90, "bottom-left"),
    ],
)
def test_the_rotation_turns_the_page_clockwise(service, marked_page, rotation, expected_corner):
    rotated = service.adjust(marked_page, ImageAdjustment(rotation=rotation))

    assert find_marker_corner(rotated) == expected_corner


@pytest.mark.parametrize(
    ("rotation", "expected_size"),
    [
        (PageRotation.CLOCKWISE_90, (120, 80)),
        (PageRotation.HALF_TURN, (80, 120)),
        (PageRotation.COUNTERCLOCKWISE_90, (120, 80)),
    ],
)
def test_a_quarter_turn_swaps_the_dimensions(service, marked_page, rotation, expected_size):
    rotated = service.adjust(marked_page, ImageAdjustment(rotation=rotation))

    assert read_jpeg_size(rotated) == expected_size


def test_four_clockwise_quarter_turns_bring_the_page_back(service, marked_page):
    page = marked_page
    for _ in range(4):
        page = service.adjust(page, ROTATE)

    assert (find_marker_corner(page), read_jpeg_size(page)) == ("top-left", PAGE_SIZE)


def test_the_adjusted_page_is_a_jpeg(service, marked_page):
    assert service.adjust(marked_page, ROTATE).startswith(b"\xff\xd8")


def test_the_crop_removes_the_dark_lid_around_the_sheet(service, sheet_on_dark_lid):
    cropped = service.adjust(sheet_on_dark_lid, CROP)

    margin = round(CROP_MARGIN_RATIO * max(LID_SIZE))
    sheet_size = (PAPER_BOX[2] - PAPER_BOX[0] + 1, PAPER_BOX[3] - PAPER_BOX[1] + 1)
    expected_size = (sheet_size[0] + 2 * margin, sheet_size[1] + 2 * margin)
    width, height = read_jpeg_size(cropped)
    assert abs(width - expected_size[0]) <= SIZE_TOLERANCE_PIXELS
    assert abs(height - expected_size[1]) <= SIZE_TOLERANCE_PIXELS


def test_the_crop_keeps_the_sheet_content(service, sheet_on_dark_lid):
    cropped = service.adjust(sheet_on_dark_lid, CROP)

    with Image.open(io.BytesIO(cropped)) as image:
        center_pixel = image.convert("RGB").getpixel((image.width // 2, image.height // 2))
    assert min(center_pixel) > 200


def test_the_crop_of_a_page_without_a_sheet_returns_the_same_bytes(service, marked_page):
    assert service.adjust(marked_page, CROP) is marked_page


def test_a_page_without_a_sheet_is_still_rotated_when_the_crop_finds_nothing(service, marked_page):
    adjusted = service.adjust(marked_page, ImageAdjustment(rotation=PageRotation.CLOCKWISE_90, auto_crop=True))

    assert read_jpeg_size(adjusted) == (120, 80)


def test_the_crop_happens_before_the_rotation(service, sheet_on_dark_lid):
    cropped_size = read_jpeg_size(service.adjust(sheet_on_dark_lid, CROP))

    adjusted = service.adjust(sheet_on_dark_lid, ImageAdjustment(rotation=PageRotation.CLOCKWISE_90, auto_crop=True))

    assert read_jpeg_size(adjusted) == (cropped_size[1], cropped_size[0])


def test_the_crop_of_a_large_page_maps_the_sheet_from_the_reduced_preview(service):
    large_size = (1600, 2240)
    large_box = (320, 480, 1279, 1759)
    large_page = build_scan_jpeg(large_size, [(large_box, PAPER)], background=DARK_LID)

    width, height = read_jpeg_size(service.adjust(large_page, CROP))

    margin = round(CROP_MARGIN_RATIO * max(large_size))
    assert abs(width - (960 + 2 * margin)) <= 3 * SIZE_TOLERANCE_PIXELS
    assert abs(height - (1280 + 2 * margin)) <= 3 * SIZE_TOLERANCE_PIXELS


@pytest.mark.parametrize("subsampling", [0, 1, 2])
def test_the_chroma_subsampling_of_the_scanner_is_kept(service, subsampling):
    scanned = build_marked_scan_jpeg(PAGE_SIZE, subsampling=subsampling)

    adjusted = service.adjust(scanned, ROTATE)

    with Image.open(io.BytesIO(scanned)) as before, Image.open(io.BytesIO(adjusted)) as after:
        assert JpegImagePlugin.get_sampling(after) == JpegImagePlugin.get_sampling(before)


def test_the_density_of_the_scanner_is_kept(service):
    scanned = build_marked_scan_jpeg(PAGE_SIZE, dpi=(300, 300))

    adjusted = service.adjust(scanned, ROTATE)

    with Image.open(io.BytesIO(adjusted)) as image:
        assert round(image.info["dpi"][0]) == 300


def test_the_colour_profile_of_the_scanner_is_kept(service):
    profile = b"not a real profile but kept byte for byte"
    scanned = build_marked_scan_jpeg(PAGE_SIZE, icc_profile=profile)

    adjusted = service.adjust(scanned, ROTATE)

    with Image.open(io.BytesIO(adjusted)) as image:
        assert image.info["icc_profile"] == profile


def test_a_grayscale_page_stays_grayscale(service):
    buffer = io.BytesIO()
    Image.new("L", PAGE_SIZE, 200).save(buffer, format="JPEG")

    adjusted = service.adjust(buffer.getvalue(), ROTATE)

    with Image.open(io.BytesIO(adjusted)) as image:
        assert image.mode == "L"


def test_running_out_of_memory_becomes_an_adjustment_failure(service, marked_page, monkeypatch):
    def out_of_memory(self: Image.Image, method: Image.Transpose) -> Image.Image:
        raise MemoryError

    monkeypatch.setattr(Image.Image, "transpose", out_of_memory)

    with pytest.raises(ImageAdjustmentFailedError):
        service.adjust(marked_page, ROTATE)


def test_bytes_that_are_not_an_image_become_a_scan_failure(service):
    with pytest.raises(ScanFailedError):
        service.adjust(b"\xff\xd8 not really a jpeg", ROTATE)


def test_a_truncated_jpeg_becomes_a_scan_failure(service, marked_page):
    with pytest.raises(ScanFailedError):
        service.adjust(marked_page[: len(marked_page) // 2], ROTATE)


def test_a_decompression_bomb_becomes_a_scan_failure(service, marked_page, monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1)

    with pytest.raises(ScanFailedError):
        service.adjust(marked_page, ROTATE)

import io
import logging

import pytest
from PIL import Image, ImageDraw, JpegImagePlugin

from digitalizadora.domain.errors import ImageAdjustmentFailedError, ScanFailedError
from digitalizadora.domain.image_adjustment import ImageAdjustment
from digitalizadora.services.image_adjustment_service import ImageAdjustmentService
from digitalizadora.services.page_crop_detection_service import PageCropDetectionService
from tests.fakes.synthetic_scans import (
    build_marked_scan_jpeg,
    build_scan_jpeg,
    read_jpeg_size,
)

PAGE_SIZE = (80, 120)
DARK_LID = (30, 30, 30)
PAPER = (240, 240, 240)
PAPER_BOX = (40, 60, 159, 219)
LID_SIZE = (200, 280)
CROP_MARGIN_RATIO = 0.01
SIZE_TOLERANCE_PIXELS = 8
CROP = ImageAdjustment(auto_crop=True)


@pytest.fixture
def service() -> ImageAdjustmentService:
    return ImageAdjustmentService(PageCropDetectionService())


@pytest.fixture
def marked_page() -> bytes:
    return build_marked_scan_jpeg(PAGE_SIZE)


def build_sheet_on_dark_lid(**save_options: object) -> bytes:
    return build_scan_jpeg(LID_SIZE, [(PAPER_BOX, PAPER)], background=DARK_LID, **save_options)


@pytest.fixture
def sheet_on_dark_lid() -> bytes:
    return build_sheet_on_dark_lid()


def test_an_inactive_adjustment_returns_the_same_bytes(service, marked_page):
    assert service.adjust(marked_page, ImageAdjustment()) is marked_page


def test_the_adjusted_page_is_a_jpeg(service, sheet_on_dark_lid):
    assert service.adjust(sheet_on_dark_lid, CROP).startswith(b"\xff\xd8")


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


def test_the_crop_of_a_page_without_a_sheet_returns_the_same_bytes(service):
    white_page = build_scan_jpeg(PAGE_SIZE)

    assert service.adjust(white_page, CROP) is white_page


def test_a_crop_that_finds_no_sheet_says_so_in_the_log(service, caplog):
    with caplog.at_level(logging.INFO):
        service.adjust(build_scan_jpeg(PAGE_SIZE), CROP)

    assert [record.levelno for record in caplog.records] == [logging.INFO]


def test_a_crop_that_finds_a_sheet_logs_nothing(service, sheet_on_dark_lid, caplog):
    with caplog.at_level(logging.INFO):
        service.adjust(sheet_on_dark_lid, CROP)

    assert caplog.records == []


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
    scanned = build_sheet_on_dark_lid(subsampling=subsampling)

    adjusted = service.adjust(scanned, CROP)

    with Image.open(io.BytesIO(scanned)) as before, Image.open(io.BytesIO(adjusted)) as after:
        assert JpegImagePlugin.get_sampling(after) == JpegImagePlugin.get_sampling(before)


def test_the_density_of_the_scanner_is_kept(service):
    scanned = build_sheet_on_dark_lid(dpi=(300, 300))

    adjusted = service.adjust(scanned, CROP)

    with Image.open(io.BytesIO(adjusted)) as image:
        assert round(image.info["dpi"][0]) == 300


def test_the_colour_profile_of_the_scanner_is_kept(service):
    profile = b"not a real profile but kept byte for byte"
    scanned = build_sheet_on_dark_lid(icc_profile=profile)

    adjusted = service.adjust(scanned, CROP)

    with Image.open(io.BytesIO(adjusted)) as image:
        assert image.info["icc_profile"] == profile


def test_a_grayscale_page_stays_grayscale(service):
    gray_image = Image.new("L", LID_SIZE, DARK_LID[0])
    ImageDraw.Draw(gray_image).rectangle(PAPER_BOX, fill=PAPER[0])
    buffer = io.BytesIO()
    gray_image.save(buffer, format="JPEG")

    adjusted = service.adjust(buffer.getvalue(), CROP)

    with Image.open(io.BytesIO(adjusted)) as image:
        assert image.mode == "L"


def test_running_out_of_memory_becomes_an_adjustment_failure(service, sheet_on_dark_lid, monkeypatch):
    def out_of_memory(self: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
        raise MemoryError

    monkeypatch.setattr(Image.Image, "crop", out_of_memory)

    with pytest.raises(ImageAdjustmentFailedError):
        service.adjust(sheet_on_dark_lid, CROP)


def test_bytes_that_are_not_an_image_become_a_scan_failure(service):
    with pytest.raises(ScanFailedError):
        service.adjust(b"\xff\xd8 not really a jpeg", CROP)


def test_a_truncated_jpeg_becomes_a_scan_failure(service, sheet_on_dark_lid):
    with pytest.raises(ScanFailedError):
        service.adjust(sheet_on_dark_lid[: len(sheet_on_dark_lid) // 2], CROP)


def test_a_decompression_bomb_becomes_a_scan_failure(service, sheet_on_dark_lid, monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1)

    with pytest.raises(ScanFailedError):
        service.adjust(sheet_on_dark_lid, CROP)


def test_the_crop_keeps_a_dark_cover_around_a_bright_picture(service):
    cover_box = (30, 30, 169, 249)
    scan = build_scan_jpeg(
        LID_SIZE,
        [(cover_box, (25, 30, 70)), ((60, 90, 139, 189), (220, 200, 120))],
        background=(40, 40, 40),
    )

    cropped_size = read_jpeg_size(service.adjust(scan, CROP))

    assert cropped_size[0] >= 140

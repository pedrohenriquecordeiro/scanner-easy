import io

import pytest
from PIL import Image

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.image_adjustment import NO_ADJUSTMENT, ImageAdjustment
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.services.image_adjustment_service import ImageAdjustmentService
from digitalizadora.services.jpeg_resolution_service import JpegResolutionService
from digitalizadora.services.master_jpeg_service import MasterJpegService
from tests.fakes.synthetic_scans import build_marked_scan_jpeg, build_scan_jpeg, read_jpeg_size

PAGE_SIZE = (80, 120)
LID_SIZE = (200, 280)
DARK_LID = (30, 30, 30)
PAPER = (240, 240, 240)
PAPER_BOX = (40, 60, 159, 219)
CROP = ImageAdjustment(auto_crop=True)
SETTINGS = ScanSettings(600, ColorMode.COLOR)


@pytest.fixture
def master_jpeg_service() -> MasterJpegService:
    return MasterJpegService(ImageAdjustmentService(), JpegResolutionService())


def build_request(adjustment: ImageAdjustment = NO_ADJUSTMENT) -> ScanRequest:
    return ScanRequest(SETTINGS, OutputFormat.JPEG, adjustment)


def read_density(jpeg_content: bytes) -> tuple[float, float]:
    with Image.open(io.BytesIO(jpeg_content)) as image:
        return image.info["dpi"]


def test_without_adjustment_the_result_is_the_scanner_image_with_the_requested_density(master_jpeg_service):
    scanned = build_marked_scan_jpeg(PAGE_SIZE, dpi=(72, 72))

    master = master_jpeg_service.build_master_jpeg(scanned, build_request())

    assert master == JpegResolutionService().with_resolution(scanned, SETTINGS.dots_per_inch)


def test_the_requested_density_is_written_after_a_crop(master_jpeg_service):
    scanned = build_scan_jpeg(LID_SIZE, [(PAPER_BOX, PAPER)], background=DARK_LID, dpi=(72, 72))

    master = master_jpeg_service.build_master_jpeg(scanned, build_request(CROP))

    assert read_density(master) == (600, 600)


def test_the_adjustment_of_the_request_is_applied(master_jpeg_service):
    scanned = build_scan_jpeg(LID_SIZE, [(PAPER_BOX, PAPER)], background=DARK_LID)

    master = master_jpeg_service.build_master_jpeg(scanned, build_request(CROP))

    assert read_jpeg_size(master)[0] < LID_SIZE[0]

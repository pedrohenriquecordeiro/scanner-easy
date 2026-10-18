import io
from datetime import datetime, timedelta, timezone

import pikepdf
import pytest
from PIL import Image

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import ScanFailedError
from digitalizadora.domain.image_adjustment import NO_ADJUSTMENT, ImageAdjustment
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_job import ScanJob
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.services.image_adjustment_service import ImageAdjustmentService
from digitalizadora.services.jpeg_resolution_service import JpegResolutionService
from digitalizadora.services.master_jpeg_service import MasterJpegService
from digitalizadora.services.page_crop_detection_service import PageCropDetectionService
from digitalizadora.services.pdf_assembly_service import PdfAssemblyService
from digitalizadora.services.scan_encoder import ScanEncoder
from digitalizadora.services.thumbnail_service import THUMBNAIL_MAXIMUM_EDGE_PIXELS, ThumbnailService
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.jpeg_segments import declare_image_size, strip_jfif_segment
from tests.fakes.sample_images import build_sample_jpeg
from tests.fakes.synthetic_scans import build_scan_jpeg

STARTED_AT = datetime(2026, 10, 13, 15, 30, 12, tzinfo=timezone(timedelta(hours=-3)))
START_OF_IMAGE = b"\xff\xd8"
START_OF_SCAN_MARKER = b"\xff\xda"
POINT_TOLERANCE = 0.01
DECOMPRESSION_BOMB_EDGE_PIXELS = 60000


def build_encoder() -> ScanEncoder:
    master_jpeg_service = MasterJpegService(ImageAdjustmentService(PageCropDetectionService()), JpegResolutionService())
    return ScanEncoder(master_jpeg_service, PdfAssemblyService(), ThumbnailService())


def build_job(
    output_format: OutputFormat, dots_per_inch: int = 300, adjustment: ImageAdjustment = NO_ADJUSTMENT
) -> ScanJob:
    request = ScanRequest(ScanSettings(dots_per_inch, ColorMode.COLOR), output_format, adjustment)
    return ScanJob(request, FixedClock(STARTED_AT).now())


def build_scanned_image(width_pixels: int = 64, height_pixels: int = 48) -> ScannedImage:
    return ScannedImage(build_sample_jpeg(width_pixels, height_pixels), "image/jpeg")


def build_scanned_image_without_jfif(width_pixels: int = 64, height_pixels: int = 48) -> ScannedImage:
    return ScannedImage(strip_jfif_segment(build_sample_jpeg(width_pixels, height_pixels)), "image/jpeg")


def read_jpeg_size(jpeg_content: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(jpeg_content)) as image:
        return image.size


def test_jpeg_output_carries_the_requested_density():
    encoded = build_encoder().encode(build_scanned_image(), build_job(OutputFormat.JPEG, 600))

    with Image.open(io.BytesIO(encoded.content)) as image:
        assert image.info["dpi"] == (600, 600)


def test_jpeg_output_gets_the_requested_density_when_the_scan_had_no_jfif():
    encoded = build_encoder().encode(build_scanned_image_without_jfif(), build_job(OutputFormat.JPEG, 600))

    with Image.open(io.BytesIO(encoded.content)) as image:
        assert image.info["dpi"] == (600, 600)


def test_jpeg_output_keeps_the_scanned_pixels():
    scanned_image = build_scanned_image()

    encoded = build_encoder().encode(scanned_image, build_job(OutputFormat.JPEG))

    original_scan = scanned_image.content[scanned_image.content.index(START_OF_SCAN_MARKER):]
    assert encoded.content[encoded.content.index(START_OF_SCAN_MARKER):] == original_scan


def test_output_format_is_propagated():
    encoded = build_encoder().encode(build_scanned_image(), build_job(OutputFormat.JPEG))

    assert encoded.output_format is OutputFormat.JPEG


def test_created_at_is_the_job_start():
    encoded = build_encoder().encode(build_scanned_image(), build_job(OutputFormat.JPEG))

    assert encoded.created_at == STARTED_AT


def test_thumbnail_is_a_jpeg_limited_to_the_thumbnail_edge():
    scanned_image = build_scanned_image(width_pixels=1000, height_pixels=800)

    encoded = build_encoder().encode(scanned_image, build_job(OutputFormat.JPEG))

    assert encoded.thumbnail_jpeg.startswith(START_OF_IMAGE)
    assert max(read_jpeg_size(encoded.thumbnail_jpeg)) == THUMBNAIL_MAXIMUM_EDGE_PIXELS


def test_wrong_media_type_raises_scan_failed():
    scanned_image = ScannedImage(build_sample_jpeg(), "image/png")

    with pytest.raises(ScanFailedError):
        build_encoder().encode(scanned_image, build_job(OutputFormat.JPEG))


UNEXPECTED_CONTENTS = [
    b"",
    b"%PDF-1.4 not an image",
    build_sample_jpeg()[:-30],
    declare_image_size(build_sample_jpeg(), DECOMPRESSION_BOMB_EDGE_PIXELS, DECOMPRESSION_BOMB_EDGE_PIXELS),
]


@pytest.mark.parametrize("unexpected_content", UNEXPECTED_CONTENTS)
def test_unexpected_content_raises_scan_failed(unexpected_content):
    scanned_image = ScannedImage(unexpected_content, "image/jpeg")

    with pytest.raises(ScanFailedError):
        build_encoder().encode(scanned_image, build_job(OutputFormat.JPEG))


def read_pdf_page_size(pdf_content: bytes) -> tuple[float, float]:
    with pikepdf.open(io.BytesIO(pdf_content)) as pdf:
        _, _, width, height = [float(value) for value in pdf.pages[0].mediabox]
    return width, height


def test_pdf_output_has_one_page():
    encoded = build_encoder().encode(build_scanned_image(), build_job(OutputFormat.PDF))

    with pikepdf.open(io.BytesIO(encoded.content)) as pdf:
        assert len(pdf.pages) == 1


def test_pdf_title_carries_the_job_start_time():
    encoded = build_encoder().encode(build_scanned_image(), build_job(OutputFormat.PDF))

    with pikepdf.open(io.BytesIO(encoded.content)) as pdf:
        assert str(pdf.docinfo["/Title"]) == "Digitalização 2026-10-13 15:30:12"


def test_pdf_page_size_follows_the_requested_resolution():
    scanned_image = build_scanned_image(width_pixels=600, height_pixels=300)

    encoded = build_encoder().encode(scanned_image, build_job(OutputFormat.PDF, dots_per_inch=600))

    assert read_pdf_page_size(encoded.content) == pytest.approx((72.0, 36.0), abs=POINT_TOLERANCE)


def test_pdf_page_size_is_right_for_a_scan_without_jfif():
    scanned_image = build_scanned_image_without_jfif(width_pixels=600, height_pixels=300)

    encoded = build_encoder().encode(scanned_image, build_job(OutputFormat.PDF, dots_per_inch=600))

    assert read_pdf_page_size(encoded.content) == pytest.approx((72.0, 36.0), abs=POINT_TOLERANCE)


def test_pdf_output_still_builds_a_thumbnail():
    encoded = build_encoder().encode(build_scanned_image(), build_job(OutputFormat.PDF))

    assert encoded.thumbnail_jpeg.startswith(START_OF_IMAGE)


def test_pdf_output_reports_the_pdf_format():
    encoded = build_encoder().encode(build_scanned_image(), build_job(OutputFormat.PDF))

    assert encoded.output_format is OutputFormat.PDF


def test_truncated_jpeg_is_rejected_even_when_a_pdf_is_requested():
    truncated_image = ScannedImage(build_sample_jpeg()[:-30], "image/jpeg")

    with pytest.raises(ScanFailedError):
        build_encoder().encode(truncated_image, build_job(OutputFormat.PDF))


DARK_LID = (30, 30, 30)
PAPER = (240, 240, 240)
LID_SIZE = (200, 280)
PAPER_BOX = (40, 60, 159, 219)


CROP = ImageAdjustment(auto_crop=True)
SHEET_ON_DARK_LID = ScannedImage(build_scan_jpeg(LID_SIZE, [(PAPER_BOX, PAPER)], background=DARK_LID), "image/jpeg")


def test_the_crop_reaches_the_jpeg_output():
    encoded = build_encoder().encode(SHEET_ON_DARK_LID, build_job(OutputFormat.JPEG, adjustment=CROP))

    width, height = read_jpeg_size(encoded.content)
    assert width < LID_SIZE[0] and height < LID_SIZE[1]


def test_the_crop_reaches_the_pdf_with_the_physical_size_of_the_cropped_region():
    cropped_jpeg = build_encoder().encode(SHEET_ON_DARK_LID, build_job(OutputFormat.JPEG, 200, CROP)).content
    cropped_width, cropped_height = read_jpeg_size(cropped_jpeg)

    encoded = build_encoder().encode(SHEET_ON_DARK_LID, build_job(OutputFormat.PDF, 200, CROP))

    expected_size = (cropped_width * 72 / 200, cropped_height * 72 / 200)
    assert read_pdf_page_size(encoded.content) == pytest.approx(expected_size, abs=POINT_TOLERANCE)


def test_the_density_is_written_after_the_crop():
    job = build_job(OutputFormat.JPEG, dots_per_inch=600, adjustment=CROP)

    encoded = build_encoder().encode(SHEET_ON_DARK_LID, job)

    with Image.open(io.BytesIO(encoded.content)) as image:
        assert image.info["dpi"] == (600, 600)

import io
from datetime import datetime, timedelta, timezone

import pikepdf
import pytest
from PIL import Image

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import ScanFailedError
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_job import ScanJob
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.services.jpeg_resolution_service import JpegResolutionService
from digitalizadora.services.pdf_assembly_service import PdfAssemblyService
from digitalizadora.services.scan_encoder import OutputIdentity, ScanEncoder
from digitalizadora.services.thumbnail_service import THUMBNAIL_MAXIMUM_EDGE_PIXELS, ThumbnailService
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.jpeg_segments import declare_image_size, strip_jfif_segment
from tests.fakes.sample_images import build_sample_jpeg

STARTED_AT = datetime(2026, 10, 13, 15, 30, 12, tzinfo=timezone(timedelta(hours=-3)))
START_OF_IMAGE = b"\xff\xd8"
START_OF_SCAN_MARKER = b"\xff\xda"
POINT_TOLERANCE = 0.01
DECOMPRESSION_BOMB_EDGE_PIXELS = 60000


def build_encoder() -> ScanEncoder:
    return ScanEncoder(JpegResolutionService(), PdfAssemblyService(), ThumbnailService())


def build_job(dots_per_inch: int = 300) -> ScanJob:
    request = ScanRequest(ScanSettings(dots_per_inch, ColorMode.COLOR), OutputFormat.JPEG)
    return ScanJob(request, FixedClock(STARTED_AT).now())


def build_identity(output_format: OutputFormat, dots_per_inch: int = 300) -> OutputIdentity:
    return OutputIdentity(STARTED_AT, dots_per_inch, output_format)


def build_scanned_image(width_pixels: int = 64, height_pixels: int = 48) -> ScannedImage:
    return ScannedImage(build_sample_jpeg(width_pixels, height_pixels), "image/jpeg")


def build_scanned_image_without_jfif(width_pixels: int = 64, height_pixels: int = 48) -> ScannedImage:
    return ScannedImage(strip_jfif_segment(build_sample_jpeg(width_pixels, height_pixels)), "image/jpeg")


def read_jpeg_size(jpeg_content: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(jpeg_content)) as image:
        return image.size


def read_pdf_page_size(pdf_content: bytes) -> tuple[float, float]:
    with pikepdf.open(io.BytesIO(pdf_content)) as pdf:
        _, _, width, height = [float(value) for value in pdf.pages[0].mediabox]
    return width, height


def test_the_master_carries_the_requested_density():
    master = build_encoder().encode_master(build_scanned_image(), build_job(600))

    with Image.open(io.BytesIO(master.jpeg_content)) as image:
        assert image.info["dpi"] == (600, 600)


def test_the_master_gets_the_requested_density_when_the_scan_had_no_jfif():
    master = build_encoder().encode_master(build_scanned_image_without_jfif(), build_job(600))

    with Image.open(io.BytesIO(master.jpeg_content)) as image:
        assert image.info["dpi"] == (600, 600)


def test_the_master_keeps_the_scanned_pixels():
    scanned_image = build_scanned_image()

    master = build_encoder().encode_master(scanned_image, build_job())

    original_scan = scanned_image.content[scanned_image.content.index(START_OF_SCAN_MARKER) :]
    assert master.jpeg_content[master.jpeg_content.index(START_OF_SCAN_MARKER) :] == original_scan


def test_the_thumbnail_is_a_jpeg_limited_to_the_thumbnail_edge():
    scanned_image = build_scanned_image(width_pixels=1000, height_pixels=800)

    master = build_encoder().encode_master(scanned_image, build_job())

    assert master.thumbnail_jpeg.startswith(START_OF_IMAGE)
    assert max(read_jpeg_size(master.thumbnail_jpeg)) == THUMBNAIL_MAXIMUM_EDGE_PIXELS


def test_wrong_media_type_raises_scan_failed():
    scanned_image = ScannedImage(build_sample_jpeg(), "image/png")

    with pytest.raises(ScanFailedError):
        build_encoder().encode_master(scanned_image, build_job())


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
        build_encoder().encode_master(scanned_image, build_job())


def test_a_jpeg_output_is_the_image_as_it_is():
    output_jpeg = build_sample_jpeg()

    encoded = build_encoder().wrap_output(output_jpeg, build_identity(OutputFormat.JPEG))

    assert encoded.content == output_jpeg


def test_the_output_format_is_propagated():
    encoded = build_encoder().wrap_output(build_sample_jpeg(), build_identity(OutputFormat.JPEG))

    assert encoded.output_format is OutputFormat.JPEG


def test_created_at_is_the_identity_moment():
    encoded = build_encoder().wrap_output(build_sample_jpeg(), build_identity(OutputFormat.JPEG))

    assert encoded.created_at == STARTED_AT


def test_a_pdf_output_has_one_page():
    encoded = build_encoder().wrap_output(build_sample_jpeg(), build_identity(OutputFormat.PDF))

    with pikepdf.open(io.BytesIO(encoded.content)) as pdf:
        assert len(pdf.pages) == 1


def test_the_pdf_title_carries_the_moment_of_the_scan():
    encoded = build_encoder().wrap_output(build_sample_jpeg(), build_identity(OutputFormat.PDF))

    with pikepdf.open(io.BytesIO(encoded.content)) as pdf:
        assert str(pdf.docinfo["/Title"]) == "Digitalização 2026-10-13 15:30:12"


def test_the_pdf_page_size_follows_the_density_of_the_identity():
    output_jpeg = build_scanned_image(width_pixels=600, height_pixels=300).content

    encoded = build_encoder().wrap_output(output_jpeg, build_identity(OutputFormat.PDF, dots_per_inch=600))

    assert read_pdf_page_size(encoded.content) == pytest.approx((72.0, 36.0), abs=POINT_TOLERANCE)


def test_the_pdf_page_size_is_right_for_an_output_without_jfif():
    output_jpeg = build_scanned_image_without_jfif(width_pixels=600, height_pixels=300).content

    encoded = build_encoder().wrap_output(output_jpeg, build_identity(OutputFormat.PDF, dots_per_inch=600))

    assert read_pdf_page_size(encoded.content) == pytest.approx((72.0, 36.0), abs=POINT_TOLERANCE)


def test_the_pdf_reports_the_pdf_format():
    encoded = build_encoder().wrap_output(build_sample_jpeg(), build_identity(OutputFormat.PDF))

    assert encoded.output_format is OutputFormat.PDF

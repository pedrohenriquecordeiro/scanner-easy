import io
from datetime import datetime, timedelta, timezone

import pikepdf
import pytest
from PIL import Image, JpegImagePlugin

from digitalizadora.domain.errors import ImageAdjustmentFailedError, SavedScanUnreadableError
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.services import scan_content_rotator
from digitalizadora.services.pdf_assembly_service import PdfAssemblyService, PdfDocumentSpecification
from digitalizadora.services.scan_content_rotator import ScanContentRotator
from tests.fakes.synthetic_scans import build_marked_scan_jpeg, find_marker_corner, read_jpeg_size

PAGE_SIZE = (100, 200)
DOTS_PER_INCH = 300
ICC_PROFILE = b"not a real profile but kept byte for byte"
CREATED_AT = datetime(2026, 10, 18, 9, 0, 0, tzinfo=timezone(timedelta(hours=-3)))
TITLE = "Digitalização de teste"


@pytest.fixture
def rotator() -> ScanContentRotator:
    return ScanContentRotator()


@pytest.fixture
def marked_jpeg() -> bytes:
    return build_marked_scan_jpeg(PAGE_SIZE, dpi=(DOTS_PER_INCH, DOTS_PER_INCH))


@pytest.fixture
def scanned_pdf(marked_jpeg: bytes) -> bytes:
    specification = PdfDocumentSpecification(dots_per_inch=DOTS_PER_INCH, title=TITLE, created_at=CREATED_AT)
    return PdfAssemblyService().build_pdf([marked_jpeg], specification)


def turn_jpeg(rotator: ScanContentRotator, content: bytes) -> bytes:
    return rotator.rotate_clockwise(content, OutputFormat.JPEG)


def turn_pdf(rotator: ScanContentRotator, content: bytes) -> bytes:
    return rotator.rotate_clockwise(content, OutputFormat.PDF)


def read_rotation_of_the_page(pdf_content: bytes) -> int:
    with pikepdf.open(io.BytesIO(pdf_content)) as document:
        return int(document.pages[0].obj.get("/Rotate", 0)) % 360


def read_image_stream(pdf_content: bytes) -> bytes:
    with pikepdf.open(io.BytesIO(pdf_content)) as document:
        return next(iter(document.pages[0].get_images().values())).read_raw_bytes()


def test_a_jpeg_turns_a_quarter_clockwise(rotator, marked_jpeg):
    turned = turn_jpeg(rotator, marked_jpeg)

    assert (read_jpeg_size(turned), find_marker_corner(turned)) == (PAGE_SIZE[::-1], "top-right")


def test_two_turns_of_a_jpeg_make_a_half_turn(rotator, marked_jpeg):
    turned = turn_jpeg(rotator, turn_jpeg(rotator, marked_jpeg))

    assert (read_jpeg_size(turned), find_marker_corner(turned)) == (PAGE_SIZE, "bottom-right")


def test_four_turns_of_a_jpeg_bring_the_corner_back(rotator, marked_jpeg):
    turned = marked_jpeg
    for _ in range(4):
        turned = turn_jpeg(rotator, turned)

    assert (read_jpeg_size(turned), find_marker_corner(turned)) == (PAGE_SIZE, "top-left")


def test_a_turned_jpeg_keeps_the_density_of_the_file(rotator, marked_jpeg):
    with Image.open(io.BytesIO(turn_jpeg(rotator, marked_jpeg))) as image:
        assert round(image.info["dpi"][0]) == DOTS_PER_INCH


def test_a_turned_jpeg_keeps_the_colour_profile_of_the_file(rotator):
    turned = turn_jpeg(rotator, build_marked_scan_jpeg(PAGE_SIZE, icc_profile=ICC_PROFILE))

    with Image.open(io.BytesIO(turned)) as image:
        assert image.info["icc_profile"] == ICC_PROFILE


@pytest.mark.parametrize("subsampling", [0, 1, 2])
def test_a_turned_jpeg_keeps_the_chroma_subsampling_of_the_file(rotator, subsampling):
    scanned = build_marked_scan_jpeg(PAGE_SIZE, subsampling=subsampling)

    turned = turn_jpeg(rotator, scanned)

    with Image.open(io.BytesIO(scanned)) as before, Image.open(io.BytesIO(turned)) as after:
        assert JpegImagePlugin.get_sampling(after) == JpegImagePlugin.get_sampling(before)


def test_a_grayscale_jpeg_stays_grayscale(rotator):
    buffer = io.BytesIO()
    Image.new("L", PAGE_SIZE, 200).save(buffer, format="JPEG")

    with Image.open(io.BytesIO(turn_jpeg(rotator, buffer.getvalue()))) as image:
        assert image.mode == "L"


def test_a_pdf_gets_a_quarter_turn_on_its_page(rotator, scanned_pdf):
    assert read_rotation_of_the_page(turn_pdf(rotator, scanned_pdf)) == 90


def test_two_turns_of_a_pdf_make_a_half_turn(rotator, scanned_pdf):
    assert read_rotation_of_the_page(turn_pdf(rotator, turn_pdf(rotator, scanned_pdf))) == 180


def test_four_turns_of_a_pdf_bring_the_rotation_back(rotator, scanned_pdf):
    turned = scanned_pdf
    for _ in range(4):
        turned = turn_pdf(rotator, turned)

    assert read_rotation_of_the_page(turned) == 0


def test_a_turned_pdf_keeps_the_image_stream_untouched(rotator, scanned_pdf):
    assert read_image_stream(turn_pdf(rotator, scanned_pdf)) == read_image_stream(scanned_pdf)


def test_a_turned_pdf_keeps_the_page_size_in_points(rotator, scanned_pdf):
    with pikepdf.open(io.BytesIO(turn_pdf(rotator, scanned_pdf))) as turned_document:
        turned_box = [float(value) for value in turned_document.pages[0].mediabox]
    with pikepdf.open(io.BytesIO(scanned_pdf)) as document:
        original_box = [float(value) for value in document.pages[0].mediabox]

    assert turned_box == original_box


def test_a_turned_pdf_keeps_its_title(rotator, scanned_pdf):
    with pikepdf.open(io.BytesIO(turn_pdf(rotator, scanned_pdf))) as document:
        assert str(document.docinfo["/Title"]) == TITLE


def test_a_turned_pdf_keeps_its_creation_date(rotator, scanned_pdf):
    with pikepdf.open(io.BytesIO(turn_pdf(rotator, scanned_pdf))) as document:
        assert str(document.docinfo["/CreationDate"]) == "D:20261018120000Z"


def test_a_turned_pdf_still_has_a_single_page(rotator, scanned_pdf):
    with pikepdf.open(io.BytesIO(turn_pdf(rotator, scanned_pdf))) as document:
        assert len(document.pages) == 1


@pytest.mark.parametrize("output_format", list(OutputFormat))
@pytest.mark.parametrize("unreadable_content", [b"", b"not a file", b"\xff\xd8 not really a jpeg", b"%PDF-1.7 broken"])
def test_content_that_cannot_be_read_raises_saved_scan_unreadable(rotator, output_format, unreadable_content):
    with pytest.raises(SavedScanUnreadableError):
        rotator.rotate_clockwise(unreadable_content, output_format)


def test_a_truncated_jpeg_raises_saved_scan_unreadable(rotator, marked_jpeg):
    with pytest.raises(SavedScanUnreadableError):
        turn_jpeg(rotator, marked_jpeg[: len(marked_jpeg) // 2])


def test_a_decompression_bomb_raises_saved_scan_unreadable(rotator, marked_jpeg, monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1)

    with pytest.raises(SavedScanUnreadableError):
        turn_jpeg(rotator, marked_jpeg)


def test_running_out_of_memory_while_turning_a_jpeg_raises_image_adjustment_failed(rotator, marked_jpeg, monkeypatch):
    def exhaust_memory(*arguments: object) -> object:
        raise MemoryError

    monkeypatch.setattr(scan_content_rotator, "replace_with", exhaust_memory)

    with pytest.raises(ImageAdjustmentFailedError):
        turn_jpeg(rotator, marked_jpeg)

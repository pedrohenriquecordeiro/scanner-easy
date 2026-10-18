import io
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pikepdf
import pytest
from PIL import Image

from digitalizadora.domain.errors import ScanFailedError
from digitalizadora.services.pdf_assembly_service import (
    DEFAULT_PDF_TITLE_TEMPLATE,
    PdfAssemblyService,
    PdfDocumentMetadata,
    PdfDocumentSpecification,
)
from tests.fakes.jpeg_segments import declare_image_size, strip_jfif_segment
from tests.fakes.sample_images import build_sample_jpeg

A4_WIDTH_PIXELS_AT_300_DOTS_PER_INCH = 2550
A4_HEIGHT_PIXELS_AT_300_DOTS_PER_INCH = 3507
A4_WIDTH_IN_POINTS = 612.0
A4_HEIGHT_IN_POINTS = 841.68
POINT_TOLERANCE = 0.01
DECOMPRESSION_BOMB_EDGE_PIXELS = 60000
CREATED_AT = datetime(2026, 10, 13, 15, 30, 12, tzinfo=timezone(timedelta(hours=-3)))
TITLE = "Digitalização 2026-10-13 15:30:12"
SPECIFICATION = PdfDocumentSpecification(dots_per_inch=300, title=TITLE, created_at=CREATED_AT)


@pytest.fixture(scope="module")
def a4_jpeg_at_300_dots_per_inch() -> bytes:
    image = Image.new("RGB", (A4_WIDTH_PIXELS_AT_300_DOTS_PER_INCH, A4_HEIGHT_PIXELS_AT_300_DOTS_PER_INCH), "gray")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def open_pdf(pdf_content: bytes) -> pikepdf.Pdf:
    return pikepdf.open(io.BytesIO(pdf_content))


def read_page_size(pdf_content: bytes) -> tuple[float, float]:
    with open_pdf(pdf_content) as pdf:
        _, _, width, height = [float(value) for value in pdf.pages[0].mediabox]
    return width, height


def test_a4_page_has_the_size_of_the_glass_at_the_fixed_resolution(a4_jpeg_at_300_dots_per_inch):
    pdf_content = PdfAssemblyService().build_pdf([a4_jpeg_at_300_dots_per_inch], SPECIFICATION)

    with open_pdf(pdf_content) as pdf:
        left, bottom, width, height = [float(value) for value in pdf.pages[0].mediabox]
    assert (left, bottom) == (0.0, 0.0)
    assert width == pytest.approx(A4_WIDTH_IN_POINTS, abs=POINT_TOLERANCE)
    assert height == pytest.approx(A4_HEIGHT_IN_POINTS, abs=POINT_TOLERANCE)


def test_page_size_ignores_the_density_stored_in_the_jpeg():
    jpeg_stored_at_72 = build_sample_jpeg(width_pixels=300, height_pixels=150, dots_per_inch=72)

    pdf_content = PdfAssemblyService().build_pdf([jpeg_stored_at_72], SPECIFICATION)

    assert read_page_size(pdf_content) == pytest.approx((72.0, 36.0), abs=POINT_TOLERANCE)


def test_page_size_of_a_jpeg_without_jfif_follows_the_fixed_resolution():
    jpeg_without_jfif = strip_jfif_segment(build_sample_jpeg(width_pixels=300, height_pixels=150))

    pdf_content = PdfAssemblyService().build_pdf([jpeg_without_jfif], SPECIFICATION)

    assert read_page_size(pdf_content) == pytest.approx((72.0, 36.0), abs=POINT_TOLERANCE)


def test_each_jpeg_becomes_one_page():
    pages = [build_sample_jpeg(), build_sample_jpeg()]

    pdf_content = PdfAssemblyService().build_pdf(pages, SPECIFICATION)

    with open_pdf(pdf_content) as pdf:
        assert len(pdf.pages) == 2


def test_jpeg_is_embedded_without_recompression():
    jpeg_content = build_sample_jpeg()

    pdf_content = PdfAssemblyService().build_pdf([jpeg_content], SPECIFICATION)

    with open_pdf(pdf_content) as pdf:
        image_stream = next(iter(pdf.pages[0].get_images().values()))
        assert str(image_stream["/Filter"]) == "/DCTDecode"
        assert image_stream.read_raw_bytes() == jpeg_content


def test_title_is_stored_in_the_document_information():
    pdf_content = PdfAssemblyService().build_pdf([build_sample_jpeg()], SPECIFICATION)

    with open_pdf(pdf_content) as pdf:
        assert str(pdf.docinfo["/Title"]) == TITLE


def test_creator_is_digitalizadora():
    pdf_content = PdfAssemblyService().build_pdf([build_sample_jpeg()], SPECIFICATION)

    with open_pdf(pdf_content) as pdf:
        assert str(pdf.docinfo["/Creator"]) == "Digitalizadora"


def test_creation_date_is_stored_in_universal_time():
    pdf_content = PdfAssemblyService().build_pdf([build_sample_jpeg()], SPECIFICATION)

    with open_pdf(pdf_content) as pdf:
        assert str(pdf.docinfo["/CreationDate"]) == "D:20261013183012Z"


def test_empty_page_list_raises_scan_failed():
    with pytest.raises(ScanFailedError):
        PdfAssemblyService().build_pdf([], SPECIFICATION)


UNREADABLE_PAGES = [
    b"",
    b"not an image",
    build_sample_jpeg()[:10],
    declare_image_size(build_sample_jpeg(), DECOMPRESSION_BOMB_EDGE_PIXELS, DECOMPRESSION_BOMB_EDGE_PIXELS),
]


@pytest.mark.parametrize("unreadable_page", UNREADABLE_PAGES)
def test_unreadable_page_raises_scan_failed(unreadable_page):
    with pytest.raises(ScanFailedError):
        PdfAssemblyService().build_pdf([unreadable_page], SPECIFICATION)


DOCUMENT_METADATA = PdfDocumentMetadata(title="Contrato do apartamento", created_at=CREATED_AT)
ONE_INCH_IN_POINTS = 72.0
HALF_INCH_IN_POINTS = 36.0


def write_page_files(folder: Path, jpeg_pages: list[bytes]) -> list[Path]:
    page_files = []
    for position, jpeg_page in enumerate(jpeg_pages, 1):
        page_file = folder / f"page-{position}.jpg"
        page_file.write_bytes(jpeg_page)
        page_files.append(page_file)
    return page_files


def write_streamed_pdf(page_files: list[Path]) -> bytes:
    output_stream = io.BytesIO()
    PdfAssemblyService().write_pdf_at_embedded_resolutions(page_files, DOCUMENT_METADATA, output_stream)
    return output_stream.getvalue()


def read_all_page_sizes(pdf_content: bytes) -> list[float]:
    """Width and height of every page, in order, flattened: [width 1, height 1, width 2, height 2...]."""
    with open_pdf(pdf_content) as pdf:
        return [float(pdf_page.mediabox[corner]) for pdf_page in pdf.pages for corner in (2, 3)]


def test_default_title_template_names_the_moment():
    assert DEFAULT_PDF_TITLE_TEMPLATE.format(moment=CREATED_AT) == TITLE


def test_streamed_pages_of_300_and_600_dots_per_inch_have_the_same_physical_size(tmp_path):
    page_at_300 = build_sample_jpeg(width_pixels=300, height_pixels=150, dots_per_inch=300)
    page_at_600 = build_sample_jpeg(width_pixels=600, height_pixels=300, dots_per_inch=600)

    pdf_content = write_streamed_pdf(write_page_files(tmp_path, [page_at_300, page_at_600]))

    assert read_all_page_sizes(pdf_content) == pytest.approx(
        [ONE_INCH_IN_POINTS, HALF_INCH_IN_POINTS, ONE_INCH_IN_POINTS, HALF_INCH_IN_POINTS], abs=POINT_TOLERANCE
    )


def test_streamed_pages_keep_the_given_order(tmp_path):
    jpeg_pages = [
        build_sample_jpeg(width_pixels=144, height_pixels=72, dots_per_inch=72),
        build_sample_jpeg(width_pixels=72, height_pixels=72, dots_per_inch=72),
        build_sample_jpeg(width_pixels=216, height_pixels=72, dots_per_inch=72),
    ]

    pdf_content = write_streamed_pdf(write_page_files(tmp_path, jpeg_pages))

    assert read_all_page_sizes(pdf_content)[::2] == pytest.approx([144.0, 72.0, 216.0], abs=POINT_TOLERANCE)


def test_streamed_jpeg_is_embedded_without_recompression(tmp_path):
    jpeg_content = build_sample_jpeg(dots_per_inch=300)

    pdf_content = write_streamed_pdf(write_page_files(tmp_path, [jpeg_content]))

    with open_pdf(pdf_content) as pdf:
        image_stream = next(iter(pdf.pages[0].get_images().values()))
        assert image_stream.read_raw_bytes() == jpeg_content


def test_streamed_pdf_stores_the_title_of_the_metadata(tmp_path):
    pdf_content = write_streamed_pdf(write_page_files(tmp_path, [build_sample_jpeg()]))

    with open_pdf(pdf_content) as pdf:
        assert str(pdf.docinfo["/Title"]) == "Contrato do apartamento"


def test_streamed_pdf_stores_the_creation_date_in_universal_time(tmp_path):
    pdf_content = write_streamed_pdf(write_page_files(tmp_path, [build_sample_jpeg()]))

    with open_pdf(pdf_content) as pdf:
        assert str(pdf.docinfo["/CreationDate"]) == "D:20261013183012Z"


def test_streamed_pdf_creator_is_digitalizadora(tmp_path):
    pdf_content = write_streamed_pdf(write_page_files(tmp_path, [build_sample_jpeg()]))

    with open_pdf(pdf_content) as pdf:
        assert str(pdf.docinfo["/Creator"]) == "Digitalizadora"


def test_streamed_pdf_without_pages_raises_scan_failed():
    with pytest.raises(ScanFailedError):
        write_streamed_pdf([])


def test_page_file_that_is_not_an_image_raises_scan_failed(tmp_path):
    with pytest.raises(ScanFailedError):
        write_streamed_pdf(write_page_files(tmp_path, [b"not an image"]))


def test_page_file_that_vanished_raises_scan_failed(tmp_path):
    with pytest.raises(ScanFailedError):
        write_streamed_pdf([tmp_path / "page-1.jpg"])

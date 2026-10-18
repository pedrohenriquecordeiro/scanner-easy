import io
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import BinaryIO

import pikepdf
import pytest

from digitalizadora.domain.document_draft_reconciliation import page_file_name
from digitalizadora.domain.errors import ScanFailedError
from digitalizadora.domain.page_framing import PageFraming
from digitalizadora.domain.page_rotation import PageRotation
from digitalizadora.repositories.file_system_document_draft_repository import CURRENT_DRAFT_FOLDER_NAME
from digitalizadora.services.document_pdf_assembler import DocumentAssemblyInput, DocumentPdfAssembler
from digitalizadora.services.page_framing_renderer import FrameRenderRequest, PageFramingRenderer
from digitalizadora.services.pdf_assembly_service import PdfAssemblyService, PdfDocumentMetadata
from tests.fakes.document_drafts import DRAFT_CREATED_AT, seed_draft_folder
from tests.fakes.page_crops import rectangle
from tests.fakes.sample_images import build_sample_jpeg

FINALIZED_AT = DRAFT_CREATED_AT + timedelta(minutes=5)
METADATA = PdfDocumentMetadata(title="Contrato", created_at=FINALIZED_AT)
DOTS_PER_INCH = 72
WIDE_PAGE = build_sample_jpeg(width_pixels=144, height_pixels=72, dots_per_inch=DOTS_PER_INCH)
SQUARE_PAGE = build_sample_jpeg(width_pixels=72, height_pixels=72, dots_per_inch=DOTS_PER_INCH)
POINT_TOLERANCE = 1.0
JPEG_QUALITY = 90


class RecordingPageRenderer(PageFramingRenderer):
    def __init__(self) -> None:
        self.requests: list[FrameRenderRequest] = []

    def render_jpeg(self, master: BinaryIO, request: FrameRenderRequest) -> bytes:
        self.requests.append(request)
        return super().render_jpeg(master, request)


def seed_input(tmp_path: Path, page_contents: list[bytes], framings: list[PageFraming]) -> DocumentAssemblyInput:
    drafts_folder = tmp_path / "drafts"
    draft = seed_draft_folder(drafts_folder, page_contents)
    for page_identifier, framing in zip(draft.page_identifiers, framings, strict=True):
        draft = draft.with_page_framing(page_identifier, framing)
    draft_folder = drafts_folder / CURRENT_DRAFT_FOLDER_NAME
    page_files = [draft_folder / page_file_name(page_identifier) for page_identifier in draft.page_identifiers]
    return DocumentAssemblyInput(draft, page_files, FINALIZED_AT, JPEG_QUALITY)


def write_pdf(assembly_input: DocumentAssemblyInput, renderer: PageFramingRenderer | None = None) -> bytes:
    output_stream = io.BytesIO()
    assembler = DocumentPdfAssembler(renderer or PageFramingRenderer(), PdfAssemblyService())
    assembler.write_pdf(assembly_input, METADATA, output_stream)
    return output_stream.getvalue()


def read_page_sizes(pdf_content: bytes) -> list[tuple[float, float]]:
    with pikepdf.open(io.BytesIO(pdf_content)) as pdf:
        return [(float(page.mediabox[2]), float(page.mediabox[3])) for page in pdf.pages]


def test_a_page_without_framing_is_embedded_without_recompression(tmp_path):
    pdf_content = write_pdf(seed_input(tmp_path, [WIDE_PAGE], [PageFraming()]))

    with pikepdf.open(io.BytesIO(pdf_content)) as pdf:
        assert next(iter(pdf.pages[0].get_images().values())).read_raw_bytes() == WIDE_PAGE


def test_a_rotated_page_has_the_turned_physical_size(tmp_path):
    pdf_content = write_pdf(seed_input(tmp_path, [WIDE_PAGE], [PageFraming(rotation=PageRotation.CLOCKWISE_90)]))

    assert read_page_sizes(pdf_content) == [pytest.approx((72.0, 144.0), abs=POINT_TOLERANCE)]


def test_a_cropped_page_has_the_physical_size_of_the_region(tmp_path):
    framing = PageFraming(crops=(rectangle(0.0, 0.0, 0.5, 1.0),))

    pdf_content = write_pdf(seed_input(tmp_path, [WIDE_PAGE], [framing]))

    assert read_page_sizes(pdf_content) == [pytest.approx((72.0, 72.0), abs=POINT_TOLERANCE)]


def test_a_cropped_and_rotated_page_has_the_size_of_the_turned_region(tmp_path):
    framing = PageFraming(PageRotation.CLOCKWISE_90, (rectangle(0.0, 0.0, 0.5, 1.0),))

    pdf_content = write_pdf(seed_input(tmp_path, [WIDE_PAGE], [framing]))

    assert read_page_sizes(pdf_content) == [pytest.approx((36.0, 144.0), abs=POINT_TOLERANCE)]


def test_the_pages_keep_the_order_of_the_draft(tmp_path):
    framings = [PageFraming(), PageFraming(rotation=PageRotation.CLOCKWISE_90), PageFraming()]

    pdf_content = write_pdf(seed_input(tmp_path, [WIDE_PAGE, WIDE_PAGE, SQUARE_PAGE], framings))

    assert [width for width, _ in read_page_sizes(pdf_content)] == pytest.approx(
        [144.0, 72.0, 72.0], abs=POINT_TOLERANCE
    )


def test_each_page_is_rendered_once_and_in_order(tmp_path):
    renderer = RecordingPageRenderer()
    framings = [PageFraming(), PageFraming(rotation=PageRotation.HALF_TURN)]
    assembly_input = seed_input(tmp_path, [WIDE_PAGE, SQUARE_PAGE], framings)

    write_pdf(assembly_input, renderer)

    assert renderer.requests == [FrameRenderRequest(framing, 0, JPEG_QUALITY) for framing in framings]


def test_the_quality_of_the_assembly_reaches_the_renderer(tmp_path):
    renderer = RecordingPageRenderer()
    assembly_input = seed_input(tmp_path, [WIDE_PAGE], [PageFraming(rotation=PageRotation.HALF_TURN)])

    write_pdf(replace(assembly_input, jpeg_quality=61), renderer)

    assert [request.jpeg_quality for request in renderer.requests] == [61]


TWO_SIDE_BY_SIDE_CROPS = PageFraming(crops=(rectangle(0.0, 0.0, 0.5, 1.0), rectangle(0.5, 0.0, 1.0, 1.0)))


def test_a_page_with_two_crops_gives_two_pdf_pages(tmp_path):
    pdf_content = write_pdf(seed_input(tmp_path, [WIDE_PAGE], [TWO_SIDE_BY_SIDE_CROPS]))

    assert len(read_page_sizes(pdf_content)) == 2


def test_each_pdf_page_of_a_page_with_two_crops_has_the_size_of_its_region(tmp_path):
    framing = PageFraming(crops=(rectangle(0.0, 0.0, 0.25, 1.0), rectangle(0.5, 0.0, 1.0, 1.0)))

    pdf_content = write_pdf(seed_input(tmp_path, [WIDE_PAGE], [framing]))

    assert read_page_sizes(pdf_content) == [
        pytest.approx((36.0, 72.0), abs=POINT_TOLERANCE),
        pytest.approx((72.0, 72.0), abs=POINT_TOLERANCE),
    ]


def test_the_frames_of_a_page_are_rendered_one_by_one_in_order(tmp_path):
    renderer = RecordingPageRenderer()

    write_pdf(seed_input(tmp_path, [WIDE_PAGE, SQUARE_PAGE], [TWO_SIDE_BY_SIDE_CROPS, PageFraming()]), renderer)

    assert [request.frame_index for request in renderer.requests] == [0, 1, 0]


def test_the_pages_after_a_page_with_two_crops_keep_their_place(tmp_path):
    framings = [TWO_SIDE_BY_SIDE_CROPS, PageFraming()]

    pdf_content = write_pdf(seed_input(tmp_path, [WIDE_PAGE, SQUARE_PAGE], framings))

    assert [width for width, _ in read_page_sizes(pdf_content)] == pytest.approx(
        [72.0, 72.0, 72.0], abs=POINT_TOLERANCE
    )


def test_a_page_that_cannot_be_read_raises_scan_failed(tmp_path):
    assembly_input = seed_input(tmp_path, [WIDE_PAGE], [PageFraming(rotation=PageRotation.CLOCKWISE_90)])
    assembly_input.page_files[0].write_bytes(b"not a jpeg")

    with pytest.raises(ScanFailedError):
        write_pdf(assembly_input)


def test_a_draft_without_pages_raises_scan_failed(tmp_path):
    one_page_draft = seed_input(tmp_path, [WIDE_PAGE], [PageFraming()]).draft
    empty_input = DocumentAssemblyInput(one_page_draft.without_last_page(), [], FINALIZED_AT, JPEG_QUALITY)

    with pytest.raises(ScanFailedError):
        write_pdf(empty_input)

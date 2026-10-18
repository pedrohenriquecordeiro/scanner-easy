import io
from datetime import timedelta
from pathlib import Path

import pikepdf
import pytest

from digitalizadora.domain.document_draft_reconciliation import page_file_name
from digitalizadora.domain.errors import ScanFailedError
from digitalizadora.domain.page_crop import RectangleCrop
from digitalizadora.domain.page_framing import PageFraming
from digitalizadora.domain.page_rotation import PageRotation
from digitalizadora.repositories.file_system_document_draft_repository import CURRENT_DRAFT_FOLDER_NAME
from digitalizadora.services.document_page_renderer import DocumentPageRenderer
from digitalizadora.services.document_pdf_assembler import DocumentAssemblyInput, DocumentPdfAssembler
from digitalizadora.services.pdf_assembly_service import PdfAssemblyService, PdfDocumentMetadata
from tests.fakes.document_drafts import DRAFT_CREATED_AT, seed_draft_folder
from tests.fakes.sample_images import build_sample_jpeg

FINALIZED_AT = DRAFT_CREATED_AT + timedelta(minutes=5)
METADATA = PdfDocumentMetadata(title="Contrato", created_at=FINALIZED_AT)
DOTS_PER_INCH = 72
WIDE_PAGE = build_sample_jpeg(width_pixels=144, height_pixels=72, dots_per_inch=DOTS_PER_INCH)
SQUARE_PAGE = build_sample_jpeg(width_pixels=72, height_pixels=72, dots_per_inch=DOTS_PER_INCH)
POINT_TOLERANCE = 1.0


class RecordingPageRenderer(DocumentPageRenderer):
    def __init__(self) -> None:
        self.rendered_file_names: list[str] = []

    def render_jpeg(self, page_file: Path, framing: PageFraming) -> bytes:
        self.rendered_file_names.append(page_file.name)
        return super().render_jpeg(page_file, framing)


def seed_input(tmp_path: Path, page_contents: list[bytes], framings: list[PageFraming]) -> DocumentAssemblyInput:
    drafts_folder = tmp_path / "drafts"
    draft = seed_draft_folder(drafts_folder, page_contents)
    for page_identifier, framing in zip(draft.page_identifiers, framings, strict=True):
        draft = draft.with_page_framing(page_identifier, framing)
    draft_folder = drafts_folder / CURRENT_DRAFT_FOLDER_NAME
    page_files = [draft_folder / page_file_name(page_identifier) for page_identifier in draft.page_identifiers]
    return DocumentAssemblyInput(draft, page_files, FINALIZED_AT)


def write_pdf(assembly_input: DocumentAssemblyInput, renderer: DocumentPageRenderer | None = None) -> bytes:
    output_stream = io.BytesIO()
    assembler = DocumentPdfAssembler(renderer or DocumentPageRenderer(), PdfAssemblyService())
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
    framing = PageFraming(crop=RectangleCrop(0.0, 0.0, 0.5, 1.0))

    pdf_content = write_pdf(seed_input(tmp_path, [WIDE_PAGE], [framing]))

    assert read_page_sizes(pdf_content) == [pytest.approx((72.0, 72.0), abs=POINT_TOLERANCE)]


def test_a_cropped_and_rotated_page_has_the_size_of_the_turned_region(tmp_path):
    framing = PageFraming(PageRotation.CLOCKWISE_90, RectangleCrop(0.0, 0.0, 0.5, 1.0))

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
    assembly_input = seed_input(tmp_path, [WIDE_PAGE, SQUARE_PAGE], [PageFraming(), PageFraming()])

    write_pdf(assembly_input, renderer)

    assert renderer.rendered_file_names == [page_file.name for page_file in assembly_input.page_files]


def test_a_page_that_cannot_be_read_raises_scan_failed(tmp_path):
    assembly_input = seed_input(tmp_path, [WIDE_PAGE], [PageFraming(rotation=PageRotation.CLOCKWISE_90)])
    assembly_input.page_files[0].write_bytes(b"not a jpeg")

    with pytest.raises(ScanFailedError):
        write_pdf(assembly_input)


def test_a_draft_without_pages_raises_scan_failed(tmp_path):
    one_page_draft = seed_input(tmp_path, [WIDE_PAGE], [PageFraming()]).draft
    empty_input = DocumentAssemblyInput(one_page_draft.without_last_page(), [], FINALIZED_AT)

    with pytest.raises(ScanFailedError):
        write_pdf(empty_input)

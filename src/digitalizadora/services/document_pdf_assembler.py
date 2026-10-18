from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from digitalizadora.domain.document_draft import DocumentDraft
from digitalizadora.services.page_framing_renderer import FrameRenderRequest, PageFramingRenderer
from digitalizadora.services.pdf_assembly_service import PdfAssemblyService, PdfDocumentMetadata
from digitalizadora.services.rendered_page_source import RenderedPageSource


@dataclass(frozen=True)
class DocumentAssemblyInput:
    """What the PDF is made of: the draft, its checked page files (one per page, in order), the moment and the
    quality of the JPEG of every page that has to be written again."""

    draft: DocumentDraft
    page_files: Sequence[Path]
    finalized_at: datetime
    jpeg_quality: int


class DocumentPdfAssembler:
    """Writes the PDF of a draft, rendering each page with its rotation and crops at the moment it is needed.

    A page with two crops gives two pages of the PDF, in the reading order of the crops."""

    def __init__(self, page_renderer: PageFramingRenderer, pdf_assembly_service: PdfAssemblyService) -> None:
        self._page_renderer = page_renderer
        self._pdf_assembly_service = pdf_assembly_service

    def write_pdf(
        self, assembly_input: DocumentAssemblyInput, metadata: PdfDocumentMetadata, output_stream: BinaryIO
    ) -> None:
        page_sources = []
        for page, page_file in zip(assembly_input.draft.pages, assembly_input.page_files, strict=True):
            for frame_index in range(page.framing.output_count):
                request = FrameRenderRequest(page.framing, frame_index, assembly_input.jpeg_quality)
                page_sources.append(RenderedPageSource(self._page_renderer, page_file, request))
        self._pdf_assembly_service.write_pdf_from_sources(page_sources, metadata, output_stream)

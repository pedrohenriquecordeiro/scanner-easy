from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from digitalizadora.domain.document_draft import DocumentDraft
from digitalizadora.services.document_page_renderer import DocumentPageRenderer
from digitalizadora.services.pdf_assembly_service import PdfAssemblyService, PdfDocumentMetadata
from digitalizadora.services.rendered_page_source import RenderedPageSource


@dataclass(frozen=True)
class DocumentAssemblyInput:
    """What the PDF is made of: the draft, its checked page files (one per page, in order) and the moment."""

    draft: DocumentDraft
    page_files: Sequence[Path]
    finalized_at: datetime


class DocumentPdfAssembler:
    """Writes the PDF of a draft, rendering each page with its rotation and crop at the moment it is needed."""

    def __init__(self, page_renderer: DocumentPageRenderer, pdf_assembly_service: PdfAssemblyService) -> None:
        self._page_renderer = page_renderer
        self._pdf_assembly_service = pdf_assembly_service

    def write_pdf(
        self, assembly_input: DocumentAssemblyInput, metadata: PdfDocumentMetadata, output_stream: BinaryIO
    ) -> None:
        page_sources = [
            RenderedPageSource(self._page_renderer, page_file, page.framing)
            for page, page_file in zip(assembly_input.draft.pages, assembly_input.page_files, strict=True)
        ]
        self._pdf_assembly_service.write_pdf_from_sources(page_sources, metadata, output_stream)

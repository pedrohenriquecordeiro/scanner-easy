import functools
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from digitalizadora.domain.document_draft import DocumentDraft
from digitalizadora.domain.document_pdf_to_save import DocumentPdfToSave
from digitalizadora.domain.errors import DocumentAssemblyFailedError, DocumentTooLargeError, ScanFailedError
from digitalizadora.domain.ports import ScanOutputRepository
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.services.pdf_assembly_service import (
    DEFAULT_PDF_TITLE_TEMPLATE,
    PdfAssemblyService,
    PdfDocumentMetadata,
)
from digitalizadora.services.storage_guard_service import StorageGuardService


@dataclass(frozen=True)
class DocumentAssemblyInput:
    """What the finalizer needs to write the PDF: the draft, its checked page files and the moment."""

    draft: DocumentDraft
    page_files: Sequence[Path]
    finalized_at: datetime


def _build_document_title(draft: DocumentDraft) -> str:
    if draft.name:
        return draft.name
    return DEFAULT_PDF_TITLE_TEMPLATE.format(moment=draft.created_at)


class DocumentFinalizer:
    """Checks the output folder and writes the PDF of a draft. Synchronous: it runs in a worker thread."""

    def __init__(
        self,
        pdf_assembly_service: PdfAssemblyService,
        scan_output_repository: ScanOutputRepository,
        storage_guard_service: StorageGuardService,
    ) -> None:
        self._pdf_assembly_service = pdf_assembly_service
        self._scan_output_repository = scan_output_repository
        self._storage_guard_service = storage_guard_service

    def ensure_capacity(self, draft: DocumentDraft) -> None:
        """The folder first: a disconnected disk is reported before any page is checked (6.6.3, step 3)."""
        self._scan_output_repository.ensure_output_folder_ready()
        self._storage_guard_service.ensure_space_for_file(
            self._scan_output_repository.output_folder(), draft.estimated_size_in_bytes
        )

    def write_document(self, assembly_input: DocumentAssemblyInput) -> ScanResult:
        """Streams the PDF into the output folder under a free name; folder and space errors pass unchanged."""
        draft = assembly_input.draft
        metadata = PdfDocumentMetadata(title=_build_document_title(draft), created_at=assembly_input.finalized_at)
        write_content = functools.partial(
            self._pdf_assembly_service.write_pdf_at_embedded_resolutions, assembly_input.page_files, metadata
        )
        document_pdf = DocumentPdfToSave(
            write_content=write_content, created_at=assembly_input.finalized_at, document_name=draft.name
        )
        try:
            return self._scan_output_repository.save_document(document_pdf)
        except ScanFailedError as error:
            raise DocumentAssemblyFailedError(f"A stored page could not be assembled: {error}") from error
        except MemoryError as error:
            raise DocumentTooLargeError("Not enough free memory to assemble the document") from error

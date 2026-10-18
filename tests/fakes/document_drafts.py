from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path

from digitalizadora.domain.documents.document_draft import DocumentDraft, DocumentPage
from digitalizadora.domain.documents.document_draft_reconciliation import (
    MANIFEST_FILE_NAME,
    page_file_name,
    thumbnail_file_name,
)
from digitalizadora.domain.scanning.color_mode import ColorMode
from digitalizadora.repositories.documents.document_manifest_codec import encode_manifest
from digitalizadora.repositories.documents.file_system_document_draft_repository import CURRENT_DRAFT_FOLDER_NAME

DRAFT_CREATED_AT = datetime(2026, 10, 17, 10, 0, 0, tzinfo=timezone(timedelta(hours=-3)))
DEFAULT_PAGE_SIZE_IN_BYTES = 3
SAMPLE_DOTS_PER_INCH = 300
SAMPLE_COLOR_MODE = ColorMode.COLOR
FIRST_PAGE_POSITION = 1


def page_identifier_at(position: int) -> str:
    """The identifier of the page at a 1-based position of build_document_draft: "0000000000000001"..."""
    return f"{position:016x}"


def build_document_page(page_identifier: str, size_in_bytes: int = DEFAULT_PAGE_SIZE_IN_BYTES) -> DocumentPage:
    return DocumentPage(
        page_identifier=page_identifier,
        scanned_at=DRAFT_CREATED_AT,
        dots_per_inch=SAMPLE_DOTS_PER_INCH,
        color_mode=SAMPLE_COLOR_MODE,
        size_in_bytes=size_in_bytes,
    )


def build_document_draft(page_count: int) -> DocumentDraft:
    pages = tuple(
        build_document_page(page_identifier_at(position))
        for position in range(FIRST_PAGE_POSITION, page_count + FIRST_PAGE_POSITION)
    )
    return DocumentDraft(name="", created_at=DRAFT_CREATED_AT, pages=pages)


PAGE_FILLER_BYTE = b"p"


def _write_draft_files(drafts_folder: Path, draft: DocumentDraft, page_contents: Sequence[bytes]) -> None:
    draft_folder = drafts_folder / CURRENT_DRAFT_FOLDER_NAME
    draft_folder.mkdir(parents=True, exist_ok=True)
    for page, page_content in zip(draft.pages, page_contents, strict=True):
        (draft_folder / page_file_name(page.page_identifier)).write_bytes(page_content)
        (draft_folder / thumbnail_file_name(page.page_identifier)).write_bytes(page_content)
    (draft_folder / MANIFEST_FILE_NAME).write_bytes(encode_manifest(draft))


def write_draft_folder(drafts_folder: Path, draft: DocumentDraft) -> None:
    """The manifest of the draft plus, for each page, a page file of the recorded size and a thumbnail."""
    _write_draft_files(drafts_folder, draft, [PAGE_FILLER_BYTE * page.size_in_bytes for page in draft.pages])


def seed_draft_folder(drafts_folder: Path, page_contents: Sequence[bytes]) -> DocumentDraft:
    """A draft whose pages hold the given contents (real JPEGs), in order; the thumbnail repeats the page."""
    pages = tuple(
        build_document_page(page_identifier_at(position), len(page_content))
        for position, page_content in enumerate(page_contents, FIRST_PAGE_POSITION)
    )
    draft = DocumentDraft(name="", created_at=DRAFT_CREATED_AT, pages=pages)
    _write_draft_files(drafts_folder, draft, page_contents)
    return draft

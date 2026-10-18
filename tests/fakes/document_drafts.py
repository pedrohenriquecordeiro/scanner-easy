from datetime import datetime, timedelta, timezone

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.document_draft import DocumentDraft, DocumentPage

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

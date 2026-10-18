import re
import secrets
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from pathlib import Path

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import EmptyDocumentError, InvalidPageOrderError, PageNotFoundError
from digitalizadora.domain.image_adjustment import RENDERED_SIZE_FACTOR
from digitalizadora.domain.page_framing import UNFRAMED, PageFraming
from digitalizadora.domain.scan_result import ScanResult

PAGE_IDENTIFIER_PATTERN = re.compile(r"[0-9a-f]{16}")
PAGE_IDENTIFIER_SIZE_IN_BYTES = 8
DRAFT_SESSION_SIZE_IN_BYTES = 8
FIRST_PAGE_POSITION = 1


def generate_page_identifier() -> str:
    return secrets.token_hex(PAGE_IDENTIFIER_SIZE_IN_BYTES)


def generate_draft_session() -> str:
    return secrets.token_hex(DRAFT_SESSION_SIZE_IN_BYTES)


def is_page_identifier(text: str) -> bool:
    return isinstance(text, str) and PAGE_IDENTIFIER_PATTERN.fullmatch(text) is not None


@dataclass(frozen=True)
class DocumentPage:
    page_identifier: str
    scanned_at: datetime
    dots_per_inch: int
    color_mode: ColorMode
    size_in_bytes: int
    # Last field with a default: every five-argument construction keeps working and means an unframed page.
    framing: PageFraming = UNFRAMED


@dataclass(frozen=True)
class DocumentPageFiles:
    page_identifier: str
    jpeg_content: bytes
    thumbnail_jpeg: bytes


def _is_exact_permutation(requested_order: tuple[object, ...], current_order: tuple[str, ...]) -> bool:
    if not all(isinstance(page_identifier, str) for page_identifier in requested_order):
        return False
    return len(requested_order) == len(current_order) and set(requested_order) == set(current_order)


@dataclass(frozen=True)
class DocumentDraft:
    """The draft in progress; the order of pages is the order of the final PDF.

    Every content change returns a new draft without both finalization markers, because a PDF
    written before the change no longer matches the draft.
    """

    name: str
    created_at: datetime
    pages: tuple[DocumentPage, ...]
    finalization_started_at: datetime | None = None
    finished_document: ScanResult | None = None

    @classmethod
    def start(cls, first_page: DocumentPage) -> "DocumentDraft":
        return cls(name="", created_at=first_page.scanned_at, pages=(first_page,))

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def output_page_count(self) -> int:
        """The pages of the PDF: a page with two crops gives two."""
        return sum(page.framing.output_count for page in self.pages)

    @property
    def page_identifiers(self) -> tuple[str, ...]:
        return tuple(page.page_identifier for page in self.pages)

    @property
    def estimated_size_in_bytes(self) -> int:
        return sum(page.size_in_bytes for page in self.pages)

    def estimate_document_size_in_bytes(self) -> int:
        """What the PDF may take: the pages that need rendering come out re-encoded at the fixed quality."""
        return sum(
            page.size_in_bytes * (RENDERED_SIZE_FACTOR if page.framing.needs_rendering else 1) for page in self.pages
        )

    def position_of(self, page_identifier: str) -> int:
        if page_identifier not in self.page_identifiers:
            raise PageNotFoundError(f"Page {page_identifier!r} is not in the draft")
        return self.page_identifiers.index(page_identifier) + FIRST_PAGE_POSITION

    def with_page_appended(self, page: DocumentPage) -> "DocumentDraft":
        return self._with_content(self.name, (*self.pages, page))

    def with_page_framing(self, page_identifier: str, framing: PageFraming) -> "DocumentDraft":
        framed_position = self.position_of(page_identifier)
        return self._with_content(
            self.name,
            tuple(
                replace(page, framing=framing) if position == framed_position else page
                for position, page in enumerate(self.pages, FIRST_PAGE_POSITION)
            ),
        )

    def without_page(self, page_identifier: str) -> "DocumentDraft":
        removed_position = self.position_of(page_identifier)
        remaining_pages = tuple(
            page for position, page in enumerate(self.pages, FIRST_PAGE_POSITION) if position != removed_position
        )
        return self._with_content(self.name, remaining_pages)

    def without_last_page(self) -> "DocumentDraft":
        if not self.pages:
            raise EmptyDocumentError("The draft has no page to discard")
        return self._with_content(self.name, self.pages[:-1])

    def reordered(self, page_identifiers: Sequence[str]) -> "DocumentDraft":
        requested_order = tuple(page_identifiers)
        if not _is_exact_permutation(requested_order, self.page_identifiers):
            raise InvalidPageOrderError(f"{list(requested_order)!r} is not a permutation of the draft pages")
        pages_by_identifier = {page.page_identifier: page for page in self.pages}
        return self._with_content(self.name, tuple(pages_by_identifier[identifier] for identifier in requested_order))

    def renamed(self, document_name: str) -> "DocumentDraft":
        return self._with_content(document_name, self.pages)

    def with_finalization_started(self, started_at: datetime) -> "DocumentDraft":
        return replace(self, finalization_started_at=started_at)

    def without_finalization_marker(self) -> "DocumentDraft":
        return replace(self, finalization_started_at=None)

    def marked_finished(self, finished_document: ScanResult) -> "DocumentDraft":
        return replace(self, finished_document=finished_document)

    def _with_content(self, name: str, pages: tuple[DocumentPage, ...]) -> "DocumentDraft":
        return DocumentDraft(name=name, created_at=self.created_at, pages=pages)


@dataclass(frozen=True)
class DocumentFinalizationResult:
    result: ScanResult
    page_count: int


class RecoveryOutcome(str, Enum):
    RESUMED = "resumed"
    PAGES_LOST = "pages_lost"
    SET_ASIDE = "set_aside"
    FAILED = "failed"


@dataclass(frozen=True)
class DraftRecoveryReport:
    outcome: RecoveryOutcome
    kept_page_count: int
    dropped_page_positions: tuple[int, ...]
    set_aside_folder: Path | None


@dataclass(frozen=True)
class DraftSnapshot:
    """Replaced as a whole in a single assignment, so a reader on another thread sees a coherent state."""

    draft_session: str
    revision: int
    draft: DocumentDraft | None
    recovery_report: DraftRecoveryReport | None = None
    last_finished_document: DocumentFinalizationResult | None = None

from datetime import datetime
from pathlib import Path
from typing import Any

from digitalizadora.domain.document_draft import (
    DocumentDraft,
    DocumentFinalizationResult,
    DocumentPage,
    DraftRecoveryReport,
    DraftSnapshot,
)
from digitalizadora.services.document_draft_store import DraftStorageState

EMPTY_PAGE_COUNT = 0
EMPTY_SIZE_IN_BYTES = 0


def build_document_body(draft_snapshot: DraftSnapshot) -> dict[str, Any]:
    """The document body of 6.5, shared by GET /api/document and every edit."""
    return {
        "draft_session": draft_snapshot.draft_session,
        "revision": draft_snapshot.revision,
        "document": _describe_draft(draft_snapshot.draft),
        "recovery": _describe_recovery(draft_snapshot.recovery_report),
        "last_finished_document": _describe_finished_document(draft_snapshot.last_finished_document),
    }


def build_document_summary_body(draft_snapshot: DraftSnapshot, draft_storage: DraftStorageState) -> dict[str, Any]:
    """The "document" key of /api/state: always an object, with zero pages when there is no draft (R8, R20)."""
    draft = draft_snapshot.draft
    return {
        "draft_session": draft_snapshot.draft_session,
        "revision": draft_snapshot.revision,
        "page_count": EMPTY_PAGE_COUNT if draft is None else draft.page_count,
        "estimated_size_in_bytes": EMPTY_SIZE_IN_BYTES if draft is None else draft.estimated_size_in_bytes,
        "draft_storage": {
            "free_space_in_bytes": draft_storage.free_space_in_bytes,
            "estimated_pages_remaining": draft_storage.estimated_pages_remaining,
            "available": draft_storage.available,
        },
    }


def _moment_text(moment: datetime | None) -> str | None:
    return None if moment is None else moment.isoformat()


def _path_text(path: Path | None) -> str | None:
    return None if path is None else str(path)


def _describe_draft(draft: DocumentDraft | None) -> dict[str, Any] | None:
    if draft is None:
        return None
    finished_document = draft.finished_document
    return {
        "name": draft.name,
        "created_at": draft.created_at.isoformat(),
        "page_count": draft.page_count,
        "estimated_size_in_bytes": draft.estimated_size_in_bytes,
        "finalization_started_at": _moment_text(draft.finalization_started_at),
        "finished_document_path": None if finished_document is None else str(finished_document.output_path),
        "pages": [_describe_page(page) for page in draft.pages],
    }


def _describe_page(page: DocumentPage) -> dict[str, Any]:
    return {
        "page_identifier": page.page_identifier,
        "scanned_at": page.scanned_at.isoformat(),
        "dots_per_inch": page.dots_per_inch,
        "color_mode": page.color_mode.value,
        "size_in_bytes": page.size_in_bytes,
    }


def _describe_recovery(recovery_report: DraftRecoveryReport | None) -> dict[str, Any] | None:
    if recovery_report is None:
        return None
    return {
        "outcome": recovery_report.outcome.value,
        "kept_page_count": recovery_report.kept_page_count,
        "dropped_page_positions": list(recovery_report.dropped_page_positions),
        "set_aside_folder": _path_text(recovery_report.set_aside_folder),
    }


def _describe_finished_document(finalization: DocumentFinalizationResult | None) -> dict[str, Any] | None:
    if finalization is None:
        return None
    result = finalization.result
    return {
        "file_name": result.output_path.name,
        "output_folder": str(result.output_path.parent),
        "page_count": finalization.page_count,
        "size_in_bytes": result.size_in_bytes,
        "finalized_at": result.scanned_at.isoformat(),
    }

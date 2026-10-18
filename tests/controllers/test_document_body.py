from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from digitalizadora.controllers.document_body import build_document_body, build_document_summary_body
from digitalizadora.domain.document_draft import (
    DocumentFinalizationResult,
    DraftRecoveryReport,
    DraftSnapshot,
    RecoveryOutcome,
)
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.page_framing import PageFraming
from digitalizadora.domain.page_rotation import PageRotation
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.services.document_draft_store import UNAVAILABLE_DRAFT_STORAGE_STATE, DraftStorageState
from tests.fakes.document_drafts import build_document_draft, page_identifier_at
from tests.fakes.page_crops import quadrilateral, rectangle

DRAFT_SESSION = "5c0f9a2e7b1d4c38"
REVISION = 4
FINALIZED_AT = datetime(2026, 10, 17, 10, 5, 30, tzinfo=timezone(timedelta(hours=-3)))
FINISHED_DOCUMENT = ScanResult(
    output_path=Path("/Volumes/External/scans/Contrato do apartamento.pdf"),
    output_format=OutputFormat.PDF,
    scanned_at=FINALIZED_AT,
    size_in_bytes=1612246,
)
DRAFT_STORAGE = DraftStorageState(free_space_in_bytes=80_000_000_000, estimated_pages_remaining=9000, available=True)
EMPTY_SNAPSHOT = DraftSnapshot(draft_session=DRAFT_SESSION, revision=REVISION, draft=None)
TWO_PAGE_SNAPSHOT = DraftSnapshot(
    draft_session=DRAFT_SESSION,
    revision=REVISION,
    draft=replace(build_document_draft(2), name="Contrato do apartamento"),
)
RESUMED_REPORT = DraftRecoveryReport(
    outcome=RecoveryOutcome.RESUMED, kept_page_count=2, dropped_page_positions=(3,), set_aside_folder=None
)
SET_ASIDE_REPORT = DraftRecoveryReport(
    outcome=RecoveryOutcome.SET_ASIDE,
    kept_page_count=0,
    dropped_page_positions=(),
    set_aside_folder=Path("/Users/digitalizadora/drafts/set-aside-20261017-100000-1a2b3c4d"),
)


def test_body_without_a_draft_has_only_the_session_and_the_revision() -> None:
    assert build_document_body(EMPTY_SNAPSHOT) == {
        "draft_session": DRAFT_SESSION,
        "revision": REVISION,
        "document": None,
        "recovery": None,
        "last_finished_document": None,
    }


def test_body_keys_come_in_the_documented_order() -> None:
    assert list(build_document_body(TWO_PAGE_SNAPSHOT)) == [
        "draft_session",
        "revision",
        "document",
        "recovery",
        "last_finished_document",
    ]


def test_document_describes_the_draft_and_its_pages_in_order() -> None:
    assert build_document_body(TWO_PAGE_SNAPSHOT)["document"] == {
        "name": "Contrato do apartamento",
        "created_at": "2026-10-17T10:00:00-03:00",
        "page_count": 2,
        "estimated_size_in_bytes": 6,
        "finalization_started_at": None,
        "finished_document_path": None,
        "pages": [
            {
                "page_identifier": page_identifier_at(1),
                "scanned_at": "2026-10-17T10:00:00-03:00",
                "dots_per_inch": 300,
                "color_mode": "color",
                "size_in_bytes": 3,
                "rotation_degrees": 0,
                "crops": [],
            },
            {
                "page_identifier": page_identifier_at(2),
                "scanned_at": "2026-10-17T10:00:00-03:00",
                "dots_per_inch": 300,
                "color_mode": "color",
                "size_in_bytes": 3,
                "rotation_degrees": 0,
                "crops": [],
            },
        ],
    }


def test_a_framed_page_reports_its_crops_with_the_four_corners() -> None:
    draft = TWO_PAGE_SNAPSHOT.draft.with_page_framing(
        page_identifier_at(2),
        PageFraming(
            PageRotation.NONE,
            (quadrilateral((0.039, 0.28), (0.65, 0.019), (0.894, 0.321), (0.282, 0.582)),),
        ),
    )

    page = build_document_body(replace(TWO_PAGE_SNAPSHOT, draft=draft))["document"]["pages"][1]

    assert page["crops"] == [
        {
            "top_left": {"x": 0.039, "y": 0.28},
            "top_right": {"x": 0.65, "y": 0.019},
            "bottom_right": {"x": 0.894, "y": 0.321},
            "bottom_left": {"x": 0.282, "y": 0.582},
        }
    ]


def test_a_framed_page_reports_its_rotation() -> None:
    draft = TWO_PAGE_SNAPSHOT.draft.with_page_framing(
        page_identifier_at(2), PageFraming(PageRotation.CLOCKWISE_90, (rectangle((0.13, 0.115, 0.924, 0.925)),))
    )

    page = build_document_body(replace(TWO_PAGE_SNAPSHOT, draft=draft))["document"]["pages"][1]

    assert page["rotation_degrees"] == 90


def test_document_keys_come_in_the_documented_order() -> None:
    assert list(build_document_body(TWO_PAGE_SNAPSHOT)["document"]) == [
        "name",
        "created_at",
        "page_count",
        "estimated_size_in_bytes",
        "finalization_started_at",
        "finished_document_path",
        "pages",
    ]


def test_document_reports_the_finalization_intention_moment() -> None:
    draft = TWO_PAGE_SNAPSHOT.draft.with_finalization_started(FINALIZED_AT)

    body = build_document_body(replace(TWO_PAGE_SNAPSHOT, draft=draft))

    assert body["document"]["finalization_started_at"] == "2026-10-17T10:05:30-03:00"


def test_document_reports_the_path_of_a_possibly_saved_pdf() -> None:
    draft = TWO_PAGE_SNAPSHOT.draft.marked_finished(FINISHED_DOCUMENT)

    body = build_document_body(replace(TWO_PAGE_SNAPSHOT, draft=draft))

    assert body["document"]["finished_document_path"] == "/Volumes/External/scans/Contrato do apartamento.pdf"


def test_recovery_describes_what_the_recovery_did() -> None:
    body = build_document_body(replace(TWO_PAGE_SNAPSHOT, recovery_report=RESUMED_REPORT))

    assert body["recovery"] == {
        "outcome": "resumed",
        "kept_page_count": 2,
        "dropped_page_positions": [3],
        "set_aside_folder": None,
    }


def test_recovery_without_a_draft_reports_the_set_aside_folder() -> None:
    body = build_document_body(replace(EMPTY_SNAPSHOT, recovery_report=SET_ASIDE_REPORT))

    assert (body["document"], body["recovery"]["set_aside_folder"]) == (None, str(SET_ASIDE_REPORT.set_aside_folder))


def test_last_finished_document_describes_the_saved_pdf() -> None:
    finalization = DocumentFinalizationResult(result=FINISHED_DOCUMENT, page_count=2)

    body = build_document_body(replace(EMPTY_SNAPSHOT, last_finished_document=finalization))

    assert body["last_finished_document"] == {
        "file_name": "Contrato do apartamento.pdf",
        "output_folder": "/Volumes/External/scans",
        "page_count": 2,
        "size_in_bytes": 1612246,
        "finalized_at": "2026-10-17T10:05:30-03:00",
    }


def test_summary_without_a_draft_counts_zero_pages() -> None:
    assert build_document_summary_body(EMPTY_SNAPSHOT, DRAFT_STORAGE) == {
        "draft_session": DRAFT_SESSION,
        "revision": REVISION,
        "page_count": 0,
        "estimated_size_in_bytes": 0,
        "draft_storage": {
            "free_space_in_bytes": 80_000_000_000,
            "estimated_pages_remaining": 9000,
            "available": True,
        },
    }


def test_summary_counts_the_pages_and_their_size() -> None:
    body = build_document_summary_body(TWO_PAGE_SNAPSHOT, DRAFT_STORAGE)

    assert (body["page_count"], body["estimated_size_in_bytes"]) == (2, 6)


def test_summary_keys_come_in_the_documented_order() -> None:
    assert list(build_document_summary_body(TWO_PAGE_SNAPSHOT, DRAFT_STORAGE)) == [
        "draft_session",
        "revision",
        "page_count",
        "estimated_size_in_bytes",
        "draft_storage",
    ]


def test_summary_reports_an_unavailable_draft_disk() -> None:
    body = build_document_summary_body(EMPTY_SNAPSHOT, UNAVAILABLE_DRAFT_STORAGE_STATE)

    assert body["draft_storage"] == {"free_space_in_bytes": 0, "estimated_pages_remaining": 0, "available": False}

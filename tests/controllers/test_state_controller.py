from dataclasses import replace
from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog
from digitalizadora.controllers.state_controller import StateController
from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.capture_mode import CaptureMode
from digitalizadora.domain.image_adjustment import ImageAdjustment
from digitalizadora.domain.last_scan import SavedScanFile
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_progress import ScanPhase, ScanProgressSnapshot
from digitalizadora.services.application_state_service import ApplicationState, StorageState
from tests.controllers.controller_test_support import SCANNED_AT, build_test_client
from tests.fakes.stored_scans import build_last_scan
from tests.fakes.stub_document_draft_service import (
    STUB_DRAFT_SESSION,
    StubDocumentDraftService,
    build_stub_snapshot,
)

CATALOG = ErrorMessageCatalog()
ADJUSTMENT = ImageAdjustment(auto_crop=True)
SETTINGS = ApplicationSettings(
    output_folder=Path("/Volumes/External/scans"),
    output_format=OutputFormat.PDF,
    scan_settings=ScanPreset.DOCUMENT_ECONOMY.settings,
    capture_mode=CaptureMode.DOCUMENT,
    adjustment=ADJUSTMENT,
)
AVAILABLE_STORAGE = StorageState(free_space_in_bytes=5_000_000_000, estimated_pages_remaining=1200)
UNAVAILABLE_STORAGE = StorageState(
    free_space_in_bytes=0, estimated_pages_remaining=0, output_folder_available=False
)
LAST_SCAN = replace(
    build_last_scan((SavedScanFile("2026-10-13_15-30-12-000000006.pdf", 734003, 1),)),
    output_folder=Path("/Volumes/External/scans"),
    scanned_at=SCANNED_AT,
)
IDLE_SNAPSHOT = ScanProgressSnapshot(
    phase=ScanPhase.IDLE, scans_completed=0, last_scan=None, last_error_code=None
)


def build_failed_snapshot(error_code: str) -> ScanProgressSnapshot:
    return ScanProgressSnapshot(
        phase=ScanPhase.IDLE, scans_completed=0, last_scan=None, last_error_code=error_code
    )


class StubApplicationStateService:
    def __init__(self, snapshot: ScanProgressSnapshot) -> None:
        self.snapshot = snapshot
        self.storage = AVAILABLE_STORAGE

    def build_state(self) -> ApplicationState:
        return ApplicationState(snapshot=self.snapshot, settings=SETTINGS, storage=self.storage)


@pytest.fixture
def state_service() -> StubApplicationStateService:
    return StubApplicationStateService(IDLE_SNAPSHOT)


@pytest.fixture
def document_service() -> StubDocumentDraftService:
    return StubDocumentDraftService(build_stub_snapshot(2))


@pytest.fixture
def client(state_service: StubApplicationStateService, document_service: StubDocumentDraftService) -> TestClient:
    controller = StateController(state_service, document_service, CATALOG)
    return build_test_client(controller.build_router())


def test_health_answers_ok(client: TestClient) -> None:
    response = client.get("/api/health")

    assert (response.status_code, response.json()) == (HTTPStatus.OK, {"status": "ok"})


def test_state_of_a_fresh_application(client: TestClient) -> None:
    body = client.get("/api/state").json()

    assert {key: body[key] for key in ("scan_phase", "scans_completed", "last_result", "last_error")} == {
        "scan_phase": "idle",
        "scans_completed": 0,
        "last_result": None,
        "last_error": None,
    }


def test_state_reports_the_current_phase_and_counter(
    client: TestClient, state_service: StubApplicationStateService
) -> None:
    state_service.snapshot = ScanProgressSnapshot(
        phase=ScanPhase.SCANNING, scans_completed=3, last_scan=None, last_error_code=None
    )

    body = client.get("/api/state").json()

    assert (body["scan_phase"], body["scans_completed"]) == ("scanning", 3)


def test_state_describes_the_last_result(
    client: TestClient, state_service: StubApplicationStateService
) -> None:
    state_service.snapshot = ScanProgressSnapshot(
        phase=ScanPhase.IDLE, scans_completed=7, last_scan=LAST_SCAN, last_error_code=None
    )

    body = client.get("/api/state").json()

    assert body["last_result"] == {
        "scan_identifier": "9f3c1a2b4d5e6f70",
        "file_names": ["2026-10-13_15-30-12-000000006.pdf"],
        "output_folder": "/Volumes/External/scans",
        "output_format": "pdf",
        "total_size_in_bytes": 734003,
        "scanned_at": "2026-10-13T15:30:12-03:00",
        "rotation_degrees": 0,
        "crops": [],
        "is_editable": True,
    }


def test_state_reports_the_revision_of_the_last_result(
    client: TestClient, state_service: StubApplicationStateService
) -> None:
    state_service.snapshot = ScanProgressSnapshot(
        phase=ScanPhase.IDLE,
        scans_completed=7,
        last_scan=LAST_SCAN,
        last_error_code=None,
        last_result_revision=9,
    )

    assert client.get("/api/state").json()["last_result_revision"] == 9


def test_state_reports_revision_zero_before_any_scan(client: TestClient) -> None:
    assert client.get("/api/state").json()["last_result_revision"] == 0


@pytest.mark.parametrize("error_code", ["insufficient_storage", "local_network_blocked"])
def test_state_describes_the_last_error_with_the_catalog_message(
    client: TestClient, state_service: StubApplicationStateService, error_code: str
) -> None:
    state_service.snapshot = build_failed_snapshot(error_code)

    body = client.get("/api/state").json()

    assert body["last_error"] == {"code": error_code, "message": CATALOG.message_for(error_code)}


def test_state_uses_the_generic_message_for_an_unknown_error_code(
    client: TestClient, state_service: StubApplicationStateService
) -> None:
    state_service.snapshot = build_failed_snapshot("never_heard_of_it")

    body = client.get("/api/state").json()

    assert body["last_error"]["message"] == CATALOG.message_for("unexpected_error")


def test_state_contains_the_settings(client: TestClient) -> None:
    body = client.get("/api/state").json()

    assert body["settings"] == {
        "output_folder": "/Volumes/External/scans",
        "output_format": "pdf",
        "dots_per_inch": 200,
        "color_mode": "grayscale",
        "capture_mode": "document",
        "auto_crop": True,
        "crop_margin": True,
        "jpeg_quality": 90,
    }


def test_state_contains_the_storage_figures(client: TestClient) -> None:
    body = client.get("/api/state").json()

    assert body["storage"] == {
        "free_space_in_bytes": 5_000_000_000,
        "estimated_pages_remaining": 1200,
        "output_folder_available": True,
    }


def test_state_reports_an_unavailable_output_folder(
    client: TestClient, state_service: StubApplicationStateService
) -> None:
    state_service.storage = UNAVAILABLE_STORAGE

    body = client.get("/api/state").json()

    assert body["storage"] == {
        "free_space_in_bytes": 0,
        "estimated_pages_remaining": 0,
        "output_folder_available": False,
    }


def test_state_has_exactly_the_documented_keys(client: TestClient) -> None:
    body = client.get("/api/state").json()

    assert set(body) == {
        "scan_phase",
        "scans_completed",
        "last_result",
        "last_result_revision",
        "last_error",
        "settings",
        "storage",
        "document",
    }


def test_state_contains_the_document_summary(client: TestClient) -> None:
    body = client.get("/api/state").json()

    assert body["document"] == {
        "draft_session": STUB_DRAFT_SESSION,
        "revision": 2,
        "page_count": 2,
        "output_page_count": 2,
        "estimated_size_in_bytes": 6,
        "draft_storage": {
            "free_space_in_bytes": 80_000_000_000,
            "estimated_pages_remaining": 9000,
            "available": True,
        },
    }


def test_state_estimates_the_draft_storage_with_the_saved_quality(
    client: TestClient, document_service: StubDocumentDraftService
) -> None:
    client.get("/api/state")

    assert document_service.received_arguments["describe_draft_storage"] == ScanPreset.DOCUMENT_ECONOMY.settings

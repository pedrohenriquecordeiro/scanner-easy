from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog
from digitalizadora.controllers.state_controller import StateController
from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.capture_mode import CaptureMode
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_progress import ScanPhase, ScanProgressSnapshot
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.services.application_state_service import ApplicationState, StorageState
from tests.controllers.controller_test_support import SCANNED_AT, build_test_client

CATALOG = ErrorMessageCatalog()
SETTINGS = ApplicationSettings(
    output_folder=Path("/Volumes/External/scans"),
    output_format=OutputFormat.PDF,
    scan_preset=ScanPreset.DOCUMENT_ECONOMY,
    capture_mode=CaptureMode.DOCUMENT,
)
AVAILABLE_STORAGE = StorageState(free_space_in_bytes=5_000_000_000, estimated_pages_remaining=1200)
UNAVAILABLE_STORAGE = StorageState(
    free_space_in_bytes=0, estimated_pages_remaining=0, output_folder_available=False
)
LAST_RESULT = ScanResult(
    output_path=Path("/Volumes/External/scans/2026-10-13_00007.pdf"),
    output_format=OutputFormat.PDF,
    scanned_at=SCANNED_AT,
    size_in_bytes=734003,
)
IDLE_SNAPSHOT = ScanProgressSnapshot(
    phase=ScanPhase.IDLE, scans_completed=0, last_result=None, last_error_code=None
)


def build_failed_snapshot(error_code: str) -> ScanProgressSnapshot:
    return ScanProgressSnapshot(
        phase=ScanPhase.IDLE, scans_completed=0, last_result=None, last_error_code=error_code
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
def client(state_service: StubApplicationStateService) -> TestClient:
    controller = StateController(state_service, CATALOG)
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
        phase=ScanPhase.SCANNING, scans_completed=3, last_result=None, last_error_code=None
    )

    body = client.get("/api/state").json()

    assert (body["scan_phase"], body["scans_completed"]) == ("scanning", 3)


def test_state_describes_the_last_result(
    client: TestClient, state_service: StubApplicationStateService
) -> None:
    state_service.snapshot = ScanProgressSnapshot(
        phase=ScanPhase.IDLE, scans_completed=7, last_result=LAST_RESULT, last_error_code=None
    )

    body = client.get("/api/state").json()

    assert body["last_result"] == {
        "file_name": "2026-10-13_00007.pdf",
        "output_folder": "/Volumes/External/scans",
        "output_format": "pdf",
        "size_in_bytes": 734003,
        "scanned_at": "2026-10-13T15:30:12-03:00",
    }


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
        "scan_preset": "document_economy",
        "capture_mode": "document",
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
        "last_error",
        "settings",
        "storage",
    }

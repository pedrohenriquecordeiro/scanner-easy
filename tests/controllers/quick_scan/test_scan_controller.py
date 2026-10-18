import logging
from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog
from digitalizadora.controllers.quick_scan.scan_controller import ScanController
from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.errors import ScanAlreadyRunningError, ScannerUnreachableError
from digitalizadora.domain.image_adjustment import ImageAdjustment
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.services.application_settings_service import ApplicationSettingsService
from tests.controllers.controller_test_support import (
    StubFolderPreparer,
    StubScanService,
    build_test_client,
)
from tests.fakes.in_memory_settings_repository import InMemoryApplicationSettingsRepository

SETTINGS = ApplicationSettings(
    output_folder=Path("/Volumes/External/scans"),
    output_format=OutputFormat.JPEG,
    scan_settings=ScanPreset.PHOTO.settings,
    adjustment=ImageAdjustment(auto_crop=True),
)
CATALOG = ErrorMessageCatalog()


@pytest.fixture
def scan_service() -> StubScanService:
    return StubScanService()


@pytest.fixture
def client(scan_service: StubScanService) -> TestClient:
    settings_service = ApplicationSettingsService(
        InMemoryApplicationSettingsRepository(SETTINGS), StubFolderPreparer()
    )
    controller = ScanController(scan_service, settings_service, CATALOG)
    return build_test_client(controller.build_router())


def test_post_scans_answers_202_accepted(client: TestClient) -> None:
    response = client.post("/api/scans")

    assert (response.status_code, response.json()) == (HTTPStatus.ACCEPTED, {"accepted": True})


def test_post_scans_runs_one_scan_with_the_request_built_from_the_settings(
    client: TestClient, scan_service: StubScanService
) -> None:
    client.post("/api/scans")

    assert scan_service.requests == [SETTINGS.to_scan_request()]


def test_post_scans_answers_409_while_a_scan_is_running(
    client: TestClient, scan_service: StubScanService
) -> None:
    scan_service.in_progress = True

    response = client.post("/api/scans")

    assert (response.status_code, response.json()) == (
        HTTPStatus.CONFLICT,
        {
            "code": "scan_already_running",
            "message": CATALOG.message_for("scan_already_running"),
        },
    )


def test_post_scans_does_not_start_a_scan_while_one_is_running(
    client: TestClient, scan_service: StubScanService
) -> None:
    scan_service.in_progress = True

    client.post("/api/scans")

    assert scan_service.requests == []


def test_a_scan_error_in_the_background_does_not_change_the_answer(
    client: TestClient, scan_service: StubScanService
) -> None:
    scan_service.failure = ScannerUnreachableError("printer offline")

    response = client.post("/api/scans")

    assert response.status_code == HTTPStatus.ACCEPTED


def test_a_scan_error_in_the_background_is_logged_with_its_code(
    client: TestClient, scan_service: StubScanService, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING)
    scan_service.failure = ScannerUnreachableError("printer offline")

    client.post("/api/scans")

    assert "scanner_unreachable" in caplog.text


def test_a_duplicate_background_scan_is_only_logged(
    client: TestClient, scan_service: StubScanService, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING)
    scan_service.failure = ScanAlreadyRunningError("a scan is already in progress")

    client.post("/api/scans")

    assert "scan_already_running" in caplog.text


def test_an_unexpected_background_failure_does_not_reach_the_client(
    client: TestClient, scan_service: StubScanService
) -> None:
    scan_service.failure = RuntimeError("boom")

    response = client.post("/api/scans")

    assert response.status_code == HTTPStatus.ACCEPTED


def test_an_unexpected_background_failure_is_logged(
    client: TestClient, scan_service: StubScanService, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.ERROR)
    scan_service.failure = RuntimeError("boom")

    client.post("/api/scans")

    assert "boom" in caplog.text

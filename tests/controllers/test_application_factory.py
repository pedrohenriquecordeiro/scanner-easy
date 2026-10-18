import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from digitalizadora.application_factory import (
    ApplicationControllers,
    WebInterfaceConfiguration,
    create_application,
)
from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog
from digitalizadora.controllers.preview_controller import PreviewController
from digitalizadora.controllers.printer_controller import PrinterController
from digitalizadora.controllers.scan_controller import ScanController
from digitalizadora.controllers.settings_controller import SettingsController
from digitalizadora.controllers.state_controller import StateController
from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.domain.scanner_route import ScannerRoute
from digitalizadora.domain.scanner_status import ScannerState
from digitalizadora.domain.stored_scan import StoredScan
from digitalizadora.services.application_settings_service import ApplicationSettingsService
from digitalizadora.services.application_state_service import ApplicationStateService
from digitalizadora.services.printer_connection_service import PrinterConnectionState
from digitalizadora.services.scan_progress_tracker import ScanProgressTracker
from digitalizadora.services.storage_guard_service import StorageGuardService
from tests.controllers.controller_test_support import (
    SCANNED_AT,
    STATE_CHANGING_HEADERS,
    TEST_BASE_ADDRESS,
    StubFolderPreparer,
    StubPrinterConnectionService,
    StubScanService,
)
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.in_memory_settings_repository import InMemoryApplicationSettingsRepository
from tests.fakes.sample_images import build_sample_jpeg

ALLOWED_HOSTS = frozenset({"127.0.0.1:8765", "localhost:8765"})
INDEX_HTML = "<!doctype html><title>Digitalizadora</title>"
STYLESHEET = "body { margin: 0; }"
FREE_SPACE_IN_BYTES = 50 * 1024**3
CATALOG = ErrorMessageCatalog()
SETTINGS = ApplicationSettings(
    output_folder=Path("/Volumes/External/scans"),
    output_format=OutputFormat.JPEG,
    scan_preset=ScanPreset.PHOTO,
)
SETTINGS_BODY = {
    "output_folder": "/Volumes/External/scans",
    "output_format": "jpg",
    "scan_preset": "photo",
    "capture_mode": "single",
}
CONNECTED_STATE = PrinterConnectionState(
    connected=True,
    display_name="HP DeskJet 2800 series",
    scanner_state=ScannerState.IDLE,
    error_code=None,
    route=ScannerRoute.USB,
)
UNEXPECTED_ERROR_BODY = {
    "code": "unexpected_error",
    "message": CATALOG.message_for("unexpected_error"),
}


@dataclass(frozen=True)
class ApplicationParts:
    controllers: ApplicationControllers
    scan_service: StubScanService
    printer_service: StubPrinterConnectionService
    progress_tracker: ScanProgressTracker


def build_application_parts() -> ApplicationParts:
    progress_tracker = ScanProgressTracker(FixedClock(SCANNED_AT))
    settings_repository = InMemoryApplicationSettingsRepository(SETTINGS)
    settings_service = ApplicationSettingsService(settings_repository, StubFolderPreparer())
    scan_service = StubScanService()
    printer_service = StubPrinterConnectionService(CONNECTED_STATE)
    storage_guard_service = StorageGuardService(lambda folder: FREE_SPACE_IN_BYTES)
    controllers = ApplicationControllers(
        scan=ScanController(scan_service, settings_service, CATALOG),
        state=StateController(
            ApplicationStateService(progress_tracker, settings_repository, storage_guard_service),
            CATALOG,
        ),
        settings=SettingsController(settings_service, CATALOG),
        printer=PrinterController(printer_service, CATALOG),
        preview=PreviewController(progress_tracker),
    )
    return ApplicationParts(controllers, scan_service, printer_service, progress_tracker)


def build_application(
    parts: ApplicationParts,
    static_directory: Path,
    shutdown_callbacks: tuple[Callable[[], Awaitable[None]], ...] = (),
) -> FastAPI:
    web_configuration = WebInterfaceConfiguration(
        allowed_hosts=ALLOWED_HOSTS,
        static_directory=static_directory,
        error_message_catalog=CATALOG,
        shutdown_callbacks=shutdown_callbacks,
    )
    return create_application(parts.controllers, web_configuration)


def build_client(
    parts: ApplicationParts,
    static_directory: Path,
    shutdown_callbacks: tuple[Callable[[], Awaitable[None]], ...] = (),
) -> TestClient:
    application = build_application(parts, static_directory, shutdown_callbacks)
    return TestClient(application, base_url=TEST_BASE_ADDRESS)


@pytest.fixture
def static_directory(tmp_path: Path) -> Path:
    directory = tmp_path / "static"
    directory.mkdir()
    (directory / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (directory / "application.css").write_text(STYLESHEET, encoding="utf-8")
    return directory


@pytest.fixture
def parts() -> ApplicationParts:
    return build_application_parts()


@pytest.fixture
def client(parts: ApplicationParts, static_directory: Path) -> TestClient:
    return build_client(parts, static_directory)


@pytest.fixture
def client_that_answers_server_errors(
    parts: ApplicationParts, static_directory: Path
) -> TestClient:
    application = build_application(parts, static_directory)
    return TestClient(application, base_url=TEST_BASE_ADDRESS, raise_server_exceptions=False)


def test_root_serves_the_index_page(client: TestClient) -> None:
    response = client.get("/")

    assert (response.status_code, response.text) == (HTTPStatus.OK, INDEX_HTML)


def test_root_is_served_as_html(client: TestClient) -> None:
    assert client.get("/").headers["content-type"].startswith("text/html")


def test_static_files_are_served_below_static(client: TestClient) -> None:
    response = client.get("/static/application.css")

    assert (response.status_code, response.text) == (HTTPStatus.OK, STYLESHEET)


def test_missing_static_file_answers_404(client: TestClient) -> None:
    assert client.get("/static/missing.js").status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_interactive_documentation_is_disabled(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == HTTPStatus.NOT_FOUND


def test_health_is_reachable_through_the_factory(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def test_state_is_reachable_through_the_factory(client: TestClient) -> None:
    body = client.get("/api/state").json()

    assert (body["settings"], body["storage"]["free_space_in_bytes"]) == (
        SETTINGS_BODY,
        FREE_SPACE_IN_BYTES,
    )


def test_settings_are_reachable_through_the_factory(client: TestClient) -> None:
    assert client.get("/api/settings").json() == SETTINGS_BODY


def test_printer_is_reachable_through_the_factory(client: TestClient) -> None:
    assert client.get("/api/printer").json()["route"] == "usb"


def test_localhost_host_header_is_allowed(client: TestClient) -> None:
    response = client.get("/api/health", headers={"host": "localhost:8765"})

    assert response.status_code == HTTPStatus.OK


def test_foreign_host_header_is_rejected(client: TestClient) -> None:
    response = client.get("/api/health", headers={"host": "evil.example"})

    assert (response.status_code, response.json()["code"]) == (HTTPStatus.FORBIDDEN, "forbidden_host")


def test_put_without_the_required_header_is_rejected(client: TestClient) -> None:
    response = client.put("/api/settings", json=SETTINGS_BODY)

    assert (response.status_code, response.json()["code"]) == (
        HTTPStatus.FORBIDDEN,
        "missing_request_header",
    )


def test_put_with_the_required_header_is_accepted(client: TestClient) -> None:
    response = client.put("/api/settings", json=SETTINGS_BODY, headers=STATE_CHANGING_HEADERS)

    assert response.status_code == HTTPStatus.OK


def test_put_with_an_incomplete_body_answers_422_in_the_error_shape(client: TestClient) -> None:
    response = client.put("/api/settings", json={}, headers=STATE_CHANGING_HEADERS)

    assert (response.status_code, response.json()) == (
        HTTPStatus.UNPROCESSABLE_ENTITY,
        {"code": "invalid_settings", "message": CATALOG.message_for("invalid_settings")},
    )


def test_put_with_a_capture_mode_that_is_not_text_answers_422_in_the_error_shape(client: TestClient) -> None:
    response = client.put(
        "/api/settings", json={**SETTINGS_BODY, "capture_mode": 1}, headers=STATE_CHANGING_HEADERS
    )

    assert (response.status_code, response.json()) == (
        HTTPStatus.UNPROCESSABLE_ENTITY,
        {"code": "invalid_settings", "message": CATALOG.message_for("invalid_settings")},
    )


def test_unknown_route_answers_404_in_the_error_shape(client: TestClient) -> None:
    response = client.get("/api/nothing")

    assert (response.status_code, response.json()) == (HTTPStatus.NOT_FOUND, UNEXPECTED_ERROR_BODY)


def test_wrong_method_answers_405_in_the_error_shape(client: TestClient) -> None:
    response = client.post("/api/health", headers=STATE_CHANGING_HEADERS)

    assert (response.status_code, response.json()) == (
        HTTPStatus.METHOD_NOT_ALLOWED,
        UNEXPECTED_ERROR_BODY,
    )


def test_wrong_method_keeps_the_allow_header(client: TestClient) -> None:
    response = client.post("/api/health", headers=STATE_CHANGING_HEADERS)

    assert response.headers["allow"] == "GET"


def test_unexpected_failure_answers_500_in_the_error_shape(
    client_that_answers_server_errors: TestClient, parts: ApplicationParts
) -> None:
    parts.printer_service.failure = RuntimeError("boom")

    response = client_that_answers_server_errors.get("/api/printer")

    assert (response.status_code, response.json()) == (
        HTTPStatus.INTERNAL_SERVER_ERROR,
        UNEXPECTED_ERROR_BODY,
    )


def test_unexpected_failure_is_logged_with_its_traceback(
    client_that_answers_server_errors: TestClient,
    parts: ApplicationParts,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR, logger="digitalizadora")
    parts.printer_service.failure = RuntimeError("boom")

    client_that_answers_server_errors.get("/api/printer")

    assert [
        record.exc_info is not None
        for record in caplog.records
        if record.name.startswith("digitalizadora")
    ] == [True]


def test_post_scans_answers_202_and_scans_once_with_the_saved_settings(
    client: TestClient, parts: ApplicationParts
) -> None:
    response = client.post("/api/scans", headers=STATE_CHANGING_HEADERS)

    assert (response.status_code, parts.scan_service.requests) == (
        HTTPStatus.ACCEPTED,
        [SETTINGS.to_scan_request()],
    )


def test_post_scans_answers_409_while_the_scan_service_is_busy(
    client: TestClient, parts: ApplicationParts
) -> None:
    parts.scan_service.in_progress = True

    response = client.post("/api/scans", headers=STATE_CHANGING_HEADERS)

    assert (response.status_code, response.json()["code"]) == (
        HTTPStatus.CONFLICT,
        "scan_already_running",
    )


def test_post_scans_without_the_required_header_does_not_scan(
    client: TestClient, parts: ApplicationParts
) -> None:
    client.post("/api/scans")

    assert parts.scan_service.requests == []


def test_thumbnail_is_404_before_a_stored_scan(client: TestClient) -> None:
    assert client.get("/api/scans/last/thumbnail").status_code == HTTPStatus.NOT_FOUND


def test_thumbnail_is_served_after_a_stored_scan(
    client: TestClient, parts: ApplicationParts
) -> None:
    thumbnail_jpeg = build_sample_jpeg()
    result = ScanResult(
        output_path=Path("/Volumes/External/scans/2026-10-13_00001.jpg"),
        output_format=OutputFormat.JPEG,
        scanned_at=SCANNED_AT,
        size_in_bytes=1234,
    )
    parts.progress_tracker.begin_scan(ScanRequest(ScanPreset.PHOTO.settings, OutputFormat.JPEG))
    parts.progress_tracker.mark_completed(StoredScan(result, thumbnail_jpeg))

    response = client.get("/api/scans/last/thumbnail")

    assert (response.status_code, response.content) == (HTTPStatus.OK, thumbnail_jpeg)


class RecordingShutdownCallback:
    def __init__(self) -> None:
        self.call_count = 0

    async def __call__(self) -> None:
        self.call_count += 1


def test_shutdown_callbacks_do_not_run_while_the_application_is_up(
    parts: ApplicationParts, static_directory: Path
) -> None:
    callback = RecordingShutdownCallback()

    with build_client(parts, static_directory, (callback,)) as running_client:
        running_client.get("/api/health")
        call_count_while_running = callback.call_count

    assert call_count_while_running == 0


def test_shutdown_callbacks_run_once_when_the_application_stops(
    parts: ApplicationParts, static_directory: Path
) -> None:
    first_callback = RecordingShutdownCallback()
    second_callback = RecordingShutdownCallback()

    with build_client(parts, static_directory, (first_callback, second_callback)):
        pass

    assert (first_callback.call_count, second_callback.call_count) == (1, 1)

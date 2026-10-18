import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from digitalizadora.application_factory import (
    VALIDATION_ERROR_CODE_PATTERNS,
    ApplicationControllers,
    WebInterfaceConfiguration,
    create_application,
    find_validation_error_code,
)
from digitalizadora.controllers.application.printer_controller import PrinterController
from digitalizadora.controllers.application.settings_controller import SettingsController
from digitalizadora.controllers.application.state_controller import StateController
from digitalizadora.controllers.documents.document_controller import DocumentController
from digitalizadora.controllers.quick_scan.last_scan_controller import LastScanController
from digitalizadora.controllers.quick_scan.preview_controller import PreviewController
from digitalizadora.controllers.quick_scan.scan_controller import ScanController
from digitalizadora.controllers.shared.error_message_catalog import ErrorMessageCatalog
from digitalizadora.domain.output.output_format import OutputFormat
from digitalizadora.domain.quick_scan.stored_scan import StoredScan
from digitalizadora.domain.scanner.scanner_route import ScannerRoute
from digitalizadora.domain.scanner.scanner_status import ScannerState
from digitalizadora.domain.scanning.scan_request import ScanRequest
from digitalizadora.domain.settings.application_settings import ApplicationSettings
from digitalizadora.domain.settings.scan_preset import ScanPreset
from digitalizadora.repositories.quick_scan.file_system_quick_scan_slot_repository import (
    FileSystemQuickScanSlotRepository,
)
from digitalizadora.repositories.storage.atomic_file_writer import AtomicFileWriter
from digitalizadora.services.application.application_settings_service import ApplicationSettingsService
from digitalizadora.services.application.application_state_service import ApplicationStateService
from digitalizadora.services.application.scan_progress_tracker import ScanProgressTracker
from digitalizadora.services.application.storage_guard_service import StorageGuardService
from digitalizadora.services.imaging.page_image_view_service import PageImageViewService
from digitalizadora.services.quick_scan.last_scan_view_service import LastScanViewService
from digitalizadora.services.scanner.printer_connection_service import PrinterConnectionState
from tests.controllers.controller_test_support import (
    SCANNED_AT,
    STATE_CHANGING_HEADERS,
    TEST_BASE_ADDRESS,
    StubFolderPreparer,
    StubPrinterConnectionService,
    StubScanService,
)
from tests.fakes.document_drafts import page_identifier_at
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.in_memory_settings_repository import InMemoryApplicationSettingsRepository
from tests.fakes.sample_images import build_sample_jpeg
from tests.fakes.stored_scans import build_last_scan
from tests.fakes.stub_document_draft_service import (
    STUB_DRAFT_SESSION,
    StubDocumentDraftService,
    build_stub_snapshot,
)
from tests.fakes.stub_last_scan_edit_service import StubLastScanEditService

ALLOWED_HOSTS = frozenset({"127.0.0.1:8765", "localhost:8765"})
INDEX_HTML = "<!doctype html><title>Digitalizadora</title>"
STYLESHEET = "body { margin: 0; }"
FREE_SPACE_IN_BYTES = 50 * 1024**3
CATALOG = ErrorMessageCatalog()
SETTINGS = ApplicationSettings(
    output_folder=Path("/Volumes/External/scans"),
    output_format=OutputFormat.JPEG,
    scan_settings=ScanPreset.PHOTO.settings,
)
SETTINGS_BODY = {
    "output_folder": "/Volumes/External/scans",
    "output_format": "jpg",
    "dots_per_inch": 600,
    "color_mode": "color",
    "capture_mode": "single",
    "auto_crop": False,
    "crop_margin": True,
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
DOCUMENT_DELETE_PATHS = [
    "/api/document",
    "/api/document/pages/last",
    f"/api/document/pages/{page_identifier_at(1)}",
]


@dataclass(frozen=True)
class ApplicationParts:
    controllers: ApplicationControllers
    scan_service: StubScanService
    printer_service: StubPrinterConnectionService
    progress_tracker: ScanProgressTracker
    document_service: StubDocumentDraftService
    last_scan_edit_service: StubLastScanEditService


def build_application_parts() -> ApplicationParts:
    progress_tracker = ScanProgressTracker(FixedClock(SCANNED_AT))
    settings_repository = InMemoryApplicationSettingsRepository(SETTINGS)
    settings_service = ApplicationSettingsService(settings_repository, StubFolderPreparer())
    scan_service = StubScanService()
    printer_service = StubPrinterConnectionService(CONNECTED_STATE)
    document_service = StubDocumentDraftService(build_stub_snapshot(2))
    last_scan_edit_service = StubLastScanEditService()
    storage_guard_service = StorageGuardService(lambda folder: FREE_SPACE_IN_BYTES)
    # The routes of these tests never reach the master, so the slot folder is never touched.
    slot_repository = FileSystemQuickScanSlotRepository(Path("/unused"), AtomicFileWriter(), FixedClock(SCANNED_AT))
    last_scan_view_service = LastScanViewService(progress_tracker, slot_repository, PageImageViewService())
    controllers = ApplicationControllers(
        scan=ScanController(scan_service, settings_service, CATALOG),
        state=StateController(
            ApplicationStateService(progress_tracker, settings_repository, storage_guard_service),
            document_service,
            CATALOG,
        ),
        settings=SettingsController(settings_service, CATALOG),
        printer=PrinterController(printer_service, CATALOG),
        preview=PreviewController(last_scan_view_service, CATALOG),
        document=DocumentController(document_service, settings_service, CATALOG),
        last_scan=LastScanController(last_scan_edit_service, CATALOG),
    )
    return ApplicationParts(
        controllers, scan_service, printer_service, progress_tracker, document_service, last_scan_edit_service
    )


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


def test_the_index_page_is_revalidated_at_every_load(client: TestClient) -> None:
    assert client.get("/").headers["cache-control"] == "no-cache"


def test_static_files_are_revalidated_at_every_load(client: TestClient) -> None:
    assert client.get("/static/application.css").headers["cache-control"] == "no-cache"


def test_a_static_file_that_did_not_change_answers_304_with_the_same_policy(client: TestClient) -> None:
    entity_tag = client.get("/static/application.css").headers["etag"]

    response = client.get("/static/application.css", headers={"If-None-Match": entity_tag})

    assert (response.status_code, response.headers["cache-control"]) == (HTTPStatus.NOT_MODIFIED, "no-cache")


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
    parts.progress_tracker.begin_scan(ScanRequest(ScanPreset.PHOTO.settings, OutputFormat.JPEG))
    parts.progress_tracker.mark_completed(StoredScan(build_last_scan(), thumbnail_jpeg))

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


def test_document_is_reachable_through_the_factory(client: TestClient) -> None:
    body = client.get("/api/document").json()

    assert (body["draft_session"], body["document"]["page_count"]) == (STUB_DRAFT_SESSION, 2)


def test_state_carries_the_document_summary_through_the_factory(client: TestClient) -> None:
    assert client.get("/api/state").json()["document"]["page_count"] == 2


def test_post_document_pages_with_the_required_header_is_accepted(client: TestClient) -> None:
    response = client.post("/api/document/pages", headers=STATE_CHANGING_HEADERS)

    assert response.status_code == HTTPStatus.ACCEPTED


@pytest.mark.parametrize("path", DOCUMENT_DELETE_PATHS)
def test_document_delete_without_the_required_header_is_rejected(client: TestClient, path: str) -> None:
    response = client.delete(path)

    assert (response.status_code, response.json()["code"]) == (HTTPStatus.FORBIDDEN, "missing_request_header")


def test_rejected_document_delete_does_not_reach_the_document_service(
    client: TestClient, parts: ApplicationParts
) -> None:
    client.delete("/api/document")

    assert parts.document_service.calls == []


@pytest.mark.parametrize(
    "body",
    [{}, {"page_identifiers": page_identifier_at(1)}, {"page_identifiers": [1, 2]}],
    ids=["empty", "text", "numbers"],
)
def test_malformed_page_order_answers_the_code_of_the_route(client: TestClient, body: dict[str, object]) -> None:
    response = client.put("/api/document/page-order", json=body, headers=STATE_CHANGING_HEADERS)

    assert (response.status_code, response.json()) == (
        HTTPStatus.UNPROCESSABLE_ENTITY,
        {"code": "invalid_page_order", "message": CATALOG.message_for("invalid_page_order")},
    )


@pytest.mark.parametrize("body", [{}, {"name": None}, {"name": ["Contrato"]}], ids=["empty", "null", "list"])
def test_malformed_document_name_answers_the_code_of_the_route(client: TestClient, body: dict[str, object]) -> None:
    response = client.put("/api/document/name", json=body, headers=STATE_CHANGING_HEADERS)

    assert (response.status_code, response.json()) == (
        HTTPStatus.UNPROCESSABLE_ENTITY,
        {"code": "invalid_document_name", "message": CATALOG.message_for("invalid_document_name")},
    )


def test_malformed_body_does_not_reach_the_document_service(client: TestClient, parts: ApplicationParts) -> None:
    client.put("/api/document/name", json={}, headers=STATE_CHANGING_HEADERS)

    assert parts.document_service.calls == []


CROP_PATH = f"/api/document/pages/{page_identifier_at(1)}/crops"
UNIT_SQUARE_CORNERS = {
    "top_left": {"x": 0, "y": 0},
    "top_right": {"x": 1, "y": 0},
    "bottom_right": {"x": 1, "y": 1},
    "bottom_left": {"x": 0, "y": 1},
}


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"crops": [{}]},
        {"crops": "whole"},
        {"crops": [{"top_left": {"x": 0, "y": 0}}]},
        {"crops": [{**UNIT_SQUARE_CORNERS, "top_left": {"x": "0", "y": 0}}]},
        {"crops": [{**UNIT_SQUARE_CORNERS, "top_left": {"x": True, "y": 0}}]},
        {"crops": [[0, 0, 1, 1]]},
        {"crops": [UNIT_SQUARE_CORNERS, UNIT_SQUARE_CORNERS, UNIT_SQUARE_CORNERS]},
    ],
    ids=["empty", "empty-crop", "text", "missing-corners", "text-coordinate", "boolean-coordinate", "list", "three"],
)
def test_malformed_crop_answers_the_code_of_the_route(client: TestClient, body: dict[str, object]) -> None:
    response = client.put(CROP_PATH, json=body, headers=STATE_CHANGING_HEADERS)

    assert (response.status_code, response.json()) == (
        HTTPStatus.UNPROCESSABLE_ENTITY,
        {"code": "invalid_crop", "message": CATALOG.message_for("invalid_crop")},
    )


def test_a_crop_body_that_is_not_json_answers_the_code_of_the_route(client: TestClient) -> None:
    response = client.put(CROP_PATH, content=b"not json", headers=STATE_CHANGING_HEADERS)

    assert (response.status_code, response.json()["code"]) == (HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_crop")


@pytest.mark.parametrize("view", ["thumbnail", "preview"])
@pytest.mark.parametrize("rotation_degrees", ["abc", "", "9.5"])
def test_a_rotation_that_is_not_a_number_answers_the_code_of_the_route(
    client: TestClient, view: str, rotation_degrees: str
) -> None:
    response = client.get(f"/api/document/pages/{page_identifier_at(1)}/{view}?rotation_degrees={rotation_degrees}")

    assert (response.status_code, response.json()) == (
        HTTPStatus.UNPROCESSABLE_ENTITY,
        {"code": "invalid_page_rotation", "message": CATALOG.message_for("invalid_page_rotation")},
    )


def test_a_malformed_crop_does_not_reach_the_document_service(client: TestClient, parts: ApplicationParts) -> None:
    client.put(CROP_PATH, json={"crops": "whole"}, headers=STATE_CHANGING_HEADERS)

    assert parts.document_service.calls == []


def test_the_patterns_of_the_validation_codes_name_only_the_routes_with_a_body_or_a_query() -> None:
    assert [(pattern.pattern, code) for pattern, code in VALIDATION_ERROR_CODE_PATTERNS] == [
        ("/api/document/page-order", "invalid_page_order"),
        ("/api/document/name", "invalid_document_name"),
        ("/api/document/pages/[^/]+/crops(/detect)?", "invalid_crop"),
        ("/api/document/pages/[^/]+/(thumbnail|preview)", "invalid_page_rotation"),
        ("/api/scans/last/crops", "invalid_crop"),
        ("/api/scans/last/preview", "invalid_page_rotation"),
    ]


def test_a_missing_scan_identifier_on_the_last_scan_preview_has_its_own_code() -> None:
    assert find_validation_error_code("/api/scans/last/preview", frozenset({"scan_identifier"})) == (
        "invalid_scan_identifier"
    )


@pytest.mark.parametrize(
    "request_path",
    [
        "/api/document/pages/a/b/crops/detect",
        "/api/document/pages/a/b/crops",
        "/api/document/pages//crops",
        "/api/settings",
    ],
)
def test_a_path_that_is_not_one_of_the_routes_keeps_the_settings_code(request_path: str) -> None:
    assert find_validation_error_code(request_path) == "invalid_settings"


def test_the_last_scan_rotation_is_reachable_through_the_factory(client: TestClient, parts: ApplicationParts) -> None:
    response = client.post("/api/scans/last/rotation", headers=STATE_CHANGING_HEADERS)

    assert (response.status_code, parts.last_scan_edit_service.calls) == (HTTPStatus.OK, ["rotate_clockwise"])


def test_the_last_scan_rotation_without_the_required_header_is_rejected(
    client: TestClient, parts: ApplicationParts
) -> None:
    response = client.post("/api/scans/last/rotation")

    assert (response.status_code, parts.last_scan_edit_service.calls) == (HTTPStatus.FORBIDDEN, [])


def test_a_malformed_last_scan_crops_body_answers_the_code_of_the_route(client: TestClient) -> None:
    response = client.put("/api/scans/last/crops", json={"crops": "whole"}, headers=STATE_CHANGING_HEADERS)

    assert (response.status_code, response.json()["code"]) == (HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_crop")


def test_a_malformed_last_scan_crops_body_does_not_reach_the_service(
    client: TestClient, parts: ApplicationParts
) -> None:
    client.put("/api/scans/last/crops", json={"crops": "whole"}, headers=STATE_CHANGING_HEADERS)

    assert parts.last_scan_edit_service.calls == []


def test_a_last_scan_preview_with_a_rotation_that_is_not_a_number_answers_the_code_of_the_route(
    client: TestClient,
) -> None:
    response = client.get("/api/scans/last/preview?scan_identifier=9f3c1a2b4d5e6f70&rotation_degrees=abc")

    assert (response.status_code, response.json()["code"]) == (HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_page_rotation")


def test_a_last_scan_preview_without_the_scan_identifier_answers_its_own_code(client: TestClient) -> None:
    response = client.get("/api/scans/last/preview?rotation_degrees=0")

    assert response.json()["code"] == "invalid_scan_identifier"


def test_the_last_scan_crops_are_reachable_through_the_factory(client: TestClient, parts: ApplicationParts) -> None:
    response = client.put("/api/scans/last/crops", json={"crops": []}, headers=STATE_CHANGING_HEADERS)

    assert (response.status_code, parts.last_scan_edit_service.calls) == (HTTPStatus.OK, ["set_crops"])


def test_the_last_scan_crops_without_the_required_header_are_rejected(
    client: TestClient, parts: ApplicationParts
) -> None:
    response = client.put("/api/scans/last/crops", json={"crops": []})

    assert (response.status_code, parts.last_scan_edit_service.calls) == (HTTPStatus.FORBIDDEN, [])


def test_the_last_scan_detection_is_reachable_through_the_factory(client: TestClient, parts: ApplicationParts) -> None:
    response = client.post("/api/scans/last/crops/detect", headers=STATE_CHANGING_HEADERS)

    assert (response.status_code, parts.last_scan_edit_service.calls) == (HTTPStatus.OK, ["detect_crops"])

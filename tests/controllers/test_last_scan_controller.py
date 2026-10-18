from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog
from digitalizadora.controllers.last_scan_controller import LAST_SCAN_ERROR_STATUSES, LastScanController
from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.errors import (
    DigitalizadoraError,
    ImageAdjustmentFailedError,
    InsufficientStorageError,
    LastScanFileMissingError,
    NoLastScanError,
    OutputFolderUnavailableError,
    SavedScanUnreadableError,
    ScanAlreadyRunningError,
)
from digitalizadora.domain.image_adjustment import ImageAdjustment
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.services.application_settings_service import ApplicationSettingsService
from tests.controllers.controller_test_support import StubFolderPreparer, build_test_client
from tests.fakes.in_memory_settings_repository import InMemoryApplicationSettingsRepository
from tests.fakes.stored_scans import (
    STORED_SCAN_OUTPUT_PATH,
    STORED_SCAN_SCANNED_AT,
    STORED_SCAN_SIZE_IN_BYTES,
)
from tests.fakes.stub_last_scan_rotation_service import StubLastScanRotationService

CATALOG = ErrorMessageCatalog()
SETTINGS = ApplicationSettings(
    output_folder=Path("/Volumes/External/scans"),
    output_format=OutputFormat.PDF,
    scan_settings=ScanPreset.DOCUMENT.settings,
    adjustment=ImageAdjustment(jpeg_quality=70),
)
ROTATION_PATH = "/api/scans/last/rotation"
EXPECTED_FAILURES = [
    (NoLastScanError("none"), HTTPStatus.NOT_FOUND),
    (ScanAlreadyRunningError("running"), HTTPStatus.CONFLICT),
    (LastScanFileMissingError("gone"), HTTPStatus.CONFLICT),
    (SavedScanUnreadableError("broken"), HTTPStatus.CONFLICT),
    (InsufficientStorageError("full"), HTTPStatus.INSUFFICIENT_STORAGE),
    (OutputFolderUnavailableError("disconnected"), HTTPStatus.SERVICE_UNAVAILABLE),
    (ImageAdjustmentFailedError("memory"), HTTPStatus.INTERNAL_SERVER_ERROR),
]


@pytest.fixture
def rotation_service() -> StubLastScanRotationService:
    return StubLastScanRotationService()


@pytest.fixture
def client(rotation_service: StubLastScanRotationService) -> TestClient:
    settings_service = ApplicationSettingsService(
        InMemoryApplicationSettingsRepository(SETTINGS), StubFolderPreparer()
    )
    return build_test_client(LastScanController(rotation_service, settings_service, CATALOG).build_router())


def test_rotating_the_last_scan_answers_the_turned_file(client: TestClient) -> None:
    response = client.post(ROTATION_PATH)

    assert (response.status_code, response.json()) == (
        HTTPStatus.OK,
        {
            "last_result": {
                "file_name": STORED_SCAN_OUTPUT_PATH.name,
                "output_folder": str(STORED_SCAN_OUTPUT_PATH.parent),
                "output_format": "pdf",
                "size_in_bytes": STORED_SCAN_SIZE_IN_BYTES,
                "scanned_at": STORED_SCAN_SCANNED_AT.isoformat(),
            }
        },
    )


def test_rotating_the_last_scan_asks_the_service_once(
    client: TestClient, rotation_service: StubLastScanRotationService
) -> None:
    client.post(ROTATION_PATH)

    assert rotation_service.rotation_count == 1


@pytest.mark.parametrize(("error", "status"), EXPECTED_FAILURES, ids=lambda value: getattr(value, "code", str(value)))
def test_rotating_answers_the_documented_errors(
    client: TestClient, rotation_service: StubLastScanRotationService, error: DigitalizadoraError, status: HTTPStatus
) -> None:
    rotation_service.failure = error

    response = client.post(ROTATION_PATH)

    assert (response.status_code, response.json()) == (
        status,
        {"code": error.code, "message": CATALOG.message_for(error.code)},
    )


def test_an_unexpected_domain_error_answers_500(
    client: TestClient, rotation_service: StubLastScanRotationService
) -> None:
    rotation_service.failure = DigitalizadoraError("something else")

    assert client.post(ROTATION_PATH).status_code == HTTPStatus.INTERNAL_SERVER_ERROR


def test_the_error_statuses_cover_the_documented_codes() -> None:
    assert {code: int(status) for code, status in LAST_SCAN_ERROR_STATUSES.items()} == {
        "no_last_scan": 404,
        "scan_already_running": 409,
        "last_scan_file_missing": 409,
        "saved_scan_unreadable": 409,
        "insufficient_storage": 507,
        "output_folder_unavailable": 503,
    }


def test_the_rotation_is_a_post_only_route(client: TestClient) -> None:
    assert client.get(ROTATION_PATH).status_code == HTTPStatus.METHOD_NOT_ALLOWED


def test_rotating_asks_for_the_saved_jpeg_quality(
    client: TestClient, rotation_service: StubLastScanRotationService
) -> None:
    client.post(ROTATION_PATH)

    assert rotation_service.received_jpeg_qualities == [70]

from dataclasses import replace
from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog
from digitalizadora.controllers.last_scan_controller import LAST_SCAN_ERROR_STATUSES, LastScanController
from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.errors import (
    DigitalizadoraError,
    DraftStorageUnavailableError,
    ImageAdjustmentFailedError,
    InsufficientDraftStorageError,
    InsufficientStorageError,
    LastScanBusyError,
    LastScanFileMissingError,
    LastScanNotEditableError,
    LastScanReplacedError,
    NoLastScanError,
    OutputFolderUnavailableError,
    SavedScanUnreadableError,
    ScanAlreadyRunningError,
)
from digitalizadora.domain.image_adjustment import ImageAdjustment
from digitalizadora.domain.last_scan import SavedScanFile
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.services.application_settings_service import ApplicationSettingsService
from digitalizadora.services.last_scan_edit_service import LastScanEditResult
from tests.controllers.controller_test_support import StubFolderPreparer, build_test_client
from tests.fakes.in_memory_settings_repository import InMemoryApplicationSettingsRepository
from tests.fakes.page_crops import quadrilateral, rectangle
from tests.fakes.stored_scans import STORED_SCAN_SCANNED_AT, build_last_scan
from tests.fakes.stub_last_scan_edit_service import StubLastScanEditService

CATALOG = ErrorMessageCatalog()
SETTINGS = ApplicationSettings(
    output_folder=Path("/Volumes/External/scans"),
    output_format=OutputFormat.PDF,
    scan_settings=ScanPreset.DOCUMENT.settings,
    adjustment=ImageAdjustment(jpeg_quality=70),
)
ROTATION_PATH = "/api/scans/last/rotation"
CROPS_PATH = "/api/scans/last/crops"
DETECT_PATH = "/api/scans/last/crops/detect"
UPPER_CROP_BODY = {
    "top_left": {"x": 0.039, "y": 0.28},
    "top_right": {"x": 0.65, "y": 0.019},
    "bottom_right": {"x": 0.894, "y": 0.321},
    "bottom_left": {"x": 0.282, "y": 0.582},
}
UPPER_CROP = quadrilateral((0.039, 0.28), (0.65, 0.019), (0.894, 0.321), (0.282, 0.582))
EXPECTED_FAILURES = [
    (NoLastScanError("none"), HTTPStatus.NOT_FOUND),
    (LastScanReplacedError("newer"), HTTPStatus.CONFLICT),
    (ScanAlreadyRunningError("running"), HTTPStatus.CONFLICT),
    (LastScanBusyError("busy"), HTTPStatus.CONFLICT),
    (LastScanFileMissingError("gone"), HTTPStatus.CONFLICT),
    (SavedScanUnreadableError("broken"), HTTPStatus.CONFLICT),
    (LastScanNotEditableError("no master"), HTTPStatus.CONFLICT),
    (InsufficientStorageError("full"), HTTPStatus.INSUFFICIENT_STORAGE),
    (OutputFolderUnavailableError("disconnected"), HTTPStatus.SERVICE_UNAVAILABLE),
    (ImageAdjustmentFailedError("memory"), HTTPStatus.INTERNAL_SERVER_ERROR),
]
EDIT_REQUESTS = [
    pytest.param("POST", ROTATION_PATH, None, id="rotation"),
    pytest.param("PUT", CROPS_PATH, {"crops": [UPPER_CROP_BODY]}, id="crops"),
    pytest.param("POST", DETECT_PATH, None, id="detection"),
]


@pytest.fixture
def edit_service() -> StubLastScanEditService:
    return StubLastScanEditService()


@pytest.fixture
def client(edit_service: StubLastScanEditService) -> TestClient:
    settings_service = ApplicationSettingsService(
        InMemoryApplicationSettingsRepository(SETTINGS), StubFolderPreparer()
    )
    return build_test_client(LastScanController(edit_service, settings_service, CATALOG).build_router())


def send(client: TestClient, method: str, path: str, body: object):
    return client.request(method, path, json=body)


def test_rotating_the_last_scan_answers_the_scan_and_the_lists_of_files(client: TestClient) -> None:
    response = client.post(ROTATION_PATH)

    assert (response.status_code, response.json()) == (
        HTTPStatus.OK,
        {
            "last_result": {
                "scan_identifier": "9f3c1a2b4d5e6f70",
                "file_names": ["2026-10-13_15-30-12-000000000.pdf"],
                "output_folder": "/Volumes/Scans",
                "output_format": "pdf",
                "total_size_in_bytes": 1234,
                "scanned_at": STORED_SCAN_SCANNED_AT.isoformat(),
                "rotation_degrees": 0,
                "crops": [],
                "is_editable": True,
            },
            "deleted_file_names": [],
            "kept_file_names": [],
        },
    )


def test_the_answer_lists_the_files_deleted_and_the_files_kept(
    client: TestClient, edit_service: StubLastScanEditService
) -> None:
    edit_service.result = LastScanEditResult(
        build_last_scan(), deleted_file_names=("a.pdf",), kept_file_names=("b.pdf",)
    )

    body = client.post(ROTATION_PATH).json()

    assert (body["deleted_file_names"], body["kept_file_names"]) == (["a.pdf"], ["b.pdf"])


@pytest.mark.parametrize(("method", "path", "body"), EDIT_REQUESTS)
def test_every_edit_asks_for_the_saved_jpeg_quality(
    client: TestClient, edit_service: StubLastScanEditService, method: str, path: str, body: object
) -> None:
    send(client, method, path, body)

    assert edit_service.received_jpeg_qualities == [70]


@pytest.mark.parametrize(("method", "path", "body"), EDIT_REQUESTS)
@pytest.mark.parametrize(("error", "status"), EXPECTED_FAILURES, ids=lambda value: getattr(value, "code", str(value)))
def test_every_edit_answers_the_documented_errors(
    client: TestClient,
    edit_service: StubLastScanEditService,
    method: str,
    path: str,
    body: object,
    error: DigitalizadoraError,
    status: HTTPStatus,
) -> None:
    edit_service.failure = error

    response = send(client, method, path, body)

    assert (response.status_code, response.json()) == (
        status,
        {"code": error.code, "message": CATALOG.message_for(error.code)},
    )


@pytest.mark.parametrize(("method", "path", "body"), EDIT_REQUESTS)
@pytest.mark.parametrize(
    ("error", "quick_mode_code", "status"),
    [
        (InsufficientDraftStorageError("full"), "insufficient_last_scan_storage", HTTPStatus.INSUFFICIENT_STORAGE),
        (DraftStorageUnavailableError("broken"), "last_scan_storage_unavailable", HTTPStatus.SERVICE_UNAVAILABLE),
    ],
    ids=lambda value: getattr(value, "code", str(value)),
)
def test_the_errors_of_the_slot_speak_of_the_last_scan_and_not_of_document_pages(
    client: TestClient,
    edit_service: StubLastScanEditService,
    method: str,
    path: str,
    body: object,
    error: DigitalizadoraError,
    quick_mode_code: str,
    status: HTTPStatus,
) -> None:
    edit_service.failure = error

    response = send(client, method, path, body)

    assert (response.status_code, response.json()["code"]) == (status, quick_mode_code)


def test_an_unexpected_domain_error_answers_500(client: TestClient, edit_service: StubLastScanEditService) -> None:
    edit_service.failure = DigitalizadoraError("something else")

    assert client.post(ROTATION_PATH).status_code == HTTPStatus.INTERNAL_SERVER_ERROR


def test_the_error_statuses_cover_the_documented_codes() -> None:
    assert {code: int(status) for code, status in LAST_SCAN_ERROR_STATUSES.items()} == {
        "no_last_scan": 404,
        "last_scan_replaced": 409,
        "scan_already_running": 409,
        "last_scan_busy": 409,
        "last_scan_file_missing": 409,
        "saved_scan_unreadable": 409,
        "last_scan_not_editable": 409,
        "invalid_crop": 422,
        "invalid_page_rotation": 422,
        "invalid_scan_identifier": 422,
        "insufficient_last_scan_storage": 507,
        "last_scan_storage_unavailable": 503,
        "insufficient_storage": 507,
        "output_folder_unavailable": 503,
        "image_adjustment_failed": 500,
    }


def test_the_rotation_is_a_post_only_route(client: TestClient) -> None:
    assert client.get(ROTATION_PATH).status_code == HTTPStatus.METHOD_NOT_ALLOWED


def test_the_crops_route_is_a_put_only_route(client: TestClient) -> None:
    assert client.post(CROPS_PATH, json={"crops": []}).status_code == HTTPStatus.METHOD_NOT_ALLOWED


def test_the_detection_is_a_post_only_route(client: TestClient) -> None:
    assert client.get(DETECT_PATH).status_code == HTTPStatus.METHOD_NOT_ALLOWED


def test_setting_the_crops_passes_the_quadrilaterals_to_the_service(
    client: TestClient, edit_service: StubLastScanEditService
) -> None:
    client.put(CROPS_PATH, json={"crops": [UPPER_CROP_BODY]})

    assert edit_service.received_crops == [[UPPER_CROP]]


def test_an_empty_list_of_crops_removes_them(client: TestClient, edit_service: StubLastScanEditService) -> None:
    client.put(CROPS_PATH, json={"crops": []})

    assert edit_service.received_crops == [[]]


def test_two_crops_are_passed_in_the_order_given(client: TestClient, edit_service: StubLastScanEditService) -> None:
    lower_body = {
        "top_left": {"x": 0.17, "y": 0.6},
        "top_right": {"x": 0.88, "y": 0.6},
        "bottom_right": {"x": 0.88, "y": 0.95},
        "bottom_left": {"x": 0.17, "y": 0.95},
    }

    client.put(CROPS_PATH, json={"crops": [UPPER_CROP_BODY, lower_body]})

    assert edit_service.received_crops == [[UPPER_CROP, rectangle((0.17, 0.6, 0.88, 0.95))]]


def test_a_crop_outside_the_page_answers_422_and_never_reaches_the_service(
    client: TestClient, edit_service: StubLastScanEditService
) -> None:
    outside = {**UPPER_CROP_BODY, "top_left": {"x": -0.2, "y": 0.28}}

    response = client.put(CROPS_PATH, json={"crops": [outside]})

    assert (response.status_code, response.json()["code"], edit_service.calls) == (422, "invalid_crop", [])


def test_the_detection_says_whether_it_found_crops_and_how_many_regions_it_ignored(
    client: TestClient, edit_service: StubLastScanEditService
) -> None:
    edit_service.result = LastScanEditResult(build_last_scan(), crops_detected=True, ignored_region_count=1)

    body = client.post(DETECT_PATH).json()

    assert (body["crops_detected"], body["ignored_region_count"]) == (True, 1)


def test_the_detection_that_finds_nothing_says_so(client: TestClient) -> None:
    body = client.post(DETECT_PATH).json()

    assert (body["crops_detected"], body["ignored_region_count"]) == (False, 0)


def test_the_answer_of_two_files_names_both(client: TestClient, edit_service: StubLastScanEditService) -> None:
    two_files = (SavedScanFile("a.pdf", 1, 1), SavedScanFile("b.pdf", 2, 2))
    edit_service.result = LastScanEditResult(replace(build_last_scan(two_files)))

    assert client.post(ROTATION_PATH).json()["last_result"]["file_names"] == ["a.pdf", "b.pdf"]

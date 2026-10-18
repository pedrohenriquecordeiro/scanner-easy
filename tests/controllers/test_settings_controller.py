from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog
from digitalizadora.controllers.settings_controller import SettingsController
from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.capture_mode import CaptureMode
from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import OutputFolderUnavailableError
from digitalizadora.domain.image_adjustment import ImageAdjustment
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.services.application_settings_service import ApplicationSettingsService
from tests.controllers.controller_test_support import StubFolderPreparer, build_test_client
from tests.fakes.in_memory_settings_repository import InMemoryApplicationSettingsRepository

CATALOG = ErrorMessageCatalog()
INITIAL_SETTINGS = ApplicationSettings(
    output_folder=Path("/Volumes/Initial/scans"),
    output_format=OutputFormat.PDF,
    scan_settings=ScanPreset.DOCUMENT.settings,
    capture_mode=CaptureMode.DOCUMENT,
)
VALID_BODY = {
    "output_folder": "/Volumes/External/scans",
    "output_format": "jpg",
    "dots_per_inch": 600,
    "color_mode": "color",
}
INVALID_SETTINGS_BODY = {
    "code": "invalid_settings",
    "message": CATALOG.message_for("invalid_settings"),
}


@pytest.fixture
def settings_repository() -> InMemoryApplicationSettingsRepository:
    return InMemoryApplicationSettingsRepository(INITIAL_SETTINGS)


@pytest.fixture
def folder_preparer() -> StubFolderPreparer:
    return StubFolderPreparer()


@pytest.fixture
def client(
    settings_repository: InMemoryApplicationSettingsRepository,
    folder_preparer: StubFolderPreparer,
) -> TestClient:
    settings_service = ApplicationSettingsService(settings_repository, folder_preparer)
    controller = SettingsController(settings_service, CATALOG)
    return build_test_client(controller.build_router())


def test_get_settings_returns_the_saved_settings(client: TestClient) -> None:
    response = client.get("/api/settings")

    assert (response.status_code, response.json()) == (
        HTTPStatus.OK,
        {
            "output_folder": "/Volumes/Initial/scans",
            "output_format": "pdf",
            "dots_per_inch": 300,
            "color_mode": "color",
            "capture_mode": "document",
            "auto_crop": False,
            "crop_margin": True,
            "jpeg_quality": 90,
        },
    )


def test_put_settings_returns_the_new_settings(client: TestClient) -> None:
    response = client.put("/api/settings", json=VALID_BODY)

    assert (response.status_code, response.json()) == (
        HTTPStatus.OK,
        {
            **VALID_BODY,
            "capture_mode": "document",
            "auto_crop": False,
            "crop_margin": True,
            "jpeg_quality": 90,
        },
    )


def test_put_settings_saves_the_new_settings(
    client: TestClient, settings_repository: InMemoryApplicationSettingsRepository
) -> None:
    client.put("/api/settings", json=VALID_BODY)

    assert settings_repository.load() == ApplicationSettings(
        output_folder=Path("/Volumes/External/scans"),
        output_format=OutputFormat.JPEG,
        scan_settings=ScanSettings(600, ColorMode.COLOR),
        capture_mode=CaptureMode.DOCUMENT,
    )


def test_put_settings_with_an_unknown_format_answers_422(client: TestClient) -> None:
    response = client.put("/api/settings", json={**VALID_BODY, "output_format": "tiff"})

    assert (response.status_code, response.json()) == (
        HTTPStatus.UNPROCESSABLE_ENTITY,
        INVALID_SETTINGS_BODY,
    )


@pytest.mark.parametrize(
    "invalid_folder",
    ["scans", "/Volumes/External/sc\u0000ans", "~digitalizadora-user-that-does-not-exist/scans"],
)
def test_put_settings_with_an_invalid_folder_answers_422(
    client: TestClient, invalid_folder: str
) -> None:
    response = client.put("/api/settings", json={**VALID_BODY, "output_folder": invalid_folder})

    assert (response.status_code, response.json()) == (
        HTTPStatus.UNPROCESSABLE_ENTITY,
        INVALID_SETTINGS_BODY,
    )


def test_put_settings_with_an_unavailable_folder_answers_422(
    client: TestClient, folder_preparer: StubFolderPreparer
) -> None:
    folder_preparer.failure = OutputFolderUnavailableError("volume disconnected")

    response = client.put("/api/settings", json=VALID_BODY)

    assert (response.status_code, response.json()) == (
        HTTPStatus.UNPROCESSABLE_ENTITY,
        {
            "code": "output_folder_unavailable",
            "message": CATALOG.message_for("output_folder_unavailable"),
        },
    )


def test_a_rejected_put_leaves_the_saved_settings_untouched(
    client: TestClient,
    settings_repository: InMemoryApplicationSettingsRepository,
) -> None:
    client.put("/api/settings", json={**VALID_BODY, "dots_per_inch": 301})

    assert settings_repository.load() == INITIAL_SETTINGS


def test_put_settings_with_the_single_mode_saves_it(
    client: TestClient, settings_repository: InMemoryApplicationSettingsRepository
) -> None:
    client.put("/api/settings", json={**VALID_BODY, "capture_mode": "single"})

    assert settings_repository.load().capture_mode is CaptureMode.SINGLE


def test_put_settings_with_the_single_mode_returns_it(client: TestClient) -> None:
    response = client.put("/api/settings", json={**VALID_BODY, "capture_mode": "single"})

    assert response.json()["capture_mode"] == "single"


def test_put_settings_with_a_null_capture_mode_keeps_the_saved_mode(client: TestClient) -> None:
    response = client.put("/api/settings", json={**VALID_BODY, "capture_mode": None})

    assert (response.status_code, response.json()["capture_mode"]) == (HTTPStatus.OK, "document")


def test_put_settings_with_an_unknown_capture_mode_answers_422(client: TestClient) -> None:
    response = client.put("/api/settings", json={**VALID_BODY, "capture_mode": "batch"})

    assert (response.status_code, response.json()) == (
        HTTPStatus.UNPROCESSABLE_ENTITY,
        INVALID_SETTINGS_BODY,
    )


def test_put_settings_with_an_unknown_capture_mode_saves_nothing(
    client: TestClient, settings_repository: InMemoryApplicationSettingsRepository
) -> None:
    client.put("/api/settings", json={**VALID_BODY, "capture_mode": "batch"})

    assert settings_repository.load() == INITIAL_SETTINGS


def test_put_settings_with_an_unknown_capture_mode_prepares_no_folder(
    client: TestClient, folder_preparer: StubFolderPreparer
) -> None:
    client.put("/api/settings", json={**VALID_BODY, "capture_mode": "batch"})

    assert folder_preparer.prepared_folders == []


def test_put_settings_without_a_quality_keeps_the_saved_quality(client: TestClient) -> None:
    body_without_quality = {"output_folder": "/Volumes/External/scans", "output_format": "jpg"}

    response = client.put("/api/settings", json=body_without_quality)

    assert (response.json()["dots_per_inch"], response.json()["color_mode"]) == (300, "color")


def test_put_settings_with_a_resolution_and_a_colour_mode_saves_them(client: TestClient) -> None:
    response = client.put("/api/settings", json={**VALID_BODY, "dots_per_inch": 1200, "color_mode": "grayscale"})

    assert (response.json()["dots_per_inch"], response.json()["color_mode"]) == (1200, "grayscale")


def test_put_settings_does_not_report_a_preset(client: TestClient) -> None:
    response = client.put("/api/settings", json=VALID_BODY)

    assert "scan_preset" not in response.json()


def test_put_settings_does_not_report_a_rotation(client: TestClient) -> None:
    response = client.put("/api/settings", json=VALID_BODY)

    assert "rotation_degrees" not in response.json()


def test_an_old_client_that_sends_a_preset_and_a_rotation_is_accepted(client: TestClient) -> None:
    response = client.put(
        "/api/settings", json={**VALID_BODY, "scan_preset": "document_economy", "rotation_degrees": 180}
    )

    assert response.status_code == HTTPStatus.OK


def test_the_preset_and_the_rotation_of_an_old_client_are_ignored(
    client: TestClient, settings_repository: InMemoryApplicationSettingsRepository
) -> None:
    client.put("/api/settings", json={**VALID_BODY, "scan_preset": "document_economy", "rotation_degrees": 180})

    assert settings_repository.load().scan_settings == ScanSettings(600, ColorMode.COLOR)


def test_an_old_preset_alone_leaves_the_saved_quality_as_it_is(
    client: TestClient, settings_repository: InMemoryApplicationSettingsRepository
) -> None:
    body_with_a_preset_only = {
        "output_folder": "/Volumes/External/scans",
        "output_format": "jpg",
        "scan_preset": "photo",
    }

    client.put("/api/settings", json=body_with_a_preset_only)

    assert settings_repository.load().scan_settings == INITIAL_SETTINGS.scan_settings


def test_an_unknown_old_preset_is_ignored_too(client: TestClient) -> None:
    response = client.put("/api/settings", json={**VALID_BODY, "scan_preset": "poster"})

    assert response.status_code == HTTPStatus.OK


def test_put_settings_saves_the_crop(
    client: TestClient, settings_repository: InMemoryApplicationSettingsRepository
) -> None:
    client.put("/api/settings", json={**VALID_BODY, "auto_crop": True})

    assert settings_repository.load().adjustment == ImageAdjustment(auto_crop=True)


def test_put_settings_saves_the_jpeg_quality(
    client: TestClient, settings_repository: InMemoryApplicationSettingsRepository
) -> None:
    response = client.put("/api/settings", json={**VALID_BODY, "jpeg_quality": 72})

    assert (response.json()["jpeg_quality"], settings_repository.load().adjustment.jpeg_quality) == (72, 72)


def test_put_settings_without_a_jpeg_quality_keeps_the_saved_one(client: TestClient) -> None:
    client.put("/api/settings", json={**VALID_BODY, "jpeg_quality": 72})

    response = client.put("/api/settings", json=VALID_BODY)

    assert response.json()["jpeg_quality"] == 72


def test_put_settings_with_a_null_jpeg_quality_keeps_the_saved_one(client: TestClient) -> None:
    client.put("/api/settings", json={**VALID_BODY, "jpeg_quality": 72})

    response = client.put("/api/settings", json={**VALID_BODY, "jpeg_quality": None})

    assert response.json()["jpeg_quality"] == 72


@pytest.mark.parametrize("invalid_quality", [49, 101, 0, -1, 10**30])
def test_put_settings_with_a_jpeg_quality_outside_the_range_answers_422(
    client: TestClient, settings_repository: InMemoryApplicationSettingsRepository, invalid_quality: int
) -> None:
    response = client.put("/api/settings", json={**VALID_BODY, "jpeg_quality": invalid_quality})

    assert (response.status_code, response.json()["code"], settings_repository.load().adjustment.jpeg_quality) == (
        HTTPStatus.UNPROCESSABLE_ENTITY,
        "invalid_settings",
        90,
    )


@pytest.mark.parametrize("invalid_quality", [True, 90.5, "90", [90]])
def test_put_settings_with_a_jpeg_quality_that_is_not_a_whole_number_is_refused(
    client: TestClient, invalid_quality: object
) -> None:
    response = client.put("/api/settings", json={**VALID_BODY, "jpeg_quality": invalid_quality})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_the_body_of_a_get_is_a_valid_body_for_a_put(client: TestClient) -> None:
    saved_body = client.get("/api/settings").json()

    response = client.put("/api/settings", json=saved_body)

    assert (response.status_code, response.json()) == (HTTPStatus.OK, saved_body)


@pytest.mark.parametrize(
    "invalid_fields",
    [{"dots_per_inch": 301}, {"color_mode": "sepia"}],
)
def test_put_settings_with_an_invalid_quality_answers_422(
    client: TestClient, invalid_fields: dict[str, object]
) -> None:
    response = client.put("/api/settings", json={**VALID_BODY, **invalid_fields})

    assert (response.status_code, response.json()) == (HTTPStatus.UNPROCESSABLE_ENTITY, INVALID_SETTINGS_BODY)


@pytest.mark.parametrize(
    "mistyped_fields",
    [{"dots_per_inch": "300"}, {"dots_per_inch": 300.5}, {"auto_crop": "true"}],
)
def test_put_settings_with_a_mistyped_field_answers_the_standard_422(
    client: TestClient, mistyped_fields: dict[str, object]
) -> None:
    response = client.put("/api/settings", json={**VALID_BODY, **mistyped_fields})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_a_mistyped_field_saves_nothing(
    client: TestClient, settings_repository: InMemoryApplicationSettingsRepository
) -> None:
    client.put("/api/settings", json={**VALID_BODY, "auto_crop": "true"})

    assert settings_repository.load() == INITIAL_SETTINGS


def test_put_settings_saves_the_crop_margin(
    client: TestClient, settings_repository: InMemoryApplicationSettingsRepository
) -> None:
    client.put("/api/settings", json={**VALID_BODY, "crop_margin": False})

    assert settings_repository.load().adjustment.crop_margin is False


def test_a_mistyped_crop_margin_answers_422_and_saves_nothing(
    client: TestClient, settings_repository: InMemoryApplicationSettingsRepository
) -> None:
    response = client.put("/api/settings", json={**VALID_BODY, "crop_margin": "false"})

    assert (response.status_code, settings_repository.load()) == (HTTPStatus.UNPROCESSABLE_ENTITY, INITIAL_SETTINGS)

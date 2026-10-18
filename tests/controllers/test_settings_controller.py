from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog
from digitalizadora.controllers.settings_controller import SettingsController
from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.errors import OutputFolderUnavailableError
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.services.application_settings_service import ApplicationSettingsService
from tests.controllers.controller_test_support import StubFolderPreparer, build_test_client
from tests.fakes.in_memory_settings_repository import InMemoryApplicationSettingsRepository

CATALOG = ErrorMessageCatalog()
INITIAL_SETTINGS = ApplicationSettings(
    output_folder=Path("/Volumes/Initial/scans"),
    output_format=OutputFormat.PDF,
    scan_preset=ScanPreset.DOCUMENT,
)
VALID_BODY = {
    "output_folder": "/Volumes/External/scans",
    "output_format": "jpg",
    "scan_preset": "photo",
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
            "scan_preset": "document",
        },
    )


def test_put_settings_returns_the_new_settings(client: TestClient) -> None:
    response = client.put("/api/settings", json=VALID_BODY)

    assert (response.status_code, response.json()) == (HTTPStatus.OK, VALID_BODY)


def test_put_settings_saves_the_new_settings(
    client: TestClient, settings_repository: InMemoryApplicationSettingsRepository
) -> None:
    client.put("/api/settings", json=VALID_BODY)

    assert settings_repository.load() == ApplicationSettings(
        output_folder=Path("/Volumes/External/scans"),
        output_format=OutputFormat.JPEG,
        scan_preset=ScanPreset.PHOTO,
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
    client.put("/api/settings", json={**VALID_BODY, "scan_preset": "poster"})

    assert settings_repository.load() == INITIAL_SETTINGS

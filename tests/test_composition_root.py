import dataclasses
import json
import logging
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from digitalizadora.application_factory import create_application
from digitalizadora.composition_root import (
    DRAFTS_FOLDER_NAME,
    ApplicationContainer,
    ContainerOverrides,
    build_container,
    build_scanner_http_client,
)
from digitalizadora.configuration import ApplicationConfiguration
from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog
from digitalizadora.infrastructure.bonjour_scanner_discovery import ServiceRecord
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter
from digitalizadora.repositories.file_system_document_draft_repository import OWNER_LOCK_FILE_NAME
from digitalizadora.repositories.json_scanner_endpoint_repository import JsonScannerEndpointRepository
from digitalizadora.services.image_pixel_limit import MAXIMUM_SCANNER_IMAGE_PIXELS
from tests.fakes.configuration_builder import TEST_PORT, build_application_configuration

SCANNER_ADDRESS = "http://scanner.test/eSCL"
LOOPBACK_BASE_ADDRESS = f"http://127.0.0.1:{TEST_PORT}"
LOCALHOST_BASE_ADDRESS = f"http://localhost:{TEST_PORT}"
OTHER_PORT_BASE_ADDRESS = f"http://127.0.0.1:{TEST_PORT + 1}"
STATE_CHANGING_HEADERS = {"X-Requested-With": "digitalizadora"}
FIXED_FREE_SPACE_IN_BYTES = 50 * 1024**3
PILLOW_DEFAULT_PIXEL_LIMIT = 89_478_485
EXPECTED_SCANNER_TIMEOUT = httpx.Timeout(30.0, connect=5.0, read=180.0)


class RecordingScannerTransport(httpx.AsyncBaseTransport):
    def __init__(self) -> None:
        self.request_count = 0
        self.is_closed = False

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.request_count += 1
        raise AssertionError("The scanner must not be contacted by this test")

    async def aclose(self) -> None:
        self.is_closed = True


class RecordingServiceRecordSource:
    def __init__(self) -> None:
        self.collect_count = 0

    async def collect_records(self, timeout_seconds: float) -> list[ServiceRecord]:
        self.collect_count += 1
        return []


@dataclass(frozen=True)
class ScannerDoubles:
    transport: RecordingScannerTransport
    record_source: RecordingServiceRecordSource


@pytest.fixture
def scanner_doubles() -> ScannerDoubles:
    return ScannerDoubles(RecordingScannerTransport(), RecordingServiceRecordSource())


@pytest.fixture
def overrides(scanner_doubles: ScannerDoubles) -> ContainerOverrides:
    return ContainerOverrides(
        scanner_transport=scanner_doubles.transport, service_record_source=scanner_doubles.record_source
    )


@pytest.fixture
def configuration(tmp_path: Path) -> ApplicationConfiguration:
    return build_application_configuration(tmp_path, None)


def build_client(container: ApplicationContainer, base_address: str) -> TestClient:
    application = create_application(container.controllers, container.web_configuration)
    return TestClient(application, base_url=base_address)


def save_settings_with_output_folder(configuration: ApplicationConfiguration, output_folder: Path) -> None:
    configuration.data_directory.mkdir(parents=True)
    document = {"output_folder": str(output_folder), "output_format": "pdf", "scan_preset": "document"}
    (configuration.data_directory / "settings.json").write_text(json.dumps(document), encoding="utf-8")


def test_health_endpoint_answers_ok(configuration: ApplicationConfiguration, overrides: ContainerOverrides) -> None:
    with build_client(build_container(configuration, overrides), LOOPBACK_BASE_ADDRESS) as client:
        response = client.get("/api/health")
    assert (response.status_code, response.json()) == (200, {"status": "ok"})


def test_state_endpoint_reports_default_settings(
    configuration: ApplicationConfiguration, overrides: ContainerOverrides
) -> None:
    with build_client(build_container(configuration, overrides), LOOPBACK_BASE_ADDRESS) as client:
        response = client.get("/api/state")
    expected_settings = {
        "output_folder": str(configuration.default_output_folder),
        "output_format": "pdf",
        "dots_per_inch": 300,
        "color_mode": "color",
        "capture_mode": "single",
        "auto_crop": False,
    }
    assert (response.status_code, response.json()["settings"]) == (200, expected_settings)


def test_state_endpoint_reports_an_idle_scanner_without_history(
    configuration: ApplicationConfiguration, overrides: ContainerOverrides
) -> None:
    with build_client(build_container(configuration, overrides), LOOPBACK_BASE_ADDRESS) as client:
        state = client.get("/api/state").json()
    assert (state["scan_phase"], state["scans_completed"], state["last_result"], state["last_error"]) == (
        "idle",
        0,
        None,
        None,
    )


def test_free_space_reader_override_reaches_the_state(
    configuration: ApplicationConfiguration, overrides: ContainerOverrides
) -> None:
    fixed_overrides = dataclasses.replace(overrides, free_space_reader=lambda folder: FIXED_FREE_SPACE_IN_BYTES)
    with build_client(build_container(configuration, fixed_overrides), LOOPBACK_BASE_ADDRESS) as client:
        storage = client.get("/api/state").json()["storage"]
    assert storage["free_space_in_bytes"] == FIXED_FREE_SPACE_IN_BYTES


def test_localhost_host_header_is_accepted(
    configuration: ApplicationConfiguration, overrides: ContainerOverrides
) -> None:
    with build_client(build_container(configuration, overrides), LOCALHOST_BASE_ADDRESS) as client:
        assert client.get("/api/health").status_code == HTTPStatus.OK


def test_host_header_with_another_port_is_forbidden(
    configuration: ApplicationConfiguration, overrides: ContainerOverrides
) -> None:
    with build_client(build_container(configuration, overrides), OTHER_PORT_BASE_ADDRESS) as client:
        assert client.get("/api/health").status_code == HTTPStatus.FORBIDDEN


def test_invalid_settings_body_is_answered_with_the_catalog_message(
    configuration: ApplicationConfiguration, overrides: ContainerOverrides
) -> None:
    with build_client(build_container(configuration, overrides), LOOPBACK_BASE_ADDRESS) as client:
        response = client.put("/api/settings", json={}, headers=STATE_CHANGING_HEADERS)
    expected_body = {"code": "invalid_settings", "message": ErrorMessageCatalog().message_for("invalid_settings")}
    assert (response.status_code, response.json()) == (HTTPStatus.UNPROCESSABLE_ENTITY, expected_body)


def test_scanner_address_override_is_persisted_in_the_data_directory(
    tmp_path: Path, overrides: ContainerOverrides
) -> None:
    configuration = build_application_configuration(tmp_path, SCANNER_ADDRESS)
    build_container(configuration, overrides)
    repository = JsonScannerEndpointRepository(
        configuration.data_directory / "scanner-endpoint.json", AtomicFileWriter()
    )
    saved_endpoint = repository.load()
    assert saved_endpoint is not None and saved_endpoint.base_address == SCANNER_ADDRESS


def test_no_endpoint_file_is_written_without_override(
    configuration: ApplicationConfiguration, overrides: ContainerOverrides
) -> None:
    build_container(configuration, overrides)
    assert not (configuration.data_directory / "scanner-endpoint.json").exists()


def test_startup_creates_the_default_output_folder(
    configuration: ApplicationConfiguration, overrides: ContainerOverrides
) -> None:
    build_container(configuration, overrides)
    assert configuration.default_output_folder.is_dir()


def test_startup_prepares_the_saved_output_folder(
    tmp_path: Path, configuration: ApplicationConfiguration, overrides: ContainerOverrides
) -> None:
    saved_folder = tmp_path / "external-disk" / "Scans"
    save_settings_with_output_folder(configuration, saved_folder)
    build_container(configuration, overrides)
    assert saved_folder.is_dir()


def test_startup_does_not_recreate_the_default_folder_when_another_is_saved(
    tmp_path: Path, configuration: ApplicationConfiguration, overrides: ContainerOverrides
) -> None:
    save_settings_with_output_folder(configuration, tmp_path / "external-disk" / "Scans")
    build_container(configuration, overrides)
    assert not configuration.default_output_folder.exists()


def test_unavailable_output_folder_at_startup_is_only_logged(
    tmp_path: Path, overrides: ContainerOverrides, caplog: pytest.LogCaptureFixture
) -> None:
    blocking_file = tmp_path / "not-a-folder"
    blocking_file.write_bytes(b"")
    blocked_configuration = dataclasses.replace(
        build_application_configuration(tmp_path, None), default_output_folder=blocking_file / "scans"
    )
    with caplog.at_level(logging.WARNING, logger="digitalizadora.composition_root"):
        build_container(blocked_configuration, overrides)
    assert "output folder is not ready at startup" in caplog.text


def test_web_configuration_points_to_the_packaged_interface(
    configuration: ApplicationConfiguration, overrides: ContainerOverrides
) -> None:
    container = build_container(configuration, overrides)
    assert (container.web_configuration.static_directory / "index.html").is_file()


def test_allowed_hosts_cover_loopback_and_localhost(
    configuration: ApplicationConfiguration, overrides: ContainerOverrides
) -> None:
    container = build_container(configuration, overrides)
    assert container.web_configuration.allowed_hosts == frozenset(
        {f"127.0.0.1:{TEST_PORT}", f"localhost:{TEST_PORT}"}
    )


async def test_shutdown_callback_closes_the_scanner_http_client(
    configuration: ApplicationConfiguration, overrides: ContainerOverrides, scanner_doubles: ScannerDoubles
) -> None:
    container = build_container(configuration, overrides)
    (shutdown_callback,) = container.web_configuration.shutdown_callbacks
    await shutdown_callback()
    assert scanner_doubles.transport.is_closed


def test_serving_state_never_contacts_the_scanner_or_discovery(
    tmp_path: Path, overrides: ContainerOverrides, scanner_doubles: ScannerDoubles
) -> None:
    container = build_container(build_application_configuration(tmp_path, SCANNER_ADDRESS), overrides)
    with build_client(container, LOOPBACK_BASE_ADDRESS) as client:
        client.get("/api/health")
        client.get("/api/state")
    assert (scanner_doubles.transport.request_count, scanner_doubles.record_source.collect_count) == (0, 0)


def test_printer_refresh_searches_through_the_injected_record_source(
    configuration: ApplicationConfiguration, overrides: ContainerOverrides, scanner_doubles: ScannerDoubles
) -> None:
    with build_client(build_container(configuration, overrides), LOOPBACK_BASE_ADDRESS) as client:
        client.post("/api/printer/refresh", headers=STATE_CHANGING_HEADERS)
    assert scanner_doubles.record_source.collect_count == 1


async def test_scanner_http_client_uses_the_gate_0_timeouts() -> None:
    async with build_scanner_http_client() as http_client:
        assert http_client.timeout == EXPECTED_SCANNER_TIMEOUT


async def test_scanner_http_client_does_not_follow_redirects() -> None:
    async with build_scanner_http_client() as http_client:
        assert http_client.follow_redirects is False


async def test_scanner_http_client_ignores_proxy_settings() -> None:
    async with build_scanner_http_client() as http_client:
        assert http_client.trust_env is False


def test_document_endpoint_reports_no_draft_on_a_fresh_start(
    configuration: ApplicationConfiguration, overrides: ContainerOverrides
) -> None:
    with build_client(build_container(configuration, overrides), LOOPBACK_BASE_ADDRESS) as client:
        body = client.get("/api/document").json()
    assert (body["revision"], body["document"], body["recovery"]) == (0, None, None)


def test_state_endpoint_reports_an_empty_document_summary(
    configuration: ApplicationConfiguration, overrides: ContainerOverrides
) -> None:
    fixed_overrides = dataclasses.replace(overrides, free_space_reader=lambda folder: FIXED_FREE_SPACE_IN_BYTES)
    with build_client(build_container(configuration, fixed_overrides), LOOPBACK_BASE_ADDRESS) as client:
        summary = client.get("/api/state").json()["document"]
    draft_storage = summary["draft_storage"]
    assert (summary["page_count"], draft_storage["free_space_in_bytes"], draft_storage["available"]) == (
        0,
        FIXED_FREE_SPACE_IN_BYTES,
        True,
    )


def test_startup_claims_the_drafts_folder(
    configuration: ApplicationConfiguration, overrides: ContainerOverrides
) -> None:
    build_container(configuration, overrides)
    assert (configuration.data_directory / DRAFTS_FOLDER_NAME / OWNER_LOCK_FILE_NAME).is_file()


def test_containers_in_different_data_directories_have_different_sessions(
    tmp_path: Path, overrides: ContainerOverrides
) -> None:
    draft_sessions = []
    for folder_name in ("first", "second"):
        container = build_container(build_application_configuration(tmp_path / folder_name, None), overrides)
        with build_client(container, LOOPBACK_BASE_ADDRESS) as client:
            draft_sessions.append(client.get("/api/document").json()["draft_session"])
    assert draft_sessions[0] != draft_sessions[1]


def test_building_the_container_raises_the_pixel_limit_to_the_scanner_size(
    configuration: ApplicationConfiguration, overrides: ContainerOverrides, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", PILLOW_DEFAULT_PIXEL_LIMIT)

    build_container(configuration, overrides)

    assert Image.MAX_IMAGE_PIXELS == MAXIMUM_SCANNER_IMAGE_PIXELS


def test_an_old_settings_file_with_only_a_preset_is_served_with_the_quality_of_the_preset(
    configuration: ApplicationConfiguration, overrides: ContainerOverrides
) -> None:
    configuration.data_directory.mkdir(parents=True)
    old_document = {
        "output_folder": str(configuration.default_output_folder),
        "output_format": "jpg",
        "scan_preset": "photo",
    }
    (configuration.data_directory / "settings.json").write_text(json.dumps(old_document), encoding="utf-8")

    with build_client(build_container(configuration, overrides), LOOPBACK_BASE_ADDRESS) as client:
        settings = client.get("/api/settings").json()

    assert (settings["dots_per_inch"], settings["color_mode"]) == (600, "color")

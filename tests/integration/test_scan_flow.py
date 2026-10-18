import asyncio
import re
import shutil
import time
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import httpx
import pikepdf
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from starlette.types import ASGIApp, Receive, Scope, Send

from digitalizadora.application_factory import create_application
from digitalizadora.composition_root import ContainerOverrides, build_container
from digitalizadora.configuration import ApplicationConfiguration
from digitalizadora.domain.errors import OutputFolderUnavailableError
from digitalizadora.infrastructure.bonjour_scanner_discovery import ServiceRecord
from digitalizadora.infrastructure.escl.escl_scanner_gateway import EsclGatewayTiming
from digitalizadora.simulator.fake_escl_scanner_app import FakeScannerBehavior, create_fake_escl_scanner_app
from tests.fakes.configuration_builder import TEST_PORT, build_application_configuration

BASE_ADDRESS = f"http://127.0.0.1:{TEST_PORT}"
SCANNER_ADDRESS = "http://scanner.test/eSCL"
STATE_CHANGING_HEADERS = {"X-Requested-With": "digitalizadora"}
DOCUMENT_PATH_SUFFIX = "/NextDocument"
SCAN_JOBS_PATH_SUFFIX = "/ScanJobs"
SCANNER_STATUS_PATH_SUFFIX = "/ScannerStatus"
JOB_PATH_PATTERN = re.compile(r"^/eSCL/ScanJobs/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
ABUNDANT_FREE_SPACE_BYTES = 100 * 1024**3
PROCESSING_POLLS_AFTER_DOCUMENT = 2
JPEG_MARKER = b"\xff\xd8"
ECONOMY_PRESET_DOTS_PER_INCH = 200
MAXIMUM_STATE_POLLS = 500
STATE_POLL_INTERVAL_SECONDS = 0.01
DOCUMENT_REQUEST_TIMEOUT_SECONDS = 5.0
TIMESTAMP_NAME_PATTERN = r"\d{4}_\d{2}_\d{2}__\d{2}_\d{2}_\d{2}_\d{9}"
PDF_NAME_PATTERN = re.compile(rf"^{TIMESTAMP_NAME_PATTERN}\.pdf$")
JPG_NAME_PATTERN = re.compile(rf"^{TIMESTAMP_NAME_PATTERN}\.jpg$")
OUTPUT_FOLDER_UNAVAILABLE_MESSAGE = (
    "Não consigo gravar na pasta de saída. Se for um disco externo, confira se está conectado."
)
INSUFFICIENT_STORAGE_MESSAGE = "Pouco espaço livre na pasta de saída. Use um disco externo ou libere espaço."
SCAN_ALREADY_RUNNING_MESSAGE = "Já existe uma digitalização em andamento."
SCANNER_UNREACHABLE_MESSAGE = (
    "Não encontrei a impressora. Confira se está ligada e com o cabo USB conectado ao Mac. "
    "Sem o cabo, confira se a luz do Wi-Fi está acesa e se ela está na mesma rede do Mac (2,4 GHz)."
)
UNAVAILABLE_STORAGE = {"free_space_in_bytes": 0, "estimated_pages_remaining": 0, "output_folder_available": False}


class InstrumentedScannerApp:
    def __init__(self, inner_application: ASGIApp) -> None:
        self.inner_application = inner_application
        self.received_requests: list[tuple[str, str]] = []
        self.document_gate = asyncio.Event()
        self.document_gate.set()
        self.document_requested = asyncio.Event()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            self.received_requests.append((scope["method"], scope["path"]))
            if scope["path"].endswith(DOCUMENT_PATH_SUFFIX):
                self.document_requested.set()
                await self.document_gate.wait()
        await self.inner_application(scope, receive, send)

    def paths_ending_with(self, path_suffix: str) -> list[str]:
        return [path for _, path in self.received_requests if path.endswith(path_suffix)]


class AdjustableFreeSpaceReader:
    """Follows the read_free_space_in_bytes contract: a missing folder raises OutputFolderUnavailableError."""

    def __init__(self, free_space_in_bytes: int) -> None:
        self.free_space_in_bytes = free_space_in_bytes

    def __call__(self, folder: Path) -> int:
        if not folder.is_dir():
            raise OutputFolderUnavailableError(f"Output folder {folder} does not exist")
        return self.free_space_in_bytes


class EmptyServiceRecordSource:
    """Stands in for DNS-SD, so the new search after a connection failure never touches the Mac's mDNS."""

    def __init__(self) -> None:
        self.collection_count = 0

    async def collect_records(self, timeout_seconds: float) -> list[ServiceRecord]:
        self.collection_count += 1
        return []


@dataclass(frozen=True)
class ScanEnvironment:
    configuration: ApplicationConfiguration
    scanner_app: InstrumentedScannerApp
    free_space_reader: AdjustableFreeSpaceReader


async def yield_without_waiting(seconds: float) -> None:
    await asyncio.sleep(0)


def build_application_with_overrides(configuration: ApplicationConfiguration, overrides: ContainerOverrides) -> FastAPI:
    container = build_container(configuration, overrides)
    return create_application(container.controllers, container.web_configuration)


def build_application(scan_environment: ScanEnvironment) -> FastAPI:
    overrides = ContainerOverrides(
        scanner_transport=httpx.ASGITransport(app=scan_environment.scanner_app),
        gateway_timing=EsclGatewayTiming(sleep=yield_without_waiting),
        free_space_reader=scan_environment.free_space_reader,
    )
    return build_application_with_overrides(scan_environment.configuration, overrides)


def build_settings(output_folder: Path, output_format: str) -> dict[str, str]:
    return {
        "output_folder": str(output_folder),
        "output_format": output_format,
        "dots_per_inch": 200,
        "color_mode": "grayscale",
    }


def has_completed_scans(expected_count: int) -> Callable[[dict], bool]:
    return lambda state: state["scan_phase"] == "idle" and state["scans_completed"] == expected_count


def has_failed(state: dict) -> bool:
    return state["scan_phase"] == "idle" and state["last_error"] is not None


def wait_for_state(client: TestClient, condition: Callable[[dict], bool]) -> dict:
    state: dict = {}
    for _ in range(MAXIMUM_STATE_POLLS):
        state = client.get("/api/state").json()
        if condition(state):
            return state
        time.sleep(STATE_POLL_INTERVAL_SECONDS)
    raise AssertionError(f"The expected state never arrived; last state: {state}")


def save_settings(client: TestClient, output_folder: Path, output_format: str) -> None:
    response = client.put(
        "/api/settings", json=build_settings(output_folder, output_format), headers=STATE_CHANGING_HEADERS
    )
    assert response.status_code == 200


def scan_once(client: TestClient, output_folder: Path, output_format: str) -> dict:
    save_settings(client, output_folder, output_format)
    scan_count_before = client.get("/api/state").json()["scans_completed"]
    scan_response = client.post("/api/scans", headers=STATE_CHANGING_HEADERS)
    assert scan_response.status_code == 202
    return wait_for_state(client, has_completed_scans(scan_count_before + 1))


def saved_file_path(state: dict) -> Path:
    last_result = state["last_result"]
    return Path(last_result["output_folder"]) / last_result["file_names"][0]


def find_job_path(scanner_app: InstrumentedScannerApp) -> str:
    return scanner_app.paths_ending_with(DOCUMENT_PATH_SUFFIX)[0].removesuffix(DOCUMENT_PATH_SUFFIX)


def count_status_reads_between_job_creations(scanner_app: InstrumentedScannerApp) -> int:
    paths = [path for _, path in scanner_app.received_requests]
    job_creation_positions = [index for index, path in enumerate(paths) if path.endswith(SCAN_JOBS_PATH_SUFFIX)]
    first_creation, second_creation = job_creation_positions[:2]
    return sum(path.endswith(SCANNER_STATUS_PATH_SUFFIX) for path in paths[first_creation:second_creation])


@pytest.fixture
def output_folder(tmp_path: Path) -> Path:
    return tmp_path / "out"


@pytest.fixture
def scan_environment(tmp_path: Path) -> ScanEnvironment:
    fake_scanner = create_fake_escl_scanner_app(
        FakeScannerBehavior(processing_polls_after_document=PROCESSING_POLLS_AFTER_DOCUMENT)
    )
    return ScanEnvironment(
        configuration=build_application_configuration(tmp_path, SCANNER_ADDRESS),
        scanner_app=InstrumentedScannerApp(fake_scanner),
        free_space_reader=AdjustableFreeSpaceReader(ABUNDANT_FREE_SPACE_BYTES),
    )


@pytest.fixture
def client(scan_environment: ScanEnvironment) -> Iterator[TestClient]:
    application = build_application(scan_environment)
    # A failed scan is reported through /api/state, so the POST itself must not re-raise it.
    with TestClient(application, base_url=BASE_ADDRESS, raise_server_exceptions=False) as test_client:
        yield test_client


def test_scan_request_is_accepted(client: TestClient, output_folder: Path) -> None:
    save_settings(client, output_folder, "pdf")
    response = client.post("/api/scans", headers=STATE_CHANGING_HEADERS)
    assert (response.status_code, response.json()) == (202, {"accepted": True})


def test_state_reports_the_completed_pdf_scan(client: TestClient, output_folder: Path) -> None:
    state = scan_once(client, output_folder, "pdf")
    assert PDF_NAME_PATTERN.match(state["last_result"]["file_names"][0])


def test_completed_scan_leaves_the_application_idle_with_one_scan(client: TestClient, output_folder: Path) -> None:
    state = scan_once(client, output_folder, "pdf")
    assert (state["scan_phase"], state["scans_completed"]) == ("idle", 1)


def test_saved_pdf_has_exactly_one_page(client: TestClient, output_folder: Path) -> None:
    state = scan_once(client, output_folder, "pdf")
    with pikepdf.open(saved_file_path(state)) as document:
        assert len(document.pages) == 1


def test_second_scan_as_jpg_gets_a_timestamp_name(client: TestClient, output_folder: Path) -> None:
    scan_once(client, output_folder, "pdf")
    state = scan_once(client, output_folder, "jpg")
    assert JPG_NAME_PATTERN.match(state["last_result"]["file_names"][0])


def test_second_scan_waits_until_the_printer_is_idle_again(
    client: TestClient, scan_environment: ScanEnvironment, output_folder: Path
) -> None:
    scan_once(client, output_folder, "pdf")
    scan_once(client, output_folder, "jpg")
    status_reads = count_status_reads_between_job_creations(scan_environment.scanner_app)
    assert status_reads > PROCESSING_POLLS_AFTER_DOCUMENT


def test_document_is_requested_on_the_path_of_the_absolute_location(
    client: TestClient, scan_environment: ScanEnvironment, output_folder: Path
) -> None:
    scan_once(client, output_folder, "pdf")
    assert JOB_PATH_PATTERN.match(find_job_path(scan_environment.scanner_app))


def test_finished_job_is_deleted_after_its_page_arrives(
    client: TestClient, scan_environment: ScanEnvironment, output_folder: Path
) -> None:
    scan_once(client, output_folder, "pdf")
    job_path = find_job_path(scan_environment.scanner_app)
    assert ("DELETE", job_path) in scan_environment.scanner_app.received_requests


def test_saved_jpg_starts_with_the_jpeg_marker(client: TestClient, output_folder: Path) -> None:
    state = scan_once(client, output_folder, "jpg")
    assert saved_file_path(state).read_bytes()[:2] == JPEG_MARKER


def test_saved_jpg_reports_the_requested_resolution(client: TestClient, output_folder: Path) -> None:
    state = scan_once(client, output_folder, "jpg")
    with Image.open(saved_file_path(state)) as image:
        assert image.info["dpi"] == (ECONOMY_PRESET_DOTS_PER_INCH, ECONOMY_PRESET_DOTS_PER_INCH)


def test_last_thumbnail_is_served_as_jpeg(client: TestClient, output_folder: Path) -> None:
    scan_once(client, output_folder, "pdf")
    response = client.get("/api/scans/last/thumbnail")
    assert (response.status_code, response.headers["content-type"]) == (200, "image/jpeg")
    assert response.content[:2] == JPEG_MARKER


def test_thumbnail_is_not_found_before_the_first_scan(client: TestClient) -> None:
    assert client.get("/api/scans/last/thumbnail").status_code == 404


def test_printer_reports_the_manual_address_as_a_connected_network_route(client: TestClient) -> None:
    printer = client.get("/api/printer").json()
    assert (printer["connected"], printer["route"]) == (True, "network")


def test_state_reports_a_missing_output_folder_as_unavailable(client: TestClient, output_folder: Path) -> None:
    save_settings(client, output_folder, "pdf")
    shutil.rmtree(output_folder)
    assert client.get("/api/state").json()["storage"] == UNAVAILABLE_STORAGE


def make_output_folder_unavailable(client: TestClient, output_folder: Path) -> None:
    save_settings(client, output_folder, "pdf")
    shutil.rmtree(output_folder)
    output_folder.write_text("a file where the folder used to be")


def test_unavailable_output_folder_is_reported_with_its_message(client: TestClient, output_folder: Path) -> None:
    make_output_folder_unavailable(client, output_folder)
    client.post("/api/scans", headers=STATE_CHANGING_HEADERS)
    state = wait_for_state(client, has_failed)
    assert state["last_error"] == {
        "code": "output_folder_unavailable",
        "message": OUTPUT_FOLDER_UNAVAILABLE_MESSAGE,
    }


def test_unavailable_output_folder_is_detected_before_contacting_the_scanner(
    client: TestClient, scan_environment: ScanEnvironment, output_folder: Path
) -> None:
    make_output_folder_unavailable(client, output_folder)
    client.post("/api/scans", headers=STATE_CHANGING_HEADERS)
    wait_for_state(client, has_failed)
    assert scan_environment.scanner_app.received_requests == []


def test_full_disk_is_reported_with_its_message(
    client: TestClient, scan_environment: ScanEnvironment, output_folder: Path
) -> None:
    save_settings(client, output_folder, "pdf")
    scan_environment.free_space_reader.free_space_in_bytes = 0
    client.post("/api/scans", headers=STATE_CHANGING_HEADERS)
    state = wait_for_state(client, has_failed)
    assert state["last_error"] == {"code": "insufficient_storage", "message": INSUFFICIENT_STORAGE_MESSAGE}


def test_full_disk_is_detected_before_contacting_the_scanner(
    client: TestClient, scan_environment: ScanEnvironment, output_folder: Path
) -> None:
    save_settings(client, output_folder, "pdf")
    scan_environment.free_space_reader.free_space_in_bytes = 0
    client.post("/api/scans", headers=STATE_CHANGING_HEADERS)
    wait_for_state(client, has_failed)
    assert scan_environment.scanner_app.received_requests == []


@dataclass(frozen=True)
class RunningScan:
    client: httpx.AsyncClient
    first_request: "asyncio.Task[httpx.Response]"


@pytest.fixture
async def running_scan(scan_environment: ScanEnvironment, output_folder: Path) -> AsyncIterator[RunningScan]:
    scanner_app = scan_environment.scanner_app
    scanner_app.document_gate.clear()
    transport = httpx.ASGITransport(app=build_application(scan_environment))
    async with httpx.AsyncClient(transport=transport, base_url=BASE_ADDRESS) as client:
        await client.put("/api/settings", json=build_settings(output_folder, "pdf"), headers=STATE_CHANGING_HEADERS)
        first_request = asyncio.create_task(client.post("/api/scans", headers=STATE_CHANGING_HEADERS))
        # The scan is parked at NextDocument only after POST ScanJobs, so the job count below is deterministic.
        await asyncio.wait_for(scanner_app.document_requested.wait(), DOCUMENT_REQUEST_TIMEOUT_SECONDS)
        yield RunningScan(client=client, first_request=first_request)
        scanner_app.document_gate.set()
        await first_request


async def test_second_scan_request_during_a_scan_is_rejected_with_conflict(running_scan: RunningScan) -> None:
    response = await running_scan.client.post("/api/scans", headers=STATE_CHANGING_HEADERS)
    assert (response.status_code, response.json()) == (
        409,
        {"code": "scan_already_running", "message": SCAN_ALREADY_RUNNING_MESSAGE},
    )


async def test_rejected_second_request_does_not_start_another_job(
    running_scan: RunningScan, scan_environment: ScanEnvironment
) -> None:
    await running_scan.client.post("/api/scans", headers=STATE_CHANGING_HEADERS)
    assert len(scan_environment.scanner_app.paths_ending_with(SCAN_JOBS_PATH_SUFFIX)) == 1


async def test_running_scan_stays_in_progress_after_a_rejected_request(running_scan: RunningScan) -> None:
    await running_scan.client.post("/api/scans", headers=STATE_CHANGING_HEADERS)
    state = (await running_scan.client.get("/api/state")).json()
    assert state["scan_phase"] == "scanning"


def refuse_connection(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("Connection refused", request=request)


@pytest.fixture
def empty_record_source() -> EmptyServiceRecordSource:
    return EmptyServiceRecordSource()


@pytest.fixture
def unreachable_client(
    scan_environment: ScanEnvironment, empty_record_source: EmptyServiceRecordSource
) -> Iterator[TestClient]:
    overrides = ContainerOverrides(
        scanner_transport=httpx.MockTransport(refuse_connection),
        gateway_timing=EsclGatewayTiming(sleep=yield_without_waiting),
        free_space_reader=scan_environment.free_space_reader,
        service_record_source=empty_record_source,
    )
    application = build_application_with_overrides(scan_environment.configuration, overrides)
    with TestClient(application, base_url=BASE_ADDRESS, raise_server_exceptions=False) as test_client:
        yield test_client


def fail_scan_on_unreachable_printer(client: TestClient, output_folder: Path) -> dict:
    save_settings(client, output_folder, "pdf")
    assert client.post("/api/scans", headers=STATE_CHANGING_HEADERS).status_code == 202
    return wait_for_state(client, has_failed)


def test_unreachable_printer_is_reported_with_its_message(unreachable_client: TestClient, output_folder: Path) -> None:
    state = fail_scan_on_unreachable_printer(unreachable_client, output_folder)
    assert state["last_error"] == {"code": "scanner_unreachable", "message": SCANNER_UNREACHABLE_MESSAGE}


def test_unreachable_printer_leaves_no_file_in_the_output_folder(
    unreachable_client: TestClient, output_folder: Path
) -> None:
    fail_scan_on_unreachable_printer(unreachable_client, output_folder)
    assert list(output_folder.iterdir()) == []


def test_unreachable_printer_is_searched_again_through_the_discovery_override(
    unreachable_client: TestClient, empty_record_source: EmptyServiceRecordSource, output_folder: Path
) -> None:
    fail_scan_on_unreachable_printer(unreachable_client, output_folder)
    assert empty_record_source.collection_count >= 1

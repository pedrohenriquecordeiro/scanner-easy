from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from digitalizadora.domain.errors import ScanAlreadyRunningError
from digitalizadora.domain.last_scan import LastScan
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.services.printer_connection_service import PrinterConnectionState
from tests.fakes.stored_scans import STORED_SCAN_SCANNED_AT, build_last_scan

TEST_BASE_ADDRESS = "http://127.0.0.1:8765"
STATE_CHANGING_HEADERS = {"X-Requested-With": "digitalizadora"}
SCANNED_AT = STORED_SCAN_SCANNED_AT


def build_test_client(router: APIRouter) -> TestClient:
    application = FastAPI()
    application.include_router(router)
    return TestClient(application, base_url=TEST_BASE_ADDRESS)


class StubScanService:
    """Duck-typed stand-in for ScanService that records the requests it receives."""

    def __init__(self) -> None:
        self.in_progress = False
        self.start_refusal: Exception | None = None
        self.failure: Exception | None = None
        self.requests: list[ScanRequest] = []

    def is_scan_in_progress(self) -> bool:
        return self.in_progress

    def ensure_scan_can_start(self) -> None:
        if self.start_refusal is not None:
            raise self.start_refusal
        if self.in_progress:
            raise ScanAlreadyRunningError("A scan is already in progress")

    async def scan_one_file(self, request: ScanRequest) -> LastScan:
        self.requests.append(request)
        if self.failure is not None:
            raise self.failure
        return build_last_scan()


class StubPrinterConnectionService:
    """Duck-typed stand-in for PrinterConnectionService that records the calls in order."""

    def __init__(self, connection_state: PrinterConnectionState) -> None:
        self.connection_state = connection_state
        self.failure: Exception | None = None
        self.calls: list[str] = []
        self.manual_addresses: list[str] = []

    async def check_connection(self) -> PrinterConnectionState:
        self.calls.append("check_connection")
        if self.failure is not None:
            raise self.failure
        return self.connection_state

    async def refresh(self) -> PrinterConnectionState:
        self.calls.append("refresh")
        return self.connection_state

    def use_manual_address(self, base_address: str) -> None:
        self.calls.append("use_manual_address")
        self.manual_addresses.append(base_address)


class StubFolderPreparer:
    """Stand-in for prepare_output_folder: records the folders and can fail on demand."""

    def __init__(self) -> None:
        self.failure: Exception | None = None
        self.prepared_folders: list[Path] = []

    def __call__(self, folder: Path) -> None:
        self.prepared_folders.append(folder)
        if self.failure is not None:
            raise self.failure

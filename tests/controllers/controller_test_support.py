from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.services.printer_connection_service import PrinterConnectionState
from tests.fakes.stored_scans import STORED_SCAN_SCANNED_AT

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
        self.failure: Exception | None = None
        self.requests: list[ScanRequest] = []

    def is_scan_in_progress(self) -> bool:
        return self.in_progress

    async def scan_one_file(self, request: ScanRequest) -> ScanResult:
        self.requests.append(request)
        if self.failure is not None:
            raise self.failure
        return ScanResult(
            output_path=Path("/Volumes/Scans/2026-10-13_00001.pdf"),
            output_format=request.output_format,
            scanned_at=SCANNED_AT,
            size_in_bytes=1234,
        )


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

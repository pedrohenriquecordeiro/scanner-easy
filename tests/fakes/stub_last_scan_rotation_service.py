from digitalizadora.domain.scan_result import ScanResult
from tests.fakes.stored_scans import build_stored_scan


class StubLastScanRotationService:
    """Duck-typed stand-in for LastScanRotationService for the controllers: counts calls and fails on demand."""

    def __init__(self) -> None:
        self.failure: Exception | None = None
        self.result = build_stored_scan().result
        self.rotation_count = 0

    async def rotate_clockwise(self) -> ScanResult:
        self.rotation_count += 1
        if self.failure is not None:
            raise self.failure
        return self.result

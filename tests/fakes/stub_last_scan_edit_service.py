from collections.abc import Sequence

from digitalizadora.domain.page_crop import PageCrop
from digitalizadora.services.quick_scan.last_scan_edit_service import LastScanEditResult
from tests.fakes.stored_scans import build_last_scan


class StubLastScanEditService:
    """Duck-typed stand-in for LastScanEditService for the controllers: records calls and fails on demand."""

    def __init__(self) -> None:
        self.failure: Exception | None = None
        self.result = LastScanEditResult(build_last_scan())
        self.calls: list[str] = []
        self.received_crops: list[Sequence[PageCrop]] = []

    async def rotate_clockwise(self) -> LastScanEditResult:
        return self._answer("rotate_clockwise")

    async def set_crops(self, crops: Sequence[PageCrop]) -> LastScanEditResult:
        self.received_crops.append(crops)
        return self._answer("set_crops")

    async def detect_crops(self) -> LastScanEditResult:
        return self._answer("detect_crops")

    def _answer(self, operation: str) -> LastScanEditResult:
        self.calls.append(operation)
        if self.failure is not None:
            raise self.failure
        return self.result

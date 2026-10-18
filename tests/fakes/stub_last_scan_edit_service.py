from collections.abc import Sequence

from digitalizadora.domain.page_crop import PageCrop
from digitalizadora.services.last_scan_edit_service import LastScanEditResult
from tests.fakes.stored_scans import build_last_scan


class StubLastScanEditService:
    """Duck-typed stand-in for LastScanEditService for the controllers: records calls and fails on demand."""

    def __init__(self) -> None:
        self.failure: Exception | None = None
        self.result = LastScanEditResult(build_last_scan())
        self.calls: list[str] = []
        self.received_jpeg_qualities: list[int] = []
        self.received_crops: list[Sequence[PageCrop]] = []

    async def rotate_clockwise(self, jpeg_quality: int) -> LastScanEditResult:
        return self._answer("rotate_clockwise", jpeg_quality)

    async def set_crops(self, crops: Sequence[PageCrop], jpeg_quality: int) -> LastScanEditResult:
        self.received_crops.append(crops)
        return self._answer("set_crops", jpeg_quality)

    async def detect_crops(self, jpeg_quality: int) -> LastScanEditResult:
        return self._answer("detect_crops", jpeg_quality)

    def _answer(self, operation: str, jpeg_quality: int) -> LastScanEditResult:
        self.calls.append(operation)
        self.received_jpeg_qualities.append(jpeg_quality)
        if self.failure is not None:
            raise self.failure
        return self.result

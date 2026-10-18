import asyncio
from dataclasses import dataclass, replace

from digitalizadora.domain.errors import LastScanFileMissingError, NoLastScanError, ScanAlreadyRunningError
from digitalizadora.domain.page_rotation import PageRotation
from digitalizadora.domain.ports import ScanOutputRepository
from digitalizadora.domain.scan_progress import ScanPhase
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.domain.stored_scan import StoredScan
from digitalizadora.services.page_image_view_service import PageImageViewService
from digitalizadora.services.scan_content_rotator import ScanContentRotator
from digitalizadora.services.scan_progress_tracker import ScanProgressTracker
from digitalizadora.services.thumbnail_service import THUMBNAIL_MAXIMUM_EDGE_PIXELS


@dataclass(frozen=True)
class LastScanRotators:
    """What turns the saved file and the thumbnail of the last scan."""

    content_rotator: ScanContentRotator
    image_view_service: PageImageViewService


class LastScanRotationService:
    """Turns the last file of the quick mode in place: the file in the output folder and its thumbnail.

    Only the last scan of this run can be turned: the tracker is the one that knows which file it is.
    """

    def __init__(
        self,
        progress_tracker: ScanProgressTracker,
        scan_output_repository: ScanOutputRepository,
        rotators: LastScanRotators,
    ) -> None:
        self._progress_tracker = progress_tracker
        self._scan_output_repository = scan_output_repository
        self._content_rotator = rotators.content_rotator
        self._image_view_service = rotators.image_view_service
        self._lock = asyncio.Lock()

    async def rotate_clockwise(self, jpeg_quality: int) -> ScanResult:
        async with self._lock:
            return await self._rotate_last_scan(jpeg_quality)

    async def _rotate_last_scan(self, jpeg_quality: int) -> ScanResult:
        if self._progress_tracker.snapshot().phase is not ScanPhase.IDLE:
            raise ScanAlreadyRunningError("A scan is running; the last file waits for it")
        last_result = self._progress_tracker.snapshot().last_result
        last_thumbnail_jpeg = self._progress_tracker.last_thumbnail_jpeg()
        if last_result is None or last_thumbnail_jpeg is None:
            raise NoLastScanError("There is no scan of this run to turn")
        stored_scan = await asyncio.to_thread(
            self._turn_the_saved_file, last_result, last_thumbnail_jpeg, jpeg_quality
        )
        # Back on the event loop: only here the tracker, which the loop owns, takes the new scan.
        self._progress_tracker.replace_last_scan(last_result, stored_scan)
        return stored_scan.result

    def _turn_the_saved_file(
        self, last_result: ScanResult, last_thumbnail_jpeg: bytes, jpeg_quality: int
    ) -> StoredScan:
        content = self._scan_output_repository.read_saved_scan(last_result.output_path)
        if content is None:
            raise LastScanFileMissingError(f"{last_result.output_path} is not in the output folder any more")
        turned_content = self._content_rotator.rotate_clockwise(content, last_result.output_format, jpeg_quality)
        self._scan_output_repository.replace_saved_scan(last_result.output_path, turned_content)
        turned_thumbnail = self._image_view_service.build_view(
            last_thumbnail_jpeg, PageRotation.CLOCKWISE_90, THUMBNAIL_MAXIMUM_EDGE_PIXELS
        )
        return StoredScan(replace(last_result, size_in_bytes=len(turned_content)), turned_thumbnail)

from digitalizadora.domain.errors import (
    LastScanNotEditableError,
    LastScanReplacedError,
    NoLastScanError,
    SavedScanUnreadableError,
    ScanFailedError,
)
from digitalizadora.domain.imaging.page_rotation import PageRotation
from digitalizadora.domain.ports import QuickScanSlotRepository
from digitalizadora.services.application.scan_progress_tracker import ScanProgressTracker
from digitalizadora.services.imaging.page_image_view_service import (
    ENLARGED_VIEW_MAXIMUM_EDGE_PIXELS,
    PageImageViewService,
)
from digitalizadora.services.imaging.thumbnail_service import THUMBNAIL_MAXIMUM_EDGE_PIXELS


class LastScanViewService:
    """What the page looks at of the last quick scan: its thumbnail and an enlarged view, both turned as shown.

    Neither takes a lock: the master only changes when the next scan confirms its manifest, and a read that meets
    that moment ends with the file it had already opened or answers that there is no last scan."""

    def __init__(
        self,
        progress_tracker: ScanProgressTracker,
        slot_repository: QuickScanSlotRepository,
        image_view_service: PageImageViewService,
    ) -> None:
        self._progress_tracker = progress_tracker
        self._slot_repository = slot_repository
        self._image_view_service = image_view_service

    def read_thumbnail(self) -> bytes | None:
        """The thumbnail of the scan as the scanner saw it, turned by the rotation of the scan."""
        last_scan = self._progress_tracker.snapshot().last_scan
        thumbnail_jpeg = self._progress_tracker.last_thumbnail_jpeg()
        if last_scan is None or thumbnail_jpeg is None:
            return None
        rotation = last_scan.framing.rotation
        if rotation is PageRotation.NONE:
            return thumbnail_jpeg
        return self._image_view_service.build_view(thumbnail_jpeg, rotation, THUMBNAIL_MAXIMUM_EDGE_PIXELS)

    def read_preview(self, scan_identifier: str, rotation: PageRotation) -> bytes:
        last_scan = self._progress_tracker.snapshot().last_scan
        if last_scan is None:
            raise NoLastScanError("There is no last scan")
        if last_scan.scan_identifier != scan_identifier:
            raise LastScanReplacedError(f"{scan_identifier} is not the last scan")
        if not last_scan.is_editable:
            raise LastScanNotEditableError("The master of the last scan was not kept")
        try:
            master_jpeg = self._slot_repository.master_file_path(scan_identifier).read_bytes()
        except FileNotFoundError as error:
            raise NoLastScanError(f"The master of {scan_identifier} is gone") from error
        except OSError as error:
            raise SavedScanUnreadableError(f"The master of {scan_identifier} cannot be read") from error
        try:
            return self._image_view_service.build_view(master_jpeg, rotation, ENLARGED_VIEW_MAXIMUM_EDGE_PIXELS)
        except ScanFailedError as error:
            raise SavedScanUnreadableError(f"The master of {scan_identifier} is not an image") from error

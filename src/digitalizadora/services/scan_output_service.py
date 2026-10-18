import io
import logging
from collections.abc import Callable
from dataclasses import dataclass, replace

from digitalizadora.domain.encoded_scan import EncodedScan
from digitalizadora.domain.errors import DigitalizadoraError, ImageAdjustmentFailedError
from digitalizadora.domain.last_scan import LastScan, QuickScanMasterFiles, QuickScanSlot, SavedScanFile
from digitalizadora.domain.page_framing import UNFRAMED, PageFraming
from digitalizadora.domain.ports import QuickScanSlotRepository, ScanOutputRepository
from digitalizadora.domain.scan_job import ScanJob
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.domain.stored_scan import StoredScan
from digitalizadora.services.page_crop_detection_service import PageCropDetectionService
from digitalizadora.services.quick_scan_output_renderer import OutputsRequest, QuickScanOutputRenderer
from digitalizadora.services.scan_encoder import EncodedMaster, OutputIdentity, ScanEncoder
from digitalizadora.services.storage_guard_service import StorageGuardService

LOGGER = logging.getLogger(__name__)
UNKNOWN_MODIFICATION_TIME = 0


@dataclass(frozen=True)
class ScanOutputParts:
    """What a quick scan is made with."""

    scan_encoder: ScanEncoder
    output_renderer: QuickScanOutputRenderer
    crop_detection_service: PageCropDetectionService
    storage_guard_service: StorageGuardService
    scan_identifier_factory: Callable[[], str]


class ScanOutputService:
    """The ScanDestination[StoredScan] of the quick mode: the files of the scan and the slot with its master.

    The scanner master is kept apart (the slot), so the crop and the rotation can be changed later without losing
    anything: the files in the output folder are always made from it. Both methods run in a worker thread.
    """

    def __init__(
        self,
        parts: ScanOutputParts,
        scan_output_repository: ScanOutputRepository,
        slot_repository: QuickScanSlotRepository,
    ) -> None:
        self._scan_encoder = parts.scan_encoder
        self._output_renderer = parts.output_renderer
        self._crop_detection_service = parts.crop_detection_service
        self._storage_guard_service = parts.storage_guard_service
        self._scan_identifier_factory = parts.scan_identifier_factory
        self._scan_output_repository = scan_output_repository
        self._slot_repository = slot_repository

    def ensure_capacity(self, request: ScanRequest) -> None:
        # The folder comes first: a disconnected disk must fail before the printer spends up to 75 s on a page.
        self._scan_output_repository.ensure_output_folder_ready()
        self._storage_guard_service.ensure_space_for_scan(
            self._scan_output_repository.output_folder(), request.settings, request.adjustment
        )

    def store(self, scanned_image: ScannedImage, job: ScanJob) -> StoredScan:
        encoded_master = self._scan_encoder.encode_master(scanned_image, job)
        scan_identifier = self._scan_identifier_factory()
        framing = self._find_framing(encoded_master.jpeg_content, job)
        is_master_kept = self._keep_master(scan_identifier, encoded_master)
        saved_files = self._save_outputs(encoded_master.jpeg_content, framing, job)
        last_scan = LastScan(
            scan_identifier=scan_identifier,
            scanned_at=job.started_at,
            output_folder=self._scan_output_repository.output_folder(),
            output_format=job.request.output_format,
            saved_files=saved_files,
            framing=framing,
            is_editable=is_master_kept,
        )
        if is_master_kept:
            last_scan = self._commit_slot(last_scan, job)
        else:
            self._forget_slot()
        return StoredScan(last_scan, encoded_master.thumbnail_jpeg)

    def _find_framing(self, master_jpeg: bytes, job: ScanJob) -> PageFraming:
        if not job.request.adjustment.auto_crop:
            return UNFRAMED
        try:
            return PageFraming().with_crops(self._crop_detection_service.detect_crops(master_jpeg).crops)
        except DigitalizadoraError:
            # A failed detection never costs the scan: the files come out whole and the user can frame them.
            LOGGER.warning("The automatic crop of the scan failed; the image was kept whole", exc_info=True)
            return UNFRAMED

    def _keep_master(self, scan_identifier: str, encoded_master: EncodedMaster) -> bool:
        """False when the disk of the Mac does not take the master: the scan still goes on, but cannot be adjusted."""
        master_files = QuickScanMasterFiles(scan_identifier, encoded_master.jpeg_content, encoded_master.thumbnail_jpeg)
        try:
            self._slot_repository.write_master_files(master_files)
        except DigitalizadoraError:
            LOGGER.warning("The master of the scan could not be kept; its files cannot be adjusted", exc_info=True)
            return False
        return True

    def _save_outputs(self, master_jpeg: bytes, framing: PageFraming, job: ScanJob) -> tuple[SavedScanFile, ...]:
        identity = OutputIdentity(job.started_at, job.request.settings.dots_per_inch, job.request.output_format)
        request = OutputsRequest(framing, identity)
        encoded_scans = self._render_outputs(master_jpeg, request)
        output_paths = self._scan_output_repository.save_scans(encoded_scans)
        saved_files = []
        for encoded_scan, output_path in zip(encoded_scans, output_paths, strict=True):
            described_file = self._scan_output_repository.describe_saved_scan(output_path)
            saved_files.append(
                described_file or SavedScanFile(output_path.name, len(encoded_scan.content), UNKNOWN_MODIFICATION_TIME)
            )
        return tuple(saved_files)

    def _render_outputs(self, master_jpeg: bytes, request: OutputsRequest) -> tuple[EncodedScan, ...]:
        try:
            return self._output_renderer.render_outputs(io.BytesIO(master_jpeg), request)
        except MemoryError as error:
            raise ImageAdjustmentFailedError("Not enough memory to make the files of the scan") from error

    def _commit_slot(self, last_scan: LastScan, job: ScanJob) -> LastScan:
        slot = QuickScanSlot(last_scan, job.request.settings.dots_per_inch, job.request.settings.color_mode)
        try:
            self._slot_repository.commit(slot)
        except DigitalizadoraError:
            LOGGER.warning("The slot of the scan could not be confirmed; its files cannot be adjusted", exc_info=True)
            self._forget_slot()
            return replace(last_scan, is_editable=False)
        return last_scan

    def _forget_slot(self) -> None:
        """The slot of the previous scan cannot outlive a new scan that has no master of its own."""
        try:
            self._slot_repository.discard()
        except DigitalizadoraError:
            LOGGER.warning("The slot of the previous scan could not be forgotten", exc_info=True)

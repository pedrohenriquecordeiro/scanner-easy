import asyncio
import functools
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

from digitalizadora.domain.errors import (
    DigitalizadoraError,
    ImageAdjustmentFailedError,
    LastScanNotEditableError,
    NoLastScanError,
    SavedScanUnreadableError,
    ScanAlreadyRunningError,
    ScanFailedError,
)
from digitalizadora.domain.imaging.page_crop import PageCrop
from digitalizadora.domain.imaging.page_framing import PageFraming
from digitalizadora.domain.ports import QuickScanSlotRepository, ScanOutputRepository
from digitalizadora.domain.quick_scan.last_scan import LastScan, QuickScanSlot, SavedScanFile
from digitalizadora.domain.quick_scan.scan_progress import ScanPhase
from digitalizadora.domain.quick_scan.stored_scan import StoredScan
from digitalizadora.services.application.scan_progress_tracker import ScanProgressTracker
from digitalizadora.services.imaging.page_crop_detection_service import PageCropDetectionService
from digitalizadora.services.imaging.thumbnail_service import THUMBNAIL_MAXIMUM_EDGE_PIXELS, ThumbnailService
from digitalizadora.services.output.scan_encoder import OutputIdentity
from digitalizadora.services.quick_scan.quick_scan_output_renderer import OutputsRequest, QuickScanOutputRenderer

LOGGER = logging.getLogger(__name__)
UNKNOWN_MODIFICATION_TIME = 0


class _SlotGoneError(SavedScanUnreadableError):
    """The slot of the last scan is not there any more, so the scan cannot be adjusted again."""


@dataclass(frozen=True)
class LastScanEditResult:
    last_scan: LastScan
    crops_detected: bool = False
    ignored_region_count: int = 0


@dataclass(frozen=True)
class LastScanEditParts:
    """What an edit of the last scan works with: its slot, its files and the pieces that make the files again."""

    slot_repository: QuickScanSlotRepository
    scan_output_repository: ScanOutputRepository
    output_renderer: QuickScanOutputRenderer
    crop_detection_service: PageCropDetectionService
    thumbnail_service: ThumbnailService


@dataclass(frozen=True)
class _PlannedFraming:
    """The framing an edit wants (None: nothing changes) and what the detection learned on the way."""

    framing: PageFraming | None
    crops_detected: bool = False
    ignored_region_count: int = 0


@dataclass(frozen=True)
class _EditOutcome:
    result: LastScanEditResult
    is_changed: bool


class LastScanEditService:
    """Adjusts the last quick scan: its rotation and its crops. New files are made from the master, each under a
    fresh name; the files written before stay where they are, whatever happened to them.

    The slot keeps the master, the framing and, while a render is under way, a mark that lets the next start finish
    it. Only one edit runs at a time, and none runs during a scan.
    """

    def __init__(self, progress_tracker: ScanProgressTracker, parts: LastScanEditParts) -> None:
        self._progress_tracker = progress_tracker
        self._slot_repository = parts.slot_repository
        self._scan_output_repository = parts.scan_output_repository
        self._output_renderer = parts.output_renderer
        self._crop_detection_service = parts.crop_detection_service
        self._thumbnail_service = parts.thumbnail_service
        self._lock = asyncio.Lock()

    async def rotate_clockwise(self) -> LastScanEditResult:
        return await self._run_edit(self._plan_rotation)

    async def set_crops(self, crops: Sequence[PageCrop]) -> LastScanEditResult:
        return await self._run_edit(functools.partial(self._plan_crops, crops))

    async def detect_crops(self) -> LastScanEditResult:
        return await self._run_edit(self._plan_detection)

    def restore_after_start(self) -> None:
        """Brings the last scan of the previous run back from its slot. It never raises: the server must start."""
        try:
            self._restore_last_scan()
        except Exception:
            LOGGER.warning("The last scan of the previous run could not be restored", exc_info=True)

    async def _run_edit(
        self, plan: Callable[[QuickScanSlot], _PlannedFraming]
    ) -> LastScanEditResult:
        async with self._lock:
            last_scan, thumbnail_jpeg = self._require_editable_last_scan()
            # No await between the check of the phase above and this mark: a scan that starts now is refused.
            self._progress_tracker.mark_last_scan_edit_started()
            try:
                outcome = await asyncio.to_thread(self._apply_edit, plan)
            except _SlotGoneError:
                self._progress_tracker.replace_last_scan(
                    last_scan.scan_identifier, StoredScan(replace(last_scan, is_editable=False), thumbnail_jpeg)
                )
                raise
            finally:
                self._progress_tracker.mark_last_scan_edit_ended()
            # Back on the event loop: only here the tracker, which the loop owns, takes the adjusted scan.
            if outcome.is_changed:
                self._progress_tracker.replace_last_scan(
                    last_scan.scan_identifier, StoredScan(outcome.result.last_scan, thumbnail_jpeg)
                )
            return outcome.result

    def _require_editable_last_scan(self) -> tuple[LastScan, bytes]:
        if self._progress_tracker.snapshot().phase is not ScanPhase.IDLE:
            raise ScanAlreadyRunningError("A scan is running; the last scan waits for it")
        last_scan = self._progress_tracker.snapshot().last_scan
        thumbnail_jpeg = self._progress_tracker.last_thumbnail_jpeg()
        if last_scan is None or thumbnail_jpeg is None:
            raise NoLastScanError("There is no scan to adjust")
        if not last_scan.is_editable:
            raise LastScanNotEditableError("The master of the last scan was not kept")
        return last_scan, thumbnail_jpeg

    def _plan_rotation(self, slot: QuickScanSlot) -> _PlannedFraming:
        return _PlannedFraming(slot.last_scan.framing.turned_clockwise())

    def _plan_crops(self, crops: Sequence[PageCrop], slot: QuickScanSlot) -> _PlannedFraming:
        return _PlannedFraming(slot.last_scan.framing.with_crops(crops))

    def _plan_detection(self, slot: QuickScanSlot) -> _PlannedFraming:
        """Looked for on the master, shown in the orientation of the page; finding nothing changes nothing."""
        master_jpeg = self._read_master(slot.last_scan.scan_identifier)
        detected = self._crop_detection_service.detect_crops(master_jpeg)
        if not detected.crops:
            return _PlannedFraming(None, False, detected.ignored_region_count)
        framing = slot.last_scan.framing
        found_framing = framing.with_crops(framing.crops_from_master(detected.crops))
        return _PlannedFraming(found_framing, True, detected.ignored_region_count)

    def _apply_edit(self, plan: Callable[[QuickScanSlot], _PlannedFraming]) -> _EditOutcome:
        """The disk work of an edit, in a worker thread (7.3)."""
        try:
            slot = self._load_slot()
            planned = plan(slot)
            current_scan = slot.last_scan
            if planned.framing is None or planned.framing == current_scan.framing:
                result = LastScanEditResult(current_scan, planned.crops_detected, planned.ignored_region_count)
                return _EditOutcome(result, is_changed=False)
            pending_slot = replace(slot, last_scan=current_scan.with_framing(planned.framing), render_pending=True)
            self._slot_repository.commit(pending_slot)
            finished_slot = self._finish_render(pending_slot, slot)
        except ScanFailedError as error:
            raise SavedScanUnreadableError(f"The master of the last scan could not be read: {error}") from error
        except MemoryError as error:
            raise ImageAdjustmentFailedError("Not enough memory to adjust the last scan") from error
        result = LastScanEditResult(finished_slot.last_scan, planned.crops_detected, planned.ignored_region_count)
        return _EditOutcome(result, is_changed=True)

    def _finish_render(
        self, pending_slot: QuickScanSlot, previous_slot: QuickScanSlot
    ) -> QuickScanSlot:
        """Renders the new files and confirms them; if that fails the manifest goes back to the framing of before."""
        try:
            saved_files = self._render_outputs(pending_slot)
            finished_scan = pending_slot.last_scan.with_saved_files(saved_files)
            finished_slot = replace(pending_slot, last_scan=finished_scan, render_pending=False)
            self._slot_repository.commit(finished_slot)
        except Exception:
            self._restore_previous_manifest(previous_slot)
            raise
        return finished_slot

    def _restore_previous_manifest(self, previous_slot: QuickScanSlot) -> None:
        try:
            self._slot_repository.commit(replace(previous_slot, render_pending=False))
        except DigitalizadoraError:
            LOGGER.warning("The manifest of the last scan could not go back to its framing of before", exc_info=True)

    def _load_slot(self) -> QuickScanSlot:
        slot = self._slot_repository.load()
        if slot is None:
            raise _SlotGoneError("The slot of the last scan is gone")
        expected = self._progress_tracker.snapshot().last_scan
        if expected is None or expected.scan_identifier != slot.last_scan.scan_identifier:
            raise NoLastScanError("The slot holds another scan than the last one")
        return slot

    def _read_master(self, scan_identifier: str) -> bytes:
        try:
            return self._slot_repository.master_file_path(scan_identifier).read_bytes()
        except OSError as error:
            raise SavedScanUnreadableError(f"The master of {scan_identifier} cannot be read") from error

    def _render_outputs(self, slot: QuickScanSlot) -> tuple[SavedScanFile, ...]:
        """Makes the files of the slot's framing from its master, each under a new name (7.3 step 4)."""
        last_scan = slot.last_scan
        identity = OutputIdentity(last_scan.scanned_at, slot.dots_per_inch, last_scan.output_format)
        request = OutputsRequest(last_scan.framing, identity)
        try:
            with self._slot_repository.master_file_path(last_scan.scan_identifier).open("rb") as master:
                outputs = self._output_renderer.render_outputs(master, request)
        except OSError as error:
            raise SavedScanUnreadableError(f"The master of {last_scan.scan_identifier} cannot be read") from error
        output_paths = self._scan_output_repository.save_scans_in_folder(last_scan.output_folder, outputs)
        saved_files = []
        for encoded_scan, output_path in zip(outputs, output_paths, strict=True):
            described_file = self._scan_output_repository.describe_saved_scan(output_path)
            saved_files.append(
                described_file or SavedScanFile(output_path.name, len(encoded_scan.content), UNKNOWN_MODIFICATION_TIME)
            )
        return tuple(saved_files)

    def _restore_last_scan(self) -> None:
        slot = self._slot_repository.load()
        if slot is None:
            self._slot_repository.delete_leftovers(None)
            return
        if not slot.last_scan.output_folder.is_dir():
            LOGGER.warning(
                "The output folder %s of the last scan is not reachable; its slot is kept as it is",
                slot.last_scan.output_folder,
            )
            return
        if not self._any_file_exists(slot.last_scan):
            self._slot_repository.discard()
            return
        if slot.render_pending:
            slot = self._finish_interrupted_render(slot)
        self._slot_repository.delete_leftovers(slot.last_scan.scan_identifier)
        thumbnail_jpeg = self._read_or_build_thumbnail(slot.last_scan.scan_identifier)
        self._progress_tracker.restore_last_scan(StoredScan(slot.last_scan, thumbnail_jpeg))

    def _any_file_exists(self, last_scan: LastScan) -> bool:
        return any(
            self._scan_output_repository.describe_saved_scan(last_scan.saved_file_path(saved_file)) is not None
            for saved_file in last_scan.saved_files
        )

    def _finish_interrupted_render(self, slot: QuickScanSlot) -> QuickScanSlot:
        saved_files = self._render_outputs(slot)
        finished_slot = replace(slot, last_scan=slot.last_scan.with_saved_files(saved_files), render_pending=False)
        self._slot_repository.commit(finished_slot)
        return finished_slot

    def _read_or_build_thumbnail(self, scan_identifier: str) -> bytes:
        thumbnail_jpeg = self._slot_repository.read_thumbnail(scan_identifier)
        if thumbnail_jpeg is not None:
            return thumbnail_jpeg
        master_jpeg = self._read_master(scan_identifier)
        return self._thumbnail_service.build_thumbnail(master_jpeg, THUMBNAIL_MAXIMUM_EDGE_PIXELS)

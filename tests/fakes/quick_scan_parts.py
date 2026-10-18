"""The services of the quick mode wired as the composition root wires them, over real files in a temporary folder."""

import io
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.image_adjustment import ImageAdjustment
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_file_naming_policy import ScanFileNamingPolicy
from digitalizadora.domain.scan_job import ScanJob
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.domain.stored_scan import StoredScan
from digitalizadora.repositories.file_system_quick_scan_slot_repository import FileSystemQuickScanSlotRepository
from digitalizadora.repositories.file_system_scan_output_repository import FileSystemScanOutputRepository
from digitalizadora.services.jpeg_resolution_service import JpegResolutionService
from digitalizadora.services.last_scan_edit_service import LastScanEditParts, LastScanEditService
from digitalizadora.services.last_scan_view_service import LastScanViewService
from digitalizadora.services.page_crop_detection_service import PageCropDetectionService
from digitalizadora.services.page_framing_renderer import PageFramingRenderer
from digitalizadora.services.page_image_view_service import PageImageViewService
from digitalizadora.services.pdf_assembly_service import PdfAssemblyService
from digitalizadora.services.quick_scan_output_renderer import QuickScanOutputRenderer
from digitalizadora.services.scan_encoder import ScanEncoder
from digitalizadora.services.scan_output_service import ScanOutputParts, ScanOutputService
from digitalizadora.services.scan_progress_tracker import ScanProgressTracker
from digitalizadora.services.storage_guard_service import StorageGuardService
from digitalizadora.services.thumbnail_service import ThumbnailService
from tests.fakes.document_service_parts import InstantFileWriter
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.in_memory_settings_repository import InMemoryApplicationSettingsRepository
from tests.fakes.photo_scenes import PlacedPhoto, build_photo_scene_jpeg

STARTED_AT = datetime(2026, 10, 13, 15, 30, 12, tzinfo=timezone(timedelta(hours=-3)))
SETTINGS = ScanSettings(300, ColorMode.COLOR)
ABUNDANT_FREE_SPACE = 1024**4
SCENE_SIZE = (291, 400)
PHOTO_SIZE = (120, 150)
UPPER_PHOTO = PlacedPhoto((75.0, 130.0), PHOTO_SIZE, 10.0)
LOWER_PHOTO = PlacedPhoto((215.0, 270.0), PHOTO_SIZE, -6.0, 2)
TWO_PHOTOS = ScannedImage(build_photo_scene_jpeg(SCENE_SIZE, [UPPER_PHOTO, LOWER_PHOTO]), "image/jpeg")
ONE_PHOTO = ScannedImage(
    build_photo_scene_jpeg(SCENE_SIZE, [PlacedPhoto((145.0, 200.0), (150, 200), 20.0)]), "image/jpeg"
)


WHOLE_IMAGE = ImageAdjustment(auto_crop=False, jpeg_quality=90)
WITH_AUTO_CROP = ImageAdjustment(auto_crop=True, jpeg_quality=90)


def build_job(output_format: OutputFormat = OutputFormat.JPEG, adjustment: ImageAdjustment = WHOLE_IMAGE) -> ScanJob:
    return ScanJob(ScanRequest(SETTINGS, output_format, adjustment), STARTED_AT)


def read_image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def read_size_of_jpeg(jpeg_content: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(jpeg_content)) as image:
        return image.size


@dataclass
class QuickScanParts:
    output_folder: Path
    slot_folder: Path
    settings_repository: InMemoryApplicationSettingsRepository
    output_repository: FileSystemScanOutputRepository
    slot_repository: FileSystemQuickScanSlotRepository
    progress_tracker: ScanProgressTracker
    scan_output_service: ScanOutputService
    last_scan_edit_service: LastScanEditService
    last_scan_view_service: LastScanViewService

    def scan(self, scanned_image: ScannedImage, job: ScanJob) -> StoredScan:
        """A quick scan as ScanService runs it: begin, store in the destination, complete."""
        self.progress_tracker.begin_scan(job.request)
        stored_scan = self.scan_output_service.store(scanned_image, job)
        self.progress_tracker.mark_completed(stored_scan)
        return stored_scan

    def saved_names(self) -> list[str]:
        return sorted(path.name for path in self.output_folder.iterdir() if path.is_file())


@dataclass(frozen=True)
class QuickScanFolders:
    output_folder: Path
    slot_folder: Path

    @classmethod
    def under(cls, tmp_path: Path) -> "QuickScanFolders":
        return cls(tmp_path / "scans", tmp_path / "quick-scan")


def build_quick_scan_parts(
    tmp_path: Path,
    output_repository: FileSystemScanOutputRepository | None = None,
    slot_repository: FileSystemQuickScanSlotRepository | None = None,
) -> QuickScanParts:
    return build_quick_scan_parts_in(QuickScanFolders.under(tmp_path), output_repository, slot_repository)


def build_quick_scan_parts_in(
    folders: QuickScanFolders,
    output_repository: FileSystemScanOutputRepository | None = None,
    slot_repository: FileSystemQuickScanSlotRepository | None = None,
) -> QuickScanParts:
    output_folder = folders.output_folder
    slot_folder = folders.slot_folder
    clock = FixedClock(STARTED_AT)
    settings_repository = InMemoryApplicationSettingsRepository(
        ApplicationSettings(output_folder, OutputFormat.PDF, ScanPreset.DOCUMENT.settings)
    )
    real_output_repository = FileSystemScanOutputRepository(
        settings_repository, ScanFileNamingPolicy(clock), InstantFileWriter()
    )
    real_slot_repository = FileSystemQuickScanSlotRepository(slot_folder, InstantFileWriter(), clock)
    used_output_repository = output_repository or real_output_repository
    used_slot_repository = slot_repository or real_slot_repository
    scan_encoder = ScanEncoder(JpegResolutionService(), PdfAssemblyService(), ThumbnailService())
    output_renderer = QuickScanOutputRenderer(PageFramingRenderer(), scan_encoder)
    crop_detection_service = PageCropDetectionService()
    progress_tracker = ScanProgressTracker(clock)
    identifiers = iter(f"{number:016x}" for number in range(1, 1000))
    scan_output_service = ScanOutputService(
        ScanOutputParts(
            scan_encoder=scan_encoder,
            output_renderer=output_renderer,
            crop_detection_service=crop_detection_service,
            storage_guard_service=StorageGuardService(lambda folder: ABUNDANT_FREE_SPACE),
            scan_identifier_factory=lambda: next(identifiers),
        ),
        used_output_repository,
        used_slot_repository,
    )
    last_scan_edit_service = LastScanEditService(
        progress_tracker,
        LastScanEditParts(
            slot_repository=used_slot_repository,
            scan_output_repository=used_output_repository,
            output_renderer=output_renderer,
            crop_detection_service=crop_detection_service,
            thumbnail_service=ThumbnailService(),
        ),
    )
    return QuickScanParts(
        output_folder=output_folder,
        slot_folder=slot_folder,
        settings_repository=settings_repository,
        output_repository=real_output_repository,
        slot_repository=real_slot_repository,
        progress_tracker=progress_tracker,
        scan_output_service=scan_output_service,
        last_scan_edit_service=last_scan_edit_service,
        last_scan_view_service=LastScanViewService(progress_tracker, used_slot_repository, PageImageViewService()),
    )

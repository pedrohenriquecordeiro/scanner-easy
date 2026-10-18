import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pikepdf
import pytest
from PIL import Image

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.encoded_scan import EncodedScan
from digitalizadora.domain.errors import (
    DigitalizadoraError,
    ImageAdjustmentFailedError,
    InsufficientStorageError,
    OutputFolderUnavailableError,
    ScanFailedError,
)
from digitalizadora.domain.image_adjustment import ImageAdjustment
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_file_naming_policy import ScanFileNamingPolicy
from digitalizadora.domain.scan_job import ScanJob
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.repositories.file_system_quick_scan_slot_repository import FileSystemQuickScanSlotRepository
from digitalizadora.repositories.file_system_scan_output_repository import FileSystemScanOutputRepository
from digitalizadora.services.jpeg_resolution_service import JpegResolutionService
from digitalizadora.services.page_crop_detection_service import DetectedCrops, PageCropDetectionService
from digitalizadora.services.page_framing_renderer import PageFramingRenderer
from digitalizadora.services.pdf_assembly_service import PdfAssemblyService
from digitalizadora.services.quick_scan_output_renderer import QuickScanOutputRenderer
from digitalizadora.services.scan_encoder import ScanEncoder
from digitalizadora.services.scan_output_service import ScanOutputParts, ScanOutputService
from digitalizadora.services.storage_guard_service import (
    MINIMUM_FREE_SPACE_BYTES,
    SAFETY_MARGIN_PAGES,
    StorageGuardService,
    estimated_page_bytes,
)
from digitalizadora.services.thumbnail_service import ThumbnailService
from tests.fakes.document_service_parts import InstantFileWriter
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.in_memory_settings_repository import InMemoryApplicationSettingsRepository
from tests.fakes.photo_scenes import PlacedPhoto, build_photo_scene_jpeg
from tests.fakes.recording_free_space_reader import RecordingFreeSpaceReader
from tests.fakes.sample_images import build_sample_jpeg
from tests.fakes.scripted_file_writer import ScriptedFileWriter
from tests.fakes.synthetic_scans import build_scan_jpeg

STARTED_AT = datetime(2026, 10, 13, 15, 30, 12, tzinfo=timezone(timedelta(hours=-3)))
SETTINGS = ScanSettings(300, ColorMode.COLOR)
REQUEST = ScanRequest(SETTINGS, OutputFormat.PDF)
JOB = ScanJob(REQUEST, STARTED_AT)
SCAN_IDENTIFIERS = ["00000000000000a1", "00000000000000a2", "00000000000000a3"]
ENOUGH_FREE_SPACE = MINIMUM_FREE_SPACE_BYTES + SAFETY_MARGIN_PAGES * estimated_page_bytes(SETTINGS)
TWO_PHOTOS_SIZE = (582, 800)
TWO_PHOTOS = ScannedImage(
    build_photo_scene_jpeg(
        TWO_PHOTOS_SIZE,
        [PlacedPhoto((150.0, 260.0), (240, 300), 10.0), PlacedPhoto((430.0, 540.0), (240, 300), -6.0, 2)],
    ),
    "image/jpeg",
)
ONE_PHOTO = ScannedImage(
    build_photo_scene_jpeg(TWO_PHOTOS_SIZE, [PlacedPhoto((290.0, 400.0), (300, 400), 20.0)]), "image/jpeg"
)
WHITE_PAGE = ScannedImage(build_scan_jpeg((200, 280)), "image/jpeg")


def job_with(
    output_format: OutputFormat = OutputFormat.PDF, auto_crop: bool = False, jpeg_quality: int = 90
) -> ScanJob:
    adjustment = ImageAdjustment(auto_crop=auto_crop, jpeg_quality=jpeg_quality)
    return ScanJob(ScanRequest(SETTINGS, output_format, adjustment), STARTED_AT)


class StubCropDetectionService(PageCropDetectionService):
    def __init__(self, failure: Exception | None = None) -> None:
        self._failure = failure
        self.detection_count = 0

    def detect_crops(self, jpeg_content: bytes) -> DetectedCrops:
        self.detection_count += 1
        if self._failure is not None:
            raise self._failure
        return super().detect_crops(jpeg_content)


class FailingOutputRepository(FileSystemScanOutputRepository):
    """Saves for real, but the save with the given number (from 1) fails."""

    def __init__(self, inner: FileSystemScanOutputRepository, failing_save_number: int) -> None:
        self._inner = inner
        self._failing_save_number = failing_save_number
        self._save_count = 0

    def __getattr__(self, name: str):
        return getattr(self._inner, name)

    def save(self, encoded_scan: EncodedScan) -> Path:
        self._save_count += 1
        if self._save_count == self._failing_save_number:
            raise OutputFolderUnavailableError("The external disk was disconnected")
        return self._inner.save(encoded_scan)


class Environment:
    def __init__(self, tmp_path: Path, free_space: int = ENOUGH_FREE_SPACE) -> None:
        self.output_folder = tmp_path / "scans"
        self.slot_folder = tmp_path / "quick-scan"
        self.free_space_reader = RecordingFreeSpaceReader(free_space)
        settings_repository = InMemoryApplicationSettingsRepository(self._settings())
        self.output_repository = FileSystemScanOutputRepository(
            settings_repository, ScanFileNamingPolicy(), InstantFileWriter()
        )
        self.slot_repository = FileSystemQuickScanSlotRepository(
            self.slot_folder, InstantFileWriter(), FixedClock(STARTED_AT)
        )
        self.detection_service = StubCropDetectionService()
        self.identifiers = iter(SCAN_IDENTIFIERS)

    def _settings(self):
        return ApplicationSettings(self.output_folder, OutputFormat.PDF, ScanPreset.DOCUMENT.settings)

    def build_service(self, output_repository=None, slot_repository=None) -> ScanOutputService:
        scan_encoder = ScanEncoder(JpegResolutionService(), PdfAssemblyService(), ThumbnailService())
        parts = ScanOutputParts(
            scan_encoder=scan_encoder,
            output_renderer=QuickScanOutputRenderer(PageFramingRenderer(), scan_encoder),
            crop_detection_service=self.detection_service,
            storage_guard_service=StorageGuardService(self.free_space_reader),
            scan_identifier_factory=lambda: next(self.identifiers),
        )
        return ScanOutputService(
            parts, output_repository or self.output_repository, slot_repository or self.slot_repository
        )

    def saved_names(self) -> list[str]:
        return sorted(path.name for path in self.output_folder.iterdir())


@pytest.fixture
def environment(tmp_path: Path) -> Environment:
    return Environment(tmp_path)


def read_image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def test_capacity_check_prepares_the_output_folder(environment):
    environment.build_service().ensure_capacity(REQUEST)

    assert environment.output_folder.is_dir()


def test_capacity_check_asks_about_the_output_folder(environment):
    environment.build_service().ensure_capacity(REQUEST)

    assert environment.free_space_reader.requested_folders == [environment.output_folder]


def test_capacity_check_passes_with_exactly_the_required_space(tmp_path):
    Environment(tmp_path, ENOUGH_FREE_SPACE).build_service().ensure_capacity(REQUEST)


def test_capacity_check_refuses_one_byte_less_than_the_required_space(tmp_path):
    environment = Environment(tmp_path, ENOUGH_FREE_SPACE - 1)

    with pytest.raises(InsufficientStorageError):
        environment.build_service().ensure_capacity(REQUEST)


def test_a_folder_that_vanishes_before_the_space_check_is_reported_as_unavailable(tmp_path):
    environment = Environment(tmp_path)
    environment.free_space_reader.failure = OutputFolderUnavailableError("The external disk was disconnected")

    with pytest.raises(OutputFolderUnavailableError):
        environment.build_service().ensure_capacity(REQUEST)


ADJUSTED_REQUEST = ScanRequest(SETTINGS, OutputFormat.PDF, ImageAdjustment(auto_crop=True))
ENOUGH_FREE_SPACE_FOR_AN_ADJUSTED_PAGE = MINIMUM_FREE_SPACE_BYTES + SAFETY_MARGIN_PAGES * estimated_page_bytes(
    SETTINGS, ADJUSTED_REQUEST.adjustment
)


def test_capacity_check_counts_the_adjustment_of_the_request(tmp_path):
    environment = Environment(tmp_path, ENOUGH_FREE_SPACE_FOR_AN_ADJUSTED_PAGE - 1)

    with pytest.raises(InsufficientStorageError):
        environment.build_service().ensure_capacity(ADJUSTED_REQUEST)


def test_capacity_check_accepts_exactly_the_space_of_an_adjusted_page(tmp_path):
    Environment(tmp_path, ENOUGH_FREE_SPACE_FOR_AN_ADJUSTED_PAGE).build_service().ensure_capacity(ADJUSTED_REQUEST)


def test_the_quality_makes_the_capacity_check_stricter(tmp_path):
    top_quality = ScanRequest(SETTINGS, OutputFormat.PDF, ImageAdjustment(auto_crop=True, jpeg_quality=100))
    environment = Environment(tmp_path, ENOUGH_FREE_SPACE_FOR_AN_ADJUSTED_PAGE)

    with pytest.raises(InsufficientStorageError):
        environment.build_service().ensure_capacity(top_quality)


def test_a_scan_without_the_crop_saves_one_jpg_with_the_bytes_of_the_scanner(environment):
    scanned_image = ScannedImage(build_sample_jpeg(), "image/jpeg")

    stored_scan = environment.build_service().store(scanned_image, job_with(OutputFormat.JPEG))

    saved_path = environment.output_folder / stored_scan.last_scan.saved_files[0].file_name
    master_jpeg = environment.slot_repository.master_file_path(stored_scan.last_scan.scan_identifier).read_bytes()
    assert saved_path.read_bytes() == master_jpeg


def test_a_scan_without_the_crop_saves_a_pdf_of_one_page(environment):
    stored_scan = environment.build_service().store(ONE_PHOTO, job_with(OutputFormat.PDF))

    with pikepdf.open(environment.output_folder / stored_scan.last_scan.saved_files[0].file_name) as pdf:
        assert len(pdf.pages) == 1


def test_a_scan_without_the_crop_does_not_look_for_photos(environment):
    environment.build_service().store(ONE_PHOTO, job_with())

    assert environment.detection_service.detection_count == 0


def test_a_scan_without_the_crop_has_no_frames(environment):
    stored_scan = environment.build_service().store(ONE_PHOTO, job_with())

    assert stored_scan.last_scan.framing.crops == ()


def test_the_master_of_the_scan_is_kept_in_the_slot_with_the_density(environment):
    stored_scan = environment.build_service().store(ONE_PHOTO, job_with())

    master_path = environment.slot_repository.master_file_path(stored_scan.last_scan.scan_identifier)
    with Image.open(master_path) as image:
        assert (image.size, image.info["dpi"]) == (TWO_PHOTOS_SIZE, (300, 300))


def test_the_slot_is_committed_with_the_density_and_the_colour_of_the_scan(environment):
    environment.build_service().store(ONE_PHOTO, job_with())

    slot = environment.slot_repository.load()
    assert (slot.dots_per_inch, slot.color_mode, slot.render_pending) == (300, ColorMode.COLOR, False)


def test_the_slot_cites_the_saved_files_with_their_sizes(environment):
    stored_scan = environment.build_service().store(ONE_PHOTO, job_with())

    saved_file = stored_scan.last_scan.saved_files[0]
    assert saved_file.size_in_bytes == (environment.output_folder / saved_file.file_name).stat().st_size
    assert environment.slot_repository.load().last_scan.saved_files == stored_scan.last_scan.saved_files


def test_the_stored_scan_gives_the_thumbnail_of_the_master(environment):
    stored_scan = environment.build_service().store(ONE_PHOTO, job_with())

    thumbnail_jpeg = environment.slot_repository.read_thumbnail(stored_scan.last_scan.scan_identifier)
    assert thumbnail_jpeg == stored_scan.thumbnail_jpeg


def test_the_scan_identifier_is_the_one_of_the_factory(environment):
    assert environment.build_service().store(ONE_PHOTO, job_with()).last_scan.scan_identifier == SCAN_IDENTIFIERS[0]


def test_the_last_scan_describes_the_output_folder_and_the_moment(environment):
    last_scan = environment.build_service().store(ONE_PHOTO, job_with()).last_scan

    assert (last_scan.output_folder, last_scan.scanned_at, last_scan.is_editable) == (
        environment.output_folder,
        STARTED_AT,
        True,
    )


def test_one_photo_with_the_crop_saves_one_cropped_file(environment):
    stored_scan = environment.build_service().store(ONE_PHOTO, job_with(OutputFormat.JPEG, auto_crop=True))

    saved_path = environment.output_folder / stored_scan.last_scan.saved_files[0].file_name
    assert len(stored_scan.last_scan.framing.crops) == 1
    assert read_image_size(saved_path)[0] < TWO_PHOTOS_SIZE[0]


def test_two_photos_with_the_crop_save_two_files_with_consecutive_names(environment):
    stored_scan = environment.build_service().store(TWO_PHOTOS, job_with(OutputFormat.JPEG, auto_crop=True))

    assert [saved_file.file_name for saved_file in stored_scan.last_scan.saved_files] == [
        "2026-10-13_00001.jpg",
        "2026-10-13_00002.jpg",
    ]


def test_two_photos_with_the_crop_keep_two_frames_in_the_last_scan(environment):
    stored_scan = environment.build_service().store(TWO_PHOTOS, job_with(OutputFormat.JPEG, auto_crop=True))

    assert len(stored_scan.last_scan.framing.crops) == 2


def test_each_file_of_two_photos_has_the_size_of_its_photo(environment):
    stored_scan = environment.build_service().store(TWO_PHOTOS, job_with(OutputFormat.JPEG, auto_crop=True))

    sizes = [read_image_size(environment.output_folder / f.file_name) for f in stored_scan.last_scan.saved_files]
    assert sizes == [pytest.approx((240, 300), abs=30), pytest.approx((240, 300), abs=30)]


def test_two_photos_saved_as_pdf_make_two_pdf_files_of_one_page(environment):
    environment.build_service().store(TWO_PHOTOS, job_with(OutputFormat.PDF, auto_crop=True))

    page_counts = []
    for name in environment.saved_names():
        with pikepdf.open(environment.output_folder / name) as pdf:
            page_counts.append(len(pdf.pages))
    assert page_counts == [1, 1]


def test_the_two_files_come_from_one_master(environment):
    environment.build_service().store(TWO_PHOTOS, job_with(OutputFormat.JPEG, auto_crop=True))

    slot_names = sorted(path.name for path in environment.slot_folder.iterdir())
    master_names = [name for name in slot_names if name.startswith("master")]
    assert master_names == [f"master-{SCAN_IDENTIFIERS[0]}.jpg"]


def test_a_white_page_with_the_crop_is_saved_whole(environment):
    stored_scan = environment.build_service().store(WHITE_PAGE, job_with(OutputFormat.JPEG, auto_crop=True))

    assert (stored_scan.last_scan.framing.crops, len(stored_scan.last_scan.saved_files)) == ((), 1)


def test_a_detection_that_fails_still_saves_the_whole_image(tmp_path):
    environment = Environment(tmp_path)
    environment.detection_service = StubCropDetectionService(ScanFailedError("x"))

    stored_scan = environment.build_service().store(ONE_PHOTO, job_with(OutputFormat.JPEG, auto_crop=True))

    saved_size = read_image_size(environment.output_folder / "2026-10-13_00001.jpg")
    assert (stored_scan.last_scan.framing.crops, saved_size) == ((), TWO_PHOTOS_SIZE)


def test_a_detection_that_fails_is_reported_in_the_log(tmp_path, caplog):
    environment = Environment(tmp_path)
    environment.detection_service = StubCropDetectionService(ScanFailedError("x"))

    with caplog.at_level(logging.WARNING):
        environment.build_service().store(ONE_PHOTO, job_with(OutputFormat.JPEG, auto_crop=True))

    assert "automatic crop of the scan failed" in caplog.text


def test_a_lower_quality_gives_smaller_files(environment, tmp_path):
    high = Environment(tmp_path / "high")
    low = Environment(tmp_path / "low")
    high.build_service().store(ONE_PHOTO, job_with(OutputFormat.JPEG, auto_crop=True, jpeg_quality=95))
    low.build_service().store(ONE_PHOTO, job_with(OutputFormat.JPEG, auto_crop=True, jpeg_quality=60))

    sizes = [(env.output_folder / "2026-10-13_00001.jpg").stat().st_size for env in (high, low)]
    assert sizes[1] < sizes[0]


def test_a_master_that_the_disk_does_not_take_still_gives_the_files(tmp_path):
    environment = Environment(tmp_path)
    failing_slot = FileSystemQuickScanSlotRepository(
        environment.slot_folder,
        ScriptedFileWriter({f"master-{SCAN_IDENTIFIERS[0]}.jpg": OSError(28, "No space left on device")}),
        FixedClock(STARTED_AT),
    )

    stored_scan = environment.build_service(slot_repository=failing_slot).store(
        ONE_PHOTO, job_with(OutputFormat.JPEG, auto_crop=True)
    )

    assert (stored_scan.last_scan.is_editable, environment.saved_names()) == (False, ["2026-10-13_00001.jpg"])


def test_a_scan_without_a_master_leaves_no_manifest(tmp_path):
    environment = Environment(tmp_path)
    failing_slot = FileSystemQuickScanSlotRepository(
        environment.slot_folder,
        ScriptedFileWriter({f"master-{SCAN_IDENTIFIERS[0]}.jpg": OSError(28, "No space left on device")}),
        FixedClock(STARTED_AT),
    )

    environment.build_service(slot_repository=failing_slot).store(ONE_PHOTO, job_with())

    assert failing_slot.load() is None


def test_a_scan_without_a_master_forgets_the_slot_of_the_previous_scan(tmp_path):
    environment = Environment(tmp_path)
    environment.build_service().store(ONE_PHOTO, job_with())
    failing_slot = FileSystemQuickScanSlotRepository(
        environment.slot_folder,
        ScriptedFileWriter({f"master-{SCAN_IDENTIFIERS[1]}.jpg": OSError(28, "No space left on device")}),
        FixedClock(STARTED_AT),
    )

    environment.build_service(slot_repository=failing_slot).store(ONE_PHOTO, job_with())

    assert failing_slot.load() is None


def test_a_manifest_that_cannot_be_written_gives_a_scan_that_cannot_be_adjusted(tmp_path):
    environment = Environment(tmp_path)
    failing_slot = FileSystemQuickScanSlotRepository(
        environment.slot_folder,
        ScriptedFileWriter({"manifest.json": OSError(5, "Input/output error")}),
        FixedClock(STARTED_AT),
    )

    stored_scan = environment.build_service(slot_repository=failing_slot).store(ONE_PHOTO, job_with())

    assert stored_scan.last_scan.is_editable is False


def test_the_next_scan_deletes_the_master_of_the_previous_one(environment):
    service = environment.build_service()
    service.store(ONE_PHOTO, job_with())

    service.store(ONE_PHOTO, job_with())

    master_names = [path.name for path in environment.slot_folder.iterdir() if path.name.startswith("master")]
    assert master_names == [f"master-{SCAN_IDENTIFIERS[1]}.jpg"]


def test_the_next_scan_continues_the_sequence_of_the_day(environment):
    service = environment.build_service()
    service.store(TWO_PHOTOS, job_with(OutputFormat.JPEG, auto_crop=True))

    stored_scan = service.store(ONE_PHOTO, job_with(OutputFormat.JPEG))

    assert stored_scan.last_scan.saved_files[0].file_name == "2026-10-13_00003.jpg"


def test_an_encoder_error_propagates_and_nothing_is_saved(environment):
    bad_image = ScannedImage(b"not a jpeg", "image/jpeg")

    with pytest.raises(ScanFailedError):
        environment.build_service().store(bad_image, job_with())

    assert environment.output_folder.exists() is False


def test_a_repository_error_propagates(environment):
    failing_repository = FailingOutputRepository(environment.output_repository, 1)

    with pytest.raises(OutputFolderUnavailableError):
        environment.build_service(output_repository=failing_repository).store(ONE_PHOTO, job_with())


def test_a_failure_on_the_second_file_keeps_the_slot_of_the_previous_scan(environment):
    environment.build_service().store(ONE_PHOTO, job_with())
    failing_repository = FailingOutputRepository(environment.output_repository, 2)

    with pytest.raises(DigitalizadoraError):
        environment.build_service(output_repository=failing_repository).store(
            TWO_PHOTOS, job_with(OutputFormat.JPEG, auto_crop=True)
        )

    assert environment.slot_repository.load().last_scan.scan_identifier == SCAN_IDENTIFIERS[0]


def test_a_failure_on_the_second_file_leaves_the_first_in_the_folder(environment):
    failing_repository = FailingOutputRepository(environment.output_repository, 2)

    with pytest.raises(DigitalizadoraError):
        environment.build_service(output_repository=failing_repository).store(
            TWO_PHOTOS, job_with(OutputFormat.JPEG, auto_crop=True)
        )

    assert environment.saved_names() == ["2026-10-13_00001.jpg"]


def test_the_frames_are_in_reading_order_in_the_last_scan(environment):
    stored_scan = environment.build_service().store(TWO_PHOTOS, job_with(OutputFormat.JPEG, auto_crop=True))

    crops = stored_scan.last_scan.framing.crops
    assert crops[0].bounding_edges.top < crops[1].bounding_edges.top


def test_the_master_files_keep_the_scanner_bytes_exactly(environment):
    stored_scan = environment.build_service().store(ONE_PHOTO, job_with())

    expected = JpegResolutionService().with_resolution(ONE_PHOTO.content, 300)
    master_path = environment.slot_repository.master_file_path(stored_scan.last_scan.scan_identifier)
    assert master_path.read_bytes() == expected


def test_running_out_of_memory_while_making_the_files_is_an_image_adjustment_failure(environment, monkeypatch):
    def exhaust_memory(*arguments: object) -> object:
        raise MemoryError

    monkeypatch.setattr(PageFramingRenderer, "render_jpeg", exhaust_memory)

    with pytest.raises(ImageAdjustmentFailedError):
        environment.build_service().store(ONE_PHOTO, job_with(OutputFormat.JPEG, auto_crop=True))

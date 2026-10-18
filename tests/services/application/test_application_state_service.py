from pathlib import Path

import pytest

from digitalizadora.domain.errors import OutputFolderUnavailableError
from digitalizadora.domain.output.output_format import OutputFormat
from digitalizadora.domain.settings.application_settings import ApplicationSettings
from digitalizadora.domain.settings.scan_preset import ScanPreset
from digitalizadora.services.application.application_state_service import (
    ApplicationStateService,
    StorageState,
)
from digitalizadora.services.application.scan_progress_tracker import ScanProgressTracker
from digitalizadora.services.application.storage_guard_service import (
    StorageGuardService,
    read_free_space_in_bytes,
)
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.in_memory_settings_repository import InMemoryApplicationSettingsRepository
from tests.fakes.recording_free_space_reader import RecordingFreeSpaceReader
from tests.fakes.stored_scans import STORED_SCAN_SCANNED_AT

OUTPUT_FOLDER = Path("/Volumes/External/scans")
FREE_SPACE_IN_BYTES = 50 * 1024**3
SETTINGS = ApplicationSettings(
    output_folder=OUTPUT_FOLDER,
    output_format=OutputFormat.PDF,
    scan_settings=ScanPreset.DOCUMENT.settings,
)
UNAVAILABLE_STORAGE = StorageState(
    free_space_in_bytes=0, estimated_pages_remaining=0, output_folder_available=False
)


def build_unreadable_folder_reader() -> RecordingFreeSpaceReader:
    """Behaves like read_free_space_in_bytes when the folder exists but cannot be inspected."""
    unreadable_reader = RecordingFreeSpaceReader(FREE_SPACE_IN_BYTES)
    unreadable_reader.failure = OutputFolderUnavailableError(f"Permission denied: {OUTPUT_FOLDER}")
    return unreadable_reader


@pytest.fixture
def progress_tracker() -> ScanProgressTracker:
    return ScanProgressTracker(FixedClock(STORED_SCAN_SCANNED_AT))


@pytest.fixture
def settings_repository() -> InMemoryApplicationSettingsRepository:
    return InMemoryApplicationSettingsRepository(SETTINGS)


@pytest.fixture
def free_space_reader() -> RecordingFreeSpaceReader:
    return RecordingFreeSpaceReader(FREE_SPACE_IN_BYTES)


@pytest.fixture
def storage_guard_service(free_space_reader: RecordingFreeSpaceReader) -> StorageGuardService:
    return StorageGuardService(free_space_reader)


@pytest.fixture
def state_service(
    progress_tracker: ScanProgressTracker,
    settings_repository: InMemoryApplicationSettingsRepository,
    storage_guard_service: StorageGuardService,
) -> ApplicationStateService:
    return ApplicationStateService(progress_tracker, settings_repository, storage_guard_service)


def build_state_service_with_reader(
    progress_tracker: ScanProgressTracker,
    settings_repository: InMemoryApplicationSettingsRepository,
    free_space_reader: RecordingFreeSpaceReader,
) -> ApplicationStateService:
    storage_guard_service = StorageGuardService(free_space_reader)
    return ApplicationStateService(progress_tracker, settings_repository, storage_guard_service)


def test_state_contains_the_tracker_snapshot(
    state_service: ApplicationStateService, progress_tracker: ScanProgressTracker
) -> None:
    progress_tracker.begin_scan(SETTINGS.to_scan_request())
    progress_tracker.mark_scanning()

    assert state_service.build_state().snapshot == progress_tracker.snapshot()


def test_state_contains_the_saved_settings(state_service: ApplicationStateService) -> None:
    assert state_service.build_state().settings == SETTINGS


def test_state_reflects_settings_saved_after_the_service_was_built(
    state_service: ApplicationStateService,
    settings_repository: InMemoryApplicationSettingsRepository,
) -> None:
    photo_settings = ApplicationSettings(
        output_folder=OUTPUT_FOLDER,
        output_format=OutputFormat.JPEG,
        scan_settings=ScanPreset.PHOTO.settings,
    )
    settings_repository.save(photo_settings)

    assert state_service.build_state().settings == photo_settings


def test_state_reports_the_free_space_of_the_output_folder(
    state_service: ApplicationStateService,
) -> None:
    assert state_service.build_state().storage.free_space_in_bytes == FREE_SPACE_IN_BYTES


def test_state_reads_the_free_space_of_the_saved_output_folder(
    state_service: ApplicationStateService, free_space_reader: RecordingFreeSpaceReader
) -> None:
    state_service.build_state()

    assert set(free_space_reader.requested_folders) == {OUTPUT_FOLDER}


def test_state_estimates_pages_for_the_selected_preset(
    state_service: ApplicationStateService, storage_guard_service: StorageGuardService
) -> None:
    expected_pages = storage_guard_service.estimate_pages_remaining(
        OUTPUT_FOLDER, ScanPreset.DOCUMENT.settings
    )

    state = state_service.build_state()

    assert state.storage == StorageState(
        free_space_in_bytes=FREE_SPACE_IN_BYTES,
        estimated_pages_remaining=expected_pages,
        output_folder_available=True,
    )


def test_storage_state_reports_an_available_folder_by_default() -> None:
    assert StorageState(free_space_in_bytes=1, estimated_pages_remaining=1).output_folder_available


def test_a_heavier_preset_leaves_fewer_estimated_pages(
    state_service: ApplicationStateService,
    settings_repository: InMemoryApplicationSettingsRepository,
) -> None:
    settings_repository.save(
        ApplicationSettings(OUTPUT_FOLDER, OutputFormat.PDF, ScanPreset.DOCUMENT_ECONOMY.settings)
    )
    economy_pages = state_service.build_state().storage.estimated_pages_remaining
    settings_repository.save(ApplicationSettings(OUTPUT_FOLDER, OutputFormat.PDF, ScanPreset.PHOTO.settings))

    photo_pages = state_service.build_state().storage.estimated_pages_remaining

    assert photo_pages < economy_pages


def test_missing_output_folder_gives_an_unavailable_storage_state(
    progress_tracker: ScanProgressTracker, tmp_path: Path
) -> None:
    missing_folder_settings = ApplicationSettings(
        output_folder=tmp_path / "unplugged-disk" / "scans",
        output_format=OutputFormat.PDF,
        scan_settings=ScanPreset.DOCUMENT.settings,
    )
    state_service = ApplicationStateService(
        progress_tracker,
        InMemoryApplicationSettingsRepository(missing_folder_settings),
        StorageGuardService(read_free_space_in_bytes),
    )

    assert state_service.build_state().storage == UNAVAILABLE_STORAGE


def test_unreadable_output_folder_gives_an_unavailable_storage_state(
    progress_tracker: ScanProgressTracker,
    settings_repository: InMemoryApplicationSettingsRepository,
) -> None:
    state_service = build_state_service_with_reader(
        progress_tracker, settings_repository, build_unreadable_folder_reader()
    )

    assert state_service.build_state().storage == UNAVAILABLE_STORAGE


def test_unavailable_output_folder_still_reports_the_settings(
    progress_tracker: ScanProgressTracker,
    settings_repository: InMemoryApplicationSettingsRepository,
) -> None:
    state_service = build_state_service_with_reader(
        progress_tracker, settings_repository, build_unreadable_folder_reader()
    )

    assert state_service.build_state().settings == SETTINGS


def test_unavailable_output_folder_still_reports_the_snapshot(
    progress_tracker: ScanProgressTracker,
    settings_repository: InMemoryApplicationSettingsRepository,
) -> None:
    state_service = build_state_service_with_reader(
        progress_tracker, settings_repository, build_unreadable_folder_reader()
    )
    progress_tracker.begin_scan(SETTINGS.to_scan_request())
    progress_tracker.mark_failed("output_folder_unavailable")

    assert state_service.build_state().snapshot == progress_tracker.snapshot()

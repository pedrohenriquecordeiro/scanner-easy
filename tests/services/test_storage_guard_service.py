import errno
import shutil
from pathlib import Path

import pytest

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import InsufficientStorageError, OutputFolderUnavailableError
from digitalizadora.domain.image_adjustment import NO_ADJUSTMENT, ImageAdjustment
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.services.storage_guard_service import (
    ADJUSTED_PAGE_SIZE_FACTOR,
    MINIMUM_FREE_SPACE_BYTES,
    SAFETY_MARGIN_PAGES,
    StorageGuardService,
    estimated_page_bytes,
    read_free_space_in_bytes,
)
from tests.fakes.recording_free_space_reader import RecordingFreeSpaceReader


def test_free_space_of_an_existing_folder_is_a_positive_integer(tmp_path):
    free_space = read_free_space_in_bytes(tmp_path)

    assert isinstance(free_space, int)
    assert free_space > 0


def test_missing_folder_raises_output_folder_unavailable_instead_of_reading_its_parent(tmp_path):
    with pytest.raises(OutputFolderUnavailableError):
        read_free_space_in_bytes(tmp_path / "not-yet-created")


def test_regular_file_raises_output_folder_unavailable(tmp_path):
    regular_file = tmp_path / "scans"
    regular_file.write_bytes(b"not a folder")

    with pytest.raises(OutputFolderUnavailableError):
        read_free_space_in_bytes(regular_file)


def test_folder_that_cannot_be_examined_raises_output_folder_unavailable(tmp_path, monkeypatch):
    def denied_folder_check(self: Path) -> bool:
        raise PermissionError(errno.EPERM, "Operation not permitted")

    monkeypatch.setattr(Path, "is_dir", denied_folder_check)

    with pytest.raises(OutputFolderUnavailableError):
        read_free_space_in_bytes(tmp_path)


@pytest.mark.parametrize(
    "disk_usage_error",
    [PermissionError(errno.EACCES, "Permission denied"), OSError(errno.EIO, "Input/output error")],
)
def test_failure_to_read_the_disk_usage_raises_output_folder_unavailable(tmp_path, monkeypatch, disk_usage_error):
    def failing_disk_usage(path: Path) -> None:
        raise disk_usage_error

    monkeypatch.setattr(shutil, "disk_usage", failing_disk_usage)

    with pytest.raises(OutputFolderUnavailableError):
        read_free_space_in_bytes(tmp_path)


OUTPUT_FOLDER = Path("/Volumes/Archive/Scans")
COLOR_AT_300 = ScanSettings(300, ColorMode.COLOR)
GRAYSCALE_AT_300 = ScanSettings(300, ColorMode.GRAYSCALE)
GRAYSCALE_AT_200 = ScanSettings(200, ColorMode.GRAYSCALE)
COLOR_AT_600 = ScanSettings(600, ColorMode.COLOR)


def build_guard(free_space_in_bytes: int) -> StorageGuardService:
    return StorageGuardService(RecordingFreeSpaceReader(free_space_in_bytes))


def required_free_space(settings: ScanSettings) -> int:
    return MINIMUM_FREE_SPACE_BYTES + SAFETY_MARGIN_PAGES * estimated_page_bytes(settings)


def test_color_page_at_300_dots_per_inch_is_estimated_at_the_documented_size():
    assert estimated_page_bytes(COLOR_AT_300) == 1_073_142


def test_grayscale_page_at_200_dots_per_inch_is_estimated_at_the_documented_size():
    assert estimated_page_bytes(GRAYSCALE_AT_200) == 317_968


def test_grayscale_page_is_smaller_than_a_color_page_of_the_same_resolution():
    assert estimated_page_bytes(GRAYSCALE_AT_300) < estimated_page_bytes(COLOR_AT_300)


def test_page_at_600_dots_per_inch_is_four_times_the_page_at_300():
    assert estimated_page_bytes(COLOR_AT_600) == 4 * estimated_page_bytes(COLOR_AT_300)


def test_free_space_exactly_at_the_required_amount_is_accepted():
    build_guard(required_free_space(COLOR_AT_300)).ensure_space_for_scan(OUTPUT_FOLDER, COLOR_AT_300)


def test_free_space_one_byte_above_the_required_amount_is_accepted():
    build_guard(required_free_space(COLOR_AT_300) + 1).ensure_space_for_scan(OUTPUT_FOLDER, COLOR_AT_300)


def test_free_space_one_byte_below_the_required_amount_is_refused():
    guard = build_guard(required_free_space(COLOR_AT_300) - 1)

    with pytest.raises(InsufficientStorageError):
        guard.ensure_space_for_scan(OUTPUT_FOLDER, COLOR_AT_300)


def test_empty_disk_is_refused():
    with pytest.raises(InsufficientStorageError):
        build_guard(0).ensure_space_for_scan(OUTPUT_FOLDER, COLOR_AT_300)


def test_space_that_fits_a_300_dots_per_inch_scan_may_not_fit_a_600_dots_per_inch_scan():
    guard = build_guard(required_free_space(COLOR_AT_300))

    guard.ensure_space_for_scan(OUTPUT_FOLDER, COLOR_AT_300)
    with pytest.raises(InsufficientStorageError):
        guard.ensure_space_for_scan(OUTPUT_FOLDER, COLOR_AT_600)


def test_guard_asks_the_reader_about_the_given_folder():
    reader = RecordingFreeSpaceReader(required_free_space(COLOR_AT_300))

    StorageGuardService(reader).ensure_space_for_scan(OUTPUT_FOLDER, COLOR_AT_300)

    assert reader.requested_folders == [OUTPUT_FOLDER]


def test_unavailable_folder_propagates_from_the_space_check():
    reader = RecordingFreeSpaceReader(required_free_space(COLOR_AT_300))
    reader.failure = OutputFolderUnavailableError("The external disk was disconnected")

    with pytest.raises(OutputFolderUnavailableError):
        StorageGuardService(reader).ensure_space_for_scan(OUTPUT_FOLDER, COLOR_AT_300)


def test_no_pages_remain_when_free_space_equals_the_minimum():
    assert build_guard(MINIMUM_FREE_SPACE_BYTES).estimate_pages_remaining(OUTPUT_FOLDER, COLOR_AT_300) == 0


@pytest.mark.parametrize("free_space_in_bytes", [0, MINIMUM_FREE_SPACE_BYTES - 1])
def test_no_pages_remain_when_free_space_is_below_the_minimum(free_space_in_bytes):
    guard = build_guard(free_space_in_bytes)

    assert guard.estimate_pages_remaining(OUTPUT_FOLDER, COLOR_AT_300) == 0


def test_one_page_remains_when_free_space_exceeds_the_minimum_by_exactly_one_page():
    free_space = MINIMUM_FREE_SPACE_BYTES + estimated_page_bytes(COLOR_AT_300)

    assert build_guard(free_space).estimate_pages_remaining(OUTPUT_FOLDER, COLOR_AT_300) == 1


def test_no_page_remains_when_free_space_is_one_byte_short_of_one_page():
    free_space = MINIMUM_FREE_SPACE_BYTES + estimated_page_bytes(COLOR_AT_300) - 1

    assert build_guard(free_space).estimate_pages_remaining(OUTPUT_FOLDER, COLOR_AT_300) == 0


def test_partial_pages_are_rounded_down():
    free_space = MINIMUM_FREE_SPACE_BYTES + 2 * estimated_page_bytes(COLOR_AT_300) + 1

    assert build_guard(free_space).estimate_pages_remaining(OUTPUT_FOLDER, COLOR_AT_300) == 2


def test_grayscale_fits_more_pages_than_color_in_the_same_space():
    guard = build_guard(MINIMUM_FREE_SPACE_BYTES + 100 * estimated_page_bytes(COLOR_AT_300))

    assert guard.estimate_pages_remaining(OUTPUT_FOLDER, GRAYSCALE_AT_300) > guard.estimate_pages_remaining(
        OUTPUT_FOLDER, COLOR_AT_300
    )


def test_free_space_in_bytes_reports_what_the_reader_returns():
    reader = RecordingFreeSpaceReader(123_456)

    assert StorageGuardService(reader).free_space_in_bytes(OUTPUT_FOLDER) == 123_456
    assert reader.requested_folders == [OUTPUT_FOLDER]


def test_unavailable_folder_propagates_from_the_free_space_query():
    reader = RecordingFreeSpaceReader(123_456)
    reader.failure = OutputFolderUnavailableError("The external disk was disconnected")

    with pytest.raises(OutputFolderUnavailableError):
        StorageGuardService(reader).free_space_in_bytes(OUTPUT_FOLDER)


def test_default_reader_reads_the_real_disk(tmp_path):
    assert StorageGuardService().free_space_in_bytes(tmp_path) > 0


DOCUMENT_SIZE_IN_BYTES = 5_000_000


def test_free_space_exactly_at_the_minimum_plus_the_file_size_is_accepted():
    guard = build_guard(MINIMUM_FREE_SPACE_BYTES + DOCUMENT_SIZE_IN_BYTES)

    guard.ensure_space_for_file(OUTPUT_FOLDER, DOCUMENT_SIZE_IN_BYTES)


def test_free_space_one_byte_below_the_minimum_plus_the_file_size_is_refused():
    guard = build_guard(MINIMUM_FREE_SPACE_BYTES + DOCUMENT_SIZE_IN_BYTES - 1)

    with pytest.raises(InsufficientStorageError):
        guard.ensure_space_for_file(OUTPUT_FOLDER, DOCUMENT_SIZE_IN_BYTES)


def test_space_check_for_a_file_asks_the_reader_about_the_given_folder():
    reader = RecordingFreeSpaceReader(MINIMUM_FREE_SPACE_BYTES + DOCUMENT_SIZE_IN_BYTES)

    StorageGuardService(reader).ensure_space_for_file(OUTPUT_FOLDER, DOCUMENT_SIZE_IN_BYTES)

    assert reader.requested_folders == [OUTPUT_FOLDER]


def test_unavailable_folder_propagates_from_the_space_check_for_a_file():
    reader = RecordingFreeSpaceReader(MINIMUM_FREE_SPACE_BYTES + DOCUMENT_SIZE_IN_BYTES)
    reader.failure = OutputFolderUnavailableError("The external disk was disconnected")

    with pytest.raises(OutputFolderUnavailableError):
        StorageGuardService(reader).ensure_space_for_file(OUTPUT_FOLDER, DOCUMENT_SIZE_IN_BYTES)


CROPPED = ImageAdjustment(auto_crop=True)
COLOR_AT_1200 = ScanSettings(1200, ColorMode.COLOR)


def test_an_active_crop_doubles_the_estimated_page_size():
    assert estimated_page_bytes(COLOR_AT_300, CROPPED) == ADJUSTED_PAGE_SIZE_FACTOR * estimated_page_bytes(COLOR_AT_300)


def test_no_adjustment_keeps_the_estimated_page_size():
    assert estimated_page_bytes(COLOR_AT_300, NO_ADJUSTMENT) == estimated_page_bytes(COLOR_AT_300)


def test_the_adjusted_factor_is_two():
    assert ADJUSTED_PAGE_SIZE_FACTOR == 2


def test_a_page_at_1200_dots_per_inch_is_four_times_the_page_at_600():
    assert estimated_page_bytes(COLOR_AT_1200) == pytest.approx(4 * estimated_page_bytes(COLOR_AT_600), rel=1e-5)


def test_the_space_check_counts_the_adjusted_page_size():
    required = MINIMUM_FREE_SPACE_BYTES + SAFETY_MARGIN_PAGES * estimated_page_bytes(COLOR_AT_300, CROPPED)
    guard = build_guard(required - 1)

    with pytest.raises(InsufficientStorageError):
        guard.ensure_space_for_scan(OUTPUT_FOLDER, COLOR_AT_300, CROPPED)


def test_the_space_check_without_adjustment_still_accepts_what_it_accepted_before():
    build_guard(required_free_space(COLOR_AT_300)).ensure_space_for_scan(OUTPUT_FOLDER, COLOR_AT_300, NO_ADJUSTMENT)


def test_fewer_pages_remain_when_an_adjustment_is_active():
    guard = build_guard(MINIMUM_FREE_SPACE_BYTES + 100 * estimated_page_bytes(COLOR_AT_300))

    assert guard.estimate_pages_remaining(OUTPUT_FOLDER, COLOR_AT_300, CROPPED) == 50

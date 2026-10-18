import asyncio
import errno
import threading
from dataclasses import replace
from pathlib import Path

import pikepdf
import pytest
from PIL import Image

from digitalizadora.domain.errors import (
    InvalidCropError,
    LastScanBusyError,
    LastScanFileMissingError,
    LastScanNotEditableError,
    NoLastScanError,
    OutputFolderUnavailableError,
    SavedScanUnreadableError,
    ScanAlreadyRunningError,
)
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.page_rotation import PageRotation
from digitalizadora.domain.scan_progress import ScanPhase
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.domain.stored_scan import StoredScan
from digitalizadora.repositories.file_system_scan_output_repository import FileSystemScanOutputRepository
from digitalizadora.services.last_scan_edit_service import LastScanEditService
from tests.fakes.page_crops import quadrilateral, rectangle
from tests.fakes.quick_scan_parts import (
    ONE_PHOTO,
    PHOTO_SIZE,
    SCENE_SIZE,
    TWO_PHOTOS,
    WHOLE_IMAGE,
    WITH_AUTO_CROP,
    QuickScanParts,
    build_job,
    build_quick_scan_parts,
    read_image_size,
)
from tests.fakes.scripted_file_writer import ScriptedFileWriter
from tests.fakes.synthetic_scans import build_scan_jpeg

JPEG_QUALITY = 90
FIRST_FILE = "2026-10-13_00001.jpg"
SECOND_FILE = "2026-10-13_00002.jpg"
THIRD_FILE = "2026-10-13_00003.jpg"
LEFT_BOX = rectangle((0.05, 0.05, 0.45, 0.45))
RIGHT_BOX = rectangle((0.55, 0.55, 0.95, 0.95))
TILTED_BOX = quadrilateral((0.30, 0.10), (0.80, 0.22), (0.70, 0.60), (0.20, 0.48))


@pytest.fixture
def parts(tmp_path: Path) -> QuickScanParts:
    return build_quick_scan_parts(tmp_path)


@pytest.fixture
def service(parts: QuickScanParts) -> LastScanEditService:
    return parts.last_scan_edit_service


def current_last_scan(parts: QuickScanParts):
    return parts.progress_tracker.snapshot().last_scan


def revision_of(parts: QuickScanParts) -> int:
    return parts.progress_tracker.snapshot().last_result_revision


def file_size(parts: QuickScanParts, file_name: str) -> tuple[int, int]:
    return read_image_size(parts.output_folder / file_name)


def two_photo_scan(parts: QuickScanParts, output_format: OutputFormat = OutputFormat.JPEG) -> None:
    parts.scan(TWO_PHOTOS, build_job(output_format, WITH_AUTO_CROP))


def one_whole_scan(parts: QuickScanParts) -> None:
    parts.scan(ONE_PHOTO, build_job(OutputFormat.JPEG))


async def test_turning_the_scan_turns_its_rotation(parts, service):
    one_whole_scan(parts)

    await service.rotate_clockwise(JPEG_QUALITY)

    assert current_last_scan(parts).framing.rotation is PageRotation.CLOCKWISE_90


async def test_turning_a_jpg_swaps_the_dimensions_of_the_file(parts, service):
    one_whole_scan(parts)

    await service.rotate_clockwise(JPEG_QUALITY)

    assert file_size(parts, FIRST_FILE) == SCENE_SIZE[::-1]


async def test_turning_a_pdf_writes_it_again_with_the_physical_size_swapped(parts, service):
    parts.scan(ONE_PHOTO, build_job(OutputFormat.PDF))
    pdf_path = parts.output_folder / "2026-10-13_00001.pdf"

    await service.rotate_clockwise(JPEG_QUALITY)

    with pikepdf.open(pdf_path) as pdf:
        assert (float(pdf.pages[0].mediabox[2]), float(pdf.pages[0].mediabox[3])) == pytest.approx(
            (SCENE_SIZE[1] * 72 / 300, SCENE_SIZE[0] * 72 / 300), abs=1.0
        )


async def test_turning_keeps_the_density_of_the_file(parts, service):
    one_whole_scan(parts)

    await service.rotate_clockwise(JPEG_QUALITY)

    with Image.open(parts.output_folder / FIRST_FILE) as image:
        assert image.info["dpi"] == pytest.approx((300, 300), abs=1)


async def test_turning_raises_the_revision_by_one(parts, service):
    one_whole_scan(parts)
    revision_before = revision_of(parts)

    await service.rotate_clockwise(JPEG_QUALITY)

    assert revision_of(parts) == revision_before + 1


async def test_turning_keeps_the_thumbnail_of_the_master(parts, service):
    one_whole_scan(parts)
    thumbnail_before = parts.progress_tracker.last_thumbnail_jpeg()

    await service.rotate_clockwise(JPEG_QUALITY)

    assert parts.progress_tracker.last_thumbnail_jpeg() == thumbnail_before


async def test_turning_does_not_count_a_new_scan(parts, service):
    one_whole_scan(parts)

    await service.rotate_clockwise(JPEG_QUALITY)

    assert parts.progress_tracker.snapshot().scans_completed == 1


async def test_four_turns_bring_the_file_back_to_its_size(parts, service):
    one_whole_scan(parts)

    for _ in range(4):
        await service.rotate_clockwise(JPEG_QUALITY)

    assert file_size(parts, FIRST_FILE) == SCENE_SIZE


async def test_turning_leaves_the_master_in_the_slot_untouched(parts, service):
    one_whole_scan(parts)
    master_path = parts.slot_repository.master_file_path(current_last_scan(parts).scan_identifier)
    master_before = master_path.read_bytes()

    await service.rotate_clockwise(JPEG_QUALITY)
    await service.rotate_clockwise(JPEG_QUALITY)

    assert master_path.read_bytes() == master_before


async def test_turning_writes_the_slot_without_the_pending_mark(parts, service):
    one_whole_scan(parts)

    await service.rotate_clockwise(JPEG_QUALITY)

    slot = parts.slot_repository.load()
    assert (slot.render_pending, slot.last_scan.framing.rotation) == (False, PageRotation.CLOCKWISE_90)


async def test_turning_updates_the_size_of_the_files_in_the_slot(parts, service):
    one_whole_scan(parts)

    result = await service.rotate_clockwise(JPEG_QUALITY)

    saved_file = result.last_scan.saved_files[0]
    assert saved_file.size_in_bytes == (parts.output_folder / FIRST_FILE).stat().st_size


async def test_turning_answers_the_new_last_scan(parts, service):
    one_whole_scan(parts)

    result = await service.rotate_clockwise(JPEG_QUALITY)

    assert result.last_scan == current_last_scan(parts)


async def test_a_lower_quality_makes_the_rewritten_file_smaller(tmp_path):
    sizes = []
    for quality in (60, 95):
        parts = build_quick_scan_parts(tmp_path / str(quality))
        one_whole_scan(parts)
        await parts.last_scan_edit_service.rotate_clockwise(quality)
        sizes.append((parts.output_folder / FIRST_FILE).stat().st_size)
    assert sizes[0] < sizes[1]


async def test_turning_two_framed_photos_rewrites_both_files(parts, service):
    two_photo_scan(parts)
    sizes_before = [file_size(parts, name) for name in (FIRST_FILE, SECOND_FILE)]

    await service.rotate_clockwise(JPEG_QUALITY)

    assert [file_size(parts, name) for name in (FIRST_FILE, SECOND_FILE)] == pytest.approx(
        [size[::-1] for size in sizes_before], abs=2
    )


async def test_turning_two_framed_photos_turns_their_frames_with_the_page(parts, service):
    two_photo_scan(parts)
    crops_before = current_last_scan(parts).framing.crops

    await service.rotate_clockwise(JPEG_QUALITY)

    turned = {tuple(sorted((c.x, c.y) for c in crop.corners)) for crop in current_last_scan(parts).framing.crops}
    expected = {tuple(sorted((c.x, c.y) for c in crop.turned_clockwise().corners)) for crop in crops_before}
    assert turned == expected


async def test_setting_the_same_crops_changes_nothing(parts, service):
    two_photo_scan(parts)
    crops = current_last_scan(parts).framing.crops
    revision_before = revision_of(parts)
    modified_before = [(parts.output_folder / n).stat().st_mtime_ns for n in (FIRST_FILE, SECOND_FILE)]

    result = await service.set_crops(crops, JPEG_QUALITY)

    assert revision_of(parts) == revision_before
    assert [(parts.output_folder / n).stat().st_mtime_ns for n in (FIRST_FILE, SECOND_FILE)] == modified_before
    assert result.last_scan == current_last_scan(parts)


async def test_adding_a_second_frame_creates_the_next_numbered_file(parts, service):
    parts.scan(ONE_PHOTO, build_job(OutputFormat.JPEG, WITH_AUTO_CROP))

    await service.set_crops([LEFT_BOX, RIGHT_BOX], JPEG_QUALITY)

    assert parts.saved_names() == [FIRST_FILE, SECOND_FILE]


async def test_a_frame_added_after_the_output_folder_changed_goes_next_to_the_first_file(parts, service, tmp_path):
    parts.scan(ONE_PHOTO, build_job(OutputFormat.JPEG, WITH_AUTO_CROP))
    settings = parts.settings_repository.load()
    parts.settings_repository.save(replace(settings, output_folder=tmp_path / "other-folder"))

    await service.set_crops([LEFT_BOX, RIGHT_BOX], JPEG_QUALITY)

    assert parts.saved_names() == [FIRST_FILE, SECOND_FILE]


async def test_a_scan_edited_after_the_output_folder_changed_can_still_be_turned(parts, service, tmp_path):
    parts.scan(ONE_PHOTO, build_job(OutputFormat.JPEG, WITH_AUTO_CROP))
    settings = parts.settings_repository.load()
    parts.settings_repository.save(replace(settings, output_folder=tmp_path / "other-folder"))
    await service.set_crops([LEFT_BOX, RIGHT_BOX], JPEG_QUALITY)

    await service.rotate_clockwise(JPEG_QUALITY)

    assert current_last_scan(parts).framing.rotation is PageRotation.CLOCKWISE_90


async def test_a_slot_that_is_gone_makes_the_scan_not_editable(parts, service):
    one_whole_scan(parts)
    parts.slot_repository.discard()

    with pytest.raises(SavedScanUnreadableError):
        await service.rotate_clockwise(JPEG_QUALITY)

    assert current_last_scan(parts).is_editable is False


async def test_adding_a_second_frame_lists_both_files_in_the_slot(parts, service):
    parts.scan(ONE_PHOTO, build_job(OutputFormat.JPEG, WITH_AUTO_CROP))

    await service.set_crops([LEFT_BOX, RIGHT_BOX], JPEG_QUALITY)

    assert [f.file_name for f in parts.slot_repository.load().last_scan.saved_files] == [FIRST_FILE, SECOND_FILE]


async def test_each_file_has_the_size_of_its_frame(parts, service):
    one_whole_scan(parts)

    await service.set_crops([LEFT_BOX, RIGHT_BOX], JPEG_QUALITY)

    assert [file_size(parts, name) for name in (FIRST_FILE, SECOND_FILE)] == pytest.approx(
        [(117, 160), (117, 160)], abs=2
    )


async def test_the_new_numbered_file_continues_the_sequence_of_the_day(parts, service):
    one_whole_scan(parts)
    parts.scan(ONE_PHOTO, build_job(OutputFormat.JPEG))

    await service.set_crops([LEFT_BOX, RIGHT_BOX], JPEG_QUALITY)

    assert parts.saved_names() == [FIRST_FILE, SECOND_FILE, THIRD_FILE]


async def test_removing_a_frame_deletes_only_the_file_of_that_frame(parts, service):
    two_photo_scan(parts)

    result = await service.set_crops(current_last_scan(parts).framing.crops[:1], JPEG_QUALITY)

    assert (parts.saved_names(), result.deleted_file_names, result.kept_file_names) == (
        [FIRST_FILE],
        (SECOND_FILE,),
        (),
    )


async def test_removing_the_first_frame_gives_the_first_file_the_content_of_the_second_photo(parts, service):
    two_photo_scan(parts)
    second_crop = current_last_scan(parts).framing.crops[1]

    await service.set_crops([second_crop], JPEG_QUALITY)

    assert file_size(parts, FIRST_FILE) == pytest.approx(PHOTO_SIZE, abs=15)
    assert parts.saved_names() == [FIRST_FILE]


async def test_a_file_edited_after_it_was_saved_is_kept_and_named(parts, service):
    two_photo_scan(parts)
    second_path = parts.output_folder / SECOND_FILE
    second_path.write_bytes(second_path.read_bytes() + b"edited later")

    result = await service.set_crops(current_last_scan(parts).framing.crops[:1], JPEG_QUALITY)

    assert (second_path.exists(), result.deleted_file_names, result.kept_file_names) == (True, (), (SECOND_FILE,))


async def test_a_file_that_is_already_gone_is_not_an_error_when_its_frame_is_removed(parts, service):
    two_photo_scan(parts)
    (parts.output_folder / SECOND_FILE).unlink()

    result = await service.set_crops(current_last_scan(parts).framing.crops[:1], JPEG_QUALITY)

    assert (result.deleted_file_names, result.kept_file_names) == ((), ())


async def test_removing_all_the_frames_leaves_one_whole_file(parts, service):
    two_photo_scan(parts)

    result = await service.set_crops([], JPEG_QUALITY)

    assert (file_size(parts, FIRST_FILE), parts.saved_names(), result.deleted_file_names) == (
        SCENE_SIZE,
        [FIRST_FILE],
        (SECOND_FILE,),
    )


async def test_a_new_frame_changes_the_file_to_a_crop(parts, service):
    one_whole_scan(parts)

    await service.set_crops([TILTED_BOX], JPEG_QUALITY)

    assert file_size(parts, FIRST_FILE) != SCENE_SIZE


async def test_a_tilted_frame_is_written_upright_with_the_size_of_its_edges(parts, service):
    one_whole_scan(parts)

    await service.set_crops([TILTED_BOX], JPEG_QUALITY)

    top_edge = (0.5 * SCENE_SIZE[0], 0.12 * SCENE_SIZE[1])
    assert file_size(parts, FIRST_FILE)[0] == pytest.approx((top_edge[0] ** 2 + top_edge[1] ** 2) ** 0.5, abs=2)


async def test_setting_crops_raises_the_revision(parts, service):
    one_whole_scan(parts)
    revision_before = revision_of(parts)

    await service.set_crops([LEFT_BOX], JPEG_QUALITY)

    assert revision_of(parts) == revision_before + 1


async def test_setting_more_than_two_crops_is_refused(parts, service):
    one_whole_scan(parts)

    with pytest.raises(InvalidCropError):
        await service.set_crops([LEFT_BOX, RIGHT_BOX, TILTED_BOX], JPEG_QUALITY)


async def test_a_missing_file_stops_the_edit_before_any_write(parts, service):
    two_photo_scan(parts)
    (parts.output_folder / FIRST_FILE).unlink()
    second_before = (parts.output_folder / SECOND_FILE).read_bytes()
    framing_before = current_last_scan(parts).framing

    with pytest.raises(LastScanFileMissingError):
        await service.rotate_clockwise(JPEG_QUALITY)

    assert (current_last_scan(parts).framing, (parts.output_folder / SECOND_FILE).read_bytes()) == (
        framing_before,
        second_before,
    )


async def test_a_missing_file_leaves_the_slot_as_it_was(parts, service):
    two_photo_scan(parts)
    (parts.output_folder / FIRST_FILE).unlink()
    slot_before = parts.slot_repository.load()

    with pytest.raises(LastScanFileMissingError):
        await service.rotate_clockwise(JPEG_QUALITY)

    assert parts.slot_repository.load() == slot_before


async def test_detecting_two_photos_on_a_scan_saved_whole_makes_two_files(parts, service):
    parts.scan(TWO_PHOTOS, build_job(OutputFormat.JPEG, WHOLE_IMAGE))

    result = await service.detect_crops(JPEG_QUALITY)

    assert (result.crops_detected, parts.saved_names()) == (True, [FIRST_FILE, SECOND_FILE])


async def test_detecting_reports_no_regions_ignored_for_two_photos(parts, service):
    parts.scan(TWO_PHOTOS, build_job(OutputFormat.JPEG, WHOLE_IMAGE))

    assert (await service.detect_crops(JPEG_QUALITY)).ignored_region_count == 0


async def test_detecting_nothing_changes_nothing(parts, service):
    from tests.fakes.quick_scan_parts import SCENE_SIZE

    parts.scan(ScannedImage(build_scan_jpeg(SCENE_SIZE), "image/jpeg"), build_job(OutputFormat.JPEG))
    revision_before = revision_of(parts)

    result = await service.detect_crops(JPEG_QUALITY)

    assert (result.crops_detected, revision_of(parts)) == (False, revision_before)


async def test_detecting_on_a_turned_scan_shows_the_crops_in_the_orientation_of_the_page(parts, service):
    parts.scan(TWO_PHOTOS, build_job(OutputFormat.JPEG, WHOLE_IMAGE))
    await service.rotate_clockwise(JPEG_QUALITY)

    await service.detect_crops(JPEG_QUALITY)

    framing = current_last_scan(parts).framing
    assert (framing.rotation, len(framing.crops)) == (PageRotation.CLOCKWISE_90, 2)
    assert file_size(parts, FIRST_FILE) == pytest.approx(PHOTO_SIZE[::-1], abs=15)


async def test_detecting_the_same_crops_again_changes_nothing(parts, service):
    parts.scan(TWO_PHOTOS, build_job(OutputFormat.JPEG, WITH_AUTO_CROP))
    revision_before = revision_of(parts)

    result = await service.detect_crops(JPEG_QUALITY)

    assert (result.crops_detected, revision_of(parts)) == (True, revision_before)


async def test_an_edit_without_a_scan_raises_no_last_scan(service):
    with pytest.raises(NoLastScanError):
        await service.rotate_clockwise(JPEG_QUALITY)


async def test_an_edit_during_a_scan_raises_scan_already_running(parts, service):
    one_whole_scan(parts)
    parts.progress_tracker.begin_scan(build_job().request)

    with pytest.raises(ScanAlreadyRunningError):
        await service.rotate_clockwise(JPEG_QUALITY)


async def test_an_edit_during_a_scan_writes_nothing(parts, service):
    one_whole_scan(parts)
    parts.progress_tracker.begin_scan(build_job().request)

    with pytest.raises(ScanAlreadyRunningError):
        await service.rotate_clockwise(JPEG_QUALITY)

    assert file_size(parts, FIRST_FILE) == SCENE_SIZE


async def test_a_scan_without_a_master_cannot_be_edited(parts, service):
    one_whole_scan(parts)
    parts.progress_tracker.replace_last_scan(
        current_last_scan(parts).scan_identifier,
        StoredScan(replace(current_last_scan(parts), is_editable=False), b"thumbnail"),
    )

    with pytest.raises(LastScanNotEditableError):
        await service.rotate_clockwise(JPEG_QUALITY)


async def test_a_master_that_vanished_raises_saved_scan_unreadable(parts, service):
    one_whole_scan(parts)
    parts.slot_repository.master_file_path(current_last_scan(parts).scan_identifier).unlink()

    with pytest.raises(SavedScanUnreadableError):
        await service.rotate_clockwise(JPEG_QUALITY)


async def test_a_master_that_cannot_be_decoded_raises_saved_scan_unreadable(parts, service):
    one_whole_scan(parts)
    parts.slot_repository.master_file_path(current_last_scan(parts).scan_identifier).write_bytes(b"not a jpeg")

    with pytest.raises(SavedScanUnreadableError):
        await service.rotate_clockwise(JPEG_QUALITY)


def stored_scan_of(last_scan) -> StoredScan:
    return StoredScan(last_scan, b"thumbnail")


async def test_a_failed_edit_restores_the_manifest_to_the_framing_of_before(tmp_path):
    parts = build_quick_scan_parts(tmp_path)
    one_whole_scan(parts)
    failing_output_repository = FileSystemScanOutputRepository(
        parts.output_repository._settings_repository,
        parts.output_repository._naming_policy,
        ScriptedFileWriter({FIRST_FILE: OSError(errno.EIO, "disk error")}),
    )
    failing_parts = build_quick_scan_parts(tmp_path, output_repository=failing_output_repository)
    failing_parts.progress_tracker.restore_last_scan(
        stored_scan_of(parts.progress_tracker.snapshot().last_scan)
    )

    with pytest.raises(OutputFolderUnavailableError):
        await failing_parts.last_scan_edit_service.rotate_clockwise(JPEG_QUALITY)

    slot = parts.slot_repository.load()
    assert (slot.render_pending, slot.last_scan.framing.rotation) == (False, PageRotation.NONE)


async def test_a_failed_edit_leaves_the_tracker_unchanged(tmp_path):
    parts = build_quick_scan_parts(tmp_path)
    one_whole_scan(parts)
    parts.slot_repository.master_file_path(current_last_scan(parts).scan_identifier).write_bytes(b"not a jpeg")
    last_scan_before = current_last_scan(parts)

    with pytest.raises(SavedScanUnreadableError):
        await parts.last_scan_edit_service.rotate_clockwise(JPEG_QUALITY)

    assert current_last_scan(parts) == last_scan_before


async def test_a_failed_edit_lets_a_scan_start_again(parts, service):
    one_whole_scan(parts)
    parts.slot_repository.master_file_path(current_last_scan(parts).scan_identifier).unlink()

    with pytest.raises(SavedScanUnreadableError):
        await service.rotate_clockwise(JPEG_QUALITY)

    parts.progress_tracker.begin_scan(build_job().request)
    assert parts.progress_tracker.snapshot().phase is ScanPhase.PREPARING


async def test_a_scan_that_starts_during_an_edit_is_refused_as_busy(tmp_path):
    parts = build_quick_scan_parts(tmp_path)
    one_whole_scan(parts)
    inside_edit = threading.Event()
    release_edit = threading.Event()
    original_replace = parts.output_repository.replace_saved_scan

    def hold_the_edit(scan_path: Path, content: bytes) -> None:
        inside_edit.set()
        release_edit.wait(timeout=5)
        original_replace(scan_path, content)

    parts.output_repository.replace_saved_scan = hold_the_edit
    edit = asyncio.create_task(parts.last_scan_edit_service.rotate_clockwise(JPEG_QUALITY))
    await asyncio.to_thread(inside_edit.wait, 5)

    with pytest.raises(LastScanBusyError):
        parts.progress_tracker.begin_scan(build_job().request)

    release_edit.set()
    await edit


async def test_two_edits_asked_at_once_are_done_one_after_the_other(parts, service):
    one_whole_scan(parts)

    await asyncio.gather(service.rotate_clockwise(JPEG_QUALITY), service.rotate_clockwise(JPEG_QUALITY))

    assert current_last_scan(parts).framing.rotation is PageRotation.HALF_TURN


async def test_a_slot_that_holds_another_scan_than_the_last_one_is_not_edited(tmp_path):
    parts = build_quick_scan_parts(tmp_path)
    one_whole_scan(parts)
    old_identifier = current_last_scan(parts).scan_identifier
    # The tracker now names another scan than the one the slot holds.
    other_scan = replace(current_last_scan(parts), scan_identifier="ffffffffffffffff")
    parts.progress_tracker.replace_last_scan(old_identifier, stored_scan_of(other_scan))
    revision_before = revision_of(parts)

    with pytest.raises(NoLastScanError):
        await parts.last_scan_edit_service.rotate_clockwise(JPEG_QUALITY)

    assert revision_of(parts) == revision_before

import dataclasses
from pathlib import Path

import pytest

from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.page_framing import PageFraming
from digitalizadora.domain.page_rotation import PageRotation
from tests.fakes.quick_scan_parts import (
    ONE_PHOTO,
    SCENE_SIZE,
    TWO_PHOTOS,
    WHOLE_IMAGE,
    WITH_AUTO_CROP,
    QuickScanParts,
    build_job,
    build_quick_scan_parts,
    read_image_size,
)

FIRST_FILE = "2026_10_13__15_30_12_000000000.jpg"
SECOND_FILE = "2026_10_13__15_30_12_000000001.jpg"
FIRST_WRITE_FIRST_PHOTO = "2026_10_13__15_30_12_000000000__1.jpg"
FIRST_WRITE_SECOND_PHOTO = "2026_10_13__15_30_12_000000000__2.jpg"
SECOND_WRITE_FIRST_PHOTO = "2026_10_13__15_30_12_000000001__1.jpg"
THIRD_WRITE_FIRST_PHOTO = "2026_10_13__15_30_12_000000002__1.jpg"
THIRD_WRITE_SECOND_PHOTO = "2026_10_13__15_30_12_000000002__2.jpg"


@pytest.fixture
def parts(tmp_path: Path) -> QuickScanParts:
    return build_quick_scan_parts(tmp_path)


def restart(parts: QuickScanParts) -> QuickScanParts:
    """A new run of the application over the same folders: new tracker, new services, same disk."""
    return build_quick_scan_parts(parts.output_folder.parent)


def commit_a_pending_render(parts: QuickScanParts, framing: PageFraming) -> None:
    """What a crash leaves in the middle of an edit: the manifest with the new framing and the pending mark."""
    slot = parts.slot_repository.load()
    pending_slot = dataclasses.replace(
        slot, last_scan=slot.last_scan.with_framing(framing), render_pending=True
    )
    parts.slot_repository.commit(pending_slot)


def test_without_a_slot_nothing_is_restored(parts):
    parts.last_scan_edit_service.restore_after_start()

    assert parts.progress_tracker.snapshot().last_scan is None


def test_a_slot_with_its_files_is_restored_into_the_tracker(parts):
    parts.scan(ONE_PHOTO, build_job(OutputFormat.JPEG))
    restarted = restart(parts)

    restarted.last_scan_edit_service.restore_after_start()

    assert restarted.progress_tracker.snapshot().last_scan == parts.slot_repository.load().last_scan


def test_the_restored_scan_brings_its_thumbnail(parts):
    stored_scan = parts.scan(ONE_PHOTO, build_job(OutputFormat.JPEG))
    restarted = restart(parts)

    restarted.last_scan_edit_service.restore_after_start()

    assert restarted.progress_tracker.last_thumbnail_jpeg() == stored_scan.thumbnail_jpeg


def test_a_thumbnail_that_is_missing_is_built_again_from_the_master(parts):
    stored_scan = parts.scan(ONE_PHOTO, build_job(OutputFormat.JPEG))
    (parts.slot_folder / f"thumbnail-{stored_scan.last_scan.scan_identifier}.jpg").unlink()
    restarted = restart(parts)

    restarted.last_scan_edit_service.restore_after_start()

    assert restarted.progress_tracker.last_thumbnail_jpeg() is not None


def test_a_restored_scan_does_not_count_as_a_scan_of_this_run(parts):
    parts.scan(ONE_PHOTO, build_job(OutputFormat.JPEG))
    restarted = restart(parts)

    restarted.last_scan_edit_service.restore_after_start()

    assert restarted.progress_tracker.snapshot().scans_completed == 0


async def test_a_restored_scan_can_be_edited(parts):
    parts.scan(ONE_PHOTO, build_job(OutputFormat.JPEG))
    restarted = restart(parts)
    restarted.last_scan_edit_service.restore_after_start()

    await restarted.last_scan_edit_service.rotate_clockwise()

    assert read_image_size(restarted.output_folder / SECOND_FILE) == SCENE_SIZE[::-1]

def test_a_restored_scan_keeps_the_framing_it_was_saved_with(parts):
    parts.scan(TWO_PHOTOS, build_job(OutputFormat.JPEG, WITH_AUTO_CROP))
    restarted = restart(parts)

    restarted.last_scan_edit_service.restore_after_start()

    assert len(restarted.progress_tracker.snapshot().last_scan.framing.crops) == 2


def test_a_slot_whose_files_were_all_deleted_is_forgotten(parts):
    parts.scan(ONE_PHOTO, build_job(OutputFormat.JPEG))
    (parts.output_folder / FIRST_FILE).unlink()
    restarted = restart(parts)

    restarted.last_scan_edit_service.restore_after_start()

    assert (restarted.progress_tracker.snapshot().last_scan, list(restarted.slot_folder.iterdir())) == (None, [])


def test_an_output_folder_that_is_not_reachable_does_not_cost_the_master(parts):
    stored_scan = parts.scan(ONE_PHOTO, build_job(OutputFormat.JPEG))
    parts.output_folder.rename(parts.output_folder.parent / "unplugged-disk")
    restarted = restart(parts)

    restarted.last_scan_edit_service.restore_after_start()

    assert (parts.slot_folder / f"master-{stored_scan.last_scan.scan_identifier}.jpg").is_file()


def test_an_output_folder_that_is_not_reachable_restores_no_panel(parts):
    parts.scan(ONE_PHOTO, build_job(OutputFormat.JPEG))
    parts.output_folder.rename(parts.output_folder.parent / "unplugged-disk")
    restarted = restart(parts)

    restarted.last_scan_edit_service.restore_after_start()

    assert restarted.progress_tracker.snapshot().last_scan is None


def test_a_slot_with_at_least_one_file_is_restored(parts):
    parts.scan(TWO_PHOTOS, build_job(OutputFormat.JPEG, WITH_AUTO_CROP))
    (parts.output_folder / FIRST_WRITE_SECOND_PHOTO).unlink()
    restarted = restart(parts)

    restarted.last_scan_edit_service.restore_after_start()

    assert restarted.progress_tracker.snapshot().last_scan is not None


def test_the_files_of_other_scans_are_deleted_from_the_slot(parts):
    stored_scan = parts.scan(ONE_PHOTO, build_job(OutputFormat.JPEG))
    (parts.slot_folder / "master-00000000000000ee.jpg").write_bytes(b"orphan")
    restarted = restart(parts)

    restarted.last_scan_edit_service.restore_after_start()

    assert sorted(path.name for path in restarted.slot_folder.iterdir()) == [
        "manifest.json",
        f"master-{stored_scan.last_scan.scan_identifier}.jpg",
        f"thumbnail-{stored_scan.last_scan.scan_identifier}.jpg",
    ]


def test_an_unreadable_manifest_leaves_the_panel_empty(parts):
    parts.scan(ONE_PHOTO, build_job(OutputFormat.JPEG))
    (parts.slot_folder / "manifest.json").write_bytes(b"{broken")
    restarted = restart(parts)

    restarted.last_scan_edit_service.restore_after_start()

    assert restarted.progress_tracker.snapshot().last_scan is None


def test_a_pending_render_is_finished_at_start_up_in_a_new_file(parts):
    parts.scan(ONE_PHOTO, build_job(OutputFormat.JPEG))
    commit_a_pending_render(parts, PageFraming(PageRotation.CLOCKWISE_90))
    restarted = restart(parts)

    restarted.last_scan_edit_service.restore_after_start()

    assert read_image_size(restarted.output_folder / SECOND_FILE) == SCENE_SIZE[::-1]


def test_a_pending_render_leaves_the_file_of_before_untouched(parts):
    parts.scan(ONE_PHOTO, build_job(OutputFormat.JPEG))
    content_before = (parts.output_folder / FIRST_FILE).read_bytes()
    commit_a_pending_render(parts, PageFraming(PageRotation.CLOCKWISE_90))
    restarted = restart(parts)

    restarted.last_scan_edit_service.restore_after_start()

    assert (restarted.output_folder / FIRST_FILE).read_bytes() == content_before


def test_a_pending_render_that_died_halfway_gets_its_own_complete_files(parts):
    parts.scan(TWO_PHOTOS, build_job(OutputFormat.JPEG, WITH_AUTO_CROP))
    crops = parts.slot_repository.load().last_scan.framing.crops
    commit_a_pending_render(parts, PageFraming(PageRotation.CLOCKWISE_90, crops))
    (parts.output_folder / SECOND_WRITE_FIRST_PHOTO).write_bytes(b"written before the crash")
    restarted = restart(parts)

    restarted.last_scan_edit_service.restore_after_start()

    saved_files = restarted.progress_tracker.snapshot().last_scan.saved_files
    assert [saved_file.file_name for saved_file in saved_files] == [THIRD_WRITE_FIRST_PHOTO, THIRD_WRITE_SECOND_PHOTO]

def test_a_finished_render_clears_the_pending_mark(parts):
    parts.scan(ONE_PHOTO, build_job(OutputFormat.JPEG))
    commit_a_pending_render(parts, PageFraming(PageRotation.CLOCKWISE_90))
    restarted = restart(parts)

    restarted.last_scan_edit_service.restore_after_start()

    assert restarted.slot_repository.load().render_pending is False


def test_a_finished_render_puts_the_new_framing_in_the_tracker(parts):
    parts.scan(ONE_PHOTO, build_job(OutputFormat.JPEG))
    commit_a_pending_render(parts, PageFraming(PageRotation.CLOCKWISE_90))
    restarted = restart(parts)

    restarted.last_scan_edit_service.restore_after_start()

    assert restarted.progress_tracker.snapshot().last_scan.framing.rotation is PageRotation.CLOCKWISE_90


def test_a_pending_render_with_two_new_frames_writes_two_new_files(parts):
    parts.scan(TWO_PHOTOS, build_job(OutputFormat.JPEG, WHOLE_IMAGE))
    detecting_parts = build_quick_scan_parts(parts.output_folder.parent / "other")
    detected = detecting_parts.scan(TWO_PHOTOS, build_job(OutputFormat.JPEG, WITH_AUTO_CROP))
    two_frames = PageFraming().with_crops(detected.last_scan.framing.crops)
    commit_a_pending_render(parts, two_frames)
    restarted = restart(parts)

    restarted.last_scan_edit_service.restore_after_start()

    assert restarted.saved_names() == [FIRST_FILE, FIRST_WRITE_FIRST_PHOTO, FIRST_WRITE_SECOND_PHOTO]

def test_a_pending_render_with_one_frame_less_keeps_every_earlier_file(parts):
    parts.scan(TWO_PHOTOS, build_job(OutputFormat.JPEG, WITH_AUTO_CROP))
    one_frame = PageFraming().with_crops(parts.slot_repository.load().last_scan.framing.crops[:1])
    commit_a_pending_render(parts, one_frame)
    restarted = restart(parts)

    restarted.last_scan_edit_service.restore_after_start()

    assert restarted.saved_names() == [FIRST_FILE, FIRST_WRITE_FIRST_PHOTO, FIRST_WRITE_SECOND_PHOTO]

def test_restoring_never_raises_when_the_slot_cannot_be_read(parts, monkeypatch):
    parts.scan(ONE_PHOTO, build_job(OutputFormat.JPEG))
    restarted = restart(parts)

    def fail(*arguments: object) -> object:
        raise RuntimeError("the disk exploded")

    monkeypatch.setattr(restarted.slot_repository, "load", fail)

    restarted.last_scan_edit_service.restore_after_start()

    assert restarted.progress_tracker.snapshot().last_scan is None


def test_a_failure_while_restoring_is_reported_in_the_log(parts, monkeypatch, caplog):
    parts.scan(ONE_PHOTO, build_job(OutputFormat.JPEG))
    restarted = restart(parts)
    monkeypatch.setattr(restarted.slot_repository, "load", lambda: 1 / 0)

    with caplog.at_level("WARNING"):
        restarted.last_scan_edit_service.restore_after_start()

    assert "could not be restored" in caplog.text

import errno
import logging
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import DraftStorageUnavailableError, InsufficientDraftStorageError
from digitalizadora.domain.last_scan import LastScan, QuickScanMasterFiles, QuickScanSlot, SavedScanFile
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter
from digitalizadora.repositories.file_system_quick_scan_slot_repository import FileSystemQuickScanSlotRepository
from digitalizadora.repositories.quick_scan_manifest_codec import encode_quick_scan_manifest
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.scripted_file_writer import ScriptedFileWriter

MOMENT = datetime(2026, 10, 18, 12, 41, 3, tzinfo=timezone(timedelta(hours=-3)))
FIRST_IDENTIFIER = "9f3c1a2b4d5e6f70"
SECOND_IDENTIFIER = "0a1b2c3d4e5f6a7b"
MASTER_BYTES = b"\xff\xd8 master of the scanner \xff\xd9"
THUMBNAIL_BYTES = b"\xff\xd8 thumbnail \xff\xd9"


def build_slot(scan_identifier: str = FIRST_IDENTIFIER) -> QuickScanSlot:
    return QuickScanSlot(
        last_scan=LastScan(
            scan_identifier=scan_identifier,
            scanned_at=MOMENT,
            output_folder=Path("/Users/pedro/Pictures/Digitalizadora"),
            output_format=OutputFormat.PDF,
            saved_files=(SavedScanFile("2026_10_18__16_14_03_000000006.pdf", 1000, 1760802063123456789),),
        ),
        dots_per_inch=300,
        color_mode=ColorMode.COLOR,
    )


def build_master_files(scan_identifier: str = FIRST_IDENTIFIER) -> QuickScanMasterFiles:
    return QuickScanMasterFiles(scan_identifier, MASTER_BYTES, THUMBNAIL_BYTES)


@pytest.fixture
def slot_folder(tmp_path: Path) -> Path:
    return tmp_path / "quick-scan"


@pytest.fixture
def repository(slot_folder: Path) -> FileSystemQuickScanSlotRepository:
    return FileSystemQuickScanSlotRepository(slot_folder, AtomicFileWriter(), FixedClock(MOMENT))


def file_names(slot_folder: Path) -> list[str]:
    return sorted(entry.name for entry in slot_folder.iterdir())


def store_a_scan(repository: FileSystemQuickScanSlotRepository, scan_identifier: str = FIRST_IDENTIFIER) -> None:
    repository.write_master_files(build_master_files(scan_identifier))
    repository.commit(build_slot(scan_identifier))


def test_the_storage_folder_is_the_one_given(repository, slot_folder):
    assert repository.storage_folder() == slot_folder


def test_ensure_storage_folder_ready_creates_the_folder(repository, slot_folder):
    repository.ensure_storage_folder_ready()

    assert slot_folder.is_dir()


def test_a_folder_that_cannot_be_created_is_reported_as_draft_storage_unavailable(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_bytes(b"a file where a folder should be")
    repository = FileSystemQuickScanSlotRepository(blocker / "quick-scan", AtomicFileWriter(), FixedClock(MOMENT))

    with pytest.raises(DraftStorageUnavailableError):
        repository.ensure_storage_folder_ready()


def test_the_master_and_the_thumbnail_are_written_under_the_scan_identifier(repository, slot_folder):
    repository.write_master_files(build_master_files())

    assert file_names(slot_folder) == [f"master-{FIRST_IDENTIFIER}.jpg", f"thumbnail-{FIRST_IDENTIFIER}.jpg"]


def test_the_master_is_kept_byte_by_byte(repository):
    repository.write_master_files(build_master_files())

    assert repository.master_file_path(FIRST_IDENTIFIER).read_bytes() == MASTER_BYTES


def test_the_thumbnail_is_read_back(repository):
    repository.write_master_files(build_master_files())

    assert repository.read_thumbnail(FIRST_IDENTIFIER) == THUMBNAIL_BYTES


def test_the_thumbnail_of_an_unknown_scan_is_none(repository):
    repository.ensure_storage_folder_ready()

    assert repository.read_thumbnail(SECOND_IDENTIFIER) is None


def test_writing_the_master_files_leaves_no_manifest(repository, slot_folder):
    repository.write_master_files(build_master_files())

    assert not (slot_folder / "manifest.json").exists()


def test_a_full_disk_while_writing_the_master_is_reported_as_insufficient_draft_storage(slot_folder):
    master_name = f"master-{FIRST_IDENTIFIER}.jpg"
    writer = ScriptedFileWriter({master_name: OSError(errno.ENOSPC, "No space left on device")})
    repository = FileSystemQuickScanSlotRepository(slot_folder, writer, FixedClock(MOMENT))

    with pytest.raises(InsufficientDraftStorageError):
        repository.write_master_files(build_master_files())


def test_without_a_slot_load_gives_none(repository):
    assert repository.load() is None


def test_a_committed_slot_is_loaded_back(repository):
    store_a_scan(repository)

    assert repository.load() == build_slot()


def test_the_manifest_is_the_encoded_slot(repository, slot_folder):
    store_a_scan(repository)

    assert (slot_folder / "manifest.json").read_bytes() == encode_quick_scan_manifest(build_slot())


def test_committing_the_next_scan_deletes_the_files_of_the_previous_one(repository, slot_folder):
    store_a_scan(repository, FIRST_IDENTIFIER)

    store_a_scan(repository, SECOND_IDENTIFIER)

    assert file_names(slot_folder) == [
        "manifest.json",
        f"master-{SECOND_IDENTIFIER}.jpg",
        f"thumbnail-{SECOND_IDENTIFIER}.jpg",
    ]


def test_a_failed_commit_keeps_the_previous_master(slot_folder):
    writer = ScriptedFileWriter({"manifest.json": OSError(errno.EIO, "disk error")})
    repository = FileSystemQuickScanSlotRepository(slot_folder, AtomicFileWriter(), FixedClock(MOMENT))
    store_a_scan(repository, FIRST_IDENTIFIER)
    failing_repository = FileSystemQuickScanSlotRepository(slot_folder, writer, FixedClock(MOMENT))
    failing_repository.write_master_files(build_master_files(SECOND_IDENTIFIER))

    with pytest.raises(DraftStorageUnavailableError):
        failing_repository.commit(build_slot(SECOND_IDENTIFIER))

    assert repository.master_file_path(FIRST_IDENTIFIER).read_bytes() == MASTER_BYTES


def test_committing_the_same_scan_again_replaces_the_manifest(repository):
    store_a_scan(repository)
    edited_slot = replace(build_slot(), render_pending=True)

    repository.commit(edited_slot)

    assert repository.load() == edited_slot


def test_a_commit_leaves_no_temporary_file(repository, slot_folder):
    store_a_scan(repository)

    assert [name for name in file_names(slot_folder) if name.startswith(".")] == []


def test_an_unreadable_manifest_is_set_aside_and_the_slot_is_empty(repository, slot_folder):
    store_a_scan(repository)
    (slot_folder / "manifest.json").write_bytes(b"{not json")

    assert repository.load() is None


def test_an_unreadable_manifest_and_the_files_with_it_move_to_a_set_aside_folder(repository, slot_folder):
    store_a_scan(repository)
    (slot_folder / "manifest.json").write_bytes(b"{not json")

    repository.load()

    folders = [entry for entry in slot_folder.iterdir() if entry.is_dir()]
    assert len(folders) == 1
    assert folders[0].name.startswith("set-aside-20261018-124103-")
    assert sorted(entry.name for entry in folders[0].iterdir()) == [
        "manifest.json",
        f"master-{FIRST_IDENTIFIER}.jpg",
        f"thumbnail-{FIRST_IDENTIFIER}.jpg",
    ]


def test_after_setting_aside_the_slot_folder_holds_only_the_set_aside_folder(repository, slot_folder):
    store_a_scan(repository)
    (slot_folder / "manifest.json").write_bytes(b"{not json")

    repository.load()

    assert [entry.name.startswith("set-aside-") for entry in slot_folder.iterdir()] == [True]


def test_a_manifest_without_its_master_is_set_aside(repository, slot_folder):
    store_a_scan(repository)
    repository.master_file_path(FIRST_IDENTIFIER).unlink()

    assert repository.load() is None


def test_a_manifest_with_an_empty_master_is_set_aside(repository):
    store_a_scan(repository)
    repository.master_file_path(FIRST_IDENTIFIER).write_bytes(b"")

    assert repository.load() is None


def test_setting_aside_is_reported_in_the_log(repository, slot_folder, caplog):
    store_a_scan(repository)
    (slot_folder / "manifest.json").write_bytes(b"{not json")

    with caplog.at_level(logging.WARNING):
        repository.load()

    assert "set aside" in caplog.text


def test_delete_leftovers_removes_the_files_of_other_scans(repository, slot_folder):
    store_a_scan(repository, FIRST_IDENTIFIER)
    repository.write_master_files(build_master_files(SECOND_IDENTIFIER))

    repository.delete_leftovers(FIRST_IDENTIFIER)

    assert file_names(slot_folder) == [
        "manifest.json",
        f"master-{FIRST_IDENTIFIER}.jpg",
        f"thumbnail-{FIRST_IDENTIFIER}.jpg",
    ]


def test_delete_leftovers_removes_temporary_files(repository, slot_folder):
    store_a_scan(repository)
    (slot_folder / f".master-{SECOND_IDENTIFIER}.jpg.1234-0a1b2c3d.part").write_bytes(b"half a master")

    repository.delete_leftovers(FIRST_IDENTIFIER)

    assert [name for name in file_names(slot_folder) if name.endswith(".part")] == []


def test_delete_leftovers_leaves_the_files_it_does_not_know(repository, slot_folder):
    store_a_scan(repository)
    (slot_folder / "notes.txt").write_bytes(b"not ours")

    repository.delete_leftovers(FIRST_IDENTIFIER)

    assert (slot_folder / "notes.txt").exists()


def test_delete_leftovers_without_a_kept_scan_removes_every_master(repository, slot_folder):
    repository.write_master_files(build_master_files())

    repository.delete_leftovers(None)

    assert file_names(slot_folder) == []


def test_delete_leftovers_of_a_missing_folder_is_not_an_error(repository):
    repository.delete_leftovers(None)


def test_discard_forgets_the_whole_slot(repository, slot_folder):
    store_a_scan(repository)

    repository.discard()

    assert (file_names(slot_folder), repository.load()) == ([], None)


def test_discard_keeps_a_set_aside_folder(repository, slot_folder):
    store_a_scan(repository)
    (slot_folder / "manifest.json").write_bytes(b"{not json")
    repository.load()

    repository.discard()

    assert [name.startswith("set-aside-") for name in file_names(slot_folder)] == [True]


@pytest.mark.parametrize(
    "crashed_write",
    [
        pytest.param(f"master-{SECOND_IDENTIFIER}.jpg", id="master"),
        pytest.param(f"thumbnail-{SECOND_IDENTIFIER}.jpg", id="thumbnail"),
        pytest.param("manifest.json", id="manifest"),
    ],
)
def test_a_crash_at_any_write_leaves_the_previous_slot_usable(slot_folder, crashed_write):
    writer = ScriptedFileWriter({crashed_write: OSError(errno.EIO, "power cut")})
    healthy = FileSystemQuickScanSlotRepository(slot_folder, AtomicFileWriter(), FixedClock(MOMENT))
    store_a_scan(healthy, FIRST_IDENTIFIER)
    crashing = FileSystemQuickScanSlotRepository(slot_folder, writer, FixedClock(MOMENT))

    with pytest.raises(DraftStorageUnavailableError):
        crashing.write_master_files(build_master_files(SECOND_IDENTIFIER))
        crashing.commit(build_slot(SECOND_IDENTIFIER))

    assert healthy.load() == build_slot(FIRST_IDENTIFIER)


def test_no_crash_ever_leaves_a_manifest_that_cites_a_missing_master(slot_folder):
    writer = ScriptedFileWriter({f"thumbnail-{SECOND_IDENTIFIER}.jpg": OSError(errno.EIO, "power cut")})
    healthy = FileSystemQuickScanSlotRepository(slot_folder, AtomicFileWriter(), FixedClock(MOMENT))
    store_a_scan(healthy, FIRST_IDENTIFIER)
    crashing = FileSystemQuickScanSlotRepository(slot_folder, writer, FixedClock(MOMENT))

    with pytest.raises(DraftStorageUnavailableError):
        crashing.write_master_files(build_master_files(SECOND_IDENTIFIER))

    loaded = healthy.load()
    assert loaded is not None and healthy.master_file_path(loaded.last_scan.scan_identifier).exists()

import errno
import fcntl
import os
import re
from contextlib import AbstractContextManager, nullcontext
from datetime import timedelta
from pathlib import Path

import pytest

from digitalizadora.domain.document_draft import DocumentPageFiles
from digitalizadora.domain.document_draft_reconciliation import DraftFileInventory
from digitalizadora.domain.errors import (
    DraftFolderInUseError,
    DraftStorageUnavailableError,
    InsufficientDraftStorageError,
    UnreadableDraftError,
)
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter
from digitalizadora.repositories.file_system_document_draft_repository import (
    FileSystemDocumentDraftRepository,
    translate_draft_storage_error,
)
from tests.fakes.document_drafts import (
    DRAFT_CREATED_AT,
    build_document_draft,
    page_identifier_at,
    seed_draft_folder,
    write_draft_folder,
)
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.sample_images import build_sample_jpeg
from tests.fakes.scripted_file_writer import ScriptedFileWriter

NOW = DRAFT_CREATED_AT + timedelta(minutes=15)
FIRST_PAGE_IDENTIFIER = page_identifier_at(1)
FIRST_PAGE_FILE_NAME = f"page-{FIRST_PAGE_IDENTIFIER}.jpg"
FIRST_THUMBNAIL_FILE_NAME = f"thumbnail-{FIRST_PAGE_IDENTIFIER}.jpg"
FIRST_PAGE_FILES = DocumentPageFiles(FIRST_PAGE_IDENTIFIER, b"page jpeg", b"thumbnail jpeg")
FULL_DISK_ERROR_NUMBERS = [errno.ENOSPC, errno.EDQUOT]
READ_ONLY_FOLDER_MODE = 0o500
CLOSED_FOLDER_MODE = 0o000
WRITABLE_FOLDER_MODE = 0o700
requires_permission_bits = pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permission bits")


@pytest.fixture
def drafts_folder(tmp_path: Path) -> Path:
    return tmp_path / "drafts"


@pytest.fixture
def draft_folder(drafts_folder: Path) -> Path:
    return drafts_folder / "current"


def build_repository(drafts_folder: Path) -> FileSystemDocumentDraftRepository:
    return FileSystemDocumentDraftRepository(drafts_folder, AtomicFileWriter(), FixedClock(NOW))


def build_scripted_repository(
    drafts_folder: Path, file_writer: ScriptedFileWriter
) -> FileSystemDocumentDraftRepository:
    return FileSystemDocumentDraftRepository(drafts_folder, file_writer, FixedClock(NOW))


def build_ready_repository(drafts_folder: Path) -> FileSystemDocumentDraftRepository:
    repository = build_repository(drafts_folder)
    repository.ensure_draft_folder_exists()
    return repository


def list_file_names(folder: Path) -> list[str]:
    return sorted(entry.name for entry in folder.iterdir())


def os_error(error_number: int) -> OSError:
    return OSError(error_number, os.strerror(error_number))


@pytest.mark.parametrize("error_number", FULL_DISK_ERROR_NUMBERS)
def test_full_disk_is_translated_to_insufficient_draft_storage(error_number):
    error = translate_draft_storage_error(os_error(error_number), "Cannot write the page")

    assert isinstance(error, InsufficientDraftStorageError)


def test_other_disk_error_is_translated_to_draft_storage_unavailable():
    error = translate_draft_storage_error(os_error(errno.EIO), "Cannot write the page")

    assert type(error) is DraftStorageUnavailableError


def test_claim_exclusive_access_creates_the_drafts_folder_with_the_owner_lock(drafts_folder):
    build_repository(drafts_folder).claim_exclusive_access()

    assert list_file_names(drafts_folder) == [".owner-lock"]


def test_second_repository_on_the_same_drafts_folder_is_refused(drafts_folder):
    owner_repository = build_repository(drafts_folder)
    owner_repository.claim_exclusive_access()

    with pytest.raises(DraftFolderInUseError):
        build_repository(drafts_folder).claim_exclusive_access()


def test_second_claim_on_the_same_repository_does_nothing(drafts_folder):
    repository = build_repository(drafts_folder)
    repository.claim_exclusive_access()

    repository.claim_exclusive_access()


def test_drafts_folder_that_is_a_file_cannot_be_claimed(drafts_folder):
    drafts_folder.parent.mkdir(parents=True, exist_ok=True)
    drafts_folder.write_bytes(b"not a folder")

    with pytest.raises(DraftStorageUnavailableError):
        build_repository(drafts_folder).claim_exclusive_access()


def test_storage_folder_is_the_drafts_folder(drafts_folder):
    assert build_repository(drafts_folder).storage_folder() == drafts_folder


def test_ensure_storage_folder_ready_creates_the_drafts_folder(drafts_folder):
    build_repository(drafts_folder).ensure_storage_folder_ready()

    assert drafts_folder.is_dir()


def test_storage_folder_below_a_file_raises_draft_storage_unavailable(tmp_path):
    (tmp_path / "blocking").write_bytes(b"not a folder")

    with pytest.raises(DraftStorageUnavailableError):
        build_repository(tmp_path / "blocking" / "drafts").ensure_storage_folder_ready()


def test_full_disk_while_preparing_the_storage_folder_raises_insufficient_draft_storage(drafts_folder, monkeypatch):
    def full_disk_mkdir(self: Path, *arguments: object, **options: object) -> None:
        raise os_error(errno.ENOSPC)

    monkeypatch.setattr(Path, "mkdir", full_disk_mkdir)

    with pytest.raises(InsufficientDraftStorageError):
        build_repository(drafts_folder).ensure_storage_folder_ready()


def test_ensure_draft_folder_exists_creates_the_current_folder(drafts_folder, draft_folder):
    build_repository(drafts_folder).ensure_draft_folder_exists()

    assert draft_folder.is_dir()


def test_ensure_draft_folder_exists_keeps_what_is_already_there(drafts_folder, draft_folder):
    write_draft_folder(drafts_folder, build_document_draft(1))

    build_repository(drafts_folder).ensure_draft_folder_exists()

    assert list_file_names(draft_folder) == ["manifest.json", FIRST_PAGE_FILE_NAME, FIRST_THUMBNAIL_FILE_NAME]


def test_load_manifest_without_a_draft_folder_returns_none(drafts_folder):
    assert build_repository(drafts_folder).load_manifest() is None


def test_saved_manifest_loads_back_the_same_draft(drafts_folder):
    repository = build_ready_repository(drafts_folder)
    draft = build_document_draft(2).renamed("Contrato do apartamento")

    repository.save_manifest(draft)

    assert repository.load_manifest() == draft


def test_manifest_is_saved_through_the_atomic_replacement(drafts_folder):
    file_writer = ScriptedFileWriter({})
    repository = build_scripted_repository(drafts_folder, file_writer)
    repository.ensure_draft_folder_exists()

    repository.save_manifest(build_document_draft(1))

    assert file_writer.written_file_names == ["manifest.json"]


@pytest.mark.parametrize("error_number", FULL_DISK_ERROR_NUMBERS)
def test_full_disk_while_saving_the_manifest_raises_insufficient_draft_storage(drafts_folder, error_number):
    repository = build_scripted_repository(drafts_folder, ScriptedFileWriter({"manifest.json": os_error(error_number)}))
    repository.ensure_draft_folder_exists()

    with pytest.raises(InsufficientDraftStorageError):
        repository.save_manifest(build_document_draft(1))


def test_manifest_that_is_not_json_raises_unreadable_draft(drafts_folder, draft_folder):
    draft_folder.mkdir(parents=True)
    (draft_folder / "manifest.json").write_bytes(b'{"format_version": 1, "na')

    with pytest.raises(UnreadableDraftError):
        build_repository(drafts_folder).load_manifest()


def test_manifest_that_cannot_be_read_raises_draft_storage_unavailable_not_unreadable(drafts_folder, draft_folder):
    (draft_folder / "manifest.json").mkdir(parents=True)

    with pytest.raises(DraftStorageUnavailableError) as raised:
        build_repository(drafts_folder).load_manifest()

    assert not isinstance(raised.value, UnreadableDraftError)


def test_folder_written_by_write_draft_folder_loads_back_the_same_draft(drafts_folder):
    draft = build_document_draft(3)
    write_draft_folder(drafts_folder, draft)

    assert build_repository(drafts_folder).load_manifest() == draft


def test_seeded_pages_have_the_sizes_of_the_manifest(drafts_folder):
    draft = seed_draft_folder(drafts_folder, [build_sample_jpeg(), build_sample_jpeg(width_pixels=32)])
    repository = build_repository(drafts_folder)

    sizes = [repository.page_file_size(page.page_identifier) for page in draft.pages]

    assert sizes == [page.size_in_bytes for page in draft.pages]


def test_seeded_pages_keep_the_given_order(drafts_folder):
    page_contents = [build_sample_jpeg(width_pixels=32), build_sample_jpeg(width_pixels=48)]
    seed_draft_folder(drafts_folder, page_contents)

    second_page_path = build_repository(drafts_folder).page_file_path(page_identifier_at(2))

    assert second_page_path.read_bytes() == page_contents[1]


def test_write_page_files_writes_the_page_before_the_thumbnail(drafts_folder):
    file_writer = ScriptedFileWriter({})
    repository = build_scripted_repository(drafts_folder, file_writer)
    repository.ensure_draft_folder_exists()

    repository.write_page_files(FIRST_PAGE_FILES)

    assert file_writer.written_file_names == [FIRST_PAGE_FILE_NAME, FIRST_THUMBNAIL_FILE_NAME]


def test_written_page_holds_the_jpeg_content(drafts_folder):
    repository = build_ready_repository(drafts_folder)

    repository.write_page_files(FIRST_PAGE_FILES)

    assert repository.page_file_path(FIRST_PAGE_IDENTIFIER).read_bytes() == b"page jpeg"


def test_thumbnail_failure_takes_the_new_page_away(drafts_folder, draft_folder):
    failures = {FIRST_THUMBNAIL_FILE_NAME: os_error(errno.EIO)}
    repository = build_scripted_repository(drafts_folder, ScriptedFileWriter(failures))
    repository.ensure_draft_folder_exists()

    with pytest.raises(DraftStorageUnavailableError):
        repository.write_page_files(FIRST_PAGE_FILES)

    assert list_file_names(draft_folder) == []


@pytest.mark.parametrize("error_number", FULL_DISK_ERROR_NUMBERS)
def test_full_disk_while_writing_a_page_raises_insufficient_draft_storage(drafts_folder, error_number):
    failures = {FIRST_PAGE_FILE_NAME: os_error(error_number)}
    repository = build_scripted_repository(drafts_folder, ScriptedFileWriter(failures))
    repository.ensure_draft_folder_exists()

    with pytest.raises(InsufficientDraftStorageError):
        repository.write_page_files(FIRST_PAGE_FILES)


def test_other_error_while_writing_a_page_raises_draft_storage_unavailable(drafts_folder):
    failures = {FIRST_PAGE_FILE_NAME: os_error(errno.EIO)}
    repository = build_scripted_repository(drafts_folder, ScriptedFileWriter(failures))
    repository.ensure_draft_folder_exists()

    with pytest.raises(DraftStorageUnavailableError):
        repository.write_page_files(FIRST_PAGE_FILES)


def test_page_file_path_is_inside_the_current_folder(drafts_folder, draft_folder):
    page_path = build_repository(drafts_folder).page_file_path(FIRST_PAGE_IDENTIFIER)

    assert page_path == draft_folder / FIRST_PAGE_FILE_NAME


def test_page_file_size_of_a_written_page(drafts_folder):
    repository = build_ready_repository(drafts_folder)
    repository.write_page_files(FIRST_PAGE_FILES)

    assert repository.page_file_size(FIRST_PAGE_IDENTIFIER) == len(b"page jpeg")


def test_page_file_size_of_a_missing_page_is_none(drafts_folder):
    assert build_ready_repository(drafts_folder).page_file_size(FIRST_PAGE_IDENTIFIER) is None


def test_page_file_size_that_cannot_be_examined_raises_draft_storage_unavailable(drafts_folder, draft_folder):
    drafts_folder.mkdir(parents=True)
    draft_folder.write_bytes(b"not a folder")

    with pytest.raises(DraftStorageUnavailableError):
        build_repository(drafts_folder).page_file_size(FIRST_PAGE_IDENTIFIER)


def test_read_thumbnail_returns_the_written_thumbnail(drafts_folder):
    repository = build_ready_repository(drafts_folder)
    repository.write_page_files(FIRST_PAGE_FILES)

    assert repository.read_thumbnail(FIRST_PAGE_IDENTIFIER) == b"thumbnail jpeg"


def test_read_thumbnail_of_a_missing_file_is_none(drafts_folder):
    assert build_ready_repository(drafts_folder).read_thumbnail(FIRST_PAGE_IDENTIFIER) is None


@pytest.mark.parametrize("invalid_identifier", ["3F9C0A1B2C3D4E5F", "last"])
def test_read_thumbnail_with_an_invalid_identifier_does_not_touch_the_disk(
    drafts_folder, draft_folder, invalid_identifier
):
    draft_folder.mkdir(parents=True)
    (draft_folder / f"thumbnail-{invalid_identifier}.jpg").write_bytes(b"must never be served")

    assert build_repository(drafts_folder).read_thumbnail(invalid_identifier) is None


def test_delete_page_files_removes_the_page_and_its_thumbnail(drafts_folder, draft_folder):
    repository = build_ready_repository(drafts_folder)
    repository.write_page_files(FIRST_PAGE_FILES)

    repository.delete_page_files(FIRST_PAGE_IDENTIFIER)

    assert list_file_names(draft_folder) == []


def test_delete_page_files_of_a_missing_page_does_not_raise(drafts_folder):
    build_ready_repository(drafts_folder).delete_page_files(FIRST_PAGE_IDENTIFIER)


@requires_permission_bits
def test_delete_page_files_never_raises_on_a_disk_error(drafts_folder, draft_folder):
    repository = build_ready_repository(drafts_folder)
    repository.write_page_files(FIRST_PAGE_FILES)
    draft_folder.chmod(READ_ONLY_FOLDER_MODE)
    try:
        repository.delete_page_files(FIRST_PAGE_IDENTIFIER)
    finally:
        draft_folder.chmod(WRITABLE_FOLDER_MODE)


def test_finished_document_that_exists_is_confirmed(drafts_folder, tmp_path):
    finished_document = tmp_path / "Contrato do apartamento.pdf"
    finished_document.write_bytes(b"%PDF-1.7")

    assert build_repository(drafts_folder).finished_document_exists(finished_document) is True


def test_missing_finished_document_is_not_confirmed(drafts_folder, tmp_path):
    assert build_repository(drafts_folder).finished_document_exists(tmp_path / "Contrato.pdf") is False


def test_folder_in_place_of_the_finished_document_is_not_confirmed(drafts_folder, tmp_path):
    (tmp_path / "Contrato.pdf").mkdir()

    assert build_repository(drafts_folder).finished_document_exists(tmp_path / "Contrato.pdf") is False


@requires_permission_bits
def test_finished_document_in_a_closed_folder_is_not_confirmed(drafts_folder, tmp_path):
    closed_folder = tmp_path / "Arquivo"
    closed_folder.mkdir()
    (closed_folder / "Contrato.pdf").write_bytes(b"%PDF-1.7")
    closed_folder.chmod(CLOSED_FOLDER_MODE)
    try:
        exists = build_repository(drafts_folder).finished_document_exists(closed_folder / "Contrato.pdf")
    finally:
        closed_folder.chmod(WRITABLE_FOLDER_MODE)

    assert exists is False


SECOND_PAGE_IDENTIFIER = page_identifier_at(2)
SET_ASIDE_FOLDER_PATTERN = re.compile(r"set-aside-20261017-101500-[0-9a-f]{8}")
PAGE_TEMPORARY_FILE_NAME = f".page-{SECOND_PAGE_IDENTIFIER}.jpg.4242-0a1b2c3d.part"
WRITE_PROBE_FILE_NAME = ".digitalizadora-write-probe-4242-0a1b2c3d"
EMPTY_INVENTORY = DraftFileInventory(
    page_file_sizes={},
    thumbnail_identifiers=frozenset(),
    temporary_file_names=frozenset(),
    unknown_file_names=frozenset(),
)


def write_files(folder: Path, file_names: list[str]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for file_name in file_names:
        (folder / file_name).write_bytes(b"12345")


def test_inventory_of_a_missing_draft_folder_is_empty(drafts_folder):
    assert build_repository(drafts_folder).take_inventory() == EMPTY_INVENTORY


def test_inventory_classifies_every_kind_of_name(drafts_folder, draft_folder):
    write_files(
        draft_folder,
        [
            "manifest.json",
            FIRST_PAGE_FILE_NAME,
            FIRST_THUMBNAIL_FILE_NAME,
            PAGE_TEMPORARY_FILE_NAME,
            WRITE_PROBE_FILE_NAME,
            ".DS_Store",
            "page-LAST.jpg",
            f".page-{SECOND_PAGE_IDENTIFIER}.jpg.part",
            "notes.txt",
        ],
    )
    (draft_folder / f"page-{SECOND_PAGE_IDENTIFIER}.jpg").mkdir()

    inventory = build_repository(drafts_folder).take_inventory()

    assert inventory == DraftFileInventory(
        page_file_sizes={FIRST_PAGE_IDENTIFIER: 5},
        thumbnail_identifiers=frozenset({FIRST_PAGE_IDENTIFIER}),
        temporary_file_names=frozenset({PAGE_TEMPORARY_FILE_NAME, WRITE_PROBE_FILE_NAME}),
        unknown_file_names=frozenset(
            {
                ".DS_Store",
                "page-LAST.jpg",
                f".page-{SECOND_PAGE_IDENTIFIER}.jpg.part",
                "notes.txt",
                f"page-{SECOND_PAGE_IDENTIFIER}.jpg",
            }
        ),
    )


def test_inventory_that_cannot_be_listed_raises_draft_storage_unavailable(drafts_folder, draft_folder):
    drafts_folder.mkdir(parents=True)
    draft_folder.write_bytes(b"not a folder")

    with pytest.raises(DraftStorageUnavailableError):
        build_repository(drafts_folder).take_inventory()


def test_page_that_vanishes_while_listing_does_not_empty_the_inventory(drafts_folder, draft_folder, monkeypatch):
    write_draft_folder(drafts_folder, build_document_draft(2))
    list_entries = os.scandir

    def scandir_then_remove_second_page(path: Path) -> AbstractContextManager[list[os.DirEntry]]:
        entries = list(list_entries(path))
        (draft_folder / f"page-{SECOND_PAGE_IDENTIFIER}.jpg").unlink()
        return nullcontext(entries)

    monkeypatch.setattr(os, "scandir", scandir_then_remove_second_page)

    inventory = build_repository(drafts_folder).take_inventory()

    assert sorted(inventory.page_file_sizes) == [FIRST_PAGE_IDENTIFIER]


def test_delete_files_removes_only_the_named_files(drafts_folder, draft_folder):
    write_files(draft_folder, ["manifest.json", FIRST_PAGE_FILE_NAME, FIRST_THUMBNAIL_FILE_NAME])

    build_repository(drafts_folder).delete_files([FIRST_PAGE_FILE_NAME, FIRST_THUMBNAIL_FILE_NAME])

    assert list_file_names(draft_folder) == ["manifest.json"]


def test_delete_files_refuses_a_name_that_climbs_out_of_the_draft_folder(drafts_folder, draft_folder):
    write_files(draft_folder, [FIRST_PAGE_FILE_NAME])
    write_files(drafts_folder, ["outside.txt"])

    build_repository(drafts_folder).delete_files(["../outside.txt"])

    assert (drafts_folder / "outside.txt").exists()


def test_delete_files_refuses_an_absolute_path(drafts_folder, tmp_path):
    write_files(tmp_path, ["outside.txt"])

    build_repository(drafts_folder).delete_files([str(tmp_path / "outside.txt")])

    assert (tmp_path / "outside.txt").exists()


def test_delete_files_of_missing_files_does_not_raise(drafts_folder):
    build_ready_repository(drafts_folder).delete_files([FIRST_PAGE_FILE_NAME])


@requires_permission_bits
def test_delete_files_never_raises_on_a_disk_error(drafts_folder, draft_folder):
    write_files(draft_folder, [FIRST_PAGE_FILE_NAME])
    draft_folder.chmod(READ_ONLY_FOLDER_MODE)
    try:
        build_repository(drafts_folder).delete_files([FIRST_PAGE_FILE_NAME])
    finally:
        draft_folder.chmod(WRITABLE_FOLDER_MODE)


def test_set_aside_files_moves_the_files_into_a_new_folder(drafts_folder, draft_folder):
    write_files(draft_folder, [FIRST_PAGE_FILE_NAME, f"page-{SECOND_PAGE_IDENTIFIER}.jpg"])

    set_aside_folder = build_repository(drafts_folder).set_aside_files([FIRST_PAGE_FILE_NAME])

    assert list_file_names(set_aside_folder) == [FIRST_PAGE_FILE_NAME]


def test_set_aside_files_keeps_the_other_files_in_place(drafts_folder, draft_folder):
    write_files(draft_folder, [FIRST_PAGE_FILE_NAME, f"page-{SECOND_PAGE_IDENTIFIER}.jpg"])

    build_repository(drafts_folder).set_aside_files([FIRST_PAGE_FILE_NAME])

    assert list_file_names(draft_folder) == [f"page-{SECOND_PAGE_IDENTIFIER}.jpg"]


def test_set_aside_files_folder_is_named_after_the_clock_inside_the_drafts_folder(drafts_folder, draft_folder):
    write_files(draft_folder, [FIRST_PAGE_FILE_NAME])

    set_aside_folder = build_repository(drafts_folder).set_aside_files([FIRST_PAGE_FILE_NAME])

    assert (set_aside_folder.parent, bool(SET_ASIDE_FOLDER_PATTERN.fullmatch(set_aside_folder.name))) == (
        drafts_folder,
        True,
    )


def test_set_aside_files_that_cannot_be_moved_raise_draft_storage_unavailable(drafts_folder):
    repository = build_ready_repository(drafts_folder)

    with pytest.raises(DraftStorageUnavailableError):
        repository.set_aside_files([FIRST_PAGE_FILE_NAME])


def test_set_aside_draft_folder_moves_the_whole_current_folder(drafts_folder, draft_folder):
    write_draft_folder(drafts_folder, build_document_draft(1))

    set_aside_folder = build_repository(drafts_folder).set_aside_draft_folder()

    assert (list_file_names(set_aside_folder), draft_folder.exists()) == (
        ["manifest.json", FIRST_PAGE_FILE_NAME, FIRST_THUMBNAIL_FILE_NAME],
        False,
    )


def test_set_aside_draft_folder_is_named_after_the_clock_inside_the_drafts_folder(drafts_folder):
    write_draft_folder(drafts_folder, build_document_draft(1))

    set_aside_folder = build_repository(drafts_folder).set_aside_draft_folder()

    assert (set_aside_folder.parent, bool(SET_ASIDE_FOLDER_PATTERN.fullmatch(set_aside_folder.name))) == (
        drafts_folder,
        True,
    )


def test_set_aside_draft_folder_without_a_current_folder_returns_none(drafts_folder):
    drafts_folder.mkdir(parents=True)

    assert build_repository(drafts_folder).set_aside_draft_folder() is None


@requires_permission_bits
def test_set_aside_draft_folder_that_cannot_be_renamed_raises_draft_storage_unavailable(drafts_folder):
    write_draft_folder(drafts_folder, build_document_draft(1))
    drafts_folder.chmod(READ_ONLY_FOLDER_MODE)
    try:
        with pytest.raises(DraftStorageUnavailableError):
            build_repository(drafts_folder).set_aside_draft_folder()
    finally:
        drafts_folder.chmod(WRITABLE_FOLDER_MODE)


def test_delete_draft_makes_the_manifest_deletion_durable_before_deleting_anything_else(drafts_folder, monkeypatch):
    write_draft_folder(drafts_folder, build_document_draft(2))
    events: list[str] = []
    original_unlink = Path.unlink
    original_fcntl = fcntl.fcntl

    def recording_unlink(self: Path, **options: object) -> None:
        events.append(self.name)
        original_unlink(self, **options)

    def recording_fcntl(descriptor: int, command: int) -> int:
        if command == fcntl.F_FULLFSYNC:
            events.append("folder flushed")
        return original_fcntl(descriptor, command)

    monkeypatch.setattr(Path, "unlink", recording_unlink)
    monkeypatch.setattr(fcntl, "fcntl", recording_fcntl)

    build_repository(drafts_folder).delete_draft()

    assert events == [
        "manifest.json",
        "folder flushed",
        FIRST_PAGE_FILE_NAME,
        f"page-{SECOND_PAGE_IDENTIFIER}.jpg",
        FIRST_THUMBNAIL_FILE_NAME,
        f"thumbnail-{SECOND_PAGE_IDENTIFIER}.jpg",
    ]


def test_delete_draft_removes_the_known_files_and_the_emptied_folder(drafts_folder):
    write_draft_folder(drafts_folder, build_document_draft(2))

    build_repository(drafts_folder).delete_draft()

    assert list_file_names(drafts_folder) == []


def test_unknown_file_survives_delete_draft(drafts_folder, draft_folder):
    write_draft_folder(drafts_folder, build_document_draft(1))
    write_files(draft_folder, [".DS_Store"])

    build_repository(drafts_folder).delete_draft()

    assert list_file_names(draft_folder) == [".DS_Store"]


def test_delete_draft_without_a_manifest_still_deletes_the_known_files(drafts_folder, draft_folder):
    write_files(draft_folder, [FIRST_PAGE_FILE_NAME, FIRST_THUMBNAIL_FILE_NAME, PAGE_TEMPORARY_FILE_NAME])

    build_repository(drafts_folder).delete_draft()

    assert list_file_names(drafts_folder) == []


def test_delete_draft_without_a_draft_folder_does_nothing(drafts_folder):
    drafts_folder.mkdir(parents=True)

    build_repository(drafts_folder).delete_draft()

    assert list_file_names(drafts_folder) == []


@requires_permission_bits
def test_failure_to_delete_the_manifest_preserves_every_file(drafts_folder, draft_folder):
    write_draft_folder(drafts_folder, build_document_draft(1))
    draft_folder.chmod(READ_ONLY_FOLDER_MODE)
    try:
        with pytest.raises(DraftStorageUnavailableError):
            build_repository(drafts_folder).delete_draft()
    finally:
        draft_folder.chmod(WRITABLE_FOLDER_MODE)

    assert list_file_names(draft_folder) == ["manifest.json", FIRST_PAGE_FILE_NAME, FIRST_THUMBNAIL_FILE_NAME]


def test_failure_to_synchronise_after_deleting_the_manifest_still_deletes_the_draft(drafts_folder, monkeypatch):
    write_draft_folder(drafts_folder, build_document_draft(2))

    def failing_flush_to_disk(descriptor: int) -> None:
        raise os_error(errno.EIO)

    monkeypatch.setattr(
        "digitalizadora.repositories.file_system_document_draft_repository.flush_to_disk", failing_flush_to_disk
    )

    build_repository(drafts_folder).delete_draft()

    assert list_file_names(drafts_folder) == []


def test_read_page_file_returns_the_whole_written_page(drafts_folder):
    repository = build_ready_repository(drafts_folder)
    repository.write_page_files(FIRST_PAGE_FILES)

    assert repository.read_page_file(FIRST_PAGE_IDENTIFIER) == b"page jpeg"


def test_read_page_file_of_a_missing_page_is_none(drafts_folder):
    assert build_ready_repository(drafts_folder).read_page_file(FIRST_PAGE_IDENTIFIER) is None


def test_read_page_file_that_cannot_be_read_raises_draft_storage_unavailable(drafts_folder, draft_folder):
    drafts_folder.mkdir(parents=True)
    draft_folder.write_bytes(b"not a folder")

    with pytest.raises(DraftStorageUnavailableError):
        build_repository(drafts_folder).read_page_file(FIRST_PAGE_IDENTIFIER)


def test_read_page_file_that_is_a_folder_raises_draft_storage_unavailable(drafts_folder, draft_folder):
    (draft_folder / FIRST_PAGE_FILE_NAME).mkdir(parents=True)

    with pytest.raises(DraftStorageUnavailableError):
        build_repository(drafts_folder).read_page_file(FIRST_PAGE_IDENTIFIER)

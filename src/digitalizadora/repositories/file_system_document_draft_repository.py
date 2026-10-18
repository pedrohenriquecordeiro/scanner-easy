import errno
import fcntl
import logging
import os
import secrets
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import BinaryIO

from digitalizadora.domain.document_draft import DocumentDraft, DocumentPageFiles, is_page_identifier
from digitalizadora.domain.document_draft_reconciliation import (
    JPEG_FILE_SUFFIX,
    MANIFEST_FILE_NAME,
    PAGE_FILE_PREFIX,
    THUMBNAIL_FILE_PREFIX,
    DraftFileInventory,
    page_file_name,
    thumbnail_file_name,
)
from digitalizadora.domain.errors import DigitalizadoraError, DraftFolderInUseError, as_draft_storage_error
from digitalizadora.domain.ports import Clock
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter, flush_to_disk, is_temporary_file_name
from digitalizadora.repositories.document_manifest_codec import decode_manifest, encode_manifest
from digitalizadora.repositories.output_folder_preparer import (
    WRITE_PROBE_FILE_PREFIX,
    prepare_output_folder,
    translate_storage_error,
)

LOGGER = logging.getLogger(__name__)

CURRENT_DRAFT_FOLDER_NAME = "current"
OWNER_LOCK_FILE_NAME = ".owner-lock"
OWNER_LOCK_OPEN_MODE = "a+b"
SET_ASIDE_FOLDER_PREFIX = "set-aside-"
SET_ASIDE_MOMENT_FORMAT = "%Y%m%d-%H%M%S"
SET_ASIDE_TOKEN_SIZE_IN_BYTES = 4
FILE_NAMES_THAT_ARE_NOT_FILES = frozenset({"", ".", ".."})


def _page_identifier_in(file_name: str, prefix: str) -> str | None:
    if not (file_name.startswith(prefix) and file_name.endswith(JPEG_FILE_SUFFIX)):
        return None
    candidate = file_name[len(prefix) : -len(JPEG_FILE_SUFFIX)]
    return candidate if is_page_identifier(candidate) else None


def _is_temporary_file_name(file_name: str) -> bool:
    return file_name.startswith(WRITE_PROBE_FILE_PREFIX) or is_temporary_file_name(file_name)


def _build_inventory(entries: Iterable[os.DirEntry]) -> DraftFileInventory:
    page_file_sizes: dict[str, int] = {}
    thumbnail_identifiers: set[str] = set()
    temporary_file_names: set[str] = set()
    unknown_file_names: set[str] = set()
    for entry in entries:
        if entry.name == MANIFEST_FILE_NAME:
            continue
        if not entry.is_file(follow_symlinks=False):
            unknown_file_names.add(entry.name)
        elif page_identifier := _page_identifier_in(entry.name, PAGE_FILE_PREFIX):
            try:
                page_file_sizes[page_identifier] = entry.stat(follow_symlinks=False).st_size
            except FileNotFoundError:  # vanished after the listing: a missing page, not a missing folder
                continue
        elif thumbnail_identifier := _page_identifier_in(entry.name, THUMBNAIL_FILE_PREFIX):
            thumbnail_identifiers.add(thumbnail_identifier)
        elif _is_temporary_file_name(entry.name):
            temporary_file_names.add(entry.name)
        else:
            unknown_file_names.add(entry.name)
    return DraftFileInventory(
        page_file_sizes=page_file_sizes,
        thumbnail_identifiers=frozenset(thumbnail_identifiers),
        temporary_file_names=frozenset(temporary_file_names),
        unknown_file_names=frozenset(unknown_file_names),
    )


def _plain_file_names(file_names: Iterable[str]) -> Iterator[str]:
    """Only simple names inside the draft folder: a separator, "." or ".." is refused with a warning."""
    for file_name in file_names:
        if file_name in FILE_NAMES_THAT_ARE_NOT_FILES or os.sep in file_name:
            LOGGER.warning("Refusing to touch %r: it is not a plain file name of the draft folder", file_name)
            continue
        yield file_name


def translate_draft_storage_error(error: OSError, description: str) -> DigitalizadoraError:
    """The draft lives on the internal disk: full disk → insufficient_draft_storage, anything else unavailable."""
    return as_draft_storage_error(translate_storage_error(error, description))


class FileSystemDocumentDraftRepository:
    def __init__(self, drafts_folder: Path, file_writer: AtomicFileWriter, clock: Clock) -> None:
        self._drafts_folder = drafts_folder
        self._draft_folder = drafts_folder / CURRENT_DRAFT_FOLDER_NAME
        self._file_writer = file_writer
        self._clock = clock
        self._owner_lock_file: BinaryIO | None = None

    def storage_folder(self) -> Path:
        return self._drafts_folder

    def claim_exclusive_access(self) -> None:
        """Takes the owner lock and keeps its file open while this repository exists (R12).

        The process that ends releases the lock, so a crash never leaves the folder locked.
        """
        if self._owner_lock_file is not None:
            return
        lock_path = self._drafts_folder / OWNER_LOCK_FILE_NAME
        try:
            self._drafts_folder.mkdir(parents=True, exist_ok=True)
            owner_lock_file = lock_path.open(OWNER_LOCK_OPEN_MODE)
        except OSError as error:
            raise translate_draft_storage_error(error, f"Cannot open {lock_path}") from error
        try:
            fcntl.flock(owner_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            owner_lock_file.close()
            raise DraftFolderInUseError(f"Another process already writes in {self._drafts_folder}") from error
        except OSError as error:
            owner_lock_file.close()
            raise translate_draft_storage_error(error, f"Cannot lock {lock_path}") from error
        self._owner_lock_file = owner_lock_file

    def ensure_storage_folder_ready(self) -> None:
        try:
            prepare_output_folder(self._drafts_folder)
        except DigitalizadoraError as error:
            raise as_draft_storage_error(error) from error

    def load_manifest(self) -> DocumentDraft | None:
        try:
            content = self._manifest_path().read_bytes()
        except FileNotFoundError:
            return None
        except OSError as error:
            raise translate_draft_storage_error(error, "Cannot read the draft manifest") from error
        return decode_manifest(content)

    def save_manifest(self, draft: DocumentDraft) -> None:
        try:
            self._file_writer.replace_file(self._manifest_path(), encode_manifest(draft))
        except OSError as error:
            raise translate_draft_storage_error(error, "Cannot save the draft manifest") from error

    def ensure_draft_folder_exists(self) -> None:
        try:
            self._draft_folder.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise translate_draft_storage_error(error, f"Cannot create {self._draft_folder}") from error

    def write_page_files(self, page_files: DocumentPageFiles) -> None:
        """The page first, then its thumbnail; a thumbnail that fails takes the new page away with it."""
        page_path = self.page_file_path(page_files.page_identifier)
        try:
            self._file_writer.write_new_file(page_path, page_files.jpeg_content)
        except OSError as error:
            raise translate_draft_storage_error(error, f"Cannot write {page_path.name}") from error
        thumbnail_path = self._thumbnail_path(page_files.page_identifier)
        try:
            self._file_writer.write_new_file(thumbnail_path, page_files.thumbnail_jpeg)
        except OSError as error:
            self._delete_quietly(page_path)
            raise translate_draft_storage_error(error, f"Cannot write {thumbnail_path.name}") from error

    def page_file_path(self, page_identifier: str) -> Path:
        return self._draft_folder / page_file_name(page_identifier)

    def page_file_size(self, page_identifier: str) -> int | None:
        page_path = self.page_file_path(page_identifier)
        try:
            return page_path.stat().st_size
        except FileNotFoundError:
            return None
        except OSError as error:
            raise translate_draft_storage_error(error, f"Cannot examine {page_path.name}") from error

    def read_page_file(self, page_identifier: str) -> bytes | None:
        """The whole page file, or None when it does not exist."""
        page_path = self.page_file_path(page_identifier)
        try:
            return page_path.read_bytes()
        except FileNotFoundError:
            return None
        except OSError as error:
            raise translate_draft_storage_error(error, f"Cannot read {page_path.name}") from error

    def read_thumbnail(self, page_identifier: str) -> bytes | None:
        if not is_page_identifier(page_identifier):
            return None
        thumbnail_path = self._thumbnail_path(page_identifier)
        try:
            return thumbnail_path.read_bytes()
        except FileNotFoundError:
            return None
        except OSError:
            LOGGER.warning("Could not read the thumbnail %s", thumbnail_path, exc_info=True)
            return None

    def delete_page_files(self, page_identifier: str) -> None:
        self._delete_quietly(self.page_file_path(page_identifier))
        self._delete_quietly(self._thumbnail_path(page_identifier))

    def finished_document_exists(self, finished_document_path: Path) -> bool:
        """Only a file confirmed now counts: a missing disk or a closed folder answers False (R15)."""
        try:
            return finished_document_path.is_file()
        except OSError:
            return False

    def _manifest_path(self) -> Path:
        return self._draft_folder / MANIFEST_FILE_NAME

    def _thumbnail_path(self, page_identifier: str) -> Path:
        return self._draft_folder / thumbnail_file_name(page_identifier)

    def _delete_quietly(self, file_path: Path) -> None:
        try:
            file_path.unlink(missing_ok=True)
        except OSError:
            LOGGER.warning("Could not delete %s", file_path)

    def take_inventory(self) -> DraftFileInventory:
        """Classifies the names in current/; a missing folder is an empty inventory."""
        try:
            directory = os.scandir(self._draft_folder)
        except FileNotFoundError:
            return _build_inventory([])
        except OSError as error:
            raise translate_draft_storage_error(error, f"Cannot list {self._draft_folder}") from error
        try:
            with directory as entries:
                return _build_inventory(entries)
        except OSError as error:
            raise translate_draft_storage_error(error, f"Cannot list {self._draft_folder}") from error

    def delete_files(self, file_names: Sequence[str]) -> None:
        for file_name in _plain_file_names(file_names):
            self._delete_quietly(self._draft_folder / file_name)

    def set_aside_files(self, file_names: Sequence[str]) -> Path:
        set_aside_folder = self._new_set_aside_folder()
        try:
            set_aside_folder.mkdir()
            for file_name in _plain_file_names(file_names):
                os.rename(self._draft_folder / file_name, set_aside_folder / file_name)
        except OSError as error:
            raise translate_draft_storage_error(error, f"Cannot set files aside in {set_aside_folder}") from error
        return set_aside_folder

    def set_aside_draft_folder(self) -> Path | None:
        set_aside_folder = self._new_set_aside_folder()
        try:
            os.rename(self._draft_folder, set_aside_folder)
        except FileNotFoundError:
            return None
        except OSError as error:
            raise translate_draft_storage_error(error, f"Cannot set {self._draft_folder} aside") from error
        return set_aside_folder

    def delete_draft(self) -> None:
        """The manifest first (a failure to delete it raises), then only the known files (R14)."""
        self._delete_manifest()
        try:
            known_file_names = self.take_inventory().known_file_names
        except DigitalizadoraError:
            LOGGER.warning("Could not list the draft folder after deleting its manifest", exc_info=True)
            return
        self.delete_files(known_file_names)
        self._remove_draft_folder_when_empty()

    def _delete_manifest(self) -> None:
        try:
            self._manifest_path().unlink(missing_ok=True)
        except OSError as error:
            raise translate_draft_storage_error(error, "Cannot delete the draft manifest") from error
        try:
            self._synchronise_draft_folder()
        except FileNotFoundError:
            return
        except OSError:
            LOGGER.warning("Could not synchronise %s after deleting its manifest", self._draft_folder, exc_info=True)

    def _synchronise_draft_folder(self) -> None:
        descriptor = os.open(self._draft_folder, os.O_RDONLY)
        try:
            flush_to_disk(descriptor)
        finally:
            os.close(descriptor)

    def _remove_draft_folder_when_empty(self) -> None:
        try:
            self._draft_folder.rmdir()
        except FileNotFoundError:
            return
        except OSError as error:
            if error.errno != errno.ENOTEMPTY:
                LOGGER.warning("Could not remove the empty draft folder %s: %s", self._draft_folder, error)

    def _new_set_aside_folder(self) -> Path:
        moment_text = self._clock.now().strftime(SET_ASIDE_MOMENT_FORMAT)
        token = secrets.token_hex(SET_ASIDE_TOKEN_SIZE_IN_BYTES)
        return self._drafts_folder / f"{SET_ASIDE_FOLDER_PREFIX}{moment_text}-{token}"

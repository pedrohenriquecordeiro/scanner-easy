import logging
import os
import secrets
from collections.abc import Iterator
from pathlib import Path

from digitalizadora.domain.errors import UnreadableQuickScanError
from digitalizadora.domain.ports import Clock
from digitalizadora.domain.quick_scan.last_scan import QuickScanMasterFiles, QuickScanSlot
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter, is_temporary_file_name
from digitalizadora.repositories.documents.file_system_document_draft_repository import translate_draft_storage_error
from digitalizadora.repositories.quick_scan.quick_scan_manifest_codec import (
    decode_quick_scan_manifest,
    encode_quick_scan_manifest,
)

LOGGER = logging.getLogger(__name__)

MANIFEST_FILE_NAME = "manifest.json"
MASTER_FILE_PREFIX = "master-"
THUMBNAIL_FILE_PREFIX = "thumbnail-"
JPEG_FILE_SUFFIX = ".jpg"
SET_ASIDE_FOLDER_PREFIX = "set-aside-"
SET_ASIDE_MOMENT_FORMAT = "%Y%m%d-%H%M%S"
SET_ASIDE_TOKEN_SIZE_IN_BYTES = 4


def _scan_identifier_of(file_name: str) -> str | None:
    """The scan a master or a thumbnail file belongs to; None for any other file."""
    for prefix in (MASTER_FILE_PREFIX, THUMBNAIL_FILE_PREFIX):
        if file_name.startswith(prefix) and file_name.endswith(JPEG_FILE_SUFFIX):
            return file_name[len(prefix) : -len(JPEG_FILE_SUFFIX)]
    return None


class FileSystemQuickScanSlotRepository:
    """The slot of the last quick scan on the internal disk: the master, its thumbnail and the manifest.

    The manifest is the commit point: it is written after the files it cites and the files of the previous scan are
    deleted only after it. Every file is written atomically, so a crash leaves either the old slot or the new one.
    """

    def __init__(self, slot_folder: Path, file_writer: AtomicFileWriter, clock: Clock) -> None:
        self._slot_folder = slot_folder
        self._file_writer = file_writer
        self._clock = clock

    def storage_folder(self) -> Path:
        return self._slot_folder

    def ensure_storage_folder_ready(self) -> None:
        try:
            self._slot_folder.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise translate_draft_storage_error(error, f"Cannot use {self._slot_folder}") from error

    def write_master_files(self, master_files: QuickScanMasterFiles) -> None:
        """The master first, then its thumbnail; neither is cited by a manifest until commit."""
        self.ensure_storage_folder_ready()
        scan_identifier = master_files.scan_identifier
        self._write_new_file(self.master_file_path(scan_identifier), master_files.master_jpeg)
        self._write_new_file(self._thumbnail_file_path(scan_identifier), master_files.thumbnail_jpeg)

    def master_file_path(self, scan_identifier: str) -> Path:
        return self._slot_folder / f"{MASTER_FILE_PREFIX}{scan_identifier}{JPEG_FILE_SUFFIX}"

    def read_thumbnail(self, scan_identifier: str) -> bytes | None:
        try:
            return self._thumbnail_file_path(scan_identifier).read_bytes()
        except FileNotFoundError:
            return None
        except OSError as error:
            raise translate_draft_storage_error(error, f"Cannot read the thumbnail of {scan_identifier}") from error

    def load(self) -> QuickScanSlot | None:
        """None when there is no slot; a slot that cannot be used is logged and set aside, and counts as none."""
        manifest_path = self._slot_folder / MANIFEST_FILE_NAME
        try:
            content = manifest_path.read_bytes()
        except FileNotFoundError:
            return None
        except OSError as error:
            return self._set_aside_slot(f"the manifest cannot be read: {error}")
        try:
            slot = decode_quick_scan_manifest(content)
        except UnreadableQuickScanError as error:
            return self._set_aside_slot(f"the manifest is unreadable: {error}")
        if not self._master_exists(slot.last_scan.scan_identifier):
            return self._set_aside_slot("the master of the last scan is missing")
        return slot

    def commit(self, slot: QuickScanSlot) -> None:
        """Makes the slot the one that counts, then deletes the files of every other scan."""
        manifest_path = self._slot_folder / MANIFEST_FILE_NAME
        try:
            self._file_writer.replace_file(manifest_path, encode_quick_scan_manifest(slot))
        except OSError as error:
            raise translate_draft_storage_error(error, f"Cannot write {manifest_path}") from error
        self.delete_leftovers(slot.last_scan.scan_identifier)

    def delete_leftovers(self, kept_scan_identifier: str | None) -> None:
        """Deletes the masters and thumbnails of other scans and the temporary files; best effort."""
        for entry in self._plain_files():
            scan_identifier = _scan_identifier_of(entry.name)
            is_leftover = is_temporary_file_name(entry.name) or (
                scan_identifier is not None and scan_identifier != kept_scan_identifier
            )
            if is_leftover:
                self._delete_quietly(Path(entry.path))

    def discard(self) -> None:
        """Forgets the slot: the manifest first, so nothing cites a file that is gone."""
        self._delete_quietly(self._slot_folder / MANIFEST_FILE_NAME)
        self.delete_leftovers(None)

    def _master_exists(self, scan_identifier: str) -> bool:
        try:
            return self.master_file_path(scan_identifier).stat().st_size > 0
        except OSError:
            return False

    def _thumbnail_file_path(self, scan_identifier: str) -> Path:
        return self._slot_folder / f"{THUMBNAIL_FILE_PREFIX}{scan_identifier}{JPEG_FILE_SUFFIX}"

    def _write_new_file(self, destination: Path, content: bytes) -> None:
        try:
            self._file_writer.write_new_file(destination, content)
        except OSError as error:
            raise translate_draft_storage_error(error, f"Cannot write {destination}") from error

    def _plain_files(self) -> Iterator[os.DirEntry]:
        try:
            entries = list(os.scandir(self._slot_folder))
        except OSError:
            return
        yield from (entry for entry in entries if entry.is_file(follow_symlinks=False))

    def _delete_quietly(self, path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            LOGGER.warning("Could not delete %s from the slot of the last scan", path)

    def _set_aside_slot(self, reason: str) -> None:
        """Moves the files of the slot into a folder of their own, so the panel starts empty and nothing is lost."""
        moment = self._clock.now().strftime(SET_ASIDE_MOMENT_FORMAT)
        token = secrets.token_hex(SET_ASIDE_TOKEN_SIZE_IN_BYTES)
        aside_folder = self._slot_folder / f"{SET_ASIDE_FOLDER_PREFIX}{moment}-{token}"
        LOGGER.warning("The slot of the last scan is set aside in %s: %s", aside_folder, reason)
        try:
            aside_folder.mkdir(parents=True)
            for entry in self._plain_files():
                os.replace(entry.path, aside_folder / entry.name)
        except OSError:
            LOGGER.warning("Could not set the slot of the last scan aside", exc_info=True)
        return None

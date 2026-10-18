from collections.abc import Mapping
from dataclasses import dataclass, replace

from digitalizadora.domain.document_draft import FIRST_PAGE_POSITION, DocumentDraft

MANIFEST_FILE_NAME = "manifest.json"
PAGE_FILE_PREFIX = "page-"
THUMBNAIL_FILE_PREFIX = "thumbnail-"
JPEG_FILE_SUFFIX = ".jpg"


def page_file_name(page_identifier: str) -> str:
    return f"{PAGE_FILE_PREFIX}{page_identifier}{JPEG_FILE_SUFFIX}"


def thumbnail_file_name(page_identifier: str) -> str:
    return f"{THUMBNAIL_FILE_PREFIX}{page_identifier}{JPEG_FILE_SUFFIX}"


@dataclass(frozen=True)
class DraftFileInventory:
    """What the draft folder holds, already classified by file name (manifest.json excluded)."""

    page_file_sizes: Mapping[str, int]
    thumbnail_identifiers: frozenset[str]
    temporary_file_names: frozenset[str]
    unknown_file_names: frozenset[str]

    @property
    def known_file_names(self) -> tuple[str, ...]:
        page_file_names = [page_file_name(page_identifier) for page_identifier in self.page_file_sizes]
        thumbnail_file_names = [thumbnail_file_name(page_identifier) for page_identifier in self.thumbnail_identifiers]
        return tuple(sorted([*page_file_names, *thumbnail_file_names, *self.temporary_file_names]))


@dataclass(frozen=True)
class DraftReconciliation:
    draft: DocumentDraft
    dropped_page_positions: tuple[int, ...]
    files_to_set_aside: tuple[str, ...]
    files_to_delete: tuple[str, ...]


def reconcile_draft(draft: DocumentDraft, inventory: DraftFileInventory) -> DraftReconciliation:
    """Keeps only the pages whose file has the size the manifest recorded.

    A confirmed page with another size is set aside, never deleted; files that were never confirmed are
    deleted; unknown names are left alone.
    """
    kept_pages = []
    dropped_page_positions = []
    files_to_set_aside = []
    dropped_identifiers = set()
    for position, page in enumerate(draft.pages, FIRST_PAGE_POSITION):
        file_size = inventory.page_file_sizes.get(page.page_identifier)
        if file_size == page.size_in_bytes:
            kept_pages.append(page)
            continue
        dropped_page_positions.append(position)
        dropped_identifiers.add(page.page_identifier)
        if file_size is not None:
            files_to_set_aside.append(page_file_name(page.page_identifier))
    listed_identifiers = set(draft.page_identifiers)
    unlisted_page_files = [
        page_file_name(page_identifier)
        for page_identifier in inventory.page_file_sizes
        if page_identifier not in listed_identifiers
    ]
    discarded_thumbnails = [
        thumbnail_file_name(page_identifier)
        for page_identifier in inventory.thumbnail_identifiers
        if page_identifier not in listed_identifiers or page_identifier in dropped_identifiers
    ]
    return DraftReconciliation(
        draft=replace(draft, pages=tuple(kept_pages)),
        dropped_page_positions=tuple(dropped_page_positions),
        files_to_set_aside=tuple(sorted(files_to_set_aside)),
        files_to_delete=tuple(sorted([*inventory.temporary_file_names, *unlisted_page_files, *discarded_thumbnails])),
    )

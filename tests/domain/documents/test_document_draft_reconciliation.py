from dataclasses import replace
from datetime import timedelta

import pytest

from digitalizadora.domain.documents.document_draft import DocumentDraft
from digitalizadora.domain.documents.document_draft_reconciliation import (
    DraftFileInventory,
    page_file_name,
    reconcile_draft,
    thumbnail_file_name,
)
from tests.fakes.document_drafts import DEFAULT_PAGE_SIZE_IN_BYTES, DRAFT_CREATED_AT, build_document_draft

FIRST = "0000000000000001"
SECOND = "0000000000000002"
THIRD = "0000000000000003"
ORPHAN = "00000000000000aa"
TEMPORARY_FILE_NAME = f".page-{ORPHAN}.jpg.4242-1a2b3c4d.part"


def build_inventory(
    page_file_sizes: dict[str, int], thumbnail_identifiers: set[str], other_file_names: tuple[str, ...] = ()
) -> DraftFileInventory:
    return DraftFileInventory(
        page_file_sizes=page_file_sizes,
        thumbnail_identifiers=frozenset(thumbnail_identifiers),
        temporary_file_names=frozenset(name for name in other_file_names if name.endswith(".part")),
        unknown_file_names=frozenset(name for name in other_file_names if not name.endswith(".part")),
    )


def complete_inventory(page_identifiers: tuple[str, ...]) -> DraftFileInventory:
    return build_inventory(
        {page_identifier: DEFAULT_PAGE_SIZE_IN_BYTES for page_identifier in page_identifiers}, set(page_identifiers)
    )


@pytest.fixture
def draft() -> DocumentDraft:
    return build_document_draft(3)


def test_page_file_name_follows_the_documented_pattern() -> None:
    assert page_file_name("3f9c0a1b2c3d4e5f") == "page-3f9c0a1b2c3d4e5f.jpg"


def test_thumbnail_file_name_follows_the_documented_pattern() -> None:
    assert thumbnail_file_name("3f9c0a1b2c3d4e5f") == "thumbnail-3f9c0a1b2c3d4e5f.jpg"


def test_known_file_names_are_pages_thumbnails_and_temporaries_in_alphabetical_order() -> None:
    inventory = build_inventory({SECOND: 3, FIRST: 3}, {FIRST}, (TEMPORARY_FILE_NAME, ".DS_Store"))

    assert inventory.known_file_names == (
        TEMPORARY_FILE_NAME,
        f"page-{FIRST}.jpg",
        f"page-{SECOND}.jpg",
        f"thumbnail-{FIRST}.jpg",
    )


def test_complete_folder_keeps_the_draft_unchanged(draft: DocumentDraft) -> None:
    reconciliation = reconcile_draft(draft, complete_inventory(draft.page_identifiers))

    assert reconciliation.draft == draft


def test_complete_folder_has_nothing_to_drop_move_or_delete(draft: DocumentDraft) -> None:
    reconciliation = reconcile_draft(draft, complete_inventory(draft.page_identifiers))

    assert (
        reconciliation.dropped_page_positions,
        reconciliation.files_to_set_aside,
        reconciliation.files_to_delete,
    ) == ((), (), ())


def test_page_without_file_is_dropped(draft: DocumentDraft) -> None:
    inventory = build_inventory({FIRST: 3, THIRD: 3}, {FIRST, THIRD})

    assert reconcile_draft(draft, inventory).draft.page_identifiers == (FIRST, THIRD)


def test_page_without_file_is_reported_by_its_manifest_position(draft: DocumentDraft) -> None:
    inventory = build_inventory({FIRST: 3, THIRD: 3}, {FIRST, THIRD})

    assert reconcile_draft(draft, inventory).dropped_page_positions == (2,)


def test_page_with_another_size_is_dropped(draft: DocumentDraft) -> None:
    inventory = build_inventory({FIRST: 3, SECOND: 2, THIRD: 3}, {FIRST, SECOND, THIRD})

    assert reconcile_draft(draft, inventory).dropped_page_positions == (2,)


def test_page_with_another_size_is_set_aside(draft: DocumentDraft) -> None:
    inventory = build_inventory({FIRST: 3, SECOND: 2, THIRD: 3}, {FIRST, SECOND, THIRD})

    assert reconcile_draft(draft, inventory).files_to_set_aside == (f"page-{SECOND}.jpg",)


def test_page_with_another_size_is_never_deleted(draft: DocumentDraft) -> None:
    inventory = build_inventory({FIRST: 3, SECOND: 2, THIRD: 3}, {FIRST, SECOND, THIRD})

    assert f"page-{SECOND}.jpg" not in reconcile_draft(draft, inventory).files_to_delete


def test_page_and_thumbnail_outside_the_manifest_are_deleted(draft: DocumentDraft) -> None:
    inventory = build_inventory({FIRST: 3, SECOND: 3, THIRD: 3, ORPHAN: 3}, {FIRST, SECOND, THIRD, ORPHAN})

    assert reconcile_draft(draft, inventory).files_to_delete == (f"page-{ORPHAN}.jpg", f"thumbnail-{ORPHAN}.jpg")


def test_temporary_file_is_deleted(draft: DocumentDraft) -> None:
    inventory = build_inventory({FIRST: 3, SECOND: 3, THIRD: 3}, {FIRST, SECOND, THIRD}, (TEMPORARY_FILE_NAME,))

    assert reconcile_draft(draft, inventory).files_to_delete == (TEMPORARY_FILE_NAME,)


def test_thumbnail_of_a_dropped_page_is_deleted(draft: DocumentDraft) -> None:
    inventory = build_inventory({FIRST: 3, THIRD: 3}, {FIRST, SECOND, THIRD})

    assert reconcile_draft(draft, inventory).files_to_delete == (f"thumbnail-{SECOND}.jpg",)


def test_missing_thumbnail_does_not_drop_the_page(draft: DocumentDraft) -> None:
    inventory = build_inventory({FIRST: 3, SECOND: 3, THIRD: 3}, {FIRST, THIRD})

    assert reconcile_draft(draft, inventory).draft == draft


def test_unknown_file_is_neither_deleted_nor_set_aside(draft: DocumentDraft) -> None:
    inventory = build_inventory({FIRST: 3, SECOND: 2, THIRD: 3}, {FIRST, SECOND, THIRD}, (".DS_Store",))

    reconciliation = reconcile_draft(draft, inventory)

    assert ".DS_Store" not in (*reconciliation.files_to_delete, *reconciliation.files_to_set_aside)


def test_kept_pages_follow_the_manifest_order() -> None:
    draft = build_document_draft(3).reordered([THIRD, FIRST, SECOND])
    inventory = build_inventory({FIRST: 3, SECOND: 3}, {FIRST, SECOND})

    assert reconcile_draft(draft, inventory).draft.page_identifiers == (FIRST, SECOND)


def test_name_and_markers_pass_unchanged(draft: DocumentDraft) -> None:
    marked_draft = replace(
        draft.renamed("Contrato"), finalization_started_at=DRAFT_CREATED_AT + timedelta(minutes=5)
    )
    inventory = build_inventory({FIRST: 3}, {FIRST})

    kept_draft = reconcile_draft(marked_draft, inventory).draft

    assert (kept_draft.name, kept_draft.finalization_started_at) == ("Contrato", marked_draft.finalization_started_at)


def test_no_page_with_a_file_keeps_no_page(draft: DocumentDraft) -> None:
    reconciliation = reconcile_draft(draft, build_inventory({}, set()))

    assert (reconciliation.draft.pages, reconciliation.dropped_page_positions) == ((), (1, 2, 3))


def test_files_to_delete_come_in_alphabetical_order(draft: DocumentDraft) -> None:
    inventory = build_inventory({FIRST: 3, THIRD: 3, ORPHAN: 3}, {FIRST, SECOND, THIRD}, (TEMPORARY_FILE_NAME,))

    assert reconcile_draft(draft, inventory).files_to_delete == (
        TEMPORARY_FILE_NAME,
        f"page-{ORPHAN}.jpg",
        f"thumbnail-{SECOND}.jpg",
    )

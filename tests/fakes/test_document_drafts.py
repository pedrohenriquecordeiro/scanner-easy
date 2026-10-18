from digitalizadora.domain.documents.document_draft import DocumentDraft, is_page_identifier
from tests.fakes.document_drafts import (
    DEFAULT_PAGE_SIZE_IN_BYTES,
    DRAFT_CREATED_AT,
    build_document_draft,
    build_document_page,
    page_identifier_at,
)


def test_build_document_page_uses_the_given_identifier() -> None:
    assert build_document_page("00000000000000aa").page_identifier == "00000000000000aa"


def test_build_document_page_uses_the_given_size() -> None:
    assert build_document_page("00000000000000aa", size_in_bytes=806123).size_in_bytes == 806123


def test_build_document_page_has_a_small_default_size() -> None:
    assert build_document_page("00000000000000aa").size_in_bytes == DEFAULT_PAGE_SIZE_IN_BYTES


def test_page_identifier_at_is_a_valid_identifier() -> None:
    assert is_page_identifier(page_identifier_at(12))


def test_build_document_draft_numbers_the_pages_in_order() -> None:
    draft = build_document_draft(3)

    assert draft.page_identifiers == ("0000000000000001", "0000000000000002", "0000000000000003")


def test_build_document_draft_has_no_name_and_no_markers() -> None:
    draft = build_document_draft(2)

    assert draft == DocumentDraft(name="", created_at=DRAFT_CREATED_AT, pages=draft.pages)


def test_build_document_draft_accepts_zero_pages() -> None:
    assert build_document_draft(0).pages == ()

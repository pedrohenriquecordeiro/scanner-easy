import dataclasses
import re
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import pytest

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.document_draft import (
    DocumentDraft,
    DocumentFinalizationResult,
    DocumentPage,
    DocumentPageFiles,
    DraftRecoveryReport,
    DraftSnapshot,
    RecoveryOutcome,
    generate_draft_session,
    generate_page_identifier,
    is_page_identifier,
)
from digitalizadora.domain.errors import EmptyDocumentError, InvalidPageOrderError, PageNotFoundError
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.page_framing import UNFRAMED, PageFraming
from digitalizadora.domain.page_rotation import PageRotation
from digitalizadora.domain.scan_result import ScanResult
from tests.fakes.document_drafts import DRAFT_CREATED_AT, build_document_draft, build_document_page
from tests.fakes.page_crops import rectangle

FIRST = "0000000000000001"
SECOND = "0000000000000002"
THIRD = "0000000000000003"
UNKNOWN = "00000000000000ff"
LATER_PAGE = DocumentPage(
    page_identifier="a07e5c9d11f04b2e",
    scanned_at=DRAFT_CREATED_AT + timedelta(seconds=41),
    dots_per_inch=600,
    color_mode=ColorMode.GRAYSCALE,
    size_in_bytes=806123,
)
FINALIZATION_STARTED_AT = DRAFT_CREATED_AT + timedelta(minutes=5)
FINISHED_DOCUMENT = ScanResult(
    output_path=Path("/Volumes/Arquivo/Contrato do apartamento.pdf"),
    output_format=OutputFormat.PDF,
    scanned_at=FINALIZATION_STARTED_AT,
    size_in_bytes=1612800,
)


@pytest.fixture
def draft() -> DocumentDraft:
    return build_document_draft(3)


@pytest.fixture
def marked_draft(draft: DocumentDraft) -> DocumentDraft:
    return draft.with_finalization_started(FINALIZATION_STARTED_AT).marked_finished(FINISHED_DOCUMENT)


def test_start_uses_the_time_of_the_first_page() -> None:
    assert DocumentDraft.start(LATER_PAGE).created_at == LATER_PAGE.scanned_at


def test_start_has_no_name() -> None:
    assert DocumentDraft.start(LATER_PAGE).name == ""


def test_start_holds_only_the_first_page() -> None:
    assert DocumentDraft.start(LATER_PAGE).pages == (LATER_PAGE,)


def test_start_has_no_markers() -> None:
    started = DocumentDraft.start(LATER_PAGE)

    assert (started.finalization_started_at, started.finished_document) == (None, None)


def test_page_count_counts_the_pages(draft: DocumentDraft) -> None:
    assert draft.page_count == 3


def test_estimated_size_is_the_sum_of_the_page_sizes() -> None:
    draft = DocumentDraft.start(build_document_page(FIRST, 806123)).with_page_appended(
        build_document_page(SECOND, 4)
    )

    assert draft.estimated_size_in_bytes == 806127


def test_appending_keeps_the_order(draft: DocumentDraft) -> None:
    assert draft.with_page_appended(LATER_PAGE).page_identifiers == (FIRST, SECOND, THIRD, LATER_PAGE.page_identifier)


@pytest.mark.parametrize(("page_identifier", "expected_position"), [(FIRST, 1), (SECOND, 2), (THIRD, 3)])
def test_position_of_counts_from_one(draft: DocumentDraft, page_identifier: str, expected_position: int) -> None:
    assert draft.position_of(page_identifier) == expected_position


def test_position_of_an_unknown_page_raises(draft: DocumentDraft) -> None:
    with pytest.raises(PageNotFoundError):
        draft.position_of(UNKNOWN)


@pytest.mark.parametrize(
    ("removed_identifier", "expected_order"),
    [(FIRST, (SECOND, THIRD)), (SECOND, (FIRST, THIRD)), (THIRD, (FIRST, SECOND))],
    ids=["first", "middle", "last"],
)
def test_without_page_removes_only_that_page(
    draft: DocumentDraft, removed_identifier: str, expected_order: tuple[str, ...]
) -> None:
    assert draft.without_page(removed_identifier).page_identifiers == expected_order


def test_without_page_of_an_unknown_page_raises(draft: DocumentDraft) -> None:
    with pytest.raises(PageNotFoundError):
        draft.without_page(UNKNOWN)


def test_without_page_of_the_only_page_leaves_no_pages() -> None:
    assert build_document_draft(1).without_page(FIRST).pages == ()


def test_without_last_page_removes_the_last_page(draft: DocumentDraft) -> None:
    assert draft.without_last_page().page_identifiers == (FIRST, SECOND)


def test_without_last_page_of_an_empty_draft_raises() -> None:
    with pytest.raises(EmptyDocumentError):
        build_document_draft(0).without_last_page()


def test_reordered_follows_the_given_permutation(draft: DocumentDraft) -> None:
    assert draft.reordered([THIRD, FIRST, SECOND]).page_identifiers == (THIRD, FIRST, SECOND)


def test_reordered_accepts_the_current_order(draft: DocumentDraft) -> None:
    assert draft.reordered([FIRST, SECOND, THIRD]).page_identifiers == (FIRST, SECOND, THIRD)


def test_reordered_keeps_the_page_details(draft: DocumentDraft) -> None:
    assert set(draft.reordered([SECOND, THIRD, FIRST]).pages) == set(draft.pages)


@pytest.mark.parametrize(
    "requested_order",
    [
        [],
        [FIRST, SECOND, THIRD, UNKNOWN],
        [FIRST, SECOND],
        [FIRST, FIRST, SECOND],
        [FIRST, SECOND, UNKNOWN],
        [FIRST, SECOND, 3],
        [FIRST, SECOND, [THIRD]],
    ],
    ids=["empty", "one-more", "one-less", "repeated", "unknown", "number", "list"],
)
def test_reordered_refuses_anything_but_an_exact_permutation(draft: DocumentDraft, requested_order: list) -> None:
    with pytest.raises(InvalidPageOrderError):
        draft.reordered(requested_order)


def test_renamed_sets_the_name(draft: DocumentDraft) -> None:
    assert draft.renamed("Contrato do apartamento").name == "Contrato do apartamento"


def test_renamed_keeps_the_pages(draft: DocumentDraft) -> None:
    assert draft.renamed("Contrato do apartamento").pages == draft.pages


def test_with_finalization_started_sets_the_intention_marker(draft: DocumentDraft) -> None:
    assert draft.with_finalization_started(FINALIZATION_STARTED_AT).finalization_started_at == FINALIZATION_STARTED_AT


def test_marked_finished_sets_the_finished_document(draft: DocumentDraft) -> None:
    assert draft.marked_finished(FINISHED_DOCUMENT).finished_document == FINISHED_DOCUMENT


def test_marked_finished_keeps_the_intention_marker(marked_draft: DocumentDraft) -> None:
    assert marked_draft.finalization_started_at == FINALIZATION_STARTED_AT


def test_without_finalization_marker_removes_the_intention_marker(marked_draft: DocumentDraft) -> None:
    assert marked_draft.without_finalization_marker().finalization_started_at is None


def test_without_finalization_marker_keeps_the_finished_document(marked_draft: DocumentDraft) -> None:
    assert marked_draft.without_finalization_marker().finished_document == FINISHED_DOCUMENT


CONTENT_CHANGES: dict[str, Callable[[DocumentDraft], DocumentDraft]] = {
    "append": lambda draft: draft.with_page_appended(LATER_PAGE),
    "delete": lambda draft: draft.without_page(SECOND),
    "discard-last": lambda draft: draft.without_last_page(),
    "reorder": lambda draft: draft.reordered([THIRD, SECOND, FIRST]),
    "rename": lambda draft: draft.renamed("Notas fiscais"),
}


@pytest.mark.parametrize("change", CONTENT_CHANGES.values(), ids=CONTENT_CHANGES.keys())
def test_content_change_removes_both_markers(
    marked_draft: DocumentDraft, change: Callable[[DocumentDraft], DocumentDraft]
) -> None:
    changed = change(marked_draft)

    assert (changed.finalization_started_at, changed.finished_document) == (None, None)


@pytest.mark.parametrize("change", CONTENT_CHANGES.values(), ids=CONTENT_CHANGES.keys())
def test_content_change_keeps_the_creation_time(
    marked_draft: DocumentDraft, change: Callable[[DocumentDraft], DocumentDraft]
) -> None:
    assert change(marked_draft).created_at == DRAFT_CREATED_AT


@pytest.mark.parametrize("change", CONTENT_CHANGES.values(), ids=CONTENT_CHANGES.keys())
def test_content_change_leaves_the_original_draft_untouched(
    marked_draft: DocumentDraft, change: Callable[[DocumentDraft], DocumentDraft]
) -> None:
    original = dataclasses.replace(marked_draft)

    change(marked_draft)

    assert marked_draft == original


IMMUTABLE_MODELS = [
    build_document_page(FIRST),
    DocumentPageFiles(page_identifier=FIRST, jpeg_content=b"\xff\xd8", thumbnail_jpeg=b"\xff\xd8"),
    build_document_draft(1),
    DocumentFinalizationResult(result=FINISHED_DOCUMENT, page_count=3),
    DraftRecoveryReport(RecoveryOutcome.RESUMED, 2, (3,), None),
    DraftSnapshot(draft_session="5c0f9a2e7b1d4c38", revision=0, draft=None),
]


@pytest.mark.parametrize("model", IMMUTABLE_MODELS, ids=lambda model: type(model).__name__)
def test_document_model_is_immutable(model: object) -> None:
    first_field_name = dataclasses.fields(model)[0].name

    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(model, first_field_name, None)


def test_draft_snapshot_starts_without_report_and_finished_document() -> None:
    snapshot = DraftSnapshot(draft_session="5c0f9a2e7b1d4c38", revision=0, draft=None)

    assert (snapshot.recovery_report, snapshot.last_finished_document) == (None, None)


@pytest.mark.parametrize(
    ("outcome", "expected_value"),
    [
        (RecoveryOutcome.RESUMED, "resumed"),
        (RecoveryOutcome.PAGES_LOST, "pages_lost"),
        (RecoveryOutcome.SET_ASIDE, "set_aside"),
        (RecoveryOutcome.FAILED, "failed"),
    ],
)
def test_recovery_outcome_has_the_json_value(outcome: RecoveryOutcome, expected_value: str) -> None:
    assert outcome.value == expected_value


def test_is_page_identifier_accepts_sixteen_lowercase_hexadecimal_digits() -> None:
    assert is_page_identifier("3f9c0a1b2c3d4e5f")


@pytest.mark.parametrize(
    "text",
    ["3f9c0a1b2c3d4e5", "3f9c0a1b2c3d4e5f0", "3F9C0A1B2C3D4E5F", "last", "../x", "", "3f9c0a1b2c3d4e5f\n"],
    ids=["fifteen", "seventeen", "uppercase", "last", "parent-path", "empty", "trailing-newline"],
)
def test_is_page_identifier_refuses_other_text(text: str) -> None:
    assert not is_page_identifier(text)


def test_is_page_identifier_refuses_a_value_that_is_not_text() -> None:
    assert not is_page_identifier(3)


def test_generate_page_identifier_returns_a_valid_identifier() -> None:
    assert is_page_identifier(generate_page_identifier())


def test_generate_draft_session_returns_sixteen_lowercase_hexadecimal_digits() -> None:
    assert re.fullmatch(r"[0-9a-f]{16}", generate_draft_session()) is not None


FRAMING = PageFraming(rotation=PageRotation.CLOCKWISE_90, crops=(rectangle((0.1, 0.2, 0.5, 0.9)),))


def test_a_page_starts_unframed() -> None:
    assert build_document_page(FIRST).framing == UNFRAMED


def test_with_page_framing_sets_the_framing_of_that_page_only(draft: DocumentDraft) -> None:
    framed_draft = draft.with_page_framing(SECOND, FRAMING)

    assert [page.framing for page in framed_draft.pages] == [UNFRAMED, FRAMING, UNFRAMED]


def test_with_page_framing_keeps_the_position(draft: DocumentDraft) -> None:
    assert draft.with_page_framing(SECOND, FRAMING).page_identifiers == draft.page_identifiers


def test_with_page_framing_keeps_the_other_details_of_the_page(draft: DocumentDraft) -> None:
    framed_page = draft.with_page_framing(SECOND, FRAMING).pages[1]

    assert dataclasses.replace(framed_page, framing=UNFRAMED) == draft.pages[1]


def test_with_page_framing_of_an_unknown_page_raises(draft: DocumentDraft) -> None:
    with pytest.raises(PageNotFoundError):
        draft.with_page_framing(UNKNOWN, FRAMING)


def test_with_page_framing_clears_both_finalization_markers(marked_draft: DocumentDraft) -> None:
    framed_draft = marked_draft.with_page_framing(FIRST, FRAMING)

    assert (framed_draft.finalization_started_at, framed_draft.finished_document) == (None, None)


def test_with_page_framing_keeps_the_name_and_creation_moment(draft: DocumentDraft) -> None:
    named_draft = draft.renamed("Contrato").with_page_framing(FIRST, FRAMING)

    assert (named_draft.name, named_draft.created_at) == ("Contrato", draft.created_at)


TWO_PHOTOS = PageFraming(crops=(rectangle((0.05, 0.1, 0.45, 0.9)), rectangle((0.55, 0.1, 0.95, 0.9))))


def test_a_draft_without_crops_has_as_many_output_pages_as_pages(draft: DocumentDraft) -> None:
    assert draft.output_page_count == 3


def test_a_page_with_two_crops_gives_two_output_pages(draft: DocumentDraft) -> None:
    assert draft.with_page_framing(SECOND, TWO_PHOTOS).output_page_count == 4


def test_a_page_with_one_crop_gives_one_output_page(draft: DocumentDraft) -> None:
    assert draft.with_page_framing(SECOND, FRAMING).output_page_count == 3


def test_the_estimated_document_size_counts_a_page_without_framing_once() -> None:
    assert build_document_draft(2).estimate_document_size_in_bytes(100) == 2 * build_document_page(FIRST).size_in_bytes


def test_the_estimated_document_size_doubles_a_page_that_needs_rendering_at_the_default_quality() -> None:
    plain_draft = build_document_draft(2)
    framed_draft = plain_draft.with_page_framing(FIRST, FRAMING)
    page_size = plain_draft.pages[0].size_in_bytes

    assert framed_draft.estimate_document_size_in_bytes(90) == 3 * page_size


def test_the_estimated_document_size_quadruples_a_page_that_needs_rendering_at_the_top_quality() -> None:
    plain_draft = build_document_draft(2)
    framed_draft = plain_draft.with_page_framing(FIRST, FRAMING)
    page_size = plain_draft.pages[0].size_in_bytes

    assert framed_draft.estimate_document_size_in_bytes(100) == 5 * page_size


def test_the_estimated_size_of_the_draft_on_disk_ignores_the_framing(draft: DocumentDraft) -> None:
    assert draft.with_page_framing(FIRST, FRAMING).estimated_size_in_bytes == draft.estimated_size_in_bytes

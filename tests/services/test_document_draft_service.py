import dataclasses
import threading
from datetime import timedelta
from pathlib import Path

import pikepdf
import pytest
from PIL import Image

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.document_draft import DocumentFinalizationResult, DocumentPage, DraftSnapshot
from digitalizadora.domain.document_draft_reconciliation import (
    MANIFEST_FILE_NAME,
    page_file_name,
    thumbnail_file_name,
)
from digitalizadora.domain.errors import (
    DamagedDocumentPageError,
    DocumentAssemblyFailedError,
    DraftStorageUnavailableError,
    EmptyDocumentError,
    NoOpenDocumentError,
    OutputFolderUnavailableError,
    PageNotFoundError,
)
from digitalizadora.domain.image_adjustment import NO_ADJUSTMENT, ImageAdjustment
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.page_rotation import PageRotation
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.services.document_draft_service import DocumentDraftService
from digitalizadora.services.document_draft_store import DraftStorageState
from digitalizadora.services.storage_guard_service import MINIMUM_FREE_SPACE_BYTES, estimated_page_bytes
from tests.fakes.document_drafts import DRAFT_CREATED_AT, build_document_draft, build_document_page, page_identifier_at
from tests.fakes.document_service_parts import (
    DRAFT_SESSION,
    PLENTY_OF_FREE_SPACE_IN_BYTES,
    DocumentServiceParts,
    build_document_service_parts,
)
from tests.fakes.page_crops import rectangle
from tests.fakes.recording_free_space_reader import RecordingFreeSpaceReader
from tests.fakes.sample_images import build_sample_jpeg
from tests.fakes.synthetic_scans import read_jpeg_size

JPEG_QUALITY = 90
WHOLE_PAGE_CROP = rectangle((0.0, 0.0, 1.0, 1.0))

SETTINGS = ScanPreset.DOCUMENT.settings
PHOTO_SETTINGS = ScanPreset.PHOTO.settings
FIRST_PAGE_IDENTIFIER = page_identifier_at(1)
SECOND_PAGE_IDENTIFIER = page_identifier_at(2)
JPEG_START_OF_IMAGE = b"\xff\xd8"
UNKNOWN_PAGE_IDENTIFIER = "00000000000000ff"


def read_page_size(page_path: Path) -> tuple[int, int]:
    with Image.open(page_path) as image:
        return image.size


class StubDraftStore:
    """Duck-typed stand-in for DocumentDraftStore: answers a fixed snapshot and counts recover()."""

    def __init__(self, draft_snapshot: DraftSnapshot) -> None:
        self._draft_snapshot = draft_snapshot
        self.recover_calls = 0

    def snapshot(self) -> DraftSnapshot:
        return self._draft_snapshot

    def recover(self) -> None:
        self.recover_calls += 1


@pytest.fixture
def parts(tmp_path: Path) -> DocumentServiceParts:
    return build_document_service_parts(tmp_path, RecordingFreeSpaceReader(PLENTY_OF_FREE_SPACE_IN_BYTES))


@pytest.fixture
def service(parts: DocumentServiceParts) -> DocumentDraftService:
    return parts.document_draft_service


def build_service_with_store(parts: DocumentServiceParts, draft_store: StubDraftStore) -> DocumentDraftService:
    collaborators = dataclasses.replace(parts.collaborators, draft_store=draft_store)
    return DocumentDraftService(parts.scan_service, collaborators, parts.clock)


async def add_pages(service: DocumentDraftService, page_count: int) -> None:
    for _ in range(page_count):
        await service.add_page(SETTINGS)


def test_snapshot_starts_in_the_session_without_a_draft(service):
    assert service.snapshot() == DraftSnapshot(draft_session=DRAFT_SESSION, revision=0, draft=None)


def test_recover_draft_asks_the_store_to_recover(parts):
    draft_store = StubDraftStore(DraftSnapshot(draft_session=DRAFT_SESSION, revision=0, draft=None))

    build_service_with_store(parts, draft_store).recover_draft()

    assert draft_store.recover_calls == 1


def test_describe_draft_storage_reports_the_space_of_the_drafts_disk(service):
    expected_pages_remaining = (PLENTY_OF_FREE_SPACE_IN_BYTES - MINIMUM_FREE_SPACE_BYTES) // estimated_page_bytes(
        SETTINGS
    )

    assert service.describe_draft_storage(SETTINGS) == DraftStorageState(
        free_space_in_bytes=PLENTY_OF_FREE_SPACE_IN_BYTES,
        estimated_pages_remaining=expected_pages_remaining,
        available=True,
    )


async def test_add_page_appends_the_scanned_page_to_the_draft(service):
    await service.add_page(SETTINGS)

    assert service.snapshot().draft.page_identifiers == (FIRST_PAGE_IDENTIFIER,)


async def test_add_page_returns_the_page_with_the_given_settings(service):
    page = await service.add_page(PHOTO_SETTINGS)

    assert (page.dots_per_inch, page.color_mode) == (600, ColorMode.COLOR)


async def test_add_page_asks_the_printer_for_the_given_settings(service, parts):
    await service.add_page(PHOTO_SETTINGS)

    assert parts.gateway.scan_requests == [PHOTO_SETTINGS]


async def test_add_page_keeps_the_page_as_a_jpeg(service, parts):
    await service.add_page(SETTINGS)

    page_file = parts.draft_folder / page_file_name(FIRST_PAGE_IDENTIFIER)
    assert page_file.read_bytes()[: len(JPEG_START_OF_IMAGE)] == JPEG_START_OF_IMAGE


async def test_rename_returns_the_draft_with_the_clean_name(service):
    await add_pages(service, 1)

    renamed_draft = await service.rename("  Notas fiscais 2026/10  ")

    assert renamed_draft.name == "Notas fiscais 2026-10"


async def test_reorder_returns_the_draft_in_the_new_order(service):
    await add_pages(service, 2)

    reordered_draft = await service.reorder([SECOND_PAGE_IDENTIFIER, FIRST_PAGE_IDENTIFIER])

    assert reordered_draft.page_identifiers == (SECOND_PAGE_IDENTIFIER, FIRST_PAGE_IDENTIFIER)


async def test_delete_page_returns_the_draft_without_the_page(service):
    await add_pages(service, 2)

    remaining_draft = await service.delete_page(FIRST_PAGE_IDENTIFIER)

    assert remaining_draft.page_identifiers == (SECOND_PAGE_IDENTIFIER,)


async def test_deleting_the_only_page_ends_the_draft(service):
    await add_pages(service, 1)

    assert await service.delete_page(FIRST_PAGE_IDENTIFIER) is None


async def test_discard_last_page_returns_the_draft_without_the_last_page(service):
    await add_pages(service, 2)

    remaining_draft = await service.discard_last_page()

    assert remaining_draft.page_identifiers == (FIRST_PAGE_IDENTIFIER,)


async def test_cancel_ends_the_draft(service):
    await add_pages(service, 1)

    await service.cancel()

    assert service.snapshot().draft is None


async def test_read_thumbnail_returns_the_thumbnail_of_the_page(service, parts):
    await add_pages(service, 1)

    thumbnail_jpeg = service.read_thumbnail(FIRST_PAGE_IDENTIFIER, PageRotation.NONE)

    assert thumbnail_jpeg == (parts.draft_folder / thumbnail_file_name(FIRST_PAGE_IDENTIFIER)).read_bytes()


async def test_read_thumbnail_with_a_rotation_turns_the_thumbnail(service):
    await add_pages(service, 1)
    unturned_size = read_jpeg_size(service.read_thumbnail(FIRST_PAGE_IDENTIFIER, PageRotation.NONE))

    turned_thumbnail = service.read_thumbnail(FIRST_PAGE_IDENTIFIER, PageRotation.CLOCKWISE_90)

    assert read_jpeg_size(turned_thumbnail) == unturned_size[::-1]


async def test_read_thumbnail_of_an_unknown_page_is_none(service):
    await add_pages(service, 1)

    assert service.read_thumbnail(UNKNOWN_PAGE_IDENTIFIER, PageRotation.NONE) is None


async def test_read_preview_gives_the_stored_page_as_it_is_displayed(service, parts):
    await add_pages(service, 1)
    page_size = read_page_size(parts.draft_folder / page_file_name(FIRST_PAGE_IDENTIFIER))

    preview = service.read_preview(FIRST_PAGE_IDENTIFIER, PageRotation.HALF_TURN)

    assert read_jpeg_size(preview) == page_size


async def test_read_preview_of_an_unknown_page_raises_page_not_found(service):
    await add_pages(service, 1)

    with pytest.raises(PageNotFoundError):
        service.read_preview(UNKNOWN_PAGE_IDENTIFIER, PageRotation.NONE)


async def test_read_preview_without_a_draft_raises_no_open_document(service):
    with pytest.raises(NoOpenDocumentError):
        service.read_preview(FIRST_PAGE_IDENTIFIER, PageRotation.NONE)


async def test_an_edit_saves_the_manifest_in_a_worker_thread(service, parts):
    await add_pages(service, 1)

    await service.rename("Contrato")

    assert parts.draft_repository.manifest_thread_identifiers[-1] != threading.get_ident()


async def test_an_edit_error_reaches_the_caller(service):
    with pytest.raises(NoOpenDocumentError):
        await service.rename("Contrato")


FINALIZATION_DELAY_SECONDS = 300
FINALIZED_AT = DRAFT_CREATED_AT + timedelta(seconds=FINALIZATION_DELAY_SECONDS)
DOCUMENT_NAME = "Contrato do apartamento"
DOCUMENT_FILE_NAME = "Contrato do apartamento.pdf"
POINT_TOLERANCE = 0.01
WIDE_SCANNED_PAGE = ScannedImage(
    content=build_sample_jpeg(width_pixels=600, height_pixels=150), media_type="image/jpeg"
)
NARROW_SCANNED_PAGE = ScannedImage(
    content=build_sample_jpeg(width_pixels=300, height_pixels=150), media_type="image/jpeg"
)

WIDE_PAGE_WIDTH_AT_300_IN_POINTS = 144.0
NARROW_PAGE_WIDTH_AT_300_IN_POINTS = 72.0
NARROW_PAGE_WIDTH_AT_600_IN_POINTS = 36.0
DRAFT_DISK_FAILURE = DraftStorageUnavailableError("the internal disk stopped answering")


def read_page_widths(pdf_path: Path) -> list[float]:
    with pikepdf.open(pdf_path) as pdf:
        return [float(pdf_page.mediabox[2]) for pdf_page in pdf.pages]


async def finalize_later(parts: DocumentServiceParts) -> DocumentFinalizationResult:
    parts.clock.advance(FINALIZATION_DELAY_SECONDS)
    return await parts.document_draft_service.finalize(JPEG_QUALITY)


async def finalize_leaving_the_draft_marked(parts: DocumentServiceParts) -> DocumentFinalizationResult:
    """A finalization whose PDF exists but whose cleanup failed: the draft stays in memory, marked finished."""
    await add_pages(parts.document_draft_service, 1)
    parts.draft_repository.deletion_failure = DRAFT_DISK_FAILURE
    finalization = await finalize_later(parts)
    parts.draft_repository.deletion_failure = None
    return finalization


async def test_finalize_writes_the_pages_in_the_order_of_the_draft(tmp_path):
    parts = build_document_service_parts(
        tmp_path, RecordingFreeSpaceReader(PLENTY_OF_FREE_SPACE_IN_BYTES), [WIDE_SCANNED_PAGE, NARROW_SCANNED_PAGE]
    )
    await add_pages(parts.document_draft_service, 2)

    finalization = await finalize_later(parts)

    assert read_page_widths(finalization.result.output_path) == pytest.approx(
        [WIDE_PAGE_WIDTH_AT_300_IN_POINTS, NARROW_PAGE_WIDTH_AT_300_IN_POINTS], abs=POINT_TOLERANCE
    )


async def test_page_scanned_with_a_newer_preset_keeps_its_own_density(tmp_path):
    parts = build_document_service_parts(
        tmp_path, RecordingFreeSpaceReader(PLENTY_OF_FREE_SPACE_IN_BYTES), [NARROW_SCANNED_PAGE, NARROW_SCANNED_PAGE]
    )
    await parts.document_draft_service.add_page(SETTINGS)
    await parts.document_draft_service.add_page(PHOTO_SETTINGS)

    finalization = await finalize_later(parts)

    assert read_page_widths(finalization.result.output_path) == pytest.approx(
        [NARROW_PAGE_WIDTH_AT_300_IN_POINTS, NARROW_PAGE_WIDTH_AT_600_IN_POINTS], abs=POINT_TOLERANCE
    )


async def test_finalize_returns_the_page_count(service, parts):
    await add_pages(service, 2)

    finalization = await finalize_later(parts)

    assert finalization.page_count == 2


async def test_finalize_writes_the_pdf_dated_at_the_finalization_moment(service, parts):
    await add_pages(service, 1)

    finalization = await finalize_later(parts)

    assert finalization.result.scanned_at == FINALIZED_AT


async def test_finalize_deletes_the_draft_manifest(service, parts):
    await add_pages(service, 1)

    await finalize_later(parts)

    assert not (parts.draft_folder / MANIFEST_FILE_NAME).exists()


async def test_finalize_leaves_no_draft_in_the_snapshot(service, parts):
    await add_pages(service, 1)

    await finalize_later(parts)

    assert service.snapshot().draft is None


async def test_finalize_leaves_the_finalization_in_the_snapshot(service, parts):
    await add_pages(service, 1)

    finalization = await finalize_later(parts)

    assert service.snapshot().last_finished_document == finalization


async def test_finalize_saves_the_pdf_under_the_chosen_name(service, parts):
    await add_pages(service, 1)
    await service.rename(DOCUMENT_NAME)

    finalization = await finalize_later(parts)

    assert finalization.result.output_path == parts.output_folder / DOCUMENT_FILE_NAME


async def test_finalize_with_the_chosen_name_taken_adds_a_number(service, parts):
    parts.output_folder.mkdir()
    (parts.output_folder / DOCUMENT_FILE_NAME).write_bytes(b"an older document")
    await add_pages(service, 1)
    await service.rename(DOCUMENT_NAME)

    finalization = await finalize_later(parts)

    assert finalization.result.output_path.name == "Contrato do apartamento (2).pdf"


async def test_finalize_assembles_the_pdf_in_a_worker_thread(service, parts):
    await add_pages(service, 1)

    await finalize_later(parts)

    assert parts.pdf_assembly_service.assembly_thread_identifiers[0] != threading.get_ident()


async def test_finalize_without_a_draft_raises_no_open_document(service):
    with pytest.raises(NoOpenDocumentError):
        await service.finalize(JPEG_QUALITY)


async def test_finalize_of_a_draft_without_pages_raises_empty_document(parts):
    draft_store = StubDraftStore(
        DraftSnapshot(draft_session=DRAFT_SESSION, revision=1, draft=build_document_draft(page_count=0))
    )

    with pytest.raises(EmptyDocumentError):
        await build_service_with_store(parts, draft_store).finalize(JPEG_QUALITY)


async def test_unusable_output_folder_keeps_the_draft(service, parts):
    await add_pages(service, 1)
    draft_before = service.snapshot().draft
    parts.output_folder.write_bytes(b"a file where the folder should be")

    with pytest.raises(OutputFolderUnavailableError):
        await finalize_later(parts)

    assert service.snapshot().draft == draft_before


async def test_unusable_output_folder_leaves_no_intention_marker(service, parts):
    await add_pages(service, 1)
    parts.output_folder.write_bytes(b"a file where the folder should be")

    with pytest.raises(OutputFolderUnavailableError):
        await finalize_later(parts)

    assert parts.read_manifest_on_disk().finalization_started_at is None


async def test_damaged_page_raises_damaged_document_page_with_its_position(service, parts):
    await add_pages(service, 2)
    (parts.draft_folder / page_file_name(SECOND_PAGE_IDENTIFIER)).unlink()

    with pytest.raises(DamagedDocumentPageError) as raised:
        await finalize_later(parts)

    assert (raised.value.page_identifier, raised.value.page_position) == (SECOND_PAGE_IDENTIFIER, 2)


async def test_damaged_page_keeps_the_draft(service, parts):
    await add_pages(service, 2)
    draft_before = service.snapshot().draft
    (parts.draft_folder / page_file_name(SECOND_PAGE_IDENTIFIER)).unlink()

    with pytest.raises(DamagedDocumentPageError):
        await finalize_later(parts)

    assert service.snapshot().draft == draft_before


async def test_damaged_page_leaves_no_intention_marker(service, parts):
    await add_pages(service, 1)
    (parts.draft_folder / page_file_name(FIRST_PAGE_IDENTIFIER)).write_bytes(b"short")

    with pytest.raises(DamagedDocumentPageError):
        await finalize_later(parts)

    assert parts.read_manifest_on_disk().finalization_started_at is None


async def test_intention_marker_is_on_disk_while_the_pdf_is_written(service, parts):
    await add_pages(service, 1)

    await finalize_later(parts)

    assert parts.pdf_assembly_service.manifests_during_assembly[0].finalization_started_at == FINALIZED_AT


def replace_page_with_garbage_of_the_same_size(parts: DocumentServiceParts, page_identifier: str) -> None:
    page_file = parts.draft_folder / page_file_name(page_identifier)
    page_file.write_bytes(b"x" * page_file.stat().st_size)


async def test_failed_assembly_clears_the_intention_marker(service, parts):
    await add_pages(service, 1)
    replace_page_with_garbage_of_the_same_size(parts, FIRST_PAGE_IDENTIFIER)

    with pytest.raises(DocumentAssemblyFailedError):
        await finalize_later(parts)

    assert parts.read_manifest_on_disk().finalization_started_at is None


async def test_failed_assembly_keeps_the_draft(service, parts):
    await add_pages(service, 1)
    draft_before = service.snapshot().draft
    replace_page_with_garbage_of_the_same_size(parts, FIRST_PAGE_IDENTIFIER)

    with pytest.raises(DocumentAssemblyFailedError):
        await finalize_later(parts)

    assert service.snapshot().draft == draft_before


async def test_failed_finished_mark_still_deletes_the_draft(service, parts):
    await add_pages(service, 1)
    parts.draft_repository.finished_mark_failure = DRAFT_DISK_FAILURE

    await finalize_later(parts)

    assert service.snapshot().draft is None


async def test_failed_finished_mark_and_cleanup_keep_the_draft_marked_finished(service, parts):
    await add_pages(service, 1)
    parts.draft_repository.finished_mark_failure = DRAFT_DISK_FAILURE
    parts.draft_repository.deletion_failure = DRAFT_DISK_FAILURE

    finalization = await finalize_later(parts)

    assert service.snapshot().draft.finished_document == finalization.result


async def test_finalize_again_with_the_mark_and_the_pdf_writes_no_other_pdf(service, parts):
    first_finalization = await finalize_leaving_the_draft_marked(parts)

    await service.finalize(JPEG_QUALITY)

    assert list(parts.output_folder.iterdir()) == [first_finalization.result.output_path]


async def test_finalize_again_with_the_mark_and_the_pdf_returns_the_first_finalization(service, parts):
    first_finalization = await finalize_leaving_the_draft_marked(parts)

    assert await service.finalize(JPEG_QUALITY) == first_finalization


async def test_finalize_again_with_the_mark_and_the_pdf_deletes_the_draft(service, parts):
    await finalize_leaving_the_draft_marked(parts)

    await service.finalize(JPEG_QUALITY)

    assert service.snapshot().draft is None


async def test_finalize_again_with_the_mark_but_without_the_pdf_writes_a_new_pdf(service, parts):
    first_finalization = await finalize_leaving_the_draft_marked(parts)
    first_finalization.result.output_path.unlink()

    second_finalization = await service.finalize(JPEG_QUALITY)

    assert second_finalization.result.output_path.is_file()


class RecordingPageScanner:
    def __init__(self) -> None:
        self.requests: list[ScanRequest] = []

    async def __call__(self, request: ScanRequest) -> DocumentPage:
        self.requests.append(request)
        return build_document_page(FIRST_PAGE_IDENTIFIER)


async def test_add_page_passes_the_adjustment_to_the_page_scanner(parts):
    page_scanner = RecordingPageScanner()
    collaborators = dataclasses.replace(parts.collaborators, page_scanner=page_scanner)
    adjustment = ImageAdjustment(auto_crop=True)

    await DocumentDraftService(parts.scan_service, collaborators, parts.clock).add_page(SETTINGS, adjustment)

    assert page_scanner.requests == [ScanRequest(SETTINGS, OutputFormat.JPEG, adjustment)]


async def test_add_page_without_adjustment_asks_for_no_adjustment(parts):
    page_scanner = RecordingPageScanner()
    collaborators = dataclasses.replace(parts.collaborators, page_scanner=page_scanner)

    await DocumentDraftService(parts.scan_service, collaborators, parts.clock).add_page(SETTINGS)

    assert page_scanner.requests[0].adjustment == NO_ADJUSTMENT


def test_describe_draft_storage_estimates_the_pages_by_the_quality_alone(service, parts):
    storage = service.describe_draft_storage(SETTINGS)

    assert storage.estimated_pages_remaining == (
        (PLENTY_OF_FREE_SPACE_IN_BYTES - MINIMUM_FREE_SPACE_BYTES) // estimated_page_bytes(SETTINGS)
    )


async def test_rotate_page_keeps_the_identifier_and_the_position(service):
    await add_pages(service, 2)

    draft = await service.rotate_page(FIRST_PAGE_IDENTIFIER)

    assert draft.page_identifiers == (FIRST_PAGE_IDENTIFIER, SECOND_PAGE_IDENTIFIER)


async def test_rotate_page_turns_the_page_a_quarter_clockwise(service):
    await add_pages(service, 2)

    draft = await service.rotate_page(FIRST_PAGE_IDENTIFIER)

    assert draft.pages[0].framing.rotation is PageRotation.CLOCKWISE_90


async def test_rotate_page_replaces_the_snapshot(service):
    await add_pages(service, 2)

    draft = await service.rotate_page(FIRST_PAGE_IDENTIFIER)

    assert service.snapshot().draft == draft


async def test_rotate_page_raises_the_revision(service):
    await add_pages(service, 1)
    revision_before = service.snapshot().revision

    await service.rotate_page(FIRST_PAGE_IDENTIFIER)

    assert service.snapshot().revision == revision_before + 1


async def test_rotate_page_leaves_the_stored_page_as_the_scanner_made_it(service, parts):
    await add_pages(service, 1)
    page_file = parts.draft_folder / page_file_name(FIRST_PAGE_IDENTIFIER)
    page_bytes_before = page_file.read_bytes()

    await service.rotate_page(FIRST_PAGE_IDENTIFIER)

    assert page_file.read_bytes() == page_bytes_before


async def test_rotate_page_of_an_unknown_page_raises_page_not_found(service):
    await add_pages(service, 1)

    with pytest.raises(PageNotFoundError):
        await service.rotate_page(UNKNOWN_PAGE_IDENTIFIER)


async def test_rotate_page_without_a_draft_raises_no_open_document(service):
    with pytest.raises(NoOpenDocumentError):
        await service.rotate_page(FIRST_PAGE_IDENTIFIER)


SAMPLE_CROP = rectangle((0.125, 0.115, 0.9, 0.925))


async def test_set_page_crop_stores_the_crop_in_the_page(service):
    await add_pages(service, 2)

    draft = await service.set_page_crops(SECOND_PAGE_IDENTIFIER, [SAMPLE_CROP])

    assert [page.framing.crops for page in draft.pages] == [(), (SAMPLE_CROP,)]


async def test_set_page_crop_replaces_the_snapshot_and_raises_the_revision(service):
    await add_pages(service, 1)
    revision_before = service.snapshot().revision

    draft = await service.set_page_crops(FIRST_PAGE_IDENTIFIER, [SAMPLE_CROP])

    assert (service.snapshot().draft, service.snapshot().revision) == (draft, revision_before + 1)


async def test_set_page_crop_to_the_same_crop_keeps_the_revision(service):
    await add_pages(service, 1)
    await service.set_page_crops(FIRST_PAGE_IDENTIFIER, [SAMPLE_CROP])
    revision_before = service.snapshot().revision

    await service.set_page_crops(FIRST_PAGE_IDENTIFIER, [SAMPLE_CROP])

    assert service.snapshot().revision == revision_before


async def test_set_page_crop_to_the_whole_page_removes_the_crop(service):
    await add_pages(service, 1)
    await service.set_page_crops(FIRST_PAGE_IDENTIFIER, [SAMPLE_CROP])

    draft = await service.set_page_crops(FIRST_PAGE_IDENTIFIER, [WHOLE_PAGE_CROP])

    assert draft.pages[0].framing.crops == ()


async def test_set_page_crop_is_saved_in_the_manifest_on_disk(service, parts):
    await add_pages(service, 1)

    await service.set_page_crops(FIRST_PAGE_IDENTIFIER, [SAMPLE_CROP])

    assert parts.read_manifest_on_disk().pages[0].framing.crops == (SAMPLE_CROP,)


async def test_set_page_crop_leaves_the_stored_page_as_the_scanner_made_it(service, parts):
    await add_pages(service, 1)
    page_file = parts.draft_folder / page_file_name(FIRST_PAGE_IDENTIFIER)
    page_bytes_before = page_file.read_bytes()

    await service.set_page_crops(FIRST_PAGE_IDENTIFIER, [SAMPLE_CROP])

    assert page_file.read_bytes() == page_bytes_before


async def test_set_page_crop_of_an_unknown_page_raises_page_not_found(service):
    await add_pages(service, 1)

    with pytest.raises(PageNotFoundError):
        await service.set_page_crops(UNKNOWN_PAGE_IDENTIFIER, [SAMPLE_CROP])


async def test_set_page_crop_without_a_draft_raises_no_open_document(service):
    with pytest.raises(NoOpenDocumentError):
        await service.set_page_crops(FIRST_PAGE_IDENTIFIER, [SAMPLE_CROP])


async def test_an_edit_of_the_framing_removes_the_finalization_marks(service, parts):
    await add_pages(service, 1)
    await service.rotate_page(FIRST_PAGE_IDENTIFIER)

    manifest = parts.read_manifest_on_disk()

    assert (manifest.finalization_started_at, manifest.finished_document) == (None, None)


def read_pdf_media_box(pdf_path: Path) -> list[float]:
    with pikepdf.open(pdf_path) as document:
        return [float(value) for value in document.pages[0].mediabox]


async def test_a_rotated_page_goes_into_the_saved_pdf_with_its_new_orientation(service, parts):
    await add_pages(service, 1)
    page_size = read_page_size(parts.draft_folder / page_file_name(FIRST_PAGE_IDENTIFIER))
    await service.rotate_page(FIRST_PAGE_IDENTIFIER)

    finalization = await service.finalize(JPEG_QUALITY)

    media_box = read_pdf_media_box(finalization.result.output_path)
    assert (media_box[2] > media_box[3]) is (page_size[1] > page_size[0])


async def test_a_cropped_page_goes_into_the_saved_pdf_with_the_size_of_its_frame(service, parts):
    await add_pages(service, 1)
    page_width, page_height = read_page_size(parts.draft_folder / page_file_name(FIRST_PAGE_IDENTIFIER))
    await service.set_page_crops(FIRST_PAGE_IDENTIFIER, [rectangle((0.0, 0.0, 0.5, 1.0))])

    finalization = await service.finalize(JPEG_QUALITY)

    media_box = read_pdf_media_box(finalization.result.output_path)
    assert media_box[2] / media_box[3] == pytest.approx(page_width / 2 / page_height, rel=0.1)


async def test_detect_page_crop_on_a_white_page_finds_nothing_and_changes_nothing(service):
    await add_pages(service, 1)
    revision_before = service.snapshot().revision

    result = await service.detect_page_crops(FIRST_PAGE_IDENTIFIER)

    assert (result.crops_detected, service.snapshot().revision) == (False, revision_before)


async def test_detect_page_crop_of_an_unknown_page_raises_page_not_found(service):
    await add_pages(service, 1)

    with pytest.raises(PageNotFoundError):
        await service.detect_page_crops(UNKNOWN_PAGE_IDENTIFIER)


async def test_detect_page_crop_without_a_draft_raises_no_open_document(service):
    with pytest.raises(NoOpenDocumentError):
        await service.detect_page_crops(FIRST_PAGE_IDENTIFIER)

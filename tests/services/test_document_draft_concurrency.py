import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest

from digitalizadora.domain.document_draft import DocumentFinalizationResult, DocumentPage
from digitalizadora.domain.errors import (
    DocumentBusyError,
    InsufficientStorageError,
    ScanAlreadyRunningError,
)
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.page_rotation import PageRotation
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.services.document_draft_service import DocumentDraftService
from tests.fakes.blocking_free_space_reader import BlockingFreeSpaceReader
from tests.fakes.document_drafts import page_identifier_at
from tests.fakes.document_service_parts import (
    PLENTY_OF_FREE_SPACE_IN_BYTES,
    DocumentServiceParts,
    build_document_service_parts,
)
from tests.fakes.recording_free_space_reader import RecordingFreeSpaceReader

JPEG_QUALITY = 90
SETTINGS = ScanPreset.DOCUMENT.settings
QUICK_SCAN_REQUEST = ScanRequest(settings=SETTINGS, output_format=OutputFormat.PDF)
FIRST_PAGE_IDENTIFIER = page_identifier_at(1)
SECOND_PAGE_IDENTIFIER = page_identifier_at(2)
JPEG_START_OF_IMAGE = b"\xff\xd8"
# A finalization held by the reader then fails for lack of space, so the draft is still there afterwards.
NO_FREE_SPACE_IN_BYTES = 0

EDITS: dict[str, Callable[[DocumentDraftService], Awaitable[object]]] = {
    "rename": lambda service: service.rename("Contrato"),
    "reorder": lambda service: service.reorder([FIRST_PAGE_IDENTIFIER]),
    "delete_page": lambda service: service.delete_page(FIRST_PAGE_IDENTIFIER),
    "rotate_page": lambda service: service.rotate_page(FIRST_PAGE_IDENTIFIER),
    "set_page_crop": lambda service: service.set_page_crops(FIRST_PAGE_IDENTIFIER, []),
    "detect_page_crop": lambda service: service.detect_page_crops(FIRST_PAGE_IDENTIFIER),
    "discard_last_page": lambda service: service.discard_last_page(),
    "cancel": lambda service: service.cancel(),
    "finalize": lambda service: service.finalize(JPEG_QUALITY),
}


@pytest.fixture
def parts(tmp_path: Path) -> DocumentServiceParts:
    return build_document_service_parts(tmp_path, RecordingFreeSpaceReader(PLENTY_OF_FREE_SPACE_IN_BYTES))


@pytest.fixture
def service(parts: DocumentServiceParts) -> DocumentDraftService:
    return parts.document_draft_service


@pytest.fixture
def blocking_reader() -> BlockingFreeSpaceReader:
    return BlockingFreeSpaceReader(NO_FREE_SPACE_IN_BYTES)


@pytest.fixture
def held_parts(tmp_path: Path, blocking_reader: BlockingFreeSpaceReader) -> DocumentServiceParts:
    return build_document_service_parts(tmp_path, blocking_reader)


async def start_held_page(parts: DocumentServiceParts) -> "asyncio.Task[DocumentPage]":
    """A page whose scan stays open on the glass until gateway.release_scan is set."""
    parts.gateway.hold_scans_open()
    page_task = asyncio.create_task(parts.document_draft_service.add_page(SETTINGS))
    await parts.gateway.scan_started.wait()
    return page_task


async def finish_held_page(parts: DocumentServiceParts, page_task: "asyncio.Task[DocumentPage]") -> None:
    parts.gateway.release_scan.set()
    await page_task


async def start_held_finalization(
    parts: DocumentServiceParts, blocking_reader: BlockingFreeSpaceReader
) -> "asyncio.Task[DocumentFinalizationResult]":
    """A draft of two pages whose finalization holds the lock until blocking_reader.release()."""
    await parts.document_draft_service.add_page(SETTINGS)
    await parts.document_draft_service.add_page(SETTINGS)
    finalization_task = asyncio.create_task(parts.document_draft_service.finalize(JPEG_QUALITY))
    await asyncio.to_thread(blocking_reader.entered.wait)
    return finalization_task


async def finish_held_finalization(
    blocking_reader: BlockingFreeSpaceReader, finalization_task: "asyncio.Task[DocumentFinalizationResult]"
) -> None:
    blocking_reader.release()
    with pytest.raises(InsufficientStorageError):
        await finalization_task


async def start_held_quick_scan(parts: DocumentServiceParts) -> "asyncio.Task[ScanResult]":
    parts.gateway.hold_scans_open()
    quick_scan_task = asyncio.create_task(parts.scan_service.scan_one_file(QUICK_SCAN_REQUEST))
    await parts.gateway.scan_started.wait()
    return quick_scan_task


@pytest.mark.parametrize("edit_name", list(EDITS))
async def test_edit_during_a_page_scan_raises_scan_already_running(parts, service, edit_name):
    page_task = await start_held_page(parts)

    with pytest.raises(ScanAlreadyRunningError):
        await EDITS[edit_name](service)

    await finish_held_page(parts, page_task)


async def test_second_page_during_a_page_scan_raises_scan_already_running(parts, service):
    page_task = await start_held_page(parts)

    with pytest.raises(ScanAlreadyRunningError):
        await service.add_page(SETTINGS)

    await finish_held_page(parts, page_task)


async def test_second_page_during_a_page_scan_never_reaches_the_printer(parts, service):
    page_task = await start_held_page(parts)
    with pytest.raises(ScanAlreadyRunningError):
        await service.add_page(SETTINGS)

    await finish_held_page(parts, page_task)

    assert parts.gateway.scan_requests == [SETTINGS]


async def test_ensure_can_add_page_during_a_page_scan_raises_scan_already_running(parts, service):
    page_task = await start_held_page(parts)

    with pytest.raises(ScanAlreadyRunningError):
        service.ensure_can_add_page()

    await finish_held_page(parts, page_task)


async def test_quick_scan_during_a_page_scan_raises_scan_already_running(parts):
    page_task = await start_held_page(parts)

    with pytest.raises(ScanAlreadyRunningError):
        await parts.scan_service.scan_one_file(QUICK_SCAN_REQUEST)

    await finish_held_page(parts, page_task)


async def test_two_pages_requested_before_either_runs_refuse_the_second(service):
    first_page_task = asyncio.create_task(service.add_page(SETTINGS))
    second_page_task = asyncio.create_task(service.add_page(SETTINGS))

    outcomes = await asyncio.gather(first_page_task, second_page_task, return_exceptions=True)

    assert isinstance(outcomes[1], ScanAlreadyRunningError)


async def test_two_pages_requested_before_either_runs_scan_once(parts, service):
    first_page_task = asyncio.create_task(service.add_page(SETTINGS))
    second_page_task = asyncio.create_task(service.add_page(SETTINGS))

    await asyncio.gather(first_page_task, second_page_task, return_exceptions=True)

    assert parts.gateway.scan_requests == [SETTINGS]


async def test_page_during_a_finalization_raises_document_busy(held_parts, blocking_reader):
    finalization_task = await start_held_finalization(held_parts, blocking_reader)

    with pytest.raises(DocumentBusyError):
        await held_parts.document_draft_service.add_page(SETTINGS)

    await finish_held_finalization(blocking_reader, finalization_task)


async def test_page_refused_during_a_finalization_never_reaches_the_printer(held_parts, blocking_reader):
    finalization_task = await start_held_finalization(held_parts, blocking_reader)
    with pytest.raises(DocumentBusyError):
        await held_parts.document_draft_service.add_page(SETTINGS)

    await finish_held_finalization(blocking_reader, finalization_task)

    assert held_parts.gateway.scan_requests == [SETTINGS, SETTINGS]


async def test_ensure_can_add_page_during_a_finalization_raises_document_busy(held_parts, blocking_reader):
    finalization_task = await start_held_finalization(held_parts, blocking_reader)

    with pytest.raises(DocumentBusyError):
        held_parts.document_draft_service.ensure_can_add_page()

    await finish_held_finalization(blocking_reader, finalization_task)


async def test_snapshot_is_read_while_a_finalization_holds_the_lock(held_parts, blocking_reader):
    finalization_task = await start_held_finalization(held_parts, blocking_reader)

    page_count = held_parts.document_draft_service.snapshot().draft.page_count

    await finish_held_finalization(blocking_reader, finalization_task)
    assert page_count == 2


async def test_thumbnail_and_preview_are_read_while_a_finalization_holds_the_lock(held_parts, blocking_reader):
    service = held_parts.document_draft_service
    finalization_task = await start_held_finalization(held_parts, blocking_reader)

    thumbnail = service.read_thumbnail(FIRST_PAGE_IDENTIFIER, PageRotation.CLOCKWISE_90)
    preview = service.read_preview(SECOND_PAGE_IDENTIFIER, PageRotation.NONE)

    await finish_held_finalization(blocking_reader, finalization_task)
    assert (thumbnail.startswith(JPEG_START_OF_IMAGE), preview.startswith(JPEG_START_OF_IMAGE)) == (True, True)


async def test_edits_queued_behind_a_finalization_run_in_order_after_it(held_parts, blocking_reader):
    service = held_parts.document_draft_service
    finalization_task = await start_held_finalization(held_parts, blocking_reader)
    rename_task = asyncio.create_task(service.rename("Contrato"))
    reorder_task = asyncio.create_task(service.reorder([SECOND_PAGE_IDENTIFIER, FIRST_PAGE_IDENTIFIER]))
    await asyncio.sleep(0)

    await finish_held_finalization(blocking_reader, finalization_task)
    renamed_draft, reordered_draft = await asyncio.gather(rename_task, reorder_task)

    assert (renamed_draft.page_identifiers, reordered_draft.name) == (
        (FIRST_PAGE_IDENTIFIER, SECOND_PAGE_IDENTIFIER),
        "Contrato",
    )


async def test_edit_that_waited_for_the_lock_and_found_a_quick_scan_raises_scan_already_running(
    held_parts, blocking_reader
):
    finalization_task = await start_held_finalization(held_parts, blocking_reader)
    rename_task = asyncio.create_task(held_parts.document_draft_service.rename("Contrato"))
    await asyncio.sleep(0)
    quick_scan_task = await start_held_quick_scan(held_parts)

    await finish_held_finalization(blocking_reader, finalization_task)

    with pytest.raises(ScanAlreadyRunningError):
        await rename_task
    held_parts.gateway.release_scan.set()
    await quick_scan_task


async def test_ensure_can_add_page_while_an_edit_waits_for_a_released_lock_raises_document_busy(
    held_parts, blocking_reader
):

    service = held_parts.document_draft_service
    finalization_task = await start_held_finalization(held_parts, blocking_reader)
    rename_task = asyncio.create_task(service.rename("Contrato"))
    await asyncio.sleep(0)
    blocking_reader.release()
    while not finalization_task.done():
        await asyncio.sleep(0)

    with pytest.raises(DocumentBusyError):
        service.ensure_can_add_page()

    await rename_task
    with pytest.raises(InsufficientStorageError):
        await finalization_task

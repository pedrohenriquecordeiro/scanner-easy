import io
from dataclasses import replace
from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog
from digitalizadora.controllers.preview_controller import PreviewController
from digitalizadora.domain.last_scan import QuickScanMasterFiles
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.page_framing import PageFraming
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter
from digitalizadora.repositories.file_system_quick_scan_slot_repository import FileSystemQuickScanSlotRepository
from digitalizadora.services.last_scan_view_service import LastScanViewService
from digitalizadora.services.page_image_view_service import PageImageViewService
from digitalizadora.services.scan_progress_tracker import ScanProgressTracker
from tests.controllers.controller_test_support import SCANNED_AT, build_test_client
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.sample_images import build_sample_jpeg
from tests.fakes.stored_scans import build_stored_scan

SCAN_REQUEST = ScanRequest(settings=ScanPreset.DOCUMENT.settings, output_format=OutputFormat.PDF)


@pytest.fixture
def progress_tracker() -> ScanProgressTracker:
    return ScanProgressTracker(FixedClock(SCANNED_AT))


@pytest.fixture
def slot_repository(tmp_path: Path) -> FileSystemQuickScanSlotRepository:
    return FileSystemQuickScanSlotRepository(tmp_path / "quick-scan", AtomicFileWriter(), FixedClock(SCANNED_AT))


@pytest.fixture
def client(
    progress_tracker: ScanProgressTracker, slot_repository: FileSystemQuickScanSlotRepository
) -> TestClient:
    view_service = LastScanViewService(progress_tracker, slot_repository, PageImageViewService())
    return build_test_client(PreviewController(view_service, ErrorMessageCatalog()).build_router())


def test_thumbnail_is_404_before_the_first_scan(client: TestClient) -> None:
    response = client.get("/api/scans/last/thumbnail")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_thumbnail_is_served_as_jpeg_after_a_scan(
    client: TestClient, progress_tracker: ScanProgressTracker
) -> None:
    thumbnail_jpeg = build_sample_jpeg()
    progress_tracker.begin_scan(SCAN_REQUEST)
    progress_tracker.mark_completed(build_stored_scan(thumbnail_jpeg))

    response = client.get("/api/scans/last/thumbnail")

    assert (response.status_code, response.headers["content-type"], response.content) == (
        HTTPStatus.OK,
        "image/jpeg",
        thumbnail_jpeg,
    )


def test_thumbnail_is_never_cached_by_the_browser(
    client: TestClient, progress_tracker: ScanProgressTracker
) -> None:
    progress_tracker.begin_scan(SCAN_REQUEST)
    progress_tracker.mark_completed(build_stored_scan(build_sample_jpeg()))

    response = client.get("/api/scans/last/thumbnail")

    assert response.headers["cache-control"] == "no-store"


def test_thumbnail_stays_available_after_a_later_failure(
    client: TestClient, progress_tracker: ScanProgressTracker
) -> None:
    thumbnail_jpeg = build_sample_jpeg()
    progress_tracker.begin_scan(SCAN_REQUEST)
    progress_tracker.mark_completed(build_stored_scan(thumbnail_jpeg))
    progress_tracker.begin_scan(SCAN_REQUEST)
    progress_tracker.mark_failed("scan_failed")

    response = client.get("/api/scans/last/thumbnail")

    assert response.content == thumbnail_jpeg


def keep_a_master(
    slot_repository: FileSystemQuickScanSlotRepository, progress_tracker: ScanProgressTracker
) -> str:
    stored_scan = build_stored_scan(build_sample_jpeg())
    progress_tracker.begin_scan(SCAN_REQUEST)
    progress_tracker.mark_completed(stored_scan)
    identifier = stored_scan.last_scan.scan_identifier
    slot_repository.write_master_files(QuickScanMasterFiles(identifier, build_sample_jpeg(160, 100), b"t"))
    return identifier


def test_the_thumbnail_is_turned_by_the_rotation_of_the_scan(client, progress_tracker) -> None:
    thumbnail_jpeg = build_sample_jpeg(160, 100)
    stored_scan = build_stored_scan(thumbnail_jpeg)
    turned_scan = replace(stored_scan, last_scan=stored_scan.last_scan.with_framing(PageFraming().turned_clockwise()))
    progress_tracker.begin_scan(SCAN_REQUEST)
    progress_tracker.mark_completed(turned_scan)

    response = client.get("/api/scans/last/thumbnail")

    with Image.open(io.BytesIO(response.content)) as image:
        assert image.size == (100, 160)


def test_the_enlarged_view_is_served_as_an_immutable_jpeg(client, progress_tracker, slot_repository) -> None:
    identifier = keep_a_master(slot_repository, progress_tracker)

    response = client.get(f"/api/scans/last/preview?scan_identifier={identifier}&rotation_degrees=0")

    assert (response.status_code, response.headers["content-type"], response.headers["cache-control"]) == (
        HTTPStatus.OK,
        "image/jpeg",
        "private, max-age=31536000, immutable",
    )


def test_the_enlarged_view_is_turned_by_the_rotation_in_the_address(client, progress_tracker, slot_repository) -> None:
    identifier = keep_a_master(slot_repository, progress_tracker)

    response = client.get(f"/api/scans/last/preview?scan_identifier={identifier}&rotation_degrees=90")

    with Image.open(io.BytesIO(response.content)) as image:
        assert image.size == (100, 160)


@pytest.mark.parametrize("rotation_degrees", [45, -90, 360])
def test_an_invalid_rotation_in_the_address_is_422(client, progress_tracker, slot_repository, rotation_degrees) -> None:
    identifier = keep_a_master(slot_repository, progress_tracker)

    response = client.get(f"/api/scans/last/preview?scan_identifier={identifier}&rotation_degrees={rotation_degrees}")

    assert (response.status_code, response.json()["code"]) == (HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_page_rotation")


def test_the_enlarged_view_of_another_scan_is_404(client, progress_tracker, slot_repository) -> None:
    keep_a_master(slot_repository, progress_tracker)

    response = client.get("/api/scans/last/preview?scan_identifier=0000000000000000&rotation_degrees=0")

    assert (response.status_code, response.json()["code"]) == (HTTPStatus.NOT_FOUND, "no_last_scan")


def test_the_enlarged_view_before_any_scan_is_404(client) -> None:
    response = client.get("/api/scans/last/preview?scan_identifier=9f3c1a2b4d5e6f70")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_the_enlarged_view_of_a_scan_without_a_master_is_409(client, progress_tracker) -> None:
    stored_scan = build_stored_scan(build_sample_jpeg())
    progress_tracker.begin_scan(SCAN_REQUEST)
    progress_tracker.mark_completed(replace(stored_scan, last_scan=replace(stored_scan.last_scan, is_editable=False)))

    response = client.get("/api/scans/last/preview?scan_identifier=9f3c1a2b4d5e6f70")

    assert (response.status_code, response.json()["code"]) == (HTTPStatus.CONFLICT, "last_scan_not_editable")


def test_the_enlarged_view_of_a_master_that_vanished_is_404(client, progress_tracker, slot_repository) -> None:
    identifier = keep_a_master(slot_repository, progress_tracker)
    slot_repository.master_file_path(identifier).unlink()

    response = client.get(f"/api/scans/last/preview?scan_identifier={identifier}")

    assert response.status_code == HTTPStatus.NOT_FOUND

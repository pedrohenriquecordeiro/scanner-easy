from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from digitalizadora.controllers.preview_controller import PreviewController
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_request import ScanRequest
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
def client(progress_tracker: ScanProgressTracker) -> TestClient:
    return build_test_client(PreviewController(progress_tracker).build_router())


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

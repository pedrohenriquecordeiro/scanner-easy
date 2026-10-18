import io
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from digitalizadora.domain.errors import (
    LastScanNotEditableError,
    LastScanReplacedError,
    NoLastScanError,
    SavedScanUnreadableError,
)
from digitalizadora.domain.imaging.page_framing import PageFraming
from digitalizadora.domain.imaging.page_rotation import PageRotation
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.quick_scan.stored_scan import StoredScan
from tests.fakes.quick_scan_parts import ONE_PHOTO, SCENE_SIZE, QuickScanParts, build_job, build_quick_scan_parts


@pytest.fixture
def parts(tmp_path: Path) -> QuickScanParts:
    return build_quick_scan_parts(tmp_path)


def size_of(jpeg_content: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(jpeg_content)) as image:
        return image.size


def turn_the_scan(parts: QuickScanParts) -> None:
    last_scan = parts.progress_tracker.snapshot().last_scan
    thumbnail_jpeg = parts.progress_tracker.last_thumbnail_jpeg()
    parts.progress_tracker.replace_last_scan(
        last_scan.scan_identifier, StoredScan(last_scan.with_framing(PageFraming().turned_clockwise()), thumbnail_jpeg)
    )


def test_without_a_scan_there_is_no_thumbnail(parts):
    assert parts.last_scan_view_service.read_thumbnail() is None


def test_the_thumbnail_of_an_unturned_scan_is_the_stored_one(parts):
    stored_scan = parts.scan(ONE_PHOTO, build_job())

    assert parts.last_scan_view_service.read_thumbnail() == stored_scan.thumbnail_jpeg


def test_the_thumbnail_of_a_turned_scan_is_turned(parts):
    parts.scan(ONE_PHOTO, build_job())
    turn_the_scan(parts)

    assert size_of(parts.last_scan_view_service.read_thumbnail()) == SCENE_SIZE[::-1]


def test_the_enlarged_view_has_the_size_of_the_master_when_it_is_small(parts):
    stored_scan = parts.scan(ONE_PHOTO, build_job())

    view = parts.last_scan_view_service.read_preview(stored_scan.last_scan.scan_identifier, PageRotation.NONE)

    assert size_of(view) == SCENE_SIZE


def test_the_enlarged_view_is_turned_by_the_rotation_asked(parts):
    stored_scan = parts.scan(ONE_PHOTO, build_job())

    view = parts.last_scan_view_service.read_preview(
        stored_scan.last_scan.scan_identifier, PageRotation.COUNTERCLOCKWISE_90
    )

    assert size_of(view) == SCENE_SIZE[::-1]


def test_the_enlarged_view_of_another_scan_raises_last_scan_replaced(parts):
    parts.scan(ONE_PHOTO, build_job())

    with pytest.raises(LastScanReplacedError):
        parts.last_scan_view_service.read_preview("ffffffffffffffff", PageRotation.NONE)


def test_the_enlarged_view_without_a_scan_raises_no_last_scan(parts):
    with pytest.raises(NoLastScanError):
        parts.last_scan_view_service.read_preview("ffffffffffffffff", PageRotation.NONE)


def test_the_enlarged_view_of_a_scan_without_a_master_raises_not_editable(parts):
    stored_scan = parts.scan(ONE_PHOTO, build_job())
    parts.progress_tracker.replace_last_scan(
        stored_scan.last_scan.scan_identifier,
        StoredScan(replace(stored_scan.last_scan, is_editable=False), stored_scan.thumbnail_jpeg),
    )

    with pytest.raises(LastScanNotEditableError):
        parts.last_scan_view_service.read_preview(stored_scan.last_scan.scan_identifier, PageRotation.NONE)


def test_the_enlarged_view_of_a_master_that_vanished_raises_no_last_scan(parts):
    stored_scan = parts.scan(ONE_PHOTO, build_job())
    parts.slot_repository.master_file_path(stored_scan.last_scan.scan_identifier).unlink()

    with pytest.raises(NoLastScanError):
        parts.last_scan_view_service.read_preview(stored_scan.last_scan.scan_identifier, PageRotation.NONE)


def test_the_enlarged_view_of_a_master_that_is_not_an_image_raises_saved_scan_unreadable(parts):
    stored_scan = parts.scan(ONE_PHOTO, build_job())
    parts.slot_repository.master_file_path(stored_scan.last_scan.scan_identifier).write_bytes(b"not a jpeg")

    with pytest.raises(SavedScanUnreadableError):
        parts.last_scan_view_service.read_preview(stored_scan.last_scan.scan_identifier, PageRotation.NONE)


def test_the_enlarged_view_of_a_pdf_scan_comes_from_the_master(parts):
    stored_scan = parts.scan(ONE_PHOTO, build_job(OutputFormat.PDF))

    view = parts.last_scan_view_service.read_preview(stored_scan.last_scan.scan_identifier, PageRotation.NONE)

    assert size_of(view) == SCENE_SIZE

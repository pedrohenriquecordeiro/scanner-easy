import logging
import os
from pathlib import Path

import pytest
from PIL import Image

from digitalizadora.domain.errors import ImageAdjustmentFailedError, ScanFailedError
from digitalizadora.domain.page_crop import PageCrop
from digitalizadora.services import page_crop_detection_service
from digitalizadora.services.page_crop_detection_service import PageCropDetectionService
from digitalizadora.services.paper_edge_detection import PaperEdges
from tests.fakes.book_on_glass import BookOnGlass, build_book_on_glass_jpeg
from tests.fakes.synthetic_scans import build_scan_jpeg

LID_SIZE = (200, 280)
DARK_LID = (30, 30, 30)
PAPER = (240, 240, 240)
PAPER_BOX = (40, 60, 159, 219)
SHEET_FRACTIONS = (40 / 200, 60 / 280, 160 / 200, 220 / 280)
MARGIN_RATIO = 0.01
FRACTION_TOLERANCE = 0.03
BOOK = BookOnGlass()
REAL_SCANS_VARIABLE = "DIGITALIZADORA_REAL_SCANS_FOLDER"


@pytest.fixture
def service() -> PageCropDetectionService:
    return PageCropDetectionService()


@pytest.fixture
def sheet_on_dark_lid() -> bytes:
    return build_scan_jpeg(LID_SIZE, [(PAPER_BOX, PAPER)], background=DARK_LID)


@pytest.fixture
def book_on_glass() -> bytes:
    return build_book_on_glass_jpeg(BOOK)


def box_of(crop: PageCrop):
    return crop.bounding_edges


def edges_of(crop: PageCrop) -> tuple[float, float, float, float]:
    edges = crop.bounding_edges
    return edges.left, edges.top, edges.right, edges.bottom


def test_the_crop_to_apply_frames_a_sheet_on_a_dark_lid(service, sheet_on_dark_lid):
    crop = service.detect_crop_to_apply(sheet_on_dark_lid)

    assert edges_of(crop) == pytest.approx(SHEET_FRACTIONS, abs=FRACTION_TOLERANCE)


def test_the_crop_to_apply_grows_the_sheet_by_a_margin_of_a_hundredth_of_the_longest_side(service, sheet_on_dark_lid):
    crop = service.detect_crop_to_apply(sheet_on_dark_lid)

    margin_in_fractions = MARGIN_RATIO * max(LID_SIZE) / LID_SIZE[0]
    assert box_of(crop).left == pytest.approx(SHEET_FRACTIONS[0] - margin_in_fractions, abs=0.02)


def test_the_crop_to_apply_of_a_white_page_is_none(service):
    white_page = build_scan_jpeg(LID_SIZE)

    assert service.detect_crop_to_apply(white_page) is None


def test_the_crop_to_apply_ignores_the_detection_by_side(service, book_on_glass):
    assert service.detect_crop_to_apply(book_on_glass) is None


def test_the_crop_to_suggest_frames_a_sheet_on_a_dark_lid_like_the_crop_to_apply(service, sheet_on_dark_lid):
    assert service.detect_crop_to_suggest(sheet_on_dark_lid) == service.detect_crop_to_apply(sheet_on_dark_lid)


def test_the_crop_to_suggest_frames_a_book_the_strict_detection_cannot_see(service, book_on_glass):
    crop = service.detect_crop_to_suggest(book_on_glass)

    assert crop is not None
    assert box_of(crop).top == pytest.approx(BOOK.top - MARGIN_RATIO * 400 / 400, abs=FRACTION_TOLERANCE)


def test_the_crop_to_suggest_keeps_the_whole_book(service, book_on_glass):
    crop = service.detect_crop_to_suggest(book_on_glass)

    edges = box_of(crop)
    assert (edges.left <= BOOK.left, edges.top <= BOOK.top, edges.right >= BOOK.right, edges.bottom >= BOOK.bottom) == (
        True,
        True,
        True,
        True,
    )


def test_the_crop_to_suggest_leaves_a_side_without_an_edge_at_the_glass(service, monkeypatch):
    def edges_without_a_left_one(preview: Image.Image) -> PaperEdges:
        return PaperEdges(None, 0.2, 0.8, None)

    monkeypatch.setattr(page_crop_detection_service, "detect_paper_edges", edges_without_a_left_one)

    crop = service.detect_crop_to_suggest(build_scan_jpeg(LID_SIZE))

    assert (box_of(crop).left, box_of(crop).bottom) == (0.0, 1.0)


def build_dark_cover_around_a_bright_picture() -> bytes:
    cover_box = (30, 30, 169, 249)
    picture_box = (60, 90, 139, 189)
    return build_scan_jpeg(
        LID_SIZE, [(cover_box, (25, 30, 70)), (picture_box, (220, 200, 120))], background=(40, 40, 40)
    )


def test_a_dark_cover_around_a_bright_picture_is_not_cut_down_to_the_picture_by_the_crop_to_apply(service):
    assert service.detect_crop_to_apply(build_dark_cover_around_a_bright_picture()) is None


def test_a_dark_cover_around_a_bright_picture_is_not_cut_down_to_the_picture_by_the_crop_to_suggest(service):
    assert service.detect_crop_to_suggest(build_dark_cover_around_a_bright_picture()) is None


def test_the_crop_to_suggest_of_a_white_page_is_none(service):
    assert service.detect_crop_to_suggest(build_scan_jpeg(LID_SIZE)) is None


def test_the_crop_of_a_large_scan_maps_the_sheet_from_the_reduced_preview(service):
    large_size = (1600, 2240)
    large_box = (320, 480, 1279, 1759)
    large_scan = build_scan_jpeg(large_size, [(large_box, PAPER)], background=DARK_LID)

    crop = service.detect_crop_to_apply(large_scan)

    assert edges_of(crop) == pytest.approx((0.2, 480 / 2240, 0.8, 1760 / 2240), abs=FRACTION_TOLERANCE)


def test_a_crop_to_apply_that_finds_no_sheet_says_so_in_the_log(service, caplog):
    with caplog.at_level(logging.INFO):
        service.detect_crop_to_apply(build_scan_jpeg(LID_SIZE))

    assert [record.levelno for record in caplog.records] == [logging.INFO]


def test_a_crop_to_apply_that_finds_a_sheet_logs_nothing(service, sheet_on_dark_lid, caplog):
    with caplog.at_level(logging.INFO):
        service.detect_crop_to_apply(sheet_on_dark_lid)

    assert caplog.records == []


def test_a_crop_to_suggest_that_finds_no_sheet_says_so_in_the_log(service, caplog):
    with caplog.at_level(logging.INFO):
        service.detect_crop_to_suggest(build_scan_jpeg(LID_SIZE))

    assert [record.levelno for record in caplog.records] == [logging.INFO]


@pytest.mark.parametrize("detect", ["detect_crop_to_apply", "detect_crop_to_suggest"])
def test_bytes_that_are_not_an_image_become_a_scan_failure(service, detect):
    with pytest.raises(ScanFailedError):
        getattr(service, detect)(b"\xff\xd8 not really a jpeg")


@pytest.mark.parametrize("detect", ["detect_crop_to_apply", "detect_crop_to_suggest"])
def test_a_decompression_bomb_becomes_a_scan_failure(service, sheet_on_dark_lid, monkeypatch, detect):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1)

    with pytest.raises(ScanFailedError):
        getattr(service, detect)(sheet_on_dark_lid)


@pytest.mark.parametrize("detect", ["detect_crop_to_apply", "detect_crop_to_suggest"])
def test_running_out_of_memory_becomes_an_adjustment_failure(service, sheet_on_dark_lid, monkeypatch, detect):
    def exhaust_memory(*arguments: object) -> object:
        raise MemoryError

    monkeypatch.setattr(page_crop_detection_service, "detect_paper_region", exhaust_memory)

    with pytest.raises(ImageAdjustmentFailedError):
        getattr(service, detect)(sheet_on_dark_lid)


def test_a_sheet_so_thin_that_its_crop_is_invalid_is_not_cropped(service, monkeypatch):
    def thin_edges(preview: Image.Image) -> object:
        return PaperEdges(0.5, 0.5, 0.505, 0.9)

    monkeypatch.setattr(page_crop_detection_service, "detect_paper_edges", thin_edges)
    monkeypatch.setattr(page_crop_detection_service, "CROP_MARGIN_RATIO", 0.0)

    assert service.detect_crop_to_suggest(build_scan_jpeg(LID_SIZE)) is None


REAL_SCANS_FOLDER = os.environ.get(REAL_SCANS_VARIABLE)
REAL_BOOK_EDGES = (0.13, 0.125, 0.91, 0.914)
REAL_SCAN_NAMES = ["1-color-100.jpg", "2-gray-100.jpg", "3-color-300.jpg", "4-color-150-photo.jpg"]


@pytest.mark.skipif(REAL_SCANS_FOLDER is None, reason=f"set {REAL_SCANS_VARIABLE} to the folder of the real scans")
@pytest.mark.parametrize("scan_name", REAL_SCAN_NAMES)
def test_the_real_scans_of_the_book_get_a_frame_that_holds_the_whole_book(service, scan_name):
    scan = (Path(REAL_SCANS_FOLDER) / scan_name).read_bytes()

    crop = service.detect_crop_to_suggest(scan)

    assert crop is not None
    assert (box_of(crop).left, box_of(crop).top, box_of(crop).right, box_of(crop).bottom) == pytest.approx(
        (0.12, 0.115, 0.924, 0.925), abs=0.035
    )
    assert (box_of(crop).left <= REAL_BOOK_EDGES[0], box_of(crop).top <= REAL_BOOK_EDGES[1]) == (True, True)
    assert (box_of(crop).right >= REAL_BOOK_EDGES[2], box_of(crop).bottom >= REAL_BOOK_EDGES[3]) == (True, True)


@pytest.mark.skipif(REAL_SCANS_FOLDER is None, reason=f"set {REAL_SCANS_VARIABLE} to the folder of the real scans")
@pytest.mark.parametrize("scan_name", REAL_SCAN_NAMES)
def test_the_strict_detection_still_sees_no_sheet_in_the_real_scans(service, scan_name):
    assert service.detect_crop_to_apply((Path(REAL_SCANS_FOLDER) / scan_name).read_bytes()) is None

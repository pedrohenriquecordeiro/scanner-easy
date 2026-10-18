import io
import logging
import math
import os
import time
from pathlib import Path

import pytest
from PIL import Image

from digitalizadora.domain.errors import ImageAdjustmentFailedError, ScanFailedError
from digitalizadora.domain.page_crop import PageCrop
from digitalizadora.services import page_crop_detection_service
from digitalizadora.services.page_crop_detection_service import PageCropDetectionService
from digitalizadora.services.paper_edge_detection import PaperEdges
from tests.fakes.book_on_glass import BookOnGlass, build_book_on_glass_jpeg
from tests.fakes.photo_scenes import PlacedPhoto, build_photo_scene_jpeg, photo_corners
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
CARD_IMAGE_VARIABLE = "DIGITALIZADORA_CARD_IMAGE"
GLASS_SIZE = (1275, 1754)


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


def only_crop(service: PageCropDetectionService, jpeg_content: bytes) -> PageCrop:
    crops = service.detect_crops(jpeg_content).crops
    assert len(crops) == 1
    return crops[0]


def test_a_sheet_on_a_dark_lid_is_framed(service, sheet_on_dark_lid):
    assert edges_of(only_crop(service, sheet_on_dark_lid)) == pytest.approx(SHEET_FRACTIONS, abs=FRACTION_TOLERANCE)


def test_the_frame_of_a_sheet_grows_by_a_margin_of_a_hundredth_of_the_longest_side(service, sheet_on_dark_lid):
    crop = only_crop(service, sheet_on_dark_lid)

    margin_in_fractions = MARGIN_RATIO * max(LID_SIZE) / LID_SIZE[0]
    assert box_of(crop).left == pytest.approx(SHEET_FRACTIONS[0] - margin_in_fractions, abs=0.02)


def test_an_upright_sheet_gets_a_plain_rectangle(service, sheet_on_dark_lid):
    assert only_crop(service, sheet_on_dark_lid).is_rectangle is True


def test_a_white_page_has_no_crops(service):
    assert service.detect_crops(build_scan_jpeg(LID_SIZE)).crops == ()


def test_a_book_on_an_open_lid_is_framed_by_the_detection_by_side(service, book_on_glass):
    crop = only_crop(service, book_on_glass)

    assert box_of(crop).top == pytest.approx(BOOK.top - MARGIN_RATIO * 400 / 400, abs=FRACTION_TOLERANCE)


def test_the_frame_of_the_book_holds_the_whole_book(service, book_on_glass):
    edges = box_of(only_crop(service, book_on_glass))

    assert (edges.left <= BOOK.left, edges.top <= BOOK.top, edges.right >= BOOK.right, edges.bottom >= BOOK.bottom) == (
        True,
        True,
        True,
        True,
    )


def test_a_book_is_never_looked_for_by_the_detector_of_regions_beyond_the_border_test(
    service, book_on_glass, monkeypatch
):
    calls = []
    real_detect = page_crop_detection_service.detect_photo_regions
    monkeypatch.setattr(
        page_crop_detection_service,
        "detect_photo_regions",
        lambda preview: calls.append(preview.size) or real_detect(preview),
    )

    service.detect_crops(book_on_glass)

    assert len(calls) == 1


def test_two_photos_never_reach_the_detection_by_side(service, monkeypatch):
    def fail_if_called(preview: Image.Image) -> object:
        raise AssertionError("the detection by side must not run when the regions are found")

    monkeypatch.setattr(page_crop_detection_service, "detect_paper_edges", fail_if_called)

    detected = service.detect_crops(TWO_PHOTOS_JPEG)

    assert len(detected.crops) == 2


def test_a_side_without_an_edge_stays_at_the_glass(service, book_on_glass, monkeypatch):
    def edges_without_a_left_one(preview: Image.Image) -> PaperEdges:
        return PaperEdges(None, 0.2, 0.8, None)

    monkeypatch.setattr(page_crop_detection_service, "detect_paper_edges", edges_without_a_left_one)

    crop = only_crop(service, book_on_glass)

    assert (box_of(crop).left, box_of(crop).bottom) == (0.0, 1.0)


def test_an_l_shaped_group_that_the_regions_reject_on_a_uniform_lid_keeps_the_whole_image(service, monkeypatch):
    def fail_if_called(preview: Image.Image) -> object:
        raise AssertionError("the detection by side must not run on a uniform lid")

    monkeypatch.setattr(page_crop_detection_service, "detect_paper_edges", fail_if_called)
    horizontal_bar = PlacedPhoto(center=(500.0, 325.0), size=(600, 250), angle_degrees=0.0)
    vertical_bar = PlacedPhoto(center=(325.0, 500.0), size=(250, 600), angle_degrees=0.0, seed=2)

    detected = service.detect_crops(build_photo_scene_jpeg(GLASS_SIZE, [horizontal_bar, vertical_bar]))

    assert detected.crops == ()


def build_dark_cover_around_a_bright_picture() -> bytes:
    cover_box = (30, 30, 169, 249)
    picture_box = (60, 90, 139, 189)
    return build_scan_jpeg(
        LID_SIZE, [(cover_box, (25, 30, 70)), (picture_box, (220, 200, 120))], background=(40, 40, 40)
    )


def test_a_dark_cover_around_a_bright_picture_is_framed_as_a_whole_and_not_cut_down_to_the_picture(service):
    cover_fractions = (30 / 200, 30 / 280, 170 / 200, 250 / 280)

    edges = edges_of(only_crop(service, build_dark_cover_around_a_bright_picture()))

    assert (edges[0] <= cover_fractions[0], edges[1] <= cover_fractions[1]) == (True, True)
    assert (edges[2] >= cover_fractions[2], edges[3] >= cover_fractions[3]) == (True, True)


def test_the_crop_of_a_large_scan_maps_the_sheet_from_the_reduced_preview(service):
    large_size = (1600, 2240)
    large_box = (320, 480, 1279, 1759)
    large_scan = build_scan_jpeg(large_size, [(large_box, PAPER)], background=DARK_LID)

    crop = only_crop(service, large_scan)

    assert edges_of(crop) == pytest.approx((0.2, 480 / 2240, 0.8, 1760 / 2240), abs=FRACTION_TOLERANCE)


def test_a_scan_without_crops_says_so_in_the_log(service, caplog):
    with caplog.at_level(logging.INFO):
        service.detect_crops(build_scan_jpeg(LID_SIZE))

    assert [record.levelno for record in caplog.records] == [logging.INFO]


def test_a_scan_with_a_sheet_logs_nothing(service, sheet_on_dark_lid, caplog):
    with caplog.at_level(logging.INFO):
        service.detect_crops(sheet_on_dark_lid)

    assert caplog.records == []


def test_bytes_that_are_not_an_image_become_a_scan_failure(service):
    with pytest.raises(ScanFailedError):
        service.detect_crops(b"\xff\xd8 not really a jpeg")


def test_a_decompression_bomb_becomes_a_scan_failure(service, sheet_on_dark_lid, monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1)

    with pytest.raises(ScanFailedError):
        service.detect_crops(sheet_on_dark_lid)


def test_running_out_of_memory_becomes_an_adjustment_failure(service, sheet_on_dark_lid, monkeypatch):
    def exhaust_memory(*arguments: object) -> object:
        raise MemoryError

    monkeypatch.setattr(page_crop_detection_service, "detect_photo_regions", exhaust_memory)

    with pytest.raises(ImageAdjustmentFailedError):
        service.detect_crops(sheet_on_dark_lid)


def test_a_sheet_so_thin_that_its_crop_is_invalid_is_not_cropped(service, monkeypatch):
    def thin_edges(preview: Image.Image) -> object:
        return PaperEdges(0.5, 0.5, 0.505, 0.9)

    monkeypatch.setattr(page_crop_detection_service, "detect_paper_edges", thin_edges)
    monkeypatch.setattr(page_crop_detection_service, "CROP_MARGIN_RATIO", 0.0)

    assert service.detect_crops(build_scan_jpeg(LID_SIZE)).crops == ()


UPPER_PHOTO = PlacedPhoto(center=(450.0, 520.0), size=(800, 540), angle_degrees=-30.0)
LOWER_PHOTO = PlacedPhoto(center=(690.0, 1330.0), size=(800, 540), angle_degrees=-2.0, seed=2)
CARD = PlacedPhoto(center=(640.0, 880.0), size=(420, 620), angle_degrees=31.0)
TWO_PHOTOS_JPEG = build_photo_scene_jpeg(GLASS_SIZE, [UPPER_PHOTO, LOWER_PHOTO])
CORNER_TOLERANCE_FRACTION = 0.012


def crop_of(photo: PlacedPhoto) -> list[tuple[float, float]]:
    return [(x / GLASS_SIZE[0], y / GLASS_SIZE[1]) for x, y in photo_corners(photo)]


def worst_distance(crop: PageCrop, truth: list[tuple[float, float]]) -> float:
    return max(math.dist((corner.x, corner.y), wanted) for corner, wanted in zip(crop.corners, truth, strict=True))


def test_two_photos_give_two_crops_in_reading_order(service):
    crops = service.detect_crops(TWO_PHOTOS_JPEG).crops

    assert [crop.bounding_edges.top < 0.5 for crop in crops] == [True, False]


def test_the_crops_of_two_photos_are_close_to_the_corners_of_the_photos_with_the_margin(service):
    crops = service.detect_crops(TWO_PHOTOS_JPEG).crops

    margin = MARGIN_RATIO * max(GLASS_SIZE) / min(GLASS_SIZE) * 2
    assert worst_distance(crops[0], crop_of(UPPER_PHOTO)) < CORNER_TOLERANCE_FRACTION + margin / 2
    assert worst_distance(crops[1], crop_of(LOWER_PHOTO)) < CORNER_TOLERANCE_FRACTION + margin / 2


def test_a_tilted_photo_is_a_crop_that_is_not_a_rectangle(service):
    crops = service.detect_crops(TWO_PHOTOS_JPEG).crops

    assert [crop.is_rectangle for crop in crops] == [False, False]


def test_a_crop_grows_outwards_so_that_it_holds_the_photo(service):
    crop = service.detect_crops(build_photo_scene_jpeg(GLASS_SIZE, [CARD])).crops[0]

    truth_edges = [min(x for x, _ in crop_of(CARD)), min(y for _, y in crop_of(CARD))]
    assert (crop.bounding_edges.left < truth_edges[0], crop.bounding_edges.top < truth_edges[1]) == (True, True)


def test_the_margin_is_a_hundredth_of_the_longest_side_in_every_direction(service):
    upright = PlacedPhoto(center=(640.0, 880.0), size=(600, 800), angle_degrees=0.0)

    crop = service.detect_crops(build_photo_scene_jpeg(GLASS_SIZE, [upright])).crops[0]

    margin_in_pixels = (340 - crop.bounding_edges.left * GLASS_SIZE[0])
    assert margin_in_pixels == pytest.approx(MARGIN_RATIO * max(GLASS_SIZE), abs=6)


def test_a_photo_five_tenths_of_a_degree_off_is_taken_as_upright(service):
    nearly_upright = PlacedPhoto(center=(640.0, 880.0), size=(600, 800), angle_degrees=0.5)

    crop = service.detect_crops(build_photo_scene_jpeg(GLASS_SIZE, [nearly_upright])).crops[0]

    assert crop.is_rectangle is True


def test_a_photo_two_degrees_off_is_not_taken_as_upright(service):
    tilted = PlacedPhoto(center=(640.0, 880.0), size=(600, 800), angle_degrees=2.2)

    crop = service.detect_crops(build_photo_scene_jpeg(GLASS_SIZE, [tilted])).crops[0]

    assert crop.is_rectangle is False


def test_the_top_role_of_a_tilted_photo_is_its_edge_closest_to_horizontal(service):
    crop = service.detect_crops(build_photo_scene_jpeg(GLASS_SIZE, [CARD])).crops[0]

    top_edge_x = (crop.top_right.x - crop.top_left.x) * GLASS_SIZE[0]
    top_edge_y = (crop.top_right.y - crop.top_left.y) * GLASS_SIZE[1]
    assert math.degrees(math.atan2(top_edge_y, top_edge_x)) == pytest.approx(31.0, abs=2.0)


def test_a_third_photo_is_ignored_and_counted(service):
    photos = [
        PlacedPhoto((330.0, 450.0), (420, 540), 0.0),
        PlacedPhoto((900.0, 450.0), (420, 540), 6.0, 2),
        PlacedPhoto((640.0, 1450.0), (360, 260), 0.0, 3),
    ]

    detected = service.detect_crops(build_photo_scene_jpeg(GLASS_SIZE, photos))

    assert (len(detected.crops), detected.ignored_region_count) == (2, 1)


def test_a_scan_without_extra_photos_ignores_nothing(service):
    assert service.detect_crops(TWO_PHOTOS_JPEG).ignored_region_count == 0


def test_a_photo_against_the_edge_of_the_glass_is_framed_inside_the_page(service):
    photo = PlacedPhoto(center=(330.0, 440.0), size=(640, 860), angle_degrees=4.0)

    crop = service.detect_crops(build_photo_scene_jpeg(GLASS_SIZE, [photo])).crops[0]

    assert all(0.0 <= corner.x <= 1.0 and 0.0 <= corner.y <= 1.0 for corner in crop.corners)


def test_detecting_the_crops_of_a_full_scan_is_fast(service):
    started = time.perf_counter()
    service.detect_crops(TWO_PHOTOS_JPEG)

    assert time.perf_counter() - started < 0.5


REAL_SCANS_FOLDER = os.environ.get(REAL_SCANS_VARIABLE)
CARD_IMAGE = os.environ.get(CARD_IMAGE_VARIABLE)
REAL_BOOK_EDGES = (0.13, 0.125, 0.91, 0.914)
REAL_SCAN_NAMES = ["1-color-100.jpg", "2-gray-100.jpg", "3-color-300.jpg", "4-color-150-photo.jpg"]
REAL_PHOTO_SCAN_NAMES = ["photos-1-color-100.jpg", "photos-2-color-300.jpg", "photos-3-gray-150.jpg"]
REAL_UPPER_PHOTO = [(0.039, 0.280), (0.650, 0.019), (0.894, 0.321), (0.282, 0.582)]
REAL_LOWER_PHOTO = [(0.171, 0.604), (0.878, 0.584), (0.896, 0.931), (0.189, 0.951)]


@pytest.mark.skipif(REAL_SCANS_FOLDER is None, reason=f"set {REAL_SCANS_VARIABLE} to the folder of the real scans")
@pytest.mark.parametrize("scan_name", REAL_SCAN_NAMES)
def test_the_real_scans_of_the_book_get_a_frame_that_holds_the_whole_book(service, scan_name):
    scan = (Path(REAL_SCANS_FOLDER) / scan_name).read_bytes()

    crop = only_crop(service, scan)

    assert edges_of(crop) == pytest.approx((0.12, 0.115, 0.924, 0.925), abs=0.035)
    assert (box_of(crop).left <= REAL_BOOK_EDGES[0], box_of(crop).top <= REAL_BOOK_EDGES[1]) == (True, True)
    assert (box_of(crop).right >= REAL_BOOK_EDGES[2], box_of(crop).bottom >= REAL_BOOK_EDGES[3]) == (True, True)


@pytest.mark.skipif(REAL_SCANS_FOLDER is None, reason=f"set {REAL_SCANS_VARIABLE} to the folder of the real scans")
@pytest.mark.parametrize("scan_name", REAL_PHOTO_SCAN_NAMES)
def test_the_real_scans_of_two_photos_give_two_crops_with_the_known_corners(service, scan_name):
    scan = (Path(REAL_SCANS_FOLDER) / scan_name).read_bytes()

    crops = service.detect_crops(scan).crops

    assert len(crops) == 2
    assert worst_distance(crops[0], REAL_UPPER_PHOTO) < 0.04
    assert worst_distance(crops[1], REAL_LOWER_PHOTO) < 0.04


@pytest.mark.skipif(CARD_IMAGE is None, reason=f"set {CARD_IMAGE_VARIABLE} to the picture of the card")
def test_the_card_at_about_25_degrees_is_framed_as_a_tilted_crop(service):
    with Image.open(CARD_IMAGE) as picture:
        buffer = io.BytesIO()
        picture.convert("RGB").save(buffer, format="JPEG", quality=90)

    crops = service.detect_crops(buffer.getvalue()).crops

    assert len(crops) == 1
    assert crops[0].is_rectangle is False

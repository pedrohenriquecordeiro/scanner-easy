"""The frames of the document mode through the whole application: up to two quadrilaterals per page."""

import json
import shutil
from pathlib import Path

import pikepdf
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from digitalizadora.composition_root import DRAFTS_FOLDER_NAME
from digitalizadora.configuration import ApplicationConfiguration
from digitalizadora.domain.document_draft_reconciliation import page_file_name
from digitalizadora.repositories.file_system_document_draft_repository import CURRENT_DRAFT_FOLDER_NAME
from digitalizadora.simulator.fake_escl_scanner_app import FakeScannerBehavior
from digitalizadora.simulator.photo_scene_page import PHOTO_PLACEMENTS_BY_SCENE, PhotoScene, photo_corners
from tests.fakes.configuration_builder import build_application_configuration
from tests.integration.flow_support import (
    DOTS_PER_INCH,
    GLASS_SIZE,
    SCANNER_ADDRESS,
    STATE_CHANGING_HEADERS,
    add_document_page,
    build_client,
    corners_of,
    crop_body,
    has_upright_markers,
    open_image,
    read_pages,
    save_settings,
)

TWO_PHOTOS = FakeScannerBehavior(scene=PhotoScene.PHOTOS_TWO)
POINTS_PER_INCH = 72
CORNER_TOLERANCE = 0.06


@pytest.fixture
def configuration(tmp_path: Path) -> ApplicationConfiguration:
    return build_application_configuration(tmp_path, SCANNER_ADDRESS)


def page_file_path(configuration: ApplicationConfiguration, page_identifier: str) -> Path:
    return (
        configuration.data_directory / DRAFTS_FOLDER_NAME / CURRENT_DRAFT_FOLDER_NAME / page_file_name(page_identifier)
    )


def put_crops(client: TestClient, page_identifier: str, crops: list[dict]):
    return client.put(
        f"/api/document/pages/{page_identifier}/crops", json={"crops": crops}, headers=STATE_CHANGING_HEADERS
    )


def finalize(client: TestClient) -> dict:
    response = client.post("/api/document/finalize", headers=STATE_CHANGING_HEADERS)
    assert response.status_code == 200
    return response.json()


def read_pdf_pages(finalization: dict) -> list[Image.Image]:
    """The images of the pages of the saved PDF, as Pillow reads them."""
    images = []
    with pikepdf.open(Path(finalization["output_folder"]) / finalization["file_name"]) as document:
        for page in document.pages:
            image_stream = next(iter(page.get_images().values()))
            images.append(open_image(image_stream.read_raw_bytes()))
    return images


def read_pdf_page_sizes(finalization: dict) -> list[tuple[float, float]]:
    with pikepdf.open(Path(finalization["output_folder"]) / finalization["file_name"]) as document:
        return [(float(page.mediabox[2]), float(page.mediabox[3])) for page in document.pages]


def worst_corner_error(crop: dict, placement_index: int) -> float:
    truth = photo_corners(PHOTO_PLACEMENTS_BY_SCENE[PhotoScene.PHOTOS_TWO][placement_index], GLASS_SIZE)
    return max(
        ((fx - tx / GLASS_SIZE[0]) ** 2 + (fy - ty / GLASS_SIZE[1]) ** 2) ** 0.5
        for (fx, fy), (tx, ty) in zip(corners_of(crop), truth, strict=True)
    )


def scan_two_photos_with_the_crop(client: TestClient, configuration: ApplicationConfiguration) -> dict:
    save_settings(client, configuration.default_output_folder, auto_crop=True)
    add_document_page(client, 1)
    return read_pages(client)[0]


def test_a_page_with_two_photos_gets_two_frames(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        page = scan_two_photos_with_the_crop(client, configuration)

    assert len(page["crops"]) == 2


def test_the_two_frames_are_where_the_photos_are_in_reading_order(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        page = scan_two_photos_with_the_crop(client, configuration)

    assert worst_corner_error(page["crops"][0], 0) < CORNER_TOLERANCE
    assert worst_corner_error(page["crops"][1], 1) < CORNER_TOLERANCE


def test_the_stored_master_never_changes_with_the_frames_the_rotation_and_the_detection(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        page = scan_two_photos_with_the_crop(client, configuration)
        page_identifier = page["page_identifier"]
        master_before = page_file_path(configuration, page_identifier).read_bytes()
        put_crops(client, page_identifier, page["crops"][:1])
        client.post(f"/api/document/pages/{page_identifier}/rotation", headers=STATE_CHANGING_HEADERS)
        client.post(f"/api/document/pages/{page_identifier}/crops/detect", headers=STATE_CHANGING_HEADERS)
        master_after = page_file_path(configuration, page_identifier).read_bytes()

    assert master_after == master_before


def test_saving_a_page_with_two_frames_gives_a_pdf_of_two_pages(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        scan_two_photos_with_the_crop(client, configuration)
        finalization = finalize(client)

    assert (finalization["page_count"], len(read_pdf_page_sizes(finalization))) == (2, 2)


def test_the_two_pages_of_the_pdf_have_the_physical_size_of_the_photos(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        scan_two_photos_with_the_crop(client, configuration)
        finalization = finalize(client)

    placements = PHOTO_PLACEMENTS_BY_SCENE[PhotoScene.PHOTOS_TWO]
    points_per_pixel = POINTS_PER_INCH / DOTS_PER_INCH
    expected = [
        (placement.width * GLASS_SIZE[0] * points_per_pixel, placement.height * GLASS_SIZE[0] * points_per_pixel)
        for placement in placements
    ]
    assert [side for size in read_pdf_page_sizes(finalization) for side in size] == pytest.approx(
        [side for size in expected for side in size], rel=0.08
    )


def test_the_two_pages_of_the_pdf_are_upright(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        scan_two_photos_with_the_crop(client, configuration)
        finalization = finalize(client)

    pages = read_pdf_pages(finalization)
    assert [has_upright_markers(page) for page in pages] == [True, True]


def test_the_state_counts_the_pages_of_the_pdf_in_the_last_finished_document(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        scan_two_photos_with_the_crop(client, configuration)
        finalize(client)
        last_finished = client.get("/api/document").json()["last_finished_document"]

    assert last_finished["page_count"] == 2


def test_two_pages_with_two_frames_each_give_four_pages_in_the_pdf(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        add_document_page(client, 1)
        add_document_page(client, 2)
        finalization = finalize(client)

    assert finalization["page_count"] == 4


def test_one_frame_removed_gives_one_page_for_that_photo(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        page = scan_two_photos_with_the_crop(client, configuration)
        put_crops(client, page["page_identifier"], page["crops"][1:])
        finalization = finalize(client)

    assert finalization["page_count"] == 1


def test_a_page_without_frames_is_one_whole_page_in_the_pdf(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        save_settings(client, configuration.default_output_folder)
        add_document_page(client, 1)
        finalization = finalize(client)

    assert read_pdf_page_sizes(finalization) == pytest.approx(
        [(GLASS_SIZE[0] * POINTS_PER_INCH / DOTS_PER_INCH, GLASS_SIZE[1] * POINTS_PER_INCH / DOTS_PER_INCH)], abs=1.0
    )


def test_a_tilted_quadrilateral_set_by_hand_is_saved_upright(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        save_settings(client, configuration.default_output_folder)
        add_document_page(client, 1)
        page_identifier = read_pages(client)[0]["page_identifier"]
        upper_photo = PHOTO_PLACEMENTS_BY_SCENE[PhotoScene.PHOTOS_TWO][0]
        truth = [(x / GLASS_SIZE[0], y / GLASS_SIZE[1]) for x, y in photo_corners(upper_photo, GLASS_SIZE)]
        response = put_crops(client, page_identifier, [crop_body(truth)])
        finalization = finalize(client)

    assert response.status_code == 200
    assert has_upright_markers(read_pdf_pages(finalization)[0])


def test_three_frames_are_refused_and_change_nothing(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        page = scan_two_photos_with_the_crop(client, configuration)
        response = put_crops(client, page["page_identifier"], [*page["crops"], page["crops"][0]])
        after = read_pages(client)[0]

    assert (response.status_code, response.json()["code"], after["crops"]) == (422, "invalid_crop", page["crops"])


def test_a_bow_tie_is_refused(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        page = scan_two_photos_with_the_crop(client, configuration)
        bow_tie = [(0.1, 0.1), (0.8, 0.8), (0.8, 0.1), (0.1, 0.8)]

        response = put_crops(client, page["page_identifier"], [crop_body(bow_tie)])

    assert (response.status_code, response.json()["code"]) == (422, "invalid_crop")


def test_turning_the_page_turns_the_frames_with_it_and_four_turns_bring_them_back(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        page = scan_two_photos_with_the_crop(client, configuration)
        page_identifier = page["page_identifier"]
        for _ in range(4):
            client.post(f"/api/document/pages/{page_identifier}/rotation", headers=STATE_CHANGING_HEADERS)
        after = read_pages(client)[0]

    assert (after["rotation_degrees"], after["crops"]) == (0, page["crops"])


def test_a_turned_page_saves_the_photos_turned_with_it(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        page = scan_two_photos_with_the_crop(client, configuration)
        client.post(
            f"/api/document/pages/{page['page_identifier']}/rotation", headers=STATE_CHANGING_HEADERS
        )
        finalization = finalize(client)

    sizes = read_pdf_page_sizes(finalization)
    placements = PHOTO_PLACEMENTS_BY_SCENE[PhotoScene.PHOTOS_TWO]
    assert all(height > width for width, height in sizes) is True
    assert len(sizes) == len(placements)


def test_the_detection_of_a_page_answers_the_flags_and_both_frames(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        save_settings(client, configuration.default_output_folder)
        add_document_page(client, 1)
        page_identifier = read_pages(client)[0]["page_identifier"]

        response = client.post(
            f"/api/document/pages/{page_identifier}/crops/detect", headers=STATE_CHANGING_HEADERS
        )

    body = response.json()
    assert (body["crops_detected"], body["ignored_region_count"], len(body["document"]["pages"][0]["crops"])) == (
        True,
        0,
        2,
    )


def test_the_frames_survive_a_restart(configuration, tmp_path):
    with build_client(configuration, TWO_PHOTOS) as client:
        page = scan_two_photos_with_the_crop(client, configuration)
        restarted_configuration = build_application_configuration(tmp_path / "restart", SCANNER_ADDRESS)
        shutil.copytree(
            configuration.data_directory / DRAFTS_FOLDER_NAME,
            restarted_configuration.data_directory / DRAFTS_FOLDER_NAME,
        )
    with build_client(restarted_configuration, TWO_PHOTOS) as restarted:
        resumed = read_pages(restarted)[0]

    assert resumed["crops"] == page["crops"]


def test_a_draft_saved_before_the_quadrilaterals_still_loads_its_rectangle(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        save_settings(client, configuration.default_output_folder)
        add_document_page(client, 1)
    manifest_path = configuration.data_directory / DRAFTS_FOLDER_NAME / CURRENT_DRAFT_FOLDER_NAME / "manifest.json"
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    document["pages"][0].pop("crops", None)
    document["pages"][0]["crop"] = {"left": 0.1, "top": 0.2, "right": 0.6, "bottom": 0.7}
    old_configuration = build_application_configuration(configuration.data_directory.parent / "old", SCANNER_ADDRESS)
    shutil.copytree(
        configuration.data_directory / DRAFTS_FOLDER_NAME, old_configuration.data_directory / DRAFTS_FOLDER_NAME
    )
    old_manifest = old_configuration.data_directory / DRAFTS_FOLDER_NAME / CURRENT_DRAFT_FOLDER_NAME / "manifest.json"
    old_manifest.write_text(json.dumps(document), encoding="utf-8")
    with build_client(old_configuration, TWO_PHOTOS) as client:
        page = read_pages(client)[0]

    assert corners_of(page["crops"][0]) == [(0.1, 0.2), (0.6, 0.2), (0.6, 0.7), (0.1, 0.7)]


def test_a_lower_jpeg_quality_makes_a_smaller_pdf(configuration, tmp_path):
    sizes = []
    for quality in (60, 95):
        quality_configuration = build_application_configuration(tmp_path / f"q{quality}", SCANNER_ADDRESS)
        with build_client(quality_configuration, TWO_PHOTOS) as client:
            save_settings(client, quality_configuration.default_output_folder, auto_crop=True, jpeg_quality=quality)
            add_document_page(client, 1)
            finalization = finalize(client)
            sizes.append(finalization["size_in_bytes"])
    assert sizes[0] < sizes[1]


def test_the_quality_saved_in_the_settings_is_the_one_the_pdf_uses(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        settings = save_settings(client, configuration.default_output_folder, auto_crop=True, jpeg_quality=55)

    assert settings["jpeg_quality"] == 55


def test_a_quality_outside_the_range_is_refused_by_the_settings(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        body = {"output_folder": str(configuration.default_output_folder), "output_format": "jpg", "jpeg_quality": 20}
        response = client.put("/api/settings", json=body, headers=STATE_CHANGING_HEADERS)

    assert (response.status_code, response.json()["code"]) == (422, "invalid_settings")

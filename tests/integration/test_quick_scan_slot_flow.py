"""The quick mode through the whole application: the master in the slot, the frames, the files, the edits."""

import asyncio
import contextlib
import dataclasses
import functools
import shutil
import threading
from collections.abc import Iterator
from pathlib import Path

import pikepdf
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from digitalizadora.composition_root import QUICK_SCAN_FOLDER_NAME
from digitalizadora.configuration import ApplicationConfiguration
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter
from digitalizadora.repositories.file_system_quick_scan_slot_repository import FileSystemQuickScanSlotRepository
from digitalizadora.simulator.fake_escl_scanner_app import FakeScannerBehavior
from digitalizadora.simulator.photo_scene_page import PHOTO_PLACEMENTS_BY_SCENE, PhotoScene, photo_corners
from tests.fakes.configuration_builder import build_application_configuration
from tests.fakes.fixed_clock import FixedClock
from tests.integration.flow_support import (
    GLASS_SIZE,
    SCANNER_ADDRESS,
    STATE_CHANGING_HEADERS,
    build_client,
    corners_of,
    crop_body,
    has_upright_markers,
    last_result_paths,
    read_image_size,
    save_settings,
    scan_once,
    wait_for_state,
)

TWO_PHOTOS = FakeScannerBehavior(scene=PhotoScene.PHOTOS_TWO)
ONE_PHOTO = FakeScannerBehavior(scene=PhotoScene.PHOTOS_ONE)
CORNER_TOLERANCE = 0.03


@pytest.fixture
def configuration(tmp_path: Path) -> ApplicationConfiguration:
    return build_application_configuration(tmp_path, SCANNER_ADDRESS)


def slot_folder(configuration: ApplicationConfiguration) -> Path:
    return configuration.data_directory / QUICK_SCAN_FOLDER_NAME


def turn_last_scan(client: TestClient):
    return client.post("/api/scans/last/rotation", headers=STATE_CHANGING_HEADERS)


def put_last_crops(client: TestClient, crops: list[dict]):
    return client.put("/api/scans/last/crops", json={"crops": crops}, headers=STATE_CHANGING_HEADERS)


def detect_last_crops(client: TestClient):
    return client.post("/api/scans/last/crops/detect", headers=STATE_CHANGING_HEADERS)


def worst_corner_error(crop: dict, placement_index: int, scene: PhotoScene) -> float:
    truth = photo_corners(PHOTO_PLACEMENTS_BY_SCENE[scene][placement_index], GLASS_SIZE)
    found = corners_of(crop)
    return max(
        ((fx - tx / GLASS_SIZE[0]) ** 2 + (fy - ty / GLASS_SIZE[1]) ** 2) ** 0.5
        for (fx, fy), (tx, ty) in zip(found, truth, strict=True)
    )


def test_one_photo_with_the_crop_gives_one_cropped_file_and_one_frame(configuration):
    with build_client(configuration, ONE_PHOTO) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        state = scan_once(client)

    (path,) = last_result_paths(state)
    assert (len(state["last_result"]["crops"]), read_image_size(path)[0] < GLASS_SIZE[0]) == (1, True)


def test_the_cropped_file_of_one_photo_is_upright(configuration):
    with build_client(configuration, ONE_PHOTO) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        state = scan_once(client)

    with Image.open(last_result_paths(state)[0]) as image:
        assert has_upright_markers(image)


def test_two_photos_give_two_files_with_consecutive_names_and_two_frames(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        state = scan_once(client)

    file_names = state["last_result"]["file_names"]
    numbers = [int(name.removesuffix(".jpg").rpartition("_")[2]) for name in file_names]
    assert (numbers[1] - numbers[0], len(state["last_result"]["crops"])) == (1, 2)


def test_the_two_frames_are_where_the_photos_are(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        crops = scan_once(client)["last_result"]["crops"]

    margin = 0.03
    assert worst_corner_error(crops[0], 0, PhotoScene.PHOTOS_TWO) < CORNER_TOLERANCE + margin
    assert worst_corner_error(crops[1], 1, PhotoScene.PHOTOS_TWO) < CORNER_TOLERANCE + margin


def test_both_files_of_two_photos_are_cut_out_upright(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        state = scan_once(client)

    results = []
    for path in last_result_paths(state):
        with Image.open(path) as image:
            results.append(has_upright_markers(image))
    assert results == [True, True]


def test_the_file_of_the_photo_turned_thirty_degrees_has_the_size_of_the_photo(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        state = scan_once(client)

    placement = PHOTO_PLACEMENTS_BY_SCENE[PhotoScene.PHOTOS_TWO][0]
    expected = (placement.width * GLASS_SIZE[0], placement.height * GLASS_SIZE[0])
    assert read_image_size(last_result_paths(state)[0]) == pytest.approx(expected, rel=0.08)


def test_the_master_is_kept_in_the_slot_with_the_scanner_size(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        state = scan_once(client)

    masters = list(slot_folder(configuration).glob("master-*.jpg"))
    assert [master.name for master in masters] == [f"master-{state['last_result']['scan_identifier']}.jpg"]
    assert read_image_size(masters[0]) == GLASS_SIZE


def test_without_the_crop_the_files_are_the_whole_glass_and_the_master_is_the_same_image(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        save_settings(client, configuration.default_output_folder)
        state = scan_once(client)

    (path,) = last_result_paths(state)
    assert (read_image_size(path), state["last_result"]["crops"]) == (GLASS_SIZE, [])


def test_the_enlarged_view_of_the_last_scan_is_served_from_the_master(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        identifier = scan_once(client)["last_result"]["scan_identifier"]
        response = client.get(f"/api/scans/last/preview?scan_identifier={identifier}&rotation_degrees=0")

    assert (response.status_code, response.headers["content-type"]) == (200, "image/jpeg")


def test_adjusting_the_frames_by_the_api_rewrites_the_files_under_the_same_names(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        state = scan_once(client)
        names_before = state["last_result"]["file_names"]
        smaller = [(0.30, 0.20), (0.60, 0.20), (0.60, 0.40), (0.30, 0.40)]

        response = put_last_crops(client, [crop_body(smaller)])

    assert response.status_code == 200
    assert response.json()["last_result"]["file_names"] == names_before[:1]
    assert response.json()["deleted_file_names"] == names_before[1:]


def test_removing_the_second_frame_deletes_the_second_file_and_says_so(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        state = scan_once(client)
        first_crop = state["last_result"]["crops"][0]

        response = put_last_crops(client, [first_crop])

    remaining = [path.name for path in configuration.default_output_folder.iterdir()]
    assert (response.json()["deleted_file_names"], remaining) == (
        state["last_result"]["file_names"][1:],
        state["last_result"]["file_names"][:1],
    )


def test_adding_a_second_frame_creates_the_next_numbered_file(configuration):
    with build_client(configuration, ONE_PHOTO) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        state = scan_once(client)
        other = [(0.05, 0.60), (0.35, 0.60), (0.35, 0.85), (0.05, 0.85)]

        response = put_last_crops(client, [state["last_result"]["crops"][0], crop_body(other)])

    assert len(response.json()["last_result"]["file_names"]) == 2
    assert len(list(configuration.default_output_folder.iterdir())) == 2


def test_the_state_reports_the_new_frames_and_a_new_revision_after_an_edit(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        state = scan_once(client)
        put_last_crops(client, [])
        after = client.get("/api/state").json()

    assert (after["last_result"]["crops"], after["last_result_revision"]) == ([], state["last_result_revision"] + 1)


def test_setting_the_same_crops_changes_no_revision(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        state = scan_once(client)
        put_last_crops(client, state["last_result"]["crops"])
        revision_after = client.get("/api/state").json()["last_result_revision"]

    assert revision_after == state["last_result_revision"]


def test_an_invalid_crop_answers_422_and_changes_nothing(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        state = scan_once(client)
        bowtie = [(0.1, 0.1), (0.8, 0.8), (0.8, 0.1), (0.1, 0.8)]

        response = put_last_crops(client, [crop_body(bowtie)])
        after = client.get("/api/state").json()

    assert (response.status_code, response.json()["code"]) == (422, "invalid_crop")
    assert after["last_result_revision"] == state["last_result_revision"]


def test_three_crops_are_refused(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        crops = scan_once(client)["last_result"]["crops"]

        response = put_last_crops(client, [*crops, crops[0]])

    assert (response.status_code, response.json()["code"]) == (422, "invalid_crop")


def test_turning_the_last_scan_turns_the_files_and_the_frames_with_the_page(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        state = scan_once(client)
        sizes_before = [read_image_size(path) for path in last_result_paths(state)]

        response = turn_last_scan(client)

    assert response.json()["last_result"]["rotation_degrees"] == 90
    sizes_after = [read_image_size(path) for path in last_result_paths(state)]
    assert [side for size in sizes_after for side in size] == pytest.approx(
        [side for size in sizes_before for side in size[::-1]], abs=3
    )


def test_a_turned_file_is_still_upright_in_its_own_orientation_after_four_turns(configuration):
    with build_client(configuration, ONE_PHOTO) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        state = scan_once(client)
        for _ in range(4):
            turn_last_scan(client)

    with Image.open(last_result_paths(state)[0]) as image:
        assert has_upright_markers(image)


def test_turning_a_pdf_scan_rewrites_the_pdf_with_the_physical_size_swapped(configuration):
    with build_client(configuration, ONE_PHOTO) as client:
        save_settings(client, configuration.default_output_folder, output_format="pdf", auto_crop=True)
        state = scan_once(client)
        (path,) = last_result_paths(state)
        with pikepdf.open(path) as pdf:
            before = (float(pdf.pages[0].mediabox[2]), float(pdf.pages[0].mediabox[3]))
        turn_last_scan(client)
        with pikepdf.open(path) as pdf:
            after = (float(pdf.pages[0].mediabox[2]), float(pdf.pages[0].mediabox[3]))

    assert after == pytest.approx(before[::-1], abs=1.0)


def test_the_detection_finds_the_photos_of_a_scan_saved_whole(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        save_settings(client, configuration.default_output_folder)
        scan_once(client)

        response = detect_last_crops(client)

    body = response.json()
    assert (body["crops_detected"], len(body["last_result"]["crops"]), len(body["last_result"]["file_names"])) == (
        True,
        2,
        2,
    )


def test_the_detection_after_a_turn_gives_the_crops_in_the_orientation_shown(configuration):
    with build_client(configuration, TWO_PHOTOS) as client:
        save_settings(client, configuration.default_output_folder)
        scan_once(client)
        turn_last_scan(client)

        body = detect_last_crops(client).json()

    assert body["last_result"]["rotation_degrees"] == 90
    assert len(body["last_result"]["crops"]) == 2


def test_a_lower_quality_makes_smaller_files(configuration, tmp_path):
    sizes = []
    for quality in (60, 95):
        quality_configuration = build_application_configuration(tmp_path / f"q{quality}", SCANNER_ADDRESS)
        with build_client(quality_configuration, ONE_PHOTO) as client:
            save_settings(client, quality_configuration.default_output_folder, auto_crop=True, jpeg_quality=quality)
            (path,) = last_result_paths(scan_once(client))
            sizes.append(path.stat().st_size)
    assert sizes[0] < sizes[1]


def test_the_quality_applies_again_when_a_frame_is_rewritten(configuration):
    with build_client(configuration, ONE_PHOTO) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True, jpeg_quality=95)
        state = scan_once(client)
        (path,) = last_result_paths(state)
        size_at_95 = path.stat().st_size
        save_settings(client, configuration.default_output_folder, auto_crop=True, jpeg_quality=55)

        turn_last_scan(client)

    assert path.stat().st_size < size_at_95


def test_an_edit_during_nothing_without_a_scan_answers_no_last_scan(configuration):
    with build_client(configuration, ONE_PHOTO) as client:
        response = turn_last_scan(client)

    assert (response.status_code, response.json()["code"]) == (404, "no_last_scan")


def copy_the_disk_to_a_new_run(configuration: ApplicationConfiguration, tmp_path: Path) -> ApplicationConfiguration:
    """What the next process finds when the first one is gone without a word: the same folders, a new lock."""
    restarted_configuration = build_application_configuration(tmp_path / "restart", SCANNER_ADDRESS)
    shutil.copytree(slot_folder(configuration), slot_folder(restarted_configuration))
    shutil.copytree(configuration.default_output_folder, restarted_configuration.default_output_folder)
    settings_file = "settings.json"
    shutil.copy(configuration.data_directory / settings_file, restarted_configuration.data_directory / settings_file)
    return restarted_configuration


def test_the_last_scan_comes_back_after_a_restart_and_can_be_edited(configuration, tmp_path):
    with build_client(configuration, TWO_PHOTOS) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        state = scan_once(client)
        restarted_configuration = copy_the_disk_to_a_new_run(configuration, tmp_path)
    with build_client(restarted_configuration, TWO_PHOTOS) as restarted:
        restored = restarted.get("/api/state").json()["last_result"]
        response = turn_last_scan(restarted)

    assert restored["scan_identifier"] == state["last_result"]["scan_identifier"]
    assert response.status_code == 200


def test_the_thumbnail_of_the_last_scan_comes_back_after_a_restart(configuration, tmp_path):
    with build_client(configuration, TWO_PHOTOS) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        scan_once(client)
        thumbnail_before = client.get("/api/scans/last/thumbnail").content
        restarted_configuration = copy_the_disk_to_a_new_run(configuration, tmp_path)
    with build_client(restarted_configuration, TWO_PHOTOS) as restarted:
        thumbnail_after = restarted.get("/api/scans/last/thumbnail").content

    assert thumbnail_after == thumbnail_before


def test_a_render_that_a_crash_left_pending_is_finished_at_start_up(configuration, tmp_path):
    with build_client(configuration, ONE_PHOTO) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        scan_once(client)
        repository = FileSystemQuickScanSlotRepository(slot_folder(configuration), AtomicFileWriter(), FixedClock(None))
        slot = repository.load()
        turned = slot.last_scan.with_framing(slot.last_scan.framing.turned_clockwise())
        repository.commit(dataclasses.replace(slot, last_scan=turned, render_pending=True))
        size_before = read_image_size(configuration.default_output_folder / slot.last_scan.saved_files[0].file_name)
        restarted_configuration = copy_the_disk_to_a_new_run(configuration, tmp_path)
    with build_client(restarted_configuration, ONE_PHOTO) as restarted:
        state = restarted.get("/api/state").json()
        size_after = read_image_size(last_result_paths(state)[0])
    restarted_repository = FileSystemQuickScanSlotRepository(
        slot_folder(restarted_configuration), AtomicFileWriter(), FixedClock(None)
    )

    assert size_after == size_before[::-1]
    assert restarted_repository.load().render_pending is False


def test_a_new_scan_replaces_the_master_and_keeps_the_files_of_the_old_one(configuration):
    with build_client(configuration, ONE_PHOTO) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        first = scan_once(client)
        second = scan_once(client)

    masters = [path.name for path in slot_folder(configuration).glob("master-*.jpg")]
    assert masters == [f"master-{second['last_result']['scan_identifier']}.jpg"]
    assert len(list(configuration.default_output_folder.iterdir())) == 2
    assert first["last_result"]["scan_identifier"] != second["last_result"]["scan_identifier"]


def test_the_edit_routes_refuse_a_request_without_the_header(configuration):
    with build_client(configuration, ONE_PHOTO) as client:
        responses = [
            client.post("/api/scans/last/rotation"),
            client.put("/api/scans/last/crops", json={"crops": []}),
            client.post("/api/scans/last/crops/detect"),
        ]

    assert [response.status_code for response in responses] == [403, 403, 403]


@contextlib.contextmanager
def scan_in_progress(configuration: ApplicationConfiguration) -> Iterator[tuple[TestClient, str]]:
    """A client whose second scan is held in its first poll until the block ends; yields it and the last scan."""
    gate = threading.Event()

    async def wait_for_the_gate(seconds: float) -> None:
        while not gate.is_set():
            await asyncio.sleep(0.001)

    slow_scanner = FakeScannerBehavior(scene=PhotoScene.PHOTOS_ONE, busy_polls_before_document=1)
    with build_client(configuration, slow_scanner, wait_for_the_gate) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        gate.set()
        scan_once(client)
        gate.clear()
        identifier = client.get("/api/state").json()["last_result"]["scan_identifier"]
        # The test client holds the answer of a scan until its background task ends, so the scan runs apart.
        post_the_scan = functools.partial(client.post, "/api/scans", headers=STATE_CHANGING_HEADERS)
        scanning = threading.Thread(target=post_the_scan)
        scanning.start()
        wait_for_state(client, lambda state: state["scan_phase"] != "idle")
        try:
            yield client, identifier
        finally:
            gate.set()
            scanning.join()


def test_the_rotation_answers_409_during_a_scan(configuration):
    with scan_in_progress(configuration) as (client, _):
        response = turn_last_scan(client)

    assert (response.status_code, response.json()["code"]) == (409, "scan_already_running")


def test_the_crops_answer_409_during_a_scan(configuration):
    with scan_in_progress(configuration) as (client, _):
        response = put_last_crops(client, [])

    assert (response.status_code, response.json()["code"]) == (409, "scan_already_running")


def test_the_detection_answers_409_during_a_scan(configuration):
    with scan_in_progress(configuration) as (client, _):
        response = detect_last_crops(client)

    assert (response.status_code, response.json()["code"]) == (409, "scan_already_running")


def test_the_thumbnail_is_still_served_during_a_scan(configuration):
    with scan_in_progress(configuration) as (client, _):
        thumbnail = client.get("/api/scans/last/thumbnail")

    assert thumbnail.status_code == 200


def test_the_enlarged_view_is_still_served_during_a_scan(configuration):
    with scan_in_progress(configuration) as (client, identifier):
        preview = client.get(f"/api/scans/last/preview?scan_identifier={identifier}&rotation_degrees=0")

    assert preview.status_code == 200

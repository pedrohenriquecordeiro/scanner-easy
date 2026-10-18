"""The frame, the rotation of a page and the quick-mode crop through the whole application, at 75 dots per inch."""

import asyncio
import io
import shutil
import time
from collections.abc import Callable
from pathlib import Path

import httpx
import pikepdf
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from digitalizadora.application_factory import create_application
from digitalizadora.composition_root import DRAFTS_FOLDER_NAME, ContainerOverrides, build_container
from digitalizadora.configuration import ApplicationConfiguration
from digitalizadora.domain.document_draft_reconciliation import page_file_name
from digitalizadora.infrastructure.escl.escl_scanner_gateway import EsclGatewayTiming
from digitalizadora.repositories.file_system_document_draft_repository import CURRENT_DRAFT_FOLDER_NAME
from digitalizadora.simulator.fake_escl_scanner_app import (
    FakeScannerBehavior,
    LidBackground,
    create_fake_escl_scanner_app,
)
from tests.fakes.configuration_builder import TEST_PORT, build_application_configuration
from tests.fakes.document_drafts import seed_draft_folder
from tests.fakes.sample_images import build_sample_jpeg

BASE_ADDRESS = f"http://127.0.0.1:{TEST_PORT}"
SCANNER_ADDRESS = "http://scanner.test/eSCL"
STATE_CHANGING_HEADERS = {"X-Requested-With": "digitalizadora"}
ABUNDANT_FREE_SPACE_BYTES = 100 * 1024**3
MAXIMUM_STATE_POLLS = 2500
STATE_POLL_INTERVAL_SECONDS = 0.002
POINTS_PER_INCH = 72
DOTS_PER_INCH = 75
GLASS_SIZE = (2550 * DOTS_PER_INCH // 300, 3508 * DOTS_PER_INCH // 300)
CROP_MARGIN_PIXELS = round(0.01 * max(GLASS_SIZE))
SHEET_SIZE_ON_DARK_LID = (
    round(0.65 * GLASS_SIZE[0]) + 2 * CROP_MARGIN_PIXELS,
    round(0.75 * GLASS_SIZE[1]) + 2 * CROP_MARGIN_PIXELS,
)
SIZE_TOLERANCE_PIXELS = 8


async def yield_without_waiting(seconds: float) -> None:
    await asyncio.sleep(0)


def read_abundant_free_space(folder: Path) -> int:
    return ABUNDANT_FREE_SPACE_BYTES


def build_client(configuration: ApplicationConfiguration, lid_background: LidBackground) -> TestClient:
    scanner_application = create_fake_escl_scanner_app(FakeScannerBehavior(lid_background=lid_background))
    overrides = ContainerOverrides(
        scanner_transport=httpx.ASGITransport(app=scanner_application),
        gateway_timing=EsclGatewayTiming(sleep=yield_without_waiting),
        free_space_reader=read_abundant_free_space,
    )
    container = build_container(configuration, overrides)
    return TestClient(create_application(container.controllers, container.web_configuration), base_url=BASE_ADDRESS)


def wait_for_state(client: TestClient, condition: Callable[[dict], bool]) -> dict:
    state: dict = {}
    for _ in range(MAXIMUM_STATE_POLLS):
        state = client.get("/api/state").json()
        if condition(state):
            return state
        time.sleep(STATE_POLL_INTERVAL_SECONDS)
    raise AssertionError(f"The expected state never arrived; last state: {state}")


def save_settings(client: TestClient, output_folder: Path, **changes: object) -> dict:
    body = {"output_folder": str(output_folder), "output_format": "jpg", "dots_per_inch": DOTS_PER_INCH, **changes}
    response = client.put("/api/settings", json=body, headers=STATE_CHANGING_HEADERS)
    assert response.status_code == 200
    return response.json()


def has_finished_a_scan(state: dict) -> bool:
    return state["scan_phase"] == "idle" and state["last_result"] is not None


def has_document_pages(expected_count: int) -> Callable[[dict], bool]:
    return lambda state: state["scan_phase"] == "idle" and state["document"]["page_count"] == expected_count


def read_scanned_file_size(client: TestClient) -> tuple[int, int]:
    last_result = client.get("/api/state").json()["last_result"]
    with Image.open(Path(last_result["output_folder"]) / last_result["file_name"]) as image:
        return image.size


@pytest.fixture
def configuration(tmp_path: Path) -> ApplicationConfiguration:
    return build_application_configuration(tmp_path, SCANNER_ADDRESS)


def test_quick_scan_without_adjustment_has_the_size_of_the_glass(configuration: ApplicationConfiguration) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        save_settings(client, configuration.default_output_folder)
        client.post("/api/scans", headers=STATE_CHANGING_HEADERS)
        wait_for_state(client, has_finished_a_scan)
        assert read_scanned_file_size(client) == GLASS_SIZE


def test_quick_scan_with_the_crop_on_a_white_page_keeps_the_whole_glass(
    configuration: ApplicationConfiguration,
) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        client.post("/api/scans", headers=STATE_CHANGING_HEADERS)
        wait_for_state(client, has_finished_a_scan)
        assert read_scanned_file_size(client) == GLASS_SIZE


def test_quick_scan_with_the_crop_against_the_dark_lid_keeps_only_the_sheet(
    configuration: ApplicationConfiguration,
) -> None:
    with build_client(configuration, LidBackground.DARK) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        client.post("/api/scans", headers=STATE_CHANGING_HEADERS)
        wait_for_state(client, has_finished_a_scan)
        width, height = read_scanned_file_size(client)
    assert abs(width - SHEET_SIZE_ON_DARK_LID[0]) <= SIZE_TOLERANCE_PIXELS
    assert abs(height - SHEET_SIZE_ON_DARK_LID[1]) <= SIZE_TOLERANCE_PIXELS


def test_quick_scan_without_the_crop_against_the_dark_lid_keeps_the_whole_glass(
    configuration: ApplicationConfiguration,
) -> None:
    with build_client(configuration, LidBackground.DARK) as client:
        save_settings(client, configuration.default_output_folder)
        client.post("/api/scans", headers=STATE_CHANGING_HEADERS)
        wait_for_state(client, has_finished_a_scan)
        assert read_scanned_file_size(client) == GLASS_SIZE


def test_the_saved_adjustments_are_served_back_after_a_scan(configuration: ApplicationConfiguration) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        saved_settings = save_settings(
            client, configuration.default_output_folder, auto_crop=True, color_mode="grayscale"
        )
        state_settings = client.get("/api/state").json()["settings"]
    assert state_settings == saved_settings
    assert (state_settings["color_mode"], state_settings["auto_crop"]) == ("grayscale", True)


def test_the_settings_no_longer_carry_a_preset_or_a_rotation(configuration: ApplicationConfiguration) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        settings = save_settings(client, configuration.default_output_folder)
    assert "scan_preset" not in settings and "rotation_degrees" not in settings


def add_document_page(client: TestClient, expected_page_count: int) -> None:
    response = client.post("/api/document/pages", headers=STATE_CHANGING_HEADERS)
    assert response.status_code == 202
    wait_for_state(client, has_document_pages(expected_page_count))


def read_pages(client: TestClient) -> list[dict]:
    return client.get("/api/document").json()["document"]["pages"]


def put_crop(client: TestClient, page_identifier: str, crop: dict | None) -> object:
    return client.put(
        f"/api/document/pages/{page_identifier}/crop", json={"crop": crop}, headers=STATE_CHANGING_HEADERS
    )


def read_page_file_bytes(configuration: ApplicationConfiguration, page_identifier: str) -> bytes:
    page_path = (
        configuration.data_directory / DRAFTS_FOLDER_NAME / CURRENT_DRAFT_FOLDER_NAME / page_file_name(page_identifier)
    )
    return page_path.read_bytes()


def read_pdf_page_sizes(finalization: dict) -> list[tuple[float, float]]:
    with pikepdf.open(Path(finalization["output_folder"]) / finalization["file_name"]) as document:
        return [(float(page.mediabox[2]), float(page.mediabox[3])) for page in document.pages]


def finalize(client: TestClient) -> dict:
    response = client.post("/api/document/finalize", headers=STATE_CHANGING_HEADERS)
    assert response.status_code == 200
    return response.json()


def test_document_page_against_the_dark_lid_gets_the_frame_of_the_sheet(
    configuration: ApplicationConfiguration,
) -> None:
    with build_client(configuration, LidBackground.DARK) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        add_document_page(client, 1)
        crop = read_pages(client)[0]["crop"]
    margin = CROP_MARGIN_PIXELS / GLASS_SIZE[0]
    assert crop["left"] == pytest.approx(0.15 - margin, abs=0.03)
    assert crop["right"] == pytest.approx(0.80 + margin, abs=0.03)
    assert crop["top"] == pytest.approx(0.10 - CROP_MARGIN_PIXELS / GLASS_SIZE[1], abs=0.03)
    assert crop["bottom"] == pytest.approx(0.85 + CROP_MARGIN_PIXELS / GLASS_SIZE[1], abs=0.03)


def test_document_page_against_the_dark_lid_keeps_the_scanner_image(configuration: ApplicationConfiguration) -> None:
    with build_client(configuration, LidBackground.DARK) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        add_document_page(client, 1)
        page_file = read_page_file_bytes(configuration, read_pages(client)[0]["page_identifier"])
    assert read_page_size_of(page_file) == GLASS_SIZE


def read_page_size_of(jpeg_content: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(jpeg_content)) as image:
        return image.size


def test_document_page_without_the_crop_checkbox_has_no_frame(configuration: ApplicationConfiguration) -> None:
    with build_client(configuration, LidBackground.DARK) as client:
        save_settings(client, configuration.default_output_folder)
        add_document_page(client, 1)
        assert read_pages(client)[0]["crop"] is None


def test_document_page_on_a_white_page_with_the_crop_checkbox_has_no_frame(
    configuration: ApplicationConfiguration,
) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        add_document_page(client, 1)
        assert read_pages(client)[0]["crop"] is None


def test_a_framed_page_is_saved_with_the_physical_size_of_its_frame(configuration: ApplicationConfiguration) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        save_settings(client, configuration.default_output_folder)
        add_document_page(client, 1)
        page_identifier = read_pages(client)[0]["page_identifier"]
        put_crop(client, page_identifier, {"left": 0.1, "top": 0.2, "right": 0.6, "bottom": 0.7})
        finalization = finalize(client)
    points_per_pixel = POINTS_PER_INCH / DOTS_PER_INCH
    expected_size = (0.5 * GLASS_SIZE[0] * points_per_pixel, 0.5 * GLASS_SIZE[1] * points_per_pixel)
    assert read_pdf_page_sizes(finalization)[0] == pytest.approx(expected_size, abs=2.0)


def test_a_framed_and_rotated_page_is_saved_with_the_turned_size_of_its_frame(
    configuration: ApplicationConfiguration,
) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        save_settings(client, configuration.default_output_folder)
        add_document_page(client, 1)
        page_identifier = read_pages(client)[0]["page_identifier"]
        put_crop(client, page_identifier, {"left": 0.0, "top": 0.0, "right": 0.5, "bottom": 1.0})
        client.post(f"/api/document/pages/{page_identifier}/rotation", headers=STATE_CHANGING_HEADERS)
        finalization = finalize(client)
    points_per_pixel = POINTS_PER_INCH / DOTS_PER_INCH
    expected_size = (GLASS_SIZE[1] * points_per_pixel, 0.5 * GLASS_SIZE[0] * points_per_pixel)
    assert read_pdf_page_sizes(finalization)[0] == pytest.approx(expected_size, abs=2.0)


def test_the_frame_turns_with_the_page(configuration: ApplicationConfiguration) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        save_settings(client, configuration.default_output_folder)
        add_document_page(client, 1)
        page_identifier = read_pages(client)[0]["page_identifier"]
        put_crop(client, page_identifier, {"left": 0.0, "top": 0.0, "right": 0.5, "bottom": 1.0})
        client.post(f"/api/document/pages/{page_identifier}/rotation", headers=STATE_CHANGING_HEADERS)
        page = read_pages(client)[0]
    assert (page["rotation_degrees"], page["crop"]) == (90, {"left": 0.0, "top": 0.0, "right": 1.0, "bottom": 0.5})


def test_four_turns_bring_the_page_and_its_frame_back(configuration: ApplicationConfiguration) -> None:
    crop = {"left": 0.1, "top": 0.2, "right": 0.5, "bottom": 0.9}
    with build_client(configuration, LidBackground.WHITE) as client:
        save_settings(client, configuration.default_output_folder)
        add_document_page(client, 1)
        page_identifier = read_pages(client)[0]["page_identifier"]
        put_crop(client, page_identifier, crop)
        for _ in range(4):
            client.post(f"/api/document/pages/{page_identifier}/rotation", headers=STATE_CHANGING_HEADERS)
        page = read_pages(client)[0]
    assert (page["rotation_degrees"], page["crop"]) == (0, crop)


def test_the_stored_page_never_changes_with_the_frame_and_the_rotation(configuration: ApplicationConfiguration) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        save_settings(client, configuration.default_output_folder)
        add_document_page(client, 1)
        page_identifier = read_pages(client)[0]["page_identifier"]
        page_before = read_page_file_bytes(configuration, page_identifier)
        put_crop(client, page_identifier, {"left": 0.1, "top": 0.1, "right": 0.9, "bottom": 0.9})
        client.post(f"/api/document/pages/{page_identifier}/rotation", headers=STATE_CHANGING_HEADERS)
        client.post(f"/api/document/pages/{page_identifier}/crop/detect", headers=STATE_CHANGING_HEADERS)
        page_after = read_page_file_bytes(configuration, page_identifier)
    assert page_after == page_before


def test_rotating_a_page_of_the_draft_keeps_its_identifier(configuration: ApplicationConfiguration) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        save_settings(client, configuration.default_output_folder)
        add_document_page(client, 1)
        page_identifier = read_pages(client)[0]["page_identifier"]
        response = client.post(f"/api/document/pages/{page_identifier}/rotation", headers=STATE_CHANGING_HEADERS)
    assert response.json()["document"]["pages"][0]["page_identifier"] == page_identifier


def test_document_with_a_resumed_page_and_a_rotated_page_is_saved_as_one_pdf(
    configuration: ApplicationConfiguration,
) -> None:
    resumed_page_size = (64, 48)
    seed_draft_folder(
        configuration.data_directory / DRAFTS_FOLDER_NAME, [build_sample_jpeg(*resumed_page_size, POINTS_PER_INCH)]
    )
    with build_client(configuration, LidBackground.WHITE) as client:
        save_settings(client, configuration.default_output_folder)
        add_document_page(client, 2)
        resumed_and_scanned_pages = read_pages(client)
        second_page_identifier = resumed_and_scanned_pages[1]["page_identifier"]
        client.post(f"/api/document/pages/{second_page_identifier}/rotation", headers=STATE_CHANGING_HEADERS)
        finalization = finalize(client)
    points_per_pixel = POINTS_PER_INCH / DOTS_PER_INCH
    rotated_page_size = (GLASS_SIZE[1] * points_per_pixel, GLASS_SIZE[0] * points_per_pixel)
    page_sizes = read_pdf_page_sizes(finalization)
    assert [*page_sizes[0], *page_sizes[1]] == pytest.approx([*resumed_page_size, *rotated_page_size], abs=1.0)


def test_detecting_the_crop_of_a_page_against_the_dark_lid_stores_the_frame(
    configuration: ApplicationConfiguration,
) -> None:
    with build_client(configuration, LidBackground.DARK) as client:
        save_settings(client, configuration.default_output_folder)
        add_document_page(client, 1)
        page_identifier = read_pages(client)[0]["page_identifier"]
        response = client.post(f"/api/document/pages/{page_identifier}/crop/detect", headers=STATE_CHANGING_HEADERS)
    body = response.json()
    assert (response.status_code, body["crop_detected"]) == (200, True)
    assert body["document"]["pages"][0]["crop"]["left"] == pytest.approx(0.15, abs=0.03)


def test_detecting_the_crop_of_a_white_page_finds_nothing_and_changes_nothing(
    configuration: ApplicationConfiguration,
) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        save_settings(client, configuration.default_output_folder)
        add_document_page(client, 1)
        page_identifier = read_pages(client)[0]["page_identifier"]
        revision_before = client.get("/api/document").json()["revision"]
        response = client.post(f"/api/document/pages/{page_identifier}/crop/detect", headers=STATE_CHANGING_HEADERS)
    assert (response.json()["crop_detected"], response.json()["revision"]) == (False, revision_before)


def test_a_frame_of_the_whole_page_removes_the_frame(configuration: ApplicationConfiguration) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        save_settings(client, configuration.default_output_folder)
        add_document_page(client, 1)
        page_identifier = read_pages(client)[0]["page_identifier"]
        put_crop(client, page_identifier, {"left": 0.1, "top": 0.1, "right": 0.9, "bottom": 0.9})
        put_crop(client, page_identifier, {"left": 0, "top": 0, "right": 1, "bottom": 1})
        assert read_pages(client)[0]["crop"] is None


@pytest.mark.parametrize(
    "invalid_crop",
    [
        {"left": 0.6, "top": 0, "right": 0.4, "bottom": 1},
        {"left": 0, "top": 0, "right": 1.2, "bottom": 1},
        {"left": 0, "top": 0, "right": 0.01, "bottom": 1},
        {"left": 0, "top": 0, "right": 1},
        {"left": 10**400, "top": 0, "right": 1, "bottom": 1},
        "whole",
    ],
)
def test_an_invalid_frame_answers_invalid_crop_and_changes_nothing(
    configuration: ApplicationConfiguration, invalid_crop: object
) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        save_settings(client, configuration.default_output_folder)
        add_document_page(client, 1)
        page_identifier = read_pages(client)[0]["page_identifier"]
        response = put_crop(client, page_identifier, invalid_crop)
        assert read_pages(client)[0]["crop"] is None
    assert (response.status_code, response.json()["code"]) == (422, "invalid_crop")


def test_the_frame_of_a_page_that_is_not_in_the_draft_answers_page_not_found(
    configuration: ApplicationConfiguration,
) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        save_settings(client, configuration.default_output_folder)
        add_document_page(client, 1)
        response = put_crop(client, "00000000000000ff", None)
    assert (response.status_code, response.json()["code"]) == (404, "page_not_found")


def test_the_thumbnail_is_turned_by_the_address(configuration: ApplicationConfiguration) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        save_settings(client, configuration.default_output_folder)
        add_document_page(client, 1)
        page_identifier = read_pages(client)[0]["page_identifier"]
        unturned = client.get(f"/api/document/pages/{page_identifier}/thumbnail")
        turned = client.get(f"/api/document/pages/{page_identifier}/thumbnail?rotation_degrees=90")
    assert read_page_size_of(turned.content) == read_page_size_of(unturned.content)[::-1]


def test_the_preview_is_the_page_as_displayed_with_a_cache_header(configuration: ApplicationConfiguration) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        save_settings(client, configuration.default_output_folder)
        add_document_page(client, 1)
        page_identifier = read_pages(client)[0]["page_identifier"]
        response = client.get(f"/api/document/pages/{page_identifier}/preview?rotation_degrees=90")
    assert (response.status_code, response.headers["cache-control"]) == (
        200,
        "private, max-age=31536000, immutable",
    )
    assert read_page_size_of(response.content) == GLASS_SIZE[::-1]


@pytest.mark.parametrize("view", ["thumbnail", "preview"])
def test_a_rotation_outside_the_four_quarters_is_refused(configuration: ApplicationConfiguration, view: str) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        response = client.get(f"/api/document/pages/00000000000000ff/{view}?rotation_degrees=45")
    assert (response.status_code, response.json()["code"]) == (422, "invalid_page_rotation")


def test_the_preview_of_a_page_that_is_not_in_the_draft_answers_page_not_found(
    configuration: ApplicationConfiguration,
) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        save_settings(client, configuration.default_output_folder)
        add_document_page(client, 1)
        response = client.get("/api/document/pages/00000000000000ff/preview")
    assert (response.status_code, response.json()["code"]) == (404, "page_not_found")


def test_the_frame_and_the_rotation_survive_a_restart(configuration: ApplicationConfiguration, tmp_path: Path) -> None:
    with build_client(configuration, LidBackground.DARK) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        add_document_page(client, 1)
        page_identifier = read_pages(client)[0]["page_identifier"]
        client.post(f"/api/document/pages/{page_identifier}/rotation", headers=STATE_CHANGING_HEADERS)
        framed_page = read_pages(client)[0]
        # The first process is gone without a word: what is on the disk is all the next one has.
        restarted_configuration = build_application_configuration(tmp_path / "restart", SCANNER_ADDRESS)
        shutil.copytree(
            configuration.data_directory / DRAFTS_FOLDER_NAME,
            restarted_configuration.data_directory / DRAFTS_FOLDER_NAME,
        )
    with build_client(restarted_configuration, LidBackground.DARK) as restarted_client:
        resumed_page = read_pages(restarted_client)[0]
    assert (resumed_page["rotation_degrees"], resumed_page["crop"]) == (90, framed_page["crop"])
    assert resumed_page["crop"] is not None


def test_a_restart_leaves_no_temporary_file_of_the_manifest(configuration: ApplicationConfiguration) -> None:
    with build_client(configuration, LidBackground.DARK) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        add_document_page(client, 1)
        client.post(
            f"/api/document/pages/{read_pages(client)[0]['page_identifier']}/rotation", headers=STATE_CHANGING_HEADERS
        )
    draft_folder = configuration.data_directory / DRAFTS_FOLDER_NAME / CURRENT_DRAFT_FOLDER_NAME
    assert [entry.name for entry in draft_folder.iterdir() if entry.name.endswith(".part")] == []


def test_rotating_a_page_that_is_not_in_the_draft_answers_page_not_found(
    configuration: ApplicationConfiguration,
) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        save_settings(client, configuration.default_output_folder)
        add_document_page(client, 1)
        response = client.post("/api/document/pages/00000000000000ff/rotation", headers=STATE_CHANGING_HEADERS)
    assert (response.status_code, response.json()["code"]) == (404, "page_not_found")


def test_rotating_without_the_request_header_is_refused(configuration: ApplicationConfiguration) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        response = client.post("/api/document/pages/00000000000000ff/rotation")
    assert (response.status_code, response.json()["code"]) == (403, "missing_request_header")


def test_the_new_routes_refuse_a_request_without_the_header(configuration: ApplicationConfiguration) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        crop_response = client.put("/api/document/pages/00000000000000ff/crop", json={"crop": None})
        detect_response = client.post("/api/document/pages/00000000000000ff/crop/detect")
        last_scan_response = client.post("/api/scans/last/rotation")
    assert [response.status_code for response in (crop_response, detect_response, last_scan_response)] == [403] * 3


def scan_once(client: TestClient, configuration: ApplicationConfiguration, output_format: str) -> None:
    save_settings(client, configuration.default_output_folder, output_format=output_format)
    scans_before = client.get("/api/state").json()["scans_completed"]
    client.post("/api/scans", headers=STATE_CHANGING_HEADERS)
    wait_for_state(client, lambda state: state["scan_phase"] == "idle" and state["scans_completed"] == scans_before + 1)


def rotate_last_scan(client: TestClient) -> object:
    return client.post("/api/scans/last/rotation", headers=STATE_CHANGING_HEADERS)


def read_last_file(client: TestClient) -> Path:
    last_result = client.get("/api/state").json()["last_result"]
    return Path(last_result["output_folder"]) / last_result["file_name"]


def test_a_quick_jpg_is_turned_in_its_own_file(configuration: ApplicationConfiguration) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        scan_once(client, configuration, "jpg")
        file_name = client.get("/api/state").json()["last_result"]["file_name"]
        response = rotate_last_scan(client)
        turned_size = read_page_size_of(read_last_file(client).read_bytes())
    assert (response.status_code, response.json()["last_result"]["file_name"]) == (200, file_name)
    assert turned_size == GLASS_SIZE[::-1]


def test_a_quick_jpg_keeps_its_density_when_turned(configuration: ApplicationConfiguration) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        scan_once(client, configuration, "jpg")
        rotate_last_scan(client)
        with Image.open(read_last_file(client)) as image:
            density = image.info["dpi"]
    assert round(density[0]) == DOTS_PER_INCH


def test_a_quick_pdf_only_gets_a_quarter_turn_on_its_page(configuration: ApplicationConfiguration) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        scan_once(client, configuration, "pdf")
        image_stream_before = read_pdf_image_stream(read_last_file(client))
        response = rotate_last_scan(client)
        turned_file = read_last_file(client)
    with pikepdf.open(turned_file) as document:
        rotation = int(document.pages[0].obj.get("/Rotate", 0))
    assert (response.status_code, rotation) == (200, 90)
    assert read_pdf_image_stream(turned_file) == image_stream_before


def read_pdf_image_stream(pdf_path: Path) -> bytes:
    with pikepdf.open(pdf_path) as document:
        return next(iter(document.pages[0].get_images().values())).read_raw_bytes()


def test_two_quick_turns_in_a_row_add_up_to_a_half_turn(configuration: ApplicationConfiguration) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        scan_once(client, configuration, "pdf")
        rotate_last_scan(client)
        rotate_last_scan(client)
        with pikepdf.open(read_last_file(client)) as document:
            rotation = int(document.pages[0].obj.get("/Rotate", 0))
    assert rotation == 180


def test_turning_the_last_scan_raises_the_revision_and_turns_the_thumbnail(
    configuration: ApplicationConfiguration,
) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        scan_once(client, configuration, "jpg")
        revision_before = client.get("/api/state").json()["last_result_revision"]
        thumbnail_before = client.get("/api/scans/last/thumbnail").content
        rotate_last_scan(client)
        revision_after = client.get("/api/state").json()["last_result_revision"]
        thumbnail_after = client.get("/api/scans/last/thumbnail").content
    assert revision_after == revision_before + 1
    assert read_page_size_of(thumbnail_after) == read_page_size_of(thumbnail_before)[::-1]


def test_the_state_reports_the_new_size_of_the_turned_file(configuration: ApplicationConfiguration) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        scan_once(client, configuration, "jpg")
        rotate_last_scan(client)
        reported_size = client.get("/api/state").json()["last_result"]["size_in_bytes"]
        actual_size = read_last_file(client).stat().st_size
    assert reported_size == actual_size


def test_turning_the_last_scan_before_any_scan_answers_no_last_scan(configuration: ApplicationConfiguration) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        response = rotate_last_scan(client)
    assert (response.status_code, response.json()["code"]) == (404, "no_last_scan")


def test_a_document_page_is_not_a_last_scan_to_turn(configuration: ApplicationConfiguration) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        save_settings(client, configuration.default_output_folder)
        add_document_page(client, 1)
        response = rotate_last_scan(client)
    assert (response.status_code, response.json()["code"]) == (404, "no_last_scan")


def test_turning_a_last_scan_that_was_deleted_answers_last_scan_file_missing(
    configuration: ApplicationConfiguration,
) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        scan_once(client, configuration, "jpg")
        read_last_file(client).unlink()
        response = rotate_last_scan(client)
    assert (response.status_code, response.json()["code"]) == (409, "last_scan_file_missing")

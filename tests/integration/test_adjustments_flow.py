"""Rotation, crop and quality through the whole application against the fake printer, at 75 dots per inch."""

import asyncio
import io
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


def read_draft_page_size(
    configuration: ApplicationConfiguration, page_position: int, client: TestClient
) -> tuple[int, int]:
    pages = client.get("/api/document").json()["document"]["pages"]
    page_path = (
        configuration.data_directory
        / DRAFTS_FOLDER_NAME
        / CURRENT_DRAFT_FOLDER_NAME
        / page_file_name(pages[page_position - 1]["page_identifier"])
    )
    with Image.open(io.BytesIO(page_path.read_bytes())) as image:
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


def test_quick_scan_with_a_quarter_turn_swaps_the_dimensions(configuration: ApplicationConfiguration) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        save_settings(client, configuration.default_output_folder, rotation_degrees=90)
        client.post("/api/scans", headers=STATE_CHANGING_HEADERS)
        wait_for_state(client, has_finished_a_scan)
        assert read_scanned_file_size(client) == GLASS_SIZE[::-1]


def test_quick_scan_with_a_half_turn_keeps_the_dimensions(configuration: ApplicationConfiguration) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        save_settings(client, configuration.default_output_folder, rotation_degrees=180)
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


def test_document_page_against_the_dark_lid_is_cropped(configuration: ApplicationConfiguration) -> None:
    with build_client(configuration, LidBackground.DARK) as client:
        save_settings(client, configuration.default_output_folder, auto_crop=True)
        client.post("/api/document/pages", headers=STATE_CHANGING_HEADERS)
        wait_for_state(client, has_document_pages(1))
        width, height = read_draft_page_size(configuration, 1, client)
    assert abs(width - SHEET_SIZE_ON_DARK_LID[0]) <= SIZE_TOLERANCE_PIXELS
    assert abs(height - SHEET_SIZE_ON_DARK_LID[1]) <= SIZE_TOLERANCE_PIXELS


def test_document_page_with_a_quarter_turn_swaps_the_dimensions(configuration: ApplicationConfiguration) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        save_settings(client, configuration.default_output_folder, rotation_degrees=90)
        client.post("/api/document/pages", headers=STATE_CHANGING_HEADERS)
        wait_for_state(client, has_document_pages(1))
        assert read_draft_page_size(configuration, 1, client) == GLASS_SIZE[::-1]


def test_document_with_a_resumed_page_and_a_rotated_page_is_saved_as_one_pdf(
    configuration: ApplicationConfiguration,
) -> None:
    resumed_page_size = (64, 48)
    seed_draft_folder(
        configuration.data_directory / DRAFTS_FOLDER_NAME, [build_sample_jpeg(*resumed_page_size, POINTS_PER_INCH)]
    )
    with build_client(configuration, LidBackground.WHITE) as client:
        save_settings(client, configuration.default_output_folder, rotation_degrees=90)
        client.post("/api/document/pages", headers=STATE_CHANGING_HEADERS)
        wait_for_state(client, has_document_pages(2))
        finalization = client.post("/api/document/finalize", headers=STATE_CHANGING_HEADERS).json()
    with pikepdf.open(Path(finalization["output_folder"]) / finalization["file_name"]) as document:
        page_sizes = [(float(page.mediabox[2]), float(page.mediabox[3])) for page in document.pages]
    points_per_pixel = POINTS_PER_INCH / DOTS_PER_INCH
    rotated_page_size = (GLASS_SIZE[1] * points_per_pixel, GLASS_SIZE[0] * points_per_pixel)
    assert [*page_sizes[0], *page_sizes[1]] == pytest.approx([*resumed_page_size, *rotated_page_size], abs=1.0)


def test_the_saved_adjustments_are_served_back_after_a_scan(configuration: ApplicationConfiguration) -> None:
    with build_client(configuration, LidBackground.WHITE) as client:
        saved_settings = save_settings(
            client, configuration.default_output_folder, rotation_degrees=270, auto_crop=True, color_mode="grayscale"
        )
        state_settings = client.get("/api/state").json()["settings"]
    assert state_settings == saved_settings
    assert (state_settings["rotation_degrees"], state_settings["auto_crop"]) == (270, True)

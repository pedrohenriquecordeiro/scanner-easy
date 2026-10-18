"""What the integration tests of the frames and of the quick-mode slot share: the whole application over the
fake scanner, at 75 dots per inch so that a scan takes a few milliseconds."""

import asyncio
import io
import time
from collections.abc import Callable
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from PIL import Image

from digitalizadora.application_factory import create_application
from digitalizadora.composition_root import ContainerOverrides, build_container
from digitalizadora.configuration import ApplicationConfiguration
from digitalizadora.infrastructure.escl.escl_scanner_gateway import EsclGatewayTiming
from digitalizadora.simulator.fake_escl_scanner_app import FakeScannerBehavior, create_fake_escl_scanner_app
from tests.fakes.configuration_builder import TEST_PORT

BASE_ADDRESS = f"http://127.0.0.1:{TEST_PORT}"
SCANNER_ADDRESS = "http://scanner.test/eSCL"
STATE_CHANGING_HEADERS = {"X-Requested-With": "digitalizadora"}
ABUNDANT_FREE_SPACE_BYTES = 100 * 1024**3
MAXIMUM_STATE_POLLS = 2500
STATE_POLL_INTERVAL_SECONDS = 0.002
DOTS_PER_INCH = 75
GLASS_SIZE = (2550 * DOTS_PER_INCH // 300, 3508 * DOTS_PER_INCH // 300)
MARKER_COLORS = {"left": (230, 0, 230), "right": (0, 200, 0)}
MARKER_TOLERANCE = 70
MARKER_INSET_SHARE = 0.12


async def yield_without_waiting(seconds: float) -> None:
    await asyncio.sleep(0)


def read_abundant_free_space(folder: Path) -> int:
    return ABUNDANT_FREE_SPACE_BYTES


def build_client(configuration: ApplicationConfiguration, behavior: FakeScannerBehavior) -> TestClient:
    scanner_application = create_fake_escl_scanner_app(behavior)
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


def scan_once(client: TestClient) -> dict:
    """A quick scan, waited for; answers the state after it."""
    scans_before = client.get("/api/state").json()["scans_completed"]
    response = client.post("/api/scans", headers=STATE_CHANGING_HEADERS)
    assert response.status_code == 202
    return wait_for_state(
        client, lambda state: state["scan_phase"] == "idle" and state["scans_completed"] == scans_before + 1
    )


def add_document_page(client: TestClient, expected_page_count: int) -> None:
    response = client.post("/api/document/pages", headers=STATE_CHANGING_HEADERS)
    assert response.status_code == 202
    wait_for_state(
        client,
        lambda state: state["scan_phase"] == "idle" and state["document"]["page_count"] == expected_page_count,
    )


def read_pages(client: TestClient) -> list[dict]:
    return client.get("/api/document").json()["document"]["pages"]


def last_result_paths(state: dict) -> list[Path]:
    last_result = state["last_result"]
    return [Path(last_result["output_folder"]) / file_name for file_name in last_result["file_names"]]


def corners_of(crop: dict) -> list[tuple[float, float]]:
    return [
        (crop[role]["x"], crop[role]["y"]) for role in ("top_left", "top_right", "bottom_right", "bottom_left")
    ]


def crop_body(corners: list[tuple[float, float]]) -> dict:
    roles = ("top_left", "top_right", "bottom_right", "bottom_left")
    return {role: {"x": x, "y": y} for role, (x, y) in zip(roles, corners, strict=True)}


def read_image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def has_upright_markers(image: Image.Image) -> bool:
    """The photo was cut out upright: its magenta block is at the top left and its green block at the top right."""
    rgb_image = image.convert("RGB")
    width, height = rgb_image.size
    inset = max(2, round(MARKER_INSET_SHARE * min(width, height)))
    left_pixel = rgb_image.getpixel((inset, inset))
    right_pixel = rgb_image.getpixel((width - 1 - inset, inset))
    return _is_close(left_pixel, MARKER_COLORS["left"]) and _is_close(right_pixel, MARKER_COLORS["right"])


def _is_close(pixel: tuple[int, int, int], color: tuple[int, int, int]) -> bool:
    return all(abs(found - wanted) < MARKER_TOLERANCE for found, wanted in zip(pixel, color, strict=True))


def open_image(content: bytes) -> Image.Image:
    return Image.open(io.BytesIO(content))

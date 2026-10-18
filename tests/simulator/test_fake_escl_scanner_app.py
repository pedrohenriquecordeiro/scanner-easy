import io
import uuid
from http import HTTPStatus
from urllib.parse import urlsplit

import httpx
import pytest
from PIL import Image

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanner_status import ScannerState
from digitalizadora.infrastructure.escl.escl_protocol import (
    ESCL_UNITS_PER_INCH,
    build_scan_settings_xml,
    parse_scanner_capabilities,
    parse_scanner_status,
)
from digitalizadora.simulator.fake_escl_scanner_app import (
    PLATEN_MAXIMUM_HEIGHT,
    PLATEN_MAXIMUM_WIDTH,
    FakeScannerBehavior,
    LidBackground,
    create_fake_escl_scanner_app,
    frame_margins_in_pixels,
    parse_lid_background,
)
from digitalizadora.simulator.photo_scene_page import (
    PHOTO_PLACEMENTS_BY_SCENE,
    SCENE_DRAWING_WIDTH_PIXELS,
    PhotoPlacement,
    PhotoScene,
    build_photo_scene_image,
    parse_photo_scene,
    photo_corners,
)

SCANNER_BASE_ADDRESS = "http://scanner.test"
CAPABILITIES_PATH = "/eSCL/ScannerCapabilities"
STATUS_PATH = "/eSCL/ScannerStatus"
SCAN_JOBS_PATH = "/eSCL/ScanJobs"
ABSOLUTE_SCAN_JOBS_PREFIX = f"{SCANNER_BASE_ADDRESS}{SCAN_JOBS_PATH}/"
NEXT_DOCUMENT_SUFFIX = "/NextDocument"
UNKNOWN_JOB_PATH = f"{SCAN_JOBS_PATH}/00000000-0000-4000-8000-000000000000"
RANDOM_IDENTIFIER_VERSION = 4
FAST_RESOLUTION = 75
JPEG_START_OF_IMAGE = b"\xff\xd8"
DARK_LEVEL_LIMIT = 100
LIGHT_LEVEL_LIMIT = 240
SHADED_LID_LEVEL_LIMIT = 230


def build_client(behavior: FakeScannerBehavior | None = None) -> httpx.AsyncClient:
    scanner_application = create_fake_escl_scanner_app(behavior or FakeScannerBehavior())
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=scanner_application), base_url=SCANNER_BASE_ADDRESS)


async def read_state(client: httpx.AsyncClient) -> ScannerState:
    response = await client.get(STATUS_PATH)
    return parse_scanner_status(response.content).state


def build_settings_document(dots_per_inch: int, color_mode: str) -> bytes:
    return (
        '<scan:ScanSettings xmlns:pwg="http://www.pwg.org/schemas/2010/12/sm" '
        'xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03">'
        "<pwg:Version>2.0</pwg:Version><pwg:ScanRegions><pwg:ScanRegion>"
        "<pwg:ContentRegionUnits>escl:ThreeHundredthsOfInches</pwg:ContentRegionUnits>"
        f"<pwg:Width>{PLATEN_MAXIMUM_WIDTH}</pwg:Width><pwg:Height>{PLATEN_MAXIMUM_HEIGHT}</pwg:Height>"
        "</pwg:ScanRegion></pwg:ScanRegions><pwg:InputSource>Platen</pwg:InputSource>"
        f"<scan:ColorMode>{color_mode}</scan:ColorMode>"
        "<pwg:DocumentFormat>image/jpeg</pwg:DocumentFormat>"
        f"<scan:XResolution>{dots_per_inch}</scan:XResolution>"
        f"<scan:YResolution>{dots_per_inch}</scan:YResolution></scan:ScanSettings>"
    ).encode()


async def post_scan_job(
    client: httpx.AsyncClient, dots_per_inch: int = FAST_RESOLUTION, color_mode: str = "RGB24"
) -> httpx.Response:
    return await client.post(
        SCAN_JOBS_PATH,
        content=build_settings_document(dots_per_inch, color_mode),
        headers={"Content-Type": "text/xml"},
    )


def job_path_of(post_response: httpx.Response) -> str:
    return urlsplit(post_response.headers["Location"]).path


async def create_job_path(client: httpx.AsyncClient) -> str:
    return job_path_of(await post_scan_job(client))


async def read_scanned_page(client: httpx.AsyncClient, color_mode: str = "RGB24") -> Image.Image:
    job_path = job_path_of(await post_scan_job(client, color_mode=color_mode))
    response = await client.get(f"{job_path}{NEXT_DOCUMENT_SUFFIX}")
    return Image.open(io.BytesIO(response.content))


async def test_capabilities_report_the_platen_size_of_the_real_printer() -> None:
    async with build_client() as client:
        response = await client.get(CAPABILITIES_PATH)
    capabilities = parse_scanner_capabilities(response.content)
    assert (capabilities.platen_maximum_width, capabilities.platen_maximum_height) == (2550, 3508)


async def test_capabilities_report_the_supported_resolutions_in_ascending_order() -> None:
    async with build_client() as client:
        response = await client.get(CAPABILITIES_PATH)
    capabilities = parse_scanner_capabilities(response.content)
    assert capabilities.supported_resolutions == (75, 100, 150, 200, 300, 400, 600, 1200)


async def test_capabilities_report_color_and_grayscale_modes() -> None:
    async with build_client() as client:
        response = await client.get(CAPABILITIES_PATH)
    capabilities = parse_scanner_capabilities(response.content)
    assert set(capabilities.supported_color_modes) == {"RGB24", "Grayscale8"}


async def test_capabilities_report_jpeg_and_pdf_formats() -> None:
    async with build_client() as client:
        response = await client.get(CAPABILITIES_PATH)
    capabilities = parse_scanner_capabilities(response.content)
    assert set(capabilities.supported_document_formats) == {"image/jpeg", "application/pdf"}


async def test_status_is_idle_by_default() -> None:
    async with build_client() as client:
        assert await read_state(client) is ScannerState.IDLE


async def test_status_reports_a_busy_initial_state() -> None:
    async with build_client(FakeScannerBehavior(initial_state="Processing")) as client:
        assert await read_state(client) is ScannerState.PROCESSING


async def test_post_answers_201_with_an_absolute_location_under_the_scan_jobs_path() -> None:
    async with build_client() as client:
        response = await post_scan_job(client)
    location_is_absolute = response.headers.get("Location", "").startswith(ABSOLUTE_SCAN_JOBS_PREFIX)
    assert (response.status_code, location_is_absolute) == (HTTPStatus.CREATED, True)


async def test_job_identifier_is_a_random_universally_unique_identifier() -> None:
    async with build_client() as client:
        job_path = await create_job_path(client)
    assert uuid.UUID(job_path.rpartition("/")[2]).version == RANDOM_IDENTIFIER_VERSION


async def test_each_job_receives_a_different_identifier() -> None:
    async with build_client() as client:
        first_job_path = await create_job_path(client)
        second_job_path = await create_job_path(client)
    assert first_job_path != second_job_path


async def test_next_document_is_delivered_on_the_first_request_by_default() -> None:
    async with build_client() as client:
        job_path = await create_job_path(client)
        response = await client.get(f"{job_path}{NEXT_DOCUMENT_SUFFIX}")
    assert response.status_code == HTTPStatus.OK


async def test_next_document_answers_503_while_busy_polls_remain_then_200() -> None:
    async with build_client(FakeScannerBehavior(busy_polls_before_document=3)) as client:
        job_path = await create_job_path(client)
        statuses = [(await client.get(f"{job_path}{NEXT_DOCUMENT_SUFFIX}")).status_code for _ in range(4)]
    assert statuses == [503, 503, 503, 200]


async def test_next_document_delivers_a_jpeg_page() -> None:
    async with build_client() as client:
        job_path = await create_job_path(client)
        response = await client.get(f"{job_path}{NEXT_DOCUMENT_SUFFIX}")
    assert (response.headers["Content-Type"], response.content[:2]) == ("image/jpeg", JPEG_START_OF_IMAGE)


async def test_next_document_answers_404_after_the_page_was_delivered() -> None:
    async with build_client() as client:
        job_path = await create_job_path(client)
        await client.get(f"{job_path}{NEXT_DOCUMENT_SUFFIX}")
        response = await client.get(f"{job_path}{NEXT_DOCUMENT_SUFFIX}")
    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_next_document_of_an_unknown_job_answers_404() -> None:
    async with build_client() as client:
        response = await client.get(f"{UNKNOWN_JOB_PATH}{NEXT_DOCUMENT_SUFFIX}")
    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_delete_of_a_live_job_answers_200_and_removes_it() -> None:
    async with build_client() as client:
        job_path = await create_job_path(client)
        deletion = await client.delete(job_path)
        document = await client.get(f"{job_path}{NEXT_DOCUMENT_SUFFIX}")
    assert (deletion.status_code, document.status_code) == (HTTPStatus.OK, HTTPStatus.NOT_FOUND)


async def test_delete_after_the_final_404_answers_404() -> None:
    async with build_client() as client:
        job_path = await create_job_path(client)
        await client.get(f"{job_path}{NEXT_DOCUMENT_SUFFIX}")
        await client.get(f"{job_path}{NEXT_DOCUMENT_SUFFIX}")
        response = await client.delete(job_path)
    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_delete_of_an_unknown_job_answers_404() -> None:
    async with build_client() as client:
        response = await client.delete(UNKNOWN_JOB_PATH)
    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_status_is_processing_between_the_post_and_the_delivery() -> None:
    async with build_client() as client:
        await post_scan_job(client)
        assert await read_state(client) is ScannerState.PROCESSING


async def test_status_is_idle_after_the_document_was_delivered() -> None:
    async with build_client() as client:
        job_path = await create_job_path(client)
        await client.get(f"{job_path}{NEXT_DOCUMENT_SUFFIX}")
        assert await read_state(client) is ScannerState.IDLE


async def test_status_is_idle_after_the_job_was_deleted() -> None:
    async with build_client() as client:
        job_path = await create_job_path(client)
        await client.delete(job_path)
        assert await read_state(client) is ScannerState.IDLE


async def test_page_size_follows_the_region_and_the_resolution() -> None:
    async with build_client() as client:
        image = await read_scanned_page(client)
    assert image.size == (
        PLATEN_MAXIMUM_WIDTH * FAST_RESOLUTION // ESCL_UNITS_PER_INCH,
        PLATEN_MAXIMUM_HEIGHT * FAST_RESOLUTION // ESCL_UNITS_PER_INCH,
    )


async def test_color_mode_rgb24_returns_an_rgb_image() -> None:
    async with build_client() as client:
        image = await read_scanned_page(client, color_mode="RGB24")
    assert image.mode == "RGB"


async def test_color_mode_grayscale8_returns_a_luminance_image() -> None:
    async with build_client() as client:
        image = await read_scanned_page(client, color_mode="Grayscale8")
    assert image.mode == "L"


async def test_page_carries_no_resolution_metadata() -> None:
    async with build_client() as client:
        image = await read_scanned_page(client)
    assert "dpi" not in image.info


async def test_page_has_a_dark_frame_close_to_the_edges() -> None:
    async with build_client() as client:
        image = await read_scanned_page(client)
    margin_x, _ = frame_margins_in_pixels(image.size)
    frame_pixel = image.convert("L").getpixel((margin_x + 1, image.size[1] // 2))
    assert frame_pixel < DARK_LEVEL_LIMIT


async def test_page_background_is_white() -> None:
    async with build_client() as client:
        image = await read_scanned_page(client)
    width_pixels, height_pixels = image.size
    assert image.convert("L").getpixel((width_pixels // 2, height_pixels // 2)) > LIGHT_LEVEL_LIMIT


async def test_accepts_the_settings_document_built_by_the_protocol_module() -> None:
    async with build_client() as client:
        capabilities = parse_scanner_capabilities((await client.get(CAPABILITIES_PATH)).content)
        settings_document = build_scan_settings_xml(ScanSettings(FAST_RESOLUTION, ColorMode.GRAYSCALE), capabilities)
        post_response = await client.post(
            SCAN_JOBS_PATH, content=settings_document, headers={"Content-Type": "text/xml"}
        )
        document = await client.get(f"{job_path_of(post_response)}{NEXT_DOCUMENT_SUFFIX}")
    image = Image.open(io.BytesIO(document.content))
    expected_size = (
        PLATEN_MAXIMUM_WIDTH * FAST_RESOLUTION // ESCL_UNITS_PER_INCH,
        PLATEN_MAXIMUM_HEIGHT * FAST_RESOLUTION // ESCL_UNITS_PER_INCH,
    )
    assert (image.mode, image.size) == ("L", expected_size)


@pytest.mark.parametrize("status_code", [HTTPStatus.CONFLICT, HTTPStatus.SERVICE_UNAVAILABLE])
async def test_post_status_code_is_returned_without_a_location(status_code: int) -> None:
    async with build_client(FakeScannerBehavior(post_status_code=status_code)) as client:
        response = await post_scan_job(client)
    assert (response.status_code, "Location" in response.headers) == (status_code, False)


async def test_a_refused_post_does_not_make_the_scanner_busy() -> None:
    async with build_client(FakeScannerBehavior(post_status_code=HTTPStatus.CONFLICT)) as client:
        await post_scan_job(client)
        assert await read_state(client) is ScannerState.IDLE


async def test_document_status_code_replaces_the_success_answer() -> None:
    behavior = FakeScannerBehavior(document_status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
    async with build_client(behavior) as client:
        job_path = await create_job_path(client)
        response = await client.get(f"{job_path}{NEXT_DOCUMENT_SUFFIX}")
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


async def test_busy_polls_still_come_before_the_replaced_document_answer() -> None:
    behavior = FakeScannerBehavior(busy_polls_before_document=1, document_status_code=HTTPStatus.NOT_FOUND)
    async with build_client(behavior) as client:
        job_path = await create_job_path(client)
        statuses = [(await client.get(f"{job_path}{NEXT_DOCUMENT_SUFFIX}")).status_code for _ in range(2)]
    assert statuses == [503, 404]


async def test_malformed_settings_answer_400() -> None:
    async with build_client() as client:
        response = await client.post(
            SCAN_JOBS_PATH, content=b"<scan:ScanSettings", headers={"Content-Type": "text/xml"}
        )
    assert response.status_code == HTTPStatus.BAD_REQUEST


async def test_settings_without_resolution_answer_400() -> None:
    document = build_settings_document(FAST_RESOLUTION, "RGB24").replace(b"XResolution", b"Ignored")
    async with build_client() as client:
        response = await client.post(SCAN_JOBS_PATH, content=document, headers={"Content-Type": "text/xml"})
    assert response.status_code == HTTPStatus.BAD_REQUEST


async def test_unsupported_color_mode_answers_400() -> None:
    async with build_client() as client:
        response = await post_scan_job(client, color_mode="BlackAndWhite1")
    assert response.status_code == HTTPStatus.BAD_REQUEST


async def test_zero_resolution_answers_400() -> None:
    async with build_client() as client:
        response = await post_scan_job(client, dots_per_inch=0)
    assert response.status_code == HTTPStatus.BAD_REQUEST


async def test_status_stays_processing_for_the_configured_polls_after_the_delivery() -> None:
    async with build_client(FakeScannerBehavior(processing_polls_after_document=2)) as client:
        job_path = await create_job_path(client)
        await client.get(f"{job_path}{NEXT_DOCUMENT_SUFFIX}")
        states = [await read_state(client) for _ in range(3)]
    assert states == [ScannerState.PROCESSING, ScannerState.PROCESSING, ScannerState.IDLE]


async def test_processing_after_the_delivery_outlasts_the_delete() -> None:
    async with build_client(FakeScannerBehavior(processing_polls_after_document=1)) as client:
        job_path = await create_job_path(client)
        await client.get(f"{job_path}{NEXT_DOCUMENT_SUFFIX}")
        await client.delete(job_path)
        assert await read_state(client) is ScannerState.PROCESSING


DARK_LID = FakeScannerBehavior(lid_background=LidBackground.DARK)


def test_the_lid_is_white_by_default() -> None:
    assert FakeScannerBehavior().lid_background is LidBackground.WHITE


@pytest.mark.parametrize("corner", ["top-left", "top-right", "bottom-left", "bottom-right"])
async def test_the_dark_lid_page_is_dark_at_every_corner(corner: str) -> None:
    async with build_client(DARK_LID) as client:
        image = (await read_scanned_page(client)).convert("L")
    width_pixels, height_pixels = image.size
    corner_pixels = {
        "top-left": (1, 1),
        "top-right": (width_pixels - 2, 1),
        "bottom-left": (1, height_pixels - 2),
        "bottom-right": (width_pixels - 2, height_pixels - 2),
    }
    assert image.getpixel(corner_pixels[corner]) < DARK_LEVEL_LIMIT


async def test_the_dark_lid_page_has_a_white_sheet_inside() -> None:
    async with build_client(DARK_LID) as client:
        image = (await read_scanned_page(client)).convert("L")
    width_pixels, height_pixels = image.size
    sheet_centre = (round(0.475 * width_pixels), round(0.475 * height_pixels))
    assert image.getpixel(sheet_centre) > LIGHT_LEVEL_LIMIT


@pytest.mark.parametrize(
    ("relative_position", "expected_to_be_sheet"),
    [
        ((0.14, 0.5), False),
        ((0.16, 0.5), True),
        ((0.5, 0.09), False),
        ((0.5, 0.11), True),
        ((0.81, 0.5), False),
        ((0.79, 0.5), True),
        ((0.5, 0.86), False),
        ((0.5, 0.84), True),
    ],
)
async def test_the_dark_lid_sheet_spans_fifteen_to_eighty_percent_of_the_width_and_ten_to_eighty_five_of_the_height(
    relative_position: tuple[float, float], expected_to_be_sheet: bool
) -> None:
    async with build_client(DARK_LID) as client:
        image = (await read_scanned_page(client)).convert("L")
    width_pixels, height_pixels = image.size
    pixel = image.getpixel((round(relative_position[0] * width_pixels), round(relative_position[1] * height_pixels)))
    assert (pixel > LIGHT_LEVEL_LIMIT) is expected_to_be_sheet


async def test_the_dark_lid_page_is_a_jpeg_of_the_requested_size() -> None:
    async with build_client(DARK_LID) as client:
        image = await read_scanned_page(client)
    assert image.size == (2550 * FAST_RESOLUTION // 300, 3508 * FAST_RESOLUTION // 300)


@pytest.mark.parametrize(
    ("text", "expected_background"),
    [
        ("dark", LidBackground.DARK),
        ("white", LidBackground.WHITE),
        ("", LidBackground.WHITE),
        (None, LidBackground.WHITE),
        ("purple", LidBackground.WHITE),
        ("DARK", LidBackground.WHITE),
    ],
)
def test_the_lid_background_is_read_from_text(text: str | None, expected_background: LidBackground) -> None:
    assert parse_lid_background(text) is expected_background


TWO_PHOTOS = FakeScannerBehavior(scene=PhotoScene.PHOTOS_TWO)
ONE_PHOTO = FakeScannerBehavior(scene=PhotoScene.PHOTOS_ONE)
MAGENTA_MARKER = (230, 0, 230)
GREEN_MARKER = (0, 200, 0)
COLOR_TOLERANCE = 40


def is_close_to(pixel: tuple[int, int, int], color: tuple[int, int, int]) -> bool:
    return all(abs(found - wanted) < COLOR_TOLERANCE for found, wanted in zip(pixel, color, strict=True))


def photo_corner_pixel(placement: PhotoPlacement, size: tuple[int, int], corner_index: int) -> tuple[int, int]:
    """A point a little inside the corner of the photo, toward its centre."""
    corners = photo_corners(placement, size)
    centre = (placement.center_x * size[0], placement.center_y * size[1])
    corner = corners[corner_index]
    return round(corner[0] + 0.04 * (centre[0] - corner[0])), round(corner[1] + 0.04 * (centre[1] - corner[1]))


def test_the_scene_is_the_sheet_by_default() -> None:
    assert FakeScannerBehavior().scene is PhotoScene.SHEET


@pytest.mark.parametrize(
    ("text", "expected_scene"),
    [
        ("photos_one", PhotoScene.PHOTOS_ONE),
        ("photos_two", PhotoScene.PHOTOS_TWO),
        ("sheet", PhotoScene.SHEET),
        ("", PhotoScene.SHEET),
        (None, PhotoScene.SHEET),
        ("three_photos", PhotoScene.SHEET),
        ("PHOTOS_TWO", PhotoScene.SHEET),
    ],
)
def test_the_scene_is_read_from_text(text: str | None, expected_scene: PhotoScene) -> None:
    assert parse_photo_scene(text) is expected_scene


async def test_the_photo_scene_page_is_a_jpeg_of_the_requested_size() -> None:
    async with build_client(TWO_PHOTOS) as client:
        image = await read_scanned_page(client)
    assert (image.format, image.size) == ("JPEG", (2550 * FAST_RESOLUTION // 300, 3508 * FAST_RESOLUTION // 300))


async def test_the_photo_scene_has_a_white_lid_at_every_corner() -> None:
    async with build_client(TWO_PHOTOS) as client:
        image = (await read_scanned_page(client)).convert("L")
    width_pixels, height_pixels = image.size
    corners = [(1, 1), (width_pixels - 2, 1), (1, height_pixels - 2), (width_pixels - 2, height_pixels - 2)]
    assert all(image.getpixel(corner) > SHADED_LID_LEVEL_LIMIT for corner in corners)


async def test_the_photo_scene_in_grayscale_is_a_grayscale_jpeg() -> None:
    async with build_client(TWO_PHOTOS) as client:
        image = await read_scanned_page(client, "Grayscale8")
    assert image.mode == "L"


@pytest.mark.parametrize("placement_index", [0, 1])
async def test_each_photo_of_the_scene_shows_its_markers_at_its_own_top_corners(placement_index: int) -> None:
    async with build_client(TWO_PHOTOS) as client:
        image = (await read_scanned_page(client)).convert("RGB")
    placement = PHOTO_PLACEMENTS_BY_SCENE[PhotoScene.PHOTOS_TWO][placement_index]
    left_marker = image.getpixel(photo_corner_pixel(placement, image.size, 0))
    right_marker = image.getpixel(photo_corner_pixel(placement, image.size, 1))
    assert (is_close_to(left_marker, MAGENTA_MARKER), is_close_to(right_marker, GREEN_MARKER)) == (True, True)


async def test_the_photos_of_the_scene_are_found_where_the_placements_say() -> None:
    async with build_client(TWO_PHOTOS) as client:
        image = (await read_scanned_page(client)).convert("L")
    first, second = PHOTO_PLACEMENTS_BY_SCENE[PhotoScene.PHOTOS_TWO]
    centres = [(round(p.center_x * image.width), round(p.center_y * image.height)) for p in (first, second)]
    assert [image.getpixel(centre) < LIGHT_LEVEL_LIMIT for centre in centres] == [True, True]


async def test_the_scene_with_one_photo_leaves_the_lower_half_of_the_glass_empty() -> None:
    async with build_client(ONE_PHOTO) as client:
        image = (await read_scanned_page(client)).convert("L")
    assert image.getpixel((image.width // 2, round(0.9 * image.height))) > SHADED_LID_LEVEL_LIMIT


async def test_the_scene_ignores_the_lid_background() -> None:
    behavior = FakeScannerBehavior(lid_background=LidBackground.DARK, scene=PhotoScene.PHOTOS_ONE)
    async with build_client(behavior) as client:
        image = (await read_scanned_page(client)).convert("L")
    assert image.getpixel((1, 1)) > SHADED_LID_LEVEL_LIMIT


def test_the_two_photos_of_the_acceptance_scene_do_not_touch() -> None:
    size = (1000, 1376)
    first, second = (photo_corners(placement, size) for placement in PHOTO_PLACEMENTS_BY_SCENE[PhotoScene.PHOTOS_TWO])

    assert max(y for _, y in first) < min(y for _, y in second)


@pytest.mark.parametrize("scene", [PhotoScene.PHOTOS_ONE, PhotoScene.PHOTOS_TWO])
def test_every_photo_of_every_scene_lies_inside_the_glass(scene: PhotoScene) -> None:
    size = (1000, 1376)
    corners = [corner for placement in PHOTO_PLACEMENTS_BY_SCENE[scene] for corner in photo_corners(placement, size)]

    assert all(0 <= x <= size[0] and 0 <= y <= size[1] for x, y in corners)


def test_the_scene_is_drawn_small_and_enlarged_for_a_large_glass() -> None:
    image = build_photo_scene_image((SCENE_DRAWING_WIDTH_PIXELS * 2, 400), PhotoScene.PHOTOS_ONE)

    assert image.size == (SCENE_DRAWING_WIDTH_PIXELS * 2, 400)

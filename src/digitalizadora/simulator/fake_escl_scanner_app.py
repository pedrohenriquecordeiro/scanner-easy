"""Fake eSCL scanner served as an ASGI application.

Used by the automated tests through httpx.ASGITransport and by `make simulator`. The platen, the
resolutions, the absolute job Location, the end-of-job 404 and the Processing state after a delivery
mirror what the HP DeskJet 2800 series answered in Gate 0 (docs/gate-0-resultado-2026-10-17.md).
"""

import io
import logging
import uuid
import xml.etree.ElementTree as ElementTree
from collections.abc import Sequence
from dataclasses import dataclass
from http import HTTPStatus

from fastapi import FastAPI, Request, Response
from PIL import Image, ImageDraw, ImageFont

from digitalizadora.infrastructure.escl.escl_protocol import ESCL_UNITS_PER_INCH

logger = logging.getLogger(__name__)

SCANNER_PATH_PREFIX = "/eSCL"
PLATEN_MAXIMUM_WIDTH = 2550
PLATEN_MAXIMUM_HEIGHT = 3508
PLATEN_MINIMUM_SIZE = 8
MAXIMUM_SCAN_REGIONS = 1
ESCL_VERSION = "2.63"
SUPPORTED_RESOLUTIONS = (75, 100, 150, 200, 300, 400, 600, 1200)
SUPPORTED_COLOR_MODES = ("RGB24", "Grayscale8")
SUPPORTED_DOCUMENT_FORMATS = ("image/jpeg", "application/pdf")
IDLE_STATE_NAME = "Idle"
XML_MEDIA_TYPE = "text/xml"
NAMESPACE_DECLARATIONS = (
    'xmlns:pwg="http://www.pwg.org/schemas/2010/12/sm" '
    'xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03"'
)
PROCESSING_STATE_NAME = "Processing"
JPEG_MEDIA_TYPE = "image/jpeg"
SCAN_JOBS_PATH = f"{SCANNER_PATH_PREFIX}/ScanJobs"


@dataclass
class FakeScannerBehavior:
    busy_polls_before_document: int = 0
    initial_state: str = IDLE_STATE_NAME
    post_status_code: int = HTTPStatus.CREATED
    document_status_code: int = HTTPStatus.OK
    processing_polls_after_document: int = 0


def build_capabilities_document(color_modes: Sequence[str]) -> bytes:
    color_mode_elements = "".join(f"<scan:ColorMode>{mode}</scan:ColorMode>" for mode in color_modes)
    format_elements = "".join(
        f"<pwg:DocumentFormat>{document_format}</pwg:DocumentFormat>"
        for document_format in SUPPORTED_DOCUMENT_FORMATS
    )
    resolution_elements = "".join(
        "<scan:DiscreteResolution>"
        f"<scan:XResolution>{resolution}</scan:XResolution>"
        f"<scan:YResolution>{resolution}</scan:YResolution>"
        "</scan:DiscreteResolution>"
        for resolution in SUPPORTED_RESOLUTIONS
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<scan:ScannerCapabilities {NAMESPACE_DECLARATIONS}>"
        f"<pwg:Version>{ESCL_VERSION}</pwg:Version>"
        "<pwg:MakeAndModel>Fake eSCL Scanner</pwg:MakeAndModel>"
        "<scan:Platen><scan:PlatenInputCaps>"
        f"<scan:MinWidth>{PLATEN_MINIMUM_SIZE}</scan:MinWidth>"
        f"<scan:MaxWidth>{PLATEN_MAXIMUM_WIDTH}</scan:MaxWidth>"
        f"<scan:MinHeight>{PLATEN_MINIMUM_SIZE}</scan:MinHeight>"
        f"<scan:MaxHeight>{PLATEN_MAXIMUM_HEIGHT}</scan:MaxHeight>"
        f"<scan:MaxScanRegions>{MAXIMUM_SCAN_REGIONS}</scan:MaxScanRegions>"
        "<scan:SettingProfiles><scan:SettingProfile>"
        f"<scan:ColorModes>{color_mode_elements}</scan:ColorModes>"
        f"<scan:DocumentFormats>{format_elements}</scan:DocumentFormats>"
        f"<scan:SupportedResolutions><scan:DiscreteResolutions>{resolution_elements}"
        "</scan:DiscreteResolutions></scan:SupportedResolutions>"
        "</scan:SettingProfile></scan:SettingProfiles>"
        "</scan:PlatenInputCaps></scan:Platen>"
        "</scan:ScannerCapabilities>"
    ).encode()


def build_status_document(state_name: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<scan:ScannerStatus {NAMESPACE_DECLARATIONS}>"
        f"<pwg:Version>{ESCL_VERSION}</pwg:Version>"
        f"<pwg:State>{state_name}</pwg:State>"
        "</scan:ScannerStatus>"
    ).encode()


class InvalidScanSettingsError(ValueError):
    """The posted ScanSettings document cannot be served."""


@dataclass(frozen=True)
class RequestedScan:
    region_width: int
    region_height: int
    dots_per_inch: int
    color_mode: str


PILLOW_MODE_BY_COLOR_MODE = {"RGB24": "RGB", "Grayscale8": "L"}


def _local_name(tag: str) -> str:
    return tag.rpartition("}")[2]


def parse_requested_scan(document: bytes) -> RequestedScan:
    try:
        root = ElementTree.fromstring(document)
    except ElementTree.ParseError as error:
        raise InvalidScanSettingsError("ScanSettings is not well-formed XML") from error
    values = {_local_name(element.tag): (element.text or "").strip() for element in root.iter()}
    try:
        return RequestedScan(
            region_width=int(values["Width"]),
            region_height=int(values["Height"]),
            dots_per_inch=int(values["XResolution"]),
            color_mode=values["ColorMode"],
        )
    except (KeyError, ValueError) as error:
        raise InvalidScanSettingsError("ScanSettings lacks a required number or color mode") from error


FRAME_MARGIN_RATIO = 0.02
FRAME_LINE_WIDTH_PIXELS = 3
INK_COLOR = "#282828"
LABEL_HEIGHT_DIVISOR = 15
LABEL_OFFSET_IN_MARGINS = 2
PAGE_LABEL_PREFIX = "Pagina"
JPEG_QUALITY = 85
MINIMUM_PAGE_SIZE_PIXELS = 1


def page_size_in_pixels(requested_scan: RequestedScan) -> tuple[int, int]:
    width_pixels = requested_scan.region_width * requested_scan.dots_per_inch // ESCL_UNITS_PER_INCH
    height_pixels = requested_scan.region_height * requested_scan.dots_per_inch // ESCL_UNITS_PER_INCH
    return width_pixels, height_pixels


def ensure_servable(requested_scan: RequestedScan) -> None:
    if requested_scan.color_mode not in PILLOW_MODE_BY_COLOR_MODE:
        raise InvalidScanSettingsError(f"Unsupported color mode {requested_scan.color_mode}")
    if min(page_size_in_pixels(requested_scan)) < MINIMUM_PAGE_SIZE_PIXELS:
        raise InvalidScanSettingsError("The requested region is smaller than one pixel")


def frame_margins_in_pixels(size_in_pixels: tuple[int, int]) -> tuple[int, int]:
    width_pixels, height_pixels = size_in_pixels
    return int(width_pixels * FRAME_MARGIN_RATIO), int(height_pixels * FRAME_MARGIN_RATIO)


def _draw_frame(draw: ImageDraw.ImageDraw, size_in_pixels: tuple[int, int]) -> None:
    width_pixels, height_pixels = size_in_pixels
    margin_x, margin_y = frame_margins_in_pixels(size_in_pixels)
    draw.rectangle(
        (margin_x, margin_y, width_pixels - 1 - margin_x, height_pixels - 1 - margin_y),
        outline=INK_COLOR,
        width=FRAME_LINE_WIDTH_PIXELS,
    )


def _draw_label(draw: ImageDraw.ImageDraw, size_in_pixels: tuple[int, int], page_number: int) -> None:
    font = ImageFont.load_default(size=size_in_pixels[1] // LABEL_HEIGHT_DIVISOR)
    margin_x, margin_y = frame_margins_in_pixels(size_in_pixels)
    label_position = (margin_x * LABEL_OFFSET_IN_MARGINS, margin_y * LABEL_OFFSET_IN_MARGINS)
    draw.text(label_position, f"{PAGE_LABEL_PREFIX} {page_number}", fill=INK_COLOR, font=font)


def build_synthetic_page(requested_scan: RequestedScan, page_number: int) -> bytes:
    size_in_pixels = page_size_in_pixels(requested_scan)
    image = Image.new(PILLOW_MODE_BY_COLOR_MODE[requested_scan.color_mode], size_in_pixels, "white")
    draw = ImageDraw.Draw(image)
    _draw_frame(draw, size_in_pixels)
    _draw_label(draw, size_in_pixels, page_number)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY)
    return buffer.getvalue()


@dataclass
class _ScanJob:
    page_number: int
    requested_scan: RequestedScan
    busy_polls_remaining: int
    page_delivered: bool = False


class FakeEsclScanner:
    def __init__(self, behavior: FakeScannerBehavior) -> None:
        self._behavior = behavior
        self._jobs: dict[str, _ScanJob] = {}
        self._created_job_count = 0
        self._processing_polls_remaining = 0

    async def read_capabilities(self) -> Response:
        return Response(content=build_capabilities_document(SUPPORTED_COLOR_MODES), media_type=XML_MEDIA_TYPE)

    async def read_status(self) -> Response:
        return Response(content=build_status_document(self._next_state_name()), media_type=XML_MEDIA_TYPE)

    async def create_job(self, request: Request) -> Response:
        if self._behavior.post_status_code != HTTPStatus.CREATED:
            return Response(status_code=self._behavior.post_status_code)
        try:
            requested_scan = parse_requested_scan(await request.body())
            ensure_servable(requested_scan)
        except InvalidScanSettingsError as error:
            logger.info("Rejected scan settings: %s", error)
            return Response(status_code=HTTPStatus.BAD_REQUEST)
        return self._register_job(request, requested_scan)

    async def next_document(self, job_identifier: str) -> Response:
        job = self._jobs.get(job_identifier)
        if job is None:
            return Response(status_code=HTTPStatus.NOT_FOUND)
        if job.page_delivered:
            # The real printer forgets a job after its final 404, so a later DELETE also answers 404.
            del self._jobs[job_identifier]
            return Response(status_code=HTTPStatus.NOT_FOUND)
        if job.busy_polls_remaining > 0:
            job.busy_polls_remaining -= 1
            return Response(status_code=HTTPStatus.SERVICE_UNAVAILABLE)
        if self._behavior.document_status_code != HTTPStatus.OK:
            return Response(status_code=self._behavior.document_status_code)
        job.page_delivered = True
        self._processing_polls_remaining = self._behavior.processing_polls_after_document
        page = build_synthetic_page(job.requested_scan, job.page_number)
        return Response(content=page, media_type=JPEG_MEDIA_TYPE)

    async def delete_job(self, job_identifier: str) -> Response:
        if self._jobs.pop(job_identifier, None) is None:
            return Response(status_code=HTTPStatus.NOT_FOUND)
        return Response(status_code=HTTPStatus.OK)

    def _register_job(self, request: Request, requested_scan: RequestedScan) -> Response:
        job_identifier = str(uuid.uuid4())
        self._created_job_count += 1
        self._jobs[job_identifier] = _ScanJob(
            self._created_job_count, requested_scan, self._behavior.busy_polls_before_document
        )
        location = f"{request.url.scheme}://{request.url.netloc}{SCAN_JOBS_PATH}/{job_identifier}"
        return Response(status_code=HTTPStatus.CREATED, headers={"Location": location})

    def _next_state_name(self) -> str:
        if any(not job.page_delivered for job in self._jobs.values()):
            return PROCESSING_STATE_NAME
        if self._processing_polls_remaining > 0:
            self._processing_polls_remaining -= 1
            return PROCESSING_STATE_NAME
        return self._behavior.initial_state


def create_fake_escl_scanner_app(behavior: FakeScannerBehavior) -> FastAPI:
    scanner = FakeEsclScanner(behavior)
    application = FastAPI(title="Fake eSCL scanner", docs_url=None, redoc_url=None, openapi_url=None)
    application.add_api_route(f"{SCANNER_PATH_PREFIX}/ScannerCapabilities", scanner.read_capabilities, methods=["GET"])
    application.add_api_route(f"{SCANNER_PATH_PREFIX}/ScannerStatus", scanner.read_status, methods=["GET"])
    application.add_api_route(SCAN_JOBS_PATH, scanner.create_job, methods=["POST"])
    job_path = f"{SCAN_JOBS_PATH}/{{job_identifier}}"
    application.add_api_route(f"{job_path}/NextDocument", scanner.next_document, methods=["GET"])
    application.add_api_route(job_path, scanner.delete_job, methods=["DELETE"])
    return application

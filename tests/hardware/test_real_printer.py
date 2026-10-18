import io
import time
from collections.abc import AsyncIterator, Callable

import pytest
from PIL import Image

from digitalizadora.composition_root import build_scanner_http_client
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scanner_endpoint import ScannerEndpoint
from digitalizadora.domain.scanner_route import ScannerRoute
from digitalizadora.infrastructure.bonjour_scanner_discovery import BonjourScannerDiscovery
from digitalizadora.infrastructure.dns_service_discovery_record_source import DnsServiceDiscoveryRecordSource
from digitalizadora.infrastructure.escl.escl_scanner_gateway import EsclGatewayTiming, EsclScannerGateway

pytestmark = pytest.mark.hardware

DISCOVERY_TIMEOUT_SECONDS = 5.0
PRESET_RESOLUTIONS = {preset.settings.dots_per_inch for preset in ScanPreset}
JPEG_MEDIA_TYPE = "image/jpeg"
JPEG_MARKER = b"\xff\xd8"
SCAN_SETTINGS = ScanPreset.DOCUMENT.settings
GLASS_SHORT_SIDE_INCHES = 8.5
MINIMUM_PAGE_EDGE_PIXELS = int(SCAN_SETTINGS.dots_per_inch * GLASS_SHORT_SIDE_INCHES / 2)


async def discover_endpoints() -> list[ScannerEndpoint]:
    discovery = BonjourScannerDiscovery(DnsServiceDiscoveryRecordSource())
    endpoints = await discovery.discover(DISCOVERY_TIMEOUT_SECONDS)
    assert endpoints, "No _uscan._tcp scanner found: is the printer on, with the USB cable or on the same Wi-Fi?"
    return endpoints


@pytest.fixture
async def scanner_endpoint() -> ScannerEndpoint:
    return (await discover_endpoints())[0]


@pytest.fixture
async def scanner_gateway(scanner_endpoint: ScannerEndpoint) -> AsyncIterator[EsclScannerGateway]:
    http_client = build_scanner_http_client()
    try:
        yield EsclScannerGateway(http_client, scanner_endpoint.base_address, EsclGatewayTiming())
    finally:
        await http_client.aclose()


async def test_discovery_finds_the_printer(scanner_endpoint: ScannerEndpoint) -> None:
    assert scanner_endpoint.base_address.startswith("http://")


async def test_discovery_offers_the_usb_route_first(scanner_endpoint: ScannerEndpoint) -> None:
    assert scanner_endpoint.route is ScannerRoute.USB, "Connect the USB cable: the USB route must come first"


async def test_capabilities_offer_every_preset_resolution(scanner_gateway: EsclScannerGateway) -> None:
    capabilities = await scanner_gateway.read_capabilities()
    assert PRESET_RESOLUTIONS <= set(capabilities.supported_resolutions)


async def test_capabilities_offer_jpeg(scanner_gateway: EsclScannerGateway) -> None:
    capabilities = await scanner_gateway.read_capabilities()
    assert JPEG_MEDIA_TYPE in capabilities.supported_document_formats


async def test_scan_one_page_returns_a_decodable_jpeg(
    scanner_gateway: EsclScannerGateway, record_property: Callable[[str, object], None]
) -> None:
    started_at = time.monotonic()
    scanned_image = await scanner_gateway.scan_page(SCAN_SETTINGS)
    record_property("scan_elapsed_seconds", round(time.monotonic() - started_at, 1))
    with Image.open(io.BytesIO(scanned_image.content)) as image:
        image.load()
        width_pixels, height_pixels = image.size
    assert scanned_image.content[:2] == JPEG_MARKER
    assert min(width_pixels, height_pixels) >= MINIMUM_PAGE_EDGE_PIXELS

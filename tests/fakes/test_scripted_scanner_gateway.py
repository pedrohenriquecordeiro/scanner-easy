import pytest

from digitalizadora.domain.errors import ScannerUnreachableError
from digitalizadora.domain.scanner.scanner_status import ScannerState, ScannerStatus
from digitalizadora.domain.scanning.color_mode import ColorMode
from digitalizadora.domain.scanning.scan_settings import ScanSettings
from digitalizadora.domain.scanning.scanned_image import ScannedImage
from tests.fakes.scripted_scanner_gateway import (
    FixedGatewayProvider,
    ScriptedScannerGateway,
    build_sample_capabilities,
)

SETTINGS = ScanSettings(dots_per_inch=300, color_mode=ColorMode.COLOR)
FIRST_IMAGE = ScannedImage(content=b"first", media_type="image/jpeg")
SECOND_IMAGE = ScannedImage(content=b"second", media_type="image/jpeg")


async def test_scan_page_returns_the_scripted_outcomes_in_order() -> None:
    gateway = ScriptedScannerGateway(build_sample_capabilities(), [FIRST_IMAGE, SECOND_IMAGE])

    first = await gateway.scan_page(SETTINGS)
    second = await gateway.scan_page(SETTINGS)

    assert (first, second) == (FIRST_IMAGE, SECOND_IMAGE)


async def test_scan_page_raises_an_exception_outcome() -> None:
    gateway = ScriptedScannerGateway(build_sample_capabilities(), [ScannerUnreachableError("off")])

    with pytest.raises(ScannerUnreachableError):
        await gateway.scan_page(SETTINGS)


async def test_scan_page_records_every_requested_setting() -> None:
    gateway = ScriptedScannerGateway(build_sample_capabilities(), [FIRST_IMAGE, SECOND_IMAGE])

    await gateway.scan_page(SETTINGS)
    await gateway.scan_page(SETTINGS)

    assert gateway.scan_requests == [SETTINGS, SETTINGS]


async def test_scan_page_without_a_scripted_outcome_fails_loudly() -> None:
    gateway = ScriptedScannerGateway(build_sample_capabilities(), [])

    with pytest.raises(AssertionError):
        await gateway.scan_page(SETTINGS)


async def test_read_capabilities_returns_the_given_capabilities() -> None:
    capabilities = build_sample_capabilities()
    gateway = ScriptedScannerGateway(capabilities, [])

    assert await gateway.read_capabilities() == capabilities


async def test_read_status_reports_an_idle_scanner() -> None:
    gateway = ScriptedScannerGateway(build_sample_capabilities(), [])

    assert await gateway.read_status() == ScannerStatus(state=ScannerState.IDLE)


async def test_fixed_gateway_provider_returns_the_same_gateway_every_time() -> None:
    gateway = ScriptedScannerGateway(build_sample_capabilities(), [])
    provider = FixedGatewayProvider(gateway)

    acquired_gateways = [await provider.acquire_gateway() for _ in range(2)]

    assert acquired_gateways == [gateway, gateway]

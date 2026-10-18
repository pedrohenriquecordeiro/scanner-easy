import dataclasses
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.encoded_scan import EncodedScan
from digitalizadora.domain.imaging.image_adjustment import ImageAdjustment
from digitalizadora.domain.imaging.page_crop import CropCorner, RectangleEdges
from digitalizadora.domain.imaging.page_framing import PageFraming
from digitalizadora.domain.imaging.pixel_region import PixelCorner, PixelRegion
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.quick_scan.last_scan import LastScan, QuickScanMasterFiles, QuickScanSlot, SavedScanFile
from digitalizadora.domain.quick_scan.scan_progress import ScanPhase, ScanProgressSnapshot
from digitalizadora.domain.quick_scan.stored_scan import StoredScan
from digitalizadora.domain.scan_job import ScanJob
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.domain.scanner_capabilities import ScannerCapabilities
from digitalizadora.domain.scanner_endpoint import ScannerEndpoint
from digitalizadora.domain.scanner_route import ScannerRoute
from digitalizadora.domain.scanner_status import ScannerState, ScannerStatus
from tests.fakes.page_crops import rectangle

MOMENT = datetime(2026, 10, 13, 15, 30, 12, tzinfo=timezone(timedelta(hours=-3)))
SETTINGS = ScanSettings(dots_per_inch=300, color_mode=ColorMode.COLOR)
REQUEST = ScanRequest(settings=SETTINGS, output_format=OutputFormat.PDF)
RESULT = ScanResult(
    output_path=Path("/tmp/scan.pdf"),
    output_format=OutputFormat.PDF,
    scanned_at=MOMENT,
    size_in_bytes=10,
)
LAST_SCAN = LastScan("0123456789abcdef", MOMENT, Path("/tmp"), OutputFormat.PDF, (SavedScanFile("a.pdf", 1, 1),))
MODELS = [
    SETTINGS,
    REQUEST,
    ScanJob(request=REQUEST, started_at=MOMENT),
    ScannerEndpoint(base_address="http://192.168.0.40:8080/eSCL", display_name="HP"),
    ScannerCapabilities("HP", 2550, 3507, (300,), ("RGB24",), ("image/jpeg",)),
    ScannerStatus(ScannerState.IDLE),
    ScannedImage(content=b"\xff\xd8", media_type="image/jpeg"),
    EncodedScan(b"x", OutputFormat.JPEG, MOMENT),
    RESULT,
    StoredScan(last_scan=LAST_SCAN, thumbnail_jpeg=b"t"),
    ApplicationSettings(Path("/tmp"), OutputFormat.PDF, ScanPreset.DOCUMENT.settings),
    ImageAdjustment(),
    PixelRegion(0, 0, 1, 1),
    rectangle((0.0, 0.0, 1.0, 1.0)),
    CropCorner(0.0, 0.0),
    RectangleEdges(0.0, 0.0, 1.0, 1.0),
    PixelCorner(0.0, 0.0),
    SavedScanFile("a.pdf", 1, 1),
    LAST_SCAN,
    QuickScanSlot(LAST_SCAN, 300, ColorMode.COLOR),
    QuickScanMasterFiles("0123456789abcdef", b"m", b"t"),
    rectangle((0.0, 0.0, 1.0, 1.0)),
    PageFraming(),
    ScanProgressSnapshot(ScanPhase.IDLE, 0, None, None),
]


@pytest.mark.parametrize("model", MODELS, ids=lambda model: type(model).__name__)
def test_domain_model_is_immutable(model: object) -> None:
    first_field_name = dataclasses.fields(model)[0].name

    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(model, first_field_name, None)


def test_scanner_endpoint_identifier_is_optional() -> None:
    endpoint = ScannerEndpoint(base_address="http://192.168.0.40:8080/eSCL", display_name="HP")

    assert endpoint.universally_unique_identifier is None


def test_scanner_endpoint_route_defaults_to_the_network() -> None:
    endpoint = ScannerEndpoint(base_address="http://192.168.0.40:8080/eSCL", display_name="HP")

    assert endpoint.route is ScannerRoute.NETWORK

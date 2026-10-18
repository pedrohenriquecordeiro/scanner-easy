import dataclasses
from collections.abc import Callable

import pytest

from digitalizadora.domain.errors import ScanFailedError, ScanRejectedError
from digitalizadora.domain.scanner.scanner_capabilities import ScannerCapabilities
from digitalizadora.domain.scanner.scanner_status import ScannerState
from digitalizadora.domain.scanning.color_mode import ColorMode
from digitalizadora.domain.scanning.scan_settings import ScanSettings
from digitalizadora.infrastructure.escl.escl_protocol import (
    ESCL_UNITS_PER_INCH,
    build_scan_settings_xml,
    extract_job_path,
    parse_scanner_capabilities,
    parse_scanner_status,
)
from tests.fakes.fixture_files import read_escl_fixture

CAPABILITIES_FIXTURE = "hp-deskjet-2800-scanner-capabilities.xml"
SYNTHETIC_CAPABILITIES_FIXTURE = "synthetic-scanner-capabilities.xml"
CAPABILITIES_WITH_OTHER_PREFIXES = b"""<?xml version="1.0"?>
<a:ScannerCapabilities xmlns:a="http://schemas.hp.com/imaging/escl/2011/05/03"
    xmlns:b="http://www.pwg.org/schemas/2010/12/sm">
  <b:MakeAndModel>Other Brand</b:MakeAndModel>
  <a:Platen><a:PlatenInputCaps>
    <a:MaxWidth>1000</a:MaxWidth><a:MaxHeight>2000</a:MaxHeight>
    <a:SettingProfiles><a:SettingProfile>
      <a:ColorModes><a:ColorMode>RGB24</a:ColorMode></a:ColorModes>
      <a:DocumentFormats><b:DocumentFormat>image/jpeg</b:DocumentFormat></a:DocumentFormats>
      <a:SupportedResolutions><a:DiscreteResolutions>
        <a:DiscreteResolution><a:XResolution>600</a:XResolution></a:DiscreteResolution>
        <a:DiscreteResolution><a:XResolution>300</a:XResolution></a:DiscreteResolution>
      </a:DiscreteResolutions></a:SupportedResolutions>
    </a:SettingProfile></a:SettingProfiles>
  </a:PlatenInputCaps></a:Platen>
</a:ScannerCapabilities>"""
PLATEN_TEMPLATE = (
    "<ScannerCapabilities><Platen><PlatenInputCaps>"
    "<MaxWidth>{width}</MaxWidth><MaxHeight>{height}</MaxHeight>"
    "</PlatenInputCaps></Platen></ScannerCapabilities>"
)


XML_DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>'
SCAN_SETTINGS_OPENING = (
    '<scan:ScanSettings xmlns:pwg="http://www.pwg.org/schemas/2010/12/sm"'
    ' xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03">'
)
EXPECTED_SCAN_SETTINGS_TEMPLATE = (
    XML_DECLARATION
    + SCAN_SETTINGS_OPENING
    + "<pwg:Version>2.0</pwg:Version>"
    + "<pwg:ScanRegions><pwg:ScanRegion>"
    + "<pwg:ContentRegionUnits>escl:ThreeHundredthsOfInches</pwg:ContentRegionUnits>"
    + "<pwg:XOffset>0</pwg:XOffset><pwg:YOffset>0</pwg:YOffset>"
    + "<pwg:Width>2550</pwg:Width><pwg:Height>3508</pwg:Height>"
    + "</pwg:ScanRegion></pwg:ScanRegions>"
    + "<pwg:InputSource>Platen</pwg:InputSource>"
    + "<scan:ColorMode>{color_mode}</scan:ColorMode>"
    + "<pwg:DocumentFormat>image/jpeg</pwg:DocumentFormat>"
    + "<scan:XResolution>{resolution}</scan:XResolution>"
    + "<scan:YResolution>{resolution}</scan:YResolution>"
    + "</scan:ScanSettings>"
)


STATUS_IDLE_FIXTURE = "hp-deskjet-2800-scanner-status-idle.xml"
STATUS_TEMPLATE = (
    '<scan:ScannerStatus xmlns:pwg="http://www.pwg.org/schemas/2010/12/sm"'
    ' xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03">'
    "<pwg:Version>2.63</pwg:Version><pwg:State>{state}</pwg:State></scan:ScannerStatus>"
)


ENTITY_DOCUMENT = (
    b'<?xml version="1.0"?><!DOCTYPE bomb [<!ENTITY laugh "ha">]>'
    b"<ScannerStatus><State>&laugh;</State></ScannerStatus>"
)
UTF16_ENTITY_DOCUMENT = (
    '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE bomb [<!ENTITY laugh "ha">]>'
    "<ScannerStatus><State>&laugh;</State></ScannerStatus>"
).encode("utf-16")
UNKNOWN_ENCODING_DOCUMENT = b'<?xml version="1.0" encoding="unknown-encoding"?><ScannerStatus/>'


def load_capabilities() -> ScannerCapabilities:
    return parse_scanner_capabilities(read_escl_fixture(CAPABILITIES_FIXTURE))


def test_real_capabilities_report_the_model() -> None:
    expected_model = "DeskJet Ink Advantage 2800 All-in-One Printer series"

    assert load_capabilities().make_and_model == expected_model


def test_real_capabilities_report_the_platen_size_in_escl_units() -> None:
    capabilities = load_capabilities()

    assert (capabilities.platen_maximum_width, capabilities.platen_maximum_height) == (2550, 3508)


def test_real_capabilities_report_resolutions_in_ascending_order() -> None:
    expected_resolutions = (75, 100, 150, 200, 300, 400, 600, 1200)

    assert load_capabilities().supported_resolutions == expected_resolutions


def test_real_capabilities_report_color_modes() -> None:
    expected_color_modes = ("BlackAndWhite1", "Grayscale8", "RGB24")

    assert load_capabilities().supported_color_modes == expected_color_modes


def test_real_capabilities_report_each_document_format_once() -> None:
    expected_formats = ("application/octet-stream", "image/jpeg", "application/pdf")

    assert load_capabilities().supported_document_formats == expected_formats


def test_synthetic_capabilities_merge_every_setting_profile() -> None:
    capabilities = parse_scanner_capabilities(read_escl_fixture(SYNTHETIC_CAPABILITIES_FIXTURE))

    assert capabilities == ScannerCapabilities(
        make_and_model="Synthetic eSCL Scanner",
        platen_maximum_width=2550,
        platen_maximum_height=3507,
        supported_resolutions=(150, 300, 600),
        supported_color_modes=("RGB24", "Grayscale8"),
        supported_document_formats=("image/jpeg", "application/pdf"),
    )


def test_capabilities_parse_ignores_namespace_prefixes_and_sorts_resolutions() -> None:
    capabilities = parse_scanner_capabilities(CAPABILITIES_WITH_OTHER_PREFIXES)

    assert capabilities == ScannerCapabilities(
        make_and_model="Other Brand",
        platen_maximum_width=1000,
        platen_maximum_height=2000,
        supported_resolutions=(300, 600),
        supported_color_modes=("RGB24",),
        supported_document_formats=("image/jpeg",),
    )


def test_capabilities_parse_rejects_malformed_xml() -> None:
    with pytest.raises(ScanFailedError, match="not valid XML"):
        parse_scanner_capabilities(b"<ScannerCapabilities><unclosed>")


def test_capabilities_parse_rejects_an_empty_document() -> None:
    with pytest.raises(ScanFailedError, match="not valid XML"):
        parse_scanner_capabilities(b"")


def test_capabilities_parse_rejects_a_document_of_another_kind() -> None:
    with pytest.raises(ScanFailedError, match="ScannerCapabilities"):
        parse_scanner_capabilities(b"<ScannerStatus/>")


def test_capabilities_parse_rejects_missing_platen_capabilities() -> None:
    document = b"<ScannerCapabilities><MakeAndModel>X</MakeAndModel></ScannerCapabilities>"

    with pytest.raises(ScanFailedError, match="platen"):
        parse_scanner_capabilities(document)


def test_capabilities_parse_rejects_a_platen_without_maximum_width() -> None:
    document = b"<ScannerCapabilities><Platen><PlatenInputCaps/></Platen></ScannerCapabilities>"

    with pytest.raises(ScanFailedError, match="MaxWidth"):
        parse_scanner_capabilities(document)


def test_capabilities_parse_rejects_a_non_numeric_maximum_width() -> None:
    document = PLATEN_TEMPLATE.format(width="wide", height="3508").encode("utf-8")

    with pytest.raises(ScanFailedError, match="MaxWidth"):
        parse_scanner_capabilities(document)


@pytest.mark.parametrize(
    ("width", "height", "field_name"),
    [
        ("0", "3508", "MaxWidth"),
        ("-1", "3508", "MaxWidth"),
        ("2550", "0", "MaxHeight"),
        ("2550", "-1", "MaxHeight"),
    ],
)
def test_capabilities_parse_rejects_a_platen_size_that_is_not_positive(
    width: str, height: str, field_name: str
) -> None:
    document = PLATEN_TEMPLATE.format(width=width, height=height).encode("utf-8")

    with pytest.raises(ScanFailedError, match=field_name):
        parse_scanner_capabilities(document)


def test_units_per_inch_is_three_hundred() -> None:
    assert ESCL_UNITS_PER_INCH == 300


@pytest.mark.parametrize(
    ("settings", "expected_color_mode", "expected_resolution"),
    [
        (ScanSettings(300, ColorMode.COLOR), "RGB24", 300),
        (ScanSettings(200, ColorMode.GRAYSCALE), "Grayscale8", 200),
        (ScanSettings(250, ColorMode.COLOR), "RGB24", 300),
        (ScanSettings(350, ColorMode.COLOR), "RGB24", 400),
        (ScanSettings(450, ColorMode.COLOR), "RGB24", 600),
        (ScanSettings(5000, ColorMode.GRAYSCALE), "Grayscale8", 1200),
    ],
)
def test_scan_settings_xml_is_exact(
    settings: ScanSettings, expected_color_mode: str, expected_resolution: int
) -> None:
    document = build_scan_settings_xml(settings, load_capabilities())

    assert document == EXPECTED_SCAN_SETTINGS_TEMPLATE.format(
        color_mode=expected_color_mode, resolution=expected_resolution
    ).encode("utf-8")


def test_scan_settings_xml_is_a_single_line() -> None:
    document = build_scan_settings_xml(ScanSettings(300, ColorMode.COLOR), load_capabilities())

    assert b"\n" not in document


def test_scan_settings_xml_uses_the_platen_size_of_the_scanner() -> None:
    capabilities = dataclasses.replace(
        load_capabilities(), platen_maximum_width=2549, platen_maximum_height=3507
    )

    document = build_scan_settings_xml(ScanSettings(300, ColorMode.COLOR), capabilities)

    assert b"<pwg:Width>2549</pwg:Width><pwg:Height>3507</pwg:Height>" in document


@pytest.mark.parametrize("color_modes", [("RGB24",), ()])
def test_scan_settings_xml_rejects_an_unsupported_grayscale_mode(
    color_modes: tuple[str, ...],
) -> None:
    capabilities = dataclasses.replace(load_capabilities(), supported_color_modes=color_modes)

    with pytest.raises(ScanRejectedError, match="Grayscale8"):
        build_scan_settings_xml(ScanSettings(200, ColorMode.GRAYSCALE), capabilities)


def test_scan_settings_xml_rejects_a_scanner_without_color() -> None:
    capabilities = dataclasses.replace(
        load_capabilities(), supported_color_modes=("Grayscale8", "BlackAndWhite1")
    )

    with pytest.raises(ScanRejectedError, match="RGB24"):
        build_scan_settings_xml(ScanSettings(300, ColorMode.COLOR), capabilities)


@pytest.mark.parametrize("document_formats", [("application/pdf",), ()])
def test_scan_settings_xml_rejects_a_scanner_that_does_not_offer_jpeg(
    document_formats: tuple[str, ...],
) -> None:
    capabilities = dataclasses.replace(
        load_capabilities(), supported_document_formats=document_formats
    )

    with pytest.raises(ScanRejectedError, match="image/jpeg"):
        build_scan_settings_xml(ScanSettings(300, ColorMode.COLOR), capabilities)


def test_scan_settings_xml_keeps_the_request_when_the_scanner_lists_no_resolution() -> None:
    capabilities = dataclasses.replace(load_capabilities(), supported_resolutions=())

    document = build_scan_settings_xml(ScanSettings(250, ColorMode.COLOR), capabilities)

    assert b"<scan:XResolution>250</scan:XResolution>" in document


@pytest.mark.parametrize(
    ("escl_state_name", "expected_state"),
    [
        ("Idle", ScannerState.IDLE),
        ("Processing", ScannerState.PROCESSING),
        ("Testing", ScannerState.TESTING),
        ("Stopped", ScannerState.STOPPED),
        ("Down", ScannerState.DOWN),
        ("Hibernating", ScannerState.UNKNOWN),
        ("", ScannerState.UNKNOWN),
    ],
)
def test_status_parse_maps_the_state_name(
    escl_state_name: str, expected_state: ScannerState
) -> None:
    document = STATUS_TEMPLATE.format(state=escl_state_name).encode("utf-8")

    assert parse_scanner_status(document).state is expected_state


def test_status_parse_reads_the_real_idle_capture() -> None:
    assert parse_scanner_status(read_escl_fixture(STATUS_IDLE_FIXTURE)).state is ScannerState.IDLE


def test_status_parse_reads_a_status_without_jobs() -> None:
    status = parse_scanner_status(read_escl_fixture("synthetic-scanner-status-idle.xml"))

    assert status.is_ready is True


def test_status_parse_reads_the_processing_fixture() -> None:
    status = parse_scanner_status(read_escl_fixture("synthetic-scanner-status-processing.xml"))

    assert status.state is ScannerState.PROCESSING


def test_status_parse_without_a_state_element_is_unknown() -> None:
    assert parse_scanner_status(b"<ScannerStatus/>").state is ScannerState.UNKNOWN


def test_status_parse_rejects_a_document_of_another_kind() -> None:
    with pytest.raises(ScanFailedError, match="ScannerStatus"):
        parse_scanner_status(read_escl_fixture(CAPABILITIES_FIXTURE))


def test_status_parse_rejects_malformed_xml() -> None:
    with pytest.raises(ScanFailedError, match="not valid XML"):
        parse_scanner_status(b"<ScannerStatus><State>Idle</ScannerStatus>")


@pytest.mark.parametrize(
    "location_header",
    [
        "http://192.168.0.40:8080/eSCL/ScanJobs/12",
        "/eSCL/ScanJobs/12",
        "/eSCL/ScanJobs/12/",
        "http://other-host.example:9999/eSCL/ScanJobs/12",
        "http://[fe80::1]:8080/eSCL/ScanJobs/12",
        "http://[fe80/eSCL/ScanJobs/12",
        "/eSCL/ScanJobs/12?token=abc",
        "  /eSCL/ScanJobs/12  ",
    ],
)
def test_extract_job_path_keeps_only_the_path(location_header: str) -> None:
    assert extract_job_path(location_header) == "/eSCL/ScanJobs/12"


def test_extract_job_path_reads_the_real_location_header() -> None:
    location_header = "http://localhost:57805/eSCL/ScanJobs/11111111-2222-3333-4444-000000000001"

    assert extract_job_path(location_header) == "/eSCL/ScanJobs/11111111-2222-3333-4444-000000000001"


@pytest.mark.parametrize(
    "location_header",
    [
        "",
        "   ",
        "/",
        "http://192.168.0.40:8080",
        "http://192.168.0.40:8080/",
        "http://[fe80",
        "ScanJobs/12",
    ],
)
def test_extract_job_path_rejects_a_location_without_an_absolute_path(location_header: str) -> None:
    with pytest.raises(ScanFailedError, match="job location"):
        extract_job_path(location_header)


@pytest.mark.parametrize("parser", [parse_scanner_capabilities, parse_scanner_status])
def test_parsers_refuse_documents_that_declare_entities(
    parser: Callable[[bytes], object],
) -> None:
    with pytest.raises(ScanFailedError, match="entities"):
        parser(ENTITY_DOCUMENT)


def test_entity_refusal_ignores_letter_case() -> None:
    document = ENTITY_DOCUMENT.replace(b"<!ENTITY", b"<!entity")

    with pytest.raises(ScanFailedError, match="entities"):
        parse_scanner_status(document)


@pytest.mark.parametrize("parser", [parse_scanner_capabilities, parse_scanner_status])
def test_parsers_refuse_entities_hidden_by_a_utf16_encoding(
    parser: Callable[[bytes], object],
) -> None:
    with pytest.raises(ScanFailedError, match="entities"):
        parser(UTF16_ENTITY_DOCUMENT)


@pytest.mark.parametrize("parser", [parse_scanner_capabilities, parse_scanner_status])
def test_parsers_reject_an_unknown_encoding_declaration(
    parser: Callable[[bytes], object],
) -> None:
    with pytest.raises(ScanFailedError, match="not valid XML"):
        parser(UNKNOWN_ENCODING_DOCUMENT)


def test_capabilities_parse_accepts_a_lowercase_doctype() -> None:
    document = read_escl_fixture(CAPABILITIES_FIXTURE).replace(b"?>", b"?><!doctype html>", 1)

    assert parse_scanner_capabilities(document).platen_maximum_width == 2550


def test_status_parse_accepts_a_lowercase_doctype() -> None:
    document = b"<!doctype html><ScannerStatus><State>Idle</State></ScannerStatus>"

    assert parse_scanner_status(document).state is ScannerState.IDLE

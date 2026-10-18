import re
import xml.etree.ElementTree as ElementTree
from collections.abc import Sequence
from types import MappingProxyType
from urllib.parse import urlsplit
from xml.parsers import expat

from digitalizadora.domain.errors import ScanFailedError, ScanRejectedError
from digitalizadora.domain.scanner.scanner_capabilities import ScannerCapabilities
from digitalizadora.domain.scanner.scanner_status import ScannerState, ScannerStatus
from digitalizadora.domain.scanning.color_mode import ColorMode
from digitalizadora.domain.scanning.scan_settings import ScanSettings

# Unit of platen_maximum_width and platen_maximum_height: 1/300 of an inch.
ESCL_UNITS_PER_INCH = 300
PWG_NAMESPACE = "http://www.pwg.org/schemas/2010/12/sm"
SCAN_NAMESPACE = "http://schemas.hp.com/imaging/escl/2011/05/03"
ESCL_VERSION = "2.0"
REGION_UNITS_NAME = "escl:ThreeHundredthsOfInches"
REGION_ORIGIN = 0
INPUT_SOURCE_PLATEN = "Platen"
JPEG_MEDIA_TYPE = "image/jpeg"
XML_DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>'
CAPABILITIES_ROOT_NAME = "ScannerCapabilities"
STATUS_ROOT_NAME = "ScannerStatus"
PLATEN_CAPABILITIES_PATH = ("Platen", "PlatenInputCaps")
COLOR_MODE_PATH = ("SettingProfiles", "SettingProfile", "ColorModes", "ColorMode")
DOCUMENT_FORMAT_PATH = ("SettingProfiles", "SettingProfile", "DocumentFormats", "DocumentFormat")
# Only DiscreteResolutions is read (the HP capture has no ResolutionRange); a device that publishes
# only a range gets no supported resolutions, and the requested value is then sent unchanged.
RESOLUTION_PATH = (
    "SettingProfiles",
    "SettingProfile",
    "SupportedResolutions",
    "DiscreteResolutions",
    "DiscreteResolution",
    "XResolution",
)
ESCL_COLOR_MODE_BY_COLOR_MODE = MappingProxyType(
    {ColorMode.COLOR: "RGB24", ColorMode.GRAYSCALE: "Grayscale8"}
)
SCANNER_STATE_BY_ESCL_NAME = MappingProxyType(
    {
        "Idle": ScannerState.IDLE,
        "Processing": ScannerState.PROCESSING,
        "Testing": ScannerState.TESTING,
        "Stopped": ScannerState.STOPPED,
        "Down": ScannerState.DOWN,
    }
)
SCHEME_SEPARATOR = "://"
PATH_SEPARATOR = "/"
QUERY_OR_FRAGMENT_PATTERN = re.compile(r"[?#]")
ENTITY_DECLARATION_PATTERN = re.compile(rb"<!ENTITY", re.IGNORECASE)
DOCUMENT_TYPE_PATTERN = re.compile(rb"<!doctype", re.IGNORECASE)
NORMALIZED_DOCUMENT_TYPE = b"<!DOCTYPE"
ENTITY_REFUSAL_MESSAGE = "The eSCL document declares XML entities, which are refused"


def parse_scanner_capabilities(document: bytes) -> ScannerCapabilities:
    root = _parse_document(document)
    _require_root_name(root, CAPABILITIES_ROOT_NAME)
    platen_capabilities = _elements_at(root, PLATEN_CAPABILITIES_PATH)
    if not platen_capabilities:
        raise ScanFailedError("Scanner capabilities do not describe a platen")
    platen = platen_capabilities[0]
    resolutions = {
        _parse_integer(element.text, "XResolution")
        for element in _elements_at(platen, RESOLUTION_PATH)
    }
    return ScannerCapabilities(
        make_and_model=_child_text(root, "MakeAndModel"),
        platen_maximum_width=_read_positive_integer(platen, "MaxWidth"),
        platen_maximum_height=_read_positive_integer(platen, "MaxHeight"),
        supported_resolutions=tuple(sorted(resolutions)),
        supported_color_modes=_unique_texts(_elements_at(platen, COLOR_MODE_PATH)),
        supported_document_formats=_unique_texts(_elements_at(platen, DOCUMENT_FORMAT_PATH)),
    )


def build_scan_settings_xml(settings: ScanSettings, capabilities: ScannerCapabilities) -> bytes:
    escl_color_mode = ESCL_COLOR_MODE_BY_COLOR_MODE[settings.color_mode]
    if not capabilities.supports_color_mode(escl_color_mode):
        raise ScanRejectedError(f"Scanner does not support the color mode {escl_color_mode}")
    if JPEG_MEDIA_TYPE not in capabilities.supported_document_formats:
        raise ScanRejectedError(f"Scanner does not offer the document format {JPEG_MEDIA_TYPE}")
    resolution = capabilities.closest_supported_resolution(settings.dots_per_inch)
    region = _element(
        "pwg:ScanRegion",
        _element("pwg:ContentRegionUnits", REGION_UNITS_NAME)
        + _element("pwg:XOffset", REGION_ORIGIN)
        + _element("pwg:YOffset", REGION_ORIGIN)
        + _element("pwg:Width", capabilities.platen_maximum_width)
        + _element("pwg:Height", capabilities.platen_maximum_height),
    )
    root_content = (
        _element("pwg:Version", ESCL_VERSION)
        + _element("pwg:ScanRegions", region)
        + _element("pwg:InputSource", INPUT_SOURCE_PLATEN)
        + _element("scan:ColorMode", escl_color_mode)
        + _element("pwg:DocumentFormat", JPEG_MEDIA_TYPE)
        + _element("scan:XResolution", resolution)
        + _element("scan:YResolution", resolution)
    )
    root_opening = f'<scan:ScanSettings xmlns:pwg="{PWG_NAMESPACE}" xmlns:scan="{SCAN_NAMESPACE}">'
    document = f"{XML_DECLARATION}{root_opening}{root_content}</scan:ScanSettings>"
    return document.encode("utf-8")


def parse_scanner_status(document: bytes) -> ScannerStatus:
    root = _parse_document(document)
    _require_root_name(root, STATUS_ROOT_NAME)
    state_name = _child_text(root, "State")
    return ScannerStatus(SCANNER_STATE_BY_ESCL_NAME.get(state_name, ScannerState.UNKNOWN))


def extract_job_path(location_header: str) -> str:
    location = location_header.strip()
    try:
        path = urlsplit(location).path
    except ValueError:
        path = _path_after_malformed_host(location)
    path = path.rstrip(PATH_SEPARATOR)
    if not path.startswith(PATH_SEPARATOR):
        raise ScanFailedError(f"The scanner returned a job location without an absolute path: {location!r}")
    return path


def _path_after_malformed_host(location: str) -> str:
    # urlsplit refuses hosts like "[fe80" (seen in real firmware); the host is ignored anyway.
    host_and_path = location.partition(SCHEME_SEPARATOR)[2]
    path_without_leading_separator = host_and_path.partition(PATH_SEPARATOR)[2]
    return PATH_SEPARATOR + QUERY_OR_FRAGMENT_PATTERN.split(path_without_leading_separator, maxsplit=1)[0]


def _parse_document(document: bytes) -> ElementTree.Element:
    if ENTITY_DECLARATION_PATTERN.search(document):
        raise ScanFailedError(ENTITY_REFUSAL_MESSAGE)
    normalized_document = DOCUMENT_TYPE_PATTERN.sub(NORMALIZED_DOCUMENT_TYPE, document)
    try:
        _refuse_entity_declarations(normalized_document)
        return ElementTree.fromstring(normalized_document)
    except (expat.ExpatError, ElementTree.ParseError, LookupError, ValueError) as error:
        raise ScanFailedError(f"The eSCL document is not valid XML: {error}") from error


def _local_name(tag: str) -> str:
    return tag.rpartition("}")[2]


def _children_named(parent: ElementTree.Element, name: str) -> list[ElementTree.Element]:
    return [child for child in parent if _local_name(child.tag) == name]


def _elements_at(start: ElementTree.Element, path: Sequence[str]) -> list[ElementTree.Element]:
    current = [start]
    for name in path:
        current = [child for element in current for child in _children_named(element, name)]
    return current


def _child_text(parent: ElementTree.Element, name: str) -> str:
    children = _children_named(parent, name)
    if not children or children[0].text is None:
        return ""
    return children[0].text.strip()


def _unique_texts(elements: Sequence[ElementTree.Element]) -> tuple[str, ...]:
    texts = (element.text.strip() for element in elements if element.text)
    return tuple(dict.fromkeys(text for text in texts if text))


def _parse_integer(text: str | None, field_name: str) -> int:
    try:
        return int((text or "").strip())
    except ValueError as error:
        raise ScanFailedError(f"The eSCL field {field_name} is not an integer") from error


def _read_positive_integer(parent: ElementTree.Element, name: str) -> int:
    children = _children_named(parent, name)
    if not children:
        raise ScanFailedError(f"The eSCL document has no {name}")
    value = _parse_integer(children[0].text, name)
    if value <= 0:
        raise ScanFailedError(f"The eSCL field {name} must be positive, got {value}")
    return value


def _require_root_name(root: ElementTree.Element, expected_name: str) -> None:
    if _local_name(root.tag) != expected_name:
        raise ScanFailedError(f"Expected an eSCL {expected_name} document, got {root.tag}")


def _element(name: str, content: object) -> str:
    return f"<{name}>{content}</{name}>"


def _refuse_entity_declarations(document: bytes) -> None:
    # A separate expat pass sees declarations in any encoding, before ElementTree could expand them.
    entity_detector = expat.ParserCreate()
    entity_detector.EntityDeclHandler = _refuse_entity_declaration
    entity_detector.Parse(document, True)


def _refuse_entity_declaration(*declaration_fields: object) -> None:
    raise ScanFailedError(ENTITY_REFUSAL_MESSAGE)

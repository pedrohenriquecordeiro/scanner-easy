import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from digitalizadora.domain.errors import InvalidCropError, UnreadableQuickScanError
from digitalizadora.domain.imaging.page_framing import MAXIMUM_CROPS_PER_PAGE, PageFraming
from digitalizadora.domain.imaging.page_rotation import PageRotation
from digitalizadora.domain.output.output_format import OutputFormat
from digitalizadora.domain.quick_scan.last_scan import LastScan, QuickScanSlot, SavedScanFile
from digitalizadora.domain.scanning.color_mode import ColorMode
from digitalizadora.repositories.storage.crop_codec import decode_crop, encode_crop

MANIFEST_FORMAT_VERSION = 1
MANIFEST_ENCODING = "utf-8"
MANIFEST_INDENTATION = 2
SCAN_IDENTIFIER_LENGTH = 16
HEXADECIMAL_DIGITS = frozenset("0123456789abcdef")
ALLOWED_DOTS_PER_INCH = range(1, 65536)
ALLOWED_SIZES_IN_BYTES = range(0, sys.maxsize)
ALLOWED_MODIFICATION_TIMES = range(0, sys.maxsize)


def encode_quick_scan_manifest(slot: QuickScanSlot) -> bytes:
    last_scan = slot.last_scan
    document = {
        "format_version": MANIFEST_FORMAT_VERSION,
        "scan_identifier": last_scan.scan_identifier,
        "scanned_at": last_scan.scanned_at.isoformat(),
        "dots_per_inch": slot.dots_per_inch,
        "color_mode": slot.color_mode.value,
        "output_folder": str(last_scan.output_folder),
        "output_format": last_scan.output_format.value,
        "rotation_degrees": last_scan.framing.rotation.value,
        "crops": [encode_crop(crop) for crop in last_scan.framing.crops],
        "saved_files": [
            {
                "file_name": saved_file.file_name,
                "size_in_bytes": saved_file.size_in_bytes,
                "modified_at_nanoseconds": saved_file.modified_at_nanoseconds,
            }
            for saved_file in last_scan.saved_files
        ],
        "render_pending": slot.render_pending,
    }
    return json.dumps(document, ensure_ascii=False, indent=MANIFEST_INDENTATION).encode(MANIFEST_ENCODING)


def decode_quick_scan_manifest(content: bytes) -> QuickScanSlot:
    """Strict reading of format version 1: anything unexpected makes the whole manifest unreadable."""
    document = _parse_json_object(content)
    if _read(document, "format_version") != MANIFEST_FORMAT_VERSION or isinstance(document["format_version"], bool):
        raise UnreadableQuickScanError(f"Unsupported manifest format version {document['format_version']!r}")
    last_scan = LastScan(
        scan_identifier=_read_scan_identifier(document),
        scanned_at=_read_moment(document),
        output_folder=_read_output_folder(document),
        output_format=_read_enum(OutputFormat, document, "output_format"),
        saved_files=_read_saved_files(_read(document, "saved_files")),
        framing=PageFraming(_read_rotation(document)).with_crops(_read_crops(_read(document, "crops"))),
    )
    return QuickScanSlot(
        last_scan=last_scan,
        dots_per_inch=_read_whole_number(document, "dots_per_inch", ALLOWED_DOTS_PER_INCH),
        color_mode=_read_enum(ColorMode, document, "color_mode"),
        render_pending=_read_boolean(document, "render_pending"),
    )


def _parse_json_object(content: bytes) -> dict[str, Any]:
    try:
        document = json.loads(content.decode(MANIFEST_ENCODING))
    except ValueError as error:
        raise UnreadableQuickScanError(f"The manifest is not valid UTF-8 JSON: {error}") from error
    if not isinstance(document, dict):
        raise UnreadableQuickScanError("The manifest is not a JSON object")
    return document


def _read(fields: dict[str, Any], key: str) -> Any:
    if key not in fields:
        raise UnreadableQuickScanError(f"The manifest has no {key!r}")
    return fields[key]


def _is_whole_number(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _read_whole_number(fields: dict[str, Any], key: str, allowed_values: range) -> int:
    value = _read(fields, key)
    if not _is_whole_number(value) or value not in allowed_values:
        raise UnreadableQuickScanError(f"{key!r} is not an allowed whole number: {value!r}")
    return value


def _read_boolean(fields: dict[str, Any], key: str) -> bool:
    value = _read(fields, key)
    if not isinstance(value, bool):
        raise UnreadableQuickScanError(f"{key!r} is not true or false: {value!r}")
    return value


def _read_text(fields: dict[str, Any], key: str) -> str:
    value = _read(fields, key)
    if not isinstance(value, str):
        raise UnreadableQuickScanError(f"{key!r} is not text")
    return value


def _read_enum[EnumMember](enum_type: type[EnumMember], fields: dict[str, Any], key: str) -> EnumMember:
    value = _read(fields, key)
    try:
        return enum_type(value)  # type: ignore[call-arg]
    except ValueError as error:
        raise UnreadableQuickScanError(f"Unknown {key!r}: {value!r}") from error


def _read_scan_identifier(fields: dict[str, Any]) -> str:
    identifier = _read_text(fields, "scan_identifier")
    if len(identifier) != SCAN_IDENTIFIER_LENGTH or not set(identifier) <= HEXADECIMAL_DIGITS:
        raise UnreadableQuickScanError(f"Invalid scan identifier {identifier!r}")
    return identifier


def _read_moment(fields: dict[str, Any]) -> datetime:
    value = _read_text(fields, "scanned_at")
    try:
        moment = datetime.fromisoformat(value)
    except ValueError as error:
        raise UnreadableQuickScanError(f"'scanned_at' is not an ISO 8601 moment: {value!r}") from error
    if moment.tzinfo is None:
        raise UnreadableQuickScanError(f"'scanned_at' has no time zone: {value!r}")
    return moment


def _read_output_folder(fields: dict[str, Any]) -> Path:
    output_folder = Path(_read_text(fields, "output_folder"))
    if not output_folder.is_absolute():
        raise UnreadableQuickScanError(f"The output folder {str(output_folder)!r} is not absolute")
    return output_folder


def _read_rotation(fields: dict[str, Any]) -> PageRotation:
    value = _read(fields, "rotation_degrees")
    try:
        if not _is_whole_number(value):
            raise ValueError(value)
        return PageRotation(value)
    except ValueError as error:
        raise UnreadableQuickScanError(f"Invalid rotation {value!r}") from error


def _read_crops(value: object) -> list:
    if not isinstance(value, list) or len(value) > MAXIMUM_CROPS_PER_PAGE:
        raise UnreadableQuickScanError("The crops are not a list of at most two crops")
    try:
        return [decode_crop(item) for item in value]
    except InvalidCropError as error:
        raise UnreadableQuickScanError(f"A crop of the manifest is invalid: {error}") from error


def _read_saved_files(value: object) -> tuple[SavedScanFile, ...]:
    if not isinstance(value, list) or not value:
        raise UnreadableQuickScanError("The saved files are not a list with at least one file")
    saved_files = tuple(_read_saved_file(item) for item in value)
    if len({saved_file.file_name for saved_file in saved_files}) != len(saved_files):
        raise UnreadableQuickScanError("The manifest lists the same saved file twice")
    return saved_files


def _read_saved_file(item: object) -> SavedScanFile:
    if not isinstance(item, dict):
        raise UnreadableQuickScanError("A saved file is not an object")
    file_name = _read_text(item, "file_name")
    if not file_name or file_name in {".", ".."} or "/" in file_name or "\0" in file_name:
        raise UnreadableQuickScanError(f"{file_name!r} is not a simple file name")
    return SavedScanFile(
        file_name=file_name,
        size_in_bytes=_read_whole_number(item, "size_in_bytes", ALLOWED_SIZES_IN_BYTES),
        modified_at_nanoseconds=_read_whole_number(item, "modified_at_nanoseconds", ALLOWED_MODIFICATION_TIMES),
    )

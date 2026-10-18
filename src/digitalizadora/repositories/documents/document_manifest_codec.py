import json
import logging
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from digitalizadora.domain.documents.document_draft import DocumentDraft, DocumentPage, is_page_identifier
from digitalizadora.domain.errors import InvalidCropError, UnreadableDraftError
from digitalizadora.domain.imaging.page_crop import PageCrop
from digitalizadora.domain.imaging.page_framing import MAXIMUM_CROPS_PER_PAGE, PageFraming
from digitalizadora.domain.imaging.page_rotation import PageRotation
from digitalizadora.domain.output.output_format import OutputFormat
from digitalizadora.domain.scanning.color_mode import ColorMode
from digitalizadora.domain.scanning.scan_result import ScanResult
from digitalizadora.repositories.storage.crop_codec import decode_crop, decode_legacy_rectangle, encode_crop

LOGGER = logging.getLogger(__name__)

MANIFEST_FORMAT_VERSION = 1
MANIFEST_ENCODING = "utf-8"
MANIFEST_INDENTATION = 2
FORMAT_VERSION_KEY = "format_version"
NAME_KEY = "name"
CREATED_AT_KEY = "created_at"
PAGES_KEY = "pages"
PAGE_IDENTIFIER_KEY = "page_identifier"
SCANNED_AT_KEY = "scanned_at"
DOTS_PER_INCH_KEY = "dots_per_inch"
COLOR_MODE_KEY = "color_mode"
SIZE_IN_BYTES_KEY = "size_in_bytes"
ROTATION_DEGREES_KEY = "rotation_degrees"
CROPS_KEY = "crops"
LEGACY_CROP_KEY = "crop"
FINALIZATION_STARTED_AT_KEY = "finalization_started_at"
FINISHED_DOCUMENT_KEY = "finished_document"
PATH_KEY = "path"
FINALIZED_AT_KEY = "finalized_at"
ALLOWED_DOTS_PER_INCH = range(1, 65536)
ALLOWED_SIZES_IN_BYTES = range(1, sys.maxsize)


def encode_manifest(draft: DocumentDraft) -> bytes:
    document = {
        FORMAT_VERSION_KEY: MANIFEST_FORMAT_VERSION,
        NAME_KEY: draft.name,
        CREATED_AT_KEY: draft.created_at.isoformat(),
        PAGES_KEY: [_encode_page(page) for page in draft.pages],
        FINALIZATION_STARTED_AT_KEY: _encode_optional_moment(draft.finalization_started_at),
        FINISHED_DOCUMENT_KEY: _encode_finished_document(draft.finished_document),
    }
    return json.dumps(document, ensure_ascii=False, indent=MANIFEST_INDENTATION).encode(MANIFEST_ENCODING)


def decode_manifest(content: bytes) -> DocumentDraft:
    """Strict reading of format version 1: anything unexpected makes the whole manifest unreadable."""
    document = _parse_json_object(content)
    _check_format_version(_read_required(document, FORMAT_VERSION_KEY))
    return DocumentDraft(
        name=_read_text(document, NAME_KEY),
        created_at=_read_moment(document, CREATED_AT_KEY),
        pages=_read_pages(_read_required(document, PAGES_KEY)),
        finalization_started_at=_read_optional_moment(document, FINALIZATION_STARTED_AT_KEY),
        finished_document=_read_finished_document(document.get(FINISHED_DOCUMENT_KEY)),
    )


def _encode_page(page: DocumentPage) -> dict[str, Any]:
    return {
        PAGE_IDENTIFIER_KEY: page.page_identifier,
        SCANNED_AT_KEY: page.scanned_at.isoformat(),
        DOTS_PER_INCH_KEY: page.dots_per_inch,
        COLOR_MODE_KEY: page.color_mode.value,
        SIZE_IN_BYTES_KEY: page.size_in_bytes,
        ROTATION_DEGREES_KEY: page.framing.rotation.value,
        CROPS_KEY: [encode_crop(crop) for crop in page.framing.crops],
    }


def _encode_optional_moment(moment: datetime | None) -> str | None:
    return None if moment is None else moment.isoformat()


def _encode_finished_document(finished_document: ScanResult | None) -> dict[str, Any] | None:
    if finished_document is None:
        return None
    return {
        PATH_KEY: str(finished_document.output_path),
        SIZE_IN_BYTES_KEY: finished_document.size_in_bytes,
        FINALIZED_AT_KEY: finished_document.scanned_at.isoformat(),
    }


def _parse_json_object(content: bytes) -> dict[str, Any]:
    try:
        document = json.loads(content.decode(MANIFEST_ENCODING))
    except ValueError as error:
        raise UnreadableDraftError(f"The manifest is not valid UTF-8 JSON: {error}") from error
    return _as_json_object(document, "manifest")


def _as_json_object(value: object, description: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise UnreadableDraftError(f"The {description} is not a JSON object")
    return value


def _read_required(fields: dict[str, Any], key: str) -> object:
    if key not in fields:
        raise UnreadableDraftError(f"The manifest has no {key!r}")
    return fields[key]


def _is_whole_number(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _check_format_version(value: object) -> None:
    if not _is_whole_number(value) or value != MANIFEST_FORMAT_VERSION:
        raise UnreadableDraftError(f"Unsupported manifest format version {value!r}")


def _read_text(fields: dict[str, Any], key: str) -> str:
    value = _read_required(fields, key)
    if not isinstance(value, str):
        raise UnreadableDraftError(f"{key!r} is not text")
    return value


def _read_whole_number(fields: dict[str, Any], key: str, allowed_values: range) -> int:
    value = _read_required(fields, key)
    if not _is_whole_number(value) or value not in allowed_values:
        raise UnreadableDraftError(f"{key!r} is not an allowed whole number: {value!r}")
    return value


def _read_moment(fields: dict[str, Any], key: str) -> datetime:
    return _parse_moment(_read_required(fields, key), key)


def _read_optional_moment(fields: dict[str, Any], key: str) -> datetime | None:
    value = fields.get(key)
    return None if value is None else _parse_moment(value, key)


def _parse_moment(value: object, key: str) -> datetime:
    if not isinstance(value, str):
        raise UnreadableDraftError(f"{key!r} is not an ISO 8601 text")
    try:
        moment = datetime.fromisoformat(value)
    except ValueError as error:
        raise UnreadableDraftError(f"{key!r} is not an ISO 8601 moment: {value!r}") from error
    if moment.tzinfo is None:
        raise UnreadableDraftError(f"{key!r} has no time zone: {value!r}")
    return moment


def _read_pages(value: object) -> tuple[DocumentPage, ...]:
    if not isinstance(value, list):
        raise UnreadableDraftError(f"{PAGES_KEY!r} is not a list")
    pages = tuple(_read_page(_as_json_object(item, "page")) for item in value)
    page_identifiers = [page.page_identifier for page in pages]
    if len(set(page_identifiers)) != len(page_identifiers):
        raise UnreadableDraftError("The manifest lists the same page identifier twice")
    return pages


def _read_page(fields: dict[str, Any]) -> DocumentPage:
    page_identifier = _read_required(fields, PAGE_IDENTIFIER_KEY)
    if not is_page_identifier(page_identifier):
        raise UnreadableDraftError(f"Invalid page identifier {page_identifier!r}")
    return DocumentPage(
        page_identifier=page_identifier,
        scanned_at=_read_moment(fields, SCANNED_AT_KEY),
        dots_per_inch=_read_whole_number(fields, DOTS_PER_INCH_KEY, ALLOWED_DOTS_PER_INCH),
        color_mode=_read_color_mode(fields),
        size_in_bytes=_read_whole_number(fields, SIZE_IN_BYTES_KEY, ALLOWED_SIZES_IN_BYTES),
        framing=_read_framing(fields, page_identifier),
    )


def _read_framing(fields: dict[str, Any], page_identifier: str) -> PageFraming:
    """Tolerant: a manifest from before the framing has neither key, and a bad value costs only that value.

    An unreadable manifest sets the whole draft aside; losing one rotation or one crop is cheap to redo.
    """
    rotation = _read_tolerant_rotation(fields, page_identifier)
    crops = _read_tolerant_crops(fields, page_identifier)
    return PageFraming(rotation).with_crops(crops)


def _read_tolerant_rotation(fields: dict[str, Any], page_identifier: str) -> PageRotation:
    if ROTATION_DEGREES_KEY not in fields:
        return PageRotation.NONE
    value = fields[ROTATION_DEGREES_KEY]
    try:
        if not _is_whole_number(value):
            raise ValueError(value)
        return PageRotation(value)
    except ValueError:
        LOGGER.warning("Page %s has an invalid rotation %r in the manifest; read as none", page_identifier, value)
        return PageRotation.NONE


def _read_tolerant_crops(fields: dict[str, Any], page_identifier: str) -> list[PageCrop]:
    """The list of the crops; a manifest from before the quadrilaterals has one rectangle under the old key."""
    if CROPS_KEY in fields:
        return _read_crop_list(fields[CROPS_KEY], page_identifier)
    legacy_crop = _read_tolerant_crop(decode_legacy_rectangle, fields.get(LEGACY_CROP_KEY), page_identifier)
    return [] if legacy_crop is None else [legacy_crop]


def _read_crop_list(value: object, page_identifier: str) -> list[PageCrop]:
    if not isinstance(value, list):
        LOGGER.warning("Page %s has invalid crops %r in the manifest; read as no crops", page_identifier, value)
        return []
    if len(value) > MAXIMUM_CROPS_PER_PAGE:
        LOGGER.warning(
            "Page %s has %d crops in the manifest; only the first %d are kept",
            page_identifier,
            len(value),
            MAXIMUM_CROPS_PER_PAGE,
        )
    items = value[:MAXIMUM_CROPS_PER_PAGE]
    crops = (_read_tolerant_crop(decode_crop, item, page_identifier) for item in items)
    return [crop for crop in crops if crop is not None]


def _read_tolerant_crop(
    read_crop: Callable[[object], PageCrop], value: object, page_identifier: str
) -> PageCrop | None:
    if value is None:
        return None
    try:
        return read_crop(value)
    except InvalidCropError:
        LOGGER.warning("Page %s has an invalid crop %r in the manifest; read as no crop", page_identifier, value)
        return None


def _read_color_mode(fields: dict[str, Any]) -> ColorMode:
    value = _read_required(fields, COLOR_MODE_KEY)
    try:
        return ColorMode(value)
    except ValueError as error:
        raise UnreadableDraftError(f"Unknown color mode {value!r}") from error


def _read_finished_document(value: object) -> ScanResult | None:
    if value is None:
        return None
    fields = _as_json_object(value, "finished document")
    output_path = Path(_read_text(fields, PATH_KEY))
    if not output_path.is_absolute():
        raise UnreadableDraftError(f"The finished document path {str(output_path)!r} is not absolute")
    return ScanResult(
        output_path=output_path,
        output_format=OutputFormat.PDF,
        scanned_at=_read_moment(fields, FINALIZED_AT_KEY),
        size_in_bytes=_read_whole_number(fields, SIZE_IN_BYTES_KEY, ALLOWED_SIZES_IN_BYTES),
    )

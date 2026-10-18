from digitalizadora.domain.errors import InvalidSettingsError, ScanFailedError

START_OF_IMAGE = b"\xff\xd8"
MARKER_PREFIX_BYTE = 0xFF
START_OF_SCAN_MARKER_BYTE = 0xDA
APPLICATION_0_MARKER_BYTE = 0xE0
JFIF_IDENTIFIER = b"JFIF\x00"
BYTE_ORDER = "big"

MARKER_SIZE_IN_BYTES = 2
LENGTH_FIELD_SIZE_IN_BYTES = 2
SEGMENT_HEADER_SIZE_IN_BYTES = MARKER_SIZE_IN_BYTES + LENGTH_FIELD_SIZE_IN_BYTES
DENSITY_FIELD_SIZE_IN_BYTES = 2

JFIF_UNITS_OFFSET = 7
JFIF_X_DENSITY_OFFSET = 8
JFIF_Y_DENSITY_OFFSET = 10
JFIF_PAYLOAD_SIZE_NEEDED_FOR_DENSITY = JFIF_Y_DENSITY_OFFSET + DENSITY_FIELD_SIZE_IN_BYTES
JFIF_UNITS_DOTS_PER_INCH = 1
JFIF_VERSION = bytes([1, 1])
JFIF_NO_THUMBNAIL = b"\x00\x00"

MINIMUM_DOTS_PER_INCH = 1
MAXIMUM_DOTS_PER_INCH = 65535


def skip_fill_bytes(jpeg_content: bytes, position: int) -> int:
    """ITU T.81 B.1.1.2 allows any number of 0xFF fill bytes before a marker; return the marker position."""
    while (
        position + 1 < len(jpeg_content)
        and jpeg_content[position] == MARKER_PREFIX_BYTE
        and jpeg_content[position + 1] == MARKER_PREFIX_BYTE
    ):
        position += 1
    return position


def find_jfif_payload_start(jpeg_content: bytes) -> int | None:
    """Return where the JFIF payload starts, or None when no JFIF segment precedes the scan data."""
    position = len(START_OF_IMAGE)
    while True:
        position = skip_fill_bytes(jpeg_content, position)
        header_end = position + SEGMENT_HEADER_SIZE_IN_BYTES
        if header_end > len(jpeg_content) or jpeg_content[position] != MARKER_PREFIX_BYTE:
            raise ScanFailedError("The JPEG marker segments are truncated or malformed")
        marker = jpeg_content[position + 1]
        if marker == START_OF_SCAN_MARKER_BYTE:
            return None
        segment_length = int.from_bytes(jpeg_content[position + MARKER_SIZE_IN_BYTES:header_end], BYTE_ORDER)
        segment_end = position + MARKER_SIZE_IN_BYTES + segment_length
        if segment_length < LENGTH_FIELD_SIZE_IN_BYTES or segment_end > len(jpeg_content):
            raise ScanFailedError("A JPEG segment declares an impossible length")
        is_jfif = marker == APPLICATION_0_MARKER_BYTE and jpeg_content.startswith(JFIF_IDENTIFIER, header_end)
        if is_jfif:
            if segment_end - header_end < JFIF_PAYLOAD_SIZE_NEEDED_FOR_DENSITY:
                raise ScanFailedError("The JFIF segment is too short to hold a density")
            return header_end
        position = segment_end


def build_jfif_segment(density_field: bytes) -> bytes:
    payload = (
        JFIF_IDENTIFIER
        + JFIF_VERSION
        + bytes([JFIF_UNITS_DOTS_PER_INCH])
        + density_field
        + density_field
        + JFIF_NO_THUMBNAIL
    )
    length_field = (len(payload) + LENGTH_FIELD_SIZE_IN_BYTES).to_bytes(LENGTH_FIELD_SIZE_IN_BYTES, BYTE_ORDER)
    return bytes([MARKER_PREFIX_BYTE, APPLICATION_0_MARKER_BYTE]) + length_field + payload


class JpegResolutionService:
    def with_resolution(self, jpeg_content: bytes, dots_per_inch: int) -> bytes:
        if not MINIMUM_DOTS_PER_INCH <= dots_per_inch <= MAXIMUM_DOTS_PER_INCH:
            raise InvalidSettingsError(f"Resolution must be between 1 and 65535 dots per inch, got {dots_per_inch}")
        if not jpeg_content.startswith(START_OF_IMAGE):
            raise ScanFailedError("The scanned content is not a JPEG image")
        density_field = dots_per_inch.to_bytes(DENSITY_FIELD_SIZE_IN_BYTES, BYTE_ORDER)
        payload_start = find_jfif_payload_start(jpeg_content)
        if payload_start is None:
            return START_OF_IMAGE + build_jfif_segment(density_field) + jpeg_content[len(START_OF_IMAGE):]
        rewritten = bytearray(jpeg_content)
        rewritten[payload_start + JFIF_UNITS_OFFSET] = JFIF_UNITS_DOTS_PER_INCH
        x_start = payload_start + JFIF_X_DENSITY_OFFSET
        y_start = payload_start + JFIF_Y_DENSITY_OFFSET
        rewritten[x_start:x_start + DENSITY_FIELD_SIZE_IN_BYTES] = density_field
        rewritten[y_start:y_start + DENSITY_FIELD_SIZE_IN_BYTES] = density_field
        return bytes(rewritten)

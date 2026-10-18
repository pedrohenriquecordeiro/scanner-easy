"""Byte-level edits of Pillow JPEGs, to build scanner images that Pillow itself never writes."""

START_OF_IMAGE_SIZE_IN_BYTES = 2
APPLICATION_0_MARKER_BYTE = 0xE0
START_OF_FRAME_BASELINE_MARKER_BYTE = 0xC0
START_OF_SCAN_MARKER_BYTE = 0xDA
BYTE_ORDER = "big"

MARKER_SIZE_IN_BYTES = 2
LENGTH_FIELD_SIZE_IN_BYTES = 2
SAMPLE_PRECISION_SIZE_IN_BYTES = 1
DIMENSION_FIELD_SIZE_IN_BYTES = 2


def read_segment_length(jpeg_content: bytes, segment_start: int) -> int:
    length_start = segment_start + MARKER_SIZE_IN_BYTES
    return int.from_bytes(jpeg_content[length_start:length_start + LENGTH_FIELD_SIZE_IN_BYTES], BYTE_ORDER)


def find_segment(jpeg_content: bytes, marker_byte: int) -> int:
    """Return where the first segment with this marker starts; meant for well-formed Pillow output only."""
    position = START_OF_IMAGE_SIZE_IN_BYTES
    while jpeg_content[position + 1] != START_OF_SCAN_MARKER_BYTE:
        if jpeg_content[position + 1] == marker_byte:
            return position
        position += MARKER_SIZE_IN_BYTES + read_segment_length(jpeg_content, position)
    raise ValueError(f"No segment with marker 0x{marker_byte:02X} before the scan data")


def strip_jfif_segment(jpeg_content: bytes) -> bytes:
    segment_start = find_segment(jpeg_content, APPLICATION_0_MARKER_BYTE)
    segment_end = segment_start + MARKER_SIZE_IN_BYTES + read_segment_length(jpeg_content, segment_start)
    return jpeg_content[:segment_start] + jpeg_content[segment_end:]


def declare_image_size(jpeg_content: bytes, width_pixels: int, height_pixels: int) -> bytes:
    """Rewrite the size in the baseline frame header without touching the compressed data."""
    frame_start = find_segment(jpeg_content, START_OF_FRAME_BASELINE_MARKER_BYTE)
    height_start = frame_start + MARKER_SIZE_IN_BYTES + LENGTH_FIELD_SIZE_IN_BYTES + SAMPLE_PRECISION_SIZE_IN_BYTES
    width_start = height_start + DIMENSION_FIELD_SIZE_IN_BYTES
    rewritten = bytearray(jpeg_content)
    rewritten[height_start:width_start] = height_pixels.to_bytes(DIMENSION_FIELD_SIZE_IN_BYTES, BYTE_ORDER)
    rewritten[width_start:width_start + DIMENSION_FIELD_SIZE_IN_BYTES] = width_pixels.to_bytes(
        DIMENSION_FIELD_SIZE_IN_BYTES, BYTE_ORDER
    )
    return bytes(rewritten)

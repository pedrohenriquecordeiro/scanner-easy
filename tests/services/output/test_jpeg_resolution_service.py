import io

import pytest
from PIL import Image

from digitalizadora.domain.errors import InvalidSettingsError, ScanFailedError
from digitalizadora.services.output.jpeg_resolution_service import JpegResolutionService
from tests.fakes.jpeg_segments import strip_jfif_segment
from tests.fakes.sample_images import build_sample_jpeg

START_OF_IMAGE = b"\xff\xd8"
START_OF_SCAN_MARKER = b"\xff\xda"
APPLICATION_0_MARKER = b"\xff\xe0"
APPLICATION_1_MARKER = b"\xff\xe1"
FILL_BYTE = b"\xff"
JFIF_SEGMENT_SIZE_IN_BYTES = 18
EXIF_DESCRIPTION_TAG = 0x010E
EXIF_DESCRIPTION = "Digitalizadora"


def read_dots_per_inch(jpeg_content: bytes) -> tuple[int, int] | None:
    with Image.open(io.BytesIO(jpeg_content)) as image:
        return image.info.get("dpi")


def read_exif_description(jpeg_content: bytes) -> str | None:
    with Image.open(io.BytesIO(jpeg_content)) as image:
        return image.getexif().get(EXIF_DESCRIPTION_TAG)


def build_jpeg_with_exif() -> bytes:
    image = Image.new("RGB", (64, 48), "white")
    exif = image.getexif()
    exif[EXIF_DESCRIPTION_TAG] = EXIF_DESCRIPTION
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif.tobytes())
    return buffer.getvalue()


def add_fill_byte_after_the_start_of_image(jpeg_content: bytes) -> bytes:
    return jpeg_content[:2] + FILL_BYTE + jpeg_content[2:]


def test_rewrites_the_density_of_an_existing_jfif_segment():
    rewritten = JpegResolutionService().with_resolution(build_sample_jpeg(), 300)

    assert read_dots_per_inch(rewritten) == (300, 300)


def test_rewrites_a_density_that_was_already_set():
    original = build_sample_jpeg(dots_per_inch=72)

    rewritten = JpegResolutionService().with_resolution(original, 600)

    assert read_dots_per_inch(rewritten) == (600, 600)


def test_rewriting_keeps_the_length_of_the_file():
    original = build_sample_jpeg()

    rewritten = JpegResolutionService().with_resolution(original, 300)

    assert len(rewritten) == len(original)


def test_rewriting_keeps_the_scan_data_byte_for_byte():
    original = build_sample_jpeg()

    rewritten = JpegResolutionService().with_resolution(original, 300)

    original_scan = original[original.index(START_OF_SCAN_MARKER):]
    assert rewritten[rewritten.index(START_OF_SCAN_MARKER):] == original_scan


def test_rewriting_keeps_the_exif_segment_that_follows_the_jfif_segment():
    original = build_jpeg_with_exif()

    rewritten = JpegResolutionService().with_resolution(original, 300)

    assert read_exif_description(rewritten) == EXIF_DESCRIPTION


def test_inserts_a_jfif_segment_when_the_file_has_none():
    original = strip_jfif_segment(build_sample_jpeg())

    inserted = JpegResolutionService().with_resolution(original, 300)

    assert read_dots_per_inch(inserted) == (300, 300)


def test_insertion_adds_exactly_one_jfif_segment():
    original = strip_jfif_segment(build_sample_jpeg())

    inserted = JpegResolutionService().with_resolution(original, 300)

    assert len(inserted) == len(original) + JFIF_SEGMENT_SIZE_IN_BYTES


def test_insertion_keeps_the_scan_data_byte_for_byte():
    original = strip_jfif_segment(build_sample_jpeg())

    inserted = JpegResolutionService().with_resolution(original, 300)

    original_scan = original[original.index(START_OF_SCAN_MARKER):]
    assert inserted[inserted.index(START_OF_SCAN_MARKER):] == original_scan


def test_insertion_keeps_an_exif_segment_that_comes_first():
    original = strip_jfif_segment(build_jpeg_with_exif())
    assert original[2:4] == APPLICATION_1_MARKER

    inserted = JpegResolutionService().with_resolution(original, 300)

    assert inserted[:2] == START_OF_IMAGE
    assert inserted[2 + JFIF_SEGMENT_SIZE_IN_BYTES:] == original[2:]
    assert read_exif_description(inserted) == EXIF_DESCRIPTION


def test_accepts_a_fill_byte_before_the_jfif_marker():
    original = add_fill_byte_after_the_start_of_image(build_sample_jpeg())

    rewritten = JpegResolutionService().with_resolution(original, 300)

    assert read_dots_per_inch(rewritten) == (300, 300)


def test_fill_byte_keeps_the_scan_data_byte_for_byte():
    original = add_fill_byte_after_the_start_of_image(build_sample_jpeg())

    rewritten = JpegResolutionService().with_resolution(original, 300)

    original_scan = original[original.index(START_OF_SCAN_MARKER):]
    assert rewritten[rewritten.index(START_OF_SCAN_MARKER):] == original_scan


def test_inserts_a_jfif_segment_when_a_fill_byte_precedes_the_first_marker():
    original = add_fill_byte_after_the_start_of_image(strip_jfif_segment(build_sample_jpeg()))

    inserted = JpegResolutionService().with_resolution(original, 300)

    assert read_dots_per_inch(inserted) == (300, 300)


MALFORMED_JPEG_CONTENTS = [
    b"",
    b"GIF89a this is not a JPEG",
    START_OF_IMAGE,
    START_OF_IMAGE + APPLICATION_1_MARKER + b"\x00\x04\x00\x00",
    START_OF_IMAGE + b"garbage right after the start of image",
    START_OF_IMAGE + APPLICATION_0_MARKER + b"\x00\x00" + b"x" * 20,
    START_OF_IMAGE + APPLICATION_0_MARKER + b"\x00\x08JFIF\x00\x01" + START_OF_SCAN_MARKER + b"\x00\x02",
    START_OF_IMAGE + FILL_BYTE * 20,
    build_sample_jpeg()[:10],
]


@pytest.mark.parametrize("malformed_content", MALFORMED_JPEG_CONTENTS)
def test_rejects_content_that_is_not_a_well_formed_jpeg_header(malformed_content):
    with pytest.raises(ScanFailedError):
        JpegResolutionService().with_resolution(malformed_content, 300)


@pytest.mark.parametrize("invalid_dots_per_inch", [-1, 0, 65536])
def test_rejects_a_resolution_outside_the_jfif_range(invalid_dots_per_inch):
    with pytest.raises(InvalidSettingsError):
        JpegResolutionService().with_resolution(build_sample_jpeg(), invalid_dots_per_inch)


@pytest.mark.parametrize("limit_dots_per_inch", [1, 65535])
def test_accepts_the_limits_of_the_jfif_range(limit_dots_per_inch):
    result = JpegResolutionService().with_resolution(build_sample_jpeg(), limit_dots_per_inch)

    assert read_dots_per_inch(result) == (limit_dots_per_inch, limit_dots_per_inch)

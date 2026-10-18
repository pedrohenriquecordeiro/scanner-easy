import io

import pytest
from PIL import Image, JpegImagePlugin

from digitalizadora.domain.errors import ScanFailedError
from digitalizadora.services.imaging.thumbnail_service import ThumbnailService
from tests.fakes.jpeg_segments import declare_image_size
from tests.fakes.sample_images import build_sample_jpeg

START_OF_IMAGE = b"\xff\xd8"
LUMINANCE_QUANTIZATION_AT_QUALITY_EIGHTY = 6
TILES_OF_A_JPEG_NOT_YET_DECODED = 1
DECOMPRESSION_BOMB_EDGE_PIXELS = 60000


def read_size(jpeg_content: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(jpeg_content)) as image:
        return image.size


def test_longest_edge_is_reduced_to_the_maximum():
    thumbnail = ThumbnailService().build_thumbnail(build_sample_jpeg(400, 200), 100)

    assert max(read_size(thumbnail)) == 100


def test_aspect_ratio_is_kept_within_one_pixel():
    thumbnail = ThumbnailService().build_thumbnail(build_sample_jpeg(300, 400), 100)

    width, height = read_size(thumbnail)
    assert height == 100
    assert abs(width - 75) <= 1


def test_edge_exactly_at_the_maximum_is_kept():
    thumbnail = ThumbnailService().build_thumbnail(build_sample_jpeg(100, 50), 100)

    assert read_size(thumbnail) == (100, 50)


def test_edge_one_pixel_above_the_maximum_is_reduced():
    thumbnail = ThumbnailService().build_thumbnail(build_sample_jpeg(101, 51), 100)

    assert max(read_size(thumbnail)) == 100


def test_small_image_is_not_enlarged():
    thumbnail = ThumbnailService().build_thumbnail(build_sample_jpeg(64, 48), 480)

    assert read_size(thumbnail) == (64, 48)


def test_output_is_a_jpeg():
    thumbnail = ThumbnailService().build_thumbnail(build_sample_jpeg(), 480)

    assert thumbnail.startswith(START_OF_IMAGE)


def test_output_is_encoded_with_quality_eighty():
    thumbnail = ThumbnailService().build_thumbnail(build_sample_jpeg(), 480)

    with Image.open(io.BytesIO(thumbnail)) as image:
        assert image.quantization[0][0] == LUMINANCE_QUANTIZATION_AT_QUALITY_EIGHTY


def test_requests_the_jpeg_draft_mode_before_decoding(monkeypatch):
    recorded_requests = []
    original_draft = JpegImagePlugin.JpegImageFile.draft

    def recording_draft(image, mode, size):
        recorded_requests.append((mode, size, len(image.tile)))
        return original_draft(image, mode, size)

    monkeypatch.setattr(JpegImagePlugin.JpegImageFile, "draft", recording_draft)

    ThumbnailService().build_thumbnail(build_sample_jpeg(400, 200), 100)

    assert recorded_requests[0] == ("RGB", (100, 100), TILES_OF_A_JPEG_NOT_YET_DECODED)


UNREADABLE_CONTENTS = [
    b"",
    b"not an image",
    build_sample_jpeg()[:-30],
    declare_image_size(build_sample_jpeg(), DECOMPRESSION_BOMB_EDGE_PIXELS, DECOMPRESSION_BOMB_EDGE_PIXELS),
]


@pytest.mark.parametrize("unreadable_content", UNREADABLE_CONTENTS)
def test_unreadable_content_raises_scan_failed(unreadable_content):
    with pytest.raises(ScanFailedError):
        ThumbnailService().build_thumbnail(unreadable_content, 480)

import io

import pytest
from PIL import Image

from tests.fakes.jpeg_segments import declare_image_size, strip_jfif_segment
from tests.fakes.sample_images import build_sample_jpeg

PILLOW_JFIF_SEGMENT_SIZE_IN_BYTES = 18


def test_stripped_jpeg_has_no_jfif_segment():
    stripped = strip_jfif_segment(build_sample_jpeg())

    with Image.open(io.BytesIO(stripped)) as image:
        assert "jfif" not in image.info


def test_stripping_removes_exactly_the_jfif_segment():
    original = build_sample_jpeg()

    assert len(strip_jfif_segment(original)) == len(original) - PILLOW_JFIF_SEGMENT_SIZE_IN_BYTES


def test_stripped_jpeg_still_decodes():
    stripped = strip_jfif_segment(build_sample_jpeg(64, 48))

    with Image.open(io.BytesIO(stripped)) as image:
        image.load()
        assert image.size == (64, 48)


def test_stripping_a_jpeg_without_jfif_raises_value_error():
    stripped = strip_jfif_segment(build_sample_jpeg())

    with pytest.raises(ValueError):
        strip_jfif_segment(stripped)


def test_declared_size_is_the_size_pillow_reads():
    declared = declare_image_size(build_sample_jpeg(64, 48), 640, 480)

    with Image.open(io.BytesIO(declared)) as image:
        assert image.size == (640, 480)


def test_declaring_a_size_keeps_the_length_of_the_file():
    original = build_sample_jpeg()

    assert len(declare_image_size(original, 640, 480)) == len(original)

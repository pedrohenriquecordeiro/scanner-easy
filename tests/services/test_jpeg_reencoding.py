import io

import pytest
from PIL import Image

from digitalizadora.domain.image_adjustment import REENCODING_JPEG_QUALITY
from digitalizadora.domain.page_rotation import PageRotation
from digitalizadora.services.jpeg_reencoding import (
    TRANSPOSE_BY_ROTATION,
    read_encoding_options,
    replace_with,
)
from tests.fakes.synthetic_scans import build_scan_jpeg

ICC_PROFILE = b"not a real profile but kept as it is"


def open_jpeg(**save_options: object) -> Image.Image:
    return Image.open(io.BytesIO(build_scan_jpeg((32, 24), **save_options)))


def test_the_options_ask_for_the_fixed_quality() -> None:
    with open_jpeg() as image:
        assert read_encoding_options(image)["quality"] == REENCODING_JPEG_QUALITY


def test_the_options_keep_the_density_of_the_source() -> None:
    with open_jpeg(dpi=(300, 300)) as image:
        assert read_encoding_options(image)["dpi"] == (300, 300)


def test_the_options_leave_out_a_density_the_source_does_not_have() -> None:
    with open_jpeg() as image:
        assert "dpi" not in read_encoding_options(image)


def test_the_options_keep_the_icc_profile_of_the_source() -> None:
    with open_jpeg(icc_profile=ICC_PROFILE) as image:
        assert read_encoding_options(image)["icc_profile"] == ICC_PROFILE


def test_the_options_keep_the_chroma_subsampling_of_the_source() -> None:
    with open_jpeg(subsampling=0) as image:
        assert read_encoding_options(image)["subsampling"] == 0


def test_replace_with_returns_the_transformed_image() -> None:
    transformed = replace_with(open_jpeg(), lambda image: image.transpose(Image.Transpose.ROTATE_90))

    assert transformed.size == (24, 32)


def test_replace_with_closes_the_source() -> None:
    source = open_jpeg()
    source.load()

    replace_with(source, lambda image: image.copy())

    with pytest.raises(ValueError):
        source.getpixel((0, 0))


def test_every_rotation_but_none_has_a_transposition() -> None:
    assert set(TRANSPOSE_BY_ROTATION) == set(PageRotation) - {PageRotation.NONE}

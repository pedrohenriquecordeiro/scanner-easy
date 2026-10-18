import io

import pytest
from PIL import Image

from digitalizadora.domain.scan_quality import pixels_per_page
from digitalizadora.services.image_pixel_limit import (
    MAXIMUM_SCANNER_IMAGE_PIXELS,
    raise_decompression_limit_to_scanner_size,
)
from tests.fakes.jpeg_segments import declare_image_size
from tests.fakes.sample_images import build_sample_jpeg

FULL_GLASS_PIXELS_AT_1200_DPI = 10200 * 14032
FORGED_EDGE_PIXELS = 20000
PILLOW_DEFAULT_LIMIT_PIXELS = 89_478_485


@pytest.fixture(autouse=True)
def restore_pillow_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", PILLOW_DEFAULT_LIMIT_PIXELS)


def test_the_limit_is_the_full_page_at_1200_dots_per_inch_plus_five_percent():
    assert MAXIMUM_SCANNER_IMAGE_PIXELS == 150_239_880


def test_the_limit_is_derived_from_the_page_estimate():
    assert MAXIMUM_SCANNER_IMAGE_PIXELS == -(-pixels_per_page(1200) * 105 // 100)


def test_the_real_glass_at_1200_dots_per_inch_stays_below_the_limit():
    assert FULL_GLASS_PIXELS_AT_1200_DPI < MAXIMUM_SCANNER_IMAGE_PIXELS


def test_raising_the_limit_sets_the_limit_of_pillow():
    raise_decompression_limit_to_scanner_size()

    assert Image.MAX_IMAGE_PIXELS == MAXIMUM_SCANNER_IMAGE_PIXELS


def test_the_default_limit_of_pillow_is_below_the_real_glass_at_1200_dots_per_inch():
    assert PILLOW_DEFAULT_LIMIT_PIXELS < FULL_GLASS_PIXELS_AT_1200_DPI


def test_a_forged_huge_image_is_still_refused_after_raising_the_limit():
    raise_decompression_limit_to_scanner_size()
    forged_jpeg = declare_image_size(build_sample_jpeg(), FORGED_EDGE_PIXELS, FORGED_EDGE_PIXELS)

    with pytest.raises(Image.DecompressionBombError):
        Image.open(io.BytesIO(forged_jpeg))

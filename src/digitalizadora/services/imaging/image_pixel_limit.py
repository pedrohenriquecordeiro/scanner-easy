from math import ceil

from PIL import Image

from digitalizadora.domain.settings.scan_quality import HIGHEST_DOTS_PER_INCH, pixels_per_page

PIXEL_LIMIT_MARGIN = 1.05
# The estimate of a full page at 1200 dpi is 143,085,600 pixels; the glass the printer really delivers has 143,126,400.
MAXIMUM_SCANNER_IMAGE_PIXELS = ceil(pixels_per_page(HIGHEST_DOTS_PER_INCH) * PIXEL_LIMIT_MARGIN)


def raise_decompression_limit_to_scanner_size() -> None:
    """Pillow only warns above this limit and refuses above twice of it.

    Pillow's default (89 million pixels) would warn on every full page at 1200 dots per inch and hide real
    warnings; a forged huge image is still refused.
    """
    Image.MAX_IMAGE_PIXELS = MAXIMUM_SCANNER_IMAGE_PIXELS

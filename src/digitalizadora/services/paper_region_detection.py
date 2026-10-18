"""Finds the sheet of paper on the glass in a small grayscale preview, with Pillow only.

The border of the preview is taken as the background (the lid, open or closed). Whatever differs enough from
it is the sheet. When the border is not trustworthy or the result is not plausible, there is no region and the
whole image is kept: failing to "do not crop" never loses content.
"""

from PIL import Image, ImageFilter

from digitalizadora.domain.pixel_region import PixelRegion

PREVIEW_MAXIMUM_EDGE_PIXELS = 400
BORDER_WIDTH_RATIO = 0.015
MINIMUM_BORDER_WIDTH_PIXELS = 2
BACKGROUND_TOLERANCE_LEVELS = 20
MINIMUM_BACKGROUND_BORDER_SHARE = 0.6
FOREGROUND_DIFFERENCE_LEVELS = 40
NOISE_FILTER_SIZE = 7
MINIMUM_LINE_COVERAGE = 0.05
MINIMUM_REGION_SHARE = 0.10
MAXIMUM_REGION_SHARE = 0.95
# Beyond the design: a sheet is a solid block, while the bounding box of loose foreground (text, scratches) is not.
MINIMUM_REGION_FILL_SHARE = 0.5
# Beyond the design: a sheet flush with a corner touches two sides of the glass; a region on three or four sides
# is the background around a big sheet taken for the sheet itself.
MAXIMUM_TOUCHED_SIDES = 2

GRAY_LEVEL_COUNT = 256
MASK_ON = 255
MASK_OFF = 0
LINE_COVERAGE_THRESHOLD = round(MINIMUM_LINE_COVERAGE * MASK_ON)


def _border_width(preview: Image.Image) -> int:
    return max(MINIMUM_BORDER_WIDTH_PIXELS, round(BORDER_WIDTH_RATIO * max(preview.size)))


def _border_strips(preview: Image.Image, border_width: int) -> list[Image.Image]:
    width, height = preview.size
    return [
        preview.crop((0, 0, width, border_width)),
        preview.crop((0, height - border_width, width, height)),
        preview.crop((0, border_width, border_width, height - border_width)),
        preview.crop((width - border_width, border_width, width, height - border_width)),
    ]


def _border_histogram(preview: Image.Image) -> list[int]:
    histogram = [0] * GRAY_LEVEL_COUNT
    for strip in _border_strips(preview, _border_width(preview)):
        for level, count in enumerate(strip.histogram()):
            histogram[level] += count
    return histogram


def _median_level(histogram: list[int]) -> int:
    half_of_pixels = sum(histogram) / 2
    counted_pixels = 0
    for level, count in enumerate(histogram):
        counted_pixels += count
        if counted_pixels >= half_of_pixels:
            return level
    return GRAY_LEVEL_COUNT - 1


def _background_share(histogram: list[int], background_level: int) -> float:
    lowest_level = max(0, background_level - BACKGROUND_TOLERANCE_LEVELS)
    highest_level = min(GRAY_LEVEL_COUNT - 1, background_level + BACKGROUND_TOLERANCE_LEVELS)
    return sum(histogram[lowest_level : highest_level + 1]) / sum(histogram)


def _foreground_mask(preview: Image.Image, background_level: int) -> Image.Image:
    table = [
        MASK_ON if abs(level - background_level) > FOREGROUND_DIFFERENCE_LEVELS else MASK_OFF
        for level in range(GRAY_LEVEL_COUNT)
    ]
    return preview.point(table).filter(ImageFilter.MedianFilter(NOISE_FILTER_SIZE))


def _covered_extent(profile: Image.Image) -> tuple[int, int, int, int] | None:
    return profile.point(lambda level: MASK_ON if level >= LINE_COVERAGE_THRESHOLD else MASK_OFF).getbbox()


def _covered_region(mask: Image.Image) -> PixelRegion | None:
    """The first and last row and column with enough foreground: it ignores loose dust and scratches."""
    width, height = mask.size
    columns_extent = _covered_extent(mask.reduce((1, height)))
    rows_extent = _covered_extent(mask.reduce((width, 1)))
    if columns_extent is None or rows_extent is None:
        return None
    return PixelRegion(columns_extent[0], rows_extent[1], columns_extent[2], rows_extent[3])


def _fill_share(mask: Image.Image, region: PixelRegion) -> float:
    covered_pixels = mask.crop(region.as_box()).histogram()[MASK_ON]
    return covered_pixels / region.area


def _touched_side_count(region: PixelRegion, preview: Image.Image) -> int:
    width, height = preview.size
    border_width = _border_width(preview)
    return sum(
        (
            region.left <= border_width,
            region.top <= border_width,
            region.right >= width - border_width,
            region.bottom >= height - border_width,
        )
    )


def detect_paper_region(preview: Image.Image) -> PixelRegion | None:
    """preview: mode "L" with the longest edge up to PREVIEW_MAXIMUM_EDGE_PIXELS. Returns pixels of the preview."""
    width, height = preview.size
    if min(width, height) <= 2 * MINIMUM_BORDER_WIDTH_PIXELS:
        return None
    border_histogram = _border_histogram(preview)
    background_level = _median_level(border_histogram)
    if _background_share(border_histogram, background_level) < MINIMUM_BACKGROUND_BORDER_SHARE:
        return None
    mask = _foreground_mask(preview, background_level)
    region = _covered_region(mask)
    if region is None:
        return None
    region_share = region.area / (width * height)
    if not MINIMUM_REGION_SHARE <= region_share <= MAXIMUM_REGION_SHARE:
        return None
    if _fill_share(mask, region) < MINIMUM_REGION_FILL_SHARE:
        return None
    if _touched_side_count(region, preview) > MAXIMUM_TOUCHED_SIDES:
        return None
    return region

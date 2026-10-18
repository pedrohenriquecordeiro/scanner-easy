"""Finds the sheet of paper on the glass in a small grayscale preview, with Pillow only.

The border of the preview is taken as the background (the lid, open or closed). Whatever differs enough from
it is the sheet. When the border is not trustworthy or the result is not plausible, there is no region and the
whole image is kept: failing to "do not crop" never loses content.
"""

from PIL import Image, ImageChops, ImageFilter

from digitalizadora.domain.pixel_region import PixelRegion

PREVIEW_MAXIMUM_EDGE_PIXELS = 400
BORDER_WIDTH_RATIO = 0.015
MINIMUM_BORDER_WIDTH_PIXELS = 2
BACKGROUND_TOLERANCE_LEVELS = 20
MINIMUM_BACKGROUND_BORDER_SHARE = 0.6
FOREGROUND_DIFFERENCE_LEVELS = 20
# Looser than the foreground, to see what the region left out: a dark part of the page next to the lid.
SURROUNDING_DIFFERENCE_LEVELS = 10
MAXIMUM_SURROUNDING_FOREGROUND_SHARE = 0.25
NOISE_FILTER_SIZE = 7
MINIMUM_LINE_COVERAGE = 0.05
MINIMUM_REGION_SHARE = 0.10
MAXIMUM_REGION_SHARE = 0.95
# Beyond the design: a sheet is a solid block, while the bounding box of loose foreground (text, scratches) is not.
MINIMUM_REGION_FILL_SHARE = 0.75
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


def _border_histogram(band: Image.Image) -> list[int]:
    histogram = [0] * GRAY_LEVEL_COUNT
    for strip in _border_strips(band, _border_width(band)):
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


def _border_is_background(border_histograms: list[list[int]], background_levels: list[int]) -> bool:
    """Every colour channel of the border must be steady around its own median."""
    background_shares = [
        _background_share(histogram, background_level)
        for histogram, background_level in zip(border_histograms, background_levels, strict=True)
    ]
    return min(background_shares) >= MINIMUM_BACKGROUND_BORDER_SHARE


def _band_difference_mask(band: Image.Image, background_level: int, difference_levels: int) -> Image.Image:
    table = [
        MASK_ON if abs(level - background_level) > difference_levels else MASK_OFF
        for level in range(GRAY_LEVEL_COUNT)
    ]
    return band.point(table)


def _foreground_mask(bands: list[Image.Image], background_levels: list[int], difference_levels: int) -> Image.Image:
    """A pixel is foreground when any colour channel differs enough, so a dark but coloured cover is not lost."""
    band_masks = [
        _band_difference_mask(band, background_level, difference_levels)
        for band, background_level in zip(bands, background_levels, strict=True)
    ]
    mask = band_masks[0]
    for band_mask in band_masks[1:]:
        mask = ImageChops.lighter(mask, band_mask)
    return mask.filter(ImageFilter.MedianFilter(NOISE_FILTER_SIZE))


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


def _surrounding_foreground_share(loose_mask: Image.Image, region: PixelRegion, ring_width: int) -> float:
    """Share of the ring just outside the region that does not look like background; 0 when there is no ring."""
    width, height = loose_mask.size
    grown_region = region.grown_within(ring_width, (width, height))
    ring_area = grown_region.area - region.area
    if ring_area == 0:
        return 0.0
    grown_foreground = loose_mask.crop(grown_region.as_box()).histogram()[MASK_ON]
    region_foreground = loose_mask.crop(region.as_box()).histogram()[MASK_ON]
    return (grown_foreground - region_foreground) / ring_area


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
    """preview: mode "L" or "RGB" with the longest edge up to PREVIEW_MAXIMUM_EDGE_PIXELS. Returns pixels of it."""
    width, height = preview.size
    if min(width, height) <= 2 * MINIMUM_BORDER_WIDTH_PIXELS:
        return None
    bands = list(preview.split())
    border_histograms = [_border_histogram(band) for band in bands]
    background_levels = [_median_level(histogram) for histogram in border_histograms]
    if not _border_is_background(border_histograms, background_levels):
        return None
    mask = _foreground_mask(bands, background_levels, FOREGROUND_DIFFERENCE_LEVELS)
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
    loose_mask = _foreground_mask(bands, background_levels, SURROUNDING_DIFFERENCE_LEVELS)
    if _surrounding_foreground_share(loose_mask, region, _border_width(preview)) > MAXIMUM_SURROUNDING_FOREGROUND_SHARE:
        return None
    return region

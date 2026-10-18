SUPPORTED_DOTS_PER_INCH: tuple[int, ...] = (75, 100, 150, 200, 300, 400, 600, 1200)
# Gate 0 (2026-10-17): 71,9 s per A4 colour page at 600 dots per inch on the real printer.
REFERENCE_DOTS_PER_INCH = 600
SLOW_SCAN_DOTS_PER_INCH = 600
HIGHEST_DOTS_PER_INCH = 1200
PLATEN_WIDTH_INCHES = 8.5
PLATEN_HEIGHT_INCHES = 11.69


def is_supported_dots_per_inch(dots_per_inch: int) -> bool:
    return dots_per_inch in SUPPORTED_DOTS_PER_INCH


def pixels_per_page(dots_per_inch: int) -> int:
    return round(PLATEN_WIDTH_INCHES * dots_per_inch) * round(PLATEN_HEIGHT_INCHES * dots_per_inch)


def scan_timeout_multiplier(dots_per_inch: int) -> float:
    """The scanner time grows with the page area: one up to the measured resolution, then the area ratio."""
    return max(1.0, (dots_per_inch / REFERENCE_DOTS_PER_INCH) ** 2)

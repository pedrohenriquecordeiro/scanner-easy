from dataclasses import dataclass

from digitalizadora.domain.errors import InvalidSettingsError

MINIMUM_JPEG_QUALITY = 50
MAXIMUM_JPEG_QUALITY = 100
DEFAULT_JPEG_QUALITY = 90
# A rewritten JPEG is this many times the size of the scanner's (which is about quality 50), measured per quality.
SIZE_FACTOR_UP_TO_QUALITY_90 = 2
SIZE_FACTOR_UP_TO_QUALITY_97 = 3
SIZE_FACTOR_ABOVE_QUALITY_97 = 4
QUALITY_90 = 90
QUALITY_97 = 97


def is_valid_jpeg_quality(jpeg_quality: object) -> bool:
    """A whole number from 50 to 100; a boolean is not one."""
    return (
        isinstance(jpeg_quality, int)
        and not isinstance(jpeg_quality, bool)
        and MINIMUM_JPEG_QUALITY <= jpeg_quality <= MAXIMUM_JPEG_QUALITY
    )


def rendered_size_factor(jpeg_quality: int) -> int:
    """How many times bigger than the scanner's JPEG the same image comes out when it is written again."""
    if jpeg_quality <= QUALITY_90:
        return SIZE_FACTOR_UP_TO_QUALITY_90
    if jpeg_quality <= QUALITY_97:
        return SIZE_FACTOR_UP_TO_QUALITY_97
    return SIZE_FACTOR_ABOVE_QUALITY_97


@dataclass(frozen=True)
class ImageAdjustment:
    auto_crop: bool = False
    jpeg_quality: int = DEFAULT_JPEG_QUALITY

    def __post_init__(self) -> None:
        if not is_valid_jpeg_quality(self.jpeg_quality):
            raise InvalidSettingsError(
                f"The JPEG quality must be a whole number from {MINIMUM_JPEG_QUALITY} to {MAXIMUM_JPEG_QUALITY}, "
                f"got {self.jpeg_quality!r}"
            )

    @property
    def is_active(self) -> bool:
        """Only the automatic crop: the quality alone changes nothing until an image is written again."""
        return self.auto_crop


NO_ADJUSTMENT = ImageAdjustment()

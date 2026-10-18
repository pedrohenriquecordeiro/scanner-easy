from dataclasses import dataclass

# Every image written again (cropped, turned or put in a PDF) takes this quality; there is no setting for it.
REENCODING_JPEG_QUALITY = 90
# A rewritten JPEG is this many times the size of the scanner's (which is about quality 50) at quality 90.
RENDERED_SIZE_FACTOR = 2


@dataclass(frozen=True)
class ImageAdjustment:
    auto_crop: bool = False
    crop_margin: bool = True

    @property
    def is_active(self) -> bool:
        """Only the automatic crop: nothing changes until an image is written again."""
        return self.auto_crop


NO_ADJUSTMENT = ImageAdjustment()

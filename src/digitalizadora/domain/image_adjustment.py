from dataclasses import dataclass

# Every image written again (cropped, turned or put in a PDF) takes this quality; there is no setting for it.
REENCODING_JPEG_QUALITY = 100
# A rewritten JPEG at quality 100 measured about 3 times the size of the scanner's (about quality 50).
RENDERED_SIZE_FACTOR = 4


@dataclass(frozen=True)
class ImageAdjustment:
    auto_crop: bool = False
    crop_margin: bool = True

    @property
    def is_active(self) -> bool:
        """Only the automatic crop: nothing changes until an image is written again."""
        return self.auto_crop


NO_ADJUSTMENT = ImageAdjustment()

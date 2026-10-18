from dataclasses import dataclass, replace

from digitalizadora.domain.page_crop import PageCrop
from digitalizadora.domain.page_rotation import DEGREES_IN_A_QUARTER_TURN, PageRotation


@dataclass(frozen=True)
class PageFraming:
    """How a stored page is shown and saved: the rotation and the crop; the stored JPEG never changes.

    The crop is in the orientation the page is displayed in, that is, after the rotation.
    """

    rotation: PageRotation = PageRotation.NONE
    crop: PageCrop | None = None

    @property
    def needs_rendering(self) -> bool:
        return self.rotation is not PageRotation.NONE or self.crop is not None

    def turned_clockwise(self) -> "PageFraming":
        turned_crop = None if self.crop is None else self.crop.turned_clockwise()
        return PageFraming(self.rotation.turned_clockwise(), turned_crop)

    def with_crop(self, crop: PageCrop | None) -> "PageFraming":
        """A crop that covers the whole page is the same as no crop."""
        if crop is not None and crop.covers_whole_page:
            return replace(self, crop=None)
        return replace(self, crop=crop)

    def crop_on_master(self) -> PageCrop | None:
        """The crop turned back to the orientation of the JPEG the scanner delivered."""
        crop = self.crop
        if crop is None:
            return None
        for _ in range(self._quarter_turn_count()):
            crop = crop.turned_counterclockwise()
        return crop

    def crop_from_master(self, master_crop: PageCrop) -> PageCrop:
        """A crop found on the stored JPEG, in the orientation the page is displayed in."""
        crop = master_crop
        for _ in range(self._quarter_turn_count()):
            crop = crop.turned_clockwise()
        return crop

    def _quarter_turn_count(self) -> int:
        return self.rotation.value // DEGREES_IN_A_QUARTER_TURN


UNFRAMED = PageFraming()

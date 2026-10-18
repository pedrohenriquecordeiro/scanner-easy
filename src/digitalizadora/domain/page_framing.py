from collections.abc import Sequence
from dataclasses import dataclass, replace

from digitalizadora.domain.errors import InvalidCropError
from digitalizadora.domain.page_crop import PageCrop
from digitalizadora.domain.page_rotation import DEGREES_IN_A_QUARTER_TURN, PageRotation

MAXIMUM_CROPS_PER_PAGE = 2
# Two crops share a row of the page when their vertical ranges overlap by more than this share of the shorter one.
READING_ORDER_ROW_OVERLAP_SHARE = 0.5


def _vertical_range(crop: PageCrop) -> tuple[float, float]:
    edges = crop.bounding_edges
    return (edges.top, edges.bottom)


def _centre(crop: PageCrop) -> tuple[float, float]:
    count = len(crop.corners)
    return (sum(corner.x for corner in crop.corners) / count, sum(corner.y for corner in crop.corners) / count)


def _share_a_row(first: PageCrop, second: PageCrop) -> bool:
    first_top, first_bottom = _vertical_range(first)
    second_top, second_bottom = _vertical_range(second)
    overlap = min(first_bottom, second_bottom) - max(first_top, second_top)
    shorter_height = min(first_bottom - first_top, second_bottom - second_top)
    return overlap > READING_ORDER_ROW_OVERLAP_SHARE * shorter_height


def put_in_reading_order(crops: Sequence[PageCrop]) -> tuple[PageCrop, ...]:
    """Left to right when the crops share a row of the page, otherwise top to bottom; a tie keeps the arrival order."""
    if len(crops) != MAXIMUM_CROPS_PER_PAGE:
        return tuple(crops)
    first, second = crops
    axis = 0 if _share_a_row(first, second) else 1
    return (second, first) if _centre(second)[axis] < _centre(first)[axis] else (first, second)


@dataclass(frozen=True)
class PageFraming:
    """How a stored page is shown and saved: the rotation and the crops; the stored JPEG never changes.

    The crops are in the orientation the page is displayed in, that is, after the rotation, in reading order.
    Each crop is one output: a page of the PDF in the document mode, a file in the quick mode.
    """

    rotation: PageRotation = PageRotation.NONE
    crops: tuple[PageCrop, ...] = ()

    def __post_init__(self) -> None:
        if len(self.crops) > MAXIMUM_CROPS_PER_PAGE:
            raise InvalidCropError(f"A page has at most {MAXIMUM_CROPS_PER_PAGE} crops, got {len(self.crops)}")

    @property
    def needs_rendering(self) -> bool:
        return self.rotation is not PageRotation.NONE or bool(self.crops)

    @property
    def output_count(self) -> int:
        return max(1, len(self.crops))

    def turned_clockwise(self) -> "PageFraming":
        turned_crops = put_in_reading_order([crop.turned_clockwise() for crop in self.crops])
        return PageFraming(self.rotation.turned_clockwise(), turned_crops)

    def with_crops(self, crops: Sequence[PageCrop]) -> "PageFraming":
        """A crop that covers the whole page is the same as no crop."""
        kept_crops = [crop for crop in crops if not crop.covers_whole_page]
        return replace(self, crops=put_in_reading_order(kept_crops))

    def crops_on_master(self) -> tuple[PageCrop, ...]:
        """The crops turned back to the orientation of the JPEG the scanner delivered."""
        quarter_turns = self._quarter_turn_count()
        return tuple(crop.seen_on_master(quarter_turns) for crop in self.crops)

    def crops_from_master(self, master_crops: Sequence[PageCrop]) -> tuple[PageCrop, ...]:
        """Crops found on the stored JPEG, in the orientation the page is displayed in."""
        crops = list(master_crops)
        for _ in range(self._quarter_turn_count()):
            crops = [crop.turned_clockwise() for crop in crops]
        return put_in_reading_order(crops)

    def _quarter_turn_count(self) -> int:
        return self.rotation.value // DEGREES_IN_A_QUARTER_TURN


UNFRAMED = PageFraming()

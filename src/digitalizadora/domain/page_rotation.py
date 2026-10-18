from enum import Enum

DEGREES_IN_A_QUARTER_TURN = 90
DEGREES_IN_A_FULL_TURN = 360


class PageRotation(int, Enum):
    """Clockwise turn applied to a scanned page."""

    NONE = 0
    CLOCKWISE_90 = 90
    HALF_TURN = 180
    COUNTERCLOCKWISE_90 = 270

    def turned_clockwise(self) -> "PageRotation":
        return PageRotation((self.value + DEGREES_IN_A_QUARTER_TURN) % DEGREES_IN_A_FULL_TURN)

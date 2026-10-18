from dataclasses import dataclass


def _round_down_ratio(value: int, numerator: int, denominator: int) -> int:
    return value * numerator // denominator


def _round_up_ratio(value: int, numerator: int, denominator: int) -> int:
    return -(-value * numerator // denominator)


@dataclass(frozen=True)
class PixelRegion:
    """A rectangle of pixels with the coordinates of Pillow: right and bottom are exclusive."""

    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def area(self) -> int:
        return self.width * self.height

    def as_box(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.right, self.bottom)

    def scaled(self, from_size: tuple[int, int], to_size: tuple[int, int]) -> "PixelRegion":
        """The same region in an image of another size; the origin rounds down and the far edges round up."""
        from_width, from_height = from_size
        to_width, to_height = to_size
        return PixelRegion(
            left=_round_down_ratio(self.left, to_width, from_width),
            top=_round_down_ratio(self.top, to_height, from_height),
            right=_round_up_ratio(self.right, to_width, from_width),
            bottom=_round_up_ratio(self.bottom, to_height, from_height),
        )

    def grown_within(self, margin: int, limits: tuple[int, int]) -> "PixelRegion":
        limit_width, limit_height = limits
        return PixelRegion(
            left=max(0, self.left - margin),
            top=max(0, self.top - margin),
            right=min(limit_width, self.right + margin),
            bottom=min(limit_height, self.bottom + margin),
        )

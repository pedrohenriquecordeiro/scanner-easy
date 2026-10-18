from dataclasses import dataclass


@dataclass(frozen=True)
class ImageAdjustment:
    auto_crop: bool = False

    @property
    def is_active(self) -> bool:
        return self.auto_crop


NO_ADJUSTMENT = ImageAdjustment()

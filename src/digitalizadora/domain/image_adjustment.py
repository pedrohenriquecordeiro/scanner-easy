from dataclasses import dataclass

from digitalizadora.domain.page_rotation import PageRotation


@dataclass(frozen=True)
class ImageAdjustment:
    rotation: PageRotation = PageRotation.NONE
    auto_crop: bool = False

    @property
    def is_active(self) -> bool:
        return self.rotation is not PageRotation.NONE or self.auto_crop


NO_ADJUSTMENT = ImageAdjustment()

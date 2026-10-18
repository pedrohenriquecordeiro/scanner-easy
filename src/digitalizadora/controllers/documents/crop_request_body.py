from pydantic import BaseModel, Field, StrictFloat, StrictInt

from digitalizadora.domain.imaging.page_crop import CropCorner, PageCrop
from digitalizadora.domain.imaging.page_framing import MAXIMUM_CROPS_PER_PAGE


class CropCornerRequestBody(BaseModel):
    x: StrictInt | StrictFloat
    y: StrictInt | StrictFloat

    def to_crop_corner(self) -> CropCorner:
        return CropCorner(self.x, self.y)


class PageCropRequestBody(BaseModel):
    """One crop: four corners in fractions of the page as it is displayed, clockwise from the top left."""

    top_left: CropCornerRequestBody
    top_right: CropCornerRequestBody
    bottom_right: CropCornerRequestBody
    bottom_left: CropCornerRequestBody

    def to_page_crop(self) -> PageCrop:
        return PageCrop.rounded(
            [
                self.top_left.to_crop_corner(),
                self.top_right.to_crop_corner(),
                self.bottom_right.to_crop_corner(),
                self.bottom_left.to_crop_corner(),
            ]
        )


class PageCropsRequestBody(BaseModel):
    """{"crops": []} removes the crops of the page."""

    crops: list[PageCropRequestBody] = Field(max_length=MAXIMUM_CROPS_PER_PAGE)

    def to_page_crops(self) -> list[PageCrop]:
        return [crop.to_page_crop() for crop in self.crops]

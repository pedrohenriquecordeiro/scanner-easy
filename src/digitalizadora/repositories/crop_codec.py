"""The JSON form of a crop, shared by the manifests: four corners named by their role, in fractions of the page."""

from digitalizadora.domain.errors import InvalidCropError
from digitalizadora.domain.page_crop import CROP_CORNER_ROLES, CropCorner, PageCrop, RectangleEdges

LEGACY_CROP_EDGE_KEYS = ("left", "top", "right", "bottom")


def encode_crop(crop: PageCrop) -> dict[str, dict[str, float]]:
    return {
        corner_role: {"x": corner.x, "y": corner.y}
        for corner_role, corner in zip(CROP_CORNER_ROLES, crop.corners, strict=True)
    }


def decode_crop(value: object) -> PageCrop:
    """InvalidCropError for anything that is not a valid crop, whatever way it is wrong."""
    if not isinstance(value, dict):
        raise InvalidCropError("The crop is not an object")
    try:
        return PageCrop(*(CropCorner(value[role]["x"], value[role]["y"]) for role in CROP_CORNER_ROLES))
    except (KeyError, TypeError) as error:
        raise InvalidCropError(f"The crop is missing a corner or a coordinate: {error!r}") from error


def decode_legacy_rectangle(value: object) -> PageCrop:
    """The rectangle of the manifests from before the quadrilaterals: left, top, right, bottom."""
    if not isinstance(value, dict):
        raise InvalidCropError("The crop is not an object")
    try:
        return PageCrop.from_rectangle(RectangleEdges(*(value[edge_key] for edge_key in LEGACY_CROP_EDGE_KEYS)))
    except KeyError as error:
        raise InvalidCropError(f"The crop is missing an edge: {error!r}") from error

from digitalizadora.domain.page_crop import CropCorner, PageCrop, RectangleEdges


def rectangle(left: float, top: float, right: float, bottom: float) -> PageCrop:
    return PageCrop.from_rectangle(RectangleEdges(left, top, right, bottom))


def quadrilateral(*points: tuple[float, float]) -> PageCrop:
    """Four (x, y) points in the role order: top left, top right, bottom right, bottom left."""
    return PageCrop(*(CropCorner(x, y) for x, y in points))

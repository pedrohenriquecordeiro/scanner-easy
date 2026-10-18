from digitalizadora.domain.page_crop import CropCorner, PageCrop, RectangleEdges


def rectangle(edges: tuple[float, float, float, float]) -> PageCrop:
    """A plain rectangle from its (left, top, right, bottom) fractions."""
    return PageCrop.from_rectangle(RectangleEdges(*edges))


def quadrilateral(*points: tuple[float, float]) -> PageCrop:
    """Four (x, y) points in the role order: top left, top right, bottom right, bottom left."""
    return PageCrop(*(CropCorner(x, y) for x, y in points))

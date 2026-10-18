from collections.abc import Callable
from typing import Any

from PIL import Image, JpegImagePlugin

from digitalizadora.domain.page_rotation import PageRotation

NO_CHROMA_SUBSAMPLING = -1
# Pillow turns counterclockwise, the page turns clockwise.
TRANSPOSE_BY_ROTATION = {
    PageRotation.CLOCKWISE_90: Image.Transpose.ROTATE_270,
    PageRotation.HALF_TURN: Image.Transpose.ROTATE_180,
    PageRotation.COUNTERCLOCKWISE_90: Image.Transpose.ROTATE_90,
}


def replace_with(image: Image.Image, transformation: Callable[[Image.Image], Image.Image]) -> Image.Image:
    """Holds at most two full images at a time: the source is released as soon as its successor exists."""
    transformed = transformation(image)
    image.close()
    return transformed


def read_encoding_options(source: Image.Image, jpeg_quality: int) -> dict[str, Any]:
    """What the new JPEG must keep of the scanner's. The sampling is read before the transformations, because a
    transposed image loses its JPEG format and "keep" would then raise."""
    options: dict[str, Any] = {"quality": jpeg_quality}
    subsampling = JpegImagePlugin.get_sampling(source)
    if subsampling != NO_CHROMA_SUBSAMPLING:
        options["subsampling"] = subsampling
    if "dpi" in source.info:
        options["dpi"] = source.info["dpi"]
    if "icc_profile" in source.info:
        options["icc_profile"] = source.info["icc_profile"]
    return options

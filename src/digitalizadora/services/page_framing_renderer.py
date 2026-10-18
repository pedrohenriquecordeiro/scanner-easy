import io
from dataclasses import dataclass
from typing import BinaryIO

from PIL import Image

from digitalizadora.domain.errors import ScanFailedError
from digitalizadora.domain.page_crop import PageCrop
from digitalizadora.domain.page_framing import PageFraming
from digitalizadora.domain.page_rotation import PageRotation
from digitalizadora.services.jpeg_reencoding import TRANSPOSE_BY_ROTATION, read_encoding_options, replace_with


@dataclass(frozen=True)
class FrameRenderRequest:
    """One output of a page: which crop of the framing (0 when the page has none or one) and the JPEG quality."""

    framing: PageFraming
    frame_index: int
    jpeg_quality: int


class PageFramingRenderer:
    """Applies the rotation and one crop of a framing to the JPEG of the scanner and writes a new JPEG.

    Synchronous and Pillow only. A master without rotation and without crops comes out with the bytes of the
    scanner. A crop with its edges parallel to the page is cut out; any other quadrilateral is straightened into
    an upright rectangle, reading straight from the whole master (measured: less memory than cutting its bounding
    box first).
    """

    def render_jpeg(self, master: BinaryIO, request: FrameRenderRequest) -> bytes:
        try:
            if not request.framing.needs_rendering:
                return master.read()
            return self._render_framed(master, request)
        except (OSError, Image.DecompressionBombError, ValueError) as error:
            raise ScanFailedError("The stored image could not be read as an image") from error

    def _render_framed(self, master: BinaryIO, request: FrameRenderRequest) -> bytes:
        image = Image.open(master)
        try:
            encoding_options = read_encoding_options(image, request.jpeg_quality)
            image = self._frame(image, request)
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", **encoding_options)
        finally:
            image.close()
        return buffer.getvalue()

    def _frame(self, image: Image.Image, request: FrameRenderRequest) -> Image.Image:
        master_crops = request.framing.crops_on_master()
        if not master_crops:
            return self._turn(image, request.framing.rotation)
        if request.frame_index >= len(master_crops):
            raise ValueError(f"The framing has no crop number {request.frame_index}")
        master_crop = master_crops[request.frame_index]
        if master_crop.is_rectangle:
            return self._cut_out_rectangle(image, master_crop)
        return self._straighten(image, master_crop)

    def _cut_out_rectangle(self, image: Image.Image, master_crop: PageCrop) -> Image.Image:
        region = master_crop.to_pixel_region(image.size)
        cut_out = replace_with(image, lambda full_image: full_image.crop(region.as_box()))
        return self._turn(cut_out, master_crop.rotation_to_upright)

    def _straighten(self, image: Image.Image, master_crop: PageCrop) -> Image.Image:
        top_left, top_right, bottom_right, bottom_left = master_crop.to_pixel_corners(image.size)
        source_quadrilateral = (
            top_left.x, top_left.y,
            bottom_left.x, bottom_left.y,
            bottom_right.x, bottom_right.y,
            top_right.x, top_right.y,
        )  # fmt: skip
        output_size = master_crop.output_size_in_pixels(image.size)
        return replace_with(
            image,
            lambda full_image: full_image.transform(
                output_size, Image.Transform.QUAD, source_quadrilateral, Image.Resampling.BICUBIC
            ),
        )

    def _turn(self, image: Image.Image, rotation: PageRotation) -> Image.Image:
        if rotation is PageRotation.NONE:
            return image
        transposition = TRANSPOSE_BY_ROTATION[rotation]
        return replace_with(image, lambda uncut_image: uncut_image.transpose(transposition))

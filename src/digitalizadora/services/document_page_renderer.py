import io
from pathlib import Path

from PIL import Image

from digitalizadora.domain.errors import ScanFailedError
from digitalizadora.domain.page_framing import PageFraming
from digitalizadora.domain.page_rotation import PageRotation
from digitalizadora.services.jpeg_reencoding import TRANSPOSE_BY_ROTATION, read_encoding_options, replace_with


class DocumentPageRenderer:
    """Applies the rotation and the crop of a page to the JPEG of the scanner, when the PDF is written.

    Synchronous and Pillow only. A page without rotation or crop comes out with the bytes of the scanner.
    """

    def render_jpeg(self, page_file: Path, framing: PageFraming) -> bytes:
        try:
            if not framing.needs_rendering:
                return page_file.read_bytes()
            return self._render_framed_page(page_file, framing)
        except (OSError, Image.DecompressionBombError, ValueError) as error:
            raise ScanFailedError(f"The page {page_file.name} could not be read as an image") from error

    def _render_framed_page(self, page_file: Path, framing: PageFraming) -> bytes:
        image = Image.open(page_file)
        try:
            encoding_options = read_encoding_options(image)
            master_crops = framing.crops_on_master()
            if master_crops:
                # The smaller image first: the crop is made in the orientation of the stored JPEG.
                master_crop = master_crops[0]
                region = master_crop.to_pixel_region(image.size)
                image = replace_with(image, lambda full_image: full_image.crop(region.as_box()))
                upright_rotation = master_crop.rotation_to_upright if master_crop.is_rectangle else PageRotation.NONE
                if upright_rotation is not PageRotation.NONE:
                    transposition = TRANSPOSE_BY_ROTATION[upright_rotation]
                    image = replace_with(image, lambda cut_image: cut_image.transpose(transposition))
            elif framing.rotation is not PageRotation.NONE:
                transposition = TRANSPOSE_BY_ROTATION[framing.rotation]
                image = replace_with(image, lambda uncut_image: uncut_image.transpose(transposition))
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", **encoding_options)
        finally:
            image.close()
        return buffer.getvalue()

import io

from PIL import Image

from digitalizadora.domain.errors import ScanFailedError
from digitalizadora.domain.page_rotation import PageRotation
from digitalizadora.services.jpeg_reencoding import TRANSPOSE_BY_ROTATION

ENLARGED_VIEW_MAXIMUM_EDGE_PIXELS = 1600
VIEW_JPEG_QUALITY = 85
VIEW_COLOR_MODE = "RGB"


class PageImageViewService:
    """A small JPEG of a page to look at: reduced while decoding, turned as the page is displayed.

    It serves the turned thumbnail, the enlarged view of a draft page and the thumbnail of the last quick scan.
    The page itself is never changed: this is only what the interface shows.
    """

    def build_view(self, jpeg_content: bytes, rotation: PageRotation, maximum_edge_pixels: int) -> bytes:
        edge_limit = (maximum_edge_pixels, maximum_edge_pixels)
        buffer = io.BytesIO()
        try:
            with Image.open(io.BytesIO(jpeg_content)) as image:
                image.draft(VIEW_COLOR_MODE, edge_limit)
                image.thumbnail(edge_limit)
                self._turned(image, rotation).save(buffer, format="JPEG", quality=VIEW_JPEG_QUALITY)
        except (OSError, Image.DecompressionBombError, ValueError) as error:
            raise ScanFailedError("The page could not be decoded for the view") from error
        return buffer.getvalue()

    def _turned(self, image: Image.Image, rotation: PageRotation) -> Image.Image:
        if rotation is PageRotation.NONE:
            return image
        return image.transpose(TRANSPOSE_BY_ROTATION[rotation])

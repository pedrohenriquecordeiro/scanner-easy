import io

from PIL import Image

from digitalizadora.domain.errors import ScanFailedError

THUMBNAIL_JPEG_QUALITY = 80
DRAFT_COLOR_MODE = "RGB"


class ThumbnailService:
    def build_thumbnail(self, jpeg_content: bytes, maximum_edge_pixels: int) -> bytes:
        edge_limit = (maximum_edge_pixels, maximum_edge_pixels)
        buffer = io.BytesIO()
        try:
            with Image.open(io.BytesIO(jpeg_content)) as image:
                image.draft(DRAFT_COLOR_MODE, edge_limit)
                image.load()
                image.thumbnail(edge_limit)
                image.save(buffer, format="JPEG", quality=THUMBNAIL_JPEG_QUALITY)
        except (OSError, Image.DecompressionBombError) as error:
            raise ScanFailedError("The scanned image could not be decoded for the thumbnail") from error
        return buffer.getvalue()

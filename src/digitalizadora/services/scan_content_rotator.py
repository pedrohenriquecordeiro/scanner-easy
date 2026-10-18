import io

import pikepdf
from PIL import Image

from digitalizadora.domain.errors import ImageAdjustmentFailedError, SavedScanUnreadableError
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.page_rotation import DEGREES_IN_A_QUARTER_TURN, PageRotation
from digitalizadora.services.jpeg_reencoding import TRANSPOSE_BY_ROTATION, read_encoding_options, replace_with


class ScanContentRotator:
    """Turns the content of a saved quick-mode scan a quarter clockwise, without going through the scanner.

    A JPG is re-encoded once (quality 95, with the density, the sampling and the profile of the file). A PDF only
    gets 90 more degrees on the /Rotate of its pages: its image streams are not touched, so nothing is lost.
    """

    def rotate_clockwise(self, content: bytes, output_format: OutputFormat) -> bytes:
        try:
            if output_format is OutputFormat.PDF:
                return self._rotate_pdf(content)
            return self._rotate_jpeg(content)
        except MemoryError as error:
            raise ImageAdjustmentFailedError("Not enough memory to turn the saved scan") from error
        except (OSError, Image.DecompressionBombError, ValueError, pikepdf.PdfError) as error:
            raise SavedScanUnreadableError("The saved scan could not be read to turn it") from error

    def _rotate_jpeg(self, content: bytes) -> bytes:
        image = Image.open(io.BytesIO(content))
        try:
            encoding_options = read_encoding_options(image)
            transposition = TRANSPOSE_BY_ROTATION[PageRotation.CLOCKWISE_90]
            image = replace_with(image, lambda uncut_image: uncut_image.transpose(transposition))
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", **encoding_options)
        finally:
            image.close()
        return buffer.getvalue()

    def _rotate_pdf(self, content: bytes) -> bytes:
        with pikepdf.open(io.BytesIO(content)) as document:
            for page in document.pages:
                page.rotate(DEGREES_IN_A_QUARTER_TURN, relative=True)
            buffer = io.BytesIO()
            document.save(buffer)
        return buffer.getvalue()

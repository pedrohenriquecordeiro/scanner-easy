import io
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

import img2pdf
from PIL import Image

from digitalizadora.domain.errors import ScanFailedError

PDF_CREATOR = "Digitalizadora"


@dataclass(frozen=True)
class PdfDocumentSpecification:
    dots_per_inch: int
    title: str
    created_at: datetime


class PdfAssemblyService:
    def build_pdf(self, jpeg_pages: Sequence[bytes], specification: PdfDocumentSpecification) -> bytes:
        if not jpeg_pages:
            raise ScanFailedError("A PDF needs at least one page")
        fixed_resolution = (specification.dots_per_inch, specification.dots_per_inch)
        try:
            return img2pdf.convert(
                *[io.BytesIO(page) for page in jpeg_pages],
                layout_fun=img2pdf.get_fixed_dpi_layout_fun(fixed_resolution),
                title=specification.title,
                creator=PDF_CREATOR,
                creationdate=specification.created_at,
                moddate=specification.created_at,
                engine=img2pdf.Engine.pikepdf,
                rotation=img2pdf.Rotation.ifvalid,
            )
        except (img2pdf.ImageOpenError, Image.DecompressionBombError) as error:
            raise ScanFailedError("A scanned page could not be read as an image") from error

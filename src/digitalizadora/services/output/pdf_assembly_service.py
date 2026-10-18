import io
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, BinaryIO, Protocol

import img2pdf
from PIL import Image

from digitalizadora.domain.errors import ScanFailedError

PDF_CREATOR = "Digitalizadora"
DEFAULT_PDF_TITLE_TEMPLATE = "Digitalização {moment:%Y-%m-%d %H:%M:%S}"


class PageImageSource(Protocol):
    def read(self) -> bytes: ...


@dataclass(frozen=True)
class PdfDocumentSpecification:
    dots_per_inch: int
    title: str
    created_at: datetime


@dataclass(frozen=True)
class PdfDocumentMetadata:
    title: str
    created_at: datetime


def _conversion_options(metadata: PdfDocumentMetadata, layout_function: Callable[..., Any]) -> dict[str, Any]:
    return {
        "layout_fun": layout_function,
        "title": metadata.title,
        "creator": PDF_CREATOR,
        "creationdate": metadata.created_at,
        "moddate": metadata.created_at,
        "engine": img2pdf.Engine.pikepdf,
        "rotation": img2pdf.Rotation.ifvalid,
    }


@contextmanager
def _unreadable_images_as_scan_failures() -> Iterator[None]:
    try:
        yield
    except (img2pdf.ImageOpenError, Image.DecompressionBombError) as error:
        raise ScanFailedError("A scanned page could not be read as an image") from error


class PdfAssemblyService:
    def build_pdf(self, jpeg_pages: Sequence[bytes], specification: PdfDocumentSpecification) -> bytes:
        if not jpeg_pages:
            raise ScanFailedError("A PDF needs at least one page")
        fixed_resolution = (specification.dots_per_inch, specification.dots_per_inch)
        metadata = PdfDocumentMetadata(specification.title, specification.created_at)
        options = _conversion_options(metadata, img2pdf.get_fixed_dpi_layout_fun(fixed_resolution))
        with _unreadable_images_as_scan_failures():
            return img2pdf.convert(*[io.BytesIO(page) for page in jpeg_pages], **options)

    def write_pdf_from_sources(
        self, page_sources: Sequence[PageImageSource], metadata: PdfDocumentMetadata, output_stream: BinaryIO
    ) -> None:
        """Each page keeps the physical size of its own JFIF density; img2pdf asks each source for its JPEG in turn.

        A source must not raise AttributeError from read(): img2pdf would take it for "no read()" and go on.
        """
        if not page_sources:
            raise ScanFailedError("A PDF needs at least one page")
        options = _conversion_options(metadata, img2pdf.default_layout_fun)
        with _unreadable_images_as_scan_failures():
            img2pdf.convert(*page_sources, outputstream=output_stream, **options)

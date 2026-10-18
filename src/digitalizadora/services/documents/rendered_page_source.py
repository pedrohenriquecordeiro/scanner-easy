from pathlib import Path

from digitalizadora.domain.errors import ScanFailedError
from digitalizadora.services.imaging.page_framing_renderer import FrameRenderRequest, PageFramingRenderer


class RenderedPageSource:
    """The object with read() that img2pdf calls when it reaches the page: the page is rendered only then.

    img2pdf reads its inputs one after the other and releases each before the next, so only one page is
    decoded at a time and no temporary JPEG is needed.
    """

    def __init__(self, page_renderer: PageFramingRenderer, page_file: Path, request: FrameRenderRequest) -> None:
        self._page_renderer = page_renderer
        self._page_file = page_file
        self._request = request

    def read(self) -> bytes:
        try:
            with self._page_file.open("rb") as master:
                return self._page_renderer.render_jpeg(master, self._request)
        except OSError as error:
            raise ScanFailedError(f"The page {self._page_file.name} could not be read") from error

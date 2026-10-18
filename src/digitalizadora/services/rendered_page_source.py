from pathlib import Path

from digitalizadora.domain.page_framing import PageFraming
from digitalizadora.services.document_page_renderer import DocumentPageRenderer


class RenderedPageSource:
    """The object with read() that img2pdf calls when it reaches the page: the page is rendered only then.

    img2pdf reads its inputs one after the other and releases each before the next, so only one page is
    decoded at a time and no temporary JPEG is needed.
    """

    def __init__(self, page_renderer: DocumentPageRenderer, page_file: Path, framing: PageFraming) -> None:
        self._page_renderer = page_renderer
        self._page_file = page_file
        self._framing = framing

    def read(self) -> bytes:
        return self._page_renderer.render_jpeg(self._page_file, self._framing)

from pathlib import Path
from typing import BinaryIO

import pytest

from digitalizadora.domain.errors import ScanFailedError
from digitalizadora.domain.page_framing import UNFRAMED, PageFraming
from digitalizadora.domain.page_rotation import PageRotation
from digitalizadora.services.page_framing_renderer import FrameRenderRequest, PageFramingRenderer
from digitalizadora.services.rendered_page_source import RenderedPageSource
from tests.fakes.synthetic_scans import build_marked_scan_jpeg, read_jpeg_size

UNTOUCHED = FrameRenderRequest(UNFRAMED, 0)
QUARTER_TURN = FrameRenderRequest(PageFraming(rotation=PageRotation.CLOCKWISE_90), 0)


class RecordingPageRenderer(PageFramingRenderer):
    def __init__(self) -> None:
        self.requests: list[FrameRenderRequest] = []

    def render_jpeg(self, master: BinaryIO, request: FrameRenderRequest) -> bytes:
        self.requests.append(request)
        return super().render_jpeg(master, request)


@pytest.fixture
def page_file(tmp_path: Path) -> Path:
    page_path = tmp_path / "page.jpg"
    page_path.write_bytes(build_marked_scan_jpeg((100, 200)))
    return page_path


def test_creating_the_source_renders_nothing(page_file):
    renderer = RecordingPageRenderer()

    RenderedPageSource(renderer, page_file, UNTOUCHED)

    assert renderer.requests == []


def test_reading_renders_the_page_with_its_request(page_file):
    renderer = RecordingPageRenderer()

    RenderedPageSource(renderer, page_file, QUARTER_TURN).read()

    assert renderer.requests == [QUARTER_TURN]


def test_reading_gives_the_rendered_jpeg(page_file):
    source = RenderedPageSource(PageFramingRenderer(), page_file, QUARTER_TURN)

    assert read_jpeg_size(source.read()) == (200, 100)


def test_the_page_is_read_from_the_disk_when_it_is_asked_for(page_file):
    source = RenderedPageSource(PageFramingRenderer(), page_file, UNTOUCHED)
    page_file.write_bytes(build_marked_scan_jpeg((40, 60)))

    assert read_jpeg_size(source.read()) == (40, 60)


def test_a_page_file_that_vanished_raises_scan_failed(page_file):
    source = RenderedPageSource(PageFramingRenderer(), page_file, UNTOUCHED)
    page_file.unlink()

    with pytest.raises(ScanFailedError):
        source.read()


def test_a_page_file_that_vanished_raises_scan_failed_when_it_needs_rendering(page_file):
    source = RenderedPageSource(PageFramingRenderer(), page_file, QUARTER_TURN)
    page_file.unlink()

    with pytest.raises(ScanFailedError):
        source.read()

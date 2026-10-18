from pathlib import Path

import pytest

from digitalizadora.domain.errors import ScanFailedError
from digitalizadora.domain.page_framing import UNFRAMED, PageFraming
from digitalizadora.domain.page_rotation import PageRotation
from digitalizadora.services.document_page_renderer import DocumentPageRenderer
from digitalizadora.services.rendered_page_source import RenderedPageSource
from tests.fakes.synthetic_scans import build_marked_scan_jpeg, read_jpeg_size


class RecordingPageRenderer(DocumentPageRenderer):
    def __init__(self) -> None:
        self.rendered_pages: list[tuple[Path, PageFraming]] = []

    def render_jpeg(self, page_file: Path, framing: PageFraming) -> bytes:
        self.rendered_pages.append((page_file, framing))
        return super().render_jpeg(page_file, framing)


@pytest.fixture
def page_file(tmp_path: Path) -> Path:
    page_path = tmp_path / "page.jpg"
    page_path.write_bytes(build_marked_scan_jpeg((100, 200)))
    return page_path


def test_creating_the_source_renders_nothing(page_file):
    renderer = RecordingPageRenderer()

    RenderedPageSource(renderer, page_file, UNFRAMED)

    assert renderer.rendered_pages == []


def test_reading_renders_the_page_with_its_framing(page_file):
    renderer = RecordingPageRenderer()
    framing = PageFraming(rotation=PageRotation.CLOCKWISE_90)

    RenderedPageSource(renderer, page_file, framing).read()

    assert renderer.rendered_pages == [(page_file, framing)]


def test_reading_gives_the_rendered_jpeg(page_file):
    source = RenderedPageSource(DocumentPageRenderer(), page_file, PageFraming(rotation=PageRotation.CLOCKWISE_90))

    assert read_jpeg_size(source.read()) == (200, 100)


def test_the_page_is_read_from_the_disk_when_it_is_asked_for(page_file):
    source = RenderedPageSource(DocumentPageRenderer(), page_file, UNFRAMED)
    page_file.write_bytes(build_marked_scan_jpeg((40, 60)))

    assert read_jpeg_size(source.read()) == (40, 60)


def test_a_page_file_that_vanished_raises_scan_failed(page_file):
    source = RenderedPageSource(DocumentPageRenderer(), page_file, UNFRAMED)
    page_file.unlink()

    with pytest.raises(ScanFailedError):
        source.read()

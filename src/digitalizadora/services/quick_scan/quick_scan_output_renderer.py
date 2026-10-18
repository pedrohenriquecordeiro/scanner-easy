from dataclasses import dataclass
from typing import BinaryIO

from digitalizadora.domain.encoded_scan import EncodedScan
from digitalizadora.domain.imaging.page_framing import PageFraming
from digitalizadora.services.imaging.page_framing_renderer import FrameRenderRequest, PageFramingRenderer
from digitalizadora.services.scan_encoder import OutputIdentity, ScanEncoder


@dataclass(frozen=True)
class OutputsRequest:
    framing: PageFraming
    identity: OutputIdentity


class QuickScanOutputRenderer:
    """The files of a quick scan, made from its master: one per frame, or the whole image when there is none."""

    def __init__(self, page_framing_renderer: PageFramingRenderer, scan_encoder: ScanEncoder) -> None:
        self._page_framing_renderer = page_framing_renderer
        self._scan_encoder = scan_encoder

    def render_outputs(self, master: BinaryIO, request: OutputsRequest) -> tuple[EncodedScan, ...]:
        """Each frame is rendered alone, so only one image is decoded at a time; the master is read again for each."""
        outputs = []
        for frame_index in range(request.framing.output_count):
            master.seek(0)
            frame_request = FrameRenderRequest(request.framing, frame_index)
            output_jpeg = self._page_framing_renderer.render_jpeg(master, frame_request)
            outputs.append(self._scan_encoder.wrap_output(output_jpeg, request.identity))
        return tuple(outputs)

import json
import logging
from pathlib import Path

from digitalizadora.domain.scanner_endpoint import ScannerEndpoint
from digitalizadora.domain.scanner_route import ScannerRoute
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter

LOGGER = logging.getLogger(__name__)


def parse_scanner_endpoint(document: object) -> ScannerEndpoint:
    if not isinstance(document, dict):
        raise ValueError("The scanner endpoint document must be a JSON object")
    base_address = document.get("base_address")
    display_name = document.get("display_name")
    identifier = document.get("universally_unique_identifier")
    if not isinstance(base_address, str) or not base_address:
        raise ValueError("The scanner endpoint document has no base_address")
    if not isinstance(display_name, str):
        raise ValueError("The scanner endpoint document has no display_name")
    if identifier is not None and not isinstance(identifier, str):
        raise ValueError("The scanner endpoint identifier must be text")
    route = ScannerRoute(document.get("route", ScannerRoute.NETWORK.value))
    return ScannerEndpoint(base_address, display_name, identifier, route)


class JsonScannerEndpointRepository:
    def __init__(self, storage_file: Path, file_writer: AtomicFileWriter) -> None:
        self._storage_file = storage_file
        self._file_writer = file_writer

    def load(self) -> ScannerEndpoint | None:
        try:
            document = json.loads(self._storage_file.read_text(encoding="utf-8"))
            return parse_scanner_endpoint(document)
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as error:
            LOGGER.warning("Ignoring the unusable scanner endpoint file %s: %s", self._storage_file, error)
            return None

    def save(self, endpoint: ScannerEndpoint) -> None:
        document = {
            "base_address": endpoint.base_address,
            "display_name": endpoint.display_name,
            "universally_unique_identifier": endpoint.universally_unique_identifier,
            "route": endpoint.route.value,
        }
        self._storage_file.parent.mkdir(parents=True, exist_ok=True)
        self._file_writer.replace_file(self._storage_file, json.dumps(document, indent=2).encode("utf-8"))

    def clear(self) -> None:
        self._storage_file.unlink(missing_ok=True)

import json
import logging
from pathlib import Path

import pytest

from digitalizadora.domain.scanner_endpoint import ScannerEndpoint
from digitalizadora.domain.scanner_route import ScannerRoute
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter
from digitalizadora.repositories.json_scanner_endpoint_repository import JsonScannerEndpointRepository

ENDPOINT = ScannerEndpoint(
    base_address="http://HP000000000001.local:8080/eSCL",
    display_name="HP DeskJet 2800 series",
    universally_unique_identifier="11111111-2222-3333-4444-555555555555",
)
USB_ENDPOINT = ScannerEndpoint(
    base_address="http://localhost:57805/eSCL",
    display_name="HP DeskJet 2800 series",
    universally_unique_identifier="11111111-2222-3333-4444-555555555555",
    route=ScannerRoute.USB,
)
ENDPOINT_WITHOUT_IDENTIFIER = ScannerEndpoint(base_address="http://192.168.0.41:8080/eSCL", display_name="Printer")


def build_repository(storage_file: Path) -> JsonScannerEndpointRepository:
    return JsonScannerEndpointRepository(storage_file, AtomicFileWriter())


def test_load_returns_none_when_the_file_is_missing(tmp_path):
    assert build_repository(tmp_path / "scanner-endpoint.json").load() is None


def test_saved_endpoint_is_loaded_back_equal(tmp_path):
    repository = build_repository(tmp_path / "scanner-endpoint.json")

    repository.save(ENDPOINT)

    assert repository.load() == ENDPOINT


def test_usb_endpoint_is_loaded_back_with_its_route(tmp_path):
    repository = build_repository(tmp_path / "scanner-endpoint.json")

    repository.save(USB_ENDPOINT)

    assert repository.load() == USB_ENDPOINT


def test_endpoint_without_identifier_is_loaded_back_equal(tmp_path):
    repository = build_repository(tmp_path / "scanner-endpoint.json")

    repository.save(ENDPOINT_WITHOUT_IDENTIFIER)

    assert repository.load() == ENDPOINT_WITHOUT_IDENTIFIER


def test_save_writes_the_documented_json_shape(tmp_path):
    storage_file = tmp_path / "scanner-endpoint.json"

    build_repository(storage_file).save(ENDPOINT)

    assert json.loads(storage_file.read_text(encoding="utf-8")) == {
        "base_address": "http://HP000000000001.local:8080/eSCL",
        "display_name": "HP DeskJet 2800 series",
        "universally_unique_identifier": "11111111-2222-3333-4444-555555555555",
        "route": "network",
    }


def test_file_written_before_routes_existed_loads_as_a_network_endpoint(tmp_path):
    storage_file = tmp_path / "scanner-endpoint.json"
    storage_file.write_text(
        '{"base_address": "http://192.168.0.40:8080/eSCL", "display_name": "Printer"}', encoding="utf-8"
    )

    assert build_repository(storage_file).load() == ScannerEndpoint(
        base_address="http://192.168.0.40:8080/eSCL", display_name="Printer", route=ScannerRoute.NETWORK
    )


def test_save_creates_the_missing_data_folder(tmp_path):
    storage_file = tmp_path / "Application Support" / "Digitalizadora" / "scanner-endpoint.json"

    build_repository(storage_file).save(ENDPOINT)

    assert storage_file.exists()


def test_save_replaces_the_previous_endpoint(tmp_path):
    repository = build_repository(tmp_path / "scanner-endpoint.json")
    repository.save(ENDPOINT)

    repository.save(ENDPOINT_WITHOUT_IDENTIFIER)

    assert repository.load() == ENDPOINT_WITHOUT_IDENTIFIER


UNUSABLE_DOCUMENTS = [
    "",
    "{not json",
    "[]",
    '"text"',
    "{}",
    '{"base_address": "http://192.168.0.40:8080/eSCL"}',
    '{"base_address": "", "display_name": "Printer"}',
    '{"base_address": 5, "display_name": "Printer"}',
    '{"base_address": "http://192.168.0.40:8080/eSCL", "display_name": "Printer", "universally_unique_identifier": 7}',
    '{"base_address": "http://192.168.0.40:8080/eSCL", "display_name": "Printer", "route": "bluetooth"}',
    '{"base_address": "http://192.168.0.40:8080/eSCL", "display_name": "Printer", "route": 5}',
]


@pytest.mark.parametrize("unusable_document", UNUSABLE_DOCUMENTS)
def test_load_returns_none_for_a_corrupt_or_incomplete_file(tmp_path, unusable_document):
    storage_file = tmp_path / "scanner-endpoint.json"
    storage_file.write_text(unusable_document, encoding="utf-8")

    assert build_repository(storage_file).load() is None


def test_load_returns_none_for_a_file_that_is_not_text(tmp_path):
    storage_file = tmp_path / "scanner-endpoint.json"
    storage_file.write_bytes(b"\xff\xfe\x00\x80")

    assert build_repository(storage_file).load() is None


def test_corrupt_file_is_reported_with_a_warning(tmp_path, caplog):
    storage_file = tmp_path / "scanner-endpoint.json"
    storage_file.write_text("{not json", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        build_repository(storage_file).load()

    assert [record.levelno for record in caplog.records] == [logging.WARNING]


def test_missing_file_is_not_reported_as_a_problem(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        build_repository(tmp_path / "scanner-endpoint.json").load()

    assert caplog.records == []


def test_clear_removes_the_saved_endpoint(tmp_path):
    repository = build_repository(tmp_path / "scanner-endpoint.json")
    repository.save(ENDPOINT)

    repository.clear()

    assert repository.load() is None
    assert not (tmp_path / "scanner-endpoint.json").exists()


def test_clear_is_idempotent(tmp_path):
    repository = build_repository(tmp_path / "scanner-endpoint.json")

    repository.clear()
    repository.clear()

    assert repository.load() is None

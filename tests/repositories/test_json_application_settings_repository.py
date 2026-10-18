import json
import logging
from pathlib import Path

import pytest

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.capture_mode import CaptureMode
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter
from digitalizadora.repositories.json_application_settings_repository import JsonApplicationSettingsRepository

DEFAULT_SETTINGS = ApplicationSettings(
    Path("/Users/someone/Pictures/Digitalizadora"), OutputFormat.PDF, ScanPreset.DOCUMENT
)
CUSTOM_SETTINGS = ApplicationSettings(Path("/Volumes/Archive/Digitalização"), OutputFormat.JPEG, ScanPreset.PHOTO)


def build_repository(storage_file: Path) -> JsonApplicationSettingsRepository:
    return JsonApplicationSettingsRepository(storage_file, DEFAULT_SETTINGS, AtomicFileWriter())


def write_document(storage_file: Path, document: dict) -> None:
    storage_file.write_text(json.dumps(document), encoding="utf-8")


def test_load_returns_the_defaults_when_the_file_is_missing(tmp_path):
    assert build_repository(tmp_path / "settings.json").load() == DEFAULT_SETTINGS


def test_saved_settings_are_loaded_back_equal(tmp_path):
    repository = build_repository(tmp_path / "settings.json")

    repository.save(CUSTOM_SETTINGS)

    assert repository.load() == CUSTOM_SETTINGS


def test_save_writes_the_documented_json_shape(tmp_path):
    storage_file = tmp_path / "settings.json"

    build_repository(storage_file).save(CUSTOM_SETTINGS)

    assert json.loads(storage_file.read_text(encoding="utf-8")) == {
        "output_folder": "/Volumes/Archive/Digitalização",
        "output_format": "jpg",
        "scan_preset": "photo",
        "capture_mode": "single",
    }


def test_save_creates_the_missing_data_folder(tmp_path):
    storage_file = tmp_path / "Application Support" / "Digitalizadora" / "settings.json"

    build_repository(storage_file).save(CUSTOM_SETTINGS)

    assert storage_file.exists()


def test_save_replaces_the_previous_settings(tmp_path):
    repository = build_repository(tmp_path / "settings.json")
    repository.save(CUSTOM_SETTINGS)

    repository.save(DEFAULT_SETTINGS)

    assert repository.load() == DEFAULT_SETTINGS


VALID_DOCUMENT = {"output_folder": "/Volumes/Archive", "output_format": "jpg", "scan_preset": "photo"}
UNUSABLE_DOCUMENTS = [
    {**VALID_DOCUMENT, "output_format": "tiff"},
    {**VALID_DOCUMENT, "scan_preset": "poster"},
    {**VALID_DOCUMENT, "output_folder": "relative/folder"},
    {**VALID_DOCUMENT, "output_folder": "~/Pictures"},
    {**VALID_DOCUMENT, "output_folder": ""},
    {**VALID_DOCUMENT, "output_folder": 123},
    {"output_format": "jpg", "scan_preset": "photo"},
    {"output_folder": "/Volumes/Archive", "scan_preset": "photo"},
    {"output_folder": "/Volumes/Archive", "output_format": "jpg"},
]


@pytest.mark.parametrize("unusable_document", UNUSABLE_DOCUMENTS)
def test_load_returns_the_whole_default_when_one_field_is_unusable(tmp_path, unusable_document):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, unusable_document)

    assert build_repository(storage_file).load() == DEFAULT_SETTINGS


@pytest.mark.parametrize("unusable_text", ["", "{not json", "[]", "null", '"text"'])
def test_load_returns_the_defaults_for_a_corrupt_file(tmp_path, unusable_text):
    storage_file = tmp_path / "settings.json"
    storage_file.write_text(unusable_text, encoding="utf-8")

    assert build_repository(storage_file).load() == DEFAULT_SETTINGS


def test_load_returns_the_defaults_for_a_file_that_is_not_text(tmp_path):
    storage_file = tmp_path / "settings.json"
    storage_file.write_bytes(b"\xff\xfe\x00\x80")

    assert build_repository(storage_file).load() == DEFAULT_SETTINGS


def test_valid_document_is_loaded_as_written_by_hand(tmp_path):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, VALID_DOCUMENT)

    assert build_repository(storage_file).load() == ApplicationSettings(
        Path("/Volumes/Archive"), OutputFormat.JPEG, ScanPreset.PHOTO
    )


def test_unusable_file_is_reported_with_a_warning(tmp_path, caplog):
    storage_file = tmp_path / "settings.json"
    storage_file.write_text("{not json", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        build_repository(storage_file).load()

    assert [record.levelno for record in caplog.records] == [logging.WARNING]


def test_missing_file_is_not_reported_as_a_problem(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        build_repository(tmp_path / "settings.json").load()

    assert caplog.records == []


DOCUMENT_MODE_SETTINGS = ApplicationSettings(
    Path("/Volumes/Archive/Digitalização"), OutputFormat.JPEG, ScanPreset.PHOTO, CaptureMode.DOCUMENT
)
SETTINGS_OF_THE_VALID_DOCUMENT = ApplicationSettings(Path("/Volumes/Archive"), OutputFormat.JPEG, ScanPreset.PHOTO)
UNKNOWN_CAPTURE_MODES = ["batch", "DOCUMENT", "", 1, True, None, ["document"], {"mode": "document"}]


def test_saved_document_mode_is_loaded_back(tmp_path):
    repository = build_repository(tmp_path / "settings.json")

    repository.save(DOCUMENT_MODE_SETTINGS)

    assert repository.load() == DOCUMENT_MODE_SETTINGS


def test_save_writes_the_document_mode_as_its_text(tmp_path):
    storage_file = tmp_path / "settings.json"

    build_repository(storage_file).save(DOCUMENT_MODE_SETTINGS)

    assert json.loads(storage_file.read_text(encoding="utf-8"))["capture_mode"] == "document"


def test_file_without_the_capture_mode_is_loaded_in_single_mode(tmp_path):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, VALID_DOCUMENT)

    assert build_repository(storage_file).load().capture_mode is CaptureMode.SINGLE


def test_file_with_the_document_mode_is_loaded_in_document_mode(tmp_path):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, {**VALID_DOCUMENT, "capture_mode": "document"})

    assert build_repository(storage_file).load().capture_mode is CaptureMode.DOCUMENT


@pytest.mark.parametrize("unknown_capture_mode", UNKNOWN_CAPTURE_MODES)
def test_unknown_capture_mode_is_read_as_single_keeping_the_other_fields(tmp_path, unknown_capture_mode):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, {**VALID_DOCUMENT, "capture_mode": unknown_capture_mode})

    assert build_repository(storage_file).load() == SETTINGS_OF_THE_VALID_DOCUMENT


def test_unknown_capture_mode_is_reported_with_a_warning(tmp_path, caplog):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, {**VALID_DOCUMENT, "capture_mode": "batch"})

    with caplog.at_level(logging.WARNING):
        build_repository(storage_file).load()

    assert [record.levelno for record in caplog.records] == [logging.WARNING]


def test_unknown_capture_mode_is_reported_only_once(tmp_path, caplog):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, {**VALID_DOCUMENT, "capture_mode": "batch"})
    repository = build_repository(storage_file)

    with caplog.at_level(logging.WARNING):
        repository.load()
        repository.load()

    assert [record.levelno for record in caplog.records] == [logging.WARNING]


def test_file_without_the_capture_mode_is_not_reported_as_a_problem(tmp_path, caplog):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, VALID_DOCUMENT)

    with caplog.at_level(logging.WARNING):
        build_repository(storage_file).load()

    assert caplog.records == []

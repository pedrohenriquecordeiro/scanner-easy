import dataclasses
import json
import logging
from pathlib import Path

import pytest

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.capture_mode import CaptureMode
from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.image_adjustment import NO_ADJUSTMENT, ImageAdjustment
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter
from digitalizadora.repositories.json_application_settings_repository import JsonApplicationSettingsRepository

DEFAULT_SETTINGS = ApplicationSettings(
    Path("/Users/someone/Pictures/Digitalizadora"), OutputFormat.PDF, ScanPreset.DOCUMENT.settings
)
CUSTOM_SETTINGS = ApplicationSettings(
    Path("/Volumes/Archive/Digitalização"), OutputFormat.JPEG, ScanPreset.PHOTO.settings
)


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
        "dots_per_inch": 600,
        "color_mode": "color",
        "capture_mode": "single",
        "auto_crop": False,
        "jpeg_quality": 90,
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
SETTINGS_OF_THE_VALID_DOCUMENT = ApplicationSettings(
    Path("/Volumes/Archive"), OutputFormat.JPEG, ScanPreset.PHOTO.settings
)
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

    assert build_repository(storage_file).load() == SETTINGS_OF_THE_VALID_DOCUMENT


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
    Path("/Volumes/Archive/Digitalização"), OutputFormat.JPEG, ScanPreset.PHOTO.settings, CaptureMode.DOCUMENT
)
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


ADJUSTED_SETTINGS = ApplicationSettings(
    Path("/Volumes/Archive"),
    OutputFormat.PDF,
    ScanSettings(1200, ColorMode.GRAYSCALE),
    CaptureMode.DOCUMENT,
    ImageAdjustment(auto_crop=True),
)
NEW_FORMAT_DOCUMENT = {
    "output_folder": "/Volumes/Archive",
    "output_format": "jpg",
    "dots_per_inch": 400,
    "color_mode": "grayscale",
    "capture_mode": "document",
    "auto_crop": True,
}
SETTINGS_OF_THE_NEW_FORMAT_DOCUMENT = ApplicationSettings(
    Path("/Volumes/Archive"),
    OutputFormat.JPEG,
    ScanSettings(400, ColorMode.GRAYSCALE),
    CaptureMode.DOCUMENT,
    ImageAdjustment(auto_crop=True),
)


def test_adjusted_settings_are_loaded_back_equal(tmp_path):
    repository = build_repository(tmp_path / "settings.json")

    repository.save(ADJUSTED_SETTINGS)

    assert repository.load() == ADJUSTED_SETTINGS


def test_save_does_not_write_the_scan_preset_any_more(tmp_path):
    storage_file = tmp_path / "settings.json"

    build_repository(storage_file).save(CUSTOM_SETTINGS)

    assert "scan_preset" not in json.loads(storage_file.read_text(encoding="utf-8"))


def test_new_format_document_is_loaded_as_written_by_hand(tmp_path):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, NEW_FORMAT_DOCUMENT)

    assert build_repository(storage_file).load() == SETTINGS_OF_THE_NEW_FORMAT_DOCUMENT


def test_old_document_with_only_the_preset_gets_the_preset_quality(tmp_path):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, VALID_DOCUMENT)

    assert build_repository(storage_file).load().scan_settings == ScanPreset.PHOTO.settings


def test_old_document_gets_no_adjustment(tmp_path):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, VALID_DOCUMENT)

    assert build_repository(storage_file).load().adjustment == NO_ADJUSTMENT


def test_the_quality_pair_wins_over_the_preset(tmp_path):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, {**VALID_DOCUMENT, "dots_per_inch": 1200, "color_mode": "grayscale"})

    assert build_repository(storage_file).load().scan_settings == ScanSettings(1200, ColorMode.GRAYSCALE)


@pytest.mark.parametrize(
    "invalid_pair",
    [
        {"dots_per_inch": 301, "color_mode": "color"},
        {"dots_per_inch": 300, "color_mode": "sepia"},
        {"dots_per_inch": True, "color_mode": "color"},
        {"dots_per_inch": "300", "color_mode": "color"},
        {"dots_per_inch": 300},
        {"color_mode": "color"},
    ],
)
def test_an_invalid_quality_pair_falls_back_to_the_preset(tmp_path, invalid_pair):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, {**VALID_DOCUMENT, **invalid_pair})

    assert build_repository(storage_file).load().scan_settings == ScanPreset.PHOTO.settings


def test_an_invalid_quality_pair_keeps_the_other_fields(tmp_path):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, {**VALID_DOCUMENT, "dots_per_inch": 301, "color_mode": "color"})

    assert build_repository(storage_file).load() == SETTINGS_OF_THE_VALID_DOCUMENT


def test_an_invalid_quality_pair_is_reported_with_a_warning(tmp_path, caplog):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, {**VALID_DOCUMENT, "dots_per_inch": 301, "color_mode": "color"})

    with caplog.at_level(logging.WARNING):
        build_repository(storage_file).load()

    assert [record.levelno for record in caplog.records] == [logging.WARNING]


NEW_FORMAT_DOCUMENT_WITH_INVALID_PAIR = {
    "output_folder": "/Volumes/Archive",
    "output_format": "jpg",
    "dots_per_inch": 301,
    "color_mode": "color",
    "capture_mode": "document",
    "auto_crop": True,
}


def test_an_invalid_quality_pair_without_a_preset_keeps_the_other_fields(tmp_path):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, NEW_FORMAT_DOCUMENT_WITH_INVALID_PAIR)

    assert build_repository(storage_file).load() == ApplicationSettings(
        output_folder=Path("/Volumes/Archive"),
        output_format=OutputFormat.JPEG,
        scan_settings=ScanPreset.DOCUMENT.settings,
        capture_mode=CaptureMode.DOCUMENT,
        adjustment=ImageAdjustment(auto_crop=True),
    )


def test_an_invalid_quality_pair_without_a_preset_is_reported_with_a_warning(tmp_path, caplog):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, NEW_FORMAT_DOCUMENT_WITH_INVALID_PAIR)

    with caplog.at_level(logging.WARNING):
        build_repository(storage_file).load()

    assert [record.levelno for record in caplog.records] == [logging.WARNING]


def test_an_invalid_quality_pair_with_an_unknown_preset_keeps_the_other_fields(tmp_path):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, {**NEW_FORMAT_DOCUMENT_WITH_INVALID_PAIR, "scan_preset": "poster"})

    assert build_repository(storage_file).load().output_folder == Path("/Volumes/Archive")


@pytest.mark.parametrize("old_rotation", [0, 90, 270, 45, "90", None, True])
def test_an_old_rotation_key_is_ignored_keeping_the_other_fields(tmp_path, old_rotation):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, {**NEW_FORMAT_DOCUMENT, "rotation_degrees": old_rotation})

    assert build_repository(storage_file).load() == SETTINGS_OF_THE_NEW_FORMAT_DOCUMENT


def test_an_old_rotation_key_is_ignored_without_a_warning(tmp_path, caplog):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, {**NEW_FORMAT_DOCUMENT, "rotation_degrees": 45})

    with caplog.at_level(logging.WARNING):
        build_repository(storage_file).load()

    assert caplog.records == []


def test_saving_an_old_document_drops_its_rotation_key(tmp_path):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, {**NEW_FORMAT_DOCUMENT, "rotation_degrees": 90})
    repository = build_repository(storage_file)

    repository.save(repository.load())

    assert "rotation_degrees" not in json.loads(storage_file.read_text(encoding="utf-8"))


@pytest.mark.parametrize("invalid_auto_crop", [1, 0, "true", None, [True]])
def test_an_invalid_auto_crop_is_read_as_off_keeping_the_other_fields(tmp_path, invalid_auto_crop):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, {**NEW_FORMAT_DOCUMENT, "auto_crop": invalid_auto_crop})

    assert build_repository(storage_file).load() == dataclasses.replace(
        SETTINGS_OF_THE_NEW_FORMAT_DOCUMENT, adjustment=ImageAdjustment(auto_crop=False)
    )


@pytest.mark.parametrize(
    ("document_update", "expected_warning_count"),
    [
        ({"auto_crop": "yes"}, 1),
        ({"auto_crop": "yes", "capture_mode": "batch"}, 2),
    ],
)
def test_each_invalid_tolerant_value_is_reported_once(tmp_path, caplog, document_update, expected_warning_count):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, {**NEW_FORMAT_DOCUMENT, **document_update})
    repository = build_repository(storage_file)

    with caplog.at_level(logging.WARNING):
        repository.load()
        repository.load()

    assert len(caplog.records) == expected_warning_count


def test_a_changed_invalid_auto_crop_is_reported_again(tmp_path, caplog):
    storage_file = tmp_path / "settings.json"
    repository = build_repository(storage_file)
    write_document(storage_file, {**NEW_FORMAT_DOCUMENT, "auto_crop": "yes"})
    repository.load()
    caplog.clear()
    write_document(storage_file, {**NEW_FORMAT_DOCUMENT, "auto_crop": "maybe"})

    with caplog.at_level(logging.WARNING):
        repository.load()

    assert len(caplog.records) == 1


def test_a_saved_jpeg_quality_is_loaded(tmp_path):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, {**NEW_FORMAT_DOCUMENT, "jpeg_quality": 65})

    assert build_repository(storage_file).load().adjustment.jpeg_quality == 65


def test_a_jpeg_quality_is_written_and_read_back(tmp_path):
    repository = build_repository(tmp_path / "settings.json")
    settings = dataclasses.replace(CUSTOM_SETTINGS, adjustment=ImageAdjustment(auto_crop=True, jpeg_quality=72))

    repository.save(settings)

    assert repository.load() == settings


def test_a_file_from_before_the_jpeg_quality_loads_with_ninety(tmp_path):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, NEW_FORMAT_DOCUMENT)

    assert build_repository(storage_file).load().adjustment.jpeg_quality == 90


@pytest.mark.parametrize("invalid_quality", [49, 101, 0, "90", 90.5, True, None, [90]])
def test_an_invalid_jpeg_quality_is_read_as_ninety_keeping_the_other_fields(tmp_path, invalid_quality):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, {**NEW_FORMAT_DOCUMENT, "jpeg_quality": invalid_quality})

    assert build_repository(storage_file).load() == SETTINGS_OF_THE_NEW_FORMAT_DOCUMENT


def test_an_invalid_jpeg_quality_is_reported_once(tmp_path, caplog):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, {**NEW_FORMAT_DOCUMENT, "jpeg_quality": 300})
    repository = build_repository(storage_file)

    with caplog.at_level(logging.WARNING):
        repository.load()
        repository.load()

    assert len(caplog.records) == 1


def test_a_missing_auto_crop_is_not_reported_as_a_problem(tmp_path, caplog):
    storage_file = tmp_path / "settings.json"
    write_document(storage_file, VALID_DOCUMENT)

    with caplog.at_level(logging.WARNING):
        build_repository(storage_file).load()

    assert caplog.records == []

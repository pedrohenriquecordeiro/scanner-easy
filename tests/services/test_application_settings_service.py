import dataclasses
from pathlib import Path

import pytest

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.capture_mode import CaptureMode
from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import InvalidSettingsError, OutputFolderUnavailableError
from digitalizadora.domain.image_adjustment import ImageAdjustment
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_quality import SUPPORTED_DOTS_PER_INCH
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.repositories.output_folder_preparer import prepare_output_folder
from digitalizadora.services.application_settings_service import (
    ApplicationSettingsService,
    SettingsUpdate,
)
from tests.fakes.in_memory_settings_repository import InMemoryApplicationSettingsRepository

INITIAL_SETTINGS = ApplicationSettings(
    output_folder=Path("/Volumes/Initial/scans"),
    output_format=OutputFormat.PDF,
    scan_settings=ScanPreset.DOCUMENT.settings,
)
FOLDER_WITH_NULL_CHARACTER = "/Volumes/External/sc\0ans"
FOLDER_OF_UNKNOWN_USER = "~digitalizadora-user-that-does-not-exist/scans"


class RecordingFolderPreparer:
    def __init__(self) -> None:
        self.prepared_folders: list[Path] = []
        self.failure: Exception | None = None

    def __call__(self, folder: Path) -> None:
        self.prepared_folders.append(folder)
        if self.failure is not None:
            raise self.failure


def build_update(
    output_folder: str = "/Volumes/External/scans",
    output_format: str = "jpg",
) -> SettingsUpdate:
    return SettingsUpdate(output_folder=output_folder, output_format=output_format)


def build_capture_mode_update(capture_mode: str | None) -> SettingsUpdate:
    return SettingsUpdate(
        output_folder="/Volumes/External/scans",
        output_format="jpg",
        capture_mode=capture_mode,
    )


@pytest.fixture
def settings_repository() -> InMemoryApplicationSettingsRepository:
    return InMemoryApplicationSettingsRepository(INITIAL_SETTINGS)


@pytest.fixture
def folder_preparer() -> RecordingFolderPreparer:
    return RecordingFolderPreparer()


@pytest.fixture
def settings_service(
    settings_repository: InMemoryApplicationSettingsRepository,
    folder_preparer: RecordingFolderPreparer,
) -> ApplicationSettingsService:
    return ApplicationSettingsService(settings_repository, folder_preparer)


def test_current_returns_the_saved_settings(settings_service: ApplicationSettingsService) -> None:
    assert settings_service.current() == INITIAL_SETTINGS


def test_update_returns_the_new_settings(settings_service: ApplicationSettingsService) -> None:
    saved = settings_service.update(build_update())

    assert saved == ApplicationSettings(
        output_folder=Path("/Volumes/External/scans"),
        output_format=OutputFormat.JPEG,
        scan_settings=INITIAL_SETTINGS.scan_settings,
    )


def test_update_saves_the_new_settings(
    settings_service: ApplicationSettingsService,
    settings_repository: InMemoryApplicationSettingsRepository,
) -> None:
    saved = settings_service.update(build_update())

    assert settings_repository.load() == saved


def test_update_prepares_the_output_folder(
    settings_service: ApplicationSettingsService, folder_preparer: RecordingFolderPreparer
) -> None:
    settings_service.update(build_update(output_folder="/Volumes/External/scans"))

    assert folder_preparer.prepared_folders == [Path("/Volumes/External/scans")]


def test_update_with_the_real_folder_preparer_creates_the_folder(
    settings_repository: InMemoryApplicationSettingsRepository, tmp_path: Path
) -> None:
    settings_service = ApplicationSettingsService(settings_repository, prepare_output_folder)
    new_folder = tmp_path / "external" / "scans"

    settings_service.update(build_update(output_folder=str(new_folder)))

    assert new_folder.is_dir()


@pytest.fixture
def home_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_update_expands_the_home_folder_marker(
    settings_service: ApplicationSettingsService, home_folder: Path
) -> None:
    saved = settings_service.update(build_update(output_folder="~/Pictures/Digitalizadora"))

    assert saved.output_folder == home_folder / "Pictures" / "Digitalizadora"


def test_update_prepares_the_expanded_home_folder(
    settings_service: ApplicationSettingsService,
    folder_preparer: RecordingFolderPreparer,
    home_folder: Path,
) -> None:
    settings_service.update(build_update(output_folder="~/Pictures/Digitalizadora"))

    assert folder_preparer.prepared_folders == [home_folder / "Pictures" / "Digitalizadora"]


@pytest.mark.parametrize("relative_folder", ["scans", "./scans", "../scans", ""])
def test_update_rejects_a_relative_output_folder(
    settings_service: ApplicationSettingsService, relative_folder: str
) -> None:
    with pytest.raises(InvalidSettingsError):
        settings_service.update(build_update(output_folder=relative_folder))


def test_update_rejects_a_folder_with_a_null_character(
    settings_service: ApplicationSettingsService,
) -> None:
    with pytest.raises(InvalidSettingsError):
        settings_service.update(build_update(output_folder=FOLDER_WITH_NULL_CHARACTER))


def test_update_rejects_the_home_folder_of_an_unknown_user(
    settings_service: ApplicationSettingsService,
) -> None:
    with pytest.raises(InvalidSettingsError):
        settings_service.update(build_update(output_folder=FOLDER_OF_UNKNOWN_USER))


def test_update_rejects_an_unknown_output_format(
    settings_service: ApplicationSettingsService,
) -> None:
    with pytest.raises(InvalidSettingsError):
        settings_service.update(build_update(output_format="tiff"))


@pytest.mark.parametrize("output_format", list(OutputFormat))
def test_update_accepts_every_known_format(
    settings_service: ApplicationSettingsService, output_format: OutputFormat
) -> None:
    saved = settings_service.update(build_update(output_format=output_format.value))

    assert saved.output_format == output_format


def test_update_without_a_quality_keeps_the_saved_quality(settings_service: ApplicationSettingsService) -> None:
    saved = settings_service.update(build_update())

    assert saved.scan_settings == INITIAL_SETTINGS.scan_settings


INVALID_UPDATES = [
    build_update(output_format="tiff"),
    build_update(output_folder="relative/scans"),
    build_update(output_folder=FOLDER_WITH_NULL_CHARACTER),
    build_update(output_folder=FOLDER_OF_UNKNOWN_USER),
    build_capture_mode_update("batch"),
]


@pytest.mark.parametrize("invalid_update", INVALID_UPDATES)
def test_invalid_update_saves_nothing(
    settings_service: ApplicationSettingsService,
    settings_repository: InMemoryApplicationSettingsRepository,
    invalid_update: SettingsUpdate,
) -> None:
    with pytest.raises(InvalidSettingsError):
        settings_service.update(invalid_update)

    assert settings_repository.load() == INITIAL_SETTINGS


@pytest.mark.parametrize("invalid_update", INVALID_UPDATES)
def test_invalid_update_prepares_no_folder(
    settings_service: ApplicationSettingsService,
    folder_preparer: RecordingFolderPreparer,
    invalid_update: SettingsUpdate,
) -> None:
    with pytest.raises(InvalidSettingsError):
        settings_service.update(invalid_update)

    assert folder_preparer.prepared_folders == []


def test_unavailable_folder_propagates_and_saves_nothing(
    settings_service: ApplicationSettingsService,
    settings_repository: InMemoryApplicationSettingsRepository,
    folder_preparer: RecordingFolderPreparer,
) -> None:
    folder_preparer.failure = OutputFolderUnavailableError("volume disconnected")

    with pytest.raises(OutputFolderUnavailableError):
        settings_service.update(build_update())

    assert settings_repository.load() == INITIAL_SETTINGS


DOCUMENT_MODE_SETTINGS = dataclasses.replace(INITIAL_SETTINGS, capture_mode=CaptureMode.DOCUMENT)


@pytest.fixture
def document_mode_repository() -> InMemoryApplicationSettingsRepository:
    return InMemoryApplicationSettingsRepository(DOCUMENT_MODE_SETTINGS)


@pytest.fixture
def document_mode_service(
    document_mode_repository: InMemoryApplicationSettingsRepository,
    folder_preparer: RecordingFolderPreparer,
) -> ApplicationSettingsService:
    return ApplicationSettingsService(document_mode_repository, folder_preparer)


def test_update_without_capture_mode_keeps_the_saved_mode(
    document_mode_service: ApplicationSettingsService,
) -> None:
    saved = document_mode_service.update(build_update())

    assert saved.capture_mode is CaptureMode.DOCUMENT


def test_update_without_capture_mode_saves_the_kept_mode(
    document_mode_service: ApplicationSettingsService,
    document_mode_repository: InMemoryApplicationSettingsRepository,
) -> None:
    document_mode_service.update(build_capture_mode_update(None))

    assert document_mode_repository.load().capture_mode is CaptureMode.DOCUMENT


def test_update_with_the_document_mode_saves_it(
    settings_service: ApplicationSettingsService,
    settings_repository: InMemoryApplicationSettingsRepository,
) -> None:
    settings_service.update(build_capture_mode_update("document"))

    assert settings_repository.load().capture_mode is CaptureMode.DOCUMENT


def test_update_with_the_single_mode_leaves_the_document_mode(
    document_mode_service: ApplicationSettingsService,
) -> None:
    saved = document_mode_service.update(build_capture_mode_update("single"))

    assert saved.capture_mode is CaptureMode.SINGLE


@pytest.mark.parametrize("capture_mode", list(CaptureMode))
def test_update_accepts_every_known_capture_mode(
    settings_service: ApplicationSettingsService, capture_mode: CaptureMode
) -> None:
    saved = settings_service.update(build_capture_mode_update(capture_mode.value))

    assert saved.capture_mode is capture_mode


@pytest.mark.parametrize("unknown_capture_mode", ["batch", "DOCUMENT", ""])
def test_update_rejects_an_unknown_capture_mode(
    settings_service: ApplicationSettingsService, unknown_capture_mode: str
) -> None:
    with pytest.raises(InvalidSettingsError):
        settings_service.update(build_capture_mode_update(unknown_capture_mode))


def build_quality_update(
    dots_per_inch: int | None = None,
    color_mode: str | None = None,
) -> SettingsUpdate:
    return SettingsUpdate(
        output_folder="/Volumes/External/scans",
        output_format="jpg",
        dots_per_inch=dots_per_inch,
        color_mode=color_mode,
    )


@pytest.fixture
def custom_quality_service(folder_preparer: RecordingFolderPreparer) -> ApplicationSettingsService:
    custom_settings = dataclasses.replace(INITIAL_SETTINGS, scan_settings=ScanSettings(1200, ColorMode.GRAYSCALE))
    return ApplicationSettingsService(InMemoryApplicationSettingsRepository(custom_settings), folder_preparer)


def test_a_resolution_alone_keeps_the_saved_colour_mode(
    custom_quality_service: ApplicationSettingsService,
) -> None:
    saved = custom_quality_service.update(build_quality_update(dots_per_inch=75))

    assert saved.scan_settings == ScanSettings(75, ColorMode.GRAYSCALE)


def test_a_colour_mode_alone_keeps_the_saved_resolution(
    custom_quality_service: ApplicationSettingsService,
) -> None:
    saved = custom_quality_service.update(build_quality_update(color_mode="color"))

    assert saved.scan_settings == ScanSettings(1200, ColorMode.COLOR)


def test_no_quality_field_keeps_the_saved_quality(custom_quality_service: ApplicationSettingsService) -> None:
    saved = custom_quality_service.update(build_quality_update())

    assert saved.scan_settings == ScanSettings(1200, ColorMode.GRAYSCALE)


@pytest.mark.parametrize("dots_per_inch", list(SUPPORTED_DOTS_PER_INCH))
def test_every_supported_resolution_is_accepted(
    settings_service: ApplicationSettingsService, dots_per_inch: int
) -> None:
    saved = settings_service.update(build_quality_update(dots_per_inch=dots_per_inch))

    assert saved.scan_settings.dots_per_inch == dots_per_inch


@pytest.mark.parametrize("dots_per_inch", [0, 72, 301, 2400, -300])
def test_an_unsupported_resolution_is_refused(
    settings_service: ApplicationSettingsService, dots_per_inch: int
) -> None:
    with pytest.raises(InvalidSettingsError):
        settings_service.update(build_quality_update(dots_per_inch=dots_per_inch))


def test_an_unknown_colour_mode_is_refused(settings_service: ApplicationSettingsService) -> None:
    with pytest.raises(InvalidSettingsError):
        settings_service.update(build_quality_update(color_mode="sepia"))


def test_the_one_bit_mode_is_not_offered(settings_service: ApplicationSettingsService) -> None:
    with pytest.raises(InvalidSettingsError):
        settings_service.update(build_quality_update(color_mode="BlackAndWhite1"))


def build_adjustment_update(auto_crop: bool | None = None) -> SettingsUpdate:
    return SettingsUpdate(
        output_folder="/Volumes/External/scans",
        output_format="jpg",
        auto_crop=auto_crop,
    )


@pytest.fixture
def adjusted_service(folder_preparer: RecordingFolderPreparer) -> ApplicationSettingsService:
    adjusted_settings = dataclasses.replace(
        INITIAL_SETTINGS, adjustment=ImageAdjustment(auto_crop=True)
    )
    return ApplicationSettingsService(InMemoryApplicationSettingsRepository(adjusted_settings), folder_preparer)


def test_update_without_adjustment_fields_keeps_the_saved_adjustment(
    adjusted_service: ApplicationSettingsService,
) -> None:
    saved = adjusted_service.update(build_adjustment_update())

    assert saved.adjustment == ImageAdjustment(auto_crop=True)


def test_a_crop_choice_is_saved(adjusted_service: ApplicationSettingsService) -> None:
    saved = adjusted_service.update(build_adjustment_update(auto_crop=False))

    assert saved.adjustment == ImageAdjustment(auto_crop=False)


def build_jpeg_quality_update(jpeg_quality: object) -> SettingsUpdate:
    return SettingsUpdate(output_folder="/Volumes/External/scans", output_format="jpg", jpeg_quality=jpeg_quality)


def test_a_jpeg_quality_is_saved(settings_service: ApplicationSettingsService) -> None:
    saved = settings_service.update(build_jpeg_quality_update(65))

    assert saved.adjustment.jpeg_quality == 65


def test_a_jpeg_quality_keeps_the_crop_choice(adjusted_service: ApplicationSettingsService) -> None:
    saved = adjusted_service.update(build_jpeg_quality_update(65))

    assert saved.adjustment == ImageAdjustment(auto_crop=True, jpeg_quality=65)


def test_a_crop_choice_keeps_the_saved_jpeg_quality(settings_service: ApplicationSettingsService) -> None:
    settings_service.update(build_jpeg_quality_update(65))

    saved = settings_service.update(build_adjustment_update(auto_crop=True))

    assert saved.adjustment == ImageAdjustment(auto_crop=True, jpeg_quality=65)


def test_an_update_without_a_jpeg_quality_keeps_the_default(settings_service: ApplicationSettingsService) -> None:
    assert settings_service.update(build_update()).adjustment.jpeg_quality == 90


@pytest.mark.parametrize("invalid_quality", [49, 101, True, 72.5, "72"])
def test_an_invalid_jpeg_quality_is_refused_and_saves_nothing(
    settings_service: ApplicationSettingsService,
    settings_repository: InMemoryApplicationSettingsRepository,
    invalid_quality: object,
) -> None:
    with pytest.raises(InvalidSettingsError):
        settings_service.update(build_jpeg_quality_update(invalid_quality))

    assert settings_repository.load() == INITIAL_SETTINGS


INVALID_QUALITY_AND_ADJUSTMENT_UPDATES = [
    build_quality_update(dots_per_inch=301),
    build_quality_update(color_mode="sepia"),
]


@pytest.mark.parametrize("invalid_update", INVALID_QUALITY_AND_ADJUSTMENT_UPDATES)
def test_a_refused_quality_or_adjustment_saves_nothing(
    settings_service: ApplicationSettingsService,
    settings_repository: InMemoryApplicationSettingsRepository,
    invalid_update: SettingsUpdate,
) -> None:
    with pytest.raises(InvalidSettingsError):
        settings_service.update(invalid_update)

    assert settings_repository.load() == INITIAL_SETTINGS


def test_a_crop_margin_choice_is_saved(adjusted_service: ApplicationSettingsService) -> None:
    update = SettingsUpdate(output_folder="/Volumes/External/scans", output_format="jpg", crop_margin=False)

    assert adjusted_service.update(update).adjustment == ImageAdjustment(auto_crop=True, crop_margin=False)


def test_the_crop_margin_is_on_by_default() -> None:
    assert ImageAdjustment().crop_margin is True

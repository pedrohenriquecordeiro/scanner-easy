from pathlib import Path

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from tests.fakes.in_memory_settings_repository import InMemoryApplicationSettingsRepository

INITIAL_SETTINGS = ApplicationSettings(Path("/scans"), OutputFormat.PDF, ScanPreset.DOCUMENT)
CHANGED_SETTINGS = ApplicationSettings(Path("/photos"), OutputFormat.JPEG, ScanPreset.PHOTO)


def test_load_returns_the_settings_given_at_construction():
    assert InMemoryApplicationSettingsRepository(INITIAL_SETTINGS).load() == INITIAL_SETTINGS


def test_load_returns_the_last_saved_settings():
    repository = InMemoryApplicationSettingsRepository(INITIAL_SETTINGS)

    repository.save(CHANGED_SETTINGS)

    assert repository.load() == CHANGED_SETTINGS

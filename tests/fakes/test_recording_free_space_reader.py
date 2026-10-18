from pathlib import Path

import pytest

from digitalizadora.domain.errors import OutputFolderUnavailableError
from tests.fakes.recording_free_space_reader import RecordingFreeSpaceReader

OUTPUT_FOLDER = Path("/Volumes/Archive/Scans")


def test_answers_the_free_space_given_at_construction():
    assert RecordingFreeSpaceReader(123_456)(OUTPUT_FOLDER) == 123_456


def test_records_every_requested_folder():
    reader = RecordingFreeSpaceReader(123_456)

    reader(OUTPUT_FOLDER)
    reader(OUTPUT_FOLDER / "other")

    assert reader.requested_folders == [OUTPUT_FOLDER, OUTPUT_FOLDER / "other"]


def test_raises_the_configured_failure_and_still_records_the_folder():
    reader = RecordingFreeSpaceReader(123_456)
    reader.failure = OutputFolderUnavailableError("The external disk was disconnected")

    with pytest.raises(OutputFolderUnavailableError):
        reader(OUTPUT_FOLDER)

    assert reader.requested_folders == [OUTPUT_FOLDER]

import pytest

from digitalizadora.domain.settings.capture_mode import CaptureMode


def test_capture_modes_are_single_and_document_in_this_order() -> None:
    assert [capture_mode.value for capture_mode in CaptureMode] == ["single", "document"]


@pytest.mark.parametrize("capture_mode", list(CaptureMode))
def test_capture_mode_is_created_from_its_stored_text(capture_mode: CaptureMode) -> None:
    assert CaptureMode(capture_mode.value) is capture_mode


def test_capture_mode_compares_equal_to_its_text() -> None:
    assert CaptureMode.DOCUMENT == "document"


def test_unknown_text_is_not_a_capture_mode() -> None:
    with pytest.raises(ValueError):
        CaptureMode("batch")

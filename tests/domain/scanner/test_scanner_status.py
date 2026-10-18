import pytest

from digitalizadora.domain.scanner.scanner_status import ScannerState, ScannerStatus


def test_status_is_ready_when_idle() -> None:
    assert ScannerStatus(ScannerState.IDLE).is_ready is True


@pytest.mark.parametrize(
    "state",
    [state for state in ScannerState if state is not ScannerState.IDLE],
)
def test_status_is_not_ready_in_any_other_state(state: ScannerState) -> None:
    assert ScannerStatus(state).is_ready is False

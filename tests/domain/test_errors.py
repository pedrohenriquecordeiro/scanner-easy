import pytest

from digitalizadora.domain import errors


@pytest.mark.parametrize(
    ("error_class", "expected_code"),
    [
        (errors.DigitalizadoraError, "unexpected_error"),
        (errors.ScannerUnreachableError, "scanner_unreachable"),
        (errors.LocalNetworkBlockedError, "local_network_blocked"),
        (errors.ScannerBusyError, "scanner_busy"),
        (errors.ScanRejectedError, "scan_rejected"),
        (errors.ScanFailedError, "scan_failed"),
        (errors.ScanTimedOutError, "scan_timed_out"),
        (errors.ScanAlreadyRunningError, "scan_already_running"),
        (errors.InsufficientStorageError, "insufficient_storage"),
        (errors.OutputFolderUnavailableError, "output_folder_unavailable"),
        (errors.InvalidSettingsError, "invalid_settings"),
    ],
)
def test_error_class_exposes_its_code(
    error_class: type[errors.DigitalizadoraError], expected_code: str
) -> None:
    assert error_class("internal detail").code == expected_code


def test_local_network_blocked_is_a_scanner_unreachable_error() -> None:
    assert issubclass(errors.LocalNetworkBlockedError, errors.ScannerUnreachableError)


def test_every_error_derives_from_the_base_error() -> None:
    error_classes = [
        value
        for value in vars(errors).values()
        if isinstance(value, type) and issubclass(value, Exception)
    ]

    assert all(issubclass(error_class, errors.DigitalizadoraError) for error_class in error_classes)

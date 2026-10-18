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
        (errors.NoOpenDocumentError, "no_open_document"),
        (errors.PageNotFoundError, "page_not_found"),
        (errors.InvalidPageOrderError, "invalid_page_order"),
        (errors.InvalidDocumentNameError, "invalid_document_name"),
        (errors.EmptyDocumentError, "empty_document"),
        (errors.DocumentBusyError, "document_busy"),
        (errors.DraftFolderInUseError, "draft_folder_in_use"),
        (errors.DraftStorageUnavailableError, "draft_storage_unavailable"),
        (errors.UnreadableDraftError, "draft_storage_unavailable"),
        (errors.InsufficientDraftStorageError, "insufficient_draft_storage"),
        (errors.DocumentAssemblyFailedError, "document_assembly_failed"),
        (errors.DocumentTooLargeError, "document_too_large"),
        (errors.ImageAdjustmentFailedError, "image_adjustment_failed"),
        (errors.InvalidCropError, "invalid_crop"),
        (errors.InvalidPageRotationError, "invalid_page_rotation"),
        (errors.NoLastScanError, "no_last_scan"),
        (errors.LastScanFileMissingError, "last_scan_file_missing"),
        (errors.SavedScanUnreadableError, "saved_scan_unreadable"),
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


DAMAGED_PAGE_IDENTIFIER = "3f9c0a1b2c3d4e5f"
DAMAGED_PAGE_POSITION = 7


@pytest.mark.parametrize(
    ("error_class", "parent_class"),
    [
        (errors.UnreadableDraftError, errors.DraftStorageUnavailableError),
        (errors.InsufficientDraftStorageError, errors.InsufficientStorageError),
        (errors.DamagedDocumentPageError, errors.DocumentAssemblyFailedError),
        (errors.DocumentTooLargeError, errors.DocumentAssemblyFailedError),
    ],
)
def test_draft_error_specializes_its_parent(
    error_class: type[errors.DigitalizadoraError], parent_class: type[errors.DigitalizadoraError]
) -> None:
    assert issubclass(error_class, parent_class)


def build_damaged_page_error() -> errors.DamagedDocumentPageError:
    return errors.DamagedDocumentPageError(DAMAGED_PAGE_IDENTIFIER, DAMAGED_PAGE_POSITION)


def test_damaged_document_page_error_exposes_its_code() -> None:
    assert build_damaged_page_error().code == "damaged_document_page"


def test_damaged_document_page_error_keeps_the_page_identifier() -> None:
    assert build_damaged_page_error().page_identifier == DAMAGED_PAGE_IDENTIFIER


def test_damaged_document_page_error_keeps_the_page_position() -> None:
    assert build_damaged_page_error().page_position == DAMAGED_PAGE_POSITION


def test_damaged_document_page_error_message_names_the_page() -> None:
    assert str(build_damaged_page_error()) == "Page 7 (3f9c0a1b2c3d4e5f) is missing or has an unexpected size"


def test_insufficient_storage_becomes_insufficient_draft_storage() -> None:
    translated = errors.as_draft_storage_error(errors.InsufficientStorageError("disk full"))

    assert type(translated) is errors.InsufficientDraftStorageError


def test_draft_storage_translation_keeps_the_internal_message() -> None:
    translated = errors.as_draft_storage_error(errors.InsufficientStorageError("disk full"))

    assert str(translated) == "disk full"


def test_unavailable_output_folder_becomes_unavailable_draft_storage() -> None:
    translated = errors.as_draft_storage_error(errors.OutputFolderUnavailableError("read-only"))

    assert type(translated) is errors.DraftStorageUnavailableError


def test_draft_storage_translation_returns_any_other_error_unchanged() -> None:
    original = errors.ScanFailedError("broken image")

    assert errors.as_draft_storage_error(original) is original


def test_draft_storage_translation_returns_a_draft_error_unchanged() -> None:
    original = errors.InsufficientDraftStorageError("draft disk full")

    assert errors.as_draft_storage_error(original) is original

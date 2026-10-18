class DigitalizadoraError(Exception):
    code = "unexpected_error"


class ScannerUnreachableError(DigitalizadoraError):
    code = "scanner_unreachable"


class LocalNetworkBlockedError(ScannerUnreachableError):
    code = "local_network_blocked"


class ScannerBusyError(DigitalizadoraError):
    code = "scanner_busy"


class ScanRejectedError(DigitalizadoraError):
    code = "scan_rejected"


class ScanFailedError(DigitalizadoraError):
    code = "scan_failed"


class ScanTimedOutError(DigitalizadoraError):
    code = "scan_timed_out"


class ScanAlreadyRunningError(DigitalizadoraError):
    code = "scan_already_running"


class InsufficientStorageError(DigitalizadoraError):
    code = "insufficient_storage"


class OutputFolderUnavailableError(DigitalizadoraError):
    code = "output_folder_unavailable"


class InvalidSettingsError(DigitalizadoraError):
    code = "invalid_settings"


class NoOpenDocumentError(DigitalizadoraError):
    code = "no_open_document"


class PageNotFoundError(DigitalizadoraError):
    code = "page_not_found"


class InvalidPageOrderError(DigitalizadoraError):
    code = "invalid_page_order"


class InvalidDocumentNameError(DigitalizadoraError):
    code = "invalid_document_name"


class EmptyDocumentError(DigitalizadoraError):
    code = "empty_document"


class DocumentBusyError(DigitalizadoraError):
    code = "document_busy"


class DraftFolderInUseError(DigitalizadoraError):
    code = "draft_folder_in_use"


class DraftStorageUnavailableError(DigitalizadoraError):
    code = "draft_storage_unavailable"


class UnreadableDraftError(DraftStorageUnavailableError):
    """The manifest cannot be used; the recovery sets the draft folder aside."""


class InsufficientDraftStorageError(InsufficientStorageError):
    code = "insufficient_draft_storage"


class DocumentAssemblyFailedError(DigitalizadoraError):
    code = "document_assembly_failed"


class DamagedDocumentPageError(DocumentAssemblyFailedError):
    code = "damaged_document_page"

    def __init__(self, page_identifier: str, page_position: int) -> None:
        super().__init__(f"Page {page_position} ({page_identifier}) is missing or has an unexpected size")
        self.page_identifier = page_identifier
        self.page_position = page_position


class DocumentTooLargeError(DocumentAssemblyFailedError):
    code = "document_too_large"


class ImageAdjustmentFailedError(DigitalizadoraError):
    code = "image_adjustment_failed"


class InvalidCropError(DigitalizadoraError):
    code = "invalid_crop"


class InvalidPageRotationError(DigitalizadoraError):
    code = "invalid_page_rotation"


class NoLastScanError(DigitalizadoraError):
    code = "no_last_scan"


class LastScanFileMissingError(DigitalizadoraError):
    code = "last_scan_file_missing"


class SavedScanUnreadableError(DigitalizadoraError):
    code = "saved_scan_unreadable"


class UnreadableQuickScanError(SavedScanUnreadableError):
    """The manifest or the master of the last quick scan cannot be used; the recovery sets the slot aside."""


class LastScanNotEditableError(DigitalizadoraError):
    code = "last_scan_not_editable"


class LastScanBusyError(DigitalizadoraError):
    code = "last_scan_busy"


def as_draft_storage_error(error: DigitalizadoraError) -> DigitalizadoraError:
    """Translates a storage error raised for the draft folder, which lives on the internal disk."""
    if isinstance(error, InsufficientStorageError) and not isinstance(error, InsufficientDraftStorageError):
        return InsufficientDraftStorageError(str(error))
    if isinstance(error, OutputFolderUnavailableError):
        return DraftStorageUnavailableError(str(error))
    return error

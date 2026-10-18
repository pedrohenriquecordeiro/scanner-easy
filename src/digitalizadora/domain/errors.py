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

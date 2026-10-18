from typing import Any

from digitalizadora.domain.scan_result import ScanResult


def describe_scan_result(result: ScanResult) -> dict[str, Any]:
    """The last saved file as the page shows it, in the state and in the answer of turning it."""
    return {
        "file_name": result.output_path.name,
        "output_folder": str(result.output_path.parent),
        "output_format": result.output_format.value,
        "size_in_bytes": result.size_in_bytes,
        "scanned_at": result.scanned_at.isoformat(),
    }

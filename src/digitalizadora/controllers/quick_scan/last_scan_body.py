from typing import Any

from digitalizadora.controllers.documents.document_body import describe_crop
from digitalizadora.domain.quick_scan.last_scan import LastScan


def describe_last_scan(last_scan: LastScan) -> dict[str, Any]:
    """The last quick scan as the page shows it, in the state and in the answer of an adjustment."""
    return {
        "scan_identifier": last_scan.scan_identifier,
        "file_names": [saved_file.file_name for saved_file in last_scan.saved_files],
        "output_folder": str(last_scan.output_folder),
        "output_format": last_scan.output_format.value,
        "total_size_in_bytes": last_scan.total_size_in_bytes,
        "scanned_at": last_scan.scanned_at.isoformat(),
        "rotation_degrees": last_scan.framing.rotation.value,
        "crops": [describe_crop(crop) for crop in last_scan.framing.crops],
        "is_editable": last_scan.is_editable,
    }

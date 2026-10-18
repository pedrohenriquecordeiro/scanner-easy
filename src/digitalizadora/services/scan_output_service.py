from digitalizadora.domain.ports import ScanOutputRepository
from digitalizadora.domain.scan_job import ScanJob
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.domain.stored_scan import StoredScan
from digitalizadora.services.scan_encoder import ScanEncoder
from digitalizadora.services.storage_guard_service import StorageGuardService


class ScanOutputService:
    def __init__(
        self,
        scan_encoder: ScanEncoder,
        scan_output_repository: ScanOutputRepository,
        storage_guard_service: StorageGuardService,
    ) -> None:
        self._scan_encoder = scan_encoder
        self._scan_output_repository = scan_output_repository
        self._storage_guard_service = storage_guard_service

    def ensure_capacity(self, request: ScanRequest) -> None:
        # The folder comes first: a disconnected disk must fail before the printer spends up to 75 s on a page.
        self._scan_output_repository.ensure_output_folder_ready()
        self._storage_guard_service.ensure_space_for_scan(
            self._scan_output_repository.output_folder(), request.settings, request.adjustment
        )

    def store(self, scanned_image: ScannedImage, job: ScanJob) -> StoredScan:
        encoded_scan = self._scan_encoder.encode(scanned_image, job)
        output_path = self._scan_output_repository.save(encoded_scan)
        result = ScanResult(
            output_path=output_path,
            output_format=encoded_scan.output_format,
            scanned_at=encoded_scan.created_at,
            size_in_bytes=len(encoded_scan.content),
        )
        return StoredScan(result, encoded_scan.thumbnail_jpeg)

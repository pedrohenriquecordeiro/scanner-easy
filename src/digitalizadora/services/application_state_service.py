from dataclasses import dataclass

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.errors import OutputFolderUnavailableError
from digitalizadora.domain.ports import ApplicationSettingsRepository
from digitalizadora.domain.scan_progress import ScanProgressSnapshot
from digitalizadora.services.scan_progress_tracker import ScanProgressTracker
from digitalizadora.services.storage_guard_service import StorageGuardService


@dataclass(frozen=True)
class StorageState:
    free_space_in_bytes: int
    estimated_pages_remaining: int
    output_folder_available: bool = True


UNAVAILABLE_STORAGE_STATE = StorageState(
    free_space_in_bytes=0, estimated_pages_remaining=0, output_folder_available=False
)


@dataclass(frozen=True)
class ApplicationState:
    snapshot: ScanProgressSnapshot
    settings: ApplicationSettings
    storage: StorageState


class ApplicationStateService:
    def __init__(
        self,
        progress_tracker: ScanProgressTracker,
        settings_repository: ApplicationSettingsRepository,
        storage_guard_service: StorageGuardService,
    ) -> None:
        self._progress_tracker = progress_tracker
        self._settings_repository = settings_repository
        self._storage_guard_service = storage_guard_service

    def build_state(self) -> ApplicationState:
        settings = self._settings_repository.load()
        return ApplicationState(
            snapshot=self._progress_tracker.snapshot(),
            settings=settings,
            storage=self._build_storage_state(settings),
        )

    def _build_storage_state(self, settings: ApplicationSettings) -> StorageState:
        folder = settings.output_folder
        try:
            free_space_in_bytes = self._storage_guard_service.free_space_in_bytes(folder)
            estimated_pages_remaining = self._storage_guard_service.estimate_pages_remaining(
                folder, settings.scan_settings, settings.adjustment
            )
        except OutputFolderUnavailableError:
            return UNAVAILABLE_STORAGE_STATE
        return StorageState(
            free_space_in_bytes=free_space_in_bytes,
            estimated_pages_remaining=estimated_pages_remaining,
        )

from typing import Any

from fastapi import APIRouter

from digitalizadora.controllers.document_body import build_document_summary_body
from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog, build_error_body
from digitalizadora.controllers.settings_body import build_settings_body
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.services.application_state_service import (
    ApplicationState,
    ApplicationStateService,
    StorageState,
)
from digitalizadora.services.document_draft_service import DocumentDraftService


class StateController:
    def __init__(
        self,
        state_service: ApplicationStateService,
        document_draft_service: DocumentDraftService,
        error_message_catalog: ErrorMessageCatalog,
    ) -> None:
        self._state_service = state_service
        self._document_draft_service = document_draft_service
        self._error_message_catalog = error_message_catalog

    def build_router(self) -> APIRouter:
        router = APIRouter()
        router.add_api_route("/api/health", self.read_health, methods=["GET"])
        router.add_api_route("/api/state", self.read_state, methods=["GET"])
        return router

    async def read_health(self) -> dict[str, str]:
        return {"status": "ok"}

    def read_state(self) -> dict[str, Any]:
        state = self._state_service.build_state()
        return {
            "scan_phase": state.snapshot.phase.value,
            "scans_completed": state.snapshot.scans_completed,
            "last_result": self._describe_last_result(state.snapshot.last_result),
            "last_error": self._describe_last_error(state),
            "settings": build_settings_body(state.settings),
            "storage": self._describe_storage(state.storage),
            "document": self._describe_document(state),
        }

    def _describe_document(self, state: ApplicationState) -> dict[str, Any]:
        """R8 and R20: the page compares draft_session and revision and re-reads GET /api/document."""
        return build_document_summary_body(
            self._document_draft_service.snapshot(),
            self._document_draft_service.describe_draft_storage(state.settings.scan_preset.settings),
        )

    @staticmethod
    def _describe_last_result(last_result: ScanResult | None) -> dict[str, Any] | None:
        if last_result is None:
            return None
        return {
            "file_name": last_result.output_path.name,
            "output_folder": str(last_result.output_path.parent),
            "output_format": last_result.output_format.value,
            "size_in_bytes": last_result.size_in_bytes,
            "scanned_at": last_result.scanned_at.isoformat(),
        }

    @staticmethod
    def _describe_storage(storage: StorageState) -> dict[str, Any]:
        return {
            "free_space_in_bytes": storage.free_space_in_bytes,
            "estimated_pages_remaining": storage.estimated_pages_remaining,
            "output_folder_available": storage.output_folder_available,
        }

    def _describe_last_error(self, state: ApplicationState) -> dict[str, str] | None:
        error_code = state.snapshot.last_error_code
        if error_code is None:
            return None
        return build_error_body(self._error_message_catalog, error_code)

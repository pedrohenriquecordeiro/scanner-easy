from typing import Any

from fastapi import APIRouter

from digitalizadora.controllers.documents.document_body import build_document_summary_body
from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog, build_error_body
from digitalizadora.controllers.quick_scan.last_scan_body import describe_last_scan
from digitalizadora.controllers.settings_body import build_settings_body
from digitalizadora.domain.quick_scan.last_scan import LastScan
from digitalizadora.services.application_state_service import (
    ApplicationState,
    ApplicationStateService,
    StorageState,
)
from digitalizadora.services.documents.document_draft_service import DocumentDraftService


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
            "last_result": self._describe_last_result(state.snapshot.last_scan),
            "last_result_revision": state.snapshot.last_result_revision,
            "last_error": self._describe_last_error(state),
            "settings": build_settings_body(state.settings),
            "storage": self._describe_storage(state.storage),
            "document": self._describe_document(state),
        }

    def _describe_document(self, state: ApplicationState) -> dict[str, Any]:
        """R8 and R20: the page compares draft_session and revision and re-reads GET /api/document."""
        draft_storage = self._document_draft_service.describe_draft_storage(state.settings.scan_settings)
        return build_document_summary_body(self._document_draft_service.snapshot(), draft_storage)

    @staticmethod
    def _describe_last_result(last_scan: LastScan | None) -> dict[str, Any] | None:
        return None if last_scan is None else describe_last_scan(last_scan)

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

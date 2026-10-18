import logging
from collections.abc import Awaitable, Mapping
from http import HTTPStatus
from types import MappingProxyType
from typing import Any

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from digitalizadora.controllers.document_body import build_document_body
from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog, build_error_body
from digitalizadora.domain.errors import DamagedDocumentPageError, DigitalizadoraError
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.services.application_settings_service import ApplicationSettingsService
from digitalizadora.services.document_draft_service import DocumentDraftService

logger = logging.getLogger(__name__)

JPEG_MEDIA_TYPE = "image/jpeg"
DOCUMENT_ERROR_STATUSES: Mapping[str, HTTPStatus] = MappingProxyType(
    {
        "scan_already_running": HTTPStatus.CONFLICT,
        "document_busy": HTTPStatus.CONFLICT,
        "damaged_document_page": HTTPStatus.CONFLICT,
        "no_open_document": HTTPStatus.NOT_FOUND,
        "page_not_found": HTTPStatus.NOT_FOUND,
        "invalid_page_order": HTTPStatus.UNPROCESSABLE_ENTITY,
        "invalid_document_name": HTTPStatus.UNPROCESSABLE_ENTITY,
        "empty_document": HTTPStatus.UNPROCESSABLE_ENTITY,
        "output_folder_unavailable": HTTPStatus.SERVICE_UNAVAILABLE,
        "draft_storage_unavailable": HTTPStatus.SERVICE_UNAVAILABLE,
        "insufficient_storage": HTTPStatus.INSUFFICIENT_STORAGE,
        "insufficient_draft_storage": HTTPStatus.INSUFFICIENT_STORAGE,
    }
)
# A page identifier is never reused, so its thumbnail never changes.
THUMBNAIL_CACHE_HEADERS: Mapping[str, str] = MappingProxyType(
    {"Cache-Control": "private, max-age=31536000, immutable"}
)


class PageOrderRequestBody(BaseModel):
    page_identifiers: list[str]


class DocumentNameRequestBody(BaseModel):
    name: str


class DocumentController:
    def __init__(
        self,
        document_draft_service: DocumentDraftService,
        settings_service: ApplicationSettingsService,
        error_message_catalog: ErrorMessageCatalog,
    ) -> None:
        self._document_draft_service = document_draft_service
        self._settings_service = settings_service
        self._error_message_catalog = error_message_catalog

    def build_router(self) -> APIRouter:
        router = APIRouter()
        router.add_api_route("/api/document", self.read_document, methods=["GET"])
        router.add_api_route("/api/document/pages", self.add_page, methods=["POST"])
        # /pages/last comes before /pages/{page_identifier}, so "last" is never taken for an identifier.
        router.add_api_route("/api/document/pages/last", self.discard_last_page, methods=["DELETE"])
        router.add_api_route("/api/document/pages/{page_identifier}", self.delete_page, methods=["DELETE"])
        router.add_api_route(
            "/api/document/pages/{page_identifier}/thumbnail", self.read_thumbnail, methods=["GET"]
        )
        router.add_api_route("/api/document/page-order", self.reorder_pages, methods=["PUT"])
        router.add_api_route("/api/document/name", self.rename_document, methods=["PUT"])
        router.add_api_route("/api/document/finalize", self.finalize_document, methods=["POST"])
        router.add_api_route("/api/document", self.cancel_document, methods=["DELETE"])
        return router

    def read_document(self) -> dict[str, Any]:
        return build_document_body(self._document_draft_service.snapshot())

    async def add_page(self, background_tasks: BackgroundTasks) -> JSONResponse:
        try:
            self._document_draft_service.ensure_can_add_page()
        except DigitalizadoraError as error:
            return self._respond_to_error(error)
        settings = self._settings_service.current().scan_preset.settings
        background_tasks.add_task(self._run_add_page, settings)
        return JSONResponse(status_code=HTTPStatus.ACCEPTED, content={"accepted": True})

    async def discard_last_page(self) -> JSONResponse:
        return await self._respond_to_edit(self._document_draft_service.discard_last_page())

    async def delete_page(self, page_identifier: str) -> JSONResponse:
        return await self._respond_to_edit(self._document_draft_service.delete_page(page_identifier))

    def read_thumbnail(self, page_identifier: str) -> Response:
        thumbnail_jpeg = self._document_draft_service.read_thumbnail(page_identifier)
        if thumbnail_jpeg is None:
            return Response(status_code=HTTPStatus.NOT_FOUND)
        return Response(content=thumbnail_jpeg, media_type=JPEG_MEDIA_TYPE, headers=dict(THUMBNAIL_CACHE_HEADERS))

    async def reorder_pages(self, body: PageOrderRequestBody) -> JSONResponse:
        return await self._respond_to_edit(self._document_draft_service.reorder(body.page_identifiers))

    async def rename_document(self, body: DocumentNameRequestBody) -> JSONResponse:
        return await self._respond_to_edit(self._document_draft_service.rename(body.name))

    async def finalize_document(self) -> JSONResponse:
        try:
            finalization = await self._document_draft_service.finalize()
        except DigitalizadoraError as error:
            return self._respond_to_error(error)
        result = finalization.result
        return JSONResponse(
            content={
                "file_name": result.output_path.name,
                "output_folder": str(result.output_path.parent),
                "page_count": finalization.page_count,
                "size_in_bytes": result.size_in_bytes,
            }
        )

    async def cancel_document(self) -> JSONResponse:
        return await self._respond_to_edit(self._document_draft_service.cancel())

    async def _respond_to_edit(self, edit: Awaitable[object]) -> JSONResponse:
        """Every edit answers with the body of the snapshot taken after it ends."""
        try:
            await edit
        except DigitalizadoraError as error:
            return self._respond_to_error(error)
        return JSONResponse(content=build_document_body(self._document_draft_service.snapshot()))

    def _respond_to_error(self, error: DigitalizadoraError) -> JSONResponse:
        content: dict[str, str] = build_error_body(self._error_message_catalog, error.code)
        if isinstance(error, DamagedDocumentPageError):
            content["page_identifier"] = error.page_identifier
        return JSONResponse(
            status_code=DOCUMENT_ERROR_STATUSES.get(error.code, HTTPStatus.INTERNAL_SERVER_ERROR), content=content
        )

    async def _run_add_page(self, settings: ScanSettings) -> None:
        try:
            await self._document_draft_service.add_page(settings)
        except DigitalizadoraError as error:
            # The progress tracker already holds the code of a failed page. A refusal of the second check
            # (another accepted request went first) only reaches the log: no sheet is read twice (R17).
            logger.warning("Document page failed with code %s: %s", error.code, error)
        except Exception as error:
            # ScanService already logged the traceback and recorded unexpected_error.
            logger.error("Document page stopped by an unexpected failure: %s", error)

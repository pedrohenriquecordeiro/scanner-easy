import logging
from collections.abc import Awaitable, Callable, Mapping
from http import HTTPStatus
from types import MappingProxyType
from typing import Any

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, StrictFloat, StrictInt

from digitalizadora.controllers.document_body import build_document_body
from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog, build_error_body
from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.errors import (
    DamagedDocumentPageError,
    DigitalizadoraError,
    InvalidCropError,
    InvalidPageRotationError,
)
from digitalizadora.domain.page_crop import CROP_PRECISION_DIGITS, CropCorner, PageCrop, RectangleEdges
from digitalizadora.domain.page_framing import MAXIMUM_CROPS_PER_PAGE
from digitalizadora.domain.page_rotation import PageRotation
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
        "invalid_crop": HTTPStatus.UNPROCESSABLE_ENTITY,
        "invalid_page_rotation": HTTPStatus.UNPROCESSABLE_ENTITY,
        "empty_document": HTTPStatus.UNPROCESSABLE_ENTITY,
        "output_folder_unavailable": HTTPStatus.SERVICE_UNAVAILABLE,
        "draft_storage_unavailable": HTTPStatus.SERVICE_UNAVAILABLE,
        "insufficient_storage": HTTPStatus.INSUFFICIENT_STORAGE,
        "insufficient_draft_storage": HTTPStatus.INSUFFICIENT_STORAGE,
    }
)
# A page identifier is never reused and a page file never changes, so the thumbnail and the enlarged view are a
# pure function of the page and the rotation in the address.
THUMBNAIL_CACHE_HEADERS: Mapping[str, str] = MappingProxyType(
    {"Cache-Control": "private, max-age=31536000, immutable"}
)


class CropCornerRequestBody(BaseModel):
    x: StrictInt | StrictFloat
    y: StrictInt | StrictFloat

    def to_crop_corner(self) -> CropCorner:
        return CropCorner(self.x, self.y)


class PageCropRequestBody(BaseModel):
    """One crop: four corners in fractions of the page as it is displayed, clockwise from the top left."""

    top_left: CropCornerRequestBody
    top_right: CropCornerRequestBody
    bottom_right: CropCornerRequestBody
    bottom_left: CropCornerRequestBody

    def to_page_crop(self) -> PageCrop:
        return PageCrop.rounded(
            [
                self.top_left.to_crop_corner(),
                self.top_right.to_crop_corner(),
                self.bottom_right.to_crop_corner(),
                self.bottom_left.to_crop_corner(),
            ]
        )


class PageCropsRequestBody(BaseModel):
    """{"crops": []} removes the crops of the page."""

    crops: list[PageCropRequestBody] = Field(max_length=MAXIMUM_CROPS_PER_PAGE)

    def to_page_crops(self) -> list[PageCrop]:
        return [crop.to_page_crop() for crop in self.crops]


class ProvisionalCropEdgesRequestBody(BaseModel):
    left: StrictInt | StrictFloat
    top: StrictInt | StrictFloat
    right: StrictInt | StrictFloat
    bottom: StrictInt | StrictFloat


class ProvisionalCropRequestBody(BaseModel):
    """The old {"crop": {...} | null} of one rectangle, until the page sends the crops."""

    crop: ProvisionalCropEdgesRequestBody | None

    def to_page_crops(self) -> list[PageCrop]:
        if self.crop is None:
            return []
        edges = (self.crop.left, self.crop.top, self.crop.right, self.crop.bottom)
        return [PageCrop.from_rectangle(RectangleEdges(*(round(edge, CROP_PRECISION_DIGITS) for edge in edges)))]


def parse_page_rotation(rotation_degrees: int) -> PageRotation:
    try:
        return PageRotation(rotation_degrees)
    except ValueError as error:
        raise InvalidPageRotationError(f"Unsupported page rotation: {rotation_degrees!r}") from error


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
        router.add_api_route("/api/document/pages/{page_identifier}/preview", self.read_preview, methods=["GET"])
        router.add_api_route("/api/document/pages/{page_identifier}/rotation", self.rotate_page, methods=["POST"])
        router.add_api_route("/api/document/pages/{page_identifier}/crops", self.set_page_crops, methods=["PUT"])
        router.add_api_route(
            "/api/document/pages/{page_identifier}/crops/detect", self.detect_page_crops, methods=["POST"]
        )
        # Provisional alias of the old route, until the page sends the crops.
        router.add_api_route("/api/document/pages/{page_identifier}/crop", self.set_page_crop, methods=["PUT"])
        router.add_api_route(
            "/api/document/pages/{page_identifier}/crop/detect", self.detect_page_crops, methods=["POST"]
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
        settings = self._settings_service.current()
        background_tasks.add_task(self._run_add_page, settings)
        return JSONResponse(status_code=HTTPStatus.ACCEPTED, content={"accepted": True})

    async def discard_last_page(self) -> JSONResponse:
        return await self._respond_to_edit(self._document_draft_service.discard_last_page())

    async def delete_page(self, page_identifier: str) -> JSONResponse:
        return await self._respond_to_edit(self._document_draft_service.delete_page(page_identifier))

    async def rotate_page(self, page_identifier: str) -> JSONResponse:
        return await self._respond_to_edit(self._document_draft_service.rotate_page(page_identifier))

    async def set_page_crops(self, page_identifier: str, body: PageCropsRequestBody) -> JSONResponse:
        return await self._respond_to_crops_edit(page_identifier, body.to_page_crops)

    async def set_page_crop(self, page_identifier: str, body: ProvisionalCropRequestBody) -> JSONResponse:
        return await self._respond_to_crops_edit(page_identifier, body.to_page_crops)

    async def _respond_to_crops_edit(
        self, page_identifier: str, build_crops: Callable[[], list[PageCrop]]
    ) -> JSONResponse:
        try:
            crops = build_crops()
        except InvalidCropError as error:
            return self._respond_to_error(error)
        return await self._respond_to_edit(self._document_draft_service.set_page_crops(page_identifier, crops))

    async def detect_page_crops(self, page_identifier: str) -> JSONResponse:
        try:
            detection = await self._document_draft_service.detect_page_crops(page_identifier)
        except DigitalizadoraError as error:
            return self._respond_to_error(error)
        body = build_document_body(self._document_draft_service.snapshot())
        return JSONResponse(
            content={
                **body,
                "crops_detected": detection.crops_detected,
                "ignored_region_count": detection.ignored_region_count,
                "crop_detected": detection.crops_detected,
            }
        )

    def read_thumbnail(self, page_identifier: str, rotation_degrees: int = 0) -> Response:
        try:
            thumbnail_jpeg = self._document_draft_service.read_thumbnail(
                page_identifier, parse_page_rotation(rotation_degrees)
            )
        except DigitalizadoraError as error:
            return self._respond_to_error(error)
        if thumbnail_jpeg is None:
            return Response(status_code=HTTPStatus.NOT_FOUND)
        return Response(content=thumbnail_jpeg, media_type=JPEG_MEDIA_TYPE, headers=dict(THUMBNAIL_CACHE_HEADERS))

    def read_preview(self, page_identifier: str, rotation_degrees: int = 0) -> Response:
        try:
            preview_jpeg = self._document_draft_service.read_preview(
                page_identifier, parse_page_rotation(rotation_degrees)
            )
        except DigitalizadoraError as error:
            return self._respond_to_error(error)
        return Response(content=preview_jpeg, media_type=JPEG_MEDIA_TYPE, headers=dict(THUMBNAIL_CACHE_HEADERS))

    async def reorder_pages(self, body: PageOrderRequestBody) -> JSONResponse:
        return await self._respond_to_edit(self._document_draft_service.reorder(body.page_identifiers))

    async def rename_document(self, body: DocumentNameRequestBody) -> JSONResponse:
        return await self._respond_to_edit(self._document_draft_service.rename(body.name))

    async def finalize_document(self) -> JSONResponse:
        try:
            jpeg_quality = self._settings_service.current().adjustment.jpeg_quality
            finalization = await self._document_draft_service.finalize(jpeg_quality)
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

    async def _run_add_page(self, settings: ApplicationSettings) -> None:
        try:
            await self._document_draft_service.add_page(settings.scan_settings, settings.adjustment)
        except DigitalizadoraError as error:
            # The progress tracker already holds the code of a failed page. A refusal of the second check
            # (another accepted request went first) only reaches the log: no sheet is read twice (R17).
            logger.warning("Document page failed with code %s: %s", error.code, error)
        except Exception as error:
            # ScanService already logged the traceback and recorded unexpected_error.
            logger.error("Document page stopped by an unexpected failure: %s", error)

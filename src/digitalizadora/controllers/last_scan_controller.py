from collections.abc import Awaitable, Mapping
from http import HTTPStatus
from types import MappingProxyType
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from digitalizadora.controllers.crop_request_body import PageCropsRequestBody
from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog, build_error_body
from digitalizadora.controllers.last_scan_body import describe_last_scan
from digitalizadora.domain.errors import DigitalizadoraError, InvalidCropError
from digitalizadora.services.application_settings_service import ApplicationSettingsService
from digitalizadora.services.last_scan_edit_service import LastScanEditResult, LastScanEditService

LAST_SCAN_ERROR_STATUSES: Mapping[str, HTTPStatus] = MappingProxyType(
    {
        "no_last_scan": HTTPStatus.NOT_FOUND,
        "scan_already_running": HTTPStatus.CONFLICT,
        "last_scan_busy": HTTPStatus.CONFLICT,
        "last_scan_file_missing": HTTPStatus.CONFLICT,
        "saved_scan_unreadable": HTTPStatus.CONFLICT,
        "last_scan_not_editable": HTTPStatus.CONFLICT,
        "invalid_crop": HTTPStatus.UNPROCESSABLE_ENTITY,
        "insufficient_storage": HTTPStatus.INSUFFICIENT_STORAGE,
        "output_folder_unavailable": HTTPStatus.SERVICE_UNAVAILABLE,
        "image_adjustment_failed": HTTPStatus.INTERNAL_SERVER_ERROR,
    }
)


def describe_edit_result(result: LastScanEditResult) -> dict[str, Any]:
    return {
        "last_result": describe_last_scan(result.last_scan),
        "deleted_file_names": list(result.deleted_file_names),
        "kept_file_names": list(result.kept_file_names),
    }


class LastScanController:
    def __init__(
        self,
        last_scan_edit_service: LastScanEditService,
        settings_service: ApplicationSettingsService,
        error_message_catalog: ErrorMessageCatalog,
    ) -> None:
        self._last_scan_edit_service = last_scan_edit_service
        self._settings_service = settings_service
        self._error_message_catalog = error_message_catalog

    def build_router(self) -> APIRouter:
        router = APIRouter()
        router.add_api_route("/api/scans/last/rotation", self.rotate_last_scan, methods=["POST"])
        router.add_api_route("/api/scans/last/crops", self.set_last_scan_crops, methods=["PUT"])
        router.add_api_route("/api/scans/last/crops/detect", self.detect_last_scan_crops, methods=["POST"])
        return router

    async def rotate_last_scan(self) -> JSONResponse:
        return await self._respond_to_edit(self._last_scan_edit_service.rotate_clockwise(self._jpeg_quality()))

    async def set_last_scan_crops(self, body: PageCropsRequestBody) -> JSONResponse:
        try:
            crops = body.to_page_crops()
        except InvalidCropError as error:
            return self._respond_to_error(error)
        return await self._respond_to_edit(self._last_scan_edit_service.set_crops(crops, self._jpeg_quality()))

    async def detect_last_scan_crops(self) -> JSONResponse:
        try:
            result = await self._last_scan_edit_service.detect_crops(self._jpeg_quality())
        except DigitalizadoraError as error:
            return self._respond_to_error(error)
        content = {
            **describe_edit_result(result),
            "crops_detected": result.crops_detected,
            "ignored_region_count": result.ignored_region_count,
        }
        return JSONResponse(content=content)

    def _jpeg_quality(self) -> int:
        return self._settings_service.current().adjustment.jpeg_quality

    async def _respond_to_edit(self, edit: Awaitable[LastScanEditResult]) -> JSONResponse:
        try:
            result = await edit
        except DigitalizadoraError as error:
            return self._respond_to_error(error)
        return JSONResponse(content=describe_edit_result(result))

    def _respond_to_error(self, error: DigitalizadoraError) -> JSONResponse:
        return JSONResponse(
            status_code=LAST_SCAN_ERROR_STATUSES.get(error.code, HTTPStatus.INTERNAL_SERVER_ERROR),
            content=build_error_body(self._error_message_catalog, error.code),
        )

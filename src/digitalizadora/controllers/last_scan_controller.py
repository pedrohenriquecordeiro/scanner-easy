from collections.abc import Mapping
from http import HTTPStatus
from types import MappingProxyType

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog, build_error_body
from digitalizadora.controllers.scan_result_body import describe_scan_result
from digitalizadora.domain.errors import DigitalizadoraError
from digitalizadora.services.application_settings_service import ApplicationSettingsService
from digitalizadora.services.last_scan_rotation_service import LastScanRotationService

LAST_SCAN_ERROR_STATUSES: Mapping[str, HTTPStatus] = MappingProxyType(
    {
        "no_last_scan": HTTPStatus.NOT_FOUND,
        "scan_already_running": HTTPStatus.CONFLICT,
        "last_scan_file_missing": HTTPStatus.CONFLICT,
        "saved_scan_unreadable": HTTPStatus.CONFLICT,
        "insufficient_storage": HTTPStatus.INSUFFICIENT_STORAGE,
        "output_folder_unavailable": HTTPStatus.SERVICE_UNAVAILABLE,
    }
)


class LastScanController:
    def __init__(
        self,
        last_scan_rotation_service: LastScanRotationService,
        settings_service: ApplicationSettingsService,
        error_message_catalog: ErrorMessageCatalog,
    ) -> None:
        self._last_scan_rotation_service = last_scan_rotation_service
        self._settings_service = settings_service
        self._error_message_catalog = error_message_catalog

    def build_router(self) -> APIRouter:
        router = APIRouter()
        router.add_api_route("/api/scans/last/rotation", self.rotate_last_scan, methods=["POST"])
        return router

    async def rotate_last_scan(self) -> JSONResponse:
        try:
            jpeg_quality = self._settings_service.current().adjustment.jpeg_quality
            result = await self._last_scan_rotation_service.rotate_clockwise(jpeg_quality)
        except DigitalizadoraError as error:
            return JSONResponse(
                status_code=LAST_SCAN_ERROR_STATUSES.get(error.code, HTTPStatus.INTERNAL_SERVER_ERROR),
                content=build_error_body(self._error_message_catalog, error.code),
            )
        return JSONResponse(content={"last_result": describe_scan_result(result)})

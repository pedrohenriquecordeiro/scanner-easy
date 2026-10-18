from http import HTTPStatus

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog, build_error_body
from digitalizadora.controllers.settings_body import build_settings_body
from digitalizadora.domain.errors import DigitalizadoraError
from digitalizadora.services.application_settings_service import (
    ApplicationSettingsService,
    SettingsUpdate,
)


class SettingsRequestBody(BaseModel):
    output_folder: str
    output_format: str
    scan_preset: str


class SettingsController:
    def __init__(
        self,
        settings_service: ApplicationSettingsService,
        error_message_catalog: ErrorMessageCatalog,
    ) -> None:
        self._settings_service = settings_service
        self._error_message_catalog = error_message_catalog

    def build_router(self) -> APIRouter:
        router = APIRouter()
        router.add_api_route("/api/settings", self.read_settings, methods=["GET"])
        router.add_api_route("/api/settings", self.update_settings, methods=["PUT"])
        return router

    def read_settings(self) -> dict[str, str]:
        return build_settings_body(self._settings_service.current())

    def update_settings(self, body: SettingsRequestBody) -> JSONResponse:
        update = SettingsUpdate(
            output_folder=body.output_folder,
            output_format=body.output_format,
            scan_preset=body.scan_preset,
        )
        try:
            saved_settings = self._settings_service.update(update)
        except DigitalizadoraError as error:
            return JSONResponse(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                content=build_error_body(self._error_message_catalog, error.code),
            )
        return JSONResponse(content=build_settings_body(saved_settings))

from http import HTTPStatus

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, StrictBool, StrictInt

from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog, build_error_body
from digitalizadora.controllers.settings_body import SettingsBody, build_settings_body
from digitalizadora.domain.errors import DigitalizadoraError
from digitalizadora.services.application_settings_service import (
    ApplicationSettingsService,
    SettingsUpdate,
)


class SettingsRequestBody(BaseModel):
    output_folder: str
    output_format: str
    # Every field but the first two: missing or null keeps the saved value, so an older client keeps working.
    scan_preset: str | None = None
    capture_mode: str | None = None
    dots_per_inch: StrictInt | None = None
    color_mode: str | None = None
    rotation_degrees: StrictInt | None = None
    auto_crop: StrictBool | None = None


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

    def read_settings(self) -> SettingsBody:
        return build_settings_body(self._settings_service.current())

    def update_settings(self, body: SettingsRequestBody) -> JSONResponse:
        update = SettingsUpdate(
            output_folder=body.output_folder,
            output_format=body.output_format,
            scan_preset=body.scan_preset,
            capture_mode=body.capture_mode,
            dots_per_inch=body.dots_per_inch,
            color_mode=body.color_mode,
            rotation_degrees=body.rotation_degrees,
            auto_crop=body.auto_crop,
        )
        try:
            saved_settings = self._settings_service.update(update)
        except DigitalizadoraError as error:
            return JSONResponse(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                content=build_error_body(self._error_message_catalog, error.code),
            )
        return JSONResponse(content=build_settings_body(saved_settings))

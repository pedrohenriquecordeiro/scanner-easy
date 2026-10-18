from http import HTTPStatus
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from digitalizadora.controllers.error_message_catalog import ErrorMessageCatalog, build_error_body
from digitalizadora.domain.errors import InvalidSettingsError
from digitalizadora.services.printer_connection_service import (
    PrinterConnectionService,
    PrinterConnectionState,
)

MANUAL_ADDRESS_REQUIRED_PREFIX = "http://"


class PrinterAddressRequestBody(BaseModel):
    base_address: str


class PrinterController:
    def __init__(
        self,
        printer_connection_service: PrinterConnectionService,
        error_message_catalog: ErrorMessageCatalog,
    ) -> None:
        self._printer_connection_service = printer_connection_service
        self._error_message_catalog = error_message_catalog

    def build_router(self) -> APIRouter:
        router = APIRouter()
        router.add_api_route("/api/printer", self.read_printer, methods=["GET"])
        router.add_api_route("/api/printer/refresh", self.refresh_printer, methods=["POST"])
        router.add_api_route("/api/printer/address", self.update_printer_address, methods=["PUT"])
        return router

    async def read_printer(self) -> dict[str, Any]:
        return self._describe(await self._printer_connection_service.check_connection())

    async def refresh_printer(self) -> dict[str, Any]:
        return self._describe(await self._printer_connection_service.refresh())

    async def update_printer_address(self, body: PrinterAddressRequestBody) -> JSONResponse:
        base_address = body.base_address.strip()
        if not base_address.startswith(MANUAL_ADDRESS_REQUIRED_PREFIX):
            return JSONResponse(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                content=build_error_body(self._error_message_catalog, InvalidSettingsError.code),
            )
        self._printer_connection_service.use_manual_address(base_address)
        connection_state = await self._printer_connection_service.check_connection()
        return JSONResponse(content=self._describe(connection_state))

    def _describe(self, connection_state: PrinterConnectionState) -> dict[str, Any]:
        scanner_state = connection_state.scanner_state
        route = connection_state.route
        error_code = connection_state.error_code
        return {
            "connected": connection_state.connected,
            "display_name": connection_state.display_name,
            "scanner_state": None if scanner_state is None else scanner_state.value,
            "route": None if route is None else route.value,
            "error": (
                None
                if error_code is None
                else build_error_body(self._error_message_catalog, error_code)
            ),
        }

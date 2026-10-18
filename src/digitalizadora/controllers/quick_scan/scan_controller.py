import logging
from http import HTTPStatus

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse

from digitalizadora.controllers.shared.error_message_catalog import ErrorMessageCatalog, build_error_body
from digitalizadora.domain.errors import DigitalizadoraError
from digitalizadora.domain.scanning.scan_request import ScanRequest
from digitalizadora.services.application.application_settings_service import ApplicationSettingsService
from digitalizadora.services.scanner.scan_service import ScanService

logger = logging.getLogger(__name__)


class ScanController:
    def __init__(
        self,
        scan_service: ScanService,
        settings_service: ApplicationSettingsService,
        error_message_catalog: ErrorMessageCatalog,
    ) -> None:
        self._scan_service = scan_service
        self._settings_service = settings_service
        self._error_message_catalog = error_message_catalog

    def build_router(self) -> APIRouter:
        router = APIRouter()
        router.add_api_route("/api/scans", self.start_scan, methods=["POST"])
        return router

    async def start_scan(self, background_tasks: BackgroundTasks) -> JSONResponse:
        try:
            self._scan_service.ensure_scan_can_start()
        except DigitalizadoraError as error:
            return JSONResponse(
                status_code=HTTPStatus.CONFLICT,
                content=build_error_body(self._error_message_catalog, error.code),
            )
        scan_request = self._settings_service.current().to_scan_request()
        background_tasks.add_task(self._run_scan, scan_request)
        return JSONResponse(status_code=HTTPStatus.ACCEPTED, content={"accepted": True})

    async def _run_scan(self, scan_request: ScanRequest) -> None:
        try:
            await self._scan_service.scan_one_file(scan_request)
        except DigitalizadoraError as error:
            # The progress tracker already holds the error code that the page will show.
            logger.warning("Scan failed with code %s: %s", error.code, error)
        except Exception as error:
            # ScanService already logged the traceback and recorded unexpected_error.
            logger.error("Scan stopped by an unexpected failure: %s", error)

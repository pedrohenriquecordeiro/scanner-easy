import logging
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from digitalizadora.controllers.document_controller import DocumentController
from digitalizadora.controllers.error_message_catalog import (
    UNEXPECTED_ERROR_CODE,
    ErrorMessageCatalog,
    build_error_body,
)
from digitalizadora.controllers.last_scan_controller import LastScanController
from digitalizadora.controllers.local_request_guard import LocalRequestGuard
from digitalizadora.controllers.preview_controller import PreviewController
from digitalizadora.controllers.printer_controller import PrinterController
from digitalizadora.controllers.revalidated_static_files import REVALIDATE_ALWAYS_HEADERS, RevalidatedStaticFiles
from digitalizadora.controllers.scan_controller import ScanController
from digitalizadora.controllers.settings_controller import SettingsController
from digitalizadora.controllers.state_controller import StateController
from digitalizadora.domain.errors import (
    InvalidCropError,
    InvalidDocumentNameError,
    InvalidPageOrderError,
    InvalidPageRotationError,
    InvalidScanIdentifierError,
    InvalidSettingsError,
)

INDEX_FILE_NAME = "index.html"
STATIC_ROUTE = "/static"
# R11: a malformed body or query on these routes answers the code of the route; any other path keeps invalid_settings.
VALIDATION_ERROR_CODE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"/api/document/page-order"), InvalidPageOrderError.code),
    (re.compile(r"/api/document/name"), InvalidDocumentNameError.code),
    (re.compile(r"/api/document/pages/[^/]+/crops(/detect)?"), InvalidCropError.code),
    (re.compile(r"/api/document/pages/[^/]+/(thumbnail|preview)"), InvalidPageRotationError.code),
    (re.compile(r"/api/scans/last/crops"), InvalidCropError.code),
    (re.compile(r"/api/scans/last/preview"), InvalidPageRotationError.code),
)

# A query field that is missing or malformed on one of these routes has a code of its own, before the code of the route.
VALIDATION_ERROR_CODE_OF_FIELDS: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"/api/scans/last/preview"), "scan_identifier", InvalidScanIdentifierError.code),
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ApplicationControllers:
    scan: ScanController
    state: StateController
    settings: SettingsController
    printer: PrinterController
    preview: PreviewController
    document: DocumentController
    last_scan: LastScanController


@dataclass(frozen=True)
class WebInterfaceConfiguration:
    allowed_hosts: frozenset[str]
    static_directory: Path
    error_message_catalog: ErrorMessageCatalog
    shutdown_callbacks: tuple[Callable[[], Awaitable[None]], ...] = ()


def find_validation_error_code(request_path: str, invalid_field_names: frozenset[str] = frozenset()) -> str:
    for path_pattern, field_name, error_code in VALIDATION_ERROR_CODE_OF_FIELDS:
        if path_pattern.fullmatch(request_path) and field_name in invalid_field_names:
            return error_code
    for path_pattern, error_code in VALIDATION_ERROR_CODE_PATTERNS:
        if path_pattern.fullmatch(request_path):
            return error_code
    return InvalidSettingsError.code


class ErrorResponses:
    """Exception handlers that keep every error answer in the {"code", "message"} shape."""

    def __init__(self, error_message_catalog: ErrorMessageCatalog) -> None:
        self._error_message_catalog = error_message_catalog

    def register(self, application: FastAPI) -> None:
        application.add_exception_handler(RequestValidationError, self.respond_to_invalid_body)
        application.add_exception_handler(StarletteHTTPException, self.respond_to_http_error)
        application.add_exception_handler(Exception, self.respond_to_unexpected_error)

    async def respond_to_invalid_body(
        self, request: Request, error: RequestValidationError
    ) -> JSONResponse:
        invalid_field_names = frozenset(str(detail["loc"][-1]) for detail in error.errors())
        error_code = find_validation_error_code(request.url.path, invalid_field_names)
        return JSONResponse(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content=build_error_body(self._error_message_catalog, error_code),
        )

    async def respond_to_http_error(
        self, request: Request, error: StarletteHTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content=build_error_body(self._error_message_catalog, UNEXPECTED_ERROR_CODE),
            headers=error.headers,
        )

    async def respond_to_unexpected_error(self, request: Request, error: Exception) -> JSONResponse:
        # The uvicorn loggers do not propagate to the log file, so the traceback is logged here.
        logger.error(
            "Unexpected failure while answering %s %s",
            request.method,
            request.url.path,
            exc_info=error,
        )
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content=build_error_body(self._error_message_catalog, UNEXPECTED_ERROR_CODE),
        )


def create_application(
    controllers: ApplicationControllers, web_configuration: WebInterfaceConfiguration
) -> FastAPI:
    @asynccontextmanager
    async def run_lifespan(application: FastAPI) -> AsyncIterator[None]:
        yield
        for shutdown_callback in web_configuration.shutdown_callbacks:
            await shutdown_callback()

    application = FastAPI(
        title="Digitalizadora",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=run_lifespan,
    )
    ErrorResponses(web_configuration.error_message_catalog).register(application)
    for controller in (
        controllers.scan,
        controllers.state,
        controllers.settings,
        controllers.printer,
        controllers.preview,
        controllers.document,
        controllers.last_scan,
    ):
        application.include_router(controller.build_router())

    index_file = web_configuration.static_directory / INDEX_FILE_NAME

    async def serve_index() -> FileResponse:
        return FileResponse(index_file, headers=REVALIDATE_ALWAYS_HEADERS)

    application.add_api_route("/", serve_index, methods=["GET"], include_in_schema=False)
    application.mount(
        STATIC_ROUTE, RevalidatedStaticFiles(directory=web_configuration.static_directory), name="static"
    )
    application.add_middleware(LocalRequestGuard, allowed_hosts=web_configuration.allowed_hosts)
    return application

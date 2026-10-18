from http import HTTPStatus
from types import MappingProxyType

from fastapi import APIRouter, Response

from digitalizadora.controllers.documents.document_controller import parse_page_rotation
from digitalizadora.controllers.quick_scan.last_scan_controller import respond_to_last_scan_error
from digitalizadora.controllers.shared.error_message_catalog import ErrorMessageCatalog
from digitalizadora.domain.errors import DigitalizadoraError
from digitalizadora.services.quick_scan.last_scan_view_service import LastScanViewService

JPEG_MEDIA_TYPE = "image/jpeg"
NO_STORE_HEADERS = {"Cache-Control": "no-store"}
# The address of the enlarged view holds the identifier of the scan and the rotation, so it never changes.
IMMUTABLE_HEADERS = MappingProxyType({"Cache-Control": "private, max-age=31536000, immutable"})


class PreviewController:
    def __init__(
        self, last_scan_view_service: LastScanViewService, error_message_catalog: ErrorMessageCatalog
    ) -> None:
        self._last_scan_view_service = last_scan_view_service
        self._error_message_catalog = error_message_catalog

    def build_router(self) -> APIRouter:
        router = APIRouter()
        router.add_api_route("/api/scans/last/thumbnail", self.read_last_thumbnail, methods=["GET"])
        router.add_api_route("/api/scans/last/preview", self.read_last_preview, methods=["GET"])
        return router

    def read_last_thumbnail(self) -> Response:
        thumbnail_jpeg = self._last_scan_view_service.read_thumbnail()
        if thumbnail_jpeg is None:
            return Response(status_code=HTTPStatus.NOT_FOUND, headers=NO_STORE_HEADERS)
        return Response(content=thumbnail_jpeg, media_type=JPEG_MEDIA_TYPE, headers=NO_STORE_HEADERS)

    def read_last_preview(self, scan_identifier: str, rotation_degrees: int = 0) -> Response:
        try:
            preview_jpeg = self._last_scan_view_service.read_preview(
                scan_identifier, parse_page_rotation(rotation_degrees)
            )
        except DigitalizadoraError as error:
            return respond_to_last_scan_error(error, self._error_message_catalog)
        return Response(content=preview_jpeg, media_type=JPEG_MEDIA_TYPE, headers=dict(IMMUTABLE_HEADERS))


from http import HTTPStatus

from fastapi import APIRouter, Response

from digitalizadora.services.scan_progress_tracker import ScanProgressTracker

JPEG_MEDIA_TYPE = "image/jpeg"
NO_STORE_HEADERS = {"Cache-Control": "no-store"}


class PreviewController:
    def __init__(self, progress_tracker: ScanProgressTracker) -> None:
        self._progress_tracker = progress_tracker

    def build_router(self) -> APIRouter:
        router = APIRouter()
        router.add_api_route("/api/scans/last/thumbnail", self.read_last_thumbnail, methods=["GET"])
        return router

    async def read_last_thumbnail(self) -> Response:
        thumbnail_jpeg = self._progress_tracker.last_thumbnail_jpeg()
        if thumbnail_jpeg is None:
            return Response(status_code=HTTPStatus.NOT_FOUND, headers=NO_STORE_HEADERS)
        return Response(
            content=thumbnail_jpeg, media_type=JPEG_MEDIA_TYPE, headers=NO_STORE_HEADERS
        )

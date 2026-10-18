import os
from collections.abc import MutableMapping
from typing import Any

from starlette.responses import Response
from starlette.staticfiles import StaticFiles

REVALIDATE_ALWAYS_HEADERS = {"Cache-Control": "no-cache"}


class RevalidatedStaticFiles(StaticFiles):
    """Static files the browser asks about every time (the ETag makes the answer a cheap 304).

    Without a Cache-Control the browser keeps an old script or style for days after an update and pairs it with the
    new page."""

    def file_response(
        self,
        full_path: str | os.PathLike[str],
        stat_result: os.stat_result,
        scope: MutableMapping[str, Any],
        status_code: int = 200,
    ) -> Response:
        response = super().file_response(full_path, stat_result, scope, status_code)
        response.headers.update(REVALIDATE_ALWAYS_HEADERS)
        return response

from http import HTTPStatus

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from digitalizadora.controllers.error_message_catalog import (
    ERROR_MESSAGES,
    FORBIDDEN_HOST_CODE,
    MISSING_REQUEST_HEADER_CODE,
)

REQUIRED_HEADER_NAME = "x-requested-with"
REQUIRED_HEADER_VALUE = "digitalizadora"
STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
WEBSOCKET_POLICY_VIOLATION_CLOSE_CODE = 1008


class LocalRequestGuard:
    def __init__(self, app: ASGIApp, allowed_hosts: frozenset[str]) -> None:
        self._app = app
        self._allowed_hosts = frozenset(host.lower() for host in allowed_hosts)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        rejection_code = self._find_rejection_code(scope)
        if rejection_code is None:
            await self._app(scope, receive, send)
        elif scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": WEBSOCKET_POLICY_VIOLATION_CLOSE_CODE})
        else:
            response = JSONResponse(
                status_code=HTTPStatus.FORBIDDEN,
                content={"code": rejection_code, "message": ERROR_MESSAGES[rejection_code]},
            )
            await response(scope, receive, send)

    def _find_rejection_code(self, scope: Scope) -> str | None:
        if scope["type"] == "lifespan":
            return None
        headers = dict(scope["headers"])
        host = headers.get(b"host", b"").decode("latin-1").lower()
        if host not in self._allowed_hosts:
            return FORBIDDEN_HOST_CODE
        if scope["type"] == "http" and scope["method"] in STATE_CHANGING_METHODS:
            header_value = headers.get(REQUIRED_HEADER_NAME.encode("latin-1"), b"")
            if header_value.decode("latin-1") != REQUIRED_HEADER_VALUE:
                return MISSING_REQUEST_HEADER_CODE
        return None

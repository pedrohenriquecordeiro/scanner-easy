from http import HTTPStatus

import httpx
import pytest
from starlette.types import Receive, Scope, Send

from digitalizadora.controllers.error_message_catalog import ERROR_MESSAGES
from digitalizadora.controllers.local_request_guard import (
    REQUIRED_HEADER_NAME,
    REQUIRED_HEADER_VALUE,
    LocalRequestGuard,
)

ALLOWED_HOSTS = frozenset({"127.0.0.1:8765", "localhost:8765"})
INNER_BODY = b"inner application reached"
FORBIDDEN_HOST_BODY = {"code": "forbidden_host", "message": ERROR_MESSAGES["forbidden_host"]}
MISSING_HEADER_BODY = {
    "code": "missing_request_header",
    "message": ERROR_MESSAGES["missing_request_header"],
}


class RecordingApplication:
    def __init__(self) -> None:
        self.scope_types: list[str] = []

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.scope_types.append(scope["type"])
        if scope["type"] != "http":
            return
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": INNER_BODY})


class RecordingSend:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    async def __call__(self, message: dict[str, object]) -> None:
        self.messages.append(message)


async def no_message() -> dict[str, object]:
    return {}


@pytest.fixture
def inner_application() -> RecordingApplication:
    return RecordingApplication()


@pytest.fixture
def guard(inner_application: RecordingApplication) -> LocalRequestGuard:
    return LocalRequestGuard(inner_application, ALLOWED_HOSTS)


async def send_request(
    guard: LocalRequestGuard, method: str, headers: dict[str, str]
) -> httpx.Response:
    transport = httpx.ASGITransport(app=guard)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8765") as client:
        return await client.request(method, "/anything", headers=headers)


async def test_allowed_host_reaches_the_application(guard: LocalRequestGuard) -> None:
    response = await send_request(guard, "GET", {"host": "127.0.0.1:8765"})

    assert (response.status_code, response.content) == (HTTPStatus.OK, INNER_BODY)


async def test_localhost_with_the_right_port_is_allowed(guard: LocalRequestGuard) -> None:
    response = await send_request(guard, "GET", {"host": "localhost:8765"})

    assert response.status_code == HTTPStatus.OK


async def test_upper_case_host_matching_ignoring_case_is_allowed(guard: LocalRequestGuard) -> None:
    response = await send_request(guard, "GET", {"host": "LOCALHOST:8765"})

    assert response.status_code == HTTPStatus.OK


async def test_foreign_host_is_rejected_with_forbidden_host(guard: LocalRequestGuard) -> None:
    response = await send_request(guard, "GET", {"host": "evil.example"})

    assert (response.status_code, response.json()) == (HTTPStatus.FORBIDDEN, FORBIDDEN_HOST_BODY)


async def test_foreign_host_never_reaches_the_application(
    guard: LocalRequestGuard, inner_application: RecordingApplication
) -> None:
    await send_request(guard, "GET", {"host": "evil.example"})

    assert inner_application.scope_types == []


async def test_same_host_with_another_port_is_rejected(guard: LocalRequestGuard) -> None:
    response = await send_request(guard, "GET", {"host": "127.0.0.1:9999"})

    assert (response.status_code, response.json()) == (HTTPStatus.FORBIDDEN, FORBIDDEN_HOST_BODY)


async def test_host_without_port_is_rejected(guard: LocalRequestGuard) -> None:
    response = await send_request(guard, "GET", {"host": "127.0.0.1"})

    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
async def test_state_changing_method_without_the_header_is_rejected(
    guard: LocalRequestGuard, method: str
) -> None:
    response = await send_request(guard, method, {"host": "127.0.0.1:8765"})

    assert (response.status_code, response.json()) == (HTTPStatus.FORBIDDEN, MISSING_HEADER_BODY)


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
async def test_state_changing_method_with_the_header_passes(
    guard: LocalRequestGuard, method: str
) -> None:
    headers = {"host": "127.0.0.1:8765", REQUIRED_HEADER_NAME: REQUIRED_HEADER_VALUE}

    response = await send_request(guard, method, headers)

    assert response.status_code == HTTPStatus.OK


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
async def test_safe_method_without_the_header_passes(
    guard: LocalRequestGuard, method: str
) -> None:
    response = await send_request(guard, method, {"host": "127.0.0.1:8765"})

    assert response.status_code == HTTPStatus.OK


async def test_wrong_header_value_is_rejected(guard: LocalRequestGuard) -> None:
    headers = {"host": "127.0.0.1:8765", REQUIRED_HEADER_NAME: "something-else"}

    response = await send_request(guard, "POST", headers)

    assert (response.status_code, response.json()) == (HTTPStatus.FORBIDDEN, MISSING_HEADER_BODY)


async def test_the_host_check_runs_before_the_header_check(guard: LocalRequestGuard) -> None:
    response = await send_request(guard, "POST", {"host": "evil.example"})

    assert response.json() == FORBIDDEN_HOST_BODY


async def test_websocket_with_a_foreign_host_is_closed(guard: LocalRequestGuard) -> None:
    recorded_send = RecordingSend()
    scope = {"type": "websocket", "headers": [(b"host", b"evil.example")]}

    await guard(scope, no_message, recorded_send)

    assert [message["type"] for message in recorded_send.messages] == ["websocket.close"]


async def test_websocket_with_a_foreign_host_never_reaches_the_application(
    guard: LocalRequestGuard, inner_application: RecordingApplication
) -> None:
    scope = {"type": "websocket", "headers": [(b"host", b"evil.example")]}

    await guard(scope, no_message, RecordingSend())

    assert inner_application.scope_types == []


async def test_websocket_with_an_allowed_host_reaches_the_application(
    guard: LocalRequestGuard, inner_application: RecordingApplication
) -> None:
    scope = {"type": "websocket", "headers": [(b"host", b"127.0.0.1:8765")]}

    await guard(scope, no_message, RecordingSend())

    assert inner_application.scope_types == ["websocket"]


async def test_lifespan_scope_passes_through_without_headers(
    guard: LocalRequestGuard, inner_application: RecordingApplication
) -> None:
    await guard({"type": "lifespan"}, no_message, RecordingSend())

    assert inner_application.scope_types == ["lifespan"]

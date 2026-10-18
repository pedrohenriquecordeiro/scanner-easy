import asyncio
import errno
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from http import HTTPStatus

import httpx
import pytest

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import (
    LocalNetworkBlockedError,
    ScanFailedError,
    ScannerBusyError,
    ScannerUnreachableError,
    ScanRejectedError,
    ScanTimedOutError,
)
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanner_status import ScannerState
from digitalizadora.infrastructure.escl.escl_protocol import (
    build_scan_settings_xml,
    parse_scanner_capabilities,
)
from digitalizadora.infrastructure.escl.escl_scanner_gateway import (
    EsclGatewayTiming,
    EsclScannerGateway,
)
from digitalizadora.simulator.fake_escl_scanner_app import (
    SUPPORTED_COLOR_MODES,
    FakeScannerBehavior,
    build_capabilities_document,
    build_status_document,
    create_fake_escl_scanner_app,
)
from tests.fakes.recording_sleep import RecordingSleep
from tests.fakes.sample_images import build_sample_jpeg

SCANNER_HOST = "scanner.test"
BASE_ADDRESS = f"http://{SCANNER_HOST}/eSCL"
JOB_SEGMENT_PATTERN = re.compile(r"(?<=/ScanJobs/)[^/]+")
JOB_PLACEHOLDER = "<job>"
CAPABILITIES_ROUTE = "GET /eSCL/ScannerCapabilities"
POST_ROUTE = "POST /eSCL/ScanJobs"
DOCUMENT_ROUTE = f"GET /eSCL/ScanJobs/{JOB_PLACEHOLDER}/NextDocument"
DELETE_ROUTE = f"DELETE /eSCL/ScanJobs/{JOB_PLACEHOLDER}"
SCAN_SETTINGS = ScanSettings(dots_per_inch=75, color_mode=ColorMode.COLOR)
TEST_BUSY_WAIT_SECONDS = 6.0
TEST_SCAN_TIMEOUT_SECONDS = 6.0
STATUS_ROUTE = "GET /eSCL/ScannerStatus"
JOB_PATH = "/eSCL/ScanJobs/11111111-2222-3333-4444-000000000001"
JOB_LOCATION = f"http://{SCANNER_HOST}{JOB_PATH}"
LOOPBACK_BASE_ADDRESS = "http://127.0.0.1:9/eSCL"
ANYIO_CONNECT_FAILURE = "All connection attempts failed"
READINESS_INTERVAL_SECONDS = 2.0
POLL_INTERVAL_SECONDS = 1.5
EXPECTED_CONNECT_TIMEOUT_SECONDS = 5.0
EXPECTED_READ_TIMEOUT_SECONDS = 30.0
MINIMUM_NEXT_DOCUMENT_READ_TIMEOUT_SECONDS = 180.0
PRODUCTION_SCAN_TIMEOUT_SECONDS = 300.0


def describe_route(request: httpx.Request) -> str:
    return f"{request.method} {JOB_SEGMENT_PATTERN.sub(JOB_PLACEHOLDER, request.url.path)}"


@dataclass(frozen=True)
class Reply:
    status_code: int
    content: bytes = b""
    headers: Mapping[str, str] = field(default_factory=dict)

    def to_response(self) -> httpx.Response:
        return httpx.Response(self.status_code, content=self.content, headers=dict(self.headers))


class ScriptedResponses:
    def __init__(self, scripts: Mapping[str, Sequence[Reply | Exception]]) -> None:
        self._pending = {route: list(replies) for route, replies in scripts.items()}

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        replies = self._pending[describe_route(request)]
        reply = replies.pop(0) if len(replies) > 1 else replies[0]
        if isinstance(reply, Exception):
            raise reply
        return reply.to_response()


class RecordingTransport(httpx.AsyncBaseTransport):
    def __init__(self, inner_transport: httpx.AsyncBaseTransport) -> None:
        self._inner_transport = inner_transport
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return await self._inner_transport.handle_async_request(request)

    def count(self, route: str) -> int:
        return sum(1 for request in self.requests if describe_route(request) == route)

    def find(self, route: str) -> httpx.Request:
        return next(request for request in self.requests if describe_route(request) == route)


class SleepDrivenClock:
    def __init__(self, recording_sleep: RecordingSleep) -> None:
        self._recording_sleep = recording_sleep

    def __call__(self) -> float:
        return sum(self._recording_sleep.delays)


@dataclass(frozen=True)
class GatewayHarness:
    gateway: EsclScannerGateway
    transport: RecordingTransport
    sleep: RecordingSleep


def build_harness(
    inner_transport: httpx.AsyncBaseTransport,
    busy_wait_seconds: float = TEST_BUSY_WAIT_SECONDS,
    scan_timeout_seconds: float = TEST_SCAN_TIMEOUT_SECONDS,
) -> GatewayHarness:
    sleep = RecordingSleep()
    transport = RecordingTransport(inner_transport)
    timing = EsclGatewayTiming(
        sleep=sleep,
        monotonic_clock=SleepDrivenClock(sleep),
        busy_wait_seconds=busy_wait_seconds,
        scan_timeout_seconds=scan_timeout_seconds,
    )
    http_client = httpx.AsyncClient(transport=transport, follow_redirects=True)
    return GatewayHarness(EsclScannerGateway(http_client, BASE_ADDRESS, timing), transport, sleep)


def fake_scanner_harness(behavior: FakeScannerBehavior | None = None) -> GatewayHarness:
    scanner_application = create_fake_escl_scanner_app(behavior or FakeScannerBehavior())
    return build_harness(httpx.ASGITransport(app=scanner_application))


def failing_document_harness(status_code: int) -> GatewayHarness:
    return fake_scanner_harness(FakeScannerBehavior(document_status_code=status_code))


def healthy_scripts() -> dict[str, list[Reply | Exception]]:
    return {
        CAPABILITIES_ROUTE: [Reply(HTTPStatus.OK, build_capabilities_document(SUPPORTED_COLOR_MODES))],
        STATUS_ROUTE: [Reply(HTTPStatus.OK, build_status_document("Idle"))],
        POST_ROUTE: [Reply(HTTPStatus.CREATED, headers={"Location": JOB_LOCATION})],
        DOCUMENT_ROUTE: [Reply(HTTPStatus.OK, build_sample_jpeg(), {"Content-Type": "image/jpeg"})],
        DELETE_ROUTE: [Reply(HTTPStatus.OK)],
    }


def scripted_harness(overrides: Mapping[str, Sequence[Reply | Exception]] | None = None) -> GatewayHarness:
    scripts = {**healthy_scripts(), **(overrides or {})}
    return build_harness(httpx.MockTransport(ScriptedResponses(scripts)))


class TransportLayerConnectError(Exception):
    """Stands in for httpcore.ConnectError, the layer between httpx.ConnectError and the socket error."""


def raise_through_the_http_layers(underlying_error: Exception) -> None:
    """Raise the way httpx 0.28 over httpcore 1.0 and anyio 4 does: httpcore keeps the error only as __context__."""
    try:
        try:
            raise OSError(ANYIO_CONNECT_FAILURE) from underlying_error
        except OSError:
            raise TransportLayerConnectError(ANYIO_CONNECT_FAILURE) from None
    except TransportLayerConnectError as transport_failure:
        raise httpx.ConnectError(ANYIO_CONNECT_FAILURE) from transport_failure


def connect_error_chained_like_httpx(underlying_error: Exception) -> httpx.ConnectError:
    with pytest.raises(httpx.ConnectError) as raised:
        raise_through_the_http_layers(underlying_error)
    return raised.value


async def refuse_with_no_route_to_host(socket_to_connect: object, address: object) -> None:
    raise OSError(errno.EHOSTUNREACH, "No route to host")


def warning_messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING]


class NeverAnsweringDocumentResponses:
    """Scripted healthy scanner whose NextDocument never answers, like a scan interrupted by a shutdown."""

    def __init__(self) -> None:
        self._scripted_responses = ScriptedResponses(healthy_scripts())
        self.document_requested = asyncio.Event()

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        if describe_route(request) == DOCUMENT_ROUTE:
            self.document_requested.set()
            await asyncio.Event().wait()
        return await self._scripted_responses(request)


async def test_scan_page_returns_a_jpeg_image() -> None:
    harness = fake_scanner_harness()
    scanned_image = await harness.gateway.scan_page(SCAN_SETTINGS)
    assert (scanned_image.media_type, scanned_image.content[:2]) == ("image/jpeg", b"\xff\xd8")


async def test_page_answered_on_the_first_request_needs_no_sleep() -> None:
    harness = fake_scanner_harness()
    await harness.gateway.scan_page(SCAN_SETTINGS)
    assert (harness.transport.count(DOCUMENT_ROUTE), harness.sleep.delays) == (1, [])


async def test_scan_page_sends_exactly_one_delete_after_a_success() -> None:
    harness = fake_scanner_harness()
    await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.transport.count(DELETE_ROUTE) == 1


async def test_post_body_is_the_scan_settings_document() -> None:
    harness = fake_scanner_harness()
    await harness.gateway.scan_page(SCAN_SETTINGS)
    capabilities = parse_scanner_capabilities(build_capabilities_document(SUPPORTED_COLOR_MODES))
    assert harness.transport.find(POST_ROUTE).content == build_scan_settings_xml(SCAN_SETTINGS, capabilities)


async def test_post_declares_a_text_xml_body() -> None:
    harness = fake_scanner_harness()
    await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.transport.find(POST_ROUTE).headers["Content-Type"] == "text/xml"


async def test_read_capabilities_is_cached_per_gateway() -> None:
    harness = fake_scanner_harness()
    first = await harness.gateway.read_capabilities()
    second = await harness.gateway.read_capabilities()
    assert (first, harness.transport.count(CAPABILITIES_ROUTE)) == (second, 1)


async def test_scan_page_reuses_the_cached_capabilities() -> None:
    harness = fake_scanner_harness()
    await harness.gateway.read_capabilities()
    await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.transport.count(CAPABILITIES_ROUTE) == 1


async def test_read_status_parses_the_scanner_status() -> None:
    harness = fake_scanner_harness()
    status = await harness.gateway.read_status()
    assert status.state is ScannerState.IDLE


async def test_status_answer_other_than_200_means_unreachable() -> None:
    harness = scripted_harness({STATUS_ROUTE: [Reply(HTTPStatus.SERVICE_UNAVAILABLE)]})
    with pytest.raises(ScannerUnreachableError):
        await harness.gateway.read_status()


async def test_capabilities_answer_other_than_200_means_unreachable() -> None:
    harness = scripted_harness({CAPABILITIES_ROUTE: [Reply(HTTPStatus.INTERNAL_SERVER_ERROR)]})
    with pytest.raises(ScannerUnreachableError):
        await harness.gateway.read_capabilities()


async def test_connection_refused_means_unreachable() -> None:
    harness = scripted_harness({STATUS_ROUTE: [httpx.ConnectError("connection refused")]})
    with pytest.raises(ScannerUnreachableError) as raised:
        await harness.gateway.read_status()
    assert raised.value.code == "scanner_unreachable"


async def test_connect_timeout_means_unreachable() -> None:
    harness = scripted_harness({STATUS_ROUTE: [httpx.ConnectTimeout("no answer")]})
    with pytest.raises(ScannerUnreachableError) as raised:
        await harness.gateway.read_status()
    assert raised.value.code == "scanner_unreachable"


async def test_host_unreachable_from_the_real_http_stack_means_local_network_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(asyncio.get_running_loop(), "sock_connect", refuse_with_no_route_to_host)
    async with httpx.AsyncClient(trust_env=False) as http_client:
        gateway = EsclScannerGateway(http_client, LOOPBACK_BASE_ADDRESS, EsclGatewayTiming(sleep=RecordingSleep()))
        with pytest.raises(LocalNetworkBlockedError):
            await gateway.read_status()


async def test_host_unreachable_linked_only_by_context_means_local_network_blocked() -> None:
    blocked = connect_error_chained_like_httpx(OSError(errno.EHOSTUNREACH, "No route to host"))
    harness = scripted_harness({STATUS_ROUTE: [blocked]})
    with pytest.raises(LocalNetworkBlockedError):
        await harness.gateway.read_status()


async def test_host_unreachable_inside_an_exception_group_means_local_network_blocked() -> None:
    attempts = ExceptionGroup(
        "connection attempts",
        [OSError(errno.ECONNREFUSED, "Connection refused"), OSError(errno.EHOSTUNREACH, "No route to host")],
    )
    harness = scripted_harness({STATUS_ROUTE: [connect_error_chained_like_httpx(attempts)]})
    with pytest.raises(LocalNetworkBlockedError):
        await harness.gateway.read_status()


async def test_other_operating_system_errors_stay_plain_unreachable() -> None:
    refused = connect_error_chained_like_httpx(OSError(errno.ECONNREFUSED, "Connection refused"))
    harness = scripted_harness({STATUS_ROUTE: [refused]})
    with pytest.raises(ScannerUnreachableError) as raised:
        await harness.gateway.read_status()
    assert raised.value.code == "scanner_unreachable"


async def test_a_cycle_in_the_exception_links_ends_the_search() -> None:
    refused = OSError(errno.ECONNREFUSED, "Connection refused")
    connect_error = httpx.ConnectError("connection refused")
    connect_error.__cause__ = refused
    refused.__context__ = connect_error
    harness = scripted_harness({STATUS_ROUTE: [connect_error]})
    with pytest.raises(ScannerUnreachableError) as raised:
        await harness.gateway.read_status()
    assert raised.value.code == "scanner_unreachable"


async def test_every_request_asks_the_scanner_to_close_the_connection() -> None:
    harness = fake_scanner_harness()
    await harness.gateway.scan_page(SCAN_SETTINGS)
    assert {request.headers["Connection"] for request in harness.transport.requests} == {"close"}


async def test_redirects_are_not_followed_even_when_the_client_would_follow_them() -> None:
    redirect = Reply(HTTPStatus.FOUND, headers={"Location": "http://203.0.113.9/elsewhere"})
    harness = scripted_harness({STATUS_ROUTE: [redirect]})
    with pytest.raises(ScannerUnreachableError):
        await harness.gateway.read_status()
    assert [request.url.host for request in harness.transport.requests] == [SCANNER_HOST]


async def test_scanner_that_is_busy_and_then_idle_is_waited_for() -> None:
    busy_then_idle = [
        Reply(HTTPStatus.OK, build_status_document("Processing")),
        Reply(HTTPStatus.OK, build_status_document("Idle")),
    ]
    harness = scripted_harness({STATUS_ROUTE: busy_then_idle})
    await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.sleep.delays == [READINESS_INTERVAL_SECONDS]


async def test_scanner_busy_past_the_waiting_limit_raises_scanner_busy() -> None:
    harness = fake_scanner_harness(FakeScannerBehavior(initial_state="Processing"))
    with pytest.raises(ScannerBusyError):
        await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.sleep.delays == [READINESS_INTERVAL_SECONDS] * 3


async def test_scanner_that_becomes_idle_exactly_at_the_limit_is_still_used() -> None:
    busy = Reply(HTTPStatus.OK, build_status_document("Processing"))
    idle = Reply(HTTPStatus.OK, build_status_document("Idle"))
    harness = scripted_harness({STATUS_ROUTE: [busy, busy, busy, idle]})
    scanned_image = await harness.gateway.scan_page(SCAN_SETTINGS)
    assert (scanned_image.media_type, harness.sleep.delays) == ("image/jpeg", [READINESS_INTERVAL_SECONDS] * 3)


async def test_busy_scanner_receives_no_scan_job() -> None:
    harness = fake_scanner_harness(FakeScannerBehavior(initial_state="Processing"))
    with pytest.raises(ScannerBusyError):
        await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.transport.count(POST_ROUTE) == 0


async def test_second_scan_waits_until_the_scanner_is_idle_again() -> None:
    harness = fake_scanner_harness(FakeScannerBehavior(processing_polls_after_document=2))
    await harness.gateway.scan_page(SCAN_SETTINGS)
    await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.sleep.delays == [READINESS_INTERVAL_SECONDS] * 2


async def test_post_answer_503_raises_scanner_busy() -> None:
    harness = fake_scanner_harness(FakeScannerBehavior(post_status_code=HTTPStatus.SERVICE_UNAVAILABLE))
    with pytest.raises(ScannerBusyError):
        await harness.gateway.scan_page(SCAN_SETTINGS)


@pytest.mark.parametrize("status_code", [HTTPStatus.BAD_REQUEST, HTTPStatus.CONFLICT])
async def test_post_answers_400_and_409_raise_scan_rejected(status_code: int) -> None:
    harness = fake_scanner_harness(FakeScannerBehavior(post_status_code=status_code))
    with pytest.raises(ScanRejectedError):
        await harness.gateway.scan_page(SCAN_SETTINGS)


async def test_post_answer_500_raises_scan_failed() -> None:
    harness = fake_scanner_harness(FakeScannerBehavior(post_status_code=HTTPStatus.INTERNAL_SERVER_ERROR))
    with pytest.raises(ScanFailedError):
        await harness.gateway.scan_page(SCAN_SETTINGS)


async def test_post_answer_201_without_location_raises_scan_failed() -> None:
    harness = scripted_harness({POST_ROUTE: [Reply(HTTPStatus.CREATED)]})
    with pytest.raises(ScanFailedError):
        await harness.gateway.scan_page(SCAN_SETTINGS)


async def test_refused_post_sends_no_delete() -> None:
    harness = fake_scanner_harness(FakeScannerBehavior(post_status_code=HTTPStatus.CONFLICT))
    with pytest.raises(ScanRejectedError):
        await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.transport.count(DELETE_ROUTE) == 0


async def test_location_with_a_foreign_host_never_redirects_the_next_requests() -> None:
    foreign_location = Reply(HTTPStatus.CREATED, headers={"Location": f"http://203.0.113.9:9999{JOB_PATH}"})
    harness = scripted_harness({POST_ROUTE: [foreign_location]})
    await harness.gateway.scan_page(SCAN_SETTINGS)
    assert {request.url.host for request in harness.transport.requests} == {SCANNER_HOST}


def color_only_busy_scanner_harness() -> GatewayHarness:
    return scripted_harness(
        {
            CAPABILITIES_ROUTE: [Reply(HTTPStatus.OK, build_capabilities_document(("RGB24",)))],
            STATUS_ROUTE: [Reply(HTTPStatus.OK, build_status_document("Processing"))],
        }
    )


async def test_unsupported_color_mode_is_rejected_before_waiting_for_a_busy_scanner() -> None:
    harness = color_only_busy_scanner_harness()
    with pytest.raises(ScanRejectedError):
        await harness.gateway.scan_page(ScanSettings(dots_per_inch=75, color_mode=ColorMode.GRAYSCALE))


async def test_unsupported_color_mode_reads_no_status_and_sends_no_scan_job() -> None:
    harness = color_only_busy_scanner_harness()
    with pytest.raises(ScanRejectedError):
        await harness.gateway.scan_page(ScanSettings(dots_per_inch=75, color_mode=ColorMode.GRAYSCALE))
    request_counts = (harness.transport.count(STATUS_ROUTE), harness.transport.count(POST_ROUTE))
    assert (request_counts, harness.sleep.delays) == ((0, 0), [])


async def test_next_document_busy_answers_are_polled_every_interval() -> None:
    harness = fake_scanner_harness(FakeScannerBehavior(busy_polls_before_document=3))
    await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.sleep.delays == [POLL_INTERVAL_SECONDS] * 3


async def test_next_document_404_before_any_page_is_retried_a_bounded_number_of_times() -> None:
    harness = failing_document_harness(HTTPStatus.NOT_FOUND)
    with pytest.raises(ScanFailedError):
        await harness.gateway.scan_page(SCAN_SETTINGS)
    assert (harness.transport.count(DOCUMENT_ROUTE), harness.sleep.delays) == (4, [POLL_INTERVAL_SECONDS] * 3)


async def test_next_document_404_that_clears_on_the_last_allowed_retry_still_delivers() -> None:
    not_found = Reply(HTTPStatus.NOT_FOUND)
    page = Reply(HTTPStatus.OK, build_sample_jpeg(), {"Content-Type": "image/jpeg"})
    harness = scripted_harness({DOCUMENT_ROUTE: [not_found, not_found, not_found, page]})
    scanned_image = await harness.gateway.scan_page(SCAN_SETTINGS)
    assert (scanned_image.media_type, harness.sleep.delays) == ("image/jpeg", [POLL_INTERVAL_SECONDS] * 3)


async def test_next_document_404_still_sends_the_delete() -> None:
    harness = failing_document_harness(HTTPStatus.NOT_FOUND)
    with pytest.raises(ScanFailedError):
        await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.transport.count(DELETE_ROUTE) == 1


async def test_next_document_500_raises_scan_failed() -> None:
    harness = failing_document_harness(HTTPStatus.INTERNAL_SERVER_ERROR)
    with pytest.raises(ScanFailedError):
        await harness.gateway.scan_page(SCAN_SETTINGS)


async def test_next_document_500_still_sends_the_delete() -> None:
    harness = failing_document_harness(HTTPStatus.INTERNAL_SERVER_ERROR)
    with pytest.raises(ScanFailedError):
        await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.transport.count(DELETE_ROUTE) == 1


async def test_exceeding_the_scan_timeout_raises_scan_timed_out() -> None:
    harness = scripted_harness({DOCUMENT_ROUTE: [Reply(HTTPStatus.SERVICE_UNAVAILABLE)]})
    with pytest.raises(ScanTimedOutError):
        await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.sleep.delays == [POLL_INTERVAL_SECONDS] * 4


async def test_exceeding_the_scan_timeout_still_sends_the_delete() -> None:
    harness = scripted_harness({DOCUMENT_ROUTE: [Reply(HTTPStatus.SERVICE_UNAVAILABLE)]})
    with pytest.raises(ScanTimedOutError):
        await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.transport.count(DELETE_ROUTE) == 1


async def test_read_timeout_becomes_scan_timed_out_only_after_the_scan_timeout() -> None:
    harness = scripted_harness({DOCUMENT_ROUTE: [httpx.ReadTimeout("scanner went silent")]})
    with pytest.raises(ScanTimedOutError):
        await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.sleep.delays == [POLL_INTERVAL_SECONDS] * 4


async def test_read_timeout_before_the_scan_timeout_is_retried() -> None:
    page = Reply(HTTPStatus.OK, build_sample_jpeg(), {"Content-Type": "image/jpeg"})
    harness = scripted_harness({DOCUMENT_ROUTE: [httpx.ReadTimeout("scanner went silent"), page]})
    scanned_image = await harness.gateway.scan_page(SCAN_SETTINGS)
    assert (scanned_image.media_type, harness.sleep.delays) == ("image/jpeg", [POLL_INTERVAL_SECONDS])


async def test_read_timeout_while_waiting_for_the_page_still_sends_the_delete() -> None:
    harness = scripted_harness({DOCUMENT_ROUTE: [httpx.ReadTimeout("scanner went silent")]})
    with pytest.raises(ScanTimedOutError):
        await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.transport.count(DELETE_ROUTE) == 1


async def test_connection_lost_while_waiting_for_the_page_raises_unreachable() -> None:
    harness = scripted_harness({DOCUMENT_ROUTE: [httpx.RemoteProtocolError("scanner went away")]})
    with pytest.raises(ScannerUnreachableError):
        await harness.gateway.scan_page(SCAN_SETTINGS)
    assert (harness.sleep.delays, harness.transport.count(DELETE_ROUTE)) == ([], 1)


async def test_next_document_read_timeout_is_never_shorter_than_180_seconds() -> None:
    harness = scripted_harness()
    await harness.gateway.scan_page(SCAN_SETTINGS)
    timeout = harness.transport.find(DOCUMENT_ROUTE).extensions["timeout"]
    expected = (EXPECTED_CONNECT_TIMEOUT_SECONDS, MINIMUM_NEXT_DOCUMENT_READ_TIMEOUT_SECONDS)
    assert (timeout["connect"], timeout["read"]) == expected


async def test_next_document_read_timeout_follows_a_longer_scan_timeout() -> None:
    scripted_transport = httpx.MockTransport(ScriptedResponses(healthy_scripts()))
    harness = build_harness(scripted_transport, TEST_BUSY_WAIT_SECONDS, PRODUCTION_SCAN_TIMEOUT_SECONDS)
    await harness.gateway.scan_page(SCAN_SETTINGS)
    timeout = harness.transport.find(DOCUMENT_ROUTE).extensions["timeout"]
    assert timeout["read"] == PRODUCTION_SCAN_TIMEOUT_SECONDS


async def test_other_requests_use_the_default_timeouts() -> None:
    harness = scripted_harness()
    await harness.gateway.read_status()
    timeout = harness.transport.find(STATUS_ROUTE).extensions["timeout"]
    assert (timeout["connect"], timeout["read"]) == (EXPECTED_CONNECT_TIMEOUT_SECONDS, EXPECTED_READ_TIMEOUT_SECONDS)


async def test_delete_that_fails_after_a_success_is_ignored() -> None:
    harness = scripted_harness({DELETE_ROUTE: [httpx.ConnectError("scanner went away")]})
    scanned_image = await harness.gateway.scan_page(SCAN_SETTINGS)
    assert scanned_image.media_type == "image/jpeg"


async def test_delete_that_fails_does_not_hide_the_original_error() -> None:
    failing_scan = {
        DOCUMENT_ROUTE: [Reply(HTTPStatus.INTERNAL_SERVER_ERROR)],
        DELETE_ROUTE: [httpx.ConnectError("scanner went away")],
    }
    harness = scripted_harness(failing_scan)
    with pytest.raises(ScanFailedError):
        await harness.gateway.scan_page(SCAN_SETTINGS)


async def test_delete_that_fails_is_logged_as_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    harness = scripted_harness({DELETE_ROUTE: [httpx.ConnectError("scanner went away")]})
    await harness.gateway.scan_page(SCAN_SETTINGS)
    assert len(warning_messages(caplog)) == 1


async def test_delete_answered_404_is_success_without_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    harness = scripted_harness({DELETE_ROUTE: [Reply(HTTPStatus.NOT_FOUND)]})
    scanned_image = await harness.gateway.scan_page(SCAN_SETTINGS)
    assert (scanned_image.media_type, warning_messages(caplog)) == ("image/jpeg", [])


async def test_delete_answered_500_keeps_the_success_and_logs_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    harness = scripted_harness({DELETE_ROUTE: [Reply(HTTPStatus.INTERNAL_SERVER_ERROR)]})
    scanned_image = await harness.gateway.scan_page(SCAN_SETTINGS)
    assert (scanned_image.media_type, len(warning_messages(caplog))) == ("image/jpeg", 1)


async def test_cancelled_scan_still_sends_the_delete() -> None:
    responses = NeverAnsweringDocumentResponses()
    harness = build_harness(httpx.MockTransport(responses))
    scan = asyncio.create_task(harness.gateway.scan_page(SCAN_SETTINGS))
    await responses.document_requested.wait()
    scan.cancel()
    with pytest.raises(asyncio.CancelledError):
        await scan
    assert harness.transport.count(DELETE_ROUTE) == 1


async def test_body_with_pdf_magic_bytes_raises_scan_failed() -> None:
    pdf_page = Reply(HTTPStatus.OK, b"%PDF-1.4 fake", {"Content-Type": "application/pdf"})
    harness = scripted_harness({DOCUMENT_ROUTE: [pdf_page]})
    with pytest.raises(ScanFailedError):
        await harness.gateway.scan_page(SCAN_SETTINGS)


async def test_pdf_body_labelled_as_jpeg_raises_scan_failed() -> None:
    mislabelled_page = Reply(HTTPStatus.OK, b"%PDF-1.4 fake", {"Content-Type": "image/jpeg"})
    harness = scripted_harness({DOCUMENT_ROUTE: [mislabelled_page]})
    with pytest.raises(ScanFailedError):
        await harness.gateway.scan_page(SCAN_SETTINGS)


async def test_empty_body_raises_scan_failed() -> None:
    empty_page = Reply(HTTPStatus.OK, b"", {"Content-Type": "image/jpeg"})
    harness = scripted_harness({DOCUMENT_ROUTE: [empty_page]})
    with pytest.raises(ScanFailedError):
        await harness.gateway.scan_page(SCAN_SETTINGS)


async def test_jpeg_body_without_a_media_type_raises_scan_failed() -> None:
    untyped_page = Reply(HTTPStatus.OK, build_sample_jpeg())
    harness = scripted_harness({DOCUMENT_ROUTE: [untyped_page]})
    with pytest.raises(ScanFailedError):
        await harness.gateway.scan_page(SCAN_SETTINGS)


async def test_media_type_parameters_are_ignored() -> None:
    parameterised_page = Reply(HTTPStatus.OK, build_sample_jpeg(), {"Content-Type": "image/jpeg; charset=binary"})
    harness = scripted_harness({DOCUMENT_ROUTE: [parameterised_page]})
    scanned_image = await harness.gateway.scan_page(SCAN_SETTINGS)
    assert scanned_image.media_type == "image/jpeg"


async def test_invalid_page_still_sends_the_delete() -> None:
    pdf_page = Reply(HTTPStatus.OK, b"%PDF-1.4 fake", {"Content-Type": "application/pdf"})
    harness = scripted_harness({DOCUMENT_ROUTE: [pdf_page]})
    with pytest.raises(ScanFailedError):
        await harness.gateway.scan_page(SCAN_SETTINGS)
    assert harness.transport.count(DELETE_ROUTE) == 1

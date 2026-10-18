"""eSCL scanner gateway: speaks HTTP to the printer through an injected httpx client."""

import asyncio
import errno
import logging
import time
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass
from http import HTTPStatus
from urllib.parse import urlsplit

import httpx

from digitalizadora.domain.errors import (
    DigitalizadoraError,
    LocalNetworkBlockedError,
    ScanFailedError,
    ScannerBusyError,
    ScannerUnreachableError,
    ScanRejectedError,
    ScanTimedOutError,
)
from digitalizadora.domain.scan_quality import scan_timeout_multiplier
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.domain.scanner_capabilities import ScannerCapabilities
from digitalizadora.domain.scanner_status import ScannerStatus
from digitalizadora.infrastructure.escl.escl_protocol import (
    build_scan_settings_xml,
    extract_job_path,
    parse_scanner_capabilities,
    parse_scanner_status,
)

logger = logging.getLogger(__name__)

CAPABILITIES_PATH = "ScannerCapabilities"
STATUS_PATH = "ScannerStatus"
SCAN_JOBS_PATH = "ScanJobs"
NEXT_DOCUMENT_PATH = "NextDocument"
XML_MEDIA_TYPE = "text/xml"
JPEG_MEDIA_TYPE = "image/jpeg"
JPEG_START_OF_IMAGE = b"\xff\xd8"
LOCATION_HEADER = "Location"
CONNECT_TIMEOUT_SECONDS = 5.0
READ_TIMEOUT_SECONDS = 30.0
# NextDocument blocks until the page is ready: 72 s for A4 colour at 600 dpi on the HP DeskJet 2800 series.
MINIMUM_NEXT_DOCUMENT_READ_TIMEOUT_SECONDS = 180.0
MAXIMUM_NOT_FOUND_RETRIES = 3
CLOSE_CONNECTION_HEADERS = {"Connection": "close"}
LOCAL_NETWORK_BLOCKED_ERRNO = errno.EHOSTUNREACH
READINESS_POLL_INTERVAL_SECONDS = 2.0
POST_FAILURE_BY_STATUS: dict[int, type[DigitalizadoraError]] = {
    HTTPStatus.SERVICE_UNAVAILABLE: ScannerBusyError,
    HTTPStatus.BAD_REQUEST: ScanRejectedError,
    HTTPStatus.CONFLICT: ScanRejectedError,
}


@dataclass(frozen=True)
class EsclGatewayTiming:
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    monotonic_clock: Callable[[], float] = time.monotonic
    document_poll_interval_seconds: float = 1.5
    busy_wait_seconds: float = 30.0
    scan_timeout_seconds: float = 300.0
    cleanup_timeout_seconds: float = 10.0

    def scan_timeout_for(self, dots_per_inch: int) -> float:
        """The page takes longer as the area grows: 300 s up to the measured 600 dpi, four times that at 1200."""
        return self.scan_timeout_seconds * scan_timeout_multiplier(dots_per_inch)


def _linked_exceptions(error: BaseException) -> Iterator[BaseException]:
    """Yield the error and every exception chained to it.

    httpx links httpcore through __cause__, httpcore links the socket error only through __context__, and anyio
    may group several connection attempts, so all three links are followed; the visited set stops a cycle.
    """
    pending: list[BaseException] = [error]
    visited_identities: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in visited_identities:
            continue
        visited_identities.add(id(current))
        yield current
        pending.extend(linked for linked in (current.__cause__, current.__context__) if linked is not None)
        if isinstance(current, BaseExceptionGroup):
            pending.extend(current.exceptions)


def _is_local_network_blocked(error: httpx.TransportError) -> bool:
    return any(
        isinstance(linked, OSError) and linked.errno == LOCAL_NETWORK_BLOCKED_ERRNO
        for linked in _linked_exceptions(error)
    )


def _translate_transport_error(error: httpx.TransportError) -> ScannerUnreachableError:
    if _is_local_network_blocked(error):
        return LocalNetworkBlockedError(f"The operating system blocked local network access: {error}")
    return ScannerUnreachableError(f"The scanner could not be reached: {error}")


def _next_not_found_count(status_code: int, not_found_count: int) -> int:
    """Return the 404 count after a NextDocument answer that is not the page; raise when the scan has failed."""
    if status_code == HTTPStatus.SERVICE_UNAVAILABLE:
        return not_found_count
    if status_code != HTTPStatus.NOT_FOUND:
        raise ScanFailedError(f"{NEXT_DOCUMENT_PATH} answered {status_code}")
    if not_found_count >= MAXIMUM_NOT_FOUND_RETRIES:
        raise ScanFailedError("The scanner never produced a page for the job")
    return not_found_count + 1


def _build_scanned_image(response: httpx.Response) -> ScannedImage:
    media_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
    if media_type != JPEG_MEDIA_TYPE:
        raise ScanFailedError(f"The scanner returned {media_type or 'an untyped body'} instead of {JPEG_MEDIA_TYPE}")
    if not response.content.startswith(JPEG_START_OF_IMAGE):
        raise ScanFailedError("The scanner body does not start with the JPEG marker")
    return ScannedImage(content=response.content, media_type=JPEG_MEDIA_TYPE)


def _is_successful_cleanup(response: httpx.Response) -> bool:
    # 404 is success too: the HP DeskJet 2800 series discards a finished job by itself (Gate 0).
    return response.is_success or response.status_code == HTTPStatus.NOT_FOUND


class EsclScannerGateway:
    def __init__(self, http_client: httpx.AsyncClient, base_address: str, timing: EsclGatewayTiming) -> None:
        self._http_client = http_client
        self._base_address = base_address.rstrip("/")
        self._timing = timing
        address_parts = urlsplit(self._base_address)
        self._origin = f"{address_parts.scheme}://{address_parts.netloc}"
        self._default_timeout = httpx.Timeout(READ_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS)
        self._capabilities: ScannerCapabilities | None = None

    async def read_capabilities(self) -> ScannerCapabilities:
        if self._capabilities is None:
            response = await self._get_document(CAPABILITIES_PATH)
            self._capabilities = parse_scanner_capabilities(response.content)
        return self._capabilities

    async def read_status(self) -> ScannerStatus:
        response = await self._get_document(STATUS_PATH)
        return parse_scanner_status(response.content)

    async def scan_page(self, settings: ScanSettings) -> ScannedImage:
        capabilities = await self.read_capabilities()
        # Built before the readiness wait, so unsupported settings are refused without waiting for a busy scanner.
        settings_document = build_scan_settings_xml(settings, capabilities)
        await self._wait_until_ready()
        job_path = await self._post_job(settings_document)
        try:
            return await self._download_page(job_path, self._timing.scan_timeout_for(settings.dots_per_inch))
        finally:
            await self._delete_job(job_path)

    async def _post_job(self, settings_document: bytes) -> str:
        request = self._http_client.build_request(
            "POST",
            f"{self._base_address}/{SCAN_JOBS_PATH}",
            content=settings_document,
            headers={"Content-Type": XML_MEDIA_TYPE},
            timeout=self._default_timeout,
        )
        response = await self._send_request(request)
        if response.status_code != HTTPStatus.CREATED:
            failure_type = POST_FAILURE_BY_STATUS.get(response.status_code, ScanFailedError)
            raise failure_type(f"POST {SCAN_JOBS_PATH} answered {response.status_code}")
        location = response.headers.get(LOCATION_HEADER)
        if not location:
            raise ScanFailedError(f"POST {SCAN_JOBS_PATH} answered 201 without a {LOCATION_HEADER} header")
        return extract_job_path(location).rstrip("/")

    async def _download_page(self, job_path: str, scan_timeout_seconds: float) -> ScannedImage:
        started_at = self._timing.monotonic_clock()
        not_found_count = 0
        while True:
            response = await self._request_next_document(job_path, scan_timeout_seconds)
            if response is not None and response.status_code == HTTPStatus.OK:
                return _build_scanned_image(response)
            if response is not None:
                not_found_count = _next_not_found_count(response.status_code, not_found_count)
            if self._timing.monotonic_clock() - started_at >= scan_timeout_seconds:
                raise ScanTimedOutError("The scanner took too long to deliver the page")
            await self._timing.sleep(self._timing.document_poll_interval_seconds)

    async def _delete_job(self, job_path: str) -> None:
        try:
            request = self._http_client.build_request(
                "DELETE",
                f"{self._origin}{job_path}",
                timeout=httpx.Timeout(self._timing.cleanup_timeout_seconds),
            )
            response = await self._send_request(request)
        except (DigitalizadoraError, httpx.HTTPError, httpx.InvalidURL) as error:
            logger.warning("Could not delete the scan job %s: %s", job_path, error)
            return
        if not _is_successful_cleanup(response):
            logger.warning("Deleting the scan job %s answered %s", job_path, response.status_code)

    async def _get_document(self, resource_name: str) -> httpx.Response:
        request = self._http_client.build_request(
            "GET",
            f"{self._base_address}/{resource_name}",
            timeout=self._default_timeout,
        )
        response = await self._send_request(request)
        if response.status_code != HTTPStatus.OK:
            raise ScannerUnreachableError(f"{resource_name} answered {response.status_code}")
        return response

    async def _send_request(self, request: httpx.Request) -> httpx.Response:
        request.headers.update(CLOSE_CONNECTION_HEADERS)
        try:
            return await self._http_client.send(request, follow_redirects=False)
        except httpx.TransportError as error:
            raise _translate_transport_error(error) from error

    async def _wait_until_ready(self) -> None:
        started_at = self._timing.monotonic_clock()
        while not (await self.read_status()).is_ready:
            if self._timing.monotonic_clock() - started_at >= self._timing.busy_wait_seconds:
                raise ScannerBusyError("The scanner stayed busy past the waiting limit")
            await self._timing.sleep(READINESS_POLL_INTERVAL_SECONDS)

    async def _request_next_document(self, job_path: str, scan_timeout_seconds: float) -> httpx.Response | None:
        """Ask for the page once; None means the read timed out before the page was ready."""
        read_timeout_seconds = max(MINIMUM_NEXT_DOCUMENT_READ_TIMEOUT_SECONDS, scan_timeout_seconds)
        request = self._http_client.build_request(
            "GET",
            f"{self._origin}{job_path}/{NEXT_DOCUMENT_PATH}",
            timeout=httpx.Timeout(READ_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS, read=read_timeout_seconds),
        )
        try:
            return await self._send_request(request)
        except ScannerUnreachableError as error:
            if isinstance(error.__cause__, httpx.ReadTimeout):
                return None
            raise

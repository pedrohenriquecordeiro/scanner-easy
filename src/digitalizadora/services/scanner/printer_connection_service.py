"""Finds the scanner (USB route first, then the network) and hands out a verified gateway."""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

from digitalizadora.domain.errors import DigitalizadoraError, LocalNetworkBlockedError, ScannerUnreachableError
from digitalizadora.domain.ports import ScannerDiscovery, ScannerEndpointRepository, ScannerGateway
from digitalizadora.domain.scanner.scanner_endpoint import ScannerEndpoint
from digitalizadora.domain.scanner.scanner_route import ScannerRoute, route_for_host_name
from digitalizadora.domain.scanner.scanner_status import ScannerState, ScannerStatus

logger = logging.getLogger(__name__)
DISCOVERY_TIMEOUT_SECONDS = 5.0
MANUAL_DISPLAY_NAME = "Manual"
ROUTE_PREFERENCE = (ScannerRoute.USB, ScannerRoute.NETWORK)


@dataclass(frozen=True)
class PrinterConnectionState:
    connected: bool
    display_name: str | None
    scanner_state: ScannerState | None
    error_code: str | None
    route: ScannerRoute | None = None


@dataclass(frozen=True)
class _Connection:
    gateway: ScannerGateway
    endpoint: ScannerEndpoint
    status: ScannerStatus


def _preference_rank(endpoint: ScannerEndpoint, preferred_identifier: str | None) -> tuple[bool, int]:
    is_preferred_scanner = (
        preferred_identifier is not None and endpoint.universally_unique_identifier == preferred_identifier
    )
    return not is_preferred_scanner, ROUTE_PREFERENCE.index(endpoint.route)


def _order_by_preference(
    discovered_endpoints: list[ScannerEndpoint], reference_endpoint: ScannerEndpoint | None
) -> list[ScannerEndpoint]:
    preferred_identifier = None if reference_endpoint is None else reference_endpoint.universally_unique_identifier
    return sorted(discovered_endpoints, key=lambda endpoint: _preference_rank(endpoint, preferred_identifier))


def _with_stored_endpoint_last(
    ordered_candidates: list[ScannerEndpoint], stored_endpoint: ScannerEndpoint | None
) -> list[ScannerEndpoint]:
    if stored_endpoint is None:
        return ordered_candidates
    if any(candidate.base_address == stored_endpoint.base_address for candidate in ordered_candidates):
        return ordered_candidates
    logger.info("The saved address %s is the last candidate", stored_endpoint.base_address)
    return [*ordered_candidates, stored_endpoint]


def _most_informative_failure(
    current_failure: ScannerUnreachableError | None, new_failure: ScannerUnreachableError
) -> ScannerUnreachableError:
    if isinstance(current_failure, LocalNetworkBlockedError):
        return current_failure
    return new_failure


def _disconnected_state(error_code: str) -> PrinterConnectionState:
    return PrinterConnectionState(
        connected=False, display_name=None, scanner_state=None, error_code=error_code, route=None
    )


def _build_manual_endpoint(base_address: str) -> ScannerEndpoint:
    normalized_address = base_address.rstrip("/")
    host_name = urlsplit(normalized_address).hostname or ""
    return ScannerEndpoint(
        base_address=normalized_address,
        display_name=MANUAL_DISPLAY_NAME,
        route=route_for_host_name(host_name),
    )


class PrinterConnectionService:
    def __init__(
        self,
        discovery: ScannerDiscovery,
        endpoint_repository: ScannerEndpointRepository,
        gateway_factory: Callable[[ScannerEndpoint], ScannerGateway],
    ) -> None:
        self._discovery = discovery
        self._endpoint_repository = endpoint_repository
        self._gateway_factory = gateway_factory
        self._connection: _Connection | None = None
        self._pending_manual_endpoint: ScannerEndpoint | None = None

    async def acquire_gateway(self) -> ScannerGateway:
        return (await self._ensure_connection()).gateway

    async def check_connection(self) -> PrinterConnectionState:
        return await self._describe(self._ensure_connection)

    async def refresh(self) -> PrinterConnectionState:
        self._connection = None
        self._pending_manual_endpoint = None
        return await self._describe(self._connect_through_discovery)

    def use_manual_address(self, base_address: str) -> None:
        manual_endpoint = _build_manual_endpoint(base_address)
        self._connection = None
        self._pending_manual_endpoint = manual_endpoint
        self._endpoint_repository.save(manual_endpoint)

    async def _describe(self, connect: Callable[[], Awaitable[_Connection]]) -> PrinterConnectionState:
        try:
            connection = await connect()
        except ScannerUnreachableError as error:
            return _disconnected_state(error.code)
        except Exception:
            logger.exception("Unexpected failure while checking the printer connection")
            return _disconnected_state(DigitalizadoraError.code)
        return PrinterConnectionState(
            connected=True,
            display_name=connection.endpoint.display_name,
            scanner_state=connection.status.state,
            error_code=None,
            route=connection.endpoint.route,
        )

    async def _ensure_connection(self) -> _Connection:
        if self._connection is not None:
            return await self._verify_current_connection(self._connection)
        if self._pending_manual_endpoint is not None:
            return await self._connect_to_manual_endpoint(self._pending_manual_endpoint)
        return await self._connect_through_discovery()

    async def _verify_current_connection(self, connection: _Connection) -> _Connection:
        try:
            return await self._connect_with(connection.gateway, connection.endpoint)
        except ScannerUnreachableError as error:
            logger.info(
                "The connected scanner at %s stopped answering; searching again", connection.endpoint.base_address
            )
            self._connection = None
            return await self._connect_through_discovery(error)

    async def _connect_to_manual_endpoint(self, manual_endpoint: ScannerEndpoint) -> _Connection:
        self._pending_manual_endpoint = None
        try:
            return await self._connect(manual_endpoint)
        except ScannerUnreachableError as error:
            logger.info("The manual scanner address %s did not answer; searching again", manual_endpoint.base_address)
            return await self._connect_through_discovery(error)

    async def _connect_through_discovery(self, failure: ScannerUnreachableError | None = None) -> _Connection:
        stored_endpoint = self._endpoint_repository.load()
        candidates = _with_stored_endpoint_last(
            _order_by_preference(await self._discover(), stored_endpoint), stored_endpoint
        )
        connection = await self._connect_to_first_answering(candidates, failure)
        self._endpoint_repository.save(connection.endpoint)
        return connection

    async def _discover(self) -> list[ScannerEndpoint]:
        try:
            return await self._discovery.discover(DISCOVERY_TIMEOUT_SECONDS)
        except Exception:
            logger.warning("Scanner discovery failed; continuing as if nothing was found", exc_info=True)
            return []

    async def _connect_to_first_answering(
        self, candidates: list[ScannerEndpoint], failure: ScannerUnreachableError | None
    ) -> _Connection:
        for endpoint in candidates:
            try:
                return await self._connect(endpoint)
            except ScannerUnreachableError as error:
                logger.info("The scanner at %s did not answer: %s", endpoint.base_address, error)
                failure = _most_informative_failure(failure, error)
        if failure is not None:
            raise failure
        raise ScannerUnreachableError("No scanner was found over USB or on the local network")

    async def _connect(self, endpoint: ScannerEndpoint) -> _Connection:
        return await self._connect_with(self._gateway_factory(endpoint), endpoint)

    async def _connect_with(self, gateway: ScannerGateway, endpoint: ScannerEndpoint) -> _Connection:
        connection = await self._verify(gateway, endpoint)
        self._connection = connection
        return connection

    async def _verify(self, gateway: ScannerGateway, endpoint: ScannerEndpoint) -> _Connection:
        try:
            status = await gateway.read_status()
        except ScannerUnreachableError:
            raise
        except DigitalizadoraError as error:
            raise ScannerUnreachableError(
                f"The scanner at {endpoint.base_address} gave an unusable status answer: {error}"
            ) from error
        if status.state is ScannerState.DOWN:
            raise ScannerUnreachableError(f"The scanner at {endpoint.base_address} reports being down")
        return _Connection(gateway, endpoint, status)

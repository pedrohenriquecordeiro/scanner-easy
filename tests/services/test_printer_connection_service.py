from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import pytest

from digitalizadora.domain.errors import LocalNetworkBlockedError, ScanFailedError, ScannerUnreachableError
from digitalizadora.domain.scanner_endpoint import ScannerEndpoint
from digitalizadora.domain.scanner_route import ScannerRoute
from digitalizadora.domain.scanner_status import ScannerState, ScannerStatus
from digitalizadora.services.printer_connection_service import (
    DISCOVERY_TIMEOUT_SECONDS,
    PrinterConnectionService,
)

STORED_ENDPOINT = ScannerEndpoint("http://HP000000000001.local:8080/eSCL", "HP Stored", "uuid-stored")
MOVED_ENDPOINT = ScannerEndpoint("http://192.168.0.77:8080/eSCL", "HP Moved", "uuid-stored")
OTHER_ENDPOINT = ScannerEndpoint("http://192.168.0.90:8080/eSCL", "HP Other", "uuid-other")
STORED_USB_ENDPOINT = ScannerEndpoint("http://localhost:57805/eSCL", "HP Stored", "uuid-stored", ScannerRoute.USB)
REPLUGGED_USB_ENDPOINT = ScannerEndpoint("http://localhost:57931/eSCL", "HP Stored", "uuid-stored", ScannerRoute.USB)
OTHER_USB_ENDPOINT = ScannerEndpoint("http://localhost:60001/eSCL", "HP Other USB", "uuid-other", ScannerRoute.USB)
LOOPBACK_ADDRESS = "http://127.0.0.1:8080/eSCL"
IDLE_STATUS = ScannerStatus(ScannerState.IDLE)
PROCESSING_STATUS = ScannerStatus(ScannerState.PROCESSING)
DOWN_STATUS = ScannerStatus(ScannerState.DOWN)


class StubScannerGateway:
    def __init__(self, outcomes: Sequence[ScannerStatus | Exception]) -> None:
        self._outcomes = list(outcomes)
        self.status_reads = 0

    async def read_status(self) -> ScannerStatus:
        self.status_reads += 1
        outcome = self._outcomes.pop(0) if len(self._outcomes) > 1 else self._outcomes[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class RecordingGatewayFactory:
    def __init__(self, gateways_by_base_address: Mapping[str, StubScannerGateway]) -> None:
        self._gateways_by_base_address = gateways_by_base_address
        self.requested_base_addresses: list[str] = []

    def __call__(self, endpoint: ScannerEndpoint) -> StubScannerGateway:
        self.requested_base_addresses.append(endpoint.base_address)
        return self._gateways_by_base_address[endpoint.base_address]


class InMemoryEndpointRepository:
    def __init__(self, stored_endpoint: ScannerEndpoint | None = None) -> None:
        self.stored_endpoint = stored_endpoint
        self.saved_endpoints: list[ScannerEndpoint] = []
        self.clear_count = 0

    def load(self) -> ScannerEndpoint | None:
        return self.stored_endpoint

    def save(self, endpoint: ScannerEndpoint) -> None:
        self.stored_endpoint = endpoint
        self.saved_endpoints.append(endpoint)

    def clear(self) -> None:
        self.stored_endpoint = None
        self.clear_count += 1


class FakeDiscovery:
    def __init__(self, endpoints: Sequence[ScannerEndpoint]) -> None:
        self.endpoints = list(endpoints)
        self.requested_timeouts: list[float] = []

    async def discover(self, timeout_seconds: float) -> list[ScannerEndpoint]:
        self.requested_timeouts.append(timeout_seconds)
        return list(self.endpoints)


class FailingDiscovery:
    def __init__(self, failure: Exception) -> None:
        self._failure = failure

    async def discover(self, timeout_seconds: float) -> list[ScannerEndpoint]:
        raise self._failure


@dataclass(frozen=True)
class ServiceHarness:
    service: PrinterConnectionService
    repository: InMemoryEndpointRepository
    discovery: FakeDiscovery
    gateway_factory: RecordingGatewayFactory


def build_harness(
    stored_endpoint: ScannerEndpoint | None,
    discovered_endpoints: Sequence[ScannerEndpoint],
    gateways_by_base_address: Mapping[str, StubScannerGateway],
) -> ServiceHarness:
    repository = InMemoryEndpointRepository(stored_endpoint)
    discovery = FakeDiscovery(discovered_endpoints)
    gateway_factory = RecordingGatewayFactory(gateways_by_base_address)
    service = PrinterConnectionService(discovery, repository, gateway_factory)
    return ServiceHarness(service, repository, discovery, gateway_factory)


def build_service_with_failing_discovery(
    stored_endpoint: ScannerEndpoint | None, failure: Exception
) -> PrinterConnectionService:
    gateways = {STORED_ENDPOINT.base_address: unreachable_gateway()}
    return PrinterConnectionService(
        FailingDiscovery(failure), InMemoryEndpointRepository(stored_endpoint), RecordingGatewayFactory(gateways)
    )


def unreachable_gateway() -> StubScannerGateway:
    return StubScannerGateway([ScannerUnreachableError("no route to the scanner")])


async def test_first_acquire_runs_discovery_even_with_a_saved_endpoint() -> None:
    gateways = {STORED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS])}
    harness = build_harness(STORED_ENDPOINT, [STORED_ENDPOINT], gateways)
    await harness.service.acquire_gateway()
    assert harness.discovery.requested_timeouts == [DISCOVERY_TIMEOUT_SECONDS]


async def test_saved_endpoint_is_not_contacted_when_discovery_finds_a_scanner() -> None:
    gateways = {MOVED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS])}
    harness = build_harness(STORED_ENDPOINT, [MOVED_ENDPOINT], gateways)
    await harness.service.acquire_gateway()
    assert harness.gateway_factory.requested_base_addresses == [MOVED_ENDPOINT.base_address]


async def test_discovered_endpoint_gives_the_gateway_built_from_it() -> None:
    gateway = StubScannerGateway([IDLE_STATUS])
    harness = build_harness(None, [MOVED_ENDPOINT], {MOVED_ENDPOINT.base_address: gateway})
    assert await harness.service.acquire_gateway() is gateway


async def test_discovered_endpoint_is_saved() -> None:
    harness = build_harness(None, [MOVED_ENDPOINT], {MOVED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS])})
    await harness.service.acquire_gateway()
    assert harness.repository.saved_endpoints == [MOVED_ENDPOINT]


async def test_chosen_endpoint_is_saved_even_when_it_matches_the_saved_one() -> None:
    gateways = {STORED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS])}
    harness = build_harness(STORED_ENDPOINT, [STORED_ENDPOINT], gateways)
    await harness.service.acquire_gateway()
    assert harness.repository.saved_endpoints == [STORED_ENDPOINT]


async def test_discovery_uses_the_five_second_timeout() -> None:
    harness = build_harness(None, [MOVED_ENDPOINT], {MOVED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS])})
    await harness.service.acquire_gateway()
    assert harness.discovery.requested_timeouts == [DISCOVERY_TIMEOUT_SECONDS]


async def test_saved_endpoint_is_used_when_discovery_finds_nothing() -> None:
    gateway = StubScannerGateway([IDLE_STATUS])
    harness = build_harness(STORED_ENDPOINT, [], {STORED_ENDPOINT.base_address: gateway})
    assert await harness.service.acquire_gateway() is gateway


async def test_saved_usb_endpoint_is_checked_before_it_is_used() -> None:
    gateway = StubScannerGateway([IDLE_STATUS])
    harness = build_harness(STORED_USB_ENDPOINT, [], {STORED_USB_ENDPOINT.base_address: gateway})
    await harness.service.acquire_gateway()
    assert gateway.status_reads == 1


async def test_busy_scanner_still_counts_as_reachable() -> None:
    gateway = StubScannerGateway([PROCESSING_STATUS])
    harness = build_harness(None, [STORED_ENDPOINT], {STORED_ENDPOINT.base_address: gateway})
    assert await harness.service.acquire_gateway() is gateway


async def test_connected_gateway_is_reused_while_it_keeps_answering() -> None:
    gateway = StubScannerGateway([IDLE_STATUS])
    harness = build_harness(None, [STORED_ENDPOINT], {STORED_ENDPOINT.base_address: gateway})
    await harness.service.acquire_gateway()
    await harness.service.acquire_gateway()
    assert harness.gateway_factory.requested_base_addresses == [STORED_ENDPOINT.base_address]


async def test_discovery_runs_once_while_the_connected_gateway_keeps_answering() -> None:
    harness = build_harness(None, [STORED_ENDPOINT], {STORED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS])})
    await harness.service.acquire_gateway()
    await harness.service.acquire_gateway()
    assert harness.discovery.requested_timeouts == [DISCOVERY_TIMEOUT_SECONDS]


async def test_reused_gateway_is_checked_again_on_every_acquire() -> None:
    gateway = StubScannerGateway([IDLE_STATUS])
    harness = build_harness(None, [STORED_ENDPOINT], {STORED_ENDPOINT.base_address: gateway})
    await harness.service.acquire_gateway()
    await harness.service.acquire_gateway()
    assert gateway.status_reads == 2


async def test_saved_network_endpoint_does_not_pin_the_app_to_the_network() -> None:
    usb_gateway = StubScannerGateway([IDLE_STATUS])
    gateways = {
        STORED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS]),
        STORED_USB_ENDPOINT.base_address: usb_gateway,
    }
    harness = build_harness(STORED_ENDPOINT, [STORED_ENDPOINT, STORED_USB_ENDPOINT], gateways)
    assert await harness.service.acquire_gateway() is usb_gateway


async def test_endpoint_with_the_stored_identifier_is_preferred_after_discovery() -> None:
    moved_gateway = StubScannerGateway([IDLE_STATUS])
    gateways = {
        OTHER_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS]),
        MOVED_ENDPOINT.base_address: moved_gateway,
    }
    harness = build_harness(STORED_ENDPOINT, [OTHER_ENDPOINT, MOVED_ENDPOINT], gateways)
    assert await harness.service.acquire_gateway() is moved_gateway


async def test_usb_route_of_the_stored_scanner_is_preferred_after_discovery() -> None:
    usb_gateway = StubScannerGateway([IDLE_STATUS])
    gateways = {
        OTHER_USB_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS]),
        MOVED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS]),
        REPLUGGED_USB_ENDPOINT.base_address: usb_gateway,
    }
    discovered = [OTHER_USB_ENDPOINT, MOVED_ENDPOINT, REPLUGGED_USB_ENDPOINT]
    harness = build_harness(STORED_ENDPOINT, discovered, gateways)
    assert await harness.service.acquire_gateway() is usb_gateway


async def test_stored_scanner_on_the_network_is_preferred_over_another_scanner_on_usb() -> None:
    moved_gateway = StubScannerGateway([IDLE_STATUS])
    gateways = {
        OTHER_USB_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS]),
        MOVED_ENDPOINT.base_address: moved_gateway,
    }
    harness = build_harness(STORED_ENDPOINT, [OTHER_USB_ENDPOINT, MOVED_ENDPOINT], gateways)
    assert await harness.service.acquire_gateway() is moved_gateway


async def test_usb_scanner_is_preferred_when_no_identifier_is_stored() -> None:
    usb_gateway = StubScannerGateway([IDLE_STATUS])
    gateways = {
        OTHER_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS]),
        OTHER_USB_ENDPOINT.base_address: usb_gateway,
    }
    harness = build_harness(None, [OTHER_ENDPOINT, OTHER_USB_ENDPOINT], gateways)
    assert await harness.service.acquire_gateway() is usb_gateway


async def test_network_route_is_used_when_the_usb_route_does_not_answer() -> None:
    moved_gateway = StubScannerGateway([IDLE_STATUS])
    gateways = {
        REPLUGGED_USB_ENDPOINT.base_address: unreachable_gateway(),
        MOVED_ENDPOINT.base_address: moved_gateway,
    }
    harness = build_harness(STORED_USB_ENDPOINT, [MOVED_ENDPOINT, REPLUGGED_USB_ENDPOINT], gateways)
    assert await harness.service.acquire_gateway() is moved_gateway


async def test_saved_usb_endpoint_with_an_old_port_is_replaced_after_discovery() -> None:
    gateways = {
        MOVED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS]),
        REPLUGGED_USB_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS]),
    }
    harness = build_harness(STORED_USB_ENDPOINT, [MOVED_ENDPOINT, REPLUGGED_USB_ENDPOINT], gateways)
    await harness.service.acquire_gateway()
    assert harness.repository.saved_endpoints == [REPLUGGED_USB_ENDPOINT]


async def test_other_scanner_is_used_when_the_stored_identifier_is_not_found() -> None:
    other_gateway = StubScannerGateway([IDLE_STATUS])
    harness = build_harness(STORED_ENDPOINT, [OTHER_ENDPOINT], {OTHER_ENDPOINT.base_address: other_gateway})
    assert await harness.service.acquire_gateway() is other_gateway


async def test_down_status_counts_as_unreachable() -> None:
    gateways = {
        STORED_ENDPOINT.base_address: StubScannerGateway([DOWN_STATUS]),
        MOVED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS]),
    }
    harness = build_harness(STORED_ENDPOINT, [STORED_ENDPOINT, MOVED_ENDPOINT], gateways)
    await harness.service.acquire_gateway()
    assert harness.repository.saved_endpoints == [MOVED_ENDPOINT]


async def test_unusable_status_answer_counts_as_unreachable_and_the_search_goes_on() -> None:
    moved_gateway = StubScannerGateway([IDLE_STATUS])
    gateways = {
        STORED_ENDPOINT.base_address: StubScannerGateway([ScanFailedError("not an eSCL status document")]),
        MOVED_ENDPOINT.base_address: moved_gateway,
    }
    harness = build_harness(STORED_ENDPOINT, [STORED_ENDPOINT, MOVED_ENDPOINT], gateways)
    assert await harness.service.acquire_gateway() is moved_gateway


async def test_nothing_found_raises_scanner_unreachable() -> None:
    harness = build_harness(None, [], {})
    with pytest.raises(ScannerUnreachableError):
        await harness.service.acquire_gateway()


async def test_unreachable_discovered_endpoint_raises_scanner_unreachable() -> None:
    harness = build_harness(None, [MOVED_ENDPOINT], {MOVED_ENDPOINT.base_address: unreachable_gateway()})
    with pytest.raises(ScannerUnreachableError):
        await harness.service.acquire_gateway()


async def test_saved_endpoint_is_tried_last_when_no_discovered_candidate_answers() -> None:
    stored_gateway = StubScannerGateway([IDLE_STATUS])
    gateways = {OTHER_ENDPOINT.base_address: unreachable_gateway(), STORED_ENDPOINT.base_address: stored_gateway}
    harness = build_harness(STORED_ENDPOINT, [OTHER_ENDPOINT], gateways)
    assert await harness.service.acquire_gateway() is stored_gateway


async def test_saved_endpoint_is_tried_after_the_discovered_candidates() -> None:
    gateways = {
        OTHER_ENDPOINT.base_address: unreachable_gateway(),
        STORED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS]),
    }
    harness = build_harness(STORED_ENDPOINT, [OTHER_ENDPOINT], gateways)
    await harness.service.acquire_gateway()
    assert harness.gateway_factory.requested_base_addresses == [
        OTHER_ENDPOINT.base_address,
        STORED_ENDPOINT.base_address,
    ]


async def test_saved_endpoint_is_not_tried_twice_when_it_was_discovered() -> None:
    harness = build_harness(STORED_ENDPOINT, [STORED_ENDPOINT], {STORED_ENDPOINT.base_address: unreachable_gateway()})
    with pytest.raises(ScannerUnreachableError):
        await harness.service.acquire_gateway()
    assert harness.gateway_factory.requested_base_addresses == [STORED_ENDPOINT.base_address]


@pytest.mark.parametrize("discovery_failure", [RuntimeError("no IPv4 interface"), OSError("socket failure")])
async def test_failing_discovery_counts_as_nothing_found(discovery_failure: Exception) -> None:
    service = build_service_with_failing_discovery(None, discovery_failure)
    with pytest.raises(ScannerUnreachableError):
        await service.acquire_gateway()


async def test_blocked_local_network_error_survives_an_empty_discovery() -> None:
    blocked_gateway = StubScannerGateway([LocalNetworkBlockedError("blocked by the operating system")])
    harness = build_harness(STORED_ENDPOINT, [], {STORED_ENDPOINT.base_address: blocked_gateway})
    with pytest.raises(LocalNetworkBlockedError):
        await harness.service.acquire_gateway()


async def test_blocked_local_network_error_wins_over_a_later_unreachable_candidate() -> None:
    gateways = {
        STORED_ENDPOINT.base_address: StubScannerGateway([LocalNetworkBlockedError("blocked by the operating system")]),
        OTHER_ENDPOINT.base_address: unreachable_gateway(),
    }
    harness = build_harness(STORED_ENDPOINT, [OTHER_ENDPOINT, STORED_ENDPOINT], gateways)
    with pytest.raises(LocalNetworkBlockedError):
        await harness.service.acquire_gateway()


async def test_blocked_local_network_error_wins_over_an_unreachable_saved_endpoint() -> None:
    gateways = {
        OTHER_ENDPOINT.base_address: StubScannerGateway([LocalNetworkBlockedError("blocked by the operating system")]),
        STORED_ENDPOINT.base_address: unreachable_gateway(),
    }
    harness = build_harness(STORED_ENDPOINT, [OTHER_ENDPOINT], gateways)
    with pytest.raises(LocalNetworkBlockedError):
        await harness.service.acquire_gateway()


async def test_connected_gateway_that_stops_answering_triggers_a_new_discovery() -> None:
    stored_gateway = StubScannerGateway([IDLE_STATUS, ScannerUnreachableError("went to sleep")])
    moved_gateway = StubScannerGateway([IDLE_STATUS])
    gateways = {STORED_ENDPOINT.base_address: stored_gateway, MOVED_ENDPOINT.base_address: moved_gateway}
    harness = build_harness(STORED_ENDPOINT, [STORED_ENDPOINT, MOVED_ENDPOINT], gateways)
    await harness.service.acquire_gateway()
    await harness.service.acquire_gateway()
    assert harness.discovery.requested_timeouts == [DISCOVERY_TIMEOUT_SECONDS, DISCOVERY_TIMEOUT_SECONDS]


async def test_connected_gateway_that_stops_answering_is_replaced_after_discovery() -> None:
    stored_gateway = StubScannerGateway([IDLE_STATUS, ScannerUnreachableError("went to sleep")])
    moved_gateway = StubScannerGateway([IDLE_STATUS])
    gateways = {STORED_ENDPOINT.base_address: stored_gateway, MOVED_ENDPOINT.base_address: moved_gateway}
    harness = build_harness(STORED_ENDPOINT, [STORED_ENDPOINT, MOVED_ENDPOINT], gateways)
    await harness.service.acquire_gateway()
    assert await harness.service.acquire_gateway() is moved_gateway


async def test_endpoint_rediscovered_after_a_failure_is_saved() -> None:
    stored_gateway = StubScannerGateway([IDLE_STATUS, ScannerUnreachableError("went to sleep")])
    moved_gateway = StubScannerGateway([IDLE_STATUS])
    gateways = {STORED_ENDPOINT.base_address: stored_gateway, MOVED_ENDPOINT.base_address: moved_gateway}
    harness = build_harness(STORED_ENDPOINT, [STORED_ENDPOINT, MOVED_ENDPOINT], gateways)
    await harness.service.acquire_gateway()
    await harness.service.acquire_gateway()
    assert harness.repository.saved_endpoints == [STORED_ENDPOINT, MOVED_ENDPOINT]


async def test_check_connection_reports_the_name_and_state_of_the_scanner() -> None:
    harness = build_harness(STORED_ENDPOINT, [], {STORED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS])})
    state = await harness.service.check_connection()
    assert (state.connected, state.display_name, state.scanner_state, state.error_code) == (
        True,
        "HP Stored",
        ScannerState.IDLE,
        None,
    )


async def test_check_connection_reports_a_busy_scanner() -> None:
    gateways = {STORED_ENDPOINT.base_address: StubScannerGateway([PROCESSING_STATUS])}
    harness = build_harness(STORED_ENDPOINT, [], gateways)
    state = await harness.service.check_connection()
    assert state.scanner_state is ScannerState.PROCESSING


async def test_check_connection_reports_the_usb_route() -> None:
    gateways = {STORED_USB_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS])}
    harness = build_harness(STORED_USB_ENDPOINT, [], gateways)
    assert (await harness.service.check_connection()).route is ScannerRoute.USB


async def test_check_connection_reports_the_network_route() -> None:
    harness = build_harness(STORED_ENDPOINT, [], {STORED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS])})
    assert (await harness.service.check_connection()).route is ScannerRoute.NETWORK


async def test_first_check_connection_runs_discovery() -> None:
    gateways = {STORED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS])}
    harness = build_harness(STORED_ENDPOINT, [STORED_ENDPOINT], gateways)
    await harness.service.check_connection()
    assert harness.discovery.requested_timeouts == [DISCOVERY_TIMEOUT_SECONDS]


async def test_check_connection_reports_an_unreachable_scanner_without_raising() -> None:
    harness = build_harness(None, [], {})
    state = await harness.service.check_connection()
    assert (state.connected, state.display_name, state.scanner_state, state.error_code, state.route) == (
        False,
        None,
        None,
        "scanner_unreachable",
        None,
    )


async def test_check_connection_reports_a_blocked_local_network() -> None:
    blocked_gateway = StubScannerGateway([LocalNetworkBlockedError("blocked by the operating system")])
    harness = build_harness(STORED_ENDPOINT, [], {STORED_ENDPOINT.base_address: blocked_gateway})
    state = await harness.service.check_connection()
    assert state.error_code == "local_network_blocked"


async def test_check_connection_reports_a_failing_discovery_as_unreachable() -> None:
    service = build_service_with_failing_discovery(STORED_ENDPOINT, RuntimeError("no IPv4 interface"))
    state = await service.check_connection()
    assert (state.connected, state.error_code) == (False, "scanner_unreachable")


async def test_check_connection_reports_an_unusable_status_answer_as_unreachable() -> None:
    gateways = {STORED_ENDPOINT.base_address: StubScannerGateway([ScanFailedError("not an eSCL status document")])}
    harness = build_harness(STORED_ENDPOINT, [], gateways)
    state = await harness.service.check_connection()
    assert state.error_code == "scanner_unreachable"


async def test_check_connection_reports_an_unexpected_failure_without_raising() -> None:
    gateways = {STORED_ENDPOINT.base_address: StubScannerGateway([RuntimeError("bug in a lower layer")])}
    harness = build_harness(STORED_ENDPOINT, [], gateways)
    state = await harness.service.check_connection()
    assert (state.connected, state.error_code) == (False, "unexpected_error")


async def test_refresh_never_clears_the_stored_endpoint() -> None:
    gateways = {STORED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS])}
    harness = build_harness(STORED_ENDPOINT, [STORED_ENDPOINT], gateways)
    await harness.service.refresh()
    assert harness.repository.clear_count == 0


async def test_every_refresh_discovers_the_scanner_again() -> None:
    gateways = {STORED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS])}
    harness = build_harness(STORED_ENDPOINT, [STORED_ENDPOINT], gateways)
    await harness.service.acquire_gateway()
    await harness.service.refresh()
    assert harness.discovery.requested_timeouts == [DISCOVERY_TIMEOUT_SECONDS, DISCOVERY_TIMEOUT_SECONDS]


async def test_refresh_forgets_the_connected_gateway() -> None:
    gateways = {STORED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS])}
    harness = build_harness(STORED_ENDPOINT, [STORED_ENDPOINT], gateways)
    await harness.service.acquire_gateway()
    await harness.service.refresh()
    assert harness.gateway_factory.requested_base_addresses == [STORED_ENDPOINT.base_address] * 2


async def test_refresh_picks_up_the_usb_route_that_appeared_after_the_start() -> None:
    gateways = {
        STORED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS]),
        STORED_USB_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS]),
    }
    harness = build_harness(STORED_ENDPOINT, [STORED_ENDPOINT], gateways)
    await harness.service.acquire_gateway()
    harness.discovery.endpoints = [STORED_ENDPOINT, STORED_USB_ENDPOINT]
    state = await harness.service.refresh()
    assert state.route is ScannerRoute.USB


async def test_refresh_reports_the_rediscovered_scanner() -> None:
    gateways = {MOVED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS])}
    harness = build_harness(STORED_ENDPOINT, [MOVED_ENDPOINT], gateways)
    state = await harness.service.refresh()
    assert (state.connected, state.display_name) == (True, "HP Moved")


async def test_refresh_saves_the_rediscovered_endpoint() -> None:
    gateways = {MOVED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS])}
    harness = build_harness(STORED_ENDPOINT, [MOVED_ENDPOINT], gateways)
    await harness.service.refresh()
    assert harness.repository.saved_endpoints == [MOVED_ENDPOINT]


async def test_refresh_prefers_the_stored_scanner_identity() -> None:
    gateways = {
        OTHER_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS]),
        MOVED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS]),
    }
    harness = build_harness(STORED_ENDPOINT, [OTHER_ENDPOINT, MOVED_ENDPOINT], gateways)
    state = await harness.service.refresh()
    assert state.display_name == "HP Moved"


async def test_refresh_falls_back_to_the_stored_endpoint_when_discovery_finds_nothing() -> None:
    harness = build_harness(STORED_ENDPOINT, [], {STORED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS])})
    state = await harness.service.refresh()
    assert (state.connected, state.display_name) == (True, "HP Stored")


async def test_refresh_tries_the_saved_endpoint_last_when_no_discovered_candidate_answers() -> None:
    gateways = {
        OTHER_ENDPOINT.base_address: unreachable_gateway(),
        STORED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS]),
    }
    harness = build_harness(STORED_ENDPOINT, [OTHER_ENDPOINT], gateways)
    state = await harness.service.refresh()
    assert (state.connected, state.display_name) == (True, "HP Stored")


async def test_refresh_keeps_the_stored_endpoint_when_nothing_is_found() -> None:
    harness = build_harness(STORED_ENDPOINT, [], {STORED_ENDPOINT.base_address: unreachable_gateway()})
    await harness.service.refresh()
    assert (harness.repository.stored_endpoint, harness.repository.saved_endpoints) == (STORED_ENDPOINT, [])


async def test_refresh_reports_when_nothing_is_found() -> None:
    harness = build_harness(STORED_ENDPOINT, [], {STORED_ENDPOINT.base_address: unreachable_gateway()})
    state = await harness.service.refresh()
    assert (state.connected, state.error_code) == (False, "scanner_unreachable")


def test_manual_address_is_saved_with_the_manual_display_name_and_no_identifier() -> None:
    harness = build_harness(None, [], {})
    harness.service.use_manual_address("http://192.168.0.50:8080/eSCL")
    assert harness.repository.saved_endpoints == [ScannerEndpoint("http://192.168.0.50:8080/eSCL", "Manual", None)]


def test_manual_address_loses_its_trailing_slash() -> None:
    harness = build_harness(None, [], {})
    harness.service.use_manual_address("http://192.168.0.50:8080/eSCL/")
    assert harness.repository.saved_endpoints[0].base_address == "http://192.168.0.50:8080/eSCL"


@pytest.mark.parametrize(
    "base_address",
    [
        "http://localhost:57805/eSCL",
        "http://LOCALHOST:57805/eSCL",
        "http://127.0.0.1:8080/eSCL",
        "http://[::1]:8080/eSCL",
    ],
)
def test_manual_address_on_a_loopback_host_is_saved_with_the_usb_route(base_address: str) -> None:
    harness = build_harness(None, [], {})
    harness.service.use_manual_address(base_address)
    assert harness.repository.saved_endpoints[0].route is ScannerRoute.USB


def test_manual_address_on_another_host_is_saved_with_the_network_route() -> None:
    harness = build_harness(None, [], {})
    harness.service.use_manual_address("http://HP000000000001.local:8080/eSCL")
    assert harness.repository.saved_endpoints[0].route is ScannerRoute.NETWORK


def test_manual_address_is_not_contacted_when_it_is_stored() -> None:
    harness = build_harness(None, [], {})
    harness.service.use_manual_address("http://192.168.0.50:8080/eSCL")
    assert harness.gateway_factory.requested_base_addresses == []


async def test_manual_address_drops_the_connected_gateway() -> None:
    manual_endpoint = ScannerEndpoint("http://192.168.0.50:8080/eSCL", "Manual")
    gateways = {
        STORED_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS]),
        manual_endpoint.base_address: StubScannerGateway([IDLE_STATUS]),
    }
    harness = build_harness(STORED_ENDPOINT, [], gateways)
    await harness.service.acquire_gateway()
    harness.service.use_manual_address(manual_endpoint.base_address)
    await harness.service.acquire_gateway()
    assert harness.gateway_factory.requested_base_addresses[-1] == manual_endpoint.base_address


async def test_manual_address_is_used_by_the_next_acquire_without_discovery() -> None:
    manual_gateway = StubScannerGateway([IDLE_STATUS])
    gateways = {OTHER_ENDPOINT.base_address: StubScannerGateway([IDLE_STATUS]), LOOPBACK_ADDRESS: manual_gateway}
    harness = build_harness(None, [OTHER_ENDPOINT], gateways)
    harness.service.use_manual_address(LOOPBACK_ADDRESS)
    assert (await harness.service.acquire_gateway(), harness.discovery.requested_timeouts) == (manual_gateway, [])


async def test_manual_address_that_does_not_answer_falls_back_to_discovery() -> None:
    other_gateway = StubScannerGateway([IDLE_STATUS])
    gateways = {OTHER_ENDPOINT.base_address: other_gateway, LOOPBACK_ADDRESS: unreachable_gateway()}
    harness = build_harness(None, [OTHER_ENDPOINT], gateways)
    harness.service.use_manual_address(LOOPBACK_ADDRESS)
    assert await harness.service.acquire_gateway() is other_gateway

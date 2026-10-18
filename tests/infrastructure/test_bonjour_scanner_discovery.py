from collections.abc import Mapping, Sequence

from digitalizadora.domain.scanner_route import ScannerRoute
from digitalizadora.infrastructure.bonjour_scanner_discovery import (
    BonjourScannerDiscovery,
    ServiceRecord,
    build_scanner_endpoint,
)

DISCOVERY_TIMEOUT_SECONDS = 5.0

INSTANCE_NAME = "HP DeskJet 2800 series [000001]"
NETWORK_HOST_NAME = "HP000000000001.local"
SECOND_NETWORK_HOST_NAME = "HP000000000002.local"
THIRD_NETWORK_HOST_NAME = "HP000000000003.local"


def build_record(
    host_name: str = NETWORK_HOST_NAME,
    properties: Mapping[str, str] | None = None,
    route: ScannerRoute = ScannerRoute.NETWORK,
) -> ServiceRecord:
    return ServiceRecord(INSTANCE_NAME, host_name, 8080, properties or {}, route)


def build_usb_record(properties: Mapping[str, str] | None = None) -> ServiceRecord:
    return ServiceRecord(INSTANCE_NAME, "localhost", 57805, properties or {}, ScannerRoute.USB)


class StubRecordSource:
    def __init__(self, records: Sequence[ServiceRecord]) -> None:
        self._records = list(records)
        self.requested_timeouts: list[float] = []

    async def collect_records(self, timeout_seconds: float) -> list[ServiceRecord]:
        self.requested_timeouts.append(timeout_seconds)
        return list(self._records)


def test_endpoint_base_address_combines_host_name_port_and_resource_path() -> None:
    endpoint = build_scanner_endpoint(build_record(properties={"rs": "eSCL"}))
    assert endpoint.base_address == "http://HP000000000001.local:8080/eSCL"


def test_endpoint_uses_the_default_resource_path_when_rs_is_missing() -> None:
    assert build_scanner_endpoint(build_record()).base_address == "http://HP000000000001.local:8080/eSCL"


def test_endpoint_uses_the_default_resource_path_when_rs_is_empty() -> None:
    assert build_scanner_endpoint(build_record(properties={"rs": ""})).base_address.endswith("/eSCL")


def test_endpoint_strips_the_slashes_around_the_resource_path() -> None:
    endpoint = build_scanner_endpoint(build_record(properties={"rs": "/eSCL/"}))
    assert endpoint.base_address == "http://HP000000000001.local:8080/eSCL"


def test_endpoint_keeps_a_custom_resource_path() -> None:
    endpoint = build_scanner_endpoint(build_record(properties={"rs": "/airscan/escl"}))
    assert endpoint.base_address == "http://HP000000000001.local:8080/airscan/escl"


def test_usb_endpoint_points_at_the_local_bridge() -> None:
    endpoint = build_scanner_endpoint(build_usb_record({"rs": "eSCL"}))
    assert endpoint.base_address == "http://localhost:57805/eSCL"


def test_endpoint_display_name_comes_from_the_ty_property() -> None:
    endpoint = build_scanner_endpoint(build_record(properties={"ty": "HP DeskJet 2800 series"}))
    assert endpoint.display_name == "HP DeskJet 2800 series"


def test_endpoint_display_name_falls_back_to_the_instance_name_without_ty() -> None:
    assert build_scanner_endpoint(build_record()).display_name == INSTANCE_NAME


def test_endpoint_display_name_falls_back_to_the_instance_name_with_an_empty_ty() -> None:
    assert build_scanner_endpoint(build_record(properties={"ty": ""})).display_name == INSTANCE_NAME


def test_endpoint_carries_the_advertised_identifier() -> None:
    endpoint = build_scanner_endpoint(build_record(properties={"uuid": "5f6c1c2e"}))
    assert endpoint.universally_unique_identifier == "5f6c1c2e"


def test_endpoint_has_no_identifier_when_none_is_advertised() -> None:
    assert build_scanner_endpoint(build_record()).universally_unique_identifier is None


def test_endpoint_has_no_identifier_when_the_advertised_one_is_empty() -> None:
    endpoint = build_scanner_endpoint(build_record(properties={"uuid": ""}))
    assert endpoint.universally_unique_identifier is None


def test_endpoint_keeps_the_usb_route_of_the_record() -> None:
    assert build_scanner_endpoint(build_usb_record()).route is ScannerRoute.USB


def test_endpoint_keeps_the_network_route_of_the_record() -> None:
    assert build_scanner_endpoint(build_record()).route is ScannerRoute.NETWORK


async def test_discover_returns_nothing_when_no_record_was_collected() -> None:
    discovery = BonjourScannerDiscovery(StubRecordSource([]))
    assert await discovery.discover(DISCOVERY_TIMEOUT_SECONDS) == []


async def test_discover_converts_a_record_into_an_endpoint() -> None:
    discovery = BonjourScannerDiscovery(StubRecordSource([build_record(properties={"ty": "Scanner"})]))
    endpoints = await discovery.discover(DISCOVERY_TIMEOUT_SECONDS)
    assert [endpoint.display_name for endpoint in endpoints] == ["Scanner"]


async def test_discover_passes_the_timeout_to_the_record_source() -> None:
    record_source = StubRecordSource([])
    await BonjourScannerDiscovery(record_source).discover(DISCOVERY_TIMEOUT_SECONDS)
    assert record_source.requested_timeouts == [DISCOVERY_TIMEOUT_SECONDS]


async def test_discover_merges_records_that_share_the_base_address() -> None:
    records = [
        build_record(properties={"uuid": "same"}),
        ServiceRecord("Same printer again", NETWORK_HOST_NAME, 8080, {"uuid": "same"}, ScannerRoute.NETWORK),
    ]
    endpoints = await BonjourScannerDiscovery(StubRecordSource(records)).discover(DISCOVERY_TIMEOUT_SECONDS)
    assert len(endpoints) == 1


async def test_discover_keeps_the_first_record_of_a_shared_base_address() -> None:
    records = [
        build_record(properties={"ty": "Scanner", "uuid": "first"}),
        build_record(properties={"ty": "Scanner", "uuid": "second"}),
    ]
    endpoints = await BonjourScannerDiscovery(StubRecordSource(records)).discover(DISCOVERY_TIMEOUT_SECONDS)
    assert [endpoint.universally_unique_identifier for endpoint in endpoints] == ["first"]


async def test_discover_merges_the_usb_bridge_seen_on_two_interfaces() -> None:
    records = [build_usb_record({"uuid": "same"}), build_usb_record({"uuid": "same", "ty": "Bridge seen on Wi-Fi"})]
    endpoints = await BonjourScannerDiscovery(StubRecordSource(records)).discover(DISCOVERY_TIMEOUT_SECONDS)
    assert [endpoint.base_address for endpoint in endpoints] == ["http://localhost:57805/eSCL"]


async def test_discover_keeps_the_usb_route_of_a_base_address_seen_on_both_routes() -> None:
    records = [
        build_record(properties={"ty": "Alpha"}),
        build_record(properties={"ty": "Zeta"}, route=ScannerRoute.USB),
    ]
    endpoints = await BonjourScannerDiscovery(StubRecordSource(records)).discover(DISCOVERY_TIMEOUT_SECONDS)
    assert [endpoint.route for endpoint in endpoints] == [ScannerRoute.USB]


async def test_discover_keeps_records_with_the_same_identifier_at_different_base_addresses() -> None:
    records = [
        build_record(NETWORK_HOST_NAME, {"uuid": "same"}),
        build_record(SECOND_NETWORK_HOST_NAME, {"uuid": "same"}),
    ]
    endpoints = await BonjourScannerDiscovery(StubRecordSource(records)).discover(DISCOVERY_TIMEOUT_SECONDS)
    assert len(endpoints) == 2


async def test_discover_keeps_both_routes_of_the_same_scanner() -> None:
    records = [build_record(properties={"uuid": "same"}), build_usb_record({"uuid": "same"})]
    endpoints = await BonjourScannerDiscovery(StubRecordSource(records)).discover(DISCOVERY_TIMEOUT_SECONDS)
    assert {endpoint.route for endpoint in endpoints} == {ScannerRoute.USB, ScannerRoute.NETWORK}


async def test_discover_lists_usb_endpoints_before_network_ones() -> None:
    records = [build_record(properties={"ty": "Alpha"}), build_usb_record({"ty": "Zeta"})]
    endpoints = await BonjourScannerDiscovery(StubRecordSource(records)).discover(DISCOVERY_TIMEOUT_SECONDS)
    assert [endpoint.route for endpoint in endpoints] == [ScannerRoute.USB, ScannerRoute.NETWORK]


async def test_discover_sorts_endpoints_of_one_route_by_display_name_ignoring_case() -> None:
    records = [
        build_record(SECOND_NETWORK_HOST_NAME, {"ty": "beta"}),
        build_record(NETWORK_HOST_NAME, {"ty": "Alpha"}),
        build_record(THIRD_NETWORK_HOST_NAME, {"ty": "Gamma"}),
    ]
    endpoints = await BonjourScannerDiscovery(StubRecordSource(records)).discover(DISCOVERY_TIMEOUT_SECONDS)
    assert [endpoint.display_name for endpoint in endpoints] == ["Alpha", "beta", "Gamma"]


async def test_discover_keeps_the_arrival_order_of_endpoints_with_the_same_name() -> None:
    records = [
        build_record(SECOND_NETWORK_HOST_NAME, {"ty": "Scanner", "uuid": "second"}),
        build_record(NETWORK_HOST_NAME, {"ty": "Scanner", "uuid": "first"}),
    ]
    endpoints = await BonjourScannerDiscovery(StubRecordSource(records)).discover(DISCOVERY_TIMEOUT_SECONDS)
    assert [endpoint.universally_unique_identifier for endpoint in endpoints] == ["second", "first"]


async def test_discover_ignores_records_with_an_empty_host_name() -> None:
    records = [build_record(host_name=""), build_record(SECOND_NETWORK_HOST_NAME, {"ty": "Kept"})]
    endpoints = await BonjourScannerDiscovery(StubRecordSource(records)).discover(DISCOVERY_TIMEOUT_SECONDS)
    assert [endpoint.display_name for endpoint in endpoints] == ["Kept"]


async def test_discover_ignores_records_without_a_port() -> None:
    records = [ServiceRecord(INSTANCE_NAME, NETWORK_HOST_NAME, 0, {}, ScannerRoute.NETWORK)]
    assert await BonjourScannerDiscovery(StubRecordSource(records)).discover(DISCOVERY_TIMEOUT_SECONDS) == []

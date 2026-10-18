import pytest

from digitalizadora.domain.scanner.scanner_route import ScannerRoute, route_for_host_name


@pytest.mark.parametrize(
    ("stored_text", "expected_route"),
    [("usb", ScannerRoute.USB), ("network", ScannerRoute.NETWORK)],
)
def test_route_is_created_from_its_stored_text(stored_text: str, expected_route: ScannerRoute) -> None:
    assert ScannerRoute(stored_text) is expected_route


@pytest.mark.parametrize("host_name", ["localhost", "LOCALHOST", "127.0.0.1", "::1"])
def test_loopback_host_name_means_the_usb_route(host_name: str) -> None:
    assert route_for_host_name(host_name) is ScannerRoute.USB


@pytest.mark.parametrize("host_name", ["HP000000000001.local", "192.168.0.40", "localhost.example.com", ""])
def test_any_other_host_name_means_the_network_route(host_name: str) -> None:
    assert route_for_host_name(host_name) is ScannerRoute.NETWORK

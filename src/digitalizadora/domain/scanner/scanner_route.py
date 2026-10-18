from enum import Enum

LOOPBACK_HOST_NAMES = frozenset({"localhost", "127.0.0.1", "::1"})


class ScannerRoute(str, Enum):
    # USB: the macOS IPP-over-USB bridge, served on a loopback host ("localhost") with a dynamic port.
    USB = "usb"
    NETWORK = "network"


def route_for_host_name(host_name: str) -> ScannerRoute:
    return ScannerRoute.USB if host_name.casefold() in LOOPBACK_HOST_NAMES else ScannerRoute.NETWORK

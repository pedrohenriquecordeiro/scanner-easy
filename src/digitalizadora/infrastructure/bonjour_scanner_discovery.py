"""Turns DNS-SD service records into scanner endpoints, USB route first; no network access in this module."""

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from digitalizadora.domain.scanner.scanner_endpoint import ScannerEndpoint
from digitalizadora.domain.scanner.scanner_route import ScannerRoute

logger = logging.getLogger(__name__)

DEFAULT_RESOURCE_PATH = "eSCL"
RESOURCE_PATH_KEY = "rs"
DISPLAY_NAME_KEY = "ty"
UNIVERSALLY_UNIQUE_IDENTIFIER_KEY = "uuid"
ROUTE_PREFERENCE = (ScannerRoute.USB, ScannerRoute.NETWORK)


@dataclass(frozen=True)
class ServiceRecord:
    instance_name: str
    host_name: str
    port: int
    properties: Mapping[str, str]
    route: ScannerRoute


class ServiceRecordSource(Protocol):
    async def collect_records(self, timeout_seconds: float) -> list[ServiceRecord]: ...


def build_scanner_endpoint(record: ServiceRecord) -> ScannerEndpoint:
    resource_path = record.properties.get(RESOURCE_PATH_KEY, "").strip("/") or DEFAULT_RESOURCE_PATH
    return ScannerEndpoint(
        base_address=f"http://{record.host_name}:{record.port}/{resource_path}",
        display_name=record.properties.get(DISPLAY_NAME_KEY) or record.instance_name,
        universally_unique_identifier=record.properties.get(UNIVERSALLY_UNIQUE_IDENTIFIER_KEY) or None,
        route=record.route,
    )


def _has_host_name_and_port(record: ServiceRecord) -> bool:
    if record.host_name and record.port > 0:
        return True
    logger.debug("Ignoring %s: the service record has no host name or port", record.instance_name)
    return False


def _sorting_key(endpoint: ScannerEndpoint) -> tuple[int, str]:
    return ROUTE_PREFERENCE.index(endpoint.route), endpoint.display_name.casefold()


class BonjourScannerDiscovery:
    def __init__(self, record_source: ServiceRecordSource) -> None:
        self._record_source = record_source

    async def discover(self, timeout_seconds: float) -> list[ScannerEndpoint]:
        records = await self._record_source.collect_records(timeout_seconds)
        endpoints = [build_scanner_endpoint(record) for record in records if _has_host_name_and_port(record)]
        unique_endpoints: dict[str, ScannerEndpoint] = {}
        for endpoint in sorted(endpoints, key=_sorting_key):
            unique_endpoints.setdefault(endpoint.base_address, endpoint)
        return list(unique_endpoints.values())

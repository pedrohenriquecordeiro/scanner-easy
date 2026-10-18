import inspect
from typing import Protocol

import pytest

from digitalizadora.domain import ports

EXPECTED_PORT_NAMES = {
    "Clock",
    "ScannerGateway",
    "ScannerGatewayProvider",
    "ScannerDiscovery",
    "ScannerEndpointRepository",
    "ApplicationSettingsRepository",
    "ScanOutputRepository",
    "DocumentDraftRepository",
    "QuickScanSlotRepository",
}
EXPECTED_METHOD_NAMES_BY_PORT = {
    "Clock": {"now", "now_in_nanoseconds"},
    "ScannerGateway": {"read_capabilities", "read_status", "scan_page"},
    "ScannerGatewayProvider": {"acquire_gateway"},
    "ScannerDiscovery": {"discover"},
    "ScannerEndpointRepository": {"load", "save", "clear"},
    "ApplicationSettingsRepository": {"load", "save"},
    "ScanOutputRepository": {
        "output_folder",
        "ensure_output_folder_ready",
        "save",
        "save_in_folder",
        "save_document",
        "describe_saved_scan",
    },
    "QuickScanSlotRepository": {
        "storage_folder",
        "ensure_storage_folder_ready",
        "write_master_files",
        "master_file_path",
        "read_thumbnail",
        "load",
        "commit",
        "delete_leftovers",
        "discard",
    },
    "DocumentDraftRepository": {
        "storage_folder",
        "claim_exclusive_access",
        "ensure_storage_folder_ready",
        "load_manifest",
        "save_manifest",
        "ensure_draft_folder_exists",
        "write_page_files",
        "page_file_path",
        "page_file_size",
        "read_page_file",
        "read_thumbnail",
        "delete_page_files",
        "take_inventory",
        "delete_files",
        "set_aside_files",
        "set_aside_draft_folder",
        "delete_draft",
        "finished_document_exists",
    },
}


def defined_classes() -> dict[str, type]:
    return {
        name: member
        for name, member in inspect.getmembers(ports, inspect.isclass)
        if member.__module__ == ports.__name__
    }


def test_ports_module_defines_exactly_the_contract_ports() -> None:
    assert set(defined_classes()) == EXPECTED_PORT_NAMES


def test_every_port_is_a_protocol() -> None:
    assert all(Protocol in port.__bases__ for port in defined_classes().values())


@pytest.mark.parametrize(("port_name", "expected_method_names"), EXPECTED_METHOD_NAMES_BY_PORT.items())
def test_port_declares_exactly_the_contract_methods(port_name: str, expected_method_names: set[str]) -> None:
    port = defined_classes()[port_name]
    declared_method_names = {
        name for name, member in vars(port).items() if inspect.isfunction(member) and not name.startswith("_")
    }

    assert declared_method_names == expected_method_names

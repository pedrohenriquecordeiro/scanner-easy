import inspect
from collections.abc import Sequence

from digitalizadora.domain.scanner_route import ScannerRoute
from digitalizadora.infrastructure.bonjour_scanner_discovery import ServiceRecordSource
from digitalizadora.infrastructure.dns_service_discovery_record_source import (
    DnsServiceDiscoveryRecordSource,
    classify_route,
    normalize_host_name,
    parse_text_record,
)


def encode_text_record(entries: Sequence[bytes]) -> bytes:
    return b"".join(bytes([len(entry)]) + entry for entry in entries)


def test_text_record_entries_become_properties() -> None:
    raw_text_record = encode_text_record([b"rs=eSCL", b"ty=HP DeskJet 2800 series"])
    assert parse_text_record(raw_text_record) == {"rs": "eSCL", "ty": "HP DeskJet 2800 series"}


def test_text_record_keys_are_lowercased() -> None:
    raw_text_record = encode_text_record([b"UUID=00000000-0000-4000-8000-000000000001"])
    assert parse_text_record(raw_text_record) == {"uuid": "00000000-0000-4000-8000-000000000001"}


def test_text_record_value_is_everything_after_the_first_equals_sign() -> None:
    raw_text_record = encode_text_record([b"adminurl=http://HP000000000001.local./?page=1"])
    assert parse_text_record(raw_text_record) == {"adminurl": "http://HP000000000001.local./?page=1"}


def test_text_record_entry_without_equals_sign_becomes_an_empty_string() -> None:
    assert parse_text_record(encode_text_record([b"duplex"])) == {"duplex": ""}


def test_text_record_entry_with_an_empty_value_stays_empty() -> None:
    assert parse_text_record(encode_text_record([b"note="])) == {"note": ""}


def test_empty_text_record_becomes_an_empty_mapping() -> None:
    assert parse_text_record(b"") == {}


def test_text_record_with_a_single_empty_entry_becomes_an_empty_mapping() -> None:
    assert parse_text_record(b"\x00") == {}


def test_text_record_values_with_invalid_bytes_are_replaced_instead_of_failing() -> None:
    assert parse_text_record(encode_text_record([b"note=\xff"])) == {"note": "�"}


def test_text_record_entry_without_a_key_is_ignored() -> None:
    assert parse_text_record(encode_text_record([b"=orphan", b"rs=eSCL"])) == {"rs": "eSCL"}


def test_text_record_keeps_the_first_value_of_a_repeated_key() -> None:
    assert parse_text_record(encode_text_record([b"rs=eSCL", b"RS=other"])) == {"rs": "eSCL"}


def test_text_record_ignores_a_truncated_last_entry() -> None:
    raw_text_record = encode_text_record([b"rs=eSCL"]) + bytes([20]) + b"ty=cut"
    assert parse_text_record(raw_text_record) == {"rs": "eSCL"}


def test_host_name_loses_the_trailing_dot_of_the_usb_bridge() -> None:
    assert normalize_host_name("localhost.") == "localhost"


def test_host_name_loses_the_trailing_dot_of_the_network_printer() -> None:
    assert normalize_host_name("HP000000000001.local.") == "HP000000000001.local"


def test_host_name_without_a_trailing_dot_is_unchanged() -> None:
    assert normalize_host_name("HP000000000001.local") == "HP000000000001.local"


def test_local_only_interface_means_the_usb_route() -> None:
    assert classify_route(0xFFFFFFFF, "localhost") is ScannerRoute.USB


def test_local_only_interface_means_the_usb_route_whatever_the_host_name() -> None:
    assert classify_route(0xFFFFFFFF, "HP000000000001.local") is ScannerRoute.USB


def test_usb_bridge_resolved_on_the_wifi_interface_means_the_usb_route() -> None:
    assert classify_route(11, "localhost") is ScannerRoute.USB


def test_network_host_on_the_wifi_interface_means_the_network_route() -> None:
    assert classify_route(11, "HP000000000001.local") is ScannerRoute.NETWORK


def test_collect_records_has_the_signature_of_the_service_record_source_protocol() -> None:
    implementation = inspect.signature(DnsServiceDiscoveryRecordSource.collect_records)
    protocol = inspect.signature(ServiceRecordSource.collect_records)
    assert list(implementation.parameters) == list(protocol.parameters)


def test_collect_records_is_a_coroutine_function() -> None:
    assert inspect.iscoroutinefunction(DnsServiceDiscoveryRecordSource.collect_records)

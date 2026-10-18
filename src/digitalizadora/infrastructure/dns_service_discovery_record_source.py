"""Collects eSCL service records through the native macOS DNS-SD API (libSystem, called with ctypes).

The USB route (the macOS IPP-over-USB bridge) is advertised by mDNSResponder only on the local-only interface,
which a pure-Python mDNS library cannot see; the system API sees both routes (Gate 0, 2026-10-17).
"""

import asyncio
import ctypes
import functools
import logging
import select
import socket
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, NamedTuple

from digitalizadora.domain.scanner_route import ScannerRoute, route_for_host_name
from digitalizadora.infrastructure.bonjour_scanner_discovery import ServiceRecord

logger = logging.getLogger(__name__)

LOCAL_ONLY_INTERFACE_INDEX = 0xFFFFFFFF
TEXT_ENCODING = "utf-8"
SYSTEM_LIBRARY_PATH = "/usr/lib/libSystem.B.dylib"
SERVICE_TYPE = b"_uscan._tcp"
SERVICE_DOMAIN = b"local."
ANY_INTERFACE_INDEX = 0
NO_FLAGS = 0
BROWSE_FLAG_ADD = 0x2
NO_ERROR = 0
RESOLVE_TIMEOUT_SECONDS = 1.5

ServiceReference = ctypes.c_void_p
BrowseReplyCallback = ctypes.CFUNCTYPE(
    None,
    ServiceReference,
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.c_int32,
    ctypes.c_char_p,
    ctypes.c_char_p,
    ctypes.c_char_p,
    ctypes.c_void_p,
)
ResolveReplyCallback = ctypes.CFUNCTYPE(
    None,
    ServiceReference,
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.c_int32,
    ctypes.c_char_p,
    ctypes.c_char_p,
    ctypes.c_uint16,
    ctypes.c_uint16,
    ctypes.POINTER(ctypes.c_ubyte),
    ctypes.c_void_p,
)


def _split_text_entries(raw_text_record: bytes) -> list[bytes]:
    entries: list[bytes] = []
    position = 0
    while position < len(raw_text_record):
        entry_end = position + 1 + raw_text_record[position]
        if entry_end > len(raw_text_record):
            logger.debug("Ignoring a truncated TXT entry at byte %s", position)
            break
        entries.append(raw_text_record[position + 1 : entry_end])
        position = entry_end
    return entries


def parse_text_record(raw_text_record: bytes) -> dict[str, str]:
    properties: dict[str, str] = {}
    for entry in _split_text_entries(raw_text_record):
        key, _, value = entry.decode(TEXT_ENCODING, errors="replace").partition("=")
        if key:
            properties.setdefault(key.lower(), value)
    return properties


def normalize_host_name(host_target: str) -> str:
    return host_target.removesuffix(".")


def classify_route(interface_index: int, host_name: str) -> ScannerRoute:
    if interface_index == LOCAL_ONLY_INTERFACE_INDEX:
        return ScannerRoute.USB
    return route_for_host_name(host_name)


class _BrowseReply(NamedTuple):
    service_reference: int | None
    flags: int
    interface_index: int
    error_code: int
    service_name: bytes
    registration_type: bytes
    reply_domain: bytes
    context: int | None


class _ResolveReply(NamedTuple):
    service_reference: int | None
    flags: int
    interface_index: int
    error_code: int
    full_name: bytes
    host_target: bytes
    network_order_port: int
    text_record_length: int
    text_record: Any
    context: int | None


@dataclass(frozen=True)
class _ServiceInstance:
    interface_index: int
    service_name: bytes
    registration_type: bytes
    reply_domain: bytes


@functools.cache
def _load_system_library() -> ctypes.CDLL:
    library = ctypes.CDLL(SYSTEM_LIBRARY_PATH)
    library.DNSServiceBrowse.argtypes = [
        ctypes.POINTER(ServiceReference),
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_char_p,
        ctypes.c_char_p,
        BrowseReplyCallback,
        ctypes.c_void_p,
    ]
    library.DNSServiceBrowse.restype = ctypes.c_int32
    library.DNSServiceResolve.argtypes = [
        ctypes.POINTER(ServiceReference),
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ResolveReplyCallback,
        ctypes.c_void_p,
    ]
    library.DNSServiceResolve.restype = ctypes.c_int32
    library.DNSServiceRefSockFD.argtypes = [ServiceReference]
    library.DNSServiceRefSockFD.restype = ctypes.c_int
    library.DNSServiceProcessResult.argtypes = [ServiceReference]
    library.DNSServiceProcessResult.restype = ctypes.c_int32
    library.DNSServiceRefDeallocate.argtypes = [ServiceReference]
    library.DNSServiceRefDeallocate.restype = None
    return library


def _process_replies(library: ctypes.CDLL, references: Sequence[ctypes.c_void_p], duration_seconds: float) -> None:
    descriptors = ((library.DNSServiceRefSockFD(reference), reference) for reference in references)
    references_by_descriptor = {descriptor: reference for descriptor, reference in descriptors if descriptor >= 0}
    deadline = time.monotonic() + duration_seconds
    while references_by_descriptor and (remaining_seconds := deadline - time.monotonic()) > 0:
        ready_descriptors, _, _ = select.select(list(references_by_descriptor), [], [], remaining_seconds)
        for descriptor in ready_descriptors:
            if library.DNSServiceProcessResult(references_by_descriptor[descriptor]) != NO_ERROR:
                logger.info("Stopped reading a DNS-SD reply stream after an error")
                del references_by_descriptor[descriptor]


def _build_service_record(instance: _ServiceInstance, reply: _ResolveReply) -> ServiceRecord:
    host_name = normalize_host_name(reply.host_target.decode(TEXT_ENCODING, errors="replace"))
    return ServiceRecord(
        instance_name=instance.service_name.decode(TEXT_ENCODING, errors="replace"),
        host_name=host_name,
        port=socket.ntohs(reply.network_order_port),
        properties=parse_text_record(bytes(reply.text_record[: reply.text_record_length])),
        route=classify_route(instance.interface_index, host_name),
    )


def _build_resolve_handler(instance: _ServiceInstance, records: list[ServiceRecord]) -> Callable[..., None]:
    def on_resolve_reply(*arguments: Any) -> None:
        reply = _ResolveReply(*arguments)
        if reply.error_code != NO_ERROR:
            logger.info("DNS-SD could not resolve %r: error %s", instance.service_name, reply.error_code)
            return
        records.append(_build_service_record(instance, reply))

    return on_resolve_reply


class DnsServiceDiscoveryRecordSource:
    async def collect_records(self, timeout_seconds: float) -> list[ServiceRecord]:
        return await asyncio.to_thread(self._collect_records_blocking, timeout_seconds)

    def _collect_records_blocking(self, timeout_seconds: float) -> list[ServiceRecord]:
        library = _load_system_library()
        instances = self._browse_instances(library, timeout_seconds)
        return self._resolve_instances(library, instances)

    def _browse_instances(self, library: ctypes.CDLL, timeout_seconds: float) -> list[_ServiceInstance]:
        instances: dict[tuple[int, bytes], _ServiceInstance] = {}

        def on_browse_reply(*arguments: Any) -> None:
            reply = _BrowseReply(*arguments)
            if reply.error_code != NO_ERROR:
                logger.info("DNS-SD browse reported error %s", reply.error_code)
                return
            instance_key = (reply.interface_index, reply.service_name)
            if reply.flags & BROWSE_FLAG_ADD:
                instances[instance_key] = _ServiceInstance(
                    reply.interface_index, reply.service_name, reply.registration_type, reply.reply_domain
                )
            else:
                instances.pop(instance_key, None)

        callback = BrowseReplyCallback(on_browse_reply)
        reference = ServiceReference()
        error_code = library.DNSServiceBrowse(
            ctypes.byref(reference), NO_FLAGS, ANY_INTERFACE_INDEX, SERVICE_TYPE, SERVICE_DOMAIN, callback, None
        )
        if error_code != NO_ERROR:
            raise OSError(f"DNSServiceBrowse failed with DNS-SD error {error_code}")
        try:
            _process_replies(library, [reference], timeout_seconds)
        finally:
            library.DNSServiceRefDeallocate(reference)
        return list(instances.values())

    def _resolve_instances(self, library: ctypes.CDLL, instances: list[_ServiceInstance]) -> list[ServiceRecord]:
        records: list[ServiceRecord] = []
        callbacks = [ResolveReplyCallback(_build_resolve_handler(instance, records)) for instance in instances]
        references: list[ctypes.c_void_p] = []
        try:
            for instance, callback in zip(instances, callbacks, strict=True):
                reference = ServiceReference()
                error_code = library.DNSServiceResolve(
                    ctypes.byref(reference),
                    NO_FLAGS,
                    instance.interface_index,
                    instance.service_name,
                    instance.registration_type,
                    instance.reply_domain,
                    callback,
                    None,
                )
                if error_code == NO_ERROR:
                    references.append(reference)
                else:
                    logger.info("DNSServiceResolve failed for %r: error %s", instance.service_name, error_code)
            _process_replies(library, references, RESOLVE_TIMEOUT_SECONDS)
        finally:
            for reference in references:
                library.DNSServiceRefDeallocate(reference)
        return records

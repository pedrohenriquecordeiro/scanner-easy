import ctypes
import select
import socket
import time

LIBRARY = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
SERVICE_REFERENCE = ctypes.c_void_p
BROWSE_CALLBACK = ctypes.CFUNCTYPE(None, SERVICE_REFERENCE, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_int32,
                                   ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p)
RESOLVE_CALLBACK = ctypes.CFUNCTYPE(None, SERVICE_REFERENCE, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_int32,
                                    ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint16, ctypes.c_uint16,
                                    ctypes.POINTER(ctypes.c_ubyte), ctypes.c_void_p)
LIBRARY.DNSServiceBrowse.argtypes = [ctypes.POINTER(SERVICE_REFERENCE), ctypes.c_uint32, ctypes.c_uint32,
                                     ctypes.c_char_p, ctypes.c_char_p, BROWSE_CALLBACK, ctypes.c_void_p]
LIBRARY.DNSServiceResolve.argtypes = [ctypes.POINTER(SERVICE_REFERENCE), ctypes.c_uint32, ctypes.c_uint32,
                                      ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, RESOLVE_CALLBACK, ctypes.c_void_p]
LIBRARY.DNSServiceRefSockFD.argtypes = [SERVICE_REFERENCE]
LIBRARY.DNSServiceProcessResult.argtypes = [SERVICE_REFERENCE]
LIBRARY.DNSServiceRefDeallocate.argtypes = [SERVICE_REFERENCE]

def pump(reference, seconds):
    descriptor = LIBRARY.DNSServiceRefSockFD(reference)
    deadline = time.monotonic() + seconds
    while (remaining := deadline - time.monotonic()) > 0:
        ready, _, _ = select.select([descriptor], [], [], remaining)
        if ready:
            LIBRARY.DNSServiceProcessResult(reference)

instances = []
def on_browse(reference, flags, interface_index, error_code, name, service_type, domain, context):
    instances.append((interface_index, name, service_type, domain))
browse_callback = BROWSE_CALLBACK(on_browse)
browse_reference = SERVICE_REFERENCE()
print("browse error", LIBRARY.DNSServiceBrowse(ctypes.byref(browse_reference), 0, 0, b"_uscan._tcp", None, browse_callback, None))
pump(browse_reference, 2.0)
LIBRARY.DNSServiceRefDeallocate(browse_reference)

def on_resolve(reference, flags, interface_index, error_code, full_name, host_target, port, text_length, text_record, context):
    text = bytes(text_record[:text_length])
    entries, position = [], 0
    while position < len(text):
        size = text[position]; entries.append(text[position + 1:position + 1 + size].decode(errors="replace")); position += 1 + size
    rs = [entry for entry in entries if entry.lower().startswith(("rs=", "uuid="))]
    print(f"  resolved if={interface_index:#x} host={host_target.decode()} port={socket.ntohs(port)} {rs}")
resolve_callback = RESOLVE_CALLBACK(on_resolve)
for interface_index, name, service_type, domain in instances:
    print("instance", hex(interface_index), name.decode(), service_type.decode(), domain.decode())
    resolve_reference = SERVICE_REFERENCE()
    LIBRARY.DNSServiceResolve(ctypes.byref(resolve_reference), 0, interface_index, name, service_type, domain, resolve_callback, None)
    pump(resolve_reference, 1.5)
    LIBRARY.DNSServiceRefDeallocate(resolve_reference)

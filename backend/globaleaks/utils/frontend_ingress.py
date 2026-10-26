"""Identity received from private, mode-0600 frontend Unix listeners only."""
import ipaddress
import os
import stat

from twisted.internet import address
from twisted.web import server


class FrontendWebRequest(server.Request):
    log_ip_and_ua = False
    frontend_ingress = 'web'

    def isSecure(self):
        # The FE accepts this socket path only after its TLS ingress trust checks.
        return True


class FrontendOnionRequest(server.Request):
    log_ip_and_ua = False
    frontend_ingress = 'onion'


def frontend_socket_paths(directory):
    if not directory or not os.path.isabs(directory):
        raise ValueError('Frontend socket directory must be absolute')
    info = os.lstat(directory)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('Frontend socket directory must be owned by the application UID with mode 0700')
    return tuple(os.path.join(directory, name) for name in ('web.sock', 'onion.sock'))


def request_identity(request, tor_exit_set):
    """Return (IP, Tor flag); never trust proxy headers on a TCP request."""
    ingress = getattr(request, 'frontend_ingress', None)
    if ingress == 'onion':
        return '127.0.0.1', True
    if ingress == 'web':
        values = request.requestHeaders.getRawHeaders(b'x-wbe-client-ip', [])
        if not values and request.path == b'/api/health':
            return '127.0.0.1', False
        if len(values) != 1:
            raise ValueError('Frontend client address is required')
        try:
            value = values[0].decode('ascii') if isinstance(values[0], bytes) else values[0]
            if '%' in value:
                raise ValueError('Scoped address is not a client identity')
            parsed = ipaddress.ip_address(value)
        except (ValueError, UnicodeError):
            raise ValueError('Invalid frontend client address') from None
        if isinstance(parsed, ipaddress.IPv6Address) and parsed.ipv4_mapped:
            parsed = parsed.ipv4_mapped
        value = str(parsed)
        return value, value in tor_exit_set
    client = request.getClientAddress()
    value = client.host if isinstance(client, (address.IPv4Address, address.IPv6Address)) else ''
    if isinstance(value, bytes):
        value = value.decode('ascii')
    if value.startswith('::ffff:'):
        value = value[7:]
    return value, value in tor_exit_set or getattr(request.getHost(), 'port', None) == 8083

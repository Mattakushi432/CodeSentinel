import ipaddress
from urllib.parse import urlparse

_BLOCKED_HOSTNAMES = frozenset({
    "localhost",
    "0.0.0.0",
    "[::]",
    "[::1]",
    "metadata.google.internal",
    "metadata.azure.internal",
    "metadata.ec2.internal",
    "169.254.169.254",
})


def is_ssrf_url(url: str) -> bool:
    """Return True if the URL targets a private/loopback/link-local/reserved address."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return True
        if hostname.lower() in _BLOCKED_HOSTNAMES:
            return True
        try:
            ip = ipaddress.ip_address(hostname)
            return (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
            )
        except ValueError:
            pass
        return False
    except Exception:
        return True

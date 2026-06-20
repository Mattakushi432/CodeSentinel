import ipaddress
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# urlparse strips brackets from IPv6 literals, so hostnames here must NOT include brackets.
_BLOCKED_HOSTNAMES = frozenset({
    "localhost",
    "0.0.0.0",
    "metadata.google.internal",
    "metadata.azure.internal",
    "metadata.ec2.internal",
    "169.254.169.254",
})

_IPV6_UNSPECIFIED = ipaddress.ip_address("::")


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
                or ip == _IPV6_UNSPECIFIED  # :: — version-safe; is_reserved changed in 3.11
            )
        except ValueError:
            pass
        return False
    except Exception as exc:
        logger.warning("SSRF check raised unexpectedly for %r: %s", url, exc)
        return True

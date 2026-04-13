from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

_GENERIC_SUBDOMAINS = {"mcp", "mcp-server", "api", "app", "www"}


class NameDerivationError(Exception):
    pass


def derive_server_name(url: str) -> str:
    hostname = urlparse(url).hostname
    if hostname is None:
        raise NameDerivationError("Invalid URL format")

    if hostname == "localhost" or _is_ip(hostname):
        raise NameDerivationError(
            "Cannot derive a name from the hostname. Please specify --name explicitly"
        )

    labels = hostname.split(".")
    if len(labels) < 2:
        raise NameDerivationError(
            "Cannot derive a name from the hostname. Please specify --name explicitly"
        )

    sld = labels[-2]
    head = labels[0]

    if head != sld and head not in _GENERIC_SUBDOMAINS:
        candidate = head
    else:
        candidate = sld

    candidate = candidate.lower()

    if not candidate or len(candidate) == 1 or candidate.isdigit():
        raise NameDerivationError(
            "Cannot derive a name from the hostname. Please specify --name explicitly"
        )

    return candidate


def _is_ip(hostname: str) -> bool:
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return True

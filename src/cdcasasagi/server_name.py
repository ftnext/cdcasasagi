from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

_GENERIC_SUBDOMAINS = {"mcp", "api", "app", "www"}
_MCP_API_FRAGMENTS = {"mcp", "api"}


class NameDerivationError(Exception):
    pass


def derive_server_name(url: str) -> str:
    hostname = urlparse(url).hostname
    if hostname is None:
        raise NameDerivationError("URL の形式が不正です")

    if hostname == "localhost" or _is_ip(hostname):
        raise NameDerivationError(
            "ホスト名から名前を導出できません。--name を明示してください"
        )

    labels = hostname.split(".")
    if len(labels) < 2:
        raise NameDerivationError(
            "ホスト名から名前を導出できません。--name を明示してください"
        )

    sld = labels[-2]
    head = labels[0]

    if (
        head != sld
        and head not in _GENERIC_SUBDOMAINS
        and not any(frag in head for frag in _MCP_API_FRAGMENTS)
    ):
        candidate = head
    else:
        candidate = sld

    candidate = candidate.lower()

    if not candidate or len(candidate) == 1 or candidate.isdigit():
        raise NameDerivationError(
            "ホスト名から名前を導出できません。--name を明示してください"
        )

    return candidate


def _is_ip(hostname: str) -> bool:
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return True

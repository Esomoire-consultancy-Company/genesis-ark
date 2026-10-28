"""Conservative hostname routing for an owner-verified Knowledge Hub subdomain.

Disabled unless the exact approved hostname is supplied in the environment.
No DNS updates, untrusted proxy hostnames or external redirect targets.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def valid_dns_hostname(name: str) -> bool:
    if not isinstance(name, str) or len(name) > 253 or not name:
        return False
    if name != name.lower() or any(x in name for x in ("/", ":", "@", "?", "#", "\\", " ")):
        return False
    labels = name.split(".")
    return len(labels) >= 2 and all(_LABEL.fullmatch(x) for x in labels)


def knowledge_landing_redirect(request_host: str, request_target: str, approved_host: str) -> str | None:
    """Only redirect the exact approved knowledge host's homepage to /knowledge.

    Location is a fixed relative path, never derived from user-supplied Host.
    Invalid/missing configuration disables routing rather than guessing.
    """
    if not valid_dns_hostname(approved_host):
        return None
    if not isinstance(request_host, str) or not isinstance(request_target, str):
        return None
    try:
        target_path = urlsplit(request_target).path
    except ValueError:
        return None
    if target_path != "/":
        return None
    supplied = request_host.strip().lower()
    if supplied.count(":") == 1:
        hostname, port = supplied.split(":")
        if not port.isdecimal() or not 1 <= int(port) <= 65535:
            return None
    else:
        hostname = supplied
    if hostname != approved_host:
        return None
    return "/knowledge"

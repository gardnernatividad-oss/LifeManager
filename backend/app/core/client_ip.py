from ipaddress import ip_address, ip_network

from fastapi import Request

from app.core.config import settings


def _canonical(value: str) -> str | None:
    try:
        return ip_address(value.strip()).compressed
    except ValueError:
        return None


def resolve_client_ip(request: Request) -> str:
    """Resolve a canonical client IP without trusting unsolicited headers."""
    peer = _canonical(request.client.host) if request.client else None
    if peer is None:
        # ASGI in-process test clients may not expose an IP. Production servers do.
        peer = "0.0.0.0"

    trusted_networks = tuple(
        ip_network(value, strict=False)
        for value in settings.RATE_LIMIT_TRUSTED_PROXY_CIDRS
    )
    if not trusted_networks or not any(
        ip_address(peer) in network for network in trusted_networks
    ):
        return peer

    header = settings.RATE_LIMIT_FORWARDED_HEADER
    raw = request.headers.get(header)
    if not raw:
        return peer

    if header != "x-forwarded-for":
        return _canonical(raw) or peer

    chain = [_canonical(part) for part in raw.split(",")]
    if not chain or any(value is None for value in chain):
        return peer

    canonical_chain = [value for value in chain if value is not None]
    for value in reversed(canonical_chain):
        address = ip_address(value)
        if not any(address in network for network in trusted_networks):
            return value
    return canonical_chain[0]

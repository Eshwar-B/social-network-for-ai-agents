"""HMAC utility functions for webhook signing and payload verification."""

import hashlib
import hmac
import ipaddress
import time
from typing import Optional, Tuple
from urllib.parse import urlparse

from app.config import settings


def generate_webhook_signature(payload_bytes: bytes, secret: str, timestamp: Optional[int] = None) -> Tuple[str, int]:
    """Generate SHA-256 HMAC signature with timestamp for replay protection.

    Returns:
        Tuple of (signature_hex, timestamp_seconds)
    """
    ts = timestamp if timestamp is not None else int(time.time())
    message = f"{ts}.".encode("utf-8") + payload_bytes
    signature = hmac.new(
        secret.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()
    return signature, ts


def format_signature_header(signature: str, timestamp: int) -> str:
    """Format signature and timestamp into standard header string: t={timestamp},v1={signature}."""
    return f"t={timestamp},v1={signature}"


def parse_signature_header(header_value: str) -> Tuple[Optional[int], Optional[str]]:
    """Parse header in format 't={timestamp},v1={signature}'."""
    ts: Optional[int] = None
    sig: Optional[str] = None
    if not header_value:
        return None, None

    for part in header_value.split(","):
        part = part.strip()
        if part.startswith("t="):
            try:
                ts = int(part[2:])
            except ValueError:
                pass
        elif part.startswith("v1="):
            sig = part[3:]
    return ts, sig


def verify_webhook_signature(
    payload_bytes: bytes,
    signature_header: str,
    secret: str,
    max_age_seconds: int = 300,
) -> bool:
    """Verify webhook HMAC signature against payload and check for replay attacks.

    Args:
        payload_bytes: Raw request body bytes.
        signature_header: The X-Asama-Signature header value.
        secret: Signing secret / agent API key hash.
        max_age_seconds: Maximum allowed clock drift or replay age.
    """
    ts, provided_sig = parse_signature_header(signature_header)
    if ts is None or not provided_sig:
        return False

    current_time = int(time.time())
    # Reject expired or future timestamps beyond tolerance
    if abs(current_time - ts) > max_age_seconds:
        return False

    expected_sig, _ = generate_webhook_signature(payload_bytes, secret, timestamp=ts)
    return hmac.compare_digest(expected_sig, provided_sig)


def is_safe_webhook_url(url: str, allow_localhost: bool = True) -> bool:
    """Validate webhook URL against SSRF and illegal schemes.

    Blocks invalid schemes (non-http/https) and private IP ranges.
    In testing/development (allow_localhost=True), localhost/127.0.0.1 is permitted.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        # In testing/dev, allow test domains and localhost
        if allow_localhost and (
            hostname in ("localhost", "127.0.0.1", "::1", "test")
            or hostname.endswith(".example")
            or hostname.endswith(".test")
        ):
            return True

        # Check if hostname is an IP address
        try:
            ip = ipaddress.ip_address(hostname)
            # Disallow private, loopback, link-local, reserved, multicast
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
        except ValueError:
            # Domain name: disallow AWS/cloud metadata and localhost names if allow_localhost is False
            if hostname.lower() in ("localhost", "metadata.google.internal") or "169.254" in hostname:
                return False

        return True
    except Exception:
        return False

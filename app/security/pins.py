"""PIN credentials: HMAC lookup key for kiosk login (no plaintext storage).

PINs are unique **per site** (not globally). Login requires ``site_id`` + the
4-digit code. Lookup uses ``HMAC-SHA256(pin_hmac_secret, f"{site_id}:{pin}")``
hex digest stored in ``site_pins.pin_hmac``. The PIN itself is never stored.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import uuid

from app.config import settings

_PIN_RE = re.compile(r"^\d{4}$")


def pin_hmac_secret() -> str:
    """Secret for PIN HMAC. Prefer dedicated env; else derive from refresh JWT."""
    dedicated = settings.pin_hmac_secret_value()
    if dedicated:
        return dedicated
    # Documented fallback: fixed prefix + refresh secret so PIN material is
    # distinct from refresh-token signing without requiring a new env in dev.
    return f"ceres-pin-hmac:{settings.refresh_jwt_secret_value()}"


def validate_pin(pin: str) -> str:
    if not _PIN_RE.match(pin):
        raise ValueError("PIN must be exactly 4 digits")
    return pin


def hash_pin(pin: str, *, site_id: uuid.UUID) -> str:
    """Return 64-char hex HMAC-SHA256 digest for storage/lookup at a site."""
    validated = validate_pin(pin)
    message = f"{site_id}:{validated}".encode("utf-8")
    digest = hmac.new(
        pin_hmac_secret().encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()
    return digest

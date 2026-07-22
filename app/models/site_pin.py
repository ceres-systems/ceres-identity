"""Site-scoped kiosk PIN credentials (fact: which PIN logs in at which site).

A user may have a different PIN at each site they belong to. Uniqueness is
``(site_id, pin_hmac)`` — the same four digits may be used at another site.
PINs are never stored in plaintext; see ``app.security.pins``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SitePin(Base):
    __tablename__ = "site_pins"
    __table_args__ = (
        UniqueConstraint("site_id", "pin_hmac", name="uq_site_pins_site_pin_hmac"),
    )

    site_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # HMAC-SHA256 hex of site_id + PIN (see security/pins.py).
    pin_hmac: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()  # pylint: disable=not-callable
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),  # pylint: disable=not-callable
        onupdate=func.now(),  # pylint: disable=not-callable
    )

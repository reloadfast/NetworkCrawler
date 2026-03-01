"""Risk ORM model — stores detected misconfiguration findings per device."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.db import Base


class Risk(Base):
    """A detected misconfiguration or security finding on a Device."""

    __tablename__ = "risks"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(
        Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    severity = Column(String, nullable=False)
    # "critical" | "high" | "medium" | "low"
    check_id = Column(String, nullable=False, index=True)
    # Stable identifier for the check, e.g. "telnet_open"
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    detected_at = Column(DateTime, nullable=False, default=func.now())
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_note = Column(String, nullable=True)

    device = relationship("Device", back_populates="risks")

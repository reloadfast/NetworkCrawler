"""Recommendation ORM model — hardening advice linked to a Risk and Device."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.db import Base


class Recommendation(Base):
    """A hardening recommendation derived from a detected Risk."""

    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(
        Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    risk_id = Column(
        Integer, ForeignKey("risks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Mirrors the Risk check_id so recommendations can be looked up without the Risk row
    check_id = Column(String, nullable=False, index=True)
    severity = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    steps = Column(Text, nullable=False)  # JSON-encoded list[str]
    effort = Column(String, nullable=False)  # "low" | "medium" | "high"
    impact = Column(String, nullable=False)  # "low" | "medium" | "high"
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    device = relationship("Device")
    risk = relationship("Risk")

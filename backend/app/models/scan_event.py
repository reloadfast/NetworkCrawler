"""ScanEvent ORM model — one row per notable change detected during a scan."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func

from app.db import Base


class ScanEvent(Base):
    """A change event detected by comparing two consecutive scan snapshots.

    event_type values:
      device_appeared   — a new IP was found on the network
      device_disappeared — a previously-seen IP was not found in this scan
      port_opened       — a port/protocol pair that was not open is now open
      port_closed       — a port/protocol pair that was open is no longer open
      risk_appeared     — a new misconfiguration risk was detected
      risk_resolved     — a previously-detected risk is no longer present
    """

    __tablename__ = "scan_events"

    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("scans.id"), nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True, index=True)
    event_type = Column(String, nullable=False)
    detail = Column(String, nullable=True)  # JSON string with event-specific context
    occurred_at = Column(DateTime, default=func.now())
    reviewed = Column(Boolean, nullable=False, default=False, server_default="0")

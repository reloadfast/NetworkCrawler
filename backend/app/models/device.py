"""Device and Port SQLAlchemy models (stub — full implementation in Phase 2)."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.db import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String, nullable=False, index=True)
    mac_address = Column(String, nullable=True)
    hostname = Column(String, nullable=True)
    os_guess = Column(String, nullable=True)
    first_seen = Column(DateTime, default=func.now())
    last_seen = Column(DateTime, default=func.now(), onupdate=func.now())

    ports = relationship("Port", back_populates="device", cascade="all, delete-orphan")


class Port(Base):
    __tablename__ = "ports"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    port_number = Column(Integer, nullable=False)
    protocol = Column(String, nullable=False, default="tcp")
    service_name = Column(String, nullable=True)
    version_banner = Column(String, nullable=True)

    device = relationship("Device", back_populates="ports")

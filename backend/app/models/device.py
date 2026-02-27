"""Device and Port SQLAlchemy ORM models."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.db import Base


class Device(Base):
    """A network device discovered by arp-scan and/or nmap."""

    __tablename__ = "devices"
    __table_args__ = (
        # One row per IP address — upserts update in place rather than inserting duplicates.
        UniqueConstraint("ip_address", name="uq_devices_ip_address"),
    )

    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String, nullable=False, index=True)
    mac_address = Column(String, nullable=True)
    vendor = Column(String, nullable=True)  # hardware vendor from arp-scan OUI lookup
    hostname = Column(String, nullable=True)
    os_guess = Column(String, nullable=True)
    first_seen = Column(DateTime, default=func.now())
    last_seen = Column(DateTime, default=func.now(), onupdate=func.now())

    ports = relationship("Port", back_populates="device", cascade="all, delete-orphan")
    risks = relationship("Risk", back_populates="device", cascade="all, delete-orphan")


class Port(Base):
    """An open TCP/UDP port observed on a Device during an nmap scan."""

    __tablename__ = "ports"
    __table_args__ = (
        # One row per (device, port, protocol) tuple.
        UniqueConstraint("device_id", "port_number", "protocol", name="uq_ports_device_port_proto"),
    )

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    port_number = Column(Integer, nullable=False)
    protocol = Column(String, nullable=False, default="tcp")
    service_name = Column(String, nullable=True)
    version_banner = Column(String, nullable=True)

    device = relationship("Device", back_populates="ports")

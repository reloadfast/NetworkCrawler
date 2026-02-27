"""Scan history ORM model."""

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, func

from app.db import Base


class Scan(Base):
    """Record of one full scan cycle (scheduled or manual)."""

    __tablename__ = "scans"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String, nullable=False, default="running")
    # "running" | "completed" | "failed"
    triggered_by = Column(String, nullable=False, default="scheduler")
    # "scheduler" | "manual"
    started_at = Column(DateTime, nullable=False, default=func.now())
    finished_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    devices_found = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

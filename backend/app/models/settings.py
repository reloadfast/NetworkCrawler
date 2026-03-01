"""AppSetting ORM model — simple key/value store for application configuration."""

from sqlalchemy import Column, String, Text

from app.db import Base


class AppSetting(Base):
    """A single persisted application setting."""

    __tablename__ = "app_settings"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=True)

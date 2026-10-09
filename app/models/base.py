from datetime import datetime, timezone

from sqlalchemy import Column, DateTime


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def created_at_column() -> Column:
    return Column(DateTime(timezone=True), nullable=False, default=utcnow)


def updated_at_column() -> Column:
    return Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

"""SQLAlchemy model for Person."""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, JSON, String

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Person(Base):
    __tablename__ = "persons"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    birth_year = Column(Integer, nullable=True)
    generation = Column(Integer, nullable=False)
    role = Column(String(100), default="Medlem")
    relation = Column(String(200), nullable=True)
    description = Column(String(500), nullable=True)
    parents = Column(JSON, default=list)
    children = Column(JSON, default=list)
    spouses = Column(JSON, default=list)
    rsvp_status = Column(String(20), nullable=False, default="pending")
    rsvp_token = Column(String(64), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

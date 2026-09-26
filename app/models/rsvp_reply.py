"""SQLAlchemy model for RsvpReply (contact info submitted with an RSVP)."""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RsvpReply(Base):
    __tablename__ = "rsvp_replies"

    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False, index=True)
    status = Column(String(20), nullable=False)
    email = Column(String(300), nullable=False)
    phone = Column(String(50), nullable=True)
    notes = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=_utcnow)

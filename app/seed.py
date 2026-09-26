"""Seed the persons table with the Släktträff family tree.

Runs once on startup when the table is empty. Family data lives in
data/family.json (gitignored — real names are personal data and must not
enter the public repo). data/family.json.example shows the shape.
"""
import json
import logging
from pathlib import Path

from app.database import SessionLocal
from app.models.person import Person
from app.schemas.enums import RsvpStatus

logger = logging.getLogger("slakttraff.seed")

_FAMILY_FILE = Path(__file__).resolve().parent.parent / "data" / "family.json"


def _load_family() -> list[dict]:
    """Load the family tree from data/family.json ([] when the file is missing)."""
    if not _FAMILY_FILE.exists():
        logger.warning(
            "data/family.json is missing — seeding an EMPTY tree. Copy "
            "data/family.json.example to data/family.json to load real family data."
        )
        return []
    with _FAMILY_FILE.open(encoding="utf-8") as fh:
        return json.load(fh)


def seed_persons_if_empty() -> int:
    """Insert the family tree once, when the persons table is empty.

    Returns the number of persons inserted (0 when the table already has data
    or the family file is missing).
    """
    family = _load_family()
    if not family:
        return 0
    db = SessionLocal()
    try:
        if db.query(Person).count() > 0:
            return 0
        ids = {}
        for entry in family:
            person = Person(
                name=entry["name"],
                generation=entry["generation"],
                role=entry.get("role", "Medlem"),
                relation=entry.get("relation"),
                description=entry.get("description"),
                parents=[],
                children=[],
                spouses=[],
                rsvp_status=RsvpStatus.PENDING.value,
                rsvp_token=entry["key"],  # legacy column, no longer gated on
            )
            db.add(person)
            db.flush()
            ids[entry["key"]] = person.id
        for entry in family:
            person = db.query(Person).filter(Person.id == ids[entry["key"]]).first()
            person.parents = [ids[p] for p in entry.get("parents", [])]
            for p in entry.get("parents", []):
                child = db.query(Person).filter(Person.id == ids[p]).first()
                child.children = list(child.children or []) + [ids[entry["key"]]]
        db.commit()
        return len(family)
    finally:
        db.close()

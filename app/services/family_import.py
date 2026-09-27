"""Family-tree import: insert family.json-style entries as Person rows.

Shared by the startup seed (app/seed.py) and the admin import endpoint
(app/routers/admin.py). The caller owns the transaction: rows are flushed,
not committed, so an import can run together with other writes atomically.
"""
from typing import List

from sqlalchemy.orm import Session

from app.models.person import Person
from app.schemas.enums import RsvpStatus


def import_family(db: Session, family_entries: List[dict]) -> int:
    """Insert one Person per family entry and wire parents/children.

    Entries are dicts with "key", "name", "generation" and optional
    "role", "relation", "description", "parents" (list of keys). Keys must
    be unique and every parents entry must reference a key in the list.
    Returns the number of persons inserted. Does NOT commit — the caller
    commits (or rolls back) the transaction.
    """
    ids = {}
    for entry in family_entries:
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
    for entry in family_entries:
        person = db.query(Person).filter(Person.id == ids[entry["key"]]).first()
        person.parents = [ids[p] for p in entry.get("parents", [])]
        for p in entry.get("parents", []):
            child = db.query(Person).filter(Person.id == ids[p]).first()
            child.children = list(child.children or []) + [ids[entry["key"]]]
    return len(family_entries)

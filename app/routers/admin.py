"""Admin-only family import: replace the whole person table from a POSTed
family.json-style entry list (the way a running deployment gets the real,
gitignored family data without PII entering the repo)."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_admin_token
from app.database import get_db
from app.models.person import Person
from app.models.registration import Registration
from app.models.rsvp_reply import RsvpReply
from app.services.family_import import import_family

router = APIRouter(prefix="/api/admin", tags=["admin"],
                   dependencies=[Depends(require_admin_token)])

_REQUIRED_FIELDS = ("key", "name", "generation")


def _validate_entries(entries: List[dict]) -> None:
    """Reject entries that would crash or corrupt the import (422, not 500).

    Each entry must be an object with a non-empty string "key", a non-empty
    string "name", an int "generation" and an optional "parents" list of
    known keys. Optional "role", "relation" and "description", when present,
    must be strings (or null) so they never reach the ORM type-wrong. An
    empty list is rejected with 400 by the endpoint: a
    replace-all import of nothing would wipe the tree and let the startup
    seed resurrect stale data on the next restart.
    """
    keys = set()
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise HTTPException(status_code=422, detail=f"Entry {i} is not an object")
        for field in _REQUIRED_FIELDS:
            if field not in entry:
                raise HTTPException(status_code=422,
                                    detail=f"Entry {i} is missing '{field}'")
        if not isinstance(entry["key"], str) or not entry["key"]:
            raise HTTPException(status_code=422,
                                detail=f"Entry {i} has a non-string or empty 'key'")
        if not isinstance(entry["name"], str) or not entry["name"]:
            raise HTTPException(status_code=422,
                                detail=f"Entry {i} has a non-string or empty 'name'")
        if not isinstance(entry["generation"], int) or isinstance(entry["generation"], bool):
            raise HTTPException(status_code=422,
                                detail=f"Entry {i} has a non-int 'generation'")
        if entry["key"] in keys:
            raise HTTPException(status_code=422,
                                detail=f"Duplicate key '{entry['key']}'")
        keys.add(entry["key"])
        for field in ("role", "relation", "description"):
            if field in entry and entry[field] is not None \
                    and not isinstance(entry[field], str):
                raise HTTPException(
                    status_code=422,
                    detail=f"Entry {i} has a non-string '{field}'")
    for i, entry in enumerate(entries):
        parents = entry.get("parents", [])
        if not isinstance(parents, list) or not all(isinstance(p, str) for p in parents):
            raise HTTPException(status_code=422,
                                detail=f"Entry {i} has a non-list 'parents'")
        for p in parents:
            if p not in keys:
                raise HTTPException(status_code=422,
                                    detail=f"Entry {i} references unknown parent '{p}'")


@router.post("/import-family")
def import_family_endpoint(entries: List[dict], db: Session = Depends(get_db)):
    """Replace-all import: delete existing persons (and their RSVP replies),
    then insert the posted entry list in one transaction."""
    if entries == []:
        raise HTTPException(status_code=400,
                            detail="An empty import would wipe the family tree; "
                                   "post at least one entry")
    _validate_entries(entries)
    # Null out registration links BEFORE deleting persons so no orphaned
    # registrations.person_id FK values survive the replace-all (the live DB
    # persists across deploys with no shell access to repair them).
    db.query(Registration).update({Registration.person_id: None})
    db.query(RsvpReply).delete()
    db.query(Person).delete()
    count = import_family(db, entries)
    db.commit()
    return {"imported": count}

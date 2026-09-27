"""Admin-only family import: replace the whole person table from a POSTed
family.json-style entry list (the way a running deployment gets the real,
gitignored family data without PII entering the repo)."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_admin_token
from app.database import get_db
from app.models.person import Person
from app.models.rsvp_reply import RsvpReply
from app.services.family_import import import_family

router = APIRouter(prefix="/api/admin", tags=["admin"],
                   dependencies=[Depends(require_admin_token)])

_REQUIRED_FIELDS = ("key", "name", "generation")


def _validate_entries(entries: List[dict]) -> None:
    """Reject entries that would crash or corrupt the import (422, not 500)."""
    keys = set()
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise HTTPException(status_code=422, detail=f"Entry {i} is not an object")
        for field in _REQUIRED_FIELDS:
            if field not in entry:
                raise HTTPException(status_code=422,
                                    detail=f"Entry {i} is missing '{field}'")
        if entry["key"] in keys:
            raise HTTPException(status_code=422,
                                detail=f"Duplicate key '{entry['key']}'")
        keys.add(entry["key"])
    for i, entry in enumerate(entries):
        for p in entry.get("parents", []):
            if p not in keys:
                raise HTTPException(status_code=422,
                                    detail=f"Entry {i} references unknown parent '{p}'")


@router.post("/import-family")
def import_family_endpoint(entries: List[dict], db: Session = Depends(get_db)):
    """Replace-all import: delete existing persons (and their RSVP replies),
    then insert the posted entry list in one transaction."""
    _validate_entries(entries)
    db.query(RsvpReply).delete()
    db.query(Person).delete()
    count = import_family(db, entries)
    db.commit()
    return {"imported": count}

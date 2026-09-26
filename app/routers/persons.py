"""Person CRUD + RSVP endpoints."""
import secrets
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_token
from app.database import get_db
from app.models.person import Person
from app.models.rsvp_reply import RsvpReply
from app.schemas.enums import RsvpStatus
from app.schemas.person import PersonCreate, PersonResponse, PersonUpdate, RsvpSubmit

router = APIRouter(
    prefix="/api/persons", tags=["persons"], dependencies=[Depends(require_token)]
)


@router.post("/", response_model=PersonResponse, status_code=status.HTTP_201_CREATED)
def create_person(person: PersonCreate, db: Session = Depends(get_db)):
    db_person = Person(
        name=person.name,
        birth_year=person.birth_year,
        generation=person.generation.value,
        role=person.role,
        relation=person.relation,
        description=person.description,
        parents=person.parents,
        children=person.children,
        spouses=person.spouses,
        rsvp_status=RsvpStatus.PENDING.value,
        rsvp_token=secrets.token_urlsafe(24),
    )
    db.add(db_person)
    db.commit()
    db.refresh(db_person)
    return db_person


@router.get("/", response_model=List[PersonResponse])
def list_persons(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Person).offset(skip).limit(limit).all()


@router.get("/{person_id}", response_model=PersonResponse)
def get_person(person_id: int, db: Session = Depends(get_db)):
    db_person = db.query(Person).filter(Person.id == person_id).first()
    if db_person is None:
        raise HTTPException(status_code=404, detail="Person not found")
    return db_person


@router.put("/{person_id}", response_model=PersonResponse)
def update_person(person_id: int, person_update: PersonUpdate, db: Session = Depends(get_db)):
    db_person = db.query(Person).filter(Person.id == person_id).first()
    if db_person is None:
        raise HTTPException(status_code=404, detail="Person not found")

    for field, value in person_update.model_dump(exclude_unset=True).items():
        setattr(db_person, field, value)

    db.commit()
    db.refresh(db_person)
    return db_person


@router.delete("/{person_id}", status_code=status.HTTP_200_OK)
def delete_person(person_id: int, db: Session = Depends(get_db)):
    db_person = db.query(Person).filter(Person.id == person_id).first()
    if db_person is None:
        raise HTTPException(status_code=404, detail="Person not found")
    db.delete(db_person)
    db.commit()
    return {"message": "Person deleted"}


@router.post("/{person_id}/rsvp", response_model=PersonResponse)
def submit_rsvp(person_id: int, rsvp: RsvpSubmit, db: Session = Depends(get_db)):
    """Accept or decline the invitation, storing the submitted contact info."""
    db_person = db.query(Person).filter(Person.id == person_id).first()
    if db_person is None:
        raise HTTPException(status_code=404, detail="Person not found")
    if rsvp.status == RsvpStatus.PENDING:
        raise HTTPException(status_code=422, detail="RSVP must be accepted or declined")

    db_person.rsvp_status = rsvp.status.value
    db.add(RsvpReply(
        person_id=person_id,
        status=rsvp.status.value,
        email=rsvp.email,
        phone=rsvp.phone,
        notes=rsvp.notes,
    ))
    db.commit()
    db.refresh(db_person)
    return db_person

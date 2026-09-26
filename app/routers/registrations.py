"""Registration CRUD endpoints."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_admin_token, require_token
from app.database import get_db
from app.models.registration import Registration
from app.schemas.registration import (
    RegistrationCreate,
    RegistrationResponse,
    RegistrationUpdate,
)

router = APIRouter(
    prefix="/api/registrations", tags=["registrations"], dependencies=[Depends(require_token)]
)


@router.post("/", response_model=RegistrationResponse, status_code=status.HTTP_201_CREATED)
def create_registration(reg: RegistrationCreate, db: Session = Depends(get_db)):
    db_reg = Registration(
        name=reg.name,
        email=reg.email,
        generations=[g.value for g in reg.generations],
        group_size=reg.group_size.value,
        notes=reg.notes,
    )
    db.add(db_reg)
    db.commit()
    db.refresh(db_reg)
    return db_reg


@router.get("/", response_model=List[RegistrationResponse],
            dependencies=[Depends(require_admin_token)])
def list_registrations(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Admin view: registrations carry contact info, so listing them needs an
    admin token (the public signup form itself is POST, site token only)."""
    return db.query(Registration).offset(skip).limit(limit).all()


@router.get("/{reg_id}", response_model=RegistrationResponse,
            dependencies=[Depends(require_admin_token)])
def get_registration(reg_id: int, db: Session = Depends(get_db)):
    db_reg = db.query(Registration).filter(Registration.id == reg_id).first()
    if db_reg is None:
        raise HTTPException(status_code=404, detail="Registration not found")
    return db_reg


@router.put("/{reg_id}", response_model=RegistrationResponse,
            dependencies=[Depends(require_admin_token)])
def update_registration(reg_id: int, reg_update: RegistrationUpdate, db: Session = Depends(get_db)):
    db_reg = db.query(Registration).filter(Registration.id == reg_id).first()
    if db_reg is None:
        raise HTTPException(status_code=404, detail="Registration not found")

    update_data = reg_update.model_dump(exclude_unset=True)
    if "generations" in update_data:
        update_data["generations"] = [g.value if hasattr(g, "value") else g
                                      for g in update_data["generations"]]
    if "group_size" in update_data and hasattr(update_data["group_size"], "value"):
        update_data["group_size"] = update_data["group_size"].value
    for field, value in update_data.items():
        setattr(db_reg, field, value)

    db.commit()
    db.refresh(db_reg)
    return db_reg


@router.delete("/{reg_id}", status_code=status.HTTP_200_OK,
               dependencies=[Depends(require_admin_token)])
def delete_registration(reg_id: int, db: Session = Depends(get_db)):
    db_reg = db.query(Registration).filter(Registration.id == reg_id).first()
    if db_reg is None:
        raise HTTPException(status_code=404, detail="Registration not found")
    db.delete(db_reg)
    db.commit()
    return {"message": "Registration deleted"}

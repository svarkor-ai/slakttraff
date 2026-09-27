"""Registration schemas for Släktträff 2026."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.enums import Generation, GroupSize


class RegistrationBase(BaseModel):
    """Shared fields for Registration models."""

    name: str = Field(..., min_length=1, max_length=200, description="Registrant full name")
    email: EmailStr = Field(..., max_length=300, description="Contact email address")
    generations: list[Generation] = Field(
        ..., min_length=1, max_length=5, description="Which generations the registrant belongs to"
    )
    group_size: GroupSize = Field(..., description="Number of people in the registrant's group")
    notes: Optional[str] = Field(
        None, max_length=1000, description="Allergies, dietary preferences, special requests"
    )

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name must not be blank")
        return v.strip()

    @field_validator("generations")
    @classmethod
    def generations_unique(cls, v: list[Generation]) -> list[Generation]:
        if len(v) != len(set(v)):
            raise ValueError("Generations must be unique")
        return sorted(v, key=lambda g: g.value)


class RegistrationCreate(RegistrationBase):
    """Input schema for creating a Registration."""


class RegistrationUpdate(BaseModel):
    """Partial update schema for Registration (all fields optional)."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    email: Optional[EmailStr] = Field(None, max_length=300)
    generations: Optional[list[Generation]] = Field(None, min_length=1, max_length=5)
    group_size: Optional[GroupSize] = None
    notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("Name must not be blank")
        return v.strip() if v else v

    @field_validator("generations")
    @classmethod
    def generations_unique(cls, v: Optional[list[Generation]]) -> Optional[list[Generation]]:
        if v is not None:
            if len(v) != len(set(v)):
                raise ValueError("Generations must be unique")
            return sorted(v, key=lambda g: g.value)
        return v


class Registration(RegistrationBase):
    """Full Registration model with ID and timestamp."""

    id: int = Field(..., description="Unique registration ID")
    person_id: Optional[int] = Field(
        None, description="Family-tree person created from this registration"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Registration timestamp"
    )

    model_config = {"frozen": True}


class RegistrationResponse(Registration):
    """API response schema for Registration."""

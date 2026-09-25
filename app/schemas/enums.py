"""Shared enums for Släktträff schemas."""
from enum import Enum


class Generation(int, Enum):
    """Valid generation numbers in the family tree."""

    G1 = 1
    G2 = 2
    G3 = 3
    G4 = 4
    G5 = 5


class GroupSize(str, Enum):
    """Valid group sizes for event registration."""

    ONE = "1"
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX_PLUS = "6+"


class RsvpStatus(str, Enum):
    """RSVP state for a family-tree spot."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"

"""Database configuration for Släktträff 2026."""
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# DB lives inside the project tree (survives reboots), overridable via env.
_DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "slakttraff.db"
DATABASE_URL = os.environ.get("SLAKTTRAFF_DATABASE_URL", f"sqlite:///{_DEFAULT_DB}")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

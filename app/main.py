"""FastAPI application for Släktträff 2026."""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import persons, registrations

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Släktträff 2026 API",
    description="API for family tree and registration management",
    version="1.1.0",
)

# CORS: explicit origins only (comma-separated env), never wildcard + credentials.
_origins = [o.strip() for o in os.environ.get("SLAKTTRAFF_CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Include routers
app.include_router(persons.router)
app.include_router(registrations.router)


@app.get("/health")
def health_check():
    return {"status": "ok", "app": "Släktträff 2026"}


@app.get("/")
def root():
    return {"message": "Welcome to Släktträff 2026 API"}

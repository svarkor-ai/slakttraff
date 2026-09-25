"""Contract tests for the Släktträff API (persons, registrations, RSVP)."""
import os
import tempfile

# Isolate the test DB before app import.
_TMPDIR = tempfile.mkdtemp(prefix="slakttraff-test-")
os.environ["SLAKTTRAFF_DATABASE_URL"] = f"sqlite:///{_TMPDIR}/test.db"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def _person_payload(**overrides):
    payload = {
        "name": "Erik Andersson",
        "birth_year": 1938,
        "generation": 1,
        "role": "Grundare",
        "relation": None,
        "description": "Släktens grundare",
    }
    payload.update(overrides)
    return payload


def _registration_payload(**overrides):
    payload = {
        "name": "Karin Larsson",
        "email": "karin@example.se",
        "generations": [2, 3],
        "group_size": "2",
        "notes": "Glutenfri",
    }
    payload.update(overrides)
    return payload


# --- health ---

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# --- persons: valid transitions ---

def test_person_create_and_get():
    r = client.post("/api/persons/", json=_person_payload())
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Erik Andersson"
    assert body["rsvp_status"] == "pending"
    assert "rsvp_token" not in body  # token must never be exposed
    r2 = client.get(f"/api/persons/{body['id']}")
    assert r2.status_code == 200
    assert r2.json()["id"] == body["id"]


def test_person_list():
    client.post("/api/persons/", json=_person_payload(name="Lista Test"))
    r = client.get("/api/persons/")
    assert r.status_code == 200
    assert any(p["name"] == "Lista Test" for p in r.json())


def test_person_update_partial():
    pid = client.post("/api/persons/", json=_person_payload()).json()["id"]
    r = client.put(f"/api/persons/{pid}", json={"role": "Barn"})
    assert r.status_code == 200
    assert r.json()["role"] == "Barn"
    assert r.json()["name"] == "Erik Andersson"  # untouched field preserved


def test_person_delete():
    pid = client.post("/api/persons/", json=_person_payload()).json()["id"]
    assert client.delete(f"/api/persons/{pid}").status_code == 200
    assert client.get(f"/api/persons/{pid}").status_code == 404


# --- persons: negative cases ---

def test_person_rejects_blank_name():
    r = client.post("/api/persons/", json=_person_payload(name="   "))
    assert r.status_code == 422


def test_person_rejects_bad_birth_year():
    r = client.post("/api/persons/", json=_person_payload(birth_year=1800))
    assert r.status_code == 422


def test_person_rejects_bad_generation():
    r = client.post("/api/persons/", json=_person_payload(generation=9))
    assert r.status_code == 422


def test_person_get_unknown_returns_404():
    assert client.get("/api/persons/99999").status_code == 404


# --- RSVP ---

def test_rsvp_accept_turns_status_accepted():
    pid = client.post("/api/persons/", json=_person_payload()).json()["id"]
    # token is per-person and not exposed; fetch it from the DB via the app session
    from app.database import SessionLocal
    from app.models.person import Person
    db = SessionLocal()
    token = db.query(Person).filter(Person.id == pid).first().rsvp_token
    db.close()

    r = client.post(f"/api/persons/{pid}/rsvp", json={"token": token, "status": "accepted"})
    assert r.status_code == 200
    assert r.json()["rsvp_status"] == "accepted"

    r2 = client.post(f"/api/persons/{pid}/rsvp", json={"token": token, "status": "declined"})
    assert r2.status_code == 200
    assert r2.json()["rsvp_status"] == "declined"


def test_rsvp_rejects_wrong_token():
    pid = client.post("/api/persons/", json=_person_payload()).json()["id"]
    r = client.post(f"/api/persons/{pid}/rsvp", json={"token": "x" * 24, "status": "accepted"})
    assert r.status_code == 403


def test_rsvp_rejects_pending():
    pid = client.post("/api/persons/", json=_person_payload()).json()["id"]
    from app.database import SessionLocal
    from app.models.person import Person
    db = SessionLocal()
    token = db.query(Person).filter(Person.id == pid).first().rsvp_token
    db.close()
    r = client.post(f"/api/persons/{pid}/rsvp", json={"token": token, "status": "pending"})
    assert r.status_code == 422


def test_rsvp_unknown_person_404():
    r = client.post("/api/persons/99999/rsvp", json={"token": "x" * 24, "status": "accepted"})
    assert r.status_code == 404


# --- registrations ---

def test_registration_create_and_list():
    r = client.post("/api/registrations/", json=_registration_payload())
    assert r.status_code == 201
    assert r.json()["group_size"] == "2"
    r2 = client.get("/api/registrations/")
    assert any(x["email"] == "karin@example.se" for x in r2.json())


def test_registration_rejects_duplicate_generations():
    r = client.post("/api/registrations/", json=_registration_payload(generations=[2, 2]))
    assert r.status_code == 422


def test_registration_rejects_invalid_email():
    r = client.post("/api/registrations/", json=_registration_payload(email="not-an-email"))
    assert r.status_code == 422


def test_registration_rejects_empty_generations():
    r = client.post("/api/registrations/", json=_registration_payload(generations=[]))
    assert r.status_code == 422


def test_registration_update_and_delete():
    rid = client.post("/api/registrations/", json=_registration_payload()).json()["id"]
    r = client.put(f"/api/registrations/{rid}", json={"notes": "Vegan", "group_size": "3"})
    assert r.status_code == 200
    assert r.json()["notes"] == "Vegan"
    assert r.json()["group_size"] == "3"
    assert client.delete(f"/api/registrations/{rid}").status_code == 200
    assert client.get(f"/api/registrations/{rid}").status_code == 404

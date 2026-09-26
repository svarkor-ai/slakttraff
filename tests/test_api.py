"""Contract tests for the Släktträff API (auth, persons, registrations, RSVP)."""
import os
import tempfile

# Isolate the test DB before app import.
_TMPDIR = tempfile.mkdtemp(prefix="slakttraff-test-")
os.environ["SLAKTTRAFF_DATABASE_URL"] = f"sqlite:///{_TMPDIR}/test.db"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)

SITE_PASSWORD = "sibbamala"  # default; tests run without SITE_PASSWORD set


def _auth_headers():
    r = client.post("/api/auth", json={"password": SITE_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


AUTH = _auth_headers()


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


def _rsvp_payload(**overrides):
    payload = {
        "status": "accepted",
        "email": "invitee@example.se",
        "phone": "070-123 45 67",
        "notes": "Tar med tårta",
    }
    payload.update(overrides)
    return payload


# --- health (public) ---

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# --- password gate ---

def test_auth_wrong_password_rejected():
    r = client.post("/api/auth", json={"password": "wrong"})
    assert r.status_code == 403
    assert "token" not in r.json()


def test_auth_empty_password_rejected():
    r = client.post("/api/auth", json={"password": ""})
    assert r.status_code == 422


def test_auth_correct_password_returns_token():
    r = client.post("/api/auth", json={"password": SITE_PASSWORD})
    assert r.status_code == 200
    token = r.json()["token"]
    assert isinstance(token, str) and len(token) >= 32


def test_api_requires_token():
    assert client.get("/api/persons/").status_code == 401
    assert client.get("/api/registrations/").status_code == 401
    assert client.get("/api/rsvp-replies/").status_code == 401
    assert client.post("/api/persons/", json=_person_payload()).status_code == 401


def test_api_rejects_bad_token():
    r = client.get("/api/persons/", headers={"Authorization": "Bearer not-a-token"})
    assert r.status_code == 401


def test_root_serves_password_screen():
    r = client.get("/")
    assert r.status_code == 200
    assert "password-screen" in r.text
    assert "Släktträff i Sibbamåla hembygdsförening, datum annonseras snart" in r.text


# --- persons: valid transitions ---

def test_person_create_and_get():
    r = client.post("/api/persons/", json=_person_payload(), headers=AUTH)
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Erik Andersson"
    assert body["rsvp_status"] == "pending"
    assert "rsvp_token" not in body  # token must never be exposed
    r2 = client.get(f"/api/persons/{body['id']}", headers=AUTH)
    assert r2.status_code == 200
    assert r2.json()["id"] == body["id"]


def test_person_list():
    client.post("/api/persons/", json=_person_payload(name="Lista Test"), headers=AUTH)
    r = client.get("/api/persons/", headers=AUTH)
    assert r.status_code == 200
    assert any(p["name"] == "Lista Test" for p in r.json())


def test_person_update_partial():
    pid = client.post("/api/persons/", json=_person_payload(), headers=AUTH).json()["id"]
    r = client.put(f"/api/persons/{pid}", json={"role": "Barn"}, headers=AUTH)
    assert r.status_code == 200
    assert r.json()["role"] == "Barn"
    assert r.json()["name"] == "Erik Andersson"  # untouched field preserved


def test_person_delete():
    pid = client.post("/api/persons/", json=_person_payload(), headers=AUTH).json()["id"]
    assert client.delete(f"/api/persons/{pid}", headers=AUTH).status_code == 200
    assert client.get(f"/api/persons/{pid}", headers=AUTH).status_code == 404


# --- persons: negative cases ---

def test_person_rejects_blank_name():
    r = client.post("/api/persons/", json=_person_payload(name="   "), headers=AUTH)
    assert r.status_code == 422


def test_person_rejects_bad_birth_year():
    r = client.post("/api/persons/", json=_person_payload(birth_year=1800), headers=AUTH)
    assert r.status_code == 422


def test_person_rejects_bad_generation():
    r = client.post("/api/persons/", json=_person_payload(generation=9), headers=AUTH)
    assert r.status_code == 422


def test_person_get_unknown_returns_404():
    assert client.get("/api/persons/99999", headers=AUTH).status_code == 404


# --- RSVP (password-gated, with contact info) ---

def test_rsvp_requires_token():
    pid = client.post("/api/persons/", json=_person_payload(), headers=AUTH).json()["id"]
    r = client.post(f"/api/persons/{pid}/rsvp", json=_rsvp_payload())
    assert r.status_code == 401


def test_rsvp_accept_and_change_with_contact():
    pid = client.post("/api/persons/", json=_person_payload(), headers=AUTH).json()["id"]
    r = client.post(f"/api/persons/{pid}/rsvp", json=_rsvp_payload(), headers=AUTH)
    assert r.status_code == 200
    assert r.json()["rsvp_status"] == "accepted"

    r2 = client.post(
        f"/api/persons/{pid}/rsvp",
        json=_rsvp_payload(status="declined", email="other@example.se"),
        headers=AUTH,
    )
    assert r2.status_code == 200
    assert r2.json()["rsvp_status"] == "declined"

    # Both replies are stored with their contact info (admin view).
    replies = client.get("/api/rsvp-replies/", headers=AUTH).json()
    mine = [x for x in replies if x["person_id"] == pid]
    assert len(mine) == 2
    assert mine[0]["email"] == "invitee@example.se"
    assert mine[0]["phone"] == "070-123 45 67"
    assert mine[1]["email"] == "other@example.se"


def test_rsvp_requires_email():
    pid = client.post("/api/persons/", json=_person_payload(), headers=AUTH).json()["id"]
    payload = _rsvp_payload()
    del payload["email"]
    r = client.post(f"/api/persons/{pid}/rsvp", json=payload, headers=AUTH)
    assert r.status_code == 422


def test_rsvp_rejects_invalid_email():
    pid = client.post("/api/persons/", json=_person_payload(), headers=AUTH).json()["id"]
    r = client.post(
        f"/api/persons/{pid}/rsvp", json=_rsvp_payload(email="not-an-email"), headers=AUTH
    )
    assert r.status_code == 422


def test_rsvp_optional_fields_default_null():
    pid = client.post("/api/persons/", json=_person_payload(), headers=AUTH).json()["id"]
    r = client.post(
        f"/api/persons/{pid}/rsvp",
        json={"status": "accepted", "email": "minimal@example.se"},
        headers=AUTH,
    )
    assert r.status_code == 200
    replies = client.get("/api/rsvp-replies/", headers=AUTH).json()
    mine = [x for x in replies if x["person_id"] == pid]
    assert mine and mine[0]["phone"] is None and mine[0]["notes"] is None


def test_rsvp_rejects_pending():
    pid = client.post("/api/persons/", json=_person_payload(), headers=AUTH).json()["id"]
    r = client.post(
        f"/api/persons/{pid}/rsvp", json=_rsvp_payload(status="pending"), headers=AUTH
    )
    assert r.status_code == 422


def test_rsvp_rejects_invalid_status():
    pid = client.post("/api/persons/", json=_person_payload(), headers=AUTH).json()["id"]
    r = client.post(
        f"/api/persons/{pid}/rsvp", json=_rsvp_payload(status="maybe"), headers=AUTH
    )
    assert r.status_code == 422


def test_rsvp_rejects_missing_status():
    pid = client.post("/api/persons/", json=_person_payload(), headers=AUTH).json()["id"]
    payload = _rsvp_payload()
    del payload["status"]
    r = client.post(f"/api/persons/{pid}/rsvp", json=payload, headers=AUTH)
    assert r.status_code == 422


def test_rsvp_unknown_person_404():
    r = client.post("/api/persons/99999/rsvp", json=_rsvp_payload(), headers=AUTH)
    assert r.status_code == 404


def test_person_list_includes_rsvp_status():
    pid = client.post(
        "/api/persons/", json=_person_payload(name="Status Test"), headers=AUTH
    ).json()["id"]
    client.post(f"/api/persons/{pid}/rsvp", json=_rsvp_payload(), headers=AUTH)
    r = client.get("/api/persons/", headers=AUTH)
    assert r.status_code == 200
    match = [p for p in r.json() if p["id"] == pid]
    assert match and match[0]["rsvp_status"] == "accepted"


# --- frontend serving (one origin) ---

def test_root_serves_tree_page():
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "/api.js" in r.text and "/tree.js" in r.text


def test_static_assets_served():
    for path in ("/style.css", "/tree.css", "/forms.css", "/api.js", "/tree.js", "/app.js"):
        r = client.get(path)
        assert r.status_code == 200, path


# --- registrations ---

def test_registration_create_and_list():
    r = client.post("/api/registrations/", json=_registration_payload(), headers=AUTH)
    assert r.status_code == 201
    assert r.json()["group_size"] == "2"
    r2 = client.get("/api/registrations/", headers=AUTH)
    assert any(x["email"] == "karin@example.se" for x in r2.json())


def test_registration_rejects_duplicate_generations():
    r = client.post(
        "/api/registrations/", json=_registration_payload(generations=[2, 2]), headers=AUTH
    )
    assert r.status_code == 422


def test_registration_rejects_invalid_email():
    r = client.post(
        "/api/registrations/", json=_registration_payload(email="not-an-email"), headers=AUTH
    )
    assert r.status_code == 422


def test_registration_rejects_empty_generations():
    r = client.post(
        "/api/registrations/", json=_registration_payload(generations=[]), headers=AUTH
    )
    assert r.status_code == 422


def test_registration_update_and_delete():
    rid = client.post("/api/registrations/", json=_registration_payload(), headers=AUTH).json()["id"]
    r = client.put(f"/api/registrations/{rid}", json={"notes": "Vegan", "group_size": "3"}, headers=AUTH)
    assert r.status_code == 200
    assert r.json()["notes"] == "Vegan"
    assert r.json()["group_size"] == "3"
    assert client.delete(f"/api/registrations/{rid}", headers=AUTH).status_code == 200
    assert client.get(f"/api/registrations/{rid}", headers=AUTH).status_code == 404

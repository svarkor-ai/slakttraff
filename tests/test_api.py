"""Contract tests for the Släktträff API (auth, persons, registrations, RSVP)."""
import os
import tempfile

# Isolate the test DB before app import.
_TMPDIR = tempfile.mkdtemp(prefix="slakttraff-test-")
os.environ["SLAKTTRAFF_DATABASE_URL"] = f"sqlite:///{_TMPDIR}/test.db"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import auth as auth_module  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)

SITE_PASSWORD = "sibbamala"  # default; tests run without SITE_PASSWORD set
ADMIN_PASSWORD = "admin-test-pw"


def _auth_headers():
    r = client.post("/api/auth", json={"password": SITE_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


AUTH = _auth_headers()


@pytest.fixture()
def admin():
    """Enable a test admin password; yield admin auth headers; restore unset."""
    auth_module.ADMIN_PASSWORD = ADMIN_PASSWORD
    auth_module._admin_tokens.clear()
    yield {"Authorization": "Bearer " + auth_module.issue_admin_token()}
    auth_module.ADMIN_PASSWORD = None
    auth_module._admin_tokens.clear()


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
    assert r.status_code in (403, 429)  # 429 when earlier tests tripped the limiter
    assert "token" not in r.json()


def test_auth_non_ascii_password_rejected_not_500():
    # Regression: hmac.compare_digest raised TypeError on non-ASCII input (500).
    r = client.post("/api/auth", json={"password": "lösenördåä"})
    assert r.status_code in (403, 429)
    assert "token" not in r.json()


def test_auth_rate_limit_blocks_parallel_brute_force():
    """The failure counter must be parallel-safe: 10 rapid failures from one
    IP trip the limit even though none of them sleeps (old sleep-based
    throttle let any number of concurrent attempts through)."""
    from app.auth import _failed_attempts, FAILED_ATTEMPTS_ALLOWED

    _failed_attempts.clear()
    codes = [
        client.post("/api/auth", json={"password": f"wrong{i}"}).status_code
        for i in range(FAILED_ATTEMPTS_ALLOWED + 3)
    ]
    assert 429 in codes
    assert codes[-1] == 429
    _failed_attempts.clear()


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
    assert client.post("/api/persons/", json=_person_payload()).status_code == 401


def test_admin_surface_exists_by_default():
    """ADMIN_PASSWORD has an owner-approved default: the admin surface exists.
    A site token must NOT grant admin access."""
    assert client.post("/api/admin/auth", json={"password": "fel"}).status_code == 403
    assert client.get("/api/rsvp-replies/", headers=AUTH).status_code == 401
    assert client.get("/api/registrations/", headers=AUTH).status_code == 401


def test_admin_auth_flow():
    """With ADMIN_PASSWORD set: correct password -> admin token; site token is
    NOT an admin token; wrong admin password -> 403."""
    auth_module.ADMIN_PASSWORD = ADMIN_PASSWORD
    try:
        r = client.post("/api/admin/auth", json={"password": ADMIN_PASSWORD})
        assert r.status_code == 200
        admin_headers = {"Authorization": "Bearer " + r.json()["token"]}
        assert client.get("/api/rsvp-replies/", headers=admin_headers).status_code == 200
        # A site-password token must not open admin endpoints (P1-4).
        assert client.get("/api/rsvp-replies/", headers=AUTH).status_code == 401
        r2 = client.post("/api/admin/auth", json={"password": "wrong"})
        assert r2.status_code == 403
    finally:
        auth_module.ADMIN_PASSWORD = None
        auth_module._admin_tokens.clear()


def test_person_delete_with_site_token_rejected():
    """P1-5: a plain site-password token must not delete persons."""
    auth_module.ADMIN_PASSWORD = ADMIN_PASSWORD
    try:
        admin_headers = {"Authorization": "Bearer " + auth_module.issue_admin_token()}
        pid = client.post("/api/persons/", json=_person_payload(),
                          headers=admin_headers).json()["id"]
        r = client.delete(f"/api/persons/{pid}", headers=AUTH)
        assert r.status_code == 401
        assert client.get(f"/api/persons/{pid}", headers=AUTH).status_code == 200
    finally:
        auth_module.ADMIN_PASSWORD = None
        auth_module._admin_tokens.clear()


def test_docs_disabled_by_default():
    """P3: /docs and /openapi.json are off unless SLAKTTRAFF_DEBUG=1."""
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_api_rejects_bad_token():
    r = client.get("/api/persons/", headers={"Authorization": "Bearer not-a-token"})
    assert r.status_code == 401


def test_root_serves_password_screen():
    r = client.get("/")
    assert r.status_code == 200
    assert "password-screen" in r.text
    assert "Släktträff i Sibbamåla hembygdsförening, datum annonseras snart" in r.text


# --- persons: valid transitions ---

def test_person_create_and_get(admin):
    r = client.post("/api/persons/", json=_person_payload(), headers=admin)
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Erik Andersson"
    assert body["rsvp_status"] == "pending"
    assert "rsvp_token" not in body  # token must never be exposed
    r2 = client.get(f"/api/persons/{body['id']}", headers=AUTH)
    assert r2.status_code == 200
    assert r2.json()["id"] == body["id"]


def test_person_list(admin):
    client.post("/api/persons/", json=_person_payload(name="Lista Test"), headers=admin)
    r = client.get("/api/persons/", headers=AUTH)
    assert r.status_code == 200
    assert any(p["name"] == "Lista Test" for p in r.json())


def test_person_update_partial(admin):
    pid = client.post("/api/persons/", json=_person_payload(), headers=admin).json()["id"]
    r = client.put(f"/api/persons/{pid}", json={"role": "Barn"}, headers=admin)
    assert r.status_code == 200
    assert r.json()["role"] == "Barn"
    assert r.json()["name"] == "Erik Andersson"  # untouched field preserved


def test_person_delete(admin):
    pid = client.post("/api/persons/", json=_person_payload(), headers=admin).json()["id"]
    assert client.delete(f"/api/persons/{pid}", headers=admin).status_code == 200
    assert client.get(f"/api/persons/{pid}", headers=AUTH).status_code == 404


# --- persons: negative cases ---

def test_person_rejects_blank_name(admin):
    r = client.post("/api/persons/", json=_person_payload(name="   "), headers=admin)
    assert r.status_code == 422


def test_person_rejects_bad_birth_year(admin):
    r = client.post("/api/persons/", json=_person_payload(birth_year=1800), headers=admin)
    assert r.status_code == 422


def test_person_rejects_bad_generation(admin):
    r = client.post("/api/persons/", json=_person_payload(generation=9), headers=admin)
    assert r.status_code == 422


def test_person_get_unknown_returns_404():
    assert client.get("/api/persons/99999", headers=AUTH).status_code == 404


# --- RSVP (password-gated, with contact info) ---

def test_rsvp_requires_token(admin):
    pid = client.post("/api/persons/", json=_person_payload(), headers=admin).json()["id"]
    r = client.post(f"/api/persons/{pid}/rsvp", json=_rsvp_payload())
    assert r.status_code == 401


def test_rsvp_accept_and_change_with_contact(admin):
    pid = client.post("/api/persons/", json=_person_payload(), headers=admin).json()["id"]
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

    # Upsert (P2): one reply row per person — the repeat submit REPLACES it.
    replies = client.get("/api/rsvp-replies/", headers=admin).json()
    mine = [x for x in replies if x["person_id"] == pid]
    assert len(mine) == 1
    assert mine[0]["email"] == "other@example.se"
    assert mine[0]["status"] == "declined"


def test_rsvp_requires_email(admin):
    pid = client.post("/api/persons/", json=_person_payload(), headers=admin).json()["id"]
    payload = _rsvp_payload()
    del payload["email"]
    r = client.post(f"/api/persons/{pid}/rsvp", json=payload, headers=AUTH)
    assert r.status_code == 422


def test_rsvp_rejects_invalid_email(admin):
    pid = client.post("/api/persons/", json=_person_payload(), headers=admin).json()["id"]
    r = client.post(
        f"/api/persons/{pid}/rsvp", json=_rsvp_payload(email="not-an-email"), headers=AUTH
    )
    assert r.status_code == 422


def test_rsvp_optional_fields_default_null(admin):
    pid = client.post("/api/persons/", json=_person_payload(), headers=admin).json()["id"]
    r = client.post(
        f"/api/persons/{pid}/rsvp",
        json={"status": "accepted", "email": "minimal@example.se"},
        headers=AUTH,
    )
    assert r.status_code == 200
    replies = client.get("/api/rsvp-replies/", headers=admin).json()
    mine = [x for x in replies if x["person_id"] == pid]
    assert mine and mine[0]["phone"] is None and mine[0]["notes"] is None


def test_rsvp_rejects_pending(admin):
    pid = client.post("/api/persons/", json=_person_payload(), headers=admin).json()["id"]
    r = client.post(
        f"/api/persons/{pid}/rsvp", json=_rsvp_payload(status="pending"), headers=AUTH
    )
    assert r.status_code == 422


def test_rsvp_rejects_invalid_status(admin):
    pid = client.post("/api/persons/", json=_person_payload(), headers=admin).json()["id"]
    r = client.post(
        f"/api/persons/{pid}/rsvp", json=_rsvp_payload(status="maybe"), headers=AUTH
    )
    assert r.status_code == 422


def test_rsvp_rejects_missing_status(admin):
    pid = client.post("/api/persons/", json=_person_payload(), headers=admin).json()["id"]
    payload = _rsvp_payload()
    del payload["status"]
    r = client.post(f"/api/persons/{pid}/rsvp", json=payload, headers=AUTH)
    assert r.status_code == 422


def test_rsvp_unknown_person_404():
    r = client.post("/api/persons/99999/rsvp", json=_rsvp_payload(), headers=AUTH)
    assert r.status_code == 404


def test_person_list_includes_rsvp_status(admin):
    pid = client.post(
        "/api/persons/", json=_person_payload(name="Status Test"), headers=admin
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

def test_registration_create_and_list(admin):
    r = client.post("/api/registrations/", json=_registration_payload(), headers=AUTH)
    assert r.status_code == 201
    assert r.json()["group_size"] == "2"
    r2 = client.get("/api/registrations/", headers=admin)
    assert any(x["email"] == "karin@example.se" for x in r2.json())


def test_registration_creates_tree_person(admin):
    """A signup must be visible in the family tree: the registration links to a
    new Person with the registrant's name and lowest chosen generation."""
    payload = _registration_payload(name="Sven Svensson", generations=[3, 2])
    r = client.post("/api/registrations/", json=payload, headers=AUTH)
    assert r.status_code == 201, r.text
    body = r.json()
    person_id = body["person_id"]
    assert isinstance(person_id, int)

    persons = client.get("/api/persons/", headers=AUTH).json()
    person = next(p for p in persons if p["id"] == person_id)
    assert person["name"] == "Sven Svensson"
    assert person["generation"] == 2  # lowest selected generation
    assert person["role"] == "Anmäld"
    assert person["rsvp_status"] == "pending"
    # rsvp_token is deliberately not exposed by the API; check it in the DB.
    from app.database import SessionLocal
    from app.models.person import Person as PersonModel

    db = SessionLocal()
    try:
        row = db.query(PersonModel).filter(PersonModel.id == person_id).first()
        assert row is not None and len(row.rsvp_token) == 32  # uuid4().hex
    finally:
        db.close()
    assert person["parents"] == [] and person["children"] == [] and person["spouses"] == []


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


def test_registration_update_and_delete(admin):
    rid = client.post("/api/registrations/", json=_registration_payload(), headers=AUTH).json()["id"]
    r = client.put(f"/api/registrations/{rid}", json={"notes": "Vegan", "group_size": "3"}, headers=admin)
    assert r.status_code == 200
    assert r.json()["notes"] == "Vegan"
    assert r.json()["group_size"] == "3"
    assert client.delete(f"/api/registrations/{rid}", headers=admin).status_code == 200
    assert client.get(f"/api/registrations/{rid}", headers=admin).status_code == 404


# --- admin family import ---

def _family_entries():
    return [
        {"key": "imp1", "name": "Import A", "generation": 1, "parents": []},
        {"key": "imp2", "name": "Import B", "generation": 2, "parents": ["imp1"]},
        {"key": "imp3", "name": "Import C", "generation": 2, "parents": ["imp1"]},
    ]


def test_admin_import_family_replaces_all(admin):
    """Import with an admin token replaces the table and wires relations."""
    r = client.post("/api/admin/import-family", json=_family_entries(), headers=admin)
    assert r.status_code == 200
    assert r.json() == {"imported": 3}

    persons = client.get("/api/persons/", headers=AUTH).json()
    assert len(persons) == 3
    by_name = {p["name"]: p for p in persons}
    assert set(by_name) == {"Import A", "Import B", "Import C"}
    # parent/child wiring from the entry list survived the import
    parent = by_name["Import A"]
    assert sorted(parent["children"]) == sorted([by_name["Import B"]["id"],
                                                 by_name["Import C"]["id"]])
    assert parent["parents"] == []
    assert by_name["Import B"]["parents"] == [parent["id"]]

    # replace-all: a second import leaves only the new entries
    r2 = client.post("/api/admin/import-family",
                     json=[{"key": "solo", "name": "Solo", "generation": 1,
                            "parents": []}], headers=admin)
    assert r2.json() == {"imported": 1}
    persons2 = client.get("/api/persons/", headers=AUTH).json()
    assert [p["name"] for p in persons2] == ["Solo"]


def test_admin_import_family_requires_admin_token():
    """A site token (or no token) must not import family data."""
    assert client.post("/api/admin/import-family",
                       json=_family_entries()).status_code == 401
    assert client.post("/api/admin/import-family",
                       json=_family_entries(), headers=AUTH).status_code == 401


def test_admin_import_family_malformed_body(admin):
    """Not-a-list, missing fields and type-wrong fields are 422, never 500."""
    assert client.post("/api/admin/import-family", json={"name": "x"},
                       headers=admin).status_code == 422
    assert client.post("/api/admin/import-family", json=["not-a-dict"],
                       headers=admin).status_code == 422
    assert client.post("/api/admin/import-family",
                       json=[{"name": "NoKey", "generation": 1}],
                       headers=admin).status_code == 422
    assert client.post("/api/admin/import-family",
                       json=[{"key": "a", "name": "A", "generation": 1,
                              "parents": ["ghost"]}],
                       headers=admin).status_code == 422
    # type-wrong shapes that previously reached the ORM and raised 500
    assert client.post("/api/admin/import-family",
                       json=[{"key": ["a"], "name": "X", "generation": 1}],
                       headers=admin).status_code == 422
    assert client.post("/api/admin/import-family",
                       json=[{"key": "a", "name": None, "generation": 1}],
                       headers=admin).status_code == 422
    assert client.post("/api/admin/import-family",
                       json=[{"key": "a", "name": "X", "generation": "senior"}],
                       headers=admin).status_code == 422
    assert client.post("/api/admin/import-family",
                       json=[{"key": "a", "name": "X", "generation": True}],
                       headers=admin).status_code == 422


def test_admin_import_family_empty_list_rejected(admin):
    """An empty import is never meaningful: 400, tree untouched."""
    client.post("/api/admin/import-family", json=_family_entries(), headers=admin)
    r = client.post("/api/admin/import-family", json=[], headers=admin)
    assert r.status_code == 400
    assert len(client.get("/api/persons/", headers=AUTH).json()) == 3


def test_admin_import_family_after_registrations_no_orphan_fk(admin):
    """Replace-all import must not leave orphaned registrations.person_id."""
    rid = client.post("/api/registrations/", json=_registration_payload(),
                      headers=AUTH).json()["id"]
    r = client.post("/api/admin/import-family", json=_family_entries(), headers=admin)
    assert r.status_code == 200
    # the registration survives, its person link is cleared
    reg = client.get(f"/api/registrations/{rid}", headers=admin).json()
    assert reg["person_id"] is None
    # no FK violations remain
    from app.database import engine
    with engine.connect() as conn:
        violations = conn.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
    assert violations == []


# --- Startup migration: registrations.person_id backfill (MC 1376.1 T3) ---

_OLD_SHAPE_SQL = [
    # persons as it existed before T2-era changes that the live DB may predate
    """CREATE TABLE persons (
        id INTEGER PRIMARY KEY,
        name VARCHAR(200) NOT NULL,
        birth_year INTEGER,
        generation INTEGER NOT NULL,
        role VARCHAR(100),
        relation VARCHAR(200),
        description VARCHAR(500),
        parents JSON,
        children JSON,
        spouses JSON,
        rsvp_status VARCHAR(20) NOT NULL,
        rsvp_token VARCHAR(64) NOT NULL,
        created_at DATETIME,
        updated_at DATETIME
    )""",
    # registrations WITHOUT person_id — the pre-T2 live shape
    """CREATE TABLE registrations (
        id INTEGER PRIMARY KEY,
        name VARCHAR(200) NOT NULL,
        email VARCHAR(300) NOT NULL,
        generations JSON NOT NULL,
        group_size VARCHAR(10) NOT NULL,
        notes VARCHAR(1000),
        created_at DATETIME
    )""",
]


def _old_shape_engine(tmp_path):
    from sqlalchemy import create_engine, text

    engine = create_engine(
        f"sqlite:///{tmp_path / 'old.db'}",
        connect_args={"check_same_thread": False},
    )
    with engine.begin() as conn:
        for ddl in _OLD_SHAPE_SQL:
            conn.execute(text(ddl))
    return engine


def _registration_columns(engine):
    from sqlalchemy import text

    with engine.connect() as conn:
        return {row[1] for row in conn.execute(text("PRAGMA table_info(registrations)"))}


def test_startup_migration_backfills_person_id(tmp_path):
    from app.migrations import run_startup_migrations

    engine = _old_shape_engine(tmp_path)
    assert "person_id" not in _registration_columns(engine)

    run_startup_migrations(engine)
    assert "person_id" in _registration_columns(engine)


def test_startup_migration_is_idempotent(tmp_path):
    from app.migrations import run_startup_migrations

    engine = _old_shape_engine(tmp_path)
    run_startup_migrations(engine)
    run_startup_migrations(engine)  # second run must not raise or duplicate
    cols = [c for c in _registration_columns(engine) if c == "person_id"]
    assert cols == ["person_id"]


def test_registration_post_works_on_migrated_old_db(tmp_path, monkeypatch):
    """The deployed scenario: old-shape DB + migration + a real registration POST."""
    from sqlalchemy import orm

    from app import database as app_database
    from app.migrations import run_startup_migrations

    engine = _old_shape_engine(tmp_path)
    run_startup_migrations(engine)

    monkeypatch.setattr(
        app_database,
        "SessionLocal",
        orm.sessionmaker(bind=engine, autocommit=False, autoflush=False),
    )
    r = client.post("/api/registrations/", json=_registration_payload(), headers=AUTH)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["person_id"] is not None

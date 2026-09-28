"""Admin family-import and startup-migration contract tests (MC 1376.1).

Split out of tests/test_api.py (file-hygiene: test files up to 600 lines);
shares the app import and auth helpers with that module's pattern.
"""
import os
import tempfile

# Isolate the test DB before app import (same pattern as tests/test_api.py).
_TMPDIR = tempfile.mkdtemp(prefix="slakttraff-test-admin-")
os.environ["SLAKTTRAFF_DATABASE_URL"] = f"sqlite:///{_TMPDIR}/test.db"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import auth as auth_module  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)

SITE_PASSWORD = "sibbamala"
ADMIN_PASSWORD = "admin-test-pw"


def _auth_headers():
    r = client.post("/api/auth", json={"password": SITE_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


AUTH = _auth_headers()


_ADMIN_PASSWORD_DEFAULT = auth_module.ADMIN_PASSWORD


@pytest.fixture()
def admin():
    """Enable a test admin password; yield admin auth headers; restore default."""
    auth_module.ADMIN_PASSWORD = ADMIN_PASSWORD
    auth_module._admin_tokens.clear()
    yield {"Authorization": "Bearer " + auth_module.issue_admin_token()}
    auth_module.ADMIN_PASSWORD = _ADMIN_PASSWORD_DEFAULT
    auth_module._admin_tokens.clear()


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
    # optional fields must be strings (or null) when present, never 500
    assert client.post("/api/admin/import-family",
                       json=[{"key": "a", "name": "X", "generation": 1,
                              "role": {"x": 1}}],
                       headers=admin).status_code == 422
    assert client.post("/api/admin/import-family",
                       json=[{"key": "a", "name": "X", "generation": 1,
                              "relation": ["parent"]}],
                       headers=admin).status_code == 422
    assert client.post("/api/admin/import-family",
                       json=[{"key": "a", "name": "X", "generation": 1,
                              "description": 42}],
                       headers=admin).status_code == 422
    # null optional fields and string values stay valid
    assert client.post("/api/admin/import-family",
                       json=[{"key": "a", "name": "X", "generation": 1,
                              "role": None, "relation": None,
                              "description": "text"}],
                       headers=admin).status_code == 200


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

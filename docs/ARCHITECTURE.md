# ARCHITECTURE — Släktträff (svarkor-slakttraff-anmalan)

Family-reunion signup backend + static frontend. Status: foundation, RSVP backend done, frontend wiring pending.

## Tree

```
app/
  main.py            FastAPI app: CORS (env SLAKTTRAFF_CORS_ORIGINS), /health, /
  database.py        SQLAlchemy engine; SQLite at data/slakttraff.db (env SLAKTTRAFF_DATABASE_URL)
  models/person.py        Person (name, birth_year, generation, role, relation, description,
                           parents/children/spouses JSON, rsvp_status, rsvp_token)
  models/registration.py  Registration (name, email, generations, group_size, notes)
  schemas/enums.py        Generation, GroupSize, RsvpStatus
  schemas/person.py       PersonBase/Create/Update/Person/PersonResponse/RsvpSubmit
  schemas/registration.py RegistrationBase/Create/Update/Registration/RegistrationResponse
  routers/persons.py      /api/persons CRUD + POST /api/persons/{id}/rsvp (token-gated)
  routers/registrations.py /api/registrations CRUD
teddy/index.html     static family-tree page (localStorage names; backend wiring pending)
tests/test_api.py    pytest contract tests (TestClient, isolated temp DB)
data/                SQLite database (gitignored)
```

## Entrypoint

`.venv/bin/uvicorn app.main:app --port <PORT>` (bind PORT env at deploy time).

## Data store

Single SQLite file `data/slakttraff.db`. No migrations tool; `Base.metadata.create_all` at import.

## Known open items

- Write/delete endpoints are unauthenticated (no auth concept yet — owner decision pending).
- Frontend does not call the API yet; RSVP colour states not rendered.
- `teddy/48.*` files are dispatch artifacts, not product code.

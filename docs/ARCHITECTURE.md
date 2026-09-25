# ARCHITECTURE — Släktträff (svarkor-slakttraff-anmalan)

Family-reunion signup backend + frontend, served as ONE origin. Status: functional —
open click-and-answer RSVP live, tree rendered from API data (build 2026-09-25).

## Tree

```
app/
  main.py            FastAPI app: CORS (env SLAKTTRAFF_CORS_ORIGINS), /health,
                     seeds family tree on fresh DB, mounts teddy/ as static files at "/"
  database.py        SQLAlchemy engine; SQLite at data/slakttraff.db (env SLAKTTRAFF_DATABASE_URL)
  seed.py            FAMILY data + seed_persons_if_empty() (runs once when table empty)
  models/person.py        Person (name, birth_year, generation, role, relation, description,
                           parents/children/spouses JSON, rsvp_status, rsvp_token [legacy, unused])
  models/registration.py  Registration (name, email, generations, group_size, notes)
  schemas/enums.py        Generation, GroupSize, RsvpStatus
  schemas/person.py       PersonBase/Create/Update/Person/PersonResponse/RsvpSubmit (status only)
  schemas/registration.py RegistrationBase/Create/Update/Registration/RegistrationResponse
  routers/persons.py      /api/persons CRUD + POST /api/persons/{id}/rsvp (OPEN: no token)
  routers/registrations.py /api/registrations CRUD
teddy/
  index.html          markup only (header, tree container, form, person modal)
  style.css           base layout, header, sections, modal, responsive
  tree.css            family tree, person spots, RSVP colour states (green/red)
  forms.css           registration form + success message
  api.js              API client (fetchPersons, submitRsvp, submitRegistration)
  tree.js             tree rendering from API data + RSVP colour application
  app.js              page wiring: init/load, person modal + RSVP buttons, form submit
tests/test_api.py    pytest contract tests (TestClient, isolated temp DB)
data/                SQLite database (gitignored)
```

## Entrypoint

`.venv/bin/uvicorn app.main:app --port <PORT>` — GET / serves the tree page,
`/api/*` the JSON API, `/health` the health check. All one origin.

## Data store

Single SQLite file `data/slakttraff.db`. No migrations tool; `Base.metadata.create_all`
at import, then `seed_persons_if_empty()` seeds the 62-person family tree once.

## RSVP model (owner decision 2026-09-25, "open click-and-answer")

POST /api/persons/{id}/rsvp takes `{"status": "accepted"|"declined"}` with NO token.
`pending` and unknown values → 422; unknown person → 404. The `rsvp_token` column is
kept but unused. Spot colours: green = accepted, red = declined, original = pending.

## Known open items

- Write/delete endpoints are unauthenticated (no auth concept yet — owner decision pending).
- `teddy/48.*` files are dispatch artifacts, not product code.

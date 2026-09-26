# ARCHITECTURE — Släktträff (svarkor-slakttraff-anmalan)

Family-reunion signup backend + frontend, served as ONE origin. Status: functional —
site-password gated, RSVP with contact info, tree rendered from API data
(build 2026-09-26). Public at sibbamala.com/slakttraff (vm106 reconciler).

## Tree

```
server.py           Repo-root entrypoint for the host: reads PORT env, runs uvicorn
                    on 0.0.0.0:$PORT (no reload). Default port 8119.
hosting.yaml        Hosting manifest for the vm106 reconciler (strict JSON).
app/
  main.py            FastAPI app: CORS (env SLAKTTRAFF_CORS_ORIGINS), /health,
                     seeds family tree on fresh DB, mounts teddy/ as static files at "/"
  auth.py            Site-password gate: SITE_PASSWORD env (default "sibbamala"),
                     hmac.compare_digest check, in-memory opaque session tokens
                     (12 h TTL), parallel-safe per-IP failure counter (max 5/60 s → 429),
                     require_token dep
  database.py        SQLAlchemy engine; SQLite at data/slakttraff.db (env SLAKTTRAFF_DATABASE_URL)
  seed.py            Loads data/family.json + seed_persons_if_empty() (empty tree + log
                     warning when the file is missing)
  models/person.py        Person (name, birth_year, generation, role, relation, description,
                           parents/children/spouses JSON, rsvp_status, rsvp_token [legacy, unused])
  models/registration.py  Registration (name, email, generations, group_size, notes)
  models/rsvp_reply.py    RsvpReply (person_id FK, status, email, phone, notes) — contact
                           info submitted with an RSVP; admin-visible only
  schemas/enums.py        Generation, GroupSize, RsvpStatus
  schemas/person.py       PersonBase/Create/Update/Person/PersonResponse,
                          RsvpSubmit (status + email + phone? + notes?), RsvpReplyResponse
  schemas/registration.py RegistrationBase/Create/Update/Registration/RegistrationResponse
  routers/auth.py         POST /api/auth {"password"} -> {"token"} (403 wrong password,
                          429 when the per-IP failure limit trips)
  routers/persons.py      /api/persons CRUD + POST /api/persons/{id}/rsvp (token required)
  routers/registrations.py /api/registrations CRUD (token required)
  routers/rsvp_replies.py  GET /api/rsvp-replies (token required; the admin contact-info view)
teddy/
  index.html          markup (password screen, header, tree container, form, person modal
                      with contact fields)
  style.css           base layout, header, password screen, modal, responsive
  tree.css            family tree, person spots, RSVP colour states (green/red)
  forms.css           registration form + success message
  api.js              API client (login, fetchPersons, submitRsvp, submitRegistration);
                      sends Bearer token, on 401 clears token + returns to password screen
  tree.js             tree rendering from API data + RSVP colour application
  app.js              page wiring: password gate, init/load, person modal + RSVP +
                      contact fields, form submit
tests/test_api.py    pytest contract tests (TestClient, isolated temp DB)
data/
  family.json           real family data (GITIGNORED — personal data, never commit)
  family.json.example   placeholder shape ("Person 1"...) committed for fresh clones
```

## Entrypoint

`PORT=8119 python3 server.py` (or `.venv/bin/uvicorn app.main:app --port 8119`) —
GET / serves the password screen, `/api/*` the JSON API, `/health` the health check.
All one origin.

## Password flow (owner decision 2026-09-26)

The whole site sits behind ONE shared password. `POST /api/auth {"password": ...}`
compares with `hmac.compare_digest` against `SITE_PASSWORD` (env var, default
`sibbamala` — never hardcoded beyond that default) and returns an opaque
`secrets.token_hex` session token kept in-memory (12 h TTL). Wrong passwords are
rate-limited per IP with a parallel-safe sliding-window counter (max 5 failures
per 60 s, advanced atomically under a lock — extra connections cannot bypass it)
and return 429 when the limit trips, 403 otherwise. Every persons /
registrations / rsvp-replies endpoint requires `Authorization: Bearer <token>`
(401 without). The frontend stores the token in sessionStorage, shows the password
screen first, and returns to it on any 401.

## Data store

Single SQLite file `data/slakttraff.db`. No migrations tool; `Base.metadata.create_all`
at import, then `seed_persons_if_empty()` seeds the family tree from
`data/family.json` once (empty tree + log warning if that file is missing).

## RSVP model (owner decisions 2026-09-25 + 2026-09-26)

POST /api/persons/{id}/rsvp takes `{"status": "accepted"|"declined", "email": ...,
"phone"?, "notes"?}` with a valid session token. `pending` and unknown values → 422;
missing/invalid email → 422; unknown person → 404. Each reply is stored as an
RsvpReply row; contact info is exposed ONLY via the token-protected
GET /api/rsvp-replies — readable by any site-password holder (owner decision
2026-09-26: one shared password gates everything). Spot colours: green = accepted,
red = declined, original = pending.

## Known accepted risks (owner decisions 2026-09-26)

- Session tokens are in-memory: a server restart logs everyone out (acceptable for
  this event site; revisit if persistence is wanted).
- One shared password means any password holder can read `/api/rsvp-replies`
  (all invitee contact info) and create/edit/delete persons, including
  `DELETE /api/persons/{id}`. Accepted under "shared password gates everything";
  revisit with a separate admin credential if that changes.
- The default password is public in this repo; set `SITE_PASSWORD` in the host
  environment before publishing or the gate is a courtesy screen only.
- RSVP and the registration form both record attendance in separate tables
  (RsvpReply vs Registration) and are not reconciled: RSVP = per-spot answer for
  invited family, registration = general sign-up.
- `teddy/48.*` files are dispatch artifacts, not product code.

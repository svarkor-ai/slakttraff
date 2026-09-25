# AUDIT — Släktträff signup backend (code + security)

Run: 20260812-audit · executed 2026-09-25 · scope: `/srv/workspace/svarkor-slakttraff-anmalan/` (app/ + teddy/)
Auditor note: this run was mandated to fan out to profile children, but the session is a depth-1
subagent (`subagent` tool returns "depth 2 exceeds maxDepth 1"), so the audit was executed inline by
the orchestrator child. All claims below are VERIFIED by direct file inspection this session unless
labelled otherwise.

## 1. Inventory — what exists and works

Backend (`app/`, 770 lines total incl. the stray schemas file):

| Piece | File | Status |
|---|---|---|
| FastAPI app, CORS, `/health`, `/` | `app/main.py` (36 l) | works; CORS misconfigured (F-1) |
| SQLite engine, `get_db` | `app/database.py` (21 l) | works; DB in `/tmp` (F-3) |
| `Person` model (name, birth_year, generation, role, relation, description, parents/children/spouses as JSON cols) | `app/models/person.py` | works |
| `Registration` model (name, email, generations, group_size, notes) | `app/models/registration.py` | works |
| Persons CRUD: POST/GET list/GET one/PUT/DELETE `/api/persons` | `app/routers/persons.py` (66 l) | works, unauthenticated (F-2) |
| Registrations CRUD: same five verbs `/api/registrations` | `app/routers/registrations.py` (63 l) | works, unauthenticated (F-2) |
| Pydantic v2 schemas with validators (Generation/GroupSize enums, name-not-empty, generations-unique) + self-test runner | `app/schemas/__init__.py` (527 l) | works but is a stray monolith (F-4); `schemas/person.py` and `schemas/registration.py` are 10-line re-export shims |

Frontend (`teddy/`): `index.html` and `index-anmalan.html` are **byte-identical** (diff = 0 lines,
1420 lines each). Static family-tree rendering with SVG connectors, person cards, a click modal that
shows name/generation/role/relation, a name-input modal persisted to **localStorage only**, and a
registration form whose submit handler is **simulated** (`setTimeout` 1500 ms → success message;
zero `fetch`/`XMLHttpRequest`/`axios` calls in the file). The page never talks to the backend.

Runtime evidence: `/tmp/slakttraff.db` exists (the app has been run); `data/` dir contains only
`.gitkeep`. No git repo (`git status` → "not a git repository"). No tests anywhere under the project
(find for `*test*` returns nothing outside `.venv`).

## 2. Findings (P0 = critical … P4 = optional)

| ID | Sev | Finding | Location |
|---|---|---|---|
| F-1 | **P0** | `allow_origins=["*"]` together with `allow_credentials=True` — an invalid/permissive CORS combination; any origin can make credentialed requests. Once auth exists this becomes an actual credential-leak vector. | `app/main.py:18-24` |
| F-2 | **P0** | Every write and delete endpoint is unauthenticated: `POST/PUT/DELETE /api/persons` and `/api/registrations` accept anonymous traffic. Anyone who can reach the host can wipe the whole tree (`DELETE /api/persons/{id}` loop). There is no auth concept at all. | `app/routers/persons.py:13,42,59`; `app/routers/registrations.py:12,37,56` |
| F-3 | **P0** | SQLite database hardcoded to `sqlite:////tmp/slakttraff.db` — `/tmp` is wiped on reboot and world-readable/writable on multi-user hosts: total data loss + tamper surface. The `data/` dir exists but is unused. | `app/database.py:5` |
| F-4 | **P1** | Stray 527-line `app/schemas/__init__.py`: a dispatch artifact (header says "MC Job 48.4, T1", carries a `run_tests()` CLI self-test) pasted into a package `__init__`. Violates the 250/400 file-hygiene rule, is imported through 10-line re-export shims, and mixes schema definitions with a test runner. | `app/schemas/__init__.py:1-527`; shims at `app/schemas/person.py`, `app/schemas/registration.py` |
| F-5 | **P1** | The owner's core feature does not exist in the frontend: no accept/decline RSVP, no green/red spot colouring, no unanswered state. Clicking a spot opens an info or name-input modal; state lives in localStorage only. The HTML is a static mock, not the product. | `teddy/index.html:1292-1318` (click handler), `1076-1086` (modal), form submit `1337-1360` |
| F-6 | **P1** | Duplicate HTML: `index.html` and `index-anmalan.html` are byte-identical (1420 lines each, diff empty). Two names for one file guarantees drift. | `teddy/index.html`, `teddy/index-anmalan.html` |
| F-7 | **P1** | No tests at all — backend has zero test files; the only "tests" are the `run_tests()` self-test inside the stray schemas file. | project tree |
| F-8 | **P1** | No git repository — no history, no rollback, no way to attribute changes. | `/srv/workspace/svarkor-slakttraff-anmalan/` |
| F-9 | **P2** | `Person.parents/children/spouses` are unvalidated free-form JSON lists with no referential integrity — a person can be its own parent, IDs can point at deleted persons. | `app/models/person.py:16-18`; `app/routers/persons.py:50-53` |
| F-10 | **P2** | `list` endpoints expose all registrations (name + email of every attendee) to anonymous callers — personal-data exposure under GDPR once real names are entered. | `app/routers/registrations.py:26-28` |
| F-11 | **P2** | Dead imports (`json` in both routers, `JSON` from sqlalchemy in `persons.py`) and a no-op if/else in `update_person` (both branches do the same `setattr`). | `app/routers/persons.py:5,9,50-53`; `app/routers/registrations.py:9` |
| F-12 | **P3** | No deployment story: no Dockerfile/systemd/hosting config, no `PORT` binding convention, no docs (`docs/ARCHITECTURE.md` absent), `requirements.txt` unpinned. | project root |
| F-13 | **P4** | `datetime.utcnow` deprecation (Python 3.12+); `check_same_thread=False` fine for SQLite+FastAPI but worth a comment. | `app/models/*.py:19`; `app/database.py:10` |

Not audited (out of scope): the `teddy/48.*` evidence/scripts files (dispatch artifacts, not product code) and the `.venv/` contents.

## 3. Gap analysis — what is missing to reach the owner's vision

Owner's vision: each family member is a spot in a visual tree; clicking your spot lets you accept or
decline the invitation — accept = green, decline = red, unanswered = original colour.

1. **Per-person RSVP status field** — `Person` has no `rsvp_status` column (`pending|accepted|declined`) nor `rsvp_token`. Backend gap.
2. **Invitation/identity flow** — no way to prove "this click is me": needs per-person tokens (e.g. link with token → RSVP endpoint) since there is no auth concept. Backend + frontend gap.
3. **RSVP endpoints** — no `POST /api/persons/{id}/rsvp` (accept/decline) exists; only generic PUT, which would let anyone flip anyone's answer.
4. **Tree rendering with colour states** — the HTML renders the tree and colours, but binds no colour to RSVP state; the click modal has no accept/decline buttons.
5. **Frontend↔backend wiring** — the page makes zero HTTP calls; form submission is faked with `setTimeout`. Everything must be wired to the real API.
6. **Persistence & deployment** — DB in `/tmp` (F-3), no git repo (F-8), no deployment config (F-12): the site cannot survive a reboot or be published safely.
7. **Tests** — none (F-7); the RSVP flow needs at least contract tests before it is trusted.

## 4. Recommended build order

1. `git init` + first commit of the current tree (F-8) — everything else builds on history.
2. Move the DB to `data/slakttraff.db` (relative to project root, env-overridable) (F-3); fix CORS to an explicit origin list without credentials (F-1).
3. Split `app/schemas/__init__.py` into real `person.py`/`registration.py` modules; delete the re-export shims and the embedded test runner (F-4).
4. Add `rsvp_status` (+ `rsvp_token`) to `Person`; add `POST /api/persons/{id}/rsvp` accepting a token; protect list/delete endpoints (token or simple admin secret) (F-2, F-10, gap 1–3).
5. Wire the HTML to the API: fetch tree on load, colour spots from `rsvp_status`, accept/decline buttons in the click modal calling the RSVP endpoint (F-5, gap 4–5). Delete the duplicate HTML file (F-6).
6. Add pytest contract tests for persons/registrations/RSVP incl. negative cases (F-7).
7. Deployment: uvicorn entrypoint binding `PORT`, `docs/ARCHITECTURE.md`, hosting config (F-12).

---

# VERDICT: FAIL — the backend CRUD layer is a reusable foundation, but P0 security gaps (open CORS, unauthenticated deletes, DB in /tmp), the complete absence of the RSVP/tree-colour feature in the frontend, no tests and no git repo mean the code as it stands is not a sound foundation without the fixes above.

# Blinkdrop

Delivery feedback app: customers rate a delivery, problem reports become
*exceptions* on an internal dashboard. FastAPI backend, plain HTML/CSS frontend,
Firestore for storage, built for Cloud Run.

## Run locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
STORAGE_BACKEND=memory .venv/bin/python -m uvicorn app.main:app --port 8080
```

Then open <http://127.0.0.1:8080/> — the pages must be served by the app, not
opened as `file://`, since they call same-origin API routes (there is no CORS
middleware by design).

The memory backend seeds itself with demo exceptions covering all six statuses,
so the dashboard has something to show.

End-to-end check (server must already be running):

```bash
.venv/bin/python scripts/e2e_smoke.py http://127.0.0.1:8080
```

It drives a real browser twice: once normally, once with JavaScript disabled to
prove the form still works without it.

## API

Everything marked **admin** requires authentication (see Security below).

| Method | Path | Notes |
|---|---|---|
| GET | `/healthz` | liveness only |
| POST | `/api/feedback` | public. JSON → `201`; form-encoded → `303` to `/thanks.html`. Rate-limited; `job_ref` must name a known job |
| GET | `/api/exceptions?status=&limit=` | **admin.** `all`, `pending`, `needs-review`, `approved`, `waived`, `exported` |
| GET | `/api/stats` | **admin.** the four dashboard tiles + per-driver counts |
| PATCH | `/api/exceptions/{id}` | **admin.** move a status; only forward transitions, audited |
| GET | `/api/exceptions/{id}/events` | **admin.** who changed this record, and when |
| POST | `/api/dev/seed` | **admin.** additive demo data; off unless `ALLOW_DEV_ENDPOINTS`. To seed a real database use `scripts/seed_firestore.py` |

## Business rules

**The wireframe never defined how feedback becomes an exception.** Everything
below was invented for this build and lives in `app/mapping.py` + `app/config.py`
so it is cheap to change:

- An exception is created when the delivery was **late**, **damaged**, or rated
  **2 stars or fewer**. A clean 3–5 star delivery is stored as feedback only.
- Type precedence is `damaged > late > service`; both flags are kept so the
  table can read "Damaged + Late".
- Rate card: late `$5.00`, damaged `$12.00`, rating-only `$0.00`, and the two
  flags **sum** to `$17.00`.
- Everything starts `pending`. The lifecycle `pending → needs_review →
  approved | waived → exported` is moved by an authenticated human via `PATCH`,
  and only forwards — a settled charge cannot be reopened, and every move is
  recorded with who made it.
- "Pending review" counts open items all-time; "Approved today" sums charges
  approved today; "Top driver" is the most exceptions today, alphabetical
  tie-break.
- The form doesn't collect a customer name — it's resolved from a `jobs` lookup
  keyed on job ref, falling back to "Unknown customer".

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8080` | set by Cloud Run |
| `STORAGE_BACKEND` | auto | `memory` or `firestore`; auto-detects from the vars below |
| `GOOGLE_CLOUD_PROJECT` | — | selects Firestore when set |
| `FIRESTORE_DATABASE` | `(default)` | Firestore database id |
| `FIRESTORE_EMULATOR_HOST` | — | selects Firestore against a local emulator |
| `SEED_ON_STARTUP` | true on memory | never defaults true against Firestore |
| `ALLOW_DEV_ENDPOINTS` | true on memory | gates `/api/dev/seed` |
| `APP_TIMEZONE_OFFSET_HOURS` | `0` | day boundary for the "today" tiles |
| `ADMIN_AUTH` | derived | `iap`, `basic`, or `off` — see Security |
| `ADMIN_USER` / `ADMIN_PASSWORD` | `admin` / — | credentials for `basic` |
| `IAP_AUDIENCE` | — | required for `iap`; selects `iap` when set |
| `IAP_ALLOWED_EMAILS` | — | optional comma-separated allowlist |
| `REQUIRE_KNOWN_JOB` | true | reject feedback naming an unknown job |
| `EXPOSE_DOCS` | true on memory | `/docs` and `/openapi.json` |
| `MAX_BODY_BYTES` | `65536` | request bodies above this are rejected |
| `FEEDBACK_RATE_LIMIT_PER_MINUTE` | `20` | per instance, per client address |

Backend selection: explicit `STORAGE_BACKEND` wins, else `FIRESTORE_EMULATOR_HOST`,
else Cloud Run/`GOOGLE_CLOUD_PROJECT`, else memory.

## Security

The feedback form is public by necessity. **Everything else is not**: the
dashboard, the exception and stats APIs, and the status-change endpoint all
require authentication.

`ADMIN_AUTH` picks how:

- **`iap`** — validates the JWT Cloud IAP sets in `X-Goog-IAP-JWT-Assertion`.
  The production target: identity is Google's and the app stores no password.
  Needs an external HTTPS load balancer with IAP in front of the service.
- **`basic`** — HTTP Basic against `ADMIN_PASSWORD`, which should come from
  Secret Manager. The stopgap when there is no load balancer.
- **`off`** — no check. Local development only.

If neither is configured and the backend is Firestore, the admin routes return
**503 rather than serving** — a deploy that forgets credentials fails closed
instead of exposing customer data.

Status changes only move forward (`pending → needs_review → approved | waived →
exported`), every change records who made it, and `GET /api/exceptions/{id}/events`
returns that history.

A full assessment, including what was found and what is still outstanding, is in
[`04-security-engineer/REVIEW.md`](04-security-engineer/REVIEW.md).

## Deploy to Cloud Run

Use `./deploy.sh`, which does all of the below idempotently:

```bash
PROJECT=my-project REGION=europe-west1 ./deploy.sh
```

It creates a **dedicated runtime service account** with a custom role granting
only Firestore create/get/list/update — deliberately **not** delete — and wires
`ADMIN_PASSWORD` from Secret Manager. Do not deploy without `--service-account`:
the Compute Engine default identity holds `roles/editor` on the whole project,
which would make any future compromise of this service a project-wide one.

`--source .` builds through Cloud Build, so local Docker isn't needed.

To seed a real database, run it locally against your own credentials — there is
no endpoint that can delete or overwrite production data:

```bash
gcloud auth application-default login
GOOGLE_CLOUD_PROJECT=<project> python scripts/seed_firestore.py
```

CI deploys are in `.github/workflows/deploy.yml`, using Workload Identity
Federation (no service account keys). It stays inert until you create the WIF
pool and set the `GCP_PROJECT`, `GCP_REGION`, `GCP_WIF_PROVIDER`, `GCP_DEPLOY_SA`
and `GCP_RUNTIME_SA` repository variables.

### Known gaps

- **The Docker image has never been built.** It was written in a sandbox with no
  Docker daemon. `gcloud run deploy --source .` builds remotely, so this is the
  first place it gets exercised.
- **The Firestore path is untested.** No emulator was available (no `gcloud` in
  the sandbox), so `app/firestore_repo.py` is verified only by inspection and by
  sharing its stats math with the in-memory backend. Smoke-test it against a real
  database before trusting it.
- **The in-app rate limit is per instance.** Cloud Run autoscales, so a
  distributed flood gets a multiple of it. Put Cloud Armor in front of
  `POST /api/feedback` before carrying real traffic.
- **Feedback submissions are not bound to a delivery.** A known `job_ref` can be
  submitted against repeatedly. Per-delivery single-use tokens are the fix; see
  D1 in the review.

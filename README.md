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

| Method | Path | Notes |
|---|---|---|
| GET | `/healthz` | reports the resolved storage backend |
| POST | `/api/feedback` | JSON → `201`; form-encoded → `303` to `/thanks.html` |
| GET | `/api/exceptions?status=&limit=` | `all`, `pending`, `needs-review`, `approved`, `waived`, `exported` |
| GET | `/api/stats` | the four dashboard tiles + per-driver counts |
| PATCH | `/api/exceptions/{id}` | move an exception's status |
| POST | `/api/dev/seed?force=` | demo data; disabled unless `ALLOW_DEV_ENDPOINTS` |

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
  approved | waived → exported` is moved by a human via `PATCH`.
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

Backend selection: explicit `STORAGE_BACKEND` wins, else `FIRESTORE_EMULATOR_HOST`,
else Cloud Run/`GOOGLE_CLOUD_PROJECT`, else memory.

## Deploy to Cloud Run

```bash
gcloud services enable run.googleapis.com firestore.googleapis.com \
  cloudbuild.googleapis.com artifactregistry.googleapis.com

gcloud firestore databases create --location=<REGION>   # Native mode, once

gcloud run deploy blinkdrop --source . --region <REGION> --allow-unauthenticated \
  --set-env-vars STORAGE_BACKEND=firestore,GOOGLE_CLOUD_PROJECT=<PROJECT>

gcloud projects add-iam-policy-binding <PROJECT> \
  --member serviceAccount:<RUNTIME_SA> --role roles/datastore.user
```

`--source .` builds through Cloud Build, so local Docker isn't needed.

To seed the real database once, deploy with `ALLOW_DEV_ENDPOINTS=true`, run
`curl -X POST "$URL/api/dev/seed"`, then redeploy without it.

### Known gaps

- **The Docker image has never been built.** It was written in a sandbox with no
  Docker daemon. `gcloud run deploy --source .` builds remotely, so this is the
  first place it gets exercised.
- **The Firestore path is untested.** No emulator was available (no `gcloud` in
  the sandbox), so `app/firestore_repo.py` is verified only by inspection and by
  sharing its stats math with the in-memory backend. Test it against a real
  database before trusting it.
- **There is no authentication.** `--allow-unauthenticated` is required for the
  public feedback form, which means the dashboard at `/dashboard.html` and every
  `/api/*` route are public too. Add an auth layer before real data goes in.

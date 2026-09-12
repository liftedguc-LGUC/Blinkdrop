# Security Review — Blinkdrop

**Reviewed:** commit `38f4fbe` (stage 03 output)
**Patched in:** commit following this document
**Scope:** the application at the repo root — FastAPI service, static frontend,
Firestore storage, Cloud Run deployment guidance.
**Attacker model:** anonymous, internet-reachable, has read the source.

## Summary

The expected problem was that the dashboard is publicly readable. That is real
but secondary. **The serious finding is that the billing state machine was
anonymously writable.** Anyone who could reach the URL could waive every
outstanding charge, mass-approve records to inflate the operator's revenue
tile, and fabricate damage charges against named drivers for deliveries that
never happened — and because `approved_at` is set once and never reset, the
original approval timestamps were destroyed in the process.

Five High findings, four Medium, two Low. All Highs and all actionable Mediums
are patched. Two design flaws are accepted with a recommendation rather than
patched, and are listed as conditions on the sign-off.

## Findings

| # | Sev | Finding | Location | Status |
|---|-----|---------|----------|--------|
| H1 | High | `PATCH /api/exceptions/{id}` unauthenticated, no transition rules — anyone can waive or approve any charge, destroying `approved_at` | `app/routes_api.py` | **Patched** |
| H2 | High | Driver attributed by string-splitting the client-supplied `job_ref` — fabricate charges against a named employee | `app/mapping.py`, `app/routes_api.py` | **Patched** |
| H3 | High | README instructed enabling `ALLOW_DEV_ENDPOINTS` in production; `POST /api/dev/seed?force=true` then deletes every document in both collections | `app/routes_api.py`, `README.md` | **Patched** |
| H4 | High | Deploy command omits `--service-account`, so the service runs as the Compute Engine default SA holding `roles/editor` project-wide | `README.md` | **Patched** |
| H5 | High | Unbounded anonymous writes amplified by unbounded `/api/stats` queries — Firestore cost and instance OOM | `app/firestore_repo.py`, `app/routes_api.py` | **Patched** |
| M6 | Medium | Anonymous read of customer names, driver performance and chargeback revenue | `app/routes_api.py` | **Patched** (same auth boundary as H1) |
| M7 | Medium | Malformed JSON returned 500 with a full traceback to logs; legitimate over-long comments failed opaquely | `app/routes_api.py` | **Patched** |
| M8 | Medium | `/docs`, `/redoc`, `/openapi.json` public and advertising the destructive seed endpoint | `app/main.py` | **Patched** |
| M9 | Medium | No request body size limit; multipart file parts spool to memory-backed container disk | `app/middleware.py` | **Patched** |
| L10 | Low | No security response headers | `app/middleware.py` | **Patched** |
| L11 | Low | Mutable base image tag, no `--proxy-headers` (no client IP in logs), `/healthz` disclosed the storage backend | `Dockerfile`, `app/routes_api.py` | **Patched** |

### H1 — anonymous control of the billing state machine

`PATCH` accepted any status for any id, in any direction, with no identity. An
attacker harvests ids from `GET /api/exceptions?limit=500`, then moves every
record to `waived` — the courier bills nobody. The reverse inflates "Approved
today", because moving to `approved` also stamps `approved_at`, which is written
once and never reset. The original approval time is then unrecoverable: this is
irreversible corruption of financial audit data, not just a nuisance.

**Patch.** `require_admin` on the route; a transition table (`pending →
needs_review → approved | waived → exported`) rejecting sideways and backward
moves with 409; every accepted change records `updated_by` and appends an
immutable row to `exception_events`, readable at
`GET /api/exceptions/{id}/events`. "Who waived this charge, and when" is now
answerable.

### H2 — attacker-controlled driver attribution

`parse_driver()` split the client-supplied `job_ref` on an em dash and used the
right-hand side as the driver. A request naming a job that never existed still
produced an exception attributed to whatever name the attacker typed — verified
during the audit: `Job #9999 - Alex M.` with `late` and `damaged` set yields a
$17.00 charge against Alex M. and puts them top of the driver leaderboard. With
"Rate cards" in the product and money on each row, that is a wage-theft and
defamation primitive.

**Patch.** `parse_driver` is deleted. Attribution comes only from a `jobs`
record; an unknown `job_ref` is rejected with 404 (the form path redirects to
`/form.html?error=1`). `REQUIRE_KNOWN_JOB=false` exists for local experiments
and defaults to on.

### H3 — destructive endpoint the README told you to expose

The gate itself was sound — `K_SERVICE` is always set on Cloud Run, so the
derived default was closed, and the audit could not find a Cloud Run
configuration where it failed open. The danger was the documented seeding
procedure: deploy with `ALLOW_DEV_ENDPOINTS=true`, curl, redeploy. During that
window one anonymous request deletes both collections — and the normal outcome
of a manual three-step procedure is that step three gets skipped.

**Patch.** The `force` branch is gone; the endpoint is additive only and no
longer in the schema. `FirestoreRepository.clear()` now raises rather than
deleting. Real seeding is `scripts/seed_firestore.py`, run locally with your own
credentials. The README procedure is removed.

### H4 — the service account

Following the README produced an internet-facing service running as the Compute
Engine default SA, which holds `roles/editor` on the entire project. Any future
SSRF or dependency compromise escalates to project takeover. The `<RUNTIME_SA>`
placeholder in the IAM step was never defined anywhere.

**Patch.** `README.md` and `deploy.sh` now create a dedicated service account and
a **custom role that deliberately omits `datastore.entities.delete`** — the exact
permission that made H3 destructive. Defence in depth: even a re-introduced
`clear()` would be denied by IAM.

### H5 — cost and availability

`/api/stats` ran an all-time, unlimited query for open exceptions. Every
exception is born `pending`, so an attacker looping the public feedback endpoint
made every subsequent dashboard load read the entire collection — at a million
records, real money per refresh, and an OOM in a 512 MiB container well before
that. `by_driver` also grew without bound, and driver names were attacker-chosen
(H2).

**Patch.** Every Firestore query is capped at `MAX_QUERY_RESULTS`; `by_driver` is
capped at 25; `count_exceptions()` stops at one document instead of scanning; a
per-instance token bucket limits `POST /api/feedback`. **The rate limiter is per
instance and Cloud Run autoscales**, so it slows a single source but is not the
real control — Cloud Armor at the edge is, and the README says so.

## IAM and surface check

### Route surface, after patching

| Route | Before | After |
|---|---|---|
| `GET /`, `/landing.html`, `/form.html`, `/thanks.html` | public | public *(intended)* |
| `GET /styles.css`, `/app.js` | public | public *(intended)* |
| `POST /api/feedback` | public, unlimited | public, rate-limited, known-job only, 64 KiB cap |
| `GET /dashboard.html` | **public** | **authenticated** |
| `GET /api/exceptions` | **public** | **authenticated** |
| `GET /api/stats` | **public** | **authenticated** |
| `PATCH /api/exceptions/{id}` | **public, unrestricted** | **authenticated + transition-checked + audited** |
| `GET /api/exceptions/{id}/events` | did not exist | authenticated |
| `POST /api/dev/seed` | public when flag on; destructive | authenticated, additive only, off by default, not in schema |
| `/docs`, `/openapi.json` | public | disabled unless `EXPOSE_DOCS` |
| `/healthz` | disclosed storage backend | bare `{"status":"ok"}` |

Authentication resolves from the environment and **fails closed**: a Firestore
backend with nothing configured returns 503 on every admin route while leaving
the public form working. A deploy that forgets to set credentials cannot serve
customer data to the internet.

### IAM, before and after

| | Before | After |
|---|---|---|
| Runtime identity | Compute Engine default SA | dedicated `blinkdrop-run@` |
| Effective roles | `roles/editor` on the project | custom role, 5 Firestore permissions |
| Can delete Firestore documents | yes | **no** (`datastore.entities.delete` withheld) |
| Blast radius of app compromise | whole project | the app's own two collections, read/write, no delete |

## Verified non-findings

Attacked and held. Listed so a later change does not quietly undo them — each
now has a regression test.

- **Path traversal in the static route.** The allowlist is checked against a
  frozen set of literals *before* any path is built, so the filesystem is never
  touched for a non-member. `..`, encoded slashes, and null bytes all 404.
- **Stored XSS via the comment field.** Two independent reasons: `app.js` uses
  `textContent` everywhere (no `innerHTML`, no `eval`, no `document.write`
  anywhere in the repo), and the dashboard never renders `comment` at all. A
  `<script>` payload round-trips through the API intact and has no rendering
  path. CSP now backs this up rather than carrying it.
- **Prototype pollution in the status lookup.** `item.status` passes Pydantic
  validation on every read path including Firestore, so only the five enum
  strings can arrive.
- **Firestore query injection.** Values are enum-validated and the client library
  uses structured protobufs. `.document(exc_id)` cannot escape its collection
  because Starlette's path converter excludes `/`.
- **CSRF.** Was moot before (no ambient credentials to abuse). Now that Basic
  auth exists it is worth a second look if any state-changing control is ever
  added to the dashboard UI — today `PATCH` is API-only.

## Design flaws — accepted, not patched

**D1. Feedback submission has no capability token.** A public form cannot require
a login, but the standard answer is a single-use per-delivery token in the link
the customer receives (`/form.html?t=…`). Requiring a known `job_ref` (H2) closes
the attribution hole, but anyone who learns a valid job reference can still
submit repeatedly against it. A token would make submissions single-use and give
rate limiting a real key. **This is the highest-value next change.**

**D2. Public and privileged surfaces share one service.** The form must be
`--allow-unauthenticated`, so the dashboard is served by the same
internet-reachable service and protected only in application code. Best practice
on Cloud Run is two services — public form, and an admin service with
`--no-allow-unauthenticated` behind IAP — so Google identity guards the
dashboard and no shared password exists. The routers are already cleanly split,
so this is close to a config change. It needs an external HTTPS load balancer,
which is why it was not done here.

The auth layer was built with D2 as the destination: `ADMIN_AUTH=iap` validates
the `X-Goog-IAP-JWT-Assertion` header today, so moving to IAP is a configuration
change, not a rewrite.

## Verification

- `pytest` — **75 passing**, up from 29. New coverage: auth on every admin route,
  the fail-closed 503, IAP claim handling, transition rules, audit events,
  unknown-job rejection, malformed JSON, body cap, rate limiting, docs disabled,
  security headers, and the path-traversal non-finding.
- `scripts/e2e_smoke.py` — three browser passes against a live server: JS-on
  submission through to a rendered dashboard row; JS-off submission still
  persisting via the 303; and the admin surface returning 401 without
  credentials while the form stays public.
- Confirmed by hand against a running instance: anonymous `dashboard.html` 401,
  `api/stats` 401, `form.html` 200, `POST /api/feedback` 201.

**Not verified here, and it matters:**

- **The Firestore backend has never been executed.** No `gcloud` and therefore no
  emulator in the review environment. `firestore_repo.py` — including the query
  caps added under H5 and the `clear()` refusal under H3 — is verified by
  inspection only. It shares its statistics logic with the in-memory backend,
  which *is* tested, but the query layer is not.
- **IAP verification is tested against a stub.** The claim handling (issuer,
  email allowlist) is covered; Google's signature verification is not exercised.
- **The Docker image has never been built.** No daemon available.

## Sign-off

**Approved to deploy, conditionally.** The findings that made this dangerous to
expose are fixed and covered by tests. It is not approved unconditionally,
because three things below are unverifiable from here and one is a standing
design gap.

Conditions, in order:

1. Deploy with a **dedicated service account and the custom role** in
   `README.md` — not the default SA. This is what keeps H3 unexploitable even if
   the code regresses.
2. Set `ADMIN_AUTH` and its credential. The app fails closed if you forget, so
   the failure mode is a 503 rather than an exposure — but it means the
   dashboard will not work until you do.
3. **Smoke-test against real Firestore before trusting it**, since that backend
   has never run. Submit one piece of feedback, load the dashboard, move one
   record through a status change, and confirm the event was written.
4. Put **Cloud Armor** in front of `POST /api/feedback`. The in-app limiter is
   per instance and does not survive autoscaling.
5. Schedule D1 (per-delivery tokens) and D2 (split services behind IAP). Neither
   blocks this deploy; both should land before the pilot carries real customer
   data at volume.

*Reviewed and patched by the 04-security-engineer stage. The patches are in the
repo root; this document is the record.*

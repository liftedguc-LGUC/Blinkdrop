# Role: Security Engineer

> **Stage brief.** The live, deployable app is at the repo root — that is the
> only copy that changes. `01-pm/` and `02-uiux-developer/` are frozen snapshots
> captured at commit `6ea38e3`; never edit a file inside them.

You assess the software engineer's application, write up the findings, patch
what is serious, re-verify, and decide whether it may ship.

## Inputs
- The application at the repo root (`app/`, `app.js`, the four HTML pages)
- `../03-swe/CLAUDE.md` — what the previous stage set out to build
- `../README.md` — the deployment posture as documented

## Produced
- `REVIEW.md` — findings table, IAM and attack-surface check, verified
  non-findings, design flaws, and the sign-off
- Patches applied **at the repo root**, not here

## A note on where patches go

The stage instruction said to patch "in `03-swe/`". In this repo the application
lives at the root and `03-swe/` holds only that stage's brief, so patches landed
at the root. This matches the repo rule in `../CLAUDE.md` that `0N-*/` folders
are append-only history. On the local machine, where `03-swe/` *is* the project
root, the two readings are the same directory.

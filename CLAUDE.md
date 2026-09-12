# Blinkdrop — delivery feedback app

Built by a staged agent pipeline. Each stage folder holds that stage's role brief
and a frozen snapshot of what it produced; the live, deployable app is at the
repo root.

| Stage | Folder | Produced |
|---|---|---|
| 1. Product manager | `01-pm/` | `wireframe.html` — four-screen low-fidelity wireframe |
| 2. UI/UX developer | `02-uiux-developer/` | `design-spec.md`, `styles.css`, the four HTML pages |
| 3. Software engineer | `03-swe/` | the FastAPI backend, frontend wiring, deploy config |

## The one rule

**Only root files change.** The `0N-*/` folders are append-only history — never
edit a file inside one. They were captured at commit `6ea38e3`, so what a later
stage changed is always one command away:

```
git diff 6ea38e3 -- form.html dashboard.html styles.css
```

## The app

Static pages (`landing.html` → `form.html` → `thanks.html`, plus
`dashboard.html`) served by a FastAPI service in `app/` that stores feedback and
derives exception records from it. See `README.md` for how to run, test, and
deploy it, and `app/mapping.py` for the feedback → exception business rules.

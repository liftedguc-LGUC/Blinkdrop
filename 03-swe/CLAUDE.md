# Role: Software Engineer

> **Stage brief.** The live, deployable app lives at the repo root — that is the
> only copy that changes. `01-pm/` and `02-uiux-developer/` are frozen snapshots
> captured at commit `6ea38e3`; never edit a file inside them.

You take the UI/UX developer's static frontend and make it a real application.

## Inputs
- `../02-uiux-developer/` — the frozen frontend and its design spec
- `gcp-docs` MCP server — Google Cloud documentation lookup (see below)

## Produced (at the repo root)
- `app/` — FastAPI service: feedback submission, exception listing, dashboard stats
- `app.js` — vanilla frontend wiring (no framework, no build step)
- `tests/`, `scripts/e2e_smoke.py` — pytest suites and a Playwright round-trip
- `Dockerfile`, `.dockerignore`, `.gcloudignore`, `README.md` — Cloud Run deploy

## MCP

`.mcp.json` in this folder mirrors the local setup at
`/Users/inardini/Desktop/feedback-app/03-swe/.mcp.json`, where a `gcp-docs`
server exposing 3 tools is connected.

**The launch command and args were not visible in the reference screenshot and
were deliberately left as `<FILL IN>` rather than guessed.** Paste the real
`command`/`args` from the local machine before using it.

Two notes:
- Claude Code auto-loads a project-scoped `.mcp.json` from the **project root**.
  On the local machine `03-swe/` *is* the project root, so the file works there.
  Opened at this repo's root, the file here is inert — keep it as the stage
  record, or copy it to the repo root if you want the server loaded in sessions
  started there.
- If credentials are ever added to its `env` block, move the file to
  `.gitignore` — it is currently versioned in the clear.

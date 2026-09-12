"""Serves the frontend from an explicit allowlist.

Not a directory mount: the repo root also holds app/, tests/, .git/ and the
stage folders, and a mount would happily serve all of it.

The allowlist check runs against a frozen set of literal names before any path
is built, so no traversal payload reaches the filesystem.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from .auth import Principal, require_admin
from .config import get_settings

PUBLIC_PAGES = {"landing.html", "form.html", "thanks.html"}
ADMIN_PAGES = {"dashboard.html"}
ASSETS = {"styles.css", "app.js"}
PUBLIC = PUBLIC_PAGES | ASSETS
SERVABLE = PUBLIC | ADMIN_PAGES

router = APIRouter()


def _serve(name: str) -> FileResponse:
    path = get_settings().web_dir / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="not found")
    headers = {"Cache-Control": "no-store" if name.endswith(".html") else "max-age=300"}
    return FileResponse(path, headers=headers)


@router.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return _serve("landing.html")


@router.get("/dashboard.html", include_in_schema=False)
async def dashboard(_: Principal = Depends(require_admin)) -> FileResponse:
    # Registered ahead of the catch-all so the admin page cannot be reached
    # without going through auth.
    return _serve("dashboard.html")


@router.get("/{name}", include_in_schema=False)
async def public_file(name: str) -> FileResponse:
    if name not in PUBLIC:
        raise HTTPException(status_code=404, detail="not found")
    return _serve(name)

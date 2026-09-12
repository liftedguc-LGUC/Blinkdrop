"""Serves the frontend from an explicit allowlist.

Not a directory mount: the repo root also holds app/, tests/, .git/ and the
stage folders, and a mount would happily serve all of it.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .config import get_settings

PAGES = {"landing.html", "form.html", "thanks.html", "dashboard.html"}
ASSETS = {"styles.css", "app.js"}
PUBLIC = PAGES | ASSETS

router = APIRouter()


def _serve(name: str) -> FileResponse:
    path = get_settings().web_dir / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="not found")
    headers = {"Cache-Control": "no-store" if name in PAGES else "max-age=300"}
    return FileResponse(path, headers=headers)


@router.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return _serve("landing.html")


@router.get("/{name}", include_in_schema=False)
async def public_file(name: str) -> FileResponse:
    if name not in PUBLIC:
        raise HTTPException(status_code=404, detail="not found")
    return _serve(name)

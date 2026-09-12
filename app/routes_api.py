import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import ValidationError

from .auth import Principal, require_admin
from .config import MAX_QUERY_RESULTS, Settings, get_settings
from .mapping import to_exception
from .models import (
    ALLOWED_TRANSITIONS,
    ExceptionRecord,
    ExceptionStatus,
    FeedbackIn,
    FeedbackOut,
    FeedbackRecord,
    StatsOut,
    StatusPatch,
    normalize_status,
)
from .rate_limit import enforce_rate_limit
from .repository import Repository
from .seed import seed_records

router = APIRouter()


def get_repo(request: Request) -> Repository:
    return request.app.state.repo


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    # Deliberately says nothing about which storage backend is in use: that
    # doubles as a hint about whether dev endpoints are enabled.
    return {"status": "ok"}


async def _store_feedback(payload: FeedbackIn, repo: Repository, settings: Settings) -> FeedbackOut:
    now = datetime.now(timezone.utc)
    job = await repo.get_job(payload.job_ref)
    if job is None and settings.require_known_job:
        # The driver used to be parsed out of this client-supplied string, which
        # let anyone file charges against any named employee for deliveries that
        # never happened. Attribution now comes only from a known job.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown job reference")

    record = FeedbackRecord(
        job_ref=payload.job_ref,
        driver=job.driver if job else "Unassigned",
        customer=job.customer if job else "Unknown customer",
        rating=payload.rating,
        comment=payload.comment,
        late=payload.late,
        damaged=payload.damaged,
        created_at=now,
    )
    feedback_id = await repo.add_feedback(record)

    exception = to_exception(payload, job, now=now)
    exception_id = None
    if exception is not None:
        exception.feedback_id = feedback_id
        exception_id = await repo.add_exception(exception)

    return FeedbackOut(
        feedback_id=feedback_id,
        exception_id=exception_id,
        exception_created=exception_id is not None,
    )


@router.post("/api/feedback")
async def submit_feedback(
    request: Request,
    repo: Repository = Depends(get_repo),
    settings: Settings = Depends(get_settings),
):
    """Accepts JSON (returns 201) or a native form POST (redirects to thanks.html).

    Both shapes normalize into FeedbackIn, so the business logic has one path.
    """
    enforce_rate_limit(request, settings)

    content_type = request.headers.get("content-type", "")
    is_form = content_type.startswith(("application/x-www-form-urlencoded", "multipart/form-data"))

    if is_form:
        form = await request.form(max_files=8, max_fields=8)
        if any(hasattr(value, "filename") for value in form.values()):
            return RedirectResponse("/form.html?error=1", status_code=303)
        rating = form.get("rating")
        try:
            payload = FeedbackIn(
                job_ref=str(form.get("job_ref") or "").strip(),
                rating=int(rating) if rating else None,
                comment=str(form.get("comment") or ""),
                late=form.get("late") is not None,
                damaged=form.get("damaged") is not None,
            )
        except (ValueError, TypeError):
            return RedirectResponse("/form.html?error=1", status_code=303)
        try:
            await _store_feedback(payload, repo, settings)
        except HTTPException:
            return RedirectResponse("/form.html?error=1", status_code=303)
        return RedirectResponse("/thanks.html", status_code=303)

    # Parsed by hand rather than through a body parameter, so FastAPI's
    # RequestValidationError handler never sees it: without this guard every
    # malformed request became a 500 with a traceback in the logs.
    try:
        payload = FeedbackIn.model_validate(await request.json())
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError, TypeError, RecursionError):
        raise HTTPException(status_code=422, detail="invalid feedback payload") from None

    result = await _store_feedback(payload, repo, settings)
    return JSONResponse(result.model_dump(), status_code=201)


@router.get("/api/exceptions")
async def list_exceptions(
    status_filter: str = Query(default="all", alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    repo: Repository = Depends(get_repo),
    _: Principal = Depends(require_admin),
) -> dict[str, object]:
    normalized = normalize_status(status_filter)
    if normalized in {"all", ""}:
        wanted = None
    elif normalized in set(ExceptionStatus):
        wanted = normalized
    else:
        # The value itself is not echoed back: no reflecting raw input.
        raise HTTPException(status_code=422, detail="unknown status filter")

    items = await repo.list_exceptions(wanted, limit)
    return {
        "items": [item.model_dump(mode="json") for item in items],
        "count": len(items),
        "status": normalized or "all",
    }


@router.get("/api/stats", response_model=StatsOut)
async def stats(
    repo: Repository = Depends(get_repo),
    settings: Settings = Depends(get_settings),
    _: Principal = Depends(require_admin),
) -> StatsOut:
    day_start, day_end = settings.day_bounds()
    return await repo.stats(day_start, day_end)


@router.patch("/api/exceptions/{exception_id}", response_model=ExceptionRecord)
async def patch_exception(
    exception_id: str,
    patch: StatusPatch,
    repo: Repository = Depends(get_repo),
    principal: Principal = Depends(require_admin),
) -> ExceptionRecord:
    current = await repo.get_exception(exception_id)
    if current is None:
        raise HTTPException(status_code=404, detail="exception not found")

    if patch.status not in ALLOWED_TRANSITIONS[current.status]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"cannot move an exception from {current.status} to {patch.status}",
        )

    updated = await repo.update_exception_status(exception_id, patch.status, str(principal))
    if updated is None:
        raise HTTPException(status_code=404, detail="exception not found")
    return updated


@router.get("/api/exceptions/{exception_id}/events")
async def exception_events(
    exception_id: str,
    repo: Repository = Depends(get_repo),
    _: Principal = Depends(require_admin),
) -> dict[str, object]:
    events = await repo.list_events(exception_id, MAX_QUERY_RESULTS)
    return {"items": [event.model_dump(mode="json") for event in events], "count": len(events)}


@router.post("/api/dev/seed", include_in_schema=False)
async def dev_seed(
    repo: Repository = Depends(get_repo),
    settings: Settings = Depends(get_settings),
    _: Principal = Depends(require_admin),
) -> JSONResponse:
    """Additive only. The destructive force=true branch that called repo.clear()
    was removed: seeding a real database is scripts/seed_firestore.py, run
    locally with your own credentials."""
    if not settings.allow_dev_endpoints:
        raise HTTPException(status_code=404, detail="not found")
    if await repo.count_exceptions() > 0:
        return JSONResponse({"created": 0, "skipped": "store not empty"}, status_code=200)
    created = await seed_records(repo)
    return JSONResponse({"created": created}, status_code=201)

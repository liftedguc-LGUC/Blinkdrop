from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse

from .config import Settings, get_settings
from .mapping import parse_driver, to_exception
from .models import (
    ExceptionRecord,
    ExceptionStatus,
    FeedbackIn,
    FeedbackOut,
    FeedbackRecord,
    StatsOut,
    StatusPatch,
    normalize_status,
)
from .repository import Repository
from .seed import seed_records

router = APIRouter()


def get_repo(request: Request) -> Repository:
    return request.app.state.repo


@router.get("/healthz")
async def healthz(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {"status": "ok", "backend": settings.backend}


async def _store_feedback(payload: FeedbackIn, repo: Repository) -> FeedbackOut:
    now = datetime.now(timezone.utc)
    job = await repo.get_job(payload.job_ref)
    record = FeedbackRecord(
        job_ref=payload.job_ref,
        driver=job.driver if job else parse_driver(payload.job_ref),
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
async def submit_feedback(request: Request, repo: Repository = Depends(get_repo)):
    """Accepts JSON (returns 201) or a native form POST (redirects to thanks.html).

    Both shapes normalize into FeedbackIn, so the business logic has one path.
    """
    content_type = request.headers.get("content-type", "")
    is_form = content_type.startswith(("application/x-www-form-urlencoded", "multipart/form-data"))

    if is_form:
        form = await request.form()
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
        await _store_feedback(payload, repo)
        return RedirectResponse("/thanks.html", status_code=303)

    payload = FeedbackIn.model_validate(await request.json())
    result = await _store_feedback(payload, repo)
    return JSONResponse(result.model_dump(), status_code=201)


@router.get("/api/exceptions")
async def list_exceptions(
    status: str = Query(default="all"),
    limit: int = Query(default=100, ge=1, le=500),
    repo: Repository = Depends(get_repo),
) -> dict[str, object]:
    normalized = normalize_status(status)
    if normalized in {"all", ""}:
        wanted = None
    elif normalized in set(ExceptionStatus):
        wanted = normalized
    else:
        raise HTTPException(status_code=422, detail=f"unknown status '{status}'")

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
) -> StatsOut:
    day_start, day_end = settings.day_bounds()
    return await repo.stats(day_start, day_end)


@router.patch("/api/exceptions/{exception_id}", response_model=ExceptionRecord)
async def patch_exception(
    exception_id: str,
    patch: StatusPatch,
    repo: Repository = Depends(get_repo),
) -> ExceptionRecord:
    updated = await repo.update_exception_status(exception_id, patch.status)
    if updated is None:
        raise HTTPException(status_code=404, detail="exception not found")
    return updated


@router.post("/api/dev/seed")
async def dev_seed(
    force: bool = Query(default=False),
    repo: Repository = Depends(get_repo),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    if not settings.allow_dev_endpoints:
        raise HTTPException(status_code=404, detail="not found")
    if force:
        await repo.clear()
    elif await repo.count_exceptions() > 0:
        return JSONResponse({"created": 0, "skipped": "store not empty"}, status_code=200)
    created = await seed_records(repo)
    return JSONResponse({"created": created}, status_code=201)

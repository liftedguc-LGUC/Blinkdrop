import asyncio
from collections import Counter
from datetime import datetime
from typing import Protocol

from .config import MAX_DRIVERS_REPORTED
from .models import (
    DriverCount,
    ExceptionEvent,
    ExceptionRecord,
    ExceptionStatus,
    FeedbackRecord,
    Job,
    StatsOut,
)

OPEN_STATUSES = (ExceptionStatus.PENDING, ExceptionStatus.NEEDS_REVIEW)
CHARGED_STATUSES = (ExceptionStatus.APPROVED, ExceptionStatus.EXPORTED)


class Repository(Protocol):
    async def add_feedback(self, fb: FeedbackRecord) -> str: ...
    async def add_exception(self, exc: ExceptionRecord) -> str: ...
    async def get_exception(self, exc_id: str) -> ExceptionRecord | None: ...
    async def list_exceptions(self, status: str | None, limit: int) -> list[ExceptionRecord]: ...
    async def update_exception_status(
        self, exc_id: str, status: ExceptionStatus, actor: str
    ) -> ExceptionRecord | None: ...
    async def list_events(self, exc_id: str, limit: int) -> list[ExceptionEvent]: ...
    async def stats(self, day_start: datetime, day_end: datetime) -> StatsOut: ...
    async def get_job(self, job_ref: str) -> Job | None: ...
    async def count_exceptions(self) -> int: ...
    async def clear(self) -> None: ...


def build_stats(records: list[ExceptionRecord], day_start: datetime, day_end: datetime) -> StatsOut:
    """Shared by both backends so the tile math has exactly one definition."""
    today = [e for e in records if day_start <= e.created_at < day_end]
    approved_today = [
        e
        for e in records
        if e.status in CHARGED_STATUSES and e.approved_at and day_start <= e.approved_at < day_end
    ]
    counts = Counter(e.driver for e in today)
    # Capped: driver names reach this from submitted data, so an unbounded list
    # would let the response body grow without limit.
    by_driver = [
        DriverCount(driver=name, count=n)
        for name, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:MAX_DRIVERS_REPORTED]
    ]
    return StatsOut(
        exceptions_today=len(today),
        pending_review=sum(1 for e in records if e.status in OPEN_STATUSES),
        approved_today_cents=sum(e.charge_cents for e in approved_today),
        approved_today_count=len(approved_today),
        top_driver=by_driver[0] if by_driver else None,
        by_driver=by_driver,
    )


class InMemoryRepository:
    """Backs local development and the test suite. Wiped on every process start."""

    def __init__(self, jobs: dict[str, Job] | None = None) -> None:
        self._feedback: dict[str, FeedbackRecord] = {}
        self._exceptions: dict[str, ExceptionRecord] = {}
        self._events: list[ExceptionEvent] = []
        self._jobs = jobs or {}
        self._counter = 0
        self._lock = asyncio.Lock()

    def _next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}_{self._counter:04d}"

    async def add_feedback(self, fb: FeedbackRecord) -> str:
        async with self._lock:
            fb.id = fb.id or self._next_id("fb")
            self._feedback[fb.id] = fb
            return fb.id

    async def add_exception(self, exc: ExceptionRecord) -> str:
        async with self._lock:
            exc.id = exc.id or self._next_id("exc")
            self._exceptions[exc.id] = exc
            if exc.feedback_id and exc.feedback_id in self._feedback:
                self._feedback[exc.feedback_id].exception_id = exc.id
            return exc.id

    async def get_exception(self, exc_id: str) -> ExceptionRecord | None:
        async with self._lock:
            return self._exceptions.get(exc_id)

    async def list_exceptions(self, status: str | None, limit: int) -> list[ExceptionRecord]:
        async with self._lock:
            items = list(self._exceptions.values())
        if status:
            items = [e for e in items if e.status == status]
        items.sort(key=lambda e: e.created_at, reverse=True)
        return items[:limit]

    async def update_exception_status(
        self, exc_id: str, status: ExceptionStatus, actor: str
    ) -> ExceptionRecord | None:
        async with self._lock:
            exc = self._exceptions.get(exc_id)
            if exc is None:
                return None
            previous = exc.status
            exc.status = status
            exc.updated_at = datetime.now(exc.created_at.tzinfo)
            exc.updated_by = actor
            if status in CHARGED_STATUSES and exc.approved_at is None:
                exc.approved_at = exc.updated_at
            self._events.append(
                ExceptionEvent(
                    id=self._next_id("evt"),
                    exception_id=exc_id,
                    from_status=previous,
                    to_status=status,
                    actor=actor,
                    at=exc.updated_at,
                )
            )
            return exc

    async def list_events(self, exc_id: str, limit: int) -> list[ExceptionEvent]:
        async with self._lock:
            return [e for e in self._events if e.exception_id == exc_id][:limit]

    async def stats(self, day_start: datetime, day_end: datetime) -> StatsOut:
        async with self._lock:
            records = list(self._exceptions.values())
        return build_stats(records, day_start, day_end)

    async def get_job(self, job_ref: str) -> Job | None:
        return self._jobs.get(job_ref)

    def put_job(self, job: Job) -> None:
        self._jobs[job.job_ref] = job

    async def count_exceptions(self) -> int:
        return len(self._exceptions)

    async def clear(self) -> None:
        async with self._lock:
            self._feedback.clear()
            self._exceptions.clear()
            self._events.clear()
            self._counter = 0

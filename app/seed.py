"""Deterministic demo data.

The dashboard is unreviewable against an empty store, so the memory backend
seeds itself on startup. Every status appears at least once, otherwise four of
the six filter pills would look broken. Seeded rows carry seeded=True.
"""

from datetime import datetime, timedelta, timezone

from .models import ExceptionRecord, ExceptionStatus, ExceptionType, Job
from .repository import CHARGED_STATUSES, Repository

JOBS = [
    Job(job_ref="Job #4821 — Alex M.", driver="Alex M.", customer="R. Patel"),
    Job(job_ref="Job #4822 — Priya N.", driver="Priya N.", customer="Greenway Foods"),
    Job(job_ref="Job #4823 — Tom B.", driver="Tom B.", customer="Novo Clinic"),
]

# (driver, customer, type, flags, charge_cents, status, hours_ago, rating)
_ROWS = [
    ("Alex M.", "R. Patel", ExceptionType.LATE, ["late"], 500, ExceptionStatus.PENDING, 1, 2),
    ("Alex M.", "Greenway Foods", ExceptionType.DAMAGED, ["damaged"], 1200, ExceptionStatus.NEEDS_REVIEW, 2, 1),
    ("Alex M.", "Novo Clinic", ExceptionType.DAMAGED, ["late", "damaged"], 1700, ExceptionStatus.APPROVED, 3, 1),
    ("Priya N.", "Greenway Foods", ExceptionType.LATE, ["late"], 500, ExceptionStatus.PENDING, 4, 3),
    ("Priya N.", "R. Patel", ExceptionType.SERVICE, [], 0, ExceptionStatus.WAIVED, 5, 2),
    ("Tom B.", "Novo Clinic", ExceptionType.DAMAGED, ["damaged"], 1200, ExceptionStatus.APPROVED, 6, 2),
    ("Tom B.", "Greenway Foods", ExceptionType.LATE, ["late"], 500, ExceptionStatus.EXPORTED, 7, 3),
    ("Tom B.", "R. Patel", ExceptionType.SERVICE, [], 0, ExceptionStatus.NEEDS_REVIEW, 8, 1),
]


def _label(flags: list[str]) -> str:
    if flags == ["late", "damaged"]:
        return "Damaged + Late"
    if flags == ["damaged"]:
        return "Damaged"
    if flags == ["late"]:
        return "Late"
    return "Service"


async def seed_records(repo: Repository) -> int:
    now = datetime.now(timezone.utc)
    if hasattr(repo, "put_job"):
        for job in JOBS:
            repo.put_job(job)

    created = 0
    for driver, customer, kind, flags, charge, status, hours_ago, rating in _ROWS:
        stamp = now - timedelta(hours=hours_ago)
        record = ExceptionRecord(
            job_ref=f"Job #48{20 + created} — {driver}",
            driver=driver,
            customer=customer,
            type=kind,
            flags=flags,
            type_label=_label(flags),
            charge_cents=charge,
            status=status,
            rating=rating,
            comment="",
            created_at=stamp,
            updated_at=stamp,
            approved_at=stamp if status in CHARGED_STATUSES else None,
            seeded=True,
        )
        await repo.add_exception(record)
        created += 1
    return created

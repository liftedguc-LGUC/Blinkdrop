from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ExceptionStatus(StrEnum):
    PENDING = "pending"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    WAIVED = "waived"
    EXPORTED = "exported"


class ExceptionType(StrEnum):
    DAMAGED = "damaged"
    LATE = "late"
    SERVICE = "service"


def normalize_status(raw: str) -> str:
    return raw.strip().lower().replace("-", "_")


# A charge moves forward through review, never sideways or backwards. Without
# this an authenticated slip (or, before auth existed, anyone at all) could flip
# a settled record back to pending and lose its approval timestamp.
ALLOWED_TRANSITIONS: dict[ExceptionStatus, frozenset[ExceptionStatus]] = {
    ExceptionStatus.PENDING: frozenset(
        {ExceptionStatus.NEEDS_REVIEW, ExceptionStatus.APPROVED, ExceptionStatus.WAIVED}
    ),
    ExceptionStatus.NEEDS_REVIEW: frozenset({ExceptionStatus.APPROVED, ExceptionStatus.WAIVED}),
    ExceptionStatus.APPROVED: frozenset({ExceptionStatus.EXPORTED}),
    ExceptionStatus.WAIVED: frozenset(),
    ExceptionStatus.EXPORTED: frozenset(),
}


class FeedbackIn(BaseModel):
    job_ref: str = Field(min_length=1, max_length=120)
    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str = Field(default="", max_length=2000)
    late: bool = False
    damaged: bool = False


class Job(BaseModel):
    job_ref: str
    driver: str
    customer: str


class FeedbackRecord(BaseModel):
    id: str = ""
    job_ref: str
    driver: str
    customer: str
    rating: int | None
    comment: str
    late: bool
    damaged: bool
    created_at: datetime
    exception_id: str | None = None


class ExceptionRecord(BaseModel):
    id: str = ""
    feedback_id: str = ""
    job_ref: str
    driver: str
    customer: str
    type: ExceptionType
    flags: list[str]
    type_label: str
    charge_cents: int
    status: ExceptionStatus
    rating: int | None
    comment: str
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None = None
    updated_by: str = ""
    seeded: bool = False


class ExceptionEvent(BaseModel):
    """Append-only record of a status change. Answers "who waived this charge"."""

    id: str = ""
    exception_id: str
    from_status: ExceptionStatus
    to_status: ExceptionStatus
    actor: str
    at: datetime


class FeedbackOut(BaseModel):
    feedback_id: str
    exception_id: str | None
    exception_created: bool


class DriverCount(BaseModel):
    driver: str
    count: int


class StatsOut(BaseModel):
    exceptions_today: int
    pending_review: int
    approved_today_cents: int
    approved_today_count: int
    top_driver: DriverCount | None
    by_driver: list[DriverCount]


class StatusPatch(BaseModel):
    status: ExceptionStatus

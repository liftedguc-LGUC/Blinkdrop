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
    seeded: bool = False


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

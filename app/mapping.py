"""Turns a feedback submission into a dashboard exception record.

The wireframe never specified this rule, so every threshold here is a product
decision, not a requirement. They are gathered in one place on purpose.
"""

from datetime import datetime, timezone

from .config import DAMAGED_CHARGE_CENTS, LATE_CHARGE_CENTS, POOR_RATING_MAX
from .models import ExceptionRecord, ExceptionStatus, ExceptionType, FeedbackIn, Job

UNKNOWN_CUSTOMER = "Unknown customer"
UNASSIGNED_DRIVER = "Unassigned"


def _type_label(flags: list[str]) -> str:
    if flags == ["late", "damaged"]:
        return "Damaged + Late"
    if flags == ["damaged"]:
        return "Damaged"
    if flags == ["late"]:
        return "Late"
    return "Service"


def to_exception(
    fb: FeedbackIn, job: Job | None, now: datetime | None = None
) -> ExceptionRecord | None:
    """Return the exception this feedback warrants, or None for a clean delivery."""
    flags = [name for name, on in (("late", fb.late), ("damaged", fb.damaged)) if on]
    poor_rating = fb.rating is not None and fb.rating <= POOR_RATING_MAX
    if not flags and not poor_rating:
        return None

    if fb.damaged:
        kind = ExceptionType.DAMAGED
    elif fb.late:
        kind = ExceptionType.LATE
    else:
        kind = ExceptionType.SERVICE

    charge = (LATE_CHARGE_CENTS if fb.late else 0) + (DAMAGED_CHARGE_CENTS if fb.damaged else 0)
    now = now or datetime.now(timezone.utc)

    return ExceptionRecord(
        job_ref=fb.job_ref,
        # Attribution comes only from a known job. It used to be parsed out of
        # the client-supplied job_ref, which let anyone file charges against any
        # named driver for deliveries that never happened.
        driver=job.driver if job else UNASSIGNED_DRIVER,
        customer=job.customer if job else UNKNOWN_CUSTOMER,
        type=kind,
        flags=flags,
        type_label=_type_label(flags),
        charge_cents=charge,
        status=ExceptionStatus.PENDING,
        rating=fb.rating,
        comment=fb.comment,
        created_at=now,
        updated_at=now,
    )

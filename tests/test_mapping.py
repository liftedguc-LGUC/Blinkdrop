"""One assertion per invented business rule — see app/mapping.py."""

import pytest

from app.mapping import parse_driver, to_exception
from app.models import ExceptionStatus, ExceptionType, FeedbackIn, Job

JOB = Job(job_ref="Job #4821 — Alex M.", driver="Alex M.", customer="R. Patel")


def feedback(**kwargs) -> FeedbackIn:
    return FeedbackIn(job_ref=JOB.job_ref, **kwargs)


def test_happy_delivery_creates_no_exception():
    assert to_exception(feedback(rating=5), JOB) is None


def test_no_rating_and_no_flags_creates_no_exception():
    assert to_exception(feedback(), JOB) is None


def test_poor_rating_alone_creates_a_service_exception():
    exc = to_exception(feedback(rating=2), JOB)
    assert exc.type is ExceptionType.SERVICE
    assert exc.charge_cents == 0
    assert exc.type_label == "Service"


def test_good_rating_with_late_flag_still_creates_an_exception():
    exc = to_exception(feedback(rating=4, late=True), JOB)
    assert exc.type is ExceptionType.LATE
    assert exc.charge_cents == 500


def test_damaged_charges_twelve_dollars():
    exc = to_exception(feedback(rating=3, damaged=True), JOB)
    assert exc.type is ExceptionType.DAMAGED
    assert exc.charge_cents == 1200


def test_both_flags_sum_charges_and_damaged_wins_the_type():
    exc = to_exception(feedback(rating=1, late=True, damaged=True), JOB)
    assert exc.type is ExceptionType.DAMAGED
    assert exc.flags == ["late", "damaged"]
    assert exc.charge_cents == 1700
    assert exc.type_label == "Damaged + Late"


def test_new_exceptions_always_start_pending():
    assert to_exception(feedback(late=True), JOB).status is ExceptionStatus.PENDING


def test_unknown_job_falls_back_to_parsed_driver_and_unknown_customer():
    exc = to_exception(feedback(damaged=True), None)
    assert exc.driver == "Alex M."
    assert exc.customer == "Unknown customer"


@pytest.mark.parametrize(
    ("job_ref", "expected"),
    [("Job #1 — Sam P.", "Sam P."), ("Job #2 - Lee K.", "Lee K."), ("Job #3", "Unassigned")],
)
def test_driver_parsed_from_job_ref(job_ref: str, expected: str):
    assert parse_driver(job_ref) == expected

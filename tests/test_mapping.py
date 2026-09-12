"""One assertion per invented business rule — see app/mapping.py."""

from app.mapping import to_exception
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


def test_an_unknown_job_never_attributes_a_named_driver():
    """The job_ref is client-supplied. Parsing a driver name out of it let
    anyone file charges against a real employee, so attribution now comes only
    from a known job record."""
    exc = to_exception(feedback(damaged=True), None)
    assert exc.driver == "Unassigned"
    assert exc.customer == "Unknown customer"

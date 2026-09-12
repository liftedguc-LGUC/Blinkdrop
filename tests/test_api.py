import asyncio
from datetime import datetime, timedelta, timezone

import pytest


def run(coro):
    return asyncio.run(coro)

from app.models import ExceptionRecord, ExceptionStatus, ExceptionType

JOB = "Job #4821 — Alex M."


def make_exception(**overrides) -> ExceptionRecord:
    now = datetime.now(timezone.utc)
    defaults = dict(
        job_ref=JOB,
        driver="Alex M.",
        customer="R. Patel",
        type=ExceptionType.LATE,
        flags=["late"],
        type_label="Late",
        charge_cents=500,
        status=ExceptionStatus.PENDING,
        rating=2,
        comment="",
        created_at=now,
        updated_at=now,
    )
    return ExceptionRecord(**{**defaults, **overrides})


def test_healthz_is_a_bare_liveness_signal(client):
    # It used to report the storage backend, which doubled as a hint about
    # whether the dev endpoints were enabled.
    assert client.get("/healthz").json() == {"status": "ok"}


def test_json_submission_creates_an_exception(client):
    response = client.post("/api/feedback", json={"job_ref": JOB, "rating": 1, "damaged": True})
    assert response.status_code == 201
    body = response.json()
    assert body["exception_created"] is True
    assert body["exception_id"]


def test_json_submission_without_problems_stores_feedback_only(client):
    body = client.post("/api/feedback", json={"job_ref": JOB, "rating": 5}).json()
    assert body["exception_created"] is False
    assert body["exception_id"] is None
    assert client.get("/api/exceptions").json()["count"] == 0


def test_form_submission_redirects_to_thanks(client):
    response = client.post(
        "/api/feedback",
        data={"job_ref": JOB, "rating": "1", "late": "on"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/thanks.html"
    assert client.get("/api/exceptions").json()["count"] == 1


def test_form_submission_keeps_the_job_reference(client):
    client.post("/api/feedback", data={"job_ref": JOB, "damaged": "on"}, follow_redirects=False)
    item = client.get("/api/exceptions").json()["items"][0]
    assert item["job_ref"] == JOB
    assert item["driver"] == "Alex M."
    assert item["customer"] == "R. Patel"


@pytest.mark.parametrize("status", ["needs_review", "needs-review"])
def test_status_filter_accepts_both_spellings(client, repo, status):
    run(repo.add_exception(make_exception(status=ExceptionStatus.NEEDS_REVIEW)))
    body = client.get(f"/api/exceptions?status={status}").json()
    assert body["count"] == 1


def test_unknown_status_is_rejected(client):
    assert client.get("/api/exceptions?status=bogus").status_code == 422


def test_patch_moves_an_exception_and_sets_approved_at(client):
    exc_id = client.post("/api/feedback", json={"job_ref": JOB, "late": True}).json()["exception_id"]
    updated = client.patch(f"/api/exceptions/{exc_id}", json={"status": "approved"}).json()
    assert updated["status"] == "approved"
    assert updated["approved_at"] is not None


def test_patch_unknown_id_is_404(client):
    assert client.patch("/api/exceptions/nope", json={"status": "approved"}).status_code == 404


def test_stats_counts_today_only_and_sums_approved_charges(client, repo):
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    now = datetime.now(timezone.utc)
    run(repo.add_exception(make_exception(created_at=yesterday, updated_at=yesterday)))
    run(repo.add_exception(make_exception(driver="Tom B.")))
    run(
        repo.add_exception(
            make_exception(
                driver="Alex M.",
                status=ExceptionStatus.APPROVED,
                charge_cents=1200,
                approved_at=now,
            )
        )
    )

    stats = client.get("/api/stats").json()
    assert stats["exceptions_today"] == 2
    # Open = pending + needs_review, all-time: yesterday's and Tom B.'s.
    # The approved one is no longer open.
    assert stats["pending_review"] == 2
    assert stats["approved_today_cents"] == 1200
    assert stats["approved_today_count"] == 1
    assert stats["top_driver"]["driver"] == "Alex M."  # tie on 1 each, alphabetical


def test_seed_endpoint_populates_every_status(client):
    assert client.post("/api/dev/seed").status_code == 201
    statuses = {item["status"] for item in client.get("/api/exceptions").json()["items"]}
    assert statuses == {"pending", "needs_review", "approved", "waived", "exported"}

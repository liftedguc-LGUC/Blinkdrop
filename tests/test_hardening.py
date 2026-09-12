"""Regression tests for the 04-security-engineer patches.

Each test names the finding it locks down.
"""

import pytest


JOB = "Job #4821 — Alex M."


def file_an_exception(client) -> str:
    return client.post("/api/feedback", json={"job_ref": JOB, "damaged": True}).json()["exception_id"]


# H2 — attacker-controlled driver attribution


def test_unknown_job_reference_is_rejected(client):
    response = client.post(
        "/api/feedback", json={"job_ref": "Job #9999 - Alex M.", "damaged": True, "rating": 1}
    )
    assert response.status_code == 404
    assert client.get("/api/exceptions").json()["count"] == 0


def test_form_path_also_rejects_unknown_jobs(client):
    response = client.post(
        "/api/feedback",
        data={"job_ref": "Job #9999 - Alex M.", "damaged": "on"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/form.html?error=1"
    assert client.get("/api/exceptions").json()["count"] == 0


def test_known_job_attributes_the_driver_from_the_jobs_record(client):
    file_an_exception(client)
    item = client.get("/api/exceptions").json()["items"][0]
    assert item["driver"] == "Alex M."
    assert item["customer"] == "R. Patel"


# H1 — billing state machine


@pytest.mark.parametrize(
    ("reached_by", "illegal_next"),
    [
        (["approved"], "pending"),        # settled charge cannot reopen
        (["waived"], "approved"),         # a waiver is final
        (["approved", "exported"], "pending"),
        (["needs_review"], "exported"),   # cannot skip the approval decision
    ],
)
def test_illegal_transitions_are_refused(client, reached_by, illegal_next):
    exc_id = file_an_exception(client)
    for step in reached_by:
        assert client.patch(f"/api/exceptions/{exc_id}", json={"status": step}).status_code == 200

    response = client.patch(f"/api/exceptions/{exc_id}", json={"status": illegal_next})
    assert response.status_code == 409
    # The refused move leaves no trace in the audit log.
    assert client.get(f"/api/exceptions/{exc_id}/events").json()["count"] == len(reached_by)


def test_legal_transition_chain_is_allowed(client):
    exc_id = file_an_exception(client)
    for target in ("needs_review", "approved", "exported"):
        assert client.patch(f"/api/exceptions/{exc_id}", json={"status": target}).status_code == 200


def test_status_change_records_who_made_it(client):
    exc_id = file_an_exception(client)
    updated = client.patch(f"/api/exceptions/{exc_id}", json={"status": "waived"}).json()
    assert updated["updated_by"] == "local-dev"

    events = client.get(f"/api/exceptions/{exc_id}/events").json()["items"]
    assert len(events) == 1
    assert (events[0]["from_status"], events[0]["to_status"]) == ("pending", "waived")
    assert events[0]["actor"] == "local-dev"


# H3 — destructive seed endpoint


def test_seed_endpoint_no_longer_accepts_force(client):
    client.post("/api/dev/seed")
    before = client.get("/api/exceptions").json()["count"]
    assert before > 0
    # The parameter is gone: it is ignored, and nothing is deleted.
    assert client.post("/api/dev/seed?force=true").json()["created"] == 0
    assert client.get("/api/exceptions").json()["count"] == before


def test_firestore_repository_refuses_to_clear():
    from app.firestore_repo import FirestoreRepository

    with pytest.raises(NotImplementedError):
        import asyncio

        asyncio.run(FirestoreRepository.clear(object()))


# M7 — malformed input used to 500 with a traceback


@pytest.mark.parametrize(
    "body",
    ['{"not json', '{"job_ref":"x","rating":99}', '{"rating":1}', "[1,2]", ""],
)
def test_malformed_json_is_422_not_500(client, body):
    response = client.post(
        "/api/feedback", content=body, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422


def test_overlong_comment_is_422(client):
    response = client.post("/api/feedback", json={"job_ref": JOB, "comment": "a" * 5000})
    assert response.status_code == 422


# M9 — body size


def test_oversized_body_is_rejected_before_parsing(client):
    response = client.post(
        "/api/feedback",
        content=b"x" * 100_000,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413


# M8 — schema disclosure


def test_docs_are_disabled_when_not_explicitly_enabled(monkeypatch, repo, make_client):
    monkeypatch.setenv("EXPOSE_DOCS", "false")
    with make_client(repo) as client:
        client.app.state.repo = repo
        for path in ("/openapi.json", "/docs", "/redoc"):
            assert client.get(path).status_code == 404


# L10 — response headers


def test_security_headers_are_present(client):
    headers = client.get("/form.html").headers
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Referrer-Policy"] == "no-referrer"


# H5 — rate limiting


def test_feedback_is_rate_limited(monkeypatch, repo, make_client):
    monkeypatch.setenv("FEEDBACK_RATE_LIMIT_PER_MINUTE", "3")
    with make_client(repo) as client:
        client.app.state.repo = repo
        codes = [
            client.post("/api/feedback", json={"job_ref": JOB, "rating": 5}).status_code
            for _ in range(5)
        ]
    assert codes[:3] == [201, 201, 201]
    assert codes[3:] == [429, 429]


# L11 — health check disclosure


def test_healthz_does_not_disclose_the_storage_backend(client):
    assert client.get("/healthz").json() == {"status": "ok"}


# Verified non-finding, locked down so a refactor cannot undo it


@pytest.mark.parametrize(
    "path",
    ["/../README.md", "/%2e%2e%2fREADME.md", "/app/main.py", "/README.md", "/requirements.txt"],
)
def test_static_allowlist_still_refuses_everything_outside_it(client, path):
    assert client.get(path).status_code == 404

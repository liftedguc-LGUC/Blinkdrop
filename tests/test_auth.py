"""The admin surface: authentication, and what stays public."""

import base64

import pytest


ADMIN_ROUTES = [
    ("get", "/dashboard.html"),
    ("get", "/api/exceptions"),
    ("get", "/api/stats"),
]
PUBLIC_ROUTES = ["/", "/landing.html", "/form.html", "/thanks.html", "/styles.css", "/app.js"]


def basic(user: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@pytest.fixture
def secured(monkeypatch, repo, make_client):
    monkeypatch.setenv("ADMIN_AUTH", "basic")
    monkeypatch.setenv("ADMIN_PASSWORD", "correct-horse")
    with make_client(repo) as client:
        client.app.state.repo = repo
        yield client


@pytest.mark.parametrize(("method", "path"), ADMIN_ROUTES)
def test_admin_routes_require_credentials(secured, method, path):
    response = getattr(secured, method)(path)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"].startswith("Basic")


@pytest.mark.parametrize(("method", "path"), ADMIN_ROUTES)
def test_admin_routes_accept_correct_credentials(secured, method, path):
    assert getattr(secured, method)(path, headers=basic("admin", "correct-horse")).status_code == 200


def test_wrong_password_is_rejected(secured):
    assert secured.get("/api/stats", headers=basic("admin", "wrong")).status_code == 401


def test_wrong_username_is_rejected(secured):
    assert secured.get("/api/stats", headers=basic("root", "correct-horse")).status_code == 401


def test_malformed_authorization_header_is_rejected(secured):
    assert secured.get("/api/stats", headers={"Authorization": "Basic !!!"}).status_code == 401


@pytest.mark.parametrize("path", PUBLIC_ROUTES)
def test_public_pages_stay_public(secured, path):
    assert secured.get(path).status_code == 200


def test_feedback_submission_stays_public(secured):
    response = secured.post("/api/feedback", json={"job_ref": "Job #4821 — Alex M.", "rating": 5})
    assert response.status_code == 201


def test_patch_requires_credentials(secured):
    assert secured.patch("/api/exceptions/exc_0001", json={"status": "approved"}).status_code == 401


def test_firestore_backend_without_auth_fails_closed(monkeypatch, repo, make_client):
    """The important one: a deploy that forgets to configure auth must refuse to
    serve the admin surface rather than defaulting open."""
    monkeypatch.delenv("ADMIN_AUTH", raising=False)
    monkeypatch.setenv("STORAGE_BACKEND", "firestore")
    # Only the auth resolution is under test; no real Firestore client here.
    monkeypatch.setattr("app.main.build_repository", lambda: repo)
    with make_client(repo) as client:
        client.app.state.repo = repo
        assert client.get("/api/stats").status_code == 503
        assert client.get("/dashboard.html").status_code == 503
        # ...while the public form is unaffected.
        assert client.get("/form.html").status_code == 200


def test_iap_mode_rejects_a_request_with_no_assertion(monkeypatch, repo, make_client):
    monkeypatch.setenv("ADMIN_AUTH", "iap")
    monkeypatch.setenv("IAP_AUDIENCE", "/projects/1/global/backendServices/2")
    with make_client(repo) as client:
        client.app.state.repo = repo
        assert client.get("/api/stats").status_code == 401


def test_iap_mode_accepts_a_verified_assertion(monkeypatch, repo, make_client):
    # Real IAP is not reachable from here, so the verifier is stubbed: this
    # covers the claim handling, not Google's signature check.
    monkeypatch.setenv("ADMIN_AUTH", "iap")
    monkeypatch.setenv("IAP_AUDIENCE", "/projects/1/global/backendServices/2")
    monkeypatch.setattr(
        "app.auth.verify_iap_assertion",
        lambda token, audience: {"iss": "https://cloud.google.com/iap", "email": "ops@example.com"},
    )
    with make_client(repo) as client:
        client.app.state.repo = repo
        assert client.get("/api/stats", headers={"X-Goog-IAP-JWT-Assertion": "x"}).status_code == 200


def test_iap_rejects_an_email_outside_the_allowlist(monkeypatch, repo, make_client):
    monkeypatch.setenv("ADMIN_AUTH", "iap")
    monkeypatch.setenv("IAP_AUDIENCE", "/projects/1/global/backendServices/2")
    monkeypatch.setenv("IAP_ALLOWED_EMAILS", "ops@example.com")
    monkeypatch.setattr(
        "app.auth.verify_iap_assertion",
        lambda token, audience: {"iss": "https://cloud.google.com/iap", "email": "other@evil.test"},
    )
    with make_client(repo) as client:
        client.app.state.repo = repo
        assert client.get("/api/stats", headers={"X-Goog-IAP-JWT-Assertion": "x"}).status_code == 403


def test_iap_rejects_a_forged_issuer(monkeypatch, repo, make_client):
    monkeypatch.setenv("ADMIN_AUTH", "iap")
    monkeypatch.setenv("IAP_AUDIENCE", "/projects/1/global/backendServices/2")
    monkeypatch.setattr(
        "app.auth.verify_iap_assertion",
        lambda token, audience: {"iss": "https://evil.test", "email": "ops@example.com"},
    )
    with make_client(repo) as client:
        client.app.state.repo = repo
        assert client.get("/api/stats", headers={"X-Goog-IAP-JWT-Assertion": "x"}).status_code == 401

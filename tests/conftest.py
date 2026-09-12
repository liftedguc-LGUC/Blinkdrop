import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["STORAGE_BACKEND"] = "memory"
os.environ["SEED_ON_STARTUP"] = "false"
os.environ["ALLOW_DEV_ENDPOINTS"] = "true"
os.environ["ADMIN_AUTH"] = "off"

from fastapi.testclient import TestClient  # noqa: E402

from app import rate_limit  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.repository import InMemoryRepository  # noqa: E402
from app.routes_api import get_repo  # noqa: E402
from app.seed import JOBS  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Settings are cached and env-derived, so every test starts from the same
    baseline and any override it makes is torn down."""
    for name in ("ADMIN_AUTH", "ADMIN_PASSWORD", "IAP_AUDIENCE", "REQUIRE_KNOWN_JOB", "EXPOSE_DOCS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("STORAGE_BACKEND", "memory")
    monkeypatch.setenv("ADMIN_AUTH", "off")
    get_settings.cache_clear()
    rate_limit.reset()
    yield
    get_settings.cache_clear()
    rate_limit.reset()


@pytest.fixture
def repo() -> InMemoryRepository:
    return InMemoryRepository(jobs={job.job_ref: job for job in JOBS})


def build_client(repo: InMemoryRepository) -> TestClient:
    """Builds an app from the env as it stands now, so a test can set
    ADMIN_AUTH et al. before the settings cache is populated."""
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    client = TestClient(app)
    client.app.state.repo = repo
    return client


@pytest.fixture
def make_client():
    return build_client


@pytest.fixture
def client(repo: InMemoryRepository) -> TestClient:
    with build_client(repo) as test_client:
        test_client.app.state.repo = repo
        yield test_client

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["STORAGE_BACKEND"] = "memory"
os.environ["SEED_ON_STARTUP"] = "false"
os.environ["ALLOW_DEV_ENDPOINTS"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.repository import InMemoryRepository  # noqa: E402
from app.routes_api import get_repo  # noqa: E402
from app.seed import JOBS  # noqa: E402


@pytest.fixture
def repo() -> InMemoryRepository:
    get_settings.cache_clear()
    return InMemoryRepository(jobs={job.job_ref: job for job in JOBS})


@pytest.fixture
def client(repo: InMemoryRepository) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    with TestClient(app) as test_client:
        test_client.app.state.repo = repo
        yield test_client

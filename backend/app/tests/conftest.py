from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db import repo as repo_module
from app.db.repo import InMemoryRepo
from app.services.seed import seed


@pytest.fixture(autouse=True)
def in_memory_repo():
    """Every test runs against a fresh in-memory store, seeded with the corpus + associates. No
    network, no disk, no API key (mock provider is the default)."""
    settings.PROVIDER_MODE = "mock"
    settings.SAMPLE_RATE = 0.0  # deterministic auto-clear; sampling tests opt in explicitly
    repo = InMemoryRepo()
    seed(repo)
    repo_module.set_repo(repo)
    yield repo
    repo_module.set_repo(None)


@pytest.fixture
def client(in_memory_repo):
    from app.main import app

    # The startup seed is a no-op here (already seeded), and the repo is the in-memory one.
    return TestClient(app)


@pytest.fixture
def provider():
    from app.providers.mock import MockLLMProvider

    return MockLLMProvider()

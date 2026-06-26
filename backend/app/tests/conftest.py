from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.celery_app import celery_app
from app.core.auth import CurrentUser, get_current_user
from app.db import repo as repo_module
from app.db.repo import InMemoryRepo


@pytest.fixture(autouse=True)
def in_memory_repo():
    """Install a dict-backed repo for every test; tear down after."""
    repo = InMemoryRepo()
    repo_module.set_repo(repo)
    yield repo
    repo_module.set_repo(None)


@pytest.fixture(autouse=True)
def eager_celery():
    """Run the agent chain inline so the pipeline is exercisable synchronously and offline."""
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    celery_app.loader.import_default_modules()
    yield
    celery_app.conf.task_always_eager = False


@pytest.fixture
def client():
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="u1", email="u@x.test"
    )
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)

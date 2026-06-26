from __future__ import annotations

from app import fixtures
from app.db.repo import Repo
from app.db.tables import ASSOCIATES, CORPUS


def seed(repo: Repo) -> None:
    """Idempotently load the corpus (EU Cellar-modelled docs, firm standard, process doc, drafts)
    and the human-maintained associate registry. Safe to call on every boot."""
    if not repo.list(CORPUS):
        for doc in fixtures.corpus():
            repo.insert(CORPUS, dict(doc))
    if not repo.list(ASSOCIATES):
        for a in fixtures.associates():
            repo.insert(ASSOCIATES, dict(a))

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.db.repo import get_repo
from app.db.tables import ASSOCIATES, CORPUS
from app.schemas.models import AssociateCreate

router = APIRouter()


@router.get("/corpus")
def list_corpus() -> list[dict]:
    return get_repo().list(CORPUS)


@router.get("/corpus/{doc_id}")
def get_corpus(doc_id: str) -> dict:
    doc = get_repo().get(CORPUS, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found.")
    return doc


@router.get("/associates")
def list_associates() -> list[dict]:
    return get_repo().list(ASSOCIATES)


@router.post("/associates", status_code=201)
def create_associate(body: AssociateCreate) -> dict:
    return get_repo().insert(ASSOCIATES, body.model_dump())

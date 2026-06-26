from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth import CurrentUser, get_current_user
from app.schemas.models import PresignRequest, PresignResponse
from app.services.storage import presign_put

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("/presign", response_model=PresignResponse)
def presign(body: PresignRequest, user: CurrentUser = Depends(get_current_user)) -> dict:
    # Size/content-type validated by the schema before a URL is issued.
    return presign_put(filename=body.filename, content_type=body.content_type)

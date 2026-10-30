import hashlib

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from ..auth import User, limiter, require_user
from .amazon import MAX_UPLOAD, parse_upload
from .models import ImportProblem
from . import service

router = APIRouter(prefix="/api/imports", tags=["imports"])


class Confirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order_keys: list[str] = Field(min_length=1, max_length=5000)
    acknowledge_review: bool = False


@router.post("/amazon/preview")
@limiter.limit("10/minute")
async def amazon_preview(request: Request, user: User = Depends(require_user)):
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_UPLOAD:
            raise ImportProblem("Upload exceeds 10 MiB", 413)
        data.extend(chunk)
    parsed = await run_in_threadpool(parse_upload, bytes(data))
    return await run_in_threadpool(service.create_preview, user.id, "amazon_file", hashlib.sha256(data).hexdigest(), parsed)


@router.get("/history")
def import_history(user: User = Depends(require_user)):
    return service.history(user.id)


@router.get("/{preview_id}")
def preview(preview_id: str, user: User = Depends(require_user)):
    return service.get_preview(user.id, preview_id)


@router.post("/{preview_id}/confirm")
@limiter.limit("20/minute")
def confirm(request: Request, preview_id: str, data: Confirmation, user: User = Depends(require_user)):
    return service.confirm_preview(user.id, preview_id, data.order_keys, data.acknowledge_review)

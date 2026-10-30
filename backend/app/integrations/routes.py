from fastapi import APIRouter, Depends, Request
from starlette.responses import RedirectResponse

from ..auth import COOKIE, User, limiter, require_user
from . import gmail
from ..imports.models import ImportProblem

router = APIRouter(prefix="/api/integrations/gmail", tags=["Gmail"])


@router.get("")
def status(user: User = Depends(require_user)):
    return gmail.status(user.id)


@router.post("/authorize")
@limiter.limit("5/minute")
def authorize(request: Request, user: User = Depends(require_user)):
    return gmail.authorize(user.id, request.cookies[COOKIE])


@router.get("/callback")
@limiter.limit("10/minute")
def callback(request: Request, user: User = Depends(require_user)):
    query = request.state.oauth_query
    state, code, error = query.get("state", ""), query.get("code"), query.get("error")
    if not 1 <= len(state) <= 200 or code is not None and len(code) > 4096 or error is not None and len(error) > 100:
        raise ImportProblem("Invalid Gmail authorization callback", 400)
    destination = gmail.callback(user.id, request.cookies[COOKIE], state, code, error)
    return RedirectResponse(destination, status_code=303, headers={"Referrer-Policy": "no-referrer", "Cache-Control": "no-store"})


@router.post("/sync")
@limiter.limit("10/minute")
def sync(request: Request, user: User = Depends(require_user)):
    return gmail.sync(user.id)


@router.post("/disconnect")
@limiter.limit("10/minute")
def disconnect(request: Request, user: User = Depends(require_user)):
    return gmail.disconnect(user.id)

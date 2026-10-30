"""Email/password authentication with opaque, revocable SQLite sessions.

This module never initializes or migrates a database. API routes use its
verified identity for ownership checks; retailer workflows remain simulated.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import sqlite3
import uuid

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

from .config import get_settings
from .db import connect

COOKIE = "cygnus_session"
CSRF_HEADER = "x-cygnus-csrf"
limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/api/auth", tags=["authentication"])
hasher = PasswordHasher(type=Type.ID)
_dummy_hash = hasher.hash(secrets.token_urlsafe(32))


def now():
    return datetime.now(timezone.utc)


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@contextmanager
def auth_database():
    try:
        with connect() as conn:
            # Refuse missing schema; migrations are always an explicit operation.
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"users", "sessions", "app_metadata"}.issubset(tables):
                raise HTTPException(503, "Account service is unavailable. Contact the application administrator.")
            yield conn
    except sqlite3.OperationalError:
        raise HTTPException(503, "Account service is temporarily unavailable.") from None


class User(BaseModel):
    id: str
    email: str
    display_name: str
    email_verified: bool


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr = Field(max_length=254)
    password: SecretStr

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, value):
        return str(value).casefold()

    @field_validator("password")
    @classmethod
    def bounded_password(cls, value):
        if not 1 <= len(value.get_secret_value()) <= 128:
            raise ValueError("Password must contain between 1 and 128 characters")
        return value


class Registration(Credentials):
    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("display_name")
    @classmethod
    def valid_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Enter a display name")
        return value

    @field_validator("password")
    @classmethod
    def strong_password(cls, value):
        if len(value.get_secret_value()) < 8:
            raise ValueError("Password must contain at least 8 characters")
        return value


def public_user(row):
    return User(id=row["id"], email=row["email"], display_name=row["display_name"], email_verified=bool(row["email_verified"]))


def require_user(request: Request) -> User:
    token = request.cookies.get(COOKIE, "")
    if len(token) != 43 or not all(c.isascii() and (c.isalnum() or c in "-_") for c in token):
        raise HTTPException(401, "Authentication required")
    with auth_database() as conn:
        row = conn.execute(
            """SELECT users.* FROM sessions JOIN users ON users.id=sessions.user_id
               WHERE sessions.token_hash=? AND sessions.revoked_at IS NULL
               AND sessions.expires_at>? AND users.is_active=1""",
            (token_hash(token), now().isoformat()),
        ).fetchone()
        if row is None:
            raise HTTPException(401, "Authentication required")
        return public_user(row)


def new_session(conn, user_id, previous_token):
    timestamp = now()
    if previous_token:
        conn.execute("UPDATE sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL", (timestamp.isoformat(), token_hash(previous_token)))
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO sessions(id,user_id,token_hash,expires_at,created_at) VALUES (?,?,?,?,?)",
        (uuid.uuid4().hex, user_id, token_hash(token), (timestamp + timedelta(seconds=get_settings().auth_session_ttl_seconds)).isoformat(), timestamp.isoformat()),
    )
    return token


def secure_cookie():
    return get_settings().app_env.lower() not in {"development", "demo", "test"}


def set_session(response, token):
    response.set_cookie(COOKIE, token, max_age=get_settings().auth_session_ttl_seconds, path="/", secure=secure_cookie(), httponly=True, samesite="lax")
    response.headers["Cache-Control"] = "no-store"


def csrf_failure(request):
    # Custom-header CSRF defense: exact trusted Origin, non-simple header,
    # JSON-only mutations and credentialed CORS restricted to explicit origins.
    settings = get_settings()
    allowed_types = {"application/json"}
    if request.url.path == "/api/imports/amazon/preview":
        allowed_types.add("application/octet-stream")
    if request.headers.get("origin") not in settings.auth_origin_list:
        detail = "This page's address is not trusted by the backend. Open the app at a configured trusted origin; localhost and 127.0.0.1 are different origins. Restart the backend after changing AUTH_TRUSTED_ORIGINS."
        if "http://localhost:5179" in settings.auth_origin_list:
            detail = "Open http://localhost:5179 and sign in there, then retry. This request's origin is not trusted; 127.0.0.1 and other ports are different origins."
        reason = "untrusted_origin"
    elif request.headers.get(CSRF_HEADER) != "1":
        detail = "The request is missing the required CSRF protection header. Refresh the app and retry. The frontend must send X-Cygnus-CSRF: 1."
        reason = "missing_csrf_header"
    elif request.headers.get("content-type", "").split(";")[0].strip().lower() not in allowed_types:
        detail = "The request has an unsupported content type. Refresh the app and retry. This action requires a supported request content type."
        reason = "invalid_content_type"
    else:
        return None
    return JSONResponse({"detail": detail, "reason": reason}, status_code=403, headers={"Cache-Control": "no-store"})


@router.post("/register", response_model=User, status_code=201)
@limiter.limit("5/minute")
def register(request: Request, response: Response, data: Registration):
    password_hash = hasher.hash(data.password.get_secret_value())
    user_id = uuid.uuid4().hex
    try:
        with auth_database() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("INSERT INTO users(id,email,display_name,password_hash,created_at) VALUES (?,?,?,?,?)", (user_id, str(data.email), data.display_name, password_hash, now().isoformat()))
            claim = conn.execute("INSERT INTO app_metadata(key,value) VALUES ('demo_data_owner',?) ON CONFLICT(key) DO NOTHING", (user_id,))
            if claim.rowcount == 1:
                conn.execute("""UPDATE orders SET user_id=? WHERE user_id IS NULL AND source='demo' AND simulated=1
                             AND id IN ('demo-order-001','demo-order-002','demo-order-003','demo-order-004')""", (user_id,))
            token = new_session(conn, user_id, request.cookies.get(COOKIE))
            user = public_user(conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Unable to register with these details. Try signing in.") from None
    set_session(response, token)
    return user


@router.post("/login", response_model=User)
@limiter.limit("10/minute")
def login(request: Request, response: Response, data: Credentials):
    with auth_database() as conn:
        row = conn.execute("SELECT * FROM users WHERE email=?", (str(data.email),)).fetchone()
    stored_hash = row["password_hash"] if row and row["password_hash"] else _dummy_hash
    try:
        valid = hasher.verify(stored_hash, data.password.get_secret_value())
    except (VerificationError, InvalidHashError):
        valid = False
    if not valid or row is None or not row["is_active"] or not row["password_hash"]:
        raise HTTPException(401, "Invalid email or password")
    replacement = hasher.hash(data.password.get_secret_value()) if hasher.check_needs_rehash(stored_hash) else None
    with auth_database() as conn:
        conn.execute("BEGIN IMMEDIATE")
        # Recheck after password verification, before issuing a session.
        current = conn.execute("SELECT * FROM users WHERE id=? AND is_active=1 AND password_hash=?", (row["id"], stored_hash)).fetchone()
        if current is None:
            raise HTTPException(401, "Invalid email or password")
        if replacement:
            conn.execute("UPDATE users SET password_hash=? WHERE id=?", (replacement, row["id"]))
        token = new_session(conn, row["id"], request.cookies.get(COOKIE))
    set_session(response, token)
    return public_user(current)


@router.get("/me", response_model=User)
def me(response: Response, user: User = Depends(require_user)):
    response.headers["Cache-Control"] = "no-store"
    return user


@router.post("/logout")
def logout(request: Request, response: Response, user: User = Depends(require_user)):
    with auth_database() as conn:
        conn.execute("UPDATE sessions SET revoked_at=? WHERE token_hash=? AND user_id=? AND revoked_at IS NULL", (now().isoformat(), token_hash(request.cookies[COOKIE]), user.id))
    response.delete_cookie(COOKIE, path="/", secure=secure_cookie(), httponly=True, samesite="lax")
    response.headers["Cache-Control"] = "no-store"
    return {"message": "Signed out"}

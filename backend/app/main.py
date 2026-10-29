"""Cygnus API entry point (FastAPI).

FastAPI = the server. The browser sends it a request ("is the backend alive?"),
a Python function runs, and the result goes back as JSON.
"""
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from typing import Literal, Self

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .ai import nebius, nvidia
from .config import get_settings
from .db import check_database
from . import returns

VERSION = "0.1.0"
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    returns.initialize()
    yield


app = FastAPI(title="Cygnus API", version=VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ReturnRequest(BaseModel):
    order_id: str = Field(min_length=1, max_length=80)
    item_id: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=2, max_length=500)


class PickupRequest(BaseModel):
    pickup_date: date


class AvailabilityRequest(BaseModel):
    availability: str = Field(min_length=3, max_length=200)


class AdvanceRequest(BaseModel):
    to_status: str


class AssistantChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2000)
    case_id: str | None = Field(default=None, min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    order_id: str | None = Field(default=None, min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message must not be blank")
        return value

    @model_validator(mode="after")
    def one_record_context_only(self) -> Self:
        if self.case_id and self.order_id:
            raise ValueError("Choose a return case or an order, not both")
        return self


class AssistantChatResponse(BaseModel):
    answer: str
    model: str
    facts: list[str]
    data_source: Literal["simulated"] = "simulated"


def _workflow_call(operation, *args):
    try:
        return operation(*args)
    except returns.WorkflowError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@app.get("/api/health")
def health() -> dict:
    """Is the server up, is the database reachable, is AI configured?
    Never returns the API key itself, only whether one exists."""
    db_ok = check_database()
    return {
        "status": "ok" if db_ok else "degraded",
        "app": settings.app_name,
        "version": VERSION,
        "environment": settings.app_env,
        "time": datetime.now(timezone.utc).isoformat(),
        "database": "ok" if db_ok else "error",
        "ai": {
            "provider": "Nebius Token Factory",
            "configured": settings.ai_configured,
            "model": settings.nebius_model_id,
        },
        "nvidia": {
            "provider": "NVIDIA API Catalog",
            "configured": settings.nvidia_configured,
            "model": settings.nvidia_model,
        },
        # Cygnus has no real retailer integration yet. Say so explicitly.
        "retailer_mode": "simulated",
    }


@app.get("/api/orders")
def orders() -> dict:
    return returns.list_orders()


@app.get("/api/orders/{order_id}")
def order_detail(order_id: str) -> dict:
    return _workflow_call(returns.get_order, order_id)


@app.get("/api/activity")
def activity() -> dict:
    return returns.activity()


@app.get("/api/returns")
def return_cases(order_id: str | None = None) -> dict:
    return returns.list_cases(order_id)


@app.post("/api/returns/eligibility")
def check_return_eligibility(request: ReturnRequest) -> dict:
    return returns.eligibility(request.order_id, request.item_id)


@app.post("/api/returns", status_code=201)
def create_return(request: ReturnRequest) -> dict:
    return _workflow_call(returns.create_case, request.order_id, request.item_id, request.reason)


@app.get("/api/returns/{case_id}")
def return_detail(case_id: str) -> dict:
    return _workflow_call(returns.get_case, case_id)


@app.post("/api/returns/{case_id}/pickup/schedule")
def schedule_pickup(case_id: str, request: PickupRequest) -> dict:
    return _workflow_call(returns.schedule_pickup, case_id, request.pickup_date)


@app.post("/api/returns/{case_id}/pickup/missed")
def mark_pickup_missed(case_id: str) -> dict:
    return _workflow_call(returns.mark_pickup_missed, case_id)


@app.post("/api/returns/{case_id}/availability")
def collect_availability(case_id: str, request: AvailabilityRequest) -> dict:
    return _workflow_call(returns.collect_availability, case_id, request.availability)


@app.post("/api/returns/{case_id}/pickup/reschedule")
def reschedule_pickup(case_id: str, request: PickupRequest) -> dict:
    return _workflow_call(returns.reschedule_pickup, case_id, request.pickup_date)


@app.post("/api/returns/{case_id}/simulate/advance")
def advance_simulation(case_id: str, request: AdvanceRequest) -> dict:
    return _workflow_call(returns.advance_simulation, case_id, request.to_status)


@app.get("/api/ai/models")
def ai_models() -> dict:
    """Lists NVIDIA models your Nebius key can call (use it to confirm the model id)."""
    try:
        return {"nvidia_models": nebius.list_nvidia_model_ids()}
    except nebius.AINotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:  # network/auth errors from the provider
        raise HTTPException(status_code=502, detail=f"Nebius request failed: {type(e).__name__}: {e}")


@app.post("/api/ai/chat", response_model=AssistantChatResponse)
def ai_chat(request: AssistantChatRequest) -> AssistantChatResponse:
    if settings.app_env.lower() not in {"development", "demo"}:
        raise HTTPException(
            status_code=403,
            detail="The assistant is limited to the demo environment until customer authorization is available.",
        )
    try:
        context = nvidia.build_context(case_id=request.case_id, order_id=request.order_id)
        result = nvidia.answer(request.message, context)
        return AssistantChatResponse(**result)
    except nvidia.AssistantError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={"code": error.code, "message": error.message},
        ) from None


@app.post("/api/ai/ping")
def ai_ping() -> dict:
    """One real inference call to prove the NVIDIA-model-via-Nebius path works."""
    try:
        return nebius.ping()
    except nebius.AINotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Nebius request failed: {type(e).__name__}: {e}")

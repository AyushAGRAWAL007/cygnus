from datetime import date
from typing import Literal
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from ..auth import User, require_user
from . import service

router = APIRouter(prefix='/api/shopping', tags=['Shopping'])


class RefundRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    amount: str = Field(min_length=1, max_length=40)
    currency: str = Field(pattern=r'^[A-Z]{3}$')
    status: Literal['pending', 'received']
    effective_date: date
    reference: str = Field(min_length=1, max_length=200)
    notes: str = Field(default='', max_length=2000)
    confirm_received: bool = Field(default=False, strict=True)

    @field_validator('reference')
    @classmethod
    def reference_nonblank(cls, value):
        value = value.strip()
        if not value or any(ord(c) < 32 for c in value):
            raise ValueError('Reference must contain visible text')
        return value


@router.get('/overview')
def overview(user: User = Depends(require_user)):
    return service.overview(user.id)


@router.get('/orders')
def orders(q: str = Query('', max_length=200), retailer: str | None = Query(None, max_length=100),
           date_from: date | None = None, date_to: date | None = None,
           status: str | None = Query(None, max_length=80),
           sort: Literal['newest','oldest','amount_desc','amount_asc'] = 'newest',
           currency: str | None = Query(None, pattern=r'^[A-Z]{3}$'),
           page: int = Query(1, ge=1, le=1000000), page_size: int = Query(20, ge=1, le=100),
           scope: Literal['all','real','demo'] = 'all', user: User = Depends(require_user)):
    return service.list_orders(user.id, q=q, retailer=retailer, date_from=date_from, date_to=date_to, status=status, sort=sort, currency_filter=currency, page=page, page_size=page_size, scope=scope)


@router.get('/orders/{order_id}')
def detail(order_id: str, user: User = Depends(require_user)):
    return service.detail(user.id, order_id)


@router.post('/orders/{order_id}/refunds')
def add_refund(order_id: str, data: RefundRequest, user: User = Depends(require_user)):
    return service.write_refund(user.id, order_id, data)


@router.put('/orders/{order_id}/refunds/{refund_id}')
def update_refund(order_id: str, refund_id: str, data: RefundRequest, user: User = Depends(require_user)):
    return service.write_refund(user.id, order_id, data, refund_id)


@router.get('/analytics')
def analytics(user: User = Depends(require_user)):
    return service.analytics(user.id)


@router.get('/retailers')
def retailers(user: User = Depends(require_user)):
    return service.retailers(user.id)

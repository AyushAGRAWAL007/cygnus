"""Shared import contract. Null means unknown; amounts remain decimal strings."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MARKETPLACES = {"amazon.in", "amazon.com", "amazon.co.uk", "amazon.ca", "amazon.de", "amazon.fr", "amazon.it", "amazon.es", "amazon.com.au", "amazon.co.jp"}


class ImportProblem(Exception):
    def __init__(self, detail: str, status_code: int = 422):
        self.detail, self.status_code = detail, status_code
        super().__init__(detail)


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_name: str = Field(min_length=1, max_length=500)
    external_item_id: str | None = Field(default=None, max_length=200)
    product_identifier: str | None = Field(default=None, max_length=100)
    quantity: int | None = Field(default=None, strict=True, ge=1, le=10000)
    unit_price: Decimal | None = Field(default=None, ge=0, le=Decimal("1000000000"), max_digits=15, decimal_places=4, allow_inf_nan=False)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    category: str | None = Field(default=None, min_length=1, max_length=100)
    details: dict[str, str] = Field(default_factory=dict, max_length=12)

    @field_validator("product_name")
    @classmethod
    def nonblank(cls, value):
        if not value.strip() or any(ord(c) < 32 for c in value):
            raise ValueError("Invalid product name")
        return value.strip()


class Order(BaseModel):
    model_config = ConfigDict(extra="forbid")
    retailer: str = Field(default="Amazon", pattern=r"^[A-Za-z][A-Za-z0-9 ._-]{0,79}$")
    external_order_id: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
    marketplace: str | None = None
    order_date: date | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    order_status: str | None = Field(default=None, max_length=100)
    total_amount: Decimal | None = Field(default=None, ge=0, le=Decimal("1000000000"), max_digits=15, decimal_places=4, allow_inf_nan=False)
    payment_status: str | None = Field(default=None, min_length=1, max_length=100, pattern=r"^[A-Za-z][A-Za-z0-9 _-]*$")
    source: Literal["amazon_file", "gmail"] = "amazon_file"
    source_reference: str = Field(default="record", max_length=500)
    source_timestamp: str | None = Field(default=None, max_length=100)
    items: list[Item] = Field(default_factory=list, max_length=500)
    review_reasons: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def retailer_identity(self):
        import re
        if self.retailer == "Amazon":
            if not re.fullmatch(r"\d{3}-\d{7}-\d{7}", self.external_order_id):
                raise ValueError("Invalid Amazon order ID")
            if self.marketplace is not None and self.marketplace not in MARKETPLACES:
                raise ValueError("Unsupported marketplace")
        elif self.marketplace is not None and not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", self.marketplace):
            raise ValueError("Invalid marketplace")
        return self

    @field_validator("marketplace")
    @classmethod
    def known_marketplace(cls, value):
        if value is not None and (len(value) > 100 or not value):
            raise ValueError("Invalid marketplace")
        return value


class ParseResult(BaseModel):
    orders: list[Order] = Field(default_factory=list)
    issues: list[dict] = Field(default_factory=list)
    unsupported: list[str] = Field(default_factory=list)
    duplicate_records: int = 0


def parse_date(value):
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError("Invalid date")
    # Deliberately no day/month guessing for slash-separated dates.
    if len(value) == 10:
        return date.fromisoformat(value)
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def review(order: Order) -> Order:
    reasons = list(order.review_reasons)
    for name in ("marketplace", "order_date", "currency"):
        if getattr(order, name) is None:
            reasons.append(f"Missing {name.replace('_', ' ')}")
    if not order.items:
        reasons.append("No supported product lines")
    if any(i.quantity is None or i.unit_price is None or i.currency is None for i in order.items):
        reasons.append("Some item quantities, prices or currencies are unknown")
    if any(i.currency and order.currency and i.currency != order.currency for i in order.items):
        reasons.append("Item currencies differ from the reported order currency")
    order.review_reasons = list(dict.fromkeys(reasons))
    return order

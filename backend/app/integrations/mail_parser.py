"""Conservative Amazon email adapter. Unrecognized templates remain review-only.

Do not retain full bodies or HTML. Sender domains are a relevance filter, not
cryptographic proof that a message represents a verified retailer record.
"""
import base64
from datetime import datetime, timezone
from email.utils import parseaddr
from html.parser import HTMLParser
import re

from pydantic import ValidationError

from .retailers import sender_retailer
from ..imports.models import MARKETPLACES, Item, Order, parse_date, review

MAX_BODY = 256 * 1024
SUBJECT = re.compile(r"\b(order|shipment|shipped|delivery|delivered|dispatch|cancelled|canceled|return|refund)\b", re.I)
ORDER_ID = re.compile(r"\b\d{3}-\d{7}-\d{7}\b")


class TextOnly(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.chunks, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "head"}:
            self.hidden += 1
        if tag in {"p", "br", "div", "tr", "li"}:
            self.chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "head"} and self.hidden:
            self.hidden -= 1
        if tag in {"p", "div", "tr", "li"}:
            self.chunks.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.chunks.append(data)


def metadata(message):
    headers = {h.get("name", "").lower(): h.get("value", "") for h in message.get("payload", {}).get("headers", []) if isinstance(h, dict) and isinstance(h.get("name"), str) and isinstance(h.get("value"), str) and len(h["value"]) <= 4096}
    address = parseaddr(headers.get("from", ""))[1].lower()
    domain = address.rsplit("@", 1)[-1] if "@" in address else ""
    marketplace = next((m for m in MARKETPLACES if domain == m or domain == "shipment-tracking." + m), None)
    return headers, marketplace


def detected_retailer(message):
    headers, _ = metadata(message)
    subject = headers.get("subject", "")
    if not isinstance(subject, str) or len(subject) > 4096 or not SUBJECT.search(subject):
        return None
    return sender_retailer(headers.get("from", ""))


def relevant(message):
    return detected_retailer(message) is not None


def extraction_supported(message):
    return detected_retailer(message) == "amazon"


def _text(payload, depth=0, budget=None):
    if budget is None:
        budget = [0, 0]
    budget[1] += 1
    if depth > 8 or budget[1] > 100:
        raise ValueError("MIME structure exceeds limits")
    parts = payload.get("parts", [])
    if parts:
        if payload.get('mimeType') == 'multipart/alternative':
            # Alternatives are representations of one body, not extra items.
            preferred = next((p for p in parts if p.get('mimeType') == 'text/plain'), None)
            preferred = preferred or next((p for p in parts if p.get('mimeType') == 'text/html'), None)
            return _text(preferred, depth + 1, budget) if preferred else ''
        chunks = [_text(p, depth + 1, budget) for p in parts if isinstance(p, dict)]
        return "\n".join(chunks)
    kind = payload.get("mimeType")
    if kind not in {"text/plain", "text/html"}:
        return ""
    data = payload.get("body", {}).get("data", "")
    if not isinstance(data, str) or len(data) > MAX_BODY * 2:
        raise ValueError("Oversized MIME body")
    raw = base64.b64decode(data + "=" * (-len(data) % 4), altchars=b"-_", validate=True)
    budget[0] += len(raw)
    if budget[0] > MAX_BODY:
        raise ValueError("Oversized message")
    text = raw.decode("utf-8", errors="strict")
    if kind == "text/html":
        parser = TextOnly()
        parser.feed(text)
        text = "".join(parser.chunks)
    return text


def parse_message(message):
    if not extraction_supported(message):
        return None
    headers, marketplace = metadata(message)
    try:
        body = _text(message.get("payload", {}))
        ids = set(ORDER_ID.findall(headers.get("subject", "") + "\n" + body))
        if len(ids) != 1:
            return None
        date_match = re.search(r"(?im)^\s*Order date:\s*(\d{4}-\d{2}-\d{2})\s*$", body)
        ordered = parse_date(date_match[1]) if date_match else None
        items = []
        # Recognize only this conservative labeled template. Other Amazon
        # templates still produce an order-ID observation requiring review.
        blocks = re.split(r"(?im)^\s*Item:\s*", body)[1:]
        if len(blocks) > 100:
            return None
        for block in blocks:
            lines = block.splitlines()
            name = lines[0].strip()
            qty = re.search(r"(?im)^\s*Quantity:\s*([1-9]\d{0,3})\s*$", block)
            amount = re.search(r"(?im)^\s*Unit price:\s*([A-Z]{3})\s+(\d{1,9}(?:\.\d{1,4})?)\s*$", block)
            asin = re.search(r"(?im)^\s*ASIN:\s*([A-Z0-9]{10})\s*$", block)
            items.append(Item(product_name=name, quantity=int(qty[1]) if qty else None, unit_price=amount[2] if amount else None, currency=amount[1] if amount else None, product_identifier=asin[1] if asin else None))
        currencies = {i.currency for i in items if i.currency}
        subject = headers.get("subject", "").lower()
        status = next((s for s in ("refund", "return", "cancelled", "canceled", "delivered", "shipped", "shipment", "order") if s in subject), "unknown")
        timestamp = datetime.fromtimestamp(int(message["internalDate"]) / 1000, timezone.utc).isoformat()
        order = Order(external_order_id=next(iter(ids)), marketplace=marketplace, order_date=ordered, currency=next(iter(currencies)) if len(currencies) == 1 else None, order_status=status, source="gmail", source_reference=message["id"], source_timestamp=timestamp, items=items, review_reasons=["Email extraction is unverified; confirm the order details in Amazon"])
        return review(order)
    except (ValueError, TypeError, KeyError, ValidationError, OverflowError, RecursionError):
        return None

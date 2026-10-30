"""Synthetic adapter contracts, never claims about an unobserved Amazon.in export."""
import io
import json
import zipfile
from pathlib import Path

import pytest


def record(**changes):
    return {"order_id": "123-1234567-1234567", "order_date": "2026-10-01", "marketplace": "amazon.in", "currency": "INR", "items": [{"product_name": "Test kettle", "quantity": 2, "unit_price": "1299.50", "asin": "B012345678"}], **changes}


def payload(*records):
    return json.dumps({"format": "cygnus-amazon-v1", "orders": list(records)}).encode()


def parse(data):
    from app.imports.amazon import parse_upload
    return parse_upload(data)


def archive(entries):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in entries:
            z.writestr(name, content)
    return data.getvalue()


def test_json_contract_preserves_exact_amount_and_unknowns():
    result = parse(payload(record()))
    assert len(result.orders) == 1
    order = result.orders[0]
    assert order.currency == "INR" and order.marketplace == "amazon.in"
    assert str(order.items[0].unit_price) == "1299.50"
    assert order.items[0].quantity == 2
    missing = parse(payload(record(items=[{"product_name": "Unknown price"}]))).orders[0]
    assert missing.items[0].unit_price is None
    assert missing.items[0].quantity is None
    assert missing.review_reasons


def test_nested_zip_csv_and_multiple_items():
    csv = 'Order ID,Order Date,Product Name,Quantity,Unit Price,Currency,Marketplace,ASIN\n123-1234567-1234567,2026-10-01,Kettle,1,20.00,INR,amazon.in,B012345678\n123-1234567-1234567,2026-10-01,Cup,2,10.00,INR,amazon.in,B112345678\n'
    result = parse(archive([("nested/orders.csv", csv), ("metadata/readme.txt", "synthetic")]))
    assert len(result.orders) == 1 and len(result.orders[0].items) == 2
    assert result.unsupported


@pytest.mark.parametrize("data", [b'{"format":"cygnus-amazon-v1","format":"other","orders":[]}', b'{"orders":[NaN]}', b'{oops', b'Order ID,Order Date,Product Name\n"unclosed', b'<html>not data</html>', b'PK\x03\x04broken'])
def test_malformed_or_unknown_upload_is_rejected(data):
    from app.imports.models import ImportProblem
    with pytest.raises(ImportProblem):
        parse(data)


@pytest.mark.parametrize("name", ["../orders.json", "/orders.json", "C:/orders.json", "x\\..\\orders.json"])
def test_traversal_is_rejected_without_extraction(name):
    from app.imports.models import ImportProblem
    with pytest.raises(ImportProblem):
        parse(archive([(name, payload(record()))]))


def test_zip_bomb_and_nested_archives_rejected():
    from app.imports.models import ImportProblem
    with pytest.raises(ImportProblem):
        parse(archive([("huge.json", b"a" * 2_000_000)]))
    with pytest.raises(ImportProblem):
        parse(archive([("nested.zip", archive([("orders.json", payload(record()))]))]))


def test_bad_item_prevents_partial_order_and_ambiguous_dates_require_review():
    bad = record(items=[{"product_name": "Good", "quantity": 1}, {"product_name": "Bad", "quantity": -2}])
    result = parse(payload(bad, record(order_id="321-1234567-1234567", order_date="01/02/2026")))
    assert not result.orders
    assert len(result.issues) == 2


def test_conflicting_duplicate_orders_are_not_silently_selected():
    result = parse(payload(record(), record(currency="USD")))
    assert not result.orders
    assert result.issues


def test_same_record_is_not_counted_twice():
    result = parse(payload(record(), record()))
    assert len(result.orders) == 1
    assert result.duplicate_records == 1


def test_missing_currency_never_infers_rupees_from_marketplace():
    result = parse(payload(record(currency=None)))
    assert result.orders[0].currency is None
    assert result.orders[0].items[0].currency is None
    assert result.orders[0].review_reasons


def test_mixed_item_currencies_require_review():
    raw = record(items=[{'product_name':'Cup','quantity':1,'unit_price':'10','currency':'USD'}])
    result = parse(payload(raw))
    assert any('currenc' in reason.lower() for reason in result.orders[0].review_reasons)


def test_checked_in_synthetic_json_and_csv_share_normalized_contract():
    folder = Path(__file__).parent / 'fixtures/amazon'
    json_order = parse((folder / 'synthetic-orders.json').read_bytes()).orders[0]
    csv_order = parse((folder / 'synthetic-orders.csv').read_bytes()).orders[0]
    assert json_order.model_dump() == csv_order.model_dump()

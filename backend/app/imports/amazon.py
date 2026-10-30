"""Bounded upload readers and explicit adapters; no claimed Amazon.in schema.

cygnus-amazon-v1 JSON and the documented CSV contract are synthetic interchange
formats. A real export adapter must be added after examining a redacted sample.
No archive entry is ever extracted to the filesystem.
"""
import csv
import io
import json
import re
import stat
import zipfile
from decimal import Decimal
from pathlib import PurePosixPath

from pydantic import ValidationError

from .models import ImportProblem, Item, Order, ParseResult, parse_date, review

MAX_UPLOAD = 10 * 1024 * 1024
MAX_EXPANDED = 30 * 1024 * 1024
MAX_ENTRY = 10 * 1024 * 1024
MAX_ENTRIES = 200
MAX_RECORDS = 5000
MAX_RATIO = 100
CSV_FIELDS = {"Order ID": "order_id", "Order Date": "order_date", "Product Name": "product_name", "Quantity": "quantity", "Unit Price": "unit_price", "Currency": "currency", "Marketplace": "marketplace", "ASIN": "asin", "Order Status": "order_status", "Item ID": "external_item_id", "Shipment ID": "shipment_id", "Delivery Date": "delivery_date", "Total Amount": "total_amount", "Payment Status": "payment_status", "Category": "category"}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def strict_json(text):
    return json.loads(text, object_pairs_hook=_unique, parse_float=Decimal, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON number")))


def _item(raw, currency):
    if not isinstance(raw, dict):
        raise ValueError("Invalid item")
    quantity = raw.get("quantity")
    if isinstance(quantity, str):
        if not re.fullmatch(r"[1-9]\d{0,4}", quantity):
            raise ValueError("Invalid quantity")
        quantity = int(quantity)
    details = {key: str(raw[key])[:500] for key in ("shipment_id", "shipment_status", "delivery_date", "product_details") if raw.get(key) is not None}
    return Item(product_name=raw.get("product_name", ""), external_item_id=raw.get("external_item_id"), product_identifier=raw.get("asin") or raw.get("product_identifier"), quantity=quantity, unit_price=raw.get("unit_price"), currency=raw.get("currency") or currency, category=raw.get("category"), details=details)


def _json_records(data):
    document = strict_json(data)
    if not isinstance(document, dict) or document.get("format") != "cygnus-amazon-v1" or not isinstance(document.get("orders"), list):
        raise ImportProblem("Unsupported JSON schema. A redacted export sample is needed to add its adapter.")
    if len(document["orders"]) > MAX_RECORDS:
        raise ImportProblem("Too many records")
    return document["orders"]


def _csv_records(data):
    reader = csv.DictReader(io.StringIO(data, newline=""), strict=True)
    headers = reader.fieldnames
    if not headers or len(headers) != len(set(headers)) or not {"Order ID", "Order Date", "Product Name"}.issubset(headers):
        raise ImportProblem("Unsupported CSV schema. Expected the documented interchange headers; Amazon.in exports need a verified adapter.")
    if not set(headers).issubset(CSV_FIELDS):
        raise ImportProblem("Unrecognized CSV columns; refusing to guess their meanings.")
    groups, seen_rows = {}, set()
    for index, row in enumerate(reader):
        if index >= MAX_RECORDS or None in row or any(v is None for v in row.values()):
            raise ImportProblem("CSV has too many records or inconsistent columns")
        raw = {CSV_FIELDS[k]: v.strip() or None for k, v in row.items()}
        identity = tuple(raw.items())
        if identity in seen_rows:
            raise ImportProblem("Ambiguous repeated CSV item rows; a source adapter is required to distinguish duplicates from separate items")
        seen_rows.add(identity)
        key = raw["order_id"]
        header = {k: raw.get(k) for k in ("order_id", "order_date", "currency", "marketplace", "order_status", "total_amount", "payment_status")}
        if key in groups and any(groups[key].get(k) != v for k, v in header.items()):
            raise ImportProblem("Conflicting CSV order metadata; review the source file")
        group = groups.setdefault(key, {**header, "items": []})
        group["items"].append(raw)
    return list(groups.values())


def _read_file(data, label, result):
    try:
        text = data.decode("utf-8-sig", errors="strict")
        if "\x00" in text:
            raise ValueError("NUL in data")
        records = _json_records(text) if text.lstrip().startswith(("{", "[")) else _csv_records(text)
    except ImportProblem:
        raise
    except (ValueError, UnicodeError, csv.Error, RecursionError, OverflowError):
        raise ImportProblem("Malformed JSON/CSV or invalid encoding; only strict UTF-8 data is supported.") from None
    for index, raw in enumerate(records):
        reference = f"{label}:{index + 1}"
        try:
            if not isinstance(raw, dict) or not isinstance(raw.get("items"), list):
                raise ValueError("Order requires item list")
            order = Order(external_order_id=raw.get("order_id"), marketplace=raw.get("marketplace"), order_date=parse_date(raw.get("order_date")), currency=raw.get("currency"), order_status=raw.get("order_status"), total_amount=raw.get("total_amount"), payment_status=raw.get("payment_status"), items=[_item(i, raw.get("currency")) for i in raw["items"]], source_reference=reference)
            result.orders.append(review(order))
        except (ValidationError, ValueError, TypeError, OverflowError):
            result.issues.append({"reference": reference, "code": "invalid_order", "message": "Invalid order, date, quantity, amount or product fields. The entire order was excluded."})


def parse_upload(data: bytes) -> ParseResult:
    if not data or len(data) > MAX_UPLOAD:
        raise ImportProblem("Upload must be nonempty and at most 10 MiB", 413)
    result = ParseResult()
    if data.startswith(b"PK"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                entries = archive.infolist()
                if len(entries) > MAX_ENTRIES:
                    raise ImportProblem("Archive contains too many entries")
                expanded, names = 0, set()
                for entry in entries:
                    name = entry.filename.replace("\\", "/")
                    path = PurePosixPath(name)
                    if path.is_absolute() or ".." in path.parts or ":" in name or "\x00" in name or name in names or len(name) > 400:
                        raise ImportProblem("Unsafe or duplicate archive path")
                    names.add(name)
                    mode = entry.external_attr >> 16
                    if stat.S_ISLNK(mode) or entry.flag_bits & 1:
                        raise ImportProblem("Symlinks and encrypted archives are unsupported")
                    if entry.is_dir():
                        continue
                    expanded += entry.file_size
                    if entry.file_size > MAX_ENTRY or expanded > MAX_EXPANDED or entry.file_size / max(entry.compress_size, 1) > MAX_RATIO:
                        raise ImportProblem("Archive exceeds decompression safety limits", 413)
                    if path.suffix.lower() in {".zip", ".gz", ".tar", ".7z", ".rar"}:
                        raise ImportProblem("Nested archives are unsupported; upload the inner order archive separately")
                    # Inspect unknown entries too; size limits apply regardless of extension.
                    with archive.open(entry) as stream:
                        content = stream.read(MAX_ENTRY + 1)
                    if len(content) > MAX_ENTRY or len(content) != entry.file_size:
                        raise ImportProblem("Archive entry size mismatch", 413)
                    if path.suffix.lower() in {".json", ".csv"}:
                        try:
                            _read_file(content, name, result)
                        except ImportProblem as error:
                            result.unsupported.append(f"{name}: {error.detail}")
                    else:
                        result.unsupported.append(f"{name}: no supported adapter")
                    if len(result.orders) + len(result.issues) > MAX_RECORDS:
                        raise ImportProblem("Too many orders in archive")
        except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError, EOFError):
            raise ImportProblem("Invalid or unsupported ZIP archive") from None
    else:
        _read_file(data, "upload", result)
    # Exact repeated order records are redundant; differing versions are unsafe.
    grouped, blocked = {}, set()
    for order in result.orders:
        key = (order.marketplace, order.external_order_id)
        if key in blocked:
            continue
        if key in grouped:
            previous = grouped[key]
            if previous.model_dump(exclude={"source_reference"}) == order.model_dump(exclude={"source_reference"}):
                result.duplicate_records += 1
            else:
                del grouped[key]
                blocked.add(key)
                result.issues.append({"reference": order.source_reference, "code": "conflicting_order", "message": "Conflicting versions of this order require a source-specific adapter."})
        else:
            grouped[key] = order
    result.orders = list(grouped.values())
    if not result.orders and not result.issues:
        raise ImportProblem("No supported order records found. Supply a redacted sample to add this export schema.")
    return result

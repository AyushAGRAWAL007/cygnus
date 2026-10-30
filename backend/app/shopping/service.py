"""Currency-separated Decimal reporting. Every entry point is owner-scoped."""
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import re
import sqlite3
import uuid

from fastapi import HTTPException
from ..db import connect

MAX_AMOUNT = Decimal('999999999999.99')


def amount(value):
    """Treat damaged, unbounded or non-finite persisted money as unknown."""
    if not isinstance(value, str) or len(value) > 40 or not re.fullmatch(r'\d{1,12}(?:\.\d{1,6})?', value):
        return None
    try:
        number = Decimal(value)
        return number if number.is_finite() and 0 <= number <= MAX_AMOUNT else None
    except InvalidOperation:
        return None


def money(value):
    return format(value, 'f')


def currency(value):
    return value if isinstance(value, str) and re.fullmatch('[A-Z]{3}', value) else None


def ready(conn):
    try:
        if not conn.execute("SELECT 1 FROM schema_migrations WHERE version='003_shopping_dashboard'").fetchone():
            raise sqlite3.OperationalError('missing migration')
        conn.execute('SELECT total_amount,payment_status FROM orders LIMIT 0')
        conn.execute('SELECT category,image_url,return_deadline FROM order_items LIMIT 0')
        conn.execute('SELECT id FROM refunds LIMIT 0')
    except sqlite3.Error:
        raise HTTPException(503, 'Shopping schema unavailable; explicitly apply migration 003_shopping_dashboard to a disposable database copy.') from None


def refund(row):
    return {key: row[key] for key in ('id', 'amount', 'currency', 'status', 'effective_date', 'reference', 'notes', 'confirmed_at')}


def safe_image(value):
    # Only established retailer image hosts; no request is made by the server.
    from urllib.parse import urlsplit
    if not value or len(value) > 2048:
        return None
    try:
        url = urlsplit(value)
        return value if url.scheme == 'https' and url.hostname in {'m.media-amazon.com', 'images-na.ssl-images-amazon.com', 'rukminim2.flixcart.com', 'assets.myntassets.com'} and not url.username and not url.password and url.port in (None, 443) else None
    except ValueError:
        return None


def order_view(conn, row, user_id):
    result = {key: row[key] for key in ('id', 'retailer', 'external_order_id', 'order_date', 'currency', 'order_status', 'payment_status', 'source')}
    result['currency'] = currency(row['currency'])
    total = amount(row['total_amount'])
    result['total_amount'] = money(total) if total is not None and result['currency'] else None
    result['simulated'] = bool(row['simulated'])
    result['items'] = []
    subtotal = Decimal(0)
    has_subtotal = False
    for item in conn.execute('SELECT i.* FROM order_items i JOIN orders o ON o.id=i.order_id WHERE i.order_id=? AND o.user_id=? ORDER BY i.id', (row['id'], user_id)):
        price = amount(item['unit_price'])
        quantity = item['quantity'] if isinstance(item['quantity'], int) and 0 < item['quantity'] <= 1000000 else None
        cur = currency(item['currency'])
        entry = {key: item[key] for key in ('id', 'name', 'category', 'return_deadline')}
        entry.update(quantity=quantity, unit_price=money(price) if price is not None else None, currency=cur,
                     image_url=safe_image(item['image_url']), return_eligibility='unknown')
        if item['final_sale']:
            entry['return_eligibility'] = 'ineligible'
        elif item['return_deadline']:
            try:
                entry['return_eligibility'] = 'eligible' if date.fromisoformat(item['return_deadline']) >= date.today() else 'expired'
            except ValueError:
                entry['return_deadline'] = None
        result['items'].append(entry)
        if price is not None and quantity is not None and cur and cur == result['currency']:
            subtotal += price * quantity
            has_subtotal = True
    result['quantity'] = sum(item['quantity'] or 0 for item in result['items'])
    result['unknown_quantities'] = sum(item['quantity'] is None for item in result['items'])
    result['known_items_subtotal'] = money(subtotal) if has_subtotal else None
    result['refunds'] = [refund(r) for r in conn.execute('SELECT * FROM refunds WHERE user_id=? AND order_id=? ORDER BY effective_date,id', (user_id, row['id']))]
    states = {r['status'] for r in result['refunds']}
    result['refund_status'] = 'mixed' if len(states) > 1 else next(iter(states), 'none')
    result['sources'] = sorted({row['source']} | {r[0] for r in conn.execute('SELECT source FROM order_source_references WHERE user_id=? AND order_id=?', (user_id, row['id']))})
    return result


def owned_orders(conn, user_id):
    ready(conn)
    return [order_view(conn, row, user_id) for row in conn.execute('SELECT * FROM orders WHERE user_id=? ORDER BY id', (user_id,))]


def list_orders(user_id, *, q='', retailer=None, date_from=None, date_to=None, status=None, sort='newest', currency_filter=None, page=1, page_size=20, scope='all'):
    if sort.startswith('amount') and not currency_filter:
        raise HTTPException(422, 'Amount sorting requires a currency')
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, 'date_from must not exceed date_to')
    with connect() as conn:
        orders = owned_orders(conn, user_id)
    retailers = sorted({o['retailer'] for o in orders})
    statuses = sorted({o['order_status'] for o in orders if o['order_status']})
    query = q.casefold()
    filtered = [o for o in orders if
                (scope == 'all' or o['simulated'] == (scope == 'demo')) and
                (not retailer or o['retailer'] == retailer) and
                (not status or o['order_status'] == status) and
                (not currency_filter or o['currency'] == currency_filter) and
                (not date_from or o['order_date'] and o['order_date'] >= date_from.isoformat()) and
                (not date_to or o['order_date'] and o['order_date'] <= date_to.isoformat()) and
                (not query or query in (o['external_order_id'] or '').casefold() or any(query in i['name'].casefold() for i in o['items']))]
    filtered.sort(key=lambda o: o['id'])
    if sort.startswith('amount'):
        known = [o for o in filtered if o['total_amount'] is not None]
        unknown = [o for o in filtered if o['total_amount'] is None]
        known.sort(key=lambda o: Decimal(o['total_amount']), reverse=sort == 'amount_desc')
        filtered = known + unknown
    else:
        known = [o for o in filtered if o['order_date']]
        unknown = [o for o in filtered if not o['order_date']]
        known.sort(key=lambda o: o['order_date'], reverse=sort == 'newest')
        filtered = known + unknown
    return dict(items=filtered[(page-1)*page_size:page*page_size], total=len(filtered), page=page, page_size=page_size, retailers=retailers, statuses=statuses)


def detail(user_id, order_id):
    with connect() as conn:
        ready(conn)
        row = conn.execute('SELECT * FROM orders WHERE id=? AND user_id=?', (order_id, user_id)).fetchone()
        if not row:
            raise HTTPException(404, 'Order not found')
        result = order_view(conn, row, user_id)
        result['return_cases'] = [dict(row) for row in conn.execute('SELECT c.* FROM return_cases c JOIN orders o ON o.id=c.order_id WHERE o.user_id=? AND o.id=? ORDER BY c.id', (user_id, order_id))]
        return result


def _overview(conn, user_id, orders):
    real = [o for o in orders if not o['simulated']]
    result = dict(total_orders=len(real), total_items=sum(o['quantity'] for o in real), unknown_quantities=sum(o['unknown_quantities'] for o in real), unknown_totals=sum(o['total_amount'] is None for o in real), open_returns=0, completed_returns=0, demo_orders=len(orders)-len(real), demo_open_returns=0, demo_completed_returns=0)
    for row in conn.execute('SELECT c.resolved,c.status,c.simulated,o.simulated AS order_simulated FROM return_cases c JOIN orders o ON o.id=c.order_id WHERE o.user_id=?', (user_id,)):
        prefix = 'demo_' if row['simulated'] or row['order_simulated'] else ''
        result[prefix + ('completed_returns' if row['resolved'] or row['status'] == 'resolved' else 'open_returns')] += 1
    totals = defaultdict(lambda: {'gross': Decimal(0), 'received': Decimal(0), 'pending': Decimal(0)})
    for order in real:
        cur = order['currency']
        if cur and order['total_amount'] is not None:
            totals[cur]['gross'] += Decimal(order['total_amount'])
        for ref in order['refunds']:
            value = amount(ref['amount'])
            refcur = currency(ref['currency'])
            if value is not None and refcur and refcur == cur:
                totals[refcur][ref['status']] += value
    result['currencies'] = [dict(currency=cur, **{k: money(v) for k, v in values.items()}, net=money(values['gross']-values['received'])) for cur, values in sorted(totals.items())]
    return result


def overview(user_id):
    with connect() as conn:
        return _overview(conn, user_id, owned_orders(conn, user_id))


def analytics(user_id):
    with connect() as conn:
        orders = owned_orders(conn, user_id)
        result = _overview(conn, user_id, orders)
    monthly, retailers, categories, counts = {}, {}, {}, defaultdict(int)
    for order in orders:
        if order['simulated']:
            continue
        try:
            month = date.fromisoformat(order['order_date']).strftime('%Y-%m')
        except (ValueError, TypeError):
            month = 'Unknown'
        counts[month] += 1
        cur = order['currency']
        if cur and order['total_amount'] is not None:
            for mapping, key in ((monthly, (month, cur)), (retailers, (order['retailer'], cur))):
                value, count = mapping.get(key, (Decimal(0), 0))
                mapping[key] = (value + Decimal(order['total_amount']), count + 1)
        for item in order['items']:
            if item['unit_price'] is not None and item['quantity'] is not None and item['currency']:
                key = (item['category'] or 'Unknown', item['currency'])
                categories[key] = categories.get(key, Decimal(0)) + Decimal(item['unit_price']) * item['quantity']
    result.update(monthly=[dict(month=k[0], currency=k[1], amount=money(v[0]), orders=v[1]) for k,v in sorted(monthly.items())],
                  retailers=[dict(retailer=k[0], currency=k[1], amount=money(v[0]), orders=v[1]) for k,v in sorted(retailers.items())],
                  categories=[dict(category=k[0], currency=k[1], amount=money(v)) for k,v in sorted(categories.items())],
                  order_counts=[dict(month=k, orders=v) for k,v in sorted(counts.items())])
    # Rank within each currency only; currencies have no meaningful shared ranking.
    tops = []
    for cur in sorted({o['currency'] for o in orders if o['currency']}):
        candidates = [o for o in orders if not o['simulated'] and o['currency'] == cur and o['total_amount'] is not None]
        candidates.sort(key=lambda o: o['id'])
        candidates.sort(key=lambda o: Decimal(o['total_amount']), reverse=True)
        tops.extend(candidates[:5])
    result['top_purchases'] = tops
    return result


def write_refund(user_id, order_id, data, refund_id=None):
    value = amount(data.amount)
    if value is None or value <= 0:
        raise HTTPException(422, 'Amount must be a positive finite decimal within supported bounds')
    if data.status == 'received' and data.confirm_received is not True:
        raise HTTPException(422, 'Explicit confirmation of receipt is required')
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        ready(conn)
        order = conn.execute('SELECT * FROM orders WHERE id=? AND user_id=?', (order_id, user_id)).fetchone()
        if not order:
            raise HTTPException(404, 'Order not found')
        if not currency(order['currency']) or order['currency'] != data.currency:
            raise HTTPException(422, 'Refund currency must match the known order currency')
        if refund_id:
            existing = conn.execute('SELECT * FROM refunds WHERE id=? AND order_id=? AND user_id=?', (refund_id, order_id, user_id)).fetchone()
            if not existing:
                raise HTTPException(404, 'Refund not found')
        else:
            existing = conn.execute('SELECT * FROM refunds WHERE user_id=? AND order_id=? AND reference=?', (user_id, order_id, data.reference)).fetchone()
        fields = dict(amount=money(value), currency=data.currency, status=data.status, effective_date=data.effective_date.isoformat(), reference=data.reference, notes=data.notes)
        if existing and all(existing[k] == v for k,v in fields.items()):
            return refund(existing)
        if existing and not refund_id:
            raise HTTPException(409, 'Reference already exists; update the existing refund')
        charged = amount(order['total_amount'])
        if order['total_amount'] is not None and charged is None:
            raise HTTPException(409, 'Stored charged total is invalid; reconcile the order before recording a refund')
        other_total = Decimal(0)
        for row in conn.execute('SELECT * FROM refunds WHERE user_id=? AND order_id=?', (user_id, order_id)):
            if existing and row['id'] == existing['id']:
                continue
            other = amount(row['amount'])
            if other is None or row['currency'] != data.currency:
                raise HTTPException(409, 'Stored refunds require reconciliation')
            other_total += other
        if charged is not None and other_total + value > charged:
            raise HTTPException(422, 'Recorded refunds exceed the charged order total')
        timestamp = datetime.now(timezone.utc).isoformat()
        confirmed = (existing['confirmed_at'] if existing and existing['status'] == 'received' else timestamp) if data.status == 'received' else None
        ident = existing['id'] if existing else str(uuid.uuid4())
        try:
            if existing:
                conn.execute('INSERT INTO refund_revisions(refund_id,user_id,snapshot_json,created_at) VALUES (?,?,?,?)', (ident, user_id, json.dumps(dict(existing), sort_keys=True), timestamp))
                conn.execute('UPDATE refunds SET amount=?,currency=?,status=?,effective_date=?,reference=?,notes=?,confirmed_at=?,updated_at=? WHERE id=? AND user_id=?', (*fields.values(), confirmed, timestamp, ident, user_id))
            else:
                conn.execute('INSERT INTO refunds(id,user_id,order_id,amount,currency,status,effective_date,reference,notes,confirmed_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', (ident, user_id, order_id, *fields.values(), confirmed, timestamp, timestamp))
        except sqlite3.IntegrityError:
            raise HTTPException(409, 'Refund reference is already in use') from None
        return refund(conn.execute('SELECT * FROM refunds WHERE id=? AND user_id=?', (ident,user_id)).fetchone())


def retailers(user_id):
    from ..integrations.retailers import catalogue
    with connect() as conn:
        ready(conn)
        counts = {r[0].casefold(): r[1] for r in conn.execute('SELECT retailer,COUNT(*) FROM orders WHERE user_id=? AND simulated=0 GROUP BY retailer', (user_id,))}
        integration = conn.execute("SELECT id,status,last_sync_at,error_code FROM integrations WHERE user_id=? AND provider='gmail'", (user_id,)).fetchone()
        detected = defaultdict(int)
        if integration:
            for row in conn.execute('SELECT observation_json FROM gmail_messages WHERE integration_id=?', (integration['id'],)):
                try:
                    observation = json.loads(row[0] or '{}')
                    retailer = observation.get('retailer')
                    if isinstance(retailer, str):
                        detected[retailer.casefold()] += 1
                except (ValueError, AttributeError):
                    pass
        items = [dict(entry, orders=counts.get(entry['id'].casefold(), counts.get(entry['name'].casefold(), 0)), detected_messages=detected[entry['id'].casefold()]) for entry in catalogue()]
        return dict(items=items, gmail={k: integration[k] if integration else ('disconnected' if k == 'status' else None) for k in ('status','last_sync_at','error_code')})

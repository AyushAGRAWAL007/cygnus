"""Dashboard financial, ownership, refund and migration regression tests."""
from pathlib import Path
import runpy
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import main, returns
from app.config import get_settings
from app.db import connect
from .test_import_service import register, HEADERS

MIGRATIONS = Path(__file__).resolve().parents[1] / 'migrations'


def migration(name):
    return runpy.run_path(str(MIGRATIONS / name))


@pytest.fixture
def client(tmp_path, monkeypatch):
    path = tmp_path / 'shopping.db'
    monkeypatch.setattr(get_settings(), 'database_path', str(path))
    returns.initialize()
    for filename in ('001_customer_ownership.py', '002_order_imports.py', '003_shopping_dashboard.py'):
        migration(filename)['migrate'](path)
    main.auth.limiter.reset()
    with TestClient(main.app) as client:
        register(client)
        yield client


def seed(client):
    with connect() as conn:
        owner = conn.execute('SELECT id FROM users').fetchone()[0]
        for ident, cur, total, day in [('real-a','USD','0.10','2026-10-01'), ('real-b','USD','0.20','2026-10-02'), ('real-c','INR','100',''), ('unknown','USD',None,'2026-09-01')]:
            conn.execute("INSERT INTO orders(id,retailer,order_date,simulated,user_id,source,currency,total_amount,order_status) VALUES (?,'amazon',?,0,?,'file',?,?,'delivered')", (ident,day,owner,cur,total))
        conn.execute("INSERT INTO order_items(id,order_id,name,quantity,unit_price,currency) VALUES ('line-a','real-a','A',2,'0.05','USD')")
        conn.execute("INSERT INTO order_items(id,order_id,name,quantity,unit_price,currency) VALUES ('line-b','unknown','Unknown',NULL,NULL,'USD')")
    return owner


def refund_data(**changes):
    return dict(amount='0.05',currency='USD',status='pending',effective_date='2026-10-02',reference='bank-1',confirm_received=False,**changes)


def test_unknowns_decimal_currency_separation_and_demo(client):
    seed(client)
    result = client.get('/api/shopping/overview').json()
    assert result['total_orders'] == 4 and result['demo_orders'] == 4
    assert result['total_items'] == 2 and result['unknown_quantities'] == 1
    assert result['unknown_totals'] == 1
    values = {entry['currency']: entry for entry in result['currencies']}
    assert values['USD']['gross'] == '0.30'
    assert values['INR']['gross'] == '100'
    report = client.get('/api/shopping/analytics').json()
    assert any(row['month'] == 'Unknown' and row['currency'] == 'INR' for row in report['monthly'])
    assert report['categories'] == [{'category':'Unknown','currency':'USD','amount':'0.10'}]
    assert sum(entry['orders'] for entry in report['order_counts']) == 4


def test_list_sort_filter_pagination_and_unknown_last(client):
    seed(client)
    assert client.get('/api/shopping/orders?sort=amount_desc').status_code == 422
    response = client.get('/api/shopping/orders?scope=real&currency=USD&sort=amount_desc&page_size=2').json()
    assert [o['id'] for o in response['items']] == ['real-b','real-a']
    assert response['total'] == 3
    response = client.get('/api/shopping/orders?scope=real&currency=USD&sort=amount_asc&page=2&page_size=2').json()
    assert [o['id'] for o in response['items']] == ['unknown']
    assert client.get('/api/shopping/orders?date_from=2026-11-01&date_to=2026-01-01').status_code == 422
    assert client.get('/api/shopping/orders?page_size=101').status_code == 422
    assert client.get('/api/shopping/orders?q=Unknown&scope=real').json()['total'] == 1
    assert client.get('/api/shopping/orders?scope=real&date_from=2026-10-01').json()['total'] == 2


def test_refund_idempotency_confirmation_audit_and_limits(client):
    seed(client)
    endpoint = '/api/shopping/orders/real-a/refunds'
    data = refund_data()
    first = client.post(endpoint, json=data, headers=HEADERS)
    assert first.status_code == 200, first.text
    ident = first.json()['id']
    assert client.post(endpoint, json=data, headers=HEADERS).json()['id'] == ident
    data['status'] = 'received'
    assert client.put(endpoint+'/'+ident,json=data,headers=HEADERS).status_code == 422
    data['confirm_received'] = True
    received = client.put(endpoint+'/'+ident,json=data,headers=HEADERS)
    assert received.status_code == 200 and received.json()['confirmed_at']
    assert client.put(endpoint+'/'+ident,json=data,headers=HEADERS).json() == received.json()
    with connect() as conn:
        assert conn.execute('SELECT COUNT(*) FROM refunds').fetchone()[0] == 1
        assert conn.execute('SELECT COUNT(*) FROM refund_revisions').fetchone()[0] == 1
    values = {entry['currency']:entry for entry in client.get('/api/shopping/overview').json()['currencies']}
    assert values['USD']['net'] == '0.25'
    assert client.post(endpoint,json={**data,'reference':'too-much','amount':'0.06'},headers=HEADERS).status_code == 422
    assert client.post(endpoint,json={**data,'reference':'wrong-currency','currency':'INR'},headers=HEADERS).status_code == 422
    for invalid in ('NaN','Infinity','-1','0','1e2','99999999999999999999999999'):
        assert client.post(endpoint,json={**data,'amount':invalid},headers=HEADERS).status_code == 422
    assert client.post(endpoint,json={**data,'amount':'0.04'},headers=HEADERS).status_code == 409


def test_account_isolation_and_csrf(client):
    seed(client)
    assert client.post('/api/shopping/orders/real-a/refunds',json=refund_data()).status_code == 403
    client.cookies.clear()
    register(client,'second@example.com')
    assert client.get('/api/shopping/orders/real-a').status_code == 404
    assert client.post('/api/shopping/orders/real-a/refunds',json=refund_data(),headers=HEADERS).status_code == 404
    assert client.get('/api/shopping/orders').json()['total'] == 0
    assert client.get('/api/shopping/overview').json()['currencies'] == []
    assert client.get('/api/shopping/analytics').json()['top_purchases'] == []


def test_missing_schema_is_actionable(client):
    with connect() as conn:
        conn.execute("DELETE FROM schema_migrations WHERE version='003_shopping_dashboard'")
    response = client.get('/api/shopping/overview')
    assert response.status_code == 503 and '003_shopping_dashboard' in response.json()['detail']


def test_migration_idempotency_drift_and_owned_foreign_keys(client):
    seed(client)
    migrate = migration('003_shopping_dashboard.py')['migrate']
    assert migrate(get_settings().database_path) is False
    with connect() as conn:
        assert not conn.execute('PRAGMA foreign_key_check').fetchall()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO orders(id,retailer,order_date) VALUES ('unowned','x','')")
        conn.execute('DROP TRIGGER shopping_order_owner_insert')
    with pytest.raises(RuntimeError, match='drift'):
        migrate(get_settings().database_path)


def test_migration_rolls_back_partial_ddl(tmp_path, monkeypatch):
    path = tmp_path/'rollback.db'
    monkeypatch.setattr(get_settings(),'database_path',str(path))
    returns.initialize()
    for filename in ('001_customer_ownership.py','002_order_imports.py'):
        migration(filename)['migrate'](path)
    # Force a failure after ALTER TABLE operations by colliding with a new table.
    with connect() as conn:
        conn.execute('CREATE TABLE refunds(id TEXT)')
    with pytest.raises(sqlite3.OperationalError):
        migration('003_shopping_dashboard.py')['migrate'](path)
    with connect() as conn:
        assert 'total_amount' not in {row[1] for row in conn.execute('PRAGMA table_info(orders)')}
        assert not conn.execute("SELECT 1 FROM schema_migrations WHERE version='003_shopping_dashboard'").fetchone()


def test_damaged_totals_are_unknown_and_refunds_refused(client):
    seed(client)
    with connect() as conn:
        conn.execute("UPDATE orders SET total_amount='NaN' WHERE id='real-a'")
    result = client.get('/api/shopping/overview').json()
    assert result['unknown_totals'] == 2
    assert client.post('/api/shopping/orders/real-a/refunds',json=refund_data(),headers=HEADERS).status_code == 409


def test_refunds_unknown_totals_demo_exclusion_and_owned_foreign_key(client):
    owner = seed(client)
    unknown = client.post('/api/shopping/orders/unknown/refunds', json={**refund_data(),'amount':'123.45'},headers=HEADERS)
    assert unknown.status_code == 200
    demo = client.post('/api/shopping/orders/demo-order-001/refunds',json={**refund_data(),'amount':'999'},headers=HEADERS)
    assert demo.status_code == 200
    overview = client.get('/api/shopping/overview').json()
    assert next(row for row in overview['currencies'] if row['currency']=='USD')['pending'] == '123.45'
    with connect() as conn:
        conn.execute("INSERT INTO users(id,email,display_name,created_at) VALUES ('outsider','outsider@example.com','Outsider','now')")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO refunds(id,user_id,order_id,amount,currency,status,effective_date,reference,created_at,updated_at) VALUES ('bad','outsider','real-a','1','USD','pending','2026-10-01','bad','now','now')")


def test_return_counts_and_retailer_metadata_owned(client):
    owner = seed(client)
    with connect() as conn:
        conn.execute("INSERT INTO return_cases(id,order_id,item_id,reason,status,created_at,updated_at,simulated) VALUES ('real-return','real-a','line-a','size','pickup_scheduled','now','now',0)")
        conn.execute("INSERT INTO return_cases(id,order_id,item_id,reason,status,resolved,created_at,updated_at,simulated) VALUES ('done-return','real-a','line-a','size','resolved',1,'now','now',0)")
        conn.execute("INSERT INTO integrations(id,user_id,provider,status,created_at,updated_at) VALUES ('gmail-shopping',?,'gmail','connected','now','now')",(owner,))
        conn.execute('INSERT INTO gmail_messages(integration_id,message_id,processed_at,outcome,observation_json) VALUES (?,?,?,?,?)',('gmail-shopping','metadata','now','unsupported','{"retailer":"flipkart"}'))
    overview = client.get('/api/shopping/overview').json()
    assert overview['open_returns'] == 1 and overview['completed_returns'] == 1
    assert overview['demo_open_returns'] + overview['demo_completed_returns'] == 1
    retailers = client.get('/api/shopping/retailers')
    assert retailers.status_code == 200, retailers.text
    values = {row['id']:row for row in retailers.json()['items']}
    assert values['amazon']['orders'] == 4
    assert values['flipkart']['detected_messages'] == 1 and not values['flipkart']['extraction_supported']
    assert retailers.json()['gmail']['status'] == 'connected'
    assert len(client.get('/api/shopping/orders/real-a').json()['return_cases']) == 2

from concurrent.futures import ThreadPoolExecutor
import io
import json
from pathlib import Path
import runpy
import sqlite3
import zipfile

import pytest

from app.config import get_settings
from app.db import connect
from app.imports.amazon import MAX_UPLOAD, parse_upload
from app.imports.models import ImportProblem
from .test_amazon_import import archive, record, payload
from .test_import_service import client, upload, confirm, register, HEADERS, MIGRATION


def test_oversized_upload_and_content_sniffing(client):
    assert upload(client, b'x' * (MAX_UPLOAD + 1)).status_code == 413
    assert upload(client, b'not a real zip').status_code == 422
    assert upload(client, payload(record())).status_code == 200


def test_nonupload_octet_stream_does_not_bypass_csrf(client):
    preview = upload(client).json()
    r = client.post(f"/api/imports/{preview['id']}/confirm", headers={**HEADERS, 'Content-Type': 'application/octet-stream'}, content=b'{}')
    assert r.status_code == 403
    assert client.post('/api/integrations/gmail/authorize', headers={**HEADERS,'Origin':'https://attacker.test'}, json={}).status_code == 403


def test_zip_entry_count_symlink_and_bad_csv():
    for contents in (archive([(f'{i}.txt','x') for i in range(201)]), b'Order ID,Order Date,Product Name\n123,2026-10-01,Cup,EXTRA\n'):
        with pytest.raises(ImportProblem):
            parse_upload(contents)
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w') as z:
        info = zipfile.ZipInfo('link.json')
        info.external_attr = 0o120777 << 16
        z.writestr(info, payload(record()))
    with pytest.raises(ImportProblem):
        parse_upload(data.getvalue())


def test_concurrent_confirmation_serializes_and_does_not_duplicate(client):
    from app.imports.service import confirm_preview
    owner = client.get('/api/auth/me').json()['id']
    one, two = upload(client).json(), upload(client).json()
    def save(preview):
        return confirm_preview(owner, preview['id'], [o['key'] for o in preview['orders']])
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, [one,two]))
    assert sum(r['imported'] for r in results) == 1
    assert sum(r['skipped'] for r in results) == 1


def test_provenance_composite_foreign_key_rejects_other_customer(client):
    preview = upload(client).json()
    confirm(client, preview)
    other = register(client, 'provenance-other@example.com')['id']
    with pytest.raises(sqlite3.IntegrityError):
        with connect() as c:
            order = c.execute('SELECT id FROM orders WHERE simulated=0').fetchone()[0]
            c.execute("INSERT INTO order_source_references(id,order_id,user_id,source,source_reference,observation_json,imported_at) VALUES ('bad',?,?,'gmail','x','{}','now')", (order, other))


def test_migration_detects_index_drift(client):
    with connect() as c:
        c.execute('DROP INDEX idx_import_order_identity')
    with pytest.raises(RuntimeError, match='drift'):
        runpy.run_path(str(MIGRATION))['migrate'](get_settings().database_path)


def test_repeated_csv_rows_require_review_instead_of_double_items():
    row = '123-1234567-1234567,2026-10-01,Cup,1,10.00,INR,amazon.in\n'
    data = ('Order ID,Order Date,Product Name,Quantity,Unit Price,Currency,Marketplace\n' + row * 2).encode()
    with pytest.raises(ImportProblem, match='repeated'):
        parse_upload(data)


@pytest.mark.parametrize('stage', ['CREATE TABLE import_previews','DROP TABLE order_items','INSERT INTO schema_migrations'])
def test_import_migration_rolls_back_schema_rebuild_on_failure(tmp_path, monkeypatch, stage):
    from unittest.mock import patch
    from app import returns
    from .test_migrations import snapshot
    path = tmp_path / 'rollback.db'
    monkeypatch.setattr(get_settings(),'database_path',str(path))
    returns.initialize()
    runpy.run_path(str(MIGRATION.with_name('001_customer_ownership.py')))['migrate'](path)
    original = snapshot(path)
    real_connect = sqlite3.connect
    class FaultConnection(sqlite3.Connection):
        def execute(self,sql,parameters=()):
            result = super().execute(sql,parameters)
            if stage in sql:
                raise RuntimeError('injected failure')
            return result
    def fault_connect(*args,**kwargs):
        return real_connect(*args,**kwargs,factory=FaultConnection)
    with patch('sqlite3.connect',fault_connect), pytest.raises(RuntimeError,match='injected failure'):
        runpy.run_path(str(MIGRATION))['migrate'](path)
    assert snapshot(path) == original


def test_prepare_database_copies_only_to_new_path(tmp_path, monkeypatch):
    from app import returns
    source = tmp_path / 'source.db'
    monkeypatch.setattr(get_settings(),'database_path',str(source))
    returns.initialize()
    import hashlib
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    prepare = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/prepare_import_database.py'))['prepare']
    output = tmp_path / 'disposable.db'
    assert prepare(output,source) == output
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    with pytest.raises(ValueError):
        prepare(source,source)
    with pytest.raises(ValueError):
        prepare(output,source)


def test_import_ai_refuses_gmail_provenance_even_when_first_source_was_file(client):
    from app.ai.nvidia import AssistantError, build_context
    from app.imports.models import Order, ParseResult
    from app.imports.service import create_preview
    owner = client.get('/api/auth/me').json()['id']
    preview = upload(client).json()
    confirm(client,preview)
    order = next(o for o in client.get('/api/orders').json()['items'] if not o['simulated'])
    data = Order.model_validate({**preview['orders'][0]['order'], 'source':'gmail','source_reference':'m1'})
    mail = create_preview(owner,'gmail','digest',ParseResult(orders=[data]))
    assert confirm(client,mail).status_code == 200
    with pytest.raises(AssistantError) as error:
        build_context(order_id=order['id'],user_id=owner)
    assert error.value.code == 'gmail_ai_unavailable'

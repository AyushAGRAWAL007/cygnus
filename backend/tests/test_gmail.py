import base64
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from pydantic import SecretStr

from app.config import get_settings
from app.db import connect
from .test_import_service import client, HEADERS, register, confirm


def message(message_id="m1", sender="Amazon <auto-confirm@amazon.in>", body=None):
    body = body or "Order #123-1234567-1234567\nOrder date: 2026-10-01\nItem: Test kettle\nQuantity: 1\nUnit price: INR 1299.50"
    return {"id": message_id, "internalDate": "1790812800000", "payload": {"mimeType": "text/plain", "headers": [{"name": "From", "value": sender}, {"name": "Subject", "value": "Your Amazon.in order confirmation"}], "body": {"data": base64.urlsafe_b64encode(body.encode()).decode()}}}


@pytest.fixture
def google(client, monkeypatch):
    from cryptography.fernet import Fernet
    from app.integrations import gmail
    settings = get_settings()
    monkeypatch.setattr(settings, "google_client_id", "fake-client")
    monkeypatch.setattr(settings, "google_client_secret", SecretStr("fake-secret"))
    monkeypatch.setattr(settings, "google_redirect_uri", "http://localhost:5173/api/integrations/gmail/callback")
    monkeypatch.setattr(settings, "integration_encryption_key", SecretStr(Fernet.generate_key().decode()))
    calls = []
    def handler(request):
        calls.append(request)
        if request.url.host == "oauth2.googleapis.com" and request.url.path == "/token":
            return httpx.Response(200, json={"access_token": "fake-access", "refresh_token": "fake-refresh", "expires_in": 3600, "scope": gmail.SCOPE, "token_type": "Bearer"})
        if request.url.path.endswith("/profile"):
            return httpx.Response(200, json={"emailAddress": "gmail-test@example.com", "historyId": "100"})
        if request.url.path.endswith("/messages"):
            return httpx.Response(200, json={"messages": [{"id": "m1"}]})
        if request.url.path.endswith("/messages/m1"):
            return httpx.Response(200, json=message())
        if request.url.path.endswith("/history"):
            return httpx.Response(200, json={"historyId": "101", "history": [{"messagesAdded": [{"message": {"id": "m1"}}]}]})
        if request.url.path == "/revoke":
            return httpx.Response(200)
        return httpx.Response(404)
    monkeypatch.setattr(gmail, "http_client", lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    return calls


def begin(client):
    r = client.post("/api/integrations/gmail/authorize", headers=HEADERS, json={})
    assert r.status_code == 200, r.text
    return parse_qs(urlsplit(r.json()["authorization_url"]).query)


def connect_gmail(client):
    query = begin(client)
    r = client.get("/api/integrations/gmail/callback", params={"state": query["state"][0], "code": "fake-code"}, follow_redirects=False)
    assert r.status_code == 303, r.text
    return query


def test_oauth_pkce_real_success_encryption_and_replay(client, google):
    query = connect_gmail(client)
    assert query["scope"] == ["https://www.googleapis.com/auth/gmail.readonly"]
    assert query["code_challenge_method"] == ["S256"]
    status = client.get("/api/integrations/gmail").json()
    assert status["status"] == "connected" and status["account_email"] == "gmail-test@example.com"
    assert "fake-access" not in json.dumps(status)
    with connect() as c:
        stored = str([tuple(r) for r in c.execute("SELECT * FROM integration_credentials")])
        assert "fake-access" not in stored and "fake-refresh" not in stored
    r = client.get("/api/integrations/gmail/callback", params={"state": query["state"][0], "code": "fake-code"})
    assert r.status_code == 400


def test_state_customer_session_expiry_and_missing_key(client, google, monkeypatch):
    query = begin(client)
    assert client.get("/api/integrations/gmail/callback", params={"state": "bad", "code": "fake"}).status_code == 400
    register(client, "other-gmail@example.com")
    assert client.get("/api/integrations/gmail/callback", params={"state": query["state"][0], "code": "fake"}).status_code == 400
    query = begin(client)
    with connect() as c:
        c.execute("UPDATE oauth_attempts SET expires_at='2000-01-01'")
    assert client.get("/api/integrations/gmail/callback", params={"state": query["state"][0], "code": "fake"}).status_code == 400
    monkeypatch.setattr(get_settings(), "integration_encryption_key", None)
    assert client.post("/api/integrations/gmail/authorize", headers=HEADERS, json={}).status_code == 503


def test_initial_incremental_sync_and_disconnect(client, google):
    connect_gmail(client)
    r = client.post("/api/integrations/gmail/sync", headers=HEADERS, json={})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["preview"]["counts"]["orders"] == 1
    assert confirm(client, data["preview"], acknowledge_review=True).json()["imported"] == 1
    result = client.post("/api/integrations/gmail/sync", headers=HEADERS, json={})
    assert result.status_code == 200 and result.json()["processed"] == 0
    assert sum(r.url.path.endswith("/messages/m1") and r.url.params.get('format') == 'full' for r in google) == 1
    assert sum(r.url.path.endswith("/messages/m1") and r.url.params.get('format') == 'metadata' for r in google) == 1
    assert any(r.url.path.endswith("/history") for r in google)
    assert client.get("/api/integrations/gmail").json()["last_sync_at"]
    assert client.post("/api/integrations/gmail/disconnect", headers=HEADERS, json={}).status_code == 200
    assert client.get("/api/integrations/gmail").json()["status"] == "disconnected"
    with connect() as c:
        assert not c.execute("SELECT * FROM integration_credentials").fetchall()


def test_refresh_expired_token_and_no_raw_body_retention(client, google):
    connect_gmail(client)
    with connect() as c:
        c.execute("UPDATE integration_credentials SET expires_at='2000-01-01'")
    assert client.post("/api/integrations/gmail/sync", headers=HEADERS, json={}).status_code == 200
    assert sum(r.url.path == "/token" for r in google) == 2
    with connect() as c:
        preview = c.execute("SELECT payload_json FROM import_previews").fetchone()[0]
        assert "Unit price:" not in preview and "auto-confirm@" not in preview


def test_parser_conservative_plain_html_and_sender_validation():
    from app.integrations.mail_parser import parse_message
    parsed = parse_message(message())
    assert parsed.external_order_id == "123-1234567-1234567"
    assert parsed.source_reference == "m1" and parsed.source == "gmail"
    assert str(parsed.items[0].unit_price) == "1299.50"
    assert parse_message(message(sender="Amazon <spoof@amazon.in.attacker.test>")) is None
    assert parse_message(message(body="A promotion with no order")) is None
    html = message(body="<script>secret()</script><p>Order #123-1234567-1234567</p><p>Item: Cup</p>")
    html["payload"]["mimeType"] = "text/html"
    result = parse_message(html)
    assert result.items[0].product_name == "Cup"
    assert "secret" not in result.model_dump_json()


def test_unauthorized_and_csrf_gmail_access(client):
    assert client.post("/api/integrations/gmail/authorize", json={}).status_code == 403
    client.cookies.clear()
    assert client.get("/api/integrations/gmail").status_code == 401
    assert client.post("/api/integrations/gmail/sync", json={}, headers=HEADERS).status_code == 401


@pytest.mark.parametrize('origin,csrf,content_type,reason', [
    ('http://127.0.0.1:5179', '1', 'application/json', 'untrusted_origin'),
    ('https://evil.example', '1', 'application/json', 'untrusted_origin'),
    (None, '1', 'application/json', 'untrusted_origin'),
    ('http://localhost:5179', None, 'application/json', 'missing_csrf_header'),
    ('http://localhost:5179', 'wrong', 'application/json', 'missing_csrf_header'),
    ('http://localhost:5179', '1', 'text/plain', 'invalid_content_type'),
])
def test_gmail_start_reports_csrf_rejection(client, google, monkeypatch, origin, csrf, content_type, reason):
    monkeypatch.setattr(get_settings(), 'auth_trusted_origins', 'http://localhost:5179')
    headers = {'Content-Type': content_type}
    if origin is not None:
        headers['Origin'] = origin
    if csrf is not None:
        headers['X-Cygnus-CSRF'] = csrf
    response = client.post('/api/integrations/gmail/authorize', content='{}', headers=headers)
    assert response.status_code == 403
    assert response.json()['reason'] == reason
    assert 'Cache-Control' in response.headers
    with connect() as conn:
        assert conn.execute('SELECT COUNT(*) FROM oauth_attempts').fetchone()[0] == 0


def test_gmail_start_from_localhost_5179_with_cookie_and_csrf(client, google, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, 'auth_trusted_origins', ' http://localhost:5179 ')
    monkeypatch.setattr(settings, 'google_redirect_uri', 'http://localhost:5179/api/integrations/gmail/callback')
    response = client.post('/api/integrations/gmail/authorize', json={}, headers={
        'Origin': 'http://localhost:5179', 'X-Cygnus-CSRF': '1',
    })
    assert response.status_code == 200
    query = parse_qs(urlsplit(response.json()['authorization_url']).query)
    assert query['redirect_uri'] == ['http://localhost:5179/api/integrations/gmail/callback']
    assert query['code_challenge_method'] == ['S256']
    assert query['state'][0]
    assert not google  # OAuth start does not call Google; navigation follows in browser.
    client.cookies.clear()
    response = client.post('/api/integrations/gmail/authorize', json={}, headers={
        'Origin': 'http://localhost:5179', 'X-Cygnus-CSRF': '1',
    })
    assert response.status_code == 401


def test_expired_or_abandoned_gmail_preview_can_be_recovered_without_refetch(client, google):
    connect_gmail(client)
    first = client.post('/api/integrations/gmail/sync', json={}, headers=HEADERS).json()['preview']
    with connect() as c:
        c.execute("UPDATE import_previews SET expires_at='2000-01-01' WHERE id=?", (first['id'],))
    again = client.post('/api/integrations/gmail/sync', json={}, headers=HEADERS).json()['preview']
    assert again and again['orders'][0]['order']['external_order_id'] == '123-1234567-1234567'
    assert sum(r.url.params.get('format') == 'full' for r in google) == 1


def test_failed_revocation_disables_sync_but_can_be_retried(client, google, monkeypatch):
    from app.integrations import gmail
    connect_gmail(client)
    original = gmail.call
    monkeypatch.setattr(gmail, 'call', lambda method, url, **kwargs: httpx.Response(503) if url.endswith('/revoke') else original(method, url, **kwargs))
    assert client.post('/api/integrations/gmail/disconnect', json={}, headers=HEADERS).status_code == 502
    assert client.get('/api/integrations/gmail').json()['status'] == 'revocation_pending'
    assert client.post('/api/integrations/gmail/sync', json={}, headers=HEADERS).status_code == 409
    monkeypatch.setattr(gmail, 'call', original)
    assert client.post('/api/integrations/gmail/disconnect', json={}, headers=HEADERS).status_code == 200


def test_google_request_errors_are_sanitized(client, google, monkeypatch):
    from app.integrations import gmail
    query = begin(client)
    monkeypatch.setattr(gmail, 'http_client', lambda: httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(400, json={'error': 'invalid_grant', 'error_description': 'fake-secret private email body'}))))
    r = client.get('/api/integrations/gmail/callback', params={'state': query['state'][0], 'code': 'fake-code'})
    assert r.status_code == 409
    assert 'fake-secret' not in r.text and 'private email body' not in r.text


def test_large_labeled_message_is_rejected_without_silent_truncation():
    from app.integrations.mail_parser import parse_message
    body = 'Order #123-1234567-1234567\n' + ''.join(f'Item: Product {i}\nQuantity: 1\n' for i in range(101))
    assert parse_message(message(body=body)) is None


def test_disconnect_invalidates_callback_already_exchanging_code(client, google, monkeypatch):
    from app.integrations import gmail
    connect_gmail(client)
    query = begin(client)
    original = gmail.call
    triggered = False
    def call(method, url, **kwargs):
        nonlocal triggered
        if url.endswith('/token') and not triggered:
            triggered = True
            gmail.disconnect(client.get('/api/auth/me').json()['id'])
        return original(method, url, **kwargs)
    monkeypatch.setattr(gmail, 'call', call)
    response = client.get('/api/integrations/gmail/callback', params={'state': query['state'][0], 'code': 'fake-code'}, follow_redirects=False)
    assert response.status_code == 409
    assert client.get('/api/integrations/gmail').json()['status'] == 'disconnected'
    with connect() as c:
        assert c.execute('SELECT COUNT(*) FROM integration_credentials').fetchone()[0] == 0


def test_pending_cap_produces_recovery_preview_instead_of_lockout(client, google):
    from app.integrations.mail_parser import parse_message
    connect_gmail(client)
    with connect() as c:
        integration_id = c.execute('SELECT id FROM integrations').fetchone()[0]
        observation = parse_message(message()).model_dump_json()
        for i in range(1000):
            c.execute("INSERT INTO gmail_messages(integration_id,message_id,processed_at,outcome,observation_json) VALUES (?,?,datetime('now'),'extracted',?)", (integration_id, f'pending{i}', observation))
    response = client.post('/api/integrations/gmail/sync', headers=HEADERS, json={})
    assert response.status_code == 200, response.text
    assert response.json()['preview']['orders']


def test_multipart_alternatives_are_one_logical_body():
    from app.integrations.mail_parser import parse_message
    plain = message()['payload']
    html = {**plain, 'mimeType': 'text/html'}
    data = message()
    data['payload'] = {'mimeType': 'multipart/alternative', 'headers': plain['headers'], 'parts': [plain, html]}
    assert len(parse_message(data).items) == 1


def test_slow_disconnect_does_not_delete_reconnected_credentials(client, google, monkeypatch):
    from app.integrations import gmail
    connect_gmail(client)
    owner = client.get('/api/auth/me').json()['id']
    original = gmail.call
    triggered = False
    def call(method, url, **kwargs):
        nonlocal triggered
        if url.endswith('/revoke') and not triggered:
            triggered = True
            gmail.disconnect(owner)
            connect_gmail(client)
        return original(method, url, **kwargs)
    monkeypatch.setattr(gmail, 'call', call)
    response = client.post('/api/integrations/gmail/disconnect', headers=HEADERS, json={})
    assert response.status_code == 409
    assert client.get('/api/integrations/gmail').json()['status'] == 'connected'
    with connect() as c:
        assert c.execute('SELECT COUNT(*) FROM integration_credentials').fetchone()[0] == 1


def test_initial_pagination_keeps_anchor_until_complete(client, google, monkeypatch):
    from app.integrations import gmail
    connect_gmail(client)
    original = gmail.call
    def call(method, url, **kwargs):
        if url.endswith('/messages'):
            return httpx.Response(200, json={'messages': [{'id':'m1'}], 'nextPageToken':'page2'} if not kwargs['params'].get('pageToken') else {'messages':[]})
        return original(method,url,**kwargs)
    monkeypatch.setattr(gmail, 'call', call)
    first = client.post('/api/integrations/gmail/sync', headers=HEADERS,json={}).json()
    assert first['has_more'] is True
    with connect() as c:
        row = c.execute('SELECT history_cursor,sync_anchor,page_cursor FROM integrations').fetchone()
        assert tuple(row) == (None,'100','page2')
    assert confirm(client,first['preview'],acknowledge_review=True).status_code == 200
    second = client.post('/api/integrations/gmail/sync', headers=HEADERS,json={}).json()
    assert second['has_more'] is False
    with connect() as c:
        assert tuple(c.execute('SELECT history_cursor,sync_anchor,page_cursor FROM integrations').fetchone()) == ('100',None,None)


def test_expired_history_cursor_recovers_with_bounded_search(client, google, monkeypatch):
    from app.integrations import gmail
    connect_gmail(client)
    original = gmail.call
    with connect() as c:
        c.execute("UPDATE integrations SET history_cursor='expired'")
    monkeypatch.setattr(gmail, 'call', lambda method,url,**kwargs: httpx.Response(404) if url.endswith('/history') else original(method,url,**kwargs))
    response = client.post('/api/integrations/gmail/sync', headers=HEADERS,json={})
    assert response.status_code == 200, response.text
    search = next(r for r in google if r.url.path.endswith('/messages'))
    assert 'newer_than:1y' in search.url.params['q']


def test_refresh_denial_requires_reauthorization_and_preserves_cursor(client, google, monkeypatch):
    from app.integrations import gmail
    connect_gmail(client)
    original = gmail.call
    with connect() as c:
        c.execute("UPDATE integration_credentials SET expires_at='2000-01-01'")
        c.execute("UPDATE integrations SET history_cursor='old-cursor'")
    monkeypatch.setattr(gmail, 'call', lambda method,url,**kwargs: httpx.Response(400,json={'error':'invalid_grant'}) if url.endswith('/token') else original(method,url,**kwargs))
    assert client.post('/api/integrations/gmail/sync',headers=HEADERS,json={}).status_code == 409
    assert client.get('/api/integrations/gmail').json()['status'] == 'reauthorization_required'
    with connect() as c:
        assert c.execute('SELECT history_cursor FROM integrations').fetchone()[0] == 'old-cursor'


def test_readonly_search_does_not_fetch_unrelated_full_body(client, google, monkeypatch):
    from app.integrations import gmail
    connect_gmail(client)
    original = gmail.call
    def call(method,url,**kwargs):
        if '/messages/m1' in url:
            return httpx.Response(200,json=message(sender='someone@other.test'))
        return original(method,url,**kwargs)
    monkeypatch.setattr(gmail,'call',call)
    response = client.post('/api/integrations/gmail/sync',headers=HEADERS,json={})
    assert response.status_code == 200 and response.json()['preview'] is None
    assert not any(r.url.params.get('format') == 'full' for r in google)


def test_google_redirect_configuration_and_session_rotation(client, google, monkeypatch):
    query = begin(client)
    login = client.post('/api/auth/login',headers=HEADERS,json={'email':'importer@example.com','password':'a very long test passphrase'})
    assert login.status_code == 200
    assert client.get('/api/integrations/gmail/callback',params={'state':query['state'][0],'code':'fake-code'}).status_code == 400
    monkeypatch.setattr(get_settings(),'google_redirect_uri','https://attacker.test/callback')
    assert client.post('/api/integrations/gmail/authorize',headers=HEADERS,json={}).status_code == 503


def test_google_read_retries_transient_error_without_logging_body(monkeypatch, caplog):
    from app.integrations import gmail
    attempts = []
    def handler(request):
        attempts.append(request)
        return httpx.Response(503 if len(attempts)==1 else 200,json={'secret_body':'never log this raw email'})
    monkeypatch.setattr(gmail,'http_client',lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    assert gmail.call('GET',gmail.API+'/profile').status_code == 200
    assert len(attempts) == 2
    assert 'never log this raw email' not in caplog.text


def test_oauth_requires_explicit_readonly_grant(client, google, monkeypatch):
    from app.integrations import gmail
    query = begin(client)
    original = gmail.call
    monkeypatch.setattr(gmail,'call',lambda method,url,**kwargs: httpx.Response(200,json={'access_token':'fake','refresh_token':'fake-refresh','expires_in':3600,'token_type':'Bearer'}) if url.endswith('/token') else original(method,url,**kwargs))
    assert client.get('/api/integrations/gmail/callback',params={'state':query['state'][0],'code':'fake-code'},follow_redirects=False).status_code == 409

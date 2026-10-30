"""Google OAuth + bounded user-triggered Gmail sync. No mailbox mutations.

HTTP response bodies, message content and tokens must never be logged. All
Google failures become fixed local errors. Tests replace http_client, not auth.
"""
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import secrets
import time
from urllib.parse import urlencode, urlsplit
import uuid

import httpx

from ..auth import COOKIE, token_hash
from ..config import get_settings
from ..imports.models import ImportProblem, Order, ParseResult
from ..imports.service import create_preview, database, now
from .crypto import cipher, decrypt, encrypt
from .mail_parser import parse_message, relevant, detected_retailer, extraction_supported
from .retailers import search_domains

SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
API = "https://gmail.googleapis.com/gmail/v1/users/me"
SEARCH = "{" + " ".join("from:" + domain for domain in search_domains()) + "} {subject:order subject:shipment subject:shipped subject:delivery subject:delivered subject:cancelled subject:return subject:refund} newer_than:1y"


def http_client():
    return httpx.Client(timeout=15, follow_redirects=False)


def configuration():
    settings = get_settings()
    cipher()  # Missing/invalid key must fail before OAuth or any token storage.
    if not settings.google_client_id or not settings.google_client_secret or not settings.google_redirect_uri:
        raise ImportProblem("Gmail is not configured. Set the server-side Google OAuth settings and encryption key.", 503)
    parsed = urlsplit(settings.google_redirect_uri)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if (parsed.path != "/api/integrations/gmail/callback" or parsed.query or parsed.fragment or parsed.username or parsed.password
            or origin not in settings.auth_origin_list
            or (parsed.scheme != "https" and not (settings.app_env in {"development", "test", "demo"} and parsed.hostname in {"localhost", "127.0.0.1"}))):
        raise ImportProblem("Google redirect URI must use the trusted application origin and exact Gmail callback path", 503)
    return settings


def call(method, url, **kwargs):
    # Never accept a provider-supplied arbitrary URL or log exceptions/bodies.
    try:
        with http_client() as client:
            response = None
            for attempt in range(3):
                response = client.request(method, url, **kwargs)
                if response.status_code not in {429, 500, 502, 503, 504} or method != "GET" or attempt == 2:
                    return response
                time.sleep(0.15 * 2 ** attempt)
            return response
    except httpx.HTTPError:
        raise ImportProblem("Google is temporarily unavailable. Retry the operation.", 502) from None


def response_json(response):
    if len(response.content) > 2 * 1024 * 1024:
        raise ImportProblem("Google response exceeded safety limits", 502)
    try:
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError()
        return result
    except ValueError:
        raise ImportProblem("Google returned an invalid response", 502) from None


def authorize(user_id, session_token):
    settings = configuration()
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    with database() as conn:
        conn.execute('BEGIN IMMEDIATE')
        integration = conn.execute("SELECT * FROM integrations WHERE user_id=? AND provider='gmail'", (user_id,)).fetchone()
        if integration and integration['status'] == 'revocation_pending':
            raise ImportProblem('Complete disconnect before connecting Gmail again', 409)
        if not integration:
            conn.execute("INSERT INTO integrations(id,user_id,provider,status,created_at,updated_at,generation) VALUES (?,?,'gmail','disconnected',?,?,?)", (uuid.uuid4().hex,user_id,now(),now(),uuid.uuid4().hex))
            integration = conn.execute("SELECT * FROM integrations WHERE user_id=? AND provider='gmail'", (user_id,)).fetchone()
        conn.execute("DELETE FROM oauth_attempts WHERE expires_at<?", (now(),))
        conn.execute("INSERT INTO oauth_attempts(state_hash,user_id,session_hash,verifier_encrypted,expires_at,integration_generation) VALUES (?,?,?,?,?,?)", (token_hash(state), user_id, token_hash(session_token), encrypt(verifier), (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(), integration['generation']))
    params = {"client_id": settings.google_client_id, "redirect_uri": settings.google_redirect_uri, "response_type": "code", "scope": SCOPE, "access_type": "offline", "prompt": "consent", "state": state, "code_challenge": challenge, "code_challenge_method": "S256"}
    return {"authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)}


def _tokens(response, require_refresh=False):
    if response.status_code != 200:
        raise ImportProblem("Google authorization expired or was denied. Connect Gmail again.", 409)
    data = response_json(response)
    scope = data.get('scope')
    if (not isinstance(data.get("access_token"), str) or not data["access_token"] or len(data["access_token"]) > 16384
            or data.get("token_type", "").lower() != "bearer"
            or not isinstance(data.get("expires_in"), int) or not 1 <= data["expires_in"] <= 86400
            or require_refresh and (not isinstance(data.get("refresh_token"), str) or not data['refresh_token'] or len(data['refresh_token']) > 16384 or scope != SCOPE)
            or scope is not None and (not isinstance(scope,str) or set(scope.split()) != {SCOPE})):
        raise ImportProblem("Google did not grant the required read-only authorization", 409)
    return data


def callback(user_id, session_token, state, code, error=None):
    settings = configuration()
    with database() as conn:
        conn.execute("BEGIN IMMEDIATE")
        attempt = conn.execute("SELECT * FROM oauth_attempts WHERE state_hash=? AND user_id=? AND session_hash=? AND consumed=0 AND expires_at>?", (token_hash(state), user_id, token_hash(session_token), now())).fetchone()
        if not attempt:
            raise ImportProblem("Invalid, expired or already used Gmail authorization state", 400)
        conn.execute("UPDATE oauth_attempts SET consumed=1 WHERE state_hash=?", (token_hash(state),))
    if error or not code:
        raise ImportProblem("Gmail authorization was not completed", 400)
    tokens = _tokens(call("POST", "https://oauth2.googleapis.com/token", data={"grant_type": "authorization_code", "client_id": settings.google_client_id, "client_secret": settings.google_client_secret.get_secret_value(), "redirect_uri": settings.google_redirect_uri, "code": code, "code_verifier": decrypt(attempt["verifier_encrypted"])}), require_refresh=True)
    profile_response = call("GET", API + "/profile", headers={"Authorization": "Bearer " + tokens["access_token"]})
    if profile_response.status_code != 200:
        raise ImportProblem("Gmail account could not be verified", 502)
    profile = response_json(profile_response)
    email = profile.get("emailAddress")
    if not isinstance(email, str) or "@" not in email or len(email) > 254:
        raise ImportProblem("Google returned an invalid account", 502)
    accepted = _store_connection(user_id, attempt, tokens, email)
    if not accepted:
        # Disconnect/reconnect invalidated this in-flight attempt. Do not retain
        # a token issued after revocation; best effort revoke the stale grant.
        try:
            call('POST', 'https://oauth2.googleapis.com/revoke', data={'token': tokens['refresh_token']})
        except ImportProblem:
            pass
        raise ImportProblem('Gmail connection changed during authorization; this callback was discarded', 409)
    parsed = urlsplit(settings.google_redirect_uri)
    return f"{parsed.scheme}://{parsed.netloc}/#/orders"


def _store_connection(user_id, attempt, tokens, email):
    with database() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM integrations WHERE user_id=? AND provider='gmail'", (user_id,)).fetchone()
        current_attempt = conn.execute('SELECT 1 FROM oauth_attempts WHERE state_hash=? AND consumed=1', (attempt['state_hash'],)).fetchone()
        if not current_attempt or not row or row['generation'] != attempt['integration_generation']:
            return False
        integration_id = row["id"] if row else uuid.uuid4().hex
        if row:
            if row["sync_lease_until"] and row["sync_lease_until"] > now():
                raise ImportProblem("Gmail is busy; finish synchronization before reconnecting", 409)
            if row["status"] == "revocation_pending":
                raise ImportProblem("Retry disconnect before connecting another account", 409)
            # Reconnecting a different mailbox requires clearing message IDs/cursors.
            conn.execute("DELETE FROM gmail_messages WHERE integration_id=?", (integration_id,))
            conn.execute("UPDATE integrations SET account_email=?,status='connected',history_cursor=NULL,page_cursor=NULL,sync_anchor=NULL,last_sync_at=NULL,error_code=NULL,generation=?,updated_at=? WHERE id=?", (email, uuid.uuid4().hex, now(), integration_id))
            conn.execute("DELETE FROM integration_credentials WHERE integration_id=?", (integration_id,))
        else:
            conn.execute("INSERT INTO integrations(id,user_id,provider,status,created_at,updated_at,account_email,generation) VALUES (?,?,'gmail','connected',?,?,?,?)", (integration_id, user_id, now(), now(), email, uuid.uuid4().hex))
        conn.execute("INSERT INTO integration_credentials(id,integration_id,encrypted_access_token,encrypted_refresh_token,expires_at,updated_at) VALUES (?,?,?,?,?,?)", (uuid.uuid4().hex, integration_id, encrypt(tokens["access_token"]), encrypt(tokens["refresh_token"]), (datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])).isoformat(), now()))
    return True


def status(user_id):
    with database() as conn:
        row = conn.execute("SELECT status,account_email,last_sync_at,error_code,page_cursor,sync_lease_until FROM integrations WHERE user_id=? AND provider='gmail'", (user_id,)).fetchone()
        if not row:
            return {"status": "disconnected", "account_email": None, "last_sync_at": None, "has_more": False, "error_code": None}
        return {"status": row["status"], "account_email": row["account_email"], "last_sync_at": row["last_sync_at"], "has_more": bool(row["page_cursor"]), "error_code": row["error_code"]}


def _access(integration):
    settings = configuration()
    with database() as conn:
        credential = conn.execute("SELECT * FROM integration_credentials WHERE integration_id=?", (integration["id"],)).fetchone()
    if not credential:
        raise ImportProblem("Connect Gmail before synchronizing", 409)
    if credential["expires_at"] > (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat():
        return decrypt(credential["encrypted_access_token"])
    refresh = decrypt(credential["encrypted_refresh_token"])
    response = call("POST", "https://oauth2.googleapis.com/token", data={"grant_type": "refresh_token", "refresh_token": refresh, "client_id": settings.google_client_id, "client_secret": settings.google_client_secret.get_secret_value()})
    try:
        tokens = _tokens(response)
    except ImportProblem:
        if response.status_code in {400, 401}:
            with database() as conn:
                conn.execute("UPDATE integrations SET status='reauthorization_required',error_code='authorization_expired' WHERE id=? AND generation=?", (integration["id"], integration["generation"]))
        raise
    with database() as conn:
        conn.execute("UPDATE integration_credentials SET encrypted_access_token=?,encrypted_refresh_token=?,expires_at=?,updated_at=? WHERE integration_id=? AND EXISTS(SELECT 1 FROM integrations WHERE id=? AND generation=? AND status='connected')", (encrypt(tokens["access_token"]), encrypt(tokens.get("refresh_token") or refresh), (datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])).isoformat(), now(), integration["id"], integration["id"], integration["generation"]))
    return tokens["access_token"]


def sync(user_id):
    configuration()
    with database() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM integrations WHERE user_id=? AND provider='gmail' AND status='connected'", (user_id,)).fetchone()
        if not row:
            raise ImportProblem("Connect or reauthorize Gmail before synchronizing", 409)
        if row["sync_lease_until"] and row["sync_lease_until"] > now():
            raise ImportProblem("Gmail synchronization is already running", 409)
        integration = dict(row)
        lease = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        integration['lease'] = lease
        conn.execute("UPDATE integrations SET sync_lease_until=? WHERE id=?", (lease, row["id"]))
    try:
        return _sync_page(user_id, integration)
    except ImportProblem as error:
        with database() as conn:
            conn.execute("UPDATE integrations SET error_code=CASE WHEN status='reauthorization_required' THEN 'authorization_expired' ELSE ? END WHERE id=? AND generation=?", ("sync_failed" if error.status_code != 409 else "authorization_or_state_error", integration["id"], integration["generation"]))
        raise
    finally:
        with database() as conn:
            conn.execute("UPDATE integrations SET sync_lease_until=NULL WHERE id=? AND sync_lease_until=?", (integration["id"], lease))


def _sync_page(user_id, integration):
    token = _access(integration)
    headers = {"Authorization": "Bearer " + token}
    def get(path, params=None, allow_missing=False):
        response = call("GET", API + path, headers=headers, params=params)
        if response.status_code == 404 and allow_missing:
            return None
        if response.status_code == 401:
            with database() as conn:
                conn.execute("UPDATE integrations SET status='reauthorization_required',error_code='authorization_expired' WHERE id=? AND generation=?", (integration["id"], integration["generation"]))
            raise ImportProblem("Google authorization is no longer valid. Reconnect Gmail.", 409)
        if response.status_code != 200:
            raise ImportProblem("Gmail synchronization failed. Retry; the previous cursor was preserved.", 502)
        return response_json(response)
    page = integration["page_cursor"]
    cursor = integration["history_cursor"]
    anchor = integration["sync_anchor"]
    if cursor:
        data = get("/history", {"startHistoryId": cursor, "historyTypes": "messageAdded", "maxResults": 50, **({"pageToken": page} if page else {})}, allow_missing=True)
        if data is None:
            # Expired history: bounded recent Amazon search; message IDs dedupe.
            cursor, page, anchor = None, None, None
    if not cursor:
        if not anchor:
            anchor = get("/profile").get("historyId")
        data = get("/messages", {"q": SEARCH, "maxResults": 50, **({"pageToken": page} if page else {})})
        ids = [m.get("id") for m in data.get("messages", []) if isinstance(m, dict)]
    else:
        ids = [added.get("message", {}).get("id") for h in data.get("history", []) for added in h.get("messagesAdded", [])]
    ids = list(dict.fromkeys(i for i in ids if isinstance(i, str) and 0 < len(i) <= 200))
    if len(ids) > 200:
        raise ImportProblem("Gmail change page is too large; narrower synchronization is required", 422)
    parsed = ParseResult()
    processed = []
    with database() as conn:
        conn.execute("DELETE FROM gmail_messages WHERE integration_id=? AND outcome='extracted' AND processed_at<?", (integration["id"], (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()))
        seen = {r[0] for r in conn.execute("SELECT message_id FROM gmail_messages WHERE integration_id=?", (integration["id"],))}
        pending = conn.execute("SELECT observation_json FROM gmail_messages WHERE integration_id=? AND outcome='extracted' AND observation_json IS NOT NULL LIMIT 1000", (integration["id"],)).fetchall()
        parsed.orders.extend(Order.model_validate_json(r[0]) for r in pending)
    if len(pending) >= 1000:
        with database() as conn:
            conn.execute('BEGIN IMMEDIATE')
            _require_current(conn,user_id,integration)
            preview = create_preview(user_id, 'gmail', 'pending-recovery', parsed,conn)
        return {'processed': 0, 'preview': preview, 'has_more': True}
    for message_id in ids:
        if message_id in seen:
            continue
        meta = get("/messages/" + _message_id(message_id), {"format": "metadata", "metadataHeaders": ["From", "Subject"]}, allow_missing=True)
        outcome, observation = "irrelevant", None
        if meta and relevant(meta):
            if not extraction_supported(meta):
                retailer = detected_retailer(meta)
                parsed.issues.append({"reference": message_id, "code": "unsupported_retailer", "message": "Retailer detected from metadata; no verified extraction adapter"})
                processed.append((message_id, "unsupported", json.dumps({"retailer": retailer})))
                continue
            full = get("/messages/" + _message_id(message_id), {"format": "full"}, allow_missing=True)
            order = parse_message(full) if full else None
            if order:
                parsed.orders.append(order)
                observation = order.model_dump_json()
                outcome = "extracted"
            else:
                parsed.issues.append({"reference": message_id, "code": "unsupported_email", "message": "Amazon email template could not be parsed safely"})
                outcome = "unsupported"
        processed.append((message_id, outcome, observation))
    next_page = data.get("nextPageToken")
    next_cursor = cursor if next_page and cursor else (data.get("historyId") if cursor else (None if next_page else anchor))
    if not next_page and not next_cursor:
        raise ImportProblem("Gmail did not return a synchronization cursor", 502)
    with database() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _require_current(conn,user_id,integration)
        # The engine groups order identities for review while preserving each
        # message observation separately instead of overwriting saved products.
        preview = create_preview(user_id, "gmail", hashlib.sha256(json.dumps(ids).encode()).hexdigest(), parsed, conn) if parsed.orders or parsed.issues else None
        for message_id, outcome, observation in processed:
            conn.execute("INSERT INTO gmail_messages(integration_id,message_id,processed_at,outcome,observation_json) VALUES (?,?,?,?,?) ON CONFLICT DO NOTHING", (integration["id"], message_id, now(), outcome, observation))
        conn.execute("UPDATE integrations SET history_cursor=?,page_cursor=?,sync_anchor=?,last_sync_at=?,error_code=NULL,updated_at=? WHERE id=?", (next_cursor, next_page, anchor if next_page and not cursor else None, now(), now(), integration["id"]))
    return {"processed": len(processed), "extracted": sum(p[1] == "extracted" for p in processed), "unsupported": sum(p[1] == "unsupported" for p in processed), "preview": preview, "has_more": bool(next_page)}


def _message_id(value):
    if not value.isalnum():
        raise ImportProblem("Gmail returned an invalid message ID", 502)
    return value


def _require_current(conn,user_id,integration):
    current = conn.execute('SELECT generation,status,sync_lease_until FROM integrations WHERE id=? AND user_id=?', (integration['id'],user_id)).fetchone()
    if not current or current['generation'] != integration['generation'] or current['status'] != 'connected' or current['sync_lease_until'] != integration['lease']:
        raise ImportProblem('Gmail connection changed during synchronization; results were discarded',409)


def disconnect(user_id):
    configuration()
    revocation_generation = uuid.uuid4().hex
    with database() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM integrations WHERE user_id=? AND provider='gmail'", (user_id,)).fetchone()
        if not row or row["status"] == "disconnected":
            conn.execute('DELETE FROM oauth_attempts WHERE user_id=?', (user_id,))
            if row:
                conn.execute('UPDATE integrations SET generation=? WHERE id=?', (revocation_generation,row['id']))
            return {"status": "disconnected"}
        credential = conn.execute("SELECT * FROM integration_credentials WHERE integration_id=?", (row["id"],)).fetchone()
        conn.execute("UPDATE integrations SET status='revocation_pending',generation=?,updated_at=? WHERE id=?", (revocation_generation, now(), row["id"]))
        conn.execute('DELETE FROM oauth_attempts WHERE user_id=?', (user_id,))
    if credential:
        token = decrypt(credential["encrypted_refresh_token"] or credential["encrypted_access_token"])
        response = call("POST", "https://oauth2.googleapis.com/revoke", data={"token": token})
        # Google's invalid_token means there is no remaining grant to revoke.
        if response.status_code != 200 and not (response.status_code == 400 and response_json(response).get("error") == "invalid_token"):
            raise ImportProblem("Local synchronization is disabled. Google revocation failed; retry disconnect or revoke access in your Google account.", 502)
    with database() as conn:
        conn.execute('BEGIN IMMEDIATE')
        current = conn.execute('SELECT generation,status FROM integrations WHERE id=?', (row['id'],)).fetchone()
        if not current or current['generation'] != revocation_generation or current['status'] != 'revocation_pending':
            raise ImportProblem('Gmail connection changed during revocation; newer credentials were preserved', 409)
        conn.execute("DELETE FROM integration_credentials WHERE integration_id=?", (row["id"],))
        conn.execute("DELETE FROM gmail_messages WHERE integration_id=?", (row["id"],))
        conn.execute("DELETE FROM oauth_attempts WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM import_previews WHERE user_id=? AND source='gmail'", (user_id,))
        conn.execute("UPDATE integrations SET status='disconnected',account_email=NULL,history_cursor=NULL,page_cursor=NULL,sync_anchor=NULL,sync_lease_until=NULL,error_code=NULL,updated_at=? WHERE id=?", (now(), row["id"]))
    return {"status": "disconnected"}

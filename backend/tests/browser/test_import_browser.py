r"""Opt-in full browser flow; owns temporary DB + servers, never uses live DB.

Run: $env:CYGNUS_BROWSER_TESTS='1'; .venv\Scripts\python.exe -m pytest tests/browser -q
Requires requirements-dev.txt and installed Microsoft Edge or Playwright Chromium.
"""
import hashlib
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import threading
import time

import httpx
import pytest
import uvicorn

from app import main, returns
from app.config import get_settings
from app.db import connect
from tests.test_amazon_import import archive, payload, record

pytestmark = pytest.mark.skipif(os.environ.get('CYGNUS_BROWSER_TESTS') != '1', reason='Opt-in real-browser tests')
ROOT = Path(__file__).resolve().parents[3]


def wait_url(url, process=None):
    deadline = time.monotonic() + 35
    while time.monotonic() < deadline:
        if process and process.poll() is not None:
            raise RuntimeError('Browser test dev server exited')
        try:
            if httpx.get(url, timeout=1).status_code < 500:
                return
        except httpx.HTTPError:
            pass
        time.sleep(.15)
    raise RuntimeError('Browser test server startup timed out')


def test_browser_file_import_and_responsive_orders(tmp_path, monkeypatch):
    from playwright.sync_api import sync_playwright, expect
    live = ROOT / 'backend/cygnus.db'
    original_hash = hashlib.sha256(live.read_bytes()).hexdigest()
    settings = get_settings()
    monkeypatch.setattr(settings, 'database_path', str(tmp_path / 'browser.db'))
    monkeypatch.setattr(settings, 'app_env', 'test')
    monkeypatch.setattr(settings, 'auth_trusted_origins', 'http://localhost:5177')
    monkeypatch.setattr(settings, 'nvidia_api_key', None)
    monkeypatch.setattr(settings, 'nebius_api_key', None)
    monkeypatch.setattr(settings, 'google_client_id', None)
    monkeypatch.setattr(settings, 'google_client_secret', None)
    monkeypatch.setattr(settings, 'integration_encryption_key', None)
    returns.initialize()
    for name in ('001_customer_ownership.py', '002_order_imports.py', '003_shopping_dashboard.py'):
        runpy.run_path(str(ROOT / 'backend/migrations' / name))['migrate'](settings.database_path)
    main.auth.limiter.reset()
    server = uvicorn.Server(uvicorn.Config(main.app, host='127.0.0.1', port=8017, log_level='error', access_log=False))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    env = {**os.environ, 'CYGNUS_DEV_API_TARGET': 'http://127.0.0.1:8017'}
    # Popen uses an argv list and a fixed executable. No shell interpolation.
    frontend = subprocess.Popen([shutil.which('node'), str(ROOT / 'frontend/node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '5177', '--strictPort'], cwd=ROOT / 'frontend', env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    try:
        wait_url('http://127.0.0.1:8017/api/health')
        wait_url('http://127.0.0.1:5177/', frontend)
        with sync_playwright() as playwright:
            edge = Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
            browser = playwright.chromium.launch(executable_path=str(edge) if edge.exists() else None, headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto('http://localhost:5177/#/register')
            page.get_by_label('Name', exact=True).fill('Browser Importer')
            page.get_by_label('Email', exact=True).fill('browser-import@example.com')
            page.locator('#account-password').fill('browser only long passphrase')
            page.get_by_role('button', name='Create account', exact=True).click()
            expect(page).to_have_url('http://localhost:5177/#/overview')
            page.goto('http://localhost:5177/#/orders')
            expect(page.get_by_role('heading', name='Import Amazon orders', exact=True)).to_be_visible()
            expect(page.get_by_text('Not connected', exact=True)).to_be_visible()
            data = archive([('nested/orders.json', payload(record()))])
            file = {'name': 'orders.zip', 'mimeType': 'application/zip', 'buffer': data}
            page.get_by_label('Amazon order file', exact=True).set_input_files(file)
            expect(page.get_by_role('heading', name='Your import preview')).to_be_visible()
            with connect() as conn:
                assert conn.execute('SELECT COUNT(*) FROM orders WHERE simulated=0').fetchone()[0] == 0
            page.get_by_role('button', name='Confirm import (1)', exact=True).click()
            expect(page.get_by_text('Import complete: 1 new orders, 0 duplicates skipped, 0 excluded records.')).to_be_visible()
            page.get_by_role('button', name='Close preview', exact=True).click()
            expect(page.get_by_text('123-1234567-1234567', exact=True)).to_be_visible()
            expect(page.get_by_text('Not verified — check Amazon', exact=True)).to_be_visible()
            page.get_by_label('Amazon order file', exact=True).set_input_files(file)
            expect(page.get_by_text('Already imported — add provenance and skip creating another order.')).to_be_visible()
            page.get_by_role('button', name='Confirm import (1)', exact=True).click()
            expect(page.get_by_text('Import complete: 0 new orders, 1 duplicates skipped, 0 excluded records.')).to_be_visible()
            page.get_by_role('button', name='Close preview', exact=True).click()
            page.get_by_label('Amazon order file', exact=True).set_input_files({'name': 'bad.json', 'mimeType': 'application/json', 'buffer': b'{broken'})
            expect(page.get_by_text('Malformed JSON/CSV or invalid encoding; only strict UTF-8 data is supported.')).to_be_visible()
            for width in (1440, 1280, 768, 390):
                page.set_viewport_size({'width': width, 'height': 1000})
                page.evaluate('window.scrollTo(0,0)')
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), f'Overflow at {width}'
                page.screenshot(path=str(tmp_path / f'orders-{width}.png'), full_page=True)
            print('Browser screenshots:', tmp_path)
            page.get_by_role('button', name='Connect Gmail with Google', exact=True).click()
            expect(page.get_by_text('Gmail requires a server-managed encryption key')).to_be_visible()
            assert not errors, errors
            browser.close()
        with connect() as conn:
            assert conn.execute('SELECT COUNT(*) FROM orders WHERE simulated=0').fetchone()[0] == 1
            assert conn.execute('SELECT COUNT(*) FROM import_history').fetchone()[0] == 2
    finally:
        frontend.terminate()
        frontend.wait(timeout=15)
        server.should_exit = True
        thread.join(timeout=15)
        assert hashlib.sha256(live.read_bytes()).hexdigest() == original_hash

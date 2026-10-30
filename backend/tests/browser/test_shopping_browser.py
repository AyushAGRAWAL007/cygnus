"""Shopping UI flow against a synthetic isolated database and owned dev servers."""
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import threading

import pytest
import uvicorn

from app import main, returns
from app.config import get_settings
from tests.test_amazon_import import payload, record
from tests.browser.test_import_browser import wait_url

pytestmark = pytest.mark.skipif(os.environ.get('CYGNUS_BROWSER_TESTS') != '1', reason='Opt-in real-browser tests')
ROOT = Path(__file__).resolve().parents[3]


def test_shopping_empty_errors_import_refund_and_analytics(tmp_path, monkeypatch):
    from playwright.sync_api import sync_playwright, expect
    settings = get_settings()
    monkeypatch.setattr(settings, 'database_path', str(tmp_path / 'shopping-browser.db'))
    monkeypatch.setattr(settings, 'app_env', 'test')
    monkeypatch.setattr(settings, 'auth_trusted_origins', 'http://localhost:5178')
    monkeypatch.setattr(settings, 'cors_origins', 'http://localhost:5178')
    monkeypatch.setattr(settings, 'google_client_id', None)
    monkeypatch.setattr(settings, 'integration_encryption_key', None)
    monkeypatch.setattr(settings, 'nvidia_api_key', None)
    monkeypatch.setattr(settings, 'nebius_api_key', None)
    returns.initialize()
    for name in ('001_customer_ownership.py', '002_order_imports.py', '003_shopping_dashboard.py'):
        runpy.run_path(str(ROOT / 'backend/migrations' / name))['migrate'](settings.database_path)
    main.auth.limiter.reset()
    server = uvicorn.Server(uvicorn.Config(main.app, host='127.0.0.1', port=8018, log_level='error', access_log=False))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    frontend = subprocess.Popen([shutil.which('node'), str(ROOT / 'frontend/node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '5178', '--strictPort'], cwd=ROOT / 'frontend', env={**os.environ, 'CYGNUS_DEV_API_TARGET': 'http://127.0.0.1:8018'}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    try:
        wait_url('http://127.0.0.1:8018/api/health')
        wait_url('http://127.0.0.1:5178/', frontend)
        with sync_playwright() as pw:
            edge = Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
            browser = pw.chromium.launch(executable_path=str(edge) if edge.exists() else None, headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 1000})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto('http://localhost:5178/#/register')
            page.get_by_label('Name', exact=True).fill('Shopping test')
            page.get_by_label('Email', exact=True).fill('shopping-browser@example.com')
            page.locator('#account-password').fill('eight888')
            page.get_by_role('button', name='Create account', exact=True).click()
            expect(page.get_by_text('No real purchases recorded yet.', exact=False)).to_be_visible()
            metrics = page.get_by_role('region', name='Real shopping metrics')
            expect(metrics.locator('dt', has_text='Total Orders').locator('..').locator('dd')).to_have_text('0')
            page.route('**/api/shopping/overview', lambda route: route.fulfill(status=503, json={'detail': 'Shopping metrics unavailable for test'}))
            page.reload()
            expect(page.get_by_text('Shopping metrics unavailable for test', exact=True)).to_be_visible()
            expect(page.get_by_role('region', name='Real shopping metrics')).to_have_count(0)
            page.unroute('**/api/shopping/overview')
            page.goto('http://localhost:5178/#/orders')
            page.get_by_label('Amazon order file', exact=True).set_input_files({'name':'shopping.json', 'mimeType':'application/json', 'buffer':payload(record(total_amount='2599.00', payment_status='paid'))})
            expect(page.get_by_role('heading', name='Your import preview')).to_be_visible()
            page.get_by_role('button', name='Confirm import (1)', exact=True).click()
            expect(page.get_by_text('Import complete: 1 new orders, 0 duplicates skipped, 0 excluded records.')).to_be_visible()
            page.get_by_role('button', name='Close preview', exact=True).click()
            page.get_by_label('Search orders', exact=True).fill('123-1234567-1234567')
            expect(page.get_by_role('link', name='View order and refunds')).to_have_count(1)
            page.get_by_role('link', name='View order and refunds').click()
            expect(page.get_by_text('INR 2599.00', exact=True).first).to_be_visible()
            page.get_by_label('Refund amount', exact=True).fill('100.00')
            page.get_by_label('Refund date', exact=True).fill('2026-10-30')
            page.get_by_label('Refund reference', exact=True).fill('synthetic-refund-1')
            page.get_by_role('button', name='Save refund record').click()
            expect(page.get_by_text('synthetic-refund-1', exact=False).first).to_be_visible()
            page.goto('http://localhost:5178/#/overview')
            metrics = page.get_by_role('region', name='Real shopping metrics')
            expect(metrics.locator('dt', has_text='Net Shopping Spend').locator('..').locator('dd')).to_have_text('INR 2599.00')
            expect(metrics.locator('dt', has_text='Pending Refunds').locator('..').locator('dd')).to_have_text('INR 100.00')
            page.goto('http://localhost:5178/#/orders')
            page.get_by_label('Search orders', exact=True).fill('123-1234567-1234567')
            page.get_by_role('link', name='View order and refunds').click()
            page.get_by_role('button', name='Edit', exact=True).click()
            page.get_by_label('Refund status', exact=True).select_option('received')
            page.get_by_role('checkbox', name=re.compile('I confirm')).check()
            page.get_by_role('button', name='Save refund record').click()
            expect(page.get_by_text('received', exact=False).first).to_be_visible()
            page.goto('http://localhost:5178/#/overview')
            metrics = page.get_by_role('region', name='Real shopping metrics')
            expect(metrics.locator('dt', has_text='Net Shopping Spend').locator('..').locator('dd')).to_have_text('INR 2499.00')
            page.goto('http://localhost:5178/#/analytics')
            expect(page.get_by_role('heading', name='Monthly expenditure')).to_be_visible()
            expect(page.get_by_role('table', name='Monthly expenditure data')).to_contain_text('2599.00')
            for route in ('orders', 'analytics', 'retailers'):
                page.goto(f'http://localhost:5178/#/{route}')
                for width in (1440, 768, 390):
                    page.set_viewport_size({'width':width, 'height':1000})
                    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), (route,width)
            assert not errors, errors
            browser.close()
    finally:
        frontend.terminate()
        frontend.wait(timeout=15)
        server.should_exit = True
        thread.join(timeout=15)

import os
import pytest
from fastapi.testclient import TestClient
from db import init_db
# initialize DB before importing server so tables exist
init_db()

def test_health(client):
    r = client.get('/health')
    assert r.status_code == 200
    assert r.json().get('status') == 'ok'

def test_generate_license_and_list(client):
    # token workaround: call token endpoint
    tok = client.post('/auth/token', json={'username':'admin','password':'x'}).json()
    headers = {'Authorization': f"Bearer {tok['access_token']}"}
    r = client.post('/admin/licenses/generate', json={'pkg':'test'}, headers=headers)
    assert r.status_code == 200
    key = r.json().get('key')
    assert key
    r2 = client.get('/admin/licenses', headers=headers)
    assert r2.status_code == 200

def test_license_signature_and_validate(client):
    tok = client.post('/auth/token', json={'username':'admin','password':'x'}).json()
    headers = {'Authorization': f"Bearer {tok['access_token']}"}
    r = client.post('/admin/licenses/generate', json={'pkg':'test'}, headers=headers)
    key = r.json().get('key')
    sig = r.json().get('signature')
    assert key and sig
    rv = client.post('/licenses/validate', json={'key':key,'device_id':'dev-1','signature':sig})
    # device not registered yet, should be false but accepted signature
    assert rv.status_code == 200


def test_admin_login_cookie_security(client):
    os.environ['AA_COOKIE_SECURE'] = '1'
    os.environ['AA_COOKIE_SAMESITE'] = 'Lax'
    # simulate admin form login and inspect the direct response cookie
    r = client.post('/admin/login', data={'username':'admin', 'password':'x'}, follow_redirects=False)
    assert r.status_code == 302
    cookie = r.headers.get('set-cookie', '')
    assert 'httponly' in cookie.lower()
    assert 'secure' in cookie.lower()
    assert 'samesite=lax' in cookie.lower()


def test_admin_login_with_cookie(client):
    # verify login cookie allows access to the dashboard
    os.environ['AA_COOKIE_SECURE'] = '0'
    os.environ['AA_COOKIE_SAMESITE'] = 'Lax'
    r = client.post('/admin/login', data={'username':'admin', 'password':'x'}, follow_redirects=True)
    assert r.status_code == 200
    assert '/admin/dashboard' in str(r.url)
    assert 'Alpha Automation Dashboard' in r.text

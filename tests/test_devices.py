import pytest
from db import init_db
# initialize DB before importing server so tables exist
init_db()

def test_register_device_and_heartbeat(client):
    tok = client.post('/auth/token', json={'username':'admin','password':'x'}).json()
    headers = {'Authorization': f"Bearer {tok['access_token']}"}
    # generate license
    r = client.post('/admin/licenses/generate', json={'pkg':'test'}, headers=headers)
    assert r.status_code == 200
    key = r.json().get('key')
    sig = r.json().get('signature')
    assert key and sig
    # register device
    rv = client.post('/devices/register', json={'device_id':'dev-123','key':key}, headers=headers)
    assert rv.status_code == 200
    # heartbeat
    hb = client.post('/devices/heartbeat', json={'device_id':'dev-123'})
    assert hb.status_code == 200
    data = hb.json()
    assert data.get('device_id') == 'dev-123'

def test_schedule_publish_endpoint(client):
    tok = client.post('/auth/token', json={'username':'admin','password':'x'}).json()
    headers = {'Authorization': f"Bearer {tok['access_token']}"}
    import datetime
    run_at = (datetime.datetime.utcnow() + datetime.timedelta(seconds=5)).isoformat()
    r = client.post('/schedule/publish', json={'run_at': run_at, 'payload': 'test-payload'}, headers=headers)
    assert r.status_code == 200
    assert 'job_id' in r.json()

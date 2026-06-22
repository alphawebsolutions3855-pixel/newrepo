import pytest
from db import init_db
# initialize DB before importing server so tables exist
init_db()

def test_report_error_and_heal(client):
    tok = client.post('/auth/token', json={'username':'admin','password':'x'}).json()
    headers = {'Authorization': f"Bearer {tok['access_token']}"}
    r = client.post('/errors/report', json={'selector':'input.foo','error':'no such element'}, headers=headers)
    assert r.status_code == 200
    # list handlers to confirm created
    r2 = client.get('/handlers/list', headers=headers)
    assert r2.status_code == 200
    data = r2.json()
    assert 'handlers' in data

import os
from db import init_db
# initialize DB before importing server so tables exist
init_db()

def test_ui_bulk_create_dry_run(client):
    # ensure dry-run mode
    os.environ['AA_DRY_RUN'] = '1'
    tok = client.post('/auth/token', json={'username':'admin','password':'x'}).json()
    headers = {'Authorization': f"Bearer {tok['access_token']}"}
    body = {'page_url':'https://facebook.com/testpage','listings':[{'message':'hello'}], 'hold': True}
    r = client.post('/facebook/ui/bulk_create', json=body, headers=headers)
    assert r.status_code == 200
    assert r.json().get('status') in ('dry','done')

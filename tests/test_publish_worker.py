from db import init_db
# initialize DB before importing server so tables exist
init_db()
from models import FBBatch, FBPostItem
from db import get_session
from sqlmodel import select

def test_publish_worker_run_once(client):
    tok = client.post('/auth/token', json={'username':'admin','password':'x'}).json()
    headers = {'Authorization': f"Bearer {tok['access_token']}"}
    # prepare a batch via API
    r = client.post('/facebook/prepare_batch', json={'name':'t1','items':[{'message':'hi'}]}, headers=headers)
    assert r.status_code == 200
    batch_id = r.json().get('batch_id')
    # run worker once
    rv = client.post('/worker/run_once', headers=headers)
    assert rv.status_code == 200
    # check batch marked fired
    with get_session() as s:
        b = s.get(FBBatch, batch_id)
        assert b.fired is True


def test_publish_worker_retries_on_failure(client):
    # simulate failures
    import fb_client
    fb_client.SIMULATE_FAILURES = True
    tok = client.post('/auth/token', json={'username':'admin','password':'x'}).json()
    headers = {'Authorization': f"Bearer {tok['access_token']}"}
    # prepare a batch with a failing item
    r = client.post('/facebook/prepare_batch', json={'name':'t_fail','items':[{'message':'please fail'}]}, headers=headers)
    assert r.status_code == 200
    batch_id = r.json().get('batch_id')
    rv = client.post('/worker/run_once', headers=headers)
    assert rv.status_code == 200
    # check item retry_count incremented
    with get_session() as s:
        items = s.exec(select(FBPostItem).where(FBPostItem.batch_id == batch_id)).all()
        assert items and items[0].retry_count >= 1

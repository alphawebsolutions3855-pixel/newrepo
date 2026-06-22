import os
from db import init_db

# initialize DB before importing server so tables exist
init_db()


def test_list_posts_and_drafts_and_ai_generation(client):
    tok = client.post('/auth/token', json={'username': 'admin', 'password': 'x'}).json()
    headers = {'Authorization': f"Bearer {tok['access_token']}"}

    # create a draft and list drafts
    r = client.post('/drafts/save', json={'title': 'Draft 1', 'body': 'Draft body', 'account_type': 'old'}, headers=headers)
    assert r.status_code == 200
    draft_id = r.json().get('draft_id')
    assert draft_id

    r2 = client.get('/drafts/list', headers=headers)
    assert r2.status_code == 200
    assert any(d['id'] == draft_id for d in r2.json().get('drafts', []))

    # publish draft and list posts
    r3 = client.post('/drafts/publish', json={'ids': [draft_id]}, headers=headers)
    assert r3.status_code == 200
    assert r3.json().get('published')

    r4 = client.get('/posts/list', headers=headers)
    assert r4.status_code == 200
    assert len(r4.json().get('posts', [])) >= 1

    # AI generation endpoint
    r5 = client.post('/ai/generate', json={'prompt': 'Test prompt', 'style': 'friendly'}, headers=headers)
    assert r5.status_code == 200
    assert r5.json().get('source') == 'local-ai'
    assert 'content' in r5.json()

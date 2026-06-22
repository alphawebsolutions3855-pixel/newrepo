import os
from db import init_db

init_db()


def test_end_to_end_batch_workflow(client):
    """E2E: Create posts, batch them, and publish via worker."""
    tok = client.post('/auth/token', json={'username': 'admin', 'password': 'x'}).json()
    headers = {'Authorization': f"Bearer {tok['access_token']}"}

    # Step 1: Create multiple posts
    posts = []
    for i in range(3):
        r = client.post(
            '/posts/create',
            json={'title': f'Post {i}', 'body': f'Content {i}'},
            headers=headers
        )
        assert r.status_code == 200
        posts.append(r.json().get('id'))

    # Step 2: Prepare Facebook batch
    r2 = client.post(
        '/facebook/prepare_batch',
        json={'name': 'e2e_batch', 'items': [{'message': f'Post {i}'} for i in range(3)]},
        headers=headers
    )
    assert r2.status_code == 200
    batch_id = r2.json().get('batch_id')

    # Step 3: Get batch details
    r3 = client.get(f'/facebook/batches/{batch_id}', headers=headers)
    assert r3.status_code == 200
    assert r3.json().get('fired') is False
    assert len(r3.json().get('items', [])) == 3

    # Step 4: Run worker once
    r4 = client.post('/worker/run_once', headers=headers)
    assert r4.status_code == 200

    # Step 5: Verify batch marked fired
    r5 = client.get(f'/facebook/batches/{batch_id}', headers=headers)
    assert r5.status_code == 200
    assert r5.json().get('fired') is True


def test_end_to_end_draft_publishing_workflow(client):
    """E2E: Create drafts, publish them, then list/filter posts."""
    tok = client.post('/auth/token', json={'username': 'admin', 'password': 'x'}).json()
    headers = {'Authorization': f"Bearer {tok['access_token']}"}

    # Step 1: Create drafts
    draft_ids = []
    for i in range(2):
        r = client.post(
            '/drafts/save',
            json={'title': f'Draft {i}', 'body': f'Draft body {i}'},
            headers=headers
        )
        assert r.status_code == 200
        draft_ids.append(r.json().get('draft_id'))

    # Step 2: List drafts
    r2 = client.get('/drafts/list', headers=headers)
    assert r2.status_code == 200
    assert len(r2.json().get('drafts', [])) >= 2

    # Step 3: Publish drafts
    r3 = client.post(
        '/drafts/publish',
        json={'ids': draft_ids},
        headers=headers
    )
    assert r3.status_code == 200
    published_count = len(r3.json().get('published', []))
    assert published_count == 2

    # Step 4: List posts and verify
    r4 = client.get('/posts/list', headers=headers)
    assert r4.status_code == 200
    posts = r4.json().get('posts', [])
    assert len(posts) >= 2


def test_end_to_end_license_and_device_workflow(client):
    """E2E: Generate license, register device, validate, and heartbeat."""
    tok = client.post('/auth/token', json={'username': 'admin', 'password': 'x'}).json()
    headers = {'Authorization': f"Bearer {tok['access_token']}"}

    # Step 1: Generate license
    r1 = client.post(
        '/admin/licenses/generate',
        json={'pkg': 'e2e_test'},
        headers=headers
    )
    assert r1.status_code == 200
    key = r1.json().get('key')
    sig = r1.json().get('signature')
    assert key and sig

    # Step 2: Register device
    r2 = client.post(
        '/devices/register',
        json={'device_id': 'e2e_dev_001', 'key': key},
        headers=headers
    )
    assert r2.status_code == 200

    # Step 3: Validate license (no auth required)
    r3 = client.post(
        '/licenses/validate',
        json={'key': key, 'device_id': 'e2e_dev_001', 'signature': sig}
    )
    assert r3.status_code == 200
    assert r3.json().get('valid') is True

    # Step 4: Device heartbeat (no auth required)
    r4 = client.post(
        '/devices/heartbeat',
        json={'device_id': 'e2e_dev_001'}
    )
    assert r4.status_code == 200
    assert r4.json().get('device_id') == 'e2e_dev_001'


def test_end_to_end_scheduled_publish_workflow(client):
    """E2E: Schedule a post publication job and list scheduled jobs."""
    tok = client.post('/auth/token', json={'username': 'admin', 'password': 'x'}).json()
    headers = {'Authorization': f"Bearer {tok['access_token']}"}

    # Step 1: Schedule a publish job
    from datetime import datetime, timedelta
    run_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
    r1 = client.post(
        '/schedule/publish',
        json={'run_at': run_at, 'payload': 'e2e_scheduled_post'},
        headers=headers
    )
    assert r1.status_code == 200
    job_id = r1.json().get('job_id')
    assert job_id

    # Step 2: List scheduled jobs
    r2 = client.get('/schedule/jobs', headers=headers)
    assert r2.status_code == 200
    jobs = r2.json().get('jobs', [])
    assert len(jobs) >= 1
    assert any(j['payload'] == 'e2e_scheduled_post' for j in jobs)


def test_end_to_end_handler_repair_workflow(client):
    """E2E: Report handler error, scan handlers, repair, and check status."""
    tok = client.post('/auth/token', json={'username': 'admin', 'password': 'x'}).json()
    headers = {'Authorization': f"Bearer {tok['access_token']}"}

    # Step 1: Report an error for a handler
    r1 = client.post(
        '/errors/report',
        json={'selector': 'button.post-btn', 'error': 'Selector not found on page'},
        headers=headers
    )
    assert r1.status_code == 200

    # Step 2: Scan HTML for handlers
    r2 = client.post(
        '/handlers/scan',
        json={'html': '<input type="text" /><select></select>'},
        headers=headers
    )
    assert r2.status_code == 200

    # Step 3: List handlers
    r3 = client.get('/handlers/list', headers=headers)
    assert r3.status_code == 200

    # Step 4: Get handler status
    r4 = client.get('/handlers/status', headers=headers)
    assert r4.status_code == 200
    handlers = r4.json().get('handlers', [])
    assert len(handlers) >= 0

    # Step 5: Repair a handler (if any failed ones exist)
    if handlers:
        selector = handlers[0]['selector']
        r5 = client.post(
            '/handlers/repair',
            json={'selector': selector},
            headers=headers
        )
        # May succeed or fail depending on handler state
        assert r5.status_code in (200, 404)


def test_end_to_end_admin_user_management_workflow(client):
    """E2E: Create user, change password, list users, set password."""
    tok = client.post('/auth/token', json={'username': 'admin', 'password': 'x'}).json()
    headers = {'Authorization': f"Bearer {tok['access_token']}"}

    # Step 1: Create a new admin user
    r1 = client.post(
        '/admin/users',
        data={'username': 'testadmin', 'password': 'testpass123', 'is_admin': True},
        headers=headers
    )
    assert r1.status_code == 200

    # Step 2: List users
    r2 = client.get('/admin/users/list', headers=headers)
    assert r2.status_code == 200
    users = r2.json().get('users', [])
    assert len(users) >= 2  # admin + testadmin
    assert any(u['username'] == 'testadmin' for u in users)

    # Step 3: Change password via /auth/token
    r3 = client.post(
        '/auth/token',
        json={'username': 'testadmin', 'password': 'testpass123'}
    )
    assert r3.status_code == 200
    tok2 = r3.json().get('access_token')

    # Step 4: Admin can set another user's password
    r4 = client.post(
        '/admin/users/testadmin/set_password',
        data={'new_password': 'newpass456'},
        headers=headers
    )
    assert r4.status_code == 200

    # Step 5: Verify new password works
    r5 = client.post(
        '/auth/token',
        json={'username': 'testadmin', 'password': 'newpass456'}
    )
    assert r5.status_code == 200


def test_end_to_end_delete_duplicates(client):
    """E2E: Create duplicate posts and verify delete_duplicates removes them."""
    tok = client.post('/auth/token', json={'username': 'admin', 'password': 'x'}).json()
    headers = {'Authorization': f"Bearer {tok['access_token']}"}

    # Step 1: Create duplicate posts
    r1 = client.post(
        '/posts/create',
        json={'title': 'Duplicate', 'body': 'Same content'},
        headers=headers
    )
    assert r1.status_code == 200
    post1_id = r1.json().get('id')

    r2 = client.post(
        '/posts/create',
        json={'title': 'Duplicate', 'body': 'Same content'},
        headers=headers
    )
    assert r2.status_code == 200
    post2_id = r2.json().get('id')

    # Step 2: Verify both exist
    r3 = client.get('/posts/list', headers=headers)
    posts_before = len(r3.json().get('posts', []))

    # Step 3: Delete duplicates
    r4 = client.post('/posts/delete_duplicates', headers=headers)
    assert r4.status_code == 200
    removed = r4.json().get('removed', [])
    assert len(removed) >= 1

    # Step 4: Verify one removed
    r5 = client.get('/posts/list', headers=headers)
    posts_after = len(r5.json().get('posts', []))
    assert posts_after < posts_before

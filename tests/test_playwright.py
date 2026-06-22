import os
import pytest
from db import init_db

init_db()

# Test Playwright automation wrapper functions
DRY_RUN = os.environ.get('AA_DRY_RUN', '1') == '1'


def test_fb_automator_login_dry_run():
    """Test Facebook login in dry-run mode."""
    os.environ['AA_DRY_RUN'] = '1'
    from fb_automator import FBAutomator
    automator = FBAutomator(headless=True)
    automator.start()
    result = automator.login('test@example.com', 'password')
    automator.stop()
    assert result is True


def test_fb_automator_bulk_create_dry_run():
    """Test bulk create posts in dry-run mode."""
    os.environ['AA_DRY_RUN'] = '1'
    from fb_automator import bulk_create
    result = bulk_create('https://facebook.com/testpage', [{'message': 'Test post'}], hold_publish=True)
    assert result.get('status') in ('dry', 'done')


def test_fb_automator_create_post_dry_run():
    """Test single post creation in dry-run mode."""
    os.environ['AA_DRY_RUN'] = '1'
    from fb_automator import create_post
    result = create_post('https://facebook.com/testpage', 'Test message')
    assert result.get('status') in ('dry', 'posted')


def test_endpoint_requires_auth_for_posts(client):
    """Verify protected endpoints reject unauthenticated requests."""
    # Try to access /posts/create without token
    r = client.post(
        '/posts/create',
        json={'title': 'Unauthorized', 'body': 'Should fail'}
    )
    assert r.status_code == 403 or r.status_code == 401


def test_endpoint_requires_auth_for_batches(client):
    """Verify batch endpoints require auth."""
    r = client.post(
        '/facebook/prepare_batch',
        json={'name': 'batch', 'items': []}
    )
    assert r.status_code == 403 or r.status_code == 401


def test_endpoint_requires_auth_for_admin(client):
    """Verify admin endpoints require auth."""
    r = client.post(
        '/admin/users',
        data={'username': 'test', 'password': 'test'}
    )
    assert r.status_code == 403 or r.status_code == 401

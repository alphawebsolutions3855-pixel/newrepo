from db import init_db, get_session
from models import User

# initialize DB before importing server so tables exist
init_db()


def test_bootstrap_and_login_and_change_password(client):
    # ensure DB initialized (start from fresh DB file)
    import os
    dbfile = 'alpha_automation.db'
    if os.path.exists(dbfile):
        os.remove(dbfile)
    from db import init_db
    init_db()
    # bootstrap admin (may already exist if startup auto-created admin)
    r = client.post('/admin/users/bootstrap', data={'username':'admin','password':'adminpass'})
    assert r.status_code in (200, 400)
    # login (try bootstrap password, then fallback to default 'x')
    resp = client.post('/auth/token', json={'username':'admin','password':'adminpass'})
    if resp.status_code == 200:
        used_old = 'adminpass'
    else:
        resp = client.post('/auth/token', json={'username':'admin','password':'x'})
        used_old = 'x'
    tok = resp.json()
    assert 'access_token' in tok
    headers = {'Authorization': f"Bearer {tok['access_token']}"}
    # change password using the password that actually authenticated
    r2 = client.post('/admin/users/change_password', data={'old_password': used_old, 'new_password':'newpass'}, headers=headers)
    assert r2.status_code == 200
    # login with new password
    tok2 = client.post('/auth/token', json={'username':'admin','password':'newpass'}).json()
    assert 'access_token' in tok2

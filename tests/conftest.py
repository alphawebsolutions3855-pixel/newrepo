import os
import pytest

# Use a temporary SQLite file for tests to avoid in-memory connection isolation
os.environ['AA_DATABASE_URL'] = 'sqlite:///./test_alpha.db'
# Ensure deterministic admin creation during tests
os.environ['AA_SECRET'] = 'test-secret'
os.environ['AA_ADMIN_PASSWORD'] = 'x'
# disable server auto-create to let tests control bootstrap explicitly
os.environ['AA_AUTO_CREATE_ADMIN'] = '0'
try:
    if os.path.exists('./test_alpha.db'):
        os.remove('./test_alpha.db')
except Exception:
    pass

from db import init_db, get_session
from models import User
from auth import get_password_hash
from sqlmodel import select


@pytest.fixture(scope='session', autouse=True)
def setup_db():
    init_db()
    # create default admin if missing
    with get_session() as s:
        any_user = s.exec(select(User)).first()
        if not any_user:
            u = User(username='admin', hashed_password=get_password_hash('x'), is_admin=True)
            s.add(u)
            s.commit()
    yield


@pytest.fixture(scope='module')
def client():
    # import app after DB and env are configured
    from fastapi.testclient import TestClient
    from server import app
    with TestClient(app) as c:
        yield c
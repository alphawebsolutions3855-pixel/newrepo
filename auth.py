from datetime import datetime, timedelta
import os
import warnings
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select
from db import get_session
from models import User

def load_secret_key() -> str:
    secret = os.environ.get('AA_SECRET')
    if not secret:
        secret_file = os.environ.get('AA_SECRET_FILE')
        if secret_file and os.path.exists(secret_file):
            with open(secret_file, 'r') as f:
                secret = f.read().strip()
    if not secret:
        # For local development make it easy to start the server without an external secret.
        # Default to allowing an insecure secret unless explicitly disabled by the environment.
        allow_insecure = os.environ.get('AA_ALLOW_INSECURE_SECRET', '1').lower() in ('1', 'true', 'yes')
        if allow_insecure or os.environ.get('PYTEST_CURRENT_TEST'):
            warnings.warn('AA_SECRET not set; using insecure default for testing/dev only. Set AA_SECRET or AA_SECRET_FILE in production.')
            secret = 'change-me-please'
        else:
            raise RuntimeError('AA_SECRET or AA_SECRET_FILE must be set')
    return secret

SECRET_KEY = load_secret_key()
ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(request: Request, token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    # token may come from Authorization header (oauth2_scheme) or from cookie `aa_token`
    used_token = token
    if not used_token:
        used_token = request.cookies.get('aa_token')
    if not used_token:
        raise credentials_exception
    try:
        payload = jwt.decode(used_token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    from sqlalchemy.exc import OperationalError
    try:
        with get_session() as s:
            statement = select(User).where(User.username == username)
            user = s.exec(statement).first()
            if not user:
                raise credentials_exception
            return user
    except OperationalError:
        try:
            from server import init_db
            init_db()
            with get_session() as s:
                statement = select(User).where(User.username == username)
                user = s.exec(statement).first()
                if not user:
                    raise credentials_exception
                return user
        except Exception:
            raise credentials_exception

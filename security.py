import hmac
import hashlib
import os

from auth import load_secret_key

SECRET = load_secret_key()

def sign_value(value: str) -> str:
    return hmac.new(SECRET.encode(), value.encode(), hashlib.sha256).hexdigest()

def verify_signed(value: str, signature: str) -> bool:
    expected = sign_value(value)
    return hmac.compare_digest(expected, signature)

def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

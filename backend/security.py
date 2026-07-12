import hashlib
import hmac
import secrets
from datetime import datetime, timedelta


def verify_password(password, stored_hash):
    if not password or not stored_hash:
        return False
    try:
        algorithm, iterations, salt, digest = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            str(password).encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        ).hex()
        return hmac.compare_digest(candidate, digest)
    except Exception:
        return False


def password_hash(password):
    salt = secrets.token_hex(16)
    iterations = 260000
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        str(password).encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def new_token():
    return secrets.token_urlsafe(32)


def expires_at(minutes):
    return datetime.now() + timedelta(minutes=minutes)


def is_expired(value):
    return bool(value and datetime.now() > value)

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from .db import now, transaction


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("A senha precisa ter pelo menos 12 caracteres")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        _, n, r, p, salt_hex, expected_hex = encoded.split("$")
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex),
                                n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(digest, bytes.fromhex(expected_hex))
    except (ValueError, TypeError):
        return False


def set_admin(conn, password: str) -> None:
    encoded = hash_password(password)
    with transaction(conn):
        conn.execute("INSERT INTO admin(id,password_hash,created_at) VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET password_hash=excluded.password_hash",
                     (encoded, now()))


def login(conn, password: str, remote_ip: str = "local") -> tuple[str, str] | None:
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    with transaction(conn):
        conn.execute("DELETE FROM login_attempt WHERE attempted_at<?", (cutoff,))
        failures = conn.execute("SELECT COUNT(*) FROM login_attempt WHERE remote_ip=?", (remote_ip,)).fetchone()[0]
        if failures >= 5:
            raise ValueError("Muitas tentativas de login; tente novamente em 15 minutos")
    row = conn.execute("SELECT password_hash FROM admin WHERE id=1").fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        with transaction(conn):
            conn.execute("INSERT INTO login_attempt(remote_ip,attempted_at) VALUES(?,?)", (remote_ip, now()))
        return None
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
    with transaction(conn):
        conn.execute("DELETE FROM session WHERE expires_at<?", (now(),))
        conn.execute("DELETE FROM login_attempt WHERE remote_ip=?", (remote_ip,))
        conn.execute("INSERT INTO session(token_hash,csrf_token,expires_at) VALUES(?,?,?)",
                     (hashlib.sha256(token.encode()).hexdigest(), csrf, expires))
    return token, csrf


def get_session(conn, token: str | None) -> dict | None:
    if not token:
        return None
    row = conn.execute("SELECT csrf_token,expires_at FROM session WHERE token_hash=?",
                       (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
    if not row or row["expires_at"] <= now():
        return None
    return dict(row)


def logout(conn, token: str | None) -> None:
    if token:
        with transaction(conn):
            conn.execute("DELETE FROM session WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))

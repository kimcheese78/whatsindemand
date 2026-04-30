"""Single-use, short-lived tokens for password reset, email verify, email change."""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from app.models import db, AuthToken


PURPOSE_PASSWORD_RESET = 'password_reset'
PURPOSE_EMAIL_VERIFY = 'email_verify'
PURPOSE_EMAIL_CHANGE = 'email_change'


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def issue(user_id: int, purpose: str, ttl: timedelta, payload: Optional[dict] = None) -> str:
    """Create a token, persist its hash, return the raw token to email out."""
    raw = secrets.token_urlsafe(32)
    token = AuthToken(
        user_id=user_id,
        token_hash=_hash(raw),
        purpose=purpose,
        payload=payload,
        expires_at=datetime.utcnow() + ttl,
    )
    db.session.add(token)
    db.session.commit()
    return raw


def consume(raw_token: str, purpose: str) -> Optional[AuthToken]:
    """Atomically consume a token. Returns the row if valid, else None."""
    if not raw_token:
        return None
    token = AuthToken.query.filter_by(token_hash=_hash(raw_token), purpose=purpose).first()
    if not token:
        return None
    if token.consumed_at is not None:
        return None
    if token.expires_at < datetime.utcnow():
        return None
    token.consumed_at = datetime.utcnow()
    db.session.commit()
    return token


def invalidate_all(user_id: int, purpose: str) -> None:
    """Invalidate every unconsumed token of a given purpose for a user."""
    AuthToken.query.filter_by(user_id=user_id, purpose=purpose, consumed_at=None).update(
        {'consumed_at': datetime.utcnow()}
    )
    db.session.commit()

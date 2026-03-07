import jwt
from datetime import datetime, timedelta
from uuid import uuid4
import bcrypt
from flask import current_app
from models import RevokedToken, db


def _coerce_user_id(user_id):
    if isinstance(user_id, str) and user_id.isdigit():
        return int(user_id)
    if isinstance(user_id, int):
        return user_id
    return None


def _coerce_timestamp_to_datetime(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.utcfromtimestamp(value)
    return None


def _build_user_revocation_jti(user_id):
    return f'user-revoke-{user_id}'


def generate_token(user_id, expires_seconds=None):
    token_ttl = int(expires_seconds or current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES', 32400))
    payload = {
        # PyJWT validates "sub" as a string in recent versions.
        'sub': str(user_id),
        'jti': uuid4().hex,
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(seconds=token_ttl)
    }
    token = jwt.encode(payload, current_app.config.get('JWT_SECRET_KEY'), algorithm='HS256')
    return token


def decode_token(token):
    try:
        payload = jwt.decode(token, current_app.config.get('JWT_SECRET_KEY'), algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def revoke_token(token):
    try:
        payload = jwt.decode(
            token,
            current_app.config.get('JWT_SECRET_KEY'),
            algorithms=['HS256'],
            options={'verify_exp': False}
        )
    except jwt.InvalidTokenError:
        return False

    jti = payload.get('jti')
    if not jti:
        return False

    existing = RevokedToken.query.filter_by(jti=jti).first()
    if existing:
        return True

    RevokedToken.query.filter(
        RevokedToken.expires_at.isnot(None),
        RevokedToken.expires_at < datetime.utcnow()
    ).delete(synchronize_session=False)

    user_id = _coerce_user_id(payload.get('sub'))

    exp_ts = payload.get('exp')
    expires_at = datetime.utcfromtimestamp(exp_ts) if exp_ts else None

    db.session.add(RevokedToken(jti=jti, user_id=user_id, expires_at=expires_at))
    db.session.commit()
    return True


def revoke_user_tokens(user_id):
    normalized_user_id = _coerce_user_id(user_id)
    if normalized_user_id is None:
        return False

    cutoff = datetime.utcnow()
    jti = _build_user_revocation_jti(normalized_user_id)
    existing = RevokedToken.query.filter_by(jti=jti).first()

    RevokedToken.query.filter(
        RevokedToken.expires_at.isnot(None),
        RevokedToken.expires_at < cutoff
    ).delete(synchronize_session=False)

    if existing:
        existing.user_id = normalized_user_id
        existing.revoked_at = cutoff
        existing.expires_at = None
    else:
        db.session.add(
            RevokedToken(
                jti=jti,
                user_id=normalized_user_id,
                revoked_at=cutoff,
                expires_at=None
            )
        )

    db.session.commit()
    return True


def is_token_revoked(payload):
    if not isinstance(payload, dict):
        return False

    jti = payload.get('jti')
    if not jti:
        return False

    if RevokedToken.query.filter_by(jti=jti).first() is not None:
        return True

    user_id = _coerce_user_id(payload.get('sub'))
    if user_id is None:
        return False

    user_revoke_marker = RevokedToken.query.filter_by(jti=_build_user_revocation_jti(user_id)).first()
    if not user_revoke_marker:
        return False

    issued_at = _coerce_timestamp_to_datetime(payload.get('iat'))
    if issued_at is None:
        return True

    return issued_at <= user_revoke_marker.revoked_at


def hash_password(password):
    if isinstance(password, str):
        password = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password, salt)
    return hashed.decode('utf-8')


def verify_password(password, hashed):
    if isinstance(password, str):
        password = password.encode('utf-8')
    if isinstance(hashed, str):
        hashed = hashed.encode('utf-8')
    return bcrypt.checkpw(password, hashed)

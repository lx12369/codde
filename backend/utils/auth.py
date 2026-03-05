import jwt
from datetime import datetime, timedelta
from uuid import uuid4
import bcrypt
from flask import current_app
from models import RevokedToken, db


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

    user_id = payload.get('sub')
    if isinstance(user_id, str) and user_id.isdigit():
        user_id = int(user_id)

    exp_ts = payload.get('exp')
    expires_at = datetime.utcfromtimestamp(exp_ts) if exp_ts else None

    db.session.add(RevokedToken(jti=jti, user_id=user_id, expires_at=expires_at))
    db.session.commit()
    return True


def is_token_revoked(payload):
    jti = payload.get('jti') if isinstance(payload, dict) else None
    if not jti:
        return False
    return RevokedToken.query.filter_by(jti=jti).first() is not None


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

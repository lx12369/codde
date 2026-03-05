from flask import Blueprint, current_app, g, request

from models import User, db
from utils import (
    error_response,
    generate_token,
    hash_password,
    revoke_token,
    success_response,
    token_required,
    verify_password
)
from utils.audit_log import write_log

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    if not data:
        return error_response('请求体不能为空', 400)

    username = str(data.get('username') or '').strip()
    password = data.get('password')
    remember_me = bool(data.get('rememberMe', False))

    if not username or not password:
        return error_response('用户名和密码为必填项', 400)

    user = User.query.filter_by(username=username).first()
    if not user:
        return error_response('用户名或密码错误', 401)

    if not verify_password(password, user.password_hash):
        return error_response('用户名或密码错误', 401)

    token_expires = (
        current_app.config.get('JWT_REMEMBER_TOKEN_EXPIRES', 604800)
        if remember_me
        else current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES', 32400)
    )
    token = generate_token(user.id, expires_seconds=token_expires)

    write_log('login', f'用户 {username} 登录成功', operator=username)
    db.session.commit()

    return success_response(
        {
            'token': token,
            'user': user.to_dict(),
            'expires_in': token_expires
        },
        '登录成功'
    )


@auth_bp.route('/password', methods=['PUT'])
@token_required
def change_password():
    user_id = getattr(g, 'current_user_id', None)
    current_user = User.query.get(user_id) if user_id is not None else None
    if not current_user:
        return error_response('用户不存在或未登录', 401)

    data = request.get_json()

    if not data:
        return error_response('请求体不能为空', 400)

    current_password = data.get('current_password')
    new_password = data.get('new_password')

    if not current_password or not new_password:
        return error_response('当前密码和新密码为必填项', 400)

    if not verify_password(current_password, current_user.password_hash):
        return error_response('当前密码错误', 400)

    if len(new_password) < 6:
        return error_response('新密码长度不能少于 6 位', 400)

    current_user.password_hash = hash_password(new_password)

    write_log(
        'password_change',
        f'用户 {current_user.username} 修改了密码',
        operator=current_user.username
    )
    db.session.commit()

    return success_response(None, '密码修改成功')


@auth_bp.route('/logout', methods=['POST'])
@token_required
def logout():
    token = getattr(g, 'current_token', None)
    if not token:
        return error_response('缺少身份令牌', 401)

    revoke_token(token)
    return success_response(None, '已退出登录')

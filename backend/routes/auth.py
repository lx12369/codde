from flask import Blueprint, request, jsonify
from utils import (
    generate_token,
    verify_password,
    hash_password,
    token_required,
    success_response,
    error_response
)
from models import db, User, Log

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    
    if not data:
        return error_response('请求体不能为空', 400)
    
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return error_response('用户名和密码为必填项', 400)
    
    user = User.query.filter_by(username=username).first()
    
    if not user:
        return error_response('用户名或密码错误', 401)
    
    if not verify_password(password, user.password_hash):
        return error_response('用户名或密码错误', 401)
    
    token = generate_token(user.id)
    
    log = Log(
        type='login',
        description=f'用户 {username} 登录成功',
        operator=username
    )
    db.session.add(log)
    db.session.commit()
    
    return success_response({
        'token': token,
        'user': user.to_dict()
    }, '登录成功')


@auth_bp.route('/password', methods=['PUT'])
@token_required
def change_password(current_user):
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
    
    log = Log(
        type='password_change',
        description=f'用户 {current_user.username} 修改了密码',
        operator=current_user.username
    )
    db.session.add(log)
    db.session.commit()
    
    return success_response(None, '密码修改成功')

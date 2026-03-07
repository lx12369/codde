from flask import Blueprint, g, request

from models.models import User, db
from utils import hash_password, revoke_user_tokens
from utils.audit_log import get_operator_name, write_log
from utils.decorators import token_required
from utils.roles import (
    ADMIN_ROLE,
    BUILTIN_ADMIN_USERNAME,
    STAFF_ROLE,
    SUPER_ADMIN_ROLE,
    is_admin,
    is_builtin_super_admin,
    is_super_admin
)
from utils.response import error_response, paginated_response, success_response

employees_bp = Blueprint('employees', __name__)

ALLOWED_ROLES = {ADMIN_ROLE, STAFF_ROLE, SUPER_ADMIN_ROLE}


def _normalize_role(value, fallback='staff'):
    if value is None:
        return fallback

    role = str(value).strip().lower()
    if not role:
        return fallback
    if role not in ALLOWED_ROLES:
        return None
    return role


def _get_current_user():
    user_id = getattr(g, 'current_user_id', None)
    if user_id is None:
        return None
    return User.query.get(user_id)


def _is_admin(user):
    return is_admin(user)


def _is_super_admin(user):
    return is_super_admin(user)


def _require_admin():
    current_user = _get_current_user()
    if not current_user:
        return None, error_response('用户不存在或未登录', 401)
    if not _is_admin(current_user):
        return None, error_response('仅管理员可执行该操作', 403)
    return current_user, None


@employees_bp.route('', methods=['GET'])
@token_required
def get_employees():
    current_user = _get_current_user()
    if not current_user:
        return error_response('用户不存在或未登录', 401)

    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', type=int)
    if page_size is None:
        page_size = request.args.get('pageSize', 10, type=int)
    search = request.args.get('search', '', type=str)

    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 10

    query = User.query
    if not _is_super_admin(current_user):
        query = query.filter(User.role != SUPER_ADMIN_ROLE)

    keyword = str(search or '').strip()
    if keyword:
        query = query.filter(User.username.ilike(f'%{keyword}%'))

    total = query.count()
    users = query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return paginated_response(
        items=[user.to_dict() for user in users],
        total=total,
        page=page,
        page_size=page_size
    )


@employees_bp.route('', methods=['POST'])
@token_required
def create_employee():
    current_user, permission_error = _require_admin()
    if permission_error:
        return permission_error

    data = request.get_json()
    if not data:
        return error_response('No data provided', 400)

    username = str(data.get('username') or '').strip()
    password = data.get('password')
    role = _normalize_role(data.get('role'), fallback='staff')

    if not username:
        return error_response('用户名不能为空', 400)
    if not password:
        return error_response('密码不能为空', 400)
    if len(str(password)) < 6:
        return error_response('密码长度不能少于 6 位', 400)
    if role is None:
        return error_response('角色仅支持 admin、staff 或 super_admin', 400)
    if role == SUPER_ADMIN_ROLE and not _is_super_admin(current_user):
        return error_response('仅超级管理员可创建超级管理员账号', 403)
    if User.query.filter_by(username=username).first():
        return error_response('用户名已存在', 409)

    user = User(
        username=username,
        password_hash=hash_password(password),
        role=role
    )
    db.session.add(user)

    operator = get_operator_name()
    write_log(
        'employee_create',
        f'创建员工账号：{username}（角色：{role}）',
        operator=operator
    )

    db.session.commit()

    return success_response(user.to_dict(), 'Employee created successfully', 201)


@employees_bp.route('/<int:user_id>', methods=['PUT'])
@token_required
def update_employee(user_id):
    current_user, permission_error = _require_admin()
    if permission_error:
        return permission_error

    target_user = User.query.get(user_id)
    if not target_user:
        return error_response('Employee not found', 404)
    if is_builtin_super_admin(target_user):
        return error_response('内置超级管理员账号不可在员工管理中修改', 403)
    if target_user.role == SUPER_ADMIN_ROLE and not _is_super_admin(current_user):
        return error_response('仅超级管理员可修改超级管理员账号', 403)

    data = request.get_json()
    if not data:
        return error_response('No data provided', 400)

    before_username = target_user.username
    before_role = target_user.role

    if 'username' in data:
        username = str(data.get('username') or '').strip()
        if not username:
            return error_response('用户名不能为空', 400)
        duplicated = User.query.filter(User.username == username, User.id != target_user.id).first()
        if duplicated:
            return error_response('用户名已存在', 409)
        target_user.username = username

    if 'role' in data:
        role = _normalize_role(data.get('role'), fallback=None)
        if role is None:
            return error_response('角色仅支持 admin、staff 或 super_admin', 400)
        if role == SUPER_ADMIN_ROLE and not _is_super_admin(current_user):
            return error_response('仅超级管理员可设置超级管理员角色', 403)
        target_user.role = role

    changes = []
    if before_username != target_user.username:
        changes.append(f'用户名：{before_username or "-"} -> {target_user.username or "-"}')
    if before_role != target_user.role:
        changes.append(f'角色：{before_role or "-"} -> {target_user.role or "-"}')

    if changes:
        operator = get_operator_name()
        write_log(
            'employee_update',
            f'更新员工账号：{target_user.username}（ID: {target_user.id}），变更：{"；".join(changes)}',
            operator=operator
        )

    db.session.commit()

    return success_response(target_user.to_dict(), 'Employee updated successfully')


@employees_bp.route('/<int:user_id>/reset-password', methods=['PUT'])
@token_required
def reset_employee_password(user_id):
    current_user, permission_error = _require_admin()
    if permission_error:
        return permission_error

    target_user = User.query.get(user_id)
    if not target_user:
        return error_response('Employee not found', 404)
    if target_user.id == current_user.id:
        return error_response('当前登录账号请通过右上角修改密码', 403)
    if is_builtin_super_admin(target_user):
        return error_response('内置超级管理员账号不可在员工管理中重置密码', 403)
    if target_user.role == SUPER_ADMIN_ROLE and not _is_super_admin(current_user):
        return error_response('仅超级管理员可重置超级管理员密码', 403)

    data = request.get_json()
    if not data:
        return error_response('No data provided', 400)

    new_password = data.get('new_password')
    if not new_password:
        return error_response('新密码不能为空', 400)
    if len(str(new_password)) < 6:
        return error_response('密码长度不能少于 6 位', 400)

    target_user.password_hash = hash_password(new_password)

    operator = get_operator_name()
    write_log(
        'employee_reset_password',
        f'重置员工密码：{target_user.username}（ID: {target_user.id}）',
        operator=operator
    )

    db.session.commit()
    revoke_user_tokens(target_user.id)

    return success_response(target_user.to_dict(), 'Password reset successfully')


@employees_bp.route('/<int:user_id>', methods=['DELETE'])
@token_required
def delete_employee(user_id):
    current_user, permission_error = _require_admin()
    if permission_error:
        return permission_error

    target_user = User.query.get(user_id)
    if not target_user:
        return error_response('Employee not found', 404)
    if target_user.id == current_user.id:
        return error_response('不能删除当前登录账号', 403)
    if str(target_user.username or '').strip().lower() == BUILTIN_ADMIN_USERNAME:
        return error_response('默认管理员账号不可删除', 403)
    if is_builtin_super_admin(target_user):
        return error_response('内置超级管理员账号不可删除', 403)
    if target_user.role == SUPER_ADMIN_ROLE and not _is_super_admin(current_user):
        return error_response('仅超级管理员可删除超级管理员账号', 403)

    username = target_user.username

    db.session.delete(target_user)

    operator = get_operator_name()
    write_log(
        'employee_delete',
        f'删除员工账号：{username}（ID: {user_id}）',
        operator=operator
    )

    db.session.commit()

    return success_response(message='Employee deleted successfully')

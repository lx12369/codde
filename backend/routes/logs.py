from flask import Blueprint, g, request

from models import Log, User, db
from utils.audit_log import (
    build_filter_options,
    enrich_log_data,
    get_action_types_map,
    get_module_types_map,
    parse_datetime_range
)
from utils.decorators import token_required
from utils.response import error_response, success_response

logs_bp = Blueprint('logs', __name__)

MODULE_TYPES_MAP = get_module_types_map()
ACTION_TYPES_MAP = get_action_types_map()
KNOWN_TYPES = sorted({log_type for types in MODULE_TYPES_MAP.values() for log_type in types})


def _require_admin():
    current_user_id = getattr(g, 'current_user_id', None)
    current_user = User.query.get(current_user_id) if current_user_id is not None else None

    if not current_user:
        return error_response('用户不存在或未登录', 401)

    if str(current_user.role or '').strip().lower() != 'admin':
        return error_response('仅管理员可执行该操作', 403)

    return None


def _apply_type_filter(query, selected, mapping):
    if not selected or selected == 'all':
        return query

    if selected == 'other':
        if not KNOWN_TYPES:
            return query
        return query.filter(db.or_(Log.type.is_(None), db.not_(Log.type.in_(KNOWN_TYPES))))

    matched_types = mapping.get(selected, [])
    if not matched_types:
        return query.filter(Log.id == -1)

    return query.filter(Log.type.in_(matched_types))


@logs_bp.route('', methods=['GET'])
@token_required
def get_logs():
    permission_error = _require_admin()
    if permission_error:
        return permission_error

    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 10, type=int)

    module = str(request.args.get('module', 'all') or 'all').strip()
    action = str(request.args.get('action', 'all') or 'all').strip()
    operator = str(request.args.get('operator', '') or '').strip()
    keyword = str(request.args.get('keyword', '') or '').strip()
    start_time = parse_datetime_range(request.args.get('start_time'), end_of_day=False)
    end_time = parse_datetime_range(request.args.get('end_time'), end_of_day=True)

    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 10
    elif page_size > 100:
        page_size = 100

    query = Log.query
    query = _apply_type_filter(query, module, MODULE_TYPES_MAP)
    query = _apply_type_filter(query, action, ACTION_TYPES_MAP)

    if operator:
        query = query.filter(Log.operator.ilike(f'%{operator}%'))

    if keyword:
        like_pattern = f'%{keyword}%'
        query = query.filter(
            db.or_(
                Log.description.ilike(like_pattern),
                Log.operator.ilike(like_pattern),
                Log.type.ilike(like_pattern)
            )
        )

    if start_time:
        query = query.filter(Log.timestamp >= start_time)
    if end_time:
        query = query.filter(Log.timestamp <= end_time)

    pagination = query.order_by(Log.timestamp.desc()).paginate(page=page, per_page=page_size, error_out=False)
    items = [enrich_log_data(item.to_dict()) for item in pagination.items]

    return success_response(
        {
            'items': items,
            'pagination': {
                'total': pagination.total,
                'page': page,
                'page_size': page_size,
                'total_pages': pagination.pages,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            },
            'filters': build_filter_options()
        }
    )

from flask import Blueprint, g, request

from models.models import db, ActiveTimer, SeatLayoutConfig, User
from utils.audit_log import get_operator_name, write_log
from utils.decorators import token_required
from utils.response import error_response, success_response
from utils.roles import is_admin
from utils.seat_layout import (
    SEAT_LAYOUT_CONFIG_KEY,
    build_table_no_remap,
    normalize_seat_layout_config,
    normalize_table_no,
    remap_timer_notes_table_nos,
)

seat_layout_config_bp = Blueprint('seat_layout_config', __name__)


def _get_current_user():
    current_user_id = getattr(g, 'current_user_id', None)
    if current_user_id is None:
        return None
    return User.query.get(current_user_id)


def _require_admin_user():
    current_user = _get_current_user()
    if not current_user:
        return None, error_response('用户不存在或未登录', 401)
    if not is_admin(current_user):
        return None, error_response('仅管理员可执行该操作', 403)
    return current_user, None


def _get_config_record():
    return SeatLayoutConfig.query.filter_by(config_key=SEAT_LAYOUT_CONFIG_KEY).first()


def _build_response_payload(record=None):
    normalized = normalize_seat_layout_config(record.config_data if record else None, strict=False)
    return {
        **normalized,
        'updatedAt': record.updated_at.isoformat() if record and record.updated_at else None
    }


def _sync_active_timer_table_nos(remap):
    if not remap:
        return 0

    changed_count = 0
    timers = ActiveTimer.query.filter(ActiveTimer.status.in_(['active', 'paused'])).all()
    for timer in timers:
        changed = False
        current_table_no = normalize_table_no(timer.table_no)
        mapped_table_no = remap.get(current_table_no, current_table_no)
        if mapped_table_no and mapped_table_no != timer.table_no:
            timer.table_no = mapped_table_no
            changed = True

        remapped_notes, notes_changed = remap_timer_notes_table_nos(timer.notes, remap)
        if notes_changed:
            timer.notes = remapped_notes
            changed = True

        if changed:
            changed_count += 1

    return changed_count


@seat_layout_config_bp.route('', methods=['GET'])
@token_required
def get_seat_layout_config():
    record = _get_config_record()
    return success_response(_build_response_payload(record))


@seat_layout_config_bp.route('', methods=['PUT'])
@token_required
def update_seat_layout_config():
    current_user, permission_error = _require_admin_user()
    if permission_error:
        return permission_error

    data = request.get_json()
    if not data:
        return error_response('Request body is required', 400)

    try:
        normalized = normalize_seat_layout_config(data, strict=True)
    except ValueError as exc:
        return error_response(str(exc), 400)

    record = _get_config_record()
    previous_config = record.config_data if record else None
    remap = build_table_no_remap(previous_config, normalized)
    changed_slots = sum(1 for old_table_no, new_table_no in remap.items() if old_table_no != new_table_no)

    if record:
        record.config_data = normalized
    else:
        record = SeatLayoutConfig(
            config_key=SEAT_LAYOUT_CONFIG_KEY,
            config_data=normalized
        )
        db.session.add(record)

    remapped_timer_count = _sync_active_timer_table_nos(remap)
    db.session.commit()

    if changed_slots > 0:
        operator = get_operator_name(default=current_user.username or current_user.account or 'unknown')
        write_log(
            'seat_layout_config_update',
            f'更新座位编号配置：变更 {changed_slots} 个座位，重映射 {remapped_timer_count} 条计时记录',
            operator=operator
        )
        db.session.commit()

    return success_response(_build_response_payload(record), 'Seat layout config updated successfully')

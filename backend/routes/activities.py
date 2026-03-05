from datetime import datetime
from flask import Blueprint, request
from models.models import db, Activity
from utils.audit_log import get_operator_name, write_log
from utils.decorators import token_required
from utils.response import success_response, error_response

activities_bp = Blueprint('activities', __name__)


def _pick(data, *keys, default=None):
    for key in keys:
        if key in data and data.get(key) is not None:
            return data.get(key)
    return default


def _normalize_status(status, fallback='active'):
    if status is None:
        return fallback
    if status not in ['active', 'inactive']:
        return None
    return status


def _date_text(value):
    return value.isoformat() if value else '-'


@activities_bp.route('', methods=['GET'])
@token_required
def get_activities():
    status = request.args.get('status', 'all', type=str)

    query = Activity.query

    if status == 'active':
        query = query.filter(Activity.status == 'active')
    elif status == 'inactive':
        query = query.filter(Activity.status == 'inactive')

    activities = query.order_by(Activity.created_at.desc()).all()

    return success_response([activity.to_dict() for activity in activities])


@activities_bp.route('', methods=['POST'])
@token_required
def create_activity():
    data = request.get_json()

    if not data:
        return error_response('No data provided', 400)

    raw_name = _pick(data, 'name')
    name = raw_name.strip() if isinstance(raw_name, str) else None
    raw_description = _pick(data, 'description')
    description = raw_description.strip() if isinstance(raw_description, str) else None
    min_amount = _pick(data, 'min_amount', 'minAmount', 'minRechargeAmount')
    bonus_amount = _pick(data, 'bonus_amount', 'bonusAmount', 'bonus_rate', 'bonusRate', 'bonusRatio')
    start_date = _pick(data, 'start_date', 'startDate')
    end_date = _pick(data, 'end_date', 'endDate')
    status = _normalize_status(_pick(data, 'status'), fallback='active')

    if not name:
        return error_response('Name is required', 400)
    if status is None:
        return error_response('Invalid status value', 400)

    last_activity = Activity.query.order_by(Activity.id.desc()).first()

    if last_activity:
        try:
            last_num = int(last_activity.id[1:])
            new_num = last_num + 1
        except (ValueError, IndexError):
            new_num = 1
    else:
        new_num = 1

    activity_id = f'A{new_num:03d}'

    while Activity.query.get(activity_id):
        new_num += 1
        activity_id = f'A{new_num:03d}'

    parsed_start_date = None
    parsed_end_date = None

    if start_date:
        try:
            parsed_start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        except ValueError:
            try:
                parsed_start_date = datetime.strptime(start_date, '%Y-%m-%d')
            except ValueError:
                return error_response('Invalid start_date format', 400)

    if end_date:
        try:
            parsed_end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError:
            try:
                parsed_end_date = datetime.strptime(end_date, '%Y-%m-%d')
            except ValueError:
                return error_response('Invalid end_date format', 400)

    activity = Activity(
        id=activity_id,
        name=name,
        description=description,
        min_amount=min_amount,
        # Stored in legacy column `bonus_rate`, semantic is fixed gift amount.
        bonus_rate=bonus_amount,
        start_date=parsed_start_date,
        end_date=parsed_end_date,
        status=status
    )

    db.session.add(activity)

    operator = get_operator_name()
    write_log(
        'activity_create',
        f'创建活动：{name}（{activity_id}），门槛 {min_amount or 0}，赠送 {bonus_amount or 0}',
        operator=operator
    )

    db.session.commit()

    return success_response(activity.to_dict(), 'Activity created successfully', 201)


@activities_bp.route('/<activity_id>', methods=['PUT'])
@token_required
def update_activity(activity_id):
    activity = Activity.query.get(activity_id)

    if not activity:
        return error_response('Activity not found', 404)

    data = request.get_json()

    if not data:
        return error_response('No data provided', 400)

    before_name = activity.name
    before_description = activity.description
    before_min_amount = activity.min_amount
    before_bonus = activity.bonus_rate
    before_start = activity.start_date
    before_end = activity.end_date
    before_status = activity.status

    name = _pick(data, 'name')
    description = _pick(data, 'description')
    min_amount = _pick(data, 'min_amount', 'minAmount', 'minRechargeAmount')
    bonus_amount = _pick(data, 'bonus_amount', 'bonusAmount', 'bonus_rate', 'bonusRate', 'bonusRatio')
    start_date = _pick(data, 'start_date', 'startDate')
    end_date = _pick(data, 'end_date', 'endDate')
    status = _pick(data, 'status')

    if name is not None:
        name = name.strip()
        if not name:
            return error_response('Name cannot be empty', 400)
        activity.name = name

    if description is not None:
        activity.description = description.strip() if description.strip() else None

    if min_amount is not None:
        activity.min_amount = min_amount

    if bonus_amount is not None:
        # Stored in legacy column `bonus_rate`, semantic is fixed gift amount.
        activity.bonus_rate = bonus_amount

    if start_date is not None:
        try:
            activity.start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        except ValueError:
            try:
                activity.start_date = datetime.strptime(start_date, '%Y-%m-%d')
            except ValueError:
                return error_response('Invalid start_date format', 400)

    if end_date is not None:
        try:
            activity.end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError:
            try:
                activity.end_date = datetime.strptime(end_date, '%Y-%m-%d')
            except ValueError:
                return error_response('Invalid end_date format', 400)

    if status is not None:
        if status not in ['active', 'inactive']:
            return error_response('Invalid status value', 400)
        activity.status = status

    changes = []
    if before_name != activity.name:
        changes.append(f'名称：{before_name or "-"} -> {activity.name or "-"}')
    if before_description != activity.description:
        changes.append('描述已更新')
    if before_min_amount != activity.min_amount:
        changes.append(f'门槛：{before_min_amount or 0} -> {activity.min_amount or 0}')
    if before_bonus != activity.bonus_rate:
        changes.append(f'赠送：{before_bonus or 0} -> {activity.bonus_rate or 0}')
    if before_start != activity.start_date:
        changes.append(f'开始时间：{_date_text(before_start)} -> {_date_text(activity.start_date)}')
    if before_end != activity.end_date:
        changes.append(f'结束时间：{_date_text(before_end)} -> {_date_text(activity.end_date)}')
    if before_status != activity.status:
        changes.append(f'状态：{before_status or "-"} -> {activity.status or "-"}')

    if changes:
        operator = get_operator_name()
        write_log(
            'activity_update',
            f'更新活动：{activity.name}（{activity.id}），变更：{"；".join(changes)}',
            operator=operator
        )

    db.session.commit()

    return success_response(activity.to_dict(), 'Activity updated successfully')


@activities_bp.route('/<activity_id>', methods=['DELETE'])
@token_required
def delete_activity(activity_id):
    activity = Activity.query.get(activity_id)

    if not activity:
        return error_response('Activity not found', 404)

    activity_name = activity.name

    db.session.delete(activity)

    operator = get_operator_name()
    write_log(
        'activity_delete',
        f'删除活动：{activity_name}（{activity_id}）',
        operator=operator
    )

    db.session.commit()

    return success_response(message='Activity deleted successfully')

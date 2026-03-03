from datetime import datetime
from flask import Blueprint, request, g
from models.models import db, Activity
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
    
    db.session.commit()
    
    return success_response(activity.to_dict(), 'Activity updated successfully')


@activities_bp.route('/<activity_id>', methods=['DELETE'])
@token_required
def delete_activity(activity_id):
    activity = Activity.query.get(activity_id)
    
    if not activity:
        return error_response('Activity not found', 404)
    
    db.session.delete(activity)
    db.session.commit()
    
    return success_response(message='Activity deleted successfully')

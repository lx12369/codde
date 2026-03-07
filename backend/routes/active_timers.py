import time
import json
from datetime import datetime
from flask import Blueprint, request
from models.models import db, ActiveTimer, Customer, Balance, Transaction, SeatLayoutConfig
from utils.audit_log import get_operator_name, write_log
from utils.decorators import token_required
from utils.misc_inventory_service import normalize_misc_selections, apply_misc_outbound
from utils.misc_selection_codec import compose_description_with_misc
from utils.response import success_response, error_response
from utils.seat_layout import (
    SEAT_LAYOUT_CONFIG_KEY,
    extract_extra_table_nos_from_notes,
    get_allowed_table_no_set,
    is_valid_table_no,
    normalize_seat_layout_config,
    normalize_table_no,
)

active_timers_bp = Blueprint('active_timers', __name__)


def _to_float(value, default=None):
    if value is None:
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _generate_transaction_id():
    last_transaction = Transaction.query.order_by(Transaction.id.desc()).first()

    if last_transaction:
        try:
            last_id_num = int(str(last_transaction.id)[1:])
            return f'T{last_id_num + 1:03d}'
        except (ValueError, TypeError, IndexError):
            pass

    return f'T{int(datetime.utcnow().timestamp() * 1000)}'


def _normalize_table_no(value):
    return normalize_table_no(value)


def _get_active_timer_occupied_seat_map(exclude_timer_id=None):
    occupied = {}
    timers = ActiveTimer.query.filter(
        ActiveTimer.status.in_(['active', 'paused'])
    ).all()

    for timer in timers:
        if exclude_timer_id and timer.id == exclude_timer_id:
            continue

        primary_table_no = _normalize_table_no(timer.table_no)
        if is_valid_table_no(primary_table_no) and primary_table_no not in occupied:
            occupied[primary_table_no] = timer.id

        for table_no in extract_extra_table_nos_from_notes(timer.notes):
            if table_no not in occupied:
                occupied[table_no] = timer.id

    return occupied


def _get_effective_seat_layout_config():
    record = SeatLayoutConfig.query.filter_by(config_key=SEAT_LAYOUT_CONFIG_KEY).first()
    return normalize_seat_layout_config(record.config_data if record else None, strict=False)


def _validate_table_no(table_no, occupied_map=None, allowed_table_nos=None):
    if not table_no:
        return '桌号不能为空'

    if not is_valid_table_no(table_no):
        return '桌号必须在 A-H/J-N/P-Z 桌、1-100号范围内'

    normalized_table_no = _normalize_table_no(table_no)
    if allowed_table_nos is not None and normalized_table_no not in allowed_table_nos:
        return f'桌号未配置：{normalized_table_no}'

    if occupied_map is not None and normalized_table_no in occupied_map:
        return f'桌号已占用：{table_no}'

    return None


def _validate_extra_table_nos(raw_notes, primary_table_no, occupied_map, allowed_table_nos):
    seen = set()
    normalized_primary_table_no = _normalize_table_no(primary_table_no)
    if is_valid_table_no(normalized_primary_table_no):
        seen.add(normalized_primary_table_no)

    extra_table_nos = extract_extra_table_nos_from_notes(raw_notes)
    for index, table_no in enumerate(extra_table_nos):
        seat_label = f'第{index + 2}座位'
        if not is_valid_table_no(table_no):
            return f'{seat_label}格式不正确'
        if table_no not in allowed_table_nos:
            return f'{seat_label}未配置：{table_no}'
        if table_no in seen:
            return f'{seat_label}不能与已选座位重复'
        if table_no in occupied_map:
            return f'{seat_label}已占用：{table_no}'
        seen.add(table_no)
    return None


@active_timers_bp.route('', methods=['GET'])
@token_required
def get_active_timers():
    timers = ActiveTimer.query.filter(
        ActiveTimer.status.in_(['active', 'paused'])
    ).order_by(ActiveTimer.created_at.desc()).all()

    result = []
    for timer in timers:
        timer_dict = timer.to_dict()
        customer = Customer.query.get(timer.customer_id)
        timer_dict['customer'] = customer.to_dict() if customer else None
        result.append(timer_dict)

    return success_response(result)


@active_timers_bp.route('', methods=['POST'])
@token_required
def create_active_timer():
    data = request.get_json()

    if not data:
        return error_response('No data provided', 400)

    customer_id = str(data.get('customer_id', '')).strip()
    timer_type = str(data.get('timer_type', '')).strip() or 'limited'
    table_no = _normalize_table_no(data.get('table_no', data.get('tableNo')))
    notes = data.get('notes', '')
    notes = str(notes).strip() if notes else None

    if not customer_id:
        return error_response('Customer ID is required', 400)

    customer = Customer.query.get(customer_id)
    if not customer or customer.is_deleted:
        return error_response('Customer not found', 404)

    seat_layout_config = _get_effective_seat_layout_config()
    allowed_table_nos = get_allowed_table_no_set(seat_layout_config)
    occupied_map = _get_active_timer_occupied_seat_map()

    table_no_error = _validate_table_no(table_no, occupied_map=occupied_map, allowed_table_nos=allowed_table_nos)
    if table_no_error:
        return error_response(table_no_error, 400)

    extra_table_no_error = _validate_extra_table_nos(notes, table_no, occupied_map, allowed_table_nos)
    if extra_table_no_error:
        return error_response(extra_table_no_error, 400)

    timer_id = f'TM{time.time_ns()}'

    timer = ActiveTimer(
        id=timer_id,
        customer_id=customer_id,
        table_no=table_no,
        start_time=datetime.utcnow(),
        timer_type=timer_type,
        notes=notes,
        status='active'
    )

    db.session.add(timer)

    operator = get_operator_name(default='unknown')
    write_log(
        'timer_start',
        f'开始计时：客户 {customer.name}（{customer_id}），桌号 {table_no}，类型 {timer_type}',
        operator=operator
    )

    db.session.commit()

    timer_dict = timer.to_dict()
    timer_dict['customer'] = customer.to_dict()

    return success_response(timer_dict, 'Timer created successfully', 201)


@active_timers_bp.route('/<timer_id>', methods=['PUT'])
@token_required
def update_active_timer(timer_id):
    timer = ActiveTimer.query.get(timer_id)

    if not timer:
        return error_response('Timer not found', 404)

    data = request.get_json()

    if not data:
        return error_response('No data provided', 400)

    before_notes = timer.notes
    before_status = timer.status
    before_timer_type = timer.timer_type
    before_table_no = timer.table_no

    timer_type = data.get('timer_type')
    notes = data.get('notes')
    status = data.get('status')
    has_table_no = 'table_no' in data or 'tableNo' in data
    table_no = _normalize_table_no(data.get('table_no', data.get('tableNo')))
    next_timer_type = timer.timer_type
    next_notes = timer.notes
    next_status = timer.status
    next_table_no = timer.table_no

    if timer_type is not None:
        timer_type = str(timer_type).strip()
        valid_timer_types = ['limited', 'weekday', 'weekend']
        if timer_type not in valid_timer_types:
            return error_response(f'Invalid timer_type. Must be one of: {", ".join(valid_timer_types)}', 400)
        next_timer_type = timer_type

    if notes is not None:
        notes = str(notes).strip()
        next_notes = notes if notes else None

    if status is not None:
        valid_statuses = ['active', 'paused', 'completed']
        if status not in valid_statuses:
            return error_response(f'Invalid status. Must be one of: {", ".join(valid_statuses)}', 400)
        next_status = status

    if has_table_no:
        next_table_no = table_no

    if has_table_no or notes is not None:
        seat_layout_config = _get_effective_seat_layout_config()
        allowed_table_nos = get_allowed_table_no_set(seat_layout_config)
        occupied_map = _get_active_timer_occupied_seat_map(exclude_timer_id=timer.id)
    else:
        allowed_table_nos = None
        occupied_map = None

    if has_table_no:
        table_no_error = _validate_table_no(next_table_no, occupied_map=occupied_map, allowed_table_nos=allowed_table_nos)
        if table_no_error:
            return error_response(table_no_error, 400)

    if notes is not None or has_table_no:
        extra_table_no_error = _validate_extra_table_nos(next_notes, next_table_no, occupied_map, allowed_table_nos)
        if extra_table_no_error:
            return error_response(extra_table_no_error, 400)

    timer.timer_type = next_timer_type
    timer.notes = next_notes
    timer.status = next_status
    timer.table_no = next_table_no

    changes = []
    if before_timer_type != timer.timer_type:
        changes.append(f'计时类型：{before_timer_type} -> {timer.timer_type}')
    if before_notes != timer.notes:
        changes.append('备注已更新')
    if before_status != timer.status:
        changes.append(f'状态：{before_status} -> {timer.status}')
    if before_table_no != timer.table_no:
        changes.append(f'桌号：{before_table_no or "-"} -> {timer.table_no}')

    if changes:
        customer = Customer.query.get(timer.customer_id)
        customer_label = f'{customer.name}（{timer.customer_id}）' if customer else timer.customer_id
        operator = get_operator_name(default='unknown')
        write_log(
            'timer_update',
            f'更新计时：{customer_label}，变更：{"；".join(changes)}',
            operator=operator
        )

    db.session.commit()

    timer_dict = timer.to_dict()
    customer = Customer.query.get(timer.customer_id)
    timer_dict['customer'] = customer.to_dict() if customer else None

    return success_response(timer_dict, 'Timer updated successfully')


@active_timers_bp.route('/<timer_id>/settle', methods=['POST'])
@token_required
def settle_active_timer(timer_id):
    timer = ActiveTimer.query.get(timer_id)

    if not timer:
        return error_response('Timer not found', 404)

    if timer.status not in ['active', 'paused']:
        return error_response('Timer is not active', 400)

    data = request.get_json() or {}

    amount = _to_float(data.get('amount'), None)
    description = str(data.get('description', '')).strip()
    notes = str(data.get('notes', '')).strip()
    misc_selections = normalize_misc_selections(data.get('misc_selections', data.get('miscSelections')))
    if not misc_selections:
        try:
            parsed_timer_notes = json.loads(timer.notes or '{}')
            if isinstance(parsed_timer_notes, dict):
                misc_selections = normalize_misc_selections(parsed_timer_notes.get('miscSelections'))
        except (TypeError, ValueError):
            misc_selections = {}

    if amount is None or amount <= 0:
        return error_response('Valid amount is required', 400)

    if not description:
        return error_response('Description is required', 400)

    customer = Customer.query.get(timer.customer_id)
    if not customer:
        return error_response('Customer not found', 404)

    balance = Balance.query.filter_by(customer_id=timer.customer_id).first()
    if not balance or balance.balance < amount:
        return error_response('Insufficient balance', 400)

    operator = get_operator_name(default='unknown')
    transaction_id = _generate_transaction_id()

    if misc_selections:
        try:
            apply_misc_outbound(
                misc_selections,
                operator=operator,
                reason=f'计时结算扣减（客户 {customer.name}（{timer.customer_id}））'
            )
        except ValueError as exc:
            db.session.rollback()
            return error_response(str(exc), 400)

    transaction = Transaction(
        id=transaction_id,
        customer_id=timer.customer_id,
        type='consumption',
        amount=amount,
        description=compose_description_with_misc(description, misc_selections),
        operator=operator
    )

    balance.balance -= amount
    timer.status = 'completed'

    if notes:
        if timer.notes:
            timer.notes = f'{timer.notes}\n[settlement] {notes}'
        else:
            timer.notes = f'[settlement] {notes}'

    write_log(
        'timer_settle',
        f'计时结算：客户 {customer.name}（{timer.customer_id}）扣费 ¥{amount:.2f}，说明：{description}',
        operator=operator
    )

    db.session.add(transaction)
    db.session.commit()

    return success_response(
        {
            'timer': timer.to_dict(),
            'transaction': transaction.to_dict()
        },
        'Timer settled successfully',
        201
    )


@active_timers_bp.route('/<timer_id>', methods=['DELETE'])
@token_required
def delete_active_timer(timer_id):
    timer = ActiveTimer.query.get(timer_id)

    if not timer:
        return error_response('Timer not found', 404)

    customer = Customer.query.get(timer.customer_id)
    customer_label = f'{customer.name}（{timer.customer_id}）' if customer else timer.customer_id

    db.session.delete(timer)

    operator = get_operator_name(default='unknown')
    write_log(
        'timer_delete',
        f'删除计时：{customer_label}，计时器ID {timer_id}',
        operator=operator
    )

    db.session.commit()

    return success_response(message='Timer ended and deleted successfully')

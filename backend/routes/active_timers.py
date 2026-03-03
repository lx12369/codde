import time
from datetime import datetime
from flask import Blueprint, request, g
from models.models import db, ActiveTimer, Customer, Balance, Transaction, Log, User
from utils.decorators import token_required
from utils.response import success_response, error_response

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


def _resolve_operator():
    user_id = getattr(g, 'current_user_id', None)
    if user_id is None:
        return 'unknown'

    user = User.query.get(user_id)
    if user and user.username:
        return user.username

    return 'unknown'


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
    notes = data.get('notes', '')
    notes = str(notes).strip() if notes else None

    if not customer_id:
        return error_response('Customer ID is required', 400)

    customer = Customer.query.get(customer_id)
    if not customer or customer.is_deleted:
        return error_response('Customer not found', 404)


    timer_id = f'TM{time.time_ns()}'

    timer = ActiveTimer(
        id=timer_id,
        customer_id=customer_id,
        start_time=datetime.utcnow(),
        timer_type=timer_type,
        notes=notes,
        status='active'
    )

    db.session.add(timer)
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

    notes = data.get('notes')
    status = data.get('status')

    if notes is not None:
        notes = str(notes).strip()
        timer.notes = notes if notes else None

    if status is not None:
        valid_statuses = ['active', 'paused', 'completed']
        if status not in valid_statuses:
            return error_response(f'Invalid status. Must be one of: {", ".join(valid_statuses)}', 400)
        timer.status = status

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

    operator = _resolve_operator()
    transaction_id = _generate_transaction_id()

    transaction = Transaction(
        id=transaction_id,
        customer_id=timer.customer_id,
        type='consumption',
        amount=amount,
        description=description,
        operator=operator
    )

    balance.balance -= amount
    timer.status = 'completed'

    if notes:
        if timer.notes:
            timer.notes = f'{timer.notes}\n[settlement] {notes}'
        else:
            timer.notes = f'[settlement] {notes}'

    log = Log(
        type='consumption',
        description=f'客户 {customer.name}（{timer.customer_id}）计时消费 ¥{amount:.2f}：{description}',
        operator=operator
    )

    db.session.add(transaction)
    db.session.add(log)
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

    db.session.delete(timer)
    db.session.commit()

    return success_response(message='Timer ended and deleted successfully')


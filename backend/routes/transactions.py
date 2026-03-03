from flask import Blueprint, request, g
from datetime import datetime, timezone
from models import db, Transaction, Customer, Balance, Activity, Log, User
from utils.response import success_response, error_response, paginated_response
from utils.decorators import token_required

transactions_bp = Blueprint('transactions', __name__)


def _generate_transaction_id():
    last_transaction = Transaction.query.order_by(Transaction.id.desc()).first()

    if last_transaction:
        try:
            last_id_num = int(str(last_transaction.id)[1:])
            return f'T{last_id_num + 1:03d}'
        except (ValueError, TypeError, IndexError):
            pass

    return f'T{int(datetime.utcnow().timestamp() * 1000)}'


def _to_float(value, default=None):
    if value is None:
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_utc_naive(value):
    if value is None:
        return None

    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    return value


def _resolve_operator():
    user_id = getattr(g, 'current_user_id', None)
    if user_id is None:
        return 'unknown'

    user = User.query.get(user_id)
    if user and user.username:
        return user.username

    return 'unknown'


def _is_activity_available(activity):
    if not activity or activity.status != 'active':
        return False

    now = datetime.utcnow()
    start_date = _to_utc_naive(activity.start_date)
    end_date = _to_utc_naive(activity.end_date)

    if start_date and now < start_date:
        return False
    if end_date and now > end_date:
        return False

    return True


def _calc_bonus_with_activity(amount, activity, requested_bonus):
    if requested_bonus is not None:
        bonus = _to_float(requested_bonus, None)
        if bonus is None or bonus < 0:
            return None
        return bonus

    if not activity:
        return 0.0

    min_amount = _to_float(activity.min_amount, 0.0) or 0.0
    # Legacy schema stores fixed gift amount in `bonus_rate`.
    bonus_amount = _to_float(activity.bonus_rate, 0.0) or 0.0
    if bonus_amount <= 0 or min_amount <= 0:
        return 0.0

    if amount < min_amount:
        return 0.0

    multiples = int(amount // min_amount)
    if multiples <= 0:
        return 0.0

    return round(multiples * bonus_amount, 2)


@transactions_bp.route('', methods=['GET'])
@token_required
def get_transactions():
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 10, type=int)
    transaction_type = request.args.get('type', None)
    customer_id = request.args.get('customer_id', None)
    date_start = request.args.get('date_start', None)
    date_end = request.args.get('date_end', None)

    query = Transaction.query

    if transaction_type:
        query = query.filter(Transaction.type == transaction_type)

    if customer_id:
        query = query.filter(Transaction.customer_id == customer_id)

    if date_start:
        try:
            start_dt = datetime.fromisoformat(date_start)
            query = query.filter(Transaction.transaction_time >= start_dt)
        except ValueError:
            pass

    if date_end:
        try:
            end_dt = datetime.fromisoformat(date_end)
            query = query.filter(Transaction.transaction_time <= end_dt)
        except ValueError:
            pass

    query = query.order_by(Transaction.transaction_time.desc())

    pagination = query.paginate(page=page, per_page=page_size, error_out=False)

    items = [t.to_dict() for t in pagination.items]

    return paginated_response(items, pagination.total, page, page_size)


@transactions_bp.route('/<transaction_id>', methods=['GET'])
@token_required
def get_transaction(transaction_id):
    transaction = Transaction.query.filter_by(id=transaction_id).first()

    if not transaction:
        return error_response('Transaction not found', 404)

    return success_response(transaction.to_dict())


@transactions_bp.route('/recharge', methods=['POST'])
@token_required
def create_recharge():
    data = request.get_json()

    if not data:
        return error_response('No data provided', 400)

    customer_id = (data.get('customer_id') or '').strip()
    amount = _to_float(data.get('amount'), None)
    payment_method = (data.get('payment_method') or '').strip()
    activity_id = (data.get('activity_id') or '').strip() or None

    if not customer_id:
        return error_response('Customer ID is required', 400)

    if amount is None or amount <= 0:
        return error_response('Valid amount is required', 400)

    if not payment_method:
        return error_response('Payment method is required', 400)

    customer = Customer.query.filter_by(id=customer_id).first()
    if not customer or customer.is_deleted:
        return error_response('Customer not found', 404)

    activity = None
    if activity_id:
        activity = Activity.query.filter_by(id=activity_id).first()
        if not activity:
            return error_response('Activity not found', 404)
        if not _is_activity_available(activity):
            return error_response('Activity is not available', 400)

    # If an activity is selected, bonus must follow activity policy.
    requested_bonus = None if activity else data.get('bonus_amount')
    bonus_amount = _calc_bonus_with_activity(amount, activity, requested_bonus)
    if bonus_amount is None:
        return error_response('Valid bonus amount is required', 400)

    new_id = _generate_transaction_id()
    operator = _resolve_operator()

    transaction = Transaction(
        id=new_id,
        customer_id=customer_id,
        type='recharge',
        amount=amount,
        bonus_amount=bonus_amount,
        payment_method=payment_method,
        activity_id=activity_id,
        operator=operator
    )

    balance = Balance.query.filter_by(customer_id=customer_id).first()
    if not balance:
        balance = Balance(customer_id=customer_id, balance=0)
        db.session.add(balance)

    total_credit = amount + bonus_amount
    balance.balance += total_credit

    log = Log(
        type='recharge',
        description=f'客户 {customer.name}（{customer_id}）充值 ¥{amount:.2f}，赠送 ¥{bonus_amount:.2f}',
        operator=operator
    )

    db.session.add(transaction)
    db.session.add(log)
    db.session.commit()

    return success_response(transaction.to_dict(), 'Recharge created successfully', 201)


@transactions_bp.route('/consumption', methods=['POST'])
@token_required
def create_consumption():
    data = request.get_json()

    if not data:
        return error_response('No data provided', 400)

    customer_id = (data.get('customer_id') or '').strip()
    amount = _to_float(data.get('amount'), None)
    description = (data.get('description') or '').strip()

    if not customer_id:
        return error_response('Customer ID is required', 400)

    if amount is None or amount <= 0:
        return error_response('Valid amount is required', 400)

    if not description:
        return error_response('Description is required', 400)

    customer = Customer.query.filter_by(id=customer_id).first()
    if not customer or customer.is_deleted:
        return error_response('Customer not found', 404)

    balance = Balance.query.filter_by(customer_id=customer_id).first()
    if not balance or balance.balance < amount:
        return error_response('Insufficient balance', 400)

    new_id = _generate_transaction_id()
    operator = _resolve_operator()

    transaction = Transaction(
        id=new_id,
        customer_id=customer_id,
        type='consumption',
        amount=amount,
        description=description,
        operator=operator
    )

    balance.balance -= amount

    log = Log(
        type='consumption',
        description=f'客户 {customer.name}（{customer_id}）消费 ¥{amount:.2f}：{description}',
        operator=operator
    )

    db.session.add(transaction)
    db.session.add(log)
    db.session.commit()

    return success_response(transaction.to_dict(), 'Consumption created successfully', 201)


@transactions_bp.route('/<transaction_id>/cancel', methods=['POST'])
@token_required
def cancel_transaction(transaction_id):
    transaction = Transaction.query.filter_by(id=transaction_id).first()
    if not transaction:
        return error_response('交易记录不存在', 404)

    customer = Customer.query.filter_by(id=transaction.customer_id).first()
    if not customer:
        return error_response('客户不存在', 404)

    balance = Balance.query.filter_by(customer_id=transaction.customer_id).first()
    if not balance:
        balance = Balance(customer_id=transaction.customer_id, balance=0.0)
        db.session.add(balance)

    transaction_amount = _to_float(transaction.amount, 0.0) or 0.0
    bonus_amount = _to_float(transaction.bonus_amount, 0.0) or 0.0

    if transaction.type == 'recharge':
        rollback_amount = transaction_amount + bonus_amount
        current_balance = _to_float(balance.balance, 0.0) or 0.0
        if current_balance + 1e-9 < rollback_amount:
            return error_response('余额不足，无法取消该充值记录', 400)
        balance.balance = current_balance - rollback_amount
        log_description = (
            f'取消充值：客户 {customer.name}（{transaction.customer_id}）'
            f'撤销 ¥{transaction_amount:.2f}，赠送撤销 ¥{bonus_amount:.2f}'
        )
    elif transaction.type == 'consumption':
        current_balance = _to_float(balance.balance, 0.0) or 0.0
        balance.balance = current_balance + transaction_amount
        log_description = (
            f'取消消费：客户 {customer.name}（{transaction.customer_id}）'
            f'退回 ¥{transaction_amount:.2f}'
        )
    else:
        return error_response('暂不支持取消该交易类型', 400)

    operator = _resolve_operator()
    cancel_log = Log(
        type=transaction.type,
        description=log_description,
        operator=operator
    )

    db.session.delete(transaction)
    db.session.add(cancel_log)
    db.session.commit()

    return success_response(
        {
            'transaction_id': transaction_id,
            'customer_id': customer.id,
            'balance': balance.balance
        },
        '交易取消成功'
    )


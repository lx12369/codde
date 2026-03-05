from datetime import datetime, timezone
from flask import Blueprint, request
import re
from models import db, Transaction, Customer, Balance, Activity, BeadInventoryBalance, BeadInventoryLedger
from utils.audit_log import get_operator_name, write_log
from utils.response import success_response, error_response, paginated_response
from utils.decorators import token_required
from utils.bead_inventory_service import generate_entity_id, generate_reference_no

transactions_bp = Blueprint('transactions', __name__)
BEAD_PURCHASE_DESC_PATTERN = re.compile(
    r'买豆入库：.+?（(?P<material_id>M\d+)）.*?入库\s+(?P<grams>\d+(?:\.\d+)?)g，单号\s+(?P<reference_no>[A-Z0-9]+)'
)


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


def _build_customer_snapshot_map(customer_ids):
    ids = [cid for cid in customer_ids if cid]
    if not ids:
        return {}

    customers = Customer.query.filter(Customer.id.in_(ids)).all()
    return {
        item.id: {
            'id': item.id,
            'name': item.name,
            'phone': item.phone,
            'wechat': item.wechat
        }
        for item in customers
    }


def _parse_bead_purchase_description(description):
    text = str(description or '').strip()
    if not text:
        return None
    match = BEAD_PURCHASE_DESC_PATTERN.search(text)
    if not match:
        return None
    try:
        grams = float(match.group('grams'))
    except (TypeError, ValueError):
        return None
    if grams <= 0:
        return None
    return {
        'material_id': match.group('material_id'),
        'grams': grams,
        'reference_no': match.group('reference_no')
    }


def _rollback_bead_purchase_inventory(transaction, operator):
    parsed = _parse_bead_purchase_description(transaction.description)
    if not parsed:
        return False, '买豆交易缺少可回滚的库存信息'

    material_id = parsed['material_id']
    inbound_reference_no = parsed['reference_no']
    fallback_grams = parsed['grams']

    inbound_ledger = (
        BeadInventoryLedger.query
        .filter(BeadInventoryLedger.material_id == material_id)
        .filter(BeadInventoryLedger.action_type == 'inbound')
        .filter(BeadInventoryLedger.reference_no == inbound_reference_no)
        .order_by(BeadInventoryLedger.created_at.desc())
        .first()
    )
    if not inbound_ledger:
        return False, '未找到对应入库流水，无法取消买豆交易'

    rollback_grams = abs(float(inbound_ledger.delta_grams or fallback_grams))
    if rollback_grams <= 0:
        return False, '入库克数异常，无法取消买豆交易'

    balance = BeadInventoryBalance.query.filter_by(material_id=material_id).first()
    if not balance:
        return False, '未找到豆仓库存记录，无法取消买豆交易'

    current_grams = float(balance.current_grams or 0.0)
    if current_grams + 1e-9 < rollback_grams:
        return False, '当前库存不足，无法取消该买豆交易'

    balance.current_grams = round(current_grams - rollback_grams, 3)
    reverse_reference_no = generate_reference_no('OUT')
    reverse_ledger = BeadInventoryLedger(
        id=generate_entity_id('BL'),
        material_id=material_id,
        action_type='outbound',
        delta_grams=-rollback_grams,
        balance_after_grams=balance.current_grams,
        unit_input='gram',
        unit_count=rollback_grams,
        reference_no=reverse_reference_no,
        reason=f'取消买豆交易（#{transaction.id}）',
        note=f'回滚入库单号 {inbound_reference_no}',
        operator=operator
    )
    db.session.add(reverse_ledger)
    return True, None


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
    customer_snapshot_map = _build_customer_snapshot_map([item.get('customer_id') for item in items])
    for item in items:
        customer_id = item.get('customer_id')
        snapshot = customer_snapshot_map.get(customer_id)
        if snapshot:
            item['customer_name'] = snapshot.get('name')
            item['customer_phone'] = snapshot.get('phone')
            item['customer_wechat'] = snapshot.get('wechat')
        elif customer_id == 'C000':
            item['customer_name'] = '豆仓采购'
            item['customer_phone'] = None
            item['customer_wechat'] = None

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
    operator = get_operator_name(default='unknown')

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

    write_log(
        'recharge',
        f'客户 {customer.name}（{customer_id}）充值 ¥{amount:.2f}，赠送 ¥{bonus_amount:.2f}',
        operator=operator
    )

    db.session.add(transaction)
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
    operator = get_operator_name(default='unknown')

    transaction = Transaction(
        id=new_id,
        customer_id=customer_id,
        type='consumption',
        amount=amount,
        description=description,
        operator=operator
    )

    balance.balance -= amount

    write_log(
        'consumption',
        f'客户 {customer.name}（{customer_id}）消费 ¥{amount:.2f}：{description}',
        operator=operator
    )

    db.session.add(transaction)
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
        if transaction.type == 'bead_purchase':
            customer = Customer(id=transaction.customer_id, name='豆仓采购', is_deleted=True)
            db.session.add(customer)
            db.session.flush()
        else:
            return error_response('客户不存在', 404)

    balance = Balance.query.filter_by(customer_id=transaction.customer_id).first()
    if not balance:
        balance = Balance(customer_id=transaction.customer_id, balance=0.0)
        db.session.add(balance)

    transaction_amount = _to_float(transaction.amount, 0.0) or 0.0
    bonus_amount = _to_float(transaction.bonus_amount, 0.0) or 0.0
    operator = get_operator_name(default='unknown')

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
        log_type = 'transaction_cancel_recharge'
    elif transaction.type == 'consumption':
        current_balance = _to_float(balance.balance, 0.0) or 0.0
        balance.balance = current_balance + transaction_amount
        log_description = (
            f'取消消费：客户 {customer.name}（{transaction.customer_id}）'
            f'退回 ¥{transaction_amount:.2f}'
        )
        log_type = 'transaction_cancel_consumption'
    elif transaction.type == 'bead_purchase':
        ok, rollback_error = _rollback_bead_purchase_inventory(transaction, operator)
        if not ok:
            return error_response(rollback_error, 400)
        log_description = (
            f'取消买豆交易：记录 {transaction.id}，金额 ¥{transaction_amount:.2f}，库存已同步回滚'
        )
        log_type = 'transaction_cancel_bead_purchase'
    else:
        return error_response('暂不支持取消该交易类型', 400)

    write_log(log_type, log_description, operator=operator)

    db.session.delete(transaction)
    db.session.commit()

    return success_response(
        {
            'transaction_id': transaction_id,
            'customer_id': customer.id,
            'balance': balance.balance
        },
        '交易取消成功'
    )

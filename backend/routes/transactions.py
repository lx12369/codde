from datetime import datetime, timezone
from flask import Blueprint, g, request
import re
from models import db, Transaction, Customer, Balance, Activity, BeadInventoryBalance, BeadInventoryLedger, User
from utils.audit_log import get_operator_name, write_log
from utils.misc_inventory_service import normalize_misc_selections, apply_misc_outbound, apply_misc_inbound
from utils.misc_selection_codec import (
    compose_description_with_misc,
    extract_misc_selections,
    split_description_and_misc
)
from utils.response import success_response, error_response, paginated_response
from utils.decorators import token_required
from utils.bead_inventory_service import generate_entity_id, generate_reference_no
from utils.roles import is_super_admin

transactions_bp = Blueprint('transactions', __name__)
BEAD_PURCHASE_DESC_PATTERN = re.compile(
    r'买豆(?P<movement>入库|出库)：.+?（(?P<material_id>M\d+)）.*?(?P=movement)\s+(?P<grams>\d+(?:\.\d+)?)g，单号\s+(?P<reference_no>[A-Z0-9]+)'
)
TIMER_CONSUMPTION_DESC_PATTERN = re.compile(r'^计时消费')
BEAD_SYSTEM_CUSTOMER_ID = 'C000'
BEAD_SYSTEM_CUSTOMER_NAME = '豆仓损耗'
EXPENSE_SYSTEM_CUSTOMER_ID = 'BEXPENSE'
EXPENSE_SYSTEM_CUSTOMER_NAME = '系统经营支出'


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


def _normalize_transaction_status(value):
    status = str(value or '').strip().lower()
    return status or 'completed'


def _get_current_user():
    current_user_id = getattr(g, 'current_user_id', None)
    if current_user_id is None:
        return None
    return User.query.get(current_user_id)


def _require_super_admin_for_expired_transactions():
    current_user = _get_current_user()
    if not current_user:
        return error_response('用户不存在或未登录', 401)
    if not is_super_admin(current_user):
        return error_response('仅超级管理员可查看过期交易', 403)
    return None


def _mark_transaction_cancelled(transaction, *, operator, reason):
    transaction.status = 'cancelled'
    transaction.cancelled_at = datetime.utcnow()
    transaction.cancel_reason = str(reason or '').strip() or None
    transaction.cancelled_by = str(operator or '').strip() or 'system'


def _mark_transaction_expired(transaction, *, operator, replaced_by_transaction_id=None):
    transaction.status = 'expired'
    transaction.cancelled_at = datetime.utcnow()
    transaction.cancel_reason = (
        f'重新结算后过期，由交易 #{replaced_by_transaction_id} 替换'
        if replaced_by_transaction_id
        else '重新结算后过期'
    )
    transaction.cancelled_by = str(operator or '').strip() or 'system'


def _ensure_system_customer(customer_id, customer_name):
    normalized_id = str(customer_id or '').strip()
    normalized_name = str(customer_name or '').strip() or '系统账户'
    if not normalized_id:
        return None

    customer = Customer.query.filter_by(id=normalized_id).first()
    if customer:
        if not customer.name:
            customer.name = normalized_name
        if normalized_id in {BEAD_SYSTEM_CUSTOMER_ID, EXPENSE_SYSTEM_CUSTOMER_ID}:
            customer.is_deleted = True
        return customer

    customer = Customer(
        id=normalized_id,
        name=normalized_name,
        is_deleted=True
    )
    db.session.add(customer)
    db.session.flush()
    return customer


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
        'movement': match.group('movement'),
        'material_id': match.group('material_id'),
        'grams': grams,
        'reference_no': match.group('reference_no')
    }


def _is_timer_consumption_transaction(transaction):
    if not transaction or transaction.type != 'consumption':
        return False

    description = str(transaction.description or '').strip()
    if not description:
        return False

    return bool(TIMER_CONSUMPTION_DESC_PATTERN.match(description))


def _rollback_bead_purchase_inventory(transaction, operator):
    parsed = _parse_bead_purchase_description(transaction.description)
    if not parsed:
        return False, '买豆交易缺少可回滚的库存信息'

    material_id = parsed['material_id']
    movement = parsed.get('movement') or '入库'
    source_reference_no = parsed['reference_no']
    fallback_grams = parsed['grams']

    source_query = (
        BeadInventoryLedger.query
        .filter(BeadInventoryLedger.material_id == material_id)
        .filter(BeadInventoryLedger.reference_no == source_reference_no)
    )
    if movement == '出库':
        source_ledger = (
            source_query
            .filter(BeadInventoryLedger.action_type.in_(['outbound', 'loss']))
            .order_by(BeadInventoryLedger.created_at.desc())
            .first()
        )
        if not source_ledger:
            return False, '未找到对应出库流水，无法取消买豆交易'
    else:
        source_ledger = (
            source_query
            .filter(BeadInventoryLedger.action_type == 'inbound')
            .order_by(BeadInventoryLedger.created_at.desc())
            .first()
        )
        if not source_ledger:
            return False, '未找到对应入库流水，无法取消买豆交易'

    rollback_grams = abs(float(source_ledger.delta_grams or fallback_grams))
    if rollback_grams <= 0:
        return False, '回滚克数异常，无法取消买豆交易'

    balance = BeadInventoryBalance.query.filter_by(material_id=material_id).first()
    if not balance:
        return False, '未找到豆仓库存记录，无法取消买豆交易'

    current_grams = float(balance.current_grams or 0.0)

    if movement == '出库':
        balance.current_grams = round(current_grams + rollback_grams, 3)
        reverse_reference_no = generate_reference_no('IN')
        reverse_action_type = 'inbound'
        reverse_delta_grams = rollback_grams
        reverse_note = f'回滚出库单号 {source_reference_no}'
    else:
        if current_grams + 1e-9 < rollback_grams:
            return False, '当前库存不足，无法取消该买豆交易'
        balance.current_grams = round(current_grams - rollback_grams, 3)
        reverse_reference_no = generate_reference_no('OUT')
        reverse_action_type = 'outbound'
        reverse_delta_grams = -rollback_grams
        reverse_note = f'回滚入库单号 {source_reference_no}'

    reverse_ledger = BeadInventoryLedger(
        id=generate_entity_id('BL'),
        material_id=material_id,
        action_type=reverse_action_type,
        delta_grams=reverse_delta_grams,
        balance_after_grams=balance.current_grams,
        unit_input='gram',
        unit_count=rollback_grams,
        reference_no=reverse_reference_no,
        reason=f'取消买豆交易（#{transaction.id}）',
        note=reverse_note,
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
    status = str(request.args.get('status', 'all') or 'all').strip().lower()
    customer_id = request.args.get('customer_id', None)
    description_keyword = str(request.args.get('description', '') or '').strip()
    date_start = request.args.get('date_start', None)
    date_end = request.args.get('date_end', None)

    query = Transaction.query

    if transaction_type:
        query = query.filter(Transaction.type == transaction_type)

    if status == 'expired':
        permission_error = _require_super_admin_for_expired_transactions()
        if permission_error:
            return permission_error
        query = query.filter(Transaction.status == 'expired')
    elif status in {'completed', 'cancelled', 'pending'}:
        query = query.filter(Transaction.status == status)
    else:
        query = query.filter(db.or_(Transaction.status.is_(None), Transaction.status != 'expired'))

    if customer_id:
        query = query.filter(Transaction.customer_id == customer_id)

    if description_keyword:
        like_pattern = f'%{description_keyword}%'
        query = query.filter(Transaction.description.ilike(like_pattern))

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

    if status == 'expired':
        query = query.order_by(Transaction.cancelled_at.desc(), Transaction.transaction_time.desc())
    else:
        query = query.order_by(Transaction.transaction_time.desc())

    pagination = query.paginate(page=page, per_page=page_size, error_out=False)

    items = []
    for record in pagination.items:
        item = record.to_dict()
        item['misc_selections'] = extract_misc_selections(record.description)
        items.append(item)
    customer_snapshot_map = _build_customer_snapshot_map([item.get('customer_id') for item in items])
    for item in items:
        customer_id = item.get('customer_id')
        snapshot = customer_snapshot_map.get(customer_id)
        if customer_id == BEAD_SYSTEM_CUSTOMER_ID:
            item['customer_name'] = BEAD_SYSTEM_CUSTOMER_NAME
            item['customer_phone'] = None
            item['customer_wechat'] = None
        elif customer_id == EXPENSE_SYSTEM_CUSTOMER_ID:
            item['customer_name'] = EXPENSE_SYSTEM_CUSTOMER_NAME
            item['customer_phone'] = None
            item['customer_wechat'] = None
        elif snapshot:
            item['customer_name'] = snapshot.get('name')
            item['customer_phone'] = snapshot.get('phone')
            item['customer_wechat'] = snapshot.get('wechat')

    return paginated_response(items, pagination.total, page, page_size)


@transactions_bp.route('/<transaction_id>', methods=['GET'])
@token_required
def get_transaction(transaction_id):
    transaction = Transaction.query.filter_by(id=transaction_id).first()

    if not transaction:
        return error_response('Transaction not found', 404)
    if _normalize_transaction_status(transaction.status) == 'expired':
        permission_error = _require_super_admin_for_expired_transactions()
        if permission_error:
            return permission_error

    payload = transaction.to_dict()
    payload['misc_selections'] = extract_misc_selections(transaction.description)
    return success_response(payload)


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
    misc_selections = normalize_misc_selections(data.get('misc_selections', data.get('miscSelections')))

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

    if misc_selections:
        try:
            apply_misc_outbound(
                misc_selections,
                operator=operator,
                reason=f'消费扣减（客户 {customer.name}（{customer_id}））'
            )
        except ValueError as exc:
            db.session.rollback()
            return error_response(str(exc), 400)

    transaction = Transaction(
        id=new_id,
        customer_id=customer_id,
        type='consumption',
        amount=amount,
        description=compose_description_with_misc(description, misc_selections),
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


@transactions_bp.route('/expense', methods=['POST'])
@token_required
def create_expense():
    data = request.get_json()

    if not data:
        return error_response('No data provided', 400)

    amount = _to_float(data.get('amount'), None)
    description = str(data.get('description') or '').strip()

    if amount is None or amount <= 0:
        return error_response('Valid amount is required', 400)

    if not description:
        return error_response('Description is required', 400)

    operator = get_operator_name(default='unknown')
    customer = _ensure_system_customer(EXPENSE_SYSTEM_CUSTOMER_ID, EXPENSE_SYSTEM_CUSTOMER_NAME)
    if not customer:
        return error_response('Expense customer is unavailable', 500)

    transaction = Transaction(
        id=_generate_transaction_id(),
        customer_id=customer.id,
        type='expense',
        amount=amount,
        description=description,
        operator=operator
    )

    write_log(
        'expense',
        f'经营支出 ¥{amount:.2f}：{description}',
        operator=operator
    )

    db.session.add(transaction)
    db.session.commit()

    return success_response(transaction.to_dict(), 'Expense created successfully', 201)


@transactions_bp.route('/<transaction_id>', methods=['PUT'])
@token_required
def update_transaction(transaction_id):
    transaction = Transaction.query.filter_by(id=transaction_id).first()
    if not transaction:
        return error_response('交易记录不存在', 404)
    current_status = _normalize_transaction_status(transaction.status)
    if current_status == 'cancelled':
        return error_response('已撤销的交易不可重新结算', 400)
    if current_status == 'expired':
        return error_response('过期交易不可重新结算', 400)

    if not _is_timer_consumption_transaction(transaction):
        return error_response('仅支持重新结算计时消费记录', 400)

    data = request.get_json()
    if not data:
        return error_response('No data provided', 400)

    has_amount = 'amount' in data
    has_description = 'description' in data
    has_misc_selections = 'misc_selections' in data or 'miscSelections' in data
    regenerate = bool(data.get('regenerate'))

    if not has_amount and not has_description and not has_misc_selections:
        return error_response('至少提供 amount / description / misc_selections 之一', 400)

    before_amount = _to_float(transaction.amount, 0.0) or 0.0
    before_description, before_misc_selections = split_description_and_misc(transaction.description)

    next_amount = before_amount
    next_description = before_description
    next_misc_selections = before_misc_selections

    if has_amount:
        parsed_amount = _to_float(data.get('amount'), None)
        if parsed_amount is None or parsed_amount <= 0:
            return error_response('Valid amount is required', 400)
        next_amount = round(parsed_amount, 2)

    if has_description:
        parsed_description = str(data.get('description') or '').strip()
        if not parsed_description:
            return error_response('Description is required', 400)
        next_description = parsed_description

    if has_misc_selections:
        next_misc_selections = normalize_misc_selections(
            data.get('misc_selections', data.get('miscSelections'))
        )

    amount_delta = round(next_amount - before_amount, 2)

    balance = Balance.query.filter_by(customer_id=transaction.customer_id).first()
    if not balance:
        balance = Balance(customer_id=transaction.customer_id, balance=0.0)
        db.session.add(balance)

    current_balance = _to_float(balance.balance, 0.0) or 0.0
    if amount_delta > 0 and (current_balance + 1e-9) < amount_delta:
        return error_response('余额不足，无法提高计时消费金额', 400)

    operator = get_operator_name(default='unknown')

    if before_misc_selections != next_misc_selections:
        try:
            if before_misc_selections:
                apply_misc_inbound(
                    before_misc_selections,
                    operator=operator,
                    reason=f'重新结算计时消费回补（交易#{transaction.id}）'
                )
            if next_misc_selections:
                apply_misc_outbound(
                    next_misc_selections,
                    operator=operator,
                    reason=f'重新结算计时消费扣减（交易#{transaction.id}）'
                )
        except ValueError as exc:
            db.session.rollback()
            return error_response(str(exc), 400)

    balance.balance = round(current_balance - amount_delta, 2)

    next_stored_description = compose_description_with_misc(next_description, next_misc_selections)

    customer = Customer.query.filter_by(id=transaction.customer_id).first()
    customer_label = f'{customer.name}（{transaction.customer_id}）' if customer else transaction.customer_id

    changes = []
    if abs(amount_delta) > 1e-9:
        changes.append(f'金额：¥{before_amount:.2f} -> ¥{next_amount:.2f}')
    if before_description != next_description:
        changes.append('描述已更新')
    if before_misc_selections != next_misc_selections:
        changes.append('杂项已更新')

    result_transaction = transaction
    replaced_transaction_id = None

    if regenerate:
        replaced_transaction_id = transaction.id
        new_transaction = Transaction(
            id=_generate_transaction_id(),
            customer_id=transaction.customer_id,
            type=transaction.type,
            amount=next_amount,
            description=next_stored_description,
            operator=operator,
            status='completed'
        )
        db.session.add(new_transaction)
        _mark_transaction_expired(
            transaction,
            operator=operator,
            replaced_by_transaction_id=new_transaction.id
        )
        result_transaction = new_transaction
    else:
        transaction.amount = next_amount
        transaction.description = next_stored_description

    if changes:
        write_log(
            'transaction_regenerate_timer_consumption' if regenerate else 'transaction_update_timer_consumption',
            (
                f'重新结算计时消费：客户 {customer_label}，交易 #{replaced_transaction_id} -> #{result_transaction.id}，'
                f'变更：{"；".join(changes)}'
                if regenerate
                else f'重新结算计时消费：客户 {customer_label}，交易 #{transaction.id}，变更：{"；".join(changes)}'
            ),
            operator=operator
        )
    elif regenerate:
        write_log(
            'transaction_regenerate_timer_consumption',
            f'重新结算计时消费：客户 {customer_label}，交易 #{replaced_transaction_id} -> #{result_transaction.id}',
            operator=operator
        )

    db.session.commit()

    transaction_payload = result_transaction.to_dict()
    transaction_payload['misc_selections'] = next_misc_selections

    return success_response(
        {
            'transaction': transaction_payload,
            'replaced_transaction_id': replaced_transaction_id,
            'customer_id': result_transaction.customer_id,
            'balance': balance.balance
        },
        '交易记录已重新结算并生成新记录' if regenerate else '交易记录已重新结算'
    )


@transactions_bp.route('/<transaction_id>/cancel', methods=['POST'])
@token_required
def cancel_transaction(transaction_id):
    transaction = Transaction.query.filter_by(id=transaction_id).first()
    if not transaction:
        return error_response('交易记录不存在', 404)
    normalized_status = _normalize_transaction_status(transaction.status)
    if normalized_status == 'cancelled':
        return error_response('该交易已撤销，请勿重复操作', 400)
    if normalized_status == 'expired':
        return error_response('过期交易不可取消', 400)

    customer = Customer.query.filter_by(id=transaction.customer_id).first()
    if not customer:
        if transaction.type == 'bead_purchase':
            customer = _ensure_system_customer(transaction.customer_id, BEAD_SYSTEM_CUSTOMER_NAME)
        elif transaction.type == 'expense':
            customer = _ensure_system_customer(transaction.customer_id, EXPENSE_SYSTEM_CUSTOMER_NAME)
        else:
            return error_response('客户不存在', 404)

    balance = Balance.query.filter_by(customer_id=transaction.customer_id).first()
    if not balance:
        balance = Balance(customer_id=transaction.customer_id, balance=0.0)
        db.session.add(balance)

    transaction_amount = _to_float(transaction.amount, 0.0) or 0.0
    bonus_amount = _to_float(transaction.bonus_amount, 0.0) or 0.0
    operator = get_operator_name(default='unknown')
    should_soft_cancel = False

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
        restored_misc = []
        misc_selections = extract_misc_selections(transaction.description)
        if misc_selections:
            try:
                inbound_result = apply_misc_inbound(
                    misc_selections,
                    operator=operator,
                    reason=f'取消消费回补（交易#{transaction.id}）'
                )
                restored_misc = inbound_result.get('details', [])
            except ValueError as exc:
                db.session.rollback()
                return error_response(str(exc), 400)
        log_description = (
            f'取消消费：客户 {customer.name}（{transaction.customer_id}）'
            f'退回 ¥{transaction_amount:.2f}'
        )
        if restored_misc:
            log_description = f'{log_description}，杂项回补：{"；".join(restored_misc)}'
        log_type = 'transaction_cancel_consumption'
    elif transaction.type == 'bead_purchase':
        ok, rollback_error = _rollback_bead_purchase_inventory(transaction, operator)
        if not ok:
            return error_response(rollback_error, 400)
        _mark_transaction_cancelled(
            transaction,
            operator=operator,
            reason='手动取消买豆交易'
        )
        should_soft_cancel = True
        log_description = (
            f'取消买豆交易：记录 {transaction.id}，金额 ¥{transaction_amount:.2f}，库存已同步回滚并标记已撤销'
        )
        log_type = 'transaction_cancel_bead_purchase'
    elif transaction.type == 'expense':
        log_description = (
            f'取消经营支出：记录 {transaction.id}，金额 ¥{transaction_amount:.2f}'
        )
        log_type = 'transaction_cancel_expense'
    else:
        return error_response('暂不支持取消该交易类型', 400)

    write_log(log_type, log_description, operator=operator)

    if not should_soft_cancel:
        db.session.delete(transaction)
    db.session.commit()

    return success_response(
        {
            'transaction_id': transaction_id,
            'customer_id': customer.id,
            'balance': balance.balance,
            'status': transaction.status if should_soft_cancel else None
        },
        '交易撤销成功' if should_soft_cancel else '交易取消成功'
    )



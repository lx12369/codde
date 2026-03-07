import json
import re
from datetime import datetime, timedelta

from flask import Blueprint, g, request

from models import (
    Balance,
    BeadInventoryBalance,
    BeadInventoryLedger,
    BeadMaterial,
    BeadStocktake,
    Customer,
    Log,
    Transaction,
    User,
    db
)
from utils.audit_log import (
    build_filter_options,
    enrich_log_data,
    get_operator_name,
    get_action_types_map,
    get_module_types_map,
    parse_datetime_range,
    write_log
)
from utils.bead_inventory_service import append_ledger, generate_reference_no, get_or_create_balance
from utils.decorators import token_required
from utils.roles import is_super_admin
from utils.misc_inventory_service import apply_misc_inbound
from utils.misc_selection_codec import extract_misc_selections
from utils.response import error_response, success_response

logs_bp = Blueprint('logs', __name__)

MODULE_TYPES_MAP = get_module_types_map()
ACTION_TYPES_MAP = get_action_types_map()
KNOWN_TYPES = sorted({log_type for types in MODULE_TYPES_MAP.values() for log_type in types})
ROLLBACK_SUPPORTED_TYPES = {
    'recharge',
    'consumption',
    'transaction_cancel_recharge',
    'transaction_cancel_consumption',
    'bead_inventory_inbound',
    'bead_inventory_outbound',
    'bead_inventory_loss',
    'bead_inventory_stocktake',
    'bead_material_create',
    'bead_material_update',
    'bead_material_delete'
}
BEAD_INVENTORY_ROLLBACK_TYPES = {
    'rollback_bead_inventory_inbound',
    'rollback_bead_inventory_outbound',
    'rollback_bead_inventory_loss',
    'rollback_bead_inventory_stocktake'
}
BEAD_MATERIAL_ROLLBACK_TYPES = {
    'rollback_bead_material_create',
    'rollback_bead_material_update',
    'rollback_bead_material_delete'
}
MATERIAL_STATUS_VALUES = {'active', 'inactive'}
AMOUNT_TOLERANCE = 0.001

RECHARGE_LOG_PATTERN = re.compile(
    r'客户\s*(?P<name>.+?)（(?P<customer_id>C\d+)）充值\s*¥(?P<amount>\d+(?:\.\d+)?)，赠送\s*¥(?P<bonus>\d+(?:\.\d+)?)'
)
CONSUMPTION_LOG_PATTERN = re.compile(
    r'客户\s*(?P<name>.+?)（(?P<customer_id>C\d+)）消费\s*¥(?P<amount>\d+(?:\.\d+)?)：(?P<description>.+)'
)
CANCEL_RECHARGE_LOG_PATTERN = re.compile(
    r'取消充值：客户\s*(?P<name>.+?)（(?P<customer_id>C\d+)）撤销\s*¥(?P<amount>\d+(?:\.\d+)?)，赠送撤销\s*¥(?P<bonus>\d+(?:\.\d+)?)'
)
CANCEL_CONSUMPTION_LOG_PATTERN = re.compile(
    r'取消消费：客户\s*(?P<name>.+?)（(?P<customer_id>C\d+)）退回\s*¥(?P<amount>\d+(?:\.\d+)?)'
)


def _require_super_admin():
    current_user_id = getattr(g, 'current_user_id', None)
    current_user = User.query.get(current_user_id) if current_user_id is not None else None

    if not current_user:
        return error_response('用户不存在或未登录', 401)

    if not is_super_admin(current_user):
        return error_response('仅超级管理员可执行该操作', 403)

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


def _to_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_non_negative_float(value, default=0.0):
    parsed = _to_float(value, None)
    if parsed is None:
        return default
    if parsed < 0:
        return default
    return float(parsed)


def _to_optional_positive_float(value):
    parsed = _to_float(value, None)
    if parsed is None or parsed <= 0:
        return None
    return float(parsed)


def _normalize_transaction_status(value):
    status = str(value or '').strip().lower()
    return status or 'completed'


def _generate_transaction_id():
    last_transaction = Transaction.query.order_by(Transaction.id.desc()).first()
    if not last_transaction:
        return f'T{int(datetime.utcnow().timestamp() * 1000)}'

    try:
        return f'T{int(str(last_transaction.id)[1:]) + 1:03d}'
    except (TypeError, ValueError, IndexError):
        return f'T{int(datetime.utcnow().timestamp() * 1000)}'


def _extract_log_context(log_record):
    raw = getattr(log_record, 'context', None)
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _is_log_already_rolled_back(log_id):
    marker = f'源日志#{int(log_id)}'
    existed = (
        Log.query
        .filter(Log.type == 'log_rollback')
        .filter(Log.description.ilike(f'%{marker}%'))
        .first()
    )
    return existed is not None


def _parse_recharge_log(description):
    text = str(description or '').strip()
    match = RECHARGE_LOG_PATTERN.search(text)
    if not match:
        return None
    amount = _to_float(match.group('amount'), None)
    bonus = _to_float(match.group('bonus'), None)
    if amount is None or amount <= 0 or bonus is None or bonus < 0:
        return None
    return {
        'customer_id': match.group('customer_id'),
        'amount': amount,
        'bonus': bonus
    }


def _parse_consumption_log(description):
    text = str(description or '').strip()
    match = CONSUMPTION_LOG_PATTERN.search(text)
    if not match:
        return None
    amount = _to_float(match.group('amount'), None)
    if amount is None or amount <= 0:
        return None
    detail = str(match.group('description') or '').strip()
    return {
        'customer_id': match.group('customer_id'),
        'amount': amount,
        'description': detail
    }


def _parse_cancel_recharge_log(description):
    text = str(description or '').strip()
    match = CANCEL_RECHARGE_LOG_PATTERN.search(text)
    if not match:
        return None
    amount = _to_float(match.group('amount'), None)
    bonus = _to_float(match.group('bonus'), None)
    if amount is None or amount <= 0 or bonus is None or bonus < 0:
        return None
    return {
        'customer_id': match.group('customer_id'),
        'amount': amount,
        'bonus': bonus
    }


def _parse_cancel_consumption_log(description):
    text = str(description or '').strip()
    match = CANCEL_CONSUMPTION_LOG_PATTERN.search(text)
    if not match:
        return None
    amount = _to_float(match.group('amount'), None)
    if amount is None or amount <= 0:
        return None
    return {
        'customer_id': match.group('customer_id'),
        'amount': amount
    }


def _resolve_rollback_context(log_record):
    log_type = str(log_record.type or '').strip()
    log_context = _extract_log_context(log_record)

    if log_type == 'recharge':
        return {
            'rollback_type': 'cancel_recharge',
            'rollback_label': '撤销充值',
            'parsed': _parse_recharge_log(log_record.description)
        }

    if log_type == 'consumption':
        return {
            'rollback_type': 'cancel_consumption',
            'rollback_label': '撤销消费',
            'parsed': _parse_consumption_log(log_record.description)
        }

    if log_type == 'transaction_cancel_recharge':
        return {
            'rollback_type': 'restore_recharge',
            'rollback_label': '恢复充值',
            'parsed': _parse_cancel_recharge_log(log_record.description)
        }

    if log_type == 'transaction_cancel_consumption':
        return {
            'rollback_type': 'restore_consumption',
            'rollback_label': '恢复消费',
            'parsed': _parse_cancel_consumption_log(log_record.description)
        }

    if log_type == 'bead_inventory_inbound':
        return {
            'rollback_type': 'rollback_bead_inventory_inbound',
            'rollback_label': '回滚入库',
            'parsed': log_context
        }

    if log_type == 'bead_inventory_outbound':
        return {
            'rollback_type': 'rollback_bead_inventory_outbound',
            'rollback_label': '回滚出库',
            'parsed': log_context
        }

    if log_type == 'bead_inventory_loss':
        return {
            'rollback_type': 'rollback_bead_inventory_loss',
            'rollback_label': '回滚损耗',
            'parsed': log_context
        }

    if log_type == 'bead_inventory_stocktake':
        return {
            'rollback_type': 'rollback_bead_inventory_stocktake',
            'rollback_label': '回滚盘点',
            'parsed': log_context
        }

    if log_type == 'bead_material_create':
        return {
            'rollback_type': 'rollback_bead_material_create',
            'rollback_label': '回滚创建',
            'parsed': log_context
        }

    if log_type == 'bead_material_update':
        return {
            'rollback_type': 'rollback_bead_material_update',
            'rollback_label': '回滚更新',
            'parsed': log_context
        }

    if log_type == 'bead_material_delete':
        return {
            'rollback_type': 'rollback_bead_material_delete',
            'rollback_label': '回滚删除',
            'parsed': log_context
        }

    return {
        'rollback_type': None,
        'rollback_label': '回滚',
        'parsed': None
    }


def _pick_nearest_transaction(candidates, anchor_time):
    if not candidates:
        return None
    anchor = anchor_time or datetime.utcnow()
    ranked = sorted(
        candidates,
        key=lambda item: abs(((item.transaction_time or anchor) - anchor).total_seconds())
    )
    return ranked[0]


def _find_target_transaction_for_log(log_record, context):
    rollback_type = context.get('rollback_type')
    parsed = context.get('parsed') or {}

    if rollback_type not in {'cancel_recharge', 'cancel_consumption'}:
        return None, '该日志不需要匹配原交易'
    if not parsed:
        return None, '日志信息不完整，无法匹配原交易'

    tx_type = 'recharge' if rollback_type == 'cancel_recharge' else 'consumption'
    customer_id = parsed.get('customer_id')
    amount = _to_float(parsed.get('amount'), None)
    if not customer_id or amount is None:
        return None, '日志信息不完整，无法匹配原交易'

    query = (
        Transaction.query
        .filter(Transaction.type == tx_type)
        .filter(Transaction.customer_id == customer_id)
        .filter(Transaction.amount >= amount - AMOUNT_TOLERANCE)
        .filter(Transaction.amount <= amount + AMOUNT_TOLERANCE)
        .filter(db.or_(Transaction.status.is_(None), db.not_(Transaction.status.in_(['cancelled', 'expired']))))
    )

    if tx_type == 'recharge':
        bonus = _to_float(parsed.get('bonus'), None)
        if bonus is None:
            return None, '日志赠送金额缺失，无法匹配充值记录'
        query = (
            query
            .filter(Transaction.bonus_amount >= bonus - AMOUNT_TOLERANCE)
            .filter(Transaction.bonus_amount <= bonus + AMOUNT_TOLERANCE)
        )
    operator = str(log_record.operator or '').strip()
    if operator and operator != '-':
        query = query.filter(Transaction.operator == operator)

    anchor = log_record.timestamp or datetime.utcnow()
    candidates = (
        query
        .filter(Transaction.transaction_time >= anchor - timedelta(days=2))
        .filter(Transaction.transaction_time <= anchor + timedelta(days=2))
        .order_by(Transaction.transaction_time.desc())
        .limit(30)
        .all()
    )

    if not candidates:
        candidates = query.order_by(Transaction.transaction_time.desc()).limit(30).all()

    target = _pick_nearest_transaction(candidates, anchor)
    if not target:
        return None, '未找到可回滚的交易记录'
    return target, None


def _cancel_transaction_record(transaction, operator):
    customer = Customer.query.filter_by(id=transaction.customer_id).first()
    if not customer:
        raise ValueError('客户不存在，无法回滚该交易')

    balance = Balance.query.filter_by(customer_id=transaction.customer_id).first()
    if not balance:
        balance = Balance(customer_id=transaction.customer_id, balance=0.0)
        db.session.add(balance)

    tx_amount = _to_float(transaction.amount, 0.0) or 0.0
    tx_bonus = _to_float(transaction.bonus_amount, 0.0) or 0.0
    current_balance = _to_float(balance.balance, 0.0) or 0.0

    if transaction.type == 'recharge':
        rollback_amount = tx_amount + tx_bonus
        if current_balance + 1e-9 < rollback_amount:
            raise ValueError('余额不足，无法撤销该充值')
        balance.balance = current_balance - rollback_amount
        write_log(
            'transaction_cancel_recharge',
            (
                f'取消充值：客户 {customer.name}（{transaction.customer_id}）'
                f'撤销 ¥{tx_amount:.2f}，赠送撤销 ¥{tx_bonus:.2f}'
            ),
            operator=operator
        )
    elif transaction.type == 'consumption':
        balance.balance = current_balance + tx_amount
        restored_misc = []
        misc_selections = extract_misc_selections(transaction.description)
        if misc_selections:
            inbound_result = apply_misc_inbound(
                misc_selections,
                operator=operator,
                reason=f'日志回滚取消消费回补（交易#{transaction.id}）'
            )
            restored_misc = inbound_result.get('details', [])
        log_description = f'取消消费：客户 {customer.name}（{transaction.customer_id}）退回 ¥{tx_amount:.2f}'
        if restored_misc:
            log_description = f'{log_description}，杂项回补：{"；".join(restored_misc)}'
        write_log(
            'transaction_cancel_consumption',
            log_description,
            operator=operator
        )
    else:
        raise ValueError('仅支持回滚充值或消费交易')

    transaction_id = transaction.id
    db.session.delete(transaction)
    return {
        'transaction_id': transaction_id,
        'customer_id': customer.id,
        'balance': round(float(balance.balance or 0.0), 2)
    }


def _restore_recharge_transaction(log_record, context, operator):
    parsed = context.get('parsed') or {}
    customer_id = str(parsed.get('customer_id') or '').strip()
    amount = _to_float(parsed.get('amount'), None)
    bonus = _to_float(parsed.get('bonus'), None)
    if not customer_id or amount is None or bonus is None:
        raise ValueError('日志信息不完整，无法恢复充值交易')

    customer = Customer.query.filter_by(id=customer_id).first()
    if not customer:
        raise ValueError('客户不存在，无法恢复充值交易')

    balance = Balance.query.filter_by(customer_id=customer_id).first()
    if not balance:
        balance = Balance(customer_id=customer_id, balance=0.0)
        db.session.add(balance)

    transaction = Transaction(
        id=_generate_transaction_id(),
        customer_id=customer_id,
        type='recharge',
        amount=amount,
        bonus_amount=bonus,
        payment_method='rollback',
        description=f'日志回滚恢复（源日志#{log_record.id}）',
        operator=operator,
        status='completed'
    )
    db.session.add(transaction)
    balance.balance = (float(balance.balance or 0.0) + amount + bonus)

    write_log(
        'recharge',
        f'客户 {customer.name}（{customer_id}）充值 ¥{amount:.2f}，赠送 ¥{bonus:.2f}',
        operator=operator
    )

    return {
        'transaction_id': transaction.id,
        'customer_id': customer_id,
        'balance': round(float(balance.balance or 0.0), 2)
    }


def _restore_consumption_transaction(log_record, context, operator):
    parsed = context.get('parsed') or {}
    customer_id = str(parsed.get('customer_id') or '').strip()
    amount = _to_float(parsed.get('amount'), None)
    if not customer_id or amount is None:
        raise ValueError('日志信息不完整，无法恢复消费交易')

    customer = Customer.query.filter_by(id=customer_id).first()
    if not customer:
        raise ValueError('客户不存在，无法恢复消费交易')

    balance = Balance.query.filter_by(customer_id=customer_id).first()
    if not balance:
        balance = Balance(customer_id=customer_id, balance=0.0)
        db.session.add(balance)

    current_balance = float(balance.balance or 0.0)
    if current_balance + 1e-9 < amount:
        raise ValueError('余额不足，无法恢复消费交易')

    transaction = Transaction(
        id=_generate_transaction_id(),
        customer_id=customer_id,
        type='consumption',
        amount=amount,
        description=f'日志回滚恢复（源日志#{log_record.id}）',
        operator=operator,
        status='completed'
    )
    db.session.add(transaction)
    balance.balance = current_balance - amount

    write_log(
        'consumption',
        f'客户 {customer.name}（{customer_id}）消费 ¥{amount:.2f}：日志回滚恢复（源日志#{log_record.id}）',
        operator=operator
    )

    return {
        'transaction_id': transaction.id,
        'customer_id': customer_id,
        'balance': round(float(balance.balance or 0.0), 2)
    }


def _find_linked_bead_purchase_transaction(parsed):
    payload = parsed if isinstance(parsed, dict) else {}
    tx_id = str(payload.get('transaction_id') or '').strip()
    reference_no = str(payload.get('reference_no') or '').strip()

    if tx_id:
        transaction = Transaction.query.filter_by(id=tx_id).first()
        if transaction and transaction.type == 'bead_purchase':
            return transaction

    query = Transaction.query.filter(Transaction.type == 'bead_purchase')
    if reference_no:
        query = query.filter(Transaction.description.ilike(f'%单号 {reference_no}%'))

    return query.order_by(Transaction.transaction_time.desc()).first()


def _validate_bead_inventory_rollback(log_record, parsed):
    if not isinstance(parsed, dict) or not parsed:
        return None, '历史日志缺少快照，暂不支持回滚'

    material_id = str(parsed.get('material_id') or '').strip()
    if not material_id:
        return None, '日志缺少豆料信息，无法回滚'

    material = BeadMaterial.query.filter_by(id=material_id).first()
    if not material:
        return None, '豆料不存在，无法回滚'

    source_delta = _to_float(parsed.get('delta_grams'), None)
    if source_delta is None:
        return None, '日志缺少克重信息，无法回滚'
    if abs(source_delta) < 1e-9:
        return None, '日志克重异常，无法回滚'

    source_reference_no = str(parsed.get('reference_no') or '').strip()
    if not source_reference_no:
        return None, '日志缺少关联单号，无法回滚'
    source_query = (
        BeadInventoryLedger.query
        .filter(BeadInventoryLedger.material_id == material_id)
        .filter(BeadInventoryLedger.reference_no == source_reference_no)
    )
    if log_record.type == 'bead_inventory_inbound':
        source_ledger = source_query.filter(BeadInventoryLedger.action_type == 'inbound').first()
    elif log_record.type in {'bead_inventory_outbound', 'bead_inventory_loss'}:
        source_ledger = source_query.filter(BeadInventoryLedger.action_type.in_(['outbound', 'loss'])).first()
    else:
        source_ledger = source_query.filter(BeadInventoryLedger.action_type == 'stocktake_adjust').first()
    if not source_ledger:
        return None, '未找到原库存流水，无法回滚'

    balance = BeadInventoryBalance.query.filter_by(material_id=material_id).first()
    current_balance = float(balance.current_grams or 0.0) if balance else 0.0
    reverse_delta = round(-source_delta, 3)
    if reverse_delta < 0 and current_balance + 1e-9 < abs(reverse_delta):
        return None, '库存不足，暂不可回滚'

    linked_transaction = None
    if log_record.type in {'bead_inventory_outbound', 'bead_inventory_loss'}:
        linked_transaction = _find_linked_bead_purchase_transaction(parsed)
        if not linked_transaction:
            return None, '未找到关联买豆交易，无法回滚'
        if _normalize_transaction_status(linked_transaction.status) == 'cancelled':
            return None, '关联买豆交易已撤销'

    return {
        'material': material,
        'balance': balance,
        'source_delta': source_delta,
        'reverse_delta': reverse_delta,
        'source_reference_no': source_reference_no,
        'linked_transaction': linked_transaction
    }, None


def _apply_material_snapshot(material, snapshot):
    name = str(snapshot.get('name') or '').strip()
    if name:
        material.name = name
    if 'color_code' in snapshot:
        material.color_code = str(snapshot.get('color_code') or '').strip() or None
    if 'spec' in snapshot:
        material.spec = str(snapshot.get('spec') or '').strip() or None
    if 'brand' in snapshot:
        material.brand = str(snapshot.get('brand') or '').strip() or None
    material.unit = 'gram'
    if 'grams_per_bag' in snapshot:
        material.grams_per_bag = _to_optional_positive_float(snapshot.get('grams_per_bag'))
    if 'grams_per_bottle' in snapshot:
        material.grams_per_bottle = _to_optional_positive_float(snapshot.get('grams_per_bottle'))
    if 'market_price_per_500g' in snapshot:
        material.market_price_per_500g = _to_non_negative_float(
            snapshot.get('market_price_per_500g'),
            default=float(material.market_price_per_500g or 50.0)
        )
    if 'safe_stock' in snapshot:
        material.safe_stock = _to_non_negative_float(
            snapshot.get('safe_stock'),
            default=float(material.safe_stock or 0.0)
        )
    if 'common_color' in snapshot:
        material.common_color = bool(snapshot.get('common_color'))

    if 'status' in snapshot:
        status = str(snapshot.get('status') or '').strip().lower()
        material.status = status if status in MATERIAL_STATUS_VALUES else 'active'


def _validate_bead_material_rollback(log_record, parsed):
    if not isinstance(parsed, dict) or not parsed:
        return None, '历史日志缺少快照，暂不支持回滚'

    log_type = str(log_record.type or '').strip()
    before_snapshot = parsed.get('before') if isinstance(parsed.get('before'), dict) else None
    after_snapshot = parsed.get('after') if isinstance(parsed.get('after'), dict) else None

    if log_type == 'bead_material_create':
        target_snapshot = after_snapshot
        if not target_snapshot:
            return None, '历史日志缺少快照，暂不支持回滚'
        material_id = str(target_snapshot.get('id') or parsed.get('material_id') or '').strip()
        if not material_id:
            return None, '日志缺少豆料快照，无法回滚'
        material = BeadMaterial.query.filter_by(id=material_id).first()
        if not material:
            return None, '豆料不存在，无法回滚创建'
        ledger_count = BeadInventoryLedger.query.filter_by(material_id=material_id).count()
        balance = BeadInventoryBalance.query.filter_by(material_id=material_id).first()
        current_grams = float(balance.current_grams if balance else 0.0)
        if ledger_count > 0 or current_grams > 0:
            return None, '豆料已有库存或流水，无法回滚创建'
        return {
            'material_id': material_id,
            'material': material,
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot
        }, None

    if log_type == 'bead_material_update':
        if not before_snapshot:
            return None, '历史日志缺少快照，暂不支持回滚'
        material_id = str(before_snapshot.get('id') or parsed.get('material_id') or '').strip()
        if not material_id:
            return None, '日志缺少豆料快照，无法回滚'
        material = BeadMaterial.query.filter_by(id=material_id).first()
        if not material:
            return None, '豆料不存在，无法回滚更新'
        return {
            'material_id': material_id,
            'material': material,
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot
        }, None

    if log_type == 'bead_material_delete':
        if not before_snapshot:
            return None, '历史日志缺少快照，暂不支持回滚'
        material_id = str(before_snapshot.get('id') or parsed.get('material_id') or '').strip()
        if not material_id:
            return None, '日志缺少豆料快照，无法回滚'
        existed = BeadMaterial.query.filter_by(id=material_id).first()
        if existed:
            return None, '豆料已存在，无需回滚删除'
        return {
            'material_id': material_id,
            'material': None,
            'before_snapshot': before_snapshot,
            'after_snapshot': after_snapshot
        }, None

    return None, '该豆料日志类型暂不支持回滚'


def _rollback_bead_inventory_log(log_record, context, operator):
    parsed = context.get('parsed') or {}
    validated, error = _validate_bead_inventory_rollback(log_record, parsed)
    if error:
        raise ValueError(error)

    material = validated['material']
    balance = validated['balance'] or get_or_create_balance(material.id)
    reverse_delta = float(validated['reverse_delta'])
    before_balance = float(balance.current_grams or 0.0)
    after_balance = round(before_balance + reverse_delta, 3)
    if after_balance < 0 and after_balance > -0.001:
        after_balance = 0.0
    if after_balance < 0:
        raise ValueError('库存不足，无法执行回滚')

    balance.current_grams = after_balance
    rollback_reference_no = generate_reference_no('RB')
    reverse_action_type = (
        'stocktake_adjust'
        if log_record.type == 'bead_inventory_stocktake'
        else ('inbound' if reverse_delta > 0 else 'outbound')
    )
    source_reference_no = str(validated.get('source_reference_no') or '').strip()
    note_parts = [f'源日志#{log_record.id}']
    if source_reference_no:
        note_parts.insert(0, f'回滚原单号 {source_reference_no}')

    ledger = append_ledger(
        material_id=material.id,
        action_type=reverse_action_type,
        delta_grams=reverse_delta,
        balance_after_grams=after_balance,
        unit_input='gram',
        unit_count=abs(reverse_delta),
        reference_no=rollback_reference_no,
        reason=f'系统日志回滚（{log_record.type}）',
        note='；'.join(note_parts),
        operator=operator
    )

    linked_transaction = validated.get('linked_transaction')
    linked_transaction_id = None
    transaction_status_changed = False
    if linked_transaction:
        if _normalize_transaction_status(linked_transaction.status) == 'cancelled':
            raise ValueError('关联买豆交易已撤销，无法重复回滚')
        linked_transaction.status = 'cancelled'
        linked_transaction.cancelled_at = datetime.utcnow()
        linked_transaction.cancel_reason = f'系统日志回滚：源日志#{log_record.id}'
        linked_transaction.cancelled_by = operator
        linked_transaction_id = linked_transaction.id
        transaction_status_changed = True
        write_log(
            'transaction_cancel_bead_purchase',
            (
                f'取消买豆交易：记录 {linked_transaction.id}，'
                f'金额 ¥{float(linked_transaction.amount or 0.0):.2f}，'
                f'来源系统日志回滚（源日志#{log_record.id}）'
            ),
            operator=operator,
            context={
                'transaction_id': linked_transaction.id,
                'source_log_id': log_record.id,
                'reason': 'log_rollback'
            }
        )

    return {
        'material_id': material.id,
        'reference_no': rollback_reference_no,
        'source_reference_no': source_reference_no or None,
        'before_balance': before_balance,
        'after_balance': after_balance,
        'delta_grams': reverse_delta,
        'ledger_id': ledger.id,
        'linked_transaction_id': linked_transaction_id,
        'transaction_status_changed': transaction_status_changed
    }


def _rollback_bead_material_log(log_record, context):
    parsed = context.get('parsed') or {}
    validated, error = _validate_bead_material_rollback(log_record, parsed)
    if error:
        raise ValueError(error)

    material_id = validated['material_id']
    log_type = str(log_record.type or '').strip()

    if log_type == 'bead_material_create':
        material = validated['material']
        balance = BeadInventoryBalance.query.filter_by(material_id=material_id).first()
        if balance:
            db.session.delete(balance)
        db.session.delete(material)
        return {
            'material_id': material_id,
            'action': 'deleted_created_material'
        }

    if log_type == 'bead_material_update':
        material = validated['material']
        before_snapshot = validated['before_snapshot'] or {}
        _apply_material_snapshot(material, before_snapshot)
        return {
            'material_id': material_id,
            'action': 'restored_material_snapshot'
        }

    if log_type == 'bead_material_delete':
        before_snapshot = validated['before_snapshot'] or {}
        material = BeadMaterial(id=material_id, name=str(before_snapshot.get('name') or '').strip() or material_id)
        _apply_material_snapshot(material, before_snapshot)
        db.session.add(material)

        target_grams = _to_non_negative_float(before_snapshot.get('balance_current_grams'), default=0.0)
        balance = BeadInventoryBalance.query.filter_by(material_id=material_id).first()
        if balance:
            balance.current_grams = target_grams
        else:
            db.session.add(BeadInventoryBalance(material_id=material_id, current_grams=target_grams))

        return {
            'material_id': material_id,
            'action': 'restored_deleted_material'
        }

    raise ValueError('该豆料日志类型暂不支持回滚')


def _build_rollback_meta(log_record):
    log_type = str(log_record.type or '').strip()
    if log_type not in ROLLBACK_SUPPORTED_TYPES:
        return {
            'rollback_supported': False,
            'rollback_label': '回滚',
            'rollback_reason': '该类型暂不支持回滚'
        }

    if _is_log_already_rolled_back(log_record.id):
        return {
            'rollback_supported': False,
            'rollback_label': '已回滚',
            'rollback_reason': '该日志已回滚'
        }

    context = _resolve_rollback_context(log_record)
    rollback_type = context.get('rollback_type')
    parsed = context.get('parsed')

    if rollback_type in {'cancel_recharge', 'cancel_consumption', 'restore_recharge', 'restore_consumption'}:
        if not parsed:
            return {
                'rollback_supported': False,
                'rollback_label': context.get('rollback_label') or '回滚',
                'rollback_reason': '日志信息不完整，无法回滚'
            }

        if rollback_type in {'cancel_recharge', 'cancel_consumption'}:
            target, error = _find_target_transaction_for_log(log_record, context)
            if target is None:
                return {
                    'rollback_supported': False,
                    'rollback_label': context.get('rollback_label') or '回滚',
                    'rollback_reason': error or '未找到可回滚的交易'
                }

        if rollback_type == 'restore_consumption':
            customer_id = str(parsed.get('customer_id') or '').strip()
            customer = Customer.query.filter_by(id=customer_id).first()
            if not customer:
                return {
                    'rollback_supported': False,
                    'rollback_label': context.get('rollback_label') or '回滚',
                    'rollback_reason': '客户不存在，暂不可回滚'
                }
            amount = _to_float(parsed.get('amount'), 0.0) or 0.0
            balance = Balance.query.filter_by(customer_id=customer_id).first()
            current_balance = float(balance.balance or 0.0) if balance else 0.0
            if current_balance + 1e-9 < amount:
                return {
                    'rollback_supported': False,
                    'rollback_label': context.get('rollback_label') or '回滚',
                    'rollback_reason': '余额不足，暂不可恢复消费'
                }
        elif rollback_type == 'restore_recharge':
            customer_id = str(parsed.get('customer_id') or '').strip()
            customer = Customer.query.filter_by(id=customer_id).first()
            if not customer:
                return {
                    'rollback_supported': False,
                    'rollback_label': context.get('rollback_label') or '回滚',
                    'rollback_reason': '客户不存在，暂不可回滚'
                }
    elif rollback_type in BEAD_INVENTORY_ROLLBACK_TYPES:
        _, error = _validate_bead_inventory_rollback(log_record, parsed)
        if error:
            return {
                'rollback_supported': False,
                'rollback_label': context.get('rollback_label') or '回滚',
                'rollback_reason': error
            }
    elif rollback_type in BEAD_MATERIAL_ROLLBACK_TYPES:
        _, error = _validate_bead_material_rollback(log_record, parsed)
        if error:
            return {
                'rollback_supported': False,
                'rollback_label': context.get('rollback_label') or '回滚',
                'rollback_reason': error
            }
    else:
        return {
            'rollback_supported': False,
            'rollback_label': context.get('rollback_label') or '回滚',
            'rollback_reason': '该类型暂不支持回滚'
        }

    return {
        'rollback_supported': True,
        'rollback_label': context.get('rollback_label') or '回滚',
        'rollback_reason': ''
    }


@logs_bp.route('', methods=['GET'])
@token_required
def get_logs():
    permission_error = _require_super_admin()
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
    items = []
    for item in pagination.items:
        payload = enrich_log_data(item.to_dict())
        payload.update(_build_rollback_meta(item))
        items.append(payload)

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


@logs_bp.route('/<int:log_id>/rollback', methods=['POST'])
@token_required
def rollback_log(log_id):
    permission_error = _require_super_admin()
    if permission_error:
        return permission_error

    log_record = Log.query.get(log_id)
    if not log_record:
        return error_response('日志记录不存在', 404)

    if _is_log_already_rolled_back(log_id):
        return error_response('该日志已回滚，请勿重复操作', 400)

    context = _resolve_rollback_context(log_record)
    rollback_type = context.get('rollback_type')

    supported_rollback_types = {
        'cancel_recharge',
        'cancel_consumption',
        'restore_recharge',
        'restore_consumption',
        *BEAD_INVENTORY_ROLLBACK_TYPES,
        *BEAD_MATERIAL_ROLLBACK_TYPES
    }
    if rollback_type not in supported_rollback_types:
        return error_response('该日志类型暂不支持回滚', 400)

    operator = get_operator_name(default='system')

    try:
        if rollback_type in {'cancel_recharge', 'cancel_consumption'}:
            target, error = _find_target_transaction_for_log(log_record, context)
            if target is None:
                return error_response(error or '未找到可回滚交易', 400)
            result = _cancel_transaction_record(target, operator)
            action_text = f'撤销交易 #{result["transaction_id"]}'
        elif rollback_type == 'restore_recharge':
            result = _restore_recharge_transaction(log_record, context, operator)
            action_text = f'恢复充值交易 #{result["transaction_id"]}'
        elif rollback_type == 'restore_consumption':
            result = _restore_consumption_transaction(log_record, context, operator)
            action_text = f'恢复消费交易 #{result["transaction_id"]}'
        elif rollback_type in BEAD_INVENTORY_ROLLBACK_TYPES:
            result = _rollback_bead_inventory_log(log_record, context, operator)
            action_text = f'{context.get("rollback_label") or "回滚"}（豆料 {result.get("material_id")}）'
        else:
            result = _rollback_bead_material_log(log_record, context)
            action_text = f'{context.get("rollback_label") or "回滚"}（豆料 {result.get("material_id")}）'

        write_log(
            'log_rollback',
            f'系统日志回滚：源日志#{log_id}（{log_record.type}）{action_text}',
            operator=operator,
            context={
                'source_log_id': log_id,
                'source_log_type': str(log_record.type or '').strip(),
                'action': action_text,
                'result': result
            }
        )
        db.session.commit()
    except ValueError as error:
        db.session.rollback()
        return error_response(str(error), 400)
    except Exception:
        db.session.rollback()
        return error_response('日志回滚失败，请稍后重试', 500)

    return success_response(
        {
            'log_id': log_id,
            'action': action_text,
            'result': result
        },
        '日志回滚成功'
    )

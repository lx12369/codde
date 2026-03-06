from uuid import uuid4

from flask import Blueprint, request

from models.models import BillingRule, db
from utils.audit_log import get_operator_name, write_log
from utils.decorators import token_required
from utils.response import error_response, success_response

billing_bp = Blueprint('billing', __name__)

RULE_TYPES = ['limited', 'weekday', 'weekend', 'materials', 'overtime', 'misc']

DEFAULT_RULES = {
    'limited': {
        'price1h': 18.9,
        'price2h': 35.8,
        'overtimeFreeMinutes': 10,
        'overtime10to30Fee': 10,
        'overtime30Fee': 18.9,
    },
    'weekday': {
        'singleUnlimited': 53.9,
        'doubleUnlimited': 103.9,
        'singleLimited': 35.9,
    },
    'weekend': {
        'singleUnlimited': 63.9,
        'doubleUnlimited': 123.9,
        'singleLimited': 42.8,
    },
    'materials': {
        'largeImageFee': 5,
        'extraSmallImageFee': 3,
        'extraLargeImageFee': 5,
    },
    'overtime': {
        'ratePerMinute': 0.5,
    },
    'misc': {
        'items': [],
    },
}


def _to_float(value, fallback=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(fallback)


def _to_int(value, fallback=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(fallback)


def _to_bool(value, fallback=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(fallback)

    raw = str(value).strip().lower()
    if raw in {'1', 'true', 'yes', 'y', 'on'}:
        return True
    if raw in {'0', 'false', 'no', 'n', 'off'}:
        return False
    return bool(fallback)


def normalize_limited_rule_data(rule_data):
    merged = dict(DEFAULT_RULES['limited'])
    if isinstance(rule_data, dict):
        merged.update(rule_data)

    price1h = max(0.0, _to_float(merged.get('price1h'), DEFAULT_RULES['limited']['price1h']))
    price2h = max(0.0, _to_float(merged.get('price2h'), DEFAULT_RULES['limited']['price2h']))
    overtime_free_minutes = max(0, _to_int(merged.get('overtimeFreeMinutes'), DEFAULT_RULES['limited']['overtimeFreeMinutes']))
    overtime_10_to_30_fee = max(0.0, _to_float(merged.get('overtime10to30Fee'), DEFAULT_RULES['limited']['overtime10to30Fee']))
    overtime_30_fee = max(0.0, _to_float(merged.get('overtime30Fee'), price1h or DEFAULT_RULES['limited']['overtime30Fee']))

    # Historical data could persist all overtime values as zero by mistake.
    # Auto-heal to default overtime policy when this corrupted pattern appears.
    if (
        overtime_free_minutes == 0
        and overtime_10_to_30_fee == 0
        and overtime_30_fee == 0
        and price1h > 0
    ):
        overtime_free_minutes = DEFAULT_RULES['limited']['overtimeFreeMinutes']
        overtime_10_to_30_fee = DEFAULT_RULES['limited']['overtime10to30Fee']
        overtime_30_fee = price1h

    return {
        'price1h': price1h,
        'price2h': price2h,
        'overtimeFreeMinutes': overtime_free_minutes,
        'overtime10to30Fee': overtime_10_to_30_fee,
        'overtime30Fee': overtime_30_fee,
    }


def normalize_overtime_rule_data(rule_data):
    merged = dict(DEFAULT_RULES['overtime'])
    if isinstance(rule_data, dict):
        merged.update(rule_data)

    return {
        'ratePerMinute': max(0.0, _to_float(merged.get('ratePerMinute'), DEFAULT_RULES['overtime']['ratePerMinute']))
    }


def _new_misc_item_id():
    return f'misc_{uuid4().hex[:12]}'


def normalize_misc_rule_data(rule_data):
    source_items = []
    if isinstance(rule_data, dict):
        source_items = rule_data.get('items', [])
    elif isinstance(rule_data, list):
        source_items = rule_data

    if not isinstance(source_items, list):
        source_items = []

    normalized_items = []
    used_ids = set()
    used_names = set()

    for index, item in enumerate(source_items, start=1):
        if not isinstance(item, dict):
            continue

        name = str(item.get('name') or '').strip()
        if not name:
            continue

        normalized_name_key = name.lower()
        if normalized_name_key in used_names:
            continue
        used_names.add(normalized_name_key)

        item_id = str(item.get('id') or '').strip() or _new_misc_item_id()
        while item_id in used_ids:
            item_id = _new_misc_item_id()
        used_ids.add(item_id)

        unit_label = str(item.get('unit_label') or '').strip() or '个'
        unit_price = round(max(0.0, _to_float(item.get('unit_price'), 0.0)), 2)
        enabled = bool(item.get('enabled', True))
        current_stock = round(max(0.0, _to_float(item.get('current_stock'), 0.0)), 3)
        safe_stock = round(max(0.0, _to_float(item.get('safe_stock'), 0.0)), 3)
        low_stock_alert = _to_bool(item.get('low_stock_alert', True), True)
        sort_order = _to_int(item.get('sort_order'), index)

        normalized_items.append({
            'id': item_id,
            'name': name,
            'unit_price': unit_price,
            'unit_label': unit_label,
            'enabled': enabled,
            'current_stock': current_stock,
            'safe_stock': safe_stock,
            'low_stock_alert': low_stock_alert,
            'sort_order': sort_order,
        })

    normalized_items.sort(key=lambda current: (
        _to_int(current.get('sort_order'), 0),
        str(current.get('name') or ''),
    ))

    for index, item in enumerate(normalized_items, start=1):
        item['sort_order'] = index

    return {
        'items': normalized_items,
    }


def _load_misc_rule():
    rule = BillingRule.query.filter_by(rule_type='misc').first()
    current_data = rule.rule_data if rule and isinstance(rule.rule_data, dict) else DEFAULT_RULES['misc']
    normalized_data = normalize_misc_rule_data(current_data)

    if rule:
        if rule.rule_data != normalized_data:
            rule.rule_data = normalized_data
    else:
        rule = BillingRule(rule_type='misc', rule_data=normalized_data)
        db.session.add(rule)

    return rule, normalized_data


def _find_misc_item(items, item_id):
    target = str(item_id or '').strip()
    if not target:
        return None
    for item in items:
        if str(item.get('id') or '').strip() == target:
            return item
    return None


def _is_low_stock(item):
    if not _to_bool(item.get('low_stock_alert', True), True):
        return False
    current_stock = max(0.0, _to_float(item.get('current_stock'), 0.0))
    safe_stock = max(0.0, _to_float(item.get('safe_stock'), 0.0))
    return current_stock <= safe_stock


def _fmt_quantity(value):
    return f'{max(0.0, _to_float(value, 0.0)):.3f}'.rstrip('0').rstrip('.')


def normalize_common_rule_data(rule_type, rule_data):
    merged = dict(DEFAULT_RULES.get(rule_type, {}))
    if isinstance(rule_data, dict):
        merged.update(rule_data)
    return merged


def normalize_rule_data(rule_type, rule_data):
    if rule_type == 'limited':
        return normalize_limited_rule_data(rule_data)
    if rule_type == 'overtime':
        return normalize_overtime_rule_data(rule_data)
    if rule_type == 'misc':
        return normalize_misc_rule_data(rule_data)
    return normalize_common_rule_data(rule_type, rule_data)


@billing_bp.route('/billing-rules', methods=['GET'])
@token_required
def get_billing_rules():
    rules = BillingRule.query.all()
    existing_types = {rule.rule_type: rule for rule in rules}

    result = {}
    should_commit = False

    for rule_type in RULE_TYPES:
        if rule_type in existing_types:
            current_data = existing_types[rule_type].rule_data
            normalized_data = normalize_rule_data(rule_type, current_data)
            result[rule_type] = normalized_data
            if normalized_data != current_data:
                existing_types[rule_type].rule_data = normalized_data
                should_commit = True
        else:
            result[rule_type] = normalize_rule_data(rule_type, DEFAULT_RULES.get(rule_type, {}))

    if should_commit:
        db.session.commit()

    return success_response(result)


@billing_bp.route('/billing-rules', methods=['PUT'])
@token_required
def update_billing_rules():
    data = request.get_json()

    if not data:
        return error_response('Request body is required', 400)

    updated_rules = {}

    for rule_type in RULE_TYPES:
        if rule_type not in data:
            continue

        rule_data = data[rule_type]
        if rule_type == 'misc':
            if not isinstance(rule_data, (dict, list)):
                return error_response('Invalid data format for misc', 400)
        elif not isinstance(rule_data, dict):
            return error_response(f'Invalid data format for {rule_type}', 400)

        normalized_data = normalize_rule_data(rule_type, rule_data)

        rule = BillingRule.query.filter_by(rule_type=rule_type).first()
        if rule:
            rule.rule_data = normalized_data
        else:
            rule = BillingRule(rule_type=rule_type, rule_data=normalized_data)
            db.session.add(rule)

        updated_rules[rule_type] = normalized_data

    if updated_rules:
        operator = get_operator_name(default='unknown')
        rule_names = '、'.join(sorted(updated_rules.keys()))
        write_log(
            'billing_rule_update',
            f'更新计费规则：{rule_names}',
            operator=operator,
        )

    db.session.commit()

    rules = BillingRule.query.all()
    existing_types = {rule.rule_type: rule for rule in rules}
    result = {}
    for rule_type in RULE_TYPES:
        if rule_type in existing_types:
            result[rule_type] = normalize_rule_data(rule_type, existing_types[rule_type].rule_data)
        else:
            result[rule_type] = normalize_rule_data(rule_type, DEFAULT_RULES.get(rule_type, {}))

    return success_response(result, 'Billing rules updated successfully')


@billing_bp.route('/billing-rules/misc-items/<item_id>/inbound', methods=['POST'])
@token_required
def inbound_misc_item_stock(item_id):
    data = request.get_json() or {}
    quantity = _to_float(data.get('quantity'), None)
    note = str(data.get('note') or '').strip()

    if quantity is None or quantity <= 0:
        return error_response('入库数量必须大于 0', 400)

    rule, normalized_misc = _load_misc_rule()
    items = normalized_misc.get('items', [])
    item = _find_misc_item(items, item_id)
    if not item:
        return error_response('杂项不存在', 404)

    before_stock = max(0.0, _to_float(item.get('current_stock'), 0.0))
    item['current_stock'] = round(before_stock + quantity, 3)
    normalized_misc = normalize_misc_rule_data(normalized_misc)
    rule.rule_data = normalized_misc

    operator = get_operator_name(default='unknown')
    detail_note = f'，备注：{note}' if note else ''
    write_log(
        'misc_inventory_inbound',
        (
            f'杂项入库：{item.get("name")}（{item.get("id")}）'
            f'+{_fmt_quantity(quantity)}{item.get("unit_label") or "个"}，'
            f'库存 {_fmt_quantity(before_stock)} -> {_fmt_quantity(item.get("current_stock"))}'
            f'{detail_note}'
        ),
        operator=operator,
    )

    db.session.commit()

    latest_item = _find_misc_item(normalized_misc.get('items', []), item_id)
    return success_response(
        {
            'misc': normalized_misc,
            'item': latest_item,
            'is_low_stock': _is_low_stock(latest_item or {}),
        },
        '杂项入库成功',
    )


@billing_bp.route('/billing-rules/misc-items/<item_id>/outbound', methods=['POST'])
@token_required
def outbound_misc_item_stock(item_id):
    data = request.get_json() or {}
    quantity = _to_float(data.get('quantity'), None)
    note = str(data.get('note') or '').strip()

    if quantity is None or quantity <= 0:
        return error_response('出库数量必须大于 0', 400)

    rule, normalized_misc = _load_misc_rule()
    items = normalized_misc.get('items', [])
    item = _find_misc_item(items, item_id)
    if not item:
        return error_response('杂项不存在', 404)

    before_stock = max(0.0, _to_float(item.get('current_stock'), 0.0))
    if before_stock + 1e-9 < quantity:
        unit_label = item.get('unit_label') or '个'
        return error_response(
            f'库存不足：当前库存 {_fmt_quantity(before_stock)}{unit_label}',
            400
        )

    item['current_stock'] = round(max(0.0, before_stock - quantity), 3)
    normalized_misc = normalize_misc_rule_data(normalized_misc)
    rule.rule_data = normalized_misc

    operator = get_operator_name(default='unknown')
    detail_note = f'，备注：{note}' if note else ''
    write_log(
        'misc_inventory_outbound',
        (
            f'杂项出库：{item.get("name")}（{item.get("id")}）'
            f'-{_fmt_quantity(quantity)}{item.get("unit_label") or "个"}，'
            f'库存 {_fmt_quantity(before_stock)} -> {_fmt_quantity(item.get("current_stock"))}'
            f'{detail_note}'
        ),
        operator=operator,
    )

    db.session.commit()

    latest_item = _find_misc_item(normalized_misc.get('items', []), item_id)
    return success_response(
        {
            'misc': normalized_misc,
            'item': latest_item,
            'is_low_stock': _is_low_stock(latest_item or {}),
        },
        '杂项出库成功',
    )

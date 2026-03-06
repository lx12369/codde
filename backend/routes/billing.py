import re
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
        'unlimited_packages': [
            {
                'id': 'weekday_unlimited_1p',
                'code': 'weekdaySingleUnlimited',
                'label': '工作日单人不限时不限板',
                'people_count': 1,
                'price': 53.9,
                'enabled': True,
                'sort_order': 1,
            },
            {
                'id': 'weekday_unlimited_2p',
                'code': 'weekdayDoubleUnlimited',
                'label': '工作日双人不限时不限板',
                'people_count': 2,
                'price': 103.9,
                'enabled': True,
                'sort_order': 2,
            },
        ],
        'singleLimited': 35.9,
    },
    'weekend': {
        'unlimited_packages': [
            {
                'id': 'weekend_unlimited_1p',
                'code': 'weekendSingleUnlimited',
                'label': '周末单人不限时不限板',
                'people_count': 1,
                'price': 63.9,
                'enabled': True,
                'sort_order': 1,
            },
            {
                'id': 'weekend_unlimited_2p',
                'code': 'weekendDoubleUnlimited',
                'label': '周末双人不限时不限板',
                'people_count': 2,
                'price': 123.9,
                'enabled': True,
                'sort_order': 2,
            },
        ],
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

PACKAGE_CODE_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{2,64}$')
DAY_TYPE_LABELS = {
    'weekday': '工作日',
    'weekend': '周末',
}
LEGACY_DAY_TYPE_MAP = {
    'weekday': {
        'singleUnlimited': 'weekdaySingleUnlimited',
        'doubleUnlimited': 'weekdayDoubleUnlimited',
        'singleLimited': 'weekdaySingleLimited',
    },
    'weekend': {
        'singleUnlimited': 'weekendSingleUnlimited',
        'doubleUnlimited': 'weekendDoubleUnlimited',
        'singleLimited': 'weekendSingleLimited',
    },
}
LEGACY_PLAN_META = {
    'weekdaySingleUnlimited': {'day_type': 'weekday', 'people_count': 1, 'label': '工作日单人不限时不限板'},
    'weekdayDoubleUnlimited': {'day_type': 'weekday', 'people_count': 2, 'label': '工作日双人不限时不限板'},
    'weekdaySingleLimited': {'day_type': 'weekday', 'people_count': 1, 'limited': True, 'label': '工作日单人不限时限板'},
    'weekendSingleUnlimited': {'day_type': 'weekend', 'people_count': 1, 'label': '周末单人不限时不限板'},
    'weekendDoubleUnlimited': {'day_type': 'weekend', 'people_count': 2, 'label': '周末双人不限时不限板'},
    'weekendSingleLimited': {'day_type': 'weekend', 'people_count': 1, 'limited': True, 'label': '周末单人不限时限板'},
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


def _clone_default_unlimited_packages(day_type):
    default_day = DEFAULT_RULES.get(day_type, {})
    source = default_day.get('unlimited_packages', [])
    if not isinstance(source, list):
        return []
    return [dict(item) for item in source if isinstance(item, dict)]


def _build_default_unlimited_label(day_type, people_count):
    day_label = DAY_TYPE_LABELS.get(day_type, day_type)
    safe_people = max(1, _to_int(people_count, 1))
    return f'{day_label}{safe_people}人不限时不限板'


def _default_unlimited_code(day_type, people_count, index):
    legacy_map = LEGACY_DAY_TYPE_MAP.get(day_type, {})
    if max(1, people_count) == 1 and legacy_map.get('singleUnlimited'):
        return legacy_map.get('singleUnlimited')
    if max(1, people_count) == 2 and legacy_map.get('doubleUnlimited'):
        return legacy_map.get('doubleUnlimited')
    safe_index = max(1, _to_int(index, 1))
    safe_people = max(1, _to_int(people_count, safe_index))
    return f'{day_type}Unlimited{safe_people}P'


def _infer_people_count_from_code(code):
    normalized = str(code or '').strip()
    meta = LEGACY_PLAN_META.get(normalized)
    if meta and meta.get('people_count'):
        return max(1, _to_int(meta.get('people_count'), 1))

    matched = re.search(r'(\d+)', normalized)
    if not matched:
        return None

    value = _to_int(matched.group(1), 0)
    if value < 1:
        return None
    return value


def _sanitize_package_code(day_type, code, people_count, index):
    normalized = re.sub(r'[^a-zA-Z0-9_-]+', '', str(code or '').strip())
    if PACKAGE_CODE_PATTERN.match(normalized):
        return normalized
    return _default_unlimited_code(day_type, people_count, index)


def _find_unlimited_package_by_people_count(unlimited_packages, people_count):
    safe_people = max(1, _to_int(people_count, 1))
    for package in unlimited_packages:
        if max(1, _to_int(package.get('people_count'), 1)) == safe_people:
            return package
    return None


def _normalize_day_rule_data(day_type, rule_data, strict=False):
    if day_type not in {'weekday', 'weekend'}:
        return normalize_common_rule_data(day_type, rule_data)

    day_label = DAY_TYPE_LABELS.get(day_type, day_type)
    source_data = rule_data if isinstance(rule_data, dict) else {}
    default_day_rule = DEFAULT_RULES.get(day_type, {})

    raw_single_limited = _to_float(source_data.get('singleLimited'), None)
    if raw_single_limited is None:
        legacy_single_limited = source_data.get('singleLimitedBoard')
        raw_single_limited = _to_float(legacy_single_limited, None)
    if raw_single_limited is None:
        raw_single_limited = _to_float(default_day_rule.get('singleLimited'), 0.0)

    if strict and raw_single_limited < 0:
        raise ValueError(f'{day_label}单人限板价格不能小于 0')
    single_limited = round(max(0.0, raw_single_limited), 2)

    source_packages = source_data.get('unlimited_packages')
    if not isinstance(source_packages, list):
        source_packages = _clone_default_unlimited_packages(day_type)
        legacy_single_unlimited = _to_float(source_data.get('singleUnlimited'), None)
        legacy_double_unlimited = _to_float(source_data.get('doubleUnlimited'), None)

        for package in source_packages:
            people_count = max(1, _to_int(package.get('people_count'), 1))
            if people_count == 1 and legacy_single_unlimited is not None:
                package['price'] = legacy_single_unlimited
            elif people_count == 2 and legacy_double_unlimited is not None:
                package['price'] = legacy_double_unlimited

    normalized_packages = []
    used_codes = set()
    used_ids = set()

    for index, item in enumerate(source_packages, start=1):
        if not isinstance(item, dict):
            if strict:
                raise ValueError(f'{day_label}不限板套餐第 {index} 项格式无效')
            continue

        raw_code = str(item.get('code') or '').strip()
        inferred_people = _infer_people_count_from_code(raw_code)
        raw_people_count = item.get('people_count', item.get('peopleCount'))
        if raw_people_count is None:
            raw_people_count = inferred_people if inferred_people is not None else 1
        people_count = _to_int(raw_people_count, 1)
        if people_count < 1:
            if strict:
                raise ValueError(f'{day_label}不限板套餐第 {index} 项人数必须大于等于 1')
            people_count = 1

        raw_price = _to_float(item.get('price'), None)
        if raw_price is None:
            if strict:
                raise ValueError(f'{day_label}不限板套餐第 {index} 项价格无效')
            raw_price = 0.0
        if strict and raw_price < 0:
            raise ValueError(f'{day_label}不限板套餐第 {index} 项价格不能小于 0')
        price = round(max(0.0, raw_price), 2)

        sort_order = _to_int(item.get('sort_order', item.get('sortOrder', index)), index)
        if strict and sort_order < 0:
            raise ValueError(f'{day_label}不限板套餐第 {index} 项排序值无效')

        label = str(item.get('label') or '').strip() or _build_default_unlimited_label(day_type, people_count)
        package_id = str(item.get('id') or '').strip() or f'{day_type}_pkg_{uuid4().hex[:12]}'
        while package_id in used_ids:
            package_id = f'{day_type}_pkg_{uuid4().hex[:12]}'
        used_ids.add(package_id)

        normalized_code = raw_code or _default_unlimited_code(day_type, people_count, index)
        normalized_code = _sanitize_package_code(day_type, normalized_code, people_count, index)
        if normalized_code in used_codes:
            if strict:
                raise ValueError(f'{day_label}不限板套餐编码重复：{normalized_code}')
            continue
        used_codes.add(normalized_code)

        normalized_packages.append({
            'id': package_id,
            'code': normalized_code,
            'label': label,
            'people_count': people_count,
            'price': price,
            'enabled': _to_bool(item.get('enabled', True), True),
            'sort_order': sort_order,
        })

    if not normalized_packages:
        if strict:
            raise ValueError(f'{day_label}至少保留一个不限板套餐')
        normalized_packages = _clone_default_unlimited_packages(day_type)
        for index, package in enumerate(normalized_packages, start=1):
            package['id'] = str(package.get('id') or f'{day_type}_pkg_{uuid4().hex[:12]}').strip() or f'{day_type}_pkg_{uuid4().hex[:12]}'
            package['code'] = _sanitize_package_code(
                day_type,
                package.get('code'),
                _to_int(package.get('people_count'), 1),
                index
            )
            package['label'] = str(package.get('label') or '').strip() or _build_default_unlimited_label(day_type, package.get('people_count'))
            package['people_count'] = max(1, _to_int(package.get('people_count'), 1))
            package['price'] = round(max(0.0, _to_float(package.get('price'), 0.0)), 2)
            package['enabled'] = _to_bool(package.get('enabled', True), True)
            package['sort_order'] = _to_int(package.get('sort_order'), index)

    normalized_packages.sort(key=lambda current: (
        _to_int(current.get('sort_order'), 0),
        _to_int(current.get('people_count'), 0),
        str(current.get('code') or '')
    ))
    for index, package in enumerate(normalized_packages, start=1):
        package['sort_order'] = index

    if not any(_to_bool(package.get('enabled', True), True) for package in normalized_packages):
        if strict:
            raise ValueError(f'{day_label}至少保留一个启用的不限板套餐')
        normalized_packages[0]['enabled'] = True

    single_unlimited = _find_unlimited_package_by_people_count(normalized_packages, 1)
    double_unlimited = _find_unlimited_package_by_people_count(normalized_packages, 2)
    fallback_first = normalized_packages[0]

    return {
        'singleLimited': single_limited,
        'unlimited_packages': normalized_packages,
        # 兼容历史前端字段，避免旧页面因升级后拿不到价格而异常。
        'singleUnlimited': round(max(0.0, _to_float((single_unlimited or fallback_first).get('price'), 0.0)), 2),
        'doubleUnlimited': round(max(0.0, _to_float((double_unlimited or single_unlimited or fallback_first).get('price'), 0.0)), 2),
    }


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


def normalize_rule_data(rule_type, rule_data, strict=False):
    if rule_type == 'limited':
        return normalize_limited_rule_data(rule_data)
    if rule_type == 'overtime':
        return normalize_overtime_rule_data(rule_data)
    if rule_type == 'misc':
        return normalize_misc_rule_data(rule_data)
    if rule_type in {'weekday', 'weekend'}:
        return _normalize_day_rule_data(rule_type, rule_data, strict=strict)
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
            normalized_data = normalize_rule_data(rule_type, current_data, strict=False)
            result[rule_type] = normalized_data
            if normalized_data != current_data:
                existing_types[rule_type].rule_data = normalized_data
                should_commit = True
        else:
            result[rule_type] = normalize_rule_data(rule_type, DEFAULT_RULES.get(rule_type, {}), strict=False)

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

        try:
            normalized_data = normalize_rule_data(rule_type, rule_data, strict=True)
        except ValueError as exc:
            return error_response(str(exc), 400)

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
            result[rule_type] = normalize_rule_data(rule_type, existing_types[rule_type].rule_data, strict=False)
        else:
            result[rule_type] = normalize_rule_data(rule_type, DEFAULT_RULES.get(rule_type, {}), strict=False)

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

from models.models import BillingRule, db
from routes.billing import normalize_misc_rule_data
from utils.audit_log import write_log
from utils.misc_selection_codec import normalize_misc_selections


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _fmt_quantity(value):
    return f'{max(0.0, _to_float(value, 0.0)):.3f}'.rstrip('0').rstrip('.')


def _load_misc_rule():
    rule = BillingRule.query.filter_by(rule_type='misc').first()
    current_data = rule.rule_data if rule and isinstance(rule.rule_data, dict) else {'items': []}
    normalized_data = normalize_misc_rule_data(current_data)

    if rule:
        if rule.rule_data != normalized_data:
            rule.rule_data = normalized_data
    else:
        rule = BillingRule(rule_type='misc', rule_data=normalized_data)
        db.session.add(rule)

    return rule, normalized_data


def apply_misc_outbound(selections, operator='unknown', reason='消费出库'):
    normalized = normalize_misc_selections(selections)
    if not normalized:
        return {
            'applied': False,
            'details': [],
            'items': []
        }

    rule, misc_data = _load_misc_rule()
    items = misc_data.get('items', [])
    item_map = {
        str(item.get('id') or '').strip(): item
        for item in items
        if isinstance(item, dict)
    }

    for item_id, quantity in normalized.items():
        item = item_map.get(item_id)
        if not item:
            raise ValueError(f'杂项不存在：{item_id}')

        current_stock = max(0.0, _to_float(item.get('current_stock'), 0.0))
        if current_stock + 1e-9 < quantity:
            name = str(item.get('name') or item_id)
            unit_label = str(item.get('unit_label') or '个')
            raise ValueError(f'杂项库存不足：{name}，当前库存 {_fmt_quantity(current_stock)}{unit_label}')

    details = []
    consumed_items = []
    for item_id, quantity in normalized.items():
        item = item_map[item_id]
        before_stock = max(0.0, _to_float(item.get('current_stock'), 0.0))
        after_stock = round(max(0.0, before_stock - quantity), 3)
        item['current_stock'] = after_stock

        name = str(item.get('name') or item_id)
        unit_label = str(item.get('unit_label') or '个')
        details.append(
            f'{name}-{_fmt_quantity(quantity)}{unit_label}（{_fmt_quantity(before_stock)}->{_fmt_quantity(after_stock)}）'
        )
        consumed_items.append({
            'id': item_id,
            'name': name,
            'quantity': quantity,
            'unit_label': unit_label,
            'before_stock': before_stock,
            'after_stock': after_stock
        })

    normalized_after = normalize_misc_rule_data(misc_data)
    rule.rule_data = normalized_after

    if details:
        write_log(
            'misc_inventory_outbound',
            f'{reason}：{"；".join(details)}',
            operator=operator
        )

    return {
        'applied': bool(details),
        'details': details,
        'items': consumed_items
    }


def apply_misc_inbound(selections, operator='unknown', reason='库存回补'):
    normalized = normalize_misc_selections(selections)
    if not normalized:
        return {
            'applied': False,
            'details': [],
            'items': []
        }

    rule, misc_data = _load_misc_rule()
    items = misc_data.get('items', [])
    item_map = {
        str(item.get('id') or '').strip(): item
        for item in items
        if isinstance(item, dict)
    }

    details = []
    restored_items = []
    for item_id, quantity in normalized.items():
        item = item_map.get(item_id)
        if not item:
            raise ValueError(f'杂项不存在：{item_id}')

        before_stock = max(0.0, _to_float(item.get('current_stock'), 0.0))
        after_stock = round(max(0.0, before_stock + quantity), 3)
        item['current_stock'] = after_stock

        name = str(item.get('name') or item_id)
        unit_label = str(item.get('unit_label') or '个')
        details.append(
            f'{name}+{_fmt_quantity(quantity)}{unit_label}（{_fmt_quantity(before_stock)}->{_fmt_quantity(after_stock)}）'
        )
        restored_items.append({
            'id': item_id,
            'name': name,
            'quantity': quantity,
            'unit_label': unit_label,
            'before_stock': before_stock,
            'after_stock': after_stock
        })

    normalized_after = normalize_misc_rule_data(misc_data)
    rule.rule_data = normalized_after

    if details:
        write_log(
            'misc_inventory_inbound',
            f'{reason}：{"；".join(details)}',
            operator=operator
        )

    return {
        'applied': bool(details),
        'details': details,
        'items': restored_items
    }

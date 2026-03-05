from datetime import datetime, timedelta
import uuid
from collections import Counter

from models import db, BeadMaterial, BeadInventoryBalance, BeadInventoryLedger


UNIT_GRAM_ALIASES = {'gram', 'grams', 'g', '克'}
UNIT_BAG_ALIASES = {'bag', 'bags', '袋'}
UNIT_BOTTLE_ALIASES = {'bottle', 'bottles', '瓶'}


def normalize_unit(unit):
    normalized = str(unit or 'gram').strip().lower()
    if normalized in UNIT_GRAM_ALIASES:
        return 'gram'
    if normalized in UNIT_BAG_ALIASES:
        return 'bag'
    if normalized in UNIT_BOTTLE_ALIASES:
        return 'bottle'
    return None


def parse_positive_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return number


def _resolve_global_conversion_standard(field_name):
    column = getattr(BeadMaterial, field_name)
    rows = (
        db.session.query(column)
        .filter(column.isnot(None))
        .all()
    )
    values = []
    for row in rows:
        parsed = parse_positive_number(row[0])
        if parsed is not None:
            values.append(round(parsed, 6))
    if not values:
        return None

    counter = Counter(values)
    most_common = counter.most_common()
    if len(most_common) > 1 and most_common[0][1] == most_common[1][1]:
        return None
    return float(most_common[0][0])


def convert_to_grams(material, unit, quantity):
    normalized_unit = normalize_unit(unit)
    normalized_quantity = parse_positive_number(quantity)
    if normalized_quantity is None:
        raise ValueError('数量必须是大于 0 的数字')
    if not normalized_unit:
        raise ValueError('单位仅支持克、袋、瓶')

    if normalized_unit == 'gram':
        return round(normalized_quantity, 3), normalized_unit

    if normalized_unit == 'bag':
        grams_per_bag = parse_positive_number(material.grams_per_bag)
        if grams_per_bag is None:
            grams_per_bag = _resolve_global_conversion_standard('grams_per_bag')
        if grams_per_bag is None:
            raise ValueError('该豆料未配置每袋克重，无法按袋换算')
        return round(normalized_quantity * grams_per_bag, 3), normalized_unit

    grams_per_bottle = parse_positive_number(material.grams_per_bottle)
    if grams_per_bottle is None:
        grams_per_bottle = _resolve_global_conversion_standard('grams_per_bottle')
    if grams_per_bottle is None:
        raise ValueError('该豆料未配置每瓶克重，无法按瓶换算')
    return round(normalized_quantity * grams_per_bottle, 3), normalized_unit


def generate_entity_id(prefix):
    return f'{prefix}{uuid.uuid4().hex[:16]}'


def generate_reference_no(prefix):
    stamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    return f'{prefix}{stamp}{uuid.uuid4().hex[:4].upper()}'


def get_or_create_balance(material_id):
    balance = BeadInventoryBalance.query.filter_by(material_id=material_id).first()
    if balance:
        return balance

    balance = BeadInventoryBalance(material_id=material_id, current_grams=0.0)
    db.session.add(balance)
    db.session.flush()
    return balance


def append_ledger(
    *,
    material_id,
    action_type,
    delta_grams,
    balance_after_grams,
    unit_input,
    unit_count,
    reference_no,
    reason,
    note,
    operator
):
    ledger = BeadInventoryLedger(
        id=generate_entity_id('BL'),
        material_id=material_id,
        action_type=action_type,
        delta_grams=float(delta_grams),
        balance_after_grams=float(balance_after_grams),
        unit_input=unit_input,
        unit_count=float(unit_count) if unit_count is not None else None,
        reference_no=reference_no,
        reason=(str(reason or '').strip() or None),
        note=(str(note or '').strip() or None),
        operator=(str(operator or '').strip() or 'system')
    )
    db.session.add(ledger)
    return ledger


def calc_recent_avg_daily_outbound_grams(material_id, days=7):
    if days <= 0:
        return 0.0

    start_time = datetime.utcnow() - timedelta(days=days)
    rows = (
        BeadInventoryLedger.query
        .filter(BeadInventoryLedger.material_id == material_id)
        .filter(BeadInventoryLedger.created_at >= start_time)
        .filter(BeadInventoryLedger.action_type.in_(['outbound', 'loss']))
        .all()
    )

    total = 0.0
    for row in rows:
        delta = float(row.delta_grams or 0.0)
        if delta < 0:
            total += abs(delta)

    return round(total / days, 3)

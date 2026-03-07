from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, Numeric

from models.models import (
    db,
    User,
    RevokedToken,
    Customer,
    Balance,
    Transaction,
    Activity,
    BillingRule,
    SeatLayoutConfig,
    ActiveTimer,
    BeadMaterial,
    BeadInventoryBalance,
    BeadInventoryLedger,
    BeadStocktake,
    Log
)


BACKUP_SCHEMA_VERSION = 4

MODEL_REGISTRY = {
    'users': User,
    'revoked_tokens': RevokedToken,
    'customers': Customer,
    'balances': Balance,
    'transactions': Transaction,
    'activities': Activity,
    'billing_rules': BillingRule,
    'seat_layout_configs': SeatLayoutConfig,
    'active_timers': ActiveTimer,
    'bead_materials': BeadMaterial,
    'bead_inventory_balances': BeadInventoryBalance,
    'bead_inventory_ledgers': BeadInventoryLedger,
    'bead_stocktakes': BeadStocktake,
    'logs': Log
}

BACKUP_ORDER = [
    'users',
    'revoked_tokens',
    'customers',
    'balances',
    'transactions',
    'activities',
    'billing_rules',
    'seat_layout_configs',
    'active_timers',
    'bead_materials',
    'bead_inventory_balances',
    'bead_inventory_ledgers',
    'bead_stocktakes',
    'logs'
]

RESTORE_INSERT_ORDER = [
    'users',
    'revoked_tokens',
    'customers',
    'activities',
    'billing_rules',
    'seat_layout_configs',
    'balances',
    'transactions',
    'active_timers',
    'bead_materials',
    'bead_inventory_balances',
    'bead_inventory_ledgers',
    'bead_stocktakes',
    'logs'
]

RESTORE_DELETE_ORDER = [
    'revoked_tokens',
    'logs',
    'bead_stocktakes',
    'bead_inventory_ledgers',
    'bead_inventory_balances',
    'bead_materials',
    'active_timers',
    'transactions',
    'balances',
    'billing_rules',
    'seat_layout_configs',
    'activities',
    'customers',
    'users'
]


def build_stats_template():
    return {
        key: 0 for key in BACKUP_ORDER
    }


def serialize_value(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def serialize_row(model, row):
    return {
        column.name: serialize_value(getattr(row, column.name))
        for column in model.__table__.columns
    }


def parse_datetime_value(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith('Z'):
            text = f'{text[:-1]}+00:00'
        dt = datetime.fromisoformat(text)

    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def parse_date_value(value):
    if value is None:
        return None

    if isinstance(value, date) and not isinstance(value, datetime):
        return value

    text = str(value).strip()
    if not text:
        return None

    try:
        return date.fromisoformat(text)
    except ValueError:
        dt = parse_datetime_value(text)
        return dt.date() if dt else None


def deserialize_value(column, value):
    if value is None:
        return None

    column_type = column.type

    if isinstance(column_type, DateTime):
        return parse_datetime_value(value)

    if isinstance(column_type, Date):
        return parse_date_value(value)

    if isinstance(column_type, Boolean):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}

    if isinstance(column_type, Integer):
        return int(value)

    if isinstance(column_type, (Float, Numeric)):
        return float(value)

    return value


def extract_snapshot(payload):
    if not isinstance(payload, dict):
        return None

    wrapped_data = payload.get('data')
    if isinstance(wrapped_data, dict):
        nested_snapshot = wrapped_data.get('snapshot')
        if isinstance(nested_snapshot, dict):
            return nested_snapshot

    snapshot = payload.get('snapshot')
    if isinstance(snapshot, dict):
        return snapshot

    return payload


def export_snapshot_payload():
    snapshot = {}
    stats = build_stats_template()

    for key in BACKUP_ORDER:
        model = MODEL_REGISTRY[key]
        rows = model.query.all()
        snapshot[key] = [serialize_row(model, row) for row in rows]
        stats[key] = len(rows)

    return {
        'meta': {
            'schema_version': BACKUP_SCHEMA_VERSION,
            'exported_at': datetime.utcnow().isoformat(),
            'engine': db.engine.url.get_backend_name()
        },
        'snapshot': snapshot
    }, stats


def restore_snapshot_payload(payload):
    snapshot = extract_snapshot(payload)
    if not isinstance(snapshot, dict):
        raise ValueError('Invalid backup payload')

    has_users_snapshot = isinstance(snapshot.get('users'), list)
    restore_delete_order = [
        table_key for table_key in RESTORE_DELETE_ORDER
        if has_users_snapshot or table_key != 'users'
    ]
    restore_insert_order = [
        table_key for table_key in RESTORE_INSERT_ORDER
        if has_users_snapshot or table_key != 'users'
    ]

    stats = build_stats_template()

    for table_key in restore_delete_order:
        model = MODEL_REGISTRY[table_key]
        model.query.delete()

    db.session.flush()

    for table_key in restore_insert_order:
        records = snapshot.get(table_key, [])
        if records is None:
            records = []
        if not isinstance(records, list):
            raise ValueError(f'Invalid data for {table_key}')

        model = MODEL_REGISTRY[table_key]

        for record in records:
            if not isinstance(record, dict):
                raise ValueError(f'Invalid item in {table_key}')

            values = {}
            if table_key == 'users':
                account = record.get('account')
                username = record.get('username')
                if account is None and username is not None:
                    values['account'] = username
                if username is None and account is not None:
                    values['username'] = account
            for column in model.__table__.columns:
                if column.name not in record:
                    if column.name not in values:
                        continue
                raw_value = record.get(column.name) if column.name in record else values.get(column.name)
                values[column.name] = deserialize_value(column, raw_value)

            db.session.add(model(**values))
            stats[table_key] += 1

    db.session.commit()
    return stats

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from flask import Blueprint, g, request
from sqlalchemy import Boolean, Date, DateTime, Float, Integer, Numeric

from models.models import (
    db,
    User,
    Customer,
    Balance,
    Transaction,
    Activity,
    BillingRule,
    ActiveTimer,
    BeadMaterial,
    BeadInventoryBalance,
    BeadInventoryLedger,
    BeadStocktake,
    Log
)
from utils.audit_log import get_operator_name, write_log
from utils.decorators import token_required
from utils.response import success_response, error_response

data_bp = Blueprint('data', __name__)

BACKUP_SCHEMA_VERSION = 3

MODEL_REGISTRY = {
    'users': User,
    'customers': Customer,
    'balances': Balance,
    'transactions': Transaction,
    'activities': Activity,
    'billing_rules': BillingRule,
    'active_timers': ActiveTimer,
    'bead_materials': BeadMaterial,
    'bead_inventory_balances': BeadInventoryBalance,
    'bead_inventory_ledgers': BeadInventoryLedger,
    'bead_stocktakes': BeadStocktake,
    'logs': Log
}

BACKUP_ORDER = [
    'users',
    'customers',
    'balances',
    'transactions',
    'activities',
    'billing_rules',
    'active_timers',
    'bead_materials',
    'bead_inventory_balances',
    'bead_inventory_ledgers',
    'bead_stocktakes',
    'logs'
]

RESTORE_INSERT_ORDER = [
    'users',
    'customers',
    'activities',
    'billing_rules',
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
    'logs',
    'bead_stocktakes',
    'bead_inventory_ledgers',
    'bead_inventory_balances',
    'bead_materials',
    'active_timers',
    'transactions',
    'balances',
    'billing_rules',
    'activities',
    'customers',
    'users'
]


def _build_storage_info():
    """Return concrete storage details for the currently configured database."""
    engine_url = db.engine.url
    engine_url_str = str(engine_url)
    backend_name = engine_url.get_backend_name()
    database = engine_url.database or ''

    storage_location = '未知'
    data_size_bytes = None

    if backend_name == 'sqlite':
        if database == ':memory:':
            storage_location = '内存数据库'
        elif database:
            db_path = Path(database).expanduser()
            if not db_path.is_absolute():
                db_path = (Path.cwd() / db_path).resolve()
            storage_location = str(db_path)
            if db_path.is_file():
                try:
                    data_size_bytes = db_path.stat().st_size
                except OSError:
                    data_size_bytes = None
    elif database:
        storage_location = database
    elif engine_url_str:
        storage_location = engine_url_str

    data_counts = {
        'users': User.query.count(),
        'customers': Customer.query.count(),
        'balances': Balance.query.count(),
        'transactions': Transaction.query.count(),
        'activities': Activity.query.count(),
        'billing_rules': BillingRule.query.count(),
        'active_timers': ActiveTimer.query.count(),
        'bead_materials': BeadMaterial.query.count(),
        'bead_inventory_balances': BeadInventoryBalance.query.count(),
        'bead_inventory_ledgers': BeadInventoryLedger.query.count(),
        'bead_stocktakes': BeadStocktake.query.count(),
        'logs': Log.query.count()
    }

    return {
        'engine': backend_name,
        'databaseUri': engine_url_str,
        'storageLocation': storage_location,
        'dataSizeBytes': data_size_bytes,
        'dataCounts': data_counts
    }


def _serialize_value(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _serialize_row(model, row):
    return {
        column.name: _serialize_value(getattr(row, column.name))
        for column in model.__table__.columns
    }


def _parse_datetime_value(value):
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


def _parse_date_value(value):
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
        dt = _parse_datetime_value(text)
        return dt.date() if dt else None


def _deserialize_value(column, value):
    if value is None:
        return None

    column_type = column.type

    if isinstance(column_type, DateTime):
        return _parse_datetime_value(value)

    if isinstance(column_type, Date):
        return _parse_date_value(value)

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


def _extract_snapshot(payload):
    if not isinstance(payload, dict):
        return None

    snapshot = payload.get('snapshot')
    if isinstance(snapshot, dict):
        return snapshot

    # Backward compatible: old backups used flat structure.
    return payload


def _build_stats_template():
    return {
        key: 0 for key in BACKUP_ORDER
    }


def _require_admin():
    current_user_id = getattr(g, 'current_user_id', None)
    current_user = User.query.get(current_user_id) if current_user_id is not None else None

    if not current_user:
        return error_response('用户不存在或未登录', 401)

    if str(current_user.role or '').strip().lower() != 'admin':
        return error_response('仅管理员可执行该操作', 403)

    return None


@data_bp.route('/storage-info', methods=['GET'])
@token_required
def storage_info():
    permission_error = _require_admin()
    if permission_error:
        return permission_error

    return success_response(_build_storage_info(), 'Storage info fetched')


@data_bp.route('/backup', methods=['GET'])
@token_required
def backup_data():
    permission_error = _require_admin()
    if permission_error:
        return permission_error

    snapshot = {}
    stats = _build_stats_template()

    for key in BACKUP_ORDER:
        model = MODEL_REGISTRY[key]
        rows = model.query.all()
        snapshot[key] = [_serialize_row(model, row) for row in rows]
        stats[key] = len(rows)

    backup_data_payload = {
        'meta': {
            'schema_version': BACKUP_SCHEMA_VERSION,
            'exported_at': datetime.utcnow().isoformat(),
            'engine': db.engine.url.get_backend_name()
        },
        'snapshot': snapshot
    }

    operator = get_operator_name(default='unknown')
    write_log(
        'data_backup',
        (
            f'执行数据备份：用户 {stats["users"]}，客户 {stats["customers"]}，交易 {stats["transactions"]}，余额 {stats["balances"]}，'
            f'活动 {stats["activities"]}，计费规则 {stats["billing_rules"]}，计时 {stats["active_timers"]}，'
            f'豆料 {stats["bead_materials"]}，豆仓库存 {stats["bead_inventory_balances"]}，豆仓流水 {stats["bead_inventory_ledgers"]}，'
            f'豆仓盘点 {stats["bead_stocktakes"]}，日志 {stats["logs"]}'
        ),
        operator=operator
    )
    db.session.commit()

    return success_response(backup_data_payload, 'Data backup completed')


@data_bp.route('/restore', methods=['POST'])
@token_required
def restore_data():
    permission_error = _require_admin()
    if permission_error:
        return permission_error

    payload = request.get_json()

    if not payload:
        return error_response('No data provided', 400)

    snapshot = _extract_snapshot(payload)
    if not isinstance(snapshot, dict):
        return error_response('Invalid backup payload', 400)

    has_users_snapshot = isinstance(snapshot.get('users'), list)

    restore_delete_order = [
        table_key for table_key in RESTORE_DELETE_ORDER
        if has_users_snapshot or table_key != 'users'
    ]
    restore_insert_order = [
        table_key for table_key in RESTORE_INSERT_ORDER
        if has_users_snapshot or table_key != 'users'
    ]

    stats = _build_stats_template()

    try:
        for table_key in restore_delete_order:
            model = MODEL_REGISTRY[table_key]
            model.query.delete()

        db.session.flush()

        for table_key in restore_insert_order:
            records = snapshot.get(table_key, [])
            if records is None:
                records = []
            if not isinstance(records, list):
                return error_response(f'Invalid data for {table_key}', 400)

            model = MODEL_REGISTRY[table_key]

            for record in records:
                if not isinstance(record, dict):
                    return error_response(f'Invalid item in {table_key}', 400)

                values = {}
                for column in model.__table__.columns:
                    if column.name not in record:
                        continue
                    values[column.name] = _deserialize_value(column, record.get(column.name))

                db.session.add(model(**values))
                stats[table_key] += 1

        db.session.commit()

        # Keep exact-restore semantics: do not append restore log into restored dataset.
        return success_response(
            {
                'schema_version': payload.get('meta', {}).get('schema_version') if isinstance(payload.get('meta'), dict) else None,
                'restored': stats
            },
            'Data restored successfully'
        )

    except Exception as e:
        db.session.rollback()
        return error_response(f'Restore failed: {str(e)}', 500)


@data_bp.route('/clear', methods=['DELETE'])
@token_required
def clear_data():
    permission_error = _require_admin()
    if permission_error:
        return permission_error

    try:
        counts = {
            'logs': Log.query.count(),
            'bead_stocktakes': BeadStocktake.query.count(),
            'bead_inventory_ledgers': BeadInventoryLedger.query.count(),
            'bead_inventory_balances': BeadInventoryBalance.query.count(),
            'bead_materials': BeadMaterial.query.count(),
            'active_timers': ActiveTimer.query.count(),
            'transactions': Transaction.query.count(),
            'balances': Balance.query.count(),
            'billing_rules': BillingRule.query.count(),
            'activities': Activity.query.count(),
            'customers': Customer.query.count(),
            'users': User.query.count()
        }

        Log.query.delete()
        BeadStocktake.query.delete()
        BeadInventoryLedger.query.delete()
        BeadInventoryBalance.query.delete()
        BeadMaterial.query.delete()
        ActiveTimer.query.delete()
        Transaction.query.delete()
        Balance.query.delete()
        BillingRule.query.delete()
        Activity.query.delete()
        Customer.query.delete()

        operator = get_operator_name(default='unknown')
        write_log(
            'data_clear',
            (
                f'清空系统数据：用户保留 {counts["users"]}，客户 {counts["customers"]}，交易 {counts["transactions"]}，余额 {counts["balances"]}，'
                f'活动 {counts["activities"]}，计费规则 {counts["billing_rules"]}，计时 {counts["active_timers"]}，'
                f'豆料 {counts["bead_materials"]}，豆仓库存 {counts["bead_inventory_balances"]}，豆仓流水 {counts["bead_inventory_ledgers"]}，'
                f'豆仓盘点 {counts["bead_stocktakes"]}，日志 {counts["logs"]}'
            ),
            operator=operator
        )

        db.session.commit()

        return success_response(message='All data cleared successfully')

    except Exception as e:
        db.session.rollback()
        return error_response(f'Clear failed: {str(e)}', 500)

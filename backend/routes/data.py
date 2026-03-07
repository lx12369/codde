from pathlib import Path

from flask import Blueprint, g, request
from sqlalchemy import text

from models.models import (
    db,
    User,
    RevokedToken,
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
from utils.data_snapshot import BACKUP_SCHEMA_VERSION, export_snapshot_payload, restore_snapshot_payload
from utils.decorators import token_required
from utils.roles import is_admin
from utils.response import error_response, success_response

data_bp = Blueprint('data', __name__)


def _resolve_restore_schema_version(payload):
    if not isinstance(payload, dict):
        return BACKUP_SCHEMA_VERSION

    meta = payload.get('meta')
    if isinstance(meta, dict) and meta.get('schema_version') is not None:
        return meta.get('schema_version')

    wrapped_data = payload.get('data')
    if isinstance(wrapped_data, dict):
        nested_meta = wrapped_data.get('meta')
        if isinstance(nested_meta, dict) and nested_meta.get('schema_version') is not None:
            return nested_meta.get('schema_version')

    return BACKUP_SCHEMA_VERSION


def _build_storage_info():
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
    elif backend_name == 'mysql' and database:
        storage_location = database
        try:
            result = db.session.execute(
                text(
                    'SELECT COALESCE(SUM(data_length + index_length), 0) '
                    'FROM information_schema.tables '
                    'WHERE table_schema = :database_name'
                ),
                {'database_name': database}
            )
            data_size_bytes = int(result.scalar() or 0)
        except Exception:
            data_size_bytes = None
    elif database:
        storage_location = database
    elif engine_url_str:
        storage_location = engine_url_str

    data_counts = {
        'users': User.query.count(),
        'revoked_tokens': RevokedToken.query.count(),
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


def _require_admin():
    current_user_id = getattr(g, 'current_user_id', None)
    current_user = User.query.get(current_user_id) if current_user_id is not None else None

    if not current_user:
        return error_response('用户不存在或未登录', 401)

    if not is_admin(current_user):
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

    backup_data_payload, stats = export_snapshot_payload()

    operator = get_operator_name(default='unknown')
    write_log(
        'data_backup',
        (
            f'执行数据备份：用户 {stats["users"]}，令牌黑名单 {stats["revoked_tokens"]}，客户 {stats["customers"]}，交易 {stats["transactions"]}，余额 {stats["balances"]}，'
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

    try:
        stats = restore_snapshot_payload(payload)
        return success_response(
            {
                'schema_version': _resolve_restore_schema_version(payload),
                'restored': stats
            },
            'Data restored successfully'
        )
    except ValueError as error:
        db.session.rollback()
        return error_response(str(error), 400)
    except Exception as error:
        db.session.rollback()
        return error_response(f'Restore failed: {str(error)}', 500)


@data_bp.route('/clear', methods=['DELETE'])
@token_required
def clear_data():
    permission_error = _require_admin()
    if permission_error:
        return permission_error

    try:
        counts = {
            'revoked_tokens': RevokedToken.query.count(),
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

        RevokedToken.query.delete()
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
                f'清空系统数据：用户保留 {counts["users"]}，令牌黑名单 {counts["revoked_tokens"]}，客户 {counts["customers"]}，交易 {counts["transactions"]}，余额 {counts["balances"]}，'
                f'活动 {counts["activities"]}，计费规则 {counts["billing_rules"]}，计时 {counts["active_timers"]}，'
                f'豆料 {counts["bead_materials"]}，豆仓库存 {counts["bead_inventory_balances"]}，豆仓流水 {counts["bead_inventory_ledgers"]}，'
                f'豆仓盘点 {counts["bead_stocktakes"]}，日志 {counts["logs"]}'
            ),
            operator=operator
        )

        db.session.commit()
        return success_response(message='All data cleared successfully')
    except Exception as error:
        db.session.rollback()
        return error_response(f'Clear failed: {str(error)}', 500)

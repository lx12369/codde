from collections import defaultdict
from datetime import datetime, time

from flask import g

from models import Log, User, db


LOG_TYPE_META = {
    'login': {
        'module': 'auth',
        'module_label': '认证',
        'action': 'login',
        'action_label': '登录',
        'type_label': '登录'
    },
    'password_change': {
        'module': 'auth',
        'module_label': '认证',
        'action': 'password_change',
        'action_label': '修改密码',
        'type_label': '修改密码'
    },
    'recharge': {
        'module': 'transaction',
        'module_label': '交易',
        'action': 'recharge',
        'action_label': '充值',
        'type_label': '充值'
    },
    'consumption': {
        'module': 'transaction',
        'module_label': '交易',
        'action': 'consumption',
        'action_label': '消费',
        'type_label': '消费'
    },
    'transaction_cancel_recharge': {
        'module': 'transaction',
        'module_label': '交易',
        'action': 'cancel_recharge',
        'action_label': '取消充值',
        'type_label': '取消充值'
    },
    'transaction_cancel_consumption': {
        'module': 'transaction',
        'module_label': '交易',
        'action': 'cancel_consumption',
        'action_label': '取消消费',
        'type_label': '取消消费'
    },
    'transaction_cancel_bead_purchase': {
        'module': 'transaction',
        'module_label': '交易',
        'action': 'cancel_bead_purchase',
        'action_label': '取消买豆交易',
        'type_label': '取消买豆交易'
    },
    'customer_create': {
        'module': 'customer',
        'module_label': '客户',
        'action': 'create',
        'action_label': '创建客户',
        'type_label': '创建客户'
    },
    'customer_update': {
        'module': 'customer',
        'module_label': '客户',
        'action': 'update',
        'action_label': '更新客户',
        'type_label': '更新客户'
    },
    'customer_delete': {
        'module': 'customer',
        'module_label': '客户',
        'action': 'delete',
        'action_label': '删除客户',
        'type_label': '删除客户'
    },
    'activity_create': {
        'module': 'activity',
        'module_label': '活动',
        'action': 'create',
        'action_label': '创建活动',
        'type_label': '创建活动'
    },
    'activity_update': {
        'module': 'activity',
        'module_label': '活动',
        'action': 'update',
        'action_label': '更新活动',
        'type_label': '更新活动'
    },
    'activity_delete': {
        'module': 'activity',
        'module_label': '活动',
        'action': 'delete',
        'action_label': '删除活动',
        'type_label': '删除活动'
    },
    'billing_rule_update': {
        'module': 'billing',
        'module_label': '计费',
        'action': 'update',
        'action_label': '更新规则',
        'type_label': '计费规则更新'
    },
    'timer_start': {
        'module': 'timer',
        'module_label': '计时',
        'action': 'start',
        'action_label': '开始计时',
        'type_label': '开始计时'
    },
    'timer_update': {
        'module': 'timer',
        'module_label': '计时',
        'action': 'update',
        'action_label': '更新计时',
        'type_label': '更新计时'
    },
    'timer_settle': {
        'module': 'timer',
        'module_label': '计时',
        'action': 'settle',
        'action_label': '计时结算',
        'type_label': '计时结算'
    },
    'timer_delete': {
        'module': 'timer',
        'module_label': '计时',
        'action': 'delete',
        'action_label': '删除计时',
        'type_label': '删除计时'
    },
    'data_backup': {
        'module': 'data',
        'module_label': '数据',
        'action': 'backup',
        'action_label': '数据备份',
        'type_label': '数据备份'
    },
    'data_restore': {
        'module': 'data',
        'module_label': '数据',
        'action': 'restore',
        'action_label': '数据恢复',
        'type_label': '数据恢复'
    },
    'data_clear': {
        'module': 'data',
        'module_label': '数据',
        'action': 'clear',
        'action_label': '清空数据',
        'type_label': '清空数据'
    },
    'bead_material_create': {
        'module': 'bead_inventory',
        'module_label': '豆仓',
        'action': 'material_create',
        'action_label': '创建豆料',
        'type_label': '创建豆料'
    },
    'bead_material_update': {
        'module': 'bead_inventory',
        'module_label': '豆仓',
        'action': 'material_update',
        'action_label': '更新豆料',
        'type_label': '更新豆料'
    },
    'bead_material_delete': {
        'module': 'bead_inventory',
        'module_label': '豆仓',
        'action': 'material_delete',
        'action_label': '删除豆料',
        'type_label': '删除豆料'
    },
    'bead_material_import_mard': {
        'module': 'bead_inventory',
        'module_label': '豆仓',
        'action': 'material_import',
        'action_label': '导入色卡',
        'type_label': '导入色卡'
    },
    'bead_inventory_inbound': {
        'module': 'bead_inventory',
        'module_label': '豆仓',
        'action': 'inbound',
        'action_label': '补货入库',
        'type_label': '补货入库'
    },
    'bead_inventory_outbound': {
        'module': 'bead_inventory',
        'module_label': '豆仓',
        'action': 'outbound',
        'action_label': '出库',
        'type_label': '出库'
    },
    'bead_inventory_loss': {
        'module': 'bead_inventory',
        'module_label': '豆仓',
        'action': 'loss',
        'action_label': '损耗',
        'type_label': '损耗'
    },
    'bead_inventory_stocktake': {
        'module': 'bead_inventory',
        'module_label': '豆仓',
        'action': 'stocktake',
        'action_label': '盘点',
        'type_label': '盘点'
    },
    'bead_conversion_standard_batch_update': {
        'module': 'bead_inventory',
        'module_label': '豆仓',
        'action': 'conversion_standard_batch_update',
        'action_label': '批量更新换算标准',
        'type_label': '批量更新换算标准'
    },
    'bead_market_price_batch_update': {
        'module': 'bead_inventory',
        'module_label': '豆仓',
        'action': 'market_price_batch_update',
        'action_label': '批量更新市场价',
        'type_label': '批量更新市场价'
    },
    'bead_safe_stock_batch_update_by_common_color': {
        'module': 'bead_inventory',
        'module_label': '豆仓',
        'action': 'safe_stock_batch_update_by_common_color',
        'action_label': '按常用色批量更新安全库存',
        'type_label': '按常用色批量更新安全库存'
    }
}

DEFAULT_META = {
    'module': 'other',
    'module_label': '其他',
    'action': 'other',
    'action_label': '其他',
    'type_label': '其他'
}


def get_operator_name(default='system'):
    user_id = getattr(g, 'current_user_id', None)
    if user_id is None:
        return default

    user = User.query.get(user_id)
    if user and user.username:
        return user.username

    return default


def write_log(log_type, description, operator=None):
    text = str(description or '').strip()
    if len(text) > 255:
        text = f'{text[:252]}...'

    log = Log(
        type=str(log_type or '').strip() or 'other',
        description=text or '-',
        operator=(operator or get_operator_name()).strip() or 'system'
    )
    db.session.add(log)
    return log


def get_log_meta(log_type):
    key = str(log_type or '').strip()
    meta = LOG_TYPE_META.get(key)
    if meta:
        return meta
    return DEFAULT_META


def enrich_log_data(log_data):
    payload = dict(log_data or {})
    meta = get_log_meta(payload.get('type'))
    payload.update(meta)
    return payload


def parse_datetime_range(value, end_of_day=False):
    if value is None:
        return None

    raw = str(value).strip()
    if not raw:
        return None

    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        pass

    try:
        day = datetime.strptime(raw, '%Y-%m-%d').date()
    except ValueError:
        return None

    if end_of_day:
        return datetime.combine(day, time.max)
    return datetime.combine(day, time.min)


def get_module_types_map():
    module_map = defaultdict(set)
    for log_type, meta in LOG_TYPE_META.items():
        module_map[meta['module']].add(log_type)
    return {key: sorted(values) for key, values in module_map.items()}


def get_action_types_map():
    action_map = defaultdict(set)
    for log_type, meta in LOG_TYPE_META.items():
        action_map[meta['action']].add(log_type)
    return {key: sorted(values) for key, values in action_map.items()}


def build_filter_options():
    module_labels = {}
    action_labels = {}

    for meta in LOG_TYPE_META.values():
        module_labels[meta['module']] = meta['module_label']
        action_labels[meta['action']] = meta['action_label']

    module_options = [{'value': 'all', 'label': '全部模块'}]
    module_options.extend(
        {'value': key, 'label': module_labels[key]}
        for key in sorted(module_labels.keys())
    )
    module_options.append({'value': 'other', 'label': '其他'})

    action_options = [{'value': 'all', 'label': '全部操作'}]
    action_options.extend(
        {'value': key, 'label': action_labels[key]}
        for key in sorted(action_labels.keys())
    )
    action_options.append({'value': 'other', 'label': '其他'})

    return {
        'modules': module_options,
        'actions': action_options
    }

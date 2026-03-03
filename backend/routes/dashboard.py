from flask import Blueprint, request
from datetime import datetime, timedelta
import re
from sqlalchemy import func
from models import db, Customer, Transaction, ActiveTimer, Log
from utils.response import success_response, error_response
from utils.decorators import token_required

dashboard_bp = Blueprint('dashboard', __name__)

TYPE_LABELS = {
    'recharge': '充值',
    'consumption': '消费',
    'login': '登录',
    'password_change': '修改密码'
}

RECHARGE_PATTERN = re.compile(
    r'^Customer\s+(.+?)\s+\(([^)]+)\)\s+recharge\s+([0-9]+(?:\.[0-9]+)?)\s+bonus\s+([0-9]+(?:\.[0-9]+)?)$',
    re.IGNORECASE
)
CONSUME_PATTERN = re.compile(
    r'^Customer\s+(.+?)\s+\(([^)]+)\)\s+consume\s+([0-9]+(?:\.[0-9]+)?):\s*(.*)$',
    re.IGNORECASE
)
TIMED_CONSUME_PATTERN = re.compile(
    r'^Customer\s+(.+?)\s+\(([^)]+)\)\s+timed\s+consumption\s+([0-9]+(?:\.[0-9]+)?):\s*(.*)$',
    re.IGNORECASE
)
LOGIN_PATTERN = re.compile(
    r'^User\s+(.+?)\s+(?:login(?:ed)?|logged\s+in)(?:\s+success(?:fully)?)?$',
    re.IGNORECASE
)
PASSWORD_PATTERN = re.compile(
    r'^User\s+(.+?)\s+(?:change|changed)\s+password$',
    re.IGNORECASE
)


def _to_money_text(value):
    try:
        return f'{float(value):.2f}'
    except (TypeError, ValueError):
        return '0.00'


def _localize_activity_description(activity_type, raw_description):
    description = str(raw_description or '').strip()
    if not description:
        return '-'

    matched = RECHARGE_PATTERN.match(description)
    if matched:
        customer_name, customer_id, amount, bonus = matched.groups()
        return f'客户 {customer_name}（{customer_id}）充值 ¥{_to_money_text(amount)}，赠送 ¥{_to_money_text(bonus)}'

    matched = TIMED_CONSUME_PATTERN.match(description)
    if matched:
        customer_name, customer_id, amount, detail = matched.groups()
        detail_text = detail.strip() if detail and detail.strip() else '无'
        return f'客户 {customer_name}（{customer_id}）计时消费 ¥{_to_money_text(amount)}：{detail_text}'

    matched = CONSUME_PATTERN.match(description)
    if matched:
        customer_name, customer_id, amount, detail = matched.groups()
        detail_text = detail.strip() if detail and detail.strip() else '无'
        return f'客户 {customer_name}（{customer_id}）消费 ¥{_to_money_text(amount)}：{detail_text}'

    matched = LOGIN_PATTERN.match(description)
    if matched:
        return f'用户 {matched.group(1)} 登录成功'

    matched = PASSWORD_PATTERN.match(description)
    if matched:
        return f'用户 {matched.group(1)} 修改了密码'

    # Keep already localized or unknown text unchanged.
    if re.search(r'[\u4e00-\u9fff]', description):
        return description

    if activity_type == 'recharge':
        return '完成充值操作'
    if activity_type == 'consumption':
        return '完成消费操作'
    if activity_type == 'login':
        return '用户登录'
    if activity_type == 'password_change':
        return '修改密码'
    return description


def _localize_activity(log):
    activity = log.to_dict()
    activity_type = str(activity.get('type') or '').strip()
    raw_description = activity.get('description')

    activity['raw_description'] = raw_description
    activity['type_label'] = TYPE_LABELS.get(activity_type, '其他')
    activity['description'] = _localize_activity_description(activity_type, raw_description)
    return activity


@dashboard_bp.route('/stats', methods=['GET'])
@token_required
def get_stats():
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    
    total_customers = Customer.query.filter(
        db.or_(Customer.is_deleted.is_(False), Customer.is_deleted.is_(None))
    ).count()
    
    today_transactions = Transaction.query.filter(
        Transaction.type == 'recharge',
        Transaction.transaction_time >= today_start,
        Transaction.transaction_time <= today_end
    ).count()
    
    today_amount_result = db.session.query(
        func.coalesce(func.sum(Transaction.amount), 0)
    ).filter(
        Transaction.type == 'recharge',
        Transaction.transaction_time >= today_start,
        Transaction.transaction_time <= today_end
    ).scalar()
    today_amount = float(today_amount_result) if today_amount_result else 0.0
    
    today_consumptions = Transaction.query.filter(
        Transaction.type == 'consumption',
        Transaction.transaction_time >= today_start,
        Transaction.transaction_time <= today_end
    ).count()
    
    today_consumption_amount_result = db.session.query(
        func.coalesce(func.sum(Transaction.amount), 0)
    ).filter(
        Transaction.type == 'consumption',
        Transaction.transaction_time >= today_start,
        Transaction.transaction_time <= today_end
    ).scalar()
    today_consumption_amount = float(today_consumption_amount_result) if today_consumption_amount_result else 0.0
    
    total_transactions = Transaction.query.count()
    
    active_timers_count = ActiveTimer.query.filter_by(status='active').count()
    
    stats = {
        'total_customers': total_customers,
        'today_transactions': today_transactions,
        'today_amount': today_amount,
        'today_consumptions': today_consumptions,
        'today_consumption_amount': today_consumption_amount,
        'total_transactions': total_transactions,
        'active_timers_count': active_timers_count
    }
    
    return success_response(stats)


@dashboard_bp.route('/charts', methods=['GET'])
@token_required
def get_charts():
    days = request.args.get('days', 7, type=int)
    
    if days not in [7, 30, 90]:
        days = 7
    
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days - 1)
    
    dates = []
    recharge_amounts = []
    consumption_amounts = []
    
    current_date = start_date
    while current_date <= end_date:
        dates.append(current_date.isoformat())
        
        day_start = datetime.combine(current_date, datetime.min.time())
        day_end = datetime.combine(current_date, datetime.max.time())
        
        recharge_amount = db.session.query(
            func.coalesce(func.sum(Transaction.amount), 0)
        ).filter(
            Transaction.type == 'recharge',
            Transaction.transaction_time >= day_start,
            Transaction.transaction_time <= day_end
        ).scalar()
        recharge_amounts.append(float(recharge_amount) if recharge_amount else 0.0)
        
        consumption_amount = db.session.query(
            func.coalesce(func.sum(Transaction.amount), 0)
        ).filter(
            Transaction.type == 'consumption',
            Transaction.transaction_time >= day_start,
            Transaction.transaction_time <= day_end
        ).scalar()
        consumption_amounts.append(float(consumption_amount) if consumption_amount else 0.0)
        
        current_date += timedelta(days=1)
    
    chart_data = {
        'dates': dates,
        'recharge_amounts': recharge_amounts,
        'consumption_amounts': consumption_amounts
    }
    
    return success_response(chart_data)


@dashboard_bp.route('/recent-activities', methods=['GET'])
@token_required
def get_recent_activities():
    limit = request.args.get('limit', 10, type=int)
    
    if limit < 1:
        limit = 10
    elif limit > 100:
        limit = 100
    
    logs = Log.query.order_by(Log.timestamp.desc()).limit(limit).all()

    activities = [_localize_activity(log) for log in logs]
    
    return success_response(activities)

from datetime import datetime, timedelta
import re

from sqlalchemy import func
from flask import Blueprint, request

from models import ActiveTimer, Customer, Log, Transaction, db
from utils.audit_log import enrich_log_data
from utils.decorators import token_required
from utils.response import error_response, success_response
from utils.weather_amap import WeatherServiceError, get_xiaying_weather

dashboard_bp = Blueprint('dashboard', __name__)

_PEOPLE_COUNT_PATTERN = re.compile(r'(\d+)\s*人')


def _estimate_consumption_people(description):
    text = str(description or '').strip()
    if not text:
        return 1

    if '双人' in text:
        return 2

    match = _PEOPLE_COUNT_PATTERN.search(text)
    if match:
        try:
            parsed = int(match.group(1))
            return max(1, parsed)
        except (TypeError, ValueError):
            return 1

    return 1


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

    today_consumption_records = Transaction.query.with_entities(Transaction.description).filter(
        Transaction.type == 'consumption',
        Transaction.transaction_time >= today_start,
        Transaction.transaction_time <= today_end
    ).all()
    today_consumption_people = sum(
        _estimate_consumption_people(row.description)
        for row in today_consumption_records
    )

    total_transactions = Transaction.query.count()

    active_timers_count = ActiveTimer.query.filter_by(status='active').count()

    stats = {
        'total_customers': total_customers,
        'today_transactions': today_transactions,
        'today_amount': today_amount,
        'today_consumptions': today_consumptions,
        'today_consumption_people': today_consumption_people,
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
    activities = [enrich_log_data(log.to_dict()) for log in logs]

    return success_response(activities)


@dashboard_bp.route('/weather/today', methods=['GET'])
@token_required
def get_weather_today():
    try:
        weather = get_xiaying_weather()
        return success_response(weather)
    except WeatherServiceError as error:
        return error_response(str(error), error.status_code)
    except Exception:
        return error_response('天气服务暂不可用，请稍后重试', 502)

from flask import Blueprint, request
from models.models import db, Customer, Balance, Transaction, Activity, BillingRule, ActiveTimer, Log, User
from utils.decorators import token_required
from utils.response import success_response, error_response

data_bp = Blueprint('data', __name__)


@data_bp.route('/backup', methods=['GET'])
@token_required
def backup_data():
    customers = Customer.query.all()
    transactions = Transaction.query.all()
    balances = Balance.query.all()
    activities = Activity.query.all()
    billing_rules = BillingRule.query.all()
    active_timers = ActiveTimer.query.all()
    logs = Log.query.all()
    
    backup_data = {
        'customers': [customer.to_dict() for customer in customers],
        'transactions': [transaction.to_dict() for transaction in transactions],
        'balances': [balance.to_dict() for balance in balances],
        'activities': [activity.to_dict() for activity in activities],
        'billing_rules': [rule.to_dict() for rule in billing_rules],
        'active_timers': [timer.to_dict() for timer in active_timers],
        'logs': [log.to_dict() for log in logs]
    }
    
    return success_response(backup_data, 'Data backup completed')


@data_bp.route('/restore', methods=['POST'])
@token_required
def restore_data():
    data = request.get_json()
    
    if not data:
        return error_response('No data provided', 400)
    
    stats = {
        'customers': 0,
        'transactions': 0,
        'balances': 0,
        'activities': 0,
        'billing_rules': 0,
        'active_timers': 0,
        'logs': 0
    }
    
    try:
        if 'customers' in data:
            for item in data['customers']:
                customer = Customer(
                    id=item['id'],
                    name=item['name'],
                    phone=item.get('phone')
                )
                db.session.merge(customer)
                stats['customers'] += 1
        
        if 'balances' in data:
            for item in data['balances']:
                balance = Balance(
                    id=item['id'],
                    customer_id=item['customer_id'],
                    balance=item['balance']
                )
                db.session.merge(balance)
                stats['balances'] += 1
        
        if 'transactions' in data:
            for item in data['transactions']:
                from datetime import datetime
                transaction = Transaction(
                    id=item['id'],
                    customer_id=item['customer_id'],
                    type=item['type'],
                    amount=item['amount'],
                    bonus_amount=item.get('bonus_amount', 0.0),
                    payment_method=item.get('payment_method'),
                    description=item.get('description'),
                    activity_id=item.get('activity_id'),
                    operator=item.get('operator'),
                    transaction_time=datetime.fromisoformat(item['transaction_time']) if item.get('transaction_time') else None
                )
                db.session.merge(transaction)
                stats['transactions'] += 1
        
        if 'activities' in data:
            for item in data['activities']:
                from datetime import datetime
                activity = Activity(
                    id=item['id'],
                    name=item['name'],
                    description=item.get('description'),
                    min_amount=item.get('min_amount'),
                    bonus_rate=item.get('bonus_amount', item.get('bonus_rate')),
                    start_date=datetime.fromisoformat(item['start_date']) if item.get('start_date') else None,
                    end_date=datetime.fromisoformat(item['end_date']) if item.get('end_date') else None,
                    status=item.get('status', 'active')
                )
                db.session.merge(activity)
                stats['activities'] += 1
        
        if 'billing_rules' in data:
            for item in data['billing_rules']:
                billing_rule = BillingRule(
                    id=item['id'],
                    rule_type=item['rule_type'],
                    rule_data=item.get('rule_data')
                )
                db.session.merge(billing_rule)
                stats['billing_rules'] += 1
        
        if 'active_timers' in data:
            for item in data['active_timers']:
                from datetime import datetime
                timer = ActiveTimer(
                    id=item['id'],
                    customer_id=item['customer_id'],
                    start_time=datetime.fromisoformat(item['start_time']) if item.get('start_time') else None,
                    timer_type=item.get('timer_type'),
                    notes=item.get('notes'),
                    status=item.get('status', 'active')
                )
                db.session.merge(timer)
                stats['active_timers'] += 1
        
        if 'logs' in data:
            for item in data['logs']:
                from datetime import datetime
                log = Log(
                    id=item['id'],
                    type=item.get('type'),
                    description=item.get('description'),
                    operator=item.get('operator'),
                    timestamp=datetime.fromisoformat(item['timestamp']) if item.get('timestamp') else None
                )
                db.session.merge(log)
                stats['logs'] += 1
        
        db.session.commit()
        
        return success_response(stats, 'Data restored successfully')
    
    except Exception as e:
        db.session.rollback()
        return error_response(f'Restore failed: {str(e)}', 500)


@data_bp.route('/clear', methods=['DELETE'])
@token_required
def clear_data():
    try:
        Log.query.delete()
        ActiveTimer.query.delete()
        Transaction.query.delete()
        Balance.query.delete()
        BillingRule.query.delete()
        Activity.query.delete()
        Customer.query.delete()
        
        db.session.commit()
        
        return success_response(message='All data cleared successfully')
    
    except Exception as e:
        db.session.rollback()
        return error_response(f'Clear failed: {str(e)}', 500)

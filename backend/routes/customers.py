from datetime import date, datetime
from flask import Blueprint, request
from models.models import db, Customer, Balance, Transaction, ActiveTimer
from utils.decorators import token_required
from utils.response import success_response, error_response, paginated_response

customers_bp = Blueprint('customers', __name__)


def _parse_birthday(value):
    if value is None:
        return None

    value_str = str(value).strip()
    if not value_str:
        return None

    try:
        return date.fromisoformat(value_str)
    except ValueError as exc:
        raise ValueError('Birthday must be in YYYY-MM-DD format') from exc


def _active_customer_filters():
    return db.or_(Customer.is_deleted.is_(False), Customer.is_deleted.is_(None))


def _active_customer_query():
    return Customer.query.filter(_active_customer_filters())


def _get_active_customer(customer_id):
    return _active_customer_query().filter(Customer.id == customer_id).first()


def _customer_to_dict(customer, balance_map=None):
    data = customer.to_dict()

    if balance_map is None:
        balance_record = Balance.query.filter_by(customer_id=customer.id).first()
        current_balance = float(balance_record.balance) if balance_record else 0.0
    else:
        current_balance = float(balance_map.get(customer.id, 0.0))

    data['balance'] = current_balance
    data['current_balance'] = current_balance
    return data


@customers_bp.route('', methods=['GET'])
@token_required
def get_customers():
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', type=int)
    if page_size is None:
        page_size = request.args.get('pageSize', 10, type=int)
    search = request.args.get('search', '', type=str)

    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 10

    query = _active_customer_query()

    if search:
        search_pattern = f'%{search}%'
        query = query.filter(
            db.or_(
                Customer.name.ilike(search_pattern),
                Customer.phone.ilike(search_pattern),
                Customer.wechat.ilike(search_pattern),
                Customer.id.ilike(search_pattern)
            )
        )

    total = query.count()
    customers = query.order_by(Customer.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    customer_ids = [customer.id for customer in customers]
    balance_map = {}
    if customer_ids:
        balances = Balance.query.filter(Balance.customer_id.in_(customer_ids)).all()
        balance_map = {item.customer_id: (float(item.balance) if item.balance is not None else 0.0) for item in balances}

    return paginated_response(
        items=[_customer_to_dict(customer, balance_map) for customer in customers],
        total=total,
        page=page,
        page_size=page_size
    )


@customers_bp.route('/<customer_id>', methods=['GET'])
@token_required
def get_customer(customer_id):
    customer = _get_active_customer(customer_id)

    if not customer:
        return error_response('Customer not found', 404)

    customer_data = _customer_to_dict(customer)
    transactions = Transaction.query.filter_by(customer_id=customer_id).order_by(Transaction.transaction_time.desc()).all()
    customer_data['transactions'] = [transaction.to_dict() for transaction in transactions]

    return success_response(customer_data)


@customers_bp.route('', methods=['POST'])
@token_required
def create_customer():
    data = request.get_json()

    if not data:
        return error_response('No data provided', 400)

    name = data.get('name', '').strip()
    phone = data.get('phone', '').strip() if data.get('phone') else None
    wechat = data.get('wechat', '').strip() if data.get('wechat') else None

    try:
        birthday = _parse_birthday(data.get('birthday'))
    except ValueError:
        return error_response('Birthday must be in YYYY-MM-DD format', 400)

    if not name:
        return error_response('Name is required', 400)

    last_customer = Customer.query.order_by(Customer.id.desc()).first()

    if last_customer:
        try:
            last_num = int(last_customer.id[1:])
            new_num = last_num + 1
        except (ValueError, IndexError):
            new_num = 1
    else:
        new_num = 1

    customer_id = f'C{new_num:03d}'

    while Customer.query.get(customer_id):
        new_num += 1
        customer_id = f'C{new_num:03d}'

    customer = Customer(
        id=customer_id,
        name=name,
        phone=phone,
        wechat=wechat,
        birthday=birthday
    )

    db.session.add(customer)

    balance = Balance(
        customer_id=customer_id,
        balance=0.0
    )
    db.session.add(balance)

    db.session.commit()

    return success_response(_customer_to_dict(customer, {customer_id: 0.0}), 'Customer created successfully', 201)


@customers_bp.route('/<customer_id>', methods=['PUT'])
@token_required
def update_customer(customer_id):
    customer = _get_active_customer(customer_id)

    if not customer:
        return error_response('Customer not found', 404)

    data = request.get_json()

    if not data:
        return error_response('No data provided', 400)

    name = data.get('name')
    phone = data.get('phone')
    wechat = data.get('wechat')

    if name is not None:
        name = name.strip()
        if not name:
            return error_response('Name cannot be empty', 400)
        customer.name = name

    if phone is not None:
        customer.phone = phone.strip() if phone.strip() else None

    if wechat is not None:
        customer.wechat = wechat.strip() if wechat.strip() else None

    if 'birthday' in data:
        try:
            customer.birthday = _parse_birthday(data.get('birthday'))
        except ValueError:
            return error_response('Birthday must be in YYYY-MM-DD format', 400)

    db.session.commit()

    return success_response(_customer_to_dict(customer), 'Customer updated successfully')


@customers_bp.route('/<customer_id>', methods=['DELETE'])
@token_required
def delete_customer(customer_id):
    customer = _get_active_customer(customer_id)

    if not customer:
        return error_response('Customer not found', 404)

    try:
        # Stop running timers, but keep historical transactions.
        ActiveTimer.query.filter_by(customer_id=customer_id).delete(synchronize_session=False)
        customer.is_deleted = True
        customer.deleted_at = datetime.utcnow()
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return error_response(f'Delete customer failed: {str(e)}', 500)

    return success_response(message='Customer deleted successfully')


@customers_bp.route('/<customer_id>/balance', methods=['GET'])
@token_required
def get_customer_balance(customer_id):
    customer = _get_active_customer(customer_id)

    if not customer:
        return error_response('Customer not found', 404)

    balance = Balance.query.filter_by(customer_id=customer_id).first()

    if not balance:
        balance = Balance(
            customer_id=customer_id,
            balance=0.0
        )
        db.session.add(balance)
        db.session.commit()

    return success_response(balance.to_dict())

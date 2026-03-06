from datetime import datetime
import re
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
MISC_MARKER_PATTERN = re.compile(r'\s*\[\[MISC_B64:[A-Za-z0-9_-]+\]\]\s*$')


def _strip_misc_marker(description):
    text = str(description or '').strip()
    if not text:
        return ''
    return MISC_MARKER_PATTERN.sub('', text).strip()


def _calculate_transaction_balance_delta(transaction):
    tx_type = str(getattr(transaction, 'type', '') or '').strip().lower()
    amount = float(getattr(transaction, 'amount', 0.0) or 0.0)
    bonus_amount = float(getattr(transaction, 'bonus_amount', 0.0) or 0.0)

    if tx_type == 'recharge':
        return amount + bonus_amount
    if tx_type == 'consumption':
        return -amount
    return 0.0


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='admin')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class RevokedToken(db.Model):
    __tablename__ = 'revoked_tokens'

    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer)
    revoked_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime)

    def to_dict(self):
        return {
            'id': self.id,
            'jti': self.jti,
            'user_id': self.user_id,
            'revoked_at': self.revoked_at.isoformat() if self.revoked_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }


class Customer(db.Model):
    __tablename__ = 'customers'

    id = db.Column(db.String(10), primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20))
    wechat = db.Column(db.String(50))
    birthday = db.Column(db.Date)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    balance = db.relationship('Balance', backref='customer', uselist=False, lazy=True)
    transactions = db.relationship('Transaction', backref='customer', lazy=True)
    active_timers = db.relationship('ActiveTimer', backref='customer', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone,
            'wechat': self.wechat,
            'birthday': self.birthday.isoformat() if self.birthday else None,
            'is_deleted': bool(self.is_deleted),
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Balance(db.Model):
    __tablename__ = 'balances'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.String(10), db.ForeignKey('customers.id'), nullable=False)
    balance = db.Column(db.Float, default=0.0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'balance': self.balance,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None
        }


class Transaction(db.Model):
    __tablename__ = 'transactions'

    id = db.Column(db.String(10), primary_key=True)
    customer_id = db.Column(db.String(10), db.ForeignKey('customers.id'), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    bonus_amount = db.Column(db.Float, default=0.0)
    payment_method = db.Column(db.String(50))
    description = db.Column(db.String(255))
    activity_id = db.Column(db.String(10))
    operator = db.Column(db.String(50))
    status = db.Column(db.String(20), nullable=False, default='completed', index=True)
    cancelled_at = db.Column(db.DateTime)
    cancel_reason = db.Column(db.String(255))
    cancelled_by = db.Column(db.String(50))
    transaction_time = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        status = str(self.status or '').strip().lower() or 'completed'
        balance_delta = _calculate_transaction_balance_delta(self)
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'type': self.type,
            'amount': self.amount,
            'balance_delta': balance_delta,
            'bonus_amount': self.bonus_amount,
            'payment_method': self.payment_method,
            'description': _strip_misc_marker(self.description),
            'activity_id': self.activity_id,
            'operator': self.operator,
            'status': status,
            'cancelled_at': self.cancelled_at.isoformat() if self.cancelled_at else None,
            'cancel_reason': self.cancel_reason,
            'cancelled_by': self.cancelled_by,
            'transaction_time': self.transaction_time.isoformat() if self.transaction_time else None
        }


class Activity(db.Model):
    __tablename__ = 'activities'

    id = db.Column(db.String(10), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    min_amount = db.Column(db.Float)
    bonus_rate = db.Column(db.Float)
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'min_amount': self.min_amount,
            # Keep both keys for compatibility; business meaning is fixed gift amount.
            'bonus_amount': self.bonus_rate,
            'bonus_rate': self.bonus_rate,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class BillingRule(db.Model):
    __tablename__ = 'billing_rules'

    id = db.Column(db.Integer, primary_key=True)
    rule_type = db.Column(db.String(50), unique=True, nullable=False)
    rule_data = db.Column(db.JSON)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'rule_type': self.rule_type,
            'rule_data': self.rule_data,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class ActiveTimer(db.Model):
    __tablename__ = 'active_timers'

    id = db.Column(db.String(20), primary_key=True)
    customer_id = db.Column(db.String(10), db.ForeignKey('customers.id'), nullable=False)
    table_no = db.Column(db.String(30))
    start_time = db.Column(db.DateTime, nullable=False)
    timer_type = db.Column(db.String(50))
    notes = db.Column(db.String(255))
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'table_no': self.table_no,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'timer_type': self.timer_type,
            'notes': self.notes,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class BeadMaterial(db.Model):
    __tablename__ = 'bead_materials'

    id = db.Column(db.String(10), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    color_code = db.Column(db.String(20))
    spec = db.Column(db.String(50))
    brand = db.Column(db.String(50))
    unit = db.Column(db.String(20), default='gram', nullable=False)
    grams_per_bag = db.Column(db.Float)
    grams_per_bottle = db.Column(db.Float)
    market_price_per_500g = db.Column(db.Float, default=50.0, nullable=False)
    safe_stock = db.Column(db.Float, default=0.0, nullable=False)
    common_color = db.Column(db.Boolean, default=False, nullable=False)
    status = db.Column(db.String(20), default='active', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    balance = db.relationship('BeadInventoryBalance', backref='material', uselist=False, lazy=True)
    ledger_entries = db.relationship('BeadInventoryLedger', backref='material', lazy=True)
    stocktakes = db.relationship('BeadStocktake', backref='material', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'color_code': self.color_code,
            'spec': self.spec,
            'brand': self.brand,
            'unit': self.unit,
            'grams_per_bag': self.grams_per_bag,
            'grams_per_bottle': self.grams_per_bottle,
            'market_price_per_500g': float(self.market_price_per_500g or 0.0),
            'safe_stock': float(self.safe_stock or 0.0),
            'common_color': bool(self.common_color),
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class BeadInventoryBalance(db.Model):
    __tablename__ = 'bead_inventory_balances'

    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.String(10), db.ForeignKey('bead_materials.id'), nullable=False, unique=True)
    current_grams = db.Column(db.Float, default=0.0, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        current = float(self.current_grams or 0.0)
        return {
            'id': self.id,
            'material_id': self.material_id,
            'current_grams': current,
            'available_grams': current,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class BeadInventoryLedger(db.Model):
    __tablename__ = 'bead_inventory_ledgers'

    id = db.Column(db.String(32), primary_key=True)
    material_id = db.Column(db.String(10), db.ForeignKey('bead_materials.id'), nullable=False, index=True)
    action_type = db.Column(db.String(30), nullable=False, index=True)
    delta_grams = db.Column(db.Float, nullable=False)
    balance_after_grams = db.Column(db.Float, nullable=False)
    unit_input = db.Column(db.String(20), default='gram')
    unit_count = db.Column(db.Float)
    reference_no = db.Column(db.String(32), index=True)
    reason = db.Column(db.String(100))
    note = db.Column(db.String(255))
    operator = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'material_id': self.material_id,
            'action_type': self.action_type,
            'delta_grams': float(self.delta_grams or 0.0),
            'balance_after_grams': float(self.balance_after_grams or 0.0),
            'unit_input': self.unit_input,
            'unit_count': self.unit_count,
            'reference_no': self.reference_no,
            'reason': self.reason,
            'note': self.note,
            'operator': self.operator,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class BeadStocktake(db.Model):
    __tablename__ = 'bead_stocktakes'

    id = db.Column(db.String(32), primary_key=True)
    material_id = db.Column(db.String(10), db.ForeignKey('bead_materials.id'), nullable=False, index=True)
    previous_grams = db.Column(db.Float, nullable=False)
    counted_grams = db.Column(db.Float, nullable=False)
    difference_grams = db.Column(db.Float, nullable=False)
    note = db.Column(db.String(255))
    operator = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'material_id': self.material_id,
            'previous_grams': float(self.previous_grams or 0.0),
            'counted_grams': float(self.counted_grams or 0.0),
            'difference_grams': float(self.difference_grams or 0.0),
            'note': self.note,
            'operator': self.operator,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Log(db.Model):
    __tablename__ = 'logs'

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50))
    description = db.Column(db.String(255))
    context = db.Column(db.JSON)
    operator = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'description': self.description,
            'operator': self.operator,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }

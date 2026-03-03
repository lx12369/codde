from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


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
    transaction_time = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'type': self.type,
            'amount': self.amount,
            'bonus_amount': self.bonus_amount,
            'payment_method': self.payment_method,
            'description': self.description,
            'activity_id': self.activity_id,
            'operator': self.operator,
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
    start_time = db.Column(db.DateTime, nullable=False)
    timer_type = db.Column(db.String(50))
    notes = db.Column(db.String(255))
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'timer_type': self.timer_type,
            'notes': self.notes,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Log(db.Model):
    __tablename__ = 'logs'

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50))
    description = db.Column(db.String(255))
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

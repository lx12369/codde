import bcrypt
from .models import db, User
from sqlalchemy import inspect, text


def init_db(app):
    with app.app_context():
        db.create_all()
        ensure_customer_columns()
        create_default_admin()


def ensure_customer_columns():
    inspector = inspect(db.engine)
    if 'customers' not in inspector.get_table_names():
        return

    existing_columns = {column['name'] for column in inspector.get_columns('customers')}
    alter_statements = []

    if 'wechat' not in existing_columns:
        alter_statements.append('ALTER TABLE customers ADD COLUMN wechat VARCHAR(50)')

    if 'birthday' not in existing_columns:
        alter_statements.append('ALTER TABLE customers ADD COLUMN birthday DATE')

    if 'is_deleted' not in existing_columns:
        alter_statements.append('ALTER TABLE customers ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT 0')

    if 'deleted_at' not in existing_columns:
        alter_statements.append('ALTER TABLE customers ADD COLUMN deleted_at DATETIME')

    if not alter_statements:
        return

    for sql in alter_statements:
        db.session.execute(text(sql))

    db.session.commit()


def create_default_admin():
    existing_admin = User.query.filter_by(username='admin').first()
    if existing_admin:
        return

    password = 'admin123'
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    admin = User(
        username='admin',
        password_hash=password_hash,
        role='admin'
    )

    db.session.add(admin)
    db.session.commit()
    print('Default admin user created: username=admin, password=admin123')

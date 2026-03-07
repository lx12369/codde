import bcrypt
import json
import sys
from pathlib import Path
from .models import db, User
from sqlalchemy import inspect, text
from .models import BeadMaterial, BeadInventoryBalance


def init_db(app):
    with app.app_context():
        db.create_all()
        ensure_customer_columns()
        ensure_transaction_columns()
        ensure_active_timer_columns()
        ensure_bead_material_columns()
        ensure_log_columns()
        ensure_builtin_mard_materials()
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


def ensure_transaction_columns():
    inspector = inspect(db.engine)
    if 'transactions' not in inspector.get_table_names():
        return

    existing_columns = {column['name'] for column in inspector.get_columns('transactions')}
    alter_statements = []

    if 'status' not in existing_columns:
        alter_statements.append("ALTER TABLE transactions ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'completed'")
    if 'cancelled_at' not in existing_columns:
        alter_statements.append('ALTER TABLE transactions ADD COLUMN cancelled_at DATETIME')
    if 'cancel_reason' not in existing_columns:
        alter_statements.append('ALTER TABLE transactions ADD COLUMN cancel_reason VARCHAR(255)')
    if 'cancelled_by' not in existing_columns:
        alter_statements.append('ALTER TABLE transactions ADD COLUMN cancelled_by VARCHAR(50)')

    for sql in alter_statements:
        db.session.execute(text(sql))

    # 历史交易统一回填为 completed，避免前端状态为空。
    db.session.execute(text("UPDATE transactions SET status = 'completed' WHERE status IS NULL OR TRIM(status) = ''"))
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


def ensure_active_timer_columns():
    inspector = inspect(db.engine)
    if 'active_timers' not in inspector.get_table_names():
        return

    backend_name = db.engine.url.get_backend_name()
    columns = inspector.get_columns('active_timers')
    existing_columns = {column['name'] for column in columns}
    column_map = {column['name']: column for column in columns}
    alter_statements = []

    if 'table_no' not in existing_columns:
        alter_statements.append('ALTER TABLE active_timers ADD COLUMN table_no VARCHAR(30)')

    id_column = column_map.get('id')
    if backend_name == 'mysql' and id_column is not None:
        try:
            id_length = int(getattr(id_column.get('type'), 'length', 0) or 0)
        except (TypeError, ValueError):
            id_length = 0
        if id_length < 32:
            alter_statements.append('ALTER TABLE active_timers MODIFY COLUMN id VARCHAR(32) NOT NULL')

    notes_column = column_map.get('notes')
    if backend_name == 'mysql' and notes_column is not None:
        notes_type = str(notes_column.get('type') or '').lower()
        if 'text' not in notes_type:
            alter_statements.append('ALTER TABLE active_timers MODIFY COLUMN notes TEXT')

    if not alter_statements:
        return

    for sql in alter_statements:
        db.session.execute(text(sql))

    db.session.commit()


def ensure_bead_material_columns():
    inspector = inspect(db.engine)
    if 'bead_materials' not in inspector.get_table_names():
        return

    existing_columns = {column['name'] for column in inspector.get_columns('bead_materials')}
    alter_statements = []

    if 'common_color' not in existing_columns:
        alter_statements.append('ALTER TABLE bead_materials ADD COLUMN common_color BOOLEAN NOT NULL DEFAULT 0')
    if 'market_price_per_500g' not in existing_columns:
        alter_statements.append('ALTER TABLE bead_materials ADD COLUMN market_price_per_500g FLOAT NOT NULL DEFAULT 50')

    if not alter_statements:
        return

    for sql in alter_statements:
        db.session.execute(text(sql))

    db.session.commit()


def ensure_log_columns():
    inspector = inspect(db.engine)
    if 'logs' not in inspector.get_table_names():
        return

    existing_columns = {column['name'] for column in inspector.get_columns('logs')}
    alter_statements = []

    if 'context' not in existing_columns:
        alter_statements.append('ALTER TABLE logs ADD COLUMN context TEXT')

    if not alter_statements:
        return

    for sql in alter_statements:
        db.session.execute(text(sql))

    db.session.commit()


def _resolve_mard_palette_file():
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / 'data' / 'mard_palette_v1.json'
    return Path(__file__).resolve().parents[1] / 'data' / 'mard_palette_v1.json'


def _load_mard_palette():
    file_path = _resolve_mard_palette_file()
    if not file_path.exists():
        return []
    try:
        payload = json.loads(file_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return []
    return payload if isinstance(payload, list) else []


def _next_material_id():
    last_item = BeadMaterial.query.order_by(BeadMaterial.id.desc()).first()
    if not last_item:
        return 'M001'
    try:
        next_number = int(str(last_item.id)[1:]) + 1
    except (TypeError, ValueError, IndexError):
        next_number = 1

    candidate = f'M{next_number:03d}'
    while BeadMaterial.query.get(candidate):
        next_number += 1
        candidate = f'M{next_number:03d}'
    return candidate


def ensure_builtin_mard_materials():
    palette_items = _load_mard_palette()
    if not palette_items:
        return

    created = 0
    updated = 0

    for item in palette_items:
        code = str(item.get('code') or '').strip().upper()
        hex_value = str(item.get('hex') or '').strip().lower()
        if not code or not hex_value:
            continue

        name = code
        legacy_name = f'Mard {code}'
        material = BeadMaterial.query.filter_by(name=name).first()
        if not material:
            material = BeadMaterial.query.filter_by(name=legacy_name).first()

        if not material:
            material = BeadMaterial(
                id=_next_material_id(),
                name=name,
                color_code=hex_value,
                spec='2.6mm',
                brand='Mard',
                unit='gram',
                safe_stock=0.0,
                status='active'
            )
            db.session.add(material)
            db.session.add(BeadInventoryBalance(material_id=material.id, current_grams=0.0))
            created += 1
            continue

        changed = False
        if material.name != name:
            material.name = name
            changed = True
        if material.color_code != hex_value:
            material.color_code = hex_value
            changed = True
        if material.brand != 'Mard':
            material.brand = 'Mard'
            changed = True
        if material.unit != 'gram':
            material.unit = 'gram'
            changed = True
        if changed:
            updated += 1

        balance = BeadInventoryBalance.query.filter_by(material_id=material.id).first()
        if not balance:
            db.session.add(BeadInventoryBalance(material_id=material.id, current_grams=0.0))

    if created or updated:
        db.session.commit()

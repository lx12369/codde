from datetime import datetime
import json
from pathlib import Path

from flask import Blueprint, request
from sqlalchemy import func, cast, Integer

from models import (
    db,
    Customer,
    Balance,
    Transaction,
    BeadMaterial,
    BeadInventoryBalance,
    BeadInventoryLedger,
    BeadStocktake
)
from utils.audit_log import get_operator_name, write_log
from utils.bead_inventory_service import (
    parse_positive_number,
    convert_to_grams,
    generate_entity_id,
    generate_reference_no,
    get_or_create_balance,
    append_ledger,
    calc_recent_avg_daily_outbound_grams
)
from utils.decorators import token_required
from utils.response import success_response, error_response, paginated_response


bead_inventory_bp = Blueprint('bead_inventory', __name__)
BEAD_PURCHASE_CUSTOMER_ID = 'C000'


def _to_int(value, default):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed


def _page_params():
    page = _to_int(request.args.get('page', 1), 1)
    page_size = _to_int(request.args.get('page_size', request.args.get('pageSize', 10)), 10)
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 10
    return page, page_size


def _to_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {'1', 'true', 'yes', 'y', 'on'}:
        return True
    if text in {'0', 'false', 'no', 'n', 'off'}:
        return False
    return default


def _parse_non_negative_number(value):
    if value in (None, ''):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def _generate_material_id():
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


def _load_mard_palette():
    file_path = Path(__file__).resolve().parents[1] / 'data' / 'mard_palette_v1.json'
    if not file_path.exists():
        raise FileNotFoundError(f'Mard 色卡文件不存在：{file_path}')

    content = file_path.read_text(encoding='utf-8')
    data = json.loads(content)
    return data if isinstance(data, list) else []


def _material_payload(item, include_stats=False):
    payload = item.to_dict()
    balance = BeadInventoryBalance.query.filter_by(material_id=item.id).first()
    current_grams = float(balance.current_grams if balance else 0.0)
    payload['current_grams'] = current_grams
    payload['available_grams'] = current_grams
    payload['is_low_stock'] = current_grams < float(item.safe_stock or 0.0)

    if include_stats:
        avg_daily_outbound = calc_recent_avg_daily_outbound_grams(item.id, days=7)
        payload['avg_daily_outbound_grams_7d'] = avg_daily_outbound
        payload['estimated_days_left'] = (
            round(current_grams / avg_daily_outbound, 2)
            if avg_daily_outbound > 0
            else None
        )
    return payload


def _generate_transaction_id():
    last_transaction = Transaction.query.order_by(Transaction.id.desc()).first()
    if last_transaction:
        try:
            last_id_num = int(str(last_transaction.id)[1:])
            return f'T{last_id_num + 1:03d}'
        except (TypeError, ValueError, IndexError):
            pass
    return f'T{int(datetime.utcnow().timestamp() * 1000)}'


def _get_or_create_bead_purchase_customer():
    customer = Customer.query.filter_by(id=BEAD_PURCHASE_CUSTOMER_ID).first()
    if not customer:
        customer = Customer(
            id=BEAD_PURCHASE_CUSTOMER_ID,
            name='豆仓采购',
            is_deleted=True
        )
        db.session.add(customer)

    balance = Balance.query.filter_by(customer_id=BEAD_PURCHASE_CUSTOMER_ID).first()
    if not balance:
        db.session.add(Balance(customer_id=BEAD_PURCHASE_CUSTOMER_ID, balance=0.0))

    return customer


def _create_bead_purchase_transaction(material, grams, reference_no, operator):
    _get_or_create_bead_purchase_customer()

    raw_price = material.market_price_per_500g
    market_price = _parse_non_negative_number(raw_price)
    amount = round(grams * ((market_price or 0.0) / 500), 2)
    price_warning = ''
    if market_price is None:
        price_warning = '（市场价缺失或异常，按 0 元记账）'

    description = (
        f'买豆入库：{material.name}（{material.id}），'
        f'入库 {grams:.3f}g，单号 {reference_no}，'
        f'市场价 {market_price if market_price is not None else 0:.2f} 元/500g{price_warning}'
    )
    transaction = Transaction(
        id=_generate_transaction_id(),
        customer_id=BEAD_PURCHASE_CUSTOMER_ID,
        type='bead_purchase',
        amount=amount,
        bonus_amount=0.0,
        description=description,
        operator=operator
    )
    db.session.add(transaction)
    return transaction


@bead_inventory_bp.route('/materials/import-mard', methods=['POST'])
@token_required
def import_mard_palette():
    try:
        palette_items = _load_mard_palette()
    except Exception as exc:
        return error_response(f'加载 Mard 色卡失败：{exc}', 500)

    created = 0
    updated = 0
    skipped = 0

    for item in palette_items:
        code = str(item.get('code') or '').strip().upper()
        hex_value = str(item.get('hex') or '').strip().lower()
        if not code or not hex_value:
            skipped += 1
            continue

        name = code
        legacy_name = f'Mard {code}'
        material = BeadMaterial.query.filter_by(name=name).first()
        if not material:
            material = BeadMaterial.query.filter_by(name=legacy_name).first()
        if not material:
            material = BeadMaterial(
                id=_generate_material_id(),
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
        else:
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
            else:
                skipped += 1

    operator = get_operator_name()
    write_log(
        'bead_material_import_mard',
        f'导入 Mard 色卡：新建 {created}，更新 {updated}，跳过 {skipped}',
        operator=operator
    )
    db.session.commit()

    return success_response(
        {
            'created': created,
            'updated': updated,
            'skipped': skipped,
            'total': len(palette_items)
        },
        'Mard 色卡导入完成'
    )


@bead_inventory_bp.route('/materials/batch-conversion-standard', methods=['POST'])
@token_required
def batch_update_conversion_standard():
    data = request.get_json() or {}
    grams_per_bag = data.get('grams_per_bag')
    grams_per_bottle = data.get('grams_per_bottle')

    grams_per_bag_value = parse_positive_number(grams_per_bag) if grams_per_bag not in (None, '') else None
    grams_per_bottle_value = parse_positive_number(grams_per_bottle) if grams_per_bottle not in (None, '') else None
    if grams_per_bag not in (None, '') and grams_per_bag_value is None:
        return error_response('每袋克重必须是大于 0 的数字', 400)
    if grams_per_bottle not in (None, '') and grams_per_bottle_value is None:
        return error_response('每瓶克重必须是大于 0 的数字', 400)
    if grams_per_bag_value is None and grams_per_bottle_value is None:
        return error_response('请至少填写每袋克重或每瓶克重，不能全部清空', 400)

    materials = BeadMaterial.query.all()
    changed = 0
    for material in materials:
        need_change = (
            material.grams_per_bag != grams_per_bag_value
            or material.grams_per_bottle != grams_per_bottle_value
        )
        if need_change:
            material.grams_per_bag = grams_per_bag_value
            material.grams_per_bottle = grams_per_bottle_value
            changed += 1

    operator = get_operator_name()
    write_log(
        'bead_conversion_standard_batch_update',
        (
            f'批量更新单位换算标准：每袋={grams_per_bag_value if grams_per_bag_value is not None else "-"}g，'
            f'每瓶={grams_per_bottle_value if grams_per_bottle_value is not None else "-"}g，影响 {changed} 条'
        ),
        operator=operator
    )
    db.session.commit()

    return success_response(
        {
            'changed': changed,
            'total': len(materials),
            'grams_per_bag': grams_per_bag_value,
            'grams_per_bottle': grams_per_bottle_value
        },
        '已应用到全部豆料'
    )


@bead_inventory_bp.route('/materials/batch-market-price', methods=['POST'])
@token_required
def batch_update_market_price():
    data = request.get_json() or {}
    market_price_raw = data.get('market_price_per_500g', 50)
    market_price_value = _parse_non_negative_number(market_price_raw)
    if market_price_value is None:
        return error_response('市场价必须是大于等于 0 的数字', 400)

    materials = BeadMaterial.query.all()
    changed = 0
    for material in materials:
        if float(material.market_price_per_500g or 0.0) != float(market_price_value):
            material.market_price_per_500g = float(market_price_value)
            changed += 1

    operator = get_operator_name()
    write_log(
        'bead_market_price_batch_update',
        f'批量更新豆料市场价：¥{float(market_price_value):.2f}/500g，影响 {changed} 条',
        operator=operator
    )
    db.session.commit()

    return success_response(
        {
            'changed': changed,
            'total': len(materials),
            'market_price_per_500g': float(market_price_value),
            'market_price_per_gram': round(float(market_price_value) / 500, 4)
        },
        '已应用到全部豆料市场价'
    )


@bead_inventory_bp.route('/materials/batch-safe-stock-by-common-color', methods=['POST'])
@token_required
def batch_update_safe_stock_by_common_color():
    data = request.get_json() or {}

    common_safe_stock_raw = data.get('common_safe_stock')
    normal_safe_stock_raw = data.get('normal_safe_stock')

    common_safe_stock = _parse_non_negative_number(common_safe_stock_raw)
    normal_safe_stock = _parse_non_negative_number(normal_safe_stock_raw)

    if common_safe_stock is None:
        return error_response('常用色安全库存必须是大于等于 0 的数字', 400)
    if normal_safe_stock is None:
        return error_response('非常用色安全库存必须是大于等于 0 的数字', 400)

    materials = BeadMaterial.query.all()
    changed = 0
    changed_common = 0
    changed_normal = 0
    target_common = 0
    target_normal = 0

    for material in materials:
        is_common = bool(material.common_color)
        target_value = float(common_safe_stock if is_common else normal_safe_stock)
        if is_common:
            target_common += 1
        else:
            target_normal += 1

        if float(material.safe_stock or 0.0) != target_value:
            material.safe_stock = target_value
            changed += 1
            if is_common:
                changed_common += 1
            else:
                changed_normal += 1

    operator = get_operator_name()
    write_log(
        'bead_safe_stock_batch_update_by_common_color',
        (
            f'按常用色分类批量更新安全库存：常用色={float(common_safe_stock):.3f}g，'
            f'非常用色={float(normal_safe_stock):.3f}g，'
            f'常用色影响 {changed_common}/{target_common} 条，'
            f'非常用色影响 {changed_normal}/{target_normal} 条'
        ),
        operator=operator
    )
    db.session.commit()

    return success_response(
        {
            'changed': changed,
            'changed_common': changed_common,
            'changed_normal': changed_normal,
            'total': len(materials),
            'target_common': target_common,
            'target_normal': target_normal,
            'common_safe_stock': float(common_safe_stock),
            'normal_safe_stock': float(normal_safe_stock)
        },
        '已按常用色分类更新安全库存'
    )


@bead_inventory_bp.route('/materials', methods=['GET'])
@token_required
def get_materials():
    page, page_size = _page_params()
    search = str(request.args.get('search', '') or '').strip()
    status = str(request.args.get('status', 'all') or 'all').strip().lower()

    query = BeadMaterial.query
    if status in {'active', 'inactive'}:
        query = query.filter(BeadMaterial.status == status)

    if search:
        pattern = f'%{search}%'
        query = query.filter(
            db.or_(
                BeadMaterial.id.ilike(pattern),
                BeadMaterial.name.ilike(pattern),
                BeadMaterial.color_code.ilike(pattern),
                BeadMaterial.spec.ilike(pattern),
                BeadMaterial.brand.ilike(pattern)
            )
        )

    total = query.count()
    items = (
        query.order_by(
            BeadMaterial.common_color.desc(),
            func.upper(func.substr(BeadMaterial.name, 1, 1)).asc(),
            cast(func.substr(BeadMaterial.name, 2), Integer).asc(),
            BeadMaterial.name.asc()
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return paginated_response([_material_payload(item) for item in items], total, page, page_size)


@bead_inventory_bp.route('/materials', methods=['POST'])
@token_required
def create_material():
    data = request.get_json() or {}
    name = str(data.get('name', '') or '').strip()
    if not name:
        return error_response('豆料名称不能为空', 400)

    safe_stock = data.get('safe_stock', 0)
    safe_stock_value = parse_positive_number(safe_stock)
    if safe_stock in (0, '0', 0.0, None, ''):
        safe_stock_value = 0.0
    if safe_stock_value is None:
        return error_response('安全库存必须是大于等于 0 的数字', 400)

    grams_per_bag = data.get('grams_per_bag')
    grams_per_bottle = data.get('grams_per_bottle')
    grams_per_bag_value = parse_positive_number(grams_per_bag) if grams_per_bag not in (None, '') else None
    grams_per_bottle_value = parse_positive_number(grams_per_bottle) if grams_per_bottle not in (None, '') else None
    if grams_per_bag not in (None, '') and grams_per_bag_value is None:
        return error_response('每袋克重必须是大于 0 的数字', 400)
    if grams_per_bottle not in (None, '') and grams_per_bottle_value is None:
        return error_response('每瓶克重必须是大于 0 的数字', 400)
    market_price_raw = data.get('market_price_per_500g', 50)
    market_price_value = _parse_non_negative_number(market_price_raw)
    if market_price_value is None:
        return error_response('市场价必须是大于等于 0 的数字', 400)

    material = BeadMaterial(
        id=_generate_material_id(),
        name=name,
        color_code=str(data.get('color_code', '') or '').strip() or None,
        spec=str(data.get('spec', '') or '').strip() or None,
        brand=str(data.get('brand', '') or '').strip() or None,
        unit='gram',
        grams_per_bag=grams_per_bag_value,
        grams_per_bottle=grams_per_bottle_value,
        market_price_per_500g=float(market_price_value),
        safe_stock=float(safe_stock_value or 0.0),
        common_color=_to_bool(data.get('common_color'), False),
        status='active'
    )
    db.session.add(material)
    db.session.add(BeadInventoryBalance(material_id=material.id, current_grams=0.0))

    operator = get_operator_name()
    write_log('bead_material_create', f'创建豆料：{material.name}（{material.id}）', operator=operator)
    db.session.commit()
    return success_response(_material_payload(material), '豆料创建成功', 201)


@bead_inventory_bp.route('/materials/<material_id>', methods=['PUT'])
@token_required
def update_material(material_id):
    material = BeadMaterial.query.filter_by(id=material_id).first()
    if not material:
        return error_response('豆料不存在', 404)

    data = request.get_json() or {}
    name = data.get('name')
    if name is not None:
        name = str(name).strip()
        if not name:
            return error_response('豆料名称不能为空', 400)
        material.name = name

    if 'color_code' in data:
        material.color_code = str(data.get('color_code') or '').strip() or None
    if 'spec' in data:
        material.spec = str(data.get('spec') or '').strip() or None
    if 'brand' in data:
        material.brand = str(data.get('brand') or '').strip() or None
    if 'status' in data:
        status = str(data.get('status') or '').strip().lower()
        if status not in {'active', 'inactive'}:
            return error_response('状态仅支持 active 或 inactive', 400)
        material.status = status
    if 'common_color' in data:
        material.common_color = _to_bool(data.get('common_color'), False)
    if 'safe_stock' in data:
        safe_stock = data.get('safe_stock')
        safe_stock_value = parse_positive_number(safe_stock)
        if safe_stock in (0, '0', 0.0):
            safe_stock_value = 0.0
        if safe_stock_value is None:
            return error_response('安全库存必须是大于等于 0 的数字', 400)
        material.safe_stock = float(safe_stock_value or 0.0)
    if 'grams_per_bag' in data:
        value = data.get('grams_per_bag')
        parsed = parse_positive_number(value) if value not in (None, '') else None
        if value not in (None, '') and parsed is None:
            return error_response('每袋克重必须是大于 0 的数字', 400)
        material.grams_per_bag = parsed
    if 'grams_per_bottle' in data:
        value = data.get('grams_per_bottle')
        parsed = parse_positive_number(value) if value not in (None, '') else None
        if value not in (None, '') and parsed is None:
            return error_response('每瓶克重必须是大于 0 的数字', 400)
        material.grams_per_bottle = parsed
    if 'market_price_per_500g' in data:
        value = _parse_non_negative_number(data.get('market_price_per_500g'))
        if value is None:
            return error_response('市场价必须是大于等于 0 的数字', 400)
        material.market_price_per_500g = float(value)

    operator = get_operator_name()
    write_log('bead_material_update', f'更新豆料：{material.name}（{material.id}）', operator=operator)
    db.session.commit()
    return success_response(_material_payload(material), '豆料更新成功')


@bead_inventory_bp.route('/materials/<material_id>', methods=['DELETE'])
@token_required
def delete_material(material_id):
    material = BeadMaterial.query.filter_by(id=material_id).first()
    if not material:
        return error_response('豆料不存在', 404)

    ledger_count = BeadInventoryLedger.query.filter_by(material_id=material_id).count()
    balance = BeadInventoryBalance.query.filter_by(material_id=material_id).first()
    current_grams = float(balance.current_grams if balance else 0.0)
    if ledger_count > 0 or current_grams > 0:
        return error_response('该豆料已存在流水或库存，不允许删除', 400)

    if balance:
        db.session.delete(balance)
    db.session.delete(material)
    operator = get_operator_name()
    write_log('bead_material_delete', f'删除豆料：{material.name}（{material.id}）', operator=operator)
    db.session.commit()
    return success_response(message='豆料删除成功')


@bead_inventory_bp.route('/balances', methods=['GET'])
@token_required
def get_balances():
    page, page_size = _page_params()
    search = str(request.args.get('search', '') or '').strip()
    query = BeadMaterial.query.filter(BeadMaterial.status == 'active')
    if search:
        pattern = f'%{search}%'
        query = query.filter(
            db.or_(
                BeadMaterial.id.ilike(pattern),
                BeadMaterial.name.ilike(pattern),
                BeadMaterial.color_code.ilike(pattern)
            )
        )

    total = query.count()
    items = (
        query.order_by(BeadMaterial.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return paginated_response([_material_payload(item, include_stats=True) for item in items], total, page, page_size)


@bead_inventory_bp.route('/inbound', methods=['POST'])
@token_required
def create_inbound():
    data = request.get_json() or {}
    material_id = str(data.get('material_id') or '').strip()
    quantity = data.get('quantity')
    unit = data.get('quantity_unit', 'gram')
    source = str(data.get('source') or '').strip()
    note = str(data.get('note') or '').strip()

    if not material_id:
        return error_response('material_id 不能为空', 400)

    material = BeadMaterial.query.filter_by(id=material_id).first()
    if not material:
        return error_response('豆料不存在', 404)

    try:
        grams, normalized_unit = convert_to_grams(material, unit, quantity)
    except ValueError as exc:
        return error_response(str(exc), 400)

    balance = get_or_create_balance(material_id)
    balance.current_grams = float(balance.current_grams or 0.0) + grams
    reference_no = generate_reference_no('IN')
    operator = get_operator_name()

    ledger = append_ledger(
        material_id=material_id,
        action_type='inbound',
        delta_grams=grams,
        balance_after_grams=balance.current_grams,
        unit_input=normalized_unit,
        unit_count=float(quantity),
        reference_no=reference_no,
        reason=source or '补货入库',
        note=note,
        operator=operator
    )
    transaction = _create_bead_purchase_transaction(material, grams, reference_no, operator)
    write_log(
        'bead_inventory_inbound',
        f'豆料入库：{material.name}（{material_id}） +{grams:.3f}g，单号 {reference_no}',
        operator=operator
    )
    db.session.commit()

    return success_response({
        'ledger': ledger.to_dict(),
        'transaction': transaction.to_dict(),
        'balance': balance.to_dict(),
        'material': _material_payload(material)
    }, '入库成功', 201)


@bead_inventory_bp.route('/outbound', methods=['POST'])
@token_required
def create_outbound():
    data = request.get_json() or {}
    material_id = str(data.get('material_id') or '').strip()
    quantity = data.get('quantity')
    unit = data.get('quantity_unit', 'gram')
    usage_type = str(data.get('usage_type') or '').strip()
    note = str(data.get('note') or '').strip()
    outbound_type = str(data.get('outbound_type') or 'outbound').strip().lower()

    if not material_id:
        return error_response('material_id 不能为空', 400)
    if outbound_type not in {'outbound', 'loss'}:
        return error_response('outbound_type 仅支持 outbound 或 loss', 400)

    material = BeadMaterial.query.filter_by(id=material_id).first()
    if not material:
        return error_response('豆料不存在', 404)

    try:
        grams, normalized_unit = convert_to_grams(material, unit, quantity)
    except ValueError as exc:
        return error_response(str(exc), 400)

    balance = get_or_create_balance(material_id)
    current_grams = float(balance.current_grams or 0.0)
    if current_grams + 1e-9 < grams:
        return error_response('库存不足，无法出库', 400)

    balance.current_grams = round(current_grams - grams, 3)
    reference_no = generate_reference_no('OUT')
    operator = get_operator_name()
    delta = -grams

    ledger = append_ledger(
        material_id=material_id,
        action_type=outbound_type,
        delta_grams=delta,
        balance_after_grams=balance.current_grams,
        unit_input=normalized_unit,
        unit_count=float(quantity),
        reference_no=reference_no,
        reason=usage_type or ('损耗出库' if outbound_type == 'loss' else '常规出库'),
        note=note,
        operator=operator
    )
    write_log(
        'bead_inventory_outbound' if outbound_type == 'outbound' else 'bead_inventory_loss',
        f'豆料出库：{material.name}（{material_id}） {delta:.3f}g，单号 {reference_no}',
        operator=operator
    )
    db.session.commit()

    return success_response({
        'ledger': ledger.to_dict(),
        'balance': balance.to_dict(),
        'material': _material_payload(material)
    }, '出库成功', 201)


@bead_inventory_bp.route('/stocktake', methods=['POST'])
@token_required
def create_stocktake():
    data = request.get_json() or {}
    material_id = str(data.get('material_id') or '').strip()
    counted_quantity = data.get('counted_quantity')
    counted_unit = data.get('counted_unit', 'gram')
    note = str(data.get('note') or '').strip()

    if not material_id:
        return error_response('material_id 不能为空', 400)

    material = BeadMaterial.query.filter_by(id=material_id).first()
    if not material:
        return error_response('豆料不存在', 404)

    try:
        counted_grams, normalized_unit = convert_to_grams(material, counted_unit, counted_quantity)
    except ValueError as exc:
        return error_response(str(exc), 400)

    balance = get_or_create_balance(material_id)
    previous_grams = float(balance.current_grams or 0.0)
    difference_grams = round(counted_grams - previous_grams, 3)
    balance.current_grams = counted_grams
    operator = get_operator_name()
    reference_no = generate_reference_no('ST')

    stocktake = BeadStocktake(
        id=generate_entity_id('BS'),
        material_id=material_id,
        previous_grams=previous_grams,
        counted_grams=counted_grams,
        difference_grams=difference_grams,
        note=note or None,
        operator=operator
    )
    db.session.add(stocktake)

    ledger = append_ledger(
        material_id=material_id,
        action_type='stocktake_adjust',
        delta_grams=difference_grams,
        balance_after_grams=counted_grams,
        unit_input=normalized_unit,
        unit_count=float(counted_quantity),
        reference_no=reference_no,
        reason='盘点调整',
        note=note,
        operator=operator
    )
    write_log(
        'bead_inventory_stocktake',
        (
            f'豆料盘点：{material.name}（{material_id}）'
            f' 实盘 {counted_grams:.3f}g，差异 {difference_grams:.3f}g，单号 {reference_no}'
        ),
        operator=operator
    )
    db.session.commit()

    return success_response({
        'stocktake': stocktake.to_dict(),
        'ledger': ledger.to_dict(),
        'balance': balance.to_dict(),
        'material': _material_payload(material)
    }, '盘点成功', 201)


@bead_inventory_bp.route('/ledger', methods=['GET'])
@token_required
def get_ledger():
    page, page_size = _page_params()
    material_id = str(request.args.get('material_id', '') or '').strip()
    action_type = str(request.args.get('action_type', '') or '').strip()
    date_start = str(request.args.get('date_start', '') or '').strip()
    date_end = str(request.args.get('date_end', '') or '').strip()

    query = BeadInventoryLedger.query
    if material_id:
        query = query.filter(BeadInventoryLedger.material_id == material_id)
    if action_type:
        query = query.filter(BeadInventoryLedger.action_type == action_type)
    if date_start:
        try:
            start = datetime.fromisoformat(date_start)
            query = query.filter(BeadInventoryLedger.created_at >= start)
        except ValueError:
            return error_response('date_start 格式错误，应为 ISO 日期时间', 400)
    if date_end:
        try:
            end = datetime.fromisoformat(date_end)
            query = query.filter(BeadInventoryLedger.created_at <= end)
        except ValueError:
            return error_response('date_end 格式错误，应为 ISO 日期时间', 400)

    total = query.count()
    items = (
        query.order_by(BeadInventoryLedger.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return paginated_response([item.to_dict() for item in items], total, page, page_size)


@bead_inventory_bp.route('/alerts', methods=['GET'])
@token_required
def get_alerts():
    materials = BeadMaterial.query.filter_by(status='active').order_by(BeadMaterial.name.asc()).all()
    items = []
    for material in materials:
        payload = _material_payload(material, include_stats=True)
        payload['alert_level'] = 'low' if payload['is_low_stock'] else 'normal'
        if payload['is_low_stock']:
            items.append(payload)

    return success_response({
        'items': items,
        'summary': {
            'total_alerts': len(items)
        }
    })

from flask import Blueprint, request
from models.models import db, BillingRule
from utils.audit_log import get_operator_name, write_log
from utils.decorators import token_required
from utils.response import success_response, error_response

billing_bp = Blueprint('billing', __name__)

DEFAULT_RULES = {
    'limited': {
        'price1h': 18.9,
        'price2h': 35.8,
        'overtimeFreeMinutes': 10,
        'overtime10to30Fee': 10,
        'overtime30Fee': 18.9
    },
    'weekday': {
        'singleUnlimited': 53.9,
        'doubleUnlimited': 103.9,
        'singleLimited': 35.9
    },
    'weekend': {
        'singleUnlimited': 63.9,
        'doubleUnlimited': 123.9,
        'singleLimited': 42.8
    },
    'materials': {
        'largeImageFee': 5,
        'extraSmallImageFee': 3,
        'extraLargeImageFee': 5
    },
    'overtime': {
        'ratePerMinute': 0.5
    }
}


def _to_float(value, fallback=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(fallback)


def _to_int(value, fallback=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(fallback)


def normalize_limited_rule_data(rule_data):
    merged = dict(DEFAULT_RULES['limited'])
    if isinstance(rule_data, dict):
        merged.update(rule_data)

    price1h = max(0.0, _to_float(merged.get('price1h'), DEFAULT_RULES['limited']['price1h']))
    price2h = max(0.0, _to_float(merged.get('price2h'), DEFAULT_RULES['limited']['price2h']))
    overtime_free_minutes = max(0, _to_int(merged.get('overtimeFreeMinutes'), DEFAULT_RULES['limited']['overtimeFreeMinutes']))
    overtime_10_to_30_fee = max(0.0, _to_float(merged.get('overtime10to30Fee'), DEFAULT_RULES['limited']['overtime10to30Fee']))
    overtime_30_fee = max(0.0, _to_float(merged.get('overtime30Fee'), price1h or DEFAULT_RULES['limited']['overtime30Fee']))

    # Historical data could persist all overtime values as zero by mistake.
    # Auto-heal to default overtime policy when this corrupted pattern appears.
    if (
        overtime_free_minutes == 0
        and overtime_10_to_30_fee == 0
        and overtime_30_fee == 0
        and price1h > 0
    ):
        overtime_free_minutes = DEFAULT_RULES['limited']['overtimeFreeMinutes']
        overtime_10_to_30_fee = DEFAULT_RULES['limited']['overtime10to30Fee']
        overtime_30_fee = price1h

    return {
        'price1h': price1h,
        'price2h': price2h,
        'overtimeFreeMinutes': overtime_free_minutes,
        'overtime10to30Fee': overtime_10_to_30_fee,
        'overtime30Fee': overtime_30_fee
    }


def normalize_overtime_rule_data(rule_data):
    merged = dict(DEFAULT_RULES['overtime'])
    if isinstance(rule_data, dict):
        merged.update(rule_data)

    return {
        'ratePerMinute': max(0.0, _to_float(merged.get('ratePerMinute'), DEFAULT_RULES['overtime']['ratePerMinute']))
    }


def get_or_create_rule(rule_type):
    rule = BillingRule.query.filter_by(rule_type=rule_type).first()
    if not rule:
        rule = BillingRule(
            rule_type=rule_type,
            rule_data=DEFAULT_RULES.get(rule_type, {})
        )
        db.session.add(rule)
        db.session.commit()
    return rule


@billing_bp.route('/billing-rules', methods=['GET'])
@token_required
def get_billing_rules():
    rules = BillingRule.query.all()

    result = {
        'limited': None,
        'weekday': None,
        'weekend': None,
        'materials': None,
        'overtime': None
    }

    existing_types = {rule.rule_type: rule for rule in rules}
    should_commit = False

    for rule_type in result.keys():
        if rule_type in existing_types:
            current_data = existing_types[rule_type].rule_data
            if rule_type == 'limited':
                normalized_data = normalize_limited_rule_data(current_data)
                result[rule_type] = normalized_data
                if normalized_data != current_data:
                    existing_types[rule_type].rule_data = normalized_data
                    should_commit = True
            elif rule_type == 'overtime':
                normalized_data = normalize_overtime_rule_data(current_data)
                result[rule_type] = normalized_data
                if normalized_data != current_data:
                    existing_types[rule_type].rule_data = normalized_data
                    should_commit = True
            else:
                result[rule_type] = current_data
        else:
            default_data = DEFAULT_RULES.get(rule_type, {})
            if rule_type == 'limited':
                default_data = normalize_limited_rule_data(default_data)
            elif rule_type == 'overtime':
                default_data = normalize_overtime_rule_data(default_data)
            result[rule_type] = default_data

    if should_commit:
        db.session.commit()

    return success_response(result)


@billing_bp.route('/billing-rules', methods=['PUT'])
@token_required
def update_billing_rules():
    data = request.get_json()

    if not data:
        return error_response('Request body is required', 400)

    valid_types = ['limited', 'weekday', 'weekend', 'materials', 'overtime']
    updated_rules = {}

    for rule_type in valid_types:
        if rule_type in data:
            rule_data = data[rule_type]

            if not isinstance(rule_data, dict):
                return error_response(f'Invalid data format for {rule_type}', 400)

            if rule_type == 'limited':
                rule_data = normalize_limited_rule_data(rule_data)
            elif rule_type == 'overtime':
                rule_data = normalize_overtime_rule_data(rule_data)

            rule = BillingRule.query.filter_by(rule_type=rule_type).first()

            if rule:
                rule.rule_data = rule_data
            else:
                rule = BillingRule(
                    rule_type=rule_type,
                    rule_data=rule_data
                )
                db.session.add(rule)

            updated_rules[rule_type] = rule_data

    if updated_rules:
        operator = get_operator_name(default='unknown')
        rule_names = '、'.join(sorted(updated_rules.keys()))
        write_log(
            'billing_rule_update',
            f'更新计费规则：{rule_names}',
            operator=operator
        )

    db.session.commit()

    result = {}
    for rule_type in valid_types:
        rule = BillingRule.query.filter_by(rule_type=rule_type).first()
        if rule:
            if rule_type == 'limited':
                result[rule_type] = normalize_limited_rule_data(rule.rule_data)
            elif rule_type == 'overtime':
                result[rule_type] = normalize_overtime_rule_data(rule.rule_data)
            else:
                result[rule_type] = rule.rule_data
        else:
            result[rule_type] = DEFAULT_RULES.get(rule_type, {})

    return success_response(result, 'Billing rules updated successfully')

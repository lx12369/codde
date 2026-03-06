import base64
import json
import re

MISC_MARKER_PREFIX = '[[MISC_B64:'
MISC_MARKER_PATTERN = re.compile(r'\s*\[\[MISC_B64:(?P<payload>[A-Za-z0-9_-]+)\]\]\s*$')


def _to_non_negative_int(value, default=0):
    try:
        num = int(float(value))
    except (TypeError, ValueError):
        num = int(default)
    return max(0, num)


def normalize_misc_selections(raw):
    if not isinstance(raw, dict):
        return {}

    result = {}
    for key, value in raw.items():
        item_id = str(key or '').strip()
        if not item_id:
            continue

        quantity = _to_non_negative_int(value, 0)
        if quantity <= 0:
            continue
        result[item_id] = quantity

    return result


def _encode_payload(selections):
    normalized = normalize_misc_selections(selections)
    if not normalized:
        return ''

    text = json.dumps(normalized, ensure_ascii=True, sort_keys=True, separators=(',', ':'))
    encoded = base64.urlsafe_b64encode(text.encode('utf-8')).decode('ascii')
    return encoded.rstrip('=')


def _decode_payload(payload):
    raw = str(payload or '').strip()
    if not raw:
        return {}

    padding = '=' * ((4 - len(raw) % 4) % 4)
    try:
        decoded = base64.urlsafe_b64decode((raw + padding).encode('ascii')).decode('utf-8')
        parsed = json.loads(decoded)
    except (ValueError, TypeError, json.JSONDecodeError):
        return {}

    return normalize_misc_selections(parsed)


def compose_description_with_misc(description, selections):
    clean_description, _ = split_description_and_misc(description)
    payload = _encode_payload(selections)
    if not payload:
        return clean_description

    marker = f'{MISC_MARKER_PREFIX}{payload}]]'
    if not clean_description:
        return marker
    return f'{clean_description} {marker}'


def split_description_and_misc(description):
    text = str(description or '').strip()
    if not text:
        return '', {}

    matched = MISC_MARKER_PATTERN.search(text)
    if not matched:
        return text, {}

    selections = _decode_payload(matched.group('payload'))
    if not selections:
        return text, {}

    clean_description = text[:matched.start()].strip()
    return clean_description, selections


def extract_misc_selections(description):
    _, selections = split_description_and_misc(description)
    return selections


def strip_misc_marker(description):
    clean, _ = split_description_and_misc(description)
    return clean

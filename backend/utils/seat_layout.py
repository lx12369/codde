import json
import re

TABLE_AREA_OPTIONS = list('ABCDEFGHJKLMNPQRSTUVWXYZ')
TABLE_SEAT_OPTIONS = [str(index) for index in range(1, 101)]
TABLE_NO_PATTERN = re.compile(r'^([A-HJ-NP-Za-hj-np-z])桌([1-9]|[1-9][0-9]|100)号$')
SEAT_LAYOUT_VERSION = 1
SEAT_LAYOUT_CONFIG_KEY = 'default'
FIXED_SEAT_LAYOUT_SECTIONS = [
    {
        'key': 'living',
        'tables': [
            {'area': 'F', 'seat_count': 4},
            {'area': 'C', 'seat_count': 6},
            {'area': 'E', 'seat_count': 4},
            {'area': 'B', 'seat_count': 6},
            {'area': 'D', 'seat_count': 4},
            {'area': 'A', 'seat_count': 6},
        ],
    },
    {
        'key': 'small',
        'tables': [
            {'area': 'G', 'seat_count': 4},
            {'area': 'H', 'seat_count': 4},
            {'area': 'J', 'seat_count': 2},
        ],
    },
    {
        'key': 'garden',
        'tables': [
            {'area': 'K', 'seat_count': 6},
            {'area': 'L', 'seat_count': 4},
        ],
    },
    {
        'key': 'upstairs',
        'tables': [
            {'area': 'M', 'seat_count': 3},
        ],
    },
]


def normalize_table_area(value, fallback=TABLE_AREA_OPTIONS[0]):
    normalized = str(value or '').strip().upper()
    if normalized in TABLE_AREA_OPTIONS:
        return normalized
    if fallback == '':
        return ''
    return fallback if fallback in TABLE_AREA_OPTIONS else TABLE_AREA_OPTIONS[0]


def normalize_table_seat(value, fallback=''):
    normalized = str(value or '').strip()
    if normalized in TABLE_SEAT_OPTIONS:
        return normalized
    fallback_value = str(fallback or '').strip()
    if fallback_value in TABLE_SEAT_OPTIONS:
        return fallback_value
    return ''


def build_table_no(area='', seat=''):
    normalized_area = normalize_table_area(area, '')
    normalized_seat = normalize_table_seat(seat, '')
    if not normalized_area or not normalized_seat:
        return ''
    return f'{normalized_area}桌{normalized_seat}号'


def normalize_table_no(value=''):
    raw = str(value or '').strip()
    matched = TABLE_NO_PATTERN.match(raw)
    if not matched:
        return raw
    return build_table_no(matched.group(1), matched.group(2))


def is_valid_table_no(value=''):
    return bool(TABLE_NO_PATTERN.match(normalize_table_no(value)))


def parse_table_no_parts(table_no='', fallback_area=TABLE_AREA_OPTIONS[0], fallback_seat=TABLE_SEAT_OPTIONS[0]):
    matched = TABLE_NO_PATTERN.match(normalize_table_no(table_no))
    if not matched:
        return {
            'tableArea': normalize_table_area(fallback_area, TABLE_AREA_OPTIONS[0]),
            'tableSeat': normalize_table_seat(fallback_seat, ''),
        }
    return {
        'tableArea': normalize_table_area(matched.group(1), fallback_area),
        'tableSeat': normalize_table_seat(matched.group(2), fallback_seat),
    }


def build_slot_key(section_key='', table_key='', seat_index=''):
    return f'{str(section_key or "").strip()}:{normalize_table_area(table_key, "")}:{str(seat_index or "").strip()}'


def get_fixed_seat_slots():
    slots = []
    for section in FIXED_SEAT_LAYOUT_SECTIONS:
        section_key = section['key']
        for table in section['tables']:
            table_key = table['area']
            seat_count = int(table['seat_count'])
            for index in range(seat_count):
                seat_index = str(index + 1)
                slot_key = build_slot_key(section_key, table_key, seat_index)
                slots.append({
                    'slotKey': slot_key,
                    'sectionKey': section_key,
                    'tableKey': table_key,
                    'seatIndex': seat_index,
                    'tableArea': table_key,
                    'tableSeat': seat_index,
                    'tableNo': build_table_no(table_key, seat_index),
                })
    return slots


FIXED_SEAT_SLOTS = get_fixed_seat_slots()
FIXED_SEAT_SLOT_MAP = {slot['slotKey']: slot for slot in FIXED_SEAT_SLOTS}


def create_default_seat_layout_config():
    return {
        'version': SEAT_LAYOUT_VERSION,
        'slots': {
            slot['slotKey']: {
                'tableArea': slot['tableArea'],
                'tableSeat': slot['tableSeat'],
            }
            for slot in FIXED_SEAT_SLOTS
        },
    }


def _build_candidate_slot_assignment(slot_key, raw_slots):
    default_slot = FIXED_SEAT_SLOT_MAP[slot_key]
    raw_slot = raw_slots.get(slot_key)
    if not isinstance(raw_slot, dict):
        return {
            'tableArea': default_slot['tableArea'],
            'tableSeat': default_slot['tableSeat'],
        }

    return {
        'tableArea': normalize_table_area(raw_slot.get('tableArea'), default_slot['tableArea']),
        'tableSeat': normalize_table_seat(raw_slot.get('tableSeat'), default_slot['tableSeat']),
    }


def _normalize_seat_layout_slots(raw_slots):
    normalized_slots = {}
    used_table_nos = {}
    duplicates = []

    for slot in FIXED_SEAT_SLOTS:
        slot_key = slot['slotKey']
        assignment = _build_candidate_slot_assignment(slot_key, raw_slots)
        table_no = build_table_no(assignment['tableArea'], assignment['tableSeat'])
        if not table_no:
            duplicates.append(slot_key)
            continue
        if table_no in used_table_nos:
            duplicates.extend([used_table_nos[table_no], slot_key])
            continue
        used_table_nos[table_no] = slot_key
        normalized_slots[slot_key] = assignment

    return normalized_slots, duplicates


def normalize_seat_layout_config(raw_config=None, strict=False):
    default_config = create_default_seat_layout_config()
    if not isinstance(raw_config, dict):
        if strict:
            raise ValueError('座位配置格式不正确')
        return default_config

    raw_slots = raw_config.get('slots')
    if not isinstance(raw_slots, dict):
        if strict:
            raise ValueError('座位配置缺少 slots')
        return default_config

    normalized_slots, duplicates = _normalize_seat_layout_slots(raw_slots)
    if duplicates or len(normalized_slots) != len(FIXED_SEAT_SLOTS):
        if strict:
            raise ValueError('座位编号不能重复，且每个固定座位都必须配置有效编号')
        return default_config

    return {
        'version': SEAT_LAYOUT_VERSION,
        'slots': normalized_slots,
    }


def get_allowed_table_no_set(config=None):
    normalized = normalize_seat_layout_config(config, strict=False)
    return {
        build_table_no(slot['tableArea'], slot['tableSeat'])
        for slot in normalized['slots'].values()
    }


def build_table_no_remap(old_config=None, new_config=None):
    previous = normalize_seat_layout_config(old_config, strict=False)
    current = normalize_seat_layout_config(new_config, strict=False)
    remap = {}
    for slot in FIXED_SEAT_SLOTS:
        slot_key = slot['slotKey']
        old_slot = previous['slots'][slot_key]
        new_slot = current['slots'][slot_key]
        old_table_no = build_table_no(old_slot['tableArea'], old_slot['tableSeat'])
        new_table_no = build_table_no(new_slot['tableArea'], new_slot['tableSeat'])
        if old_table_no and new_table_no:
            remap[old_table_no] = new_table_no
    return remap


def extract_extra_table_nos_from_notes(raw_notes):
    text = str(raw_notes or '').strip()
    if not text:
        return []

    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []

    if not isinstance(parsed, dict):
        return []

    normalized = []
    seen = set()

    extra_table_nos = parsed.get('extraTableNos')
    if isinstance(extra_table_nos, list):
        for item in extra_table_nos:
            table_no = normalize_table_no(item)
            if not is_valid_table_no(table_no):
                continue
            if table_no in seen:
                continue
            seen.add(table_no)
            normalized.append(table_no)

    legacy_second_table_no = normalize_table_no(parsed.get('secondTableNo'))
    if not normalized and is_valid_table_no(legacy_second_table_no) and legacy_second_table_no not in seen:
        normalized.append(legacy_second_table_no)

    return normalized


def remap_timer_notes_table_nos(raw_notes, remap):
    text = str(raw_notes or '').strip()
    if not text:
        return raw_notes, False

    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return raw_notes, False

    if not isinstance(parsed, dict):
        return raw_notes, False

    changed = False
    next_extra_table_nos = []
    seen = set()

    source_extra = parsed.get('extraTableNos')
    if isinstance(source_extra, list):
        for item in source_extra:
            normalized = normalize_table_no(item)
            mapped = remap.get(normalized, normalized)
            if not is_valid_table_no(mapped):
                continue
            if mapped in seen:
                continue
            seen.add(mapped)
            next_extra_table_nos.append(mapped)
        if next_extra_table_nos != source_extra:
            parsed['extraTableNos'] = next_extra_table_nos
            changed = True

    expected_second_table_no = next_extra_table_nos[0] if next_extra_table_nos else ''
    if str(parsed.get('secondTableNo') or '') != expected_second_table_no:
        parsed['secondTableNo'] = expected_second_table_no
        changed = True

    if not changed:
        return raw_notes, False

    return json.dumps(parsed, ensure_ascii=False), True

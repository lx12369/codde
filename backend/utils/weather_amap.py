import json
import re
import threading
from datetime import datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from flask import current_app


class WeatherServiceError(Exception):
    def __init__(self, message, status_code=502):
        super().__init__(message)
        self.status_code = status_code


_CACHE_LOCK = threading.Lock()
_CACHE_EXPIRES_AT = None
_CACHE_DATA = None
_CACHED_ADCODE = ''
_QUOTA_MONTH = ''
_QUOTA_USED = 0


def _to_float(value):
    try:
        parsed = float(value)
        return parsed if parsed == parsed else None
    except (TypeError, ValueError):
        return None


def _parse_wind_power_to_speed(value):
    text = str(value or '').strip()
    if not text:
        return None
    match = re.search(r'(\d+(?:\.\d+)?)', text)
    if not match:
        return None
    return _to_float(match.group(1))


def _build_url(base_host, path, params):
    base = str(base_host or '').rstrip('/')
    return f'{base}{path}?{urlencode(params)}'


def _check_and_consume_quota():
    global _QUOTA_MONTH, _QUOTA_USED

    monthly_quota = max(1, int(current_app.config.get('AMAP_WEATHER_MONTHLY_QUOTA', 5000)))
    current_month = datetime.utcnow().strftime('%Y-%m')
    if _QUOTA_MONTH != current_month:
        _QUOTA_MONTH = current_month
        _QUOTA_USED = 0

    if _QUOTA_USED >= monthly_quota:
        raise WeatherServiceError('天气服务月配额已达上限，请稍后再试', 503)

    _QUOTA_USED += 1


def _http_get_json(url, timeout_seconds):
    _check_and_consume_quota()
    try:
        with urlopen(url, timeout=timeout_seconds) as response:
            body = response.read().decode('utf-8')
            return json.loads(body)
    except HTTPError as error:
        raise WeatherServiceError(f'天气服务请求失败（HTTP {error.code}）', 502) from error
    except URLError as error:
        raise WeatherServiceError('天气服务连接失败，请稍后重试', 504) from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WeatherServiceError('天气服务返回数据格式异常', 502) from error


def _http_get_json_without_quota(url, timeout_seconds):
    try:
        with urlopen(url, timeout=timeout_seconds) as response:
            body = response.read().decode('utf-8')
            return json.loads(body)
    except HTTPError as error:
        raise WeatherServiceError(f'天气服务请求失败（HTTP {error.code}）', 502) from error
    except URLError as error:
        raise WeatherServiceError('天气服务连接失败，请稍后重试', 504) from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WeatherServiceError('天气服务返回数据格式异常', 502) from error


def _resolve_adcode(api_host, api_key, location_text, timeout_seconds):
    url = _build_url(
        api_host,
        '/v3/geocode/geo',
        {
            'address': location_text,
            'key': api_key
        }
    )
    payload = _http_get_json(url, timeout_seconds)
    if payload.get('status') != '1':
        raise WeatherServiceError(payload.get('info') or '天气服务地区解析失败', 502)

    geocodes = payload.get('geocodes') or []
    if not geocodes:
        raise WeatherServiceError('未找到目标地区编码，请检查地区配置', 502)

    adcode = str(geocodes[0].get('adcode') or '').strip()
    if not adcode:
        raise WeatherServiceError('地区编码解析失败', 502)
    return adcode


def _fetch_live_weather(api_host, api_key, adcode, timeout_seconds):
    url = _build_url(
        api_host,
        '/v3/weather/weatherInfo',
        {
            'city': adcode,
            'key': api_key,
            'extensions': 'base'
        }
    )
    payload = _http_get_json(url, timeout_seconds)
    if payload.get('status') != '1':
        raise WeatherServiceError(payload.get('info') or '实时天气数据获取失败', 502)

    lives = payload.get('lives') or []
    if not lives:
        raise WeatherServiceError('实时天气数据为空', 502)
    return lives[0]


def _fetch_forecast_weather(api_host, api_key, adcode, timeout_seconds):
    url = _build_url(
        api_host,
        '/v3/weather/weatherInfo',
        {
            'city': adcode,
            'key': api_key,
            'extensions': 'all'
        }
    )
    payload = _http_get_json(url, timeout_seconds)
    if payload.get('status') != '1':
        raise WeatherServiceError(payload.get('info') or '天气预报数据获取失败', 502)

    forecasts = payload.get('forecasts') or []
    if not forecasts:
        raise WeatherServiceError('天气预报数据为空', 502)

    casts = forecasts[0].get('casts') or []
    if not casts:
        raise WeatherServiceError('当日天气预报数据为空', 502)
    return casts[0]


def _build_weather_result(live_data, forecast_data):
    city_label = str(current_app.config.get('AMAP_WEATHER_CITY_LABEL') or '').strip() or '宁波市鄞州区下应街道'
    temperature = _to_float(live_data.get('temperature'))

    return {
        'city': city_label,
        'weather': live_data.get('weather') or forecast_data.get('dayweather') or '--',
        'temperature': temperature,
        'feels_like': temperature,
        'temp_min': _to_float(forecast_data.get('nighttemp')),
        'temp_max': _to_float(forecast_data.get('daytemp')),
        'humidity': _to_float(live_data.get('humidity')),
        'wind_direction': live_data.get('winddirection') or forecast_data.get('daywind') or '--',
        'wind_speed': _parse_wind_power_to_speed(live_data.get('windpower') or forecast_data.get('daypower')),
        'observed_at': live_data.get('reporttime') or datetime.utcnow().isoformat(),
        'provider': 'Amap Weather'
    }


def _map_open_meteo_weather_text(weather_code):
    code = int(weather_code) if isinstance(weather_code, (int, float)) else None
    weather_map = {
        0: '晴',
        1: '晴间多云',
        2: '多云',
        3: '阴',
        45: '雾',
        48: '雾凇',
        51: '小毛雨',
        53: '毛雨',
        55: '大毛雨',
        56: '冻毛雨',
        57: '强冻毛雨',
        61: '小雨',
        63: '中雨',
        65: '大雨',
        66: '冻雨',
        67: '强冻雨',
        71: '小雪',
        73: '中雪',
        75: '大雪',
        77: '冰粒',
        80: '阵雨',
        81: '强阵雨',
        82: '暴雨',
        85: '阵雪',
        86: '强阵雪',
        95: '雷暴',
        96: '雷暴伴小冰雹',
        99: '雷暴伴强冰雹'
    }
    return weather_map.get(code, '未知')


def _load_weather_from_open_meteo(timeout_seconds, location_text):
    city_label = str(current_app.config.get('AMAP_WEATHER_CITY_LABEL') or '').strip() or '宁波市鄞州区下应街道'
    geocode_url = _build_url(
        'https://geocoding-api.open-meteo.com',
        '/v1/search',
        {
            'name': location_text,
            'count': 1,
            'language': 'zh',
            'format': 'json'
        }
    )
    geocode_payload = _http_get_json_without_quota(geocode_url, timeout_seconds)
    results = geocode_payload.get('results') or []
    if not results:
        raise WeatherServiceError('天气服务地区解析失败', 502)

    result = results[0]
    latitude = result.get('latitude')
    longitude = result.get('longitude')
    if latitude is None or longitude is None:
        raise WeatherServiceError('天气服务地区坐标解析失败', 502)

    forecast_url = _build_url(
        'https://api.open-meteo.com',
        '/v1/forecast',
        {
            'latitude': latitude,
            'longitude': longitude,
            'timezone': 'auto',
            'forecast_days': 1,
            'current': 'temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m,wind_direction_10m',
            'daily': 'temperature_2m_max,temperature_2m_min'
        }
    )
    forecast_payload = _http_get_json_without_quota(forecast_url, timeout_seconds)
    current = forecast_payload.get('current') or {}
    daily = forecast_payload.get('daily') or {}
    temp_max_arr = daily.get('temperature_2m_max') or []
    temp_min_arr = daily.get('temperature_2m_min') or []

    city_parts = [result.get('name'), result.get('admin1'), result.get('country')]
    city = ' '.join([str(part).strip() for part in city_parts if str(part or '').strip()]) or city_label
    weather_code = current.get('weather_code')

    return {
        'city': city,
        'weather': _map_open_meteo_weather_text(weather_code),
        'temperature': _to_float(current.get('temperature_2m')),
        'feels_like': _to_float(current.get('apparent_temperature')),
        'temp_min': _to_float(temp_min_arr[0]) if temp_min_arr else None,
        'temp_max': _to_float(temp_max_arr[0]) if temp_max_arr else None,
        'humidity': _to_float(current.get('relative_humidity_2m')),
        'wind_direction': str(current.get('wind_direction_10m') or '--'),
        'wind_speed': _to_float(current.get('wind_speed_10m')),
        'observed_at': current.get('time') or datetime.utcnow().isoformat(),
        'provider': 'Open-Meteo'
    }


def _load_weather_from_provider():
    global _CACHED_ADCODE

    api_key = str(current_app.config.get('AMAP_WEATHER_KEY') or '').strip()
    timeout_seconds = int(current_app.config.get('AMAP_WEATHER_TIMEOUT_SECONDS', 5))
    location_text = current_app.config.get('AMAP_WEATHER_LOCATION', '宁波市鄞州区下应街道')

    if not api_key:
        return _load_weather_from_open_meteo(timeout_seconds, location_text)

    api_host = current_app.config.get('AMAP_WEATHER_API_HOST', 'https://restapi.amap.com')
    adcode = str(current_app.config.get('AMAP_WEATHER_ADCODE') or '').strip()

    if not adcode:
        adcode = _CACHED_ADCODE
    if not adcode:
        adcode = _resolve_adcode(api_host, api_key, location_text, timeout_seconds)
        _CACHED_ADCODE = adcode

    live_data = _fetch_live_weather(api_host, api_key, adcode, timeout_seconds)
    forecast_data = _fetch_forecast_weather(api_host, api_key, adcode, timeout_seconds)
    return _build_weather_result(live_data, forecast_data)


def get_xiaying_weather():
    global _CACHE_DATA, _CACHE_EXPIRES_AT

    cache_seconds = int(current_app.config.get('AMAP_WEATHER_CACHE_SECONDS', 300))
    now = datetime.utcnow()

    if _CACHE_DATA and _CACHE_EXPIRES_AT and now < _CACHE_EXPIRES_AT:
        return dict(_CACHE_DATA)

    with _CACHE_LOCK:
        now = datetime.utcnow()
        if _CACHE_DATA and _CACHE_EXPIRES_AT and now < _CACHE_EXPIRES_AT:
            return dict(_CACHE_DATA)

        weather_data = _load_weather_from_provider()
        _CACHE_DATA = dict(weather_data)
        _CACHE_EXPIRES_AT = now + timedelta(seconds=max(1, cache_seconds))
        return dict(_CACHE_DATA)

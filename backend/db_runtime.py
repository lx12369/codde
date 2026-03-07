import json
import os
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


DEFAULT_MYSQL_HOST = '127.0.0.1'
DEFAULT_MYSQL_PORT = 3306
DEFAULT_MYSQL_DATABASE = 'studio_system'
DEFAULT_MYSQL_USERNAME = 'root'
RUNTIME_APP_DIRNAME = 'StudioSystem'
RUNTIME_CONFIG_NAME = 'config.json'


def get_runtime_data_dir():
    data_dir = Path.home() / 'AppData' / 'Local' / RUNTIME_APP_DIRNAME
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_runtime_config_path():
    return get_runtime_data_dir() / RUNTIME_CONFIG_NAME


def default_runtime_db_config():
    return {
        'host': DEFAULT_MYSQL_HOST,
        'port': DEFAULT_MYSQL_PORT,
        'database': DEFAULT_MYSQL_DATABASE,
        'username': DEFAULT_MYSQL_USERNAME,
        'password': ''
    }


def load_runtime_db_config():
    config_path = get_runtime_config_path()
    if not config_path.exists():
        return None

    try:
        payload = json.loads(config_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None

    return payload if isinstance(payload, dict) else None


def save_runtime_db_config(config_data):
    config_path = get_runtime_config_path()
    merged = default_runtime_db_config()
    if isinstance(config_data, dict):
        merged.update(config_data)
    config_path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    return config_path


def ensure_runtime_db_config():
    config_data = load_runtime_db_config()
    if config_data:
        return get_runtime_config_path(), False
    return save_runtime_db_config(default_runtime_db_config()), True


def get_runtime_config_missing_fields(config_data, require_password=True):
    if not isinstance(config_data, dict):
        required_fields = ['host', 'port', 'database', 'username']
        if require_password:
            required_fields.append('password')
        return required_fields

    missing = []
    for key in ('host', 'port', 'database', 'username'):
        value = config_data.get(key)
        if value is None or str(value).strip() == '':
            missing.append(key)

    if require_password:
        password = config_data.get('password')
        if password is None or str(password) == '':
            missing.append('password')

    return missing


def normalize_mysql_settings(config_data=None, env=None):
    source = default_runtime_db_config()
    if isinstance(config_data, dict):
        source.update({
            'host': config_data.get('host', source['host']),
            'port': config_data.get('port', source['port']),
            'database': config_data.get('database', source['database']),
            'username': config_data.get('username', source['username']),
            'password': config_data.get('password', source['password'])
        })

    env = env or os.environ

    if env.get('MYSQL_HOST'):
        source['host'] = env.get('MYSQL_HOST')
    if env.get('MYSQL_PORT'):
        source['port'] = env.get('MYSQL_PORT')
    if env.get('MYSQL_DATABASE'):
        source['database'] = env.get('MYSQL_DATABASE')
    if env.get('MYSQL_USER'):
        source['username'] = env.get('MYSQL_USER')
    if env.get('MYSQL_PASSWORD') is not None:
        source['password'] = env.get('MYSQL_PASSWORD')

    try:
        port = int(source.get('port', DEFAULT_MYSQL_PORT))
    except (TypeError, ValueError):
        port = DEFAULT_MYSQL_PORT

    return {
        'host': str(source.get('host') or DEFAULT_MYSQL_HOST).strip() or DEFAULT_MYSQL_HOST,
        'port': port,
        'database': str(source.get('database') or DEFAULT_MYSQL_DATABASE).strip() or DEFAULT_MYSQL_DATABASE,
        'username': str(source.get('username') or DEFAULT_MYSQL_USERNAME).strip() or DEFAULT_MYSQL_USERNAME,
        'password': '' if source.get('password') is None else str(source.get('password'))
    }


def build_mysql_database_uri(config_data=None, env=None):
    settings = normalize_mysql_settings(config_data=config_data, env=env)
    username = quote_plus(settings['username'])
    password = quote_plus(settings['password'])
    host = settings['host']
    port = settings['port']
    database = settings['database']
    return f'mysql+pymysql://{username}:{password}@{host}:{port}/{database}?charset=utf8mb4'


def resolve_database_uri(prefer_runtime_config=False, env=None):
    env = env or os.environ
    direct_uri = str(env.get('DATABASE_URL') or '').strip()
    if direct_uri:
        return direct_uri

    runtime_config = load_runtime_db_config() if prefer_runtime_config else None
    if runtime_config:
        return build_mysql_database_uri(config_data=runtime_config, env=env)

    return build_mysql_database_uri(env=env)


def get_sqlalchemy_engine_options(database_uri):
    try:
        backend_name = make_url(database_uri).get_backend_name()
    except Exception:
        return {}

    if backend_name != 'mysql':
        return {}

    return {
        'pool_pre_ping': True,
        'pool_recycle': 3600
    }


def ensure_database_exists(database_uri):
    try:
        parsed = make_url(database_uri)
    except Exception:
        return

    if parsed.get_backend_name() != 'mysql' or not parsed.database:
        return

    db_name = parsed.database
    server_url = parsed.set(database=None)
    temp_engine = create_engine(server_url, pool_pre_ping=True)
    escaped_db_name = db_name.replace('`', '``')

    try:
        with temp_engine.connect() as connection:
            connection.execute(
                text(
                    f'CREATE DATABASE IF NOT EXISTS `{escaped_db_name}` '
                    'CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'
                )
            )
            connection.commit()
    finally:
        temp_engine.dispose()


def mysql_settings_from_database_uri(database_uri):
    parsed = make_url(database_uri)
    if parsed.get_backend_name() != 'mysql':
        return None

    return {
        'host': parsed.host or DEFAULT_MYSQL_HOST,
        'port': int(parsed.port or DEFAULT_MYSQL_PORT),
        'database': parsed.database or DEFAULT_MYSQL_DATABASE,
        'username': parsed.username or DEFAULT_MYSQL_USERNAME,
        'password': parsed.password or ''
    }

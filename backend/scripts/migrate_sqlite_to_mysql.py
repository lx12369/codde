import argparse
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import create_app
from db_runtime import (
    build_mysql_database_uri,
    get_runtime_config_path,
    load_runtime_db_config,
    mysql_settings_from_database_uri,
    normalize_mysql_settings,
    save_runtime_db_config
)
from utils.data_snapshot import export_snapshot_payload, restore_snapshot_payload


def parse_args():
    parser = argparse.ArgumentParser(description='Migrate SQLite data into MySQL.')
    parser.add_argument('--source', help='Source SQLite file path')
    parser.add_argument('--target-url', help='Target MySQL SQLAlchemy URL')
    parser.add_argument('--target-host', help='Target MySQL host')
    parser.add_argument('--target-port', type=int, help='Target MySQL port')
    parser.add_argument('--target-database', help='Target MySQL database name')
    parser.add_argument('--target-user', help='Target MySQL username')
    parser.add_argument('--target-password', help='Target MySQL password')
    parser.add_argument('--skip-write-runtime-config', action='store_true', help='Do not write desktop runtime config after migration')
    return parser.parse_args()


def resolve_source_sqlite_path(explicit_path=None):
    candidates = []
    if explicit_path:
        candidates.append(Path(explicit_path).expanduser())

    local_appdata = Path.home() / 'AppData' / 'Local' / 'StudioSystem' / 'app.db'
    candidates.extend([
        local_appdata,
        BASE_DIR / 'instance' / 'app.db',
        BASE_DIR / 'app.db'
    ])

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()

    checked = '\n'.join(str(path) for path in candidates)
    raise FileNotFoundError(f'未找到 SQLite 数据文件，请通过 --source 指定。已检查路径：\n{checked}')


def resolve_target_database_uri(args):
    if args.target_url:
        return args.target_url

    overrides = {}
    if args.target_host:
        overrides['host'] = args.target_host
    if args.target_port:
        overrides['port'] = args.target_port
    if args.target_database:
        overrides['database'] = args.target_database
    if args.target_user:
        overrides['username'] = args.target_user
    if args.target_password is not None:
        overrides['password'] = args.target_password

    runtime_config = load_runtime_db_config() or {}
    runtime_config.update(overrides)

    if runtime_config.get('password'):
        return build_mysql_database_uri(config_data=runtime_config)

    direct_uri = os.environ.get('DATABASE_URL')
    if direct_uri:
        return direct_uri

    env_settings = normalize_mysql_settings(config_data=runtime_config)
    if env_settings.get('password'):
        return build_mysql_database_uri(config_data=env_settings)

    raise RuntimeError('缺少 MySQL 目标连接信息。请提供 --target-url，或通过 --target-password / MYSQL_PASSWORD / 桌面配置文件补全密码。')


def build_runtime_config_from_target_uri(target_uri):
    settings = mysql_settings_from_database_uri(target_uri)
    if not settings:
        raise RuntimeError('目标数据库不是 MySQL，无法写入桌面运行配置。')
    return settings


def main():
    args = parse_args()
    source_path = resolve_source_sqlite_path(args.source)
    source_uri = f"sqlite:///{source_path.as_posix()}"
    target_uri = resolve_target_database_uri(args)

    print(f'源 SQLite: {source_path}')
    print(f'目标 MySQL: {target_uri}')

    source_app = create_app('production', database_uri=source_uri, init_database=False)
    with source_app.app_context():
        payload, source_stats = export_snapshot_payload()

    target_app = create_app('production', database_uri=target_uri, init_database=True)
    with target_app.app_context():
        restored_stats = restore_snapshot_payload(payload)

    print('源数据统计:')
    for key, value in source_stats.items():
        print(f'  {key}: {value}')

    print('恢复数据统计:')
    for key, value in restored_stats.items():
        print(f'  {key}: {value}')

    if not args.skip_write_runtime_config:
        runtime_config = build_runtime_config_from_target_uri(target_uri)
        config_path = save_runtime_db_config(runtime_config)
        print(f'桌面运行配置已写入: {config_path}')
    else:
        print(f'已跳过写入桌面运行配置，目标路径应为: {get_runtime_config_path()}')

    print('SQLite -> MySQL 迁移完成。')


if __name__ == '__main__':
    main()

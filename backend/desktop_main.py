import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path

from flask import jsonify, send_from_directory

from db_runtime import (
    build_mysql_database_uri,
    ensure_runtime_db_config,
    get_runtime_config_missing_fields,
    get_runtime_config_path,
    load_runtime_db_config
)


def _resolve_frontend_dist() -> Path:
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / 'web_dist'
    return Path(__file__).resolve().parent / 'web_dist'


def _configure_runtime_env() -> Path:
    config_path, created = ensure_runtime_db_config()
    runtime_config = load_runtime_db_config() or {}

    if 'DATABASE_URL' not in os.environ:
        missing_fields = get_runtime_config_missing_fields(runtime_config, require_password=True)
        if missing_fields:
            if created:
                print(f'已生成数据库配置模板：{config_path}')
            missing_text = ', '.join(missing_fields)
            raise RuntimeError(
                f'桌面版缺少 MySQL 连接配置，请编辑 {get_runtime_config_path()}，补全字段：{missing_text}'
            )
        os.environ['DATABASE_URL'] = build_mysql_database_uri(config_data=runtime_config)

    return config_path.parent


def _get_bind_host() -> str:
    host = str(os.environ.get('STUDIO_HOST', '0.0.0.0')).strip()
    return host or '0.0.0.0'


def _get_bind_port() -> int:
    raw_port = os.environ.get('STUDIO_PORT', '5000')
    try:
        port = int(raw_port)
    except (TypeError, ValueError):
        return 5000

    if port < 1 or port > 65535:
        return 5000
    return port


def _get_local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(('10.255.255.255', 1))
        ip = sock.getsockname()[0]
        if ip:
            return ip
    except OSError:
        pass
    finally:
        sock.close()
    return '127.0.0.1'


def _attach_spa_routes(app, dist_dir: Path) -> None:
    if not dist_dir.exists():
        return

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_spa(path: str):
        if path.startswith('api/'):
            return jsonify({'error': 'Not Found'}), 404

        file_path = dist_dir / path
        if path and file_path.exists() and file_path.is_file():
            return send_from_directory(str(dist_dir), path)

        return send_from_directory(str(dist_dir), 'index.html')


def main():
    _configure_runtime_env()
    from app import create_app

    app = create_app('production')
    dist_dir = _resolve_frontend_dist()
    _attach_spa_routes(app, dist_dir)

    host = _get_bind_host()
    port = _get_bind_port()
    local_url = f'http://127.0.0.1:{port}'
    lan_ip = _get_local_ip()
    lan_url = f'http://{lan_ip}:{port}'

    print(f'StudioSystem running at: {local_url}')
    if host == '0.0.0.0':
        print(f'LAN access URL: {lan_url}')

    threading.Timer(1.0, lambda: webbrowser.open(local_url)).start()
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == '__main__':
    main()

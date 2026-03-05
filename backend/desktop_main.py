import os
import sys
import threading
import webbrowser
import socket
from pathlib import Path

from flask import jsonify, send_from_directory


def _resolve_frontend_dist() -> Path:
    """Resolve bundled frontend dist directory for both dev and PyInstaller runtime."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "web_dist"
    return Path(__file__).resolve().parent / "web_dist"


def _configure_runtime_env() -> Path:
    """Persist runtime data in a stable per-user location."""
    data_dir = Path.home() / "AppData" / "Local" / "StudioSystem"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_file = data_dir / "app.db"
    os_db_uri = f"sqlite:///{db_file.as_posix()}"
    if "DATABASE_URL" not in os.environ:
        os.environ["DATABASE_URL"] = os_db_uri
    return data_dir


def _get_bind_host() -> str:
    host = str(os.environ.get("STUDIO_HOST", "0.0.0.0")).strip()
    return host or "0.0.0.0"


def _get_bind_port() -> int:
    raw_port = os.environ.get("STUDIO_PORT", "5000")
    try:
        port = int(raw_port)
    except (TypeError, ValueError):
        return 5000

    if port < 1 or port > 65535:
        return 5000
    return port


def _get_local_ip() -> str:
    # Derive LAN IP without external dependency; fallback to localhost.
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("10.255.255.255", 1))
        ip = sock.getsockname()[0]
        if ip:
            return ip
    except OSError:
        pass
    finally:
        sock.close()
    return "127.0.0.1"


def _attach_spa_routes(app, dist_dir: Path) -> None:
    if not dist_dir.exists():
        return

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_spa(path: str):
        if path.startswith("api/"):
            return jsonify({"error": "Not Found"}), 404

        file_path = dist_dir / path
        if path and file_path.exists() and file_path.is_file():
            return send_from_directory(str(dist_dir), path)

        return send_from_directory(str(dist_dir), "index.html")


def main():
    _configure_runtime_env()
    from app import create_app

    app = create_app("production")
    dist_dir = _resolve_frontend_dist()
    _attach_spa_routes(app, dist_dir)

    host = _get_bind_host()
    port = _get_bind_port()
    local_url = f"http://127.0.0.1:{port}"
    lan_ip = _get_local_ip()
    lan_url = f"http://{lan_ip}:{port}"

    print(f"StudioSystem running at: {local_url}")
    if host == "0.0.0.0":
        print(f"LAN access URL: {lan_url}")

    threading.Timer(1.0, lambda: webbrowser.open(local_url)).start()
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()

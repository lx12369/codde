import os
import sys
import threading
import webbrowser
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

    url = "http://127.0.0.1:5000"
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()

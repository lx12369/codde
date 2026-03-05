# Repository Guidelines

## Project Structure & Module Organization
- `frontend/`: Vue 3 + Vite client app. Main code is in `frontend/src/`:
  - `views/` page modules (`Dashboard.vue`, `Customers.vue`, etc.)
  - `api/index.js` Axios API layer
  - `router/index.js` route guards
  - `stores/index.js` Pinia stores
  - `utils/` shared helpers (for example, consumption calculation)
- `backend/`: Flask API and desktop entrypoint:
  - `app.py` app factory + blueprint registration
  - `routes/` API endpoints by domain
  - `models/` SQLAlchemy models and DB initialization
  - `utils/` auth, decorators, response helpers
  - `instance/` runtime SQLite files
- Generated artifacts live in `frontend/dist/`, `backend/build/`, `backend/dist/`, and `release/`; do not edit these directly.

## Build, Test, and Development Commands
- `cd frontend && npm install`: install frontend dependencies.
- `cd frontend && npm run dev`: start Vite at `http://localhost:3000` (proxies `/api` to `http://localhost:5000`).
- `cd backend && ..\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt`: install backend dependencies.
- `cd backend && ..\\.venv\\Scripts\\python.exe app.py`: run Flask API locally on port `5000`.
- `cd frontend && npm run build`: create production frontend bundle.
- `cd backend && .\\build_exe.ps1`: build desktop EXE with PyInstaller (uses frontend dist output).

## Coding Style & Naming Conventions
- Python: PEP 8, 4-space indentation, `snake_case` functions/variables, `PascalCase` classes.
- Vue/JavaScript: 2-space indentation, single quotes, no semicolons, `PascalCase.vue` component filenames.
- Follow existing API and ID patterns: route names like `/api/active-timers`, IDs like `C001`, `A001`, `T001`.

## Testing Guidelines
- No dedicated automated test suite is committed yet.
- Before opening a PR, run smoke tests across key flows: login, customer CRUD, recharge/consumption, active timers, dashboard stats/charts.
- For changed files, run quick syntax checks (example: `python -m py_compile backend\\routes\\customers.py`).
- New tests should go in `backend/tests/` (API) and `frontend/src/__tests__/` (UI/unit).

## Commit & Pull Request Guidelines
- Use Conventional Commits (`feat:`, `fix:`, `chore:`, etc.); current history includes `chore: initial commit`.
- Keep each commit focused on one logical change.
- PRs should include: purpose, impacted paths, verification steps run, and screenshots/GIFs for UI changes.

## Security & Configuration Tips
- Configure `SECRET_KEY`, `JWT_SECRET_KEY`, and `DATABASE_URL` via environment variables outside development.
- Do not commit local DB files, tokens, `.env` secrets, or generated build outputs.

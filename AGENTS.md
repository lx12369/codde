# Repository Guidelines

## Project Structure & Module Organization
- `frontend/`: Vue 3 + Vite client. Main code lives in `frontend/src/`:
  - `views/` page modules such as `Dashboard.vue`, `Employees.vue`, `Billing.vue`
  - `api/` Axios requests
  - `router/` route guards
  - `stores/` Pinia state
  - `utils/` shared helpers
- `backend/`: Flask API and desktop packaging entry:
  - `app.py` app factory
  - `routes/` domain endpoints
  - `models/` SQLAlchemy models and init logic
  - `utils/` auth, roles, audit, backup helpers
  - `scripts/` migration scripts
- Generated output should not be edited directly: `frontend/dist/`, `backend/build/`, `backend/dist/`, `release/`.

## Build, Test, and Development Commands
- `cd frontend && npm run dev`: start the frontend at `http://localhost:3000`.
- `cd frontend && npm run build`: build the production frontend bundle.
- `cd backend && ..\.venv\Scripts\python.exe app.py`: run the Flask API locally on port `5000`.
- `python -m py_compile backend\routes\employees.py`: quick syntax validation for changed Python files.
- `cd backend && .\build_exe.ps1`: build the desktop EXE with PyInstaller.

## Coding Style & Naming Conventions
- Python: PEP 8, 4-space indentation, `snake_case` for functions and variables, `PascalCase` for classes.
- Vue/JavaScript: 2-space indentation, single quotes, no semicolons, `PascalCase.vue` component names.
- Keep API and ID conventions consistent, for example `/api/active-timers`, `C001`, `T001`, `A001`.
- Prefer focused edits; do not hand-edit generated files.

## Testing Guidelines
- No full automated test suite is committed yet; use targeted validation.
- For backend changes, run `python -m py_compile` on touched modules.
- For frontend changes, run `cd frontend && npm run build`.
- Smoke-test key flows before merging: login, employee management, customer CRUD, transactions, active timers, billing rules, data management.

## Commit & Pull Request Guidelines
- Follow Conventional Commits: `feat:`, `fix:`, `chore:`, `docs:`.
- Keep each commit scoped to one logical change.
- PRs should include:
  - purpose and impacted paths
  - validation steps run
  - screenshots for UI changes
  - deployment notes if backend config or database behavior changed

## Security & Configuration Tips
- Do not commit `.env`, database files, tokens, or build artifacts.
- Production database uses MySQL via `DATABASE_URL`.
- Zip-based server deploys must preserve `backend/.env`, `backend/.venv`, and `backend/instance`.

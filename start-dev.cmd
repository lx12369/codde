@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Missing Python runtime: .venv\Scripts\python.exe
  echo Backend dependencies are not ready.
  pause
  exit /b 1
)

if not exist "frontend\node_modules" (
  echo [ERROR] Missing frontend dependencies: frontend\node_modules
  echo Run npm install in the frontend directory first.
  pause
  exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] npm was not found in PATH.
  pause
  exit /b 1
)

echo Starting backend and frontend from:
echo %CD%
echo.

start "Codde Backend" cmd /k "cd /d %CD% && .venv\Scripts\python.exe backend\app.py"
start "Codde Frontend" cmd /k "cd /d %CD%\frontend && call npm run dev"

echo Backend window: Codde Backend
echo Frontend window: Codde Frontend
echo Frontend address: http://localhost:3000
echo.
echo Close the opened windows to stop the services.
pause

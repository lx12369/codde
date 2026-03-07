@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Missing Python runtime: .venv\Scripts\python.exe
  echo Please install backend dependencies first.
  pause
  exit /b 1
)

echo Starting backend from:
echo %CD%
echo.

".venv\Scripts\python.exe" backend\app.py

echo.
echo Backend process exited.
pause

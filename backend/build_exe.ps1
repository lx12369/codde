param(
  [string]$PythonExe = "C:\Users\PC\Desktop\codde\.venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"

Write-Host "1/3 构建前端..."
Push-Location "..\frontend"
npm run build
Pop-Location

Write-Host "2/3 安装打包依赖..."
& $PythonExe -m pip install pyinstaller

Write-Host "3/3 打包 EXE..."
& $PythonExe -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --name StudioSystem `
  desktop_main.py `
  --add-data "..\frontend\dist;web_dist" `
  --add-data ".\data;data"

Write-Host "完成：backend\dist\StudioSystem.exe"

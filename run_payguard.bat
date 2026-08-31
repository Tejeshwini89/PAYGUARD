@echo off
setlocal
cd /d "%~dp0"
if not exist "backend\.venv\Scripts\python.exe" (
  echo Creating virtual environment...
  py -3.13 -m venv backend\.venv
  if errorlevel 1 exit /b 1
  echo Installing dependencies...
  backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
  if errorlevel 1 exit /b 1
)
echo Starting PAYGUARD at http://127.0.0.1:8000
backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload

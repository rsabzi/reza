@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo ERROR: Run setup.bat first. & exit /b 1)
if not exist "frontend\node_modules" (echo ERROR: Run setup.bat first. & exit /b 1)
if "%APP_PORT%"=="" set APP_PORT=8000

set ENV_ARG=
if exist ".env" set ENV_ARG=--env-file .env

echo Building current Dashboard assets...
call npm run build --prefix frontend --silent || exit /b 1

echo Starting unified Agent Core Dashboard and API...
start "Agent Core Dashboard + API" /D "%CD%" cmd /k .venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 0.0.0.0 --port %APP_PORT% %ENV_ARG%
echo Dashboard: http://127.0.0.1:%APP_PORT%
echo API docs: http://127.0.0.1:%APP_PORT%/docs
echo One origin, one process; no browser proxy is required.
endlocal

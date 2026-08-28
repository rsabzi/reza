@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo [1/7] Checking Python 3.10+...
where py >nul 2>nul || (echo ERROR: Python launcher was not found. & exit /b 1)
py -3 -c "import sys; assert sys.version_info >= (3,10), 'Python 3.10+ is required'; print('      Python', sys.version.split()[0], 'OK')" || exit /b 1

echo [2/7] Checking Node.js and npm...
where node >nul 2>nul || (echo ERROR: Node.js was not found. & exit /b 1)
where npm >nul 2>nul || (echo ERROR: npm was not found. & exit /b 1)
node -e "const m=+process.versions.node.split('.')[0];if(m<20)throw Error('Node.js 20+ is required');console.log('      Node.js '+process.versions.node+' OK')" || exit /b 1

echo [3/7] Creating Python virtual environment...
if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv || exit /b 1

echo [4/7] Installing Backend dependencies...
.venv\Scripts\python.exe -m pip install --disable-pip-version-check --quiet --upgrade pip || exit /b 1
.venv\Scripts\python.exe -m pip install --disable-pip-version-check --quiet -r backend\requirements.txt || exit /b 1

echo [5/7] Installing Frontend dependencies from lockfile...
call npm ci --prefix frontend --no-audit --no-fund --silent || exit /b 1

echo [6/7] Building unified Dashboard assets...
call npm run build --prefix frontend --silent || exit /b 1

echo [7/7] Preparing local configuration...
if not exist ".env" copy /Y ".env.example" ".env" >nul

echo.
echo Setup complete.
echo Start both services with: start_app.bat
echo Dashboard: http://127.0.0.1:8000
echo API docs: http://127.0.0.1:8000/docs
echo Gemini: open Dashboard Settings to securely add and validate your key.
endlocal

@echo off
setlocal
cd /d "%~dp0"
if "%AIGC_INSTALL_DEPENDENCIES%"=="1" (
  python -m pip install -r requirements.txt
)
if "%AIGC_WEBAPP_HOST%"=="" set AIGC_WEBAPP_HOST=127.0.0.1
if "%PORT%"=="" set PORT=8000
uvicorn src.webapp.app:app --host %AIGC_WEBAPP_HOST% --port %PORT%
pause

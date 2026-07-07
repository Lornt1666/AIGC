@echo off
setlocal
cd /d "%~dp0"
if "%AIGC_INSTALL_DEPENDENCIES%"=="1" (
  python -m pip install -r requirements.txt
)
uvicorn src.webapp.app:app --host 0.0.0.0 --port 8000
pause

@echo off
setlocal
cd /d "%~dp0"
if not "%AIGC_SKIP_DEPENDENCY_INSTALL%"=="1" (
  python -m pip install -r requirements.txt
)
python -m streamlit run src\dashboard\operator_cockpit_app.py
pause
